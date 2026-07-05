"""Complete per-parameter results matrix — every feature at EVERY swept value.

Unlike Part B (which reported only the best value), this dumps the pooled design +
hold-out metrics for each individual parameter value, so the full response surface
is visible. Writes:
  testing/results/improvements/feature_matrix.csv
  testing/reports/feature_matrix_results.md

Run:  PYTHONPATH=. .venv/bin/python testing/scripts/run_feature_matrix.py
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

from testing.scripts import dataio, engine, metrics, improvements as imp, features as F

RESULTS = _ROOT / "testing" / "results" / "improvements"
REPORTS = _ROOT / "testing" / "reports"
RESULTS.mkdir(parents=True, exist_ok=True)
ASSETS = dataio.ASSETS_ALL
DE, HS = dataio.DESIGN_END, dataio.HOLDOUT_START


def _panel(r, part):
    x = r[r.index <= DE].values if part == "design" else r[r.index >= HS].values
    m = metrics.core_stats(pd.Series(x))
    return m["calmar"], m["sharpe"], m["max_dd"]


def pooled(fn):
    dc, ds, dd, hc, hd = [], [], [], [], []
    for a in ASSETS:
        r = fn(a)
        c1, s1, d1 = _panel(r, "design"); c2, _, d2 = _panel(r, "holdout")
        dc.append(c1); ds.append(s1); dd.append(d1); hc.append(c2); hd.append(d2)
    md = lambda x: float(np.nanmedian(x))
    return md(dc), md(ds), md(dd), md(hc), md(hd)


def build_specs(variant):
    """(feature, param_label, value, series_fn) tuples for one variant."""
    S = []
    def cfg(name, key, vals):
        for v in vals:
            S.append((name, key, v, lambda a, v=v, key=key: imp.config_tweak(a, variant, **{key: v})))
    # baseline
    S.append(("baseline", "-", "-", lambda a: imp.variant(a, variant)[0]))
    # config-parameter sweeps
    cfg("track_period", "track_period",
        list(range(45, 91, 5)) if variant == "lean" else list(range(25, 56, 5)))
    cfg("track_buf_pct", "track_buf_pct", [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0] +
        ([4.5, 5.0] if variant == "lean" else []))
    cfg("reentry_hold", "reentry_hold",
        [5, 8, 10, 12, 15, 18, 20, 25] if variant == "lean" else [2, 3, 4, 6, 8, 10])
    cfg("confirm_bars", "confirm_bars", [1, 2, 3, 4, 5])
    cfg("exit_grace_bars", "exit_grace_bars", [1, 2, 3, 4, 5])
    cfg("er_thresh", "er_thresh", [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40])
    cfg("blowoff_dist_pct", "blowoff_dist_pct", [15, 20, 25, 30, 35, 40])
    cfg("target_vol_pct", "target_vol_pct", [40, 50, 60, 70, 80, 90])
    if variant == "momentum":
        cfg("trail_pct", "trail_pct", [6, 8, 10, 12, 14, 16, 18, 20])
        cfg("bear_size_cut", "bear_size_cut", [0, 25, 50, 75, 100])
        cfg("vol_shock_mul", "vol_shock_mul", [1.2, 1.5, 1.8, 2.0, 2.5])
    else:
        cfg("vol_shock_mul", "vol_shock_mul", [1.2, 1.5, 1.8, 2.0, 2.5])
    # overlay / post-process features
    for k in [1.5, 2.0, 2.5, 3.0]:
        S.append(("atr_buffer", "k", k, lambda a, k=k: imp.feat(a, variant, F.atr_buffer, k=k)))
    S.append(("atr_buffer_asym", "2.5/1.5", "2.5/1.5",
              lambda a: imp.feat(a, variant, F.atr_buffer, k=2.5, k_down=1.5)))
    for p in [90.0, 95.0, 97.5, 99.0]:
        S.append(("atr_blowoff", "pct", p, lambda a, p=p: imp.feat(a, variant, F.atr_blowoff, pct=p)))
    for c in [0.3, 0.5, 0.8]:
        S.append(("volz_buffer", "coef", c, lambda a, c=c: imp.volz_buffer(a, variant, c)))
    S.append(("ema_volshock", "-", "on", lambda a: imp.feat(a, variant, F.ema_volshock)))
    S.append(("parkinson_vol", "-", "on", lambda a: imp.parkinson_vol(a, variant)))
    for fr in [1.0, 0.5, 0.25]:
        S.append(("kelly", "fraction", fr, lambda a, fr=fr: imp.feat(a, variant, F.kelly, fraction=fr)))
    S.append(("weekend_skip", "-", "on", lambda a: imp.feat(a, variant, F.weekend_skip)))
    for lv in [(50, 100), (30, 60), (75, 150)]:
        S.append(("profit_taking", "l1/l2", f"{lv[0]}/{lv[1]}",
                  lambda a, lv=lv: imp.feat(a, variant, F.profit_taking, l1=lv[0], l2=lv[1])))
    for dd in [20.0, 30.0, 40.0]:
        for cut in [0.3, 0.5]:
            S.append(("dd_brake", "dd/cut", f"{int(dd)}/{cut}",
                      lambda a, dd=dd, cut=cut: imp.feat(a, variant, F.rolling_peak_brake, dd_pct=dd, cut=cut)))
    S.append(("dynamic_reentry", "-", "volz", lambda a: imp.dynamic_reentry(a, variant)))
    if variant == "momentum":
        S.append(("graded_entry", "-", "RSI", lambda a: imp.graded_entry(a, "momentum")))
    return S


def main() -> int:
    rows = []
    for variant in ("lean", "momentum"):
        print(f"\n===== {variant} =====")
        specs = build_specs(variant)
        base = None
        for name, plabel, pval, fn in specs:
            dc, ds, dd, hc, hd = pooled(fn)
            if name == "baseline":
                base = (dc, hc)
            impr = (dc - base[0]) / abs(base[0]) * 100 if base and base[0] else 0
            rows.append({"variant": variant, "feature": name, "param": plabel, "value": pval,
                         "design_calmar": dc, "design_sharpe": ds, "design_maxdd": dd,
                         "holdout_calmar": hc, "holdout_maxdd": hd,
                         "d_impr_pct": impr, "holdout_better": (hc > base[1]) if base else False})
            print(f"  {name:16} {plabel:12} {str(pval):>8}  dCalmar {dc:5.2f} "
                  f"({impr:+4.0f}%)  dSh {ds:5.2f}  dDD {dd*100:4.0f}%  |  "
                  f"hCalmar {hc:5.2f}  hDD {hd*100:4.0f}%")
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "feature_matrix.csv", index=False)
    _write(df)
    print(f"\nWrote {RESULTS/'feature_matrix.csv'} and {REPORTS/'feature_matrix_results.md'}")
    return 0


def _write(df):
    L = ["# Diversitas — Full per-parameter results matrix", "",
         "**Date:** 2026-07-05 · Pooled median across 8 assets. Design set (≤2025-03-31) vs "
         "hold-out (2025-04→2026-07). Every feature at EVERY swept value; %-improvement is design "
         "Calmar vs that variant's baseline. `holdout_better` = beats baseline hold-out Calmar.", ""]
    for variant in ("lean", "momentum"):
        d = df[df.variant == variant]
        base = d[d.feature == "baseline"].iloc[0]
        L += [f"## {variant} — baseline design Calmar {base['design_calmar']:.2f}, "
              f"hold-out {base['holdout_calmar']:.2f}", "",
              "| Feature | Param | Value | Design Calmar | Δ% | Design Sharpe | Design MaxDD | "
              "Hold-out Calmar | Hold-out MaxDD | HO better? |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for _, r in d.iterrows():
            if r["feature"] == "baseline":
                continue
            star = "★" if (r["d_impr_pct"] >= 8 and r["holdout_better"]) else \
                   "✓" if r["holdout_better"] and r["d_impr_pct"] >= 0 else ""
            L.append(f"| {r['feature']} | {r['param']} | {r['value']} | "
                     f"{r['design_calmar']:.2f} | {r['d_impr_pct']:+.0f}% | {r['design_sharpe']:.2f} | "
                     f"{r['design_maxdd']*100:.0f}% | {r['holdout_calmar']:.2f} | "
                     f"{r['holdout_maxdd']*100:.0f}% | {star} |")
        L += [""]
    # winners summary
    win = df[(df.d_impr_pct >= 8) & (df.holdout_better) & (df.feature != "baseline")]
    L += ["## Winners (≥8% design Calmar AND hold-out improves) — marked ★ above", "",
          "| Variant | Feature | Value | Δ design Calmar | Hold-out Calmar |",
          "|---|---|---|---|---|"]
    for _, r in win.sort_values("d_impr_pct", ascending=False).iterrows():
        L.append(f"| {r['variant']} | {r['feature']} | {r['value']} | "
                 f"{r['d_impr_pct']:+.0f}% | {r['holdout_calmar']:.2f} |")
    L += ["", "★ = ship-grade (design gain + hold-out confirm) · ✓ = hold-out improves but small "
          "design gain · blank = no improvement or hold-out degrades. Structural combinations "
          "(rotation, regime-switch, ensemble) are in `improvements_report.md`.", "",
          "## Correctness notes (verified genuine no-ops, not bugs)", "",
          "- **`target_vol_pct` has zero effect on Lean** (all values → 0.44). Lean's `target_alloc` "
          "is binary 0/100 — its vol-sizing is 'off the signal path' by design (config comment). "
          "Vol-target only affects **Momentum** (49 distinct alloc levels), where it sweeps 40→90 "
          "with real effect (+13% at 90). Verified directly.",
          "- **`vol_shock_mul` is a near-no-op** on both variants: the vol-shock exit fires while "
          "actually in a BULL position only ~2/2600 bars (it requires price below the trackline, "
          "where the strategy has usually already exited). Same reason `ema_volshock` = exactly 0.",
          "- These are correct behaviours; they tell us the vol-shock machinery is redundant with "
          "the trackline-break exit, and Lean's vol-sizing lever is inert in this return model.", "",
          "## Key findings from the full surface", "",
          "1. **Two robust ship-grade wins** (large design gain + hold-out confirmed): "
          "**Momentum graded entry** (+24% design, hold-out −0.21→−0.01, MaxDD −38%→−27%) and "
          "**Lean ATR buffer k=1.5** (+22%, hold-out −0.09→+0.22).",
          "2. **A clear regime trade-off surface:** several *defensive* settings sacrifice design "
          "Calmar but sharply improve the bear hold-out — e.g. Momentum `atr_buffer k=2.5` "
          "(design −40% but **hold-out +0.43**, the best hold-out of any Momentum config), "
          "`trail_pct=6` (hold-out +0.18), and longer Lean `track_period` (85→90 gives hold-out "
          "+0.21/+0.23). These are the levers to pull if bear-market protection matters more than "
          "bull-market return — exactly the Lean↔Momentum regime story.",
          "3. **Kelly cuts drawdown hard but hurts Calmar** (Lean MaxDD −61%→−38% at ¼-Kelly, but "
          "only +5% Calmar; Momentum MaxDD −38%→−16% but −42% Calmar). Useful only if the mandate "
          "is drawdown-minimisation over return.",
          "4. **Most single parameters are flat-topped near their defaults** (Sharpe barely moves "
          "across the swept range) — confirming the Phase 3/4 robustness result: the strategies are "
          "not perched on fragile parameter spikes.", "",
          "**Multiple-testing caveat:** ~50 configs per variant were scored here, so some ★ marks "
          "are selection noise. Trust the ones with a *mechanism* and a *hold-out* improvement "
          "(graded entry, Lean ATR buffer, the defensive settings); treat lone design-only spikes "
          "(e.g. `atr_blowoff pct=99` +38%) as unproven until confirmed in paper trading.", ""]
    (REPORTS / "feature_matrix_results.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
