"""Unit tests for the source-selection and parser logic of data_source.

No real network calls — we mock requests.get and yfinance via monkeypatch.
"""
import time as _time
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from shared import data_source as ds


# ---------- parsers --------------------------------------------------------

def test_binance_parse_columns_and_types():
    raw = [
        [1700000000000, "100.0", "110.0", "90.0", "105.0", "1234.5",
         1700086399999, "0", 0, "0", "0", "0"],
    ]
    df = ds._binance_parse(raw)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df["close"].iloc[0] == 105.0
    assert df.index[0].tzname() == "UTC"


def test_coinbase_parse_columns_and_types():
    # Coinbase order: [time_sec, low, high, open, close, volume]
    raw = [
        [1700000000, 90.0, 110.0, 100.0, 105.0, 1234.5],
    ]
    df = ds._coinbase_parse(raw)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    # Verify the L/H reorder didn't drop anything
    assert df["low"].iloc[0] == 90.0
    assert df["high"].iloc[0] == 110.0
    assert df["close"].iloc[0] == 105.0
    assert df.index[0].tzname() == "UTC"


# ---------- source ordering -----------------------------------------------

def _ok_df():
    idx = pd.date_range("2025-01-01", periods=3, freq="D", tz="UTC")
    return pd.DataFrame({"open": [1, 2, 3], "high": [1, 2, 3],
                         "low": [1, 2, 3], "close": [1, 2, 3],
                         "volume": [1, 2, 3]}, index=idx)


def test_default_prefer_tries_binance_first(monkeypatch):
    calls = []
    monkeypatch.setattr(ds, "_binance_fetch",
                        lambda *a, **kw: (calls.append("binance"), _ok_df())[1])
    monkeypatch.setattr(ds, "_coinbase_fetch",
                        lambda *a, **kw: (calls.append("coinbase"), _ok_df())[1])
    monkeypatch.setattr(ds, "_yf_fetch",
                        lambda *a, **kw: (calls.append("yahoo"), _ok_df())[1])

    df = ds.fetch_candles("BTC", "1d", bars=3)
    assert len(df) == 3
    assert calls == ["binance"]  # never touched fallbacks


def test_binance_failure_falls_to_coinbase(monkeypatch):
    calls = []

    def fail_binance(*a, **kw):
        calls.append("binance")
        raise ds.DataSourceError("simulated geo block")

    monkeypatch.setattr(ds, "_binance_fetch", fail_binance)
    monkeypatch.setattr(ds, "_coinbase_fetch",
                        lambda *a, **kw: (calls.append("coinbase"), _ok_df())[1])
    monkeypatch.setattr(ds, "_yf_fetch",
                        lambda *a, **kw: (calls.append("yahoo"), _ok_df())[1])

    df = ds.fetch_candles("BTC", "1d", bars=3)
    assert len(df) == 3
    assert calls == ["binance", "coinbase"]  # yahoo never reached


def test_all_exchanges_fail_yahoo_rescue(monkeypatch):
    calls = []
    monkeypatch.setattr(ds, "_binance_fetch",
                        lambda *a, **kw: (calls.append("b"), (_ for _ in ()).throw(
                            ds.DataSourceError("binance down")))[1])
    monkeypatch.setattr(ds, "_coinbase_fetch",
                        lambda *a, **kw: (calls.append("c"), (_ for _ in ()).throw(
                            ds.DataSourceError("coinbase down")))[1])
    monkeypatch.setattr(ds, "_yf_fetch",
                        lambda *a, **kw: (calls.append("y"), _ok_df())[1])

    df = ds.fetch_candles("BTC", "1d", bars=3)
    assert len(df) == 3
    assert calls == ["b", "c", "y"]


def test_all_sources_fail_raises(monkeypatch):
    def boom(*a, **kw):
        raise ds.DataSourceError("nope")
    monkeypatch.setattr(ds, "_binance_fetch", boom)
    monkeypatch.setattr(ds, "_coinbase_fetch", boom)
    monkeypatch.setattr(ds, "_yf_fetch", boom)

    with pytest.raises(ds.DataSourceError, match="All sources failed"):
        ds.fetch_candles("BTC", "1d", bars=3)


def test_prefer_yahoo_swaps_order(monkeypatch):
    calls = []
    monkeypatch.setattr(ds, "_binance_fetch",
                        lambda *a, **kw: (calls.append("binance"), _ok_df())[1])
    monkeypatch.setattr(ds, "_coinbase_fetch",
                        lambda *a, **kw: (calls.append("coinbase"), _ok_df())[1])
    monkeypatch.setattr(ds, "_yf_fetch",
                        lambda *a, **kw: (calls.append("yahoo"), _ok_df())[1])

    ds.fetch_candles("BTC", "1d", bars=3, prefer="yahoo")
    assert calls == ["yahoo"]


def test_missing_symbol_key_skips_source(monkeypatch):
    """BNB has no `coinbase` key in DEFAULT_SYMBOL_MAP — coinbase branch
    must raise DataSourceError before any HTTP call, so the loop moves on."""
    coinbase_called = []
    monkeypatch.setattr(ds, "_binance_fetch",
                        lambda *a, **kw: (_ for _ in ()).throw(
                            ds.DataSourceError("simulated")))
    monkeypatch.setattr(ds, "_coinbase_fetch",
                        lambda *a, **kw: coinbase_called.append(True) or _ok_df())
    monkeypatch.setattr(ds, "_yf_fetch", lambda *a, **kw: _ok_df())

    df = ds.fetch_candles("BNB", "1d", bars=3)
    assert len(df) == 3
    # BNB has no coinbase product → coinbase fetch must NOT have been invoked.
    assert coinbase_called == []


# ---------- interval map sanity -------------------------------------------

def test_interval_map_completeness():
    """Every interval present in _INTERVAL_MAP must have keys for all three
    providers (with `None` allowed for unsupported)."""
    for interval, entry in ds._INTERVAL_MAP.items():
        assert "binance" in entry, interval
        assert "yf" in entry, interval
        assert "coinbase_sec" in entry, interval


def test_coinbase_unsupported_interval_raises():
    """1w / 4h are not natively supported by Coinbase — function must raise
    DataSourceError so the source loop can fall through."""
    with pytest.raises(ds.DataSourceError, match="does not support"):
        ds._coinbase_fetch("BTC-USD", "1w", bars=10)
    with pytest.raises(ds.DataSourceError, match="does not support"):
        ds._coinbase_fetch("BTC-USD", "4h", bars=10)


def test_symbol_map_btc_eth_sol_have_coinbase():
    for sym in ("BTC", "ETH", "SOL"):
        assert "coinbase" in ds.DEFAULT_SYMBOL_MAP[sym], sym
