"""Does donchian_ok predict anything on its own, across EVERY day?

Everything so far measured the 244 days on BTC (100 on ETH) where the filter
changed the position. That is the strategy's footprint, not the signal's power,
and it is a small sample conditional on all the other rules.

This asks the raw question on all 2700 bars: split every day by donchian_ok and
compare what happens next. Three things are measured, because the claim being
tested is about crashes rather than about returns:

    forward return          does it pick better days at all
    forward max drawdown    the actual claim — does it avoid collapses
    crash frequency         share of days followed by a fall worse than -20 %

Then the harder version. Conditional on the strategy ALREADY wanting to buy —
above_tl, track_rising_window, regime_ok, no blow-off all satisfied — does the
extra Donchian veto still separate anything? That is its marginal contribution,
and it is the number that decides whether it earns its place rather than
duplicating rules already present.

Forward windows overlap, so every CI uses a block bootstrap with the block set to
the horizon.

Output: testing/data/donchian_signal_power.json
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

from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

HORIZONS = (5, 20, 60)
SRC = ROOT / "testing" / "data" / "sources"
OUT = ROOT / "testing" / "data" / "donchian_signal_power.json"
rng = np.random.default_rng(20260808)


def fwd_ret(close: np.ndarray, h: int) -> np.ndarray:
    out = np.full(len(close), np.nan)
    out[:len(close) - h] = (close[h:] / close[:len(close) - h] - 1) * 100
    return out


def fwd_maxdd(close: np.ndarray, h: int) -> np.ndarray:
    """Worst peak-to-trough fall inside the next h bars, in per cent."""
    n = len(close)
    out = np.full(n, np.nan)
    for i in range(n - h):
        w = close[i:i + h + 1]
        out[i] = (w / np.maximum.accumulate(w) - 1).min() * 100
    return out


def ci(x: np.ndarray, block: int, nb: int = 2000):
    """Block bootstrap on the mean; None when the sample cannot carry one."""
    m = len(x)
    if m < 3 * block:
        return None
    k = int(np.ceil(m / block))
    st = rng.integers(0, m, size=(nb, k))
    idx = (st[:, :, None] + np.arange(block)[None, None, :]
           ).reshape(nb, k * block)[:, :m] % m
    mu = x[idx].mean(axis=1)
    return [round(float(np.percentile(mu, 2.5)), 2),
            round(float(np.percentile(mu, 97.5)), 2)]


def compare(mask, ok, fr, fd, h, label_yes, label_no):
    """Split by a boolean and report both sides plus the gap."""
    res = {}
    for tag, m in ((label_yes, mask & ok), (label_no, mask & ~ok)):
        r, d = fr[m], fd[m]
        res[tag] = {
            "n": int(m.sum()),
            "ret": round(float(r.mean()), 2) if len(r) else None,
            "ret_ci": ci(r, h) if len(r) else None,
            "maxdd": round(float(d.mean()), 2) if len(d) else None,
            "maxdd_ci": ci(d, h) if len(d) else None,
            "crash_pct": round(float((r < -20).mean() * 100), 1) if len(r) else None,
            "win_pct": round(float((r > 0).mean() * 100), 1) if len(r) else None,
        }
    a, b = res[label_yes], res[label_no]
    if a["n"] and b["n"]:
        res["gap_ret"] = round(a["ret"] - b["ret"], 2)
        res["gap_maxdd"] = round(a["maxdd"] - b["maxdd"], 2)
        res["gap_crash"] = round(a["crash_pct"] - b["crash_pct"], 1)
    return res


def main() -> int:
    out = {}
    smod = engine.strategy_module("lean")
    cfg = engine.make_config("lean", use_donchian=True, donchian_period=20)

    for sym, f in (("BTC", "BTC_binance_warmup.parquet"), ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(SRC / f)
        df = trim_warmup(smod.compute_features(raw, None, cfg))
        close = df["close"].to_numpy(float)
        dok = df["donchian_ok"].fillna(False).to_numpy()
        # the strategy's own entry conditions, WITHOUT Donchian
        others = (df["above_tl"].fillna(False).to_numpy()
                  & df["track_rising_window"].fillna(False).to_numpy()
                  & df["regime_ok"].fillna(False).to_numpy()
                  & ~df["blowoff"].fillna(False).to_numpy())

        sym_res = {"n_bars": int(len(df)),
                   "donchian_ok_pct": round(float(dok.mean() * 100), 1),
                   "others_ok_pct": round(float(others.mean() * 100), 1)}
        print(f"\n{'='*78}\n{sym} · {len(df)} barov · "
              f"{df.index[0].date()} → {df.index[-1].date()}")
        print(f"donchian_ok velja na {dok.mean()*100:.1f} % dni · "
              f"ostali vstopni pogoji na {others.mean()*100:.1f} % dni\n{'='*78}")

        for h in HORIZONS:
            fr, fd = fwd_ret(close, h), fwd_maxdd(close, h)
            valid = np.isfinite(fr) & np.isfinite(fd)
            allm = valid

            a = compare(allm, dok, fr, fd, h, "donchian DA", "donchian NE")
            b = compare(allm & others, dok, fr, fd, h,
                        "ostali DA + donchian DA", "ostali DA + donchian NE")
            sym_res[f"h{h}"] = {"all_days": a, "given_others": b}

            print(f"\n  ── naslednjih {h} dni " + "─" * 44)
            print(f"  {'skupina':<28}{'dni':>6}{'donos':>9}{'95 % IZ':>19}"
                  f"{'najv. padec':>13}{'zlom <-20 %':>13}{'dobiček':>9}")
            for blk in (a, b):
                for k, v in blk.items():
                    if not isinstance(v, dict):
                        continue
                    c = (f"[{v['ret_ci'][0]:+.1f}, {v['ret_ci'][1]:+.1f}]"
                         if v["ret_ci"] else "—")
                    print(f"  {k:<28}{v['n']:>6}{v['ret']:>+8.2f}%{c:>19}"
                          f"{v['maxdd']:>12.2f}%{v['crash_pct']:>12.1f}%"
                          f"{v['win_pct']:>8.1f}%")
                print(f"  {'razlika':<28}{'':>6}{blk['gap_ret']:>+8.2f}%{'':>19}"
                      f"{blk['gap_maxdd']:>+12.2f}%{blk['gap_crash']:>+12.1f}%")
        out[sym] = sym_res

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
