"""Strategy 3 of 3 — allocation across sleeves and across the two books.

Three layers, each usable alone, each answering a different question. Keeping
them separate matters: if they are fused into one function and the result is
good, nobody can say which layer earned it.

  `overlay_book`   keep the strategic weights, modulate each sleeve by its own
                   trend signal, leave the rest in cash. The conservative
                   design: the book you chose is still the book you hold.
  `rotate_within`  drop the strategic weights, hold the top-k sleeves by
                   momentum. The aggressive design, and the direct port of
                   `momentum/diversitas/rotation.py`.
  `dual_book`      the brief's "dual rotation": hold Portfolio 1 or Portfolio 2
                   or cash, on absolute plus relative momentum.

Cash is not a free parameter. In `cash_rate` it is the ECB deposit facility if
you supply it, and zero otherwise. Zero is conservative from 2015-2022 and
badly wrong from 2023, when cash paid 3-4 %: a rotation strategy that sits in
cash for a year and is credited 0 % is being under-measured, and a strategy that
is credited a 2026 rate over the whole history is being over-measured. Supply
the real series.

No look-ahead anywhere: every weight applied on day t is computed from data up
to t-1 via `.shift(1)`, and the rebalance calendar only ever holds a stale
weight forward, never a future one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

from shared import indicators as ind
from shared.costs import net_returns
from .config import DEFAULT_CONFIG, ETFConfig
from .strategy import S_BULL, run_strategy


@dataclass
class RotationResult:
    returns: pd.Series          # daily portfolio return, net of cost
    gross: pd.Series            # before cost, so the fee drag is visible
    weights: pd.DataFrame       # per-sleeve weight actually held
    equity: pd.Series
    cash_weight: pd.Series
    turnover: pd.Series
    meta: dict = field(default_factory=dict)


# ── shared plumbing ───────────────────────────────────────────────────────────

def sleeve_positions(frames: Dict[str, pd.DataFrame],
                     cfg: ETFConfig = DEFAULT_CONFIG,
                     per_sleeve_cfg: Optional[Dict[str, ETFConfig]] = None
                     ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the trend strategy on each sleeve.

    Returns `(position, strength)`, both already lagged one bar. Position is the
    fraction of that sleeve's own allocation to hold; strength is the ranking
    input for `rotate_within`, expressed in ATR units so a bond sleeve and a
    small-cap sleeve are on the same scale — ranking on `dist_pct` would put the
    most volatile sleeve on top every day, which is a volatility bet wearing a
    momentum label.
    """
    pos, strength = {}, {}
    for key, daily in frames.items():
        c = (per_sleeve_cfg or {}).get(key, cfg)
        df = run_strategy(daily, config=c).df
        pos[key] = (df["target_alloc"] / 100.0).shift(1).fillna(0.0)
        bull = (df["signal_state"] == S_BULL).astype(float)
        strength[key] = (bull + df["dist_atr"].clip(lower=0.0).fillna(0.0) / 5.0).shift(1)
    return pd.DataFrame(pos), pd.DataFrame(strength)


def _hold_between_rebalances(w: pd.DataFrame, every: int) -> pd.DataFrame:
    """Set target weights only every `every` bars; carry them in between.

    Carrying, not re-deriving: between rebalances the held weights drift with
    price, and pretending they stay at target invents trades that never happened
    and charges for them. This returns the *target*; `_drifted` applies the drift.
    """
    if every <= 1:
        return w
    keep = np.zeros(len(w), dtype=bool)
    keep[::every] = True
    return w.where(pd.Series(keep, index=w.index), other=np.nan).ffill().fillna(0.0)


def _drifted(target: pd.DataFrame, rets: pd.DataFrame, every: int
             ) -> tuple[pd.DataFrame, pd.Series]:
    """Actual held weights once drift between rebalances is respected, plus the
    turnover that was really traded.

    This is the ETF-side equivalent of the point `shared/costs.py` makes for the
    crypto sleeve: turnover is what you *traded*, and a position that grew
    because the price rose was not traded. Charging `weights.diff()` on a
    monthly-rebalanced book overstates cost by roughly the drift, every day.
    """
    idx = target.index
    cols = target.columns
    held = np.zeros((len(idx), len(cols)))
    trade = np.zeros(len(idx))
    cur = np.zeros(len(cols))
    R = rets.reindex(idx)[cols].fillna(0.0).to_numpy()
    T = target[cols].to_numpy()
    for i in range(len(idx)):
        if i == 0 or (every <= 1) or (i % every == 0):
            trade[i] = np.abs(T[i] - cur).sum()
            cur = T[i].copy()
        held[i] = cur
        cur = cur * (1.0 + R[i])          # drift into tomorrow
    return (pd.DataFrame(held, index=idx, columns=cols),
            pd.Series(trade, index=idx))


def _fees(cfg: ETFConfig, keys: Sequence[str]) -> pd.Series:
    return pd.Series({k: cfg.fee_overrides.get(k, cfg.fee_per_side_pct) for k in keys})


