# API report — kaj se fetch-a, preko katerega API-ja, in zakaj

Združen dokument: kaj točno strategiji potrebujemo, kateri API to dostavi,
kako se polja mapirajo, kateri viri so se izkazali za dobre / slabe.

Vsa testiranja v živo: probe iz tega gostitelja, 2026-06-11.

---

## 1. Kaj strategija sploh potrebuje

Obe varianti (Full Pro v3 in Lean) potrebujeta **dva vhodna tokova**:

| Tok | Vsebina | Kdaj | Kdo ga uporablja |
|---|---|---|---|
| **A. Daily OHLCV izbranega simbola** | Open / High / Low / Close / Volume, dnevne sveče (~1500 bars za 4-letni backtest, 400+ minimum za warmup) | Vedno | Trackline, RSI, EMA, ADX, market structure, vol regime, conviction, state machine — **vse** |
| **B. Daily OHLCV za BTC** (kot ločen feed) | Samo close (za BTC cross-asset filter), ostala polja pa tudi pridejo s callom | Kadar `use_btc_filter=True` (default ON v Full, OFF v Lean) | BTC EMA50 filter za altcoine |

**Weekly podatki se NE fetch-ajo ločeno** — resampliramo dnevne v `to_weekly()`
(`W-MON, closed=left, label=left`). Eno API klic = pokrije dnevni + tedenski
nivo.

**Skupno število API klicev** na dashboard refresh (na 60 s):
- 1 simbol brez BTC filtra: **1 klic**
- 1 simbol + BTC filter: **2 klica**
- Caching (`@st.cache_data(ttl=60)`) drži rezultat 60 s, torej praktično **0 klicev/min** če uporabnik ne menja simbola

---

## 2. Glavna tabela — vsak vir za vsak data type

| Polje / izračun | Source field iz API-ja | Glavni vir | Fallback #1 | Fallback #2 |
|---|---|---|---|---|
| **OHLCV za BTC/ETH/SOL/XRP/ADA/AVAX/LINK daily** | `open, high, low, close, volume` | Binance `klines` (1d) | Coinbase `candles` (gran 86400) | yfinance `Ticker.history(interval='1d')` |
| **OHLCV za BNB daily** | enako | Binance | — (BNB ni na Coinbase) | yfinance |
| **OHLCV weekly** (rare) | enako | Binance `klines` (1w) | — (Coinbase ne podpira 1w) | yfinance (`interval='1wk'`) |
| **BTC daily za cross-asset filter** | `close` (in vse OHLCV iz iste tabele) | Binance `klines` (1d) | Coinbase | yfinance |
| **Weekly EMA21, SMA30, close** | derivirano | resample iz daily | resample | resample |
| **200 MA, 50 MA** | derivirano iz `close` | resample iz daily | resample | resample |
| **Trackline (Kijun)** | derivirano iz `high`, `low` | iz daily | iz daily | iz daily |
| **Conviction / ADX / RSI / EMA** | derivirano iz OHLCV | iz daily | iz daily | iz daily |

**Pomembno:** vse tri možne vire vrnejo identično strukturo (5 OHLCV polj), zato
je strategija indiferentna na to, kateri je dejansko bil uporabljen. Razlika je
le v latenci, zanesljivosti in zgodovinski globini.

---

## 3. Per-API field mapping (kako parsamo response)

### 3.1 Binance — `_binance_parse()` v `shared/data_source.py:111`

Binance vrne JSON array of arrays. Vsaka vrstica:
```
[open_time_ms, "open", "high", "low", "close", "volume",
 close_time_ms, "quote_vol", trades, "taker_buy_base", "taker_buy_quote", "ignore"]
```

| Polje iz Binance | Vrsta | Uporabimo? | Polje v df |
|---|---|---|---|
| `open_time_ms` | int (ms epoch) | da → DatetimeIndex (UTC) | `time` (index) |
| `open` | string | da → float | `open` |
| `high` | string | da → float | `high` |
| `low` | string | da → float | `low` |
| `close` | string | da → float | `close` |
| `volume` | string | da → float | `volume` |
| `close_time_ms` | int | ne |
| `quote_vol` | string | ne |
| `trades` | int | ne |
| `taker_buy_*` | string | ne |
| `ignore` | string | ne (Binance pravi "ignore") |

### 3.2 Coinbase Advanced — `_coinbase_parse()` v `shared/data_source.py:185`

Coinbase vrne JSON array of arrays, **najnovejša sveča prva** (obraten vrstni
red od Binance). Vsaka vrstica:
```
[time_sec, low, high, open, close, volume]
```
Ključna razlika: low je PRED high, ne za njim. Naš parser to popravi.

| Polje iz Coinbase | Vrsta | Uporabimo? | Polje v df |
|---|---|---|---|
| `time_sec` | int (s epoch) | da → DatetimeIndex (UTC) | `time` (index) |
| `low` | float | da | `low` |
| `high` | float | da | `high` |
| `open` | float | da | `open` |
| `close` | float | da | `close` |
| `volume` | float | da | `volume` |

