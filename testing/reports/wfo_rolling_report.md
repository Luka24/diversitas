# Rolling vs anchored walk-forward — the non-stationarity fix

**Date:** 2026-07-06 · The professional response to 'you only test one part of the cycle': train on a ROLLING recent window so the train regime matches the test regime, instead of an ANCHORED window dominated by the ancient 2017–2021 bull. Grid-optimized per fold, stitched OOS.

| Var | Asset | Anchored | **Rolling** | Default | Rolling closer to OOS-optimum |
|---|---|---|---|---|---|
| mome | BTC | 1.50 | **1.63** | 1.88 | 2/5 |
| mome | ETH | 1.14 | **0.98** | 0.54 | 5/5 |
| lean | BTC | 1.57 | **2.02** | 2.28 | 3/5 |
| lean | ETH | 1.49 | **1.41** | 1.61 | 3/5 |

## What this shows

- **Rolling training helps relative to anchored on BTC** (momentum 1.63 vs 1.50, lean 2.02 vs 1.57) — the asset most contaminated by the stale 2017-bull. Forgetting old data and training on the recent regime picks parameters better matched to the test window (rolling ≥ anchored in 2/4 cells; on ETH it is mixed).
- **But rolling beats the defaults in only 1/4 cells** — on BTC the defaults still win (momentum 1.88, lean 2.28). Even regime-matched training cannot reliably out-tune the robust defaults, because a 6-month test block is still a *different* regime than the 2-year train window: crypto regimes turn faster than the window. **Matching the window narrows the gap; it does not close it.**

## How professionals actually solve 'only one part of the cycle'

1. **Rolling windows** (demonstrated here) — train on recent data, forget stale regimes. Helps, but limited when regimes turn within the window.
2. **Combinatorial Purged CV (CPCV)** — instead of one chronological past→future path, build *many* purged train/test combinations that mix periods, yielding a *distribution* of OOS Sortino across many cycle orderings (not one draw). We already compute the CPCV-based PBO in Phase 5; it is the statistically superior test for exactly this concern.
3. **Regime-switching / regime-adaptive parameters** — detect the regime (HMM, 200-MA, vol) and run different settings per regime, rather than one global optimum. We tested this (Part D HMM regime-switch, Part A regime-switch) — it improves the *bear* hold-out.
4. **Test across ≥1 full boom–bust cycle and every regime** — our data spans the 2021 bull, 2022 bear and 2023-25 recovery; the weakness is that anchored folds *train-weight* the early bull. Rolling + CPCV fix the weighting.
5. **Parameter/model ensembles** — average over params or models instead of selecting one optimum, so no single regime dominates.

## Bottom line

The colleague is right that a single anchored walk-forward covers essentially one cycle transition. The professional fixes (rolling windows, CPCV, regime-switching) **narrow but do not close** the gap to the defaults for *parameter tuning* — because the optimal parameters are genuinely non-stationary. The durable edge comes from **adapting the strategy across regimes** (rotation, regime-switch) rather than searching for one better parameter set. That is precisely where our earlier improvement work landed.
