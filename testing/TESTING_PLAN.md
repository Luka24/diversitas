# Diversitas — Master Testing & Validation Plan v2

**Verzija:** 2.0 | **Datum:** 2026-06-18
**Avtorja:** Luka + Peter | **Variante:** Full (Pro v3) + Lean

---

## 1. Trenutno stanje in cilji

### Implementirano
- Pipe 1 (Technical) — auditiran, 0 napak v Pine→Python portu
- Full: Trackline + conviction(5) + ADX + structure + weekly gate + BTC filter + ER
- Lean: Trackline + 50/200 MA + blow-off/vol shock + ER
- Dashboard z vsemi metrikami, equity curve, signal timeline, itd.

### Ni implementirano
- Pipe 2 (On-chain): MVRV + Coinbase Premium
- Pipe 3 (Macro): BBB spread + DXY YoY
- Convergence Gate (3 pipe-i → 1 signal)
- Dodatne funkcionalnosti iz Q&A (dinamičen buffer, Kelly sizing, itd.)

### Kriteriji uspešnosti (iz Q&A dokumenta)
1. Max drawdown < Buy & Hold max drawdown
2. CAGR >= 60% B&H CAGR
3. Število signalov < 20 na 3 leta
4. Ni obdobij > 2 meseca z očitno napačnim signalom (BEAR med 50%+ rallyjem)

### Primarna metrika za optimizacijo
**Calmar Ratio** (`CAGR / |Max DD|`) — uravnoteži donos in tveganje. Sekundarna: Omega Ratio.

---

## 2. Orodja in tehnike

### 2.1 Backtesting engine
**Naš obstoječi Python engine** za vse teste. Razlogi:
- Že validiran proti Pine Script (audit z 0 napakami)
- Deterministično reproducibilen
- Dovolj hiter za naše potrebe (~1s per run na 2000 barov)

Za parameter sweep: **custom numpy vektoriziran sweep** (ne VectorBT). Razlog: naša strategija ima state machine (forward pass), ki se ne da popolnoma vektorizirati. Namesto tega:

```python
# Pristop: loop čez parametre, vektorizirana metrika znotraj
for params in param_grid:
    cfg = Config(**params)
    result = run_strategy(daily, btc_daily, cfg)
    metrics = compute_all_metrics(result.df)
    results.append({**params, **metrics})
df_results = pd.DataFrame(results)
df_results.to_csv(output_path)
```

### 2.2 Grid Search vs Optuna — kdaj kaj

| Situacija | Metoda | Razlog |
|-----------|--------|--------|
| **1 parameter naenkrat** (sensitivity) | Grid search | Preprosto, vizualiziraj kot linijski graf |
| **2 parametra** (interakcija) | Grid search + heatmap | 2D grid je obvladljiv (npr. 10×8 = 80 kombinacij) |
| **3+ parametrov hkrati** | **Optuna** (TPE sampler) | Grid explodira: 10×8×9 = 720. Optuna najde dobre regije v ~200 trialih |
| **Dodatne funkcionalnosti** (A/B test) | Paired comparison | Isti podatki, isti seed — primerjaj staro vs novo |

**Optuna konfiguracija:**
```python
import optuna

def objective(trial):
    track_period = trial.suggest_int("track_period", 45, 90, step=5)
    buffer_pct = trial.suggest_float("buffer_pct", 1.0, 5.0, step=0.5)
    threshold_base = trial.suggest_int("threshold_base", 45, 80, step=5)
    reentry_hold = trial.suggest_int("reentry_hold", 5, 25, step=1)

    cfg = Config(track_period=track_period, track_buf_pct=buffer_pct, ...)
    result = run_strategy(daily, btc_daily=btc, config=cfg)
    metrics = compute_metrics(result.df)

    # Primarni cilj: Calmar. Optuna minimizira, zato negiramo.
    return -metrics["calmar"]

study = optuna.create_study(
    direction="minimize",
    sampler=optuna.samplers.TPESampler(seed=42),
    pruner=optuna.pruners.MedianPruner(),
)
study.optimize(objective, n_trials=300, timeout=3600)
```

**Kdaj Optuna:**
- Faza 2b (multi-parameter optimization)
- Faza 4 (convergence gate tuning)
- Faza 7 (dodatne funkcionalnosti — iskanje optimalnih k za ATR buffer, itd.)

### 2.3 Razširjene metrike — implementacija

Vsa logika gre v `testing/scripts/metrics.py`:

