# Diversitas — Coverage audit (Q&A doc) + overfitting-safe test methodology

**Date:** 2026-07-05 · Scope: **Lean + Momentum** (per user). This document answers three
questions: (1) did we test everything in `Diversitas_vprašanja_3.6.2026.docx`? (2) with which
parameters? (3) how should everything be tested so we don't overfit — grounded in how crypto
strategies are actually trained.

---

## Part 1 — Complete coverage of every Q&A idea

Legend: ✅ tested · 🟡 partial · ⛔ N/A for Lean/Momentum (belongs to the **Full** variant's
conviction score) · ⏸ excluded per user (external data) · 📌 design decision (no test needed).

### §1 Strategy
| # | Q&A idea | Status | Where / parameters |
|---|---|---|---|
| 1.1 | Position sizing vs binary 0/100 (Kelly `f*=(p·b−q)/b`) | ✅ | Kelly ½ & ¼ (Ph7/B9); **graded RSI sizing** (B7, +24% mom); vol-target sweep (B1) |
| 1.2 | Define the exact optimization metric | 📌 | **Calmar** chosen as primary (matches "cut drawdown" goal); Sharpe/Sortino/Omega/Ulcer all reported |
| 1.3 | Asset universe / survivor bias | ✅ | Added **XRP/BNB/ADA control group** never used for tuning (all phases) |

### §2 Trackline
| # | Q&A idea | Status | Where / parameters |
|---|---|---|---|
| 2.1 | Trackline component weights (30/25/20/15/10) | ⛔ | Conviction-score = **Full** variant only |
| 2.2 | Trackline period (45/60/75/90) | ✅ | Sensitivity Ph3: **lean 45–90 step5, momentum 25–55 step5** |
| 2.3 | Dynamic buffer `base·(1+vol_z·0.5)` | ✅ | **volz_buffer coef {0.3,0.5,0.8}** (gap run) — marginal |
| 2.4 | ATR buffer `k·ATR/close`, k∈[1.5,3], asymmetric | ✅ | atr_buffer **k {1.5,2,2.5,3}** + asym (Ph7 & B4) — **SHIP for Lean k=1.5**, hurts momentum |

### §3 Conviction score (all ⛔ — Full variant only; Lean/Momentum have no conviction score)
| # | Q&A idea | Status |
|---|---|---|
| 3.1 | Trend range [-5,+5] → z-score | ⛔ Full |
| 3.2 | Robust z-score (median+MAD) for Trend/EMA/Volume/Drawdown | ⛔ Full |
| 3.3 | RSI normalization [30,65] | ⛔ Full (Momentum uses RSI>50 gate → tested via **graded entry B7**) |
| 3.4 | EMA spread [-2,+3] asymmetric | ⛔ Full |
| 3.5 | Weekly macro DA/NE weighting | ⛔ Full |
| 3.6 | Weekly gate vs weekly macro dedup | ⛔ Full |
| 3.7 | Volume weight higher | ⛔ Full |
| 3.8 | Drawdown peak: ATH vs 1-yr rolling | 🟡 | tested as **rolling-peak DD brake** (B6, dd {20,30,40}); the conviction-component form is Full |

### §4 Filters
| # | Q&A idea | Status | Where / parameters |
|---|---|---|---|
| 4.1 | ADX filter | ⛔ | Full variant |
| 4.2 | Weekly gate rolling-7d vs Sunday close | ⛔ | Full variant |
| 4.3 | BTC filter for altcoins (on/off) | ✅ | **btc_filter A/B** (gap run): **ON helps Momentum alts (0.97→1.12)**, slightly hurts Lean alts |

### §5 Volatility regime
| # | Q&A idea | Status | Where / parameters |
|---|---|---|---|
| 5.1 | EMA vs SMA for vol reference | ✅ | ema_volshock (Ph7) — no-op (vol_shock ≈ redundant); vol_z regime is Full |
| 5.2 | Yang-Zhang / Parkinson OHLC volatility | ✅ | **parkinson_vol** (B3) — marginal-to-negative |
| 5.3 | Thresholds 55/60/70 → linear 55–70 | ⛔ | Conviction threshold = Full; Momentum gate softening tested via **graded entry** |
| 5.4 | Threshold sensitivity 45–80 step5 | ⛔ | Full variant |

### §6 On-chain & §7 Macro — ⏸ excluded per user
MVRV thresholds/dynamic, MVRV-for-alts, Coinbase premium (−0.05/−0.1/−0.2, SMA 7 vs 14), DXY
YoY (period, 2% threshold), BBB SMA (21/42/63), macro pipe. **Not tested** (need new data
sources; user scoped these out). Listed here for completeness so nothing is silently dropped.

