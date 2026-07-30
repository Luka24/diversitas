"""Switch off every condition in turn and measure all four headline numbers.

The reports so far reported Sortino and MaxDD. That is not enough to defend a
removal in a meeting: Sortino punishes only downside deviation, so a rule can
look good there while costing plain return, and MaxDD is a single number from a
single path. Sharpe, CAGR and the final multiple are added, plus an equity curve
per candidate so the effect is visible rather than tabulated.

Entry filters cannot be switched off through the config -- they are hard-wired
into `bull_condition` -- so they are disabled by forcing their column to True and
recomposing that expression exactly as strategy.py does. If the recomposition
ever drifts from the shipped one, the baseline check at the top of main() fails
loudly instead of quietly measuring the wrong thing.

Output: testing/data/ablation_full_BTC.json
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

from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

FEE, PPY = 0.30, 365
NBOOT, BLOCK, SEED = 2000, 20, 20260801
SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
OUT = ROOT / "testing" / "data" / "ablation_full_BTC.json"

# The seven terms of bull_condition, in the order strategy.py ANDs them.
BULL_TERMS = ("above_tl", "above_ma_med", "track_rising_window", "dist_entry_ok",
              "regime_ok", "btc_filter_ok", "donchian_ok")

# name -> (entry filters to force True, config overrides, plain-language label)
CASES = {
    "izhodišče": ((), {}, "vse pravilo vklopljeno"),
    "brez vol-shocka": ((), {"vol_shock_mul": 999.0}, "vol-shock izklopljen"),
    "brez dist_entry_ok": (("dist_entry_ok",), {}, "odstranjen dvojnik above_tl"),
    "brez obojega": (("dist_entry_ok",), {"vol_shock_mul": 999.0},
                     "oba predlagana izbrisa skupaj"),
    "brez blow-offa": ((), {"blowoff_dist_pct": 9999.0}, "blow-off izklopljen"),
    "brez above_ma_med": (("above_ma_med",), {}, "50-dnevni filter izklopljen"),
    "brez track_rising": (("track_rising_window",), {}, "naklon trackline izklopljen"),
    "brez regime_ok": (("regime_ok",), {}, "200-dnevni zapornik izklopljen"),
    "brez above_tl": (("above_tl", "dist_entry_ok"), {}, "trackline kot vstop izklopljen"),
}


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def sharpe(r):
    sd = r.std(ddof=1) * np.sqrt(PPY)
    return float(r.mean() * PPY / sd) if sd > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def cagr(r):
    return float((float(np.prod(1.0 + r)) ** (PPY / len(r)) - 1.0) * 100.0)


def _blocks(rng, n, B, L):
    nb = int(np.ceil(n / L))
    st = rng.integers(0, n, size=(B, nb))
    return (st[:, :, None] + np.arange(L)[None, None, :]).reshape(B, nb * L)[:, :n] % n


def paired_ci(a, b, fn, rng):
    idx = _blocks(rng, len(a), NBOOT, BLOCK)
    d = np.array([fn(a[i]) - fn(b[i]) for i in idx])
    d = d[np.isfinite(d)]
    lo, hi = np.percentile(d, [2.5, 97.5])
    return round(float(lo), 3), round(float(hi), 3), bool(lo > 0 or hi < 0)


def run(raw, force=(), **kw):
    smod = engine.strategy_module("lean")
    cfg = engine.make_config("lean", **kw)
    df = smod.compute_features(raw, None, cfg)
    if force:
        for col in force:
            df[col] = True
        # recompose exactly as strategy.py does
        bull = pd.Series(True, index=df.index)
        for t in BULL_TERMS:
            bull &= df[t]
        df["bull_condition"] = bull.fillna(False)
        df["green_dot"] = df["bull_condition"]
    df = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)
    r = net_returns(pos, raw["close"].pct_change().fillna(0.0), FEE)
    return r.to_numpy(float), pos, df.index


def main():
    raw = pd.read_parquet(SRC)
    rng = np.random.default_rng(SEED)

    # sanity: the recomposition must reproduce the shipped path bit for bit
    a, _, _ = run(raw)
    b, _, _ = run(raw, force=("btc_filter_ok",))     # already all-True in Lean
    assert np.allclose(a, b), "sestavljanje bull_condition se ne ujema s strategy.py"

    base_r, base_pos, idx = run(raw)
    bench = raw["close"].pct_change().fillna(0.0).reindex(idx).to_numpy(float)
    out = {"from": str(idx[0].date()), "to": str(idx[-1].date()), "n": len(idx),
           "fee_per_side_pct": FEE, "nboot": NBOOT, "block": BLOCK,
           "index": [str(d.date()) for d in idx],
           "benchmark": {"equity": [round(float(v), 4)
                                    for v in np.cumprod(1.0 + bench)],
                         "maxdd": round(maxdd(bench), 1),
                         "cagr": round(cagr(bench), 1),
                         "sharpe": round(sharpe(bench), 3),
                         "sortino": round(sortino(bench), 3)},
           "cases": {}}

    print(f"{out['from']} → {out['to']}  ({out['n']} dni)  fee+slip {FEE} %/stran\n")
    print(f"{'primer':22} {'Sortino':>8} {'Sharpe':>8} {'CAGR':>8} {'MaxDD':>9} "
          f"{'konec':>7} {'poslov':>7} {'izpost.':>8}")

    for name, (force, kw, label) in CASES.items():
        r, pos, _ = run(raw, force=force, **kw)
        eq = np.cumprod(1.0 + r)
        row = {"label": label, "forced": list(force), "config": kw,
               "sortino": round(sortino(r), 3), "sharpe": round(sharpe(r), 3),
               "cagr": round(cagr(r), 1), "maxdd": round(maxdd(r), 1),
               "final": round(float(eq[-1]), 3),
               "expo": round(float(pos.mean() * 100), 1),
               "turnover": round(float(turnover(pos).sum()), 1),
               "trades": int((np.diff(pos.to_numpy(), prepend=pos.to_numpy()[0]) > 0).sum()),
               "equity": [round(float(v), 4) for v in eq]}
        if name != "izhodišče":
            for key, fn in (("sortino", sortino), ("sharpe", sharpe),
                            ("cagr", cagr), ("maxdd", maxdd)):
                lo, hi, sig = paired_ci(r, base_r, fn, rng)
                row[f"d_{key}"] = round(row[key] - out["cases"]["izhodišče"][key], 3)
                row[f"ci_{key}"] = [lo, hi]
                row[f"sig_{key}"] = sig
            row["identical"] = bool(np.allclose(r, base_r, atol=1e-12))
        out["cases"][name] = row
        mark = "  = IDENTIČNO" if row.get("identical") else ""
        print(f"{name:22} {row['sortino']:8.3f} {row['sharpe']:8.3f} {row['cagr']:7.1f} % "
              f"{row['maxdd']:8.1f} % {row['final']:7.2f} {row['trades']:7d} "
              f"{row['expo']:7.1f} %{mark}")

    print(f"\n{'kupi in drži':22} {out['benchmark']['sortino']:8.3f} "
          f"{out['benchmark']['sharpe']:8.3f} {out['benchmark']['cagr']:7.1f} % "
          f"{out['benchmark']['maxdd']:8.1f} %")

    print("\nRAZLIKE PROTI IZHODIŠČU (razpon iz parnega bločnega bootstrapa)")
    for name, row in out["cases"].items():
        if name == "izhodišče":
            continue
        print(f"\n  {name}")
        for key, unit in (("sortino", ""), ("sharpe", ""), ("cagr", " o. t."),
                          ("maxdd", " o. t.")):
            print(f"    Δ{key:8} {row[f'd_{key}']:+7.3f}{unit:7} "
                  f"razpon [{row[f'ci_{key}'][0]:+.2f}, {row[f'ci_{key}'][1]:+.2f}]"
                  f"{'   ZNAČILNO' if row[f'sig_{key}'] else ''}")

    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON -> {OUT}  ({OUT.stat().st_size/1024:.0f} kB)")
    return out


if __name__ == "__main__":
    main()
