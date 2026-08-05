"""Is the Donchian result overfitted? Five independent attempts to break it.

A strong result is exactly when to look hardest. Donchian passed BTC's nested
walk-forward and ETH's out-of-sample test, so before it goes anywhere near the
engine it gets audited:

  1. PBO via CSCV (Bailey, Borwein, Lopez de Prado). Split the history into 12
     blocks, take all C(12,6) = 924 balanced in/out splits, pick the best period
     in-sample and see where it ranks out-of-sample. PBO is the fraction of
     splits where the in-sample winner lands below the out-of-sample median.
     Same S and path count as the project's earlier PBO of 0.694, so the two
     numbers are directly comparable.

  2. CPCV win rate. Across the same 924 splits, how often does Donchian beat the
     disabled engine on the out-of-sample half? A real effect wins most splits;
     a fitted one wins about half.

  3. How independent is ETH really? An out-of-sample test on an asset that moves
     with the first one is worth less than it looks. Measured on both price
     returns and strategy returns.

  4. Random circular shift. Rotate the donchian_ok series by a random offset.
     That keeps its frequency and its clustering and destroys only its alignment
     with price. If the real alignment carries no information, the true result
     sits in the middle of 1000 rotations.

  5. Assets never used for this. XRP, BNB and ADA were excluded from strategy
     work for being too unlike BTC — which is precisely what makes them useful
     here. Supplementary, and labelled as such.

Output: testing/data/donchian_overfit_BTC.json
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

np.seterr(all="ignore")

FEE, PPY, PERIOD = 0.30, 365, 20
PERIODS = [10, 12, 15, 20, 25, 30, 40, 55]
S_BLOCKS, N_SHIFT = 12, 1000
SRC = ROOT / "testing" / "data" / "sources"
OUT = ROOT / "testing" / "data" / "donchian_overfit_BTC.json"
BULL_TERMS = ("above_tl", "track_rising_window", "regime_ok",
              "btc_filter_ok", "donchian_ok")


def sortino(r):
    if len(r) < 20:
        return np.nan
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def series(raw, period):
    kw = ({} if period is None
          else {"use_donchian": True, "donchian_period": int(period)})
    cfg = engine.make_config("lean", **kw)
    smod = engine.strategy_module("lean")
    df = trim_warmup(smod.run_strategy(raw, btc_daily=None, config=cfg).df)
    pos = pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)
    ret = raw["close"].pct_change().fillna(0.0)
    return net_returns(pos, ret, FEE).reindex(df.index).to_numpy(float), pos, df


def pbo_cscv(mat: np.ndarray, names: list[str]):
    """mat[i] = daily net returns of config i, all same length."""
    n = mat.shape[1]
    blocks = np.array_split(np.arange(n), S_BLOCKS)
    lam, below, best_counts = [], 0, {nm: 0 for nm in names}
    half = S_BLOCKS // 2
    for sel in itertools.combinations(range(S_BLOCKS), half):
        is_idx = np.concatenate([blocks[i] for i in sel])
        oos_idx = np.concatenate([blocks[i] for i in range(S_BLOCKS) if i not in sel])
        s_is = np.array([sortino(m[is_idx]) for m in mat])
        s_oos = np.array([sortino(m[oos_idx]) for m in mat])
        if not np.isfinite(s_is).all() or not np.isfinite(s_oos).all():
            continue
        k = int(np.argmax(s_is))
        best_counts[names[k]] += 1
        rank = float((s_oos < s_oos[k]).sum()) / (len(names) - 1)   # 1 = best OOS
        rank = min(max(rank, 1e-6), 1 - 1e-6)
        lam.append(np.log(rank / (1 - rank)))
        below += int(rank < 0.5)
    lam = np.array(lam)
    return {"paths": int(len(lam)), "pbo": round(float(below / len(lam)), 3),
            "median_logit": round(float(np.median(lam)), 3),
            "picked_in_sample": best_counts}


def main() -> int:
    out = {"fee_per_side_pct": FEE, "period": PERIOD, "S_blocks": S_BLOCKS}
    btc = pd.read_parquet(SRC / "BTC_binance_warmup.parquet")
    eth = pd.read_parquet(SRC / "ETH_binance.parquet")

    # ── 1 + 2. PBO and CPCV win rate ──────────────────────────────────────
    for tag, raw in (("BTC", btc), ("ETH", eth)):
        names = ["off"] + [str(p) for p in PERIODS]
        rows = [series(raw, None)[0]] + [series(raw, p)[0] for p in PERIODS]
        L = min(len(r) for r in rows)
        mat = np.vstack([r[-L:] for r in rows])

        res = pbo_cscv(mat, names)
        # CPCV: Donchian 20 against off, out-of-sample halves
        i20 = names.index(str(PERIOD))
        blocks = np.array_split(np.arange(L), S_BLOCKS)
        wins = tot = 0
        deltas = []
        for sel in itertools.combinations(range(S_BLOCKS), S_BLOCKS // 2):
            oos = np.concatenate([blocks[i] for i in range(S_BLOCKS) if i not in sel])
            a, b = sortino(mat[i20][oos]), sortino(mat[0][oos])
            if np.isfinite(a) and np.isfinite(b):
                tot += 1
                wins += int(a > b)
                deltas.append(a - b)
        res["cpcv_winrate_pct"] = round(wins / tot * 100, 1)
        res["cpcv_median_delta"] = round(float(np.median(deltas)), 3)
        out[f"pbo_{tag}"] = res
        print(f"\n1+2. PBO / CPCV — {tag}   ({res['paths']} poti, {S_BLOCKS} blokov)")
        print(f"   PBO {res['pbo']:.3f}   (prejšnji PBO projekta na drugih "
              f"parametrih: 0,694)")
        print(f"   Donchian 20 premaga izklopljeno v {res['cpcv_winrate_pct']:.1f} % "
              f"od {tot} zunajvzorčnih polovic, mediana Δ {res['cpcv_median_delta']:+.3f}")
        top = sorted(res["picked_in_sample"].items(), key=lambda x: -x[1])[:4]
        print("   najpogosteje izbrano v vzorcu: "
              + "  ".join(f"{k}:{v}" for k, v in top))

    # ── 3. how independent is ETH ─────────────────────────────────────────
    rb, pb, _ = series(btc, PERIOD)
    re_, pe, _ = series(eth, PERIOD)
    idx = pb.index.intersection(pe.index)
    pr_b = btc["close"].pct_change().reindex(idx)
    pr_e = eth["close"].pct_change().reindex(idx)
    sb = pd.Series(rb, index=pb.index).reindex(idx)
    se = pd.Series(re_, index=pe.index).reindex(idx)
    corr = {"price_returns": round(float(pr_b.corr(pr_e)), 3),
            "strategy_returns": round(float(sb.corr(se)), 3),
            "position_overlap_pct": round(float((pb.reindex(idx) ==
                                                 pe.reindex(idx)).mean() * 100), 1),
            "n_overlap_days": int(len(idx))}
    out["independence"] = corr
    print("\n3. KAKO NEODVISEN JE SPLOH ETH TEST")
    print(f"   dnevni donosi BTC proti ETH:        r = {corr['price_returns']:.3f}")
    print(f"   donosi strategije BTC proti ETH:    r = {corr['strategy_returns']:.3f}")
    print(f"   isti položaj (v trgu / zunaj):      {corr['position_overlap_pct']:.1f} % dni")
    print("   Višja ko je korelacija, manj je ETH neodvisna potrditev.")

    # ── 4. random circular shift of the filter ────────────────────────────
    print(f"\n4. NAKLJUČNI ZAMIK FILTRA — {N_SHIFT} rotacij")
    smod = engine.strategy_module("lean")
    cfg = engine.make_config("lean", use_donchian=True, donchian_period=PERIOD)
    shift_res = {}
    rng = np.random.default_rng(20260807)
    for tag, raw in (("BTC", btc), ("ETH", eth)):
        feat = smod.compute_features(raw, None, cfg)
        dok = feat["donchian_ok"].fillna(False).to_numpy()
        base_ret = series(raw, None)[0]
        real_ret = series(raw, PERIOD)[0]
        s_real, s_off = sortino(real_ret), sortino(base_ret)
        n = len(dok)
        sims = []
        for _ in range(N_SHIFT):
            k = int(rng.integers(60, n - 60))
            f2 = feat.copy()
            f2["donchian_ok"] = np.roll(dok, k)
            bull = pd.Series(True, index=f2.index)
            for t in BULL_TERMS:
                bull &= f2[t]
            f2["bull_condition"] = (bull & ~f2["blowoff"]).fillna(False)
            st = trim_warmup(smod.run_state_machine(f2, cfg))
            p = pd.Series(engine.position(st, s_bull_code=1), index=st.index,
                          dtype=float)
            r = net_returns(p, raw["close"].pct_change().fillna(0.0),
                            FEE).to_numpy(float)
            sims.append(sortino(r))
        sims = np.array([s for s in sims if np.isfinite(s)])
        pct = float((sims < s_real).mean() * 100)
        shift_res[tag] = {"n": int(sims.size), "real": round(s_real, 3),
                          "off": round(s_off, 3),
                          "shift_mean": round(float(sims.mean()), 3),
                          "shift_p05": round(float(np.percentile(sims, 5)), 3),
                          "shift_p95": round(float(np.percentile(sims, 95)), 3),
                          "real_percentile": round(pct, 1)}
        r_ = shift_res[tag]
        print(f"   {tag}: pravi {r_['real']:.3f}   zamaknjeni povpr. "
              f"{r_['shift_mean']:.3f}   5–95 % [{r_['shift_p05']:.3f}, "
              f"{r_['shift_p95']:.3f}]   izklopljen {r_['off']:.3f}")
        print(f"        pravi filter je na {pct:.1f}. percentilu naključnih zamikov")
    out["circular_shift"] = shift_res

    # ── 5. assets never used for this ─────────────────────────────────────
    print("\n5. SREDSTVA, KI ZA TO NISO BILA UPORABLJENA  (dopolnilno)")
    extra = {}
    for sym in ("XRP", "BNB", "ADA"):
        f = SRC / f"{sym}_binance.parquet"
        if not f.exists():
            continue
        raw = pd.read_parquet(f)
        r0, p0, d0 = series(raw, None)
        r1, p1, _ = series(raw, PERIOD)
        eq0, eq1 = np.cumprod(1 + r0), np.cumprod(1 + r1)
        extra[sym] = {
            "n_bars": len(r0), "from": str(p0.index[0].date()),
            "sortino_off": round(sortino(r0), 3), "sortino_on": round(sortino(r1), 3),
            "maxdd_off": round(float((eq0 / np.maximum.accumulate(eq0) - 1).min() * 100), 1),
            "maxdd_on": round(float((eq1 / np.maximum.accumulate(eq1) - 1).min() * 100), 1),
            "final_off": round(float(eq0[-1]), 2), "final_on": round(float(eq1[-1]), 2),
            "expo_off": round(float(p0.mean() * 100), 1),
            "expo_on": round(float(p1.mean() * 100), 1)}
        e = extra[sym]
        print(f"   {sym}  {e['n_bars']} barov od {e['from']}   "
              f"Sortino {e['sortino_off']:.3f} → {e['sortino_on']:.3f}   "
              f"MaxDD {e['maxdd_off']:.1f} % → {e['maxdd_on']:.1f} %   "
              f"konec {e['final_off']:.2f}× → {e['final_on']:.2f}×")
    out["extra_assets"] = extra
    print("   Ta tri sredstva so bila iz razvoja strategije izločena kot preveč")
    print("   drugačna od BTC — za preverjanje posplošljivosti filtra je prav to")
    print("   njihova prednost, a rezultat je dopolnilen in ne odloča.")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
