# Diversitas — Statistical Validation & Improvement Testing Plan (v3, Lean + Momentum)

## Context

Two production-candidate strategies now exist as Python ports of Pine scripts:
**Lean** (`lean/diversitas/`, hard bear block, 75-bar trackline, binary 0/100 alloc) and
**Momentum** (`momentum/diversitas/`, soft 50% bear cut, 35-bar trackline, trailing stop,
vol-scaled alloc). An existing `testing/TESTING_PLAN.md` (v2, 2026-06-18) laid out a solid
program but (a) targets **Full + Lean** — momentum did not exist yet, and (b) predates a set
of explicit methodological criticisms that any serious reviewer will raise:

> Grid search for "optimal" params (curve-fitting to the past) · lack of Monte Carlo ·
> lack of out-of-sample testing · high correlation/beta with BTC · lack of statistical
> methods · lack of stability tests.

Separately, the Q&A doc (`strategyDescription/Diversitas_vprašanja_3.6.2026.docx`) contains
~20 concrete improvement ideas (dynamic ATR buffer, Kelly sizing, z-score conviction,
rolling-peak drawdown, ATR-based blow-off, dynamic re-entry lock, EMA vol_z, linear
thresholds, profit-taking, weekend-skip, fees/slippage…).

**Goal of this plan:** a single, sequenced, statistically-defensible testing campaign that
(1) validates Lean and Momentum with methods that directly rebut each of the 6 criticisms,
and (2) A/B-tests every Q&A improvement idea **one at a time, gated**, so we always know what
works before stacking the next change. Full is kept only as a comparison reference (not
optimized). Deliverable: this plan **plus** a reusable testing harness so every phase is
immediately runnable.

---

## How each criticism is rebutted (the core of the plan)