```python
def compute_all_metrics(df, bear_alloc_pct=0.0, fee_pct=0.0):
    """Izračunaj vse metrike za eno simulacijo."""
    close = df["close"]
    ret = close.pct_change().fillna(0.0)
    sig = df["signal_state"]
    is_bull = (sig.shift(1) == S_BULL).astype(float)
    pos = np.where(is_bull, 1.0, bear_alloc_pct / 100.0)
    strat_ret = ret * pos

    # Fees: odštej ob vsakem signal change
    if fee_pct > 0:
        changes = df["signal_changed"].astype(float)
        strat_ret = strat_ret - changes * (fee_pct / 100.0)

    eq = (1.0 + strat_ret).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1.0

    years = len(ret) / 365
    final = float(eq.iloc[-1])
    cagr = final ** (1.0 / years) - 1.0
    ann_ret = strat_ret.mean() * 365
    ann_std = strat_ret.std() * np.sqrt(365)
    neg = strat_ret[strat_ret < 0]
    down_std = neg.std() * np.sqrt(365) if len(neg) > 1 else np.nan
    max_dd = float(dd.min())

    # Osnovne
    sharpe = ann_ret / ann_std if ann_std > 1e-9 else np.nan
    sortino = ann_ret / down_std if down_std > 1e-9 else np.nan
    calmar = cagr / abs(max_dd) if max_dd < -1e-6 else np.nan

    # Omega Ratio (threshold = 0)
    excess = strat_ret
    omega = excess[excess > 0].sum() / abs(excess[excess < 0].sum()) if (excess < 0).any() else np.nan

    # Ulcer Index
    ulcer = np.sqrt((dd**2).mean())

    # Tail Ratio
    p95 = np.percentile(strat_ret.dropna(), 95)
    p5 = np.percentile(strat_ret.dropna(), 5)
    tail_ratio = p95 / abs(p5) if abs(p5) > 1e-9 else np.nan

    # Trade-based metrics
    trades = build_trade_ledger(df)
    closed = [t for t in trades if not t["open"]]
    n_trades = len(closed)
    wins = [t for t in closed if t["pnl_pct"] > 0]
    losses = [t for t in closed if t["pnl_pct"] <= 0]
    win_rate = len(wins) / n_trades * 100 if n_trades else np.nan
    avg_win = np.mean([t["pnl_pct"] for t in wins]) if wins else 0
    avg_loss = np.mean([abs(t["pnl_pct"]) for t in losses]) if losses else 0
    payoff = avg_win / avg_loss if avg_loss > 0 else np.nan
    profit_factor = sum(t["pnl_pct"] for t in wins) / abs(sum(t["pnl_pct"] for t in losses)) if losses else np.nan
    avg_duration = np.mean([t["duration_days"] for t in closed]) if closed else np.nan
    recovery_factor = (final - 1.0) / abs(max_dd) if max_dd < -1e-6 else np.nan
    exposure = pos.mean() * 100

    # Max consecutive losses
    max_consec_loss = 0
    current = 0
    for t in closed:
        if t["pnl_pct"] <= 0:
            current += 1
            max_consec_loss = max(max_consec_loss, current)
        else:
            current = 0

    return {
        "cagr": cagr, "sharpe": sharpe, "sortino": sortino,
        "max_dd": max_dd, "calmar": calmar, "omega": omega,
        "ulcer": ulcer, "tail_ratio": tail_ratio,
        "n_trades": n_trades, "win_rate": win_rate,
        "payoff_ratio": payoff, "profit_factor": profit_factor,
        "avg_duration": avg_duration, "recovery_factor": recovery_factor,
        "max_consec_loss": max_consec_loss, "exposure": exposure,
    }
```

---

## 3. Faze — podrobna izvedba

---

### FAZA 1: Baseline validacija
**Cilj:** Referenčne metrike za vse assete, obe varianti.
**Trajanje:** 1–2 dni
**Predpogoj:** Nič — obstoječa koda zadošča.
**Orodje:** `testing/scripts/run_baseline.py`

#### Korak za korakom:

**1.1 Napiši `run_baseline.py`:**
```python
# Za vsak (asset, varianta) par:
#   1. Fetch data (reuse shared/data_source.py)
#   2. Run strategy z default Config / LeanConfig
#   3. Compute all metrics (osnovna + razširjena)
#   4. Compute B&H metrics za primerjavo
#   5. Zapiši v CSV

ASSETS = ["BTC", "ETH", "SOL", "AVAX", "LINK", "XRP", "BNB", "ADA"]
VARIANTS = ["full", "lean"]
PERIOD = ("2020-01-01", "2026-06-18")  # SOL/AVAX od 2021

for asset in ASSETS:
    for variant in VARIANTS:
        cfg = Config() if variant == "full" else LeanConfig()
        daily = fetch_candles(asset, "1d", bars=2500, config=cfg)
        btc = fetch_btc_daily(bars=2500, config=cfg) if cfg.use_btc_filter else None
        result = run_strategy(daily, btc_daily=btc, config=cfg)
        df = result.df.loc[start:end]
        metrics = compute_all_metrics(df)
        bh_metrics = compute_bh_metrics(df)
        # Save to CSV
```

**1.2 Pogoni skripto in preglej rezultate.**

**1.3 Evaluacija po kriterijih:**
- Za vsak asset preveri 4 kriterije iz Q&A
- Zapiši PASS/FAIL za vsakega
- Posebna pozornost: SOL in AVAX (krajša zgodovina, survivor bias)
- XRP, BNB, ADA so **survivor bias check** — ti asseti NISO bili v originalni testni skupini

**1.4 Full vs Lean primerjava:**
- Tabela: za vsak asset prikaži Calmar(Full), Calmar(Lean), #trades(Full), #trades(Lean)
- Katera varianta ima boljši risk-adjusted return?
- Katera ima manj tradov (manj šuma)?

