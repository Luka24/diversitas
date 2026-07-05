"""Single source of truth for performance metrics.

`core_stats` reproduces the live dashboards' `_stats()` (`*/diversitas/dashboard.py`)
bit-for-bit so tests and UI never disagree. `compute_all_metrics` adds the
extended panel (Omega, Ulcer, tail ratio, trade stats, exposure) specified in the
v2 plan. Trade ledger mirrors the momentum dashboard's `_build_trade_ledger`.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

TRADING_DAYS = 365


# ── core (matches dashboard _stats to 1e-6) ───────────────────────────────────

def core_stats(r: pd.Series, td: int = TRADING_DAYS) -> dict:
    r = r.replace([np.inf, -np.inf], 0.0)
    eq     = (1.0 + r).cumprod()
    peak   = eq.cummax()
    dd     = eq / peak - 1.0
    max_dd = float(dd.min()) if len(dd) else 0.0
    years  = max(len(r) / td, 1e-9)
    final  = float(eq.iloc[-1]) if len(eq) else 1.0
    cagr   = final ** (1.0 / years) - 1.0
    ann_ret = r.mean() * td
    ann_std = r.std() * np.sqrt(td)
    down_dev = np.sqrt(np.mean(np.minimum(r.values, 0.0) ** 2)) * np.sqrt(td)
    sharpe   = ann_ret / ann_std  if ann_std  > 1e-9 else np.nan
    sortino  = ann_ret / down_dev if down_dev > 1e-9 else np.nan
    calmar   = cagr / abs(max_dd)  if max_dd  < -1e-6 else np.nan
    return dict(cagr=cagr, sharpe=sharpe, sortino=sortino,
                max_dd=max_dd, calmar=calmar,
                ann_ret=float(ann_ret), ann_std=float(ann_std),
                final=final, eq=eq, dd=dd)


# ── extended return-based metrics ─────────────────────────────────────────────

def extended_stats(r: pd.Series) -> dict:
    r = r.replace([np.inf, -np.inf], 0.0).dropna()
    if len(r) < 5:
        return dict(omega=np.nan, ulcer=np.nan, tail_ratio=np.nan,
                    skew=np.nan, kurtosis=np.nan)
    eq   = (1.0 + r).cumprod()
    dd   = eq / eq.cummax() - 1.0
    pos  = r[r > 0].sum()
    neg  = abs(r[r < 0].sum())
    omega = pos / neg if neg > 1e-12 else np.nan
    ulcer = float(np.sqrt((dd ** 2).mean()))
    p95, p5 = np.percentile(r, 95), np.percentile(r, 5)
    tail = p95 / abs(p5) if abs(p5) > 1e-12 else np.nan
    return dict(omega=omega, ulcer=ulcer, tail_ratio=tail,
                skew=float(r.skew()), kurtosis=float(r.kurtosis()))


# ── trade ledger (mirrors momentum dashboard _build_trade_ledger) ─────────────

def build_trades(df: pd.DataFrame, s_bull: int = 1, s_bear: int = 3) -> list[dict]:
    changes = df[df["signal_changed"].fillna(False)]
    trades: list[dict] = []
    open_entry = None
    for ts, row in changes.iterrows():
        sig = int(row["signal_state"])
        if sig == s_bull:
            open_entry = {"entry_date": ts, "entry_px": float(row["close"])}
        elif open_entry is not None:      # any non-bull change closes the position
            pnl = (row["close"] / open_entry["entry_px"] - 1.0) * 100.0
            trades.append({**open_entry, "exit_date": ts,
                           "exit_px": float(row["close"]),
                           "duration_days": (ts - open_entry["entry_date"]).days,
                           "pnl_pct": pnl, "open": False})
            open_entry = None
    last = df.iloc[-1]
    if open_entry is not None and int(last["signal_state"]) == s_bull:
        pnl = (last["close"] / open_entry["entry_px"] - 1.0) * 100.0
        trades.append({**open_entry, "exit_date": last.name,
                       "exit_px": float(last["close"]),
                       "duration_days": (last.name - open_entry["entry_date"]).days,
                       "pnl_pct": pnl, "open": True})
    return trades


def trade_stats(trades: list[dict]) -> dict:
    closed = [t for t in trades if not t["open"]]
    n = len(closed)
    if n == 0:
        return dict(n_trades=0, win_rate=np.nan, profit_factor=np.nan,
                    payoff=np.nan, avg_pnl=np.nan, avg_duration=np.nan,
                    best=np.nan, worst=np.nan, max_consec_loss=0)
    pnls   = [t["pnl_pct"] for t in closed]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gp, gl = sum(wins), abs(sum(losses))
    avg_w  = np.mean(wins)          if wins   else 0.0
    avg_l  = abs(np.mean(losses))   if losses else 0.0
    consec = mx = 0
    for p in pnls:
        consec = consec + 1 if p <= 0 else 0
        mx = max(mx, consec)
    return dict(
        n_trades=n,
        win_rate=len(wins) / n * 100.0,
        profit_factor=(gp / gl) if gl > 1e-12 else np.nan,
        payoff=(avg_w / avg_l) if avg_l > 1e-12 else np.nan,
        avg_pnl=float(np.mean(pnls)),
        avg_duration=float(np.mean([t["duration_days"] for t in closed])),
        best=float(max(pnls)), worst=float(min(pnls)),
        max_consec_loss=mx,
    )


# ── the full panel ────────────────────────────────────────────────────────────

def compute_all_metrics(strat_ret: pd.Series, df: pd.DataFrame,
                        position: Optional[np.ndarray] = None,
                        td: int = TRADING_DAYS,
                        s_bull: int = 1, s_bear: int = 3) -> dict:
    """One dict with every metric. `strat_ret` is the position-scaled return series."""
    c = core_stats(strat_ret, td)
    e = extended_stats(strat_ret)
    t = trade_stats(build_trades(df, s_bull, s_bear))
    exposure = float(np.mean(position) * 100.0) if position is not None else np.nan
    out = {k: c[k] for k in ("cagr", "sharpe", "sortino", "max_dd", "calmar",
                             "ann_ret", "ann_std")}
    out.update(e)
    out.update(t)
    out["exposure"] = exposure
    return out
