"""Audit of the macro study: three things the first two passes got wrong or skipped.

1. HOW OFTEN DOES EACH SIGNAL FLIP?
   Never measured, and it matters more than how often a signal is ON. A filter
   that is risk-off 43 % of the time can be one long block or two hundred short
   ones, and at 0.30 % per side those are completely different strategies. MOVE
   collapsing to Sortino 0.36 was reported as if it said something about bond
   volatility. It may only say the flag chatters.

2. DOES MACRO ADD ANYTHING THE TRACKLINE DOES NOT ALREADY HAVE?
   The headline claim from the second pass is that the trackline exit reaches
   the door first. That was argued from two dates in March 2020. It deserves a
   test. An encompassing regression puts both predictors in together:

       forward return = a + b1 * (strategy is long) + b2 * (macro risk-off)

   If b2 is indistinguishable from zero once b1 is in, the macro signal carries
   nothing the strategy did not already know, on every day rather than on two.

3. PBO FOR THE SECOND PASS.
   macro_v2's own docstring says the PBO below spans both rounds. There is no
   PBO in macro_v2. That sentence was false; this computes it, over the first
   round's variants and the second's together, which is the honest denominator
   given the second set was chosen after seeing the first fail.

    python testing/scripts/macro_audit.py
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
import statsmodels.api as sm

from shared.costs import net_returns, turnover
from testing.scripts.macro_data import load as load_macro
from testing.scripts.macro_v2 import (FEE, PPY, START, build, maxdd, risk_off,
                                      sortino)

np.seterr(all="ignore")
S_BLOCKS, PURGE = 12, 21
OUT = ROOT / "testing" / "data" / "macro_audit.json"


def flips(flag: pd.Series) -> dict:
    f = flag.astype(bool).to_numpy()
    changes = int((np.diff(f.astype(int)) != 0).sum())
    on = f.sum()
    # length of each risk-off episode
    runs, cur = [], 0
    for v in f:
        if v:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return {"on_pct": round(float(f.mean() * 100), 1), "flips": changes,
            "episodes": len(runs),
            "median_len": int(np.median(runs)) if runs else 0,
            "longest": int(max(runs)) if runs else 0}


def encompass(ret: pd.Series, bull: pd.Series, flag: pd.Series, h: int):
    """Forward return on the strategy signal AND the macro flag together."""
    fwd = ret.shift(-1).rolling(h).sum().shift(-(h - 1))
    d = pd.concat([fwd.rename("y"), bull.astype(float).rename("bull"),
                   flag.astype(float).rename("macro")], axis=1).dropna()
    if len(d) < 100 or d["macro"].nunique() < 2 or d["bull"].nunique() < 2:
        return None
    m = sm.OLS(d["y"], sm.add_constant(d[["bull", "macro"]])).fit(
        cov_type="HAC", cov_kwds={"maxlags": h})
    return {"b_bull": float(m.params["bull"]) * 100,
            "t_bull": float(m.tvalues["bull"]),
            "b_macro": float(m.params["macro"]) * 100,
            "t_macro": float(m.tvalues["macro"]),
            "p_macro": float(m.pvalues["macro"])}


def pbo(mat: np.ndarray, names: list) -> tuple:
    blocks = np.array_split(np.arange(mat.shape[1]), S_BLOCKS)
    below = tot = 0
    picks = {c: 0 for c in names}
    for sel in itertools.combinations(range(S_BLOCKS), S_BLOCKS // 2):
        isx = np.concatenate([b[PURGE:len(b) - PURGE] if len(b) > 2 * PURGE else b
                              for b in (blocks[i] for i in sel)])
        oos = np.concatenate([blocks[i] for i in range(S_BLOCKS) if i not in sel])
        si = np.array([sortino(m[isx]) for m in mat])
        so = np.array([sortino(m[oos]) for m in mat])
        if not (np.isfinite(si).all() and np.isfinite(so).all()):
            continue
        k = int(np.argmax(si))
        picks[names[k]] += 1
        tot += 1
        below += int((so < so[k]).sum() / (len(names) - 1) < 0.5)
    return (round(below / tot, 3) if tot else float("nan"),
            {k: v for k, v in picks.items() if v})


def main() -> int:
    macro = load_macro()
    out = {}
    for sym, f in (("BTC", "BTC_binance_warmup.parquet"),
                   ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / f)
        ret = raw["close"].pct_change().fillna(0.0)
        flags = risk_off(macro, raw.index)
        base = build(raw, pd.Series(False, index=raw.index))
        idx = base.index
        base_r = net_returns(base, ret, FEE).to_numpy(float)
        ret_w, bull = ret.reindex(idx), (base > 0)

        print(f"\n{'=' * 94}\n{sym}   {idx[0].date()} -> {idx[-1].date()}\n{'=' * 94}")

        # 1 ─ chatter
        print("\n1. KAKO POGOSTO SE SIGNAL PREKLAPLJA  (to doslej nisem meril)")
        print(f"   {'signal':<16}{'vklop %':>9}{'preklopov':>11}{'epizod':>8}"
              f"{'mediana dni':>13}{'najdaljsa':>11}{'poslov':>8}")
        fl_stats = {}
        for name, fl in flags.items():
            st = flips(fl.reindex(idx))
            pos = build(raw, fl)
            st["trades"] = int(turnover(pos).sum() / 2)
            fl_stats[name] = st
            print(f"   {name:<16}{st['on_pct']:>8.1f}%{st['flips']:>11d}"
                  f"{st['episodes']:>8d}{st['median_len']:>13d}{st['longest']:>11d}"
                  f"{st['trades']:>8d}")
        b_tr = int(turnover(base).sum() / 2)
        print(f"   {'(izhodisce)':<16}{'':>9}{'':>11}{'':>8}{'':>13}{'':>11}{b_tr:>8d}")

        # 2 ─ encompassing
        print("\n2. ALI MAKRO POVE KAJ, CESAR TRACKLINE SE NE VE")
        print("   regresija:  donos naprej = a + b1*(smo v BTC) + b2*(makro risk-off)")
        print(f"   {'signal':<16}{'h':>4}{'b1 strat':>11}{'t1':>7}"
              f"{'b2 makro':>11}{'t2':>7}{'p2':>8}")
        enc = {}
        for name, fl in flags.items():
            enc[name] = {}
            for h in (5, 20):
                r = encompass(ret_w, bull, fl.reindex(idx), h)
                enc[name][h] = r
                if r:
                    star = "  <-- se steje" if r["p_macro"] < 0.05 else ""
                    print(f"   {name:<16}{h:>4}{r['b_bull']:>10.2f}%{r['t_bull']:>7.2f}"
                          f"{r['b_macro']:>10.2f}%{r['t_macro']:>7.2f}"
                          f"{r['p_macro']:>8.3f}{star}")

        # 3 ─ PBO over both rounds
        print("\n3. PBO CEZ OBA KROGA SKUPAJ")
        mats, names = [base_r], ["izhodisce"]
        for name, fl in flags.items():
            for mode in ("vstop", "vstop+izstop"):
                pos = build(raw, fl, mode)
                mats.append(net_returns(pos, ret, FEE).to_numpy(float))
                names.append(f"{name}|{mode}")
        p, picks = pbo(np.vstack(mats), names)
        print(f"   celic: {len(names)}    PBO = {p}")
        print("   najveckrat izbrano v vzorcu: "
              + ", ".join(f"{k} ({v})" for k, v in
                          sorted(picks.items(), key=lambda x: -x[1])[:4]))
        out[sym] = {"flips": fl_stats, "encompass": enc, "pbo": p, "picks": picks}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