**1.5 Bear alloc sensitivity:**
- Samo BTC, samo Full varianta
- Pogoni z bear_alloc = 0, 5, 10, 15, 20, 25, 30%
- Izriši: bear_alloc vs CAGR, bear_alloc vs Max DD, bear_alloc vs Calmar
- Najdi "sweet spot" kjer Calmar pade minimalno ampak Max DD se občutno zmanjša

**1.6 Vizualni pregled:**
- Odpri dashboard za BTC Full, 2020–2026
- Scrollaj skozi chart in preveri: ali je kdaj BEAR signal aktiven med očitnim 50%+ rallyjem za več kot 2 meseca?
- Naredi screenshot vsakega sumljivega obdobja
- Zapiši v TESTING_LOG.md

**Output Faze 1:**
- `testing/results/phase1/baseline_all_assets.csv`
- `testing/results/phase1/bear_alloc_sensitivity.csv`
- `testing/reports/phase1_report.md`
- Screenshots v `testing/results/phase1/screenshots/`

**Gate za nadaljevanje:** Vsaj 6 od 8 assetov mora PASS-ati vse 4 kriterije. Če ne — preglej zakaj in dokumentiraj pred nadaljevanjem.

---

### FAZA 2: Sensitivity analiza
**Cilj:** Najdi robustne parametre, identificiraj preobčutljive.
**Trajanje:** 2–3 dni
**Predpogoj:** Faza 1 zaključena (imamo baseline za primerjavo).
**Orodje:** `testing/scripts/run_sensitivity.py`

#### Faza 2a: Enoparametrski sweep (Grid Search)

Za vsakega od 10 parametrov posebej (ostali ostanejo default):

| # | Parameter | Vrednosti | #runs |
|---|-----------|-----------|-------|
| 2a.1 | track_period | 45, 50, 55, 60, 65, 70, 75, 80, 85, 90 | 10 |
| 2a.2 | track_buf_pct | 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0 | 8 |
| 2a.3 | base_threshold | 40, 45, 50, 55, 60, 65, 70, 75, 80 | 9 |
| 2a.4 | reentry_hold | 5, 7, 10, 12, 15, 18, 20, 25 | 8 |
| 2a.5 | exit_grace_bars | 1, 2, 3, 4, 5 | 5 |
| 2a.6 | confirm_bars | 1, 2, 3, 4, 5 | 5 |
| 2a.7 | er_thresh | 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40 | 7 |
| 2a.8 | conv_smooth | 2, 3, 5, 7, 10 | 5 |
| 2a.9 | blowoff_dist_pct | 15, 20, 25, 30, 35, 40 | 6 |
| 2a.10 | vol_shock_mul | 1.2, 1.3, 1.5, 1.8, 2.0, 2.5 | 6 |

**Skupaj:** ~69 run-ov na BTC. Pri ~1s/run = ~1 minuta.

**Tehnika za vsakega:**
```python
# Pseudo-koda za 2a.1
param_name = "track_period"
values = [45, 50, 55, 60, 65, 70, 75, 80, 85, 90]
results = []
for v in values:
    cfg = Config(track_period=v)  # ostali default
    result = run_strategy(daily, btc, cfg)
    m = compute_all_metrics(result.df)
    results.append({"track_period": v, **m})

df = pd.DataFrame(results)
df.to_csv("testing/results/phase2/sweep_track_period.csv")

# Vizualizacija:
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
axes[0,0].plot(df["track_period"], df["calmar"]); axes[0,0].set_title("Calmar")
axes[0,1].plot(df["track_period"], df["max_dd"]); axes[0,1].set_title("Max DD")
axes[1,0].plot(df["track_period"], df["n_trades"]); axes[1,0].set_title("#Trades")
axes[1,1].plot(df["track_period"], df["sharpe"]); axes[1,1].set_title("Sharpe")
fig.savefig("testing/results/phase2/sweep_track_period.png")
```

**Robustnost check za vsak parameter:**
```python
# Parameter je robusten če:
# 1. Optimalna vrednost ni na robu range-a (edge effect)
# 2. Sosednje vrednosti (±1 korak) dajo Calmar znotraj ±20% optimuma
# 3. Ni spike-a (ena vrednost drastično boljša od vseh)
for i in range(1, len(df)-1):
    left = df.iloc[i-1]["calmar"]
    center = df.iloc[i]["calmar"]
    right = df.iloc[i+1]["calmar"]
    robustness = min(left, right) / center  # blizu 1.0 = robusten
```

**Zapiši za vsak parameter:** optimalna vrednost, robustnost score (0–1), graf.

#### Faza 2b: Multi-parameter optimization (Optuna)

**Ko:** Po 2a, ko vemo kateri parametri so občutljivi.
**Zakaj Optuna in ne Grid:** Če optimiziramo 4 parametre hkrati z po 8 vrednostmi = 4096 kombinacij = ~1 ura. Optuna to naredi v 200–300 trialih (~5 min) s TPE samplerjem.

**Kateri parametri:**
Samo tiste, ki so v 2a pokazali visoko občutljivost (robustnost < 0.7). Tipiočno: track_period, buffer_pct, threshold, reentry_hold.

