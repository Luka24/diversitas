"""Crypto candle fetching — Binance primary, Coinbase + yfinance fallbacks.

Public API of this module:
    fetch_candles(symbol, interval='1d', bars=500) -> pd.DataFrame
        Returns UTC-indexed DataFrame with columns [open, high, low, close, volume].

Source ordering (per call):
    1. Binance public REST  (no key, 6000 weight/min)
    2. Coinbase Advanced    (no key, 10 req/sec, deepest history from 2015,
                             US-friendly when Binance is geo-blocked)
    3. yfinance              (no key, ~15 min latency, daily candles only)

Rationale documented in API_REPORT.md.

Symbol resolution: pass `config` (any object exposing a `.symbol_map` dict)
or rely on the built-in DEFAULT_SYMBOL_MAP fallback. This keeps the module
config-agnostic — both `full` and `lean` Diversitas variants share it.
"""
from __future__ import annotations
import time
import warnings
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd
import requests


# Default symbol → per-source identifier mapping. Both LeanConfig and (Full)
# Config also carry this map; callers can override by passing `config`.
DEFAULT_SYMBOL_MAP: Mapping[str, Mapping[str, str]] = {
    "BTC": {"binance": "BTCUSDT", "coinbase": "BTC-USD", "yahoo": "BTC-USD", "coingecko": "bitcoin"},
    "ETH": {"binance": "ETHUSDT", "coinbase": "ETH-USD", "yahoo": "ETH-USD", "coingecko": "ethereum"},
    "SOL": {"binance": "SOLUSDT", "coinbase": "SOL-USD", "yahoo": "SOL-USD", "coingecko": "solana"},
    # BNB is not listed on Coinbase — leave the key out so fallback skips it.
    "BNB": {"binance": "BNBUSDT", "yahoo": "BNB-USD", "coingecko": "binancecoin"},
    "XRP": {"binance": "XRPUSDT", "coinbase": "XRP-USD", "yahoo": "XRP-USD", "coingecko": "ripple"},
    "ADA": {"binance": "ADAUSDT", "coinbase": "ADA-USD", "yahoo": "ADA-USD", "coingecko": "cardano"},
    "AVAX": {"binance": "AVAXUSDT", "coinbase": "AVAX-USD", "yahoo": "AVAX-USD", "coingecko": "avalanche-2"},
    "LINK": {"binance": "LINKUSDT", "coinbase": "LINK-USD", "yahoo": "LINK-USD", "coingecko": "chainlink"},
    # ── equities / ETFs (yfinance only, 252 trading days/yr) ─────────────────
    "SPY": {"yahoo": "SPY"},   # S&P 500 ETF
    "QQQ": {"yahoo": "QQQ"},   # Nasdaq-100 ETF
    "GLD": {"yahoo": "GLD"},   # Gold ETF
}


def _resolve_symbol_map(config: Any) -> Mapping[str, Mapping[str, str]]:
    """Accept either a Config object (with .symbol_map) or None for default."""
    if config is None:
        return DEFAULT_SYMBOL_MAP
    sm = getattr(config, "symbol_map", None)
    if sm is None:
        return DEFAULT_SYMBOL_MAP
    return sm


BINANCE_URL = "https://api.binance.com/api/v3/klines"
COINBASE_URL = "https://api.exchange.coinbase.com/products/{pid}/candles"

