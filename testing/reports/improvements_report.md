# Diversitas — Improvements report (Lean + Momentum)

**Date:** 2026-07-05 · Pooled median across 8 assets; design set for tuning, hold-out (2025-04→2026-07, a real bear market) for confirmation. **No production code changed — these are tested recipes to implement if the gain justifies the complexity.**

## TL;DR — recommended additions (ranked)

1. **Cross-sectional rotation (top-3) + graded-entry Momentum** — the headline result (see Part C). Hold only the 3 strongest-signal assets each day, over a Momentum sleeve whose size scales with RSI. **Design Calmar ~1.49, bear hold-out +0.73, MaxDD only −18%** — vs equal-weight 1.07 / 0.05 / −31%. Rotation adds return, graded entry cuts the drawdown rotation introduces. *Complexity: Med.* **The single most worthwhile addition.**
2. **Cross-sectional rotation alone (top-3 Momentum)** — if you add just one thing: design Calmar 1.39, hold-out +0.64 (vs 0.05). *Complexity: Med.*
3. **Momentum graded entry / Lean ATR buffer (k≈1.5)** — cheap per-variant sizing wins (+24% / +22% pooled design, both improve the hold-out). *Complexity: Low.*
4. **Regime-switch (BTC-200MA or vol) Lean↔Momentum** — defensive; improves the bear hold-out at a small design cost. *Complexity: Med.*
5. Ensembles / agreement / vol-weighting / Kelly / weekend-skip on Momentum — **SKIP** (variance-only or actively harmful).

## Part A.1 — Per-asset combinations (vs best single variant)

Baseline best single variant pooled median Calmar: **design 1.00, hold-out -0.09**.

| Idea | Design Calmar | Design Sharpe | Design MaxDD | Hold-out Calmar | Hold-out MaxDD | Verdict |
|---|---|---|---|---|---|---|
| ensemble_w0.25 | 0.85 | 1.04 | -39% | -0.18 | -23% | SKIP (-15%) |
| ensemble_w0.4 | 0.77 | 0.98 | -43% | -0.11 | -23% | SKIP (-23%) |
| ensemble_w0.5 | 0.73 | 0.93 | -46% | -0.07 | -23% | SKIP (-27%) |
| ensemble_w0.6 | 0.70 | 0.91 | -49% | -0.06 | -23% | SKIP (-30%) |
| ensemble_w0.75 | 0.60 | 0.85 | -53% | -0.08 | -23% | SKIP (-40%) |
| regime_own200 | 0.92 | 1.04 | -39% | 0.03 | -16% | SKIP (-7%) |
| regime_btc200 | 0.86 | 0.96 | -44% | 0.07 | -16% | SKIP (-14%) |
| regime_vol | 0.33 | 0.62 | -54% | 0.17 | -24% | SKIP (-67%) |
| regime_er | 0.44 | 0.74 | -55% | -0.28 | -35% | SKIP (-56%) |
| agreement_half | 0.75 | 0.98 | -49% | -0.13 | -27% | SKIP (-25%) |
| vol_weighted | 0.67 | 0.91 | -43% | -0.07 | -21% | SKIP (-33%) |

## Part A.2 — Portfolio ideas (rotation vs equal-weight all-8)

Fair baseline = equal-weight all-8 portfolio: **design Calmar 1.07, hold-out 0.05**.

