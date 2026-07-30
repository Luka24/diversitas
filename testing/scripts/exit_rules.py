"""A second, harder look at the two exit rules recommended for removal.

Two rules failing at once is a suspicious result, and the first pass had a real
weakness: blow-off was compared against *all other days*. That is the same
mistake that was already caught and fixed for vol-shock. An exit rule is only
ever consulted when the strategy is holding, and blow-off specifically only when
price is far above the trackline, so its honest peer group is "days that were
already extended" — not the whole sample, most of which is nothing like the
situation the rule was written for.

Three things this adds:

  1. THE RIGHT PEER GROUP. Blow-off against other extended days; vol-shock
     against the below-trackline days on which it could actually act (the first
     two bars, before the ordinary exit takes over).

  2. DRAWDOWN, NOT RETURN. An exit rule's job is to avoid a fall, not to catch a
     rise. A rule can look bad on forward return and still earn its place if what
     follows is a deep drawdown. Forward MaxDD was computed in event_study.py and
     never displayed; here it is the primary measure.

  3. THE ACTUAL TRADES. For every exit blow-off caused, what the position would
     have done had it stayed. Six observations prove nothing on their own, but
     they show whether the aggregate is telling the truth about this strategy.

Output: testing/data/exit_rules_BTC.json
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
HORIZONS = (5, 20, 60)
NBOOT, SEED, MIN_GROUP = 2000, 20260731, 25
SRC = ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance_warmup.parquet"
OUT = ROOT / "testing" / "data" / "exit_rules_BTC.json"


def fwd_ret(c, h):
    o = np.full(len(c), np.nan); o[:-h] = (c[h:] / c[:-h] - 1) * 100; return o


def fwd_dd(c, h):
    o = np.full(len(c), np.nan)
    for t in range(len(c) - h):
        p = c[t:t + h + 1]
        o[t] = (p / np.maximum.accumulate(p) - 1).min() * 100
    return o


def _blocks(rng, n, B, L):
    nb = int(np.ceil(n / L))
    st = rng.integers(0, n, size=(B, nb))
    return (st[:, :, None] + np.arange(L)[None, None, :]).reshape(B, nb * L)[:, :n] % n


def compare(a, b, rng, h):
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < MIN_GROUP or len(b) < MIN_GROUP:
        return {"n_true": int(len(a)), "n_false": int(len(b)), "too_few": True}
    L = max(20, h)
    d = a[_blocks(rng, len(a), NBOOT, L)].mean(1) - b[_blocks(rng, len(b), NBOOT, L)].mean(1)
    lo, hi = np.percentile(d, [2.5, 97.5])
    return {"n_true": int(len(a)), "n_false": int(len(b)), "too_few": False,
            "mean_true": round(float(a.mean()), 2), "mean_false": round(float(b.mean()), 2),
            "diff": round(float(a.mean() - b.mean()), 2),
            "ci": [round(float(lo), 2), round(float(hi), 2)],
            "sig": bool(lo > 0 or hi < 0)}


def main():
    raw = pd.read_parquet(SRC)
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = trim_warmup(smod.run_strategy(raw, btc_daily=None, config=cfg).df)
    close = raw["close"].reindex(df.index).to_numpy(float)
    rng = np.random.default_rng(SEED)

    st = df["signal_state"].to_numpy()
    bl = df["below_tl"].fillna(False).to_numpy()
    bc = df["below_count"].to_numpy()
    bo = df["blowoff"].fillna(False).to_numpy()
    vs = df["vol_shock"].fillna(False).to_numpy()
    dist = df["dist_pct"].to_numpy(float)
    rsi = df["rsi"].to_numpy(float)
    holding = np.concatenate([[False], st[:-1] == 1])   # in a position entering this bar

    R = {h: fwd_ret(close, h) for h in HORIZONS}
    DD = {h: fwd_dd(close, h) for h in HORIZONS}

    out = {"symbol": SYMBOL, "source": "binance", "fee_per_side_pct": FEE,
           "from": str(df.index[0].date()), "to": str(df.index[-1].date()),
           "n_days": int(len(df)), "nboot": NBOOT, "seed": SEED}
    print(f"{out['from']} -> {out['to']}  {out['n_days']} dni\n")

    # ── 1. blow-off against the days it was actually written for ────────────
    ext = dist > cfg.blowoff_dist_pct          # already far above the trackline
    print(f"BLOW-OFF · pravi primerjalni vzorec")
    print(f"  dni, ko je cena >{cfg.blowoff_dist_pct:.0f} % nad trackline: {ext.sum()}")
    print(f"  od tega z RSI > 80 (= sprozitev):                {int((ext & bo).sum())}")
    blk = {"n_extended": int(ext.sum()), "n_fire": int(bo.sum()),
           "n_holding_at_fire": int((bo & holding).sum()), "m": {}}
    for lab, M in (("donos", R), ("maxdd", DD)):
        blk["m"][lab] = {}
        for h in HORIZONS:
            r = compare(M[h][ext & bo], M[h][ext & ~bo], rng, h)
            blk["m"][lab][str(h)] = r
            if r["too_few"]:
                print(f"    {lab:6} {h:>3}d  premalo ({r['n_true']} proti {r['n_false']})")
            else:
                print(f"    {lab:6} {h:>3}d  ob sprozitvi {r['mean_true']:+7.2f} · "
                      f"drugi razsirjeni dnevi {r['mean_false']:+7.2f} · "
                      f"razlika {r['diff']:+6.2f} CI [{r['ci'][0]:+.2f},{r['ci'][1]:+.2f}]"
                      f"{'  ZNACILNO' if r['sig'] else ''}")
    out["blowoff_vs_extended"] = blk

    # ── 2. what happened after each exit blow-off actually caused ───────────
    fired = []
    for i in range(1, len(st)):
        if st[i] != 1 and st[i - 1] == 1 and not (bl[i] and bc[i] >= cfg.exit_grace_bars) and bo[i]:
            row = {"date": str(df.index[i].date()), "close": round(float(close[i]), 1),
                   "dist_pct": round(float(dist[i]), 1), "rsi": round(float(rsi[i]), 1)}
            for h in HORIZONS:
                row[f"ret{h}"] = None if not np.isfinite(R[h][i]) else round(float(R[h][i]), 1)
                row[f"dd{h}"] = None if not np.isfinite(DD[h][i]) else round(float(DD[h][i]), 1)
            fired.append(row)
    out["blowoff_exits"] = fired
    print(f"\n  izstopi, ki jih je blow-off DEJANSKO povzrocil: {len(fired)}")
    print(f"  {'datum':12} {'dist%':>7} {'RSI':>6} {'+20d':>8} {'+60d':>8} {'najgl. padec 60d':>18}")
    for r in fired:
        print(f"  {r['date']:12} {r['dist_pct']:7.1f} {r['rsi']:6.1f} "
              f"{str(r['ret20']):>8} {str(r['ret60']):>8} {str(r['dd60']):>18}")
    ok = [r for r in fired if r["ret60"] is not None]
    if ok:
        good = sum(1 for r in ok if r["ret60"] < 0)
        out["blowoff_exits_summary"] = {
            "n": len(ok), "n_price_fell_60d": good,
            "median_ret60": round(float(np.median([r["ret60"] for r in ok])), 1),
            "median_dd60": round(float(np.median([r["dd60"] for r in ok])), 1)}
        print(f"  -> cena je v 60 dneh padla po {good} od {len(ok)} izstopov · "
              f"mediana donosa {np.median([r['ret60'] for r in ok]):+.1f} % · "
              f"mediana najglobljega vmesnega padca {np.median([r['dd60'] for r in ok]):+.1f} %")

    # ── 3. can vol-shock ever act? and does a looser threshold help? ────────
    actionable = holding & bl & (bc < cfg.exit_grace_bars)
    print(f"\nVOL-SHOCK · ali sploh lahko kdaj deluje")
    print(f"  dni v poziciji, pod trackline, se pred rednim izstopom: {int(actionable.sum())}")
    print(f"  od tega s sprozenim vol-shockom: {int((actionable & vs).sum())}")
    out["vol_shock_actionable"] = {"n_window": int(actionable.sum()),
                                   "n_fire_in_window": int((actionable & vs).sum())}

    vsb = {"m": {}}
    for lab, M in (("donos", R), ("maxdd", DD)):
        vsb["m"][lab] = {}
        for h in HORIZONS:
            r = compare(M[h][bl & vs], M[h][bl & ~vs], rng, h)
            vsb["m"][lab][str(h)] = r
            if not r["too_few"]:
                print(f"    {lab:6} {h:>3}d  ob sprozitvi {r['mean_true']:+7.2f} · "
                      f"drugi dnevi pod TL {r['mean_false']:+7.2f} · "
                      f"razlika {r['diff']:+6.2f} CI [{r['ci'][0]:+.2f},{r['ci'][1]:+.2f}]"
                      f"{'  ZNACILNO' if r['sig'] else ''}")
    out["vol_shock_vs_below_tl"] = vsb

    # Would a rule that CAN fire do any good? Push the threshold down until it does.
    print(f"\n  ce prag znizamo, da se pravilo sploh sprozi:")
    sweep = []
    base_r = None
    for mul in (0.8, 1.0, 1.1, 1.2, 1.5, 2.0, 999.0):
        c2 = engine.make_config("lean", vol_shock_mul=mul)
        d2 = trim_warmup(smod.run_strategy(raw, btc_daily=None, config=c2).df)
        pos = pd.Series(engine.position(d2, s_bull_code=1), index=d2.index, dtype=float)
        r = net_returns(pos, raw["close"].pct_change().fillna(0.0), FEE).to_numpy(float)
        dn = np.sqrt(np.mean(np.minimum(r, 0) ** 2)) * np.sqrt(365)
        so = float(r.mean() * 365 / dn)
        eq = np.cumprod(1 + r); dd = float((eq / np.maximum.accumulate(eq) - 1).min() * 100)
        n_ex = int(((d2["signal_state"].to_numpy()[1:] != 1) &
                    (d2["signal_state"].to_numpy()[:-1] == 1)).sum())
        n_fire = int(d2["vol_shock"].fillna(False).sum())
        if mul == 999.0:
            base_r = so
        sweep.append({"mul": mul, "sortino": round(so, 3), "maxdd": round(dd, 1),
                      "exits": n_ex, "fires": n_fire})
        print(f"    mnozitelj {mul:6.1f} · sprozitev {n_fire:4d} · izstopov {n_ex:3d} · "
              f"Sortino {so:.3f} · MaxDD {dd:.1f} %")
    out["vol_shock_threshold_sweep"] = sweep
    out["vol_shock_off_sortino"] = round(base_r, 3)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
