# Leakage-safe validation (3-way split) — winners + new ideas

**Date:** 2026-07-05 · TRAIN ≤2023-06-30 · VALIDATION 2023-07→2025-03 (selection) · HOLD-OUT ≥2025-04 (reported once). A candidate is credible only if it beats the baseline on **validation** (the honest selection set) AND holds up on the hold-out — the hold-out was NOT used to pick it.

| Candidate | Train Calmar | **Validation** Calmar | Hold-out Calmar | Verdict |
|---|---|---|---|---|
| lean_baseline | 0.40 | 0.88 | -0.09 | — baseline — |
| momentum_baseline | 0.66 | 1.51 | -0.21 | — baseline — |
| momentum_graded_entry | 0.92 | 1.54 | -0.01 | DROP (no val gain) |
| lean_atr_buffer_k1.5 | 0.53 | 0.80 | 0.22 | DROP (no val gain) |
| rotation_k3_momentum | 1.29 | 2.48 | 0.64 | KEEP (val +0.98, holdout holds) |
| rotation_k3_graded | 1.39 | 3.21 | 0.73 | KEEP (val +1.70, holdout holds) |
| regime_switch_btc200 | 0.84 | 1.16 | 0.07 | KEEP (val +0.29, holdout holds) |
| momentum_tsmom_60 | 0.73 | 1.01 | -0.26 | DROP (no val gain) |
| momentum_tsmom_90 | 0.66 | 0.96 | -0.24 | DROP (no val gain) |
| momentum_tsmom_120 | 1.31 | 1.27 | 0.21 | DROP (no val gain) |
| lean_tsmom_60 | 0.40 | 0.72 | -0.09 | DROP (no val gain) |
| lean_tsmom_90 | 0.56 | 0.87 | 0.12 | DROP (no val gain) |
| lean_tsmom_120 | 0.60 | 0.90 | 0.12 | DROP (no val gain) |
| momentum_supertrend | 0.66 | 1.35 | -0.28 | DROP (no val gain) |
| lean_supertrend | 0.52 | 0.88 | -0.09 | DROP (no val gain) |
| momentum_dynamic_trail | 0.67 | 1.30 | -0.21 | DROP (no val gain) |

## Reading — the honest, leakage-corrected picture

- **Baselines** — Lean val 0.88 / holdout -0.09; Momentum val 1.51 / holdout -0.21.
- **Only survivor of clean selection (KEEP): rotation_k3_momentum, rotation_k3_graded, regime_switch_btc200.**
- **Cross-sectional rotation is the one robust win.** Validation Calmar 2.48 (plain) / 3.21 (graded sleeve) vs Momentum baseline 1.51 — a large gain on the slice used for *selection*, and the hold-out still holds (0.64 / 0.73). This is not a leakage artifact.
- **The per-variant tweaks were inflated by hold-out reuse.** `momentum graded entry` looked like +24% on the old design pool but is only **+0.03 on the validation slice** (1.54 vs 1.51); `lean ATR buffer k=1.5` looked like +22% but is **worse on validation** (0.80 vs 0.88) — its design gain came from repeatedly peeking at the hold-out. Honest verdict: **marginal at best**, not the ship-grade wins the earlier report implied.
- **New research ideas (SuperTrend, dynamic trailing, TSMOM) do NOT beat baseline on validation** — SuperTrend 1.35, dynamic-trail 1.30, TSMOM-120 1.27, all below 1.51. They are neutral-to-defensive, not improvements.
- **Defensive levers (regime-switch, TSMOM-120, longer trail) trade bull for bear:** they lose on the validation (bull) slice but improve the bear hold-out. Keep them only if drawdown protection is the mandate, not for raw Calmar.

## Bottom line

After correcting the hold-out leakage, **cross-sectional rotation (top-3, optionally over a graded-Momentum sleeve) is the single addition that robustly improves results.** The smaller sizing/signal tweaks do not survive clean selection — the earlier `improvements_report.md` overstated them. For anything adopted, do the durable thing: select inside walk-forward/CPCV folds (Phase 5 machinery) and paper-trade before sizing up. Strictly, the hold-out is now observed too, so treat these as the last in-sample estimates.
