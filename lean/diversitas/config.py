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

    # Efficiency Ratio trend filter (Kaufman)
    use_er: bool = True
    er_len: int = 10          # lookback bars
    er_thresh: float = 0.30   # below this = chop, entry blocked

    # Optional cross-asset filter — OFF by default in Lean
    use_btc_filter: bool = False

    # Trading-day calendar: 365 for crypto (24/7), 252 for stock ETFs
    trading_days: int = 365

    # Symbol → per-source identifier (same map as full)
    symbol_map: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        "BTC": {"binance": "BTCUSDT", "yahoo": "BTC-USD", "coingecko": "bitcoin"},
        "ETH": {"binance": "ETHUSDT", "yahoo": "ETH-USD", "coingecko": "ethereum"},
        "SOL": {"binance": "SOLUSDT", "yahoo": "SOL-USD", "coingecko": "solana"},
        "BNB": {"binance": "BNBUSDT", "yahoo": "BNB-USD", "coingecko": "binancecoin"},
        "XRP": {"binance": "XRPUSDT", "yahoo": "XRP-USD", "coingecko": "ripple"},
        "ADA": {"binance": "ADAUSDT", "yahoo": "ADA-USD", "coingecko": "cardano"},
        "AVAX": {"binance": "AVAXUSDT", "yahoo": "AVAX-USD", "coingecko": "avalanche-2"},
        "LINK": {"binance": "LINKUSDT", "yahoo": "LINK-USD", "coingecko": "chainlink"},
        # ── equities / ETFs (yfinance only, 252 trading days/yr) ─────────────
        "SPY":  {"yahoo": "SPY"},    # S&P 500 ETF
        "QQQ":  {"yahoo": "QQQ"},    # Nasdaq-100 ETF
        "GLD":  {"yahoo": "GLD"},    # Gold ETF
    })


DEFAULT_CONFIG = LeanConfig()
