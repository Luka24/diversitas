"""Step 5 — should the dead band scale with volatility?

Pre-registered in `testing/nacrt_korak5.md` (dc702b1, amended c5534d6 and again
for power before this script existed). Thresholds and sub-periods come from that
document and are not to be edited to fit the output.

    A  fixed 3 % both sides                     control, today's engine
    E  3 % x (annual_vol / vol_avg50), BOTH     0 new parameters
    F  the same, ENTRY only; exit stays fixed   0 new parameters

Both ingredients already exist in the engine — `annual_vol` (20d) and
`vol_avg50` (SMA50 of it) survived step 3 because the dashboard draws them — so
the adaptive band introduces no window, no multiplier and no clamp. Both are
trailing, so the construction is causal, and the anchor holds: measured mean
buffer 3.05 %.

E and F are not variations on a theme, they pull opposite ways. The existing
sweep shows exposure RISING with band width (42.3 % -> 50.0 %), because a wider
band delays the exit more than it delays the entry. So in a volatile stretch E
exits later and holds MORE, while F only raises the entry hurdle and holds LESS.

Two things are known before running and are not news when they appear:
  * entry decisions differ on 40 bars, exits on 57 — not the hundreds the plan
    first claimed, so a confidence interval will not exclude zero;
  * an adaptive band is volatility scaling wearing a costume. Kim, Tse & Wald
    (JFM 2016) find that is where trend-following alpha mostly comes from, so
    §5.7's placebo — variant A, rules untouched, position scaled by
    vol_avg50/annual_vol — is a gate, not a footnote.

Output: testing/data/adaptive_buffer_BTC.json
"""
from __future__ import annotations

import hashlib
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

SYMBOL, FEE, PPY = "BTC", 0.30, 365
SEED, NBOOT, BLOCK, H = 20260805, 5000, 20, 20

SRC = ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance_warmup.parquet"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
OUT = ROOT / "testing" / "data" / f"adaptive_buffer_{SYMBOL}.json"

SUBPERIODS = [("I", "2019-03-09", "2021-01-31"), ("II", "2021-02-01", "2022-11-30"),
              ("III", "2022-12-01", "2024-09-30"), ("IV", "2024-10-01", "2026-07-29")]
VARIANTS = ("A", "E", "F")
LABEL = {"A": "fiksnih 3 % (danes)", "E": "prilagodljiv, obe strani",
         "F": "prilagodljiv, samo vstop"}
BULL_TERMS = ("above_tl", "track_rising_window", "regime_ok",
              "btc_filter_ok", "donchian_ok")


def build(raw: pd.DataFrame, cfg, variant: str) -> pd.DataFrame:
    """Features with the chosen band, then the untouched production state machine."""
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)

    # Guard: if this recomposition ever drifts from strategy.py, every number
    # below is measuring a different strategy than the one we ship.
    bull = pd.Series(True, index=df.index)
    for t in BULL_TERMS:
        bull &= df[t]
    bull = (bull & ~df["blowoff"]).fillna(False)
    assert np.array_equal(bull.to_numpy(),
                          df["bull_condition"].fillna(False).to_numpy()), \
        "sestavljanje bull_condition se ne ujema s strategy.py"

    if variant != "A":
        # NaN until vol_avg50 exists (~70 bars, all inside the warm-up that gets
        # trimmed). Filled with 1.0 so the band falls back to the fixed 3 % rather
        # than turning every comparison against NaN into a silent False — the trap
        # documented in engine.py.
        rel = (df["annual_vol"] / df["vol_avg50"]).replace([np.inf, -np.inf],
                                                           np.nan).fillna(1.0)
        band = cfg.track_buf_pct * rel / 100.0
        tl = df["trackline"]
        df["band_pct"] = band * 100.0
        df["above_tl"] = df["close"] > tl * (1.0 + band)
        if variant == "E":
            df["below_tl"] = df["close"] < tl * (1.0 - band)
        bull = pd.Series(True, index=df.index)
        for t in BULL_TERMS:
            bull &= df[t]
        df["bull_condition"] = (bull & ~df["blowoff"]).fillna(False)
        df["trend_break"] = df["below_tl"]
        df["green_dot"] = df["bull_condition"]
        df["red_dot"] = df["below_tl"]
    else:
        df["band_pct"] = float(cfg.track_buf_pct)

    return smod.run_state_machine(df, cfg)


