"""Momentum tuning + nested WF z realnimi stroški 0.3 % na stran (BTC).

Dva outputa v eno poročilo:
  A) Tuning tabela (iste vrstice kot prej), a NETO pri 0.3 %/stran (round-trip 0.6 %),
     merjeno na zadnjih 3 letih (danes - 3 leta → zadnji podatek).
  B) Nested walk-forward, ista struktura foldov kot prej, prav tako 0.3 %/stran.

Run:  PYTHONPATH=. .venv/bin/python testing/scripts/run_costed_3y.py
"""
from __future__ import annotations

import sys
import warnings
from itertools import product
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from testing.scripts import dataio, engine

REPORTS = _ROOT / "testing" / "reports"
TD = 365
EMBARGO = 21
FEE = 0.30  # % na stran (fee + slippage skupaj), round-trip 0.60 %

# --- tuning table configs (iste vrstice kot porocilo_agresivno_tuning_btc.md) ---
ROWS = [
    ("Baseline (12/4/50)", {}),
    ("trailing 8", {"trail_pct": 8}),
    ("trailing 10", {"trail_pct": 10}),
    ("trailing 15", {"trail_pct": 15}),
    ("trailing 18", {"trail_pct": 18}),
    ("trailing 20", {"trail_pct": 20}),
    ("re-entry 1", {"reentry_hold": 1}),
    ("re-entry 2", {"reentry_hold": 2}),
    ("re-entry 3", {"reentry_hold": 3}),
    ("bear-cut 0", {"bear_size_cut": 0.0}),
    ("bear-cut 25", {"bear_size_cut": 25.0}),
    ("bear-cut 70", {"bear_size_cut": 70.0}),
    ("bear-cut 100", {"bear_size_cut": 100.0}),
    ("re-entry2 + bear25", {"reentry_hold": 2, "bear_size_cut": 25.0}),
    ("re-entry2 + bear25 + trail10", {"reentry_hold": 2, "bear_size_cut": 25.0, "trail_pct": 10}),
    ("trail18 + re-entry2", {"trail_pct": 18, "reentry_hold": 2}),
]

# --- nested WF grid + folds (isto kot run_aggressive_nested.py) ---
GRID = [{"reentry_hold": r, "bear_size_cut": b, "trail_pct": t}
        for r, b, t in product([1, 2, 3, 4], [0.0, 25.0, 50.0, 75.0], [10, 12, 15, 18, 20])]
OOS = [("2021-01-01", "2021-12-31", "bull/top"),
       ("2022-01-01", "2022-12-31", "bear"),
       ("2023-01-01", "2023-12-31", "recovery"),
       ("2024-01-01", "2024-12-31", "bull"),
       ("2025-01-01", "2025-12-31", "bear/chop")]


def _sortino(r):
    r = np.asarray(r, float); r = r[np.isfinite(r)]
    if len(r) < 15:
        return np.nan
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(TD)
    return float(r.mean() * TD / d) if d > 1e-9 else np.nan


def _metrics(ret, pos):
    r = ret.values
    eq = np.cumprod(1.0 + r)
    n = len(r)
    cagr = float(eq[-1] ** (TD / n) - 1) if n else np.nan
    dd = eq / np.maximum.accumulate(eq) - 1.0
    maxdd = float(dd.min())
    sd = r.std(ddof=0)
    sharpe = float(r.mean() / sd * np.sqrt(TD)) if sd > 1e-12 else np.nan
    sortino = _sortino(r)
    calmar = float(cagr / abs(maxdd)) if maxdd < -1e-9 else np.nan
    exposure = float(np.mean(pos) * 100)
    return cagr, exposure, maxdd, sharpe, sortino, calmar


