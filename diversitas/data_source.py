"""Crypto candle fetching — Binance primary, yfinance fallback.

Public API of this module:
    fetch_candles(symbol, interval='1d', bars=500) -> pd.DataFrame
        Returns UTC-indexed DataFrame with columns [open, high, low, close, volume].

Source ordering (per call):
    1. Binance public REST  (no key, 6000 weight/min)
    2. yfinance              (no key, ~15 min latency, daily candles only)

Symbol resolution uses Config.symbol_map.
"""
from __future__ import annotations
import time
import warnings
from typing import Optional

import numpy as np
import pandas as pd
import requests

from .config import Config, DEFAULT_CONFIG


BINANCE_URL = "https://api.binance.com/api/v3/klines"

# Logical interval -> (Binance code, pandas resample rule, yfinance interval)
_INTERVAL_MAP = {
    "1d": {"binance": "1d", "yf": "1d"},
    "1w": {"binance": "1w", "yf": "1wk"},
    "4h": {"binance": "4h", "yf": "1h"},  # yf has no 4h, caller resamples
    "1h": {"binance": "1h", "yf": "1h"},
}


class DataSourceError(RuntimeError):
    pass


def _binance_fetch(symbol_binance: str, interval: str, bars: int) -> pd.DataFrame:
    """Fetch up to `bars` recent candles from Binance.

    Binance's `limit` max is 1000. For larger requests we paginate backwards
    using `endTime`.
    """
    per_call = 1000
    remaining = bars
    chunks: list[pd.DataFrame] = []
    end_time: Optional[int] = None

    while remaining > 0:
        params = {
            "symbol": symbol_binance,
            "interval": interval,
            "limit": min(per_call, remaining),
        }
        if end_time is not None:
            params["endTime"] = end_time
        r = requests.get(BINANCE_URL, params=params, timeout=15)
        if r.status_code == 429:
            raise DataSourceError("Binance rate limit hit (HTTP 429)")
        if r.status_code != 200:
            raise DataSourceError(
                f"Binance HTTP {r.status_code}: {r.text[:200]}"
            )
        raw = r.json()
        if not raw:
            break
        df_chunk = _binance_parse(raw)
        chunks.append(df_chunk)
        remaining -= len(df_chunk)
        # next page: end at the open of the earliest candle minus 1 ms
        first_open_ms = int(raw[0][0])
        end_time = first_open_ms - 1
        if len(raw) < params["limit"]:
            break
        time.sleep(0.05)  # be polite

    if not chunks:
        raise DataSourceError(f"Binance returned no candles for {symbol_binance}")

    df = pd.concat(chunks[::-1]).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df.tail(bars)


def _binance_parse(raw: list[list]) -> pd.DataFrame:
    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore",
    ]
    df = pd.DataFrame(raw, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"].astype("int64"), unit="ms", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    df = df.set_index("open_time")[["open", "high", "low", "close", "volume"]]
    df.index.name = "time"
    return df


def _yf_fetch(symbol_yf: str, interval: str, bars: int) -> pd.DataFrame:
    """yfinance fallback. Daily candles only — for weekly we resample after."""
    import yfinance as yf

    # Need enough history for `bars` daily candles + buffer
    period_days = max(bars + 30, 60)
    if period_days > 730:
        period = "max"
    else:
        period = f"{period_days}d"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ticker = yf.Ticker(symbol_yf)
        df = ticker.history(
            period=period,
            interval=_INTERVAL_MAP.get(interval, _INTERVAL_MAP["1d"])["yf"],
            auto_adjust=False,
        )

    if df.empty:
        raise DataSourceError(f"yfinance returned empty for {symbol_yf}")

    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "time"
    return df.tail(bars)


def fetch_candles(
    symbol: str,
    interval: str = "1d",
    bars: int = 500,
    config: Config = DEFAULT_CONFIG,
    prefer: str = "binance",
) -> pd.DataFrame:
    """Public entry point.

    Args:
        symbol: logical symbol, e.g. 'BTC', 'ETH'. Must be in config.symbol_map.
        interval: '1d', '1w', '4h', '1h'.
        bars: number of most-recent candles to return.
        prefer: 'binance' (default) or 'yahoo' to force a source.

    Returns:
        DataFrame indexed by UTC timestamp, columns [open, high, low, close, volume].
    """
    symbol = symbol.upper()
    if symbol not in config.symbol_map:
        raise ValueError(
            f"Unknown symbol {symbol!r}. Known: {sorted(config.symbol_map)}"
        )
    if interval not in _INTERVAL_MAP:
        raise ValueError(f"Unsupported interval {interval!r}")

    sources = ["binance", "yahoo"] if prefer == "binance" else ["yahoo", "binance"]
    last_err: Optional[Exception] = None

    for src in sources:
        try:
            if src == "binance":
                return _binance_fetch(
                    config.symbol_map[symbol]["binance"],
                    _INTERVAL_MAP[interval]["binance"],
                    bars,
                )
            if src == "yahoo":
                return _yf_fetch(
                    config.symbol_map[symbol]["yahoo"],
                    interval,
                    bars,
                )
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise DataSourceError(
        f"All sources failed for {symbol} {interval}: {last_err}"
    )


def fetch_btc_daily(bars: int = 500, config: Config = DEFAULT_CONFIG) -> pd.DataFrame:
    """Convenience: BTC daily for the cross-asset filter."""
    return fetch_candles("BTC", "1d", bars=bars, config=config)


def to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to weekly (Mon-anchored, label = Monday).

    Used for the macro filters (weekly EMA/SMA/close).
    """
    rule = "W-MON"
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    return daily.resample(rule, closed="left", label="left").agg(agg).dropna()
