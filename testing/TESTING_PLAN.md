# Diversitas — Master Testing & Validation Plan

**Verzija:** 1.0 | **Datum:** 2026-06-18
**Avtorja:** Luka + Peter | **Variante:** Full (Pro v3) + Lean

---

## 1. Povzetek trenutnega stanja

### Kaj JE implementirano
- **Pipe 1 (Technical)** — v celoti, auditiran Pine → Python port (0 napak)
  - Full: Trackline + 5-komponentni conviction + ADX + market structure + weekly gate + BTC filter + ER filter
  - Lean: Trackline + 50/200 MA + blow-off/vol shock + ER filter (brez conviction, ADX, weekly gate)
- **Dashboard** — KPI kartice, equity curve, signal timeline, rolling Sharpe, monthly heatmap, trade ledger, P&L distribution, scatter plot
- **Bear allocation slider** — minimalna alokacija v BEAR režimu (0–50%)

### Kaj NI implementirano (iz specifikacije)
- **Pipe 2 (On-chain)** — MVRV ratio + Coinbase Premium
- **Pipe 3 (Macro)** — BBB Credit Spread + DXY Year-over-Year
- **Convergence Gate** — kombinacija treh pipe-ov v finalni signal
- **MVRV-enhanced blow-off** — 17.5% namesto 25% ko je MVRV >= 3.5
- **Fees + slippage** v backtestu
- **Dinamičen buffer** (ATR-based, iz Q&A idej)
- **Position sizing** (Kelly Criterion, iz Q&A idej)

---

## 2. Testni okvir in orodja

### 2.1 Priporočen stack

| Orodje | Namen | Zakaj |
|--------|-------|-------|
| **VectorBT** | Parameter sweep, Monte Carlo | Najhitrejši za batch backtesting — 1000 kombinacij v minutah. Vektorizirano z NumPy. |
| **Obstoječi Python engine** | Referenčni backtest | Že validiran proti Pine Script. Uporabljaj za single-run verifikacijo. |
| **pandas + numpy** | Metrike, analiza | Že v uporabi. Dodaj Omega ratio, Ulcer index. |
| **plotly** | Vizualizacija rezultatov | Že v dashboardu. Razširi za testne reporte. |
| **pytest** | Regresijski testi | Že nastavljen. Dodaj teste za nove pipe-e. |

### 2.2 Zakaj ne Backtrader
Backtrader je event-driven (počasen za sweep) in development je zamrl 2021. VectorBT je 100-1000x hitrejši za parameter optimization. Za live trading bomo po potrebi dodali execution layer kasneje.

### 2.3 Instalacija
```bash
pip install vectorbt
# ali samo numpy/pandas za custom sweep (že v env)
```

---

## 3. Organizacija datotek

```
diversitas/
  testing/
    TESTING_PLAN.md          ← ta dokument
    TESTING_LOG.md           ← kronološki dnevnik vseh testov
    results/
      phase1/                ← baseline rezultati
        btc_baseline_full.csv
        btc_baseline_lean.csv
        eth_baseline_full.csv
        ...
      phase2/                ← sensitivity analiza
        sweep_trackline.csv
        sweep_buffer.csv
        sweep_threshold.csv
        ...
      phase3/                ← pipe 2+3 rezultati
      phase4/                ← integracija
      phase5/                ← walk-forward
      phase6/                ← Monte Carlo
    scripts/
      run_baseline.py        ← Faza 1 avtomatski batch
      run_sensitivity.py     ← Faza 2 parameter sweep
      run_walkforward.py     ← Faza 5 walk-forward
      run_montecarlo.py      ← Faza 6 Monte Carlo
      metrics.py             ← razširjene metrike (Omega, Ulcer, ...)
    reports/
      phase1_report.md       ← pisni zaključki po fazi
      phase2_report.md
      ...
```

### Verzioniranje variant (Full vs Lean)
- Vsak test se poganja na **obeh variantah** vzporedno
- V CSV rezultatih je stolpec `variant` (full / lean)
- V TESTING_LOG.md se zabeleži katera varianta je bila testirana
- Primerjava Full vs Lean je **ekspliciten test** (Faza 1.3)

