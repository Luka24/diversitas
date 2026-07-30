"""Are the three "dead" rules dead everywhere, or only at today's settings?

The zero-effect result was measured at one point in parameter space. That is not
enough to justify deleting code: a rule can be dormant at the shipped defaults and
active one step away. It matters here for a concrete reason -- the recommendation
elsewhere is to average over 81 neighbouring settings, so a rule that wakes up in
any of them is not removable without changing the ensemble.

Two things could wake each rule:

  vol_shock       needs below_tl AND below_count < exit_grace_bars. A LONGER grace
                  period widens that window, so a large exit_grace_bars is where it
                  would get its chance.
  above_ma_med    blocks 65 days that confirm_bars and reentry_hold currently
                  absorb. Shortening either should let those days become trades.
  dist_entry_ok   is above_tl whenever min_dist_entry_pct is 0. Raising it above 0
                  makes it a real, separate condition -- so the question is not
                  whether it is dead but whether waking it helps.

Tested over the 81-member ensemble grid plus one-at-a-time sweeps of everything
that could plausibly matter. Comparison is on the POSITION SERIES, not on metrics:
identical metrics could in principle come from different paths, identical positions
cannot.

Output: testing/data/dead_rules_BTC.json
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

from shared.costs import net_returns
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

FEE, PPY = 0.30, 365
SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
OUT = ROOT / "testing" / "data" / "dead_rules_BTC.json"
BULL = ("above_tl", "above_ma_med", "track_rising_window", "dist_entry_ok",
        "regime_ok", "btc_filter_ok", "donchian_ok")

# The three candidates, and how each is switched off.
RULES = {
    "vol_shock":     ((), {"vol_shock_mul": 999.0}),
    "above_ma_med":  (("above_ma_med",), {}),
    "dist_entry_ok": (("dist_entry_ok",), {}),
}

# One-at-a-time sweeps. Each entry is the parameter and the values to try; the
# ranges deliberately reach well past anything anyone would ship, because the
# question is whether a rule is dormant by construction or only by luck.
SWEEPS = {
    "exit_grace_bars":  [1, 2, 3, 4, 5, 6, 8, 10, 14],
    "confirm_bars":     [1, 2, 3, 4, 5, 6, 7],
    "reentry_hold":     [0, 3, 6, 9, 12, 15, 20, 25, 30],
    "track_period":     [45, 55, 65, 75, 85, 95, 105, 115],
    "track_buf_pct":    [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0],
    "ma_long_len":      [100, 150, 200, 250, 300],
    "ma_med_len":       [20, 30, 40, 50, 60, 80, 100],
    "vol_shock_mul":    [0.8, 1.0, 1.2, 1.5, 2.0, 3.0],
    "vol_lookback":     [10, 14, 20, 30, 40],
    "min_dist_entry_pct": [0.0, 0.5, 1.0, 2.0, 3.0, 5.0],
}
GRID = {"ma_long_len": [150, 200, 250], "confirm_bars": [2, 3, 4],
        "reentry_hold": [10, 15, 20], "exit_grace_bars": [2, 3, 4]}


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def run(raw, force=(), **kw):
    smod = engine.strategy_module("lean")
    cfg = engine.make_config("lean", **kw)
    df = smod.compute_features(raw, None, cfg)
    if force:
        for c in force:
            df[c] = True
        bull = pd.Series(True, index=df.index)
        for t in BULL:
            bull &= df[t]
        df["bull_condition"] = bull.fillna(False)
    df = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)
    r = net_returns(pos, raw["close"].pct_change().fillna(0.0), FEE)
    return pos, r.to_numpy(float)


def probe(raw, rule, base_kw):
    """Does switching `rule` off change the held position at this setting?"""
    force, over = RULES[rule]
    p0, r0 = run(raw, **base_kw)
    p1, r1 = run(raw, force=force, **{**base_kw, **over})
    idx = p0.index.intersection(p1.index)
    a, b = p0.reindex(idx).to_numpy(), p1.reindex(idx).to_numpy()
    nd = int((np.abs(a - b) > 1e-9).sum())
    if nd == 0:
        return {"days": 0, "d_sortino": 0.0, "d_maxdd": 0.0}
    m = np.isin(p0.index, idx)
    n = np.isin(p1.index, idx)
    return {"days": nd,
            "d_sortino": round(sortino(r1[n]) - sortino(r0[m]), 3),
            "d_maxdd": round(maxdd(r1[n]) - maxdd(r0[m]), 1)}


def main():
    raw = pd.read_parquet(SRC)
    out = {"rules": list(RULES), "sweeps": {}, "grid": {}, "settings_tested": 0}

    print("A. PRELETI PO EN PARAMETER NAENKRAT")
    print("   'dni' = na koliko dni bi imeli drugačno pozicijo, če pravilo izklopimo\n")
    hdr = f"{'parameter':20} {'vrednost':>9} " + "".join(f"{r:>26}" for r in RULES)
    print(hdr)
    n_set = 0
    for prm, vals in SWEEPS.items():
        out["sweeps"][prm] = []
        for v in vals:
            kw = {prm: v}
            row = {"value": v}
            cells = ""
            for rule in RULES:
                # skip probing a rule through its own knob: switching it off and
                # simultaneously retuning it is not a robustness question
                if prm in ("vol_shock_mul", "vol_lookback") and rule == "vol_shock":
                    row[rule] = None; cells += f"{'—':>26}"; continue
                if prm == "min_dist_entry_pct" and rule == "dist_entry_ok":
                    row[rule] = None; cells += f"{'—':>26}"; continue
                if prm == "ma_med_len" and rule == "above_ma_med":
                    row[rule] = None; cells += f"{'—':>26}"; continue
                res = probe(raw, rule, kw)
                row[rule] = res
                if res["days"] == 0:
                    cells += f"{'0 dni':>26}"
                else:
                    cells += (f"{res['days']:>5} dni "
                              f"ΔS{res['d_sortino']:+.2f} "
                              f"ΔDD{res['d_maxdd']:+.1f}".rjust(26))
            out["sweeps"][prm].append(row)
            n_set += 1
            star = " <- privzeto" if v == getattr(engine.make_config("lean"), prm) else ""
            print(f"{prm:20} {v:>9} {cells}{star}")
        print()

    print("B. VSEH 81 ČLANOV ANSAMBLA")
    keys = list(GRID)
    hits = {r: [] for r in RULES}
    for combo in itertools.product(*(GRID[k] for k in keys)):
        kw = dict(zip(keys, combo))
        for rule in RULES:
            res = probe(raw, rule, kw)
            if res["days"]:
                hits[rule].append({"config": kw, **res})
        n_set += 1
    out["grid"] = {r: hits[r] for r in RULES}
    for rule in RULES:
        h = hits[rule]
        print(f"   {rule:15} oživi pri {len(h)} od 81 članov"
              + (f" · npr. {h[0]['config']} ({h[0]['days']} dni, "
                 f"ΔSortino {h[0]['d_sortino']:+.2f})" if h else ""))

    out["settings_tested"] = n_set
    print(f"\nC. POVZETEK — {n_set} nastavitev preizkušenih")
    summ = {}
    for rule in RULES:
        alive, better, worse = [], 0, 0
        for prm, rows in out["sweeps"].items():
            for row in rows:
                res = row.get(rule)
                if res and res["days"]:
                    alive.append((prm, row["value"], res))
                    if res["d_sortino"] > 0:
                        better += 1
                    elif res["d_sortino"] < 0:
                        worse += 1
        for h in hits[rule]:
            alive.append(("ansambel", str(h["config"]), h))
            if h["d_sortino"] > 0:
                better += 1
            elif h["d_sortino"] < 0:
                worse += 1
        summ[rule] = {"n_alive": len(alive), "removal_better": better,
                      "removal_worse": worse,
                      "examples": [{"kje": f"{a[0]}={a[1]}", **a[2]} for a in alive[:6]]}
        verdict = ("MRTVO PRI VSEH PREIZKUŠENIH NASTAVITVAH" if not alive else
                   f"oživi pri {len(alive)} nastavitvah · odstranitev boljša {better}×, "
                   f"slabša {worse}×")
        print(f"   {rule:15} {verdict}")
    out["summary"] = summ

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
