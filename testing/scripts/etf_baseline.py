"""First measurement of the ETF sleeve — the baseline everything else is judged against.

    python testing/scripts/etf_baseline.py

Deliberately run before any tuning. The altcoin campaign's most expensive lesson
was that a candidate looks good on the window it was born on; the only defence is
to write down what the untuned port does, on a fixed split, before touching a
parameter. Everything printed here is therefore a *baseline*, not a result, and
the design window is the only one anything may be chosen on.

Six sections:
  1  data quality — what the loader had to do to each of the eight
  2  risk structure — realised vol, correlation, IDM, capital share vs risk share
  3  dated phases — how many rising and falling phases the sample actually holds
  4  gate ablation — which of the ported crypto entry conditions survive contact
     with an equity index, one at a time
  5  book level — buy & hold vs trend overlay vs rotation vs dual-book, split
     into design / validation / hold-out
  6  the verdict — phase protocol plus paired block bootstrap on the headline

Output: testing/data/etf_baseline.json
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "etf"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared.costs import net_returns                                   # noqa: E402
from shared.etf_data import load, load_panel, quality_report           # noqa: E402
from shared.etf_universe import PORTFOLIOS, UNIVERSE, usable_start     # noqa: E402
from testing.scripts import etf_eval as EV                             # noqa: E402
from testing.scripts import etf_wfo as W                               # noqa: E402

from diversitas.config import DEFAULT_CONFIG, ETFConfig                # noqa: E402
from diversitas.mean_reversion import DEFAULT_MR_CONFIG                # noqa: E402
from diversitas.mean_reversion import run_strategy as run_mr           # noqa: E402
from diversitas.rotation import (buy_and_hold, dual_book, overlay_book,  # noqa: E402
                                 rotate_within)
from diversitas.strategy import run_strategy                           # noqa: E402

OUT = ROOT / "testing" / "data" / "etf_baseline.json"
TD = 252


def _sleeve_return(key: str, cfg: ETFConfig, runner=run_strategy) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    daily = load(key, start=UNIVERSE[key].usable_from)
    df = runner(daily, config=cfg).df
    pos = (df["target_alloc"] / 100.0).shift(1).fillna(0.0)
    ret = df["close"].pct_change().fillna(0.0)
    fee = cfg.fee_overrides.get(key, cfg.fee_per_side_pct) if hasattr(cfg, "fee_overrides") else 0.20
    return net_returns(pos, ret, fee), ret, df


# ── 1. data quality ───────────────────────────────────────────────────────────

def section_data() -> dict:
    frames = {k: load(k, start=UNIVERSE[k].usable_from) for k in UNIVERSE}
    q = quality_report(frames)
    print("\n1  DATA QUALITY\n" + "-" * 78)
    print(q.to_string())
    print(f"\n   usable joint start  P1 {usable_start('P1')}   P2 {usable_start('P2')}")
    return dict(quality=json.loads(q.reset_index().to_json(orient="records")))


# ── 2. risk structure ─────────────────────────────────────────────────────────

def section_risk() -> dict:
    keys = list(UNIVERSE)
    px = pd.DataFrame({k: load(k, start=UNIVERSE[k].usable_from)["close"] for k in keys})
    r = px.pct_change().dropna()
    print("\n2  RISK STRUCTURE  (joint window "
          f"{r.index.min().date()} -> {r.index.max().date()}, {len(r)} bars)\n" + "-" * 78)
    vol = (r.std() * np.sqrt(TD) * 100).round(2)
    vol250 = (r.tail(250).std() * np.sqrt(TD) * 100).round(2)
    print(pd.DataFrame({"ann_vol_pct": vol, "last250_pct": vol250}).to_string())
    print("\n   correlation\n" + (r.corr() * 100).round(0).astype(int).to_string())

    out = dict(ann_vol=vol.to_dict(), ann_vol_250=vol250.to_dict(),
               corr=(r.corr().round(3)).to_dict(), books={})
    for name, w in PORTFOLIOS.items():
        cols = list(w)
        wv = np.array([w[c] for c in cols])
        C = r[cols].corr().to_numpy()
        s = r[cols].std().to_numpy() * np.sqrt(TD)
        S = np.outer(s, s) * C
        pv = float(np.sqrt(wv @ S @ wv))
        idm = 1.0 / float(np.sqrt(wv @ C @ wv))
        rc = wv * (S @ wv) / pv ** 2
        print(f"\n   {name}: portfolio vol {pv*100:.2f} %   IDM {idm:.2f}")
        print("      capital share : " + "  ".join(f"{c} {w[c]*100:.0f}%" for c in cols))
        print("      risk    share : " + "  ".join(f"{c} {v*100:.0f}%" for c, v in zip(cols, rc)))
        out["books"][name] = dict(vol_pct=round(pv * 100, 2), idm=round(idm, 3),
                                  risk_share={c: round(float(v), 4) for c, v in zip(cols, rc)},
                                  capital_share=w)
    return out


# ── 3. dated phases ───────────────────────────────────────────────────────────

def section_phases() -> tuple[dict, list]:
    world = load("World", start=UNIVERSE["World"].usable_from)["close"]
    tbl = W.phase_table(world)
    phases = W.date_phases(world)
    print("\n3  DATED PHASES of MSCI World in EUR (Bry-Boschan / Pagan-Sossounov, "
          f"K={W.K_WINDOW}, min {W.MIN_PHASE} bars, min {W.MIN_AMPL:.0%})\n" + "-" * 78)
    print(tbl.to_string(index=False) if len(tbl) else "   none found")
    n_up = int((tbl["kind"] == "rast").sum()) if len(tbl) else 0
    n_dn = int((tbl["kind"] == "padec").sum()) if len(tbl) else 0
    print(f"\n   rising {n_up}   falling {n_dn}   "
          f"-> the crypto criterion 'win 3 of 5 falling' is not expressible here")
    return dict(table=json.loads(tbl.to_json(orient="records")) if len(tbl) else [],
                n_rising=n_up, n_falling=n_dn), phases


# ── 4. gate ablation ──────────────────────────────────────────────────────────

def section_ablation() -> dict:
    """Which ported gate costs what, on the broad equity index.

    One variant per gate removed, plus the two canonical equity trend rules the
    literature would use instead. The point is not to pick a winner — that would
    be selecting on the same data — but to see whether the crypto entry stack is
    even in the right region for this asset class.
    """
    key = "World"
    daily = load(key, start=UNIVERSE[key].usable_from)
    base_ret = daily["close"].pct_change().fillna(0.0)
    fee = DEFAULT_CONFIG.fee_per_side_pct

    variants = {
        "ported stack (all gates)": DEFAULT_CONFIG,
        "  - ADX filter": replace(DEFAULT_CONFIG, use_adx=False),
        "  - RSI/EMA momentum": replace(DEFAULT_CONFIG, rsi_entry=0.0, ema_slow_len=2),
        "  - rising-trackline": replace(DEFAULT_CONFIG, track_slope_bars=1),
        "  - ATR entry buffer": replace(DEFAULT_CONFIG, use_atr_buffer=False, track_buf_pct=0.0),
        "  - ATR trailing stop": replace(DEFAULT_CONFIG, use_trail=False),
        "  - vol targeting": replace(DEFAULT_CONFIG, use_vol_sizing=False),
        "only trackline + MA200": replace(DEFAULT_CONFIG, use_adx=False, rsi_entry=0.0,
                                          ema_slow_len=2, track_slope_bars=1,
                                          use_trail=False),
    }
    rows = [EV.evaluate(base_ret, label="buy & hold")]
    detail = {}
    for label, cfg in variants.items():
        df = run_strategy(daily, config=cfg).df
        pos = (df["target_alloc"] / 100.0).shift(1).fillna(0.0)
        r = net_returns(pos, base_ret, fee)
        row = EV.evaluate(r, bench=base_ret, position=pos, label=label)
        rows.append(row)
        detail[label] = {k: (None if isinstance(v, float) and not np.isfinite(v) else v)
                         for k, v in row.items() if not isinstance(v, (pd.Series, pd.DataFrame))}

    # the two canonical equity trend rules, for reference
    close = daily["close"]
    sma200 = close.rolling(200).mean()
    for label, sig in (("ref: close > SMA200", (close > sma200)),
                       ("ref: 12-month momentum > 0", (close / close.shift(252) - 1) > 0)):
        pos = sig.shift(1).fillna(False).astype(float)
        r = net_returns(pos, base_ret, fee)
        row = EV.evaluate(r, bench=base_ret, position=pos, label=label)
        rows.append(row)
        detail[label] = {k: (None if isinstance(v, float) and not np.isfinite(v) else v)
                         for k, v in row.items()}

    print("\n4  GATE ABLATION on World, EUR, "
          f"{daily.index.min().date()} -> {daily.index.max().date()}\n" + "-" * 78)
    print(EV.fmt(EV.compare(rows, sort_by="cagr")))
    return detail


# ── 5. book level ─────────────────────────────────────────────────────────────

def section_books(phases: list) -> dict:
    out = {}
    for name in ("P1", "P2"):
        _, frames = load_panel(name)
        w = PORTFOLIOS[name]
        cfg = DEFAULT_CONFIG
        cands = {
            "buy & hold (annual reb.)": buy_and_hold(frames, w, rebalance_every=252,
                                                     fee_per_side_pct=cfg.fee_per_side_pct),
            "buy & hold (quarterly)": buy_and_hold(frames, w, rebalance_every=63,
                                                   fee_per_side_pct=cfg.fee_per_side_pct),
            "trend overlay (monthly)": overlay_book(frames, w, cfg, rebalance_every=21),
            "trend overlay (daily)": overlay_book(frames, w, cfg, rebalance_every=1),
            "rotate top-k (monthly)": rotate_within(frames, cfg, k=max(2, len(w) // 2),
                                                    rebalance_every=21),
        }
        bench = cands["buy & hold (annual reb.)"].returns
        rows, per_split = [], {}
        for label, res in cands.items():
            rows.append(EV.evaluate(res.returns, bench=bench,
                                    position=res.weights.sum(axis=1),
                                    turnover=res.turnover, gross=res.gross, label=label))
            per_split[label] = {
                sp: EV.evaluate(W.split(res.returns, sp), label=f"{label} [{sp}]")
                for sp in ("design", "validation", "holdout")}
        print(f"\n5  BOOK {name}   {', '.join(f'{k} {v:.0%}' for k, v in w.items())}\n"
              + "-" * 78)
        print(EV.fmt(EV.compare(rows, sort_by="sortino")))
        print("\n   by split (Sortino / MaxDD %):")
        for label in cands:
            cells = "   ".join(
                f"{sp[:4]} {per_split[label][sp]['sortino']:+.2f} / "
                f"{per_split[label][sp]['max_dd']*100:5.1f}"
                for sp in ("design", "validation", "holdout"))
            print(f"      {label:<26} {cells}")
        out[name] = dict(
            full={r["label"]: _clean(r) for r in rows},
            splits={lb: {sp: _clean(v) for sp, v in d.items()} for lb, d in per_split.items()},
            returns_index=[str(d.date()) for d in cands["trend overlay (monthly)"].returns.index[:1]],
        )
        out[name]["_series"] = {lb: res.returns for lb, res in cands.items()}
    return out


def _clean(d: dict) -> dict:
    return {k: (None if isinstance(v, float) and not np.isfinite(v) else
                (v if not isinstance(v, (pd.Timestamp,)) else str(v)))
            for k, v in d.items() if not isinstance(v, (pd.Series, pd.DataFrame))}


# ── 6. verdict ────────────────────────────────────────────────────────────────

def section_verdict(books: dict, phases: list) -> dict:
    print("\n6  VERDICT — phase protocol + paired block bootstrap\n" + "-" * 78)
    out = {}
    for name in ("P1", "P2"):
        series = books[name].pop("_series")
        base = series["buy & hold (annual reb.)"]
        for label in ("trend overlay (monthly)", "rotate top-k (monthly)"):
            cand = series[label]
            ph = W.per_phase(cand, base, phases)
            comb = W.combinatorial(cand, base, phases, k=min(3, max(1, len(phases))))
            ci_s = W.paired_diff_ci(cand, base, n_boot=2000)
            ci_dd = W.paired_diff_ci(
                cand, base, metric=lambda r: float((np.cumprod(1 + r) /
                                                    np.maximum.accumulate(np.cumprod(1 + r)) - 1).min() * 100),
                n_boot=2000)
            v = W.verdict(ph, comb, ci_s)
            print(f"\n   {name}  {label}")
            if len(ph):
                print(ph.to_string(index=False))
            print(f"      rising {v['rising']}  falling {v['falling']}  "
                  f"subsets {comb['n_subsets']} win {comb['win_rate']}%")
            print(f"      d Sortino {ci_s['point']:+.3f} [{ci_s['lo']:+.3f}, {ci_s['hi']:+.3f}]"
                  f"  P(better) {ci_s['p_better']:.0%}  -> {ci_s['verdict']}")
            print(f"      d MaxDD   {ci_dd['point']:+.1f} [{ci_dd['lo']:+.1f}, {ci_dd['hi']:+.1f}]"
                  f"  -> {ci_dd['verdict']}")
            print(f"      ACCEPTED: {v['accepted']}")
            out[f"{name}|{label}"] = dict(phases=json.loads(ph.to_json(orient="records")) if len(ph) else [],
                                          combinatorial=comb, ci_sortino=ci_s,
                                          ci_maxdd=ci_dd, verdict=v)
    return out


def main() -> int:
    pd.set_option("display.width", 220)
    res = {"generated": str(pd.Timestamp.utcnow())}
    res["data"] = section_data()
    res["risk"] = section_risk()
    res["phases"], phases = section_phases()
    res["ablation"] = section_ablation()
    books = section_books(phases)
    res["verdict"] = section_verdict(books, phases)
    res["books"] = books
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nwritten: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
