"""The macro gates cut drawdown. Is that information, or just less exposure?

Several cells in macro_gates.py improve MaxDD a lot — DXY with a forced exit
takes BTC from -28.6 % to -18.9 %. But their time in the market falls at the
same time, and being out of the market cuts drawdown whether or not you picked
the right days to be out.

Two tests separate those.

  1. Exposure-matched baseline. Scale the UNFILTERED position down to the
     filter's average exposure and compare MaxDD. (Scale the baseline DOWN, not
     the variant up — clipping a binary series at 1 does nothing. Sortino is
     scale-invariant so it cannot move here; drawdown can.)

  2. Circular shift. Rotate the gate. Same number of blocked days, same
     clustering, wrong dates. If the real gate is not better than rotated ones,
     it is not choosing days, only counting them.

    python testing/scripts/macro_drawdown.py
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
from testing.scripts.macro_data import load as load_macro
from testing.scripts.macro_gates import (FEE, START, build, gate_for, maxdd,
                                         risk_flags, sortino)

N_SHIFT = 400
rng = np.random.default_rng(20260812)

# The cells worth interrogating: the ones whose drawdown looked best.
CANDIDATES = [("B DXY", "vstop+izstop"), ("B DXY", "vstop"),
              ("F vsi", "vstop"), ("G vecina", "vstop"), ("E MOVE", "vstop")]


def main() -> int:
    macro = load_macro()
    out = {}
    for sym, f in (("BTC", "BTC_binance_warmup.parquet"),
                   ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / f)
        ret = raw["close"].pct_change().fillna(0.0)
        flags = risk_flags(macro, raw.index)
        base = build(raw, pd.Series(True, index=raw.index), "vstop")
        base_r = net_returns(base, ret, FEE).to_numpy(float)
        print(f"\n{'=' * 92}\n{sym}   izhodisce: MaxDD {maxdd(base_r):.1f} %   "
              f"Sortino {sortino(base_r):.3f}   izpostavljenost {base.mean()*100:.1f} %"
              f"\n{'=' * 92}")
        print(f"  {'celica':<22}{'izpost':>8}{'MaxDD':>9}"
              f"{'izhod. @ isti izpost.':>23}{'razlika':>9}{'placebo %':>11}")
        rows = {}
        for v, mode in CANDIDATES:
            gate = gate_for(v, flags, raw.index)
            pos = build(raw, gate, mode)
            r = net_returns(pos, ret, FEE).to_numpy(float)
            dd, expo = maxdd(r), float(pos.mean())

            # 1. baseline scaled DOWN to the same average exposure
            scaled = base * (expo / float(base.mean()))
            dd_scaled = maxdd(net_returns(scaled, ret, FEE).to_numpy(float))

            # 2. rotate the gate
            g = gate.to_numpy(bool)
            n = len(g)
            shifted = []
            for k in rng.integers(1, n, size=N_SHIFT):
                p = build(raw, pd.Series(np.roll(g, int(k)), index=gate.index), mode)
                shifted.append(maxdd(net_returns(p, ret, FEE).to_numpy(float)))
            shifted = np.array(shifted)
            # percentile of the real gate: high = shallower drawdown than rotations
            pct = float((shifted < dd).mean() * 100)

            rows[f"{v} [{mode}]"] = {"exposure": round(expo * 100, 1),
                                     "maxdd": round(dd, 1),
                                     "maxdd_exposure_matched": round(dd_scaled, 1),
                                     "edge": round(dd - dd_scaled, 1),
                                     "placebo_pct": round(pct, 1)}
            print(f"  {v + ' [' + mode + ']':<22}{expo*100:>7.1f}%{dd:>8.1f}%"
                  f"{dd_scaled:>22.1f}%{dd - dd_scaled:>8.1f}{pct:>10.1f}%")
        out[sym] = rows

    (ROOT / "testing" / "data" / "macro_drawdown.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    # Both numbers are negative percentages, so a SHALLOWER drawdown is the
    # larger one. edge = filter - matched, hence edge > 0 means the filter is
    # ahead. (This legend was printed inverted when first written.)
    print("\nrazlika > 0: filter je BOLJSI od izhodisca pri isti izpostavljenosti")
    print("razlika < 0: izhodisce, samo zmanjsano na isto izpostavljenost, ima PLITVEJSI padec")
    print("placebo < 95 %: zavrten filter doseze isto, torej datumi ne nosijo informacije")
    return 0


if __name__ == "__main__":
    sys.exit(main())