| # | Criticism | Rebuttal method | Phase |
|---|-----------|-----------------|-------|
| 1 | **Grid search / curve-fitting** | Never accept a param from in-sample grid alone. Every param passes anchored **walk-forward** + **Combinatorial Purged CV (CPCV)**; final numbers reported on an **untouched hold-out** (last ~15 months, quarantined from day 1). | 5, 8 |
| 2 | **No Monte Carlo** | Four MC families: **stationary block bootstrap** (Politis–Romano, preserves vol clustering — *not* naive shuffle), **trade-order shuffle**, **parameter-noise** perturbation, **synthetic GBM/blocks** re-run. Report CIs + p-values, not point estimates. | 4 |
| 3 | **No out-of-sample** | Anchored walk-forward (4 folds) + CPCV (many backtest paths) + a final hold-out never seen during any tuning. **Walk-Forward Efficiency** and **PBO** quantify it. | 5, 8 |
| 4 | **High BTC correlation/beta** | OLS of strategy returns on BTC returns → **α, β, R², Newey–West HAC t-stat**; rolling 90d β/corr; build a **BTC-β-hedged** return series and re-score. Proves edge is *not* just BTC exposure. | 2 |
| 5 | **No statistical methods** | **Deflated Sharpe Ratio** (Bailey–López de Prado, corrects for #trials, skew, kurtosis) as the acceptance gate; **Probability of Backtest Overfitting (PBO)**; **White's Reality Check / Hansen SPA** across the config set; bootstrap CIs; a maintained **trial counter** feeding the DSR. | 4, 5, 7 |
| 6 | **No stability tests** | Parameter-noise **coefficient of variation**; parameter **stability across WF folds** (std/mean); **regime-conditional** metrics (bull/bear/chop × hi/lo vol); **data-source robustness** (Binance vs Coinbase); look-ahead audit. | 3, 4, 6 |

**Golden rule enforced throughout:** a maintained counter `N_trials` (every distinct config
ever scored on a given asset) is logged; the DSR uses it so we can never "find one good run
in 500" and call it significant.

---

## Deliverables

1. **`testing/TESTING_PLAN_v3.md`** — this campaign, committed to the repo (supersedes v2 for lean+momentum; v2 kept for history).
2. **Testing harness** under `testing/scripts/`:
   - `engine.py` — variant-agnostic runner. Reuses the `_switch_variant()` pattern already in `regression_test.py:31` to import `diversitas` from `lean/` or `momentum/`; wraps `run_strategy()` + a shared position model (`_pos_from_df` logic from `momentum/diversitas/dashboard.py:117`).
   - `metrics.py` — `compute_all_metrics()` (CAGR/Sharpe/Sortino/Calmar/Omega/Ulcer/tail/trade-stats/exposure) — lifted from the v2 plan's spec and the dashboard's `_stats()` (`*/dashboard.py`). Single source of truth for both dashboards and tests.
   - `stats.py` — `deflated_sharpe()`, `prob_backtest_overfit()` (CPCV), `stationary_bootstrap()`, `alpha_beta_regression()` (Newey–West), `whites_reality_check()`.
   - `dataio.py` — cached loader wrapping `shared/data_source.py` `fetch_candles`/`fetch_btc_daily`, writing Parquet snapshots to `testing/data/` so the **whole campaign runs on frozen data** (reproducible, no API drift mid-study).
   - `run_baseline.py`, `run_btc_dependence.py`, `run_sensitivity.py`, `run_montecarlo.py`, `run_walkforward.py`, `run_cpcv.py`, `run_optuna.py`, `run_feature_ab.py`, `run_final.py` — one per phase.
3. **`testing/results/phaseN/…`** CSVs + PNGs, **`testing/reports/phaseN_report.md`**, appended to `testing/TESTING_LOG.md`.

Directory:
```
testing/
  scripts/{engine,metrics,stats,dataio,run_*}.py
  data/                # frozen Parquet snapshots (git-ignored, hash logged)
  results/phase{0..8}/
  reports/phase{0..8}_report.md
  TESTING_PLAN_v3.md   TESTING_LOG.md
```

---

## Data & reproducibility (fixed once, up front)

- **Assets:** BTC, ETH, SOL, AVAX, LINK (original set) **+ XRP, BNB, ADA** as an explicit
  *survivor-bias control group* (never used for tuning; OOS-only sanity check).
- **Window:** full available history per asset → split into **Design set** (start → 2025-03-31)
  and **Hold-out** (2025-04-01 → today, ~15 months) **quarantined from day 1**. Nothing in
  phases 1–7 may read the hold-out.
- **Freeze data** to Parquet with a logged SHA so re-runs are bit-identical (removes the
  "results changed because the API returned different candles" failure mode).
- **Benchmark:** per-asset Buy&Hold + BTC (for β) + SPX (already wired via `fetch_spx_daily`).
- All returns use `close.pct_change()`, positions use `shift(1)` (look-ahead audit in Phase 0).
- `trading_days=365` crypto / `252` ETFs (already handled per-config).

---

## Phases (sequential; each has a hard gate before the next)

### Phase 0 — Harness + metrics (foundation)
Build `engine/metrics/stats/dataio`. **Unit-test** `metrics.py` against hand-computed toy
series (a known equity curve with known Max DD/Sharpe) and cross-check against the live
dashboard `_stats()` on one asset (must match to 1e-6). Look-ahead audit: assert every
position series is a function of `shift(1)` signals only.
**Gate:** metrics match dashboard + toy fixtures; unit tests green (`pytest testing/`).

### Phase 1 — Baseline (Lean + Momentum, all assets)
`run_baseline.py`: for each (asset × {lean, momentum}) on the **Design set**, compute full
metric panel + B&H, evaluate the 4 Q&A success criteria (Max DD < B&H, CAGR ≥ 60% B&H,
< 20 signals / 3 yr, no > 2-month wrong-signal window). Visual scan for wrong-regime periods.
Lean-vs-Momentum head-to-head table. Initialize `N_trials` counter.
**Gate:** ≥ 6/8 assets pass on at least one variant; baseline panel archived.

### Phase 2 — BTC dependence (criticism #4, done early because it's fundamental)
`run_btc_dependence.py`, for each altcoin strategy + the blended portfolio:
- OLS `r_strat = α + β·r_BTC + ε`; report **α (annualized), β, R², Newey–West t(α)**.
- Rolling 90-day β and correlation (plot).
- **BTC-β-hedged series** `r_hedged = r_strat − β·r_BTC`; re-score Sharpe/DSR. If hedged α
  stays positive and significant → real edge. If it collapses → strategy is levered BTC beta.
- Report **beta to B&H of the same asset** too (is the strategy just "long the coin"?).
**Gate:** documented α, β, hedged-Sharpe per asset. (Informational gate — shapes expectations, not pass/fail.)

### Phase 3 — Sensitivity, one parameter at a time (criticism #1 groundwork, #6)
`run_sensitivity.py`, per variant, BTC first then ETH/SOL. Sweep each parameter alone; every
run increments `N_trials`. Robustness score per parameter (neighbors within ±20% of local
optimum, optimum not on range edge, no lone spike). Plot Calmar/MaxDD/#trades/Sharpe vs param.

Per-variant grids:

| Lean param | Values | | Momentum param | Values |
|---|---|---|---|---|
| track_period | 45–90 step5 | | track_period | 25–55 step5 |
| track_buf_pct | 1.0–5.0 | | track_buf_pct | 1.0–4.0 |
| ma_med/ma_long | {50/200,30/150,20/100} | | ma_fast/ma_reg | {20/100,15/75,10/50} |
| confirm_bars | 1–5 | | trail_pct | 6–20 step2 |
| reentry_hold | 5–25 | | bear_size_cut | 0,25,50,75,100 |
| exit_grace_bars | 1–5 | | reentry_hold | 2–10 |
| er_thresh | 0.10–0.40 | | er_thresh | 0.10–0.40 |
| blowoff_dist_pct | 15–40 | | blowoff_dist_pct | 15–40 |
| vol_shock_mul | 1.2–2.5 | | target_vol_pct | 40–80 |

**Gate:** ≤ 3 parameters per variant show high sensitivity (robustness < 0.7). Those are the
only ones eligible for Phase 6 optimization; the rest stay at Pine defaults (anti-curve-fit).

### Phase 4 — Monte Carlo & stability (criticisms #2, #6)
`run_montecarlo.py` at baseline params, per variant/asset:
1. **Stationary block bootstrap** (Politis–Romano, mean block ≈ 20d) of daily strat returns, 5000×
   → 95% CIs for CAGR/Sharpe/Calmar/MaxDD. *Block* preserves volatility clustering (naive IID
   shuffle would understate tail risk — deliberately avoided).
2. **Trade-order shuffle** 5000× → is the low Max DD skill or lucky ordering? (actual DD percentile in MC dist).
3. **Parameter noise** ±10% on all params, 1000× → **CV = std/mean of Calmar**; CV<0.2 robust, >0.5 fragile.
4. **Synthetic paths**: re-run the *full strategy* on block-bootstrapped price paths → distribution of Sharpe; p-value that real ≥ synthetic.
**Gate:** parameter-noise CV < 0.30; 95% Sharpe CI excludes 0; actual MaxDD not in worst 5% of trade-shuffle dist.

### Phase 5 — Out-of-sample: walk-forward + CPCV + DSR/PBO (criticisms #1, #3, #5)
The overfitting firewall.
- **Anchored walk-forward** (4 folds, train grows from 2020, test = next 6-month block).
  Purge + **embargo ≈ 200 bars** (max indicator lookback) around each split. Per fold: optimize
  the ≤3 sensitive params on train (small Optuna, 100 trials), score on test. Compute
  **Walk-Forward Efficiency = mean(OOS)/mean(IS)** and **parameter stability** (std/mean across folds).
- **CPCV**: N=8 groups, k=2 test groups → many train/test paths; produce the OOS Sharpe
  distribution and **Probability of Backtest Overfitting (PBO)** = fraction of paths where the
  in-sample-best config underperforms the median OOS.
- **Deflated Sharpe Ratio** using the maintained `N_trials`, plus return skew/kurtosis, for the
  baseline and the WF-selected config.
**Gate:** WFE > 0.4 · PBO < 0.5 · DSR p < 0.05 · parameter std/mean < 0.25. A variant failing
this is declared "not proven" and is **not** carried into feature stacking.

### Phase 6 — Multi-parameter optimization, honestly (criticism #1)
Only the ≤3 sensitive params, **Optuna TPE**, optimized **on Design-set train folds only**,
objective = Calmar with a soft penalty for #trades>20 and for exposure<30%. Validate the top-3
configs OOS and **cross-asset** (tune on BTC → apply unchanged to ETH/SOL; keep if OOS Calmar >
50% of BTC IS). Every trial increments `N_trials` → re-deflate Sharpe. If Optima don't beat
Pine defaults after deflation, **keep defaults** (documented, and itself a strong anti-overfit result).
**Gate:** chosen config's DSR still significant *after* adding these trials to the count.

### Phase 7 — Q&A improvements, one at a time, each gated (the "test everything" ask)
`run_feature_ab.py`: each idea implemented behind a flag, **paired A/B** on identical frozen data
vs the Phase-6 baseline, scored with **paired block-bootstrap** Δ-Calmar/Δ-DSR and evaluated
OOS. **Accept a feature only if** Δ is positive with 95% CI excluding 0 **and** it survives the
hold-out later. Stack accepted features cumulatively (so we see marginal contribution), re-running
the gate each time.

| Q&A idea | Applies to | A/B contrast |
|---|---|---|
| Dynamic ATR buffer `k·ATR(14)/close`, incl. asymmetric up/down | both | fixed % vs ATR, k∈{1.5,2,2.5,3} |
| ATR-based blow-off `RSI>80 & (px−TL)/ATR>k`, k = 95/97.5-pctile | both | fixed 20/25% vs ATR-percentile |
| Rolling 365d peak for drawdown/blow-off reference | both | all-time vs 365d rolling |
| Dynamic re-entry lock (vol_z-scaled 5–30) | both | fixed vs dynamic |
| EMA vs SMA for vol_z / annual_vol | both | SMA vs EMA |
| Position sizing: Kelly / half-Kelly (rolling p,b) | lean(binary→sized), momentum(vs vol-target) | binary vs ½-Kelly vs ¼-Kelly |
| Linear/sigmoid thresholds (Momentum RSI/EMA gate softening) | momentum | discrete vs linear |
| z-score normalization of dist/EMA-spread inputs | both | fixed range vs rolling z (robust: median+MAD) |
| Profit-taking / scale-out variants | both (momentum already trails) | none vs fixed vs trailing vs conviction |
| Weekend-skip on/off | both | signals on weekends vs skipped |
| Trailing-stop % (Momentum core) | momentum | already in Phase 3 grid, confirm here |

**Gate per feature:** ship only DSR-positive, CI-clean, OOS-confirmed features.

### Phase 8 — Fees, hold-out, final report (criticism #3 close-out)
- **Fees + slippage** three scenarios (optimist 0.075+0.03%, realist 0.10+0.05%, pessimist
  0.10+0.10%), charged per signal change; re-score final config net.
- **Break the glass:** run the frozen final config **once** on the quarantined **hold-out** and
  the survivor-bias control assets (XRP/BNB/ADA). This is the only legitimate estimate of live edge.
- **Final report:** per variant — accepted params/features, DSR, PBO, WFE, α/β vs BTC,
  fee-net Calmar, hold-out numbers, and an explicit "what we rejected and why" section.
**Gate (go/no-go for paper trading):** hold-out Max DD < B&H, hold-out DSR p < 0.10, fee-net Calmar > 0.5.

---

## Statistical methods appendix (implemented in `stats.py`)

- **Deflated Sharpe Ratio** — `DSR = Φ((SR − SR0)·√(n−1) / √(1 − γ3·SR + (γ4−1)/4·SR²))`,
  where `SR0` is the expected max Sharpe under N independent trials (uses `N_trials`, Euler–Mascheroni
  approximation). Skew γ3, kurtosis γ4 from realized returns. Source: Bailey & López de Prado (2014).
- **PBO via CPCV** — rank configs in each CPCV path by IS, check OOS rank of the IS-winner; PBO =
  P(IS-winner lands below OOS median). Source: López de Prado, *Advances in Financial ML*, ch. 11–12.
- **Stationary block bootstrap** — Politis–Romano geometric block length (mean ~20d) to preserve
  autocorrelation/vol-clustering; used for all return-based CIs.
- **Alpha/Beta regression** — OLS with **Newey–West HAC** covariance (lag ~10) for honest t-stats
  under autocorrelated/heteroskedastic daily returns.
- **White's Reality Check / Hansen SPA** — bootstrap the max outperformance across the config family
  to test data-snooping across the whole sweep, not just one config.

---

## Verification (how we know the harness itself is correct)

1. `pytest testing/` — metrics unit tests + look-ahead audit pass.
2. `metrics.compute_all_metrics()` on BTC/lean matches the live dashboard KPI numbers to 1e-6.
3. `stats.deflated_sharpe` reproduces the worked example from the Bailey–López de Prado paper.
4. `stats.stationary_bootstrap` on IID input returns CIs matching the analytic normal approx.
5. Each `run_*.py` writes its CSV + report and appends a dated entry to `TESTING_LOG.md`; a
   re-run on frozen Parquet data is bit-identical (reproducibility check).
6. Full existing suite still green: `PYTHONPATH=. .venv/bin/python -m pytest` and
   `regression_test.py` unaffected.

## Sources
- [Deflated Sharpe Ratio — Bailey & López de Prado (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) · [paper PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [Combinatorial Purged Cross-Validation (Towards AI)](https://towardsai.com/p/l/the-combinatorial-purged-cross-validation-method) · [Purged CV — Wikipedia](https://en.wikipedia.org/wiki/Purged_cross-validation)
- [Backtest overfitting: OOS testing methods compared (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110)
- [Minimum backtest length & deflated SR (ML4T)](https://stefan-jansen.github.io/machine-learning-for-trading/08_ml4t_workflow/01_multiple_testing/)
- Existing `testing/TESTING_PLAN.md` (v2) and Q&A `strategyDescription/Diversitas_vprašanja_3.6.2026.docx`
