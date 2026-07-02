"""Diversitas Momentum backtest CLI."""
from __future__ import annotations
import argparse
import sys

import pandas as pd

from shared.data_source import fetch_candles, fetch_btc_daily
from .config import MomentumConfig
from .strategy import run_strategy, S_BULL, S_BEAR


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Diversitas Momentum backtest")
    p.add_argument("symbol", nargs="?", default="BTC")
    p.add_argument("bars", nargs="?", type=int, default=1500)
    p.add_argument("--btc-filter", action="store_true")
    args = p.parse_args(argv)

    symbol  = args.symbol.upper()
    use_btc = args.btc_filter and symbol != "BTC"
    cfg     = MomentumConfig(use_btc_filter=use_btc)

    print(f"Fetching {symbol} ({args.bars} daily bars)…")
    daily = fetch_candles(symbol, "1d", bars=args.bars, config=cfg)
    btc   = fetch_btc_daily(bars=args.bars, config=cfg) if use_btc else None

    print("Running Momentum strategy…")
    result = run_strategy(daily, btc_daily=btc, config=cfg)
    df = result.df.dropna(subset=["ma_reg"])
    s  = result.summary

    print("\n" + "=" * 60)
    print(f"  {symbol}  —  latest bar  {s['time'].date()}  (MOMENTUM)")
    print("=" * 60)
    print(f"  Signal           : {s['signal']}")
    print(f"  Display regime   : {s['regime']}")
    print(f"  Close            : ${s['close']:,.2f}")
    print(f"  Trackline        : ${s['trackline']:,.2f}  "
          f"({'RISING' if s['track_rising_window'] else 'FLAT/FALLING'})")
    print(f"  Price vs TL      : {s['dist_pct']:+.2f}%")
    print(f"  Trend MA (20)    : {'ABOVE' if s['above_ma_fast'] else 'BELOW'}")
    print(f"  Regime MA (100)  : {s['ma_reg_status']}")
    print(f"  Annual vol       : {s['annual_vol']:.1f}%")
    print(f"  RSI              : {s['rsi']:.1f}")
    print(f"  Momentum OK      : {'YES' if s['momentum_ok'] else 'NO'}")
    print(f"  Target alloc     : {s['target_alloc']:.0f}%")
    if s["trail_stop"] is not None:
        print(f"  Trail stop       : ${s['trail_stop']:,.2f}")
    if s["blowoff"]:
        print("  WARNING          : BLOW-OFF detected")
    if s["vol_shock"]:
        print("  WARNING          : VOL SHOCK detected")

    print(f"\nSignal distribution (analyzed bars: {len(df)}):")
    sig_vc = df["signal_state"].value_counts().sort_index()
    for code, n in sig_vc.items():
        label = "BULL" if code == S_BULL else "BEAR"
        print(f"  {label:5} {n:4} bars ({n/len(df)*100:.1f}%)")

    ch = df[df["signal_changed"]]
    print(f"\nSignal transitions ({len(ch)}):")
    for ts, row in ch.iterrows():
        label  = "BULL" if row["signal_state"] == S_BULL else "BEAR"
        reason = ""
        if label == "BEAR":
            if row["exit_reason_trail"]:
                reason = "  [trail-stop]"
            elif row["blowoff"]:
                reason = "  [blow-off]"
            elif row["vol_shock"]:
                reason = "  [vol-shock]"
            else:
                reason = "  [trend-break]"
        print(f"  {ts.date()}  -> {label:4}  "
              f"close=${row['close']:>10,.0f}  "
              f"dist={row['dist_pct']:+5.1f}%{reason}")

    df = df.copy()
    df["ret"]       = df["close"].pct_change().fillna(0.0)
    df["pos"]       = df["target_alloc"].shift(1).fillna(0.0) / 100.0
    df["strat_ret"] = df["pos"] * df["ret"]
    bh_total = (1 + df["ret"]).prod() - 1
    st_total = (1 + df["strat_ret"]).prod() - 1
    print(f"\nEquity proxy (vol-scaled alloc, no fees):")
    print(f"  Buy & hold           : {bh_total*100:+.1f}%")
    print(f"  Diversitas Momentum  : {st_total*100:+.1f}%")
    print(f"  Avg exposure         : {df['pos'].mean()*100:.1f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
