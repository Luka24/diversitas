"""Tests for the production cross-sectional rotation layer."""
import numpy as np
import pandas as pd
import pytest

from diversitas.config import MomentumConfig
from diversitas.rotation import run_rotation, _strength, _sleeve_returns
from diversitas.strategy import run_strategy


def _synth(seed, n=800, start="2021-01-01"):
    """Synthetic OHLC with a trend + noise so the strategy produces signals."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="D", tz="UTC")
    drift = np.linspace(0, 1.2, n)
    close = 100 * np.exp(drift + np.cumsum(rng.normal(0, 0.03, n)))
    close = pd.Series(close, index=idx)
    high = close * (1 + rng.uniform(0, 0.02, n))
    low = close * (1 - rng.uniform(0, 0.02, n))
    return pd.DataFrame({"open": close.shift(1).fillna(close),
                         "high": high, "low": low, "close": close,
                         "volume": rng.uniform(1e6, 5e6, n)}, index=idx)


def _universe(n_assets=4):
    return {f"A{i}": _synth(i) for i in range(n_assets)}


def test_weights_sum_to_one_or_zero():
    res = run_rotation(_universe(4), k=3)
    ws = res.weights.sum(axis=1)
    # each day weights sum to ~1 (fully invested in held) or 0 (all cash)
    assert ((ws.sub(1.0).abs() < 1e-9) | (ws.abs() < 1e-9)).all()


def test_at_most_k_held():
    res = run_rotation(_universe(5), k=3)
    assert (res.held_count <= 3).all()


def test_k_ge_n_holds_all_eligible():
    uni = _universe(3)
    res = run_rotation(uni, k=10, rebalance_every=1)   # daily → held reflects same-day eligibility
    S = res.strength
    elig = (S >= 1.0).sum(axis=1)
    assert (res.held_count == elig).all()


def test_rebalance_reduces_turnover():
    uni = _universe(5)
    daily_r = run_rotation(uni, k=3, rebalance_every=1)
    weekly_r = run_rotation(uni, k=3, rebalance_every=7)
    to = lambda r: 0.5 * r.weights.diff().abs().sum(axis=1).sum()
    assert to(weekly_r) < to(daily_r)                  # weekly churns less


def test_rebalance_default_is_weekly():
    uni = _universe(4)
    assert np.allclose(run_rotation(uni, k=3).returns.values,
                       run_rotation(uni, k=3, rebalance_every=7).returns.values)


def test_no_lookahead_strength_is_lagged():
    df = run_strategy(_synth(0)).df
    s = _strength(df)
    # strength at t must equal the un-lagged score at t-1
    raw = (df["signal_state"].eq(1).astype(float) + (df["dist_pct"] / 20).clip(lower=0))
    assert np.allclose(s.dropna().values, raw.shift(1).dropna().reindex(s.dropna().index).values)


def test_future_change_does_not_affect_past_weights():
    uni = _universe(4)
    res_a = run_rotation(uni, k=2)
    uni2 = {a: d.copy() for a, d in uni.items()}
    uni2["A0"].iloc[-1, uni2["A0"].columns.get_loc("close")] *= 1.5   # perturb the future
    res_b = run_rotation(uni2, k=2)
    # weights before the last bar unchanged
    assert np.allclose(res_a.weights.iloc[:-1].values, res_b.weights.iloc[:-1].values)


def test_graded_reduces_or_equals_exposure():
    uni = _universe(3)
    g = run_rotation(uni, k=3, graded=True).returns
    ng = run_rotation(uni, k=3, graded=False).returns
    # graded scales positions by ≤1 conviction → its gross exposure never exceeds ungraded
    assert g.abs().sum() <= ng.abs().sum() + 1e-6
