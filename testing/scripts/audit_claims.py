"""Audit the claims the reports make, looking for the ways each could be wrong.

Every number in this project comes from one asset over one window, with defaults
that were chosen by someone who had already seen that window. Nothing here is
out of sample in the sense that matters. This script checks whether the claims
survive that, by asking of each one the question that would sink it:

  1. BASE RATES. Bitcoin rose 48%/yr over the sample, so forward returns are
     positive almost everywhere. "Positive after the condition" is only evidence
     if it beats the unconditional average, and "a drawdown followed every
     blow-off exit" is only evidence if 60-day windows without a drawdown exist.

  2. MULTIPLE TESTING. Six tests were run on blow-off (two measures x three
     horizons). One of them came out significant. That is roughly what chance
     delivers, and the reports currently lean on it.

  3. SINGLE-PATH STATISTICS. MaxDD is one number from one history. A 2pp change
     in it is not obviously distinguishable from noise, and the ablation's own
     interval says whether it is.

Output: testing/data/audit_BTC.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "testing", ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
ES = json.loads((ROOT / "testing" / "data" / "event_study_BTC.json").read_text(encoding="utf-8"))
AB = json.loads((ROOT / "testing" / "data" / "ablation_BTC.json").read_text(encoding="utf-8"))
EX = json.loads((ROOT / "testing" / "data" / "exit_rules_BTC.json").read_text(encoding="utf-8"))
OUT = ROOT / "testing" / "data" / "audit_BTC.json"


def fwd_ret(c, h):
    o = np.full(len(c), np.nan); o[:-h] = (c[h:] / c[:-h] - 1) * 100; return o


def fwd_dd(c, h):
    o = np.full(len(c), np.nan)
    for t in range(len(c) - h):
        p = c[t:t + h + 1]
        o[t] = (p / np.maximum.accumulate(p) - 1).min() * 100
    return o


def main():
    raw = pd.read_parquet(SRC)
    cfg = engine.make_config("lean")
    df = trim_warmup(engine.strategy_module("lean")
                     .run_strategy(raw, btc_daily=None, config=cfg).df)
    close = raw["close"].reindex(df.index).to_numpy(float)
    out = {"from": str(df.index[0].date()), "to": str(df.index[-1].date()),
           "n_days": int(len(df))}

    # ── 1. what does an average day look like? ──────────────────────────────
    print("BAZNE STOPNJE — kaj dobi cisto navaden dan, brez vsakega pravila")
    base = {}
    for h in (5, 20, 60):
        r = fwd_ret(close, h); r = r[np.isfinite(r)]
        d = fwd_dd(close, h); d = d[np.isfinite(d)]
        base[str(h)] = {"mean_ret": round(float(r.mean()), 2),
                        "median_ret": round(float(np.median(r)), 2),
                        "share_positive": round(float((r > 0).mean() * 100), 1),
                        "mean_dd": round(float(d.mean()), 2),
                        "median_dd": round(float(np.median(d)), 2)}
        print(f"  {h:>3}d  povprecen donos {r.mean():+6.2f} % · pozitiven na "
              f"{(r > 0).mean()*100:.0f} % dni · povprecen vmesni padec {d.mean():.1f} %")
    out["base_rates"] = base

    # ── 2. the blow-off drawdown claim against its base rate ────────────────
    d60 = fwd_dd(close, 60); d60 = d60[np.isfinite(d60)]
    thr = 13.0
    share = float((d60 <= -thr).mean() * 100)
    print(f"\nTRDITEV: 'po vsakem od 8 izstopov je sledil padec 13-28 %'")
    print(f"  delez VSEH 60-dnevnih oken s padcem >= {thr:.0f} %: {share:.1f} %")
    print(f"  verjetnost, da 8 nakljucnih dni vseh 8 preseze prag: "
          f"{(share/100)**8*100:.1f} %")
    out["dd_base_rate"] = {"threshold_pct": thr,
                           "share_of_all_windows": round(share, 1),
                           "p_all_eight_by_chance": round((share / 100) ** 8, 4)}

    # median dd after blow-off vs the unconditional median
    bo_dd = [r["dd60"] for r in EX["blowoff_exits"] if r["dd60"] is not None]
    print(f"  mediana padca po sprozitvi {np.median(bo_dd):.1f} % proti "
          f"mediani vseh oken {np.median(d60):.1f} %")
    out["dd_base_rate"]["median_after_blowoff"] = round(float(np.median(bo_dd)), 1)
    out["dd_base_rate"]["median_all_windows"] = round(float(np.median(d60)), 1)

    # ── 3. multiple testing on the blow-off battery ─────────────────────────
    bx = EX["blowoff_vs_extended"]
    tests, sig = [], []
    for meas in ("donos", "maxdd"):
        for h in ("5", "20", "60"):
            v = bx["m"][meas][h]
            if v and not v.get("too_few"):
                tests.append(f"{meas}/{h}d")
                if v["sig"]:
                    sig.append(f"{meas}/{h}d")
    n, k = len(tests), len(sig)
    p_any = 1 - 0.95 ** n
    print(f"\nVECKRATNO TESTIRANJE pri blow-offu")
    print(f"  opravljenih testov: {n} · znacilnih: {k} ({', '.join(sig) or '-'})")
    print(f"  verjetnost vsaj enega znacilnega po nakljucju pri {n} testih: {p_any*100:.0f} %")
    print(f"  Bonferronijev prag namesto 0,05: {0.05/n:.4f}")
    out["multiple_testing_blowoff"] = {"n_tests": n, "n_significant": k,
                                       "significant": sig,
                                       "p_at_least_one_by_chance": round(p_any, 3),
                                       "bonferroni_alpha": round(0.05 / n, 4)}

    # ── 4. is the MaxDD gain from blow-off distinguishable from noise? ──────
    ab = {a["name"]: a for a in AB["ablations"]}["brez_blowoff"]
    print(f"\nABLACIJA blow-offa — ali je 2 o. t. MaxDD sploh locljivo od suma")
    print(f"  dSortino {ab['d_sortino']:+.3f}  CI [{ab['ci_d_sortino'][0]:+.2f}, "
          f"{ab['ci_d_sortino'][1]:+.2f}]  {'znacilno' if ab['sig'] else 'NI znacilno'}")
    print(f"  dMaxDD   {ab['d_maxdd']:+.1f}    CI [{ab['ci_d_maxdd'][0]:+.1f}, "
          f"{ab['ci_d_maxdd'][1]:+.1f}]  {'znacilno' if ab['sig_maxdd'] else 'NI znacilno'}")
    out["blowoff_ablation"] = {k: ab[k] for k in
                               ("d_sortino", "ci_d_sortino", "sig",
                                "d_maxdd", "ci_d_maxdd", "sig_maxdd")}

    # ── 5. how many entry-condition results survive the base rate? ──────────
    print(f"\nVSTOPNI POGOJI proti bazni stopnji")
    rows = []
    for c in ES["conditions"]:
        if c["side"] != "vstop":
            continue
        r = {"key": c["key"], "h": {}}
        for h in ("5", "20", "60"):
            v = c["m"]["donos"][h]
            if not v:
                continue
            r["h"][h] = {"mean_true": v["mean_true"],
                         "base": base[h]["mean_ret"],
                         "vs_base": round(v["mean_true"] - base[h]["mean_ret"], 2),
                         "sig": v["sig"]}
        rows.append(r)
        s20 = r["h"].get("20", {})
        print(f"  {c['key']:22} 20d ob pogoju {s20.get('mean_true',0):+6.2f} % · "
              f"navaden dan {s20.get('base',0):+6.2f} % · nad bazo "
              f"{s20.get('vs_base',0):+6.2f} o. t.")
    out["entry_vs_base"] = rows
    n_sig = sum(1 for c in ES["conditions"] if c["side"] == "vstop"
                for h in ("5", "20", "60")
                if (v := c["m"]["donos"][h]) and v["sig"])
    n_all = sum(1 for c in ES["conditions"] if c["side"] == "vstop"
                for h in ("5", "20", "60") if c["m"]["donos"][h])
    print(f"  -> znacilnih {n_sig} od {n_all} meritev; pri {n_all} testih bi jih po "
          f"nakljucju pricakovali {n_all*0.05:.1f}")
    out["entry_significance"] = {"n_tests": n_all, "n_significant": n_sig,
                                 "expected_by_chance": round(n_all * 0.05, 1)}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
