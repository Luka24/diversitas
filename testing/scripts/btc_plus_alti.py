"""Luka's split: 50 % BTC, 10 % in each altcoin, and a separate altcoin rule.

The instinct behind a separate altcoin strategy is right. Lean's thresholds are
absolute, so a 3 % band is 0.92 daily sigma on BTC and 0.55 on LINK, which means
the wilder assets get whipsawed by a band that was never meant for them.

Two ways to adapt, and only one of them is a new idea:

  VOL SCALING   band and blow-off distance multiplied by the asset's volatility
                relative to BTC's. Measured, not chosen, the same normalisation
                already used for position size.

  BTC FILTER    the altcoin may only enter while BTC itself is above its 50-day
                EMA. This already exists in the config as use_btc_filter and has
                never been switched on. It encodes something true about crypto:
                altcoins follow bitcoin, so a bitcoin that is falling is a poor
                moment to be long anything else.

Weights are Luka's: BTC 50 %, each alt 10 %. HYPE cannot be computed, so its
10 % stays in cash, which is what would really happen.

    python testing/scripts/btc_plus_alti.py
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
VOL = {"BTC": 62, "ETH": 83, "SOL": 98, "LINK": 104}
WEIGHTS = {"BTC": 0.50, "ETH": 0.10, "SOL": 0.10, "LINK": 0.10}
ALTS = ("ETH", "SOL", "LINK")

_sm = dict(DEFAULT_CONFIG.symbol_map)
for s in ("SOL", "LINK"):
    _sm.setdefault(s, {"coinbase": f"{s}-USD", "yahoo": f"{s}-USD"})


class Cfg:
    symbol_map = _sm


def met(r: np.ndarray, promet: float) -> dict:
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    down = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return {"sortino": float(r.mean() * PPY / down),
            "cagr": float((eq[-1] ** (PPY / len(r)) - 1) * 100),
            "maxdd": float(dd.min() * 100), "final": float(eq[-1]), "turn": promet}


_CACHE: dict = {}


def surovi_podatki() -> dict:
    """Fetch once. Four variants times four assets is sixteen calls to Coinbase
    for data that does not change between them, and it starts resetting the
    connection."""
    if not _CACHE:
        for s in VOL:
            _CACHE[s] = fetch_candles(s, "1d", bars=3000, config=Cfg,
                                      prefer="coinbase", strict=True)
    return _CACHE


def signali(vol_skala: bool, btc_filter: bool):
    """One Lean per asset. BTC always runs the plain rules; only the altcoins
    are adapted, which is the whole point of the split."""
    surovi = surovi_podatki()
    btc_raw = surovi["BTC"]
    out = {}
    for s in VOL:
        je_alt = s in ALTS
        k = VOL[s] / VOL["BTC"] if (vol_skala and je_alt) else 1.0
        cfg = LeanConfig(track_buf_pct=3.0 * k, blowoff_dist_pct=25.0 * k,
                         use_btc_filter=bool(btc_filter and je_alt))
        d = trim_warmup(run_strategy(surovi[s],
                                     btc_daily=btc_raw if je_alt else None,
                                     config=cfg).df)
        out[s] = ((d["prev_signal_state"] == S_BULL).astype(float),
                  surovi[s]["close"].pct_change().reindex(d.index).fillna(0.0))
    return out


def tek(sig: dict, utezi: dict):
    """Fixed sleeves, no rebalancing, which is what won the earlier test."""
    syms = list(utezi)
    idx = sig[syms[0]][0].index
    for s in syms:
        idx = idx.intersection(sig[s][0].index)
    S = pd.DataFrame({s: sig[s][0].reindex(idx) for s in syms})
    R = pd.DataFrame({s: sig[s][1].reindex(idx) for s in syms})

    # Track sleeve VALUES, not shares. A first version let `w` grow unnormalised
    # and then used it directly as a portfolio fraction, so after BTC doubled the
    # position read 2.0 and the reference row showed -100 % drawdown on a
    # strategy that never lost that much. Shares have to be recomputed from
    # values every bar, and whatever is not in a sleeve is cash that earns
    # nothing.
    V = np.array([utezi[s] for s in syms], dtype=float)
    cash = 1.0 - V.sum()
    prej = np.zeros(len(syms))
    don, promet = [], 0.0
    for i in range(len(idx)):
        s_i, r_i = S.iloc[i].to_numpy(float), R.iloc[i].to_numpy(float)
        skupaj = V.sum() + cash
        w = V / skupaj                    # each sleeve's share of the portfolio
        poz = w * s_i                     # invested fraction
        p = float(np.abs(poz - prej).sum())
        promet += p
        don.append(float((poz * r_i).sum()) - p * FEE / 100)
        prej = poz
        V = V * (1 + s_i * r_i)           # sleeves drift, never rebalanced
    return np.array(don), promet, idx, S


def main() -> int:
    print("utezi: BTC 50 %, ETH 10 %, SOL 10 %, LINK 10 %, HYPE 10 % v gotovini\n")
    print(f"  {'':34s}{'Sortino':>9}{'letno':>8}{'MaxDD':>9}{'konec':>8}{'promet':>9}")

    osn = signali(False, False)
    r, p, idx, _ = tek({"BTC": osn["BTC"]}, {"BTC": 0.50})
    m = met(r, p)
    print(f"  {'samo BTC pri 50 %':34s}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
          f"{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{m['turn']:>9.1f}")
    r, p, idx, _ = tek({"BTC": osn["BTC"]}, {"BTC": 1.00})
    m = met(r, p)
    print(f"  {'samo BTC pri 100 % (referenca)':34s}{m['sortino']:>9.3f}"
          f"{m['cagr']:>7.1f}%{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{m['turn']:>9.1f}")

    print()
    for oznaka, vs, bf in (("A  ista pravila povsod", False, False),
                           ("B  alti: pragovi po volatilnosti", True, False),
                           ("C  alti: filter BTC", False, True),
                           ("D  alti: oboje", True, True)):
        sig = signali(vs, bf)
        r, p, idx, S = tek(sig, WEIGHTS)
        m = met(r, p)
        print(f"  {oznaka:34s}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
              f"{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{m['turn']:>9.1f}")

    sig = signali(True, True)
    _, _, idx, S = tek(sig, WEIGHTS)
    print(f"\n  okno {idx[0].date()} do {idx[-1].date()}, {len(idx)} dni")
    print("  koliko casa je vsak v poziciji, pri razlicici D:")
    for s in WEIGHTS:
        print(f"    {s:5s} {float(S[s].mean()*100):5.1f} %")
    izpo = float((S * pd.Series(WEIGHTS)).sum(axis=1).mean() * 100)
    print(f"  povprecna izpostavljenost portfelja: {izpo:.1f} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
