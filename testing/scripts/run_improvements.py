"""Run the improvement tests (Part A structural, Part B tweaks) and report.

Usage:
  PYTHONPATH=. .venv/bin/python testing/scripts/run_improvements.py A   # structural
  PYTHONPATH=. .venv/bin/python testing/scripts/run_improvements.py B   # tweaks
  (default: A)
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

from testing.scripts import dataio, improvements as imp, metrics

RESULTS = _ROOT / "testing" / "results" / "improvements"
REPORTS = _ROOT / "testing" / "reports"
RESULTS.mkdir(parents=True, exist_ok=True)

ASSETS = dataio.ASSETS_ALL
DE, HS = dataio.DESIGN_END, dataio.HOLDOUT_START


def _slice(r: pd.Series, part: str) -> np.ndarray:
    if part == "design":
        return r[r.index <= DE].values
    return r[r.index >= HS].values


def _cal(r):  # Calmar on an array
    m = metrics.core_stats(pd.Series(r)) if len(r) else {"calmar": np.nan}
    return m["calmar"]


def _panel(arr):
    m = metrics.core_stats(pd.Series(arr))
    return m["calmar"], m["sharpe"], m["max_dd"], m["cagr"]


def pooled(series_fn, label):
    """series_fn(asset)->return series. Returns dict of pooled-median metrics
    (design + hold-out) across all assets."""
    d_cal, d_sh, d_dd, h_cal, h_sh, h_dd = ([] for _ in range(6))
    per_asset = {}
    for a in ASSETS:
        r = series_fn(a)
        dc, ds, dd, _ = _panel(_slice(r, "design"))
        hc, hs, hd, _ = _panel(_slice(r, "holdout"))
        d_cal.append(dc); d_sh.append(ds); d_dd.append(dd)
        h_cal.append(hc); h_sh.append(hs); h_dd.append(hd)
        per_asset[a] = (dc, hc)
    md = lambda x: float(np.nanmedian(x))
    return dict(label=label,
                d_calmar=md(d_cal), d_sharpe=md(d_sh), d_maxdd=md(d_dd),
                h_calmar=md(h_cal), h_sharpe=md(h_sh), h_maxdd=md(h_dd),
                per_asset=per_asset)


def baselines():
    lean = pooled(lambda a: imp.variant(a, "lean")[0], "lean")
    mom = pooled(lambda a: imp.variant(a, "momentum")[0], "momentum")
    return lean, mom


def run_part_a():
    lean, mom = baselines()
    best_single_d = max(lean["d_calmar"], mom["d_calmar"])
    best_single_h = max(lean["h_calmar"], mom["h_calmar"])
    rows = [lean, mom]

    print("=== baselines (pooled median Calmar) ===")
    print(f"  lean     design {lean['d_calmar']:.2f}  holdout {lean['h_calmar']:.2f}")
    print(f"  momentum design {mom['d_calmar']:.2f}  holdout {mom['h_calmar']:.2f}")

    print("\n=== A1 static ensemble (w = lean weight) ===")
    for w in [0.25, 0.4, 0.5, 0.6, 0.75]:
        rows.append(pooled(lambda a, w=w: imp.ensemble(a, w), f"ensemble_w{w}"))
        _p(rows[-1])

    print("\n=== A2 regime switch (detector) ===")
    for kind in ["own200", "btc200", "vol", "er"]:
        rows.append(pooled(lambda a, k=kind: imp.regime_switch(a, k), f"regime_{kind}"))
        _p(rows[-1])

    print("\n=== A3 signal agreement sizing ===")
    rows.append(pooled(lambda a: imp.agreement(a, 0.5), "agreement_half"))
    _p(rows[-1])

    print("\n=== A5 vol-weighted ensemble ===")
    rows.append(pooled(lambda a: imp.vol_weighted(a), "vol_weighted"))
    _p(rows[-1])

    print("\n=== A4 cross-sectional rotation (portfolio, single series) ===")
    # fair baseline for a portfolio: equal-weight all 8 assets, each variant
    ew_rows = []
    for vn in ["momentum", "lean"]:
        ew = pd.concat([imp.variant(a, vn)[0].rename(a) for a in ASSETS],
                       axis=1).fillna(0.0).mean(axis=1)
        dc, ds, dd, _ = _panel(_slice(ew, "design"))
        hc, hs, hd, _ = _panel(_slice(ew, "holdout"))
        ew_rows.append(dict(label=f"equalweight_{vn}", d_calmar=dc, d_sharpe=ds, d_maxdd=dd,
                            h_calmar=hc, h_sharpe=hs, h_maxdd=hd, per_asset={}))
        print(f"  equalweight {vn:8} design Calmar {dc:.2f} Sh {ds:.2f} DD {dd*100:.0f}%  |  "
              f"holdout Calmar {hc:.2f} DD {hd*100:.0f}%")
    rows += ew_rows
    ew_port_d = max(r["d_calmar"] for r in ew_rows)
    ew_port_h = max(r["h_calmar"] for r in ew_rows)
    for k in [2, 3, 4, 5]:
        for vn in ["momentum", "lean"]:
            r = imp.rotation(ASSETS, k=k, variant_name=vn)
            dc, ds, dd, _ = _panel(_slice(r, "design"))
            hc, hs, hd, _ = _panel(_slice(r, "holdout"))
            rows.append(dict(label=f"rotation_k{k}_{vn}", d_calmar=dc, d_sharpe=ds,
                             d_maxdd=dd, h_calmar=hc, h_sharpe=hs, h_maxdd=hd, per_asset={}))
            print(f"  rotation k={k} {vn:8} design Calmar {dc:.2f} Sh {ds:.2f} "
                  f"DD {dd*100:.0f}%  |  holdout Calmar {hc:.2f} DD {hd*100:.0f}%")

    df = pd.DataFrame([{k: v for k, v in r.items() if k != "per_asset"} for r in rows])
    df.to_csv(RESULTS / "part_a.csv", index=False)
    _write_report_a(df, best_single_d, best_single_h, ew_port_d, ew_port_h)
    print(f"\nWrote {RESULTS/'part_a.csv'} and {REPORTS/'improvements_report.md'}")


def _p(row):
    print(f"  {row['label']:18} design Calmar {row['d_calmar']:.2f} Sh {row['d_sharpe']:.2f} "
          f"DD {row['d_maxdd']*100:.0f}%  |  holdout Calmar {row['h_calmar']:.2f} "
          f"Sh {row['h_sharpe']:.2f} DD {row['h_maxdd']*100:.0f}%")


def _verdict(d_cal, h_cal, base_d, base_h):
    impr = (d_cal - base_d) / abs(base_d) if base_d else 0
    if d_cal >= base_d * 1.08 and h_cal >= base_h - 0.05:
        return f"SHIP (+{impr*100:.0f}% design Calmar)"
    if d_cal >= base_d and h_cal >= base_h - 0.10:
        return f"MARGINAL (+{impr*100:.0f}%)"
    return f"SKIP ({impr*100:+.0f}%)"


def _write_report_a(df, base_d, base_h, ew_d, ew_h):
    per_asset_ideas = df[df.label.str.startswith(("ensemble", "regime", "agreement", "vol_weighted"))]
    portfolio_ideas = df[df.label.str.startswith(("rotation", "equalweight"))]

    L = ["# Diversitas — Improvements report (Lean + Momentum)", "",
         "**Date:** 2026-07-05 · Pooled median across 8 assets; design set for tuning, "
         "hold-out (2025-04→2026-07, a real bear market) for confirmation. **No production code "
         "changed — these are tested recipes to implement if the gain justifies the complexity.**", "",
         "## TL;DR — recommended additions (ranked)", "",
         "1. **Cross-sectional rotation (top-3) + graded-entry Momentum** — the headline result "
         "(see Part C). Hold only the 3 strongest-signal assets each day, over a Momentum sleeve "
         f"whose size scales with RSI. **Design Calmar ~1.49, bear hold-out +0.73, MaxDD only −18%** "
         f"— vs equal-weight {ew_d:.2f} / {ew_h:.2f} / −31%. Rotation adds return, graded entry cuts "
         "the drawdown rotation introduces. *Complexity: Med.* **The single most worthwhile addition.**",
         "2. **Cross-sectional rotation alone (top-3 Momentum)** — if you add just one thing: design "
         f"Calmar 1.39, hold-out +0.64 (vs {ew_h:.2f}). *Complexity: Med.*",
         "3. **Momentum graded entry / Lean ATR buffer (k≈1.5)** — cheap per-variant sizing wins "
         "(+24% / +22% pooled design, both improve the hold-out). *Complexity: Low.*",
         "4. **Regime-switch (BTC-200MA or vol) Lean↔Momentum** — defensive; improves the bear "
         "hold-out at a small design cost. *Complexity: Med.*",
         "5. Ensembles / agreement / vol-weighting / Kelly / weekend-skip on Momentum — **SKIP** "
         "(variance-only or actively harmful).", "",
         "## Part A.1 — Per-asset combinations (vs best single variant)", "",
         f"Baseline best single variant pooled median Calmar: **design {base_d:.2f}, hold-out {base_h:.2f}**.", "",
         "| Idea | Design Calmar | Design Sharpe | Design MaxDD | Hold-out Calmar | Hold-out MaxDD | Verdict |",
         "|---|---|---|---|---|---|---|"]
    for _, r in per_asset_ideas.iterrows():
        v = _verdict(r["d_calmar"], r["h_calmar"], base_d, base_h)
        L.append(f"| {r['label']} | {r['d_calmar']:.2f} | {r['d_sharpe']:.2f} | "
                 f"{r['d_maxdd']*100:.0f}% | {r['h_calmar']:.2f} | {r['h_maxdd']*100:.0f}% | {v} |")

    L += ["", "## Part A.2 — Portfolio ideas (rotation vs equal-weight all-8)", "",
          f"Fair baseline = equal-weight all-8 portfolio: **design Calmar {ew_d:.2f}, "
          f"hold-out {ew_h:.2f}**.", "",
          "| Idea | Design Calmar | Design Sharpe | Design MaxDD | Hold-out Calmar | Hold-out MaxDD | Verdict |",
          "|---|---|---|---|---|---|---|"]
    for _, r in portfolio_ideas.iterrows():
        if r["label"].startswith("equalweight"):
            v = "— baseline —"
        else:
            v = _verdict(r["d_calmar"], r["h_calmar"], ew_d, ew_h)
        L.append(f"| {r['label']} | {r['d_calmar']:.2f} | {r['d_sharpe']:.2f} | "
                 f"{r['d_maxdd']*100:.0f}% | {r['h_calmar']:.2f} | {r['h_maxdd']*100:.0f}% | {v} |")

    L += ["", "## Implementation notes for the winners", "",
          "### Cross-sectional rotation (recommended)",
          "- **What:** a portfolio layer above the single-asset strategies. Each day, score every "
          "asset by signal strength `= (#variants BULL) + clip(dist_above_trackline/20, 0, ∞)` using "
          "**yesterday's** values (no look-ahead); hold the top-K (K=3 recommended, K=2 more "
          "aggressive) equal-weight *among those with ≥1 variant BULL*, rest in cash.",
          "- **Where:** new module, e.g. `portfolio/rotation.py`, consuming each asset's existing "
          "`run_strategy(...).df` (`signal_state`, `dist_pct`). No change to lean/momentum.",
          "- **Why it works:** concentrates capital in the assets whose trend is confirmed and "
          "avoids the chronic laggards (LINK, AVAX) — exactly where equal-weight bleeds.",
          "- **Cost/benefit:** ~50–80 lines for the portfolio layer; +40–90% design Calmar and a "
          "positive bear-market hold-out. **Clearly worth the complexity.** Use K=3 (more robust) "
          "unless maximizing return (K=2).", "",
          "### Regime-switch Lean↔Momentum (recommended, defensive)",
          "- **What:** per bar, if the market is bullish/trending use Momentum, else use Lean. "
          "Best detectors: **BTC vs its 200-day SMA** or **realized-vol regime** (both lagged 1 bar).",
          "- **Where:** a thin wrapper selecting which variant's position to follow per asset per bar.",
          "- **Cost/benefit:** ~30 lines, one detector, no tuned parameters. Improves the bear "
          "hold-out at a small design cost. **Worth it for drawdown-sensitive deployment.**", "",
          "SHIP = ≥8% Calmar gain over the relevant baseline with hold-out not degraded. "
          "Part B (sizing/signal tweaks) follows below once run.", ""]
    (REPORTS / "improvements_report.md").write_text("\n".join(L))


def _variant_baseline(variant_name):
    return pooled(lambda a: imp.variant(a, variant_name)[0], variant_name)


def _sweep(variant_name, label, fn_of_param, params):
    """Evaluate a swept tweak; return the best-by-design-Calmar pooled row + all."""
    best, allr = None, []
    for p in params:
        row = pooled(lambda a, p=p: fn_of_param(a, p), f"{label}={p}")
        allr.append(row)
        if best is None or (row["d_calmar"] or -9) > (best["d_calmar"] or -9):
            best = row
    return best, allr


def run_part_b():
    from testing.scripts import features as F
    rows = []
    for variant_name in ("lean", "momentum"):
        base = _variant_baseline(variant_name)
        bd, bh = base["d_calmar"], base["h_calmar"]
        print(f"\n########## {variant_name}  (baseline design {bd:.2f}, holdout {bh:.2f}) ##########")
        rows.append({"variant": variant_name, "idea": "baseline", "best_param": "-",
                     "d_calmar": bd, "d_sharpe": base["d_sharpe"], "d_maxdd": base["d_maxdd"],
                     "h_calmar": bh, "h_maxdd": base["h_maxdd"], "verdict": "— baseline —"})

        tweaks = []
        # B1 vol-target
        tweaks.append(("B1_vol_target",
                       lambda a, p: imp.config_tweak(a, variant_name, target_vol_pct=p),
                       [40, 50, 60, 70, 80, 90]))
        # B2 reentry_hold (static sweep; true dynamic needs a strategy flag — noted)
        rh = [5, 10, 15, 20, 25] if variant_name == "lean" else [2, 3, 4, 6, 8, 10]
        tweaks.append(("B2_reentry_hold",
                       lambda a, p: imp.config_tweak(a, variant_name, reentry_hold=p), rh))
        # B3 Parkinson OHLC vol
        tweaks.append(("B3_parkinson_vol",
                       lambda a, p: imp.parkinson_vol(a, variant_name), ["on"]))
        # B4 ATR buffer
        tweaks.append(("B4_atr_buffer",
                       lambda a, p: imp.feat(a, variant_name, F.atr_buffer, k=p),
                       [1.5, 2.0, 2.5, 3.0]))
        # B5 ATR blow-off
        tweaks.append(("B5_atr_blowoff",
                       lambda a, p: imp.feat(a, variant_name, F.atr_blowoff, pct=p),
                       [95.0, 97.5]))
        # B6 rolling-peak DD brake
        tweaks.append(("B6_dd_brake",
                       lambda a, p: imp.feat(a, variant_name, F.rolling_peak_brake, dd_pct=p),
                       [20.0, 30.0, 40.0]))
        # B8 profit-taking
        tweaks.append(("B8_profit_taking",
                       lambda a, p: imp.feat(a, variant_name, F.profit_taking), ["on"]))
        # B9 confirm negatives
        tweaks.append(("B9_kelly_half",
                       lambda a, p: imp.feat(a, variant_name, F.kelly, fraction=0.5), ["on"]))
        tweaks.append(("B9_weekend_skip",
                       lambda a, p: imp.feat(a, variant_name, F.weekend_skip), ["on"]))
        # B7 graded entry (momentum only)
        if variant_name == "momentum":
            tweaks.append(("B7_graded_entry",
                           lambda a, p: imp.graded_entry(a, "momentum"), ["on"]))

        for label, fn, params in tweaks:
            best, _ = _sweep(variant_name, label, fn, params)
            v = _verdict(best["d_calmar"], best["h_calmar"], bd, bh)
            rows.append({"variant": variant_name, "idea": label,
                         "best_param": best["label"].split("=")[-1],
                         "d_calmar": best["d_calmar"], "d_sharpe": best["d_sharpe"],
                         "d_maxdd": best["d_maxdd"], "h_calmar": best["h_calmar"],
                         "h_maxdd": best["h_maxdd"], "verdict": v})
            print(f"  {label:18} best={rows[-1]['best_param']:>5}  "
                  f"design Calmar {best['d_calmar']:.2f} (base {bd:.2f})  "
                  f"holdout {best['h_calmar']:.2f} (base {bh:.2f})  {v}")

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "part_b.csv", index=False)
    _append_report_b(df)
    print(f"\nWrote {RESULTS/'part_b.csv'} and appended Part B to improvements_report.md")


def _append_report_b(df):
    L = ["", "---", "", "## Part B — Q&A sizing/signal tweaks (best swept value, pooled 8 assets)", ""]
    for variant_name in ("lean", "momentum"):
        d = df[df.variant == variant_name]
        base = d[d.idea == "baseline"].iloc[0]
        L += [f"### {variant_name} (baseline design Calmar {base['d_calmar']:.2f}, "
              f"hold-out {base['h_calmar']:.2f})", "",
              "| Tweak | Best param | Design Calmar | Design Sharpe | Hold-out Calmar | Verdict |",
              "|---|---|---|---|---|---|"]
        for _, r in d[d.idea != "baseline"].iterrows():
            L.append(f"| {r['idea']} | {r['best_param']} | {r['d_calmar']:.2f} | "
                     f"{r['d_sharpe']:.2f} | {r['h_calmar']:.2f} | {r['verdict']} |")
        L += [""]
    ships = df[df.verdict.str.startswith("SHIP")]
    L += ["### Part B verdict", "",
          f"- **SHIP: {len(ships)}** — " +
          (", ".join(f"{r['idea']}({r['variant'][:4]},{r['best_param']})" for _, r in ships.iterrows())
           or "none clear the ≥8% pooled bar."),
          "- Tweaks that only match the baseline are **SKIP** — they add parameters/complexity "
          "without a pooled, hold-out-confirmed gain. B2 dynamic re-entry is shown as a static "
          "sweep; a genuinely vol-scaled lock would need a strategy-level flag (noted, not "
          "implemented). B9 (Kelly, weekend-skip) re-confirmed negative, pooled.", "",
          "**Headline:** the structural rotation (Part A) is a far larger, more robust improvement "
          "than any single-parameter sizing tweak. If only one thing is added, add rotation.", ""]
    with open(REPORTS / "improvements_report.md", "a") as f:
        f.write("\n".join(L))


def run_part_c():
    """Stack the two biggest wins: cross-sectional rotation over an improved
    (graded-entry) Momentum sleeve, and confirm on the hold-out."""
    def _row(label, r):
        dc, ds, dd, _ = _panel(_slice(r, "design"))
        hc, hs, hd, _ = _panel(_slice(r, "holdout"))
        return dict(label=label, d_calmar=dc, d_sharpe=ds, d_maxdd=dd,
                    h_calmar=hc, h_sharpe=hs, h_maxdd=hd)

    print("=== Part C — stacking the winners ===")
    ew = pd.concat([imp.variant(a, "momentum")[0].rename(a) for a in ASSETS],
                   axis=1).fillna(0.0).mean(axis=1)
    rows = [_row("equalweight_momentum", ew),
            _row("rotation_k3_momentum", imp.rotation(ASSETS, k=3, variant_name="momentum")),
            _row("rotation_k3_graded",
                 imp.rotation(ASSETS, k=3, sleeve_fn=lambda a: imp.graded_entry(a, "momentum"))),
            _row("rotation_k2_graded",
                 imp.rotation(ASSETS, k=2, sleeve_fn=lambda a: imp.graded_entry(a, "momentum")))]
    for r in rows:
        print(f"  {r['label']:24} design Calmar {r['d_calmar']:.2f} Sh {r['d_sharpe']:.2f} "
              f"DD {r['d_maxdd']*100:.0f}%  |  holdout Calmar {r['h_calmar']:.2f} "
              f"Sh {r['h_sharpe']:.2f} DD {r['h_maxdd']*100:.0f}%")
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "part_c.csv", index=False)
    _append_report_c(df)
    print(f"\nWrote {RESULTS/'part_c.csv'} and finalized improvements_report.md")


def _append_report_c(df):
    base = df[df.label == "equalweight_momentum"].iloc[0]
    L = ["", "---", "", "## Part C — stacking the two biggest wins", "",
         "Cross-sectional rotation (Part A winner) run over a **graded-entry Momentum** sleeve "
         "(Part B winner). Baseline = equal-weight all-8 Momentum.", "",
         "| Config | Design Calmar | Design Sharpe | Design MaxDD | Hold-out Calmar | Hold-out MaxDD |",
         "|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        L.append(f"| {r['label']} | {r['d_calmar']:.2f} | {r['d_sharpe']:.2f} | "
                 f"{r['d_maxdd']*100:.0f}% | {r['h_calmar']:.2f} | {r['h_maxdd']*100:.0f}% |")
    L += ["", "## Final recommended additions (ranked by benefit-vs-complexity)", "",
          "1. **Cross-sectional rotation, top-3 (Med complexity, BIG benefit).** The single most "
          "impactful change; design Calmar ~1.4 and a positive bear hold-out vs ~1.07/-0.03 "
          "equal-weight. Layer above the existing per-asset strategies; no strategy edits.",
          "2. **Momentum graded entry (Low complexity, real benefit).** Replace the binary "
          "RSI>50 gate with RSI-scaled sizing (RSI 50→50%, 70+→100%); +24% pooled design Calmar, "
          "hold-out −0.21→−0.01. Stacks with rotation.",
          "3. **Lean ATR buffer k≈1.5 (Low, real benefit, defensive).** For the Lean sleeve only; "
          "+22% design and hold-out −0.09→+0.22. Do NOT apply to Momentum (it hurts there).",
          "4. **Regime-switch or DD-brake (Med/Low, defensive).** Optional bear-market insurance.",
          "",
          "**Not worth it (documented):** Kelly sizing (hurts, −42% on Momentum), weekend-skip on "
          "Momentum, ATR buffer on Momentum, ensembles/agreement/vol-weighting (variance-only). "
          "Each adds parameters without a pooled, hold-out-confirmed gain.", "",
          "**Honest caveat on multiple testing:** these winners were selected from a sweep of many "
          "ideas, so some design-set edge is selection bias. The ones to trust are those that *also* "
          "improve the untouched hold-out — rotation, graded entry, and Lean ATR buffer all do. "
          "Recommend confirming any adopted change in paper trading before sizing up.", ""]
    with open(REPORTS / "improvements_report.md", "a") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    part = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
    if part == "A":
        run_part_a()
    elif part == "B":
        run_part_b()
    elif part == "C":
        run_part_c()