def positions(raw: pd.DataFrame, variant: str):
    cfg = engine.make_config("lean")
    df = trim_warmup(build(raw, cfg, variant))
    pos = pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)
    return pos, df


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def capture(pos, bench):
    b = bench.reindex(pos.index).fillna(0.0).to_numpy()
    s = pos.to_numpy() * b
    up, dn = b > 0, b < 0
    return (round(float(s[up].sum() / b[up].sum() * 100), 1),
            round(float(s[dn].sum() / b[dn].sum() * 100), 1))


def metrics(pos, raw):
    ret = raw["close"].pct_change().fillna(0.0)
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1.0 + r)
    p = pos.to_numpy()
    u, d = capture(pos, ret)
    sd = r.std(ddof=1) * np.sqrt(PPY)
    return {"sortino": round(sortino(r), 3),
            "sharpe": round(float(r.mean() * PPY / sd), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 3),
            "exposure": round(float(p.mean() * 100), 1),
            "upside_capture": u, "downside_capture": d,
            "trades": int((np.diff(p, prepend=p[0]) > 0).sum()),
            "turnover": round(float(turnover(pos).sum()), 1)}


def digest(pos):
    h = hashlib.sha256()
    h.update(np.asarray(pos.index.view("int64")).tobytes())
    h.update(np.ascontiguousarray(pos.to_numpy()).tobytes())
    return h.hexdigest()


