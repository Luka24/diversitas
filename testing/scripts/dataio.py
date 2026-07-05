"""Frozen data layer for the validation campaign.

The whole testing campaign must run on *frozen* candles so that results are
bit-reproducible and don't drift because the Binance/yfinance API returned
slightly different history mid-study. First access fetches via
`shared.data_source`, writes a Parquet snapshot to `testing/data/`, and logs a
SHA256. Every later access reads the snapshot.

Usage:
    from testing.scripts.dataio import load, freeze_all, DESIGN_END, HOLDOUT_START
    df = load("BTC")                    # full frozen history
    df = load("BTC", split="design")    # start .. DESIGN_END
    df = load("BTC", split="holdout")   # HOLDOUT_START .. end  (quarantined!)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]          # DIVERSITAS/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.data_source import fetch_candles, fetch_btc_daily, fetch_spx_daily  # noqa: E402

DATA_DIR = _ROOT / "testing" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
_MANIFEST = DATA_DIR / "manifest.json"

# ── Campaign split — the hold-out is quarantined from day 1. ──────────────────
DESIGN_END    = pd.Timestamp("2025-03-31", tz="UTC")
HOLDOUT_START = pd.Timestamp("2025-04-01", tz="UTC")

# Original tuning universe + explicit survivor-bias control group (OOS only).
ASSETS_CORE    = ["BTC", "ETH", "SOL", "AVAX", "LINK"]
ASSETS_CONTROL = ["XRP", "BNB", "ADA"]           # never used for tuning
ASSETS_ALL     = ASSETS_CORE + ASSETS_CONTROL

_BARS = 2600   # ~7 years of daily candles — covers full history for all assets


def _sha256(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()[:16]


def _read_manifest() -> dict:
    if _MANIFEST.exists():
        return json.loads(_MANIFEST.read_text())
    return {}


def _write_manifest(m: dict) -> None:
    _MANIFEST.write_text(json.dumps(m, indent=2, sort_keys=True))


def _snapshot_path(key: str) -> Path:
    return DATA_DIR / f"{key}.parquet"


def freeze(key: str, fetcher) -> pd.DataFrame:
    """Return frozen snapshot for `key`; fetch + persist on first access."""
    path = _snapshot_path(key)
    if path.exists():
        return pd.read_parquet(path)
    df = fetcher()
    if df is None or len(df) == 0:
        raise RuntimeError(f"fetch for {key} returned no data")
    if not isinstance(df, pd.DataFrame):        # SPX comes back as a Series
        df = df.to_frame("close")
    df.to_parquet(path)
    man = _read_manifest()
    man[key] = {"rows": int(len(df)),
                "first": str(df.index[0]), "last": str(df.index[-1]),
                "sha16": _sha256(df)}
    _write_manifest(man)
    return df


def load(symbol: str, split: str = "all") -> pd.DataFrame:
    """Frozen candles for `symbol`. split ∈ {all, design, holdout}."""
    df = freeze(symbol, lambda: fetch_candles(symbol, "1d", bars=_BARS))
    idx = df.index
    if idx.tz is None:
        df = df.tz_localize("UTC")
    if split == "design":
        return df.loc[df.index <= DESIGN_END]
    if split == "holdout":
        return df.loc[df.index >= HOLDOUT_START]
    return df


def load_btc(split: str = "all") -> pd.DataFrame:
    df = freeze("BTC_filter", lambda: fetch_btc_daily(bars=_BARS))
    if df.index.tz is None:
        df = df.tz_localize("UTC")
    if split == "design":
        return df.loc[df.index <= DESIGN_END]
    if split == "holdout":
        return df.loc[df.index >= HOLDOUT_START]
    return df


def load_spx(split: str = "all") -> pd.Series:
    df = freeze("SPX", lambda: fetch_spx_daily(_BARS))
    s = df["close"] if "close" in df.columns else df.iloc[:, 0]
    if s.index.tz is None:
        s = s.tz_localize("UTC")
    if split == "design":
        return s.loc[s.index <= DESIGN_END]
    if split == "holdout":
        return s.loc[s.index >= HOLDOUT_START]
    return s


def freeze_all() -> dict:
    """Fetch + persist every asset up front. Returns the manifest."""
    for a in ASSETS_ALL:
        try:
            load(a)
            print(f"  frozen {a}")
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED {a}: {e}")
    try:
        load_btc(); print("  frozen BTC_filter")
    except Exception as e:  # noqa: BLE001
        print(f"  FAILED BTC_filter: {e}")
    try:
        load_spx(); print("  frozen SPX")
    except Exception as e:  # noqa: BLE001
        print(f"  FAILED SPX: {e}")
    return _read_manifest()


if __name__ == "__main__":
    print("Freezing campaign data snapshots …")
    man = freeze_all()
    print(json.dumps(man, indent=2, sort_keys=True))
