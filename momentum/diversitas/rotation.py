"""Cross-sectional rotation — production portfolio layer over the Momentum strategy.

The one robust structural improvement from the validation campaign: instead of trading
every asset equally, hold only the K strongest-signal assets, with a graded (RSI-scaled)
Momentum sleeve, rebalanced weekly. It *adapts across regimes* (rotates toward whichever
assets are trending) rather than tuning fixed parameters — which the campaign proved does
not generalize out-of-sample.

Honest profile (calibrated, not overclaimed):
  - Its edge is **drawdown control + bear robustness**, NOT beating a diversified hold on
    every window. Full-period design Calmar ≈1.58 vs equal-weight ≈1.07 and a strong bear
    hold-out (Sortino ~1.8 vs ~0), with max drawdown roughly halved — but it *loses* some
    calm bull windows (it concentrates / goes to cash and misses broad rallies), winning
    ~2/5 design windows on Sortino. Position it as risk-controlled, not a universal winner.
  - **Turnover is high and fee-sensitive**: ~1500%/yr at weekly rebalance (was ~3400% daily).
    All figures should be quoted net of fees; needs low-cost execution.

Design invariants:
  - No look-ahead: the day-t weight uses only signal strength known at t-1 (shift(1)).
  - Pine port untouched: this consumes `run_strategy(...).df`, nothing more.
  - Graded sleeve: in-market position is scaled by RSI conviction (RSI 50→0.5, 70+→1.0),
    which cut rotation's drawdown from −46% to −18% in testing while raising return.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .config import MomentumConfig, DEFAULT_CONFIG
from .strategy import run_strategy, S_BULL


@dataclass
class RotationResult:
    returns: pd.Series            # daily portfolio return
    weights: pd.DataFrame         # per-asset weight over time (rows=dates, cols=assets)
    strength: pd.DataFrame        # per-asset signal strength (lagged), for inspection
    equity: pd.Series             # cumulative equity (starts at 1.0)
    held_count: pd.Series         # number of assets held each day
    assets: list


def _sleeve_returns(df: pd.DataFrame, close: pd.Series, graded: bool) -> pd.Series:
    """Graded Momentum sleeve return for one asset: next-bar vol-scaled position,
    optionally scaled by RSI conviction. Uses shift(1) — no look-ahead."""
    ret = close.pct_change().fillna(0.0)
    pos = df["target_alloc"].shift(1).fillna(0.0) / 100.0
    if graded:
        conv = ((df["rsi"] - 50.0) / 20.0).clip(0.5, 1.0).shift(1).fillna(1.0)
        pos = pos * conv
    return pd.Series(ret.to_numpy() * pos.to_numpy(), index=df.index)


def _strength(df: pd.DataFrame) -> pd.Series:
    """Signal strength for ranking: BULL flag + normalized distance above the
    trackline, lagged one bar so day-t ranking uses only t-1 information.

    Design note: this uses the Momentum signal ONLY (self-contained; no cross-variant
    coupling). The validation campaign ranked by lean+momentum BULL votes; this
    momentum-only version is **design-set-equivalent** (Calmar 1.51 vs 1.49) and
    robust across the walk-forward OOS blocks (beats equal-weight on 3/5 design blocks
    + hold-out), so the simplification does not add overfitting risk — it removes it.
    """
    bull = (df["signal_state"] == S_BULL).astype(float)
    dist = (df["dist_pct"] / 20.0).clip(lower=0.0)
    return (bull + dist).shift(1)


def run_rotation(daily_by_asset: Dict[str, pd.DataFrame],
                 config: MomentumConfig = DEFAULT_CONFIG,
                 k: int = 3, graded: bool = True, min_strength: float = 1.0,
                 rebalance_every: int = 7,
                 btc_daily: Optional[pd.DataFrame] = None) -> RotationResult:
    """Run the Momentum strategy on each asset, then each day hold the top-`k`
    assets by (lagged) signal strength with strength ≥ `min_strength`, equal weight;
    the rest in cash. Returns portfolio returns + weights aligned on the union index.

    `rebalance_every` (days) holds the target weights between rebalances. Default is
    **weekly (7)**: on the leakage-safe design/hold-out split it beats daily on the
    design set (Calmar 1.58 vs 1.19 net of 0.15%/side) without degrading the hold-out
    (1.35 vs 1.33) and roughly halves turnover (~1500% vs ~3400%). Daily overtrades on
    RSI noise; biweekly (14) looks better in-sample but overfits (hold-out Calmar drops
    to 0.87). Weights are set only from lagged information → no look-ahead at any cadence.
    """
    assets = list(daily_by_asset.keys())
    sleeves, strengths = {}, {}
    for a, daily in daily_by_asset.items():
        df = run_strategy(daily, btc_daily=btc_daily, config=config).df
        sleeves[a] = _sleeve_returns(df, daily["close"], graded).rename(a)
        strengths[a] = _strength(df).rename(a)

    idx = None
    for s in strengths.values():
        idx = s.index if idx is None else idx.union(s.index)
    S = pd.DataFrame(strengths).reindex(idx)
    R = pd.DataFrame(sleeves).reindex(idx).fillna(0.0)

    # eligibility: strength must exist and clear the floor
    elig = S.where(S >= min_strength)
    # rank per row, keep the top-k eligible
    ranks = elig.rank(axis=1, ascending=False, method="first")
    held_mask = ranks.le(k) & elig.notna()
    held_count = held_mask.sum(axis=1)
    weights = held_mask.div(held_count.replace(0, np.nan), axis=0).fillna(0.0)

    if rebalance_every > 1:
        # keep only every Nth row's target weights; hold (ffill) in between
        keep = np.zeros(len(weights), dtype=bool)
        keep[::rebalance_every] = True
        weights = weights.where(pd.Series(keep, index=weights.index), other=np.nan).ffill().fillna(0.0)
        held_count = (weights > 0).sum(axis=1)

    port = (weights * R).sum(axis=1)
    equity = (1.0 + port).cumprod()
    return RotationResult(returns=port, weights=weights, strength=S,
                          equity=equity, held_count=held_count.astype(int),
                          assets=assets)


def current_allocation(daily_by_asset: Dict[str, pd.DataFrame],
                       config: MomentumConfig = DEFAULT_CONFIG,
                       k: int = 3, graded: bool = True,
                       min_strength: float = 1.0) -> dict:
    """Today's target allocation for live / paper trading, computed from the latest
    bar (act on the next bar → no look-ahead). Returns a dict with the effective
    per-asset weight (fraction of capital), a CASH remainder, per-asset signal
    detail, and the held set. Effective weight = (1/held_count) × momentum position
    × RSI conviction — i.e. what the backtest actually holds."""
    detail, strengths = {}, {}
    for a, daily in daily_by_asset.items():
        last = run_strategy(daily, config=config).df.iloc[-1]
        bull = 1.0 if last["signal_state"] == S_BULL else 0.0
        strengths[a] = bull + max(float(last["dist_pct"]) / 20.0, 0.0)
        conv = float(np.clip((last["rsi"] - 50.0) / 20.0, 0.5, 1.0)) if graded else 1.0
        detail[a] = dict(state="BULL" if bull else "BEAR",
                         strength=round(strengths[a], 3),
                         dist_pct=round(float(last["dist_pct"]), 2),
                         rsi=round(float(last["rsi"]), 1),
                         momentum_pos=round(float(last["target_alloc"]) / 100.0 * conv, 4))
    elig = {a: s for a, s in strengths.items() if s >= min_strength}
    held = sorted(elig, key=elig.get, reverse=True)[:k]
    hc = len(held)
    alloc = {a: (round((1.0 / hc) * detail[a]["momentum_pos"], 4) if a in held else 0.0)
             for a in daily_by_asset}
    alloc["CASH"] = round(max(0.0, 1.0 - sum(alloc.values())), 4)
    return dict(allocation=alloc, held=held, detail=detail,
                k=k, graded=graded, min_strength=min_strength)
