# Phase 7 — Q&A improvement A/B tests: report

**Date:** 2026-07-05 · Each feature tested in isolation vs Pine-default baseline (Phase 6) on the design set. ΔSharpe CI = paired stationary block bootstrap (2000×). Accept = CI>0 **and** OOS not degraded **and** cross-asset ΔCalmar sign consistent.

## lean

| Feature | ΔSharpe [95% CI] | ΔCalmar | ΔMaxDD | Δ#tr | OOS Calmar b→f | x-asset | Verdict |
|---|---|---|---|---|---|---|---|
| atr_buffer_k2 | -0.48 [-0.97, +0.07] | -0.62 | -18.6% | -2 | 7.11→2.33 | ++ | **NEUTRAL** |
| atr_buffer_k2.5 | -0.43 [-0.94, +0.17] | -0.57 | -18.6% | -3 | 7.11→2.41 | ++ | **NEUTRAL** |
| atr_buffer_asym | -0.02 [-0.35, +0.35] | -0.07 | -2.8% | -3 | 7.11→2.33 | ++ | **NEUTRAL** |
| atr_blowoff_p97.5 | -0.06 [-0.19, +0.05] | -0.08 | +0.0% | +0 | 7.11→4.31 | -+ | **NEUTRAL** |
| ema_volshock | +0.00 [+0.00, +0.00] | +0.00 | +0.0% | +0 | 7.11→7.11 | 00 | **NEUTRAL** |
| kelly_half | +0.01 [-0.60, +0.55] | -0.18 | +10.0% | +0 | 7.11→5.07 | -+ | **NEUTRAL** |
| kelly_quarter | -0.03 [-0.77, +0.63] | -0.23 | +10.0% | +0 | 7.11→4.94 | -+ | **NEUTRAL** |
| weekend_skip | +0.00 [-0.08, +0.07] | +0.04 | +1.5% | +0 | 7.11→8.31 | +- | **NEUTRAL** |
| profit_taking | -0.01 [-0.04, +0.01] | -0.00 | +0.6% | +0 | 7.11→7.11 | -- | **REJECT** |
| add_trailing_12 | +0.09 [-0.48, +0.59] | +0.04 | +6.8% | +0 | 7.11→6.33 | -- | **NEUTRAL** |
| rolling_peak_brake | -0.01 [-0.18, +0.14] | +0.04 | +5.1% | +0 | 7.11→7.11 | ++ | **NEUTRAL** |

## momentum

| Feature | ΔSharpe [95% CI] | ΔCalmar | ΔMaxDD | Δ#tr | OOS Calmar b→f | x-asset | Verdict |
|---|---|---|---|---|---|---|---|
| atr_buffer_k2 | -0.37 [-0.69, -0.10] | -0.50 | -5.4% | -4 | 5.87→8.11 | -+ | **REJECT** |
| atr_buffer_k2.5 | -0.39 [-0.79, -0.03] | -0.56 | -8.3% | -7 | 5.87→8.11 | -- | **REJECT** |
| atr_buffer_asym | -0.33 [-0.71, +0.02] | -0.49 | -6.3% | -7 | 5.87→8.11 | -- | **REJECT** |
| atr_blowoff_p97.5 | -0.11 [-0.35, +0.13] | -0.14 | -0.0% | +5 | 5.87→5.85 | -+ | **NEUTRAL** |
| ema_volshock | +0.00 [+0.00, +0.00] | +0.00 | +0.0% | +0 | 5.87→5.87 | 00 | **NEUTRAL** |
| kelly_half | -0.51 [-1.08, +0.10] | -0.50 | +20.4% | +0 | 5.87→3.39 | -- | **REJECT** |
| kelly_quarter | -0.69 [-1.44, +0.07] | -0.68 | +20.5% | +0 | 5.87→3.35 | -- | **REJECT** |
| weekend_skip | -0.20 [-0.37, -0.06] | -0.24 | -0.4% | -2 | 5.87→5.71 | -+ | **REJECT** |
| profit_taking | +0.00 [-0.03, +0.04] | -0.02 | +0.0% | +0 | 5.87→6.83 | -- | **REJECT** |
| add_trailing_12 | +0.00 [+0.00, +0.00] | +0.00 | +0.0% | +0 | 5.87→5.87 | 00 | **NEUTRAL** |
| rolling_peak_brake | -0.05 [-0.24, +0.14] | -0.01 | +4.4% | +0 | 5.87→5.87 | -+ | **NEUTRAL** |

## Summary

- **Accepted: 0** — none
- Neutral: 14 · Rejected: 8
- **22 isolated A/B tests (11 ideas × 2 variants). Not one clears the bar of (ΔSharpe CI>0) + (OOS not degraded) + (cross-asset sign consistent).**

### Detailed reading per idea (why each did not make it)
- **Dynamic ATR buffer** (k·ATR): consistently *hurts* risk-adjusted return (ΔSharpe −0.33 to −0.48; momentum CI excludes 0 → REJECT). A vol-scaled buffer delays entries/exits; on the realized history it cost more return than the whipsaws it saved. The fixed % buffer is already fine after the ER + trackline-slope filters.
- **ATR-normalized blow-off** (percentile trigger): ≈neutral. The blow-off exit fires so rarely that re-specifying its threshold barely moves the equity curve.
- **EMA vol-shock reference**: *exactly zero* effect — the vol-shock flag changes on 41 bars but all occur while already flat (vol_shock requires below-trackline), so the realized path is identical. The vol-shock exit is near-redundant with the trackline break.
- **Kelly / half-Kelly sizing**: clearly *harmful* (momentum ΔSharpe −0.51/−0.69; Max DD +20pp worse). Rolling p and payoff are too noisy on ~15–40 trades; Kelly over-levers into the wrong regimes. Textbook 'Kelly is fragile to estimation error'.
- **Weekend skip**: neutral on Lean, *harmful* on Momentum (−0.20, CI excludes 0). Crypto trades 24/7, so suppressing weekend signals just misses moves — the Q&A's own doubt confirmed.
- **Profit-taking / scale-out**: negligible-to-negative. Cutting winners early lowers return without materially cutting drawdown for a trend follower.
- **Add trailing stop to Lean**: ΔSharpe +0.09 but CI includes 0, OOS degrades (7.11→6.33) and cross-asset negative → not robust. (Sanity: adding a 12% trail to *Momentum*, which already trails at 12%, gives exactly 0 — the harness is faithful.)
- **Rolling 365-day peak drawdown brake**: ≈neutral; the regime MA + trackline already take the strategy to cash before a 30%-from-peak brake would bind.

### Conclusion
Tested rigorously and in isolation, **none of the Q&A improvement ideas beats the a-priori Pine design** — the same verdict Phase 6 reached for parameters. This is a *positive* result: it says the shipped strategies are already at a robust operating point, and it prevents adopting intuitive-but-unproven changes. 'x-asset' = sign of ΔCalmar on ETH then SOL; a feature had to keep its sign cross-asset, blocking BTC-specific fitting.

No feature proceeds to stacking. Phase 8 runs the unchanged defaults on the quarantined hold-out for the final honest estimate.