---

## 4. Metrike

### 4.1 Osnovne (že implementirane)
| Metrika | Formula | Cilj (crypto trend-following) |
|---------|---------|-------------------------------|
| CAGR | `final^(1/years) - 1` | > B&H ali primerljiv |
| Sharpe | `ann_ret / ann_std` | > 1.0 (odlično > 2.0) |
| Sortino | `ann_ret / down_std` | > 1.5 |
| Max Drawdown | `min(eq / cummax - 1)` | < B&H (absolutno) |
| Calmar | `CAGR / |Max DD|` | > 1.0 |
| Win Rate | `wins / total` | > 50% |
| Profit Factor | `gross_profit / gross_loss` | > 1.5 (odlično > 2.0) |
| Exposure | `mean(position_size)` | 40–70% (efektiven izkoristek) |

### 4.2 Razširjene (dodati za testiranje)
| Metrika | Formula | Zakaj |
|---------|---------|-------|
| **Omega Ratio** | `sum(max(r-T, 0)) / sum(max(T-r, 0))` za T=0 | Ujame celotno distribucijo, ne samo povprečje/variance. Boljši od Sharpe za asimetrične returne (crypto!). > 1.5 je dobro. |
| **Ulcer Index** | `sqrt(mean(drawdown^2))` | Meri "bolečino" drawdownov — utežuje dolge, globoke DD bolj kot kratke. Nižji = boljši. |
| **Tail Ratio** | `percentile_95 / |percentile_5|` | Razmerje med dobrimi in slabimi outlierji. > 1.0 = dobre priložnosti presegajo slabe. |
| **MAR Ratio** | `CAGR / |Max DD|` | Isto kot Calmar ampak na celotnem obdobju. |
| **Avg Bars in Trade** | `mean(trade_duration)` | Koliko dolgo drži povprečno pozicijo. |
| **Max Consecutive Losses** | Najdaljši niz zaporednih izgub | Psihološki indikator — koliko slabih tradov zaporedoma? |
| **Recovery Factor** | `net_profit / |max_dd|` | Koliko zaslužiš na enoto najhujšega drawdowna. |
| **Payoff Ratio** | `avg_win / |avg_loss|` | Razmerje med povprečnim dobičkom in izgubo. > 1.5 za trend-following. |

### 4.3 Regime-specifične metrike
Za vsako metriko beležimo tudi vrednost **po režimu**:
- **Bull market** (BTC > 200 SMA, SMA rising)
- **Bear market** (BTC < 200 SMA, SMA falling)
- **Sideways / chop** (BTC v 15% rangu za 60+ dni)
- **High volatility** (vol_z > 1)
- **Low volatility** (vol_z < -1)

To pokaže kdaj strategija deluje in kdaj ne — ključno za zaupanje.

---

## 5. Testne faze — podroben plan

### FAZA 1: Baseline validacija (Prioriteta: VISOKA)
**Cilj:** Potrditi da Pipe 1 dela pravilno na vseh assetih. Zbrati referenčne metrike.
**Trajanje:** 1–2 dni
**Orodja:** Obstoječi dashboard + skripta `run_baseline.py`

| # | Test | Asset | Obdobje | Varianta | Output |
|---|------|-------|---------|----------|--------|
| 1.1 | Baseline metrike | BTC | 2020-01-01 → 2026-06-18 | Full + Lean | CSV z vsemi metrikami |
| 1.2 | Baseline metrike | ETH | 2020-01-01 → 2026-06-18 | Full + Lean | CSV |
| 1.3 | Baseline metrike | SOL | 2021-01-01 → 2026-06-18 | Full + Lean | CSV |
| 1.4 | Baseline metrike | AVAX | 2021-01-01 → 2026-06-18 | Full + Lean | CSV |
| 1.5 | Baseline metrike | LINK | 2020-01-01 → 2026-06-18 | Full + Lean | CSV |
| 1.6 | Full vs Lean primerjava | Vsi | Polno obdobje | Oba | Primerjalna tabela |
| 1.7 | Signal count | BTC | 2023-01-01 → 2026-06-18 | Oba | Mora biti < 20 |
| 1.8 | Vizualni pregled | BTC | 2020 → 2026 | Oba | Screenshot + komentarji: ali je BEAR med 50%+ rallyjem? |
| 1.9 | Bear alloc sensitivity | BTC | 2020 → 2026 | Full | 0%, 5%, 10%, 15%, 20%, 25%, 30% |
| 1.10 | Survivor bias check | XRP, BNB, ADA | 2021 → 2026 | Full | Ali rezultati držijo na assetih izven originalne test skupine? |

