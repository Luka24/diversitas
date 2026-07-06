# Diversitas — Improvements: final consolidated summary

**Date:** 2026-07-05 · Scope: Lean + Momentum. This is the capstone over all
improvement testing. It states (1) what was tested, (2) what actually improves
results after leakage-safe validation, (3) what to implement, ranked by
benefit-vs-complexity. Detailed per-idea numbers live in the linked reports.

## Document coverage — now complete

**Every idea in `Diversitas_vprašanja_3.6.2026.docx` that is testable on free data
has been tested.** The only untested item is **MVRV** (needs a paid on-chain feed;
recipe documented in `external_report.md`). Full mapping: `coverage_and_methodology.md`.

| Q&A area | Status |
|---|---|
| Position sizing, Kelly, graded entry, vol-target | ✅ swept |
| Trackline period/buffer, ATR & vol_z buffer | ✅ swept |
| Re-entry (static + dynamic), confirm/grace bars | ✅ swept |
| Blow-off (fixed + ATR-percentile), vol-shock, EMA vs SMA | ✅ swept |
| OHLC volatility (Parkinson), profit-taking, weekend-skip, rolling-peak brake | ✅ swept |
| BTC filter on/off | ✅ tested |
| **On-chain (Coinbase premium) + Macro (DXY+BBB)** | ✅ tested (inert as doc predicted) |
| MVRV | ⏸ paid data — recipe documented |
| Conviction-score family (weights, z-score, ADX, weekly) | ⛔ Full-variant only, not in Lean/Momentum |

## Methodology (leakage-safe) — how these were judged

3-way split: **TRAIN ≤2023-06 · VALIDATION 2023-07→2025-03 (selection) · HOLD-OUT
≥2025-04 (reported once)**. A change is credible only if it beats baseline on the
**validation** slice (used for choosing) *and* holds on the untouched hold-out.
This corrected an earlier bias where the hold-out had been reused as a selection
filter across ~185 configs (which inflated the first-pass "winners"). Grounded in
the crypto backtesting literature (`coverage_and_methodology.md`, sources therein).

## What actually improves results (ranked)

| # | Addition | Effect (leakage-safe) | Complexity | Verdict |
|---|---|---|---|---|
| 1 | **Cross-sectional rotation, top-3** (hold the 3 strongest-signal assets) | Validation Calmar **2.48** vs 1.51 baseline; hold-out **+0.64** | Med (portfolio layer) | **ADD** |
| 2 | **Rotation over a graded-Momentum sleeve** | Validation Calmar **3.21**; hold-out **+0.73** | Med | **ADD (best)** |
| 3 | **Lean: Donchian-55 breakout confirmation** | Validation Calmar +0.52 (monotone across 20/34/55); hold-out flat | Low (one channel) | **ADD to Lean** |
| 4 | Defensive overlay (TSMOM-120 *or* dynamic vol-trailing *or* regime-switch) | Improves bear hold-out (+0.2…+0.5) at a bull-Calmar cost | Low–Med | **OPTIONAL** (bear insurance) |
| — | Graded entry / ATR buffer as *standalone* per-variant tweaks | Inflated in first pass; only +0.03 / negative on validation | Low | SKIP standalone (use graded only as the rotation sleeve) |
| — | Kelly, weekend-skip (momentum), SuperTrend, profit-taking, macro/on-chain pipes | No validation gain; several actively hurt | — | SKIP |

## Recommended implementation (exactly what was tested)

1. **Rotation layer** (`portfolio/rotation.py`, new): each day rank assets by
   `strength = (#variants BULL) + clip(dist_above_trackline/20, 0, ∞)` using
   **yesterday's** values; hold the top-3 with strength ≥1, equal-weight, else cash.
   Sleeve = Momentum with **graded RSI sizing** (position × `clip((RSI−50)/20, 0.5, 1)`).
   No change to the Lean/Momentum engines.
2. **Lean Donchian confirmation** (config flag, default off): add
   `close in top quartile of 55-day high/low channel` to Lean's entry condition.
3. *(Optional)* a single defensive overlay if drawdown protection is the priority —
   pick one, don't stack (they are substitutes): TSMOM-120 gate, or vol-calibrated
   trailing, or BTC-200MA regime-switch to Lean.

## Honest caveats

- **Multiple testing:** hundreds of configs were scored; trust the ones with a
  *mechanism* and a *monotone/consistent* response (rotation, Donchian) over
  single-corner spikes.
- **Hold-out is now observed**, so even it is no longer pristine. Before sizing up,
  confirm any adopted change inside walk-forward/CPCV folds (Phase 5 machinery) and
  **paper-trade** first.
- **Regime dependence:** the bull design set favours Momentum; the bear hold-out
  favours Lean and defensive overlays. Rotation is the one change that helped in
  both — which is why it is the headline recommendation.

## Advanced techniques (Part D) — tested, none displaces rotation

Web research pointed to ML/portfolio methods beyond rule tweaks; all tested under the
leakage-safe split (meta-labeling with **purged K-fold CV**):

| Technique | Result vs baseline | Verdict |
|---|---|---|
| **Meta-labeling** (triple-barrier + ML sizing) | de-risks weak signals → lower bull Calmar; one config val 1.61 but hold-out −0.37 (overfit) | SKIP as return-booster; possible drawdown tool |
| **Hierarchical Risk Parity** | val 2.51 ≈ rotation 2.48 but hold-out −0.34 vs +0.64 | SKIP (doesn't beat rotation) |
| **HMM regime (2/3-state)** | 2-state ≈ baseline; 3-state defensive | SKIP (defensive only) |
| **Ensemble / stacking** | majority val 1.54 ≈ baseline, hold-out +0.01 | SKIP (marginal) |
| **Cross-asset lead-lag** | val ≤ baseline | SKIP |

**Takeaway:** the sophisticated techniques do **not** beat the simple structural edge
(rotation). Meta-labeling is a *drawdown-reduction* lever, not a return booster, on this
universe. Details: `advanced_report.md`.

## Report index
- `coverage_and_methodology.md` — every Q&A idea + parameters + overfitting protocol
- `feature_matrix_results.md` — 185 configs, each parameter value, design + hold-out
- `improvements_report.md` — Part A/B/C structural + tweaks (first pass, upper bounds)
- `validation_report.md` — leakage-safe re-test of winners
- `new_ideas_report.md` — SuperTrend / TSMOM / dynamic-trail / Donchian sweep
- `external_report.md` — on-chain + macro pipes
- `final_report.md` — the Phase 0–8 validation campaign
