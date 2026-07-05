# Phase 6 — Honest multi-parameter optimization: report

**Date:** 2026-07-05 · Optuna TPE, 150 trials, optimize Calmar on train (≤ 2024-09-30); validate on OOS block (2024-10-01..2025-03-31) + cross-asset. Hold-out still quarantined.

| Var | Train Calmar def→opt | OOS Calmar def→opt | OOS winner | x-asset ETH opt/def | x-asset SOL opt/def | DSR(mined) def→opt |
|---|---|---|---|---|---|---|
| lean | 0.74→1.40 | 7.11→1.11 | default | 1.21/0.52 | 0.88/0.71 | 0.261→0.350 |
| mome | 0.92→1.49 | 5.87→7.04 | optimized | 1.24/1.28 | 0.98/1.12 | 0.412→0.587 |

### Chosen params

- **lean**: default `{'track_period': 75, 'track_buf_pct': 3.0, 'reentry_hold': 15}` · optimized `{'track_period': 85, 'track_buf_pct': 2.0, 'reentry_hold': 6}`
- **momentum**: default `{'track_period': 35, 'track_buf_pct': 2.0, 'reentry_hold': 4}` · optimized `{'track_period': 25, 'track_buf_pct': 1.0, 'reentry_hold': 3}`

## Verdict

- A *robust* improvement must beat the default **out-of-sample AND transfer to both cross-assets** (ETH & SOL). That holds for **0/2** variants.
- **Lean:** the optimized config nearly doubled in-sample Calmar (0.74→1.40) but **collapsed out-of-sample (7.11→1.11)** — the textbook overfitting signature. Default wins.
- **Momentum:** the optimized config wins the BTC OOS block (5.87→7.04) but is **worse on both ETH (1.24<1.28) and SOL (0.98<1.12)** — the BTC win does not generalize, so it is not a robust improvement.
- After adding the Optuna trials the **data-mined DSR stays well below 0.95** for every config (default and optimized), N≈538.

## Decision: keep the Pine defaults (both variants)

The optimizer cannot demonstrate a robust, out-of-sample, cross-asset, deflation-surviving improvement over the a-priori configuration. Adopting the in-sample optimum would be exactly the curve-fitting the reviewer warned about. **'We optimized and deliberately changed nothing' is the strongest anti-overfitting evidence in the campaign.**
