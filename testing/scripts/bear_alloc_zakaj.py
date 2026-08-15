"""A floor loses on every measure since 2021. So when would it not?

The sweep says hold nothing while the signal is out. That is an answer about
this signal on this history. It does not answer the question underneath, which
is what the floor is actually for.

A floor is insurance against the signal being wrong. If the timing carries no
information, the strategy is just a random sampler of a rising market and any
permanent exposure pays. If the timing is good, the floor only drags. So there
is a break-even level of signal quality, and knowing where it sits is worth more
than knowing that 0 % won.

Three measurements:

  1. WHAT DO WE MISS. The largest rallies that happened while flat, which is the
     scenario a floor is meant to cushion.
  2. WHERE IS THE BREAK-EVEN. Degrade the signal by blending it with a random
     one of the same frequency, and find the mix at which a 10 % floor starts to
     beat 0 %.
  3. WHAT IF THE SIGNAL IS WORTHLESS. Circular-shift the signal so it keeps its
     frequency and clustering but points at the wrong days, then re-run the
     sweep. If the optimal floor jumps, the floor is precisely a hedge against
     the signal failing.

    python testing/scripts/bear_alloc_zakaj.py
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
from model.strategy import S_BULL, net_returns, run_strategy, trim_warmup

FEE, PPY = 0.30, 365
START = "2021-01-01"
rng = np.random.default_rng(20260815)


def sortino(r: np.ndarray) -> float:
    down = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / down) if down else float("nan")


def score(sig: pd.Series, ret: pd.Series, b: float) -> float:
    pos = b + (1 - b) * sig
    return sortino(net_returns(pos, ret, FEE).to_numpy(float))


def main() -> int:
    for sym, fname in (("BTC", "BTC_coinbase.parquet"), ("ETH", "ETH_coinbase.parquet")):
        raw = pd.read_parquet(LEAN / "data" / fname)
        d = trim_warmup(run_strategy(raw, config=LeanConfig()).df)
        m = d.index >= START
        sig = (d["prev_signal_state"] == S_BULL).astype(float)[m]
        ret = raw["close"].pct_change().reindex(d.index).fillna(0.0)[m]
        close = raw["close"].reindex(sig.index)

        print(f"\n{'=' * 82}\n{sym}   {sig.index[0].date()} do {sig.index[-1].date()}"
              f"   v trgu {sig.mean()*100:.0f} % dni\n{'=' * 82}")

        # 1 ─ what a floor would have cushioned
        print("\n1. NAJVECJI ZAMUJENI VZPONI  (30-dnevni, ko smo bili zunaj cel cas)")
        flat = sig == 0
        cand = []
        for i in range(len(close) - 30):
            if flat.iloc[i:i + 30].all():
                cand.append((close.index[i].date(),
                             float(close.iloc[i + 30] / close.iloc[i] - 1) * 100))
        cand.sort(key=lambda x: -x[1])
        for dt, g in cand[:3]:
            print(f"   od {dt}   {g:+6.1f} %   pri 10 % pragu bi vzel {g*0.10:+5.1f} %")
        if cand:
            print(f"   najhujsi zamujeni: {cand[0][1]:+.1f} %"
                  f"   povprecje vseh takih oken: {np.mean([g for _, g in cand]):+.1f} %")

        # 2 ─ how bad must the signal get before a floor wins
        print("\n2. PRELOMNA TOCKA  (signal zmesan z nakljucnim iste pogostosti)")
        print(f"   {'kvaliteta':>10}{'Sortino 0 %':>13}{'Sortino 10 %':>14}{'zmagovalec':>12}")
        n = len(sig)
        for q in (1.0, 0.75, 0.5, 0.25, 0.0):
            s0, s10 = [], []
            for _ in range(40):
                nak = pd.Series(rng.permutation(sig.to_numpy()), index=sig.index)
                mix = pd.Series(np.where(rng.random(n) < q, sig, nak), index=sig.index)
                s0.append(score(mix, ret, 0.0))
                s10.append(score(mix, ret, 0.10))
            a, b = float(np.mean(s0)), float(np.mean(s10))
            print(f"   {q*100:>9.0f}%{a:>13.3f}{b:>14.3f}{'0 %' if a > b else '10 %':>12}")

        # 3 ─ if the timing is worthless
        print("\n3. ZAVRTEN SIGNAL  (ista pogostost in grucenje, napacni dnevi)")
        best = []
        g = sig.to_numpy()
        for k in rng.integers(1, n, size=120):
            rot = pd.Series(np.roll(g, int(k)), index=sig.index)
            best.append(max((0.0, 0.10, 0.20, 0.30, 0.50),
                            key=lambda b: score(rot, ret, b)))
        vals, cnt = np.unique(best, return_counts=True)
        print("   najboljsi prag pri zavrtenem signalu: "
              + ", ".join(f"{v*100:.0f} % v {c/len(best)*100:.0f} % primerov"
                          for v, c in zip(vals, cnt)))
        print(f"   pri pravem signalu: 0 %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