def block_idx(rng, n, nb):
    k = int(np.ceil(n / BLOCK))
    st = rng.integers(0, n, size=(nb, k))
    return (st[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(nb, k * BLOCK)[:, :n] % n


MIN_BLOCKS = 3


def mean_ci(x, rng):
    """Block bootstrap on the mean, or None when the sample cannot carry one.

    Forward returns overlap for H bars, so the block has to be H long — which
    means a sample shorter than a few blocks has no resampling freedom left. At
    n = 14 with BLOCK = 20 the index is (start + arange(20)) % 14, i.e. the whole
    series in some rotation, so every draw returns the same mean and the interval
    collapses to a point. That looks like an extremely tight CI and is in fact
    no CI at all. Refusing to print one is the honest output.
    """
    if len(x) < MIN_BLOCKS * BLOCK:
        return None
    idx = block_idx(rng, len(x), 2000)
    mu = x[idx].mean(axis=1)
    return [round(float(np.percentile(mu, 2.5)), 2),
            round(float(np.percentile(mu, 97.5)), 2)]


def n_episodes(mask, index) -> int:
    """Contiguous runs, which is the honest sample size for clustered days."""
    dts = index[mask]
    if len(dts) == 0:
        return 0
    return 1 + int((dts.to_series().diff().dt.days.fillna(0) > 1).sum())


def paired_ci(a, b, rng):
    n = len(a)
    out = []
    for lo in range(0, NBOOT, 500):
        idx = block_idx(rng, n, min(500, NBOOT - lo))
        out.append(np.array([sortino(a[i]) - sortino(b[i]) for i in idx]))
    d = np.concatenate(out)
    d = d[np.isfinite(d)]
    return {"delta": round(float(sortino(a) - sortino(b)), 3),
            "ci_lo": round(float(np.percentile(d, 2.5)), 3),
            "ci_hi": round(float(np.percentile(d, 97.5)), 3),
            "excludes_zero": bool(np.percentile(d, 2.5) > 0
                                  or np.percentile(d, 97.5) < 0)}


def main() -> int:
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    rng = np.random.default_rng(SEED)
    out: dict = {"symbol": SYMBOL, "fee_per_side_pct": FEE, "seed": SEED,
                 "preregistered": "testing/nacrt_korak5.md"}

    print("KONTROLA — različica A proti zamrznjeni referenci")
    pos = {v: positions(raw, v) for v in VARIANTS}
    posA, dfA = pos["A"]
    ref = pd.read_parquet(REF)["position"]
    same = posA.index.equals(ref.index) and np.allclose(posA.to_numpy(),
                                                        ref.to_numpy(), atol=1e-12)
    print(f"  serija enaka: {same}   SHA256 {digest(posA)[:32]}…")
    if not same:
        print("  Harness se moti na kontroli. USTAVLJAM.")
        return 2
    out["control_matches_reference"] = True

    # ── realised band ─────────────────────────────────────────────────────
    bandE = pos["E"][1]["band_pct"]
    q = {f"p{p}": round(float(np.percentile(bandE, p)), 2)
         for p in (0, 1, 5, 25, 50, 75, 95, 99, 100)}
    by_year = bandE.groupby(bandE.index.year).mean().round(2).to_dict()
    out["band"] = {"pct": q, "mean": round(float(bandE.mean()), 2),
                   "by_year": {str(k): v for k, v in by_year.items()},
                   "days_below_1pct": int((bandE < 1).sum()),
                   "days_above_10pct": int((bandE > 10).sum())}
    print(f"\nPAS — povprečje {bandE.mean():.2f} %  (sidro 3 %)")
    print("  po letih: " + "  ".join(f"{y}:{v:.1f}" for y, v in by_year.items()))
    print(f"  dni pod 1 %: {out['band']['days_below_1pct']}   "
          f"nad 10 %: {out['band']['days_above_10pct']}")

    # ── primary: per-day event study ──────────────────────────────────────
    print("\nDNEVNA ŠTUDIJA — donos BTC v naslednjih 20 dneh")
    cl = dfA["close"].to_numpy(float)
    n = len(dfA)
    fwd = np.full(n, np.nan)
    fwd[:n - H] = (cl[H:] / cl[:n - H] - 1) * 100
    ok = np.isfinite(fwd)
    base = fwd[ok].mean()
    print(f"  izhodišče, vsi dnevi ({int(ok.sum())}): {base:+.2f} %")
    ev = {"baseline_all_days": round(float(base), 2), "n_all": int(ok.sum())}
    for v in ("E", "F"):
        aA = dfA["above_tl"].fillna(False).to_numpy()
        aV = pos[v][1]["above_tl"].fillna(False).to_numpy()
        for tag, m in ((f"{v}: vstop odprt, A zaprt", aV & ~aA),
                       (f"{v}: A odprt, {v} zaprt", aA & ~aV)):
            x = fwd[m & ok]
            ci = mean_ci(x, rng) if len(x) else None
            ep = n_episodes(m & ok, dfA.index)
            ev[tag] = {"n": int(len(x)), "episodes": ep,
                       "mean_fwd20": round(float(x.mean()), 2) if len(x) else None,
                       "ci": ci, "vs_baseline": round(float(x.mean() - base), 2)
                       if len(x) else None}
            c = f"[{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else "IZ ni mogoč"
            print(f"  {tag:26} n={len(x):>3} ({ep} epizod)  "
                  f"{x.mean() if len(x) else float('nan'):+6.2f} %  {c}"
                  f"   proti izhodišču {x.mean()-base if len(x) else float('nan'):+.2f}")
    out["event_study"] = ev

    # ── trade-level ───────────────────────────────────────────────────────
    print("\nMETRIKE — celotno okno, neto 0,30 % na stran")
    print(f"  {'':2}{'Sortino':>9}{'Sharpe':>8}{'MaxDD':>8}{'izpost':>8}"
          f"{'zajem+':>8}{'zajem-':>8}{'poslov':>8}{'obrat':>8}")
    res = {}
    for v in VARIANTS:
        m = metrics(pos[v][0], raw)
        m["sha256"] = digest(pos[v][0])
        m["label"] = LABEL[v]
        res[v] = m
        print(f"  {v:2}{m['sortino']:>9.3f}{m['sharpe']:>8.3f}{m['maxdd']:>8.1f}"
              f"{m['exposure']:>8.1f}{m['upside_capture']:>8.1f}"
              f"{m['downside_capture']:>8.1f}{m['trades']:>8d}{m['turnover']:>8.1f}")
    out["variants"] = res

    # ── where do they differ at all ───────────────────────────────────────
    print("\nKJE SE POZICIJE RAZLIKUJEJO")
    div = {}
    for v in ("E", "F"):
        m = np.abs(posA.to_numpy() - pos[v][0].to_numpy()) > 1e-12
        k = int(m.sum())
        if k:
            dts = posA.index[m]
            yr = pd.Series(1, index=dts).groupby(dts.year).sum().to_dict()
            div[v] = {"n_days": k, "first": str(dts[0].date()),
                      "last": str(dts[-1].date()),
                      "by_year": {str(a): int(b) for a, b in yr.items()}}
            print(f"  A proti {v}: {k:>4} dni  {dts[0].date()} → {dts[-1].date()}")
            print("      po letih: " + "  ".join(f"{a}:{b}" for a, b in yr.items()))
        else:
            div[v] = {"n_days": 0}
            print(f"  A proti {v}:    0 dni  IDENTIČNI")
    out["divergence"] = div

    # ── bootstrap ─────────────────────────────────────────────────────────
    print("\nSPARJENI BOOTSTRAP — ΔSortino proti A")
    rA = net_returns(posA, ret, FEE).to_numpy(float)
    boot = {}
    for v in ("E", "F"):
        rV = net_returns(pos[v][0], ret, FEE).to_numpy(float)
        boot[v] = paired_ci(rV, rA, rng)
        c = boot[v]
        print(f"  {v} - A   Δ {c['delta']:+.3f}   95 % CI "
              f"[{c['ci_lo']:+.3f}, {c['ci_hi']:+.3f}]   "
              f"{'IZKLJUČUJE ničlo' if c['excludes_zero'] else 'objame ničlo'}")
    out["bootstrap_vs_A"] = boot

    # ── sub-periods ───────────────────────────────────────────────────────
    print("\nPODOBDOBJA — Sortino, okna določena vnaprej")
    print(f"  {'okno':4}{'A':>9}{'E':>9}{'F':>9}   zmagovalec")
    subs, wins = {}, {v: 0 for v in VARIANTS}
    for name, a, b in SUBPERIODS:
        row = {}
        for v in VARIANTS:
            p = pos[v][0]
            w = p.index[(p.index >= a) & (p.index <= b)]
            row[v] = round(sortino(net_returns(p.reindex(w), ret, FEE).to_numpy(float)), 3)
        win = max(row, key=lambda k: row[k])
        wins[win] += 1
        subs[name] = {"from": a, "to": b, "sortino": row, "winner": win}
        print(f"  {name:4}" + "".join(f"{row[v]:>9.3f}" for v in VARIANTS) + f"   {win}")
    out["subperiods"] = {"windows": subs, "wins": wins}
    print("  zmag: " + "  ".join(f"{v}={wins[v]}" for v in VARIANTS))

    # ── exposure matching + volatility placebo ────────────────────────────
    print("\nIZENAČENA IZPOSTAVLJENOST + PLACEBO Z NIHAJNOSTJO")
    eA = res["A"]["exposure"]
    print(f"  {'':22}{'Sortino':>9}{'MaxDD':>8}{'zajem-':>8}{'izpost':>8}")
    match = {}
    for v in VARIANTS:
        p = pos[v][0]
        ps = (p * (eA / res[v]["exposure"])).clip(0.0, 1.0)
        r = net_returns(ps, ret, FEE).to_numpy(float)
        _, dn = capture(ps, ret)
        match[v] = {"sortino": round(sortino(r), 3), "maxdd": round(maxdd(r), 1),
                    "downside_capture": dn, "exposure": round(float(ps.mean() * 100), 1)}
        print(f"  {v:<22}{match[v]['sortino']:>9.3f}{match[v]['maxdd']:>8.1f}"
              f"{dn:>8.1f}{match[v]['exposure']:>8.1f}")

    # A untouched, position scaled by inverse volatility, matched to A's exposure
    inv = (dfA["vol_avg50"] / dfA["annual_vol"]).replace([np.inf, -np.inf],
                                                         np.nan).fillna(1.0)
    plac = posA * inv
    plac = (plac * (posA.mean() / plac.mean())).clip(0.0, 1.0)
    plac = plac * (posA.mean() / plac.mean())
    rp = net_returns(plac, ret, FEE).to_numpy(float)
    _, dnp = capture(plac, ret)
    match["placebo"] = {"sortino": round(sortino(rp), 3), "maxdd": round(maxdd(rp), 1),
                        "downside_capture": dnp,
                        "exposure": round(float(plac.mean() * 100), 1),
                        "turnover": round(float(turnover(plac).sum()), 1)}
    print(f"  {'PLACEBO (A + skal.)':<22}{match['placebo']['sortino']:>9.3f}"
          f"{match['placebo']['maxdd']:>8.1f}{dnp:>8.1f}"
          f"{match['placebo']['exposure']:>8.1f}")
    print("  Če placebo dosega E, prilagodljiv pas ni boljši vstop, ampak")
    print("  skaliranje z nihajnostjo po ovinku.")
    out["exposure_matched"] = match

    # ── lookahead ─────────────────────────────────────────────────────────
    print("\nREVIZIJA POGLEDA V PRIHODNOST")
    la = {}
    for v in ("E", "F"):
        full = pos[v][0]
        cand = full.index[(full.index >= "2019-09-01") & (full.index <= "2026-06-30")]
        dates = pd.DatetimeIndex(sorted(rng.choice(cand, size=40, replace=False)))
        bad = []
        for t in dates:
            pt, _ = positions(raw.loc[:t], v)
            if pt.index[-1] != t or abs(float(pt.iloc[-1]) - float(full.loc[t])) > 1e-12:
                bad.append(str(t.date()))
        la[v] = {"n_dates": len(dates), "n_differing": len(bad)}
        print(f"  {v}: {len(dates)} datumov · razlik {len(bad)}")
    out["lookahead"] = la

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
