"""Entry on a MAJORITY of the trend conditions instead of all of them.

Follows the two-trackline test, which found that requiring both trackline rules
is never worth the second condition, but where the Model Confidence Set retained
all five cells and so could not separate anything.

That leaves an option the earlier test did not cover: keep both rules but stop
requiring every condition at once. With three trend conditions available —

    A      close > mid(75) + 3 % of price       today's gate
    D      close > mid(20) + 25 % of range(20)  Donchian, as a trackline
    slope  the 75-day trackline is rising

— the cells are "at least k of three", k in 1, 2, 3.

regime_ok and the blow-off veto stay HARD requirements in every cell and are
never put to the vote. Making the bear-market block optional would let the
strategy buy inside a confirmed bear market, which is a change to the risk
profile rather than to the entry timing, and it is not what is being asked here.

Three additions the previous test lacked:

  A downside-penalised loss for the MCS. Running it on mean return alone can only
  see mean return, so two variants with the same average and very different
  drawdowns look identical. L = -r + 2*min(r,0)^2 keeps the ranking sensitive to
  the left tail.

  A circular shift for the leading cell, the same placebo Donchian had to pass:
  rotate the gate series, keeping its frequency and clustering while destroying
  its alignment with price.

  An explicit indicator count, because the previous write-up got this wrong. The
  75-day trackline is required by the exit, by the slope condition and by the
  blow-off distance, so any cell using D computes BOTH channels. D replaces a
  condition, never an indicator.

Output: testing/data/majority_vote.json
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

from shared import indicators as ind
from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from testing.scripts import engine
from testing.scripts.two_tracklines import (conditions, sortino, maxdd, mcs,
                                            FEE, PPY, SUBPERIODS)

np.seterr(all="ignore")

SRC = ROOT / "testing" / "data" / "sources"
OUT = ROOT / "testing" / "data" / "majority_vote.json"
N_SHIFT = 1000
rng = np.random.default_rng(20260810)

CELLS = {
    "danes  A&naklon":  ("today", 2),
    "vsi trije 3/3":    ("k", 3),
    "vecina    2/3":    ("k", 2),
    "vsaj eden 1/3":    ("k", 1),
    "D&naklon":         ("dslope", 2),
}


def gate_series(raw, df):
    A, D = conditions(raw, df.index)
    slope = df["track_rising_window"].fillna(False)
    return A, D, slope


def build(raw, kind, k):
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    A, D, slope = gate_series(raw, df)
    if kind == "today":
        gate = A & slope
    elif kind == "dslope":
        gate = D & slope
    else:
        gate = (A.astype(int) + D.astype(int) + slope.astype(int)) >= k
    # regime and blow-off are never voted on
    df["bull_condition"] = (gate & df["regime_ok"] & df["btc_filter_ok"]
                            & ~df["blowoff"]).fillna(False)
    st = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos, gate.reindex(st.index)


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


def main() -> int:
    out = {"fee_per_side_pct": FEE, "n_shift": N_SHIFT}
    for sym, f in (("BTC", "BTC_binance_warmup.parquet"), ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(SRC / f)
        ret = raw["close"].pct_change().fillna(0.0)
        pos, gates = {}, {}
        for name, (kind, k) in CELLS.items():
            pos[name], gates[name] = build(raw, kind, k)
        idx = next(iter(pos.values())).index

        print(f"\n{'='*96}\n{sym} · {len(idx)} dni\n{'='*96}")
        print(f"  {'celica':<18}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
              f"{'izpost':>8}{'posl':>6}{'kanalov':>9}    I     II    III    IV")
        res = {}
        for name in CELLS:
            m = metrics(pos[name], ret)
            sub = {}
            for nm, a, b in SUBPERIODS:
                w = idx[(idx >= a) & (idx <= b)]
                sub[nm] = (round(sortino(net_returns(pos[name].reindex(w), ret, FEE)
                                         .to_numpy(float)), 2) if len(w) > 60 else None)
            m["sub"] = sub
            # the 75-day channel is always needed (exit, slope, blow-off);
            # anything touching D needs the 20-day channel as well
            m["channels"] = 2 if ("D" in name or "/3" in name) else 1
            res[name] = m
            s = "  ".join(f"{v:5.2f}" if v is not None else "    —" for v in sub.values())
            print(f"  {name:<18}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%{m['maxdd']:>7.1f}%"
                  f"{m['final']:>6.2f}x{m['exposure']:>7.1f}%{m['trades']:>6d}"
                  f"{m['channels']:>9}  {s}")

        # ── MCS on a downside-penalised loss ────────────────────────────────
        names = list(CELLS)
        R = np.vstack([net_returns(pos[n], ret, FEE).to_numpy(float) for n in names])
        loss_mean = -R
        loss_down = -R + 2.0 * np.minimum(R, 0.0) ** 2
        for tag, L in (("povprecen donos", loss_mean), ("s kaznijo za padce", loss_down)):
            keep, elim = mcs(L, names)
            print(f"\n  MCS ({tag}): preživele {len(keep)}/5 → {', '.join(keep)}")
            if elim:
                print(f"      izločene: {', '.join(f'{n} (p={p})' for n, p in elim)}")
            out.setdefault(sym, {}).setdefault("mcs", {})[tag] = {
                "kept": keep, "eliminated": elim}

        # ── circular shift on the leading cell ──────────────────────────────
        best = max(res, key=lambda k: res[k]["sortino"])
        cfg = engine.make_config("lean")
        smod = engine.strategy_module("lean")
        df = smod.compute_features(raw, None, cfg)
        g = gates[best].reindex(df.index).fillna(False).to_numpy()
        sims = []
        for _ in range(N_SHIFT):
            f2 = df.copy()
            f2["bull_condition"] = (pd.Series(np.roll(g, int(rng.integers(60, len(g) - 60))),
                                              index=df.index)
                                    & f2["regime_ok"] & f2["btc_filter_ok"]
                                    & ~f2["blowoff"]).fillna(False)
            st = trim_warmup(smod.run_state_machine(f2, cfg))
            p = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
            sims.append(sortino(net_returns(p, ret, FEE).to_numpy(float)))
        sims = np.array([x for x in sims if np.isfinite(x)])
        real = res[best]["sortino"]
        pct = float((sims < real).mean() * 100)
        out[sym]["shift"] = {"cell": best, "real": real, "n": int(sims.size),
                             "mean": round(float(sims.mean()), 3),
                             "p05": round(float(np.percentile(sims, 5)), 3),
                             "p95": round(float(np.percentile(sims, 95)), 3),
                             "percentile": round(pct, 1)}
        print(f"\n  NAKLJUČNI ZAMIK vodilne celice «{best}» ({N_SHIFT} rotacij)")
        print(f"    pravi {real:.3f}   zamaknjeni povpr. {sims.mean():.3f}   "
              f"5–95 % [{np.percentile(sims,5):.3f}, {np.percentile(sims,95):.3f}]")
        print(f"    pravi je na {pct:.1f}. percentilu")
        out[sym]["cells"] = res

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
