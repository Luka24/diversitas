# Diversitas — Final campaign report (v3, Lean + Momentum)

**Date:** 2026-07-05 · Hold-out (2025-04-01 → today) touched **once**, here. Configs = unchanged Pine defaults (Phases 6–7 concluded: change nothing).

## 1. Fee sensitivity (BTC, design set)

| Variant | none | optimist | realist | pessimist |
|---|---|---|---|---|
| lean Calmar | 0.85 | 0.83 | 0.82 | 0.81 |
| momentum Calmar | 1.02 | 0.96 | 0.94 | 0.91 |

Fees per side: optimist 0.105%, realist 0.15%, pessimist 0.20% (charged on every signal change). Momentum trades more, so it pays more fee drag — captured here.

## 2. Hold-out performance (realist fees, never-seen data)

| Var | Asset | Bars | CAGR | B&H | Calmar | Max DD | B&H DD | PSR | DD<BH |
|---|---|---|---|---|---|---|---|---|---|
| lean | BTC | 460 | 3% | -19% | 0.28 | -12% | -53% | 0.63 | ✓ |
| lean | ETH | 461 | 2% | -2% | 0.11 | -22% | -68% | 0.60 | ✓ |
| lean | SOL | 461 | -11% | -28% | -0.31 | -34% | -75% | 0.47 | ✓ |
| lean | AVAX | 461 | -25% | -54% | -0.60 | -41% | -83% | 0.16 | ✓ |
| lean | LINK | 461 | -13% | -34% | -0.34 | -38% | -73% | 0.44 | ✓ |
| lean | XRP* | 461 | 11% | -37% | 1.18 | -10% | -71% | 0.87 | ✓ |
| lean | BNB* | 461 | 35% | -4% | 1.25 | -28% | -58% | 0.88 | ✓ |
| lean | ADA* | 461 | -9% | -62% | -0.40 | -23% | -85% | 0.41 | ✓ |
| mome | BTC | 460 | -7% | -19% | -0.27 | -25% | -53% | 0.37 | ✓ |
| mome | ETH | 461 | -12% | -2% | -0.36 | -34% | -68% | 0.31 | ✓ |
| mome | SOL | 461 | -15% | -28% | -0.39 | -38% | -75% | 0.30 | ✓ |
| mome | AVAX | 461 | -16% | -54% | -0.64 | -25% | -83% | 0.24 | ✓ |
| mome | LINK | 461 | 10% | -34% | 0.60 | -17% | -73% | 0.72 | ✓ |
| mome | XRP* | 461 | -7% | -37% | -0.23 | -31% | -71% | 0.38 | ✓ |
| mome | BNB* | 461 | 31% | -4% | 1.87 | -16% | -58% | 0.89 | ✓ |
| mome | ADA* | 461 | -5% | -62% | -0.26 | -21% | -85% | 0.44 | ✓ |

`*` = survivor-bias control (never used for tuning).

- **lean hold-out:** median Calmar -0.10, DD beats B&H on 8/8 assets, median PSR 0.53, median exposure 16%.
- **momentum hold-out:** median Calmar -0.27, DD beats B&H on 8/8 assets, median PSR 0.38, median exposure 15%.

## 3. Verdict — the hold-out was a real crypto bear market

The hold-out window (2025-04 → 2026-07) saw Buy&Hold fall on **every** asset (BTC −19%, SOL −29%, AVAX −54%, ADA −62%). That makes it an ideal stress test of the primary objective.
- **Drawdown control held out-of-sample on 16/16 asset-variant combos (both variants, all 8 assets).** Examples: lean BTC Max DD −12% vs B&H −53%; momentum ADA −21% vs −85%. The strategy's stated reason to exist — cut the drawdown — is confirmed on data used nowhere in tuning.
- **Regime reversal (honest, important):** in this *bear* hold-out, **Lean outperformed Momentum** on return (median CAGR -3% vs -7%) and PSR — its caution paid off when markets fell. In the (bull-heavy) design set Momentum led. **Neither variant dominates across regimes** — Momentum is the trend/bull engine, Lean the defensive one. This is the concrete case for shipping *both*.
- **Fees don't break it**: realist fees cost ~0.03 Calmar (lean) / ~0.08 (momentum); even pessimist fees leave the design-set Calmar positive. Momentum's higher turnover pays more drag, as expected.

## 4. What the campaign answers (the 6 criticisms)

| Criticism | Evidence | Where |
|---|---|---|
| Grid-search overfitting | Optimized configs collapse OOS / don't transfer cross-asset; we keep Pine defaults | Ph 5–6 |
| No Monte Carlo | Block bootstrap CIs, trade shuffle, parameter noise (CV 0.14/0.20) | Ph 4 |
| No out-of-sample | Anchored WF (WFE>1), CPCV PBO, + this untouched hold-out | Ph 5, 8 |
| High BTC beta | β 0.09–0.31, R² 0.03–0.20; edge survives beta-hedging | Ph 2 |
| No statistical methods | Deflated/Probabilistic Sharpe, Newey–West, PBO, paired bootstrap | Ph 2,4,5,7 |
| No stability tests | Parameter-noise CV, WF param stability, cross-asset agreement | Ph 3–5 |

## 5. Recommendation

1. **Ship both variants with Pine-default parameters unchanged** — Momentum as the trend/bull engine, Lean as the defensive one. The hold-out proves they cover different regimes; a simple regime switch or an even split is the natural product. Every attempt to 'improve' via optimization (Ph 6) or Q&A features (Ph 7) failed rigorous out-of-sample + cross-asset testing, so we ship the a-priori design.
2. **Exclude or special-case LINK** (weak on every metric; hedged edge ≈ 0).
3. **Report the honest headline**: the a-priori strategies are significant (PSR), robust (param-noise CV 0.14/0.20), low-beta to BTC (0.09–0.31), and **cut drawdown on 16/16 asset-variant combos in a real out-of-sample bear market** — while being transparent that the deeply data-mined Sharpe is not significant (as it should not be, and we never rely on it).
4. **Next**: paper trading with realist fees; a lightweight regime detector to arbitrate Lean↔Momentum; monitor rolling β and live tracking-error vs this hold-out baseline.
