"""Which exit? Five cells with the entry held fixed.

Pre-registered in `testing/nacrt_izstop.md`, committed before this ran.

Almost everything in this project has been tested on the entry side. The
literature points the other way — Turtle System 1 enters on a 20-day high and
exits on a 10-day low, System 2 enters on 55 and exits on 20, so the exit
lookback is always faster than the entry — and attributes more of the payoff to
asymmetric exits than to entry timing.

    E0    trackline75 - 3 %, 3 grace bars     today, the control
    E0h   trackline75 - 3 %, 0 grace bars     isolates the grace, not a candidate
    E10   close < 10-day low, no grace        Turtle System 1
    E20   close < 20-day low, no grace        Turtle System 2
    E55   close < 55-day low, no grace

Entry is today's rule in every cell, so any difference is attributable to the
exit. The blow-off exit is untouched throughout. Periods 10, 20 and 55 are
existing conventions; nothing is swept.

ETH is computed and reported but NOT counted as confirmation — the two
pre-registered uses of it are spent.

Output: testing/data/exit_variants.json
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

from shared import indicators as ind
from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from testing.scripts import engine
from testing.scripts.two_tracklines import sortino, maxdd, mcs, FEE, PPY, SUBPERIODS

np.seterr(all="ignore")

SRC = ROOT / "testing" / "data" / "sources"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
OUT = ROOT / "testing" / "data" / "exit_variants.json"
S_BLOCKS, NBOOT, BLOCK, N_SHIFT = 12, 5000, 20, 1000
rng = np.random.default_rng(20260812)

CELLS = {
    "E0  danes":      ("tl", 3),
    "E0h brez milost": ("tl", 0),
    "E10 Turtle S1":  ("low", 10),
    "E20 Turtle S2":  ("low", 20),
    "E55":            ("low", 55),
}


def build(raw, kind, arg):
    """Only the exit trigger varies; entry and blow-off are today's."""
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    if kind == "low":
        # .shift(1) is required, not cosmetic. lowest(low, N) includes TODAY's
        # low, and the close can never be below the day's own low, so the
        # unshifted condition is false on every bar of the history — all three
        # periods then produce bit-identical results and 94 % exposure, which is
        # what gave the bug away. A Turtle exit means a new low against the
        # PREVIOUS N bars.
        dn = ind.lowest(raw["low"], arg).shift(1).reindex(df.index)
        # Breaking a rolling low is a definite event, so it fires at once. The
        # grace counter is what E0h exists to isolate.
        df["below_tl"] = (df["close"] < dn).fillna(False)
        grace = 1
    else:
        grace = max(arg, 1)
    df["trend_break"] = df["below_tl"]
    cfg2 = engine.make_config("lean", exit_grace_bars=grace)
    st = trim_warmup(smod.run_state_machine(df, cfg2))
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos, df["below_tl"].reindex(st.index)


