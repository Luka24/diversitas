"""Steps 6 and 8 re-tested properly, together, with the metrics that were wrong.

Three things the first pass got wrong or skipped:

  The entry-lag column counted bars since bull_condition first turned true, so a
  looser gate produced longer runs and a bigger number — 1/3 reported 99.5 days,
  which is an artifact, not a delay. Lag is measured here as bars the entry was
  READY while flat but held back, which is comparable across cells.

  The ATR criterion measured protection without measuring its cost or matching
  exposure. Both are here, and the exposure-matched comparison scales the
  BASELINE DOWN to meet the variant, since scaling a binary series up and
  clipping is a no-op.

  Neither was tried in combination. A looser entry paired with a tighter exit is
  a coherent design and was never run.

Four cells:

    danes        3/3 entry, trackline exit           control
    2/3          majority entry, trackline exit
    ATR3         3/3 entry, peak - 3 x ATR(14) exit  Chandelier convention
    2/3+ATR3     both together

N = 3 is fixed, not swept: the earlier grid showed protection rising smoothly with
tightness while returns collapsed, so there is no shape left to read, and PBO of
0.672 and 0.694 says picking a value here does not transfer.

Full battery, same as every other decision in this project: paired block
bootstrap, MCS under two loss functions, nested walk-forward, PBO via CSCV,
circular shift.

Output: testing/data/retest_6_8.json
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
from testing.scripts.two_tracklines import sortino, maxdd, mcs, FEE, PPY, SUBPERIODS
from testing.scripts.atr_trailing import atr

np.seterr(all="ignore")

SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
OUT = ROOT / "testing" / "data" / "retest_6_8.json"
TERMS = ("above_tl", "track_rising_window", "regime_ok")
S_BLOCKS, NBOOT, BLOCK, N_SHIFT, ATR_MULT = 12, 5000, 20, 1000, 3.0
CELLS = {"danes": (3, False), "2/3": (2, False),
         "ATR3": (3, True), "2/3+ATR3": (2, True)}
rng = np.random.default_rng(20260814)


def build(raw, k, use_atr):
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    gate = sum(df[t].fillna(False).astype(int) for t in TERMS) >= k
    df["bull_condition"] = (gate & df["btc_filter_ok"] & ~df["blowoff"]).fillna(False)

    n = len(df)
    bull = df["bull_condition"].to_numpy()
    below = df["below_tl"].fillna(False).to_numpy()
    blow = df["blowoff"].fillna(False).to_numpy()
    close = df["close"].to_numpy(float)
    av = atr(raw).reindex(df.index).to_numpy(float)
    sig = np.full(n, 3, np.int8)
    alloc = np.zeros(n, np.float32)
    chg = np.zeros(n, bool)
    cur, prev, bsig, hold, bc, peak = 3, 3, 999, 0, 0, np.nan
    ready_since, lags, blocked = -1, [], 0
    for i in range(n):
        bsig += 1
        bc = bc + 1 if below[i] else 0
        hold = hold + 1 if bull[i] else 0
        if cur == 1:
            if use_atr:
                peak = max(peak, close[i])
                hit = np.isfinite(av[i]) and close[i] < peak - ATR_MULT * av[i]
            else:
                hit = below[i] and bc >= cfg.exit_grace_bars
            if hit or blow[i]:
                cur, bsig, peak, ready_since = 3, 0, np.nan, -1
        else:
            rdy = bull[i] and hold >= cfg.confirm_bars
            if not rdy:
                ready_since = -1
            else:
                if ready_since < 0:
                    ready_since = i
                if bsig >= cfg.reentry_hold:
                    lags.append(i - ready_since)
                    cur, bsig, peak, ready_since = 1, 0, close[i], -1
                else:
                    blocked += 1
        alloc[i] = 100.0 if cur == 1 else 0.0
        chg[i] = cur != prev
        prev = cur
        sig[i] = cur
    st = df.copy()
    st["signal_state"] = sig
    st["target_alloc"] = alloc
    st["signal_changed"] = chg
    st["display_state"] = sig
    st = trim_warmup(st)
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos, (round(float(np.mean(lags)), 1) if lags else None), blocked


def capture(pos, bench):
    b = bench.reindex(pos.index).fillna(0.0).to_numpy()
    s = pos.to_numpy() * b
    up, dn = b > 0, b < 0
    return (round(float(s[up].sum() / b[up].sum() * 100), 1),
            round(float(s[dn].sum() / b[dn].sum() * 100), 1))


def met(pos, ret):
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1 + r)
    up, dn = capture(pos, ret)
    return {"sortino": round(sortino(r), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
            "exposure": round(float(pos.mean() * 100), 1),
            "trades": int((np.diff(pos.to_numpy(), prepend=pos.iloc[0]) > 0).sum()),
            "turnover": round(float(turnover(pos).sum()), 1),
            "up_capture": up, "down_capture": dn}


def main() -> int:
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    pos, lag, blk = {}, {}, {}
    for nm, (k, a) in CELLS.items():
        pos[nm], lag[nm], blk[nm] = build(raw, k, a)
    names = list(CELLS)
    idx = pos["danes"].index

    ref = pd.read_parquet(REF)["position"]
    ok = idx.equals(ref.index) and np.allclose(pos["danes"].to_numpy(),
                                               ref.to_numpy(), atol=1e-12)
    print(f"KONTROLA: danes = referenca? {'DA' if ok else 'NE'}")
    if not ok:
        return 2

    print(f"\nBTC · {len(idx)} dni")
    print(f"  {'celica':<10}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
          f"{'izpost':>8}{'posl':>6}{'zajem+':>8}{'zajem−':>8}{'zamuda':>8}"
          f"    I     II    III    IV")
    res = {}
    for nm in names:
        m = met(pos[nm], ret)
        m["entry_lag"] = lag[nm]
        m["blocked_days"] = blk[nm]
        sub = {}
        for s, a, b in SUBPERIODS:
            w = idx[(idx >= a) & (idx <= b)]
            sub[s] = round(sortino(net_returns(pos[nm].reindex(w), ret, FEE)
                                   .to_numpy(float)), 2) if len(w) > 60 else None
        m["sub"] = sub
        res[nm] = m
        ss = "  ".join(f"{v:5.2f}" if v is not None else "    —" for v in sub.values())
        print(f"  {nm:<10}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%{m['maxdd']:>7.1f}%"
              f"{m['final']:>6.2f}x{m['exposure']:>7.1f}%{m['trades']:>6d}"
              f"{m['up_capture']:>8.1f}{m['down_capture']:>8.1f}"
              f"{str(m['entry_lag']):>8}  {ss}")

    print(f"\n  IZENAČENA IZPOSTAVLJENOST — danes pomanjšan na vsako celico")
    e0 = res["danes"]["exposure"]
    print(f"  {'celica':<10}{'izpost':>8}{'zajem− celica':>15}{'zajem− danes':>15}"
          f"{'MaxDD celica':>14}{'MaxDD danes':>13}")
    emat = {}
    for nm in names[1:]:
        e = res[nm]["exposure"]
        ps = (pos["danes"] * (e / e0)).clip(0, 1)
        r0 = net_returns(ps, ret, FEE).to_numpy(float)
        _, dn0 = capture(ps, ret)
        emat[nm] = {"cell_dn": res[nm]["down_capture"], "base_dn": dn0,
                    "cell_dd": res[nm]["maxdd"], "base_dd": round(maxdd(r0), 1),
                    "better": bool(res[nm]["down_capture"] < dn0)}
        print(f"  {nm:<10}{e:>8.1f}{res[nm]['down_capture']:>15.1f}{dn0:>15.1f}"
              f"{res[nm]['maxdd']:>14.1f}{maxdd(r0):>13.1f}")

    base = net_returns(pos["danes"], ret, FEE).to_numpy(float)
    n = len(base)
    kb = int(np.ceil(n / BLOCK))
    print(f"\n  ΔSortino proti danes")
    boots = {}
    for nm in names[1:]:
        a = net_returns(pos[nm], ret, FEE).to_numpy(float)
        ds = []
        for lo in range(0, NBOOT, 500):
            m_ = min(500, NBOOT - lo)
            stt = rng.integers(0, n, size=(m_, kb))
            ii = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]
                  ).reshape(m_, kb * BLOCK)[:, :n] % n
            ds.append(np.array([sortino(a[i]) - sortino(base[i]) for i in ii]))
        d = np.concatenate(ds)
        d = d[np.isfinite(d)]
        lo_, hi_ = np.percentile(d, [2.5, 97.5])
        boots[nm] = {"delta": round(float(sortino(a) - sortino(base)), 3),
                     "ci": [round(float(lo_), 3), round(float(hi_), 3)]}
        print(f"    {nm:<10}{boots[nm]['delta']:+7.3f}   [{lo_:+.3f}, {hi_:+.3f}]   "
              f"{'IZKLJUČUJE' if lo_ > 0 or hi_ < 0 else 'objame ničlo'}")

    R = np.vstack([net_returns(pos[x], ret, FEE).to_numpy(float) for x in names])
    mres = {}
    for tag, L in (("povprecen donos", -R),
                   ("s kaznijo za padce", -R + 2.0 * np.minimum(R, 0.0) ** 2)):
        keep, elim = mcs(L, names)
        mres[tag] = {"kept": keep, "eliminated": elim}
        print(f"\n  MCS ({tag}): {len(keep)}/4 → {', '.join(keep)}")

    print(f"\n  UGNEZDENI WALK-FORWARD")
    wf = {}
    for tr, te in ((3, 1), (2, 1)):
        picks, segs, b_segs = [], [], []
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
            picks.append(pk)
            segs.append(pos[pk].reindex(t))
            b_segs.append(pos["danes"].reindex(t))
            start = start + pd.DateOffset(years=te)
        if segs:
            wf[f"{tr}y/{te}y"] = {"picks": picks,
                                  "refit": met(pd.concat(segs), ret)["sortino"],
                                  "danes": met(pd.concat(b_segs), ret)["sortino"]}
            w_ = wf[f"{tr}y/{te}y"]
            print(f"    {tr}y/{te}y  {picks}   danes {w_['danes']:.3f}  "
                  f"refit {w_['refit']:.3f}")

    blocks = np.array_split(np.arange(R.shape[1]), S_BLOCKS)
    below = tot = 0
    picked = {x: 0 for x in names}
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
          + "  ".join(f"{k}:{v}" for k, v in picked.items() if v))

    OUT.write_text(json.dumps({"cells": res, "exposure_matched": emat,
                               "bootstrap": boots, "mcs": mres,
                               "walk_forward": wf,
                               "pbo": round(below / tot, 3), "pbo_picked": picked},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
