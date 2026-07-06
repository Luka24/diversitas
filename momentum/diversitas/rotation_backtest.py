"""Cross-sectional rotation backtest CLI (production data path).

Fetches live candles for the universe via shared.data_source and runs the rotation
portfolio. Standalone — does not depend on the testing harness.

Run (as a module, so relative imports resolve):
      PYTHONPATH=momentum .venv/bin/python -m diversitas.rotation_backtest
      PYTHONPATH=momentum .venv/bin/python -m diversitas.rotation_backtest --k 3 --assets BTC,ETH,SOL,AVAX,LINK
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from shared.data_source import fetch_candles
from .config import MomentumConfig
from .rotation import run_rotation

DEFAULT_UNIVERSE = ["BTC", "ETH", "SOL", "AVAX", "LINK", "XRP", "BNB", "ADA"]


def _metrics(r: pd.Series, td: int = 365) -> dict:
    r = r.dropna()
    if len(r) < 10:
        return {}
    eq = (1 + r).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    cagr = float(eq.iloc[-1] ** (td / len(r)) - 1)
    down = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(td)
    sharpe = float(r.mean() * td / (r.std() * np.sqrt(td))) if r.std() > 0 else np.nan
    sortino = float(r.mean() * td / down) if down > 0 else np.nan
    return dict(cagr=cagr, sharpe=sharpe, sortino=sortino, max_dd=dd,
                calmar=(cagr / abs(dd) if dd < 0 else np.nan), final=float(eq.iloc[-1]))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Diversitas cross-sectional rotation backtest")
    p.add_argument("--assets", default=",".join(DEFAULT_UNIVERSE))
    p.add_argument("--k", type=int, default=3, help="number of assets held")
    p.add_argument("--bars", type=int, default=2600)
    p.add_argument("--no-graded", action="store_true", help="disable RSI conviction sizing")
    p.add_argument("--rebalance", type=int, default=7, help="rebalance every N days (default weekly)")
    args = p.parse_args(argv)

    assets = [a.strip().upper() for a in args.assets.split(",") if a.strip()]
    cfg = MomentumConfig()
    print(f"Fetching {len(assets)} assets ({args.bars} bars): {', '.join(assets)} …")
    daily = {}
    for a in assets:
        try:
            daily[a] = fetch_candles(a, "1d", bars=args.bars, config=cfg)
        except Exception as e:  # noqa: BLE001
            print(f"  skip {a}: {e}")
    if len(daily) < 2:
        print("Need at least 2 assets."); return 1

    res = run_rotation(daily, config=cfg, k=args.k, graded=not args.no_graded,
                       rebalance_every=args.rebalance)
    turnover = 0.5 * res.weights.diff().abs().sum(axis=1).fillna(0.0)
    m = _metrics(res.returns)

    print("\n" + "=" * 60)
    print(f"  ROTATION  ·  top-{args.k} of {len(daily)}  ·  "
          f"{'graded' if not args.no_graded else 'binary'} · rebalance {args.rebalance}d")
    print("=" * 60)
    print(f"  Period          : {res.returns.index[0].date()} → {res.returns.index[-1].date()}")
    print(f"  CAGR            : {m['cagr']*100:+.1f}%")
    print(f"  Sharpe          : {m['sharpe']:.2f}")
    print(f"  Sortino         : {m['sortino']:.2f}")
    print(f"  Calmar          : {m['calmar']:.2f}")
    print(f"  Max drawdown    : {m['max_dd']*100:.1f}%")
    print(f"  Value of 100    : {m['final']*100:,.0f}")
    print(f"  Avg assets held : {res.held_count.mean():.1f} / {args.k}")
    print(f"  Ann. turnover   : {turnover.mean()*365*100:,.0f}%  (fee-sensitive)")

    # current allocation (last bar)
    last_w = res.weights.iloc[-1]
    held = last_w[last_w > 0]
    print(f"\n  Trenutna alokacija ({res.weights.index[-1].date()}):")
    if len(held):
        for a, w in held.sort_values(ascending=False).items():
            print(f"    {a:5} {w*100:4.0f}%")
    else:
        print("    100% CASH (noben asset ni dovolj močan)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
