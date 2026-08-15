"""Is a permanent minimum BTC holding worth it?

The dashboard's "Min BEAR allocation %" holds b instead of 0 while the signal
says out. That is not a new rule, it is a dial:

    position(t) = b + (1 - b) * signal(t)
    return(t)   = b * buy-and-hold  +  (1 - b) * the 0/100 strategy

So the question is not "does a floor help" but "what mix of holding and timing
is best", and the answer is a curve rather than a yes or no.

Two things move in opposite directions as b rises. Return goes up, because BTC
drifted upward and time out of the market costs that drift. Drawdown gets worse,
because the floor is still held through every crash. Costs fall, because only
(1 - b) of the capital ever trades.

    python testing/scripts/bear_alloc.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from diversitas.config import LeanConfig
from diversitas.strategy import run_strategy, S_BULL

FEE, PPY = 0.30, 365
LEVELS = [0, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100]
LEAN = ROOT.parent / "diversitas-lean"
ASSETS = (("BTC", "BTC_coinbase.parquet"), ("ETH", "ETH_coinbase.parquet"))
OUT = ROOT / "testing" / "data" / "bear_alloc.json"


def stats(pos: pd.Series, ret: pd.Series) -> dict:
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    # Textbook downside deviation over every day, not the std of the negative
    # subset. The wrong one moves with time spent out of the market, which is
    # exactly what this sweep changes, so it would have measured the dial rather
    # than the effect.
    down = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return {"sortino": float(r.mean() * PPY / down),
            "cagr": float((eq[-1] ** (PPY / len(r)) - 1) * 100),
            "maxdd": float(dd.min() * 100),
            "final": float(eq[-1]),
            "exposure": float(pos.mean() * 100),
            "cost_pct": float(turnover(pos).sum() * FEE / 100 * 100),
            "calmar": float((eq[-1] ** (PPY / len(r)) - 1) * 100 / abs(dd.min() * 100))}


def main() -> int:
    out = {}
    for sym, fname in ASSETS:
        raw = pd.read_parquet(LEAN / "data" / fname)
        df = trim_warmup(run_strategy(raw, config=LeanConfig()).df)
        # Position is yesterday's signal, same as the dashboard and verify.py.
        sig = (df["prev_signal_state"] == S_BULL).astype(float)
        close = raw["close"].reindex(df.index)
        ret = close.pct_change().fillna(0.0)

        for oznaka, maska in (("celotno okno", df.index >= df.index[0]),
                              ("od 2021", df.index >= "2021-01-01")):
            s, r = sig[maska], ret[maska]
            print(f"\n{'=' * 84}\n{sym}  {oznaka}   {s.index[0].date()} do "
                  f"{s.index[-1].date()}   {len(s)} dni\n{'=' * 84}")
            print(f"  {'min v BTC':>10}{'Sortino':>9}{'letno':>8}{'MaxDD':>9}"
                  f"{'konec':>9}{'v trgu':>8}{'stroski':>9}{'Calmar':>8}")
            vrstice = {}
            for b in LEVELS:
                pos = b / 100 + (1 - b / 100) * s
                m = stats(pos, r)
                vrstice[b] = m
                zvezda = ""
                print(f"  {b:>9} %{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
                      f"{m['maxdd']:>8.1f}%{m['final']:>8.2f}x{m['exposure']:>7.1f}%"
                      f"{m['cost_pct']:>8.1f}%{m['calmar']:>8.2f}{zvezda}")
            naj_s = max(vrstice, key=lambda b: vrstice[b]["sortino"])
            naj_c = max(vrstice, key=lambda b: vrstice[b]["calmar"])
            print(f"\n  najboljsi Sortino pri {naj_s} %   najboljsi Calmar pri {naj_c} %")
            out[f"{sym} {oznaka}"] = {"rows": vrstice, "best_sortino": naj_s,
                                      "best_calmar": naj_c}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
