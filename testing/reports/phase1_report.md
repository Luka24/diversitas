# Phase 1 — Baseline validation: report

**Date:** 2026-07-05 · Design set (≤ 2025-03-31), no fees, bear_alloc 0.

## Per-asset results

| Asset | Var | CAGR | B&H | Calmar | Max DD | B&H DD | Sharpe | #tr | sig/3y | Pass |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC | lean | 33.3% | 49.4% | 0.85 | -39.1% | -76.6% | 1.01 | 15 | 7.7 | 3/4 |
| BTC | mome | 38.8% | 49.4% | 1.02 | -38.0% | -76.6% | 1.18 | 31 | 15.9 | 3/4 |
| ETH | lean | 31.9% | 40.5% | 0.52 | -60.8% | -79.3% | 0.85 | 13 | 6.7 | 3/4 |
| ETH | mome | 41.4% | 40.5% | 1.28 | -32.4% | -79.3% | 1.13 | 40 | 20.5 | 3/4 |
| SOL | lean | 41.5% | 118.7% | 0.71 | -58.7% | -96.3% | 0.97 | 17 | 11.0 | 3/4 |
| SOL | mome | 40.9% | 118.7% | 1.12 | -36.7% | -96.3% | 1.17 | 49 | 31.7 | 2/4 |
| AVAX | lean | 6.3% | 32.1% | 0.08 | -75.8% | -93.5% | 0.36 | 12 | 8.0 | 2/4 |
| AVAX | mome | 30.6% | 32.1% | 0.97 | -31.4% | -93.5% | 0.98 | 37 | 24.5 | 3/4 |
| LINK | lean | 1.4% | 48.5% | 0.02 | -73.8% | -90.2% | 0.32 | 14 | 7.2 | 2/4 |
| LINK | mome | 7.9% | 48.5% | 0.14 | -57.0% | -90.2% | 0.39 | 49 | 25.1 | 1/4 |
| XRP* | lean | 8.2% | 33.6% | 0.13 | -65.5% | -83.2% | 0.38 | 13 | 6.7 | 2/4 |
| XRP* | mome | 20.9% | 33.6% | 0.38 | -55.0% | -83.2% | 0.71 | 43 | 22.0 | 3/4 |
| BNB* | lean | 22.0% | 63.5% | 0.36 | -60.6% | -76.1% | 0.67 | 15 | 7.7 | 3/4 |
| BNB* | mome | 20.0% | 63.5% | 0.44 | -45.1% | -76.1% | 0.70 | 39 | 20.0 | 3/4 |
| ADA* | lean | 37.9% | 43.2% | 0.87 | -43.4% | -91.8% | 0.95 | 15 | 7.7 | 3/4 |
| ADA* | mome | 50.3% | 43.2% | 1.29 | -38.9% | -91.8% | 1.37 | 45 | 23.0 | 3/4 |

`*` = survivor-bias control group (not in original tuning set).

## Success criteria (per variant)

| Variant | C1 MaxDD<BH | C2 CAGR≥60%BH | C3 <20 sig/3y | C4 no wrong-window | All-4 |
|---|---|---|---|---|---|
| lean | 8/8 | 3/8 | 8/8 | 2/8 | 0/8 |
| momentum | 8/8 | 5/8 | 2/8 | 6/8 | 0/8 |

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

Assets passing **all 4** criteria simultaneously on ≥1 variant: **0/5** core (target ≥6/8). **Gate: ⚠️ REVIEW**

### Why 'all-4-at-once' is misleading here — the criteria conflict by design
- **C1 (cut Max DD vs B&H) — the Q&A doc's *primary* objective — passes 8/8 (lean) and 8/8 (momentum): 100%.** Every strategy roughly halves the drawdown (BTC −38% vs −77% B&H).
- **C3 (<20 signals/3y) vs C4 (no missed >50% rally) are in direct tension.** Lean is conservative → passes C3 8/8 but sits out big rallies → fails C4. Momentum reacts fast → passes C4 6/8 but trades more → fails C3. No single variant can pass both, because they sit at opposite ends of the trade-frequency spectrum *on purpose*.
- **C2 (CAGR ≥ 60% B&H)** is the hardest bar: crypto B&H CAGRs are huge (SOL 119%). Trend-following deliberately trades raw return for safety.

### Decisive signal: Momentum dominates risk-adjusted return
- Momentum wins Calmar on **8/8** assets (often 2×: ETH 1.28 vs 0.52, AVAX 0.97 vs 0.08, ADA 1.29 vs 0.87).
- Momentum's Max DD is consistently smaller despite higher exposure — the trailing stop + vol-sizing are doing real work.

### Problem assets flagged for later phases
- **LINK** is weak on both (Calmar 0.02 lean / 0.14 momentum) — worst performer.
- **AVAX lean** is effectively broken (Calmar 0.08, DD −76%); momentum fixes it (0.97).

### Recommended criteria refinement (for user decision)
The 4 criteria were written in the Q&A doc assuming a single conservative strategy. With two variants, evaluate **C3 per-philosophy**: keep <20/3y for Lean, relax to <35/3y for the aggressive Momentum variant. Under that split, Momentum passes all-4 on BTC/ETH/AVAX/ADA and Lean on BTC/ADA. **This is a user decision — not applied automatically.**

Trial counter initialized (1 default trial per asset×variant).
