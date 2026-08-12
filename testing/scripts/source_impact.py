"""How much does the venue change the answer?

The dashboard has been running on Coinbase since Binance started answering 451.
The banner says the numbers are not comparable; this measures by how much, so
the decision to switch the pinned source or not is made on a number.

Same window, same config, same 0.30 %/side. Only the price series differs.

    python testing/scripts/source_impact.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared.costs import net_returns
from shared.data_source import fetch_candles
from shared.warmup import trim_warmup, required_history
from diversitas.config import DEFAULT_CONFIG, LeanConfig
from diversitas.strategy import run_strategy, S_BULL

FEE, PPY = 0.30, 365      # PERCENT per side
VENUES = ("binance", "coinbase", "yahoo")


def sortino(r: np.ndarray) -> float:
    d = r[r < 0]
    if len(d) == 0 or d.std() == 0:
        return float("nan")
    return float(r.mean() / d.std() * np.sqrt(PPY))


def maxdd(r: np.ndarray) -> float:
    eq = np.cumprod(1 + r)
    return float((eq / np.maximum.accumulate(eq) - 1).min() * 100)


def main() -> int:
    cfg = LeanConfig()
    bars = 2000 + required_history(cfg)

    raw = {}
    for v in VENUES:
        try:
            raw[v] = fetch_candles("BTC", "1d", bars=bars, config=DEFAULT_CONFIG,
                                   prefer=v, strict=True)
        except Exception as e:
            print(f"  {v}: ni dosegljiv — {type(e).__name__}: {str(e)[:120]}")
    if len(raw) < 2:
        print("Potrebujem vsaj dva vira za primerjavo.")
        return 1

    # Common window, so the comparison is not an artefact of different history.
    lo = max(d.index[0] for d in raw.values())
    hi = min(d.index[-1] for d in raw.values())
    for v in raw:
        raw[v] = raw[v].loc[lo:hi]
    print(f"Skupno okno: {lo.date()} → {hi.date()}   ({len(raw[VENUES[0]] if VENUES[0] in raw else next(iter(raw.values())))} barov)")

    base = VENUES[0] if VENUES[0] in raw else list(raw)[0]
    print(f"\n1. RAZLIKA V CENI proti {base}")
    bc = raw[base]["close"]
    for v in raw:
        if v == base:
            continue
        d = (raw[v]["close"] / bc - 1).abs() * 100
        print(f"   {v:<10} povprecno {d.mean():.3f} %   mediana {d.median():.3f} %"
              f"   najvec {d.max():.2f} %")

    print(f"\n2. STRATEGIJA  (provizija 0,30 % na stran)")
    print(f"   {'vir':<10}{'Sortino':>9}{'CAGR':>8}{'MaxDD':>9}{'konec':>8}{'poslov':>8}")
    res = {}
    for v in raw:
        df = trim_warmup(run_strategy(raw[v], config=cfg).df)
        pos = (df["signal_state"] == S_BULL).astype(float)
        ret = raw[v]["close"].pct_change().reindex(df.index).fillna(0.0)
        r = net_returns(pos, ret, FEE).to_numpy(float)
        eq = float(np.cumprod(1 + r)[-1])
        n_tr = int((np.diff(pos.to_numpy(), prepend=pos.iloc[0]) > 0).sum())
        res[v] = {"pos": pos, "df": df}
        print(f"   {v:<10}{sortino(r):>9.3f}{(eq ** (PPY / len(r)) - 1) * 100:>7.1f}%"
              f"{maxdd(r):>8.1f}%{eq:>7.2f}x{n_tr:>8d}")

    print(f"\n3. ALI SO POSLI ISTI DNEVI?")
    bp = res[base]["pos"]
    for v in res:
        if v == base:
            continue
        p = res[v]["pos"].reindex(bp.index)
        diff = int((p != bp).sum())
        print(f"   {v:<10} pozicija se razlikuje {diff:4d} dni od {len(bp)}"
              f"   ({diff / len(bp) * 100:.1f} % casa)")
        # entry dates that exist on one venue and not the other
        eb = set(bp.index[(bp.diff() > 0).fillna(False)].date)
        ev = set(p.index[(p.diff() > 0).fillna(False)].date)
        only_b, only_v = sorted(eb - ev), sorted(ev - eb)
        if only_b:
            print(f"              vstopi samo na {base}: "
                  + ", ".join(str(x) for x in only_b[:6]))
        if only_v:
            print(f"              vstopi samo na {v}: "
                  + ", ".join(str(x) for x in only_v[:6]))
        if not only_b and not only_v:
            print(f"              isti vstopni dnevi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