```python
import optuna

def objective(trial):
    track_period = trial.suggest_int("track_period", 55, 85, step=5)
    buffer_pct = trial.suggest_float("buffer_pct", 1.5, 4.5, step=0.5)
    # Dodaj samo občutljive parametre

    cfg = Config(track_period=track_period, track_buf_pct=buffer_pct, ...)
    result = run_strategy(daily, btc, cfg)
    m = compute_all_metrics(result.df)

    # Multi-objective: Calmar + kaznovati preveč tradov
    score = m["calmar"] - 0.01 * max(0, m["n_trades"] - 20)
    return -score  # Optuna minimizira

study = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=42))
study.optimize(objective, n_trials=300)

# Top 10 kombinacij:
top10 = study.trials_dataframe().nsmallest(10, "value")
```

**Cross-asset validacija:**
- Vzemi top 3 parametrske kombinacije iz BTC optimizacije
- Pogoni jih na ETH in SOL **brez sprememb**
- Če Calmar ostane > 50% BTC vrednosti → parametri so robustni
- Če pade pod 30% → overfitting na BTC, uporabi BTC default-e

**Output Faze 2:**
- `testing/results/phase2/sweep_*.csv` (10 datotek)
- `testing/results/phase2/sweep_*.png` (10 grafov)
- `testing/results/phase2/optuna_multi_param.csv`
- `testing/results/phase2/cross_asset_validation.csv`
- `testing/reports/phase2_report.md`

**Gate:** Identificiranih <= 3 parametrov ki zahtevajo spremembo od default-a. Če jih je več, strategija ni robustna.

---

### FAZA 3: Walk-Forward validacija
**Cilj:** Dokaži da parametri niso overfitted na celoten dataset.
**Trajanje:** 2–3 dni
**Predpogoj:** Faza 2 zaključena — imamo "optimalne" parametre.
**Orodje:** `testing/scripts/run_walkforward.py`

#### Tehnika: Anchored Walk-Forward

```
Okno 1:  [====== TRAIN 2020-01 → 2022-06 ======][== TEST 2022-07 → 2023-06 ==]
Okno 2:  [======== TRAIN 2020-01 → 2023-06 ========][== TEST 2023-07 → 2024-06 ==]
Okno 3:  [========== TRAIN 2020-01 → 2024-06 ==========][== TEST 2024-07 → 2025-06 ==]
Okno 4:  [============ TRAIN 2020-01 → 2025-06 ============][== TEST 2025-07 → 2026-06 ==]
```

**Zakaj anchored (ne rolling):** Vedno začnemo od 2020 — damo modelu vse zgodovinske podatke. Test je vedno naslednje polletje.

#### Korak za korakom:

**3.1 Za vsako okno:**
1. Na TRAIN podatkih: pogoni Optuna (100 trialov) → najdi najboljše parametre
2. Na TEST podatkih: pogoni strategijo z optimiziranimi parametri
3. Zapiši: in-sample Calmar, out-of-sample Calmar, parametre

**3.2 Primerjaj:**
```python
results = []
for window in walk_forward_windows:
    # Optimiziraj na train
    best_params = optuna_optimize(train_data, n_trials=100)
    # Testiraj na test
    in_sample = compute_all_metrics(run_on_train(best_params))
    out_sample = compute_all_metrics(run_on_test(best_params))
    results.append({
        "window": window,
        "is_calmar": in_sample["calmar"],
        "oos_calmar": out_sample["calmar"],
        "oos_ratio": out_sample["calmar"] / in_sample["calmar"],
        **best_params,
    })
```

**3.3 Walk-Forward Efficiency (WFE):**
```
WFE = mean(OOS_Calmar) / mean(IS_Calmar)
```
- WFE > 0.5 = dobro (out-of-sample je vsaj 50% in-sample)
- WFE > 0.7 = odlično
- WFE < 0.3 = overfit

**3.4 Stabilnost parametrov:**
Preveri ali se optimalni parametri drastično spreminjajo med okni:
- Če track_period skače med 50 in 90 → parameter ni stabilen → uporabi default
- Če ostane v ozkem pasu (70–80) → stabilen

**3.5 Multi-asset walk-forward:**
- Optimiziraj na BTC
- Testiraj na ETH, SOL brez re-optimizacije
- Če deluje → strategija je robustna across assets
- Če ne → asset-specific parametri (manj zaželeno)

**Pass kriteriji:**
- WFE > 0.4
- Noben test window nima OOS Sharpe < -0.5
- Parametri so stabilni (std < 20% mean-a)
- Multi-asset OOS Calmar > 30% BTC IS Calmar

**Output:**
- `testing/results/phase3_walkforward/wf_results.csv`
- `testing/results/phase3_walkforward/wf_params_stability.csv`
- `testing/reports/phase3_report.md`

---

### FAZA 4: Monte Carlo + Bootstrap validacija
**Cilj:** Kvantificiraj zaupanje v rezultate — p-values in confidence intervals.
**Trajanje:** 1–2 dni
**Predpogoj:** Faza 2 zaključena (imamo optimalne parametre).
**Orodje:** `testing/scripts/run_montecarlo.py`

#### Test 4.1: Trade shuffle bootstrap (5000 iteracij)

**Kaj:** Naključno premeši vrstni red zaprtih tradov. Ohrani trade P&L-e ampak razbij časovni vrstni red.

