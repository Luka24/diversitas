"""Re-run the binary variants on 4-hour bars, to see whether their ranking is real.

On daily bars the choice between the variants rests on 8 to 9 trades. Nothing can
be ranked on 8 trades: majority vote scores 0.878 and the plateau-centre point
scores 0.983, and there is no way to tell whether that 0.1 is a preference or a
coin flip.

Four-hour bars are the same market over the same window, read on a finer clock.
That is not an independent sample and this script never claims it is. What it buys
is observations: roughly six times as many bars and, with them, enough trades for
the ranking to mean something. The question it answers is narrow and useful:

    do the variants keep their order when the clock changes?

If they do, the daily ordering is a property of the strategy. If they scramble,
the daily ordering was noise and the choice between variants should be made on
principle rather than on score.

EVERY LOOKBACK IS MULTIPLIED BY SIX. Without that the test compares a different
strategy rather than a different clock, which is the standard failure mode of
timeframe robustness checks. The scale factor is derived from the data, not typed
in, so it cannot silently drift.
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
NBOOT, BLOCK, SEED = 2000, 20, 20260731
D1 = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
H4 = ROOT / "testing" / "data" / "sources" / "BTC_binance_4h.parquet"
OUT = ROOT / "testing" / "data" / "intraday_BTC.json"

SIMPLE = {"vol_shock_mul": 999.0, "blowoff_dist_pct": 9999.0}

# Every parameter measured in bars. Anything not here is a ratio or a threshold
# and must NOT be scaled.
BAR_PARAMS = ("track_period", "ma_med_len", "ma_long_len", "ma_slope",
              "track_slope_bars", "confirm_bars", "reentry_hold",
              "exit_grace_bars", "vol_lookback", "rsi_len", "donchian_period")

GRID = {"ma_long_len": [150, 200, 250], "confirm_bars": [2, 3, 4],
        "reentry_hold": [10, 15, 20], "exit_grace_bars": [2, 3, 4]}
DEFAULTS = {"ma_long_len": 200, "confirm_bars": 3, "reentry_hold": 15,
            "exit_grace_bars": 3}
PLATEAU = {"ma_long_len": 225, "confirm_bars": 1, "reentry_hold": 15,
           "exit_grace_bars": 4}


def sortino(r, ppy):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(ppy)
    return float(r.mean() * ppy / d) if d > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def _blocks(rng, n, B, L):
    nb = int(np.ceil(n / L))
    st = rng.integers(0, n, size=(B, nb))
    return (st[:, :, None] + np.arange(L)[None, None, :]).reshape(B, nb * L)[:, :n] % n


def paired_ci(a, b, fn, rng):
    idx = _blocks(rng, len(a), NBOOT, BLOCK)
    d = np.array([fn(a[i]) - fn(b[i]) for i in idx])
    d = d[np.isfinite(d)]
    return round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)


def scaled(base_kw: dict, k: int) -> dict:
    """Multiply every bar-denominated parameter by k, keep ratios untouched."""
    cfg0 = engine.make_config("lean")
    kw = {}
    for name in BAR_PARAMS:
        v = getattr(cfg0, name, None)
        if isinstance(v, (int, float)) and v > 0:
            kw[name] = max(1, int(round(v * k)))
    for name, v in base_kw.items():
        kw[name] = max(1, int(round(v * k))) if name in BAR_PARAMS else v
    return kw


def positions(raw, k, ppy, **kw):
    cfg = engine.make_config("lean", trading_days=ppy, **{**SIMPLE, **scaled(kw, k)})
    df = trim_warmup(engine.strategy_module("lean")
                     .run_strategy(raw, btc_daily=None, config=cfg).df)
    return pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)


def run_clock(path: Path, k: int, label: str, rng) -> dict:
    raw = pd.read_parquet(path)
    ppy = 365 * k
    ret_all = raw["close"].pct_change().fillna(0.0)
    keys = list(GRID)
    combos = list(itertools.product(*(GRID[key] for key in keys)))

    P = {c: positions(raw, k, ppy, **dict(zip(keys, c))) for c in combos}
    common = None
    for sr in P.values():
        common = sr.index if common is None else common.intersection(sr.index)
    win = common[(common >= WIN_FROM) & (common <= WIN_TO)]
    P = {c: sr.reindex(win) for c, sr in P.items()}
    ret = ret_all.reindex(win)

    ens = np.mean([P[c].to_numpy() for c in combos], axis=0)
    dflt = tuple(DEFAULTS[key] for key in keys)
    plat = positions(raw, k, ppy, **PLATEAU).reindex(win).to_numpy()

    def score(pos_arr):
        pos = pd.Series(pos_arr, index=win)
        r = net_returns(pos, ret, FEE).to_numpy(float)
        n_tr = int((np.diff(pos_arr, prepend=pos_arr[0]) > 0).sum())
        return {"sortino": round(sortino(r, ppy), 3), "maxdd": round(maxdd(r), 1),
                "expo": round(float(pos.mean() * 100), 1),
                "turnover": round(float(turnover(pos).sum()), 1),
                "trades": n_tr}, r

    variants = {
        "ena tocka (privzetki)": P[dflt].to_numpy(),
        "ansambel, zvezna": ens,
        "glasovanje: vecina": (ens > 0.5 - 1e-9).astype(float),
        "glasovanje: dve tretjini": (ens > 2 / 3 - 1e-9).astype(float),
        "sredina ravnine": plat,
    }
    res, series = {}, {}
    for name, arr in variants.items():
        res[name], series[name] = score(arr)

    # is the gap between the two leading binary variants distinguishable?
    lo, hi = paired_ci(series["sredina ravnine"], series["glasovanje: vecina"],
                       lambda r: sortino(r, ppy), rng)
    return {"label": label, "bars_per_day": k, "periods_per_year": ppy,
            "window": [str(win[0].date()), str(win[-1].date())],
            "n_bars": len(win), "members": len(combos),
            "variants": res,
            "plateau_minus_majority": {
                "diff": round(res["sredina ravnine"]["sortino"]
                              - res["glasovanje: vecina"]["sortino"], 3),
                "ci": [lo, hi], "sig": bool(lo > 0 or hi < 0)}}


def main():
    rng = np.random.default_rng(SEED)
    out = {"fee_per_side_pct": FEE, "nboot": NBOOT, "seed": SEED, "clocks": []}
    for path, k, label in ((D1, 1, "dnevni bari"), (H4, 6, "4-urni bari")):
        r = run_clock(path, k, label, rng)
        out["clocks"].append(r)
        print(f"\n{'='*84}\n{label.upper()}  ·  {r['window'][0]} → {r['window'][1]}  ·  "
              f"{r['n_bars']} barov  ·  {r['periods_per_year']} obdobij/leto")
        print(f"{'razlicica':26} {'Sortino':>8} {'MaxDD':>8} {'izpost.':>8} "
              f"{'promet':>7} {'poslov':>7}")
        for n, v in r["variants"].items():
            print(f"  {n:24} {v['sortino']:8.3f} {v['maxdd']:7.1f} % {v['expo']:7.1f} % "
                  f"{v['turnover']:7.1f} {v['trades']:7d}")
        g = r["plateau_minus_majority"]
        print(f"  sredina ravnine - vecina: {g['diff']:+.3f}  CI [{g['ci'][0]:+.2f}, "
              f"{g['ci'][1]:+.2f}]  {'ZNACILNO' if g['sig'] else 'NI locljivo od suma'}")

    d1, h4 = out["clocks"]
    names = list(d1["variants"])
    r1 = sorted(names, key=lambda n: -d1["variants"][n]["sortino"])
    r6 = sorted(names, key=lambda n: -h4["variants"][n]["sortino"])
    from itertools import combinations
    conc = sum(1 for a, b in combinations(names, 2)
               if (r1.index(a) < r1.index(b)) == (r6.index(a) < r6.index(b)))
    tot = len(list(combinations(names, 2)))
    tau = 2 * conc / tot - 1
    out["ranking"] = {"daily": r1, "h4": r6, "concordant_pairs": conc,
                      "total_pairs": tot, "kendall_tau": round(tau, 2)}
    print(f"\n{'='*84}\nALI SE VRSTNI RED OHRANI?")
    for i, (a, b) in enumerate(zip(r1, r6), 1):
        print(f"  {i}. dnevno: {a:26}   4h: {b}")
    print(f"  skladnih parov {conc}/{tot} · Kendallov tau {tau:+.2f}")
    print(f"  poslov: dnevno {d1['variants']['glasovanje: vecina']['trades']} → "
          f"4h {h4['variants']['glasovanje: vecina']['trades']}")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
