"""Configuration for Diversitas Pro v3 — mirrors Pine Script inputs."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Config:
    # Trackline
    track_period: int = 75
    track_buf_pct: float = 3.0

    # Momentum
    rsi_len: int = 14
    # NOTE: Pine declares `rsiThresh` (default 45) but never uses it —
    # blowoff uses a hardcoded `rsiVal > 80`. We do not mirror the dead
    # input here. See full/AUDIT.md §11 (Pine bug #1) for the rationale.
    ema_fast: int = 21
    ema_slow: int = 55
    adx_len: int = 14
    struct_len: int = 20

    # Macro
    wk_ema_len: int = 21
    wk_sma_len: int = 30
    use_btc_filter: bool = True

    # Volume
    vol_len: int = 20

    # Volatility
    vol_lookback: int = 20
    target_vol_pct: float = 25.0
    blowoff_dist_pct: float = 25.0
    vol_shock_mul: float = 1.5

    # Anti-churn
    confirm_bars: int = 3
    reentry_hold: int = 15
    grace_bars: int = 5
    exit_grace_bars: int = 3
    conv_smooth: int = 5

    # Efficiency Ratio trend filter (Kaufman)
    use_er: bool = True
    er_len: int = 10          # lookback bars
    er_thresh: float = 0.30   # below this = chop, entry blocked

    # Display / behaviour
    skip_weekend: bool = True

    # Asset symbol mapping (logical -> per-source identifier)
    # Used by data_source.py
    symbol_map: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        # ── crypto (Binance primary, yfinance fallback) ───────────────────────
        "BTC":  {"binance": "BTCUSDT", "yahoo": "BTC-USD",  "coingecko": "bitcoin"},
        "ETH":  {"binance": "ETHUSDT", "yahoo": "ETH-USD",  "coingecko": "ethereum"},
        "SOL":  {"binance": "SOLUSDT", "yahoo": "SOL-USD",  "coingecko": "solana"},
        "BNB":  {"binance": "BNBUSDT", "yahoo": "BNB-USD",  "coingecko": "binancecoin"},
        "XRP":  {"binance": "XRPUSDT", "yahoo": "XRP-USD",  "coingecko": "ripple"},
        "ADA":  {"binance": "ADAUSDT", "yahoo": "ADA-USD",  "coingecko": "cardano"},
        "AVAX": {"binance": "AVAXUSDT","yahoo": "AVAX-USD", "coingecko": "avalanche-2"},
        "LINK": {"binance": "LINKUSDT","yahoo": "LINK-USD", "coingecko": "chainlink"},
        # ── equities / ETFs (yfinance only, 252 trading days/yr) ─────────────
        "SPY":  {"yahoo": "SPY"},    # S&P 500 ETF
        "QQQ":  {"yahoo": "QQQ"},    # Nasdaq-100 ETF
        "GLD":  {"yahoo": "GLD"},    # Gold ETF
    })


DEFAULT_CONFIG = Config()
