"""Donchian and the Kijun trackline are the same formula. Which difference matters?

The mentor's observation turns out to be exact rather than approximate. Writing
the Donchian condition in terms of the channel midpoint:

    (close - low) / (high - low) > 0.75
    close > low + 0.75 * (high - low)
    close > mid + 0.25 * (high - low)          because mid = (high + low) / 2

Verified identical on all 2700 BTC bars. So both rules have the same shape —
"above the midpoint of the high/low range, plus a buffer" — and differ in exactly
two ways:

    period    75 days (trackline) against 20 days (Donchian)
    buffer    3 % of PRICE, fixed, against 25 % of RANGE WIDTH, which moves
              with the range and so with volatility

That is a clean 2x2, and it separates the two explanations for the Donchian
result. Either the short lookback does the work, or the range-scaled buffer does
— the thing step 5 tried to build by hand and could not.

    A  mid75 + 3 % of price        today's engine
    B  mid20 + 3 % of price        short period, fixed buffer
    C  mid75 + 25 % of range75     long period, range buffer
    D  mid20 + 25 % of range20     Donchian, what was tested

Exactly four cells. Both periods and both buffer definitions are pre-existing
conventions, nothing is swept, and no fifth combination is tried.

Output: testing/data/kijun_vs_donchian.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "testing", ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared import indicators as ind
from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

FEE, PPY = 0.30, 365
SRC = ROOT / "testing" / "data" / "sources"
OUT = ROOT / "testing" / "data" / "kijun_vs_donchian.json"
SUBPERIODS = [("I", "2019-03-09", "2021-01-31"), ("II", "2021-02-01", "2022-11-30"),
              ("III", "2022-12-01", "2024-09-30"), ("IV", "2024-10-01", "2026-07-29")]
BULL_TERMS = ("track_rising_window", "regime_ok", "btc_filter_ok")

CELLS = {
    "A": (75, "cena", "mid75 + 3 % cene  (danes)"),
    "B": (20, "cena", "mid20 + 3 % cene"),
    "C": (75, "razpon", "mid75 + 25 % razpona75"),
    "D": (20, "razpon", "mid20 + 25 % razpona20  (Donchian)"),
}


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def build(raw, period, buftype):
    """Rebuild above_tl / below_tl from the chosen midpoint and buffer, then run
    the untouched production state machine."""
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    hi = ind.highest(raw["high"], period)
    lo = ind.lowest(raw["low"], period)
    mid = (hi + lo) / 2.0
    band = (mid * cfg.track_buf_pct / 100.0 if buftype == "cena"
            else 0.25 * (hi - lo))
    df["trackline"] = mid
    df["above_tl"] = df["close"] > mid + band
    df["below_tl"] = df["close"] < mid - band
    df["dist_pct"] = (df["close"] - mid) / mid * 100.0
    df["track_rising_window"] = mid > mid.shift(cfg.track_slope_bars)
    df["blowoff"] = (df["dist_pct"] > cfg.blowoff_dist_pct) & (df["rsi"] > 80)
    df["band_pct"] = (band / df["close"] * 100.0)
    bull = df["above_tl"].copy()
    for t in BULL_TERMS:
        bull &= df[t]
    df["bull_condition"] = (bull & ~df["blowoff"]).fillna(False)
    df["trend_break"] = df["below_tl"]
    st = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos, st


def main() -> int:
    out = {"fee_per_side_pct": FEE, "cells": {k: v[2] for k, v in CELLS.items()}}
    for sym, f in (("BTC", "BTC_binance_warmup.parquet"), ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(SRC / f)
        ret = raw["close"].pct_change().fillna(0.0)
        print(f"\n{'='*94}\n{sym}\n{'='*94}")
        print(f"  {'':38}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
              f"{'izpost':>8}{'posl':>6}{'pas mediana':>13}   I    II   III    IV")
        res = {}
        for k, (per, bt, lab) in CELLS.items():
            pos, st = build(raw, per, bt)
            r = net_returns(pos, ret, FEE).to_numpy(float)
            eq = np.cumprod(1 + r)
            p = pos.to_numpy()
            sub = {}
            for nm, a, b in SUBPERIODS:
                w = pos.index[(pos.index >= a) & (pos.index <= b)]
                sub[nm] = (round(sortino(net_returns(pos.reindex(w), ret, FEE)
                                         .to_numpy(float)), 2) if len(w) > 60 else None)
            bm = float(st["band_pct"].median())
            res[k] = {"label": lab, "period": per, "buffer": bt,
                      "sortino": round(sortino(r), 3),
                      "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
                      "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
                      "exposure": round(float(p.mean() * 100), 1),
                      "trades": int((np.diff(p, prepend=p[0]) > 0).sum()),
                      "turnover": round(float(turnover(pos).sum()), 1),
                      "band_median_pct": round(bm, 1), "sub": sub}
            m = res[k]
            s = "  ".join(f"{v:.2f}" if v is not None else "  — " for v in sub.values())
            print(f"  {k}  {lab:<35}{m['sortino']:>7.3f}{m['cagr']:>6.1f}%"
                  f"{m['maxdd']:>7.1f}%{m['final']:>6.2f}x{m['exposure']:>7.1f}%"
                  f"{m['trades']:>6d}{bm:>12.1f}%   {s}")
        out[sym] = res
        a, b, c, dd = (res[x]["sortino"] for x in "ABCD")
        print(f"\n  razgradnja proti A = {a:.3f}")
        print(f"    samo krajša perioda  (A→B)  {b-a:+.3f}")
        print(f"    samo pas iz razpona  (A→C)  {c-a:+.3f}")
        print(f"    oboje                (A→D)  {dd-a:+.3f}")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
