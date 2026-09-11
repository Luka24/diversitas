"""Evaluation panel for the ETF sleeve — the four things `metrics.py` does not do.

`testing/scripts/metrics.py` stays the single source of truth for the numbers it
already defines (CAGR, Sharpe, Sortino, MaxDD, Calmar, Omega, Ulcer, profit
factor, win rate, exposure). This module does not redefine any of them; it calls
them with `td=252` and adds:

  1. **Recovery time.** MaxDD says how deep; it does not say how long. On a
     20-year equity horizon "recovered in 7 months" and "recovered in 6 years"
     are the same number in `metrics.core_stats` and completely different
     experiences. `drawdown_episodes` dates every episode and flags the one that
     has not recovered yet, which is the one that matters most and the one a
     single MaxDD figure hides.
  2. **A benchmark that is the actual book.** Comparing a trend overlay to cash,
     or to the S&P, answers nothing. The benchmark here is the same eight funds
     at the same strategic weights, rebalanced on the same calendar, paying the
     same costs — so the only difference left is the signal.
  3. **Up/down capture.** The altcoin campaign's most useful single diagnostic:
     a defensive overlay always improves ratio metrics by being out of the
     market, so ratios alone cannot distinguish skill from absence. Capture
     splits it — how much of the benchmark's gains it kept against how much of
     its losses it took.
  4. **The trading-day constant.** `metrics.TRADING_DAYS` is 365 and
     `stats._SQRT_TD` is 365. Both are correct for a 24/7 asset and both are
     wrong here by a factor of 1.204 on every annualised figure. Every entry
     point in this module passes 252 explicitly; nothing here inherits a default.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from testing.scripts import metrics as M  # noqa: E402

TD = 252


# ── 1. drawdowns, with dates and durations ────────────────────────────────────

def drawdown_episodes(returns: pd.Series, min_depth: float = 0.05) -> pd.DataFrame:
    """Every drawdown deeper than `min_depth`, dated.

    Columns: peak, trough, recovered, depth_pct, days_to_trough, days_to_recover,
    total_days, underwater (True when the episode never recovered inside the
    sample). Sorted deepest first.
    """
    r = returns.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    eq = (1.0 + r).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1.0
    in_dd = dd < -1e-12

    rows = []
    start = None
    for i, (ts, flag) in enumerate(in_dd.items()):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            rows.append((start, i))
            start = None
    if start is not None:
        rows.append((start, None))

    out = []
    for a, b in rows:
        seg = dd.iloc[a:(b if b is not None else len(dd))]
        depth = float(seg.min())
        if depth > -abs(min_depth):
            continue
        trough_ts = seg.idxmin()
        peak_ts = eq.iloc[:a].idxmax() if a > 0 else eq.index[0]
        rec_ts = dd.index[b] if b is not None else None
        out.append(dict(
            peak=peak_ts, trough=trough_ts, recovered=rec_ts,
            depth_pct=round(depth * 100, 2),
            days_to_trough=int((trough_ts - peak_ts).days),
            days_to_recover=(int((rec_ts - trough_ts).days) if rec_ts is not None else None),
            total_days=(int((rec_ts - peak_ts).days) if rec_ts is not None
                        else int((dd.index[-1] - peak_ts).days)),
            underwater=rec_ts is None))
    if not out:
        return pd.DataFrame(columns=["peak", "trough", "recovered", "depth_pct",
                                     "days_to_trough", "days_to_recover",
                                     "total_days", "underwater"])
    return pd.DataFrame(out).sort_values("depth_pct").reset_index(drop=True)


def recovery_summary(returns: pd.Series) -> dict:
    """The three numbers a MaxDD figure leaves out."""
    ep = drawdown_episodes(returns)
    if ep.empty:
        return dict(worst_depth_pct=0.0, worst_recovery_days=None,
                    longest_underwater_days=0, time_underwater_pct=0.0)
    worst = ep.iloc[0]
    r = returns.fillna(0.0)
    eq = (1 + r).cumprod()
    underwater = (eq < eq.cummax() - 1e-12)
    return dict(
        worst_depth_pct=float(worst["depth_pct"]),
        worst_recovery_days=(None if worst["underwater"] else int(worst["days_to_recover"])),
        longest_underwater_days=int(ep["total_days"].max()),
        time_underwater_pct=round(float(underwater.mean() * 100), 1))


# ── 2 & 3. against the benchmark ──────────────────────────────────────────────

def capture(strat: pd.Series, bench: pd.Series) -> dict:
    """Up- and down-capture (Morningstar convention), and the ratio between them.

    Geometric mean per up-day and per down-day, not the compounded total. The
    compounded version looks more natural and is unusable: over seventeen years
    the product over up-days alone is of order 1e30, and a ratio of two such
    numbers is arithmetic noise, not a capture rate. The geometric mean is the
    same statistic per unit of time and stays on a readable scale.

    Up-capture 60 % with down-capture 30 % is a real edge; 60 / 60 is just less
    money at risk. This is the diagnostic the altcoin campaign leaned on, because
    every defensive overlay flatters ratio metrics simply by being absent.
    """
    s, b = strat.align(bench, join="inner")
    up, dn = b > 0, b < 0

    def gmean(x: pd.Series) -> float:
        if len(x) == 0:
            return 0.0
        return float(np.exp(np.log1p(x.to_numpy()).mean()) - 1.0)

    bu, bd = gmean(b[up]), gmean(b[dn])
    su, sd = gmean(s[up]), gmean(s[dn])
    up_c = (su / bu * 100.0) if abs(bu) > 1e-12 else np.nan
    dn_c = (sd / bd * 100.0) if abs(bd) > 1e-12 else np.nan
    return dict(up_capture=up_c, down_capture=dn_c,
                capture_ratio=(up_c / dn_c) if (dn_c and abs(dn_c) > 1e-9) else np.nan)


def versus(strat: pd.Series, bench: pd.Series, td: int = TD) -> dict:
    """Excess-return view: tracking error, information ratio, beta, capture."""
    s, b = strat.align(bench, join="inner")
    d = s - b
    te = float(d.std() * np.sqrt(td))
    ir = float(d.mean() * td / te) if te > 1e-12 else np.nan
    var_b = float(b.var())
    beta = float(np.cov(s, b)[0, 1] / var_b) if var_b > 1e-15 else np.nan
    alpha = float((s.mean() - beta * b.mean()) * td) if np.isfinite(beta) else np.nan
    eq_s, eq_b = (1 + s).cumprod(), (1 + b).cumprod()
    out = dict(tracking_error=te, information_ratio=ir, beta=beta, alpha_ann=alpha,
               total_return_pct=float((eq_s.iloc[-1] - 1) * 100),
               bench_total_return_pct=float((eq_b.iloc[-1] - 1) * 100))
    out.update(capture(s, b))
    return out


# ── the panel ─────────────────────────────────────────────────────────────────

def evaluate(returns: pd.Series, bench: Optional[pd.Series] = None,
             position: Optional[pd.Series] = None,
             turnover: Optional[pd.Series] = None,
             gross: Optional[pd.Series] = None,
             label: str = "strategy", td: int = TD) -> dict:
    """One dict per candidate. `metrics.core_stats` supplies the ratios; this
    adds duration, cost drag and the benchmark comparison.

    `gross` is optional but strongly recommended: reporting only the net series
    hides whether a candidate is losing to costs or to the signal, and those
    have opposite fixes.
    """
    r = returns.replace([np.inf, -np.inf], 0.0).dropna()
    c = M.core_stats(r, td)
    e = M.extended_stats(r)
    out = dict(label=label, n_days=len(r), years=round(len(r) / td, 2))
    out.update({k: c[k] for k in ("cagr", "sharpe", "sortino", "max_dd", "calmar",
                                  "ann_ret", "ann_std")})
    out["final_multiple"] = c["final"]
    out.update(e)
    out.update(recovery_summary(r))
    if position is not None:
        out["exposure_pct"] = float(position.reindex(r.index).fillna(0.0).mean() * 100)
    if turnover is not None:
        t = turnover.reindex(r.index).fillna(0.0)
        out["ann_turnover_pct"] = float(t.sum() / (len(r) / td) * 100)
    if gross is not None:
        g = gross.reindex(r.index).fillna(0.0)
        out["cost_drag_ann_pct"] = float((g.mean() - r.mean()) * td * 100)
    if bench is not None:
        out.update(versus(r, bench.reindex(r.index).fillna(0.0), td))
    return out


def trade_panel(df: pd.DataFrame, s_bull: int = 1) -> dict:
    """Profit factor / win rate / durations, from the signal frame.

    Reuses `metrics.build_trades`, which reads `signal_changed` + `signal_state`
    — the same ledger the dashboards draw, so a report and the UI cannot
    disagree about how many trades there were.
    """
    return M.trade_stats(M.build_trades(df, s_bull=s_bull))


def compare(rows: list[dict], sort_by: str = "sortino") -> pd.DataFrame:
    """Candidates as a table, most-interesting columns first."""
    cols = ["label", "years", "cagr", "sharpe", "sortino", "max_dd", "calmar",
            "worst_recovery_days", "longest_underwater_days", "time_underwater_pct",
            "exposure_pct", "ann_turnover_pct", "cost_drag_ann_pct",
            "up_capture", "down_capture", "capture_ratio",
            "information_ratio", "final_multiple"]
    df = pd.DataFrame(rows)
    cols = [c for c in cols if c in df.columns]
    return df[cols].sort_values(sort_by, ascending=False).reset_index(drop=True)


def fmt(df: pd.DataFrame) -> str:
    """Percent-scale the columns that are fractions, so a printed table reads."""
    d = df.copy()
    for c in ("cagr", "max_dd", "ann_ret", "ann_std"):
        if c in d.columns:
            d[c] = (d[c] * 100).round(2)
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].round(2)
    return d.to_string(index=False)
