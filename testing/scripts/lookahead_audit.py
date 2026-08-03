"""Does the strategy ever use information it could not have had?

This is the one error that would make every number in the project meaningless,
and it had never been checked systematically. Reading the code for it is
unreliable -- lookahead hides in rolling windows, in resample, in a forgotten
ffill, in a shift with the wrong sign.

The check used here needs no code reading and cannot miss any of those:

    for many dates T, run the strategy on data TRUNCATED AT T and compare
    every column on day T against the same day computed from the full history.

If a value on day T changes once data after T becomes available, that value
depended on the future. Truncation only removes the end, so the warm-up trim
point and the whole state-machine path up to T are unaffected; any difference is
real.

A detector that always passes is worth nothing, so the run starts with a
POSITIVE CONTROL: a deliberately broken variant that peeks one bar ahead. If the
audit fails to flag that, the audit itself is broken and the run aborts.

Output: testing/data/lookahead_BTC.json
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

from shared.warmup import required_history
from testing.scripts import engine

np.seterr(all="ignore")

SYMBOL = "BTC"
N_DATES = 200
SEED = 20260803
SRC = ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance_warmup.parquet"
OUT = ROOT / "testing" / "data" / "lookahead_BTC.json"

# Columns worth comparing. Split so a failure says WHERE the leak is.
FEATURE_COLS = [
    "trackline", "track_rising", "track_rising_window", "above_tl", "below_tl",
    "dist_pct", "ma_med", "ma_long", "above_ma_med", "above_ma_long",
    "ma_long_rising", "ma_long_falling", "bear_regime", "regime_ok",
    "rsi", "annual_vol", "vol_avg50", "donchian_ok",
    "bull_condition", "trend_break", "blowoff",
]
STATE_COLS = [
    "signal_state", "display_state", "target_alloc",
    "bars_since_signal", "below_count", "bull_hold", "signal_changed",
]
TOL = 1e-9


def build(raw: pd.DataFrame, cfg, peek: str | None = None) -> pd.DataFrame:
    """Full pipeline.  injects a known bug, to prove the audit detects.

    "signal"  tomorrow's close decides today's signal. Blunt, but only visible on
              days where the leaked value differs, so roughly half of them.
    "window"  a centred rolling mean instead of a trailing one. This is the
              realistic accident -- one forgotten center=True -- and it shifts a
              continuous value on essentially every bar, so detection should be
              near total. If this one is missed, the audit has no power for the
              failure mode that actually happens.
    """
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    if peek == "signal":
        df["bull_condition"] = (df["close"].shift(-1) > df["close"]).fillna(False)
    elif peek == "window":
        df["ma_long"] = df["close"].rolling(cfg.ma_long_len, center=True).mean()
        df["above_ma_long"] = df["close"] > df["ma_long"]
        df["ma_long_falling"] = df["ma_long"] < df["ma_long"].shift(cfg.ma_slope)
        df["bear_regime"] = (~df["above_ma_long"]) & df["ma_long_falling"]
        df["regime_ok"] = ~df["bear_regime"]
        df["bull_condition"] = (df["bull_condition"] & df["regime_ok"]).fillna(False)
    return smod.run_state_machine(df, cfg)


def compare_row(full: pd.Series, trunc: pd.Series, cols) -> list[str]:
    bad = []
    for c in cols:
        if c not in full.index or c not in trunc.index:
            continue
        a, b = full[c], trunc[c]
        if pd.isna(a) and pd.isna(b):
            continue
        # One-sided NaN is a difference and must be caught here. Falling through
        # to the numeric branch would hide it: abs(x - nan) is nan, and
        # nan > TOL is False, so the comparison silently passes.
        if pd.isna(a) != pd.isna(b):
            bad.append(c)
            continue
        if isinstance(a, (bool, np.bool_)) or isinstance(b, (bool, np.bool_)):
            if bool(a) != bool(b):
                bad.append(c)
        else:
            try:
                if abs(float(a) - float(b)) > TOL:
                    bad.append(c)
            except (TypeError, ValueError):
                if a != b:
                    bad.append(c)
    return bad


def audit(raw, cfg, dates, peek=None):
    """Returns {date: [columns that changed]} for every date that leaked."""
    full = build(raw, cfg, peek=peek)
    leaks: dict[str, dict] = {}
    for t in dates:
        cut = raw.loc[:t]
        trunc = build(cut, cfg, peek=peek)
        if trunc.index[-1] != t:
            continue
        f, u = full.loc[t], trunc.iloc[-1]
        bad_f = compare_row(f, u, FEATURE_COLS)
        bad_s = compare_row(f, u, STATE_COLS)
        if bad_f or bad_s:
            leaks[str(t.date())] = {"features": bad_f, "state": bad_s}
    return leaks, len(full)


def main() -> int:
    raw = pd.read_parquet(SRC)
    cfg = engine.make_config("lean")
    need = required_history(cfg)
    rng = np.random.default_rng(SEED)

    # only dates with enough history behind them, and not the very last bar
    usable = raw.index[need + 30: len(raw) - 2]
    dates = pd.DatetimeIndex(sorted(rng.choice(usable, size=min(N_DATES, len(usable)),
                                               replace=False)))
    # `compare_row` skips columns it cannot find, which is what makes the audit
    # tolerant of variant differences — and also what would let a rename or a
    # removal quietly shrink the audit to nothing. So the lists are checked
    # against the real frame first.
    have = set(build(raw, cfg).columns)
    missing = [c for c in FEATURE_COLS + STATE_COLS if c not in have]
    if missing:
        print(f"NAPAKA: teh stolpcev ni več v strategiji: {missing}")
        print("Popravi seznam, sicer revizija tiho preverja manj, kot misliš.")
        return 1

    print(f"{SYMBOL} · {len(raw)} barov · potrebna zgodovina {need}")
    print(f"preverjam {len(dates)} datumov med {dates[0].date()} in {dates[-1].date()}\n")

    # ── positive controls: prove the detector detects ───────────────────────
    print("KONTROLE — namerno pokvarjeni različici, da preverim, ali revizija zazna")
    ctrl_dates = dates[:40]
    hits: dict[str, float] = {}
    for tag, lab in (("signal", "jutrišnji zaključek odloča o današnjem signalu"),
                     ("window", "centrirano drseče povprečje namesto zaostalega")):
        c, _ = audit(raw, cfg, ctrl_dates, peek=tag)
        hits[tag] = len(c) / len(ctrl_dates) * 100
        print(f"  {lab:48} zaznano {len(c):3d}/{len(ctrl_dates)} = {hits[tag]:5.1f} %")
    if min(hits.values()) == 0:
        print("  NAPAKA: revizija ne zazna niti namerne napake. USTAVLJAM.")
        return 1
    print("  Prva je vidna le na dneh, kjer se ukradena vrednost razlikuje, zato je")
    print("  ~50 % pričakovano. Druga premakne zvezno vrednost na skoraj vsakem baru")
    print("  in prav ta oblika napake se v praksi dogaja.\n")

    # ── the real audit ──────────────────────────────────────────────────────
    print("REVIZIJA — dejanska strategija")
    leaks, n_full = audit(raw, cfg, dates, peek=None)
    out = {"symbol": SYMBOL, "n_bars": int(n_full), "n_dates": len(dates),
           "from": str(dates[0].date()), "to": str(dates[-1].date()),
           "required_history": int(need), "seed": SEED,
           "control_detected_pct": {k: round(v, 1) for k, v in hits.items()},
           "n_leaking_dates": len(leaks), "leaks": leaks}

    if not leaks:
        print(f"  {len(dates)} datumov · {len(FEATURE_COLS)} značilk · "
              f"{len(STATE_COLS)} stanj")
        print("  NOBENE RAZLIKE. Vrednost na dan T se ne spremeni, ko postanejo")
        print("  na voljo podatki po T. Pogleda v prihodnost ni.")
        out["verdict"] = "cisto"
    else:
        print(f"  POGLED V PRIHODNOST NA {len(leaks)} DATUMIH")
        cnt: dict[str, int] = {}
        for v in leaks.values():
            for c in v["features"] + v["state"]:
                cnt[c] = cnt.get(c, 0) + 1
        for c, n in sorted(cnt.items(), key=lambda x: -x[1]):
            print(f"    {c:24} {n:4d} datumov")
        print("  USTAVI VSE. Dokler to ni popravljeno, so vse dosedanje številke")
        print("  brez pomena.")
        out["verdict"] = "puscanje"

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0 if not leaks else 2


if __name__ == "__main__":
    sys.exit(main())