```python
trades_pnl = [t["pnl_pct"] for t in closed_trades]
mc_max_dd = []
mc_cagr = []

for i in range(5000):
    shuffled = np.random.permutation(trades_pnl)
    eq = np.cumprod(1 + shuffled / 100)
    peak = np.maximum.accumulate(eq)
    dd = (eq / peak - 1).min()
    mc_max_dd.append(dd)
    mc_cagr.append(eq[-1] ** (1/years) - 1)

# 95% confidence interval za Max DD:
dd_ci_lower = np.percentile(mc_max_dd, 2.5)
dd_ci_upper = np.percentile(mc_max_dd, 97.5)
actual_dd = compute_actual_max_dd()

# Interpretacija:
# Če actual_dd je v spodnjih 5% mc_max_dd → strategija ima nadpovprečno
# dober risk management (ni samo sreča z vrstnim redom)
```

**Zakaj:** Preveri ali je nizek Max DD posledica dobrega upravljanja ali zgolj srečnega vrstnega reda tradov.

#### Test 4.2: Return shuffle (5000 iteracij)

**Kaj:** Naključno premeši dnevne returne in pogoni strategijo na premešanih podatkih. Primerja Sharpe dejanskih rezultatov z distribucijo naključnih.

```python
actual_sharpe = compute_sharpe(actual_returns)
mc_sharpes = []

for i in range(5000):
    shuffled_prices = generate_from_shuffled_returns(close)
    # Re-run strategijo na shuffled cenah (signali se spremenijo!)
    result = run_strategy(shuffled_data, btc, cfg)
    mc_sharpes.append(compute_sharpe(result))

p_value = (np.array(mc_sharpes) >= actual_sharpe).mean()
# p < 0.05 → strategija ima statistično značilen edge
```

**Zakaj:** Preveri ali bi strategija delala na naključnih podatkih z isto distribucijo. Če da → ni pravega edge-a.

#### Test 4.3: Parameter noise (1000 iteracij)

**Kaj:** Dodaj naključni šum (±10%) na vsak parameter. Koliko se metrike spremenijo?

```python
base_params = {"track_period": 75, "buffer_pct": 3.0, ...}
mc_metrics = []

for i in range(1000):
    noisy = {}
    for k, v in base_params.items():
        noise = np.random.uniform(0.9, 1.1)  # ±10%
        if isinstance(v, int):
            noisy[k] = max(1, round(v * noise))
        else:
            noisy[k] = v * noise
    result = run_strategy(daily, btc, Config(**noisy))
    mc_metrics.append(compute_all_metrics(result.df))

calmar_std = np.std([m["calmar"] for m in mc_metrics])
calmar_mean = np.mean([m["calmar"] for m in mc_metrics])
cv = calmar_std / calmar_mean  # coefficient of variation

# CV < 0.20 → robusten
# CV > 0.50 → overfit (majhne spremembe = veliki efekti)
```

**Zakaj:** Preveri ali so parametri na "vrhu hriba" (robusten) ali na "ostri konici" (overfit).

#### Test 4.4: Bootstrap confidence intervals

```python
# 95% CI za vse ključne metrike
for metric_name in ["cagr", "sharpe", "calmar", "max_dd"]:
    bootstrap_values = []
    for i in range(5000):
        # Resample daily returns z zamenjavo
        sample = strat_ret.sample(frac=1.0, replace=True)
        eq = (1 + sample).cumprod()
        bootstrap_values.append(compute_metric(eq, metric_name))

    ci_lower = np.percentile(bootstrap_values, 2.5)
    ci_upper = np.percentile(bootstrap_values, 97.5)
    print(f"{metric_name}: {ci_lower:.3f} — {ci_upper:.3f}")
```

**Pass kriteriji:**
- p-value (test 4.2) < 0.05
- Parameter noise CV (test 4.3) < 0.30
- 95% CI za Sharpe ne vključuje 0
- 95% CI za Calmar > 0.5

**Output:**
- `testing/results/phase4_montecarlo/trade_shuffle.csv`
- `testing/results/phase4_montecarlo/return_shuffle.csv`
- `testing/results/phase4_montecarlo/parameter_noise.csv`
- `testing/results/phase4_montecarlo/confidence_intervals.csv`
- `testing/reports/phase4_report.md`

---

### FAZA 5: Implementacija Pipe 2 + Pipe 3
**Cilj:** Dodaj on-chain in macro podatke, implementiraj convergence gate.
**Trajanje:** 1–2 tedna
**Predpogoj:** Faza 1 zaključena.

#### Korak za korakom:

**5.1 Data source implementacija:**

| Podatek | Vir | API | Frekvenca | Fallback |
|---------|-----|-----|-----------|----------|
| MVRV | CoinGlass API ali Glassnode | REST, API key | Dnevno | Pipe vrne NEUTRAL |
| Coinbase Premium | Coinbase Pro API (BTC-USD) vs Binance (BTCUSDT) | REST, brez key | Dnevno | Pipe vrne NEUTRAL |
| BBB Spread | FRED API (BAMLC0A4CBBB) | REST, brez key | Dnevno (business days, ffill vikende) | Pipe vrne NEUTRAL |
| DXY | Yahoo Finance (DX-Y.NYB) ali FRED (DTWEXBGS) | yfinance / REST | Dnevno | Pipe vrne NEUTRAL |