def _cash_series(index: pd.DatetimeIndex, cash_rate: Optional[pd.Series],
                 trading_days: int) -> pd.Series:
    """Daily cash return. `cash_rate` is an annual percentage series."""
    if cash_rate is None:
        return pd.Series(0.0, index=index)
    r = cash_rate.reindex(index.union(cash_rate.index)).ffill().reindex(index).fillna(0.0)
    return r / 100.0 / trading_days


# ── layer 1: strategic weights with a trend overlay ───────────────────────────

def overlay_book(frames: Dict[str, pd.DataFrame], weights: Dict[str, float],
                 cfg: ETFConfig = DEFAULT_CONFIG, rebalance_every: int = 21,
                 cash_rate: Optional[pd.Series] = None,
                 per_sleeve_cfg: Optional[Dict[str, ETFConfig]] = None
                 ) -> RotationResult:
    """Hold `weights[k] x position[k]` in each sleeve; the remainder in cash.

    The strategic allocation is preserved — nothing is ever overweighted beyond
    its target — so the only thing the signal can do is take risk off. That makes
    the comparison against buy-and-hold clean: any difference is the overlay's
    doing, not a different book.
    """
    pos, _ = sleeve_positions(frames, cfg, per_sleeve_cfg)
    keys = [k for k in weights if k in pos.columns]
    pos = pos[keys].dropna(how="all")
    px = pd.DataFrame({k: frames[k]["close"] for k in keys}).reindex(pos.index)
    rets = px.pct_change().fillna(0.0)

    w_target = pos.mul(pd.Series({k: weights[k] for k in keys}), axis=1)
    w_target = _hold_between_rebalances(w_target, rebalance_every)
    held, traded = _drifted(w_target, rets, rebalance_every)

    fee = _fees(cfg, keys) / 100.0
    gross = (held * rets).sum(axis=1)
    cash_w = (1.0 - held.sum(axis=1)).clip(lower=0.0)
    gross = gross + cash_w * _cash_series(pos.index, cash_rate, cfg.trading_days)
    # Per-sleeve cost: traded fraction of each sleeve times that sleeve's fee.
    per_sleeve_trade = w_target.diff().abs().fillna(0.0)
    per_sleeve_trade.iloc[0] = 0.0
    cost = (per_sleeve_trade * fee).sum(axis=1)
    net = gross - cost

    return RotationResult(returns=net, gross=gross, weights=held,
                          equity=(1 + net).cumprod(), cash_weight=cash_w,
                          turnover=traded,
                          meta=dict(layer="overlay_book", rebalance_every=rebalance_every,
                                    keys=keys, weights=dict(weights),
                                    ann_turnover=float(traded.sum() / (len(traded) / cfg.trading_days))))


# ── layer 2: cross-sectional rotation inside one book ─────────────────────────

def rotate_within(frames: Dict[str, pd.DataFrame], cfg: ETFConfig = DEFAULT_CONFIG,
                  k: int = 2, min_strength: float = 1.0, rebalance_every: int = 21,
                  cash_rate: Optional[pd.Series] = None) -> RotationResult:
    """Equal-weight the top-`k` sleeves by lagged signal strength; rest in cash.

    Direct port of `momentum/diversitas/rotation.py`, with two changes forced by
    the asset class: ranking is on `dist_atr` rather than `dist_pct` (see
    `sleeve_positions`), and the default rebalance is monthly rather than weekly
    because an equity book cannot pay weekly turnover out of a 12 % volatility
    budget. Both are assumptions to be tested, not results.
    """
    pos, strength = sleeve_positions(frames, cfg)
    keys = list(pos.columns)
    px = pd.DataFrame({key: frames[key]["close"] for key in keys}).reindex(pos.index)
    rets = px.pct_change().fillna(0.0)

    elig = strength.where(strength >= min_strength)
    ranks = elig.rank(axis=1, ascending=False, method="first")
    mask = ranks.le(k) & elig.notna()
    n_held = mask.sum(axis=1)
    w = mask.div(n_held.replace(0, np.nan), axis=0).fillna(0.0) * pos

    w_target = _hold_between_rebalances(w, rebalance_every)
    held, traded = _drifted(w_target, rets, rebalance_every)

    fee = _fees(cfg, keys) / 100.0
    gross = (held * rets).sum(axis=1)
    cash_w = (1.0 - held.sum(axis=1)).clip(lower=0.0)
    gross = gross + cash_w * _cash_series(pos.index, cash_rate, cfg.trading_days)
    per_sleeve_trade = w_target.diff().abs().fillna(0.0)
    per_sleeve_trade.iloc[0] = 0.0
    net = gross - (per_sleeve_trade * fee).sum(axis=1)

    return RotationResult(returns=net, gross=gross, weights=held,
                          equity=(1 + net).cumprod(), cash_weight=cash_w,
                          turnover=traded,
                          meta=dict(layer="rotate_within", k=k, min_strength=min_strength,
                                    rebalance_every=rebalance_every, keys=keys))


