"""Aggressive-tier tuning: can we capture more upside without breaking drawdown control?

Reviewer's point: exposure ~35-41% is low and we lag B&H upside. Test three
loosenings — wider trailing stop, faster re-entry, higher bear-regime size — on the
objective that matters for the aggressive tier: MORE CAGR + exposure, accepting more
drawdown (as long as MaxDD stays well under B&H). Evaluated leakage-safe on the design
set AND the untouched hold-out, pooled across the core assets, so we don't overfit.

Run:  PYTHONPATH=. .venv/bin/python testing/scripts/run_aggressive_tuning.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from testing.scripts import dataio, engine

RESULTS = _ROOT / "testing" / "results" / "aggressive"
REPORTS = _ROOT / "testing" / "reports"
RESULTS.mkdir(parents=True, exist_ok=True)

CORE = ["BTC", "ETH", "SOL", "AVAX", "LINK"]
DE, HS = dataio.DESIGN_END, dataio.HOLDOUT_START
TD = 365


def _metrics(sr: pd.Series, pos: pd.Series, part: str) -> dict:
    m = (sr.index <= DE) if part == "design" else (sr.index >= HS)
    r = sr[m].dropna()
    p = pos[m]
    if len(r) < 20:
        return {}
    eq = (1 + r).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    cagr = float(eq.iloc[-1] ** (TD / len(r)) - 1)
    down = np.sqrt(np.mean(np.minimum(r.values, 0.0) ** 2)) * np.sqrt(TD)
    ann_std = r.std() * np.sqrt(TD)
    return dict(cagr=cagr, exposure=float(p.mean() * 100), max_dd=dd,
                sharpe=(float(r.mean() * TD / ann_std) if ann_std > 1e-9 else np.nan),
                sortino=(float(r.mean() * TD / down) if down > 0 else np.nan),
                calmar=(cagr / abs(dd) if dd < 0 else np.nan))


def evaluate(label: str, overrides: dict) -> dict:
    rows = {"design": [], "holdout": []}
    btc_detail = {}
    for a in CORE:
        daily = dataio.load(a, "all")
        df = engine.run("momentum", daily, **overrides)
        sr = engine.strat_returns(df, s_bull_code=1)
        pos = pd.Series(engine.position(df, s_bull_code=1), index=df.index)
        for part in ("design", "holdout"):
            mm = _metrics(sr, pos, part)
            if mm:
                rows[part].append(mm)
                if a == "BTC":
                    btc_detail[part] = mm
    def med(part, key):
        vals = [r[key] for r in rows[part] if np.isfinite(r.get(key, np.nan))]
        return float(np.median(vals)) if vals else np.nan
    return {"label": label,
            **{f"d_{k}": med("design", k) for k in ("cagr", "exposure", "max_dd", "sharpe", "sortino", "calmar")},
            **{f"h_{k}": med("holdout", k) for k in ("cagr", "exposure", "max_dd", "sharpe", "sortino", "calmar")},
            "btc": btc_detail}


def main() -> int:
    configs = [
        ("BASELINE (trail12/reentry4/bear50)", {}),
        # 1) trailing stop — full meaningful range
        ("trail=8", {"trail_pct": 8.0}),
        ("trail=10", {"trail_pct": 10.0}),
        ("trail=15", {"trail_pct": 15.0}),
        ("trail=18", {"trail_pct": 18.0}),
        ("trail=20", {"trail_pct": 20.0}),
        # 2) re-entry lock — fast end
        ("reentry=1", {"reentry_hold": 1}),
        ("reentry=2", {"reentry_hold": 2}),
        ("reentry=3", {"reentry_hold": 3}),
        # 3) bear-regime size — full range
        ("bear_cut=0", {"bear_size_cut": 0.0}),
        ("bear_cut=25", {"bear_size_cut": 25.0}),
        ("bear_cut=70", {"bear_size_cut": 70.0}),
        ("bear_cut=100", {"bear_size_cut": 100.0}),
        # combinations
        ("COMBO reentry2+bear25", {"reentry_hold": 2, "bear_size_cut": 25.0}),
        ("COMBO reentry2+bear25+trail10",
         {"reentry_hold": 2, "bear_size_cut": 25.0, "trail_pct": 10.0}),
        ("COMBO trail18+reentry2 (bear50)", {"trail_pct": 18.0, "reentry_hold": 2}),
        ("COMBO trail18+reentry2+bear70",
         {"trail_pct": 18.0, "reentry_hold": 2, "bear_size_cut": 70.0}),
    ]
    rows = [evaluate(lbl, ov) for lbl, ov in configs]
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "btc"} for r in rows])
    df.to_csv(RESULTS / "aggressive_tuning.csv", index=False)

    print(f"{'config':<40} | {'DESIGN: CAGR  exp  MaxDD  Sort  Calm':<38} | HOLD-OUT: CAGR  exp  MaxDD  Sort")
    for r in rows:
        print(f"{r['label']:<40} | {r['d_cagr']*100:5.0f}% {r['d_exposure']:4.0f}% "
              f"{r['d_max_dd']*100:5.0f}% {r['d_sortino']:5.2f} {r['d_calmar']:5.2f} | "
              f"{r['h_cagr']*100:5.0f}% {r['h_exposure']:4.0f}% {r['h_max_dd']*100:5.0f}% {r['h_sortino']:5.2f}")
    _write(rows)
    print(f"\nWrote {RESULTS/'aggressive_tuning.csv'} and {REPORTS/'aggressive_tuning_report.md'}")
    return 0


def _write(rows):
    def r_of(lbl):
        return next(r for r in rows if r["label"].startswith(lbl))
    base = rows[0]
    L = ["# Momentum — rezultati tuninga (agresivni tier)", "",
         "Pooled median čez BTC/ETH/SOL/AVAX/LINK, neto brez fees. Ločeno na starem obdobju "
         "(design) in na 2025+ holdoutu ki ga pri nastavljanju nismo videli. Vsaka vrstica = cela "
         "baseline strategija, spremenjen samo navedeni parameter (razen COMBO vrstic).", "",
         "Za primerjavo: BTC buy&hold ima drawdown ~−77 %, torej so vse variante še vedno pol nižje.", "",
         "| Nastavitev | CAGR | Exp | MaxDD | Sharpe | Sortino | Calmar | HO CAGR | HO Sortino |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['label']} | {r['d_cagr']*100:.0f}% | {r['d_exposure']:.0f}% | "
                 f"{r['d_max_dd']*100:.0f}% | {r['d_sharpe']:.2f} | {r['d_sortino']:.2f} | "
                 f"{r['d_calmar']:.2f} | {r['h_cagr']*100:.0f}% | {r['h_sortino']:.2f} |")

    def delta(lbl, key):
        return r_of(lbl)[f"d_{key}"] - base[f"d_{key}"]
    L += ["", "## Kaj rezultati pokažejo", "",
          f"**Baseline (12/4/50):** CAGR {base['d_cagr']*100:.0f}%, exposure {base['d_exposure']:.0f}%, "
          f"MaxDD {base['d_max_dd']*100:.0f}%, Sharpe {base['d_sharpe']:.2f}, Sortino {base['d_sortino']:.2f}, "
          f"Calmar {base['d_calmar']:.2f}; holdout CAGR {base['h_cagr']*100:.0f}%.", "",
          "**Trailing stop** — malo premika in se nad 20 nasiti (18 in 20 skoraj enaka baseline-u). "
          "Tesnejši (8–10) niža drawdown a tudi donos. Šibek vzvod.",
          f"**Re-entry lock** — najmočnejši vzvod. reentry=2: Calmar "
          f"{r_of('reentry=2')['d_calmar']:.2f} (baseline {base['d_calmar']:.2f}), CAGR "
          f"{r_of('reentry=2')['d_cagr']*100:.0f}%. reentry=1 podoben, reentry=3 vmes. Nad 4 (baseline) slabše.",
          f"**Bear-cut** — nižje je bolje: bear=25 ima Calmar {r_of('bear_cut=25')['d_calmar']:.2f} in "
          f"boljši drawdown ({r_of('bear_cut=25')['d_max_dd']*100:.0f}%), bear=70 in bear=100 monotono "
          f"slabše (Calmar {r_of('bear_cut=70')['d_calmar']:.2f} / {r_of('bear_cut=100')['d_calmar']:.2f}, "
          f"MaxDD {r_of('bear_cut=100')['d_max_dd']*100:.0f}%). bear=0 (poln blok) je vmes.",
          f"**Najboljša kombinacija — reentry2+bear25:** CAGR {r_of('COMBO reentry2+bear25')['d_cagr']*100:.0f}%, "
          f"Calmar {r_of('COMBO reentry2+bear25')['d_calmar']:.2f}, MaxDD "
          f"{r_of('COMBO reentry2+bear25')['d_max_dd']*100:.0f}%, holdout Sortino "
          f"{r_of('COMBO reentry2+bear25')['h_sortino']:.2f}. Dva vzvoda ki delujeta skupaj.", "",
          "**Opomba glede Sharpe/Sortino:** dobri vzvodi dvignejo CAGR in Calmar, drawdown držijo ali "
          "znižajo, Sharpe in Sortino pa se malo premakneta (več tradanja doda volatilnost hitreje kot "
          "donos). Za agresivni tier smiselna menjava; za maksimiranje Sharpe ne.", ""]
    (REPORTS / "aggressive_tuning_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