**5.2 Pipe 2 logika (on-chain):**
```python
def compute_onchain_pipe(mvrv, cb_premium_smoothed):
    mvrv_overheated = mvrv >= 3.5
    mvrv_elevated = mvrv >= 2.5
    mvrv_healthy = (mvrv >= 1.0) & (mvrv < 2.5)
    mvrv_undervalued = mvrv < 1.0

    cb_bull = cb_premium_smoothed > 0.0
    cb_bear = cb_premium_smoothed < -0.001  # -0.1%

    if mvrv_overheated or (mvrv_elevated and cb_bear):
        return BEAR
    elif (mvrv_healthy or mvrv_undervalued) and cb_bull:
        return BULL
    else:
        return NEUTRAL
```

**5.3 Pipe 3 logika (macro):**
```python
def compute_macro_pipe(bbb_spread, bbb_ma63, dxy_yoy):
    bbb_bull = bbb_spread < bbb_ma63
    bbb_bear = bbb_spread > bbb_ma63 * 1.10

    dxy_bull = dxy_yoy < 0
    dxy_bear = dxy_yoy > 2.0

    if bbb_bull and dxy_bull:
        return BULL
    elif bbb_bear and dxy_bear:
        return BEAR
    else:
        return NEUTRAL
```

**5.4 Convergence gate:**
```python
def convergence_gate(tech_state, onchain_state, macro_state):
    # Entry: tech mora biti BULL + max 1 od ostalih v BEAR
    bear_count = (onchain_state == BEAR) + (macro_state == BEAR)

    if tech_state == BULL and bear_count <= 1:
        return BULL

    # Exit: samo technical conditions (blow-off, vol shock, trackline break)
    # Non-tech pipes NIKOLI ne triggerajo exit-a sami
    if tech_state == BEAR:
        return BEAR

    return NEUTRAL  # hold previous
```

**5.5 MVRV-enhanced blow-off:**
```python
# Ko MVRV >= 3.5, znižaj blowoff prag z 25% na 17.5%
effective_blowoff = 17.5 if mvrv >= 3.5 else cfg.blowoff_dist_pct
blowoff = (dist_pct > effective_blowoff) & (rsi > 80)
```

**5.6 Testiranje:**
- Primerjaj metrike: Tech only vs Tech+OnChain vs Tech+OnChain+Macro
- Za vsako kombinacijo 3 pipe-ov: zapiši vse metrike
- Preveri: ali macro/onchain dodajata vrednost ali samo zmanjšujeta exposure brez koristi?

---

### FAZA 6: Integracijsko testiranje
**Cilj:** Full pipeline testiranje z vsemi pipe-i in fees.
**Trajanje:** 3–5 dni
**Predpogoj:** Faza 5 zaključena.

**6.1 Full pipeline backtest:**
- BTC 2020–2026, vsi 3 pipe-i, optimizirani parametri iz Faze 2
- Vse metrike + regime analiza

**6.2 Pipe contribution analysis:**
- Pogoni 4 konfiguracije: Tech, Tech+OC, Tech+Macro, Tech+OC+Macro
- Za vsako izračunaj Calmar, Max DD, #trades
- Tabela: kateri pipe dodaja največ vrednosti?

**6.3 Convergence gate sensitivity:**
- Testiraj: bear_count <= 0 (zelo strogo), <= 1 (default), <= 2 (zelo ohlapno)
- Kateri da najboljši Calmar?

**6.4 Fees + slippage:**
```python
# Model:
FEE_PCT = 0.10  # 0.1% per trade (Binance taker)
SLIPPAGE_BTC = 0.05  # 0.05% za BTC
SLIPPAGE_ALT = 0.10  # 0.10% za altcoine

# Implementacija: odštej ob vsakem signal change
total_cost_per_trade = (FEE_PCT + slippage) * 2  # entry + exit
# Za 15 tradov: ~15 * 0.3% = ~4.5% total drag
```

**6.5 Variant A vs B z vsemi pipe-i:**
- A = Full (Pro v3) z vsemi pipe-i
- B = Lean z vsemi pipe-i (ali morda convergence gate brez conviction, samo trackline rules)
- Primerjaj: kateri da boljši Calmar neto po fees?

---

### FAZA 7: Testiranje dodatnih funkcionalnosti
**Cilj:** Testiraj vsako Q&A idejo kot A/B test proti baseline-u.
**Trajanje:** 1–2 tedna (lahko vzporedno z drugimi fazami)
**Metoda:** Za vsako funkcionalnost: implementiraj → pogoni na BTC → primerjaj z baseline

#### 7.1 Dinamičen buffer (ATR-based)
**Kdaj testirati:** Po Fazi 2a (ko vemo kako občutljiv je buffer_pct)
**Implementacija:**
```python
atr14 = ATR(high, low, close, 14)
buffer = k * atr14 / close  # k ∈ [1.5, 3.0]
# k optimiziraj z grid search: 1.0, 1.5, 2.0, 2.5, 3.0
```
**A/B test:** Fiksni 3% buffer vs ATR-based z optimiziranim k
**Metriki:** Calmar, #trades, Max DD
**Razširitev:** Testiraj tudi asimetrični buffer (k_up = 2.0, k_down = 1.5)

