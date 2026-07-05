# New research ideas — thorough sweep (leakage-safe 3-way split)

**Date:** 2026-07-05 · Selection = VALIDATION Calmar (2023-07→2025-03); HOLD-OUT (≥2025-04) reported once. Baselines: Lean val 0.88/holdout -0.09, Momentum val 1.51/holdout -0.21.

Each idea is swept over its parameters. `val gain` = validation Calmar − baseline; a real improvement needs a positive validation gain **and** a non-degraded hold-out.

## supertrend

| Variant | Param | Val Calmar | Val gain | Val Sharpe | Hold-out Calmar | Hold-out gain |
|---|---|---|---|---|---|---|
| lean | 7/2.0 | 1.05 | +0.18 | 0.88 | -0.09 | +0.00 |
| lean | 7/2.5 | 0.88 | +0.00 | 0.71 | -0.09 | +0.00 |
| lean | 7/3.0 | 0.88 | +0.00 | 0.71 | -0.09 | +0.00 |
| lean | 7/3.5 | 0.88 | +0.00 | 0.71 | -0.09 | +0.00 |
| lean | 10/2.0 | 0.88 | +0.00 | 0.71 | -0.09 | +0.00 |
| lean | 10/2.5 | 0.88 | +0.00 | 0.71 | -0.09 | +0.00 |
| lean | 10/3.0 | 0.88 | +0.00 | 0.71 | -0.09 | +0.00 |
| lean | 10/3.5 | 0.88 | +0.00 | 0.71 | -0.09 | +0.00 |
| lean | 14/2.0 | 0.97 | +0.09 | 0.80 | -0.09 | +0.00 |
| lean | 14/2.5 | 0.88 | +0.00 | 0.71 | -0.09 | +0.00 |
| lean | 14/3.0 | 0.88 | +0.00 | 0.71 | -0.09 | +0.00 |
| lean | 14/3.5 | 0.88 | +0.00 | 0.71 | -0.09 | +0.00 |
| momentum | 7/2.0 | 1.51 | +0.00 | 1.16 | -0.21 | +0.00 |
| momentum | 7/2.5 | 1.51 | +0.00 | 1.16 | -0.22 | -0.01 |
| momentum | 7/3.0 | 1.15 | -0.36 | 1.07 | -0.28 | -0.07 |
| momentum | 7/3.5 | 1.14 | -0.36 | 1.07 | -0.29 | -0.08 |
| momentum | 10/2.0 | 1.51 | +0.00 | 1.16 | -0.21 | +0.00 |
| momentum | 10/2.5 | 1.35 | -0.16 | 1.10 | -0.23 | -0.02 |
| momentum | 10/3.0 | 1.35 | -0.16 | 1.10 | -0.28 | -0.06 |
| momentum | 10/3.5 | 1.14 | -0.36 | 1.07 | -0.22 | -0.00 |
| momentum | 14/2.0 | 1.51 | +0.00 | 1.16 | -0.22 | -0.01 |
| momentum | 14/2.5 | 1.35 | -0.16 | 1.10 | -0.23 | -0.02 |
| momentum | 14/3.0 | 1.35 | -0.16 | 1.10 | -0.30 | -0.09 |
| momentum | 14/3.5 | 1.34 | -0.16 | 1.10 | -0.15 | +0.06 |

## tsmom_filter

| Variant | Param | Val Calmar | Val gain | Val Sharpe | Hold-out Calmar | Hold-out gain |
|---|---|---|---|---|---|---|
| lean | 30 | 0.87 | -0.01 | 0.68 | -0.09 | +0.00 |
| lean | 60 | 0.72 | -0.15 | 0.70 | -0.09 | +0.00 |
| lean | 90 | 0.87 | -0.01 | 0.68 | 0.12 | +0.21 |
| lean | 120 | 0.90 | +0.03 | 0.87 | 0.12 | +0.21 |
| lean | 150 | 0.59 | -0.28 | 0.65 | 0.12 | +0.20 |
| lean | 200 | 0.62 | -0.25 | 0.63 | -0.36 | -0.27 |
| momentum | 30 | 1.68 | +0.17 | 1.24 | -0.21 | +0.00 |
| momentum | 60 | 1.01 | -0.49 | 0.98 | -0.26 | -0.05 |
| momentum | 90 | 0.96 | -0.55 | 0.93 | -0.24 | -0.02 |
| momentum | 120 | 1.27 | -0.24 | 1.06 | 0.21 | +0.43 |
| momentum | 150 | 1.22 | -0.28 | 1.04 | 0.02 | +0.23 |
| momentum | 200 | 1.17 | -0.33 | 0.96 | -0.21 | +0.00 |

