"""The permanent floor: one formula, one place, and everyone reads it.

The floor keeps a slice invested while the signal says out, so an exit sells
95 % rather than 100 %. It is a linear blend, not a new rule:

    position = floor + (1 - floor) * signal

The risk being guarded here is not that the arithmetic is wrong. It is that the
dashboard and scripts/verify.py each used to spell out their own version of
"what fraction are we holding", and they disagreed about the one-bar lag for
months without anyone noticing. Everything now goes through position().
"""
import numpy as np
import pandas as pd
import pytest

from diversitas.config import DEFAULT_CONFIG, LeanConfig
from diversitas.strategy import S_BULL, position, run_strategy, traded_fraction
from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup


def _synth(seed=5, n=900):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    close = 100 * np.exp(np.linspace(0, 1, n) + np.cumsum(rng.normal(0, 0.03, n)))
    close = pd.Series(close, index=idx)
    return pd.DataFrame({"open": close, "high": close * 1.02, "low": close * 0.98,
                         "close": close, "volume": rng.uniform(1e6, 5e6, n)}, index=idx)


@pytest.fixture(scope="module")
def df():
    return trim_warmup(run_strategy(_synth(), config=LeanConfig()).df)


def test_default_floor_is_five_percent():
    assert DEFAULT_CONFIG.bear_alloc_pct == 5.0


def test_long_holds_everything_and_flat_drifts(df):
    """The floor is bought once and then left alone, so the share it represents
    moves with the price. A constant 0.05 would mean rebalancing to exactly 5 %
    every single day, which is not what was asked for and would cost fees."""
    cfg = LeanConfig()
    pos = position(df, cfg)
    bull = df["prev_signal_state"] == S_BULL
    assert pos[bull].eq(1.0).all(), "a long bar must hold the whole position"
    flat = pos[~bull]
    assert flat.min() > 0, "with a floor there is no fully flat bar"
    assert flat.nunique() > 10, "the flat share must drift, not sit at 5 %"
    assert 0.01 < flat.min() < 0.05 < flat.max() < 0.20, (
        f"drift ran to {flat.min():.3f}..{flat.max():.3f}, which is not a floor")


def test_an_exit_sells_ninety_five_percent(df):
    """The point of the setting, stated as the user stated it."""
    cfg = LeanConfig()
    pos, trd = position(df, cfg), traded_fraction(df, cfg)
    bull = (df["prev_signal_state"] == S_BULL).astype(int)
    exit_bars = bull.diff() < 0
    assert exit_bars.sum() > 0
    # the sale is 95 % of whatever was held, and what was held was everything
    assert np.allclose(trd[exit_bars].to_numpy(), 0.95)
    assert np.allclose(pos[exit_bars].to_numpy(), 0.05)


def test_drift_is_not_billed_as_a_trade(df):
    """Turnover must count transactions, not price movement. Charging the daily
    drift would bill something nobody does."""
    cfg = LeanConfig()
    trd = traded_fraction(df, cfg)
    naive = turnover(position(df, cfg))
    assert float(trd.sum()) < float(naive.sum()), (
        "traded_fraction is no cheaper than diffing the position, so it is "
        "probably still counting drift")
    bull = (df["prev_signal_state"] == S_BULL).astype(int)
    switches = (bull.diff().fillna(0) != 0)
    assert (trd[~switches] == 0).all(), "a trade was charged on a bar with no switch"


def test_zero_floor_reproduces_the_old_behaviour(df):
    pos = position(df, LeanConfig(bear_alloc_pct=0.0))
    old = (df["prev_signal_state"] == S_BULL).astype(float)
    assert pos.equals(old)


def test_position_lags_the_signal_by_one_bar(df):
    """The floor is the new part; the lag is the part that must not regress."""
    cfg = LeanConfig(bear_alloc_pct=0.0)
    assert not position(df, cfg).equals(
        (df["signal_state"] == S_BULL).astype(float)), (
        "position tracked the same bar's signal, which is a one-bar lookahead")


def test_dashboard_and_position_agree(df):
    """Both build an equity curve from a held fraction. Same floor, same lag,
    same costs, so the two curves must land on the same number. This is the
    test that would have caught the months when they did not."""
    import diversitas.dashboard as D


    cfg = LeanConfig()
    m = D._compute_metrics(df, bear_alloc_pct=cfg.bear_alloc_pct, td=365,
                           fee_per_side_pct=0.30)
    pos = position(df, cfg)
    trd = traded_fraction(df, cfg)
    ret = df["close"].pct_change().fillna(0.0)
    mine = float(np.cumprod(
        1 + net_returns(pos, ret, 0.30, traded=trd).to_numpy(float))[-1])
    theirs = float(m["strategy"]["eq"].iloc[-1])
    assert mine == pytest.approx(theirs, rel=1e-9)