#### 7.2 Position sizing (Kelly Criterion)
**Kdaj testirati:** Po Fazi 1 (potrebujemo win rate in payoff ratio iz baseline-a)
**Implementacija:**
```python
# Izračunaj iz zadnjih 20 tradov (rolling)
p = rolling_win_rate
b = rolling_avg_win / rolling_avg_loss
kelly_fraction = (p * b - (1 - p)) / b
half_kelly = kelly_fraction / 2
position_size = np.clip(half_kelly, 0.0, 1.0)  # 0% do 100%

strat_ret = ret * position_size  # namesto binarno 0/1
```
**A/B test:** Binary (0/100%) vs Half-Kelly vs Quarter-Kelly
**Metriki:** Calmar, Max DD, CAGR — Kelly naj zmanjša DD brez prevelikega padca CAGR
**Opozorilo:** Kelly je občutljiv na napake v p in b — zato Half-Kelly

#### 7.3 Adaptivni conviction thresholds
**Kdaj testirati:** V Fazi 2a poleg diskretnih thresholdov
**Implementacija:**
```python
# Varianta 1: Linearna
threshold = 55 + 15 * np.clip(vol_z, -1, 1) * 0.5 + 0.5  # 55 do 70

# Varianta 2: Sigmoid (gladka)
threshold = 55 + 15 / (1 + np.exp(-2 * vol_z))  # S-krivulja med 55 in 70
```
**A/B test:** Diskretni (55/60/70) vs linearni vs sigmoid
**Metriki:** Calmar, signal smoothness (koliko flip-ov med režimi?)

#### 7.4 Z-score normalizacija conviction komponent
**Kdaj testirati:** Po Fazi 2 (ko vemo katere komponente so občutljive)
**Implementacija:**
```python
# Namesto fiksnega range [-5%, +5%] za trend:
rolling_mean = dist_pct.rolling(200).mean()
rolling_std = dist_pct.rolling(200).std()
trend_z = (dist_pct - rolling_mean) / rolling_std
trend_normalized = np.clip(trend_z / 2 + 0.5, 0, 1)  # map [-2σ,+2σ] → [0,1]
trend_score = trend_normalized * 30

# Isto za EMA spread, volume ratio, drawdown
```
**A/B test:** Fiksni range vs z-score za vsako komponento
**Metriki:** Calmar, cross-asset performance (z-score bi moral boljše delati na altcoinih)

#### 7.5 Rolling peak (365d) za drawdown brake
**Kdaj testirati:** V Fazi 2 kot modifikacija drawdown komponente
**Implementacija:**
```python
peak_rolling = close.rolling(365, min_periods=200).max()
dd_rolling = (close - peak_rolling) / peak_rolling * 100
# Namesto:
# peak = close.cummax()
# dd = (close - peak) / peak * 100
```
**A/B test:** All-time peak vs 365d rolling peak
**Metriki:** Calmar, ali strategija hitreje okreva po dolgem bear market-u?

#### 7.6 Dinamičen re-entry lock
**Kdaj testirati:** V Fazi 2 poleg fiksnega reentry_hold
**Implementacija:**
```python
# Base 15, prilagodi z vol_z
base = 15
dynamic_reentry = np.clip(base - vol_z * 5, 5, 30).astype(int)
# High vol (z=2): 15-10=5 barov (hitro nazaj)
# Low vol (z=-2): 15+10=25 barov (počakaj)
```
**A/B test:** Fiksnih 15 vs dinamičen
**Metriki:** #trades, missed entries, Calmar

#### 7.7 Weekend skip test
**Kdaj testirati:** V Fazi 1 kot del baseline-a
**Implementacija:** Že obstaja `skip_weekend` config flag
**A/B test:** skip_weekend=True vs False
**Metriki:** #trades, ali vikendni signali dodajajo ali škodijo?

#### 7.8 Profit taking
**Kdaj testirati:** Po Fazi 6 (ko imamo fees model)
**Implementacija:**
```python
# Varianta A: Fixed profit taking
if unrealized_pnl >= 50:
    reduce_position_by(25%)
if unrealized_pnl >= 100:
    reduce_position_by(25%)

# Varianta B: Trailing stop
trailing_stop = max_unrealized * (1 - 0.15)  # 15% od vrha
if unrealized_pnl < trailing_stop:
    exit_position()

# Varianta C: Conviction-based
if conviction < threshold + 10 and unrealized_pnl > 30:
    reduce_position_by(50%)  # conviction pada ampak še ni BEAR
```
**A/B test:** Brez profit taking vs Fixed vs Trailing vs Conviction-based
**Metriki:** CAGR (bo nižji), Max DD (bo nižji), Calmar (ali se izboljša?)

#### 7.9 Fees + slippage model
**Kdaj testirati:** V Fazi 6 obvezno — pred tem vse metrike so brez fees
**Implementacija:**
```python
def apply_fees(strat_ret, signal_changed, fee_pct=0.10, slippage_pct=0.05):
    total_cost = (fee_pct + slippage_pct) / 100.0 * 2  # entry + exit
    costs = signal_changed.astype(float) * total_cost
    return strat_ret - costs
```
**Testni scenariji:**
- Optimist: 0.075% fee + 0.03% slippage (BNB popust, BTC likvidnost)
- Realist: 0.10% fee + 0.05% slippage
- Pesimist: 0.10% fee + 0.10% slippage (altcoini)

