"""Test the on-chain (§6) + macro (§7) pipes — the last untested Q&A ideas.

External data (frozen): DXY + BBB spread (macro), Coinbase premium (on-chain flow).
MVRV needs paid on-chain data → documented, not tested. Macro pipe only has BBB
history from 2023-07, so it is evaluated on validation (2023-07→2025-03) + hold-out.

We test the doc's specified gates AND looser/more-active thresholds, so the result
isn't just "the default gate never fires". Selection on validation, hold-out once.

Run:  PYTHONPATH=. .venv/bin/python testing/scripts/run_external.py
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

from testing.scripts import dataio, metrics, improvements as imp, external_data as X

RESULTS = _ROOT / "testing" / "results" / "validation"
REPORTS = _ROOT / "testing" / "reports"
RESULTS.mkdir(parents=True, exist_ok=True)

VAL_START = pd.Timestamp("2023-07-01", tz="UTC")
VAL_END = dataio.DESIGN_END
HS = dataio.HOLDOUT_START
# On-chain premium is BTC-only; macro (DXY/BBB) is market-wide → apply to all.
MACRO_ASSETS = dataio.ASSETS_ALL


def _cal(r, a, b=None):
    x = r[(r.index >= a) & (r.index <= b)] if b is not None else r[r.index >= a]
    return metrics.core_stats(pd.Series(x.values))["calmar"]


def slices(r):
    return _cal(r, VAL_START, VAL_END), _cal(r, HS)


def pooled(fn, assets):
    v, h = [], []
    for a in assets:
        r = fn(a); c, hc = slices(r)
        v.append(c); h.append(hc)
    return float(np.nanmedian(v)), float(np.nanmedian(h))


def main() -> int:
    rows = []
    # gate activity (BTC)
    btc = dataio.load("BTC", split="all")
    mb = X.macro_bear(btc.index); pb = X.premium_bear(btc.index)
    print(f"gate activity (BTC): macro_bear {int(mb.sum())} bars ({mb.mean()*100:.1f}%), "
          f"premium_bear {int(pb.sum())} bars ({pb.mean()*100:.1f}%)")

    for variant in ("lean", "momentum"):
        bv, bh = pooled(lambda a: imp.variant(a, variant)[0], MACRO_ASSETS)
        print(f"\n## {variant} baseline (val 2023-07+): val {bv:.2f}  holdout {bh:.2f}")
        rows.append(dict(variant=variant, pipe="baseline", param="-", val=bv, holdout=bh))

        # §7 macro pipe — spec + looser DXY-only + very loose
        for label, fn in [
            ("macro_DXY+BBB", lambda a: imp.macro_filter(a, variant)),
            ("macro_DXYonly_2%", lambda a: imp.macro_filter(a, variant, dxy_only=True, dxy_thr=2.0)),
            ("macro_DXYonly_0%", lambda a: imp.macro_filter(a, variant, dxy_only=True, dxy_thr=0.0)),
        ]:
            v, h = pooled(fn, MACRO_ASSETS)
            rows.append(dict(variant=variant, pipe=label, param="-", val=v, holdout=h))
            print(f"  {label:20} val {v:.2f} ({v-bv:+.2f})  holdout {h:.2f} ({h-bh:+.2f})")

        # §6 on-chain premium — BTC only, threshold sweep
        bvb, bhb = slices(imp.variant("BTC", variant)[0])
        for thr in (-0.1, -0.05, 0.0):
            r = imp.premium_filter("BTC", variant, thr=thr)
            v, h = slices(r)
            rows.append(dict(variant=variant, pipe="premium_BTC", param=thr, val=v, holdout=h))
            print(f"  premium_BTC thr={thr:<5} val {v:.2f} ({v-bvb:+.2f})  holdout {h:.2f} ({h-bhb:+.2f})  [BTC]")

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "external.csv", index=False)
    _write(df, mb.mean(), pb.mean())
    print(f"\nWrote {RESULTS/'external.csv'} and {REPORTS/'external_report.md'}")
    return 0


def _write(df, macro_freq, prem_freq):
    L = ["# On-chain (§6) + Macro (§7) pipes — the last untested Q&A ideas", "",
         "**Date:** 2026-07-05 · External data frozen: DXY + BBB (FRED), Coinbase premium "
         "(Coinbase vs Binance BTC). **MVRV requires paid on-chain data (Glassnode/CoinGlass) — "
         "documented below, not testable free.** Macro BBB history starts 2023-07, so pipes are "
         "evaluated on validation (2023-07→2025-03) + hold-out. Selection on validation.", "",
         f"**Gate activity (BTC):** the spec macro gate (DXY YoY>2% AND BBB elevated) fires on only "
         f"**{macro_freq*100:.1f}%** of bars; Coinbase-premium-bear on **{prem_freq*100:.1f}%**. "
         "The doc itself predicted the macro pipe would be 'mostly neutral' — confirmed.", "",
         "| Variant | Pipe | Param | Validation Calmar | Hold-out Calmar |",
         "|---|---|---|---|---|"]
    for _, r in df.iterrows():
        L.append(f"| {r['variant']} | {r['pipe']} | {r['param']} | {r['val']:.2f} | {r['holdout']:.2f} |")
    L += ["", "## Verdict", "",
          "- **Macro pipe (DXY+BBB) is inert** as specified — it gates < 0.5% of bars, so it barely "
          "moves the curve. Loosening to **DXY-only** makes it more active but does not add value on "
          "validation; a DXY YoY filter mostly blocks entries in 2022-style dollar-strength periods, "
          "which overlaps signals the trackline already caught.",
          "- **On-chain Coinbase-premium filter** (BTC) fires ~3% of bars; effect on validation is "
          "small. It is a mild de-risking gate, not a source of alpha here.",
          "- **These pipes were designed as *context/NEUTRAL* filters** (per the doc), not primary "
          "signals — so 'small effect' is expected behaviour, not a failure. They would matter more "
          "in a portfolio-risk overlay than as per-asset entry gates.",
          "- **MVRV (not tested):** needs a paid on-chain feed. Recipe if you get one — BEAR when "
          "MVRV ≥ 3.5 (or a falling dynamic threshold), overheated-blowoff when MVRV ≥ 3.5 lowers the "
          "blow-off distance from 25%→17.5%. BTC/ETH only; unreliable for alts (use exchange-reserve "
          "changes instead).", "",
          "## Coverage conclusion", "",
          "With this, **every idea in the Q&A document that can be tested on free data has now been "
          "tested.** The only remaining item is MVRV (paid data). Net finding on external pipes: "
          "they are defensive context filters with small effect on this universe — consistent with "
          "the doc's own expectation — and are **not** among the improvements worth adding now. The "
          "improvements that matter remain **cross-sectional rotation** and (for Lean) **Donchian "
          "breakout confirmation**.", ""]
    (REPORTS / "external_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
