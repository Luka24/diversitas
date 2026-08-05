"""How much responsiveness does the dead band actually want?

Step 5 tested two points on a spectrum and found almost nothing. The obvious
follow-up is whether the band was simply not responsive enough. This sweeps
responsiveness directly, as a ONE-parameter family that contains today's engine
as an exact special case:

    band_t = anchor x ( vol_t / mean_w(vol) ) ** k

    k = 0    the ratio disappears, band is a flat 3 % -> today's engine
    k = 1    what step 5 called E/F
    k = 2    twice as reactive: a doubling of relative volatility quadruples
             the band
    w        the normalisation window: 50 days asks "unusual right now",
             expanding asks "unusual in absolute terms" (the Keltner form)

Two one-dimensional sweeps, not a grid: k at fixed w = 50, then w at fixed k = 1.
A grid would multiply the trial count for no extra insight into shape.

READ THE SHAPE, DO NOT TAKE THE ARGMAX. Written here before the run so it cannot
be quietly abandoned afterwards. PBO for this strategy is 0.694 — the best
in-sample setting lands below median out of sample about seven times in ten — so
the maximum of a sweep is not information about the future. A flat curve says
responsiveness does not matter; a spike says today's value is luck; a monotone
rise to the grid edge says the grid is too narrow.

k = 0 must reproduce the frozen reference bar for bar. That is a control built
into the sweep itself: if the family does not contain today's engine exactly,
every other row is measuring something else.

Only the ENTRY threshold is made adaptive. Step 5 established that adaptivity on
the exit side hurts (variant E 1.537 against F 1.576, and all 66 days between
them are exit-side), so sweeping it too would be spending trials on a question
already answered.

Output: testing/data/band_response_BTC.json
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

from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

SYMBOL, FEE, PPY = "BTC", 0.30, 365
SRC = ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance_warmup.parquet"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
OUT = ROOT / "testing" / "data" / f"band_response_{SYMBOL}.json"

K_GRID = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
W_GRID = [20, 50, 100, 250, "expanding"]
SUBPERIODS = [("I", "2019-03-09", "2021-01-31"), ("II", "2021-02-01", "2022-11-30"),
              ("III", "2022-12-01", "2024-09-30"), ("IV", "2024-10-01", "2026-07-29")]
BULL_TERMS = ("above_tl", "track_rising_window", "regime_ok",
              "btc_filter_ok", "donchian_ok")


def run(raw, cfg, k: float, w):
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    if k != 0.0:
        v = df["annual_vol"]
        ref = (v.expanding(min_periods=1).mean() if w == "expanding"
               else v.rolling(w, min_periods=max(5, w // 4)).mean())
        rel = (v / ref).replace([np.inf, -np.inf], np.nan).fillna(1.0)
        band = cfg.track_buf_pct * np.power(rel, k) / 100.0
        df["band_pct"] = band * 100.0
        df["above_tl"] = df["close"] > df["trackline"] * (1.0 + band)
        bull = pd.Series(True, index=df.index)
        for t in BULL_TERMS:
            bull &= df[t]
        df["bull_condition"] = (bull & ~df["blowoff"]).fillna(False)
        df["green_dot"] = df["bull_condition"]
    else:
        df["band_pct"] = float(cfg.track_buf_pct)
    st = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos, st


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def row(pos, st, raw, ret, base_pos):
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1.0 + r)
    p = pos.to_numpy()
    b = st["band_pct"]
    sub = {}
    for name, a, z in SUBPERIODS:
        w = pos.index[(pos.index >= a) & (pos.index <= z)]
        sub[name] = round(sortino(net_returns(pos.reindex(w), ret, FEE).to_numpy(float)), 3)
    return {"sortino": round(sortino(r), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(float((eq / np.maximum.accumulate(eq) - 1).min() * 100), 1),
            "final": round(float(eq[-1]), 2),
            "exposure": round(float(p.mean() * 100), 1),
            "trades": int((np.diff(p, prepend=p[0]) > 0).sum()),
            "turnover": round(float(turnover(pos).sum()), 1),
            "band_mean": round(float(b.mean()), 2),
            "band_p1": round(float(np.percentile(b, 1)), 2),
            "band_p99": round(float(np.percentile(b, 99)), 2),
            "days_vs_base": int((np.abs(p - base_pos.to_numpy()) > 1e-12).sum()),
            "sub": sub}


def show(title, rows, keyname):
    print(f"\n{title}")
    print(f"  {keyname:>10}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
          f"{'izpost':>7}{'posl':>5}{'pas p1-p99':>13}{'dni≠':>6}   podobdobja I-IV")
    for key, m in rows.items():
        s = "  ".join(f"{m['sub'][n]:.2f}" for n, _, _ in SUBPERIODS)
        print(f"  {str(key):>10}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%{m['maxdd']:>7.1f}%"
              f"{m['final']:>6.2f}x{m['exposure']:>6.1f}%{m['trades']:>5d}"
              f"{m['band_p1']:>6.2f}-{m['band_p99']:<6.2f}{m['days_vs_base']:>5d}   {s}")


def main() -> int:
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    cfg = engine.make_config("lean")

    base_pos, base_st = run(raw, cfg, 0.0, 50)
    ref = pd.read_parquet(REF)["position"]
    same = base_pos.index.equals(ref.index) and np.allclose(base_pos.to_numpy(),
                                                            ref.to_numpy(), atol=1e-12)
    print(f"KONTROLA — k = 0 proti zamrznjeni referenci: {'ujema se' if same else 'NE UJEMA'}")
    if not same:
        print("  Družina ne vsebuje današnjega motorja. USTAVLJAM.")
        return 2

    out = {"symbol": SYMBOL, "fee_per_side_pct": FEE,
           "note": "diagnostika oblike krivulje; argmaks se namenoma ne izbira"}

    ks = {}
    for k in K_GRID:
        pos, st = run(raw, cfg, k, 50)
        ks[k] = row(pos, st, raw, ret, base_pos)
    show("ODZIVNOST k  (okno normalizacije fiksno 50 dni)", ks, "k")
    out["sweep_k"] = {str(k): v for k, v in ks.items()}

    ws = {}
    for w in W_GRID:
        pos, st = run(raw, cfg, 1.0, w)
        ws[w] = row(pos, st, raw, ret, base_pos)
    show("OKNO NORMALIZACIJE w  (odzivnost fiksna k = 1)", ws, "w")
    out["sweep_w"] = {str(w): v for w, v in ws.items()}

    print("\nOBLIKA")
    sk = [ks[k]["sortino"] for k in K_GRID]
    sw = [ws[w]["sortino"] for w in W_GRID]
    for lbl, vals, grid in (("k", sk, K_GRID), ("w", sw, W_GRID)):
        rng = max(vals) - min(vals)
        best = grid[int(np.argmax(vals))]
        edge = best in (grid[0], grid[-1])
        print(f"  {lbl}: razpon Sortina {rng:.3f}   najboljša {best}"
              f"{'  (NA ROBU MREŽE)' if edge else ''}   izhodišče (k=0) {sk[0]:.3f}")
    out["shape"] = {"k_range": round(max(sk) - min(sk), 3),
                    "w_range": round(max(sw) - min(sw), 3),
                    "baseline_sortino": sk[0]}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
