"""Two different things drift, and only one of them should make you trade.

When a sleeve holds a winner, its share of the portfolio grows. A classic
rebalancing band says trim it back. But trend following says let winners run,
and the literature agrees that rebalancing in trending markets hurts.

CTAs resolve this by never rebalancing to fixed weights at all. They resize by
VOLATILITY, which is a different operation with a different trigger:

    weight band     triggers on PROFIT       trims winners, fights the trend
    volatility      triggers on RISK         trims when the ride gets rough

Those coincide only when a rising price comes with rising volatility. Whether it
does is an empirical question, measured below, and it decides whether the two
rules are cousins or opposites.

Four ways of running the same sleeves, on the same signals:

  A  no rebalancing      sleeves drift with performance, forever
  B  band on weight      trim back to the band edge when a sleeve exits it
  C  band on volatility  resize the sleeve when its own vol moves out of band
  D  monthly reset       everything back to target on the first of the month

    python testing/scripts/pas.py
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
SYMS = ("BTC", "ETH", "SOL", "LINK")
VOLS = {"BTC": 0.62, "ETH": 0.83, "SOL": 0.98, "LINK": 1.04}
PAS = 0.05          # 5 odstotnih tock okoli cilja

_sm = dict(DEFAULT_CONFIG.symbol_map)
for s in ("SOL", "LINK"):
    _sm.setdefault(s, {"coinbase": f"{s}-USD", "yahoo": f"{s}-USD"})


class Cfg:
    symbol_map = _sm


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d else float("nan")


def stats(r, promet):
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    return {"sortino": sortino(r), "cagr": float((eq[-1] ** (PPY / len(r)) - 1) * 100),
            "maxdd": float(dd.min() * 100), "final": float(eq[-1]),
            "turn": float(promet)}


def tek(S: pd.DataFrame, R: pd.DataFrame, cilj: dict, nacin: str, V=None):
    """Sleeve accounting, one bar at a time. `w` is each sleeve's share of the
    whole portfolio, and it grows with the sleeve's own return."""
    syms = list(S.columns)
    w = np.array([cilj[s] for s in syms], dtype=float)
    donosi, promet_skupaj = [], 0.0
    prej_mesec = None
    # The invested position is sleeve x signal. Cost is charged on changes to
    # THAT, so a signal switching on pays just as a rebalance does. Charging
    # only for rebalancing, as an earlier version of this did, made "never
    # rebalance" look free when it still trades every time a signal flips.
    prej_poz = np.zeros(len(syms))

    for i, ts in enumerate(S.index):
        sig = S.iloc[i].to_numpy(float)
        r = R.iloc[i].to_numpy(float)

        poz = w * sig
        promet_sig = float(np.abs(poz - prej_poz).sum())
        promet_skupaj += promet_sig

        d = float((poz * r).sum()) - promet_sig * FEE / 100
        donosi.append(d)
        prej_poz = poz

        # grow the sleeves
        w = w * (1 + sig * r)
        w = w / w.sum() if w.sum() > 0 else w

        cilj_v = np.array([cilj[s] for s in syms])
        nova = w.copy()
        if nacin == "pas_utez":
            zgoraj, spodaj = cilj_v + PAS, cilj_v - PAS
            nova = np.where(w > zgoraj, zgoraj, np.where(w < spodaj, spodaj, w))
        elif nacin == "pas_vol" and V is not None:
            # resize on the sleeve's OWN volatility, not on its profit
            vol = V.iloc[i].to_numpy(float)
            osnova = np.array([VOLS[s] for s in syms])
            faktor = osnova / np.clip(vol, 0.15, None)
            zelen = cilj_v * faktor
            zelen = zelen / zelen.sum()
            zunaj = np.abs(w - zelen) > PAS
            nova = np.where(zunaj, zelen, w)
        elif nacin == "mesecno":
            if prej_mesec is not None and ts.month != prej_mesec:
                nova = cilj_v.copy()
            prej_mesec = ts.month

        if nova.sum() > 0:
            nova = nova / nova.sum()
        # rebalancing turnover is charged on the invested part only
        prom = float((np.abs(nova - w) * sig).sum())
        promet_skupaj += prom
        donosi[-1] -= prom * FEE / 100
        prej_poz = nova * sig
        w = nova

    return np.array(donosi), promet_skupaj


def main() -> int:
    S, R, V = {}, {}, {}
    for s in SYMS:
        raw = fetch_candles(s, "1d", bars=3000, config=Cfg, prefer="coinbase", strict=True)
        d = trim_warmup(run_strategy(raw, config=LeanConfig()).df)
        S[s] = (d["prev_signal_state"] == S_BULL).astype(float)
        r = raw["close"].pct_change().reindex(d.index).fillna(0.0)
        R[s] = r
        V[s] = (r.rolling(20).std() * np.sqrt(PPY)).shift(1)

    idx = S[SYMS[0]].index
    for s in SYMS:
        idx = idx.intersection(S[s].index)
    S = pd.DataFrame({s: S[s].reindex(idx) for s in SYMS})
    R = pd.DataFrame({s: R[s].reindex(idx) for s in SYMS})
    V = pd.DataFrame({s: V[s].reindex(idx) for s in SYMS}).bfill()

    inv = {s: 1 / VOLS[s] for s in SYMS}
    tot = sum(inv.values())
    cilj = {s: inv[s] / tot for s in SYMS}
    print(f"okno {idx[0].date()} do {idx[-1].date()}   {len(idx)} dni")
    print("ciljne utezi: " + "  ".join(f"{s} {cilj[s]*100:.1f} %" for s in SYMS))

    print("\n1. ALI VISJA CENA POMENI VISJO VOLATILNOST?")
    print("   (ce da, sta pas na utez in pas na volatilnost sorodna; ce ne, sta nasprotna)")
    for s in SYMS:
        d30 = R[s].rolling(30).sum()
        v30 = V[s]
        k = float(pd.concat([d30, v30], axis=1).dropna().corr().iloc[0, 1])
        print(f"   {s:5s} korelacija med 30-dnevnim donosom in volatilnostjo: {k:+.3f}")

    print(f"\n2. NACINI URAVNOTEZENJA  (provizija {FEE} %/stran)")
    print(f"  {'':26s}{'Sortino':>9}{'letno':>8}{'MaxDD':>9}{'konec':>8}{'promet':>9}")
    for oznaka, nacin in (("A  brez uravnotezenja", "nic"),
                          ("B  pas na utez", "pas_utez"),
                          ("C  pas na volatilnost", "pas_vol"),
                          ("D  mesecni reset", "mesecno")):
        r, prom = tek(S, R, cilj, nacin, V)
        m = stats(r, prom)
        print(f"  {oznaka:26s}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
              f"{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{m['turn']:>9.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
