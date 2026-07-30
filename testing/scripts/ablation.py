"""Evidence for (or against) removing each component — BTC only, net of costs.

Two separate questions, deliberately kept apart because conflating them is how
the earlier "delete the 50-day MA" recommendation went wrong:

  A. Is the RULE useless?      -> switch the rule off entirely, compare backtests.
  B. Is the KNOB useless?      -> sweep the knob across a wide range with the rule
                                  still on. A flat sweep means "stop tuning this",
                                  NOT "delete the rule".

A rule can be indispensable while its knob is inert; `ma_med_len` is exactly that
case. Only a rule that fails A is a deletion candidate.

Paired block bootstrap throughout: the same resampled day indices are applied to
both return series, so the interval is on the DIFFERENCE and the common market
movement cancels.
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

from shared.costs import net_returns
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

SYMBOL, FEE = "BTC", 0.30
NBOOT, BLOCK, SEED = 2000, 20, 20260729
OUT = ROOT / "testing" / "data" / "ablation_BTC.json"

# Switching a rule OFF is done by pushing its threshold out of reach, never by
# editing the strategy — the code path under test stays the shipped one.
ABLATIONS = [
    ("baseline",      {},                                             "vse pravilo vklopljeno"),
    ("brez_vol_shock", {"vol_shock_mul": 999.0},                       "vol-shock izklopljen"),
    ("brez_blowoff",  {"blowoff_dist_pct": 9999.0},                    "blow-off izklopljen"),
    ("brez_obeh",     {"vol_shock_mul": 999.0, "blowoff_dist_pct": 9999.0}, "oba izklopljena"),
]

# knob, values to sweep, whether the underlying RULE is also being questioned
SWEEPS = [
    ("ma_med_len",         [20, 30, 40, 50, 60, 80, 100, 120]),
    ("rsi_len",            [7, 10, 14, 21, 28]),
    ("vol_shock_mul",      [1.2, 1.5, 1.8, 2.2, 2.6, 3.0]),
    ("vol_lookback",       [10, 14, 20, 30, 40]),
    ("min_dist_entry_pct", [0.0, 0.5, 1.0, 2.0, 3.0]),
    ("blowoff_dist_pct",   [15.0, 20.0, 25.0, 30.0, 35.0]),
]


def sortino(r: np.ndarray) -> float:
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(365)
    return float(r.mean() * 365 / d) if d > 1e-12 else float("nan")


def maxdd(r: np.ndarray) -> float:
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def cagr(r: np.ndarray) -> float:
    eq = float(np.prod(1.0 + r))
    return float((eq ** (365.0 / len(r)) - 1.0) * 100.0)


def _block_index(rng, n, B, L):
    nb = int(np.ceil(n / L))
    st = rng.integers(0, n, size=(B, nb))
    return (st[:, :, None] + np.arange(L)[None, None, :]).reshape(B, nb * L)[:, :n] % n


def paired_ci(a: np.ndarray, b: np.ndarray, fn, rng):
    """CI for fn(a) - fn(b), same resampled days applied to both."""
    idx = _block_index(rng, len(a), NBOOT, BLOCK)
    d = np.array([fn(a[i]) - fn(b[i]) for i in idx])
    d = d[np.isfinite(d)]
    lo, hi = np.percentile(d, [2.5, 97.5])
    return round(float(lo), 3), round(float(hi), 3), bool(lo > 0 or hi < 0)


def run(raw, **kw):
    cfg = engine.make_config("lean", **kw)
    df = trim_warmup(engine.strategy_module("lean")
                     .run_strategy(raw, btc_daily=None, config=cfg).df)
    pos = pd.Series(engine.position(df, s_bull_code=1), index=df.index)
    r = net_returns(pos, raw["close"].pct_change().fillna(0.0), FEE)
    return r.to_numpy(float), pos.to_numpy(float), df


def exit_reasons(df, cfg) -> dict:
    """Attribute every BULL->BEAR transition to the branch that caused it.

    The order below mirrors the elif chain in run_state_machine; reading it off
    the columns rather than instrumenting the loop keeps the shipped code path
    untouched, at the cost of having to keep the two in step.
    """
    st = df["signal_state"].to_numpy()
    bl = df["below_tl"].fillna(False).to_numpy()
    bc = df["below_count"].to_numpy()
    bo = df["blowoff"].fillna(False).to_numpy()
    vs = df["vol_shock"].fillna(False).to_numpy()
    out = {"below_tl": 0, "blowoff": 0, "vol_shock": 0}
    for i in range(1, len(st)):
        if not (st[i] != 1 and st[i - 1] == 1):
            continue
        if bl[i] and bc[i] >= cfg.exit_grace_bars:
            out["below_tl"] += 1
        elif bo[i]:
            out["blowoff"] += 1
        elif vs[i]:
            out["vol_shock"] += 1
    return out


def main():
    raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance_warmup.parquet")
    rng = np.random.default_rng(SEED)
    out = {"symbol": SYMBOL, "fee_per_side_pct": FEE, "nboot": NBOOT, "block": BLOCK}

    base_r, base_pos, base_df = run(raw)
    out["baseline"] = {"sortino": round(sortino(base_r), 3), "maxdd": round(maxdd(base_r), 1),
                       "cagr": round(cagr(base_r), 1),
                       "exposure": round(float(base_pos.mean() * 100), 1),
                       "trades": int((np.diff(base_pos, prepend=base_pos[0]) > 0).sum()),
                       "exit_reasons": exit_reasons(base_df, engine.make_config("lean"))}
    print(f"izhodišče: Sortino {out['baseline']['sortino']}  MaxDD {out['baseline']['maxdd']} %  "
          f"CAGR {out['baseline']['cagr']} %  izpostavljenost {out['baseline']['exposure']} %  "
          f"poslov {out['baseline']['trades']}")
    print("  izstopi po vzroku: " + ", ".join(f"{k}={v}" for k, v in
          out["baseline"]["exit_reasons"].items()))

    print("\nA. IZKLOP PRAVILA (ali je pravilo sploh potrebno)")
    abl = []
    for name, kw, label in ABLATIONS:
        r, pos, _ = run(raw, **kw)
        row = {"name": name, "label": label,
               "sortino": round(sortino(r), 3), "maxdd": round(maxdd(r), 1),
               "cagr": round(cagr(r), 1), "exposure": round(float(pos.mean() * 100), 1),
               "trades": int((np.diff(pos, prepend=pos[0]) > 0).sum())}
        if name != "baseline":
            lo, hi, sig = paired_ci(r, base_r, sortino, rng)
            row["d_sortino"] = round(row["sortino"] - out["baseline"]["sortino"], 3)
            row["ci_d_sortino"] = [lo, hi]
            row["sig"] = sig
            lo2, hi2, sig2 = paired_ci(r, base_r, maxdd, rng)
            row["d_maxdd"] = round(row["maxdd"] - out["baseline"]["maxdd"], 1)
            row["ci_d_maxdd"] = [round(lo2, 1), round(hi2, 1)]
            row["sig_maxdd"] = sig2
            print(f"  {label:24} Sortino {row['sortino']:.3f} ({row['d_sortino']:+.3f}, "
                  f"CI [{lo:+.2f},{hi:+.2f}]{'  ZNAČILNO' if sig else ''})   "
                  f"MaxDD {row['maxdd']:.1f} % ({row['d_maxdd']:+.1f} o.t.)   "
                  f"poslov {row['trades']}")
        abl.append(row)
    out["ablations"] = abl

    print("\nB. PRELET GUMBA (ali je gumb sploh vreden nastavljanja) — pravilo ostaja vklopljeno")
    sw = []
    for knob, vals in SWEEPS:
        pts = []
        for v in vals:
            r, pos, _ = run(raw, **{knob: v})
            pts.append({"value": v, "sortino": round(sortino(r), 3),
                        "maxdd": round(maxdd(r), 1),
                        "trades": int((np.diff(pos, prepend=pos[0]) > 0).sum())})
        s = [p["sortino"] for p in pts]
        rng_s = max(s) - min(s)
        sw.append({"knob": knob, "points": pts, "range_sortino": round(rng_s, 3),
                   "inert": bool(rng_s < 0.10)})
        print(f"  {knob:20} Sortino {min(s):.3f}–{max(s):.3f}  razpon {rng_s:.3f}"
              f"{'   MRTEV GUMB' if rng_s < 0.10 else ''}")
        print("       " + "  ".join(f"{p['value']}:{p['sortino']:.2f}" for p in pts))
    out["sweeps"] = sw

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
