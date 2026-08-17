"""How the capital is shared matters more than which assets are in the basket.

The naive version gives each asset a fixed 1/N and leaves the rest in cash. With
four assets that are each long only 12-35 % of the time, the portfolio ends up
invested 22.5 % of days, and most of the loss against BTC alone is that idle
capital rather than the extra assets.

What CTAs actually do is size positions by risk and spend the whole budget on
whatever is currently trending. Four ways of sharing the same signals:

  A  fixed 1/N        each asset gets 25 %, rest cash        (the naive one)
  B  redistribute     split capital across the assets that
                      are long right now, so the portfolio is
                      fully invested whenever anything fires
  C  inverse vol      redistribute, but weight by 1/sigma so
                      a quiet asset gets more than a wild one
  D  vol target       redistribute and scale the whole book
                      to a fixed annual volatility, capped at 1

None of these use leverage: total weight never exceeds 1.

    python testing/scripts/vec_sredstev_2.py
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
from model.strategy import S_BULL, run_strategy, trim_warmup

FEE, PPY = 0.30, 365
VOL_LB, VOL_TARGET = 20, 0.50

_sm = dict(DEFAULT_CONFIG.symbol_map)
for s in ("SOL", "HYPE", "LINK"):
    _sm.setdefault(s, {"coinbase": f"{s}-USD", "yahoo": f"{s}-USD"})


class Cfg:
    symbol_map = _sm


def sortino(r):
    down = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / down) if down else float("nan")


def stats(r, W):
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    return {"sortino": sortino(r),
            "cagr": float((eq[-1] ** (PPY / len(r)) - 1) * 100),
            "maxdd": float(dd.min() * 100), "final": float(eq[-1]),
            "expo": float(W.sum(axis=1).mean() * 100),
            "turn": float(W.diff().abs().sum(axis=1).fillna(0).sum())}


def portfelj(W: pd.DataFrame, R: pd.DataFrame) -> np.ndarray:
    """Weights are held from the day AFTER they are set, and each change in a
    weight pays the fee, so switching between assets costs both legs."""
    bruto = (W * R).sum(axis=1).to_numpy(float)
    promet = W.diff().abs().sum(axis=1).fillna(0.0).to_numpy(float)
    return bruto - promet * FEE / 100


def main() -> int:
    cfg = LeanConfig()
    P, R, V = {}, {}, {}
    for s in ("BTC", "ETH", "SOL", "LINK"):
        raw = fetch_candles(s, "1d", bars=3000, config=Cfg, prefer="coinbase", strict=True)
        d = trim_warmup(run_strategy(raw, config=cfg).df)
        P[s] = (d["prev_signal_state"] == S_BULL).astype(float)
        r = raw["close"].pct_change().reindex(d.index).fillna(0.0)
        R[s] = r
        V[s] = r.rolling(VOL_LB).std().shift(1) * np.sqrt(PPY)

    idx = P["BTC"].index
    for s in P:
        idx = idx.intersection(P[s].index)
    P = pd.DataFrame({s: P[s].reindex(idx) for s in P})
    R = pd.DataFrame({s: R[s].reindex(idx) for s in R})
    V = pd.DataFrame({s: V[s].reindex(idx) for s in V}).bfill().clip(lower=0.10)
    n = P.shape[1]

    print(f"okno {idx[0].date()} do {idx[-1].date()}   {len(idx)} dni   "
          f"provizija {FEE} %/stran\n")

    # A fiksno 1/N
    WA = P / n
    # B prerazporeditev na aktivne
    aktivnih = P.sum(axis=1).replace(0, np.nan)
    WB = P.div(aktivnih, axis=0).fillna(0.0)
    # C obratna volatilnost
    inv = (1.0 / V) * P
    WC = inv.div(inv.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    # D ciljna volatilnost, brez vzvoda
    port_vol = (WC * V).sum(axis=1).replace(0, np.nan)
    skala = (VOL_TARGET / port_vol).clip(upper=1.0).fillna(0.0)
    WD = WC.mul(skala, axis=0)

    # referenca: samo BTC
    WBTC = pd.DataFrame({"BTC": P["BTC"]}).reindex(columns=P.columns).fillna(0.0)

    print(f"  {'':26s}{'Sortino':>9}{'letno':>8}{'MaxDD':>9}{'konec':>8}"
          f"{'v trgu':>9}{'promet':>9}")
    vrstice = [("samo BTC (referenca)", WBTC),
               ("A  fiksno 1/N", WA),
               ("B  prerazporeditev", WB),
               ("C  obratna volatilnost", WC),
               ("D  ciljna volatilnost", WD)]
    for oznaka, W in vrstice:
        m = stats(portfelj(W, R), W)
        print(f"  {oznaka:26s}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
              f"{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{m['expo']:>8.1f}%{m['turn']:>9.1f}")

    print("\n  brez LINK, ki je na tem oknu izgubljal:")
    tri = ["BTC", "ETH", "SOL"]
    P3, R3, V3 = P[tri], R[tri], V[tri]
    a3 = P3.sum(axis=1).replace(0, np.nan)
    WB3 = P3.div(a3, axis=0).fillna(0.0)
    inv3 = (1.0 / V3) * P3
    WC3 = inv3.div(inv3.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    for oznaka, W in (("B  prerazporeditev", WB3), ("C  obratna volatilnost", WC3)):
        m = stats(portfelj(W, R3), W)
        print(f"  {oznaka:26s}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
              f"{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{m['expo']:>8.1f}%{m['turn']:>9.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