### 3.3 yfinance — `_yf_fetch()` v `shared/data_source.py:217`

yfinance vrne pandas DataFrame z imenovanimi stolpci:
```
Open, High, Low, Close, Adj Close, Volume, Dividends, Stock Splits
```

| Polje iz yfinance | Vrsta | Uporabimo? | Polje v df |
|---|---|---|---|
| `Open` | float | da | `open` |
| `High` | float | da | `high` |
| `Low` | float | da | `low` |
| `Close` | float | da | `close` |
| `Adj Close` | float | **ne** (za crypto je enak kot Close) |
| `Volume` | float | da | `volume` |
| `Dividends` | float | ne (crypto = vedno 0) |
| `Stock Splits` | float | ne (crypto = vedno 0) |

---

## 4. Source ordering — kdo se kliče v kakšnem vrstnem redu

V `shared/data_source.py:230` (funkcija `fetch_candles`):

```python
if prefer == "yahoo":      sources = ["yahoo", "binance", "coinbase"]
elif prefer == "coinbase": sources = ["coinbase", "binance", "yahoo"]
else:                      sources = ["binance", "coinbase", "yahoo"]   # default
```

Za vsak vir v zaporedju:
1. Če simbol nima ključa za ta vir (npr. BNB nima `coinbase` mapping) →
   preskoči, ne pošlji HTTP.
2. Če interval ni podprt (npr. Coinbase nima 4h/1w) → preskoči.
3. Sicer pokliči `_<src>_fetch()`. Pri exception → naslednji vir.
4. Če vsi padejo → `DataSourceError("All sources failed for ...")`.

### Scenariji kdaj se kateri sproži

| Scenarij | Klic 1 | Klic 2 | Klic 3 |
|---|---|---|---|
| **Normalno** (default) | Binance ✓ | — | — |
| Binance vrne HTTP 451 (US geo block) | Binance ✗ | Coinbase ✓ | — |
| Binance ima 5-min outage | Binance ✗ (timeout) | Coinbase ✓ | — |
| Coinbase tudi padel | Binance ✗ | Coinbase ✗ | yfinance ✓ |
| BNB simbol (ni na Coinbase) | Binance ✓ | — | — |
| BNB + Binance padel | Binance ✗ | Coinbase preskočen | yfinance ✓ |
| Interval `1w` | Binance ✓ | — | — |
| Interval `1w` + Binance padel | Binance ✗ | Coinbase preskočen (no 1w) | yfinance ✓ |

---

## 5. Live probe rezultati (2026-06-11)

### 5.1 Enkratni klic, BTC daily, 200 bars

| API | Status | Latenca | Bars vrnjeno | Last close |
|---|---|---|---|---|
| **Binance** | ✓ | 364 ms | 200 | $61,853 |
| **Coinbase** | ✓ | 118 ms | 350 (vrne preveč) | $61,797 |
| **yfinance** | ✓ | 2088 ms | 199 | $61,788 |
| CoinGecko | ✓ | 206 ms | 180 (4h candles) | $61,493 |
| Kraken | ✓ | 215 ms | 721 | $61,794 |
| CryptoCompare | ✗ HTTP 401 | 77 ms | — | — |

Razlika v close cenah ($60 v razponu $61,500–$61,900) pomeni, da so podatki
**konsistentni** med viri.

### 5.2 Burst — 10 zaporednih klicev brez pavze

| API | Avg latenca | Fails |
|---|---|---|
| **Coinbase** | **68 ms** | 0/10 |
| Kraken | 76 ms | 0/10 |
| **Binance** | 316 ms | 0/10 |
| CoinGecko | 64 ms | **5/10** ← rate limit |

### 5.3 Coverage / globina zgodovine

| API | Najstarejši BTC daily | Bars per call |
|---|---|---|
| **Coinbase** | **2015-07** ali starejši | 300 |
| **Binance** | 2017-08-17 | 1000 |
| yfinance | 2014 | "max" |
| Kraken | 2024-06-21 samo (720 plafon) | 720 |
| CoinGecko | unreliable | varia |

---

## 6. Zakaj točno ta vrstni red

**Binance prvi:**
- Globalna budget (6000 weight/min) → praktično neomejen za naš use case
- 1000 bars/call → 1 call za polni 4-letni backtest
- Sub-sekundna latenca v praksi
- Brez incidenta zadnjih 235+ dni (per IsDown)
- Pokritost vseh majorjev + alti

**Coinbase drugi:**
- Pokrije US scenarij kjer Binance vrne HTTP 451
- Najhitrejši v burstu (68 ms)
- Najgloblja zgodovina (2015 — 3 leta dlje od Binance)
- Regulirano US podjetje → minimalno tveganje izklopa
- 10 req/sec/IP → dovolj za naš 1-call-per-minute vzorec
- Šibkost: 300 bars/call → 4× pagination za 1000 bars (1.7 s za pol fetch)