**Kriteriji uspešnosti (iz Q&A dokumenta):**
1. Max drawdown < B&H max drawdown
2. CAGR >= 60% B&H CAGR (ujamemo vsaj 60% bikovskega trga)
3. Število signalov < 20 na 3 leta
4. Ni obdobij > 2 meseca z očitno napačnim signalom

### FAZA 2: Sensitivity analiza (Prioriteta: VISOKA)
**Cilj:** Identificirati optimalne parametre in preveriti robustnost.
**Trajanje:** 2–3 dni
**Orodja:** `run_sensitivity.py` z VectorBT ali custom numpy sweep

| # | Parameter | Range | Korak | Asset | Metrika |
|---|-----------|-------|-------|-------|---------|
| 2.1 | trackline_period | 45, 50, 55, 60, 65, 70, 75, 80, 85, 90 | 5 | BTC, ETH | Calmar, #trades |
| 2.2 | buffer_pct | 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0 | — | BTC, ETH | Calmar, Max DD |
| 2.3 | conviction threshold | 40, 45, 50, 55, 60, 65, 70, 75, 80 | 5 | BTC | Calmar, exposure |
| 2.4 | reentry_hold | 5, 7, 10, 12, 15, 18, 20, 25 | — | BTC | #trades, missed % |
| 2.5 | exit_grace_bars | 1, 2, 3, 4, 5 | 1 | BTC | Max DD, false exits |
| 2.6 | confirm_bars | 1, 2, 3, 4, 5 | 1 | BTC | #trades, entry timing |
| 2.7 | ER threshold | 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40 | 0.05 | BTC | #trades, Calmar |
| 2.8 | conv_smooth | 3, 5, 7, 10 | — | BTC | Signal noise |
| 2.9 | blowoff_dist | 15, 20, 25, 30, 35, 40 | 5 | BTC | Blow-off detection rate |
| 2.10 | vol_shock_mul | 1.2, 1.3, 1.5, 1.8, 2.0 | — | BTC | Vol shock false positive rate |

**Metoda:**
1. Za vsako parametrsko kombinacijo poganjaj backtest na BTC 2020–2026
2. Zapiši vse metrike v CSV
3. Ustvari heatmap (parameter vs Calmar) za vizualizacijo
4. **Robustnost test:** parameter je "robusten" če sosednje vrednosti (±1 korak) dajo podobne rezultate (Calmar ± 20%). Če rezultati drastično nihajo, je parameter preobčutljiv.

**Multi-asset validacija:** Po optimizaciji na BTC, pogoni iste parametre na ETH, SOL brez sprememb. Če delajo na vseh — parametri so robustni. Če ne — overfitting na BTC.

### FAZA 3: Implementacija Pipe 2 + Pipe 3 (Prioriteta: SREDNJA)
**Cilj:** Dodati on-chain in macro podatke.
**Trajanje:** 1–2 tedna

| # | Naloga | Vir podatkov | API | Kompleksnost |
|---|--------|--------------|-----|--------------|
| 3.1 | MVRV ratio | CoinGlass ali Glassnode | REST API (key needed) | Srednja |
| 3.2 | Coinbase Premium | Coinbase BTC/USD vs Binance BTC/USDT | Že imamo Binance; dodaj Coinbase | Nizka |
| 3.3 | BBB Credit Spread | FRED (St. Louis Fed) | Brezplačen API key | Nizka |
| 3.4 | DXY Year-over-Year | Yahoo Finance (DX-Y.NYB) ali FRED | yfinance (že v env) | Nizka |
| 3.5 | On-chain pipe logika | MVRV + CB Premium → state | — | Nizka |
| 3.6 | Macro pipe logika | BBB + DXY → state | — | Nizka |
| 3.7 | Convergence gate | Tech + OnChain + Macro → signal | — | Srednja |
| 3.8 | MVRV-enhanced blow-off | 17.5% namesto 25% ko MVRV >= 3.5 | — | Nizka |

