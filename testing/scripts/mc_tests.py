"""Is the strategy better than luck? Two tests, each fixing an earlier mistake.

TEST 1 — TIMING OF RETURN. Shuffle the market, re-run the strategy, ask whether
the real result stands out. The first version of this was CONFOUNDED BY DRIFT:
bitcoin rose over the sample, a shuffled path still rises, and any filter that is
long part of the time looks good on it. The mean Sortino on shuffled data came out
at +0.61, which is that drift and nothing else — so the test was measuring the
market, not the strategy. Here the drift is removed before shuffling, which
isolates the only thing worth asking: does the timing add anything?

TEST 2 — TIMING OF DRAWDOWN. The product claims shallower drawdowns, not higher
returns, so that is what has to be tested. White's Reality Check on mean return
answered a question nobody asked, and my first attempt to redirect it at the
drawdown gap was mis-constructed (it compared each configuration against itself,
giving p ~ 0.5 by construction).

The replacement keeps everything about the strategy's behaviour fixed — the exact
in-market and out-of-market spells, so the same exposure and the same number of
holding periods — and only shuffles their ORDER. That asks precisely: of all the
ways to spend 43% of six years in bitcoin, how good is the strategy's particular
arrangement at avoiding the deep falls?

Output: testing/data/mc_tests_BTC.json
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
NPERM, NSHUF, SEED = 1000, 2000, 20260730
OUT = ROOT / "testing" / "data" / "mc_tests_BTC.json"


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(365)
    return float(r.mean() * 365 / d) if d > 1e-12 else np.nan


def maxdd_from_returns(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def run_on(frame):
    cfg = engine.make_config("lean")
    df = trim_warmup(engine.strategy_module("lean")
                     .run_strategy(frame, btc_daily=None, config=cfg).df)
    pos = pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)
    r = net_returns(pos, frame["close"].pct_change().fillna(0.0), FEE)
    return r.to_numpy(float), pos.to_numpy(float)


def synth(rr, index, p0, hi_r, lo_r):
    close = p0 * np.cumprod(1.0 + rr)
    s = pd.DataFrame(index=index)
    s["close"] = close
    s["open"] = np.concatenate([[p0], close[:-1]])
    s["high"] = close * hi_r
    s["low"] = close * lo_r
    s["volume"] = 1.0
    return s


def spells(pos: np.ndarray) -> list[tuple[int, int]]:
    """The in/out runs, as (state, length). Shuffling these keeps exposure and
    the number of holding periods exactly as the strategy produced them."""
    out, cur, n = [], int(pos[0] > 0), 1
    for v in pos[1:]:
        s = int(v > 0)
        if s == cur:
            n += 1
        else:
            out.append((cur, n)); cur, n = s, 1
    out.append((cur, n))
    return out


def main():
    raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance_warmup.parquet")
    rng = np.random.default_rng(SEED)
    real_r, real_pos = run_on(raw)
    real_s = sortino(real_r)

    ret = raw["close"].pct_change().fillna(0.0).to_numpy(float)[1:]
    idx, p0 = raw.index[1:], float(raw["close"].iloc[0])
    hi_r = float((raw["high"] / raw["close"]).median())
    lo_r = float((raw["low"] / raw["close"]).median())
    mu = float(ret.mean())
    dm = ret - mu                       # same shape and volatility, zero drift

    real_dm_r, _ = run_on(synth(dm, idx, p0, hi_r, lo_r))
    real_dm_s = sortino(real_dm_r)

    out = {"symbol": SYMBOL, "fee_per_side_pct": FEE, "seed": SEED,
           "real_sortino": round(real_s, 3),
           "real_sortino_demeaned": round(real_dm_s, 3),
           "drift_annual_pct": round(mu * 365 * 100, 1)}
    print(f"resnicni BTC             Sortino {real_s:.3f}")
    print(f"resnicni BTC brez rasti  Sortino {real_dm_s:.3f}   <- kar ostane brez drifta")
    print(f"  (rast BTC v vzorcu: {mu*365*100:.0f} % letno)\n")

    # ── TEST 1: return timing, drift removed ───────────────────────────────
    for tag, blk in (("iid", 1), ("block20", 20)):
        vals = []
        for _ in range(NPERM):
            if blk == 1:
                sh = rng.permutation(dm)
            else:
                nb = int(np.ceil(len(dm) / blk))
                st = rng.integers(0, max(1, len(dm) - blk), size=nb)
                sh = np.concatenate([dm[s:s + blk] for s in st])[:len(dm)]
            try:
                r, _ = run_on(synth(sh, idx, p0, hi_r, lo_r))
                vals.append(sortino(r))
            except Exception:
                continue
        v = np.array([x for x in vals if np.isfinite(x)])
        pv = float((v >= real_dm_s).mean())
        out[f"perm_{tag}"] = {
            "n": len(v), "mean": round(float(v.mean()), 3), "sd": round(float(v.std()), 3),
            "p95": round(float(np.percentile(v, 95)), 3),
            "percentile": round(float((v < real_dm_s).mean() * 100), 1),
            "p_value": round(pv, 4), "significant": bool(pv < 0.05),
            "hist": np.histogram(v, bins=20, range=(-2.0, 2.5))[0].tolist(),
            "bins": [round(x, 3) for x in np.histogram_bin_edges(v, bins=20, range=(-2.0, 2.5))],
        }
        print(f"  premesan trg ({tag:8}): povprecje {v.mean():+.3f} · "
              f"resnicni {real_dm_s:.3f} je nad {(v < real_dm_s).mean()*100:.1f} % · p = {pv:.4f}"
              f"{'  ZNACILNO' if pv < 0.05 else '  ni znacilno'}")

    # ── TEST 2: drawdown timing, exposure held fixed ───────────────────────
    bench = raw["close"].pct_change().fillna(0.0).reindex(
        pd.Index(raw.index[-len(real_pos):])).to_numpy(float)
    bench = bench[-len(real_pos):]
    sp = spells(real_pos)
    n_hold = sum(1 for s, _ in sp if s == 1)
    real_dd = maxdd_from_returns(real_r)
    bh_dd = maxdd_from_returns(bench)
    # Both drawdowns are negative. A SHALLOWER drawdown than buy & hold is the
    # good outcome, so the gap has to be strategy - benchmark: -39.8 - (-76.6)
    # = +36.8. Writing it the other way round flips the sign of the whole test
    # and turns p = 0.028 into p = 0.972.
    def gap_of(dd): return dd - bh_dd

    real_gap = gap_of(real_dd)

    gaps = np.empty(NSHUF)
    for b in range(NSHUF):
        order = rng.permutation(len(sp))
        pos = np.concatenate([np.full(sp[i][1], float(sp[i][0])) for i in order])[:len(bench)]
        gaps[b] = gap_of(maxdd_from_returns(net_returns(
            pd.Series(pos), pd.Series(bench), FEE).to_numpy(float)))
    pv = float((gaps >= real_gap).mean())
    out["exposure_shuffle"] = {
        "n": NSHUF, "exposure_pct": round(float(real_pos.mean() * 100), 1),
        "holding_periods": n_hold,
        "buyhold_maxdd": round(bh_dd, 1), "strategy_maxdd": round(real_dd, 1),
        "real_gap": round(real_gap, 1),
        "shuffled_mean_gap": round(float(gaps.mean()), 1),
        "shuffled_p95_gap": round(float(np.percentile(gaps, 95)), 1),
        "percentile": round(float((gaps < real_gap).mean() * 100), 1),
        "p_value": round(pv, 4), "significant": bool(pv < 0.05),
        "hist": np.histogram(gaps, bins=24)[0].tolist(),
        "bins": [round(x, 2) for x in np.histogram_bin_edges(gaps, bins=24)],
    }
    print(f"\n  kupi-in-drzi MaxDD {bh_dd:.1f} % · strategija {real_dd:.1f} % · "
          f"razlika {real_gap:+.1f} o. t.")
    print(f"  ista izpostavljenost ({real_pos.mean()*100:.1f} %), istih {n_hold} obdobij, "
          f"premesan vrstni red:")
    print(f"    nakljucna razporeditev v povprecju {gaps.mean():+.1f} o. t. · "
          f"resnicna je nad {(gaps < real_gap).mean()*100:.1f} % · p = {pv:.4f}"
          f"{'  ZNACILNO' if pv < 0.05 else '  ni znacilno'}")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
