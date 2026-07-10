"""Robustnost tuninga proti overfittingu — BTC.

En holdout (2025, večinoma bear) ni dovolj: strategija ki dela le v enem režimu je
overfit nanj. Zato kandidata (re-entry2 + bear-cut25) proti baseline preverim s tremi
profesionalnimi pristopi:
  1. Per-leto / per-režim — mora pomagati (ali vsaj ne škoditi) v VEČ obdobjih, ne le enem.
  2. CPCV-lite — čez mnogo mešanih pod-obdobij, kolikokrat kandidat premaga baseline.
  3. Block-bootstrap CI — je ΔSortino statistično nad 0 ali samo šum.

Run:  PYTHONPATH=. .venv/bin/python testing/scripts/run_aggressive_robustness.py
"""
from __future__ import annotations

import sys
import warnings
from itertools import combinations
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from testing.scripts import dataio, engine, stats

REPORTS = _ROOT / "testing" / "reports"
RESULTS = _ROOT / "testing" / "results" / "aggressive"
RESULTS.mkdir(parents=True, exist_ok=True)
TD = 365

BASELINE = {}
CANDIDATE = {"reentry_hold": 2, "bear_size_cut": 25.0}


def _sortino(r):
    r = np.asarray(r, float); r = r[np.isfinite(r)]
    if len(r) < 15:
        return np.nan
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(TD)
    return float(r.mean() * TD / d) if d > 1e-9 else np.nan


def _ann_ret(r):
    r = np.asarray(r, float); return float(np.mean(r) * TD * 100)


def _returns(ov):
    daily = dataio.load("BTC", "all")
    df = engine.run("momentum", daily, **ov)
    return engine.strat_returns(df, s_bull_code=1)


def _regime(daily):
    """Data-driven BTC regime from the 200-day MA (bull = above & rising)."""
    c = daily["close"]; ma = c.rolling(200, min_periods=100).mean()
    rising = ma > ma.shift(20)
    reg = pd.Series("sideways", index=c.index)
    reg[(c > ma) & rising] = "bull"
    reg[(c < ma) & (~rising)] = "bear"
    return reg


def main() -> int:
    daily = dataio.load("BTC", "all")
    rb = _returns(BASELINE)
    rc = _returns(CANDIDATE)
    al = pd.concat([rb.rename("base"), rc.rename("cand")], axis=1).dropna()

    # 1) per calendar year
    years = sorted({d.year for d in al.index})
    per_year = []
    for y in years:
        m = al.index.year == y
        if m.sum() < 60:
            continue
        per_year.append((y, _sortino(al["base"][m]), _sortino(al["cand"][m]),
                         _ann_ret(al["base"][m]), _ann_ret(al["cand"][m])))

    # 2) per data-driven regime
    reg = _regime(daily).reindex(al.index).fillna("sideways")
    per_reg = []
    for name in ["bull", "bear", "sideways"]:
        m = (reg == name).values
        if m.sum() < 30:
            continue
        per_reg.append((name, int(m.sum()), _sortino(al["base"][m]), _sortino(al["cand"][m])))

    # 3) CPCV-lite: split into 10 blocks, all balanced train/test combos, use TEST halves;
    #    fraction of sub-periods where candidate Sortino >= baseline
    n = len(al); blocks = np.array_split(np.arange(n), 10)
    wins, total, deltas = 0, 0, []
    for test_sel in combinations(range(10), 5):
        idx = np.concatenate([blocks[i] for i in test_sel])
        sb, sc = _sortino(al["base"].values[idx]), _sortino(al["cand"].values[idx])
        if np.isfinite(sb) and np.isfinite(sc):
            total += 1; wins += (sc >= sb); deltas.append(sc - sb)
    cpcv_winrate = wins / total * 100 if total else np.nan
    cpcv_med_delta = float(np.median(deltas)) if deltas else np.nan

    # 4) paired block-bootstrap CI on ΔSortino (full period)
    idxs = stats.stationary_bootstrap(np.arange(n), n_boot=5000, mean_block=20, seed=7).astype(int)
    bd = np.array([_sortino(al["cand"].values[ii]) - _sortino(al["base"].values[ii]) for ii in idxs])
    bd = bd[np.isfinite(bd)]
    ci_lo, ci_hi = np.percentile(bd, 2.5), np.percentile(bd, 97.5)
    frac_pos = float((bd > 0).mean() * 100)

    full_b, full_c = _sortino(al["base"].values), _sortino(al["cand"].values)
    _write(per_year, per_reg, full_b, full_c, cpcv_winrate, cpcv_med_delta,
           ci_lo, ci_hi, frac_pos, total)

    print(f"Full-period Sortino: baseline {full_b:.2f}  candidate {full_c:.2f}  (Δ {full_c-full_b:+.2f})")
    print("\nPer year (Sortino base → cand):")
    for y, sb, sc, rbn, rcn in per_year:
        print(f"  {y}: {sb:5.2f} → {sc:5.2f}   ({'+' if sc>=sb else '−'})")
    print("\nPer regime (Sortino base → cand):")
    for nm, cnt, sb, sc in per_reg:
        print(f"  {nm:8} ({cnt:4}d): {sb:5.2f} → {sc:5.2f}")
    print(f"\nCPCV-lite: kandidat premaga baseline v {cpcv_winrate:.0f}% od {total} pod-obdobij "
          f"(median Δ {cpcv_med_delta:+.2f})")
    print(f"Bootstrap ΔSortino 95% CI: [{ci_lo:+.2f}, {ci_hi:+.2f}], nad 0 v {frac_pos:.0f}% resamplov")
    print(f"\nWrote {REPORTS/'aggressive_robustness_btc.md'}")
    return 0


