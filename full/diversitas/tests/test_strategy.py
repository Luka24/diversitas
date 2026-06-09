"""Unit tests for strategy state machine + feature pipeline."""
import numpy as np
import pandas as pd
import pytest

from diversitas.config import Config
from diversitas.strategy import (
    run_strategy, compute_features, run_state_machines,
    S_BULL, S_NEUTRAL, S_BEAR,
)


def _synth_ohlcv(close: np.ndarray, start="2023-01-01") -> pd.DataFrame:
    """Build a synthetic OHLCV frame from a close path."""
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
def cfg_no_btc():
    return Config(use_btc_filter=False, skip_weekend=False)


def test_uptrend_eventually_triggers_bull(cfg_no_btc):
    """A long uptrend with mild pullbacks should produce a BULL signal.

    A *perfectly* linear up-path never has a lower low and so structure_bull
    is undefined — the realistic case has small pullbacks, which the strategy
    needs to recognise structure.
    """
    n = 500
    np.random.seed(10)
    trend = 100 * (1.001 ** np.arange(n))
    noise = 1.0 + 0.02 * np.random.randn(n)  # +/- 2 % daily wobble
    close = trend * noise
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg_no_btc)
    sigs = result.df["signal_state"].dropna()
    assert (sigs == S_BULL).any(), "Uptrend with normal noise should produce BULL"


def test_downtrend_stays_bear(cfg_no_btc):
    """A sustained downtrend should never go BULL."""
    n = 500
    close = 200 * (0.999 ** np.arange(n))
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg_no_btc)
    sigs = result.df["signal_state"].dropna()
    assert (sigs == S_BEAR).all()


def test_state_codes_valid(cfg_no_btc):
    """All state values are in {1, 2, 3}."""
    n = 400
    np.random.seed(1)
    close = 100 + np.cumsum(np.random.randn(n))
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg_no_btc)
    for col in ("raw_state", "display_state", "signal_state"):
        vals = set(result.df[col].unique())
        assert vals.issubset({S_BULL, S_NEUTRAL, S_BEAR}), f"{col}: {vals}"


def test_conviction_bounded(cfg_no_btc):
    """raw_conviction must lie in [0, 100] given valid weights."""
    n = 500
    np.random.seed(2)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = _synth_ohlcv(close)
    feats = compute_features(df, btc_daily=None, cfg=cfg_no_btc)
    raw = feats["raw_conviction"].dropna()
    assert (raw >= 0).all() and (raw <= 100).all()


def test_reentry_lock_respected(cfg_no_btc):
    """After a BULL→BEAR flip, the next BULL must be at least reentry_hold
    bars away (counting from the BULL bar, not the BEAR bar)."""
    n = 600
    np.random.seed(3)
    close = 100 + np.cumsum(np.random.randn(n) * 1.5)
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg_no_btc)
    transitions = result.df[result.df["signal_changed"]]
    bull_dates = transitions[transitions["signal_state"] == S_BULL].index.tolist()
    # consecutive BULL re-entries must be ≥ reentry_hold days apart
    for a, b in zip(bull_dates[:-1], bull_dates[1:]):
        assert (b - a).days >= cfg_no_btc.reentry_hold, (
            f"Re-entry lock violated: {a} → {b}"
        )


def test_confirm_bars_enforced(cfg_no_btc):
    """BULL must require raw_hold >= confirm_bars."""
    n = 500
    np.random.seed(4)
    close = 100 + np.cumsum(np.random.randn(n))
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg_no_btc)
    # On every BULL transition, raw_hold (computed AT that bar) must be ≥ confirm_bars
    bull_bars = result.df[
        (result.df["signal_changed"]) & (result.df["signal_state"] == S_BULL)
    ]
    assert (bull_bars["raw_hold"] >= cfg_no_btc.confirm_bars).all()


def test_blowoff_triggers_bear_from_bull(cfg_no_btc):
    """A blowoff pattern (extreme distance + RSI>80) while in BULL → BEAR."""
    # Construct a path: long uptrend then a parabolic spike
    n = 300
    base = np.linspace(100, 130, 200)
    spike = 130 * (1.05 ** np.arange(100))  # +5% per day
    close = np.concatenate([base, spike])
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg_no_btc)
    # Somewhere after the spike, signal should be BEAR even though we'd
    # normally be in BULL — because of blow-off or vol shock
    last_state = int(result.df["signal_state"].iloc[-1])
    assert last_state == S_BEAR, "Parabolic spike must end in BEAR"


def test_skip_weekend_blocks_transitions():
    """With skip_weekend=True, no state transition can happen on a Sat/Sun."""
    n = 400
    np.random.seed(5)
    close = 100 + np.cumsum(np.random.randn(n) * 2.0)
    df = _synth_ohlcv(close)
    cfg = Config(use_btc_filter=False, skip_weekend=True)
    result = run_strategy(df, btc_daily=None, config=cfg)
    weekend_changes = result.df[
        result.df["signal_changed"] & result.df["is_weekend"]
    ]
    assert len(weekend_changes) == 0


def test_summary_fields_present(cfg_no_btc):
    n = 400
    np.random.seed(6)
    close = 100 + np.cumsum(np.random.randn(n))
    df = _synth_ohlcv(close)
    result = run_strategy(df, btc_daily=None, config=cfg_no_btc)
    required = {
        "signal", "regime", "ma200_status", "threshold", "conviction",
        "trackline", "track_rising", "dist_pct", "trend_quality_pct",
        "annual_vol", "final_alloc", "close", "time",
    }
    assert required.issubset(set(result.summary)), (
        f"Missing: {required - set(result.summary)}"
    )
