"""Unit tests for Diversitas Lean strategy."""
import numpy as np
import pandas as pd
import pytest

from diversitas.config import LeanConfig
from diversitas.strategy import (
    run_strategy, compute_features, run_state_machine,
    S_BULL, S_NEUTRAL, S_BEAR,
)


def _synth_ohlcv(close: np.ndarray, start="2022-01-01") -> pd.DataFrame:
    n = len(close)
    idx = pd.date_range(start, periods=n, freq="D", tz="UTC")
    df = pd.DataFrame({
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.full(n, 1_000_000.0),
    }, index=idx)
    df.index.name = "time"
    return df


@pytest.fixture
def cfg():
    return LeanConfig(use_btc_filter=False)


# ---------- bull condition --------------------------------------------------

def test_bull_condition_requires_all_components(cfg):
    n = 500
    np.random.seed(7)
    trend = 100 * (1.001 ** np.arange(n))
    noise = 1.0 + 0.015 * np.random.randn(n)
    close = trend * noise
    df = _synth_ohlcv(close)
    feats = compute_features(df, btc_daily=None, cfg=cfg)

    valid = feats.dropna(subset=["ma_long"])
    when_bull = valid[valid["bull_condition"]]
    assert (when_bull["above_tl"]).all()
    assert (when_bull["above_ma_med"]).all()
    assert (when_bull["track_rising_window"]).all()
    assert (when_bull["regime_ok"]).all()


def test_bear_regime_blocks_bull(cfg):
    """In a sustained downtrend below the falling 200 MA, bull_condition
    must never fire."""
    n = 500
    close = 200 * (0.998 ** np.arange(n))
    df = _synth_ohlcv(close)
    feats = compute_features(df, btc_daily=None, cfg=cfg)
    valid = feats.dropna(subset=["ma_long"])
    # During bear_regime, regime_ok is False so bull_condition must be False
    in_bear = valid[valid["bear_regime"]]
    assert (in_bear["bull_condition"] == False).all()  # noqa: E712


# ---------- state machine ---------------------------------------------------

def test_uptrend_triggers_bull(cfg):
    n = 500
    np.random.seed(10)
    trend = 100 * (1.001 ** np.arange(n))
    noise = 1.0 + 0.02 * np.random.randn(n)
    df = _synth_ohlcv(trend * noise)
    result = run_strategy(df, btc_daily=None, config=cfg)
    sigs = result.df["signal_state"].dropna()
    assert (sigs == S_BULL).any()


def test_downtrend_stays_bear(cfg):
    n = 500
    close = 200 * (0.998 ** np.arange(n))
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg)
    sigs = result.df["signal_state"].dropna()
    assert (sigs == S_BEAR).all()


def test_state_codes_valid(cfg):
    n = 400
    np.random.seed(1)
    close = 100 + np.cumsum(np.random.randn(n))
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg)
    for col in ("signal_state", "display_state"):
        vals = set(result.df[col].unique())
        assert vals.issubset({S_BULL, S_NEUTRAL, S_BEAR})


def test_blowoff_triggers_bear_from_bull(cfg):
    n = 300
    base = np.linspace(100, 130, 200)
    spike = 130 * (1.05 ** np.arange(100))
    close = np.concatenate([base, spike])
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg)
    last_state = int(result.df["signal_state"].iloc[-1])
    assert last_state == S_BEAR


def test_reentry_lock_respected(cfg):
    """Re-entry to BULL after any signal change must be ≥ reentry_hold bars."""
    n = 600
    np.random.seed(3)
    close = 100 + np.cumsum(np.random.randn(n) * 1.5)
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg)
    transitions = result.df[result.df["signal_changed"]]
    bull_dates = transitions[transitions["signal_state"] == S_BULL].index.tolist()
    for prev_ts, next_ts in zip(bull_dates[:-1], bull_dates[1:]):
        gap = (next_ts - prev_ts).days
        assert gap >= cfg.reentry_hold, f"Re-entry too soon: {prev_ts} -> {next_ts}"


def test_confirm_bars_enforced(cfg):
    """BULL only fires when bull_hold ≥ confirm_bars at the transition bar."""
    n = 500
    np.random.seed(4)
    close = 100 + np.cumsum(np.random.randn(n))
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg)
    bull_bars = result.df[
        (result.df["signal_changed"]) & (result.df["signal_state"] == S_BULL)
    ]
    assert (bull_bars["bull_hold"] >= cfg.confirm_bars).all()


def test_bars_since_signal_resets_on_both_directions(cfg):
    """Lean key difference vs Full: bars_since_signal resets on BOTH directions."""
    n = 500
    np.random.seed(5)
    close = 100 + np.cumsum(np.random.randn(n) * 1.5)
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg)
    transitions = result.df[result.df["signal_changed"]]
    # On every transition bar, bars_since_signal should be 0
    assert (transitions["bars_since_signal"] == 0).all()


def test_alloc_zero_when_bear(cfg):
    n = 500
    close = 200 * (0.998 ** np.arange(n))
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg)
    # When BEAR, alloc must be 0
    bear_rows = result.df[result.df["signal_state"] == S_BEAR]
    assert (bear_rows["target_alloc"] == 0.0).all()


def test_alloc_capped_at_100(cfg):
    n = 400
    np.random.seed(9)
    close = 100 + np.cumsum(np.random.randn(n) * 0.3)
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg)
    assert (result.df["target_alloc"] <= 100.0).all()


def test_summary_has_required_keys(cfg):
    n = 400
    np.random.seed(6)
    close = 100 + np.cumsum(np.random.randn(n))
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg)
    required = {
        "signal", "regime", "ma_long_status", "trackline", "dist_pct",
        "annual_vol", "target_alloc", "close", "time", "above_ma_med",
    }
    assert required.issubset(set(result.summary))
