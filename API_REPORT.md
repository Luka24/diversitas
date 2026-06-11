# API report — kateri viri so v projektu, kateri so se izkazali za slabe

Generirano 2026-06-11 po **dejanskem testiranju vseh kandidatov v živo** + spletni
raziskavi. Vsi podatki, ki so v prvotni `API_RESEARCH.md` od prejšnjega tedna,
so bili ponovno preverjeni — pri nekaterih virih se je situacija medtem
spremenila (CryptoCompare zdaj zahteva ključ, CoinGecko je še bolj
nestabilen pod burstom).

---

## 1. Trenutno stanje v kodi (`shared/data_source.py`)

| Vloga | Vir | Status |
|---|---|---|
| **Primary** | Binance public REST (`/api/v3/klines`) | aktiven |
| **Fallback** | yfinance (Yahoo Finance scraper) | aktiven |
| Ostali kandidati | Coinbase, CoinGecko, Kraken, CryptoCompare | NE uporabljeni |

---

## 2. Rezultati živih meritev (probe iz tega gostitelja)

### 2.1 Enkratni klic (BTC, daily, ≤200 candles)

| API | Status | Latenca | Bars | Opomba |
|---|---|---|---|---|
| **Binance** | ✓ OK | 364 ms | 200 | exponira `x-mbx-used-weight` header |
| **Coinbase Advanced** | ✓ OK | 118 ms | 350 | vrne več kot je zahtevano (default 300) |
| **CoinGecko (free)** | ✓ OK | 206 ms | 180 | endpoint `/ohlc`, brez volume |
| **Kraken** | ✓ OK | 215 ms | 721 | trd plafon — 720 candles max |
| **CryptoCompare** | ✗ **FAIL** | 77 ms | — | HTTP 401 — API key now required |
| **yfinance** | ✓ OK | **2088 ms** | 199 | 10× počasnejši od najhitrejšega |

### 2.2 Burst test (10 zaporednih klicev, ne sleep)

| API | Avg latenca | Fails | Opomba |
|---|---|---|---|
| **Binance** | 316 ms | 0/10 | uporabljenih ~20 weight (od 6000/min) |
| **Coinbase** | **68 ms** | 0/10 | najhitrejši |
| **Kraken** | 76 ms | 0/10 | stabilen v burstu |
| **CoinGecko (free)** | 64 ms | **5/10** | **50 % fail rate** pod burstom — rate limit |

### 2.3 Coverage / history depth

| API | Najstarejši BTC daily bar | Bars per call | Opomba |
|---|---|---|---|
| Binance | 2017-08-17 | 1000 | ~8 let zgodovine, pagination z `endTime` |
| **Coinbase** | **2015-07** ali starejši | 300 | **najgloblja zgodovina**, pagination potrebna |
| Kraken | 2024-06-21 (samo) | 720 | **~2 leti max** — trd plafon |
| CoinGecko `/market_chart` | 0 (vrnil prazen seznam) | — | `days=max` ne dela zanesljivo |
| yfinance | 2014 | — | najgloblja zgodovina BTC-USD, a počasna |

### 2.4 Altcoin podpora

| API | ETH | SOL | XRP / ADA / AVAX |
|---|---|---|---|
| Binance | ✓ ETHUSDT | ✓ SOLUSDT | ✓ vsi |
| Coinbase | ✓ ETH-USD | ✓ SOL-USD | ✓ vsi |
| Kraken | ✓ ETHUSD | ✓ SOLUSD | delno (čudna imena, npr. XBT) |
| yfinance | ✓ ETH-USD | ✓ SOL-USD | ✓ vsi |

---

## 3. Spletna raziskava — uptime in trenutno stanje

### Binance ([uptime monitorji](https://isdown.app/status/binance))
- **235+ dni brez incidenta** v zadnjih 12 mesecih (per IsDown June 2026)
- 2 manjši downtime v 2025: 10. okt (10 min) in 15. apr (11 min)
- Geo restrictions: blokiran v ZDA in nekaterih jurisdikcijah → fallback obvezen
- Rate limit: [6000 weight/min/IP, klines = 2 weight](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/limits)

