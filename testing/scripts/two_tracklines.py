"""Do we need both trackline rules, or does one of them suffice?

Pre-registered in `testing/nacrt_dva_trackline.md`, committed before this ran.

    A   close > mid(75) + 3 % of price          today's rule
    D   close > mid(20) + 25 % of range(20)     Donchian, written as a trackline

Five cells, the complete lattice over two binary conditions, with everything
else in the engine untouched:

    A · D · A and D · A or D · neither

Nothing is swept. Both periods and both buffer definitions are existing values.

Two methods carry the decision, chosen because both can return "the data cannot
tell" instead of crowning a winner:

  Forecast encompassing. Regress the 20-day forward return on both indicators at
  once. A coefficient indistinguishable from zero means that condition is
  redundant given the other. Newey-West errors at lag 20, since forward windows
  overlap and naive errors would be understated roughly fourfold.

  Model Confidence Set (Hansen, Lunde & Nason 2011). Returns the set of cells
  that cannot be separated at a given confidence. Uninformative data leave a
  large set, which is the honest outcome when five variants sit on ~20 trades.

Then nested walk-forward over the five cells, PBO via CSCV, and ETH as the second
and final pre-registered use.

Output: testing/data/two_tracklines.json
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "testing", ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared import indicators as ind
from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

FEE, PPY, H = 0.30, 365, 20
S_BLOCKS = 12
SRC = ROOT / "testing" / "data" / "sources"
OUT = ROOT / "testing" / "data" / "two_tracklines.json"
CELLS = ("A", "D", "A&D", "A|D", "brez")
SUBPERIODS = [("I", "2019-03-09", "2021-01-31"), ("II", "2021-02-01", "2022-11-30"),
              ("III", "2022-12-01", "2024-09-30"), ("IV", "2024-10-01", "2026-07-29")]
OTHER_TERMS = ("track_rising_window", "regime_ok", "btc_filter_ok")
rng = np.random.default_rng(20260809)


# ── the two conditions ──────────────────────────────────────────────────────
def conditions(raw, index):
    h75 = ind.highest(raw["high"], 75).reindex(index)
    l75 = ind.lowest(raw["low"], 75).reindex(index)
    h20 = ind.highest(raw["high"], 20).reindex(index)
    l20 = ind.lowest(raw["low"], 20).reindex(index)
    c = raw["close"].reindex(index)
    A = c > (h75 + l75) / 2 * 1.03
    D = c > (h20 + l20) / 2 + 0.25 * (h20 - l20)
    return A.fillna(False), D.fillna(False)


def build(raw, cell):
    """Swap the trackline gate, keep the production state machine."""
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    A, D = conditions(raw, df.index)
    gate = {"A": A, "D": D, "A&D": A & D, "A|D": A | D,
            "brez": pd.Series(True, index=df.index)}[cell]
    # exit stays on today's definition throughout, so only the entry gate varies
    bull = gate.copy()
    for t in OTHER_TERMS:
        bull &= df[t]
    df["bull_condition"] = (bull & ~df["blowoff"]).fillna(False)
    st = trim_warmup(smod.run_state_machine(df, cfg))
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos, st


def sortino(r):
    if len(r) < 20:
        return np.nan
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def metrics(pos, ret):
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1 + r)
    p = pos.to_numpy()
    return {"sortino": round(sortino(r), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
            "exposure": round(float(p.mean() * 100), 1),
            "trades": int((np.diff(p, prepend=p[0]) > 0).sum()),
            "turnover": round(float(turnover(pos).sum()), 1)}


# ── Newey-West OLS ──────────────────────────────────────────────────────────
def ols_hac(y, X, lag):
    """Coefficients with Bartlett-kernel HAC standard errors."""
    X = np.column_stack([np.ones(len(y)), X])
    XtXi = np.linalg.pinv(X.T @ X)
    b = XtXi @ (X.T @ y)
    e = y - X @ b
    n, k = X.shape
    S = (X * e[:, None]).T @ (X * e[:, None])
    for j in range(1, lag + 1):
        w = 1.0 - j / (lag + 1.0)
        G = (X[j:] * e[j:, None]).T @ (X[:-j] * e[:-j, None])
        S += w * (G + G.T)
    V = XtXi @ S @ XtXi * n / (n - k)
    se = np.sqrt(np.diag(V))
    return b, se, b / se


# ── Model Confidence Set (range statistic, block bootstrap) ─────────────────
def mcs(losses: np.ndarray, names, alpha=0.10, nboot=2000, block=20):
    """losses[i] = per-day loss of model i. Returns the surviving set."""
    alive = list(range(len(names)))
    n = losses.shape[1]
    k = int(np.ceil(n / block))
    st = rng.integers(0, n, size=(nboot, k))
    idx = (st[:, :, None] + np.arange(block)[None, None, :]
           ).reshape(nboot, k * block)[:, :n] % n
    eliminated = []
    while len(alive) > 1:
        L = losses[alive]
        d = L.mean(axis=1)[:, None] - L.mean(axis=1)[None, :]      # mean diffs
        boot = L[:, idx].mean(axis=2)                              # (m, nboot)
        db = boot[:, None, :] - boot[None, :, :]
        var = db.var(axis=2) + 1e-18
        t = np.abs(d) / np.sqrt(var)
        np.fill_diagonal(t, 0.0)
        T = t.max()
        tb = np.abs(db - d[:, :, None]) / np.sqrt(var)[:, :, None]
        Tb = tb.max(axis=(0, 1))
        p = float((Tb > T).mean())
        if p > alpha:
            break
        worst = alive[int(np.argmax((d / np.sqrt(var)).mean(axis=1)))]
        eliminated.append((names[worst], round(p, 3)))
        alive.remove(worst)
    return [names[i] for i in alive], eliminated


def main() -> int:
    out = {"fee_per_side_pct": FEE, "cells": list(CELLS),
           "preregistered": "testing/nacrt_dva_trackline.md"}

    for sym, f in (("BTC", "BTC_binance_warmup.parquet"), ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(SRC / f)
        ret = raw["close"].pct_change().fillna(0.0)
        pos = {c: build(raw, c) for c in CELLS}
        idx = pos["A"][0].index
        res = {}
        print(f"\n{'='*92}\n{sym} · {len(idx)} dni · {idx[0].date()} → {idx[-1].date()}\n{'='*92}")
        print(f"  {'celica':<8}{'vrat':>7}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}"
              f"{'konec':>7}{'izpost':>8}{'posl':>6}    I     II    III    IV")
        # Number of price GATES, not tracklines: track_rising_window still
        # uses the 75-day trackline in every cell, so the 75-day line is
        # always computed. What varies is how many gates guard the entry.
        n_tl = {"A": 1, "D": 1, "A&D": 2, "A|D": 2, "brez": 0}
        for c in CELLS:
            p = pos[c][0]
            m = metrics(p, ret)
            sub = {}
            for nm, a, b in SUBPERIODS:
                w = p.index[(p.index >= a) & (p.index <= b)]
                sub[nm] = (round(sortino(net_returns(p.reindex(w), ret, FEE)
                                         .to_numpy(float)), 2) if len(w) > 60 else None)
            m["sub"] = sub
            m["n_price_gates"] = n_tl[c]
            res[c] = m
            s = "  ".join(f"{v:5.2f}" if v is not None else "    —" for v in sub.values())
            print(f"  {c:<8}{n_tl[c]:>7}{m['sortino']:>9.3f}{m['cagr']:>6.1f}%"
                  f"{m['maxdd']:>7.1f}%{m['final']:>6.2f}x{m['exposure']:>7.1f}%"
                  f"{m['trades']:>6d}  {s}")

        # ── encompassing ────────────────────────────────────────────────────
        A, D = conditions(raw, idx)
        cl = raw["close"].reindex(idx).to_numpy(float)
        fwd = np.full(len(idx), np.nan)
        fwd[:len(idx) - H] = (cl[H:] / cl[:len(idx) - H] - 1) * 100
        ok = np.isfinite(fwd)
        b, se, t = ols_hac(fwd[ok], np.column_stack([A.to_numpy()[ok].astype(float),
                                                     D.to_numpy()[ok].astype(float)]), H)
        enc = {"n": int(ok.sum()), "const": round(float(b[0]), 2),
               "beta_A": round(float(b[1]), 2), "t_A": round(float(t[1]), 2),
               "beta_D": round(float(b[2]), 2), "t_D": round(float(t[2]), 2)}
        print(f"\n  TEST ZAOBJETJA — donos +{H} dni ~ A + D   (Newey-West, zamik {H})")
        print(f"    konstanta {b[0]:+6.2f}")
        sa, sd = abs(t[1]) > 1.96, abs(t[2]) > 1.96
        print(f"    A         {b[1]:+6.2f}   t = {t[1]:+5.2f}   "
              f"{'značilen' if sa else 'NI značilen'}")
        print(f"    D         {b[2]:+6.2f}   t = {t[2]:+5.2f}   "
              f"{'značilen' if sd else 'NI značilen'}")
        # Reading the four cases explicitly. When NEITHER is significant the test
        # is inconclusive; saying "both are redundant" would invert its meaning.
        verdict = ("A je ob D odveč" if sd and not sa else
                   "D ob A ne doda" if sa and not sd else
                   "oba nosita svojo informacijo" if sa and sd else
                   "NEODLOČENO — pri teh napakah nobeden ni značilen, "
                   "test ne loči")
        print(f"    -> {verdict}")
        enc["verdict"] = verdict
        out.setdefault(sym, {})["encompassing"] = enc

        # ── MCS ─────────────────────────────────────────────────────────────
        losses = np.vstack([-net_returns(pos[c][0], ret, FEE).to_numpy(float)
                            for c in CELLS])
        keep, elim = mcs(losses, list(CELLS))
        print(f"\n  MODEL CONFIDENCE SET (α = 0,10, izguba = −dnevni neto donos)")
        print(f"    preživele: {', '.join(keep)}")
        print(f"    izločene:  {', '.join(f'{n} (p={p})' for n, p in elim) or '—'}")
        out[sym]["mcs"] = {"kept": keep, "eliminated": elim}

        # ── nested walk-forward ─────────────────────────────────────────────
        print(f"\n  UGNEZDENI WALK-FORWARD — celica izbrana samo iz učnega dela")
        wf = {}
        for tr_y, te_y in ((3, 1), (2, 1)):
            segs, picks, seg_a = [], [], []
            start = idx[0]
            while True:
                tb = start + pd.DateOffset(years=tr_y)
                eb = tb + pd.DateOffset(years=te_y)
                if eb > idx[-1]:
                    break
                sc = {}
                for c in CELLS:
                    w = idx[(idx >= start) & (idx <= tb)]
                    sc[c] = sortino(net_returns(pos[c][0].reindex(w), ret, FEE)
                                    .to_numpy(float))
                pick = max(sc, key=lambda k: sc[k] if np.isfinite(sc[k]) else -9e9)
                te = idx[(idx > tb) & (idx <= eb)]
                picks.append(pick)
                segs.append(pos[pick][0].reindex(te))
                seg_a.append(pos["A"][0].reindex(te))
                start = start + pd.DateOffset(years=te_y)
            if not segs:
                continue
            mr = metrics(pd.concat(segs), ret)
            ma = metrics(pd.concat(seg_a), ret)
            wf[f"{tr_y}y/{te_y}y"] = {"picks": picks, "refit": mr, "A": ma,
                                      "refit_beats_A": bool(mr["sortino"] > ma["sortino"])}
            print(f"    {tr_y}y/{te_y}y  izbire {picks}")
            print(f"      A {ma['sortino']:.3f}   refit {mr['sortino']:.3f}   "
                  f"{'refit boljši' if mr['sortino'] > ma['sortino'] else 'A boljši'}")
        out[sym]["walk_forward"] = wf

        # ── PBO via CSCV ────────────────────────────────────────────────────
        mat = np.vstack([net_returns(pos[c][0], ret, FEE).to_numpy(float) for c in CELLS])
        blocks = np.array_split(np.arange(mat.shape[1]), S_BLOCKS)
        below = tot = 0
        picked = {c: 0 for c in CELLS}
        for sel in itertools.combinations(range(S_BLOCKS), S_BLOCKS // 2):
            i_is = np.concatenate([blocks[i] for i in sel])
            i_oos = np.concatenate([blocks[i] for i in range(S_BLOCKS) if i not in sel])
            s_is = np.array([sortino(m[i_is]) for m in mat])
            s_oos = np.array([sortino(m[i_oos]) for m in mat])
            if not (np.isfinite(s_is).all() and np.isfinite(s_oos).all()):
                continue
            k = int(np.argmax(s_is))
            picked[CELLS[k]] += 1
            tot += 1
            below += int((s_oos < s_oos[k]).sum() / (len(CELLS) - 1) < 0.5)
        out[sym]["pbo"] = {"paths": tot, "pbo": round(below / tot, 3), "picked": picked}
        print(f"\n  PBO (CSCV, {tot} poti): {below/tot:.3f}   "
              f"izbrano v vzorcu: " + "  ".join(f"{k}:{v}" for k, v in picked.items() if v))
        out[sym]["cells"] = res

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
