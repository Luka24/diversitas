# Phase 1 — Baseline validation: report

**Date:** 2026-07-05 · Design set (≤ 2025-03-31), no fees, bear_alloc 0.

## Per-asset results

| Asset | Var | CAGR | B&H | Calmar | Max DD | B&H DD | Sharpe | #tr | sig/3y | Pass |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC | lean | 33.3% | 49.4% | 0.85 | -39.1% | -76.6% | 1.01 | 15 | 7.7 | 3/4 |
| BTC | mome | 38.8% | 49.4% | 1.02 | -38.0% | -76.6% | 1.18 | 31 | 15.9 | 3/4 |
| ETH | lean | 31.9% | 40.5% | 0.52 | -60.8% | -79.3% | 0.85 | 13 | 6.7 | 3/4 |
| ETH | mome | 41.4% | 40.5% | 1.28 | -32.4% | -79.3% | 1.13 | 40 | 20.5 | 4/4 |
| SOL | lean | 41.5% | 118.7% | 0.71 | -58.7% | -96.3% | 0.97 | 17 | 11.0 | 3/4 |
| SOL | mome | 40.9% | 118.7% | 1.12 | -36.7% | -96.3% | 1.17 | 49 | 31.7 | 3/4 |
| AVAX | lean | 6.3% | 32.1% | 0.08 | -75.8% | -93.5% | 0.36 | 12 | 8.0 | 2/4 |
| AVAX | mome | 30.6% | 32.1% | 0.97 | -31.4% | -93.5% | 0.98 | 37 | 24.5 | 4/4 |
| LINK | lean | 1.4% | 48.5% | 0.02 | -73.8% | -90.2% | 0.32 | 14 | 7.2 | 2/4 |
| LINK | mome | 7.9% | 48.5% | 0.14 | -57.0% | -90.2% | 0.39 | 49 | 25.1 | 2/4 |
| XRP* | lean | 8.2% | 33.6% | 0.13 | -65.5% | -83.2% | 0.38 | 13 | 6.7 | 2/4 |
| XRP* | mome | 20.9% | 33.6% | 0.38 | -55.0% | -83.2% | 0.71 | 43 | 22.0 | 4/4 |
| BNB* | lean | 22.0% | 63.5% | 0.36 | -60.6% | -76.1% | 0.67 | 15 | 7.7 | 3/4 |
| BNB* | mome | 20.0% | 63.5% | 0.44 | -45.1% | -76.1% | 0.70 | 39 | 20.0 | 3/4 |
| ADA* | lean | 37.9% | 43.2% | 0.87 | -43.4% | -91.8% | 0.95 | 15 | 7.7 | 3/4 |
| ADA* | mome | 50.3% | 43.2% | 1.29 | -38.9% | -91.8% | 1.37 | 45 | 23.0 | 4/4 |

`*` = survivor-bias control group (not in original tuning set).

## Success criteria (per variant)

| Variant | C1 MaxDD<BH | C2 CAGR≥60%BH | C3 sig-budget | C4 no wrong-window | All-4 |
|---|---|---|---|---|---|
| lean | 8/8 | 3/8 | 8/8 | 2/8 | 0/8 |
| momentum | 8/8 | 5/8 | 8/8 | 6/8 | 4/8 |

## Lean vs Momentum (design set)

| Asset | Calmar L | Calmar M | Sharpe L | Sharpe M | #tr L | #tr M | Winner |
|---|---|---|---|---|---|---|---|
| BTC | 0.85 | 1.02 | 1.01 | 1.18 | 15 | 31 | M |
| ETH | 0.52 | 1.28 | 0.85 | 1.13 | 13 | 40 | M |
| SOL | 0.71 | 1.12 | 0.97 | 1.17 | 17 | 49 | M |
| AVAX | 0.08 | 0.97 | 0.36 | 0.98 | 12 | 37 | M |
| LINK | 0.02 | 0.14 | 0.32 | 0.39 | 14 | 49 | M |
| XRP | 0.13 | 0.38 | 0.38 | 0.71 | 13 | 43 | M |
| BNB | 0.36 | 0.44 | 0.67 | 0.70 | 15 | 39 | M |
| ADA | 0.87 | 1.29 | 0.95 | 1.37 | 15 | 45 | M |

## Gate & interpretation

**C3 signal budget applied per-philosophy (user decision): Lean <20/3y, Momentum <35/3y.**

Assets passing **all 4** criteria on ≥1 variant: **2/5** core. **Gate: ⚠️ REVIEW** (the 4-at-once bar stays strict on purpose — C1 is the objective that actually matters). 
Momentum all-4: ETH, AVAX, XRP, ADA. Lean all-4: —.

### C1 — the primary objective — is met everywhere
- **C1 (cut Max DD vs B&H) passes 8/8 (lean) and 8/8 (momentum): 100%.** Every strategy roughly halves the drawdown (BTC −38% vs −77% B&H). This is the Q&A doc's stated primary goal.
- **C2 (CAGR ≥ 60% B&H)** is now the binding constraint (crypto B&H CAGRs are huge — SOL 119%). Trend-following deliberately trades raw return for safety; failing C2 on the biggest-CAGR coins is expected, not a defect.

### Decisive signal: Momentum dominates risk-adjusted return
- Momentum wins Calmar on **8/8** assets (often 2×: ETH 1.28 vs 0.52, AVAX 0.97 vs 0.08, ADA 1.29 vs 0.87), with smaller Max DD despite higher exposure — the trailing stop + vol-sizing are doing real work.

### Problem assets flagged for later phases
- **LINK** is weak on both (Calmar 0.02 lean / 0.14 momentum) — worst performer; fails C2 and C4. Candidate for exclusion or asset-specific handling.
- **AVAX lean** is effectively broken (Calmar 0.08, DD −76%); momentum fixes it (0.97).

Trial counter initialized (1 default trial per asset×variant).