**Testiranje po implementaciji:**
- Primerjaj: samo Tech vs Tech+OnChain vs Tech+OnChain+Macro
- Za vsako kombinacijo zapiši vse metrike
- On-chain je zanesljiv samo za BTC (in delno ETH) — za altcoine on-chain pipe vrne NEUTRAL

### FAZA 4: Integracijsko testiranje (Prioriteta: SREDNJA)
**Cilj:** Testirati celoten 3-pipe sistem.
**Trajanje:** 3–5 dni

| # | Test | Opis |
|---|------|------|
| 4.1 | Full pipeline BTC | 2020–2026, vsi 3 pipe-i, vse metrike |
| 4.2 | Pipe contribution analysis | Koliko vsak pipe prispeva? Primerjaj CAGR/DD z/brez |
| 4.3 | Variant A vs B | Full filtri vs Lean z vsemi pipe-i — kateri da boljši Calmar? |
| 4.4 | Altcoin test | ETH, SOL z vsemi pipe-i (on-chain → NEUTRAL za altcoine) |
| 4.5 | Convergence gate tuning | Testiraj: 0 BEAR pipes allowed vs 1 vs 2 |
| 4.6 | Fees + slippage | Dodaj 0.1% per trade + 0.05% slippage, primerjaj rezultate |
| 4.7 | Bear alloc z vsemi pipe-i | 0%, 10%, 20% bear alloc s polnim pipeline-om |

### FAZA 5: Walk-Forward validacija (Prioriteta: VISOKA)
**Cilj:** Preveriti da parametri niso overfitted.
**Trajanje:** 2–3 dni
**Orodja:** `run_walkforward.py`

| # | Test | Train | Test | Rolling |
|---|------|-------|------|---------|
| 5.1 | Fixed split | 2020-01 → 2024-06 | 2024-07 → 2026-06 | Ne |
| 5.2 | Rolling 2Y/6M | 2Y train, 6M test | Premikaj za 6M | 6 iteracij |
| 5.3 | Rolling 3Y/1Y | 3Y train, 1Y test | Premikaj za 1Y | 3 iteracije |
| 5.4 | Multi-asset | Train na BTC, test na ETH/SOL (brez re-optimizacije) | — | — |

**Walk-forward pass rate:**
- Strategija "passira" če je out-of-sample Calmar > 50% in-sample Calmar
- In-sample Sharpe > 0 v vsaj 80% oken
- Ne sme biti out-of-sample obdobja z negative Sharpe > -0.5

**Pozor za crypto:**
- Crypto trguje 24/7/365 — ni vikendov in praznikov
- Volatilnost se dramatično spreminja med cikli (2020 = nizka, 2021 = visoka, 2022 = crash, 2023 = recovery)
- Train/test split mora vsebovati vsaj 1 bull + 1 bear market

### FAZA 6: Monte Carlo + Bootstrap validacija (Prioriteta: SREDNJA)
**Cilj:** Kvantificirati zaupanje v rezultate in zaznati overfitting.
**Trajanje:** 1–2 dni
**Orodja:** `run_montecarlo.py`

| # | Test | Metoda | Iteracij |
|---|------|--------|----------|
| 6.1 | Equity curve bootstrap | Naključno premeši vrstni red tradov, izračunaj DD distribucijo | 5000 |
| 6.2 | Return shuffle | Naključno premeši daily returns, primerjaj z dejanskim Sharpe-om | 5000 |
| 6.3 | Parameter noise | Dodaj ±10% šum na vsak parameter, koliko se metrike spremenijo? | 1000 |
| 6.4 | Confidence intervals | 95% CI za CAGR, Sharpe, Max DD iz bootstrap-a | 5000 |

