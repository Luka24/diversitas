"""Configuration for Diversitas Lean — mirrors `diversitas_lean.pine` inputs.

Lean is intentionally smaller than Full: no conviction score, no ADX, no
weekly gate, no market structure. Bear regime is a hard block.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class LeanConfig:
    # Core trackline
    track_period: int = 75
    track_buf_pct: float = 3.0

    # Moving averages
    ma_med_len: int = 50     # trend MA, price must be above for BULL
    ma_long_len: int = 200   # regime MA, hard block when below + falling
    ma_slope: int = 5        # lookback bars for regime MA slope

    # Exits
    blowoff_dist_pct: float = 25.0
    rsi_len: int = 14
    vol_shock_mul: float = 1.5
    vol_lookback: int = 20

    # Range filter (kills sideways chop)
    track_slope_bars: int = 10
    min_dist_entry_pct: float = 0.0

    # Anti-churn
    confirm_bars: int = 3
    reentry_hold: int = 15
    exit_grace_bars: int = 3

    # Sizing (additive, off the signal path)
    use_vol_sizing: bool = True
    target_vol_pct: float = 50.0

    # NOTE: the Kaufman Efficiency Ratio gate (`use_er`, `er_len`, `er_thresh`) was
    # removed on 2026-07-27. It was a Python-only addition that Pine never had, and
    # it could not be shown to do anything: its threshold sat on the median of the ER
    # distribution, mean ER on BULL days (0.35) matched BEAR days (0.32), every
    # confidence interval spanned zero, and simply scaling positions to the same
    # average exposure matched or beat it on drawdown. See
    # `testing/porocilo_ER_lean.md` and `testing/porocilo_ER_BTC.html`.

    # Donchian breakout confirmation (validated improvement; OFF by default so the
    # a-priori Lean is unchanged). When ON, entry also requires the close to sit in
    # the top quartile of the `donchian_period`-day high/low channel.
    use_donchian: bool = False
    donchian_period: int = 55
    donchian_top_frac: float = 0.75

    # Optional cross-asset filter — OFF by default in Lean
    use_btc_filter: bool = False

    # Trading-day calendar: 365 for crypto (24/7), 252 for stock ETFs
    trading_days: int = 365

    # Symbol → per-source identifier (same map as full)
    # NOTE: the `coinbase` ids were missing here until 2026-07-27. Because this map
    # overrides `shared.data_source.DEFAULT_SYMBOL_MAP`, the Coinbase branch raised
    # "No Coinbase product" and was skipped — the fallback chain was silently
    # binance → yahoo, with no middle step and no indication in the UI.
    symbol_map: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        "BTC": {"binance": "BTCUSDT", "coinbase": "BTC-USD", "yahoo": "BTC-USD", "coingecko": "bitcoin"},
        "ETH": {"binance": "ETHUSDT", "coinbase": "ETH-USD", "yahoo": "ETH-USD", "coingecko": "ethereum"},
        "SOL": {"binance": "SOLUSDT", "coinbase": "SOL-USD", "yahoo": "SOL-USD", "coingecko": "solana"},
        # BNB is not listed on Coinbase — key intentionally absent.
        "BNB": {"binance": "BNBUSDT", "yahoo": "BNB-USD", "coingecko": "binancecoin"},
        "XRP": {"binance": "XRPUSDT", "coinbase": "XRP-USD", "yahoo": "XRP-USD", "coingecko": "ripple"},
        "ADA": {"binance": "ADAUSDT", "coinbase": "ADA-USD", "yahoo": "ADA-USD", "coingecko": "cardano"},
        "AVAX": {"binance": "AVAXUSDT", "coinbase": "AVAX-USD", "yahoo": "AVAX-USD", "coingecko": "avalanche-2"},
        "LINK": {"binance": "LINKUSDT", "coinbase": "LINK-USD", "yahoo": "LINK-USD", "coingecko": "chainlink"},
        # ── equities / ETFs (yfinance only, 252 trading days/yr) ─────────────
        "SPY":  {"yahoo": "SPY"},    # S&P 500 ETF
        "QQQ":  {"yahoo": "QQQ"},    # Nasdaq-100 ETF
        "GLD":  {"yahoo": "GLD"},    # Gold ETF
    })


DEFAULT_CONFIG = LeanConfig()
