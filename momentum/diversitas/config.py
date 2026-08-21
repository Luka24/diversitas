"""Configuration for Diversitas Momentum — mirrors `diversitas_momentum.pine` inputs.

Momentum is the aggressive sibling to Diversitas:
  - Faster trackline (35 vs 75)
  - Bear regime is SOFT (cuts size) not a hard block
  - Trailing stop locks gains on short moves
  - Vol-targeted sizing applies (aggression != recklessness)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class MomentumConfig:
    # Core trackline (fast)
    track_period: int = 35
    track_buf_pct: float = 2.0
    track_slope_bars: int = 7

    # Moving averages
    ma_fast_len: int = 20      # trend MA — price must be above for BULL
    ma_reg_len: int = 100      # regime MA — soft block when below + falling
    ma_slope: int = 5          # lookback bars for regime MA slope

    # Momentum filter (RSI + slow EMA)
    rsi_len: int = 14
    ema_slow_len: int = 55     # slow EMA — price must be above for momentumOK

    # Efficiency Ratio trend filter
    use_er: bool = True
    er_len: int = 10
    er_thresh: float = 0.25

    # Exits
    use_trail: bool = True
    trail_pct: float = 12.0    # trailing stop: exit if price falls trail_pct% from peak
    blowoff_dist_pct: float = 20.0
    vol_lookback: int = 20

    # Bear-regime soft cut (0 = full block like Lean, 50 = half size)
    bear_size_cut: float = 50.0

    # Anti-churn (loosened vs Lean)
    confirm_bars: int = 1
    reentry_hold: int = 4
    exit_grace_bars: int = 1

    # Sizing
    use_vol_sizing: bool = True
    target_vol_pct: float = 60.0

    # Optional cross-asset filter
    use_btc_filter: bool = False

    # Trading-day calendar: 365 for crypto (24/7), 252 for stock ETFs
    trading_days: int = 365

    # Symbol → per-source identifier
    symbol_map: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        # `coinbase` added 2026-08-21. Every crypto key here was missing one,
        # while deployment.toml pinned price_source to coinbase, so the live
        # chain asked for a venue this map could not resolve. It failed with
        # "No Coinbase product for BTC" on every render and fell through to
        # Binance. That looked like an outage and was not one; the entry simply
        # did not exist. On Streamlit Cloud, where Binance answers HTTP 451 to
        # datacenter IPs, both links failed and the page would not load at all.
        # All eight products verified online on Coinbase on 2026-08-21.
        "BTC":  {"coinbase": "BTC-USD", "binance": "BTCUSDT", "yahoo": "BTC-USD", "coingecko": "bitcoin"},
        "ETH":  {"coinbase": "ETH-USD", "binance": "ETHUSDT", "yahoo": "ETH-USD", "coingecko": "ethereum"},
        "SOL":  {"coinbase": "SOL-USD", "binance": "SOLUSDT", "yahoo": "SOL-USD", "coingecko": "solana"},
        # Coinbase listed BNB on 2025-10-22, so its history there is short.
        # Lean's config still carries a comment saying BNB is not on Coinbase;
        # that was true when it was written and is not any more.
        "BNB":  {"coinbase": "BNB-USD", "binance": "BNBUSDT", "yahoo": "BNB-USD", "coingecko": "binancecoin"},
        "XRP":  {"coinbase": "XRP-USD", "binance": "XRPUSDT", "yahoo": "XRP-USD", "coingecko": "ripple"},
        "ADA":  {"coinbase": "ADA-USD", "binance": "ADAUSDT", "yahoo": "ADA-USD", "coingecko": "cardano"},
        "AVAX": {"coinbase": "AVAX-USD", "binance": "AVAXUSDT", "yahoo": "AVAX-USD", "coingecko": "avalanche-2"},
        "LINK": {"coinbase": "LINK-USD", "binance": "LINKUSDT", "yahoo": "LINK-USD", "coingecko": "chainlink"},
        "SPY":  {"yahoo": "SPY"},
        "QQQ":  {"yahoo": "QQQ"},
        "GLD":  {"yahoo": "GLD"},
    })


DEFAULT_CONFIG = MomentumConfig()