**Interpretacija:**
- Če je p-value strategijskega Sharpe-a < 0.05 proti naključnim premestitvam → statistično značilen edge
- Če 95% CI za Sharpe vključuje 0 → ni dovolj dokazov za edge
- Če se metrike spremenijo za > 30% ob ±10% parameter noise → overfit

---

## 6. Dodatne profesionalne funkcionalnosti (iz Q&A + research)

### 6.1 Dinamičen buffer (ATR-based)
Iz Q&A: `buffer = k * ATR(14) / close` z `k ∈ [1.5, 3]`
- Namesto fiksnih 3% se buffer prilagaja volatilnosti
- Testirati: primerjaj fiksni 3% vs ATR-based na BTC 2020–2026
- Lahko je asimetričen (širši za gor, ožji za dol)

### 6.2 Position sizing (Kelly Criterion)
Iz Q&A: `f* = (p·b − q) / b`
- p = win rate, b = avg_win/avg_loss, q = 1 - p
- Namesto binarnega 0/100% izračunaj optimalno velikost pozicije
- Half-Kelly (f*/2) je standardna praksa za zmanjšanje variance
- Testirati: binary vs Kelly vs Half-Kelly na BTC

### 6.3 Adaptivni conviction thresholds
Iz Q&A: "mogoce smiselno thresholde narediti linearno med 55-70"
- Namesto diskretnih 55/60/70 uporabi: `threshold = 55 + 15 * sigmoid(vol_z)`
- Gladki prehod med režimi brez skokov
- Testirati: diskretni vs linearni vs sigmoid

### 6.4 Z-score normalizacija komponent
Iz Q&A: uporabi z-score za Trend, EMA spread, Volume, Drawdown
- `z = (value - mean) / std` z rolling oknom
- Prilagaja se različnim assetom avtomatsko
- Odpravlja problem fiksnih odstotkov (5% pri BTC ≠ 5% pri SOL)

### 6.5 Rolling peak za drawdown
Iz Q&A: "1-letni rolling peak namesto all-time peak"
- `peak = close.rolling(365).max()` namesto `close.cummax()`
- Bolj smiselno za multi-letne teste (BTC ATH $69K ne vpliva na scoring v 2024)

### 6.6 Dinamičen re-entry lock
Iz Q&A: "V high vol lock 5–7 barov, v low vol 25–30 barov"
- `reentry_hold = base + k * vol_z`
- V mirnih trgih počakaj dlje (manj šuma), v divjih hitreje nazaj
- Testirati: fiksnih 15 vs dinamičen

### 6.7 Weekend skip testiranje
Iz Q&A: "Je smiselno sploh weekend skip?"
- Crypto trguje 24/7 — vikendi imajo pogosto nižji volumen
- Testirati: z weekend skip vs brez na BTC 2020–2026

### 6.8 Profit taking
Iz Q&A: "Kasneje: profit taking?"
- Npr. zmanjšaj pozicijo za 25% ko je +50% v profitu, za nadaljnjih 25% ko je +100%
- Alternativa: trailing stop (npr. 15% od peak-a)
- Testirati: brez vs trailing stop vs fixed profit taking

### 6.9 Fees + slippage model
Iz Q&A: "Dodat bi bilo verjetno dobro fees in slippage"
- Binance: 0.1% maker/taker (0.075% z BNB popustom)
- Slippage: 0.05% za BTC, 0.1% za altcoine (nižja likvidnost)
- Impact: pri 15 tradih na 3 leta = ~3% skupnega profita lost

---

## 7. Režimska analiza — kako jo izvesti

### 7.1 Definicija režimov
```python
# Bull market
bull_regime = (close > sma200) & (sma200 > sma200.shift(20))

# Bear market
bear_regime = (close < sma200) & (sma200 < sma200.shift(20))

# Sideways (< 15% range za 60 dni)
rolling_range = (close.rolling(60).max() - close.rolling(60).min()) / close.rolling(60).min()
sideways = rolling_range < 0.15

# High / Low volatility
high_vol = vol_z > 1.0
low_vol = vol_z < -1.0
```

