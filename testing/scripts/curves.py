"""Equity curves for the three versions, plus what removing the dead knobs bought.

Three questions this answers, all of them ones a reader will ask on seeing the
recommendation:

  1. Does the majority vote actually look different from today's setting, or is
     the whole exercise invisible on a chart?

  2. What did deleting vol_shock_mul, vol_lookback and min_dist_entry_pct buy?
     The honest answer is nothing in performance -- and the way to show that is
     to plot it and let the lines sit on top of each other. If they diverge by
     even a pixel, the deletion was not neutral and something is wrong.

  3. Daily bars cannot see an intraday drawdown. Measuring the same strategy on
     4h bars gives the more accurate figure, and the gap between them is how much
     the daily number flatters us. This is a real gain from a finer clock -- not
     statistical power, which it cannot give, but accuracy.

Output: testing/data/curves_BTC.json
"""
from __future__ import annotations

import itertools
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

FEE = 0.30
WIN_FROM, WIN_TO = "2021-07-01", "2026-06-30"
D1 = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
H4 = ROOT / "testing" / "data" / "sources" / "BTC_binance_4h.parquet"
OUT = ROOT / "testing" / "data" / "curves_BTC.json"

# The three knobs the plan deletes. Each is set to a value that makes its rule
# unreachable, which is what deleting the code would do.
DEAD = {"vol_shock_mul": 999.0, "vol_lookback": 20, "min_dist_entry_pct": 0.0}
GRID = {"ma_long_len": [150, 200, 250], "confirm_bars": [2, 3, 4],
        "reentry_hold": [10, 15, 20], "exit_grace_bars": [2, 3, 4]}
DEFAULTS = {"ma_long_len": 200, "confirm_bars": 3, "reentry_hold": 15,
            "exit_grace_bars": 3}
BAR_PARAMS = ("track_period", "ma_med_len", "ma_long_len", "ma_slope",
              "track_slope_bars", "confirm_bars", "reentry_hold",
              "exit_grace_bars", "vol_lookback", "rsi_len", "donchian_period")


def sortino(r, ppy):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(ppy)
    return float(r.mean() * ppy / d) if d > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def cagr(r, ppy):
    return float((float(np.prod(1.0 + r)) ** (ppy / len(r)) - 1.0) * 100.0)


def scaled(kw, k):
    cfg0 = engine.make_config("lean")
    out = {}
    for name in BAR_PARAMS:
        v = getattr(cfg0, name, None)
        if isinstance(v, (int, float)) and v > 0:
            out[name] = max(1, int(round(v * k)))
    for name, v in kw.items():
        out[name] = max(1, int(round(v * k))) if name in BAR_PARAMS else v
    return out


def pos_of(raw, k, ppy, **kw):
    cfg = engine.make_config("lean", trading_days=ppy, **scaled(kw, k))
    df = trim_warmup(engine.strategy_module("lean")
                     .run_strategy(raw, btc_daily=None, config=cfg).df)
    return pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)


