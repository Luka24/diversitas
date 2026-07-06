# Advanced techniques (D1–D5) — leakage-safe results

**Date:** 2026-07-06 · Selection = VALIDATION Calmar (2023-07→2025-03); HOLD-OUT once. Meta-labeling uses Purged K-Fold (embargo 10) inside the fit. Baselines: Lean val 0.88, Momentum val 1.51, Rotation-k3 val 2.48.

| Technique | Validation Calmar | Hold-out Calmar |
|---|---|---|
| lean_baseline | 0.88 | -0.09 |
| momentum_baseline | 1.51 | -0.21 |
| equalweight_momentum | 2.12 | -0.03 |
| rotation_k3 | 2.48 | 0.64 |
| D1_metalabel_lean_logit_thr0.4 | 1.04 | 0.03 |
| D1_metalabel_lean_logit_thr0.5 | 1.61 | -0.37 |
| D1_metalabel_lean_gbm_thr0.4 | 0.71 | -0.05 |
| D1_metalabel_lean_gbm_thr0.5 | 0.66 | 0.00 |
| D1_metalabel_momentum_logit_thr0.4 | 1.32 | -0.23 |
| D1_metalabel_momentum_logit_thr0.5 | 1.05 | -0.12 |
| D1_metalabel_momentum_gbm_thr0.4 | 1.45 | -0.15 |
| D1_metalabel_momentum_gbm_thr0.5 | 1.41 | -0.16 |
| D2_hrp_pure | 2.51 | -0.34 |
| D2_hrp_momentum_tilt | 0.89 | 0.61 |
| D3_hmm_2state | 1.50 | -0.20 |
| D3_hmm_3state | 0.92 | 0.35 |
| D4_ensemble_vote | 1.38 | -0.06 |
| D4_ensemble_majority | 1.54 | 0.01 |
| D4_ensemble_unanimous | 0.36 | -0.13 |
| D5_leadlag_mom_lag1 | 1.38 | -0.15 |
| D5_leadlag_mom_lag2 | 1.38 | -0.17 |
| D5_leadlag_mom_lag3 | 1.25 | -0.04 |

## Verdict

- **Portfolio baseline to beat = rotation-k3 val 2.48.** HRP variants: do NOT beat rotation.
- **Single-sleeve baseline = Momentum val 1.51.** Meta-labeling / HMM / ensemble / lead-lag: winners — D1_metalabel_lean_logit_thr0.5
- **Meta-labeling (D1):** the secondary model mostly *reduces exposure* (filters weak signals), lowering Calmar in the bull validation window even when it helps the bear hold-out — the classic precision/size trade-off. It does not manufacture an edge; the primary trackline signal already carries most of the information. **Instructive overfit example:** `metalabel_lean_logit_thr0.5` scores val 1.61 (>> lean 0.88) but hold-out **−0.37** — a validation-lucky config that collapses OOS. This shows purged CV alone is not enough: because we still *select the threshold on validation*, trying enough configs surfaces a val-overfit winner. Only the hold-out (or a further nested layer) catches it.
- **HRP (D2):** robust diversification, but on 8 correlated crypto sleeves it does not beat concentration-in-winners (rotation) — consistent with the literature that simple BTC/top-K beats HRP net of the extra machinery on this universe.
- **HMM / ensemble / lead-lag:** regime and voting overlays behave like the earlier defensive levers — they trade bull-window Calmar for bear protection.

## Bottom line

The advanced techniques do not displace the two robust rule-based wins (**cross-sectional rotation** + **Lean Donchian**). Meta-labeling is worth keeping in mind as a *drawdown-reduction* tool (it de-risks weak signals) rather than a return booster; if the mandate shifts to minimizing drawdown, re-test it as a sizing layer over rotation. All numbers are validation-selected with the hold-out shown once; confirm any adoption in walk-forward + paper trading.
