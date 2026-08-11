"""Does Donchian confirmation earn its place, or only its sweep?

Pre-registered in `testing/nacrt_korak6_donchian.md`, committed before this ran.

Donchian requires the close to sit in the top quartile of the N-day high/low
channel — a real breakout rather than a trackline crossing. It is already in the
engine, switched off, and an earlier sweep put BTC Sortino at 1.72-1.76 for
periods 12-22 against 1.55 disabled.

Those numbers are a sweep, which is why the PRIMARY test here is a nested
walk-forward that picks the period from the training part only. That changes the
question from "which period was best" to "does picking from the past pay in the
future". The fixed sweep still runs, but only to read plateau against spike; the
argmax is not taken.

`donchian_top_frac` stays at its existing 0.75 and is not swept — sweeping both
would be a grid and double the trials for no extra insight.

Output: testing/data/donchian_BTC.json
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

SYMBOL, FEE, PPY, H = "BTC", 0.30, 365, 20
SRC = ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance_warmup.parquet"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
OUT = ROOT / "testing" / "data" / f"donchian_{SYMBOL}.json"

PERIODS = [10, 12, 15, 20, 25, 30, 40, 55]
SCHEMES = [(3, 1), (2, 1)]                       # (train years, test years)
SUBPERIODS = [("I", "2019-03-09", "2021-01-31"), ("II", "2021-02-01", "2022-11-30"),
              ("III", "2022-12-01", "2024-09-30"), ("IV", "2024-10-01", "2026-07-29")]


def positions(raw: pd.DataFrame, period: int | None):
    """period=None -> Donchian off, i.e. today's engine."""
    kw = ({} if period is None
          else {"use_donchian": True, "donchian_period": int(period)})
    cfg = engine.make_config("lean", **kw)
    smod = engine.strategy_module("lean")
    df = trim_warmup(smod.run_strategy(raw, btc_daily=None, config=cfg).df)
    return pd.Series(engine.position(df, s_bull_code=1), index=df.index,
                     dtype=float), df


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def metrics(pos, ret):
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1.0 + r)
    p = pos.to_numpy()
    return {"sortino": round(sortino(r), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
            "exposure": round(float(p.mean() * 100), 1),
            "trades": int((np.diff(p, prepend=p[0]) > 0).sum()),
            "turnover": round(float(turnover(pos).sum()), 1)}


def window_sortino(pos, ret, a, b):
    w = pos.index[(pos.index >= a) & (pos.index <= b)]
    if len(w) < 30:
        return np.nan
    return sortino(net_returns(pos.reindex(w), ret, FEE).to_numpy(float))


def main() -> int:
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    out: dict = {"symbol": SYMBOL, "fee_per_side_pct": FEE,
                 "top_frac": 0.75, "periods": PERIODS,
                 "preregistered": "testing/nacrt_korak6_donchian.md"}

    print("KONTROLA — Donchian izklopljen proti zamrznjeni referenci")
    pos = {None: positions(raw, None)}
    ref = pd.read_parquet(REF)["position"]
    base = pos[None][0]
    same = base.index.equals(ref.index) and np.allclose(base.to_numpy(),
                                                        ref.to_numpy(), atol=1e-12)
    print(f"  ujema se: {same}")
    if not same:
        print("  Harness se moti na kontroli. USTAVLJAM.")
        return 2
    out["control_matches_reference"] = True

    for n in PERIODS:
        pos[n] = positions(raw, n)

    # ── fixed sweep: shape only ───────────────────────────────────────────
    print("\nFIKSNE PERIODE — oblika, argmaks se ne izbira")
    print(f"  {'N':>5}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
          f"{'izpost':>8}{'posl':>6}{'obrat':>7}   podobdobja I-IV")
    fixed = {}
    for key in [None] + PERIODS:
        m = metrics(pos[key][0], ret)
        m["sub"] = {n: round(float(window_sortino(pos[key][0], ret, a, b)), 3)
                    for n, a, b in SUBPERIODS}
        fixed["off" if key is None else str(key)] = m
        s = "  ".join(f"{m['sub'][n]:.2f}" for n, _, _ in SUBPERIODS)
        lbl = "izkl." if key is None else str(key)
        print(f"  {lbl:>5}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%{m['maxdd']:>7.1f}%"
              f"{m['final']:>6.2f}x{m['exposure']:>7.1f}%{m['trades']:>6d}"
              f"{m['turnover']:>7.1f}   {s}")
    out["fixed"] = fixed
    sw = [fixed[str(n)]["sortino"] for n in PERIODS]
    best = PERIODS[int(np.argmax(sw))]
    print(f"  razpon {max(sw)-min(sw):.3f}   najboljša {best}"
          f"{'  (NA ROBU)' if best in (PERIODS[0], PERIODS[-1]) else ''}"
          f"   izklopljeno {fixed['off']['sortino']:.3f}")

    # ── nested walk-forward: THE test ─────────────────────────────────────
    print("\nUGNEZDENI WALK-FORWARD — perioda izbrana SAMO iz učnega dela")
    idx = base.index
    wf = {}
    for tr_y, te_y in SCHEMES:
        folds, seg_refit, seg_off, seg_20 = [], [], [], []
        start = idx[0]
        while True:
            tr_a = start
            tr_b = tr_a + pd.DateOffset(years=tr_y)
            te_b = tr_b + pd.DateOffset(years=te_y)
            if te_b > idx[-1]:
                break
            sc = {n: window_sortino(pos[n][0], ret, tr_a, tr_b) for n in PERIODS}
            sc_off = window_sortino(base, ret, tr_a, tr_b)
            pick = max(sc, key=lambda k: (sc[k] if np.isfinite(sc[k]) else -9e9))
            te = idx[(idx > tr_b) & (idx <= te_b)]
            folds.append({"train": [str(tr_a.date()), str(tr_b.date())],
                          "test": [str(te[0].date()), str(te[-1].date())],
                          "pick": int(pick),
                          "train_sortino_pick": round(float(sc[pick]), 3),
                          "train_sortino_off": round(float(sc_off), 3)})
            seg_refit.append(pos[pick][0].reindex(te))
            seg_off.append(base.reindex(te))
            seg_20.append(pos[20][0].reindex(te))
            start = start + pd.DateOffset(years=te_y)
        if not folds:
            continue
        res = {}
        for nm, seg in (("refit", seg_refit), ("off", seg_off), ("fiksna 20", seg_20)):
            p = pd.concat(seg)
            res[nm] = metrics(p, ret)
        picks = [f["pick"] for f in folds]
        wf[f"{tr_y}y/{te_y}y"] = {"folds": folds, "picks": picks,
                                  "distinct_picks": len(set(picks)), "results": res}
        print(f"\n  shema učno {tr_y} leta / testno {te_y}   "
              f"{len(folds)} zavojev   izbrane periode: {picks}")
        print(f"    {'':12}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}{'posl':>6}")
        for nm in ("off", "refit", "fiksna 20"):
            m = res[nm]
            print(f"    {nm:<12}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%"
                  f"{m['maxdd']:>7.1f}%{m['final']:>6.2f}x{m['trades']:>6d}")
        beats = res["refit"]["sortino"] > res["off"]["sortino"]
        print(f"    refit prekaša izklopljeno: {'DA' if beats else 'NE'}")
    out["walk_forward"] = wf

    # ── what does Donchian actually keep us out of? ───────────────────────
    # Measured on the POSITION, not on bull_condition. A blocked entry signal on
    # a day we were already long changes nothing, so counting condition flips
    # overstates the footprint and mixes in days that were never in play.
    print("\nKAJ DONCHIAN DEJANSKO SPREMENI (perioda 20)")
    p20, p0 = pos[20][0], base
    cl = pos[None][1]["close"].to_numpy(float)
    n = len(p0)
    fwd = np.full(n, np.nan)
    fwd[:n - H] = (cl[H:] / cl[:n - H] - 1) * 100
    ok = np.isfinite(fwd)
    outof = (p0.to_numpy() > 0.5) & (p20.to_numpy() < 0.5)   # off long, D flat
    into = (p0.to_numpy() < 0.5) & (p20.to_numpy() > 0.5)    # D long, off flat
    bl = {"baseline": round(float(fwd[ok].mean()), 2)}
    print(f"  izhodišče, vsi dnevi: {fwd[ok].mean():+.2f} %")
    for tag, m in (("Donchian nas drži ZUNAJ", outof), ("Donchian nas drži NOTRI", into)):
        x = fwd[m & ok]
        bl[tag] = {"n": int(m.sum()),
                   "mean_fwd20": round(float(x.mean()), 2) if len(x) else None}
        if len(x):
            print(f"  {tag:24} {int(m.sum()):>4} dni   {x.mean():+6.2f} %"
                  f"   proti izhodišču {x.mean()-fwd[ok].mean():+.2f}")
    out["position_effect"] = bl

    # ── exposure matching ─────────────────────────────────────────────────
    # Donchian LOWERS exposure, so the baseline has to be scaled DOWN to meet it.
    # Scaling the variant up and clipping at 1 is a no-op on a binary series —
    # the first version of this did exactly that and printed the unmatched
    # numbers back, which would have let a drawdown artifact through for the
    # fourth time in this project.
    print("\nIZENAČENA IZPOSTAVLJENOST — izklopljeno pomanjšano na vsako periodo")
    print(f"  {'N':>5}{'izpost':>8}{'Sortino D':>11}{'Sortino izkl.':>14}"
          f"{'MaxDD D':>9}{'MaxDD izkl.':>12}")
    match = {}
    for nn in PERIODS:
        eV = fixed[str(nn)]["exposure"]
        pv = pos[nn][0]
        p_ref = (base * (eV / fixed["off"]["exposure"])).clip(0.0, 1.0)
        rv = net_returns(pv, ret, FEE).to_numpy(float)
        r0 = net_returns(p_ref, ret, FEE).to_numpy(float)
        match[str(nn)] = {"exposure": eV,
                          "sortino_d": round(sortino(rv), 3),
                          "sortino_off_scaled": round(sortino(r0), 3),
                          "maxdd_d": round(maxdd(rv), 1),
                          "maxdd_off_scaled": round(maxdd(r0), 1),
                          "exposure_off_scaled": round(float(p_ref.mean() * 100), 1)}
        m = match[str(nn)]
        print(f"  {nn:>5}{eV:>8.1f}{m['sortino_d']:>11.3f}"
              f"{m['sortino_off_scaled']:>14.3f}{m['maxdd_d']:>9.1f}"
              f"{m['maxdd_off_scaled']:>12.1f}")
    print("  Če je 'Sortino izkl.' po pomanjšanju enak Donchianovemu, je prednost")
    print("  posledica manj časa v trgu in ne izbire dni.")
    out["exposure_matched"] = match

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
