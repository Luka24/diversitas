"""Do macro risk gates help Lean? BTC and ETH, from 2021.

Design is fixed in testing/nacrt_makro_varovalke.md and was written before this
ran. Read that first; the short version is one gate shape for every series
(value against its own MA200), a closed list of variants, and four acceptance
criteria set in advance.

The sample is the thing to keep in mind: 11 trades on BTC since 2021, 8 on ETH.
Nothing can be concluded at trade level, so everything here is measured on daily
returns, where BTC has 730 days in position and 365 of them losing.

    python testing/scripts/macro_gates.py
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "testing", ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared.costs import net_returns
from shared.warmup import trim_warmup
from testing.scripts import engine
from testing.scripts.macro_data import load as load_macro

np.seterr(all="ignore")

FEE, PPY = 0.30, 365      # PERCENT per side — net_returns divides by 100
START = "2021-01-01"
MA = 200                      # the strategy's own regime length, not tuned here
S_BLOCKS, PURGE = 12, 21
NBOOT, BLOCK, N_SHIFT = 5000, 20, 1000
OUT = ROOT / "testing" / "data" / "macro_gates.json"
rng = np.random.default_rng(20260811)

# name -> (column, True if HIGH is bad)
SERIES = {"DXY": ("dxy", True), "kredit": ("credit", False),
          "VIX": ("vix", True), "MOVE": ("move", True)}
VARIANTS = ["A brez", "B DXY", "C kredit", "D VIX", "E MOVE", "F vsi", "G vecina"]
MODES = ["vstop", "vstop+izstop"]


def sortino(r: np.ndarray) -> float:
    d = r[r < 0]
    if len(d) == 0 or d.std() == 0:
        return float("nan")
    return float(r.mean() / d.std() * np.sqrt(PPY))


def maxdd(r: np.ndarray) -> float:
    eq = np.cumprod(1 + r)
    return float((eq / np.maximum.accumulate(eq) - 1).min() * 100)


def risk_flags(macro: pd.DataFrame, index: pd.DatetimeIndex) -> dict:
    """One boolean per series: True = risk is OK. Same shape for all of them."""
    out = {}
    for name, (col, high_bad) in SERIES.items():
        s = macro[col]
        ma = s.rolling(MA, min_periods=MA).mean()
        ok = (s < ma) if high_bad else (s > ma)
        out[name] = ok.reindex(index).ffill().fillna(True).astype(bool)
    return out


def gate_for(variant: str, flags: dict, index) -> pd.Series:
    """Always a Series on `index`. It used to hand back a bare array for one
    variant, which silently aligned by position against a longer frame."""
    if variant.startswith("A"):
        return pd.Series(True, index=index)
    if variant.startswith("F"):
        out = flags[next(iter(SERIES))].copy()
        for k in SERIES:
            out &= flags[k]
        return out
    if variant.startswith("G"):
        return sum(flags[k].astype(int) for k in SERIES) >= 3
    return flags[variant.split()[1]]


def build(raw: pd.DataFrame, gate, mode: str):
    """Run Lean with `gate` ANDed into entry, and optionally into the exit."""
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    # Align by DATE, never by position — the gate is built on the macro index and
    # the feature frame is longer.
    g = gate.reindex(df.index).ffill().fillna(True).astype(bool)

    df["bull_condition"] = (df["bull_condition"] & g).fillna(False)
    if mode == "vstop+izstop":
        # Force the exit through the same door the trend break uses, so it
        # inherits the three-day confirmation rather than firing on one bad day.
        df["below_tl"] = (df["below_tl"] | ~g).fillna(False)
        df["trend_break"] = df["below_tl"]

    st = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos[pos.index >= START]


def met(pos: pd.Series, ret: pd.Series) -> dict:
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = float(np.cumprod(1 + r)[-1])
    return {"sortino": round(sortino(r), 3),
            "cagr": round((eq ** (PPY / len(r)) - 1) * 100, 1),
            "maxdd": round(maxdd(r), 1), "final": round(eq, 2),
            "exposure": round(float(pos.mean() * 100), 1),
            "trades": int((np.diff(pos.to_numpy(), prepend=pos.iloc[0]) > 0).sum())}


def boot_ci(a: np.ndarray, b: np.ndarray) -> tuple:
    """Paired block bootstrap on the Sortino difference."""
    n = len(a)
    kb = int(np.ceil(n / BLOCK))
    ds = []
    for lo in range(0, NBOOT, 500):
        m = min(500, NBOOT - lo)
        st = rng.integers(0, n, size=(m, kb))
        ii = (st[:, :, None] + np.arange(BLOCK)[None, None, :]
              ).reshape(m, kb * BLOCK)[:, :n] % n
        ds.append(np.array([sortino(a[i]) - sortino(b[i]) for i in ii]))
    d = np.concatenate(ds)
    d = d[np.isfinite(d)]
    return tuple(round(float(x), 3) for x in np.percentile(d, [2.5, 97.5]))


def placebo(raw, gate, mode, ret, real: float) -> float:
    """Rotate the gate. Keeps how often it blocks and how it clusters, destroys
    when. If the real alignment is not better than a random one, the filter is
    just spending less time in the market."""
    g = np.asarray(gate, dtype=bool)
    n = len(g)
    scores = []
    for k in rng.integers(1, n, size=N_SHIFT // 10):
        p = build(raw, pd.Series(np.roll(g, int(k)), index=gate.index), mode)
        scores.append(sortino(net_returns(p, ret, FEE).to_numpy(float)))
    scores = np.array([s for s in scores if np.isfinite(s)])
    return round(float((scores < real).mean() * 100), 1)


def pbo(mat: np.ndarray, names: list) -> tuple:
    blocks = np.array_split(np.arange(mat.shape[1]), S_BLOCKS)
    below = tot = 0
    picks = {c: 0 for c in names}
    for sel in itertools.combinations(range(S_BLOCKS), S_BLOCKS // 2):
        isx = np.concatenate([b[PURGE:len(b) - PURGE] if len(b) > 2 * PURGE else b
                              for b in (blocks[i] for i in sel)])
        oos = np.concatenate([blocks[i] for i in range(S_BLOCKS) if i not in sel])
        si = np.array([sortino(m[isx]) for m in mat])
        so = np.array([sortino(m[oos]) for m in mat])
        if not (np.isfinite(si).all() and np.isfinite(so).all()):
            continue
        k = int(np.argmax(si))
        picks[names[k]] += 1
        tot += 1
        below += int((so < so[k]).sum() / (len(names) - 1) < 0.5)
    return (round(below / tot, 3) if tot else float("nan"),
            {k: v for k, v in picks.items() if v})


def main() -> int:
    macro = load_macro()
    out = {"start": START, "ma": MA, "lag_days": 1}

    for sym, f in (("BTC", "BTC_binance_warmup.parquet"), ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / f)
        ret = raw["close"].pct_change().fillna(0.0)
        base_pos = build(raw, pd.Series(True, index=raw.index), "vstop")
        idx = base_pos.index
        # Flags span the WHOLE history, not just the measured window, so the
        # filter is in force before 2021 too and the position carried into the
        # window is the one it would really have had.
        flags = risk_flags(macro, raw.index)

        print(f"\n{'=' * 96}\n{sym}   {idx[0].date()} -> {idx[-1].date()}   "
              f"{len(idx)} dni   provizija 0,30 %/stran\n{'=' * 96}")
        print("  koliko casa je vsak filter 'v redu':  "
              + "   ".join(f"{k} {flags[k].reindex(idx).mean() * 100:.0f} %" for k in SERIES))

        base_r = net_returns(base_pos, ret, FEE).to_numpy(float)
        rows, series_for_pbo, names = {}, [base_r], ["A brez"]

        print(f"\n  {'celica':<22}{'Sortino':>9}{'CAGR':>8}{'MaxDD':>9}"
              f"{'konec':>8}{'izpost':>8}{'posl':>6}{'d Sortino':>11}   95 % CI")
        for mode in MODES:
            for v in VARIANTS:
                if v.startswith("A") and mode != MODES[0]:
                    continue                      # baseline has no mode
                gate = gate_for(v, flags, raw.index)
                pos = build(raw, gate, mode)
                m = met(pos, ret)
                r = net_returns(pos, ret, FEE).to_numpy(float)
                label = "A brez" if v.startswith("A") else f"{v} [{mode}]"
                if not v.startswith("A"):
                    m["delta"] = round(m["sortino"] - rows["A brez"]["sortino"], 3)
                    m["ci"] = boot_ci(r, base_r)
                    series_for_pbo.append(r)
                    names.append(label)
                    ci = f"[{m['ci'][0]:+.3f}, {m['ci'][1]:+.3f}]"
                    excl = "  IZKLJUCI 0" if (m["ci"][0] > 0 or m["ci"][1] < 0) else ""
                    d = f"{m['delta']:+.3f}"
                else:
                    ci, excl, d = "", "", ""
                rows[label] = m
                print(f"  {label:<22}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
                      f"{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{m['exposure']:>7.1f}%"
                      f"{m['trades']:>6d}{d:>11}   {ci}{excl}")

        p, picks = pbo(np.vstack(series_for_pbo), names)
        print(f"\n  PBO (s purgeom {PURGE}): {p}    izbire: "
              + ", ".join(f"{k.split()[0]}:{v}" for k, v in picks.items()))
        out[sym] = {"rows": rows, "pbo": p, "picks": picks,
                    "flags_on_pct": {k: round(float(flags[k].reindex(idx).mean() * 100), 1)
                                     for k in SERIES}}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
