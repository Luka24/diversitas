"""Test every entry and exit condition against its own premise.

The strategy has 17 trades. No claim can be established from 17 observations. But
every condition is either true or false on each of ~2400 days, so the question
"does this condition actually precede better outcomes" carries two orders of
magnitude more evidence than "does removing it change the backtest".

Three things this script is careful about, because each of them can flip a verdict:

1. OVERLAPPING WINDOWS. Consecutive 20-day forward returns share 19 of 20 days,
   so a naive t-test counts the same evidence twenty times. Every interval here
   comes from a circular block bootstrap; the naive interval is reported next to
   it purely to show how much it would have exaggerated.

2. THE RIGHT COMPARISON GROUP. `vol_shock` is gated on `below_tl` in the code, so
   it never fires on its own — it only accelerates an exit that `below_tl` was
   already going to make three bars later. Comparing its days against all other
   days measures `below_tl`, not `vol_shock`. It is compared against the other
   `below_tl` days instead.

3. RISK, NOT ONLY RETURN. The strategy's only surviving claim is about drawdown,
   so forward MaxDD and forward volatility are measured alongside forward return.

Output: JSON to testing/data/event_study_BTC.json, consumed by the report builder.
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

SYMBOL = "BTC"
HORIZONS = (5, 20, 60)
# Bootstrap block length must outlast the dependence it is meant to absorb. The
# forward return at horizon h is autocorrelated out to roughly h lags (measured:
# 0.73 at lag 20 for h=60), so a fixed 20-bar block is far too short at the long
# end and leaves the interval too narrow. Block length tracks the horizon.
def block_len(h: int) -> int:
    return max(20, h)


NBOOT = 2000
SEED = 20260729
MIN_GROUP = 30       # below this a comparison is not attempted at all

OUT = ROOT / "testing" / "data" / "event_study_BTC.json"

# key, side, plain-language label, comparison group ("all" or a gating column)
CONDITIONS = [
    ("above_tl",            "vstop",  "cena nad trackline + mrtvi pas", "all"),
    ("above_ma_med",        "vstop",  "cena nad 50-dnevnim povprečjem", "all"),
    ("track_rising_window", "vstop",  "trackline raste čez 10 barov",   "all"),
    ("regime_ok",           "vstop",  "200-dnevno povprečje ne blokira", "all"),
    ("bull_condition",      "vstop",  "vsi vstopni pogoji hkrati",      "all"),
    ("below_tl",            "izstop", "cena pod trackline − mrtvi pas", "all"),
    ("blowoff",             "izstop", "blow-off (daleč nad trackline in RSI > 80)", "all"),
    ("vol_shock",           "izstop", "vol-shock",                      "below_tl"),
]

# entry filters, for the conditional and incremental tests
ENTRY_FILTERS = ["above_tl", "above_ma_med", "track_rising_window",
                 "dist_entry_ok", "regime_ok"]


# ── forward outcome measures ────────────────────────────────────────────────
def forward_return(close: np.ndarray, h: int) -> np.ndarray:
    out = np.full(len(close), np.nan)
    out[:-h] = (close[h:] / close[:-h] - 1.0) * 100.0
    return out


def forward_maxdd(close: np.ndarray, h: int) -> np.ndarray:
    """Deepest drawdown inside the next h days, in percent (negative)."""
    n = len(close)
    out = np.full(n, np.nan)
    for t in range(n - h):
        path = close[t:t + h + 1]
        out[t] = (path / np.maximum.accumulate(path) - 1.0).min() * 100.0
    return out


def forward_vol(close: np.ndarray, h: int) -> np.ndarray:
    r = np.diff(np.log(close), prepend=np.nan)
    n = len(close)
    out = np.full(n, np.nan)
    for t in range(n - h):
        out[t] = np.nanstd(r[t + 1:t + h + 1]) * np.sqrt(365) * 100.0
    return out


MEASURES = {
    "donos":  ("nadaljnji donos (%)",        forward_return, +1),
    "maxdd":  ("najgloblji vmesni padec (%)", forward_maxdd,  -1),
    "vol":    ("nadaljnja volatilnost (%)",   forward_vol,    -1),
}


# ── inference ───────────────────────────────────────────────────────────────
def _block_index(rng, n: int, B: int, L: int) -> np.ndarray:
    """Circular block bootstrap indices, shape (B, n)."""
    nb = int(np.ceil(n / L))
    starts = rng.integers(0, n, size=(B, nb))
    idx = (starts[:, :, None] + np.arange(L)[None, None, :]) % n
    return idx.reshape(B, nb * L)[:, :n]


def compare(a: np.ndarray, b: np.ndarray, rng, h: int) -> dict | None:
    """mean(a) - mean(b) with a block-bootstrap interval and the naive one."""
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < MIN_GROUP or len(b) < MIN_GROUP:
        return None
    diff = float(a.mean() - b.mean())

    L = block_len(h)
    ia = _block_index(rng, len(a), NBOOT, L)
    ib = _block_index(rng, len(b), NBOOT, L)
    draws = a[ia].mean(axis=1) - b[ib].mean(axis=1)
    lo, hi = np.percentile(draws, [2.5, 97.5])

    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return {
        "block": L,
        "n_true": int(len(a)), "n_false": int(len(b)),
        "mean_true": round(float(a.mean()), 2), "mean_false": round(float(b.mean()), 2),
        "diff": round(diff, 2),
        "ci": [round(float(lo), 2), round(float(hi), 2)],
        "ci_naive": [round(diff - 1.96 * se, 2), round(diff + 1.96 * se, 2)],
        "widen": round(float((hi - lo) / (2 * 1.96 * se)), 1) if se > 0 else None,
        "sig": bool(lo > 0 or hi < 0),
    }


def autocorr(x: np.ndarray, lags=(1, 5, 10, 20)) -> dict:
    s = pd.Series(x).dropna()
    return {str(k): round(float(s.autocorr(k)), 2) for k in lags}


# ── main ────────────────────────────────────────────────────────────────────
def main() -> dict:
    smod = engine.strategy_module("lean")
    cfg = engine.make_config("lean")
    raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance_warmup.parquet")
    df = trim_warmup(smod.run_strategy(raw, btc_daily=None, config=cfg).df)
    close = raw["close"].reindex(df.index).to_numpy(float)
    rng = np.random.default_rng(SEED)

    out: dict = {
        "symbol": SYMBOL,
        "source": "binance",
        "from": str(df.index[0].date()),
        "to": str(df.index[-1].date()),
        "n_days": int(len(df)),
        "block_rule": "max(20, horizont)", "nboot": NBOOT, "seed": SEED,
        "horizons": list(HORIZONS),
    }

    fwd = {m: {h: f(close, h) for h in HORIZONS} for m, (_, f, _) in MEASURES.items()}
    out["autocorr"] = {str(h): autocorr(fwd["donos"][h]) for h in HORIZONS}

    # ── 1. structural inventory: which terms of bull_condition actually bite ──
    inv = []
    for k in ENTRY_FILTERS + ["btc_filter_ok", "donchian_ok"]:
        if k not in df.columns:
            continue
        v = df[k].fillna(False).to_numpy().astype(bool)
        inv.append({"key": k, "share": round(float(v.mean() * 100), 1),
                    "constant": bool(v.all() or (~v).all())})
    # dist_entry_ok is above_tl by construction when min_dist_entry_pct == 0
    if {"dist_entry_ok", "above_tl"} <= set(df.columns):
        a = df["above_tl"].fillna(False).to_numpy()
        d = df["dist_entry_ok"].fillna(False).to_numpy()
        out["dist_entry_identical_to_above_tl"] = bool((a == d).all())
        out["dist_entry_disagreements"] = int((a != d).sum())
    out["inventory"] = inv

    # ── 2. the event study proper ───────────────────────────────────────────
    rows = []
    for key, side, label, gate in CONDITIONS:
        if key not in df.columns:
            continue
        c = df[key].fillna(False).to_numpy().astype(bool)
        mask = np.ones(len(c), bool)
        if gate != "all":
            mask = df[gate].fillna(False).to_numpy().astype(bool)
        row = {"key": key, "side": side, "label": label, "gate": gate,
               "n_fire": int(c.sum()), "share": round(float(c.mean() * 100), 1),
               "n_gate": int(mask.sum()), "m": {}}
        for mname in MEASURES:
            row["m"][mname] = {}
            for h in HORIZONS:
                f = fwd[mname][h]
                res = compare(f[mask & c], f[mask & ~c], rng, h)
                row["m"][mname][str(h)] = res
        rows.append(row)
    out["conditions"] = rows

    # ── 3. each entry filter, but only inside a market the regime already allows ─
    cond_rows = []
    reg = df["regime_ok"].fillna(False).to_numpy().astype(bool)
    for key in ENTRY_FILTERS:
        if key == "regime_ok" or key not in df.columns:
            continue
        c = df[key].fillna(False).to_numpy().astype(bool)
        r = {"key": key, "m": {}}
        for h in HORIZONS:
            f = fwd["donos"][h]
            r["m"][str(h)] = compare(f[reg & c], f[reg & ~c], rng, h)
        cond_rows.append(r)
    out["conditional_on_regime"] = cond_rows

    # ── 4. incremental: what does each filter block, and was it worth blocking? ─
    inc = []
    base = df["bull_condition"].fillna(False).to_numpy().astype(bool)
    for key in ENTRY_FILTERS:
        if key not in df.columns:
            continue
        others = np.ones(len(df), bool)
        for k2 in ENTRY_FILTERS:
            if k2 != key and k2 in df.columns:
                others &= df[k2].fillna(False).to_numpy().astype(bool)
        added = others & ~base          # days the filter is the sole blocker
        r = {"key": key, "n_added": int(added.sum()), "m": {}}
        if added.sum() >= MIN_GROUP:
            for h in HORIZONS:
                f = fwd["donos"][h]
                r["m"][str(h)] = compare(f[added], f[base], rng, h)
        inc.append(r)
    out["incremental"] = inc

    # ── 5. blow-off mechanism: does it actually fire near tops? ──────────────
    if "blowoff" in df.columns:
        b = df["blowoff"].fillna(False).to_numpy().astype(bool)
        f60 = fwd["donos"][60]
        ok = b & np.isfinite(f60)
        allok = np.isfinite(f60)
        pct = [float((f60[allok] < v).mean() * 100) for v in f60[ok]]
        out["blowoff_mechanism"] = {
            "n_fire": int(b.sum()),
            "n_with_forward": int(ok.sum()),
            "median_percentile_of_fwd60": round(float(np.median(pct)), 1) if pct else None,
            "share_in_worst_quartile": round(float(np.mean(np.array(pct) < 25) * 100), 1) if pct else None,
            "share_in_best_quartile": round(float(np.mean(np.array(pct) > 75) * 100), 1) if pct else None,
            "percentiles": [round(v, 1) for v in pct],
            "fwd60_at_fire": [round(float(v), 1) for v in f60[ok]],
            "fwd60_deciles": [round(float(v), 1) for v in np.percentile(f60[allok], np.arange(0, 101, 10))],
            "dates": [str(d.date()) for d in df.index[b]],
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    o = main()
    print(f"{o['symbol']} {o['from']} -> {o['to']}  {o['n_days']} dni  vir {o['source']}")
    print(f"dist_entry_ok == above_tl: {o.get('dist_entry_identical_to_above_tl')} "
          f"(neujemanj: {o.get('dist_entry_disagreements')})")
    print("\nkonstantni/mrtvi členi bull_condition:")
    for i in o["inventory"]:
        print(f"  {i['key']:22} velja {i['share']:5.1f} %  "
              f"{'KONSTANTEN' if i['constant'] else ''}")
    print("\nnadaljnji DONOS (o. t. razlike, 95 % CI iz bločnega bootstrapa):")
    for r in o["conditions"]:
        g = "" if r["gate"] == "all" else f"  [primerjano znotraj {r['gate']}]"
        print(f"\n  {r['key']} — {r['label']}{g}")
        print(f"    sproži se {r['n_fire']}× ({r['share']} % dni)")
        for h in o["horizons"]:
            v = r["m"]["donos"][str(h)]
            if v is None:
                print(f"    {h:>3}d  premalo opazovanj")
                continue
            print(f"    {h:>3}d  {v['diff']:+6.2f}  CI [{v['ci'][0]:+.2f}, {v['ci'][1]:+.2f}]"
                  f"   naivni CI [{v['ci_naive'][0]:+.2f}, {v['ci_naive'][1]:+.2f}] "
                  f"({v['widen']}× ožji){'  ZNAČILNO' if v['sig'] else ''}")
    print(f"\nJSON -> {OUT}")
