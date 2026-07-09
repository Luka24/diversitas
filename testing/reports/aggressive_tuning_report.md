# Aggressive-tier tuning — capture more upside without breaking DD control

**Date:** 2026-07-10 · Pooled median across BTC/ETH/SOL/AVAX/LINK, leakage-safe (design ≤2025-03 for reading, hold-out ≥2025-04 shown alongside). Objective for the aggressive tier: **higher CAGR + exposure**, accepting more drawdown while MaxDD stays well under Buy&Hold (~−77% for BTC).

| Config | Design CAGR | Exp | MaxDD | Sortino | Calmar | HO CAGR | HO Exp | HO MaxDD | HO Sortino |
|---|---|---|---|---|---|---|---|---|---|
| BASELINE (trail12/reentry4/bear50) | 39% | 19% | -38% | 1.83 | 1.02 | -11% | 18% | -25% | -0.55 |
| trail=15 | 38% | 21% | -42% | 1.87 | 1.00 | -5% | 19% | -25% | -0.29 |
| trail=18 | 40% | 22% | -38% | 1.76 | 1.06 | -5% | 19% | -25% | -0.29 |
| trail=20 | 39% | 22% | -38% | 1.75 | 0.94 | -5% | 19% | -25% | -0.29 |
| reentry=3 | 37% | 19% | -38% | 1.70 | 1.15 | -5% | 20% | -25% | -0.29 |
| reentry=2 | 41% | 20% | -38% | 1.75 | 1.19 | -5% | 20% | -25% | -0.29 |
| bear_cut=60 | 39% | 19% | -38% | 1.80 | 0.96 | -12% | 19% | -27% | -0.61 |
| bear_cut=70 | 38% | 20% | -38% | 1.78 | 0.91 | -13% | 20% | -28% | -0.64 |
| bear_cut=80 | 38% | 20% | -39% | 1.75 | 0.87 | -14% | 20% | -29% | -0.68 |
| AGGRESSIVE (trail18/reentry2/bear70) | 38% | 23% | -42% | 1.59 | 1.13 | -7% | 22% | -27% | -0.36 |
| AGGRESSIVE-lite (trail15/reentry3/bear60) | 36% | 21% | -43% | 1.86 | 0.97 | -6% | 21% | -26% | -0.33 |
| RECOMMENDED (trail18/reentry2/bear50) | 40% | 22% | -38% | 1.68 | 1.08 | -5% | 20% | -25% | -0.29 |

## Reading — two of the three suggestions help, one backfires

- **Baseline** (pooled): design CAGR 39%, exposure 19%, MaxDD -38%, Sortino 1.83, hold-out CAGR -11% / Sortino -0.55. Exposure is low — the reviewer is right about that.

**1. Wider trailing stop (→18): ✓ modest win.** Exposure 19→22%, design CAGR/MaxDD unchanged, and the **hold-out improves** (CAGR −11%→−5%, Sortino −0.55→−0.29) — 12% was indeed a touch tight, tripping out of runs that continued. 15–20 are all similar; 18 is a sensible mid-point. 15 slightly worsens design MaxDD (−42%).
**2. Faster re-entry (→2): ✓ the best single lever.** Design CAGR 39→41%, **Calmar 1.02→1.19**, MaxDD unchanged (−38%), and hold-out improves too. Getting back in faster captures more with no drawdown cost. Clear adopt.
**3. Higher bear-regime size (60/70/80): ✗ BACKFIRES.** It raises exposure exactly in bear regimes: design Calmar *falls* (1.02→0.96→0.91→0.87) and the **bear-market hold-out gets worse** (CAGR −11%→−12/−13/−14%, Sortino −0.55→−0.64→−0.68). The drawdown control the reviewer praised comes *from* the bear-cut — loosening it erodes precisely that. The premise ‘DD is controlled, we can afford more bear exposure’ is backwards. **Keep 50%** (or lower).

## Recommendation

- **Adopt `trail_pct=18` + `reentry_hold=2`, keep `bear_size_cut=50`** (the RECOMMENDED row). This lifts exposure/CAGR and improves the hold-out, without the bear-cut mistake — the combined-AGGRESSIVE row (with bear=70) shows the bear component dragging MaxDD to −42% and Sortino down.
- **Honest scale of the win:** the gains are *incremental*, not transformative — exposure rises ~19%→~22%, CAGR a few points. The strategy is structurally low-exposure (flat ~65% of the time by design). To materially raise exposure you must loosen the ENTRY logic (trackline/momentum gates), not just the exit/sizing — that is a bigger change and should be tested separately, leakage-safe.
- All adopted changes are **hold-out-confirmed** (not overfit to design); the rejected bear-cut change fails the hold-out, which is exactly how the leakage-safe test earns its keep.
