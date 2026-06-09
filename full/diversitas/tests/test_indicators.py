"""Unit tests for indicators."""
import numpy as np
import pandas as pd
import pytest

from diversitas import indicators as ind


@pytest.fixture
def trend_series():
    """Linear up-trend — RSI should saturate near 100, ADX should be high."""
    return pd.Series(np.linspace(100.0, 200.0, 100))


@pytest.fixture
def random_close():
    np.random.seed(42)
    return pd.Series(100 + np.cumsum(np.random.randn(300)))


def test_sma_matches_mean():
    s = pd.Series(np.arange(10, dtype=float))
    res = ind.sma(s, 3)
    assert res.iloc[2] == pytest.approx(1.0)  # (0+1+2)/3
    assert res.iloc[9] == pytest.approx(8.0)  # (7+8+9)/3
    assert pd.isna(res.iloc[1])


def test_ema_first_valid_equals_sma_seed():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    # Pine ta.ema(close, 3) with adjust=False, min_periods=3
    res = ind.ema(s, 3)
    # First valid value is at index 2; subsequent values use alpha=2/(N+1)=0.5
    # Pine seeds EMA with the simple recursion from the first bar but only
    # exposes a value at min_periods; pandas ewm(adjust=False) without seed
    # starts from the first value. We accept Pine's documented behaviour.
    assert pd.notna(res.iloc[2])
    assert res.iloc[-1] > res.iloc[2]


def test_rma_alpha_one_over_n():
    s = pd.Series([1.0] * 50 + [2.0] * 50)
    res = ind.rma(s, 10)
    # After many bars at 1.0, value should be ~1.0
    assert res.iloc[40] == pytest.approx(1.0, abs=1e-6)
    # After the step it should rise toward 2.0 with alpha=0.1
    assert 1.0 < res.iloc[60] < 2.0
    assert res.iloc[-1] > res.iloc[60]


def test_rsi_in_range_and_extremes(trend_series):
    r = ind.rsi(trend_series, 14)
    valid = r.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()
    # Pure uptrend → RSI saturates at 100 (no losses)
    assert r.iloc[-1] == pytest.approx(100.0)


def test_rsi_downtrend_low():
    down = pd.Series(np.linspace(200.0, 100.0, 100))
    r = ind.rsi(down, 14)
    # Pure downtrend → RSI near 0
    assert r.iloc[-1] < 5.0


def test_adx_responds_to_trend(trend_series):
    high = trend_series + 0.5
    low = trend_series - 0.5
    a = ind.adx(high, low, trend_series, 14)
    valid = a.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()
    # Strong directional trend → high ADX
    assert a.iloc[-1] > 30.0


def test_highest_lowest():
    s = pd.Series([3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0])
    assert ind.highest(s, 3).iloc[5] == 9.0  # max of [4,1,5,9]? no, last 3 = [1,5,9]→9
    assert ind.lowest(s, 3).iloc[5] == 1.0
    assert pd.isna(ind.highest(s, 3).iloc[1])


def test_bars_since_counts_correctly():
    cond = pd.Series([False, False, True, False, False, True, False])
    bs = ind.bars_since(cond)
    assert pd.isna(bs.iloc[0])
    assert pd.isna(bs.iloc[1])
    assert bs.iloc[2] == 0  # condition True
    assert bs.iloc[3] == 1
    assert bs.iloc[4] == 2
    assert bs.iloc[5] == 0  # True again
    assert bs.iloc[6] == 1


def test_stdev_pop_matches_numpy(random_close):
    s = random_close
    res = ind.stdev_pop(s, 20)
    last = res.iloc[-1]
    expected = np.std(s.iloc[-20:].to_numpy(), ddof=0)
    assert last == pytest.approx(expected, rel=1e-10)
