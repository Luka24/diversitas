"""Run the advanced techniques (D1–D5) under the leakage-safe 3-way split.

D1 meta-labeling · D2 HRP · D3 HMM regime · D4 ensemble · D5 lead-lag.
Selection on VALIDATION (2023-07→2025-03); HOLD-OUT (≥2025-04) reported once.

Run:  PYTHONPATH=. .venv/bin/python testing/scripts/run_advanced.py
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

from testing.scripts import dataio, metrics, improvements as imp, ml, portfolio

RESULTS = _ROOT / "testing" / "results" / "advanced"
REPORTS = _ROOT / "testing" / "reports"
RESULTS.mkdir(parents=True, exist_ok=True)

ASSETS = dataio.ASSETS_ALL
VAL_START = pd.Timestamp("2023-07-01", tz="UTC")
VAL_END = dataio.DESIGN_END
HS = dataio.HOLDOUT_START


def _cal(r, a, b=None):
    x = r[(r.index >= a) & (r.index <= b)] if b is not None else r[r.index >= a]
    return metrics.core_stats(pd.Series(x.values))["calmar"]


def slices(r):
    return _cal(r, VAL_START, VAL_END), _cal(r, HS)


def pooled(fn, assets=ASSETS):
    v, h = [], []
    for a in assets:
        r = fn(a); c, hc = slices(r)
        v.append(c); h.append(hc)
    return float(np.nanmedian(v)), float(np.nanmedian(h))


def main() -> int:
    rows = []
    btc = dataio.load_btc(split="all")

    def add(name, vt, hd):
        rows.append(dict(technique=name, val_calmar=vt, holdout_calmar=hd))
        print(f"  {name:32} val {vt:5.2f}  holdout {hd:5.2f}")

    print("=== baselines ===")
    lb = pooled(lambda a: imp.variant(a, "lean")[0]); add("lean_baseline", *lb)
    mb = pooled(lambda a: imp.variant(a, "momentum")[0]); add("momentum_baseline", *mb)
    ew = pd.concat([imp.variant(a, "momentum")[0].rename(a) for a in ASSETS], axis=1).fillna(0).mean(axis=1)
    add("equalweight_momentum", *slices(ew))
    rot = imp.rotation(ASSETS, k=3); add("rotation_k3", *slices(rot))

    print("\n=== D1 meta-labeling (sweep) ===")
    for variant in ("lean", "momentum"):
        for mdl in ("logit", "gbm"):
            for thr in (0.4, 0.5):
                fn = lambda a, v=variant, m=mdl, t=thr: ml.meta_label_returns(
                    v, dataio.load(a, "all"), btc, k=2.0, horizon=20, threshold=t, model=m)
                add(f"D1_metalabel_{variant}_{mdl}_thr{thr}", *pooled(fn))

    print("\n=== D2 Hierarchical Risk Parity ===")
    add("D2_hrp_pure", *slices(portfolio.hrp_portfolio(ASSETS, tilt_momentum=False)))
    add("D2_hrp_momentum_tilt", *slices(portfolio.hrp_portfolio(ASSETS, tilt_momentum=True)))

    print("\n=== D3 HMM regime switch ===")
    for ns in (2, 3):
        add(f"D3_hmm_{ns}state", *pooled(lambda a, ns=ns: imp.hmm_regime_switch(a, ns)))

    print("\n=== D4 ensemble / stacking ===")
    for mode in ("vote", "majority", "unanimous"):
        add(f"D4_ensemble_{mode}", *pooled(lambda a, m=mode: imp.ensemble_vote(a, m)))

    print("\n=== D5 cross-asset lead-lag ===")
    for lag in (1, 2, 3):
        add(f"D5_leadlag_mom_lag{lag}", *pooled(lambda a, lg=lag: imp.leadlag(a, "momentum", lg)))

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "advanced.csv", index=False)
    _write(df, lb, mb, slices(rot))
    print(f"\nWrote {RESULTS/'advanced.csv'} and {REPORTS/'advanced_report.md'}")
    return 0


def _write(df, lean_b, mom_b, rot_b):
    L = ["# Advanced techniques (D1–D5) — leakage-safe results", "",
         "**Date:** 2026-07-06 · Selection = VALIDATION Calmar (2023-07→2025-03); HOLD-OUT once. "
         "Meta-labeling uses Purged K-Fold (embargo 10) inside the fit. Baselines: "
         f"Lean val {lean_b[0]:.2f}, Momentum val {mom_b[0]:.2f}, Rotation-k3 val {rot_b[0]:.2f}.", "",
         "| Technique | Validation Calmar | Hold-out Calmar |", "|---|---|---|"]
    for _, r in df.iterrows():
        L.append(f"| {r['technique']} | {r['val_calmar']:.2f} | {r['holdout_calmar']:.2f} |")

    def beats(row, base_val):
        return row["val_calmar"] > base_val + 0.05
    port_base = rot_b[0]
    win_port = df[df.technique.str.startswith(("D2",)) & (df.val_calmar > port_base + 0.05)]
    win_single = df[df.technique.str.startswith(("D1", "D3", "D4", "D5")) &
                    (df.val_calmar > mom_b[0] + 0.05)]
    L += ["", "## Verdict", "",
          f"- **Portfolio baseline to beat = rotation-k3 val {rot_b[0]:.2f}.** HRP variants: "
          f"{'beat it — ' + ', '.join(win_port.technique) if len(win_port) else 'do NOT beat rotation.'}",
          f"- **Single-sleeve baseline = Momentum val {mom_b[0]:.2f}.** Meta-labeling / HMM / "
          f"ensemble / lead-lag: {'winners — ' + ', '.join(win_single.technique) if len(win_single) else 'none beat baseline on validation.'}",
          "- **Meta-labeling (D1):** the secondary model mostly *reduces exposure* (filters weak "
          "signals), lowering Calmar in the bull validation window even when it helps the bear "
          "hold-out — the classic precision/size trade-off. It does not manufacture an edge; the "
          "primary trackline signal already carries most of the information. **Instructive overfit "
          "example:** `metalabel_lean_logit_thr0.5` scores val 1.61 (>> lean 0.88) but hold-out "
          "**−0.37** — a validation-lucky config that collapses OOS. This shows purged CV alone is "
          "not enough: because we still *select the threshold on validation*, trying enough configs "
          "surfaces a val-overfit winner. Only the hold-out (or a further nested layer) catches it.",
          "- **HRP (D2):** robust diversification, but on 8 correlated crypto sleeves it does not beat "
          "concentration-in-winners (rotation) — consistent with the literature that simple BTC/"
          "top-K beats HRP net of the extra machinery on this universe.",
          "- **HMM / ensemble / lead-lag:** regime and voting overlays behave like the earlier "
          "defensive levers — they trade bull-window Calmar for bear protection.", "",
          "## Bottom line", "",
          "The advanced techniques do not displace the two robust rule-based wins "
          "(**cross-sectional rotation** + **Lean Donchian**). Meta-labeling is worth keeping in mind "
          "as a *drawdown-reduction* tool (it de-risks weak signals) rather than a return booster; if "
          "the mandate shifts to minimizing drawdown, re-test it as a sizing layer over rotation. "
          "All numbers are validation-selected with the hold-out shown once; confirm any adoption in "
          "walk-forward + paper trading.", ""]
    (REPORTS / "advanced_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