def _write(per_year, per_reg, fb, fc, cpcv_wr, cpcv_md, lo, hi, fp, npaths):
    L = ["# Robustnost tuninga (BTC) — je re-entry2 + bear-cut25 overfit?", "",
         "Kandidat = re-entry lock 2 + bear-cut 25 (proti baseline 4 / 50). En bear-year holdout "
         "ni dovolj, zato preverim čez več režimov, čez mnogo mešanih pod-obdobij (CPCV) in z "
         "bootstrap intervalom.", "",
         f"Full-period Sortino: baseline **{fb:.2f}** → kandidat **{fc:.2f}** (Δ {fc-fb:+.2f}).", "",
         "## 1. Po letih (vsako leto je svoj režim)", "",
         "| Leto | režim | Sortino baseline | Sortino kandidat | boljši? |",
         "|---|---|---|---|---|"]
    lab = {2019: "bull", 2020: "bull", 2021: "bull/top", 2022: "bear", 2023: "recovery",
           2024: "bull", 2025: "bear/chop", 2026: "chop"}
    for y, sb, sc, rbn, rcn in per_year:
        L.append(f"| {y} | {lab.get(y,'?')} | {sb:.2f} | {sc:.2f} | {'da' if sc>=sb-0.05 else 'NE'} |")
    L += ["", "## 2. Po režimu (200-MA: bull / bear / sideways)", "",
          "| režim | dni | Sortino baseline | Sortino kandidat |", "|---|---|---|---|"]
    for nm, cnt, sb, sc in per_reg:
        L.append(f"| {nm} | {cnt} | {sb:.2f} | {sc:.2f} |")
    L += ["", "## 3. CPCV + bootstrap", "",
          f"- **CPCV-lite:** čez {npaths} mešanih pod-obdobij kandidat premaga baseline v "
          f"**{cpcv_wr:.0f}%** (median Δ Sortino {cpcv_md:+.2f}). To ni ena pot, ampak porazdelitev "
          "čez mnogo kombinacij obdobij.",
          f"- **Block-bootstrap (5000×, blok 20 dni):** ΔSortino 95% CI **[{lo:+.2f}, {hi:+.2f}]**, "
          f"pozitiven v **{fp:.0f}%** resamplov.", "",
          "## Zaključek", ""]
    n_better = sum(1 for _, sb, sc, *_ in per_year if sc >= sb - 0.05)
    robust = (cpcv_wr >= 60 and lo > -0.1 and n_better >= len(per_year) * 0.6)
    if robust:
        L += [f"Izboljšava zdrži: bolje ali enako v {n_better}/{len(per_year)} letih, čez pod-obdobja "
              f"zmaga v {cpcv_wr:.0f}%, bootstrap CI je večinoma nad 0. Ni videti kot overfit na eno "
              "obdobje — mehanizem (hitrejši re-entry, manjša bear-pozicija) je tudi ekonomsko smiseln.",
              "", "Vseeno pošteno: gre za majhno spremembo dveh parametrov, testirano na enem coinu. "
              "Pred uporabo v živo bi to potrdil še s paper tradingom in spremljal ali drži v novem "
              "režimu (nestacionarnost)."]
    else:
        L += [f"Previdno: kandidat NE zdrži enakomerno — zmaga le v {n_better}/{len(per_year)} letih "
              f"oz. CPCV winrate {cpcv_wr:.0f}%. Videti je bolj vezano na določena obdobja; ne bi ga "
              "vzel brez dodatne potrditve."]
    L += ["", "*Metoda: per-režim + CPCV + block-bootstrap, kot je standard za robustnost čez "
          "nestacionarne trge (Lopez de Prado / walk-forward praksa).*", ""]
    (REPORTS / "aggressive_robustness_btc.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