### §8 Convergence gate + anti-churn
| # | Q&A idea | Status | Where / parameters |
|---|---|---|---|
| 8.1 | 3-bar persistence (confirm_bars / exit_grace) | ✅ | Ph3: **confirm_bars 1–5, exit_grace_bars 1–5** |
| 8.2 | Re-entry lock 15 (test 7/10/20/25) | ✅ | Ph3 + **B2 reentry_hold** (lean 5–25, momentum 2–10) |
| 8.3 | **Dynamic** re-entry lock (hi-vol 5–7, lo-vol 25–30) | ✅ | **dynamic_reentry** (gap run) — hurts Momentum (−58%), neutral Lean |
| 8.4 | ATR blow-off `RSI>80 & (px−TL)/ATR>k`, k=95/97.5 pctile | ✅ | **atr_blowoff pct {95,97.5}** (Ph7 & B5) — neutral |
| 8.5 | Weekend skip | ✅ | weekend_skip (Ph7 & B9): helps Lean, **hurts Momentum (−26%)** |
| 8.6 | Profit taking | ✅ | profit_taking +50/+100% scale-out (Ph7 & B8) — marginal |
| 8.7 | API-missing → NEUTRAL | 📌 | N/A for OHLCV-only Lean/Momentum |

### §9 Next steps (process)
| # | Q&A idea | Status | Where |
|---|---|---|---|
| 9.1 | Sensitivity (trackline/buffer/threshold/reentry) | ✅ | Phase 3 |
| 9.2 | Variant A (full filters) vs B (simplified) | ✅ | = Full vs Lean; both implemented |
| 9.3 | Walk-forward | ✅ | Phase 5 (anchored, 4 folds) + CPCV |
| 9.4 | Fees + slippage | ✅ | Phase 8 (3 scenarios) |
| 9.5 | Profit taking | ✅ | B8 |

### Structural additions I proposed and tested (beyond the Q&A doc)
Static ensemble (w sweep), **regime-switch** (BTC-200MA / own-200 / vol / ER detectors),
signal-agreement sizing, **cross-sectional rotation** (K∈{2,3,4,5}), vol-weighted ensemble,
**rotation × graded-entry stack**. Rotation+graded is the headline win (see improvements_report.md).

### Bottom line on coverage
**Every Q&A idea applicable to Lean/Momentum has been tested, most with a parameter sweep.**
What remains untested is (a) the **Full-variant conviction-score** family (⛔ — architecturally
absent from Lean/Momentum) and (b) **on-chain/macro** (⏸ — user-excluded external data). If you
want (a) or (b), they are a separate work item on the Full variant / new data pipes.

---

## Part 2 — Parameter index (what was swept)

| Feature | Variant(s) | Values swept |
|---|---|---|
| track_period | lean / mom | 45–90 step5 / 25–55 step5 |
| track_buf_pct | both | 1.0–5.0 / 1.0–4.0 step0.5 |
| ma pair | lean / mom | {50/200,30/150,20/100} / {20/100,15/75,10/50} |
| confirm_bars, exit_grace_bars | both | 1–5 |
| reentry_hold | lean / mom | 5–25 / 2–10 |
| er_thresh | both | 0.10–0.40 step0.05 |
| blowoff_dist_pct | both | 15–40 |
| vol_shock_mul | lean | 1.2–2.5 |
| trail_pct | mom | 6–20 step2 |
| bear_size_cut | mom | 0,25,50,75,100 |
| target_vol_pct | mom (B1) | 40–90 |
| ATR buffer k | both | 1.5,2,2.5,3 (+asym 2.5/1.5) |
| ATR blow-off pctile | both | 95, 97.5 |
| vol_z buffer coef | both | 0.3,0.5,0.8 |
| DD-brake dd_pct | both | 20,30,40 |
| Kelly fraction | both | 0.5, 0.25 |
| rotation K | portfolio | 2,3,4,5 (× lean/mom sleeve, × graded) |
| ensemble w | both | 0.25,0.4,0.5,0.6,0.75 |
| regime detector | both | own200, btc200, vol, ER |
| dynamic reentry | both | base15/coef5, clip[5,30] |
| BTC filter | alts | on / off |

Full numeric results: `testing/results/{phase3,phase7,improvements}/*.csv`.

---

## Part 3 — Overfitting-safe test methodology (how crypto strategies should be trained)

