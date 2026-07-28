"""Indicator warm-up must be trimmed before any metric is computed.

The bug this locks down: while `ma_long` is NaN, `close > NaN` and `NaN < NaN` both
evaluate to False, so `bear_regime` collapses to False and `regime_ok` to True — the
regime block is silently disabled instead of being undefined. Nothing downstream can
detect it, so it has to be caught here.
"""
import numpy as np
import pandas as pd
import pytest

from testing.scripts import engine


def _synthetic(n=600, seed=0):
    """A price path long enough for SMA200 to become valid."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    return pd.DataFrame({"open": close, "high": close * 1.01,
                         "low": close * 0.99, "close": close}, index=idx)


def test_lean_warmup_is_the_200_sma():
    daily = _synthetic()
    raw = engine.run("lean", daily, trim_warmup=False)
    assert engine.warmup_bars(raw) == 199            # SMA200 first valid at index 199
    assert raw["ma_long"].iloc[:199].isna().all()
    assert pd.notna(raw["ma_long"].iloc[199])


def test_run_trims_by_default():
    daily = _synthetic()
    trimmed = engine.run("lean", daily)
    raw = engine.run("lean", daily, trim_warmup=False)
    assert len(raw) - len(trimmed) == 199
    assert trimmed.index[0] == raw.index[199]


def test_no_undefined_indicator_survives_the_trim():
    """Every warm-up column is fully defined on the trimmed frame."""
    daily = _synthetic()
    trimmed = engine.run("lean", daily)
    for col in engine._WARMUP_COLS:
        if col in trimmed.columns:
            assert trimmed[col].notna().all(), f"{col} still has NaNs after trimming"


def test_regime_block_is_silently_disabled_during_warmup():
    """Documents the actual failure mode — regime_ok is True, not NaN, while
    ma_long is undefined. If this ever starts failing, the strategy changed."""
    daily = _synthetic()
    raw = engine.run("lean", daily, trim_warmup=False)
    warm = raw.iloc[:199]
    assert warm["ma_long"].isna().all()
    assert not warm["bear_regime"].any()             # never blocks …
    assert warm["regime_ok"].all()                   # … i.e. always permissive


def test_state_machine_outputs_do_not_drive_the_trim():
    """`entry_peak`/`trail_stop` are NaN until the first trade; using them would
    throw away real history. Momentum's warm-up must stay at its SMA100."""
    daily = _synthetic()
    raw = engine.run("momentum", daily, trim_warmup=False)
    assert engine.warmup_bars(raw) == 99
    assert "entry_peak" not in engine._WARMUP_COLS


def test_run_overlay_trims_too():
    daily = _synthetic()
    trimmed = engine.run_overlay("lean", daily, None)
    raw = engine.run_overlay("lean", daily, None, trim_warmup=False)
    assert len(raw) - len(trimmed) == 199


def test_history_shorter_than_lookback_raises():
    daily = _synthetic(n=120)                        # SMA200 never becomes valid
    raw = engine.run("lean", daily, trim_warmup=False)
    with pytest.raises(ValueError, match="NaN over the whole sample"):
        engine.warmup_bars(raw)
