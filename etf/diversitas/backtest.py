"""ETF backtest CLI.

    python -m diversitas.backtest World
    python -m diversitas.backtest --portfolio P1
    python -m diversitas.backtest --portfolio P2 --compare

Run from inside `etf/` (so `import diversitas` resolves to this variant), the
same convention as `lean/` and `momentum/`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.etf_data import load, load_panel, quality_report          # noqa: E402
from shared.etf_universe import PORTFOLIOS, UNIVERSE, usable_start    # noqa: E402
from testing.scripts import etf_eval as EV                            # noqa: E402

from .config import DEFAULT_CONFIG, ETFConfig            # noqa: E402
from .rotation import buy_and_hold, dual_book, overlay_book, rotate_within  # noqa: E402
from .strategy import run_strategy                        # noqa: E402


def _single(key: str, cfg: ETFConfig) -> int:
    # Start where the line is actually tradable, not at listing. On IWDA.L that
    # discards 2009-2012, where 40-81 % of closes are stale repeats and every
    # backtested fill there is fiction. See `shared/etf_universe.usable_from`.
    daily = load(key, start=UNIVERSE[key].usable_from)
    res = run_strategy(daily, config=cfg)
    df, s = res.df, res.summary
    inst = UNIVERSE[key]
    print("\n" + "=" * 66)
    print(f"  {key}  {inst.yahoo}  ({inst.isin})   latest bar {s['time'].date()}")
    print("=" * 66)
    print(f"  Signal            : {s['signal']}   (display: {s['regime']})")
    print(f"  Close             : EUR {s['close']:,.2f}")
    print(f"  Trackline (D{cfg.track_period}) : EUR {s['trackline']:,.2f}   "
          f"{s['dist_pct']:+.2f}%  = {s['dist_atr']:+.2f} ATR")
    print(f"  MA{cfg.ma_fast_len} / MA{cfg.ma_reg_len}      : "
          f"{'ABOVE' if s['above_ma_fast'] else 'BELOW'} / {s['ma_reg_status']}")
    print(f"  ADX({cfg.adx_len})           : {s['adx']:.1f}   "
          f"{'PASS' if s['adx_ok'] else 'FAIL'} (need > {cfg.adx_thresh})")
    print(f"  RSI / momentum    : {s['rsi']:.1f}   {'OK' if s['momentum_ok'] else 'NO'}")
    print(f"  ATR               : {s['atr_pct']:.2f}% of price")
    print(f"  Realised vol      : {s['annual_vol']:.1f}%  ->  vol scale "
          f"{s['vol_scale']:.2f} (target {cfg.target_vol_pct}%)")
    print(f"  Target allocation : {s['target_alloc']:.0f}%")
    if s["trail_stop"] is not None:
        print(f"  Trailing stop     : EUR {s['trail_stop']:,.2f} "
              f"({cfg.trail_atr_mult} x ATR below peak)")

    from shared.costs import net_returns
    pos = (df["target_alloc"] / 100.0).shift(1).fillna(0.0)
    ret = df["close"].pct_change().fillna(0.0)
    fee = cfg.fee_overrides.get(key, cfg.fee_per_side_pct)
    strat = net_returns(pos, ret, fee)
    bh = ret
    rows = [EV.evaluate(strat, bench=bh, position=pos, label=f"{key} trend"),
            EV.evaluate(bh, label=f"{key} buy & hold")]
    print("\n" + EV.fmt(EV.compare(rows)))
    t = EV.trade_panel(df)
    print(f"\n  trades {t['n_trades']}   win rate {t['win_rate']:.0f}%   "
          f"profit factor {t['profit_factor']:.2f}   "
          f"avg hold {t['avg_duration']:.0f} days")
    return 0


def _portfolio(name: str, cfg: ETFConfig, compare_all: bool) -> int:
    panel, frames = load_panel(name)
    w = PORTFOLIOS[name]
    print(f"\n{name}: {', '.join(f'{k} {v:.0%}' for k, v in w.items())}")
    print(f"usable history from {usable_start(name)}  "
          f"({panel.index.min().date()} -> {panel.index.max().date()}, {len(panel)} bars)\n")
    print(quality_report(frames).to_string())

    bh = buy_and_hold(frames, w, fee_per_side_pct=cfg.fee_per_side_pct)
    ov = overlay_book(frames, w, cfg)
    rows = [EV.evaluate(bh.returns, label=f"{name} buy & hold",
                        turnover=bh.turnover, gross=bh.gross),
            EV.evaluate(ov.returns, bench=bh.returns, label=f"{name} trend overlay",
                        position=ov.weights.sum(axis=1), turnover=ov.turnover,
                        gross=ov.gross)]
    if compare_all:
        rw = rotate_within(frames, cfg, k=max(2, len(w) // 2))
        rows.append(EV.evaluate(rw.returns, bench=bh.returns,
                                label=f"{name} rotate top-k",
                                position=rw.weights.sum(axis=1),
                                turnover=rw.turnover, gross=rw.gross))
    print("\n" + EV.fmt(EV.compare(rows)))
    print("\nworst drawdowns (overlay):")
    print(EV.drawdown_episodes(ov.returns).head(5).to_string(index=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Diversitas ETF backtest")
    p.add_argument("key", nargs="?", default=None,
                   help=f"instrument key: {', '.join(UNIVERSE)}")
    p.add_argument("--portfolio", choices=sorted(PORTFOLIOS), default=None)
    p.add_argument("--compare", action="store_true",
                   help="also run the rotation layer")
    p.add_argument("--target-vol", type=float, default=None)
    p.add_argument("--fee", type=float, default=None, help="percent per side")
    args = p.parse_args(argv)

    cfg = DEFAULT_CONFIG
    if args.target_vol is not None:
        cfg = ETFConfig(**{**cfg.__dict__, "target_vol_pct": args.target_vol})
    if args.fee is not None:
        cfg = ETFConfig(**{**cfg.__dict__, "fee_per_side_pct": args.fee})

    pd.set_option("display.width", 200)
    if args.portfolio:
        return _portfolio(args.portfolio, cfg, args.compare)
    if args.key:
        return _single(args.key, cfg)
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
