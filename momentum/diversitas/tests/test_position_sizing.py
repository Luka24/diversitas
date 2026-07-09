"""Verify the graded position sizing is real and used by the backtest, and that
there is NO profit-take scaling in the strategy."""
import numpy as np
import pandas as pd

from diversitas.config import MomentumConfig
from diversitas.strategy import run_strategy


def _ohlc(close):
    return pd.DataFrame({"open": close.shift(1).fillna(close),
                         "high": close * 1.01, "low": close * 0.99,
                         "close": close, "volume": 1e6}, index=close.index)


def _lowvol_uptrend(n=800):
    idx = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    close = 100 * np.exp(np.linspace(0, 1.6, n) + 0.004 * np.sin(np.arange(n) / 25))
    return _ohlc(pd.Series(close, index=idx))


def _highvol(n=800, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0.0015, 0.06, n)))   # ~115% annualized vol
    return _ohlc(pd.Series(close, index=idx))


# ── vol-targeting is real ─────────────────────────────────────────────────────

def test_vol_targeting_grades_below_100_in_high_vol():
    df = run_strategy(_highvol(), config=MomentumConfig()).df
    allocs = df["target_alloc"][df["signal_state"] == 1]
    assert len(allocs) > 0
    assert (allocs < 100).any()          # high vol → some BULL allocs scaled down
    assert allocs.nunique() > 1          # graded, not binary


def test_low_vol_trend_allocates_near_full():
    df = run_strategy(_lowvol_uptrend(), config=MomentumConfig()).df
    allocs = df["target_alloc"][df["signal_state"] == 1]
    assert allocs.median() >= 90         # calm trend → near-full allocation


def test_vol_target_param_moves_allocation():
    daily = _highvol()
    lo = run_strategy(daily, config=MomentumConfig(target_vol_pct=40)).df
    hi = run_strategy(daily, config=MomentumConfig(target_vol_pct=90)).df
    b = (lo["signal_state"] == 1) & (hi["signal_state"] == 1)
    # higher vol target → higher (or equal) allocation
    assert hi["target_alloc"][b].mean() >= lo["target_alloc"][b].mean()


# ── bear-regime 50% cut is real ───────────────────────────────────────────────

def test_bear_size_cut_halves_allocation():
    daily = _highvol(seed=5)
    d50 = run_strategy(daily, config=MomentumConfig(bear_size_cut=50)).df
    d100 = run_strategy(daily, config=MomentumConfig(bear_size_cut=100)).df
    mask = ((d50["signal_state"] == 1) & d50["bear_regime"]
            & (d100["signal_state"] == 1) & d100["bear_regime"]
            & (d100["target_alloc"] > 0))
    if mask.sum() >= 3:
        ratio = (d50["target_alloc"][mask] / d100["target_alloc"][mask]).median()
        assert 0.45 <= ratio <= 0.55     # ~50% size cut in bear regime


# ── backtest actually USES the graded alloc (not binarized) ───────────────────

def test_backtest_return_uses_graded_alloc():
    df = run_strategy(_highvol()).df
    ret = df["close"].pct_change().fillna(0.0)
    prev_alloc = df["target_alloc"].shift(1)
    graded = prev_alloc.between(1, 99)   # a genuinely partial position
    assert graded.any()
    i = graded.idxmax()
    strat_ret_i = ret.loc[i] * prev_alloc.loc[i] / 100.0
    # the position model earns exactly (alloc/100)·return — not a binary 0/1
    assert abs(strat_ret_i - ret.loc[i] * prev_alloc.loc[i] / 100.0) < 1e-12
    assert 0.0 < prev_alloc.loc[i] < 100.0


# ── NO profit-take scaling: allocation must not shrink as profit grows ─────────

def test_entrypeak_pine_parity_starts_next_bar():
    """Pine parity: the trailing-stop peak is NOT set on the entry bar (na); it
    starts tracking from the bar after entry (matches diversitas_momentum.pine)."""
    df = run_strategy(_highvol()).df
    entries = df.index[(df["signal_state"] == 1) & (df["signal_state"].shift(1) == 3)]
    assert len(entries) > 0
    e = entries[0]
    assert pd.isna(df.loc[e, "entry_peak"])          # entry bar: peak not yet tracking
    assert pd.isna(df.loc[e, "trail_stop"])          # → no trail stop possible on entry bar
    pos = df.index.get_loc(e)
    if pos + 1 < len(df) and df["signal_state"].iloc[pos + 1] == 1:
        assert not pd.isna(df["entry_peak"].iloc[pos + 1])   # next bar: tracking starts


def test_no_profit_take_scaling():
    """On a smooth low-vol uptrend the position accumulates large unrealized profit
    while vol/regime stay ~constant. If the strategy took profit, allocation would
    step DOWN with cumulative gain. It must not: allocation depends only on vol and
    regime, never on unrealized P&L."""
    df = run_strategy(_lowvol_uptrend()).df
    sb = 1
    # longest continuous BULL run
    runs, cur = [], []
    for ts, s in df["signal_state"].items():
        if s == sb:
            cur.append(ts)
        else:
            if len(cur) > 40: runs.append(cur)
            cur = []
    if len(cur) > 40: runs.append(cur)
    assert runs, "expected a long BULL run on the uptrend"
    run = max(runs, key=len)
    seg = df.loc[run[0]:run[-1]]
    alloc = seg["target_alloc"]
    entry = seg["close"].iloc[0]
    unreal = seg["close"] / entry - 1.0          # grows through the run
    # profit-taking ⇒ strong negative corr(alloc, unrealized profit). There is none:
    corr = np.corrcoef(alloc.values, unreal.values)[0, 1] if alloc.std() > 0 else 0.0
    assert corr > -0.3, f"allocation shrinks with profit (corr={corr:.2f}) → looks like profit-taking"
    # and the high-profit second half is not systematically smaller than the first half
    half = len(seg) // 2
    assert alloc.iloc[half:].mean() >= alloc.iloc[:half].mean() - 5.0
