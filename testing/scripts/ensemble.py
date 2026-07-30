"""What to do about the four parameters that sit on a sharp peak.

The sweep in porocilo_parametri_BTC.html found four knobs whose neighbours are
visibly worse, and three of them peak exactly on the shipped default. That is the
signature of a value that was chosen while looking at this history. This script
measures the three ways out, so the recommendation rests on numbers rather than
on the general principle that ensembles are good:

  1. PEAK PREMIUM. Run all 3^4 = 81 neighbours and average their positions. The
     gap between the single-point default and that average is a direct estimate
     of how much of the backtest came from picking the number.

  2. INTERACTION. The sweep moved one knob at a time, which is only valid if the
     knobs do not interact. Decomposing the 81-cell grid into main effects and
     two-way interactions says whether that assumption held — and therefore
     whether combinations have to be searched at all.

  3. ROBUST SINGLE VALUE. If an ensemble is too much machinery, the fallback is
     to keep one value but choose the centre of the widest flat region instead
     of the maximum. Computed here as the value maximising a 3-point moving
     average of the sweep.

Everything runs on the simplified strategy (blow-off and vol-shock switched off),
because that is what the deletion step leaves behind and tuning the version we
are about to discard would be wasted work.

Window matches porocilo_parametri_BTC.html: 2021-07-01 -> 2026-06-30.
Members have different ma_long_len and therefore different warm-up, so positions
are aligned on the INTERSECTION of indices before anything is compared.
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

from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

SYMBOL, FEE = "BTC", 0.30
WIN_FROM, WIN_TO = "2021-07-01", "2026-06-30"
NBOOT, BLOCK, SEED = 2000, 20, 20260730
OUT = ROOT / "testing" / "data" / "ensemble_BTC.json"

# The simplified strategy: the two exits that failed their own premise are off.
SIMPLE = {"vol_shock_mul": 999.0, "blowoff_dist_pct": 9999.0}

# The four sharp peaks and the neighbours to average over.
GRID = {
    "ma_long_len":     [150, 200, 250],
    "confirm_bars":    [2, 3, 4],
    "reentry_hold":    [10, 15, 20],
    "exit_grace_bars": [2, 3, 4],
}
DEFAULTS = {"ma_long_len": 200, "confirm_bars": 3, "reentry_hold": 15, "exit_grace_bars": 3}

# Sweep grids copied from porocilo_parametri_BTC.html so the robust-value
# calculation uses exactly the curve the report shows.
SWEEPS = {
    "ma_long_len":     ([100, 125, 150, 175, 200, 225, 250, 275, 300],
                        [1.002, 0.972, 0.900, 1.099, 1.219, 1.219, 1.119, 1.122, 1.091]),
    "confirm_bars":    ([1, 2, 3, 4, 5, 6, 7],
                        [1.302, 1.356, 1.219, 1.030, 1.239, 1.171, 1.229]),
    "reentry_hold":    ([0, 3, 6, 9, 12, 15, 18, 21, 25, 30],
                        [1.053, 1.008, 1.074, 0.971, 1.131, 1.219, 1.200, 1.027, 0.977, 1.062]),
    "exit_grace_bars": ([1, 2, 3, 4, 5, 6, 8],
                        [0.705, 1.022, 1.219, 1.047, 1.138, 1.045, 1.046]),
}


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(365)
    return float(r.mean() * 365 / d) if d > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def cagr(r):
    return float((float(np.prod(1.0 + r)) ** (365.0 / len(r)) - 1.0) * 100.0)


def _blocks(rng, n, B, L):
    nb = int(np.ceil(n / L))
    st = rng.integers(0, n, size=(B, nb))
    return (st[:, :, None] + np.arange(L)[None, None, :]).reshape(B, nb * L)[:, :n] % n


def paired_ci(a, b, fn, rng):
    idx = _blocks(rng, len(a), NBOOT, BLOCK)
    d = np.array([fn(a[i]) - fn(b[i]) for i in idx])
    d = d[np.isfinite(d)]
    return round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)


def member_position(raw, **kw) -> pd.Series:
    cfg = engine.make_config("lean", **{**SIMPLE, **kw})
    df = trim_warmup(engine.strategy_module("lean")
                     .run_strategy(raw, btc_daily=None, config=cfg).df)
    return pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)


def metrics(pos: pd.Series, ret: pd.Series) -> dict:
    r = net_returns(pos, ret, FEE).to_numpy(float)
    return {"sortino": round(sortino(r), 3), "maxdd": round(maxdd(r), 1),
            "cagr": round(cagr(r), 1), "expo": round(float(pos.mean() * 100), 1),
            "turnover": round(float(turnover(pos).sum()), 1)}, r


def robust_value(xs, ys):
    """Value maximising a 3-point moving average — the centre of the flattest high
    region rather than the single best point."""
    best_i, best_v = 0, -1e9
    for i in range(len(xs)):
        lo, hi = max(0, i - 1), min(len(xs), i + 2)
        v = float(np.mean(ys[lo:hi]))
        if v > best_v:
            best_i, best_v = i, v
    return xs[best_i], round(best_v, 3)


def main():
    raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance.parquet")
    ret_full = raw["close"].pct_change().fillna(0.0)
    rng = np.random.default_rng(SEED)

    keys = list(GRID)
    combos = list(itertools.product(*(GRID[k] for k in keys)))
    print(f"{len(combos)} članov ({' x '.join(str(len(GRID[k])) for k in keys)})")

    pos_map: dict[tuple, pd.Series] = {}
    for c in combos:
        pos_map[c] = member_position(raw, **dict(zip(keys, c)))

    # R2 from the plan: members warm up at different speeds; align on the
    # intersection or the ensemble is biased by whoever happens to be present.
    common = None
    for s in pos_map.values():
        common = s.index if common is None else common.intersection(s.index)
    win = common[(common >= WIN_FROM) & (common <= WIN_TO)]
    print(f"presek indeksov: {common[0].date()} -> {common[-1].date()} ({len(common)})")
    print(f"okno primerjave: {win[0].date()} -> {win[-1].date()} ({len(win)} dni)")

    ret = ret_full.reindex(win)
    P = {c: s.reindex(win) for c, s in pos_map.items()}

    dflt = tuple(DEFAULTS[k] for k in keys)
    m_point, r_point = metrics(P[dflt], ret)

    ens_pos = pd.Series(np.mean([P[c].to_numpy() for c in combos], axis=0), index=win)
    m_ens, r_ens = metrics(ens_pos, ret)

    lo, hi = paired_ci(r_point, r_ens, sortino, rng)
    lo_dd, hi_dd = paired_ci(r_point, r_ens, maxdd, rng)
    premium = round(m_point["sortino"] - m_ens["sortino"], 3)

    scores = {c: metrics(P[c], ret)[0]["sortino"] for c in combos}
    vals = np.array(list(scores.values()))
    pct_default = float((vals < m_point["sortino"]).mean() * 100)

    print(f"\nena točka (privzetki) : Sortino {m_point['sortino']}  MaxDD {m_point['maxdd']} %  "
          f"promet {m_point['turnover']}")
    print(f"ansambel {len(combos)} članov  : Sortino {m_ens['sortino']}  MaxDD {m_ens['maxdd']} %  "
          f"promet {m_ens['turnover']}")
    print(f"PREMIJA KONICE       : {premium:+.3f}  95 % CI [{lo:+.3f}, {hi:+.3f}]"
          f"{'   ZNAČILNA' if (lo > 0 or hi < 0) else '   ni značilna'}")
    print(f"                       MaxDD razlika {m_point['maxdd']-m_ens['maxdd']:+.1f} o. t. "
          f"CI [{lo_dd:+.1f}, {hi_dd:+.1f}]")
    print(f"privzetki so boljši od {pct_default:.0f} % vseh {len(combos)} sosedov "
          f"(razpon {vals.min():.3f}–{vals.max():.3f})")

    # ── interactions: is one-at-a-time tuning even valid? ───────────────────
    shape = tuple(len(GRID[k]) for k in keys)
    A = np.array([scores[c] for c in combos]).reshape(shape)
    grand = float(A.mean())
    main_eff = {}
    for i, k in enumerate(keys):
        marg = A.mean(axis=tuple(j for j in range(len(keys)) if j != i))
        main_eff[k] = round(float(marg.max() - marg.min()), 3)
    inter = {}
    for i, j in itertools.combinations(range(len(keys)), 2):
        others = tuple(x for x in range(len(keys)) if x not in (i, j))
        cell = A.mean(axis=others)
        ri = cell.mean(axis=1, keepdims=True)
        cj = cell.mean(axis=0, keepdims=True)
        resid = cell - ri - cj + grand
        inter[f"{keys[i]} x {keys[j]}"] = round(float(np.abs(resid).max()), 3)

    print("\nGLAVNI UČINKI (koliko parameter premakne Sortino sam zase):")
    for k, v in sorted(main_eff.items(), key=lambda x: -x[1]):
        print(f"  {k:18} {v:.3f}")
    print("INTERAKCIJE (koliko učinek enega je odvisen od drugega):")
    for k, v in sorted(inter.items(), key=lambda x: -x[1]):
        print(f"  {k:38} {v:.3f}")
    worst_i = max(inter.values()); biggest_m = max(main_eff.values())
    print(f"  -> največja interakcija je {worst_i/biggest_m*100:.0f} % največjega glavnega učinka")

    # ── robust single values ────────────────────────────────────────────────
    print("\nČE OSTANEMO PRI ENI VREDNOSTI — vrh proti sredini ravnine:")
    rob = {}
    for k, (xs, ys) in SWEEPS.items():
        ys = np.array(ys, float)
        i_def = xs.index(DEFAULTS[k])
        peak_v = xs[int(np.argmax(ys))]
        rv, rscore = robust_value(xs, ys)
        nb = [ys[i] for i in (i_def - 1, i_def + 1) if 0 <= i < len(ys)]
        rob[k] = {"default": DEFAULTS[k], "peak": peak_v, "robust": rv,
                  "score_default": round(float(ys[i_def]), 3),
                  "drop_to_neighbour": round(float(ys[i_def] - max(nb)), 3),
                  "worst_neighbour_drop": round(float(ys[i_def] - min(nb)), 3)}
        print(f"  {k:18} privzeto {DEFAULTS[k]:>4} (Sortino {ys[i_def]:.3f}) · "
              f"vrh {peak_v:>4} · robustna izbira {rv:>4} · "
              f"padec na najslabšega soseda {ys[i_def]-min(nb):+.3f}")

    out = {"symbol": SYMBOL, "fee_per_side_pct": FEE,
           "window": [str(win[0].date()), str(win[-1].date())], "n_days": len(win),
           "members": len(combos), "grid": GRID, "defaults": DEFAULTS,
           "simplified": SIMPLE,
           "point": m_point, "ensemble": m_ens,
           "peak_premium": premium, "ci_peak_premium": [lo, hi],
           "sig_peak_premium": bool(lo > 0 or hi < 0),
           "d_maxdd": round(m_point["maxdd"] - m_ens["maxdd"], 1),
           "ci_d_maxdd": [lo_dd, hi_dd],
           "default_percentile_among_members": round(pct_default, 1),
           "member_sortino": {"min": round(float(vals.min()), 3),
                              "max": round(float(vals.max()), 3),
                              "mean": round(float(vals.mean()), 3),
                              "sd": round(float(vals.std()), 3),
                              "all": [round(float(v), 3) for v in vals]},
           "main_effects": main_eff, "interactions": inter,
           "robust_values": rob,
           "nboot": NBOOT, "block": BLOCK, "seed": SEED}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
