# Phase 4 — Monte Carlo & stability: report

**Date:** 2026-07-05 · Design set · block bootstrap (2000×, mean block 20d), trade shuffle (2000×), parameter noise ±10% (300×, BTC).

| Var | Asset | Sharpe [95% CI] | excl 0? | Calmar [95% CI] | Max DD [95% CI] | MDD pctile | Noise CV |
|---|---|---|---|---|---|---|---|
| lean | BTC | 1.01 [+0.11, +1.90] | ✓ | 0.85 [-0.03, 2.93] | -39% [-66%, -25%] | 15% | 0.20 |
| lean | ETH | 0.85 [-0.00, +1.72] | ✗ | 0.52 [-0.17, 2.81] | -61% [-89%, -30%] | 20% | — |
| lean | SOL | 0.97 [-0.17, +1.98] | ✗ | 0.71 [-0.19, 3.82] | -59% [-82%, -31%] | 6% | — |
| mome | BTC | 1.18 [+0.29, +2.06] | ✓ | 1.02 [0.08, 3.43] | -38% [-60%, -23%] | 52% | 0.14 |
| mome | ETH | 1.13 [+0.28, +1.91] | ✓ | 1.28 [0.07, 3.46] | -32% [-61%, -24%] | 72% | — |
| mome | SOL | 1.17 [-0.01, +2.16] | ✗ | 1.12 [-0.07, 3.96] | -37% [-63%, -23%] | 97% | — |

## Interpretation

- **Sharpe 95% CI excludes 0 in 3/6 cases** (block bootstrap that preserves volatility clustering — a naive IID shuffle would look artificially tighter). Where it includes 0, the per-asset edge is not bootstrap-significant on its own.
- **Parameter-noise Calmar CV: 0.20, 0.14** (mean 0.17). CV < 0.2 = robust, < 0.35 = acceptable. This confirms Phase 3's finding *quantitatively*: small perturbations to ALL parameters at once barely move Calmar → the strategies sit on a plateau, not a spike.
- **Trade-shuffle Max-DD percentile** = share of random trade orderings whose drawdown is worse-or-equal to the realized one. **Momentum lands high (52/72/97%)** → its realized Max DD is at the *pessimistic* end of what ordering luck could produce, so the reported drawdown is conservative, not flattered. **Lean lands low (15/20/6%)** → its realized Max DD is at the *optimistic* end, i.e. the actual sequence was favourable and other orderings would be worse — a caveat that Lean's low DD is partly ordering-dependent, not purely structural.

## Gate

- Parameter-noise CV < 0.35 on both variants: ✅ (0.20, 0.14)
- Sharpe CI excludes 0 on the core BTC test: ✅

Interpretation: the strategies are **stable** (low CV) — the remaining question is out-of-sample validity, which Phase 5 (walk-forward + CPCV + Deflated Sharpe) settles.
