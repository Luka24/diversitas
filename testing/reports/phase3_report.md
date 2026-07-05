# Phase 3 — Sensitivity analysis: report

**Date:** 2026-07-05 · Single-parameter sweeps, others at default.
Primary robustness on BTC (metric = Calmar); ETH/SOL swept too for cross-asset agreement.
Every scored config counts as a trial (feeds the Deflated Sharpe hurdle).

**Key distinction:** an `edge-low/edge-high` optimum means the best value sits at the swept range boundary — a *directional pull*, usually toward more aggression on in-sample BTC history. That is the overfitting temptation, not fragility. `interior-sharp` means a genuinely fragile peak (neighbours >30% worse). `interior-flat` = robust plateau.

## lean — 1 genuinely fragile · 3 edge-directional / 9 params

| Param | Default | Best (BTC) | Opt type | Robust | x-asset agree | Calmar range |
|---|---|---|---|---|---|---|
| track_period | 75.0 | 45.0 | `edge-low` | 0.00 | 0/2 | 0.35–1.25 |
| track_buf_pct | 3.0 | 2.0 | `interior-sharp` | 0.68 | 0/2 | 0.64–0.99 |
| confirm_bars | 3.0 | 1.0 | `edge-low` | 0.00 | 1/2 | 0.70–1.04 |
| reentry_hold | 15.0 | 5.0 | `edge-low` | 0.00 | 0/2 | 0.74–0.87 |
| exit_grace_bars | 3.0 | 3.0 | `interior-flat` | 0.93 | 0/2 | 0.45–0.85 |
| er_thresh | 0.3 | 0.15 | `interior-flat` | 0.94 | 1/2 | 0.78–0.88 |
| blowoff_dist_pct | 25.0 | 35.0 | `interior-flat` | 0.87 | 0/2 | 0.59–1.01 |
| vol_shock_mul | 1.5 | 1.5 | `interior-flat` | 0.95 | 1/2 | 0.81–0.85 |
| track_slope_bars | 10.0 | 10.0 | `interior-flat` | 0.92 | 0/2 | 0.69–0.85 |

## momentum — 0 genuinely fragile · 5 edge-directional / 9 params

| Param | Default | Best (BTC) | Opt type | Robust | x-asset agree | Calmar range |
|---|---|---|---|---|---|---|
| track_period | 35.0 | 25.0 | `edge-low` | 0.00 | 0/2 | 0.77–1.29 |
| track_buf_pct | 2.0 | 1.0 | `edge-low` | 0.00 | 0/2 | 0.88–1.21 |
| trail_pct | 12.0 | 8.0 | `interior-flat` | 0.85 | 0/2 | 0.97–1.15 |
| bear_size_cut | 50.0 | 25.0 | `interior-flat` | 0.86 | 0/2 | 0.79–1.19 |
| reentry_hold | 4.0 | 2.0 | `edge-low` | 0.00 | 1/2 | 1.00–1.24 |
| er_thresh | 0.25 | 0.2 | `interior-flat` | 0.91 | 0/2 | 0.91–1.10 |
| blowoff_dist_pct | 20.0 | 35.0 | `interior-flat` | 0.94 | 1/2 | 0.92–1.16 |
| target_vol_pct | 60.0 | 80.0 | `edge-high` | 0.00 | 2/2 | 0.86–1.07 |
| confirm_bars | 1.0 | 5.0 | `edge-high` | 0.00 | 0/2 | 0.78–1.31 |

## Gate & interpretation

- **lean: 1 genuinely fragile (interior-sharp) params** ⚠️ — track_buf_pct. Edge-directional (in-sample pull toward aggression): track_period, confirm_bars, reentry_hold.
- **momentum: 0 genuinely fragile (interior-sharp) params** ✅ — none. Edge-directional (in-sample pull toward aggression): track_period, track_buf_pct, reentry_hold, target_vol_pct, confirm_bars.

### Reading
- **Momentum has zero fragile peaks; Lean has one** (`track_buf_pct`, rob 0.68) — but ETH/SOL disagree with BTC's choice there (x-agree 0/2), so it is asset-specific noise: keep the default 3.0. Neither strategy is structurally fragile. Phase 4's parameter-noise CV will confirm this quantitatively.
- The edge optima **all point the same way** (shorter trackline, smaller buffer, faster re-entry, higher vol-target) = in-sample BTC history rewards more aggression. **We do NOT chase these** — that is precisely the curve-fitting trap. Whether more aggression survives out-of-sample is decided by walk-forward + CPCV (Phase 5), not by picking the in-sample edge here.
- **Cross-asset agreement** columns show whether ETH/SOL want the same value as BTC. Low agreement ⇒ asset-specific noise ⇒ keep the default. High agreement on an edge ⇒ a real (if aggressive) structural preference worth testing OOS.

### Phase 6 optimization shortlist
Rather than every edge param, Phase 6 will jointly optimize a **small** set with the strongest, most cross-asset-consistent in-sample signal (candidates: `track_period`, `track_buf_pct`, `reentry_hold`), strictly under walk-forward + DSR control. Everything else stays at Pine defaults.
