"""Macro safeguards, second pass: from 2020, with the signals the literature prefers.

Three things change from macro_gates.py.

WINDOW. 2020-01-01, so March 2020 is inside it. That is the only genuine credit
event in crypto's history and the first pass excluded it by construction, which
made the whole exercise unable to see the thing it was testing for.

SIGNALS. Two are replaced by better-founded versions.
  - VIX term structure (VIX / VIX3M) instead of the VIX level. Backwardation —
    spot fear above three-month fear — is the shape that shows up in real
    crises. It fires on 7.2 % of days but on 34 of the 36 days of the March 2020
    crash. And its threshold is the shape itself, so alone among everything here
    it has no parameter to tune.
  - HY against IG (HYG/LQD) alongside HY against treasuries. Both legs are
    corporate, so the rate move largely cancels and what is left is closer to
    default compensation alone.

TEST. The overlay only sees days the strategy holds — 36 % of the sample. A
predictive regression sees all of them, so it answers the prior question with
far more power: does the signal forecast BTC returns at all? If it does not, no
overlay built on it can work, and that is worth knowing before reading any
Sortino.

Honest note on multiplicity: these signals were chosen after seeing the first
pass fail, which is a second look at the same data. This file does NOT compute
PBO — an earlier version of this paragraph claimed it did, which was false. The
figure spanning both rounds is in macro_audit.py, and it is 0.767 on BTC.

    python testing/scripts/macro_v2.py
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
import statsmodels.api as sm

from shared.costs import net_returns
from shared.warmup import trim_warmup
from testing.scripts import engine
from testing.scripts.macro_data import load as load_macro

np.seterr(all="ignore")

FEE, PPY, MA = 0.30, 365, 200   # FEE is a PERCENT per side
START = "2020-01-01"
HORIZONS = (1, 5, 20)
NBOOT, BLOCK, N_SHIFT = 4000, 20, 300
OUT = ROOT / "testing" / "data" / "macro_v2.json"
rng = np.random.default_rng(20260813)

CRISES = [("marec 2020", "2020-02-20", "2020-04-10"),
          ("medved 2022", "2022-01-01", "2022-12-31"),
          ("FTX", "2022-11-01", "2022-12-31")]


def sortino(r):
    d = r[r < 0]
    return float(r.mean() / d.std() * np.sqrt(PPY)) if len(d) and d.std() else np.nan


def maxdd(r):
    eq = np.cumprod(1 + r)
    return float((eq / np.maximum.accumulate(eq) - 1).min() * 100)


def risk_off(macro: pd.DataFrame, index) -> dict:
    """True = risk is OFF, i.e. the safeguard wants you out."""
    def vs_ma(col, above_is_bad=True):
        s = macro[col]
        ma = s.rolling(MA, min_periods=MA).mean()
        return (s > ma) if above_is_bad else (s < ma)

    raw = {
        "VIX ts": macro["vix_ts"] > 1.0,          # no parameter at all
        "kredit HY/IG": vs_ma("credit_hy_ig", above_is_bad=False),
        "kredit HY/UST": vs_ma("credit", above_is_bad=False),
        "DXY": vs_ma("dxy"),
        "MOVE": vs_ma("move"),
    }
    return {k: v.reindex(index).ffill().fillna(False).astype(bool)
            for k, v in raw.items()}


def predictive(ret: pd.Series, flag: pd.Series, h: int):
    """Forward h-day return on the risk-off flag, Newey-West at lag h.

    Overlapping windows make plain OLS errors far too small; the HAC correction
    is what keeps the t-statistic honest.
    """
    fwd = ret.shift(-1).rolling(h).sum().shift(-(h - 1))
    d = pd.concat([fwd.rename("y"), flag.astype(float).rename("x")], axis=1).dropna()
    if len(d) < 100 or d["x"].nunique() < 2:
        return None
    m = sm.OLS(d["y"], sm.add_constant(d["x"])).fit(
        cov_type="HAC", cov_kwds={"maxlags": h})
    return {"beta": float(m.params.iloc[1]) * 100, "t": float(m.tvalues.iloc[1]),
            "p": float(m.pvalues.iloc[1]), "n": int(len(d))}


def build(raw, block, mode="vstop+izstop"):
    """`block` True = stay out."""
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    b = block.reindex(df.index).ffill().fillna(False).astype(bool)
    df["bull_condition"] = (df["bull_condition"] & ~b).fillna(False)
    if mode == "vstop+izstop":
        df["below_tl"] = (df["below_tl"] | b).fillna(False)
        df["trend_break"] = df["below_tl"]
    st = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos[pos.index >= START]


def boot_ci(a, b):
    n = len(a)
    kb = int(np.ceil(n / BLOCK))
    ds = []
    for lo in range(0, NBOOT, 500):
        m = min(500, NBOOT - lo)
        s = rng.integers(0, n, size=(m, kb))
        ii = (s[:, :, None] + np.arange(BLOCK)[None, None, :]
              ).reshape(m, kb * BLOCK)[:, :n] % n
        ds.append(np.array([sortino(a[i]) - sortino(b[i]) for i in ii]))
    d = np.concatenate(ds)
    d = d[np.isfinite(d)]
    return tuple(round(float(x), 3) for x in np.percentile(d, [2.5, 97.5]))


def main() -> int:
    macro = load_macro()
    out = {"start": START}

    for sym, f in (("BTC", "BTC_binance_warmup.parquet"),
                   ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / f)
        ret = raw["close"].pct_change().fillna(0.0)
        flags = risk_off(macro, raw.index)
        base = build(raw, pd.Series(False, index=raw.index))
        idx = base.index
        base_r = net_returns(base, ret, FEE).to_numpy(float)
        ret_w = ret.reindex(idx)

        print(f"\n{'=' * 100}\n{sym}   {idx[0].date()} -> {idx[-1].date()}   "
              f"{len(idx)} dni\n{'=' * 100}")

        # ── 1. does the signal predict anything at all ──────────────────────
        print("\n  NAPOVEDNA MOC  (donos BTC naprej ~ signal, Newey-West)")
        print(f"  {'signal':<16}{'% dni':>7}" +
              "".join(f"{'b'+str(h)+'d':>9}{'t':>7}" for h in HORIZONS))
        pred = {}
        for name, fl in flags.items():
            f_w = fl.reindex(idx)
            cells, row = [], {}
            for h in HORIZONS:
                r = predictive(ret_w, f_w, h)
                row[h] = r
                cells.append(f"{r['beta']:>8.2f}%{r['t']:>7.2f}" if r else f"{'—':>16}")
            pred[name] = row
            star = "  <-- p<0.05" if any(
                row[h] and row[h]["p"] < 0.05 for h in HORIZONS) else ""
            print(f"  {name:<16}{f_w.mean()*100:>6.1f}%" + "".join(cells) + star)

        # ── 2. what it does inside the crises ───────────────────────────────
        print("\n  V KRIZAH  (delez dni, ko je signal vklopljen)")
        print(f"  {'signal':<16}" + "".join(f"{c[0]:>14}" for c in CRISES))
        for name, fl in flags.items():
            cells = []
            for _, s, e in CRISES:
                w = fl.reindex(idx)[(idx >= s) & (idx <= e)]
                cells.append(f"{w.mean()*100:>13.0f}%" if len(w) else f"{'—':>14}")
            print(f"  {name:<16}" + "".join(cells))

        # ── 3. the overlay ─────────────────────────────────────────────────
        print(f"\n  PREKRIVANJE  (vstop+izstop, provizija 0,30 %/stran)")
        print(f"  {'celica':<16}{'Sortino':>9}{'CAGR':>8}{'MaxDD':>9}{'konec':>8}"
              f"{'izpost':>8}{'posl':>6}{'dSort':>8}   95 % CI")
        eqb = float(np.cumprod(1 + base_r)[-1])
        print(f"  {'izhodisce':<16}{sortino(base_r):>9.3f}"
              f"{(eqb**(PPY/len(base_r))-1)*100:>7.1f}%{maxdd(base_r):>8.1f}%"
              f"{eqb:>7.2f}x{base.mean()*100:>7.1f}%"
              f"{int((np.diff(base.to_numpy(),prepend=base.iloc[0])>0).sum()):>6d}")
        rows = {}
        cells = list(flags) + ["katerikoli od 2"]
        for name in cells:
            blk = (flags["VIX ts"] | flags["kredit HY/IG"]) if name.startswith("kateri") \
                else flags[name]
            pos = build(raw, blk)
            r = net_returns(pos, ret, FEE).to_numpy(float)
            eq = float(np.cumprod(1 + r)[-1])
            ci = boot_ci(r, base_r)
            rows[name] = {"sortino": round(sortino(r), 3),
                          "cagr": round((eq**(PPY/len(r))-1)*100, 1),
                          "maxdd": round(maxdd(r), 1), "final": round(eq, 2),
                          "exposure": round(float(pos.mean()*100), 1),
                          "trades": int((np.diff(pos.to_numpy(), prepend=pos.iloc[0]) > 0).sum()),
                          "delta": round(sortino(r) - sortino(base_r), 3), "ci": ci}
            m = rows[name]
            excl = "  IZKLJUCI 0" if (ci[0] > 0 or ci[1] < 0) else ""
            print(f"  {name:<16}{m['sortino']:>9.3f}{m['cagr']:>7.1f}%"
                  f"{m['maxdd']:>8.1f}%{m['final']:>7.2f}x{m['exposure']:>7.1f}%"
                  f"{m['trades']:>6d}{m['delta']:>+8.3f}   "
                  f"[{ci[0]:+.3f}, {ci[1]:+.3f}]{excl}")

        # ── 4. exposure-matched drawdown + circular shift ───────────────────
        print(f"\n  JE TO INFORMACIJA ALI LE MANJ TRGA?")
        print(f"  {'celica':<16}{'MaxDD':>9}{'izhod. @ isti izpost.':>23}"
              f"{'razlika':>9}{'placebo %':>11}")
        for name in cells:
            blk = (flags["VIX ts"] | flags["kredit HY/IG"]) if name.startswith("kateri") \
                else flags[name]
            pos = build(raw, blk)
            r = net_returns(pos, ret, FEE).to_numpy(float)
            dd, expo = maxdd(r), float(pos.mean())
            scaled = base * (expo / float(base.mean()))
            dds = maxdd(net_returns(scaled, ret, FEE).to_numpy(float))
            g = blk.reindex(raw.index).fillna(False).to_numpy(bool)
            sh = []
            for k in rng.integers(1, len(g), size=N_SHIFT):
                p = build(raw, pd.Series(np.roll(g, int(k)), index=raw.index))
                sh.append(maxdd(net_returns(p, ret, FEE).to_numpy(float)))
            pct = float((np.array(sh) < dd).mean() * 100)
            rows[name].update({"maxdd_matched": round(dds, 1),
                               "edge": round(dd - dds, 1), "placebo_pct": round(pct, 1)})
            print(f"  {name:<16}{dd:>8.1f}%{dds:>22.1f}%{dd-dds:>+9.1f}{pct:>10.1f}%")

        out[sym] = {"pred": pred, "rows": rows}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8")
    print(f"\nrazlika > 0: filter je boljsi od izhodisca pri isti izpostavljenosti")
    print(f"placebo < 95 %: zavrten signal doseze isto\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
