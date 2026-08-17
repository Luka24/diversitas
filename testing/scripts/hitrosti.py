"""An ensemble of speeds, when the strategy already mixes timeframes internally.

A classic CTA ensemble runs ONE rule at several lookbacks and averages. Lean is
not one rule: it is four conditions, each with its own horizon, doing different
jobs. 20 days triggers the entry, 75 defines the trend and drives the exit, 200
decides the regime, 14 spots overheating. Those are not four speeds of the same
thing, so "average them" has no obvious meaning.

The version that does have a meaning is to give the WHOLE strategy a speed and
keep the internal ratios. 20:75:200 is 1:3.75:10, so a half-speed copy is
10:38:100 and a double-speed copy is 40:150:400. Then combine the three copies.

Two ways to combine, and the difference matters:

  AVERAGE   position is 0, 1/3, 2/3 or 1. Smooth, but no longer binary, which
            breaks the operational constraint this project runs under.
  MAJORITY  in when at least two of three say in. Stays binary.

RSI stays at 14 in every copy. It is paired with a hard threshold of 80, so
scaling the length while the threshold stands still would measure the
interaction rather than the speed.

    python testing/scripts/hitrosti.py
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
SPEEDS = (0.5, 1.0, 2.0)

_sm = dict(DEFAULT_CONFIG.symbol_map)
for s in ("SOL", "LINK"):
    _sm.setdefault(s, {"coinbase": f"{s}-USD", "yahoo": f"{s}-USD"})


class Cfg:
    symbol_map = _sm


def sortino(r):
    down = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / down) if down else float("nan")


def stats(r, pos):
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    return {"sortino": sortino(r),
            "cagr": float((eq[-1] ** (PPY / len(r)) - 1) * 100),
            "maxdd": float(dd.min() * 100), "final": float(eq[-1]),
            "expo": float(pos.mean() * 100),
            "turn": float(pos.diff().abs().fillna(0).sum())}


def skaliraj(k: float) -> LeanConfig:
    """Every time parameter times k, ratios preserved. RSI deliberately not."""
    r = lambda x: max(2, int(round(x * k)))
    return LeanConfig(
        track_period=r(75), ma_long_len=r(200), ma_slope=r(5),
        track_slope_bars=r(10), donchian_period=r(20),
        confirm_bars=r(3), reentry_hold=r(15), exit_grace_bars=r(3),
    )


def main() -> int:
    for sym in ("BTC", "ETH"):
        raw = fetch_candles(sym, "1d", bars=3000, config=Cfg,
                            prefer="coinbase", strict=True)
        sig = {}
        for k in SPEEDS:
            cfg = skaliraj(k)
            d = trim_warmup(run_strategy(raw, config=cfg).df)
            sig[k] = (d["prev_signal_state"] == S_BULL).astype(float)

        idx = sig[SPEEDS[0]].index
        for k in SPEEDS:
            idx = idx.intersection(sig[k].index)
        S = pd.DataFrame({k: sig[k].reindex(idx) for k in SPEEDS})
        ret = raw["close"].pct_change().reindex(idx).fillna(0.0)

        print(f"\n{'=' * 88}\n{sym}   {idx[0].date()} do {idx[-1].date()}   "
              f"{len(idx)} dni\n{'=' * 88}")
        c = skaliraj(2.0)
        print(f"  dvojna hitrost pomeni: kanal {c.donchian_period} dni, "
              f"trackline {c.track_period}, rezim {c.ma_long_len}")
        print(f"\n  {'':26s}{'Sortino':>9}{'letno':>8}{'MaxDD':>9}"
              f"{'konec':>8}{'v trgu':>9}{'promet':>9}")

        vrstice = []
        for k in SPEEDS:
            vrstice.append((f"sama hitrost {k}x", S[k]))
        vrstice.append(("povprecje treh (0-1)", S.mean(axis=1)))
        vrstice.append(("vecina 2 od 3 (binarno)", (S.sum(axis=1) >= 2).astype(float)))

        osnova = None
        for oznaka, pos in vrstice:
            r = net_returns(pos, ret, FEE).to_numpy(float)
            m = stats(r, pos)
            if oznaka == "sama hitrost 1.0x":
                osnova = m["sortino"]
            razlika = "" if osnova is None or oznaka == "sama hitrost 1.0x" \
                else f"{m['sortino'] - osnova:+7.3f}"
            print(f"  {oznaka:26s}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
                  f"{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{m['expo']:>8.1f}%"
                  f"{m['turn']:>9.1f}{razlika}")

        print(f"\n  koliko hitrosti se strinja:")
        n = S.sum(axis=1)
        for j in range(4):
            print(f"    {j} od 3: {float((n == j).mean() * 100):5.1f} % dni")
        print(f"  vse tri hkrati noter: {float((n == 3).mean() * 100):.1f} % dni")
    return 0


if __name__ == "__main__":
    sys.exit(main())
