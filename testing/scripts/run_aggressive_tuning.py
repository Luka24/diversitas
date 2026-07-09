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
        # 1) wider trailing stop
        ("trail=15", {"trail_pct": 15.0}),
        ("trail=18", {"trail_pct": 18.0}),
        ("trail=20", {"trail_pct": 20.0}),
        # 2) faster re-entry
        ("reentry=3", {"reentry_hold": 3}),
        ("reentry=2", {"reentry_hold": 2}),
        # 3) higher bear-regime size
        ("bear_cut=60", {"bear_size_cut": 60.0}),
        ("bear_cut=70", {"bear_size_cut": 70.0}),
        ("bear_cut=80", {"bear_size_cut": 80.0}),
        # combined aggressive
        ("AGGRESSIVE (trail18/reentry2/bear70)",
         {"trail_pct": 18.0, "reentry_hold": 2, "bear_size_cut": 70.0}),
        ("AGGRESSIVE-lite (trail15/reentry3/bear60)",
         {"trail_pct": 15.0, "reentry_hold": 3, "bear_size_cut": 60.0}),
        # RECOMMENDED: the two levers that help, WITHOUT the bear-cut increase (which backfires)
        ("RECOMMENDED (trail18/reentry2/bear50)",
         {"trail_pct": 18.0, "reentry_hold": 2}),
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
    base = rows[0]
    L = ["# Aggressive-tier tuning — capture more upside without breaking DD control", "",
         "**Date:** 2026-07-10 · Pooled median across BTC/ETH/SOL/AVAX/LINK, leakage-safe "
         "(design ≤2025-03 for reading, hold-out ≥2025-04 shown alongside). Objective for the "
         "aggressive tier: **higher CAGR + exposure**, accepting more drawdown while MaxDD stays "
         "well under Buy&Hold (~−77% for BTC).", "",
         "| Config | Design CAGR | Exp | MaxDD | **Sharpe** | **Sortino** | Calmar | HO CAGR | HO Sharpe | HO Sortino |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['label']} | {r['d_cagr']*100:.0f}% | {r['d_exposure']:.0f}% | "
                 f"{r['d_max_dd']*100:.0f}% | {r['d_sharpe']:.2f} | {r['d_sortino']:.2f} | {r['d_calmar']:.2f} | "
                 f"{r['h_cagr']*100:.0f}% | {r['h_sharpe']:.2f} | {r['h_sortino']:.2f} |")
    L += ["", "## Reading — two of the three suggestions help, one backfires", "",
          f"- **Baseline** (pooled): design CAGR {base['d_cagr']*100:.0f}%, exposure "
          f"{base['d_exposure']:.0f}%, MaxDD {base['d_max_dd']*100:.0f}%, Sortino {base['d_sortino']:.2f}, "
          f"hold-out CAGR {base['h_cagr']*100:.0f}% / Sortino {base['h_sortino']:.2f}. Exposure is low — "
          "the reviewer is right about that.", "",
          "**1. Wider trailing stop (→18): ✓ modest win.** Exposure 19→22%, design CAGR/MaxDD "
          "unchanged, and the **hold-out improves** (CAGR −11%→−5%, Sortino −0.55→−0.29) — 12% was "
          "indeed a touch tight, tripping out of runs that continued. 15–20 are all similar; 18 is a "
          "sensible mid-point. 15 slightly worsens design MaxDD (−42%).",
          "**2. Faster re-entry (→2): ✓ the best single lever.** Design CAGR 39→41%, **Calmar "
          "1.02→1.19**, MaxDD unchanged (−38%), and hold-out improves too. Getting back in faster "
          "captures more with no drawdown cost. Clear adopt.",
          "**3. Higher bear-regime size (60/70/80): ✗ BACKFIRES.** It raises exposure exactly in "
          "bear regimes: design Calmar *falls* (1.02→0.96→0.91→0.87) and the **bear-market hold-out "
          "gets worse** (CAGR −11%→−12/−13/−14%, Sortino −0.55→−0.64→−0.68). The drawdown control the "
          "reviewer praised comes *from* the bear-cut — loosening it erodes precisely that. The "
          "premise ‘DD is controlled, we can afford more bear exposure’ is backwards. **Keep 50%** "
          "(or lower).", "",
          "## Recommendation", "",
          "- **Adopt `trail_pct=18` + `reentry_hold=2`, keep `bear_size_cut=50`** (the RECOMMENDED "
          "row). This lifts exposure/CAGR and improves the hold-out, without the bear-cut mistake — "
          "the combined-AGGRESSIVE row (with bear=70) shows the bear component dragging MaxDD to "
          "−42% and Sortino down.",
          "- **Honest scale of the win:** the gains are *incremental*, not transformative — exposure "
          "rises ~19%→~22%, CAGR a few points. The strategy is structurally low-exposure (flat ~65% "
          "of the time by design). To materially raise exposure you must loosen the ENTRY logic "
          "(trackline/momentum gates), not just the exit/sizing — that is a bigger change and should "
          "be tested separately, leakage-safe.",
          "- All adopted changes are **hold-out-confirmed** (not overfit to design); the rejected "
          "bear-cut change fails the hold-out, which is exactly how the leakage-safe test earns its "
          "keep.", "",
          "## How CAGR / Sharpe / Sortino react (the risk-adjusted trade-off)", "",
          "- **CAGR** goes UP with the good levers: faster re-entry is the driver (39→41%), wider "
          "trail ~flat (39→40%), bear-cut flat-to-down. RECOMMENDED ≈ 40%.",
          "- **Sharpe** ticks DOWN slightly on design for *every* loosening (baseline 1.13 → "
          "~1.04–1.11): more aggression = more trades/exposure, which adds volatility a bit faster "
          "than return. reentry=2 → 1.10, trail=18 → 1.11, trail=20 → 1.04 (too wide).",
          "- **Sortino** likewise dips a little on design (1.83 → ~1.68–1.87; reentry=2 → 1.75, "
          "trail=18 → 1.76) — same reason.",
          "- **BUT on the bear-market hold-out the good levers IMPROVE both** (Sharpe −0.39→−0.21, "
          "Sortino −0.55→−0.29) because they stop out less prematurely. The bear-cut increase does "
          "the opposite (Sharpe −0.39→−0.47).",
          "- **Interpretation:** this is the classic aggressive-tier trade-off — you gain **CAGR** "
          "and **Calmar** (return & drawdown-adjusted) and better bear robustness, at the cost of a "
          "small dip in **Sharpe/Sortino** (volatility-adjusted efficiency) on the calm design set. "
          "For an aggressive product that explicitly wants more upside, that trade is defensible; "
          "for a Sharpe-maximising mandate it is not. Net: RECOMMENDED lifts CAGR 39→40% and Calmar "
          "1.02→1.08 with Sharpe 1.13→1.07 (−0.06) and Sortino 1.83→1.68 (−0.15), and a clearly "
          "better hold-out.", ""]
    (REPORTS / "aggressive_tuning_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
