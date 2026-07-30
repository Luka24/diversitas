"""Would re-fitting the parameters as we go beat leaving them alone?

Three ways of choosing parameters are put on the same footing and judged only on
the out-of-sample stretches, so none of them can see the data it is scored on:

  FIXED       the shipped defaults, never re-fitted. The thing to beat.
  REFIT       on each training window pick the single best of the 81 combinations
              by Sortino, then trade it through the next test window. This is
              walk-forward re-optimisation as usually described.
  REFIT-ROBUST same, but pick the combination with the best NEIGHBOURHOOD mean
              rather than the best point -- the penalised-objective idea, which
              punishes settings whose neighbours are worse.
  VOTE        majority of all 81, never re-fitted. No selection at all.

The question underneath is whether there is enough data to fit on. That gets
answered first and quantitatively: a fold that contains four trades cannot support
choosing between 81 configurations, no matter how the choice is made.

Output: testing/data/wf_refit_BTC.json
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

FEE, PPY = 0.30, 365
SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
OUT = ROOT / "testing" / "data" / "wf_refit_BTC.json"
BULL = ("above_tl", "above_ma_med", "track_rising_window", "dist_entry_ok",
        "regime_ok", "btc_filter_ok", "donchian_ok")
DROP = ("dist_entry_ok", "above_ma_med")          # the two settled removals

GRID = {"ma_long_len": [150, 200, 250], "confirm_bars": [2, 3, 4],
        "reentry_hold": [10, 15, 20], "exit_grace_bars": [2, 3, 4]}
DEFAULTS = {"ma_long_len": 200, "confirm_bars": 3, "reentry_hold": 15,
            "exit_grace_bars": 3}
# train / test lengths in years, to show the trade-count problem from several angles
SCHEMES = [(2, 1), (3, 1), (4, 1), (3, 2)]


def sortino(r):
    if len(r) < 5:
        return np.nan
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def sharpe(r):
    sd = r.std(ddof=1) * np.sqrt(PPY)
    return float(r.mean() * PPY / sd) if sd > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def cagr(r):
    return float((float(np.prod(1.0 + r)) ** (PPY / len(r)) - 1.0) * 100.0)


def positions(raw, **kw):
    smod = engine.strategy_module("lean")
    cfg = engine.make_config("lean", **kw)
    df = smod.compute_features(raw, None, cfg)
    for c in DROP:
        df[c] = True
    bull = pd.Series(True, index=df.index)
    for t in BULL:
        bull &= df[t]
    df["bull_condition"] = bull.fillna(False)
    df = trim_warmup(smod.run_state_machine(df, cfg))
    return pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)


def neighbours(combo, keys):
    """Grid cells one step away in exactly one dimension."""
    out = []
    for i, k in enumerate(keys):
        vals = GRID[k]
        j = vals.index(combo[i])
        for jj in (j - 1, j + 1):
            if 0 <= jj < len(vals):
                c = list(combo)
                c[i] = vals[jj]
                out.append(tuple(c))
    return out


def main():
    raw = pd.read_parquet(SRC)
    ret_all = raw["close"].pct_change().fillna(0.0)
    keys = list(GRID)
    combos = list(itertools.product(*(GRID[k] for k in keys)))
    dflt = tuple(DEFAULTS[k] for k in keys)

    POS = {c: positions(raw, **dict(zip(keys, c))) for c in combos}
    idx = None
    for sr in POS.values():
        idx = sr.index if idx is None else idx.intersection(sr.index)
    POS = {c: sr.reindex(idx) for c, sr in POS.items()}
    RET = {c: net_returns(POS[c], ret_all, FEE) for c in combos}
    ens = np.mean([POS[c].to_numpy() for c in combos], axis=0)
    VOTE = net_returns(pd.Series((ens > 0.5 - 1e-9).astype(float), index=idx),
                       ret_all, FEE)

    out = {"from": str(idx[0].date()), "to": str(idx[-1].date()), "n": len(idx),
           "members": len(combos), "fee_per_side_pct": FEE, "schemes": []}
    print(f"{out['from']} → {out['to']} ({out['n']} dni) · {len(combos)} kombinacij\n")

    for tr_y, te_y in SCHEMES:
        tr, te = int(tr_y * 365), int(te_y * 365)
        folds, picks = [], []
        seg = {"fixed": [], "refit": [], "robust": [], "vote": []}
        i = tr
        while i + te <= len(idx):
            trs, tes = slice(i - tr, i), slice(i, i + te)
            # trades available to fit on
            pos_d = POS[dflt].to_numpy()[trs]
            n_tr = int((np.diff(pos_d, prepend=pos_d[0]) > 0).sum())
            scores = {c: sortino(RET[c].to_numpy()[trs]) for c in combos}
            best = max(combos, key=lambda c: (scores[c] if np.isfinite(scores[c]) else -9))
            def nb_mean(c):
                vs = [scores[c]] + [scores[n] for n in neighbours(c, keys)]
                vs = [v for v in vs if np.isfinite(v)]
                return np.mean(vs) if vs else -9
            best_rb = max(combos, key=nb_mean)
            folds.append({"train": [str(idx[i-tr].date()), str(idx[i-1].date())],
                          "test": [str(idx[i].date()), str(idx[i+te-1].date())],
                          "trades_in_train": n_tr,
                          "best": dict(zip(keys, best)),
                          "best_robust": dict(zip(keys, best_rb)),
                          "train_sortino_best": round(float(scores[best]), 3),
                          "train_sortino_default": round(float(scores[dflt]), 3)})
            picks.append(best)
            seg["fixed"].append(RET[dflt].to_numpy()[tes])
            seg["refit"].append(RET[best].to_numpy()[tes])
            seg["robust"].append(RET[best_rb].to_numpy()[tes])
            seg["vote"].append(VOTE.to_numpy()[tes])
            i += te

        res = {}
        for k, parts in seg.items():
            r = np.concatenate(parts)
            res[k] = {"sortino": round(sortino(r), 3), "sharpe": round(sharpe(r), 3),
                      "cagr": round(cagr(r), 1), "maxdd": round(maxdd(r), 1),
                      "final": round(float(np.prod(1.0 + r)), 3)}
        n_uniq = len({tuple(p) for p in picks})
        row = {"train_years": tr_y, "test_years": te_y, "folds": folds,
               "n_folds": len(folds), "oos_days": int(sum(len(x) for x in seg["fixed"])),
               "median_trades_in_train": int(np.median([f["trades_in_train"] for f in folds])),
               "distinct_picks": n_uniq, "results": res}
        out["schemes"].append(row)

        print(f"── trening {tr_y} let / test {te_y} leto · {len(folds)} rezin · "
              f"{row['oos_days']} dni izven vzorca")
        print(f"   poslov v treningu: mediana {row['median_trades_in_train']}, "
              f"razpon {min(f['trades_in_train'] for f in folds)}–"
              f"{max(f['trades_in_train'] for f in folds)}")
        print(f"   izbrana nastavitev se je zamenjala {n_uniq}× od {len(folds)} rezin")
        print(f"   {'metoda':14} {'Sortino':>8} {'Sharpe':>8} {'CAGR':>8} {'MaxDD':>9} {'konec':>7}")
        NAMES = {"fixed": "fiksni privzetki", "refit": "sprotno nastavljanje",
                 "robust": "sprotno, robustno", "vote": "glasovanje 81"}
        for k in ("fixed", "refit", "robust", "vote"):
            m = res[k]
            print(f"   {NAMES[k]:14} {m['sortino']:8.3f} {m['sharpe']:8.3f} "
                  f"{m['cagr']:7.1f} % {m['maxdd']:8.1f} % {m['final']:7.2f}")
        print()

    # how often does the in-sample winner stay a winner out of sample?
    wins = {"refit": 0, "robust": 0, "vote": 0, "n": 0}
    for row in out["schemes"]:
        f = row["results"]["fixed"]["sortino"]
        wins["n"] += 1
        for k in ("refit", "robust", "vote"):
            if row["results"][k]["sortino"] > f:
                wins[k] += 1
    out["beats_fixed"] = wins
    print(f"Kolikokrat metoda prekaša fiksne privzetke (od {wins['n']} shem):")
    for k in ("refit", "robust", "vote"):
        print(f"   {k:8} {wins[k]}/{wins['n']}")

    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