### 7.2 Per-regime reporting
Za vsak režim izračunaj:
- Koliko časa strategija preživela v tem režimu
- CAGR, Sharpe, Max DD v tem režimu
- Število tradov v tem režimu
- Win rate v tem režimu

### 7.3 Pričakovanja po režimu
| Režim | Pričakovan rezultat | Sprejemljivo |
|-------|--------------------|----|
| Bull | Pozitiven return, blizu B&H | CAGR > 70% B&H |
| Bear | Majhen loss ali flat | Max DD < 50% B&H DD |
| Sideways | Flat ali rahlo negativen (iz tradov) | DD < 10% |
| High vol | Manj tradov, konservativni | Sharpe > 0 |
| Low vol | Zgodnejši vstopi, več exposure | Win rate > 55% |

---

## 8. TESTING_LOG.md format

Vsak test dobi zapis v kronološkem vrstnem redu:

```markdown
---
## [DATUM] | Faza X.Y | [Kratek opis]

**Config:**
- Varianta: Full / Lean
- Asset: BTC
- Obdobje: 2020-01-01 → 2026-06-18
- Parametri: default / spremembe

**Rezultati:**
| Metrika | Strategija | B&H |
|---------|-----------|-----|
| CAGR | +XX% | +XX% |
| Sharpe | X.XX | X.XX |
| Max DD | -XX% | -XX% |
| Calmar | X.XX | X.XX |
| Trades | XX | — |
| Win Rate | XX% | — |

**Opažanja:**
- [Kaj je bilo zanimivo, nepričakovano]

**Zaključek:**
- [PASS / FAIL / PARTIAL]
- [Naslednji korak]
---
```

---

## 9. Prioritetna razvrstitev in časovnica

| Faza | Prioriteta | Trajanje | Predpogoji | Status |
|------|-----------|----------|------------|--------|
| **1. Baseline** | VISOKA | 1–2 dni | Nič (dashboard obstaja) | TODO |
| **2. Sensitivity** | VISOKA | 2–3 dni | Faza 1 zaključena | TODO |
| **5. Walk-forward** | VISOKA | 2–3 dni | Faza 2 zaključena | TODO |
| **3. Pipe 2+3** | SREDNJA | 1–2 tedna | Faza 1 zaključena (lahko vzporedno s 2) | TODO |
| **4. Integracija** | SREDNJA | 3–5 dni | Faza 3 zaključena | TODO |
| **6. Monte Carlo** | SREDNJA | 1–2 dni | Faza 2 zaključena | TODO |

**Predlagan vrstni red:** 1 → 2 → 5 → 6 → (3 → 4 vzporedno)

Faze 1, 2, 5, 6 se lahko izvedejo **brez nove kode za pipe-e** — testiramo samo Technical pipe ki že deluje. Faze 3 in 4 zahtevajo novo kodo (API integracije, convergence gate).

---

## 10. Viri in reference

- [Coin Bureau: How To Backtest Crypto Strategy 2026](https://coinbureau.com/guides/how-to-backtest-your-crypto-trading-strategy)
- [Python Backtesting Libraries 2026: VectorBT vs Backtrader](https://rmbell09-lang.github.io/tradesight/blog/python-backtesting-libraries-2026.html)
- [Monte Carlo Simulations for Strategy Validation](https://quantproof.io/blog/monte-carlo-simulations-trading-strategy-validation)
- [Overfitting Prevention in Trading](http://adventuresofgreg.com/blog/2025/12/18/avoid-overfitting-testing-trading-rules/)
- [Omega Ratio: Distribution-free Risk-adjusted Performance](https://www.pfolio.io/academy/omega-ratio)
- [Trend Following in Crypto: A Decade of Evidence (arXiv)](https://arxiv.org/pdf/2009.12155)
- [Adaptive Portfolio Construction in Crypto (arXiv 2026)](https://arxiv.org/pdf/2602.11708)
- Diversitas Strategy Spec v1.0 (May 2026) — `strategyDescription/Copy of Diversitas_Trading_Signal_Engine_Spec (1).docx`
- Diversitas Q&A (Jun 2026) — `strategyDescription/Diversitas_vprašanja_3.6.2026.docx`