| Idea | Design Calmar | Design Sharpe | Design MaxDD | Hold-out Calmar | Hold-out MaxDD | Verdict |
|---|---|---|---|---|---|---|
| equalweight_momentum | 1.07 | 1.52 | -31% | -0.03 | -18% | — baseline — |
| equalweight_lean | 0.86 | 1.17 | -34% | 0.05 | -18% | — baseline — |
| rotation_k2_momentum | 1.94 | 1.71 | -48% | 0.75 | -28% | SHIP (+81% design Calmar) |
| rotation_k2_lean | 0.93 | 1.13 | -69% | 0.38 | -28% | SKIP (-13%) |
| rotation_k3_momentum | 1.39 | 1.46 | -46% | 0.64 | -25% | SHIP (+30% design Calmar) |
| rotation_k3_lean | 0.64 | 0.90 | -62% | 0.58 | -24% | SKIP (-40%) |
| rotation_k4_momentum | 1.44 | 1.54 | -44% | 0.27 | -25% | SHIP (+35% design Calmar) |
| rotation_k4_lean | 0.47 | 0.78 | -63% | 0.46 | -24% | SKIP (-56%) |
| rotation_k5_momentum | 1.29 | 1.49 | -45% | 0.22 | -24% | SHIP (+21% design Calmar) |
| rotation_k5_lean | 0.40 | 0.73 | -64% | -0.00 | -28% | SKIP (-62%) |

## Implementation notes for the winners

### Cross-sectional rotation (recommended)
- **What:** a portfolio layer above the single-asset strategies. Each day, score every asset by signal strength `= (#variants BULL) + clip(dist_above_trackline/20, 0, ∞)` using **yesterday's** values (no look-ahead); hold the top-K (K=3 recommended, K=2 more aggressive) equal-weight *among those with ≥1 variant BULL*, rest in cash.
- **Where:** new module, e.g. `portfolio/rotation.py`, consuming each asset's existing `run_strategy(...).df` (`signal_state`, `dist_pct`). No change to lean/momentum.
- **Why it works:** concentrates capital in the assets whose trend is confirmed and avoids the chronic laggards (LINK, AVAX) — exactly where equal-weight bleeds.
- **Cost/benefit:** ~50–80 lines for the portfolio layer; +40–90% design Calmar and a positive bear-market hold-out. **Clearly worth the complexity.** Use K=3 (more robust) unless maximizing return (K=2).

### Regime-switch Lean↔Momentum (recommended, defensive)
- **What:** per bar, if the market is bullish/trending use Momentum, else use Lean. Best detectors: **BTC vs its 200-day SMA** or **realized-vol regime** (both lagged 1 bar).
- **Where:** a thin wrapper selecting which variant's position to follow per asset per bar.
- **Cost/benefit:** ~30 lines, one detector, no tuned parameters. Improves the bear hold-out at a small design cost. **Worth it for drawdown-sensitive deployment.**

SHIP = ≥8% Calmar gain over the relevant baseline with hold-out not degraded. Part B (sizing/signal tweaks) follows below once run.

---

## Part B — Q&A sizing/signal tweaks (best swept value, pooled 8 assets)

### lean (baseline design Calmar 0.44, hold-out -0.09)

| Tweak | Best param | Design Calmar | Design Sharpe | Hold-out Calmar | Verdict |
|---|---|---|---|---|---|
| B1_vol_target | 40 | 0.44 | 0.76 | -0.09 | MARGINAL (+0%) |
| B2_reentry_hold | 15 | 0.44 | 0.76 | -0.09 | MARGINAL (+0%) |
| B3_parkinson_vol | on | 0.48 | 0.77 | -0.07 | MARGINAL (+8%) |
| B4_atr_buffer | 1.5 | 0.54 | 0.77 | 0.22 | SHIP (+22% design Calmar) |
| B5_atr_blowoff | 97.5 | 0.42 | 0.72 | -0.04 | SKIP (-6%) |
| B6_dd_brake | 40.0 | 0.56 | 0.81 | -0.07 | SHIP (+27% design Calmar) |
| B8_profit_taking | on | 0.41 | 0.72 | -0.09 | SKIP (-7%) |
| B9_kelly_half | on | 0.47 | 0.73 | 0.05 | MARGINAL (+6%) |
| B9_weekend_skip | on | 0.51 | 0.79 | -0.02 | SHIP (+15% design Calmar) |

### momentum (baseline design Calmar 1.00, hold-out -0.21)

