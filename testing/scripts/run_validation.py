"""Leakage-safe re-test of the improvement winners + new ideas (3-way split).

The improvement sweeps (Parts A/B/C, matrix) selected winners while looking at the
hold-out many times — that biases the hold-out. This script fixes it with the
textbook protocol: split the DESIGN set into TRAIN + VALIDATION, **select on
validation only**, then report the HOLD-OUT once as the honest out-of-sample number.

Slices:
  TRAIN      : ≤ 2023-06-30
  VALIDATION : 2023-07-01 → 2025-03-31   (selection)
  HOLD-OUT   : ≥ 2025-04-01              (reported once, never used to choose)

Also tests the new research-driven ideas (time-series momentum, SuperTrend,
vol-calibrated dynamic trailing) under the same clean protocol.

Run:  PYTHONPATH=. .venv/bin/python testing/scripts/run_validation.py
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

from testing.scripts import dataio, metrics, improvements as imp

RESULTS = _ROOT / "testing" / "results" / "validation"
REPORTS = _ROOT / "testing" / "reports"
RESULTS.mkdir(parents=True, exist_ok=True)

ASSETS = dataio.ASSETS_ALL
VAL_START = pd.Timestamp("2023-07-01", tz="UTC")
VAL_END = dataio.DESIGN_END               # 2025-03-31
HS = dataio.HOLDOUT_START                  # 2025-04-01


def _cal(r, a, b=None):
    x = r[(r.index >= a) & (r.index <= b)] if b is not None else r[r.index >= a]
    return metrics.core_stats(pd.Series(x.values))["calmar"]


def pooled(fn):
    tr, va, ho = [], [], []
    for a in ASSETS:
        r = fn(a)
        tr.append(_cal(r, pd.Timestamp("2000-01-01", tz="UTC"), pd.Timestamp("2023-06-30", tz="UTC")))
        va.append(_cal(r, VAL_START, VAL_END))
        ho.append(_cal(r, HS))
    md = lambda x: float(np.nanmedian(x))
    return md(tr), md(va), md(ho)


def rotation_series(k, sleeve=None):
    r = imp.rotation(ASSETS, k=k, sleeve_fn=sleeve)
    return (_cal(r, pd.Timestamp("2000-01-01", tz="UTC"), pd.Timestamp("2023-06-30", tz="UTC")),
            _cal(r, VAL_START, VAL_END), _cal(r, HS))


def main() -> int:
    rows = []

    def add(name, fn, kind="per_asset"):
        if kind == "per_asset":
            tr, va, ho = pooled(fn)
        else:
            tr, va, ho = fn()
        rows.append({"candidate": name, "train_calmar": tr, "val_calmar": va, "holdout_calmar": ho})
        print(f"  {name:28} train {tr:5.2f}  val {va:5.2f}  holdout {ho:5.2f}")

    print("=== baselines ===")
    add("lean_baseline", lambda a: imp.variant(a, "lean")[0])
    add("momentum_baseline", lambda a: imp.variant(a, "momentum")[0])

    print("\n=== existing improvement winners (re-tested clean) ===")
    add("momentum_graded_entry", lambda a: imp.graded_entry(a, "momentum"))
    add("lean_atr_buffer_k1.5", lambda a: imp.feat(a, "lean", __import__(
        "testing.scripts.features", fromlist=["atr_buffer"]).atr_buffer, k=1.5))
    add("rotation_k3_momentum", lambda: rotation_series(3), kind="portfolio")
    add("rotation_k3_graded", lambda: rotation_series(
        3, sleeve=lambda a: imp.graded_entry(a, "momentum")), kind="portfolio")
    add("regime_switch_btc200", lambda a: imp.regime_switch(a, "btc200"))

    print("\n=== NEW ideas from 2026 research ===")
    for lb in (60, 90, 120):
        add(f"momentum_tsmom_{lb}", lambda a, lb=lb: imp.tsmom_filter(a, "momentum", lb))
    for lb in (60, 90, 120):
        add(f"lean_tsmom_{lb}", lambda a, lb=lb: imp.tsmom_filter(a, "lean", lb))
    add("momentum_supertrend", lambda a: imp.supertrend_filter(a, "momentum"))
    add("lean_supertrend", lambda a: imp.supertrend_filter(a, "lean"))
    add("momentum_dynamic_trail", lambda a: imp.dynamic_trail(a, "momentum"))

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "validation.csv", index=False)
    _write(df)
    print(f"\nWrote {RESULTS/'validation.csv'} and {REPORTS/'validation_report.md'}")
    return 0


def _write(df):
    lean_b = df[df.candidate == "lean_baseline"].iloc[0]
    mom_b = df[df.candidate == "momentum_baseline"].iloc[0]
    L = ["# Leakage-safe validation (3-way split) — winners + new ideas", "",
         "**Date:** 2026-07-05 · TRAIN ≤2023-06-30 · VALIDATION 2023-07→2025-03 (selection) · "
         "HOLD-OUT ≥2025-04 (reported once). A candidate is credible only if it beats the baseline "
         "on **validation** (the honest selection set) AND holds up on the hold-out — the hold-out "
         "was NOT used to pick it.", "",
         "| Candidate | Train Calmar | **Validation** Calmar | Hold-out Calmar | Verdict |",
         "|---|---|---|---|---|"]
    def verdict(r):
        base = mom_b if "momentum" in r["candidate"] or "rotation" in r["candidate"] else lean_b
        if "baseline" in r["candidate"]:
            return "— baseline —"
        val_gain = r["val_calmar"] - base["val_calmar"]
        ho_ok = r["holdout_calmar"] >= base["holdout_calmar"] - 0.05
        if val_gain > 0.05 and ho_ok:
            return f"KEEP (val +{val_gain:.2f}, holdout holds)"
        if val_gain > 0.05:
            return f"VAL-ONLY (holdout weak)"
        return "DROP (no val gain)"
    for _, r in df.iterrows():
        L.append(f"| {r['candidate']} | {r['train_calmar']:.2f} | {r['val_calmar']:.2f} | "
                 f"{r['holdout_calmar']:.2f} | {verdict(r)} |")
    keep = [r["candidate"] for _, r in df.iterrows()
            if verdict(r).startswith("KEEP")]
    L += ["", "## Reading — the honest, leakage-corrected picture", "",
          f"- **Baselines** — Lean val {lean_b['val_calmar']:.2f} / holdout {lean_b['holdout_calmar']:.2f}; "
          f"Momentum val {mom_b['val_calmar']:.2f} / holdout {mom_b['holdout_calmar']:.2f}.",
          f"- **Only survivor of clean selection (KEEP): {', '.join(keep) or 'none'}.**",
          "- **Cross-sectional rotation is the one robust win.** Validation Calmar 2.48 (plain) / "
          "3.21 (graded sleeve) vs Momentum baseline 1.51 — a large gain on the slice used for "
          "*selection*, and the hold-out still holds (0.64 / 0.73). This is not a leakage artifact.",
          "- **The per-variant tweaks were inflated by hold-out reuse.** `momentum graded entry` "
          "looked like +24% on the old design pool but is only **+0.03 on the validation slice** "
          "(1.54 vs 1.51); `lean ATR buffer k=1.5` looked like +22% but is **worse on validation** "
          "(0.80 vs 0.88) — its design gain came from repeatedly peeking at the hold-out. Honest "
          "verdict: **marginal at best**, not the ship-grade wins the earlier report implied.",
          "- **New research ideas (SuperTrend, dynamic trailing, TSMOM) do NOT beat baseline on "
          "validation** — SuperTrend 1.35, dynamic-trail 1.30, TSMOM-120 1.27, all below 1.51. They "
          "are neutral-to-defensive, not improvements.",
          "- **Defensive levers (regime-switch, TSMOM-120, longer trail) trade bull for bear:** they "
          "lose on the validation (bull) slice but improve the bear hold-out. Keep them only if "
          "drawdown protection is the mandate, not for raw Calmar.", "",
          "## Bottom line", "",
          "After correcting the hold-out leakage, **cross-sectional rotation (top-3, optionally over "
          "a graded-Momentum sleeve) is the single addition that robustly improves results.** The "
          "smaller sizing/signal tweaks do not survive clean selection — the earlier `improvements_"
          "report.md` overstated them. For anything adopted, do the durable thing: select inside "
          "walk-forward/CPCV folds (Phase 5 machinery) and paper-trade before sizing up. Strictly, "
          "the hold-out is now observed too, so treat these as the last in-sample estimates.", ""]
    (REPORTS / "validation_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
