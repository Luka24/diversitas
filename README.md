# Diversitas Pro v3 — Python port + live dashboard

Faithful Python implementation of the `diversitas_pro_v3_200ma.pine` TradingView indicator, with a live Streamlit dashboard backed by Binance public market data.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Backtest from the terminal

```bash
.venv/bin/python -m diversitas.backtest BTC           # default 1500 daily bars
.venv/bin/python -m diversitas.backtest ETH 1000      # ETH with BTC filter
.venv/bin/python -m diversitas.backtest SOL 800 --no-btc-filter
```

Output: latest-bar status, signal distribution, every signal transition, naive equity proxy.

## Live dashboard

```bash
.venv/bin/streamlit run diversitas/dashboard.py
```
Open <http://localhost:8501> in a browser.

Features:
- Symbol selector (BTC / ETH / SOL / BNB / XRP / ADA / AVAX / LINK)
- Candlestick chart with segmented trackline, 200 MA, green/red dots, BULL/BEAR labels, regime background
- Conviction subplot with dynamic threshold overlay
- Conviction breakdown (5 components stacked)
- Status panel mirroring the Pine table
- BTC cross-asset filter toggle, 60 s auto-refresh, manual refresh button

## Tests

```bash
.venv/bin/python -m pytest diversitas/tests/ -v
```
18 tests covering indicators (RSI, EMA, RMA, ADX, bars_since, stdev) and strategy (state machine, re-entry lock, confirm bars, blow-off, weekend filter, conviction bounds).

## Data sources

- **Primary**: Binance public REST (`/api/v3/klines`, no key, 6000 weight/min).
- **Fallback**: `yfinance` (`BTC-USD`, `ETH-USD`, …).

See `API_RESEARCH.md` for full evaluation.

## Documents

- `STRATEGY_ANALYSIS.md` — Pine → Python mapping, formulas, state machine spec.
- `API_RESEARCH.md` — comparison of 6 candidate data APIs and the choice rationale.
- `VALIDATION.md` — test results, backtest sanity check, dashboard render verification.

## Project layout

```
diversitas/
├── config.py        # Config dataclass mirroring Pine inputs
├── data_source.py   # Binance + yfinance fetching, weekly resample
├── indicators.py    # RSI, EMA, SMA, RMA, ADX, bars_since, stdev (Pine-compatible)
├── strategy.py      # compute_features + run_state_machines + build_summary
├── backtest.py      # CLI runner
├── dashboard.py     # Streamlit live UI
└── tests/
    ├── test_indicators.py
    └── test_strategy.py
```