## tsmom_sizing

| Variant | Param | Val Calmar | Val gain | Val Sharpe | Hold-out Calmar | Hold-out gain |
|---|---|---|---|---|---|---|
| lean | 60 | 0.92 | +0.05 | 0.77 | -0.01 | +0.08 |
| lean | 90 | 0.90 | +0.02 | 0.78 | -0.07 | +0.01 |
| lean | 120 | 0.81 | -0.06 | 0.82 | -0.01 | +0.08 |
| momentum | 60 | 1.48 | -0.02 | 1.14 | -0.21 | +0.01 |
| momentum | 90 | 1.20 | -0.30 | 0.96 | -0.25 | -0.03 |
| momentum | 120 | 1.44 | -0.07 | 1.08 | -0.09 | +0.12 |

## dynamic_trail

| Variant | Param | Val Calmar | Val gain | Val Sharpe | Hold-out Calmar | Hold-out gain |
|---|---|---|---|---|---|---|
| lean | 8/2.0 | 0.55 | -0.33 | 0.44 | 0.30 | +0.39 |
| lean | 8/4.0 | 0.55 | -0.33 | 0.44 | 0.30 | +0.39 |
| lean | 8/6.0 | 0.55 | -0.33 | 0.44 | 0.30 | +0.39 |
| lean | 10/2.0 | 1.07 | +0.20 | 0.71 | 0.13 | +0.21 |
| lean | 10/4.0 | 1.07 | +0.20 | 0.71 | -0.21 | -0.13 |
| lean | 10/6.0 | 1.07 | +0.19 | 0.70 | -0.21 | -0.13 |
| lean | 12/2.0 | 0.91 | +0.03 | 0.66 | 0.39 | +0.48 |
| lean | 12/4.0 | 0.74 | -0.13 | 0.59 | 0.39 | +0.48 |
| lean | 12/6.0 | 1.02 | +0.15 | 0.75 | 0.39 | +0.48 |
| lean | 14/2.0 | 0.82 | -0.05 | 0.67 | 0.43 | +0.52 |
| lean | 14/4.0 | 0.82 | -0.05 | 0.67 | 0.43 | +0.52 |
| lean | 14/6.0 | 1.41 | +0.53 | 0.90 | 0.50 | +0.58 |
| momentum | 8/2.0 | 0.72 | -0.78 | 0.82 | 0.09 | +0.30 |
| momentum | 8/4.0 | 0.72 | -0.78 | 0.82 | 0.10 | +0.32 |
| momentum | 8/6.0 | 0.70 | -0.80 | 0.79 | 0.12 | +0.33 |
| momentum | 10/2.0 | 1.58 | +0.07 | 0.95 | -0.19 | +0.02 |
| momentum | 10/4.0 | 1.56 | +0.06 | 0.95 | -0.15 | +0.06 |
| momentum | 10/6.0 | 1.55 | +0.04 | 0.95 | -0.15 | +0.06 |
| momentum | 12/2.0 | 1.30 | -0.21 | 0.98 | -0.21 | +0.00 |
| momentum | 12/4.0 | 1.30 | -0.21 | 0.98 | -0.21 | +0.00 |
| momentum | 12/6.0 | 1.30 | -0.21 | 0.98 | -0.20 | +0.01 |
| momentum | 14/2.0 | 1.51 | +0.00 | 1.16 | -0.21 | +0.00 |
| momentum | 14/4.0 | 1.51 | +0.00 | 1.16 | -0.21 | +0.00 |
| momentum | 14/6.0 | 1.51 | +0.00 | 1.16 | -0.21 | +0.00 |

