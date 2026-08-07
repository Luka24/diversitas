"""Step 6 as originally specified: entry on a majority of the THREE entry rules.

Pre-registered in `testing/nacrt_koraka_6_in_8.md`.

The earlier majority_vote.py voted over {above_tl, Donchian, slope} while holding
regime_ok hard. The original asks for a vote over the three conditions the engine
actually uses, plus a leave-one-out arm that was skipped:

    above_tl · track_rising_window · regime_ok

    3/3        all three, today's engine, control
    2/3        at least two
    1/3        at least one
    -above_tl  drop the price gate, other two required
    -naklon    drop the slope
    -regime    drop the bear-market block

Blow-off stays a hard requirement everywhere; it is an exit rule that has also
blocked entry since 2026-08-04.

Read with this in mind: 2/3, 1/3 and -regime all permit buying inside a confirmed
bear market. That is a changed risk profile, not changed entry timing.

The original plan named the finding that would matter most, and it is not the
threshold: if 1/3 is not much worse than 3/3, the entry conditions together carry
no information.

Output: testing/data/entry_vote_orig.json
"""
from __future__ import annotations

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

np.seterr(all="ignore")

SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
OUT = ROOT / "testing" / "data" / "entry_vote_orig.json"
NBOOT, BLOCK = 5000, 20
rng = np.random.default_rng(20260813)

TERMS = ("above_tl", "track_rising_window", "regime_ok")
CELLS = {
    "3/3  danes":  ("k", 3),
    "2/3":         ("k", 2),
    "1/3":         ("k", 1),
    "brez above_tl": ("drop", "above_tl"),
    "brez naklona":  ("drop", "track_rising_window"),
    "brez rezima":   ("drop", "regime_ok"),
}


def build(raw, kind, arg):
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    cols = [df[t].fillna(False) for t in TERMS]
    if kind == "k":
        gate = sum(c.astype(int) for c in cols) >= arg
    else:
        keep = [df[t].fillna(False) for t in TERMS if t != arg]
        gate = keep[0] & keep[1]
    df["bull_condition"] = (gate & df["btc_filter_ok"] & ~df["blowoff"]).fillna(False)
    st = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos, st


def capture(pos, bench):
    b = bench.reindex(pos.index).fillna(0.0).to_numpy()
    s = pos.to_numpy() * b
    up, dn = b > 0, b < 0
    return (round(float(s[up].sum() / b[up].sum() * 100), 1),
            round(float(s[dn].sum() / b[dn].sum() * 100), 1))


def entry_lag(st, cfg):
    """Bars the entry was ready but held back by confirm_bars / reentry_hold."""
    bull = st["bull_condition"].fillna(False).to_numpy()
    sig = st["signal_state"].to_numpy()
    chg = st["signal_changed"].to_numpy()
    lags, run = [], -1
    for i in range(len(st)):
        if bull[i]:
            if run < 0:
                run = i
        else:
            run = -1
        if chg[i] and sig[i] == 1 and run >= 0:
            lags.append(i - run)
    return (round(float(np.mean(lags)), 1) if lags else None,
            int(np.median(lags)) if lags else None)


