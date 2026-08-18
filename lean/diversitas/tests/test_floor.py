"""The permanent 5 % floor: an exit sells 95 %, not 100 %.

The frozen reference in testing/ covers the SIGNAL series and is deliberately
blind to this, since the floor is a sizing decision layered on top rather than a
change to when the strategy trades. That leaves the floor uncovered, so it is
covered here.
"""
import numpy as np
import pandas as pd
import pytest

from diversitas.config import DEFAULT_CONFIG, LeanConfig
from diversitas.strategy import S_BULL, position, run_strategy
from shared.warmup import trim_warmup


@pytest.fixture(scope="module")
def df():
    rng = np.random.default_rng(5)
    n = 900
    idx = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    close = 100 * np.exp(np.linspace(0, 1, n) + np.cumsum(rng.normal(0, 0.03, n)))
    close = pd.Series(close, index=idx)
    raw = pd.DataFrame({"open": close, "high": close * 1.02, "low": close * 0.98,
                        "close": close, "volume": rng.uniform(1e6, 5e6, n)}, index=idx)
    return trim_warmup(run_strategy(raw, config=LeanConfig()).df)


def test_default_floor_is_five_percent():
    assert DEFAULT_CONFIG.bear_alloc_pct == 5.0


def test_an_exit_sells_ninety_five_percent(df):
    pos = position(df, LeanConfig())
    exits = pos.diff().dropna()
    exits = exits[exits < 0]
    assert len(exits) > 0
    assert np.allclose(exits.to_numpy(), -0.95)


def test_flat_holds_the_floor(df):
    pos = position(df, LeanConfig())
    bull = df["prev_signal_state"] == S_BULL
    assert pos[bull].eq(1.0).all()
    assert pos[~bull].eq(0.05).all()


def test_zero_floor_reproduces_the_old_behaviour(df):
    pos = position(df, LeanConfig(bear_alloc_pct=0.0))
    assert pos.equals((df["prev_signal_state"] == S_BULL).astype(float))


def test_position_lags_the_signal_by_one_bar(df):
    """The floor is new; the lag must not regress while adding it."""
    assert not position(df, LeanConfig(bear_alloc_pct=0.0)).equals(
        (df["signal_state"] == S_BULL).astype(float))


def test_run_keeps_the_untrimmed_frame():
    """Returns are differenced on this, so the first bar after the warm-up cut
    keeps a real return instead of a NaN that becomes zero."""
    import diversitas.dashboard as D
    cfg, daily, res = D._run.__wrapped__("BTC", 700, False)
    assert hasattr(res, "untrimmed")
    assert len(res.untrimmed) > len(res.df)
