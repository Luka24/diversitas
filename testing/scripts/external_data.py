"""External data for the on-chain (§6) + macro (§7) pipes — fetched once, frozen.

Obtainable free:
  - DXY  (US dollar index)          — FRED DTWEXBGS
  - BBB corporate spread            — FRED BAMLC0A4CBBB
  - Coinbase Premium (BTC)          — Coinbase BTC-USD vs Binance BTCUSDT
Not obtainable free (documented, not tested):
  - MVRV                            — needs Glassnode/CoinGlass (paid on-chain)

All series are reindexed onto a crypto daily (24/7) index with forward-fill so the
gates line up with the OHLCV strategy bars.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import shared.data_source as ds

DATA = _ROOT / "testing" / "data"
DATA.mkdir(parents=True, exist_ok=True)


def _fred(series_id: str) -> pd.Series:
    r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", timeout=20)
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "val"]
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["val"] = pd.to_numeric(df["val"], errors="coerce")
    return df.dropna().set_index("date")["val"]


def _freeze(name: str, fetch) -> pd.Series:
    p = DATA / f"ext_{name}.parquet"
    if p.exists():
        return pd.read_parquet(p)["val"]
    s = fetch().rename("val")
    s.to_frame().to_parquet(p)
    return s


def dxy() -> pd.Series:
    return _freeze("dxy", lambda: _fred("DTWEXBGS"))


def bbb() -> pd.Series:
    return _freeze("bbb", lambda: _fred("BAMLC0A4CBBB"))


def cb_premium() -> pd.Series:
    """Coinbase BTC-USD vs Binance BTCUSDT close, as a % premium (frozen)."""
    def fetch():
        cb = ds._coinbase_fetch("BTC-USD", "1d", 2000)   # returns parsed DataFrame
        bn = ds._binance_fetch("BTCUSDT", "1d", 2000)
        al = pd.concat([cb["close"].rename("cb"), bn["close"].rename("bn")],
                       axis=1).dropna()
        return (al["cb"] / al["bn"] - 1.0) * 100.0
    return _freeze("cb_premium", fetch)


def align(series: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Reindex a business-day/irregular series onto a crypto daily index (ffill)."""
    s = series.copy()
    if s.index.tz is None:
        s.index = s.index.tz_localize("UTC")
    idx = index.tz_convert("UTC") if index.tz is not None else index.tz_localize("UTC")
    return s.reindex(s.index.union(idx)).ffill().reindex(idx)


# ── derived gate signals (per Q&A doc logic) ─────────────────────────────────

def macro_bear(index, dxy_yoy_thr=2.0, bbb_mult=1.10, bbb_ma=63) -> pd.Series:
    """Macro pipe BEAR (per §7): DXY YoY > thr% AND BBB spread > bbb_ma-SMA·mult."""
    d = align(dxy(), index)
    yoy = (d / d.shift(252) - 1.0) * 100.0
    b = align(bbb(), index)
    bbb_bear = b > b.rolling(bbb_ma, min_periods=20).mean() * bbb_mult
    dxy_bear = yoy > dxy_yoy_thr
    return (bbb_bear & dxy_bear).fillna(False)


def premium_bear(index, thr=-0.1, smooth=14) -> pd.Series:
    """On-chain flow BEAR (per §6): smoothed Coinbase premium < thr% (BTC)."""
    p = align(cb_premium(), index).rolling(smooth, min_periods=3).mean()
    return (p < thr).fillna(False)


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    print("Freezing external data …")
    for n, f in [("DXY", dxy), ("BBB", bbb), ("CB premium", cb_premium)]:
        try:
            s = f()
            print(f"  {n:12} {len(s)} rows  {s.index[0].date()} → {s.index[-1].date()}")
        except Exception as e:  # noqa: BLE001
            print(f"  {n:12} FAILED: {e}")