def main() -> int:
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    cfg = engine.make_config("lean")
    pos, sts = {}, {}
    for nm, (k, a) in CELLS.items():
        pos[nm], sts[nm] = build(raw, k, a)
    names = list(CELLS)
    idx = pos[names[0]].index

    ref = pd.read_parquet(REF)["position"]
    ok = (pos["3/3  danes"].index.equals(ref.index)
          and np.allclose(pos["3/3  danes"].to_numpy(), ref.to_numpy(), atol=1e-12))
    print(f"KONTROLA: 3/3 = zamrznjena referenca? {'DA' if ok else 'NE'}")
    if not ok:
        print("  Harness se moti na kontroli. USTAVLJAM.")
        return 2

    print(f"\nBTC · {len(idx)} dni · {idx[0].date()} → {idx[-1].date()}")
    print(f"  {'celica':<16}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
          f"{'izpost':>8}{'posl':>6}{'zajem-':>8}{'zamuda':>8}    I     II    III    IV")
    res = {}
    for nm in names:
        p, st = pos[nm], sts[nm]
        r = net_returns(p, ret, FEE).to_numpy(float)
        eq = np.cumprod(1 + r)
        up, dn = capture(p, ret)
        lag_m, lag_med = entry_lag(st, cfg)
        sub = {}
        for s, a, b in SUBPERIODS:
            w = idx[(idx >= a) & (idx <= b)]
            sub[s] = (round(sortino(net_returns(p.reindex(w), ret, FEE).to_numpy(float)), 2)
                      if len(w) > 60 else None)
        m = {"sortino": round(sortino(r), 3),
             "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
             "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
             "exposure": round(float(p.mean() * 100), 1),
             "trades": int((np.diff(p.to_numpy(), prepend=p.iloc[0]) > 0).sum()),
             "turnover": round(float(turnover(p).sum()), 1),
             "upside_capture": up, "downside_capture": dn,
             "entry_lag_mean": lag_m, "sub": sub}
        res[nm] = m
        ss = "  ".join(f"{v:5.2f}" if v is not None else "    —" for v in sub.values())
        print(f"  {nm:<16}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%{m['maxdd']:>7.1f}%"
              f"{m['final']:>6.2f}x{m['exposure']:>7.1f}%{m['trades']:>6d}"
              f"{dn:>8.1f}{str(lag_m):>8}  {ss}")

    base = net_returns(pos["3/3  danes"], ret, FEE).to_numpy(float)
    print(f"\n  ΔSortino proti 3/3 (sparjeni blokovni bootstrap)")
    boots = {}
    n = len(base)
    kb = int(np.ceil(n / BLOCK))
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
        print(f"    {nm:<16}{boots[nm]['delta']:+7.3f}   [{lo_:+.3f}, {hi_:+.3f}]   "
              f"{'IZKLJUČUJE ničlo' if lo_ > 0 or hi_ < 0 else 'objame ničlo'}")

    R = np.vstack([net_returns(pos[n_], ret, FEE).to_numpy(float) for n_ in names])
    mres = {}
    for tag, L in (("povprecen donos", -R),
                   ("s kaznijo za padce", -R + 2.0 * np.minimum(R, 0.0) ** 2)):
        keep, elim = mcs(L, names)
        mres[tag] = {"kept": keep, "eliminated": elim}
        print(f"\n  MCS ({tag}): {len(keep)}/6 → {', '.join(keep)}")

    # the headline the original plan asked for
    s33, s13 = res["3/3  danes"]["sortino"], res["1/3"]["sortino"]
    print(f"\n  IZVIRNO VPRAŠANJE: je 1/3 bistveno slabši od 3/3?")
    print(f"    3/3 {s33:.3f}   1/3 {s13:.3f}   razlika {s13-s33:+.3f}")
    print(f"    {'da -> vstopni pogoji nosijo informacijo' if s13 < s33 - 0.3 else 'NE -> vstopni pogoji skupaj nosijo malo informacije'}")

    # acceptance criterion for 2/3
    c = res["2/3"]
    base_m = res["3/3  danes"]
    lag_ok = (c["entry_lag_mean"] or 9e9) < (base_m["entry_lag_mean"] or 0)
    dn_ok = c["downside_capture"] - base_m["downside_capture"] < 1.0
    print(f"\n  SPREJEMNI KRITERIJ za 2/3 (izvirni)")
    print(f"    zmanjša zamudo:                {'DA' if lag_ok else 'NE'}"
          f"   ({base_m['entry_lag_mean']} → {c['entry_lag_mean']})")
    print(f"    zajem navzdol znotraj 1,0 o.t: {'DA' if dn_ok else 'NE'}"
          f"   ({base_m['downside_capture']} → {c['downside_capture']})")
    print(f"    IZID: {'PRESTANE' if lag_ok and dn_ok else 'NE PRESTANE'}")

    OUT.write_text(json.dumps({"cells": res, "bootstrap": boots, "mcs": mres,
                               "accept_2of3": bool(lag_ok and dn_ok)},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
