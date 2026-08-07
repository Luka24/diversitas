"""Given D, is the 75-day price gate A still needed?

One focused comparison, not another grid. Two cells only:

    D+n     D and slope            (regime and blow-off hard, as always)
    A+D+n   A and D and slope

They differ on exactly one thing, so everything measured here is attributable to
A. Five questions, in the order that matters:

  1. How many days does A actually change the position? A rule that never binds
     cannot be needed.
  2. What did price do on those days? A blocks entries; if the blocked days rose,
     A costs money, if they fell, A earns its place.
  3. Paired block bootstrap on the Sortino difference, same resampled days on
     both series so market movement cancels.
  4. Sub-period consistency, the pre-specified four windows.
  5. Walk-forward between just these two: choosing on train only, which wins on
     test?

Output: testing/data/is_A_needed.json
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

from shared.costs import net_returns
from testing.scripts.two_tracklines import sortino, maxdd, FEE, PPY, SUBPERIODS
from testing.scripts.majority_vote import build, metrics

np.seterr(all="ignore")

H, NBOOT, BLOCK = 20, 5000, 20
SRC = ROOT / "testing" / "data" / "sources"
OUT = ROOT / "testing" / "data" / "is_A_needed.json"
rng = np.random.default_rng(20260811)


def paired_ci(a, b):
    n = len(a)
    k = int(np.ceil(n / BLOCK))
    diffs = []
    for lo in range(0, NBOOT, 500):
        m = min(500, NBOOT - lo)
        st = rng.integers(0, n, size=(m, k))
        idx = (st[:, :, None] + np.arange(BLOCK)[None, None, :]
               ).reshape(m, k * BLOCK)[:, :n] % n
        diffs.append(np.array([sortino(a[i]) - sortino(b[i]) for i in idx]))
    d = np.concatenate(diffs)
    d = d[np.isfinite(d)]
    return (round(float(sortino(a) - sortino(b)), 3),
            round(float(np.percentile(d, 2.5)), 3),
            round(float(np.percentile(d, 97.5)), 3),
            round(float((d > 0).mean() * 100), 1))


def main() -> int:
    out = {"fee_per_side_pct": FEE}
    for sym, f in (("BTC", "BTC_binance_warmup.parquet"), ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(SRC / f)
        ret = raw["close"].pct_change().fillna(0.0)
        pD, _ = build(raw, "dslope", 2)          # D and slope
        pA, _ = build(raw, "k", 3)               # A and D and slope
        idx = pD.index
        cl = raw["close"].reindex(idx).to_numpy(float)
        rr = ret.reindex(idx).to_numpy(float)

        mD, mA = metrics(pD, ret), metrics(pA, ret)
        print(f"\n{'='*84}\n{sym} · {len(idx)} dni\n{'='*84}")
        print(f"  {'':12}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
              f"{'izpost':>8}{'posl':>6}")
        for nm, m in (("D + naklon", mD), ("A + D + naklon", mA)):
            print(f"  {nm:<12}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%{m['maxdd']:>7.1f}%"
                  f"{m['final']:>6.2f}x{m['exposure']:>7.1f}%{m['trades']:>6d}")

        # 1 + 2. where does A bind, and what happened there
        blocked = (pD.to_numpy() > .5) & (pA.to_numpy() < .5)
        added = (pD.to_numpy() < .5) & (pA.to_numpy() > .5)
        runs = []
        for t in idx[blocked]:
            if runs and (t - runs[-1][1]).days == 1:
                runs[-1][1] = t
            else:
                runs.append([t, t])
        cum = float(np.prod(1 + rr[blocked]) - 1) * 100 if blocked.sum() else 0.0
        print(f"\n  A ZADRŽI VSTOP na {int(blocked.sum())} dneh v {len(runs)} epizodah"
              f"   (obratno: {int(added.sum())} dni)")
        print(f"  kumulativno gibanje cene v teh dneh: {cum:+.1f} %"
              f"   {'-> A je prihranil' if cum < 0 else '-> A je stal'}")
        eps = []
        for a, b in runs:
            w = (idx >= a) & (idx <= b)
            ch = float(np.prod(1 + rr[w]) - 1) * 100
            eps.append({"from": str(a.date()), "to": str(b.date()),
                        "days": int((b - a).days) + 1, "ret": round(ch, 1)})
            print(f"    {a.date()} – {b.date()}  {(b-a).days+1:>3} dni  {ch:+7.1f} %"
                  f"   {'prihranek' if ch < 0 else 'strošek'}")

        # 3. paired bootstrap
        rA = net_returns(pA, ret, FEE).to_numpy(float)
        rD = net_returns(pD, ret, FEE).to_numpy(float)
        d, lo, hi, frac = paired_ci(rA, rD)
        print(f"\n  ΔSortino (z A − brez A): {d:+.3f}   95 % IZ [{lo:+.3f}, {hi:+.3f}]"
              f"   nad nič v {frac:.0f} % vzorcev")
        print(f"    {'IZKLJUČUJE ničlo' if lo > 0 or hi < 0 else 'objame ničlo — A ni dokazljivo potreben'}")

        # 4. sub-periods
        print(f"\n  PODOBDOBJA        brez A     z A")
        wins = 0
        subs = {}
        for nm, a, b in SUBPERIODS:
            w = idx[(idx >= a) & (idx <= b)]
            if len(w) < 60:
                continue
            sD = sortino(net_returns(pD.reindex(w), ret, FEE).to_numpy(float))
            sA = sortino(net_returns(pA.reindex(w), ret, FEE).to_numpy(float))
            wins += int(sA > sD)
            subs[nm] = {"without_A": round(sD, 3), "with_A": round(sA, 3)}
            tag = "z A bolje" if sA > sD else ("enako" if abs(sA - sD) < 1e-9 else "brez A bolje")
            print(f"    {nm:<14}{sD:>9.3f}{sA:>8.3f}   {tag}")
        print(f"    z A bolje v {wins} od {len(subs)}")

        # 5. walk-forward between just these two
        print(f"\n  WALK-FORWARD med tema dvema")
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
                sD = sortino(net_returns(pD.reindex(w), ret, FEE).to_numpy(float))
                sA = sortino(net_returns(pA.reindex(w), ret, FEE).to_numpy(float))
                pick = "z A" if sA > sD else "brez A"
                t = idx[(idx > tb) & (idx <= eb)]
                picks.append(pick)
                segs.append((pA if pick == "z A" else pD).reindex(t))
                start = start + pd.DateOffset(years=te)
            if not segs:
                continue
            wf[f"{tr}y/{te}y"] = {"picks": picks,
                                  "refit": metrics(pd.concat(segs), ret)["sortino"]}
            print(f"    {tr}y/{te}y  izbire: {picks}")
        out[sym] = {"without_A": mD, "with_A": mA,
                    "A_blocks": {"days": int(blocked.sum()), "episodes": eps,
                                 "cum_move_pct": round(cum, 1),
                                 "reverse_days": int(added.sum())},
                    "delta_sortino": {"delta": d, "ci": [lo, hi], "pct_above_0": frac},
                    "subperiods": subs, "with_A_wins": wins, "walk_forward": wf}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
