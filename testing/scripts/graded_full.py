"""Step 1 of DELOVNI_NACRT: the full battery on graded sizing.

Five cells. Everything outside the entry gate, the sizing rule and the exit is
today's engine.

    1  all three, binary, trackline exit          control, must match the reference
    2  k >= 1, position k/3, trackline exit       consensus sizing
    3  all three + Donchian, binary               Donchian alone
    4  k >= 1 over four, position k/4             both together
    5  k >= 1, position k/3, ATR x 3 exit         grading with the stop

Cell 5 exists because the ATR stop has been rejected twice but never paired with
GRADED sizing — grading could soften the standing objection that the stop leaves
the market too often, since the exit would no longer be all-or-nothing.

Eight tests, and the eighth is the one that decides this particular candidate.
Grading more than doubles turnover, so the advantage has to survive a fee level
we do not control. The pre-registered bar is 0.50 % per side.

PBO is purged by 21 days. Every PBO reported earlier in this project was not, and
is therefore optimistic.

Output: testing/data/graded_full.json
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
from testing.scripts.two_tracklines import sortino, maxdd, mcs, PPY, SUBPERIODS
from testing.scripts.atr_trailing import atr as _atr

np.seterr(all="ignore")

FEE = 0.30
SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
ETH = ROOT / "testing" / "data" / "sources" / "ETH_binance.parquet"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
OUT = ROOT / "testing" / "data" / "graded_full.json"
BASE3 = ("above_tl", "track_rising_window", "regime_ok")
S_BLOCKS, PURGE, NBOOT, BLOCK, N_SHIFT = 12, 21, 5000, 20, 1000
FEE_GRID = [0.30, 0.40, 0.50, 0.75, 1.00]
ATR_MULT = 3.0
rng = np.random.default_rng(20260815)

CELLS = {
    "1 danes":       dict(donch=False, graded=False, atr=False),
    "2 k/3":         dict(donch=False, graded=True,  atr=False),
    "3 +Donchian":   dict(donch=True,  graded=False, atr=False),
    "4 k/4 +Donch":  dict(donch=True,  graded=True,  atr=False),
    "5 k/3 +ATR3":   dict(donch=False, graded=True,  atr=True),
}


def build(raw, donch, graded, atr):
    cfg = engine.make_config("lean", use_donchian=donch, donchian_period=20)
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    terms = list(BASE3) + (["donchian_ok"] if donch else [])
    k = sum(df[t].fillna(False).astype(int) for t in terms)
    need = 1 if graded else len(terms)
    df = df.copy()
    df["bull_condition"] = ((k >= need) & df["btc_filter_ok"]
                            & ~df["blowoff"]).fillna(False)

    n = len(df)
    bull = df["bull_condition"].to_numpy()
    below = df["below_tl"].fillna(False).to_numpy()
    blow = df["blowoff"].fillna(False).to_numpy()
    close = df["close"].to_numpy(float)
    av = _atr(raw).reindex(df.index).to_numpy(float)
    sig = np.full(n, 3, np.int8)
    alloc = np.zeros(n, np.float32)
    cur, bsig, hold, bc, peak = 3, 999, 0, 0, np.nan
    for i in range(n):
        bsig += 1
        bc = bc + 1 if below[i] else 0
        hold = hold + 1 if bull[i] else 0
        if cur == 1:
            if atr:
                peak = max(peak, close[i])
                hit = np.isfinite(av[i]) and close[i] < peak - ATR_MULT * av[i]
            else:
                hit = below[i] and bc >= cfg.exit_grace_bars
            if hit or blow[i]:
                cur, bsig, peak = 3, 0, np.nan
        elif bull[i] and hold >= cfg.confirm_bars and bsig >= cfg.reentry_hold:
            cur, bsig, peak = 1, 0, close[i]
        alloc[i] = 100.0 if cur == 1 else 0.0
        sig[i] = cur
    st = df.assign(signal_state=sig, target_alloc=alloc,
                   display_state=sig, signal_changed=False)
    st = trim_warmup(st)
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    if graded:
        pos = pos * (k.reindex(st.index).shift(1).fillna(0) / len(terms))
    return pos


def met(pos, ret, fee=FEE):
    r = net_returns(pos, ret, fee).to_numpy(float)
    eq = np.cumprod(1 + r)
    to = float(turnover(pos).sum())
    return {"sortino": round(sortino(r), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
            "exposure": round(float(pos.mean() * 100), 1),
            "turnover": round(to, 1), "fees_pct": round(to * fee, 1)}


def pbo_purged(mat, purge):
    blocks = np.array_split(np.arange(mat.shape[1]), S_BLOCKS)
    below = tot = 0
    for sel in itertools.combinations(range(S_BLOCKS), S_BLOCKS // 2):
        is_i = [b[purge:len(b) - purge] if purge and len(b) > 2 * purge else b
                for b in (blocks[i] for i in sel)]
        oos_i = [blocks[i] for i in range(S_BLOCKS) if i not in sel]
        a, o = np.concatenate(is_i), np.concatenate(oos_i)
        s_is = np.array([sortino(m[a]) for m in mat])
        s_oos = np.array([sortino(m[o]) for m in mat])
        if not (np.isfinite(s_is).all() and np.isfinite(s_oos).all()):
            continue
        k = int(np.argmax(s_is))
        tot += 1
        below += int((s_oos < s_oos[k]).sum() / (mat.shape[0] - 1) < 0.5)
    return round(below / tot, 3), tot


def main() -> int:
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    names = list(CELLS)
    pos = {n: build(raw, **CELLS[n]) for n in names}
    idx = pos[names[0]].index

    ref = pd.read_parquet(REF)["position"]
    ok = idx.equals(ref.index) and np.allclose(pos["1 danes"].to_numpy(),
                                               ref.to_numpy(), atol=1e-12)
    print(f"KONTROLA: celica 1 = zamrznjena referenca? {'DA' if ok else 'NE'}")
    if not ok:
        return 2

    print(f"\n1) METRIKE — BTC, {len(idx)} dni, 0,30 % na stran")
    print(f"  {'celica':<15}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
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
        m["wins_vs_control"] = sum(
            1 for s in sub if sub[s] is not None
            and sub[s] > (res["1 danes"]["sub"][s] if "1 danes" in res else -9e9))
        res[n] = m
        ss = "  ".join(f"{v:5.2f}" if v is not None else "    —" for v in sub.values())
        print(f"  {n:<15}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%{m['maxdd']:>7.1f}%"
              f"{m['final']:>6.2f}x{m['exposure']:>7.1f}%{m['turnover']:>8.1f}"
              f"{m['fees_pct']:>10.1f}%  {ss}")
    for n in names[1:]:
        res[n]["wins_vs_control"] = sum(
            1 for s in res[n]["sub"]
            if res[n]["sub"][s] is not None and res[n]["sub"][s] > res["1 danes"]["sub"][s])
        print(f"     {n} boljši v {res[n]['wins_vs_control']} od 4 podobdobij")

    base = net_returns(pos["1 danes"], ret, FEE).to_numpy(float)
    n_ = len(base)
    kb = int(np.ceil(n_ / BLOCK))
    print(f"\n2) ΔSortino proti kontroli")
    boots = {}
    for n in names[1:]:
        a = net_returns(pos[n], ret, FEE).to_numpy(float)
        ds = []
        for lo in range(0, NBOOT, 500):
            m_ = min(500, NBOOT - lo)
            stt = rng.integers(0, n_, size=(m_, kb))
            ii = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]
                  ).reshape(m_, kb * BLOCK)[:, :n_] % n_
            ds.append(np.array([sortino(a[i]) - sortino(base[i]) for i in ii]))
        d = np.concatenate(ds)
        d = d[np.isfinite(d)]
        lo_, hi_ = np.percentile(d, [2.5, 97.5])
        boots[n] = {"delta": round(float(sortino(a) - sortino(base)), 3),
                    "ci": [round(float(lo_), 3), round(float(hi_), 3)],
                    "excl0": bool(lo_ > 0 or hi_ < 0)}
        print(f"   {n:<15}{boots[n]['delta']:+7.3f}   [{lo_:+.3f}, {hi_:+.3f}]   "
              f"{'IZKLJUČUJE ničlo' if lo_ > 0 or hi_ < 0 else 'objame ničlo'}")

    R = np.vstack([net_returns(pos[n], ret, FEE).to_numpy(float) for n in names])
    mres = {}
    print()
    for tag, L in (("povprecen donos", -R),
                   ("s kaznijo za padce", -R + 2.0 * np.minimum(R, 0.0) ** 2)):
        keep, elim = mcs(L, names)
        mres[tag] = {"kept": keep, "eliminated": elim}
        print(f"3) MCS ({tag}): {len(keep)}/5 → {', '.join(keep)}")

    print(f"\n4) UGNEZDENI WALK-FORWARD")
    wf = {}
    for tr, te in ((3, 1), (2, 1)):
        picks, segs, bs = [], [], []
        start = idx[0]
        while True:
            tb = start + pd.DateOffset(years=tr)
            eb = tb + pd.DateOffset(years=te)
            if eb > idx[-1]:
                break
            w = idx[(idx >= start) & (idx <= tb)]
            sc = {x: sortino(net_returns(pos[x].reindex(w), ret, FEE).to_numpy(float))
                  for x in names}
            pk = max(sc, key=lambda z: sc[z] if np.isfinite(sc[z]) else -9e9)
            t = idx[(idx > tb) & (idx <= eb)]
            picks.append(pk.split()[0])
            segs.append(pos[pk].reindex(t))
            bs.append(pos["1 danes"].reindex(t))
            start = start + pd.DateOffset(years=te)
        if segs:
            wf[f"{tr}y/{te}y"] = {
                "picks": picks, "refit": met(pd.concat(segs), ret)["sortino"],
                "control": met(pd.concat(bs), ret)["sortino"]}
            w_ = wf[f"{tr}y/{te}y"]
            print(f"   {tr}y/{te}y  {picks}   kontrola {w_['control']:.3f}   "
                  f"refit {w_['refit']:.3f}   "
                  f"{'refit boljši' if w_['refit'] > w_['control'] else 'kontrola boljša'}")

    p_pur, t_pur = pbo_purged(R, PURGE)
    p_raw, _ = pbo_purged(R, 0)
    print(f"\n5) PBO (CSCV, {t_pur} poti): s purge {PURGE} dni = {p_pur:.3f}"
          f"   brez purge = {p_raw:.3f}")

    print(f"\n6) NAKLJUČNI ZAMIK ({N_SHIFT} rotacij)")
    shifts = {}
    for n in ("2 k/3", "4 k/4 +Donch"):
        cfgd = CELLS[n]
        cfg = engine.make_config("lean", use_donchian=cfgd["donch"], donchian_period=20)
        smod = engine.strategy_module("lean")
        df = smod.compute_features(raw, None, cfg)
        terms = list(BASE3) + (["donchian_ok"] if cfgd["donch"] else [])
        k = sum(df[t].fillna(False).astype(int) for t in terms).to_numpy()
        sims = []
        for _ in range(N_SHIFT):
            kk = pd.Series(np.roll(k, int(rng.integers(60, len(k) - 60))), index=df.index)
            f2 = df.copy()
            f2["bull_condition"] = ((kk >= 1) & f2["btc_filter_ok"]
                                    & ~f2["blowoff"]).fillna(False)
            st = trim_warmup(smod.run_state_machine(f2, cfg))
            p = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
            p = p * (kk.reindex(st.index).shift(1).fillna(0) / len(terms))
            sims.append(sortino(net_returns(p, ret, FEE).to_numpy(float)))
        sims = np.array([x for x in sims if np.isfinite(x)])
        pct = float((sims < res[n]["sortino"]).mean() * 100)
        shifts[n] = {"real": res[n]["sortino"], "mean": round(float(sims.mean()), 3),
                     "percentile": round(pct, 1)}
        print(f"   {n:<15} pravi {res[n]['sortino']:.3f}   zamaknjeni "
              f"{sims.mean():.3f}   {pct:.1f}. percentil")

    print(f"\n7) PRELOMNA PROVIZIJA — Sortino pri različnih stroških na stran")
    print(f"  {'celica':<15}" + "".join(f"{f:>9.2f}%" for f in FEE_GRID))
    fees = {}
    for n in names:
        row = [met(pos[n], ret, f)["sortino"] for f in FEE_GRID]
        fees[n] = dict(zip(map(str, FEE_GRID), [round(x, 3) for x in row]))
        print(f"  {n:<15}" + "".join(f"{x:>10.3f}" for x in row))
    b = [met(pos["1 danes"], ret, f)["sortino"] for f in FEE_GRID]
    print(f"\n  prednost proti kontroli:")
    for n in names[1:]:
        row = [met(pos[n], ret, f)["sortino"] - bb for f, bb in zip(FEE_GRID, b)]
        brk = next((f for f, d in zip(FEE_GRID, row) if d <= 0), None)
        print(f"  {n:<15}" + "".join(f"{x:>+10.3f}" for x in row)
              + (f"   prelom pri {brk:.2f} %" if brk else "   drži do 1,00 %"))
        fees[n]["breakeven"] = brk

    OUT.write_text(json.dumps({"cells": res, "bootstrap": boots, "mcs": mres,
                               "walk_forward": wf, "pbo_purged": p_pur,
                               "pbo_raw": p_raw, "shift": shifts, "fees": fees},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
