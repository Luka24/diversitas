# Why can't optimization beat the defaults? — root-cause diagnosis

**Date:** 2026-07-06 · momentum/BTC. For each walk-forward fold we scan a coarse grid (track_period × track_buf_pct) on the *train* window and on the *OOS* block, and compare the argmax of each. This isolates whether the failure is a regime shift.

| OOS block | Train ret / vol | OOS ret / vol | Train-best TP/buf | OOS-best TP/buf | Best-possible OOS | Realized (train-best) | Regret |
|---|---|---|---|---|---|---|---|
| 2022-07..2022-12 | +271% / 76% | -14% / 56% | 30/1.0 | 55/1.0 | -1.99 | -2.27 | 0.28 |
| 2023-01..2023-06 | +118% / 74% | +83% / 50% | 30/1.0 | 50/1.0 | 4.02 | 2.15 | 1.87 |
| 2023-07..2023-12 | +229% / 72% | +38% / 38% | 30/1.0 | 30/2.0 | 4.96 | 4.50 | 0.47 |
| 2024-01..2024-06 | +425% / 69% | +42% / 55% | 30/1.0 | 25/1.0 | 2.16 | 1.36 | 0.81 |
| 2024-07..2025-03 | +786% / 67% | +31% / 52% | 30/1.0 | 40/1.0 | 3.76 | 0.98 | 2.78 |

## Diagnosis

- **H2 (distribution shift) is confirmed.** The train-optimal parameter equals the OOS-optimal only **1/5** of the time for track_period and **4/5** for the buffer. What was best on the past is usually *not* what turns out best on the next window — so even a perfect optimizer, restricted to past data, points to the wrong setting. This is the fundamental reason WFO can't win: **the answer changes between fit-time and use-time.**
- **H1 (regime/trend) is the mechanism.** The regime stats differ sharply across windows — train windows are dominated by the huge 2017–2021 bull (high return, high vol), while the OOS blocks include the 2022 bear and the calmer, ETF-era 2023–2025 (lower vol, choppier). A trackline/buffer tuned on wild bull-market swings is mis-sized for the tighter later regime, and vice-versa.
- **The 'regret' column** (best-possible OOS Sortino − what the train-best actually delivered) averages **1.24** points: there *was* a better config each period, but it was only knowable *after* seeing the test data. That gap is pure hindsight, not something an honest optimizer can capture.
- **Why the defaults win anyway:** the Pine defaults are a *compromise* setting that is never the per-period optimum but is never far off either — a robust middle of the plateau across regimes. The optimizer, by contrast, over-commits to whichever regime dominated the train window and pays for it when the regime turns.

## Bottom line for the colleague

It is not that we failed to search hard enough — we ran per-fold Optuna with plateau selection and 5 seeds. It is that **the optimal parameters are non-stationary**: BTC's regime changed (2021 bull → 2022 bear → 2023-25 ETF-era), so the best setting on the training history is systematically the wrong setting for the next period. Chasing the in-sample optimum would therefore *reduce* live performance. The robust, regime-agnostic defaults are the right choice — and the honest way to add value is a **regime-switch or cross-sectional rotation** (which adapt across regimes), not finer parameter tuning.