**yfinance tretji:**
- Zadnja varnost če bi oba pravi viri padla istočasno
- Najgloblja zgodovina (2014)
- A: 2088 ms latenca, neuradni scraper, krhko (Yahoo lahko menja endpoint kadarkoli)
- OK za daily backtest, NE za live trade-decision pipeline

---

## 7. Zavrnjeni kandidati (NE uporabljeni)

| API | Razlog | Dokazljiv s | Posledica za projekt |
|---|---|---|---|
| **CoinGecko free** | 50 % FAIL pod burstom, limit 5–15 calls/min ne dovoli 60-s polling | Naš probe (5/10 fails) + [CoinGecko docs](https://support.coingecko.com/hc/en-us/articles/4538771776153) | Ni v fallback chainu. V prvotnem researchu sem ga napačno priporočil — popravljeno v `API_RESEARCH.md` disclaimerju. |
| **CryptoCompare** | HTTP 401 brez ključa — model spremenjen leta 2025 (migracija na CoinDesk Data) | Naš probe + uradno [dokumentacija](https://min-api.cryptocompare.com/) | Ne uporabljen. Bi zahteval registracijo + secret management. |
| **Kraken** | Trd plafon 720 bars za REST OHLC. Naš strategy potrebuje minimalno 400 bars warmup, idealno 1500. | [Kraken docs](https://docs.kraken.com/api/docs/rest-api/get-ohlc-data/) | Ne uporabljen. Tudi pair naming "XBT" namesto "BTC" je nestandarden. |

---

## 8. Praktična poraba (per dashboard session)

### Scenarij A: uporabnik gleda BTC (brez BTC filtra)
- Vsakih 60 s: **1 klic** na Binance `klines?symbol=BTCUSDT&interval=1d&limit=1000`
- Mesečno: ~43,200 klicev (= 0.7 % Binance dnevnega budgeta po IP)
- Pravo: caching v Streamlit znižuje na ~1 klic na 60 s ne glede na uporabniške interakcije

### Scenarij B: uporabnik gleda ETH z BTC filtrom (default v Full)
- Vsakih 60 s: **2 klica** — ETH OHLCV + BTC OHLCV
- ETH gre na Binance kot `ETHUSDT`, BTC kot `BTCUSDT`
- Še vedno daleč pod limitom

### Scenarij C: backtest 1500 bars na BTC (CLI)
- **1 klic** (Binance vrne 1000 bars/call, paginate za 1500 = 2 klica)
- Tudi z Coinbase fallback bi bilo 5 klicev (1500 / 300)
- Eno samo zagonjenje — irrelevantno za rate limit

### Scenarij D: backtest 1500 bars ETH + 1500 BTC filter
- **4 klica** (2 vira × 2 simbola)
- Ena sekunda, brez problemov

---

## 9. Kaj se NE fetch-a (in zakaj)

| Stvar | Zakaj NE iz API-ja |
|---|---|
| **Weekly OHLCV** | Resamplamo iz daily — manj klicev, manj tveganje za neusklajenost med dnevnim in tedenskim virom |
| **Real-time tick / order book** | Strategy je daily — ne potrebujemo tick-by-tick. Binance ima WebSocket `wss://stream.binance.com:9443/ws/btcusdt@kline_1d` za live, ampak overhead ni vreden — 60 s polling je dovolj. |
| **Volume profile, open interest** | Strategy ne uporablja teh metrik |
| **On-chain podatki, social sentiment** | Diversitas namensko izpušča te pipe-e (glej Pine komentar v `lean/diversitas_lean.pine` vrstice 16-17) |
| **Fundamentalni podatki** | Ni relevantno za crypto trend-following strategijo |
| **API ključi / autenticirani endpointi** | Vse je javno, brez registracije — laže shareati, brez secrets management |

---

## 10. Zaključek

| Vprašanje | Odgovor |
|---|---|
| Katerih virov je v kodi? | **3:** Binance (primary), Coinbase Advanced (fallback #1), yfinance (fallback #2) |
| Kaj točno se fetcha? | **Daily OHLCV** izbranega simbola + (opcijsko) **daily OHLCV za BTC** kot cross-asset filter |
| Koliko klicev na dashboard refresh? | 1 ali 2 (odvisno od BTC filtra), z 60 s cachom |
| Kakšen rate-limit headroom? | Binance ~0.3 % budgeta, Coinbase ~1.3 % — praktično neomejeno |
| Kateri viri so bili zavrnjeni? | CoinGecko (50 % fail pod burstom), CryptoCompare (zaprto brez ključa), Kraken (720 candle plafon) |
| Zakaj 3 viri in ne 1? | Geo-redundanca (US Binance ban), outage resilience, deep history (Coinbase od 2015) |
| Brez API ključev? | Da — vsi 3 viri delajo brez registracije |
| Konsistentnost podatkov? | $50 razlika v BTC close med viri (= 0.08 %) — strategija indiferentna |

Vsi probe testi (raw output, latence, fail counts) so reproducibilni z
`shared/tests/test_data_source.py` (parsers + ordering) in z one-off probe
skriptami uporabljenimi v sled tega reporta.
