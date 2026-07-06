"""Regression + behaviour tests for the optional Lean Donchian confirmation."""
import numpy as np
import pandas as pd

from diversitas.config import LeanConfig
from diversitas.strategy import run_strategy


def _synth(seed=1, n=900):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    close = 100 * np.exp(np.linspace(0, 1, n) + np.cumsum(rng.normal(0, 0.03, n)))
    close = pd.Series(close, index=idx)
    return pd.DataFrame({"open": close, "high": close * 1.02, "low": close * 0.98,
                         "close": close, "volume": rng.uniform(1e6, 5e6, n)}, index=idx)


def test_default_is_donchian_off_and_identical():
    daily = _synth()
    d_default = run_strategy(daily, config=LeanConfig()).df
    d_off = run_strategy(daily, config=LeanConfig(use_donchian=False)).df
    # a-priori Lean must be bit-identical whether the flag is defaulted or set False
    assert np.array_equal(d_default["signal_state"].values, d_off["signal_state"].values)
    assert np.allclose(d_default["target_alloc"].values, d_off["target_alloc"].values)
    assert (d_default["donchian_ok"] == True).all()   # noqa: E712 — factor is all-True when off


def test_donchian_on_is_a_stricter_filter():
    daily = _synth()
    d_off = run_strategy(daily, config=LeanConfig(use_donchian=False)).df
    d_on = run_strategy(daily, config=LeanConfig(use_donchian=True)).df
    assert not np.array_equal(d_off["signal_state"].values, d_on["signal_state"].values)
    # an extra AND-gate can only reduce (never increase) the number of BULL bars
    assert (d_on["signal_state"] == 1).sum() <= (d_off["signal_state"] == 1).sum()
