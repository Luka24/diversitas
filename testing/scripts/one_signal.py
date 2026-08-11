"""Can we drop condition A and run ONE trackline instead of two?

The colleague's actual question, which earlier tests answered three different
ways without saying so. There are three distinct meanings of "replace" and they
give different numbers:

    A  today                         75-day midpoint + 3 % of price
    B  ONE signal, full replacement  20-day midpoint + 25 % of range, used for
                                     ENTRY, EXIT and SLOPE — only one channel
                                     is computed at all
    C  entry gate only               20-day gate for entry, but exit and slope
                                     still come from the 75-day trackline, so
                                     BOTH channels are computed
    D  both required                 today's gate AND the Donchian gate

Only B is what "one signal" means. C looks like a replacement and is not: the
75-day channel is still needed by the exit, by the slope condition and by the
blow-off distance, so nothing is removed.

Full battery on all four, with the 21-day purge that earlier PBO runs lacked.

Output: testing/data/one_signal.json
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
OUT = ROOT / "testing" / "data" / "one_signal.json"
S_BLOCKS, PURGE, NBOOT, BLOCK, N_SHIFT = 12, 21, 5000, 20, 1000
CELLS = ("A danes", "B en signal", "C samo vstop", "D oba")
rng = np.random.default_rng(20260816)


def gates(raw, index):
    h75 = ind.highest(raw["high"], 75).reindex(index)
    l75 = ind.lowest(raw["low"], 75).reindex(index)
    h20 = ind.highest(raw["high"], 20).reindex(index)
    l20 = ind.lowest(raw["low"], 20).reindex(index)
    c = raw["close"].reindex(index)
    return (h75 + l75) / 2, (h20 + l20) / 2, (h20 - l20), c


def build(raw, cell):
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    m75, m20, r20, c = gates(raw, df.index)

    if cell == "B en signal":
        # everything moves to the 20-day channel: entry, exit, slope, blow-off
        band = 0.25 * r20
        df["trackline"] = m20
        df["above_tl"] = c > m20 + band
        df["below_tl"] = c < m20 - band
        df["dist_pct"] = (c - m20) / m20 * 100
        df["track_rising_window"] = m20 > m20.shift(cfg.track_slope_bars)
        df["blowoff"] = (df["dist_pct"] > cfg.blowoff_dist_pct) & (df["rsi"] > 80)
        gate = df["above_tl"]
    else:
        A = c > m75 * 1.03
        D = c > m20 + 0.25 * r20
        gate = {"A danes": A, "C samo vstop": D, "D oba": A & D}[cell]

    bull = gate & df["track_rising_window"] & df["regime_ok"] & df["btc_filter_ok"]
    df["bull_condition"] = (bull & ~df["blowoff"]).fillna(False)
    df["trend_break"] = df["below_tl"]
    st = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos, gate.reindex(st.index)


def met(pos, ret):
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1 + r)
    return {"sortino": round(sortino(r), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
            "exposure": round(float(pos.mean() * 100), 1),
            "trades": int((np.diff(pos.to_numpy(), prepend=pos.iloc[0]) > 0).sum()),
            "turnover": round(float(turnover(pos).sum()), 1)}


def pbo(mat, purge):
    blocks = np.array_split(np.arange(mat.shape[1]), S_BLOCKS)
    below = tot = 0
    picks = {c: 0 for c in CELLS}
    for sel in itertools.combinations(range(S_BLOCKS), S_BLOCKS // 2):
        isx = np.concatenate([b[purge:len(b) - purge] if purge and len(b) > 2 * purge
                              else b for b in (blocks[i] for i in sel)])
        oos = np.concatenate([blocks[i] for i in range(S_BLOCKS) if i not in sel])
        si = np.array([sortino(m[isx]) for m in mat])
        so = np.array([sortino(m[oos]) for m in mat])
        if not (np.isfinite(si).all() and np.isfinite(so).all()):
            continue
        k = int(np.argmax(si))
        picks[CELLS[k]] += 1
        tot += 1
        below += int((so < so[k]).sum() / (len(CELLS) - 1) < 0.5)
    return round(below / tot, 3), picks


def main() -> int:
    out = {"purge": PURGE}
    for sym, f in (("BTC", "BTC_binance_warmup.parquet"), ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(SRC / f)
        ret = raw["close"].pct_change().fillna(0.0)
        pos, gts = {}, {}
        for c in CELLS:
            pos[c], gts[c] = build(raw, c)
        idx = pos["A danes"].index

        if sym == "BTC":
            ref = pd.read_parquet(REF)["position"]
            ok = idx.equals(ref.index) and np.allclose(pos["A danes"].to_numpy(),
                                                       ref.to_numpy(), atol=1e-12)
            print(f"KONTROLA: A = zamrznjena referenca? {'DA' if ok else 'NE'}")
            if not ok:
                return 2

        print(f"\n{'='*92}\n{sym} · {len(idx)} dni\n{'='*92}")
        print(f"  {'celica':<15}{'kanalov':>9}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}"
              f"{'konec':>7}{'izpost':>8}{'posl':>6}    I     II    III    IV   zmag")
        ch = {"A danes": 1, "B en signal": 1, "C samo vstop": 2, "D oba": 2}
        res = {}
        for c in CELLS:
            m = met(pos[c], ret)
            sub = {}
            for s, a, b in SUBPERIODS:
                w = idx[(idx >= a) & (idx <= b)]
                sub[s] = round(sortino(net_returns(pos[c].reindex(w), ret, FEE)
                                       .to_numpy(float)), 2) if len(w) > 60 else None
            m["sub"] = sub
            m["channels"] = ch[c]
            res[c] = m
        for c in CELLS:
            m = res[c]
            wins = sum(1 for s in m["sub"] if m["sub"][s] is not None
                       and m["sub"][s] > res["A danes"]["sub"][s])
            m["wins"] = wins
            ss = "  ".join(f"{v:5.2f}" if v is not None else "    —"
                           for v in m["sub"].values())
            print(f"  {c:<15}{m['channels']:>9}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%"
                  f"{m['maxdd']:>7.1f}%{m['final']:>6.2f}x{m['exposure']:>7.1f}%"
                  f"{m['trades']:>6d}  {ss}{wins:>6}")

        base = net_returns(pos["A danes"], ret, FEE).to_numpy(float)
        n = len(base)
        kb = int(np.ceil(n / BLOCK))
        print(f"\n  ΔSortino proti A")
        for c in CELLS[1:]:
            a = net_returns(pos[c], ret, FEE).to_numpy(float)
            ds = []
            for lo in range(0, NBOOT, 500):
                mm = min(500, NBOOT - lo)
                stt = rng.integers(0, n, size=(mm, kb))
                ii = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]
                      ).reshape(mm, kb * BLOCK)[:, :n] % n
                ds.append(np.array([sortino(a[i]) - sortino(base[i]) for i in ii]))
            d = np.concatenate(ds)
            d = d[np.isfinite(d)]
            lo_, hi_ = np.percentile(d, [2.5, 97.5])
            res[c]["delta"] = round(float(sortino(a) - sortino(base)), 3)
            res[c]["ci"] = [round(float(lo_), 3), round(float(hi_), 3)]
            print(f"    {c:<15}{res[c]['delta']:+7.3f}   [{lo_:+.3f}, {hi_:+.3f}]   "
                  f"{'IZKLJUČUJE' if lo_ > 0 or hi_ < 0 else 'objame ničlo'}")

        R = np.vstack([net_returns(pos[c], ret, FEE).to_numpy(float) for c in CELLS])
        for tag, L in (("povprecen donos", -R),
                       ("s kaznijo za padce", -R + 2.0 * np.minimum(R, 0.0) ** 2)):
            keep, _ = mcs(L, list(CELLS))
            print(f"  MCS ({tag}): {len(keep)}/4 → {', '.join(keep)}")

        print(f"\n  UGNEZDENI WALK-FORWARD")
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
                      for x in CELLS}
                pk = max(sc, key=lambda z: sc[z] if np.isfinite(sc[z]) else -9e9)
                t = idx[(idx > tb) & (idx <= eb)]
                picks.append(pk.split()[0])
                segs.append(pos[pk].reindex(t))
                bs.append(pos["A danes"].reindex(t))
                start = start + pd.DateOffset(years=te)
            if segs:
                print(f"    {tr}y/{te}y  {picks}   A {met(pd.concat(bs), ret)['sortino']:.3f}"
                      f"   refit {met(pd.concat(segs), ret)['sortino']:.3f}")

        p_p, picks = pbo(R, PURGE)
        p_r, _ = pbo(R, 0)
        print(f"\n  PBO: s purge {p_p:.3f}   brez purge {p_r:.3f}   "
              + "  ".join(f"{k.split()[0]}:{v}" for k, v in picks.items() if v))
        out[sym] = {"cells": res, "pbo_purged": p_p, "pbo_raw": p_r,
                    "pbo_picks": picks}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