### Coinbase Advanced Trade
- [Public endpoints: 10 req/sec po IP](https://docs.cloud.coinbase.com/advanced-trade/docs/rest-api-rate-limits) (= 600/min)
- Regulirano US podjetje → manjše tveganje za geo block
- Authenticated endpoints: 30 req/sec

### CryptoCompare (= CoinDesk Data)
- **Migracija na CoinDesk Data brand** (account/auth pod CoinDesk)
- "Works without key but IP limits slowly reduced over time" — danes praktično blokirano za anonimne zahteve
- **Naš probe: HTTP 401 "API key required"** na vsakem klicu — povsem zaprto za public use

### CoinGecko free
- [5–15 calls/min](https://support.coingecko.com/hc/en-us/articles/4538771776153) (varira po globalnem prometu)
- Demo plan (free, zahteva sign-up): 30 calls/min
- "Difficult to scale high-frequency or high-throughput applications without paid plan"
- Naš burst test potrdi: pri 10 zaporednih klicih 5 odpovedi

### yfinance
- [Trading Dude: "yfinance keeps getting blocked"](https://medium.com/@trading.dude/why-yfinance-keeps-getting-blocked-and-what-to-use-instead-92d84bb2cc01)
- Scraper Yahoojevih neuradnih endpointov — Yahoo lahko kadarkoli spremeni
- 2024–2025: knjižnica se je dvakrat zlomila (popravljeno v ranaroussi/yfinance#2052)
- "Dangerous to use for automated trading decisions" — naša raba (60-sec polling) je sprejemljiva, a fragilna

### Kraken
- [Public endpoints: ~1 req/sec/IP](https://docs.kraken.com/api/docs/guides/spot-rest-ratelimits/)
- [720 candle max hard limit](https://docs.kraken.com/api/docs/rest-api/get-ohlc-data/) — neuporaben za 4+ let backtest
- Stabilen, ampak ne ponuja konkurenčne globine

---

## 4. Ranking — kateri so se izkazali za **dobre**, kateri za **slabe**

### Dobri (priporočeni)

**1. Binance** — še vedno najboljša izbira za primary
- Pluses: globaln budget (6000 w/min), 1000 bars/call, sub-sekundna latenca, 8 let zgodovine BTC, vsi alti, WebSocket za live ticker
- Minuses: geo-blokiran v ZDA/Kanadi
- **Verdict:** PRIMARY — ostane

**2. Coinbase Advanced Trade** — manjkajoči kandidat
- Pluses: 68 ms (najhitrejši v testu), US-regulirano (no geo block v ZDA), najgloblja zgodovina (2015), čista REST shema (`BTC-USD` naming)
- Minuses: 300 bars/call (3× pagination za 1000 bars vs Binance 1×)
- **Verdict:** **bi se splačal kot FALLBACK #1**, da pokrijemo Binance geo block. Trenutno NI v kodi — priporočam dodatek.

**3. yfinance** — sprejemljiv fallback
- Pluses: zero setup, najgloblja zgodovina (2014), pokriva vse simbole (BTC-USD format)
- Minuses: 2 sec latenca, neuradni scraper, fragilen pri Yahoo spremembah
- **Verdict:** FALLBACK #2 — ostane kot zadnja rešilna mreža za daily backtest, ne za live.

### Slabi (NE priporočeni)

**4. CoinGecko free** — IZKAZAL SE ZA SLABEGA pod realno rabo
- **50 % fail rate pod burst** (10 zaporednih klicev)
- 5–15 calls/min limit pomeni: ne moremo polingati vsakih 60 s na 8 simbolov (8 × 60 = 480 klicev/uro = neprestano čez limit)
- `/market_chart?days=max` vrnil prazen response
- `/ohlc` deluje, a brez volume → potrebovali bi 2 klica per simbol
- **Verdict:** **OMIT iz produkcijske kode**, bi povzročil intermitentne napake na dashboardu. V mojem prvotnem `API_RESEARCH.md` je bil omenjen kot fallback — to je bilo zavajajoče in popravim.

**5. CryptoCompare** — POSTAL NEUPORABEN
- **HTTP 401 "API key required"** danes na vsak public klic
- V prvotnem researchu sem pisal "free 250k calls/month" — to ni več res
- Account migration na CoinDesk Data — sprememba modela
- **Verdict:** **REMOVE iz vseh dokumentov**, brez API ključa neuporaben.

**6. Kraken** — NIŠA, ne za naš use case
- 720 candle hard limit = ~2 leti backtest
- Naš strategija potrebuje 400+ bars (200 MA + warmup), in idealno 1500+ bars za sanity backtest
- **Verdict:** **OMIT** — premalo zgodovine za naš strategy

---

## 5. Predlog: konkretne spremembe v kodi

### Trenutno (`shared/data_source.py`)
```python
sources = ["binance", "yahoo"] if prefer == "binance" else ["yahoo", "binance"]
```

### Priporočeno
```python
sources = ["binance", "coinbase", "yahoo"]
```
- Dodaj `_coinbase_fetch()` z paginated 300-bars-per-call branjem (pageBack do želene globine)
- Coinbase pokriva primer, ko je uporabnik v ZDA in Binance vrača HTTP 451 (Unavailable For Legal Reasons)
- Vrstni red: Binance (najhitrejši/widest, geo-omejen) → Coinbase (regulated US, deep history) → yfinance (last resort)

### Posodobitev `API_RESEARCH.md`
- **Odstrani CryptoCompare** (zavajajoče — zdaj zahteva ključ)
- **Označi CoinGecko free kot "ne priporočamo"** (50 % fail pod burstom — dokumentiramo svoj probe)
- **Dodaj Coinbase Advanced** v primarno priporočilo
- Linki na uptime monitorje (IsDown za Binance) za pregled zgodovine

---

## 6. Zaključek — odgovor na "katere si uporabil in kateri so slabi"

**Uporabil v projektu:**
1. **Binance** (primary) — odlično, ostane
2. **yfinance** (fallback) — fragilen, ampak deluje za naš polling vzorec

**Razmišljal o, a ne uporabil:**
3. **Coinbase Advanced** — pomota, da nisem dal v fallback. Najhitrejši v testu, najgloblja zgodovina, US-friendly. **Priporočam dodati v naslednjem commitu.**
4. **CoinGecko free** — v mojem prvotnem researchu sem pisal "fallback #1", a živi probe pokaže **50 % fail rate** pod realno rabo. **Slab predlog — popravim research dokument.**
5. **Kraken** — zavrnjen takrat (1 req/s), zdaj potrjeno tudi: 720 candle limit ga naredi neuporabnega za 4+ letni backtest.
6. **CryptoCompare** — zavrnjen takrat (zahteva ključ), zdaj potrjeno: 401 že pri prvem klicu. Star research je pisal "free 250k/mo" — to ni več res.

**Slabi viri = ne uporabljati za naš use case:**
- ❌ CryptoCompare (zaprto brez ključa)
- ❌ CoinGecko free (rate limit 5–15/min in 50 % fail pod burst)
- ❌ Kraken (720 candle plafon)

**Dobri viri = primerni za naš dashboard:**
- ✅ Binance (primary)
- ✅ Coinbase Advanced (FALLBACK #1 — še NI v kodi, priporočam dodati)
- ⚠️ yfinance (fallback #2, fragilen ampak zadnja zaščita)