def test_dashboard_uses_the_untrimmed_frame_for_returns():
    """The first bar after the warm-up cut needs the bar before it to have a
    return at all, and that bar only exists in the untrimmed frame.

    Passing the trimmed frame covers the user's date filter but not the warm-up
    boundary, so a real day was zeroed. It stayed invisible while the position
    on that bar was 0; the floor makes it never 0.
    """
    import diversitas.dashboard as D

    D._set_theme(True)
    raw = _synth()
    res = run_strategy(raw, config=LeanConfig())
    untrimmed = res.df
    df = trim_warmup(res.df)


    m = D._compute_metrics(df, bear_alloc_pct=5.0, td=365,
                           df_full=untrimmed, fee_per_side_pct=0.30)
    ret = raw["close"].pct_change().reindex(df.index).fillna(0.0)
    cfg = LeanConfig()
    mine = float(np.cumprod(
        1 + net_returns(position(df, cfg), ret, 0.30,
                        traded=traded_fraction(df, cfg)).to_numpy(float))[-1])
    assert float(m["strategy"]["eq"].iloc[-1]) == pytest.approx(mine, rel=1e-9)

    # and the trimmed frame really does give a different, wrong answer
    bad = D._compute_metrics(df, bear_alloc_pct=5.0, td=365,
                             df_full=df, fee_per_side_pct=0.30)
    assert float(bad["strategy"]["eq"].iloc[-1]) != pytest.approx(mine, rel=1e-9)


def test_run_keeps_the_untrimmed_frame():
    import diversitas.dashboard as D
    cfg, daily, res = D._run.__wrapped__("BTC", 700, False)
    assert hasattr(res, "untrimmed")
    assert len(res.untrimmed) > len(res.df)


def test_every_dashboard_path_uses_one_position_formula():
    """Six places on the page answer "how much are we holding". They must all
    ask the same function.

    Each used to compute `np.where(is_bull, 1, floor)` itself, which is right
    only while the floor is rebalanced daily. Once it drifts, six hand-written
    copies means six different pictures of the same portfolio, and the page
    disagreeing with itself is worse than the page being wrong in one place.
    """
    import inspect
    import diversitas.dashboard as D

    src = inspect.getsource(D)
    assert "np.where(is_bull" not in src
    assert "bear_alloc_pct / 100.0), index=" not in src
    # and the helper really is used by more than the metrics function
    assert src.count("_held_and_traded(") >= 6


def test_portfolio_mode_runs_with_the_floor():
    """Portfolio mode kept its own copy of the position formula and so was
    never exercised against the drifting one."""
    import diversitas.dashboard as D
    D._set_theme(True)
    _, _, res_a = D._run.__wrapped__("BTC", 700, False)
    _, res_b = D._run_b.__wrapped__("ETH", 700)
    out = D._compute_portfolio_metrics(res_a.df, res_b.df, 60, 40, 5.0,
                                       365, 365, res_a.untrimmed, res_b.df, 0.30)
    stats = [e for e in out if isinstance(e, dict) and "strategy" in e]
    assert len(stats) >= 2
    for e in stats:
        assert np.isfinite(e["strategy"]["sortino"])


def test_the_leftover_is_a_fixed_quantity_not_a_fixed_percent(df):
    """Luka's words: an exit leaves 5 % in BTC, say 0.05 BTC, and if BTC rises
    that may become 7 % of the portfolio, but it is still 0.05 BTC. Nothing is
    bought and nothing is sold.

    So the invariant is the QUANTITY, not the share. This reconstructs the coin
    count from the held fraction and the portfolio value and asserts it does not
    move between trades. A constant-percent floor would fail here, because
    holding 5 % of a moving asset means trading it back every day.
    """

    cfg = LeanConfig()
    pos = position(df, cfg).to_numpy()
    trd = traded_fraction(df, cfg).to_numpy()
    ret = df["close"].pct_change().fillna(0.0).to_numpy()
    # price at the START of each bar, which is what the held fraction refers to
    open_px = df["close"].shift(1).to_numpy()
    bull = (df["prev_signal_state"] == S_BULL).astype(int).to_numpy()

    value = 1.0
    qty = np.empty(len(pos))
    for i in range(len(pos)):
        if i > 0:
            value = value * (1 + pos[i - 1] * ret[i - 1] - trd[i - 1] * 0.003)
        qty[i] = pos[i] * value / open_px[i]

    stretches = 0
    i = 0
    while i < len(pos):
        if bull[i] == 0 and trd[i] > 0:            # the exit bar
            j = i + 1
            while j < len(pos) and bull[j] == 0 and trd[j] == 0:
                j += 1
            held = qty[i + 1:j]
            if len(held) > 3:
                stretches += 1
                spread = held.max() / held.min() - 1
                assert spread < 1e-9, (
                    f"the coin count moved by {spread:.2%} between "
                    f"{df.index[i + 1].date()} and {df.index[j - 1].date()}, "
                    f"so something was bought or sold")
            i = j
        else:
            i += 1
    assert stretches >= 3, "not enough flat stretches to have tested anything"


def test_allocation_line_shows_the_drift_not_the_instruction(df):
    """The chart's allocation line must plot what is held, at enough precision
    to see it move. It used to draw a flat 5 % step at whole-percent hover,
    which is a picture of the instruction rather than the holding."""
    import diversitas.dashboard as D

    D._set_theme(True)
    fig = D._build_price_chart(df.tail(400), "TEST", 5.0)
    line = [t for t in fig.data if "Alloc" in (t.name or "")][0]
    y = np.asarray(line.y, dtype=float)
    flat = y[y < 90]

    assert len(np.unique(flat)) > 20, "the flat stretch is drawn as a constant"
    assert flat.min() < 4.5 and flat.max() > 4.9, (
        f"the drift spans only {flat.min():.2f}..{flat.max():.2f} %")
    assert ".0f" not in line.hovertemplate, (
        "whole-percent hover rounds 3.5 % to 4 % and hides the drift")
    assert line.line.shape != "hv", (
        "a step line draws drift as if it were a sequence of trades")
