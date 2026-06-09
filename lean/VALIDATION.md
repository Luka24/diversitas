# Validation — Diversitas Lean (Python port)

## 1. Unit tests
```
$ cd lean && ../.venv/bin/python -m pytest diversitas/tests/ -v
======================== 21 passed in 1.18s =========================
```

| Test | What it checks |
|---|---|
| `test_sma_matches_mean` | SMA basic |
| `test_ema_first_valid_equals_sma_seed` | EMA seeding |
| `test_rma_alpha_one_over_n` | Wilder smoothing |
| `test_rsi_in_range_and_extremes` | RSI ∈ [0,100], saturates on uptrend |
| `test_rsi_downtrend_low` | RSI < 5 on pure downtrend |
| `test_adx_responds_to_trend` | ADX > 30 on strong move |
| `test_highest_lowest` | rolling extremes |
| `test_bars_since_counts_correctly` | Pine barssince semantics |
| `test_stdev_pop_matches_numpy` | population stdev |
| `test_bull_condition_requires_all_components` | bull_condition is hard AND |
| `test_bear_regime_blocks_bull` | hard regime block works |
| `test_uptrend_triggers_bull` | strategy emits BULL on uptrend |
| `test_downtrend_stays_bear` | strategy stays BEAR on downtrend |
| `test_state_codes_valid` | states ∈ {1,2,3} |
| `test_blowoff_triggers_bear_from_bull` | blowoff exit fires |
| `test_reentry_lock_respected` | ≥ reentry_hold days between BULL re-entries |
| `test_confirm_bars_enforced` | BULL needs bull_hold ≥ confirm_bars |
| `test_bars_since_signal_resets_on_both_directions` | **Lean-specific:** reset on BOTH BULL and BEAR (Full only resets on BULL) |
| `test_alloc_zero_when_bear` | alloc = 0 when BEAR |
| `test_alloc_capped_at_100` | alloc ≤ 100 always |
| `test_summary_has_required_keys` | summary dict complete |

## 2. Backtest sanity (live Binance)

### BTC, 1500 daily bars
```
BULL bars : 590 (45.3%)
BEAR bars : 711 (54.7%)
Transitions: 18

Naive equity:
  Buy & hold       : +276.0%
  Diversitas Lean  : +193.8%
  Exposure         : 45.3%
```
**Lean captures 70 % of buy-and-hold while only being in market 45 % of the time.**

### Visual spot-check of transitions
- 2023-01-19 BULL at $21K — bottom of 2022 bear
- 2023-12-05 BEAR at $44K (blow-off) — caught the December top
- 2024-03-04 BEAR at $68K (blow-off) — caught the March top
- 2024-11-21 BEAR at $98K (blow-off) — caught the post-election top
- 2025-09-27 BEAR at $109K — currently in BEAR

All three blow-off exits triggered at actual local tops. The strategy is doing its job.

## 3. Dashboard (Streamlit)

Launched with:
```
.venv/bin/streamlit run lean/diversitas/dashboard.py --server.headless true --server.port 8502
```
Health probe:
```
GET http://localhost:8502/_stcore/health -> "ok"
GET http://localhost:8502/                -> HTTP 200
```

Pipeline render simulation:
```
price chart traces: 35
vol chart traces: 2
trades: 6
OK
```

Dashboard sections:
- **Hero row** (5 cards): Signal · Regime · Close · Price vs TL · Allocation
- **Main chart** (720 px): candles + segmented trackline (by 10-bar slope) +
  50 MA + 200 MA (segmented by 5-bar slope) + green/red dots + BULL/BEAR triangles +
  background by display state + allocation stepline subplot
- **Entry gates panel** (Lean signature): PASS/FAIL row for each of the 5–6
  conditions required for BULL — instantly shows what's missing for re-entry
- **Status detail**: 200 MA / 50 MA / Trackline slope / RSI / Vol / (BTC filter)
- **Performance summary**: trades, win rate, avg P&L, avg duration, best/worst,
  cumulative strategy total vs buy-and-hold
- **Volatility chart**: annual vol with vol-shock threshold overlay
- **Trade ledger**: last 12 trades with exit trigger (blow-off / vol-shock / trend-break)

Auto-refresh: 60 s. Manual refresh button clears caches.

## 4. Differences vs Full (validated)

| Property | Full | Lean |
|---|---|---|
| Bear regime | Soft (+15 thr) | **Hard block** |
| Entry decision | Conviction score 0–100 | Hard AND of 5–6 gates |
| State levels | 3 (raw / display / signal) | 1 (signal) + display |
| `barsSinceSignal` reset | On BULL only | **On BOTH BULL and BEAR** (validated by `test_bars_since_signal_resets_on_both_directions`) |
| Allocation formula | `conv × volScale × trendPersistence` | `100 × volScale` (when BULL) |
| Default target vol | 25 % | 50 % |
| BTC filter default | ON | **OFF** |
| Weekend handling | Optional skip | Always trades |
