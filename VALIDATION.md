# Validation — Diversitas Pro v3 (Python port)

## 1. Unit tests
```
$ .venv/bin/python -m pytest diversitas/tests/ -v
======================== 18 passed in 1.40s =========================
```

| Test | What it checks |
|---|---|
| `test_sma_matches_mean` | rolling SMA basic |
| `test_ema_first_valid_equals_sma_seed` | EMA semantics |
| `test_rma_alpha_one_over_n` | Wilder smoothing matches alpha=1/N |
| `test_rsi_in_range_and_extremes` | RSI ∈ [0,100], saturates at 100 on pure uptrend |
| `test_rsi_downtrend_low` | RSI < 5 on pure downtrend |
| `test_adx_responds_to_trend` | ADX > 30 on strong directional move |
| `test_highest_lowest` | rolling extremes correct |
| `test_bars_since_counts_correctly` | Pine `barssince` semantics |
| `test_stdev_pop_matches_numpy` | population stdev (ddof=0) matches `np.std` |
| `test_uptrend_eventually_triggers_bull` | strategy emits BULL on uptrend |
| `test_downtrend_stays_bear` | strategy never goes BULL on downtrend |
| `test_state_codes_valid` | all states ∈ {1,2,3} |
| `test_conviction_bounded` | raw_conviction ∈ [0,100] |
| `test_reentry_lock_respected` | consecutive BULL re-entries ≥ `reentry_hold` apart |
| `test_confirm_bars_enforced` | BULL transition only when `raw_hold ≥ confirm_bars` |
| `test_blowoff_triggers_bear_from_bull` | parabolic spike → BEAR exit |
| `test_skip_weekend_blocks_transitions` | no transitions on Sat/Sun when enabled |
| `test_summary_fields_present` | summary dict contains all panel fields |

## 2. Backtest sanity (real Binance data)

### BTC, 1500 daily bars (≈4 years)
```
Bars analyzed: 1422
BULL bars: 701 (49.3%)
BEAR bars: 721 (50.7%)
Transitions: 20
Naive equity: +93.2%  vs B&H +168.6%  (exposure 49.3%)
```
Per-unit-exposure return: 0.5 × buy-and-hold while sitting in cash half the time → defensive but capturing roughly half of the upside, as expected from a regime-filter overlay.

### ETH, 1000 daily bars
```
BULL bars: 230 (24.9%)
BEAR bars: 692 (75.1%)
Naive equity: +75.6%  vs B&H -20.1%  (exposure 24.9%)
```
Strong outperformance vs buy-and-hold because the BTC cross-asset filter held the strategy out of ETH's deepest drawdowns.

### Signal sanity check (visual spot-check)
- 2023-01-18 BULL at $20K — corresponds to the textbook 2022 bear-market low.
- 2024-03-04 BEAR at $68K then BULL at $66K — blow-off detected, re-entry on continuation.
- 2025-10-16 BEAR at $108K — top before the 2026 drawdown.

These line up with the major regime changes in the BTC chart.

## 3. Dashboard (Streamlit)

Launched with:
```
.venv/bin/streamlit run diversitas/dashboard.py --server.headless true --server.port 8501
```
Server health probe:
```
GET http://localhost:8501/_stcore/health  -> "ok"
GET http://localhost:8501/                -> HTTP 200
```

Pipeline render simulation (`_run` + chart builders for BTC/ETH/SOL):
```
BTC  signal=BEAR regime=BEAR   close=$62,920 conv= 7.0 thr=75
ETH  signal=BEAR regime=BEAR   close=$ 1,669 conv= 8.0 thr=85
SOL  signal=BEAR regime=BEAR   close=$    66 conv=  7.0 thr=75
Price chart traces: 121 (multi-segment trackline + dots + labels)
Breakdown chart traces: 6 (5 components stacked + threshold line)
```

Dashboard sections rendered:
- Top: 5-card status row (Signal / Regime / Close / Price vs TL / Allocation)
- Main: 720 px candlestick + segmented trackline + 200 MA + green/red dots + BULL/BEAR labels + background tint by regime + conviction subplot with threshold overlay
- Bottom-left: 5 colored status chips (200 MA, Threshold/Conviction, Trackline, Trend Quality, Volatility regime) + blow-off / vol-shock warnings
- Bottom-right: stacked conviction breakdown (last 120 bars)
- Footer: recent 15 signal transitions table
- Sidebar: symbol selector, history slider, BTC-filter toggle, manual refresh, auto-refresh (60 s)

Live behaviour:
- `@st.cache_data(ttl=60)` on `_load_candles`, `_load_btc`, `_run` → fresh poll every 60 s without re-hammering Binance.
- Auto-refresh checkbox triggers `st.rerun()` every 60 s.
- "Refresh now" button clears caches.

## 4. What was NOT validated (out of scope for v1)

- Tick-for-tick parity vs TradingView Pine — would require running both on identical data and reconciling every bar. The structural ports of `ta.rsi`/`ta.ema`/`ta.adx`/`ta.barssince` follow Pine docs exactly, but micro-differences can exist at the seed (first ~length bars).
- Slippage / fees / position sizing — backtest is a naive "long when BULL, flat when BEAR" return proxy.
- WebSocket live updates — current implementation polls every 60 s, plenty for daily-bar strategy.
