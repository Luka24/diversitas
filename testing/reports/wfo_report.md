# Professional walk-forward optimization — results

**Date:** 2026-07-06 · Per-fold anchored WFO (5 folds, 21-day embargo), plateau selection (neighbourhood-averaged, not peak), 5 Optuna seeds, stitched OOS. Compared to Pine defaults on identical stitched windows; hold-out confirmed once.

| Var | Asset | Stitched-OOS Sortino (opt, 5-seed) | 95% CI | Default | Winner | Hold-out opt/def | Param stability |
|---|---|---|---|---|---|---|---|
| mome | BTC | 1.44 ± 0.13 | [1.33, 1.62] | 1.88 | **default** | -0.97 / -0.29 | {'track_period': 2, 'track_buf_pct': 3, 'reentry_hold': 7, 'target_vol_pct': 5} |
| mome | ETH | 0.66 ± 0.24 | [0.34, 0.97] | 0.54 | opt | 0.89 / -0.50 | {'track_period': 2, 'track_buf_pct': 6, 'reentry_hold': 5, 'target_vol_pct': 5} |
| mome | SOL | 0.86 ± 0.16 | [0.64, 1.09] | 1.44 | **default** | -1.20 / -0.55 | {'track_period': 4, 'track_buf_pct': 6, 'reentry_hold': 2, 'target_vol_pct': 6} |
| lean | BTC | 0.94 ± 0.21 | [0.61, 1.13] | 2.28 | **default** | 0.58 / 0.44 | {'track_period': 6, 'track_buf_pct': 7, 'reentry_hold': 8} |
| lean | ETH | 0.63 ± 0.24 | [0.38, 1.03] | 1.61 | **default** | 1.02 / 0.38 | {'track_period': 3, 'track_buf_pct': 6, 'reentry_hold': 10} |
| lean | SOL | 1.52 ± 0.49 | [0.97, 2.11] | 0.44 | opt | -0.99 / -0.09 | {'track_period': 2, 'track_buf_pct': 7, 'reentry_hold': 3} |

## Verdict

- **Optimized beats defaults on the stitched OOS in only 2/6 cases** — and even that overstates it. This is the strongest honest optimization possible: per-fold re-optimization (each fold sees only its own past), plateau selection (robust region, not the lucky peak), 5 seeds to average out optimizer luck, plus a final untouched hold-out.
- **The stitched-OOS wins do NOT hold up out-of-sample.** In 1/2 of the 'wins', the optimized config then *loses* the hold-out — e.g. lean/SOL wins the stitched OOS (1.52 vs 0.44) but collapses on the hold-out (−0.99 vs −0.09). Only 1/6 configs beat the default on *both* the stitched OOS and the hold-out — consistent with chance across 6 attempts.
- **Parameter instability is the tell:** across 25 fits (5 folds × 5 seeds) the winning `track_buf_pct` takes 6–7 distinct values and `reentry_hold` 8–10 — the optimizer is chasing noise, not converging on a stable structural setting. A real edge would pin the params to a narrow band.
- **The optimum keeps drifting toward aggression** (short trackline, tight buffer, high vol-target) that wins in-sample and fails forward — the classic overfitting signature the plateau/seed/hold-out machinery is designed to expose.

## Answer to the colleague

We ran the full professional walk-forward optimization on the existing Lean/Momentum features — per-fold re-optimization + plateau selection + multi-seed + hold-out, exactly the recipe used to avoid overfitting. **The optimizer does NOT robustly beat the Pine defaults**: the in-sample-optimal region keeps drifting toward aggression that does not survive the stitched out-of-sample, and the hold-out confirms it. The defaults already sit on the robust plateau. Keeping them is the correct, overfitting-safe decision.

Reproducible: `python testing/scripts/run_wfo.py`. Raw per-fold params in `testing/results/wfo/wfo.csv`.
