"""Does the 5 % floor stay at 5 %, or does it drift with the price?

position() returns a constant 0.05 while the signal is out. A constant weight
means the holding is rebalanced back to 5 % every single day, and because the
series never changes, turnover() sees no movement and charges nothing for it.
So the current model rebalances daily and gets it for free.

That matters more than the size of the floor suggests. In the longest flat
stretch, 409 days from December 2021, BTC fell 58 %. Holding a constant 5 %
through that means buying on the way down, every day, all the way to the bottom.

Three readings of "keep 5 % in BTC", priced honestly:

  A  constant 5 %, free        what the code does now
  B  constant 5 %, paid        same holding, rebalancing charged at 0.30 %/side
  C  drift                     sell down to 5 % at the exit, then leave it
                               alone until the next entry

C is the plain reading of "an exit sells 95 %". A and B are a standing
instruction to hold exactly 5 % forever.

    python testing/scripts/prag_drift.py
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

from model.config import LeanConfig
from model.strategy import S_BULL, run_strategy, trim_warmup

FEE, PPY = 0.30, 365
FLOOR = 0.05


def met(r: np.ndarray, promet: float, expo: float) -> dict:
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    down = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return {"sortino": float(r.mean() * PPY / down),
            "cagr": float((eq[-1] ** (PPY / len(r)) - 1) * 100),
            "maxdd": float(dd.min() * 100), "final": float(eq[-1]),
            "expo": expo, "turn": promet}


def konstanten(bull, ret, placaj: bool):
    """Weight pinned at 5 % when flat, 100 % when long."""
    pos = FLOOR + (1 - FLOOR) * bull
    r = pos * ret
    # The signal switch always costs. Whether the daily rebalancing inside a
    # flat stretch costs is the question this function answers.
    prom = np.abs(np.diff(pos, prepend=pos[0]))
    if placaj:
        # holding a constant fraction of a moving asset means trading it back
        # every day: the drift that has to be undone is weight x return
        prom = prom + np.abs(pos * ret) * (pos < 1)
    return r - prom * FEE / 100, float(prom.sum()), float(pos.mean() * 100)


def drift(bull, ret):
    """Sell down to 5 % at the exit, then leave it. The sleeve moves with the
    price and the cash does not, so the share drifts."""
    n = len(bull)
    v_btc, v_cash = (1.0, 0.0) if bull[0] else (FLOOR, 1 - FLOOR)
    don, prom_skupaj, delezi = [], 0.0, []
    prej_bull = bull[0]
    for i in range(n):
        # Rebalance FIRST, then earn. `bull` is already yesterday's signal, so
        # bull[i] is the allocation to hold ON day i. A first version checked for
        # the switch at the END of the bar, which held the old allocation through
        # the day the signal changed and put a second one-day lag on top of the
        # one already there. The control test caught it: at a 0 % floor this
        # function must reproduce the constant-weight one exactly, and it did not.
        prom = 0.0
        if bull[i] != prej_bull:
            skupaj = v_btc + v_cash
            cilj = skupaj if bull[i] else FLOOR * skupaj
            prom = abs(cilj - v_btc) / skupaj
            prom_skupaj += prom
            v_btc, v_cash = cilj, skupaj - cilj
            prej_bull = bull[i]

        skupaj = v_btc + v_cash
        delez = v_btc / skupaj
        delezi.append(delez)
        don.append(delez * ret[i] - prom * FEE / 100)
        v_btc *= (1 + ret[i])                      # only the sleeve moves
    return np.array(don), prom_skupaj, float(np.mean(delezi) * 100), np.array(delezi)


def main() -> int:
    for sym, f in (("BTC", "BTC_coinbase.parquet"), ("ETH", "ETH_coinbase.parquet")):
        raw = pd.read_parquet(LEAN / "data" / f)
        df = trim_warmup(run_strategy(raw, config=LeanConfig()).df)
        bull = (df["prev_signal_state"] == S_BULL).to_numpy().astype(float)
        ret = raw["close"].pct_change().reindex(df.index).fillna(0.0).to_numpy()

        print(f"\n{'=' * 88}\n{sym}   {df.index[0].date()} do {df.index[-1].date()}"
              f"   {len(df)} dni\n{'=' * 88}")
        print(f"  {'':32s}{'Sortino':>9}{'letno':>8}{'MaxDD':>9}"
              f"{'konec':>9}{'v trgu':>9}{'promet':>9}")

        rA, pA, eA = konstanten(bull, ret, placaj=False)
        rB, pB, eB = konstanten(bull, ret, placaj=True)
        rC, pC, eC, delezi = drift(bull, ret)
        for oznaka, r, p, e in (("A  konstantnih 5 %, brezplacno", rA, pA, eA),
                                ("B  konstantnih 5 %, s stroski", rB, pB, eB),
                                ("C  pusti teci (5 % ob izstopu)", rC, pC, eC)):
            m = met(r, p, e)
            print(f"  {oznaka:32s}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
                  f"{m['maxdd']:>8.1f}%{m['final']:>8.2f}x{m['expo']:>8.1f}%"
                  f"{m['turn']:>9.1f}")

        zunaj = delezi[bull == 0]
        print(f"\n  pri C se delez, ko smo zunaj, giblje med "
              f"{zunaj.min()*100:.1f} % in {zunaj.max()*100:.1f} %, povprecno "
              f"{zunaj.mean()*100:.1f} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
