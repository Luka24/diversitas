"""Macro series for the risk-gate test, cached to parquet.

Everything comes from Yahoo, which matters for a reason beyond convenience.
FRED carries the textbook credit-spread series (BAMLH0A0HYM2), but those publish
with a lag and get revised, so a backtest reading them by date sees numbers that
did not exist on the day — a lookahead that is invisible unless you go looking.
The ETF pair HYG/IEF is a traded proxy for the same thing: it prints in real
time, never revises, and you could actually have acted on it.

Alignment: US markets close ~20:00-21:00 UTC, a Binance daily bar closes at
23:59 UTC, so the same-day macro close IS known before the crypto close. We lag
by a day regardless. It costs signal and it removes the argument.

    python testing/scripts/macro_data.py          # refresh the cache
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import requests

OUT = ROOT / "testing" / "data" / "macro.parquet"
HDRS = {"User-Agent": "Mozilla/5.0"}
LAG_DAYS = 1

# Ticker -> what it stands for. Deliberately short: five series, each a
# different axis of risk, none of them a variation on another.
TICKERS = {
    "DX-Y.NYB": "dxy",     # dollar
    "^VIX": "vix",         # equity vol
    "^MOVE": "move",       # bond vol
    "HYG": "hyg",          # high-yield credit
    "IEF": "ief",          # duration-matched treasuries, for the credit ratio
}


def _yahoo(ticker: str, rng: str = "15y") -> pd.Series:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    r = requests.get(url, params={"range": rng, "interval": "1d"},
                     headers=HDRS, timeout=30)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).normalize()
    s = pd.Series(res["indicators"]["quote"][0]["close"], index=idx,
                  dtype="float64").dropna()
    return s[~s.index.duplicated(keep="last")].sort_index()


def build() -> pd.DataFrame:
    cols = {}
    for tkr, name in TICKERS.items():
        for attempt in range(3):
            try:
                cols[name] = _yahoo(tkr)
                print(f"  {name:5s} {tkr:10s} {len(cols[name]):5d} points  "
                      f"{cols[name].index[0].date()} -> {cols[name].index[-1].date()}")
                break
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"{tkr}: {type(e).__name__}: {e}") from e
                time.sleep(2)
    df = pd.DataFrame(cols)

    # Credit stress as one number. Falling ratio = high yield underperforming
    # duration-matched treasuries = spreads widening.
    df["credit"] = df["hyg"] / df["ief"]

    # Daily grid, forward-filled across weekends and holidays, then lagged.
    # Crypto trades on days these markets do not; carrying the last known value
    # is what a live system would have.
    full = pd.date_range(df.index[0], df.index[-1], freq="D", tz="UTC")
    df = df.reindex(full).ffill().shift(LAG_DAYS)
    df.attrs["lag_days"] = LAG_DAYS
    return df.dropna(how="all")


def load() -> pd.DataFrame:
    if not OUT.exists():
        raise FileNotFoundError(
            f"{OUT} missing — run `python testing/scripts/macro_data.py` first")
    return pd.read_parquet(OUT)


def main() -> int:
    print("Fetching macro series from Yahoo")
    df = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT)
    print(f"\n{len(df)} rows  {df.index[0].date()} -> {df.index[-1].date()}"
          f"   lagged {LAG_DAYS} day")
    print(f"-> {OUT}")
    sub = df[df.index >= "2021-01-01"]
    print(f"\nFrom 2021: {len(sub)} rows, missing values per column:")
    print(sub.isna().sum().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
