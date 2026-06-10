"""Backtest CLI — fetch history, run strategy, print signal summary.

Usage:
    python -m diversitas.backtest BTC            # default BTC, 1500 daily bars
    python -m diversitas.backtest ETH 1000
    python -m diversitas.backtest SOL 800 --no-btc-filter
"""
from __future__ import annotations
import argparse
import sys

import pandas as pd

from shared.data_source import fetch_candles, fetch_btc_daily
from .config import Config
from .strategy import run_strategy, S_BULL, S_BEAR


def _format_alloc(x: float) -> str:
    return "n/a" if pd.isna(x) else f"{x:5.1f}%"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Diversitas Pro v3 backtest")
    p.add_argument("symbol", nargs="?", default="BTC",
                   help="Logical symbol (BTC, ETH, SOL, ...)")
    p.add_argument("bars", nargs="?", type=int, default=1500,
                   help="Number of daily candles to load (default 1500 ≈ 4y)")
    p.add_argument("--no-btc-filter", action="store_true",
                   help="Disable BTC cross-asset filter")
    args = p.parse_args(argv)

    symbol = args.symbol.upper()
    cfg = Config(use_btc_filter=(not args.no_btc_filter and symbol != "BTC"))

    print(f"Fetching {symbol} ({args.bars} daily bars)…")
    daily = fetch_candles(symbol, "1d", bars=args.bars, config=cfg)
    btc = None
    if cfg.use_btc_filter:
        print("Fetching BTC for cross-asset filter…")
        btc = fetch_btc_daily(bars=args.bars, config=cfg)

    print("Running strategy…")
    result = run_strategy(daily, btc_daily=btc, config=cfg)
    df = result.df.dropna(subset=["conviction"])

    # --- Header status ---
    s = result.summary
    print("\n" + "=" * 60)
    print(f"  {symbol}  —  latest bar  {s['time'].date()}")
    print("=" * 60)
    print(f"  Signal           : {s['signal']}")
    print(f"  Display regime   : {s['regime']}")
    print(f"  Close            : ${s['close']:,.2f}")
    print(f"  Trackline        : ${s['trackline']:,.2f}  "
          f"({'RISING' if s['track_rising'] else 'FALLING'})")
    print(f"  Price vs TL      : {s['dist_pct']:+.2f}%")
    print(f"  Conviction       : {s['conviction']:.1f}  /  threshold {s['threshold']:.0f}")
    print(f"  200 MA           : {s['ma200_status']}")
    print(f"  Annual vol       : {s['annual_vol']:.1f}%")
    print(f"  Trend quality    : {s['trend_quality_pct']:.0f}%")
    print(f"  Final allocation : {_format_alloc(s['final_alloc'])}")

    # --- Distribution ---
    print("\nSignal distribution (analyzed bars: {}):".format(len(df)))
    sig_vc = df["signal_state"].value_counts().sort_index()
    for code, n in sig_vc.items():
        label = "BULL" if code == S_BULL else "BEAR"
        print(f"  {label:5} {n:4} bars ({n/len(df)*100:.1f}%)")

    # --- Transitions ---
    ch = df[df["signal_changed"]]
    print(f"\nSignal transitions ({len(ch)}):")
    for ts, row in ch.iterrows():
        label = "BULL" if row["signal_state"] == S_BULL else "BEAR"
        print(f"  {ts.date()}  -> {label:4}  "
              f"close=${row['close']:>10,.0f}  "
              f"conv={row['conviction']:>5.1f}  "
              f"thr={row['dynamic_threshold']:>4.0f}")

    # --- Simple equity proxy (BULL-only, no slippage/fees) ---
    df = df.copy()
    df["ret"] = df["close"].pct_change().fillna(0.0)
    df["pos"] = (df["signal_state"].shift(1) == S_BULL).astype(float)
    df["strat_ret"] = df["pos"] * df["ret"]
    bh_total = (1 + df["ret"]).prod() - 1
    st_total = (1 + df["strat_ret"]).prod() - 1
    print(f"\nNaive equity proxy (BULL = long, BEAR = flat, no fees):")
    print(f"  Buy & hold       : {bh_total*100:+.1f}%")
    print(f"  Diversitas (BULL): {st_total*100:+.1f}%")
    print(f"  Exposure         : {df['pos'].mean()*100:.1f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