# ── layer 3: rotation between the two books ───────────────────────────────────

def dual_book(book_returns: Dict[str, pd.Series], lookback: int = 252,
              vol_lookback: int = 60, risk_adjusted: bool = True,
              rebalance_every: int = 21, cash_rate: Optional[pd.Series] = None,
              trading_days: int = 252, fee_per_side_pct: float = 0.20,
              blend: bool = False) -> RotationResult:
    """Absolute + relative momentum across the books, with cash as the floor.

    `book_returns` are the *buy-and-hold* daily returns of each book (or of any
    two candidate allocations). Each month:

      1. score each book by its trailing `lookback` return, divided by trailing
         volatility when `risk_adjusted` — without that division the comparison
         is between a 16 %-vol book and a 6 %-vol book, and the equity book wins
         almost always for the trivial reason that it carries more risk;
      2. drop any book whose score is below cash (absolute momentum);
      3. hold the survivor with the higher score, or split them when `blend`.

    Dual momentum's published edge comes almost entirely from step 2 — the
    absolute filter — not from step 3. That is worth remembering when the
    relative part looks clever in a backtest.
    """
    names = list(book_returns)
    R = pd.DataFrame(book_returns).dropna()
    eq = (1 + R).cumprod()
    cash_d = _cash_series(R.index, cash_rate, trading_days)
    cash_cum = (1 + cash_d).cumprod()

    mom = eq / eq.shift(lookback) - 1.0
    cash_mom = cash_cum / cash_cum.shift(lookback) - 1.0
    if risk_adjusted:
        vol = R.rolling(vol_lookback, min_periods=vol_lookback // 2).std() * np.sqrt(trading_days)
        score = mom.div(vol.replace(0, np.nan))
        cash_score = pd.Series(np.where(cash_mom.abs() > 0, np.inf, 0.0), index=R.index)
        # A risk-adjusted score for cash is undefined (zero volatility). Compare
        # the raw excess instead: a book qualifies if its own return beat cash.
        qualifies = mom.sub(cash_mom, axis=0) > 0
    else:
        score = mom
        qualifies = mom.sub(cash_mom, axis=0) > 0

    score = score.where(qualifies)
    w = pd.DataFrame(0.0, index=R.index, columns=names)
    if blend:
        pos_score = score.clip(lower=0.0)
        tot = pos_score.sum(axis=1).replace(0, np.nan)
        w = pos_score.div(tot, axis=0).fillna(0.0)
    else:
        best = score.idxmax(axis=1)
        for nm in names:
            w[nm] = (best == nm).astype(float)
        w[score.isna().all(axis=1)] = 0.0
    w = w.shift(1).fillna(0.0)              # decide on t-1, hold on t

    w_target = _hold_between_rebalances(w, rebalance_every)
    held, traded = _drifted(w_target, R, rebalance_every)

    gross = (held * R).sum(axis=1)
    cash_w = (1.0 - held.sum(axis=1)).clip(lower=0.0)
    gross = gross + cash_w * cash_d
    trade_frac = w_target.diff().abs().sum(axis=1).fillna(0.0)
    trade_frac.iloc[0] = 0.0
    net = gross - trade_frac * (fee_per_side_pct / 100.0)

    return RotationResult(returns=net, gross=gross, weights=held,
                          equity=(1 + net).cumprod(), cash_weight=cash_w,
                          turnover=traded,
                          meta=dict(layer="dual_book", lookback=lookback,
                                    risk_adjusted=risk_adjusted, blend=blend,
                                    rebalance_every=rebalance_every, books=names))


def buy_and_hold(frames: Dict[str, pd.DataFrame], weights: Dict[str, float],
                 rebalance_every: int = 252, fee_per_side_pct: float = 0.20,
                 trading_days: int = 252) -> RotationResult:
    """The benchmark: the book, rebalanced on a calendar, nothing else.

    Rebalanced rather than left to drift, because that is what the strategic
    allocation actually prescribes, and because a drifting book slowly turns
    into 100 % of whatever won — which would flatter or damn the overlay for
    reasons that have nothing to do with the signal.
    """
    keys = [k for k in weights if k in frames]
    px = pd.DataFrame({k: frames[k]["close"] for k in keys}).dropna()
    rets = px.pct_change().fillna(0.0)
    target = pd.DataFrame(
        np.tile(np.array([weights[k] for k in keys]), (len(px), 1)),
        index=px.index, columns=keys)
    target = _hold_between_rebalances(target, rebalance_every)
    held, traded = _drifted(target, rets, rebalance_every)
    gross = (held * rets).sum(axis=1)
    net = gross - traded * (fee_per_side_pct / 100.0)
    return RotationResult(returns=net, gross=gross, weights=held,
                          equity=(1 + net).cumprod(),
                          cash_weight=pd.Series(0.0, index=px.index),
                          turnover=traded,
                          meta=dict(layer="buy_and_hold", keys=keys,
                                    rebalance_every=rebalance_every))
