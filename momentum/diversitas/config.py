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
    vol_shock_mul: float = 1.5
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
        "BTC":  {"binance": "BTCUSDT", "yahoo": "BTC-USD", "coingecko": "bitcoin"},
        "ETH":  {"binance": "ETHUSDT", "yahoo": "ETH-USD", "coingecko": "ethereum"},
        "SOL":  {"binance": "SOLUSDT", "yahoo": "SOL-USD", "coingecko": "solana"},
        "BNB":  {"binance": "BNBUSDT", "yahoo": "BNB-USD", "coingecko": "binancecoin"},
        "XRP":  {"binance": "XRPUSDT", "yahoo": "XRP-USD", "coingecko": "ripple"},
        "ADA":  {"binance": "ADAUSDT", "yahoo": "ADA-USD", "coingecko": "cardano"},
        "AVAX": {"binance": "AVAXUSDT", "yahoo": "AVAX-USD", "coingecko": "avalanche-2"},
        "LINK": {"binance": "LINKUSDT", "yahoo": "LINK-USD", "coingecko": "chainlink"},
        "SPY":  {"yahoo": "SPY"},
        "QQQ":  {"yahoo": "QQQ"},
        "GLD":  {"yahoo": "GLD"},
    })


DEFAULT_CONFIG = MomentumConfig()
