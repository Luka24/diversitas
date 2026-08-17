"""Same parameters on every asset, or fitted per asset?

The tempting answer is per asset: SOL is wilder than BTC, so why should both use
a 20-day channel? The problem is that each asset you fit multiplies the number
of choices being made from the same data, and every one of those choices can be
luck.

This measures it directly. For each asset, sweep the Donchian period, find the
one that looks best on the first half of the history, then check what it does on
the second half. If per-asset fitting is real, the winner from the first half
should keep winning. If it is luck, it should not.

Compared against the shared 20, which was picked from the Turtle literature and
never from this data.

    python testing/scripts/isti_parametri.py
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
PERIODS = [10, 15, 20, 25, 30, 40, 55]
SYMS = ("BTC", "ETH", "SOL", "LINK")

_sm = dict(DEFAULT_CONFIG.symbol_map)
for s in ("SOL", "LINK"):
    _sm.setdefault(s, {"coinbase": f"{s}-USD", "yahoo": f"{s}-USD"})


class Cfg:
    symbol_map = _sm


def sortino(r: np.ndarray) -> float:
    down = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / down) if down else float("nan")


def run(raw: pd.DataFrame, period: int):
    cfg = LeanConfig(donchian_period=period)
    d = trim_warmup(run_strategy(raw, config=cfg).df)
    pos = (d["prev_signal_state"] == S_BULL).astype(float)
    ret = raw["close"].pct_change().reindex(d.index).fillna(0.0)
    return pos, ret


def main() -> int:
    surovi = {s: fetch_candles(s, "1d", bars=3000, config=Cfg,
                               prefer="coinbase", strict=True) for s in SYMS}

    print("1. NAJBOLJSA PERIODA ZA VSAKO SREDSTVO, na CELI zgodovini")
    print(f"  {'sredstvo':10s}" + "".join(f"{p:>8}" for p in PERIODS) + "   najboljsa")
    for s in SYMS:
        vrst, naj, naj_v = [], None, -9e9
        for p in PERIODS:
            pos, ret = run(surovi[s], p)
            v = sortino(net_returns(pos, ret, FEE).to_numpy(float))
            vrst.append(v)
            if v > naj_v:
                naj_v, naj = v, p
        print(f"  {s:10s}" + "".join(f"{v:>8.2f}" for v in vrst) + f"   {naj} dni")

    print("\n2. ALI SE IZBIRA PRENESE?  izberi na prvi polovici, preveri na drugi")
    print(f"  {'sredstvo':10s}{'izbrano':>9}{'na 1. pol':>11}"
          f"{'na 2. pol':>11}{'skupnih 20':>12}{'razlika':>10}")
    skupaj_izbrano, skupaj_20 = [], []
    for s in SYMS:
        pos20, ret = run(surovi[s], 20)
        n = len(pos20)
        prva, druga = slice(0, n // 2), slice(n // 2, n)
        naj, naj_v = None, -9e9
        for p in PERIODS:
            pos, r = run(surovi[s], p)
            v = sortino(net_returns(pos, r, FEE).to_numpy(float)[prva])
            if v > naj_v:
                naj_v, naj = v, p
        pos_naj, r_naj = run(surovi[s], naj)
        oos_naj = sortino(net_returns(pos_naj, r_naj, FEE).to_numpy(float)[druga])
        oos_20 = sortino(net_returns(pos20, ret, FEE).to_numpy(float)[druga])
        skupaj_izbrano.append(oos_naj)
        skupaj_20.append(oos_20)
        znak = "" if oos_naj > oos_20 else "  slabsi"
        print(f"  {s:10s}{naj:>7} dni{naj_v:>11.2f}{oos_naj:>11.2f}"
              f"{oos_20:>12.2f}{oos_naj - oos_20:>+10.2f}{znak}")
    print(f"\n  povprecje na drugi polovici:  izbrano po sredstvu "
          f"{np.mean(skupaj_izbrano):.3f}   skupnih 20 dni {np.mean(skupaj_20):.3f}")
    zmag = sum(1 for a, b in zip(skupaj_izbrano, skupaj_20) if a > b)
    print(f"  izbiranje po sredstvu je bilo boljse na {zmag} od {len(SYMS)} sredstev")

    print("\n3. KOLIKO IZBIR DELAMO")
    print(f"  ena skupna perioda:        1 izbira")
    print(f"  perioda na sredstvo:       {len(SYMS)} izbir")
    print(f"  vseh 10 parametrov na sredstvo: {10 * len(SYMS)} izbir iz istih podatkov")
    return 0


if __name__ == "__main__":
    sys.exit(main())
