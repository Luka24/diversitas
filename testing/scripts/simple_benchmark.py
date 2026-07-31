"""Is Lean better than the simplest thing that could possibly work?

This is the first question a reviewer asks and it had not been asked. Every
comparison so far has been against buy and hold, which is a low bar for anything
that spends 40% of its time in cash. The honest bar is a one-line trend rule:
hold when the close is above a moving average, otherwise hold nothing.

The comparison is deliberately unfair to Lean in one respect and fair in another.
Unfair: the simple rules pay the same 0.30% per side and trade two to three times
more often, so costs bite them harder. Fair: they have four settings between them
and Lean has 137 trials behind it, so whatever selection advantage exists sits on
Lean's side of the table.

Output: testing/data/simple_benchmark_BTC.json
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

from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

FEE, PPY = 0.30, 365
NBOOT, BLOCK, SEED = 2000, 20, 20260801
SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
OUT = ROOT / "testing" / "data" / "simple_benchmark_BTC.json"
WINDOWS = {"pet let": ("2021-07-01", "2026-06-30"),
           "celotno": (None, None)}
MA_LENS = [100, 150, 200, 250]


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def sharpe(r):
    sd = r.std(ddof=1) * np.sqrt(PPY)
    return float(r.mean() * PPY / sd) if sd > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def cagr(r):
    return float((float(np.prod(1.0 + r)) ** (PPY / len(r)) - 1.0) * 100.0)


def _blocks(rng, n, B, L):
    nb = int(np.ceil(n / L))
    st = rng.integers(0, n, size=(B, nb))
    return (st[:, :, None] + np.arange(L)[None, None, :]).reshape(B, nb * L)[:, :n] % n


def paired_ci(a, b, fn, rng):
    """CI for fn(a) - fn(b) with the same resampled days applied to both."""
    idx = _blocks(rng, len(a), NBOOT, BLOCK)
    d = np.array([fn(a[i]) - fn(b[i]) for i in idx])
    d = d[np.isfinite(d)]
    lo, hi = np.percentile(d, [2.5, 97.5])
    return round(float(lo), 3), round(float(hi), 3), bool(lo > 0 or hi < 0)


def main():
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    rng = np.random.default_rng(SEED)

    df = trim_warmup(engine.strategy_module("lean")
                     .run_strategy(raw, btc_daily=None, config=engine.make_config("lean")).df)
    lean_full = pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)

    # The MA rules need their own warm-up; align everything on what all of them share.
    sig = {}
    for n in MA_LENS:
        ma = raw["close"].rolling(n).mean()
        s = (raw["close"] > ma).shift(1)
        sig[n] = s.reindex(lean_full.index).astype("boolean").fillna(False).astype(float)
    common = lean_full.dropna().index
    for n in MA_LENS:
        common = common.intersection(sig[n].dropna().index)

    out = {"fee_per_side_pct": FEE, "nboot": NBOOT, "block": BLOCK, "windows": {}}
    for wname, (w0, w1) in WINDOWS.items():
        win = common
        if w0:
            win = win[(win >= w0) & (win <= w1)]
        r = ret.reindex(win)
        series = {"Lean": net_returns(lean_full.reindex(win), r, FEE).to_numpy(float)}
        pos = {"Lean": lean_full.reindex(win)}
        for n in MA_LENS:
            pos[f"nad {n} MA"] = sig[n].reindex(win)
            series[f"nad {n} MA"] = net_returns(sig[n].reindex(win), r, FEE).to_numpy(float)
        bh = r.to_numpy(float)

        rows = {}
        for name, rr in series.items():
            p = pos[name]
            rows[name] = {
                "sortino": round(sortino(rr), 3), "sharpe": round(sharpe(rr), 3),
                "cagr": round(cagr(rr), 1), "maxdd": round(maxdd(rr), 1),
                "final": round(float(np.prod(1.0 + rr)), 2),
                "expo": round(float(p.mean() * 100), 1),
                "turnover": round(float(turnover(p).sum()), 1),
                "trades": int((np.diff(p.to_numpy(), prepend=p.to_numpy()[0]) > 0).sum())}
        rows["kupi in drži"] = {
            "sortino": round(sortino(bh), 3), "sharpe": round(sharpe(bh), 3),
            "cagr": round(cagr(bh), 1), "maxdd": round(maxdd(bh), 1),
            "final": round(float(np.prod(1.0 + bh)), 2), "expo": 100.0,
            "turnover": 1.0, "trades": 1}

        # Lean against the best simple rule, judged on both metrics
        best = max(MA_LENS, key=lambda n: rows[f"nad {n} MA"]["sortino"])
        b = series[f"nad {best} MA"]
        s_lo, s_hi, s_sig = paired_ci(series["Lean"], b, sortino, rng)
        d_lo, d_hi, d_sig = paired_ci(series["Lean"], b, maxdd, rng)
        cmp = {"best_ma": best,
               "d_sortino": round(rows["Lean"]["sortino"] - rows[f"nad {best} MA"]["sortino"], 3),
               "ci_sortino": [s_lo, s_hi], "sig_sortino": s_sig,
               "d_maxdd": round(rows["Lean"]["maxdd"] - rows[f"nad {best} MA"]["maxdd"], 1),
               "ci_maxdd": [d_lo, d_hi], "sig_maxdd": d_sig}
        out["windows"][wname] = {
            "from": str(win[0].date()), "to": str(win[-1].date()), "n": len(win),
            "rows": rows, "vs_best_simple": cmp}

        print(f"\n{'='*82}\n{wname.upper()}  {win[0].date()} → {win[-1].date()}  ({len(win)} dni)")
        print(f"{'razlicica':16} {'Sortino':>8} {'Sharpe':>8} {'CAGR':>8} {'MaxDD':>9} "
              f"{'konec':>7} {'poslov':>7} {'izpost':>8}")
        for name, m in rows.items():
            print(f"  {name:14} {m['sortino']:8.3f} {m['sharpe']:8.3f} {m['cagr']:7.1f} % "
                  f"{m['maxdd']:8.1f} % {m['final']:7.2f} {m['trades']:7d} {m['expo']:7.1f} %")
        print(f"\n  Lean proti najboljšemu preprostemu (nad {best} MA):")
        print(f"    ΔSortino {cmp['d_sortino']:+.3f}  razpon [{s_lo:+.2f}, {s_hi:+.2f}]"
              f"{'  ZNAČILNO' if s_sig else '  ni značilno'}")
        print(f"    ΔMaxDD   {cmp['d_maxdd']:+.1f} o. t.  razpon [{d_lo:+.1f}, {d_hi:+.1f}]"
              f"{'  ZNAČILNO' if d_sig else '  ni značilno'}")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