## donchian

| Variant | Param | Val Calmar | Val gain | Val Sharpe | Hold-out Calmar | Hold-out gain |
|---|---|---|---|---|---|---|
| lean | 20 | 1.15 | +0.27 | 0.99 | -0.10 | -0.02 |
| lean | 34 | 1.25 | +0.38 | 1.07 | -0.09 | -0.00 |
| lean | 55 | 1.39 | +0.52 | 1.10 | -0.09 | -0.00 |
| momentum | 20 | 1.19 | -0.32 | 1.01 | -0.10 | +0.12 |
| momentum | 34 | 1.25 | -0.26 | 1.09 | -0.13 | +0.09 |
| momentum | 55 | 1.18 | -0.33 | 1.08 | -0.15 | +0.07 |

## Survivors (validation gain > 0.05 AND hold-out holds)

| Variant | Idea | Param | Val gain | Hold-out |
|---|---|---|---|---|
| lean | dynamic_trail | 14/6.0 | +0.53 | 0.50 |
| lean | donchian | 55 | +0.52 | -0.09 |
| lean | donchian | 34 | +0.38 | -0.09 |
| lean | donchian | 20 | +0.27 | -0.10 |
| lean | dynamic_trail | 10/2.0 | +0.20 | 0.13 |
| lean | supertrend | 7/2.0 | +0.18 | -0.09 |
| momentum | tsmom_filter | 30 | +0.17 | -0.21 |
| lean | dynamic_trail | 12/6.0 | +0.15 | 0.39 |
| lean | supertrend | 14/2.0 | +0.09 | -0.09 |
| momentum | dynamic_trail | 10/2.0 | +0.07 | -0.19 |
| momentum | dynamic_trail | 10/4.0 | +0.06 | -0.15 |

## Do survivors stack on rotation?

| Combo | Val Calmar | Hold-out Calmar |
|---|---|---|
| rotation_k3_plain | 2.48 | 0.64 |
| rotation_k3_tsmom_size90 | 2.08 | 0.78 |
| rotation_k3_graded | 3.21 | 0.73 |

## Verdict

- **Lean genuinely benefits from two new ideas** (it starts from a weaker 0.88 baseline, so there is room): **Donchian breakout** confirmation is the standout — validation Calmar rises monotonically with the channel period (period 20/34/55 → +0.27/+0.38/+0.52) while the hold-out is unchanged. A monotone, non-spiky response across parameters is the signature of a *real* effect, not curve-fitting. **Dynamic vol-trailing** also lifts Lean on validation (10/2 → +0.20) and, at tighter settings, sharply improves the bear hold-out.
- **Momentum (1.51 baseline) is hard to beat**: the new filters are mostly **defensive** — TSMOM-120 and Donchian help the bear hold-out (+0.4 / +0.1) but cost Calmar on the bull validation slice. Only TSMOM-30 (a very short lookback ≈ a light entry confirm) shows a small validation gain (+0.17), likely noise given how many configs were tried.
- **Rotation remains the one large structural win** (val 2.48 plain, 3.21 with a graded sleeve). Pairing rotation with a TSMOM sizing sleeve trades validation (2.08) for a better hold-out (0.78) — a defensive variant of the same idea.

## Recommendation (leakage-safe)

1. **Rotation (top-3), graded-Momentum sleeve** — the primary, robust improvement.
2. **Lean sleeve: add a Donchian-55 breakout confirmation** — the one signal-level tweak that survives clean selection with a monotone response. Low complexity (one channel).
3. **Optional bear insurance:** a TSMOM-120 or dynamic-trailing overlay — adopt only if drawdown protection outweighs the bull-market Calmar cost; they are substitutes for each other, not additive.
4. **Multiple-testing caveat:** ~80 new configs were scored; treat single-corner wins (e.g. dynamic_trail 14/6) as unproven and prefer the monotone/consistent ones (Donchian). Confirm any adoption inside walk-forward folds + paper trading.