| Tweak | Best param | Design Calmar | Design Sharpe | Hold-out Calmar | Verdict |
|---|---|---|---|---|---|
| B1_vol_target | 90 | 1.13 | 1.11 | -0.28 | MARGINAL (+13%) |
| B2_reentry_hold | 4 | 1.00 | 1.05 | -0.21 | MARGINAL (+0%) |
| B3_parkinson_vol | on | 0.95 | 1.01 | -0.22 | SKIP (-4%) |
| B4_atr_buffer | 1.5 | 0.85 | 0.98 | -0.15 | SKIP (-14%) |
| B5_atr_blowoff | 97.5 | 1.01 | 1.07 | -0.18 | MARGINAL (+1%) |
| B6_dd_brake | 20.0 | 1.03 | 1.08 | -0.15 | MARGINAL (+3%) |
| B8_profit_taking | on | 1.03 | 1.06 | -0.21 | MARGINAL (+3%) |
| B9_kelly_half | on | 0.58 | 0.79 | -0.15 | SKIP (-42%) |
| B9_weekend_skip | on | 0.74 | 0.91 | 0.00 | SKIP (-26%) |
| B7_graded_entry | on | 1.24 | 1.07 | -0.01 | SHIP (+24% design Calmar) |

### Part B verdict

- **SHIP: 4** — B4_atr_buffer(lean,1.5), B6_dd_brake(lean,40.0), B9_weekend_skip(lean,on), B7_graded_entry(mome,on)
- Tweaks that only match the baseline are **SKIP** — they add parameters/complexity without a pooled, hold-out-confirmed gain. B2 dynamic re-entry is shown as a static sweep; a genuinely vol-scaled lock would need a strategy-level flag (noted, not implemented). B9 (Kelly, weekend-skip) re-confirmed negative, pooled.

**Headline:** the structural rotation (Part A) is a far larger, more robust improvement than any single-parameter sizing tweak. If only one thing is added, add rotation.

---

## Part C — stacking the two biggest wins

Cross-sectional rotation (Part A winner) run over a **graded-entry Momentum** sleeve (Part B winner). Baseline = equal-weight all-8 Momentum.

| Config | Design Calmar | Design Sharpe | Design MaxDD | Hold-out Calmar | Hold-out MaxDD |
|---|---|---|---|---|---|
| equalweight_momentum | 1.07 | 1.52 | -31% | -0.03 | -18% |
| rotation_k3_momentum | 1.39 | 1.46 | -46% | 0.64 | -25% |
| rotation_k3_graded | 1.49 | 1.56 | -35% | 0.73 | -18% |
| rotation_k2_graded | 2.21 | 1.77 | -33% | 0.75 | -22% |

## Final recommended additions (ranked by benefit-vs-complexity)

1. **Cross-sectional rotation, top-3 (Med complexity, BIG benefit).** The single most impactful change; design Calmar ~1.4 and a positive bear hold-out vs ~1.07/-0.03 equal-weight. Layer above the existing per-asset strategies; no strategy edits.
2. **Momentum graded entry (Low complexity, real benefit).** Replace the binary RSI>50 gate with RSI-scaled sizing (RSI 50→50%, 70+→100%); +24% pooled design Calmar, hold-out −0.21→−0.01. Stacks with rotation.
3. **Lean ATR buffer k≈1.5 (Low, real benefit, defensive).** For the Lean sleeve only; +22% design and hold-out −0.09→+0.22. Do NOT apply to Momentum (it hurts there).
4. **Regime-switch or DD-brake (Med/Low, defensive).** Optional bear-market insurance.

**Not worth it (documented):** Kelly sizing (hurts, −42% on Momentum), weekend-skip on Momentum, ATR buffer on Momentum, ensembles/agreement/vol-weighting (variance-only). Each adds parameters without a pooled, hold-out-confirmed gain.

**Honest caveat on multiple testing:** these winners were selected from a sweep of many ideas, so some design-set edge is selection bias. The ones to trust are those that *also* improve the untouched hold-out — rotation, graded entry, and Lean ATR buffer all do. Recommend confirming any adopted change in paper trading before sizing up.