---

## 4. Režimska analiza — kdaj in kako

**Izvedi v:** Fazi 1 (baseline) in Fazi 6 (integracija).

**Implementacija:**
```python
def classify_regime(df):
    sma200 = df["close"].rolling(200).mean()
    regimes = pd.Series("sideways", index=df.index)
    regimes[(df["close"] > sma200) & (sma200 > sma200.shift(20))] = "bull"
    regimes[(df["close"] < sma200) & (sma200 < sma200.shift(20))] = "bear"

    # Volatility overlay
    vol_z = compute_vol_z(df)
    regimes[vol_z > 1.0] = regimes[vol_z > 1.0] + "_highvol"
    regimes[vol_z < -1.0] = regimes[vol_z < -1.0] + "_lowvol"
    return regimes

# Per-regime metrike:
for regime in ["bull", "bear", "sideways", "bull_highvol", "bear_highvol"]:
    mask = (regimes == regime)
    regime_ret = strat_ret[mask]
    regime_metrics = compute_metrics_from_returns(regime_ret)
```

---

## 5. Časovnica in zaporedje

```
Teden 1:
  Dan 1-2:  FAZA 1 — Baseline (run_baseline.py, vizualni pregled)
  Dan 2-3:  FAZA 7.7 — Weekend skip test (hiter, del baseline-a)
  Dan 3-5:  FAZA 2a — Enoparametrski sweep (run_sensitivity.py)

Teden 2:
  Dan 1-2:  FAZA 2b — Optuna multi-parameter + cross-asset validacija
  Dan 2-3:  FAZA 7.1-7.6 — A/B testi dodatnih funkcionalnosti
  Dan 3-5:  FAZA 3 — Walk-forward (run_walkforward.py)

Teden 3:
  Dan 1-2:  FAZA 4 — Monte Carlo (run_montecarlo.py)
  Dan 3-5:  FAZA 5 — Pipe 2+3 implementacija (data sources)

Teden 4:
  Dan 1-3:  FAZA 5 — Pipe 2+3 logika + convergence gate
  Dan 3-5:  FAZA 6 — Integracijsko testiranje + fees

Teden 5:
  Dan 1-2:  FAZA 7.8 — Profit taking
  Dan 3-5:  Finalni report, odločitev o parametrih, priprava za paper trading
```

---

## 6. Odločitvena drevesa

### Po Fazi 1:
```
Ali vsi 4 kriteriji PASS na BTC?
├─ DA → nadaljuj s Fazo 2
└─ NE → Kateri kriterij FAIL?
    ├─ Max DD previsok → preveri buffer_pct in exit_grace
    ├─ CAGR prenizek → preveri threshold in confirm_bars
    ├─ Preveč signalov → preveri reentry_hold in ER thresh
    └─ Napačen signal > 2 meseca → vizualno preglej, diagnosticiraj
```

### Po Fazi 2:
```
Ali so parametri robustni (CV < 0.20)?
├─ DA → uporabi optimalne, nadaljuj s Fazo 3
└─ NE → Kateri parametri so občutljivi?
    ├─ 1-2 parametra → A/B testiraj alternativne pristope (7.1-7.6)
    └─ 3+ parametrov → strategija je fundamentalno krhka, razmisli o poenostavitvi
```

### Po Fazi 3 (walk-forward):
```
Ali je WFE > 0.4?
├─ DA → parametri so validni, nadaljuj
└─ NE → overfit!
    ├─ Zmanjšaj število optimiziranih parametrov
    ├─ Uporabi privzete vrednosti (iz Pine)
    └─ Povečaj train window
```

### Po Fazi 4 (Monte Carlo):
```
Ali je p-value < 0.05?
├─ DA → statistično značilen edge, nadaljuj z Pipe 2+3
└─ NE → ni dovolj dokazov za edge
    ├─ Preveri ali je premalo tradov (< 30) → daljše obdobje
    ├─ Preveri ali je strategija preveč v cashu (exposure < 30%)
    └─ Razmisli ali je Technical pipe dovolj sam — morda pipe 2+3 pomagajo
```

---

## 7. Viri

- [Coin Bureau: How To Backtest Crypto Strategy 2026](https://coinbureau.com/guides/how-to-backtest-your-crypto-trading-strategy)
- [Python Backtesting Libraries 2026](https://rmbell09-lang.github.io/tradesight/blog/python-backtesting-libraries-2026.html)
- [Monte Carlo Simulations for Strategy Validation](https://quantproof.io/blog/monte-carlo-simulations-trading-strategy-validation)
- [Overfitting Prevention in Trading](http://adventuresofgreg.com/blog/2025/12/18/avoid-overfitting-testing-trading-rules/)
- [Omega Ratio](https://www.pfolio.io/academy/omega-ratio)
- [Trend Following in Crypto (arXiv)](https://arxiv.org/pdf/2009.12155)
- [Adaptive Portfolio Construction in Crypto (arXiv 2026)](https://arxiv.org/pdf/2602.11708)
- Diversitas Strategy Spec v1.0 — `strategyDescription/Copy of Diversitas_Trading_Signal_Engine_Spec (1).docx`
- Diversitas Q&A — `strategyDescription/Diversitas_vprašanja_3.6.2026.docx`
