# PROMPT ZA CLAUDA — Diversitas Lean port

Vrniti tega prompta v novo sejo Clauda, da reproducira (ali ponovno generira)
celoten port `diversitas_lean.pine` v Python + live dashboard.

---

## Kontekst

V direktoriju `/Users/sara/Documents/1FAKS/MAG2LETNIK/LUKA/DIVERSITAS/lean`
je datoteka `diversitas_lean.pine` — Pine Script v6 trading indikator
"Diversitas Lean" za TradingView. Lean je minimalistična različica
`diversitas_pro_v3_200ma.pine` (`../full/`): obdrži le, kar se je v Full
izkazalo za vredno, ostalo izpusti.

Lean filozofija (iz Pine komentarja vrstice 4–21):
- Obdrži: Kijun trackline, 50 MA (trend), 200 MA (regime), blow-off,
  vol shock, anti-churn state machine, vol-targeted sizing.
- Izpusti: conviction score, ADX, market structure (HH/LL),
  weekly higher-timeframe gate, on-chain, macro.

Cilj: strategijo prenesti v Python in jo prikazati na živem dashboardu,
identično v slogu obstoječemu Full dashboardu (`../full/diversitas/dashboard.py`)
za vizualno konsistentnost.

---

## Naloga v 5 fazah

### FAZA 1 — Analiza strategije

Preberi `diversitas_lean.pine` v celoti in razčleni:
- **Trackline** (Kijun: 75-bar high/low midpoint, 3 % buffer) + **slope filter**
  (`trackline > trackline[trackSlopeBars=10]`) — to gateuje vstope, ne le smer
- **Dva MA**: `maMed = SMA(close, 50)` (trend MA — cena MORA biti nad njo),
  `maLong = SMA(close, 200)` (regime MA — slope merjen preko 5 barov)
- **Bear regime** = `!aboveMaLong AND maLongFalling` — **HARD BLOCK** (ne soft
  penalty kot v Full)
- **BullCondition** = hard AND vseh pogojev (above_tl AND above_med AND
  rising_window AND dist_entry_ok AND regime_ok AND btc_filter_ok) — **brez
  conviction score**
- **Exits**: blow-off (`distPct > 25 % AND RSI > 80`), vol shock
  (`vol > 1.5 × SMA50 AND belowTL`), trend break (`belowTL` z `belowCount ≥
  exitGraceBars`)
- **State machine**: ena spremenljivka `signalState` (BULL/BEAR) +
  pomožni `displayState` za UI; nima ločenih raw/display/signal kot Full
- **Anti-churn**: `bullHoldCount ≥ confirmBars`, `barsSinceSignal ≥ reentryHold`
- **Sizing**: `targetAlloc = round(100 × volScale)` ko BULL, sicer 0;
  default `targetVol = 50 %`

Naredi `STRATEGY_ANALYSIS.md` z mapiranjem Pine → Python za vsako sekcijo.
Eksplicitno označi razlike od Full (predvsem: hard block, no conviction,
barsSinceSignal reset on BOTH directions, bullHoldCount reset na 0 ne 1).

### FAZA 2 — Raziskava API-jev (preskoči če `../full/API_RESEARCH.md` že obstaja)

Če v `../` ali `../full/` ne obstaja `API_RESEARCH.md`, naredi raziskavo
zanesljivih crypto API-jev:
- **Binance** (`api.binance.com` — `/api/v3/klines`)
- CoinGecko, Coinbase, Kraken, CryptoCompare, yfinance

Izberi primary (Binance — 6000 weight/min, no key) + fallback (yfinance).
Sicer ponovno uporabi obstoječi `../full/API_RESEARCH.md`.

### FAZA 3 — Python implementacija

Struktura (zrcali Full):
```
lean/diversitas/
├── config.py        # LeanConfig dataclass + Config = LeanConfig alias
│                    # (alias je za kompatibilnost s shared data_source.py)
├── data_source.py   # KOPIJA iz full/ — Binance + yfinance + to_weekly
├── indicators.py    # KOPIJA iz full/ — RSI, SMA, EMA, RMA, ADX, bars_since
├── strategy.py      # NOVO: compute_features + run_state_machine + summary
├── backtest.py      # NOVO: CLI runner z signal stats + naive equity proxy
├── dashboard.py     # NOVO: live Streamlit (preprostejši od Full)
└── tests/
    ├── test_indicators.py  # KOPIJA iz full/
    └── test_strategy.py    # NOVO: bull_condition, hard regime block,
                            #       blow-off, bars_since reset on both directions
```

**Pravila**:
- Vse v pandas/numpy. State machine v eni forward pass (`df.itertuples()`
  ali `for i in range(n)` po numpy arrays).
