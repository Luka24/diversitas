"""Would running Lean on five assets diversify anything?

The appeal of five assets is that five bets should beat one. That only holds if
the bets are different. In crypto they largely are not: altcoins follow bitcoin,
and a trend signal on each of them tends to fire at the same time, so five
positions can be one position wearing five hats.

Measured here, before any portfolio is built:

  1. RETURN CORRELATION between the assets.
  2. SIGNAL OVERLAP: how often the strategy holds them simultaneously. This is
     the number that decides whether the portfolio is diversified, not the
     return correlation, because the strategy is only exposed when long.
  3. WHAT A NAIVE EQUAL-WEIGHT PORTFOLIO ACTUALLY DOES against BTC alone, on
     the window where all the assets exist.

HYPE is excluded throughout: it has 194 daily bars on Coinbase and the strategy
needs 220 for the 200-day regime average, so it cannot be computed at all.

    python testing/scripts/vec_sredstev.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAN = ROOT.parent / "diversitas-lean"
for p in (ROOT, LEAN):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from model.config import DEFAULT_CONFIG, LeanConfig
from model.data_source import fetch_candles
from model.strategy import S_BULL, net_returns, run_strategy, trim_warmup

FEE, PPY = 0.30, 365
SYMS = ("BTC", "ETH", "SOL", "LINK")

_sm = dict(DEFAULT_CONFIG.symbol_map)
for s in ("SOL", "HYPE", "LINK"):
    _sm.setdefault(s, {"coinbase": f"{s}-USD", "yahoo": f"{s}-USD"})


class Cfg:
    symbol_map = _sm


def sortino(r: np.ndarray) -> float:
    down = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / down) if down else float("nan")


def stats(r: np.ndarray) -> dict:
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    return {"sortino": sortino(r),
            "cagr": float((eq[-1] ** (PPY / len(r)) - 1) * 100),
            "maxdd": float(dd.min() * 100), "final": float(eq[-1])}


def main() -> int:
    cfg = LeanConfig()
    pos, ret = {}, {}
    for s in SYMS:
        raw = fetch_candles(s, "1d", bars=3000, config=Cfg, prefer="coinbase", strict=True)
        d = trim_warmup(run_strategy(raw, config=cfg).df)
        pos[s] = (d["prev_signal_state"] == S_BULL).astype(float)
        ret[s] = raw["close"].pct_change().reindex(d.index).fillna(0.0)
        print(f"  {s:5s} {len(d):5d} dni po zaletu   {d.index[0].date()} do {d.index[-1].date()}")

    idx = pos[SYMS[0]].index
    for s in SYMS[1:]:
        idx = idx.intersection(pos[s].index)
    print(f"\nskupno okno vseh stirih: {idx[0].date()} do {idx[-1].date()}   {len(idx)} dni")

    R = pd.DataFrame({s: ret[s].reindex(idx) for s in SYMS})
    P = pd.DataFrame({s: pos[s].reindex(idx) for s in SYMS})

    print("\n1. KORELACIJA DNEVNIH DONOSOV")
    c = R.corr()
    print("        " + "".join(f"{s:>8}" for s in SYMS))
    for a in SYMS:
        print(f"  {a:5s} " + "".join(f"{c.loc[a,b]:>8.2f}" for b in SYMS))

    print("\n2. PREKRIVANJE SIGNALOV  (delez dni, ko sta OBA v poziciji)")
    print("        " + "".join(f"{s:>8}" for s in SYMS))
    for a in SYMS:
        vrstica = []
        for b in SYMS:
            skupaj = float(((P[a] > 0) & (P[b] > 0)).mean() * 100)
            vrstica.append(f"{skupaj:>7.0f}%")
        print(f"  {a:5s} " + "".join(vrstica))
    print("\n  koliko sredstev drzimo hkrati:")
    n = P.sum(axis=1)
    for k in range(5):
        print(f"    {k}: {float((n == k).mean() * 100):5.1f} % dni")
    print(f"  povprecno hkrati: {float(n.mean()):.2f} od 4")

    print("\n3. PORTFELJ PROTI SAMEMU BTC  (enake utezi, provizija 0,30 %/stran)")
    print(f"  {'':22s}{'Sortino':>9}{'letno':>8}{'MaxDD':>9}{'konec':>8}{'v trgu':>9}")
    for oznaka, w in (("samo BTC", {"BTC": 1.0}),
                      ("BTC + ETH", {"BTC": .5, "ETH": .5}),
                      ("vsi stirje", {s: .25 for s in SYMS})):
        r = np.zeros(len(idx))
        expo = 0.0
        for s, wt in w.items():
            p = P[s] * wt
            r = r + net_returns(p, R[s], FEE).to_numpy(float)
            expo += float(p.mean())
        m = stats(r)
        print(f"  {oznaka:22s}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
              f"{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{expo*100:>8.1f}%")

    print("\n  posamezno, vsak sam zase na tem oknu:")
    for s in SYMS:
        m = stats(net_returns(P[s], R[s], FEE).to_numpy(float))
        print(f"  {s:22s}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
              f"{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{float(P[s].mean())*100:>8.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