def main() -> int:
    daily = dataio.load("BTC", "all")
    end = daily.index.max()
    win_start = end - pd.DateOffset(years=3)
    print(f"BTC podatki: {daily.index.min().date()} … {end.date()}")
    print(f"Tuning tabela okno (zadnja 3 leta): {win_start.date()} → {end.date()}, "
          f"stroški {FEE:.2f} %/stran\n")

    # ---- A) tuning table over last 3 years, net of fees ----
    table = []
    for lab, ov in ROWS:
        df = engine.run("momentum", daily, **ov)
        ret = engine.strat_returns(df, fee_per_side_pct=FEE, s_bull_code=1)
        pos = engine.position(df, 0.0, 1)
        mask = ret.index >= win_start
        ret_w = ret[mask]
        pos_w = pd.Series(pos, index=df.index)[mask].values
        table.append((lab, *_metrics(ret_w, pos_w)))
        c, e, m, sh, so, ca = table[-1][1:]
        print(f"{lab:30} CAGR {c*100:5.0f}%  exp {e:4.0f}%  MaxDD {m*100:5.0f}%  "
              f"Sharpe {sh:4.2f}  Sortino {so:4.2f}  Calmar {ca:4.2f}")

    # ---- B) nested WF, same folds, net of fees ----
    print()
    ret_g = {tuple(sorted(c.items())): engine.strat_returns(engine.run("momentum", daily, **c),
                                                            fee_per_side_pct=FEE, s_bull_code=1)
             for c in GRID}
    base = engine.strat_returns(engine.run("momentum", daily), fee_per_side_pct=FEE, s_bull_code=1)
    ds = daily.index.min()
    frows, sel_oos, base_oos = [], [], []
    for ts, te, lab in OOS:
        ts_, te_ = pd.Timestamp(ts, tz="UTC"), pd.Timestamp(te, tz="UTC")
        tr_end = ts_ - pd.Timedelta(days=EMBARGO)
        best, bs = None, -1e9
        for c in GRID:
            s = _sortino(ret_g[tuple(sorted(c.items()))].loc[:tr_end].values)
            if np.isfinite(s) and s > bs:
                bs, best = s, c
        r_sel = ret_g[tuple(sorted(best.items()))].loc[ts_:te_]
        r_base = base.loc[ts_:te_]
        sel_oos.append(r_sel); base_oos.append(r_base)
        frows.append((lab, ts_, te_, tr_end, best, _sortino(r_sel.values), _sortino(r_base.values)))
        print(f"{lab:10} TRAIN {ds.date()}→{tr_end.date()}  TEST {ts_.date()}→{te_.date()}  "
              f"izbran {best['reentry_hold']}/{best['bear_size_cut']:.0f}/{best['trail_pct']}  "
              f"OOS Sort izbran {_sortino(r_sel.values):5.2f}  baseline {_sortino(r_base.values):5.2f}")
    ss = _sortino(pd.concat(sel_oos).values); sb = _sortino(pd.concat(base_oos).values)
    bh = daily["close"].pct_change().reindex(pd.concat(sel_oos).index)
    sbh = _sortino(bh.values)
    print(f"\nZLEPLJEN OOS Sortino: izberi-iz-train {ss:.2f}  baseline {sb:.2f}  (Δ {ss-sb:+.2f})  "
          f"| BTC buy&hold {sbh:.2f}")

    _write(win_start, end, ds, table, frows, ss, sb, sbh)
    print(f"\nWrote {REPORTS/'porocilo_costed_3y_btc.md'}")
    return 0


def _write(win_start, end, ds, table, frows, ss, sb, sbh):
    L = [f"# Momentum z realnimi stroški 0.3 %/stran — Bitcoin", "",
         f"Stroški: **{FEE:.2f} % na nakup ali prodajo** (fee + slippage skupaj), round-trip "
         f"{2*FEE:.2f} %. Model zaračuna strošek ob vsaki menjavi signala (opomba: ne ob dnevnem "
         "graded rebalansiranju, zato je realni strošek še malenkost višji).", "",
         f"## A) Tuning tabela — zadnja 3 leta ({win_start.date()} → {end.date()})", "",
         "Vsaka vrstica = cela baseline strategija, spremenjen samo navedeni parameter. "
         "Baseline = trailing 12 / re-entry 4 / bear-cut 50. Vse NETO (0.3 %/stran).", "",
         "| Nastavitev | CAGR | Exp | MaxDD | Sharpe | Sortino | Calmar |",
         "|---|---|---|---|---|---|---|"]
    for lab, c, e, m, sh, so, ca in table:
        b = "**" if lab.startswith("Baseline") else ""
        L.append(f"| {b}{lab}{b} | {c*100:.0f}% | {e:.0f}% | {m*100:.0f}% | {sh:.2f} | {so:.2f} | {ca:.2f} |")
    L += ["", f"## B) Nested walk-forward — iste folde, NETO ({FEE:.2f} %/stran)", "",
          "Train se vedno začne 2019-05-23 in raste; med train in test 21-dnevni embargo. "
          "V vsakem foldu izberem re-entry×bear-cut×trail SAMO iz train dela (po train Sortino), "
          "uporabim na neviden test, zlepim.", "",
          "| Fold | TRAIN | TEST | izbran iz train (re-entry / bear / trail) | OOS Sortino izbran | OOS Sortino baseline |",
          "|---|---|---|---|---|---|"]
    for lab, ts_, te_, tr_end, cfg, s, b in frows:
        L.append(f"| {lab} | {ds.date()} → {tr_end.date()} | {ts_.date()} → {te_.date()} | "
                 f"{cfg['reentry_hold']} / {cfg['bear_size_cut']:.0f} / {cfg['trail_pct']} | "
                 f"{s:.2f} | {b:.2f} |")
    picks_b = [int(cfg["bear_size_cut"]) for *_, cfg, _, _ in frows]
    picks_t = [cfg["trail_pct"] for *_, cfg, _, _ in frows]
    picks_r = [cfg["reentry_hold"] for *_, cfg, _, _ in frows]
    L += ["", f"**Zlepljen OOS Sortino: izberi-iz-train {ss:.2f} vs fiksni baseline {sb:.2f} "
          f"(Δ {ss-sb:+.2f}).** Nevtralna referenca BTC buy&hold: {sbh:.2f}.", "",
          f"Izbrani re-entry po foldih: {picks_r}. Bear-cut: {picks_b}. Trail: {picks_t}.", "",
          "## Zaključek", ""]
    if ss > sb + 0.10:
        L += ["Izbira iz preteklosti tudi neto premaga baseline na nevidenih podatkih — generalizira."]
    else:
        L += ["Tudi z višjimi stroški (0.3 %/stran) izbira-iz-preteklosti **ne premaga** baseline-a "
              f"na nevidenih podatkih (Δ {ss-sb:+.2f}). Izbrani parametri ostajajo nestabilni "
              "(bear-cut/trail skačeta po foldih). Zaključek se ne spremeni: tuning teh parametrov "
              "ne prinese zanesljive OOS prednosti → ostani pri baseline."]
    (REPORTS / "porocilo_costed_3y_btc.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
