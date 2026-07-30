"""Does vol_shock earn its two parameters once we stop standing on one point?

It wakes in 45 of the 81 ensemble members, so deleting it changes the ensemble.
That was the reason to keep it. But "changes the ensemble" and "changes the
ensemble by an amount worth two tunable parameters" are different claims, and only
the second one justifies the complexity. This measures the second.

The comparison that decides it: the majority vote of all 81 neighbours, computed
once with vol_shock live and once with it switched off. Whatever the 45 members do
individually, the vote is what we would actually trade.

Also assembles the joint parameter verdict from both reports — sweep shape from
the parameter page, removability from the conditions page — into one table, so the
recommendation is derived rather than asserted.

Output: testing/data/merge_BTC.json
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

FEE, PPY = 0.30, 365
WIN_FROM, WIN_TO = "2021-07-01", "2026-06-30"
NBOOT, BLOCK, SEED = 2000, 20, 20260802
SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
PAR = json.loads((ROOT / "testing" / "data" / "parametri_BTC.json").read_text(encoding="utf-8"))
DR = json.loads((ROOT / "testing" / "data" / "dead_rules_BTC.json").read_text(encoding="utf-8"))
OUT = ROOT / "testing" / "data" / "merge_BTC.json"

BULL = ("above_tl", "above_ma_med", "track_rising_window", "dist_entry_ok",
        "regime_ok", "btc_filter_ok", "donchian_ok")
GRID = {"ma_long_len": [150, 200, 250], "confirm_bars": [2, 3, 4],
        "reentry_hold": [10, 15, 20], "exit_grace_bars": [2, 3, 4]}
DEFAULTS = {"ma_long_len": 200, "confirm_bars": 3, "reentry_hold": 15,
            "exit_grace_bars": 3}
# The two removals that survived the robustness probe.
DROP = ("dist_entry_ok", "above_ma_med")


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
    idx = _blocks(rng, len(a), NBOOT, BLOCK)
    d = np.array([fn(a[i]) - fn(b[i]) for i in idx])
    d = d[np.isfinite(d)]
    return round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)


def member(raw, vol_shock: bool, **kw):
    over = dict(kw)
    if not vol_shock:
        over["vol_shock_mul"] = 999.0
    cfg = engine.make_config("lean", **over)
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    for c in DROP:
        df[c] = True
    bull = pd.Series(True, index=df.index)
    for t in BULL:
        bull &= df[t]
    df["bull_condition"] = bull.fillna(False)
    df = trim_warmup(smod.run_state_machine(df, cfg))
    return pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)


def main():
    raw = pd.read_parquet(SRC)
    ret_all = raw["close"].pct_change().fillna(0.0)
    rng = np.random.default_rng(SEED)
    keys = list(GRID)
    combos = list(itertools.product(*(GRID[k] for k in keys)))

    P = {}
    for vs in (True, False):
        P[vs] = {c: member(raw, vs, **dict(zip(keys, c))) for c in combos}
    common = None
    for d in P.values():
        for sr in d.values():
            common = sr.index if common is None else common.intersection(sr.index)
    win = common[(common >= WIN_FROM) & (common <= WIN_TO)]
    ret = ret_all.reindex(win)

    out = {"window": [str(win[0].date()), str(win[-1].date())], "n": len(win),
           "members": len(combos), "fee_per_side_pct": FEE, "variants": {}}

    def score(pos_arr, name):
        pos = pd.Series(pos_arr, index=win)
        r = net_returns(pos, ret, FEE).to_numpy(float)
        out["variants"][name] = {
            "sortino": round(sortino(r), 3), "sharpe": round(sharpe(r), 3),
            "cagr": round(cagr(r), 1), "maxdd": round(maxdd(r), 1),
            "final": round(float(np.cumprod(1.0 + r)[-1]), 3),
            "expo": round(float(pos.mean() * 100), 1),
            "turnover": round(float(turnover(pos).sum()), 1),
            "trades": int((np.diff(pos_arr, prepend=pos_arr[0]) > 0).sum())}
        return r

    dflt = tuple(DEFAULTS[k] for k in keys)
    res = {}
    for vs, tag in ((True, "z vol_shockom"), (False, "brez vol_shocka")):
        ens = np.mean([P[vs][c].reindex(win).to_numpy() for c in combos], axis=0)
        vote = (ens > 0.5 - 1e-9).astype(float)
        res[(vs, "vote")] = score(vote, f"glasovanje, {tag}")
        res[(vs, "point")] = score(P[vs][dflt].reindex(win).to_numpy(),
                                   f"ena tocka, {tag}")

    print(f"{out['window'][0]} → {out['window'][1]} ({out['n']} dni) · "
          f"{len(combos)} članov · fee {FEE} %/stran\n")
    print(f"{'različica':30} {'Sortino':>8} {'Sharpe':>8} {'CAGR':>8} {'MaxDD':>9} "
          f"{'konec':>7} {'poslov':>7}")
    for n, m in out["variants"].items():
        print(f"  {n:28} {m['sortino']:8.3f} {m['sharpe']:8.3f} {m['cagr']:7.1f} % "
              f"{m['maxdd']:8.1f} % {m['final']:7.2f} {m['trades']:7d}")

    for tag, a, b in (("glasovanje", res[(True, "vote")], res[(False, "vote")]),
                      ("ena tocka", res[(True, "point")], res[(False, "point")])):
        same = bool(np.allclose(a, b, atol=1e-12))
        lo, hi = paired_ci(b, a, sortino, rng)
        lo2, hi2 = paired_ci(b, a, maxdd, rng)
        ka, kb = (f"{'glasovanje' if tag=='glasovanje' else 'ena tocka'}, z vol_shockom",
                  f"{'glasovanje' if tag=='glasovanje' else 'ena tocka'}, brez vol_shocka")
        out[f"drop_vol_shock_{tag.replace(' ','_')}"] = {
            "identical": same,
            "days_different": int((np.abs(np.asarray(a) - np.asarray(b)) > 1e-12).sum()),
            "d_sortino": round(out["variants"][kb]["sortino"]
                               - out["variants"][ka]["sortino"], 3),
            "ci_sortino": [lo, hi],
            "d_maxdd": round(out["variants"][kb]["maxdd"]
                             - out["variants"][ka]["maxdd"], 1),
            "ci_maxdd": [lo2, hi2]}
        d = out[f"drop_vol_shock_{tag.replace(' ','_')}"]
        print(f"\nizklop vol_shocka pri »{tag}«: ΔSortino {d['d_sortino']:+.3f} "
              f"razpon [{lo:+.2f}, {hi:+.2f}] · ΔMaxDD {d['d_maxdd']:+.1f} o. t. "
              f"razpon [{lo2:+.1f}, {hi2:+.1f}]"
              + ("  IDENTIČNO" if same else ""))

    # ── joint parameter verdict, derived from both reports ──────────────────
    KIND = {p["name"]: p for p in PAR["params"]}
    REMOVE = {"min_dist_entry_pct": "dist_entry_ok", "ma_med_len": "above_ma_med"}
    ENS = set(GRID)
    rows = []
    for name, p in KIND.items():
        if name in REMOVE:
            act = "odstraniti"
            why = f"pravilo <code>{REMOVE[name]}</code> je mrtvo pri vseh nastavitvah"
        elif name in ENS:
            act = "prepustiti glasovanju"
            why = "ostra konica; vrednost naj določi večina 81 sosedov"
        elif p["kind"] == "plato":
            act = "pustiti pri miru"
            why = f"plato, razpon {p['rng']:.2f}; natančna vrednost ni pomembna"
        elif p["kind"] == "inerten":
            act = "zakleniti"
            why = f"inerten, razpon {p['rng']:.2f}; ni vreden nastavljanja"
        else:
            act = "pustiti pri miru"
            why = f"{p['kind']}, razpon {p['rng']:.2f}"
        rows.append({"name": name, "default": p["default"], "kind": p["kind"],
                     "range": p["rng"], "best": p["best_value"],
                     "action": act, "why": why,
                     "wakes_rule": name in ("vol_shock_mul", "vol_lookback")})
    out["parameter_plan"] = rows
    print(f"\n{'parameter':20} {'privzeto':>9} {'oblika':>13} {'razpon':>7}   ukrep")
    for r in rows:
        print(f"{r['name']:20} {str(r['default']):>9} {r['kind']:>13} "
              f"{r['range']:7.3f}   {r['action']}")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