# Logical interval -> per-source code / granularity.
# Coinbase only supports a fixed set of granularities (seconds):
#   60 / 300 / 900 / 3600 / 21600 / 86400. We mark unsupported as None.
_INTERVAL_MAP = {
    "1d": {"binance": "1d", "yf": "1d",  "coinbase_sec": 86400},
    "1w": {"binance": "1w", "yf": "1wk", "coinbase_sec": None},  # caller resamples
    "4h": {"binance": "4h", "yf": "1h",  "coinbase_sec": None},  # 14400 not supported
    "1h": {"binance": "1h", "yf": "1h",  "coinbase_sec": 3600},
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


def _coinbase_fetch(product_id: str, interval: str, bars: int) -> pd.DataFrame:
    """Fetch up to `bars` recent candles from Coinbase Advanced Trade.

    The endpoint is `/products/{id}/candles` (max 300 candles/call). We
    paginate backwards via the `end` parameter using the oldest timestamp
    of the previous page minus one granularity step.

    Coinbase returns candles **newest first**, as arrays
    `[time_sec, low, high, open, close, volume]`.

    Only supports granularities listed in `_INTERVAL_MAP[interval]['coinbase_sec']`;
    raises DataSourceError for unsupported intervals (caller's source loop
    will fall through to the next provider).
    """
    gran = _INTERVAL_MAP[interval]["coinbase_sec"]
    if gran is None:
        raise DataSourceError(
            f"Coinbase does not support interval {interval!r} natively"
        )

    per_call = 300
    remaining = bars
    chunks: list[pd.DataFrame] = []
    end_ts: Optional[int] = None  # epoch seconds

    headers = {"User-Agent": "diversitas/1.0"}

    while remaining > 0:
        params: dict = {"granularity": gran}
        if end_ts is not None:
            # end is inclusive on Coinbase — step one granularity back
            end_dt = pd.Timestamp(end_ts, unit="s", tz="UTC")
            start_dt = end_dt - pd.Timedelta(seconds=gran * per_call)
            params["start"] = start_dt.isoformat()
            params["end"] = end_dt.isoformat()

        r = requests.get(
            COINBASE_URL.format(pid=product_id),
            params=params, headers=headers, timeout=15,
        )
        if r.status_code == 429:
            raise DataSourceError("Coinbase rate limit hit (HTTP 429)")
        if r.status_code != 200:
            raise DataSourceError(
                f"Coinbase HTTP {r.status_code}: {r.text[:200]}"
            )
        raw = r.json()
        if not isinstance(raw, list) or not raw:
            break

        df_chunk = _coinbase_parse(raw)
        chunks.append(df_chunk)
        remaining -= len(df_chunk)
        # next page: end = earliest_returned - 1 second
        earliest_ts = int(min(row[0] for row in raw))
        end_ts = earliest_ts - 1
        if len(raw) < per_call:
            break
        time.sleep(0.1)  # be polite (10 req/sec IP cap)

    if not chunks:
        raise DataSourceError(
            f"Coinbase returned no candles for {product_id}"
        )

    df = pd.concat(chunks).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df.tail(bars)


def _coinbase_parse(raw: list[list]) -> pd.DataFrame:
    """Coinbase candle order: [time_sec, low, high, open, close, volume]."""
    cols = ["time_sec", "low", "high", "open", "close", "volume"]
    df = pd.DataFrame(raw, columns=cols)
    df["time"] = pd.to_datetime(df["time_sec"].astype("int64"), unit="s", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    df = df.set_index("time")[["open", "high", "low", "close", "volume"]]
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
    config: Any = None,
    prefer: str = "binance",
) -> pd.DataFrame:
    """Public entry point.

    Args:
        symbol: logical symbol, e.g. 'BTC', 'ETH'. Must be in symbol_map.
        interval: '1d', '1w', '4h', '1h'.
        bars: number of most-recent candles to return.
        config: any object exposing `.symbol_map` (e.g. Config, LeanConfig).
                Pass `None` to use the built-in DEFAULT_SYMBOL_MAP.
        prefer: which source to try FIRST. Accepts 'binance' (default),
                'coinbase', or 'yahoo'. The other two are tried in order
                as fallbacks if the preferred one fails.

    Returns:
        DataFrame indexed by UTC timestamp, columns [open, high, low, close, volume].
    """
    symbol_map = _resolve_symbol_map(config)
    symbol = symbol.upper()
    if symbol not in symbol_map:
        raise ValueError(
            f"Unknown symbol {symbol!r}. Known: {sorted(symbol_map)}"
        )
    if interval not in _INTERVAL_MAP:
        raise ValueError(f"Unsupported interval {interval!r}")

    # Source ordering: primary first, then fallbacks. `prefer` can override
    # the primary; we always try Coinbase before yfinance because Coinbase is
    # a real exchange (Yahoo is a scraper).
    if prefer == "yahoo":
        sources = ["yahoo", "binance", "coinbase"]
    elif prefer == "coinbase":
        sources = ["coinbase", "binance", "yahoo"]
    else:  # default / "binance"
        sources = ["binance", "coinbase", "yahoo"]

    last_err: Optional[Exception] = None
    for src in sources:
        try:
            if src == "binance":
                if "binance" not in symbol_map[symbol]:
                    raise DataSourceError(f"No Binance id for {symbol}")
                return _binance_fetch(
                    symbol_map[symbol]["binance"],
                    _INTERVAL_MAP[interval]["binance"],
                    bars,
                )
            if src == "coinbase":
                if "coinbase" not in symbol_map[symbol]:
                    raise DataSourceError(f"No Coinbase product for {symbol}")
                return _coinbase_fetch(
                    symbol_map[symbol]["coinbase"],
                    interval,
                    bars,
                )
            if src == "yahoo":
                if "yahoo" not in symbol_map[symbol]:
                    raise DataSourceError(f"No Yahoo ticker for {symbol}")
                return _yf_fetch(
                    symbol_map[symbol]["yahoo"],
                    interval,
                    bars,
                )
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise DataSourceError(
        f"All sources failed for {symbol} {interval}: {last_err}"
    )


def fetch_btc_daily(bars: int = 500, config: Any = None) -> pd.DataFrame:
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