- State machine MORA natančno replicirati Pine logiko — še posebej:
  - `barsSinceSignal := 0` se izvede **tako na BULL kot na BEAR** transitions
  - `bullHoldCount` se resetira na **0** kadar ni bullCondition (ne na 1)
  - **NI** weekend filtra — Lean teče vsak dan
  - Display state se evaluira instantno (brez `greenAbsentCount`-jevega grace
    bars-a)
- `dataclass LeanConfig` z vsemi 17 input parametri iz Pine.
- BTC filter privzeto **OFF** (`use_btc_filter=False`).
- Default `target_vol_pct = 50.0` (Full ima 25.0).

### FAZA 4 — Live dashboard

Streamlit. Mora vsebovati:
- **Hero row**: Signal · Regime · Close · Price vs TL · Allocation (5 enotnih
  kartic z barvno črto zgoraj kot accent — ne polnih barvnih blokov)
- **Glavni grafikon** (720 px):
  - Sveče (muted bull/bear barve)
  - Trackline (segmentiran po `track_rising_window` slope — barva pomeni
    range-filter status)
  - **50 MA** kot enotna modra (trend MA)
  - **200 MA** (segmentiran po 5-bar slope — barva označuje rising/falling
    regime)
  - Green/red dots, BULL/BEAR triangles
  - Background tint po `displayState`
  - **Subplot z allocation** kot stepline
- **Entry gates panel** (Lean signature):
  Za vsak pogoj v `bullCondition` prikaži PASS/FAIL row. Uporabnik takoj vidi,
  KATERI pogoj manjka za BULL. To je glavna razlika dashboarda od Full.
- **Status detail** (numerični panel)
- **Performance summary**: bar z 8 statistikami (trades, win rate, avg P&L,
  avg duration, best/worst, strategy total, buy-and-hold) — enako kot v Full
- **Vol chart**: annual vol % z vol-shock threshold overlay (1.5 × SMA50)
- **Trade ledger**: zadnjih 12 BULL→BEAR pairov s P&L, trajanjem, **exit
  triggerom** (blow-off / vol-shock / trend-break) — kategorizacija razlogov
  za izhod je dodana vrednost Lean ledgerja

Auto-refresh vsakih 60 s. Manual refresh z `st.cache_data.clear()`.

Pri uvozih NE uporabljaj relativnih (`from .config ...`) — Streamlit zažene
skripto kot `__main__`. Namesto tega:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from diversitas.config import LeanConfig, DEFAULT_CONFIG
```

### FAZA 5 — Validacija

1. `pytest diversitas/tests/ -v` — vsi testi PASS (minimalno 20+ testov)
2. Backtest na BTC-USD (1500 dni): preveri 18+ transitions, BULL ≈ 45 %
   exposure, blow-off exits naj se sprožijo na lokalnih vrhovih (Mar 2024,
   Nov 2024)
3. Zaženi dashboard `streamlit run lean/diversitas/dashboard.py
   --server.port 8502` — preveri HTTP 200 + `_stcore/health` = "ok"
4. Naredi `VALIDATION.md` s tabelo testov, backtest številkami, dashboard
   verifikacijo, in **razliko vs Full** (tabelo)

---

## Pravila

- **Slovenščina za output uporabniku**, angleščina v kodi + commit messages
- **Brez izmišljenih URL-jev** — uporabi samo obstoječe API endpoints
- **Brez `talib`** — uporabi shared `indicators.py` iz Full
- **Vsako fazo zaključi z "FAZA X DONE"** povzetkom
- **Če kaj v Pine logiki ni 100 % jasno, vprašaj** — predvsem state machine
  edge cases (`barsSinceSignal` reset, `bullHoldCount` semantics)
- **Ne dupliciraj indikatorjev/data sourca** — kopiraj iz Full s `cp`, ne
  pisati znova. Le `strategy.py`, `backtest.py`, `dashboard.py`, `test_strategy.py`
  in `config.py` so Lean-specifični.
- **Barve naj bodo enake kot v Full dashboardu** (GitHub-dark muted palette)
  za vizualno konsistentnost.

---

## Output ob koncu

- `lean/STRATEGY_ANALYSIS.md`, `lean/VALIDATION.md`, `lean/CLAUDE_PROMPT.md`
- `lean/diversitas/` Python paket z working backtest CLI in dashboard
- Test suite z 100 % PASS
- Dashboard dostopen lokalno na portu 8502 (Full uporablja 8501)
- Vse spushano na GitHub kot Luka24 (brez Claude attribution v commitih)

---

## Reference

- **Full Python implementacija** (referenca za stil + shared moduli):
  `../full/diversitas/`
- **Full audit + analysis**: `../full/AUDIT.md`, `../full/STRATEGY_ANALYSIS.md`
- **Full validation**: `../full/VALIDATION.md`
- **API research**: `../API_RESEARCH.md` (v projektnem root)
