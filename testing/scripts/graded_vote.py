"""The majority vote done the way CTAs actually do it, plus a purged CSCV.

Two gaps in the earlier treatment, both real.

FIRST: I tested THRESHOLDS, not consensus sizing. "At least 2 of 3" still takes a
full position. What the trend-following literature describes is different — the
position is SIZED by how many signals agree, so 1 of 3 is a third of a position
and 3 of 3 is a full one. That is the professional form and it was never run.

    danes      binary, all three required, full position
    ocenjeno   state machine gated on k >= 1, position scaled by k/3
    cisto      position = k/3 every day, no state machine at all

The third cell drops confirm_bars, reentry_hold and the grace counter, so it also
answers a question worth knowing: how much of this strategy is the anti-churn
apparatus rather than the signals?

SECOND: none of my CSCV runs purged. Blocks were cut contiguously and used as-is,
but the features carry 200-day rolling windows, so a block adjacent to the test
set shares information with it. Lopez de Prado is explicit that this inflates
apparent out-of-sample performance. The project's own earlier PBO used a 21-day
purge; mine did not, so every PBO I have reported is optimistic. Purging is
implemented here and the two numbers are printed side by side.

Turnover is the thing to watch on the graded cells. A position that moves with
the count changes on every condition flip, and at 0.30 % per side that is not
free.

Output: testing/data/graded_vote.json
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
from testing.scripts.two_tracklines import sortino, maxdd, FEE, PPY, SUBPERIODS

np.seterr(all="ignore")

SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
OUT = ROOT / "testing" / "data" / "graded_vote.json"
TERMS = ("above_tl", "track_rising_window", "regime_ok")
S_BLOCKS, PURGE = 12, 21


def counts(raw):
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    k = sum(df[t].fillna(False).astype(int) for t in TERMS)
    return df, k, cfg, smod


def build(raw, mode):
    df, k, cfg, smod = counts(raw)
    if mode == "cisto":
        # No state machine: hold k/3 every day, shifted so today's count drives
        # tomorrow's position — the same one-bar rule the engine uses.
        w = (k / len(TERMS)).where(~df["blowoff"].fillna(False), 0.0)
        pos = w.shift(1).fillna(0.0)
        st = trim_warmup(df.assign(signal_state=1, target_alloc=w * 100,
                                   display_state=1, signal_changed=False))
        return pos.reindex(st.index)
    gate = k >= (len(TERMS) if mode == "danes" else 1)
    df = df.copy()
    df["bull_condition"] = (gate & df["btc_filter_ok"] & ~df["blowoff"]).fillna(False)
    st = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    if mode == "ocenjeno":
        pos = pos * (k.reindex(st.index).shift(1).fillna(0) / len(TERMS))
    return pos


def met(pos, ret):
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1 + r)
    to = float(turnover(pos).sum())
    return {"sortino": round(sortino(r), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
            "exposure": round(float(pos.mean() * 100), 1),
            "turnover": round(to, 1), "fees_pct": round(to * FEE, 1)}


def pbo(mat, names, purge):
    blocks = np.array_split(np.arange(mat.shape[1]), S_BLOCKS)
    below = tot = 0
    for sel in itertools.combinations(range(S_BLOCKS), S_BLOCKS // 2):
        oos_b = [i for i in range(S_BLOCKS) if i not in sel]
        is_i, oos_i = [], []
        for i in sel:
            b = blocks[i]
            # drop the edges of every in-sample block so it cannot share a
            # rolling window with an adjacent test block
            is_i.append(b[purge:len(b) - purge] if purge and len(b) > 2 * purge else b)
        for i in oos_b:
            oos_i.append(blocks[i])
        i_is, i_oos = np.concatenate(is_i), np.concatenate(oos_i)
        s_is = np.array([sortino(m[i_is]) for m in mat])
        s_oos = np.array([sortino(m[i_oos]) for m in mat])
        if not (np.isfinite(s_is).all() and np.isfinite(s_oos).all()):
            continue
        k = int(np.argmax(s_is))
        tot += 1
        below += int((s_oos < s_oos[k]).sum() / (len(names) - 1) < 0.5)
    return round(below / tot, 3), tot


def main() -> int:
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    names = ["danes", "ocenjeno", "cisto"]
    labels = {"danes": "binarno, vsi trije",
              "ocenjeno": "ocenjeno k/3, s strojem stanj",
              "cisto": "čisto k/3, brez stroja stanj"}
    pos = {n: build(raw, n) for n in names}
    idx = pos["danes"].index

    ref = pd.read_parquet(REF)["position"]
    ok = idx.equals(ref.index) and np.allclose(pos["danes"].to_numpy(),
                                               ref.to_numpy(), atol=1e-12)
    print(f"KONTROLA: danes = referenca? {'DA' if ok else 'NE'}")
    if not ok:
        return 2

    print(f"\nBTC · {len(idx)} dni")
    print(f"  {'celica':<32}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
          f"{'izpost':>8}{'obrat':>8}{'provizije':>11}    I     II    III    IV")
    res = {}
    for n in names:
        m = met(pos[n], ret)
        sub = {}
        for s, a, b in SUBPERIODS:
            w = idx[(idx >= a) & (idx <= b)]
            sub[s] = round(sortino(net_returns(pos[n].reindex(w), ret, FEE)
                                   .to_numpy(float)), 2) if len(w) > 60 else None
        m["sub"] = sub
        res[n] = m
        ss = "  ".join(f"{v:5.2f}" if v is not None else "    —" for v in sub.values())
        print(f"  {labels[n]:<32}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%{m['maxdd']:>7.1f}%"
              f"{m['final']:>6.2f}x{m['exposure']:>7.1f}%{m['turnover']:>8.1f}"
              f"{m['fees_pct']:>10.1f}%  {ss}")

    mat = np.vstack([net_returns(pos[n], ret, FEE).to_numpy(float) for n in names])
    p_no, t_no = pbo(mat, names, 0)
    p_yes, t_yes = pbo(mat, names, PURGE)
    print(f"\n  PBO brez purge: {p_no:.3f} ({t_no} poti)")
    print(f"  PBO s purge {PURGE} dni: {p_yes:.3f} ({t_yes} poti)")
    print(f"  Vsi prej poročani PBO v tem projektu so brez purge, torej optimistični.")

    print(f"\n  STROŠEK OCENJEVANJA")
    b = res["danes"]
    for n in names[1:]:
        m = res[n]
        print(f"    {labels[n]:<32} obrat {m['turnover']:.1f} proti {b['turnover']:.1f}"
              f"   provizije {m['fees_pct']:.1f} % proti {b['fees_pct']:.1f} %"
              f"   ({m['fees_pct']-b['fees_pct']:+.1f} o. t.)")

    OUT.write_text(json.dumps({"cells": res, "labels": labels,
                               "pbo_no_purge": p_no, "pbo_purged": p_yes,
                               "purge_days": PURGE}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
