"""Diversitas Lean backtest CLI."""
from __future__ import annotations
import argparse
import sys

import pandas as pd

from .config import LeanConfig
from .data_source import fetch_candles, fetch_btc_daily
from .strategy import run_strategy, S_BULL, S_BEAR


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Diversitas Lean backtest")
    p.add_argument("symbol", nargs="?", default="BTC")
    p.add_argument("bars", nargs="?", type=int, default=1500)
    p.add_argument("--btc-filter", action="store_true",
                   help="Enable BTC cross-asset filter (off by default in Lean)")
    args = p.parse_args(argv)

    symbol = args.symbol.upper()
    use_btc = args.btc_filter and symbol != "BTC"
    cfg = LeanConfig(use_btc_filter=use_btc)

    print(f"Fetching {symbol} ({args.bars} daily bars)…")
    daily = fetch_candles(symbol, "1d", bars=args.bars, config=cfg)
    btc = fetch_btc_daily(bars=args.bars, config=cfg) if use_btc else None

    print("Running Lean strategy…")
    result = run_strategy(daily, btc_daily=btc, config=cfg)
    df = result.df.dropna(subset=["ma_long"])
    s = result.summary

    # --- Latest bar status ---
    print("\n" + "=" * 60)
    print(f"  {symbol}  —  latest bar  {s['time'].date()}  (LEAN)")
    print("=" * 60)
    print(f"  Signal           : {s['signal']}")
    print(f"  Display regime   : {s['regime']}")
    print(f"  Close            : ${s['close']:,.2f}")
    print(f"  Trackline        : ${s['trackline']:,.2f}  "
          f"({'RISING' if s['track_rising_window'] else 'FLAT/FALLING'})")
    print(f"  Price vs TL      : {s['dist_pct']:+.2f}%")
    print(f"  Trend MA (50)    : {'ABOVE' if s['above_ma_med'] else 'BELOW'}")
    print(f"  Regime MA (200)  : {s['ma_long_status']}")
    print(f"  Annual vol       : {s['annual_vol']:.1f}%")
    print(f"  RSI              : {s['rsi']:.1f}")
    print(f"  Target alloc     : {s['target_alloc']:.0f}%")
    if s["blowoff"]:
        print(f"  WARNING          : BLOW-OFF detected")
    if s["vol_shock"]:
        print(f"  WARNING          : VOL SHOCK detected")

    # --- Signal distribution ---
    print(f"\nSignal distribution (analyzed bars: {len(df)}):")
    sig_vc = df["signal_state"].value_counts().sort_index()
    for code, n in sig_vc.items():
        label = "BULL" if code == S_BULL else "BEAR"
        print(f"  {label:5} {n:4} bars ({n/len(df)*100:.1f}%)")

    # --- Transitions ---
    ch = df[df["signal_changed"]]
    print(f"\nSignal transitions ({len(ch)}):")
    for ts, row in ch.iterrows():
        label = "BULL" if row["signal_state"] == S_BULL else "BEAR"
        reason = ""
        if label == "BEAR":
            if row["blowoff"]:
                reason = "  [blow-off]"
            elif row["vol_shock"]:
                reason = "  [vol-shock]"
            else:
                reason = "  [trend-break]"
        print(f"  {ts.date()}  -> {label:4}  "
              f"close=${row['close']:>10,.0f}  "
              f"dist={row['dist_pct']:+5.1f}%{reason}")

    # --- Naive equity proxy ---
    df = df.copy()
    df["ret"] = df["close"].pct_change().fillna(0.0)
    df["pos"] = (df["signal_state"].shift(1) == S_BULL).astype(float)
    df["strat_ret"] = df["pos"] * df["ret"]
    bh_total = (1 + df["ret"]).prod() - 1
    st_total = (1 + df["strat_ret"]).prod() - 1
    print(f"\nNaive equity proxy (BULL = long, BEAR = flat, no fees):")
    print(f"  Buy & hold       : {bh_total*100:+.1f}%")
    print(f"  Diversitas Lean  : {st_total*100:+.1f}%")
    print(f"  Exposure         : {df['pos'].mean()*100:.1f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