def metrics(pos, ret):
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1 + r)
    p = pos.to_numpy()
    return {"sortino": round(sortino(r), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
            "exposure": round(float(p.mean() * 100), 1),
            "trades": int((np.diff(p, prepend=p[0]) > 0).sum()),
            "turnover": round(float(turnover(pos).sum()), 1)}


def paired_ci(a, b):
    n = len(a)
    k = int(np.ceil(n / BLOCK))
    d = []
    for lo in range(0, NBOOT, 500):
        m = min(500, NBOOT - lo)
        st = rng.integers(0, n, size=(m, k))
        idx = (st[:, :, None] + np.arange(BLOCK)[None, None, :]
               ).reshape(m, k * BLOCK)[:, :n] % n
        d.append(np.array([sortino(a[i]) - sortino(b[i]) for i in idx]))
    d = np.concatenate(d)
    d = d[np.isfinite(d)]
    return (round(float(sortino(a) - sortino(b)), 3),
            round(float(np.percentile(d, 2.5)), 3),
            round(float(np.percentile(d, 97.5)), 3))


def main() -> int:
    out = {"fee_per_side_pct": FEE, "cells": list(CELLS)}
    names = list(CELLS)

    for sym, f in (("BTC", "BTC_binance_warmup.parquet"), ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(SRC / f)
        ret = raw["close"].pct_change().fillna(0.0)
        pos, trig = {}, {}
        for nm, (kind, arg) in CELLS.items():
            pos[nm], trig[nm] = build(raw, kind, arg)
        idx = pos[names[0]].index
        print(f"\n{'='*100}\n{sym} · {len(idx)} dni · {idx[0].date()} → {idx[-1].date()}\n{'='*100}")

        if sym == "BTC":
            ref = pd.read_parquet(REF)["position"]
            ok = (pos["E0  danes"].index.equals(ref.index)
                  and np.allclose(pos["E0  danes"].to_numpy(), ref.to_numpy(), atol=1e-12))
            print(f"  KONTROLA: E0 = zamrznjena referenca? {'DA' if ok else 'NE'}")
            if not ok:
                print("  Harness se moti na kontroli. USTAVLJAM.")
                return 2
            out["control_ok"] = True

        print(f"\n  {'celica':<18}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
              f"{'izpost':>8}{'posl':>6}{'obrat':>7}    I     II    III    IV")
        res = {}
        for nm in names:
            m = metrics(pos[nm], ret)
            sub = {}
            for s, a, b in SUBPERIODS:
                w = idx[(idx >= a) & (idx <= b)]
                sub[s] = (round(sortino(net_returns(pos[nm].reindex(w), ret, FEE)
                                        .to_numpy(float)), 2) if len(w) > 60 else None)
            m["sub"] = sub
            res[nm] = m
            ss = "  ".join(f"{v:5.2f}" if v is not None else "    —" for v in sub.values())
            print(f"  {nm:<18}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%{m['maxdd']:>7.1f}%"
                  f"{m['final']:>6.2f}x{m['exposure']:>7.1f}%{m['trades']:>6d}"
                  f"{m['turnover']:>7.1f}  {ss}")

        base = net_returns(pos["E0  danes"], ret, FEE).to_numpy(float)
        print(f"\n  ΔSortino proti E0 (sparjeni blokovni bootstrap)")
        boots = {}
        for nm in names[1:]:
            d, lo, hi = paired_ci(net_returns(pos[nm], ret, FEE).to_numpy(float), base)
            boots[nm] = {"delta": d, "ci": [lo, hi],
                         "excl0": bool(lo > 0 or hi < 0)}
            print(f"    {nm:<18}{d:+7.3f}   [{lo:+.3f}, {hi:+.3f}]   "
                  f"{'IZKLJUČUJE ničlo' if lo > 0 or hi < 0 else 'objame ničlo'}")

        R = np.vstack([net_returns(pos[n], ret, FEE).to_numpy(float) for n in names])
        mcs_res = {}
        for tag, L in (("povprecen donos", -R),
                       ("s kaznijo za padce", -R + 2.0 * np.minimum(R, 0.0) ** 2)):
            keep, elim = mcs(L, names)
            mcs_res[tag] = {"kept": keep, "eliminated": elim}
            print(f"\n  MCS ({tag}): {len(keep)}/5 → {', '.join(keep)}")
            if elim:
                print(f"      izločene: {', '.join(f'{n} (p={p})' for n, p in elim)}")

        print(f"\n  UGNEZDENI WALK-FORWARD")
        wf = {}
        for tr, te in ((3, 1), (2, 1)):
            picks, segs = [], []
            start = idx[0]
            while True:
                tb = start + pd.DateOffset(years=tr)
                eb = tb + pd.DateOffset(years=te)
                if eb > idx[-1]:
                    break
                w = idx[(idx >= start) & (idx <= tb)]
                sc = {n: sortino(net_returns(pos[n].reindex(w), ret, FEE).to_numpy(float))
                      for n in names}
                pk = max(sc, key=lambda k: sc[k] if np.isfinite(sc[k]) else -9e9)
                t = idx[(idx > tb) & (idx <= eb)]
                picks.append(pk.split()[0])
                segs.append(pos[pk].reindex(t))
                start = start + pd.DateOffset(years=te)
            if segs:
                a_seg = pd.concat([pos["E0  danes"].reindex(s.index) for s in segs])
                wf[f"{tr}y/{te}y"] = {"picks": picks,
                                      "refit": metrics(pd.concat(segs), ret)["sortino"],
                                      "E0": metrics(a_seg, ret)["sortino"]}
                w_ = wf[f"{tr}y/{te}y"]
                print(f"    {tr}y/{te}y  {picks}   E0 {w_['E0']:.3f}  refit {w_['refit']:.3f}")

        blocks = np.array_split(np.arange(R.shape[1]), S_BLOCKS)
        below = tot = 0
        picked = {n: 0 for n in names}
        for sel in itertools.combinations(range(S_BLOCKS), S_BLOCKS // 2):
            i_is = np.concatenate([blocks[i] for i in sel])
            i_oos = np.concatenate([blocks[i] for i in range(S_BLOCKS) if i not in sel])
            s_is = np.array([sortino(m[i_is]) for m in R])
            s_oos = np.array([sortino(m[i_oos]) for m in R])
            if not (np.isfinite(s_is).all() and np.isfinite(s_oos).all()):
                continue
            k = int(np.argmax(s_is))
            picked[names[k]] += 1
            tot += 1
            below += int((s_oos < s_oos[k]).sum() / (len(names) - 1) < 0.5)
        print(f"\n  PBO (CSCV, {tot} poti): {below/tot:.3f}   "
              + "  ".join(f"{n.split()[0]}:{v}" for n, v in picked.items() if v))

        best = max(res, key=lambda k: res[k]["sortino"])
        cfg = engine.make_config("lean")
        smod = engine.strategy_module("lean")
        df0 = smod.compute_features(raw, None, cfg)
        g = trig[best].reindex(df0.index).fillna(False).to_numpy()
        grace = 1 if CELLS[best][0] == "low" else max(CELLS[best][1], 1)
        cfg2 = engine.make_config("lean", exit_grace_bars=grace)
        sims = []
        for _ in range(N_SHIFT):
            f2 = df0.copy()
            f2["below_tl"] = pd.Series(np.roll(g, int(rng.integers(60, len(g) - 60))),
                                       index=df0.index)
            st = trim_warmup(smod.run_state_machine(f2, cfg2))
            p = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
            sims.append(sortino(net_returns(p, ret, FEE).to_numpy(float)))
        sims = np.array([x for x in sims if np.isfinite(x)])
        pct = float((sims < res[best]["sortino"]).mean() * 100)
        print(f"\n  NAKLJUČNI ZAMIK vodilne «{best}»: pravi {res[best]['sortino']:.3f}   "
              f"zamaknjeni povpr. {sims.mean():.3f}   pravi na {pct:.1f}. percentilu")

        out[sym] = {"cells": res, "bootstrap": boots, "mcs": mcs_res,
                    "walk_forward": wf, "pbo": round(below / tot, 3),
                    "pbo_picked": picked,
                    "shift": {"cell": best, "real": res[best]["sortino"],
                              "mean": round(float(sims.mean()), 3),
                              "percentile": round(pct, 1)},
                    "counts_as_evidence": sym == "BTC"}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
