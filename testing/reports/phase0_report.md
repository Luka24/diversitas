# Phase 0 — Harness + metrics: report

**Date:** 2026-07-05 · **Status:** ✅ GATE PASSED

## Built
- `testing/scripts/dataio.py` — frozen Parquet snapshots (design/holdout split quarantined at `2025-03-31 / 2025-04-01`), SHA-logged manifest.
- `testing/scripts/engine.py` — variant-agnostic runner (lean/momentum) via `sys.path` switch; unified `position()` / `strat_returns()` using `shift(1)` (no look-ahead).
- `testing/scripts/metrics.py` — `core_stats` (matches dashboard `_stats`), `extended_stats` (Omega/Ulcer/tail/skew/kurtosis), trade ledger + `trade_stats`, `compute_all_metrics`.
- `testing/scripts/stats.py` — `deflated_sharpe`, `probabilistic_sharpe`, `stationary_bootstrap`, `bootstrap_ci`, `alpha_beta` (Newey–West HAC), `hedged_returns`, `prob_backtest_overfit` (CSCV), `whites_reality_check`.

## Gate evidence
- `pytest testing/tests/` → **16 passed** (metrics fixtures, trade ledger, look-ahead audit, DSR monotonicity, bootstrap, alpha/beta recovery, PBO on noise).
- **Dashboard cross-check (BTC/momentum, design set):** cagr/sharpe/sortino/max_dd/calmar all match live dashboard to **< 1e-6**.
- Look-ahead audit: mutating a future bar leaves all prior positions unchanged.

## Baseline sniff (BTC design set, no fees, bear_alloc 0)
| Variant | CAGR | Sharpe | Calmar | Max DD | Trades | Win% | Exposure |
|---|---|---|---|---|---|---|---|
| lean | 33.3% | 1.01 | 0.85 | −39.1% | 15 | 53% | 34% |
| momentum | 38.8% | 1.18 | 1.02 | −38.0% | 31 | 48% | 35% |

*(Indicative only — full baseline with all assets + criteria is Phase 1.)*

## Next
Phase 1 — `run_baseline.py`: all 8 assets × {lean, momentum} on the design set, 4 success criteria, initialize `N_trials` counter.
