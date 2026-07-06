"""Live rotation signal export — for paper trading / monitoring.

Fetches live candles for the universe, computes today's target rotation allocation
(top-K strongest Momentum-BULL assets, graded sleeve), and writes it to JSON + CSV.
Run this after each daily close; rebalance to the target on your chosen cadence
(weekly is the validated default). This is the honest next step before committing
capital — the hold-out has now been observed, so live tracking is the only clean
forward test left.

Run (as a module):
      PYTHONPATH=momentum .venv/bin/python -m diversitas.rotation_signal
      PYTHONPATH=momentum .venv/bin/python -m diversitas.rotation_signal --k 3 --out signals/
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

from shared.data_source import fetch_candles
from .config import MomentumConfig
from .rotation import current_allocation

DEFAULT_UNIVERSE = ["BTC", "ETH", "SOL", "AVAX", "LINK", "XRP", "BNB", "ADA"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Export today's rotation target allocation")
    p.add_argument("--assets", default=",".join(DEFAULT_UNIVERSE))
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--bars", type=int, default=600)
    p.add_argument("--no-graded", action="store_true")
    p.add_argument("--out", default="signals", help="output directory")
    args = p.parse_args(argv)

    assets = [a.strip().upper() for a in args.assets.split(",") if a.strip()]
    cfg = MomentumConfig()
    print(f"Fetching {len(assets)} assets …")
    daily = {}
    for a in assets:
        try:
            daily[a] = fetch_candles(a, "1d", bars=args.bars, config=cfg)
        except Exception as e:  # noqa: BLE001
            print(f"  skip {a}: {e}")
    if len(daily) < 2:
        print("Need at least 2 assets."); return 1

    sig = current_allocation(daily, config=cfg, k=args.k, graded=not args.no_graded)
    as_of = max(d.index[-1] for d in daily.values())
    payload = {
        "as_of": str(as_of.date()),
        "generated_utc": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "universe": list(daily.keys()),
        "k": args.k,
        "graded": not args.no_graded,
        "rebalance_note": "Rebalance to this target weekly (validated default).",
        **sig,
    }

    os.makedirs(args.out, exist_ok=True)
    dated = os.path.join(args.out, f"rotation_signal_{as_of.date()}.json")
    latest = os.path.join(args.out, "rotation_signal_latest.json")
    for path in (dated, latest):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    # flat CSV of the allocation
    csv_path = os.path.join(args.out, "rotation_signal_latest.csv")
    with open(csv_path, "w", encoding="utf-8") as fh:
        fh.write("asset,weight\n")
        for a, w in sig["allocation"].items():
            fh.write(f"{a},{w}\n")

    # human-readable summary
    print("\n" + "=" * 56)
    print(f"  ROTATION SIGNAL  ·  {payload['as_of']}  ·  top-{args.k} of {len(daily)}")
    print("=" * 56)
    alloc = {a: w for a, w in sig["allocation"].items() if w > 0}
    if len(alloc) <= 1 and sig["allocation"].get("CASH", 0) > 0.99:
        print("  100% CASH — noben asset ni dovolj močan.")
    else:
        for a, w in sorted(alloc.items(), key=lambda x: -x[1]):
            tag = "" if a == "CASH" else f"  [{sig['detail'][a]['state']}, "\
                  f"RSI {sig['detail'][a]['rsi']}, dist {sig['detail'][a]['dist_pct']:+.1f}%]"
            print(f"    {a:5} {w*100:5.1f}%{tag}")
    print(f"\n  Held: {', '.join(sig['held']) or '—'}")
    print(f"  Wrote {latest}, {dated}, {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