def build(path, k, label):
    raw = pd.read_parquet(path)
    ppy = 365 * k
    ret_all = raw["close"].pct_change().fillna(0.0)
    keys = list(GRID)
    combos = list(itertools.product(*(GRID[key] for key in keys)))

    # today: every rule on, defaults everywhere
    p_today = pos_of(raw, k, ppy, **DEFAULTS)
    # after deleting the three dead knobs -- everything else identical
    p_clean = pos_of(raw, k, ppy, **{**DEFAULTS, **DEAD})
    # majority vote of the 81 neighbours, on the cleaned strategy
    P = {c: pos_of(raw, k, ppy, **{**dict(zip(keys, c)), **DEAD}) for c in combos}

    common = p_today.index.intersection(p_clean.index)
    for sr in P.values():
        common = common.intersection(sr.index)
    win = common[(common >= WIN_FROM) & (common <= WIN_TO)]
    ens = np.mean([P[c].reindex(win).to_numpy() for c in combos], axis=0)

    series = {
        "danes": p_today.reindex(win).to_numpy(),
        "brez mrtvih gumbov": p_clean.reindex(win).to_numpy(),
        "glasovanje: vecina": (ens > 0.5 - 1e-9).astype(float),
    }
    ret = ret_all.reindex(win)
    out = {"label": label, "bars_per_day": k, "n_bars": len(win),
           "window": [str(win[0].date()), str(win[-1].date())],
           "index": [str(d.date()) for d in win], "curves": {}, "metrics": {},
           "benchmark": None}

    bh = np.cumprod(1.0 + ret.to_numpy(float))
    out["benchmark"] = {"equity": [round(float(v), 4) for v in bh],
                        "maxdd": round(maxdd(ret.to_numpy(float)), 1),
                        "cagr": round(cagr(ret.to_numpy(float), ppy), 1)}

    for name, pos_arr in series.items():
        pos = pd.Series(pos_arr, index=win)
        r = net_returns(pos, ret, FEE).to_numpy(float)
        eq = np.cumprod(1.0 + r)
        out["curves"][name] = [round(float(v), 4) for v in eq]
        out["metrics"][name] = {
            "sortino": round(sortino(r, ppy), 3), "maxdd": round(maxdd(r), 1),
            "cagr": round(cagr(r, ppy), 1),
            "final": round(float(eq[-1]), 3),
            "expo": round(float(pos.mean() * 100), 1),
            "turnover": round(float(turnover(pos).sum()), 1),
            "trades": int((np.diff(pos_arr, prepend=pos_arr[0]) > 0).sum())}

    a = out["curves"]["danes"]
    b = out["curves"]["brez mrtvih gumbov"]
    out["deletion_is_neutral"] = bool(max(abs(x - y) for x, y in zip(a, b)) < 1e-9)
    out["max_abs_curve_gap"] = float(max(abs(x - y) for x, y in zip(a, b)))
    return out


def main():
    res = {"fee_per_side_pct": FEE, "clocks": []}
    for path, k, label in ((D1, 1, "dnevni bari"), (H4, 6, "4-urni bari")):
        r = build(path, k, label)
        res["clocks"].append(r)
        print(f"\n{'='*80}\n{label.upper()}  {r['window'][0]} → {r['window'][1]}  "
              f"({r['n_bars']} barov)")
        print(f"{'razlicica':24} {'Sortino':>8} {'MaxDD':>9} {'CAGR':>7} "
              f"{'konec':>7} {'poslov':>7}")
        for n, m in r["metrics"].items():
            print(f"  {n:22} {m['sortino']:8.3f} {m['maxdd']:8.1f} % {m['cagr']:6.1f} % "
                  f"{m['final']:7.2f} {m['trades']:7d}")
        print(f"  {'kupi in drzi':22} {'':8} {r['benchmark']['maxdd']:8.1f} % "
              f"{r['benchmark']['cagr']:6.1f} %")
        print(f"  brisanje mrtvih gumbov je nevtralno: {r['deletion_is_neutral']} "
              f"(najvecja razlika krivulje {r['max_abs_curve_gap']:.2e})")

    d1, h4 = res["clocks"]
    print(f"\n{'='*80}\nKOLIKO DNEVNI BARI POLEPSAJO PADEC")
    for n in d1["metrics"]:
        a, b = d1["metrics"][n]["maxdd"], h4["metrics"][n]["maxdd"]
        print(f"  {n:22} dnevno {a:6.1f} %  ·  4-urno {b:6.1f} %  ·  "
              f"skrito {a - b:+.1f} o. t.")
    res["dd_understated"] = {n: round(d1["metrics"][n]["maxdd"]
                                      - h4["metrics"][n]["maxdd"], 1)
                             for n in d1["metrics"]}
    OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON -> {OUT}  ({OUT.stat().st_size/1024:.0f} kB)")
    return res


if __name__ == "__main__":
    main()
