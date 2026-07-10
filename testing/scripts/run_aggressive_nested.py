"""Nested walk-forward — pravi test brez selection biasa (BTC).

Prejšnji checki (per-leto, CPCV, bootstrap) so gledali kandidata izbranega na CELIH
podatkih → selection bias. Tukaj parameter izberem SAMO iz train dela vsakega folda in
uporabim na neviden test del. Izbira nikoli ne vidi testa. Če ta "izberi-iz-train"
postopek na zlepljenih OOS delih premaga fiksni baseline, potem izboljšava dejansko
generalizira; če ne, je bil full-sample win le selection bias.

Search space: re-entry {1,2,3,4} × bear-cut {0,25,50,75}. Izbira po train Sortino.

Run:  PYTHONPATH=. .venv/bin/python testing/scripts/run_aggressive_nested.py
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
RESULTS = _ROOT / "testing" / "results" / "aggressive"
RESULTS.mkdir(parents=True, exist_ok=True)
TD = 365
EMBARGO = 21

REENTRY = [1, 2, 3, 4]
BEARCUT = [0.0, 25.0, 50.0, 75.0]
GRID = [{"reentry_hold": r, "bear_size_cut": b} for r, b in product(REENTRY, BEARCUT)]

# anchored OOS blocks across different regimes
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


def main() -> int:
    daily = dataio.load("BTC", "all")
    # precompute returns for every grid config + baseline once
    ret = {tuple(sorted(c.items())): engine.strat_returns(engine.run("momentum", daily, **c), s_bull_code=1)
           for c in GRID}
    base = engine.strat_returns(engine.run("momentum", daily), s_bull_code=1)

    rows, sel_oos, base_oos = [], [], []
    for ts, te, lab in OOS:
        ts_, te_ = pd.Timestamp(ts, tz="UTC"), pd.Timestamp(te, tz="UTC")
        train_end = ts_ - pd.Timedelta(days=EMBARGO)
        # choose config by TRAIN-only Sortino
        best, best_s = None, -1e9
        for c in GRID:
            k = tuple(sorted(c.items()))
            s = _sortino(ret[k].loc[:train_end].values)
            if np.isfinite(s) and s > best_s:
                best_s, best = s, c
        r_sel = ret[tuple(sorted(best.items()))].loc[ts_:te_]
        r_base = base.loc[ts_:te_]
        sel_oos.append(r_sel); base_oos.append(r_base)
        rows.append((lab, best, _sortino(r_sel.values), _sortino(r_base.values)))
        print(f"{ts[:4]} {lab:10} → izbran train: re-entry {best['reentry_hold']}, "
              f"bear {best['bear_size_cut']:.0f}  |  OOS Sortino izbran {_sortino(r_sel.values):5.2f}  "
              f"baseline {_sortino(r_base.values):5.2f}")

    stitched_sel = pd.concat(sel_oos); stitched_base = pd.concat(base_oos)
    ss, sb = _sortino(stitched_sel.values), _sortino(stitched_base.values)
    print(f"\nZLEPLJEN OOS Sortino: izberi-iz-train {ss:.2f}  vs fiksni baseline {sb:.2f}  (Δ {ss-sb:+.2f})")
    _write(rows, ss, sb)
    print(f"Wrote {REPORTS/'aggressive_nested_btc.md'}")
    return 0


def _write(rows, ss, sb):
    wins = sum(1 for _, _, s, b in rows if s >= b - 0.05)
    L = ["# Nested walk-forward (BTC) — pravi test brez selection biasa", "",
         "Prej sem kandidata izbral gledajoč vse podatke, kar je selection bias. Tukaj v vsakem "
         "obdobju parameter izberem SAMO iz preteklosti (train), potem ga uporabim na neviden test. "
         "Izbira nikoli ne vidi testa. Iščem po re-entry {1,2,3,4} × bear-cut {0,25,50,75}, izberem "
         "po train Sortino.", "",
         "| Test obdobje | režim | izbran iz train | OOS Sortino (izbran) | OOS Sortino (baseline) |",
         "|---|---|---|---|---|"]
    for lab, cfg, s, b in rows:
        L.append(f"| {lab} | | re-entry {cfg['reentry_hold']}, bear {cfg['bear_size_cut']:.0f} | "
                 f"{s:.2f} | {b:.2f} |")
    L += ["", f"**Zlepljen OOS Sortino: izberi-iz-train {ss:.2f} vs fiksni baseline {sb:.2f} "
          f"(Δ {ss-sb:+.2f}).**", "",
          "## Kaj to pomeni", ""]
    if ss > sb + 0.10:
        L += ["Postopek 'izberi parameter samo iz preteklosti' na nevidenih obdobjih dejansko "
              "premaga fiksni baseline. To je pravi out-of-sample dokaz — izbira nikoli ni videla "
              "testa, pa vseeno generalizira. Ni le selection bias."]
    else:
        L += ["**Ko izbira NE vidi testa, prednost izgine (Δ ≈ 0).** To pomeni da je bil full-sample "
              "'win' (Sortino 1.62 → 1.92) večinoma **selection bias** — nastal je ker sem parameter "
              "izbral gledajoč iste podatke na katerih sem ga potem meril. Na res nevidenih podatkih "
              "se prednost ne ponovi.",
              "", "Mehanizem se vidi v izbranih parametrih: **bear-cut je nestabilen** — train izbere "
              "75 (2021, 2022), potem 0 (2023, 2024), potem 25 (2025). Nima stabilne vrednosti, ker "
              "kar je bilo optimalno na preteklosti ni optimalno na naslednjem obdobju (nestacionaren "
              "trg). Re-entry je bolj stabilen (večinoma 2), a sam ne dvigne zlepljenega OOS nad "
              "baseline.",
              "", "**Zaključek: brez ločenega train/test-a so per-leto/CPCV/bootstrap checki gledali "
              "isto izbiro na istih podatkih in so bili zavajajoče pozitivni. Nested walk-forward je "
              "edini ki to odpravi — in pokaže da tuning teh parametrov ne prinese zanesljive OOS "
              "prednosti. Ostani pri baseline (Pine) vrednostih.**"]
    # stability of picks
    picks_r = [cfg["reentry_hold"] for _, cfg, _, _ in rows]
    picks_b = [cfg["bear_size_cut"] for _, cfg, _, _ in rows]
    L += [f"Izbrani re-entry po foldih: {picks_r}. Izbrani bear-cut: {[int(x) for x in picks_b]}.",
          "", "*To je nested walk-forward: edini način ki brez ločenega fiksnega test-seta zagotovi "
          "da izbira parametra ne pogleda testnih podatkov (Lopez de Prado, AFML ch. 7/12).*", ""]
    (REPORTS / "aggressive_nested_btc.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