Synthesised from current practice (sources below). The guiding facts: **walk-forward alone
validates in a single market regime and can overfit to it**; crypto needs **regime coverage
(bull/bear/sideways)**; and any parameter chosen by search must clear a **multiple-testing**
correction and an **untouched hold-out**.

### The protocol we use (and recommend keeping)
1. **Quarantined hold-out from day 1.** Last ~15 months (2025-04→2026-07) reserved, touched
   exactly once at the end. ≥20% out-of-sample is the standard minimum; ours is the most recent,
   which is also a real **bear market** — the hardest test.
2. **Design vs hold-out split** with **purge + embargo (~200 bars = max indicator lookback)** so
   no indicator warmup leaks across the boundary (López de Prado). Crypto trades 24/7, so the
   embargo is in calendar days, not "trading" days.
3. **Anchored walk-forward (4 folds)** for realism — train grows from inception, test = next
   6-month block. Anchored (not rolling) because a **trend follower benefits from long history**;
   we also report parameter stability across folds.
4. **Combinatorial Purged CV (CPCV)** on top of WF — many train/test paths → a *distribution* of
   OOS performance and the **Probability of Backtest Overfitting (PBO)**. CPCV is the current
   best practice for overfitting detection; WF remains for realistic simulation. We run both.
5. **Regime-segmented reporting (bull / bear / sideways).** A change is only "real" if it doesn't
   only work in one regime. The hold-out being a bear market already stress-tests this; we also
   classify by BTC-vs-200MA and vol regime.
6. **Multiple-testing correction.** Every config scored is counted (campaign trial counter =
   1397); the **Deflated Sharpe Ratio** deflates by the expected best-of-N. A-priori configs
   (never selected from the sweep) use N=3 (the three designed variants); data-mined picks use
   the full N. We publish both.
7. **Pooled cross-asset evidence.** Significance is claimed from consistency across 8 assets +
   the control group (XRP/BNB/ADA), never a single asset — this is how we dodge the "one lucky
   coin" trap and survivor bias.
8. **Overfitting red-flag tripwires** (auto-reject): backtest win-rate > 80% or profit-factor
   > 5 are treated as overfit, not edge. Parameter-noise CV > 0.5 = fragile.

### How to test the *improvements* specifically without overfitting
- **Sweep on design, pick on pooled median, confirm on hold-out** — a feature ships only if it
  improves the pooled-median Calmar *and* the untouched hold-out (not design alone). This is why
  rotation, graded entry, and Lean ATR-buffer are trusted (all three improve the hold-out) while
  design-only winners (e.g. Lean DD-brake) are held as "MARGINAL".
- **Paired block-bootstrap** on the return *difference* for ΔSharpe CIs (preserves vol
  clustering) rather than comparing point estimates.
- **Complexity gate** — a statistically real but small gain that adds parameters/state is a SKIP;
  we only ship gains that clearly beat their added complexity.
- **Nested WF for any adopted parameter** — if you later decide to *tune* a shipped feature
  (e.g. rotation K), do it inside each WF training fold (nested), never on the whole history.
- **Recommended next step before capital:** paper-trade the adopted change and track live
  tracking-error vs this hold-out baseline; re-deflate as new trials accumulate.

### Sources
- [Adaptive Regime-Based Trading on Bitcoin — Backtesting & Walk-Forward](https://www.researchgate.net/publication/395401021_Adaptive_Regime-Based_Trading_on_Bitcoin_Backtesting_and_Walk-Forward_Evaluation)
- [Combinatorial Purged Cross-Validation (Towards AI)](https://towardsai.com/p/l/the-combinatorial-purged-cross-validation-method) · [Purged CV — Wikipedia](https://en.wikipedia.org/wiki/Purged_cross-validation)
- [Deep RL for Crypto Trading: addressing backtest overfitting (arXiv)](https://arxiv.org/pdf/2209.05559)
- [Walk-Forward Optimization: anchored vs rolling (S. Potter)](https://www.susanpotter.net/quant/walk-forward-optimization/) · [QuantInsti](https://blog.quantinsti.com/walk-forward-optimization-introduction/)
- [Backtesting AI crypto strategies safely — overfitting/look-ahead/leakage](https://www.blockchain-council.org/cryptocurrency/backtesting-ai-crypto-trading-strategies-avoiding-overfitting-lookahead-bias-data-leakage/)
- [How to backtest your crypto strategy 2026 (Coin Bureau)](https://coinbureau.com/guides/how-to-backtest-your-crypto-trading-strategy)
- [Deflated Sharpe Ratio — Bailey & López de Prado](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
