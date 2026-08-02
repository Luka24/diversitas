"""How long a track record would we need before the Sharpe means anything?

Every test in this project comes back "cannot tell", and the reason is always the
same: 11 to 21 trades. This turns that complaint into a number. The Minimum Track
Record Length (Bailey & Lopez de Prado) asks how many observations are required
before an observed Sharpe can be distinguished from a benchmark at a given
confidence, given the skew and fat tails actually present in the returns:

    MinTRL = 1 + [1 - g3*SR + (g4-1)/4 * SR^2] * (Z_alpha / (SR - SR*))^2

with SR the per-period Sharpe, g3 skewness, g4 kurtosis, SR* the benchmark.

Two benchmarks are worth asking about. Against zero: is there any edge at all.
Against the buy-and-hold Sharpe: is the strategy worth running rather than simply
holding the asset -- which is the question that actually matters and needs far
more data, because the two are close.

Output: testing/data/mintrl_BTC.json
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

from shared.costs import net_returns
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

FEE, PPY = 0.30, 365
CONF = 0.95
SRC = ROOT / "testing" / "data" / "sources" / "BTC_binance_warmup.parquet"
OUT = ROOT / "testing" / "data" / "mintrl_BTC.json"


def norm_ppf(p: float) -> float:
    """Acklam's inverse normal CDF; accurate to ~1e-9, avoids a scipy dependency."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    lo = 0.02425
    if p < lo:
        q = np.sqrt(-2 * np.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > 1 - lo:
        q = np.sqrt(-2 * np.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5]) * q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def mintrl(x: np.ndarray, sr_bench: float) -> float | None:
    """Observations needed to reject SR <= sr_bench at CONF. None if never."""
    mu, sd = x.mean(), x.std(ddof=1)
    sr = mu / sd
    if sr <= sr_bench:
        return None
    g3 = float(((x - mu) ** 3).mean() / sd ** 3)
    g4 = float(((x - mu) ** 4).mean() / sd ** 4)
    z = norm_ppf(CONF)
    return float(1 + (1 - g3 * sr + (g4 - 1) / 4 * sr ** 2) * (z / (sr - sr_bench)) ** 2)


def main():
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    df = trim_warmup(engine.strategy_module("lean")
                     .run_strategy(raw, btc_daily=None, config=engine.make_config("lean")).df)
    pos = pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)

    out = {"confidence": CONF, "fee_per_side_pct": FEE, "windows": {}}
    for lab, a, b in (("zadnjih 5 let", "2021-07-01", "2026-06-30"),
                      ("celotno", str(df.index[0].date()), str(df.index[-1].date()))):
        win = df.index[(df.index >= a) & (df.index <= b)]
        x = net_returns(pos.reindex(win), ret.reindex(win), FEE).to_numpy(float)
        bh = ret.reindex(win).to_numpy(float)
        n = len(x)
        mu, sd = x.mean(), x.std(ddof=1)
        sr_d = mu / sd
        sr_bh_d = bh.mean() / bh.std(ddof=1)
        g3 = float(((x - mu) ** 3).mean() / sd ** 3)
        g4 = float(((x - mu) ** 4).mean() / sd ** 4)

        row = {"from": str(win[0].date()), "to": str(win[-1].date()), "n": n,
               "sharpe_annual": round(sr_d * np.sqrt(PPY), 3),
               "sharpe_bh_annual": round(sr_bh_d * np.sqrt(PPY), 3),
               "skew": round(g3, 2), "kurtosis": round(g4, 1), "targets": {}}
        print(f"\n{lab.upper()}  {win[0].date()} → {win[-1].date()}  ({n} dni = {n/365:.1f} let)")
        print(f"  letni Sharpe {sr_d*np.sqrt(PPY):.3f} · kupi-in-drži {sr_bh_d*np.sqrt(PPY):.3f} "
              f"· asimetrija {g3:+.2f} · sploščenost {g4:.1f}")
        for tag, bench in (("proti nič", 0.0), ("proti kupi-in-drži", sr_bh_d)):
            m = mintrl(x, bench)
            if m is None:
                row["targets"][tag] = None
                print(f"  {tag:20} Sharpe ni nad pragom — nobena dolžina ne zadostuje")
                continue
            row["targets"][tag] = {"days": round(m), "years": round(m / 365, 1),
                                   "enough": bool(n >= m),
                                   "missing_years": round(max(0.0, (m - n) / 365), 1)}
            v = row["targets"][tag]
            verdict = ("ZADOSTUJE" if v["enough"]
                       else f"manjka še {v['missing_years']} let")
            print(f"  {tag:20} potrebnih {v['days']:>8,} dni = {v['years']:>6.1f} let  ->  {verdict}")
        out["windows"][lab] = row

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return out


if __name__ == "__main__":
    main()
