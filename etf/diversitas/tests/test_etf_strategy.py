"""Tests for the ETF sleeve.

Two categories, and the second is the one that matters. The first checks the
strategy does what it says. The second checks the *data layer* does not lie,
because every wrong number this project has produced came from data that looked
fine: a monthly series labelled daily, a sibling ticker of the same ISIN, a
forward-filled hole treated as a tradable close, 365 trading days in a year that
has 252.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from diversitas.config import DEFAULT_CONFIG, ETFConfig
from diversitas.mean_reversion import DEFAULT_MR_CONFIG
from diversitas.mean_reversion import run_strategy as run_mr
from diversitas.rotation import _drifted, _hold_between_rebalances, buy_and_hold
from diversitas.strategy import S_BEAR, S_BULL, run_strategy

from shared import indicators as ind
from shared.etf_data import _mark_quality, target_calendar
from shared.etf_universe import PORTFOLIOS, UNIVERSE, usable_start


def _synthetic(n=900, trend=0.0004, vol=0.01, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=n, tz="UTC")
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(trend, vol, n))), index=idx)
    return pd.DataFrame({"open": close.shift(1).fillna(close.iloc[0]),
                         "high": close * (1 + abs(rng.normal(0, vol / 2, n))),
                         "low": close * (1 - abs(rng.normal(0, vol / 2, n))),
                         "close": close,
                         "volume": rng.integers(1e4, 1e6, n).astype(float)},
                        index=idx)


# ── universe / registry ───────────────────────────────────────────────────────

def test_every_portfolio_member_is_in_the_universe():
    for name, weights in PORTFOLIOS.items():
        for key in weights:
            assert key in UNIVERSE, f"{name} references unknown sleeve {key}"


def test_portfolio_weights_sum_to_one():
    for name, weights in PORTFOLIOS.items():
        assert abs(sum(weights.values()) - 1.0) < 1e-9, name


def test_usable_start_is_not_before_any_members_usable_date():
    for name in PORTFOLIOS:
        s = usable_start(name)
        for key in PORTFOLIOS[name]:
            assert s >= UNIVERSE[key].usable_from


def test_no_two_instruments_share_a_ticker():
    """A duplicated ticker would mean two sleeves are secretly the same series,
    which inflates diversification and understates portfolio risk."""
    tickers = [i.yahoo for i in UNIVERSE.values()]
    assert len(tickers) == len(set(tickers))


# ── data layer ────────────────────────────────────────────────────────────────

def test_target_calendar_excludes_fixed_and_moving_holidays():
    cal = target_calendar("2024-01-01", "2024-12-31")
    for closed in ("2024-01-01", "2024-03-29", "2024-04-01", "2024-05-01",
                   "2024-12-25", "2024-12-26"):
        assert pd.Timestamp(closed, tz="UTC") not in cal, closed
    assert pd.Timestamp("2024-07-15", tz="UTC") in cal


def test_stale_and_filled_bars_are_labelled_not_smoothed():
    """The failure this prevents: a repeated close on zero volume is a price the
    backtest can act on that nobody could have traded."""
    cal = target_calendar("2024-01-02", "2024-01-19")
    raw = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0,
                        "close": 100.0, "volume": 5000.0, "adjclose": 100.0},
                       index=cal)
    raw.loc[cal[3], "volume"] = 0.0          # same close, no volume -> stale
    raw = raw.drop(index=cal[5])             # no print at all -> filled
    out = _mark_quality(raw, cal)
    assert bool(out.loc[cal[3], "stale"]) and not bool(out.loc[cal[3], "traded"])
    assert bool(out.loc[cal[5], "filled"]) and not bool(out.loc[cal[5], "traded"])
    assert out.loc[cal[5], "close"] == pytest.approx(100.0)   # carried, not NaN


def test_annualisation_uses_252_not_365():
    """A 20 % daily-vol series must annualise to sigma*sqrt(252). With 365 the
    answer is 20 % too high and nothing on a chart shows it."""
    c = _synthetic(400, trend=0.0, vol=0.01)["close"]
    got = float(ind.realized_vol(c, 60, trading_days=252).iloc[-1])
    daily = float(np.log(c / c.shift(1)).rolling(60).std(ddof=0).iloc[-1])
    assert got == pytest.approx(daily * np.sqrt(252) * 100, rel=1e-9)
    assert DEFAULT_CONFIG.trading_days == 252


# ── strategy behaviour ────────────────────────────────────────────────────────

def test_no_lookahead_a_future_bar_cannot_change_todays_signal():
    """Truncating the series must leave every earlier signal untouched."""
    d = _synthetic(700)
    full = run_strategy(d, config=DEFAULT_CONFIG).df
    cut = run_strategy(d.iloc[:-60], config=DEFAULT_CONFIG).df
    common = cut.index
    pd.testing.assert_series_equal(full.loc[common, "signal_state"],
                                   cut["signal_state"], check_names=False)


def test_atr_buffer_scales_with_instrument_volatility():
    """The point of moving the buffer from percent to ATR: the same parameter
    must mean the same statistical distance on a 4 %-vol bond fund and a
    19 %-vol small-cap fund."""
    quiet = run_strategy(_synthetic(600, vol=0.002), config=DEFAULT_CONFIG).df
    wild = run_strategy(_synthetic(600, vol=0.02), config=DEFAULT_CONFIG).df
    q = (quiet["buffer"] / quiet["close"]).median()
    w = (wild["buffer"] / wild["close"]).median()
    assert w > q * 3, f"buffer did not scale: quiet {q:.5f} vs wild {w:.5f}"


def test_vol_sizing_binds_only_above_target_and_never_levers():
    cfg = ETFConfig(target_vol_pct=12.0, max_leverage=1.0)
    df = run_strategy(_synthetic(700, vol=0.02), config=cfg).df
    assert df["target_alloc"].max() <= 100.0
    live = df[df["signal_state"] == S_BULL]
    if len(live):
        assert live["vol_scale"].max() <= 1.0 + 1e-9


def test_vol_floor_stops_a_near_zero_vol_sleeve_exploding():
    """Without the floor, a 1 %-vol bond series gives target/vol = 12x."""
    cfg = ETFConfig(vol_floor_pct=3.0, target_vol_pct=12.0, max_leverage=1.0)
    df = run_strategy(_synthetic(700, vol=0.0005), config=cfg).df
    assert df["vol_scale"].max() <= 1.0 + 1e-9


def test_trailing_stop_is_measured_in_atr():
    df = run_strategy(_synthetic(700), config=DEFAULT_CONFIG).df
    live = df[(df["signal_state"] == S_BULL) & df["trail_stop"].notna()]
    if len(live):
        gap = (live["entry_peak"] - live["trail_stop"]) / live["atr"]
        assert gap.round(6).nunique() == 1
        assert gap.iloc[0] == pytest.approx(DEFAULT_CONFIG.trail_atr_mult)


def test_position_is_zero_whenever_the_signal_is_bear():
    df = run_strategy(_synthetic(700), config=DEFAULT_CONFIG).df
    assert (df.loc[df["signal_state"] == S_BEAR, "target_alloc"] == 0).all()


# ── mean reversion ────────────────────────────────────────────────────────────

def test_mean_reversion_never_goes_long_below_the_macro_ma():
    df = run_mr(_synthetic(900), config=DEFAULT_MR_CONFIG).df
    live = df["signal_state"] == S_BULL
    assert not (live & ~df["macro_ok"].fillna(False)).any()


def test_mean_reversion_respects_the_time_stop():
    df = run_mr(_synthetic(900), config=DEFAULT_MR_CONFIG).df
    assert df["bars_held"].max() <= DEFAULT_MR_CONFIG.max_hold_bars


# ── rotation plumbing ─────────────────────────────────────────────────────────

def test_rebalance_holding_does_not_peek_forward():
    w = pd.DataFrame({"a": np.arange(10.0)}, index=pd.bdate_range("2024-01-01", periods=10, tz="UTC"))
    held = _hold_between_rebalances(w, 3)
    assert held["a"].tolist() == [0, 0, 0, 3, 3, 3, 6, 6, 6, 9]


def test_turnover_counts_trades_not_drift():
    """A weight that grew because the price rose was not traded. Charging
    `weights.diff()` on a rebalanced book invents a cost every single day."""
    idx = pd.bdate_range("2024-01-01", periods=60, tz="UTC")
    rets = pd.DataFrame({"a": 0.01, "b": 0.0}, index=idx)
    target = pd.DataFrame({"a": 0.5, "b": 0.5}, index=idx)
    target = _hold_between_rebalances(target, 21)
    held, traded = _drifted(target, rets, 21)
    assert (traded > 0).sum() <= 3            # only on rebalance bars
    assert held["a"].iloc[5] > held["a"].iloc[0]    # it drifted up in between


def test_buy_and_hold_benchmark_holds_the_stated_weights():
    frames = {"x": _synthetic(400, seed=1), "y": _synthetic(400, seed=2)}
    res = buy_and_hold(frames, {"x": 0.6, "y": 0.4}, rebalance_every=21)
    on_reb = res.weights.iloc[0]
    assert on_reb["x"] == pytest.approx(0.6)
    assert on_reb["y"] == pytest.approx(0.4)
    assert res.weights.sum(axis=1).max() < 1.5


# ── tax model ─────────────────────────────────────────────────────────────────

def test_holding_period_brackets_step_down():
    from shared.tax import SLOVENIA_2026
    t = SLOVENIA_2026
    assert t.rate(0.5) == pytest.approx(0.25)
    assert t.rate(4.99) == pytest.approx(0.25)
    assert t.rate(5.0) == pytest.approx(0.20)
    assert t.rate(12.0) == pytest.approx(0.15)
    assert t.rate(15.0) == pytest.approx(0.00)


def test_losses_offset_gains_within_the_same_year():
    """Without this, a strategy that lost money still pays tax, because every
    profitable disposal is taxed and every losing one is ignored."""
    from shared.tax import _net_year_tax
    assert _net_year_tax([(100.0, 0.25), (-100.0, 0.25)]) == pytest.approx(0.0)
    # a loss is used against the highest-taxed gain first
    assert _net_year_tax([(100.0, 0.25), (100.0, 0.15), (-100.0, 0.0)]) == pytest.approx(15.0)


def test_never_selling_pays_no_tax_until_liquidation():
    from shared.tax import SLOVENIA_2026, simulate_brokerage, summarise
    px = pd.DataFrame({"a": np.linspace(100, 200, 500)},
                      index=pd.bdate_range("2018-01-01", periods=500, tz="UTC"))
    w = pd.DataFrame({"a": 1.0}, index=px.index)
    never = pd.Series(False, index=px.index)
    r = simulate_brokerage(w, px, SLOVENIA_2026, rebalance_mask=never)
    assert r.tax_paid.sum() == pytest.approx(0.0)
    assert r.terminal_tax > 0          # the gain is taxed once, at the end
    s = summarise(r)
    assert s["cagr_after_tax"] == pytest.approx(s["cagr_pre_tax"], abs=1e-9)
    assert s["cagr_after_liquidation"] < s["cagr_pre_tax"]


def test_inr_is_tax_free_after_fifteen_years():
    from shared.tax import INR_2026, simulate_inr, summarise
    idx = pd.bdate_range("2005-01-03", periods=16 * 252, tz="UTC")
    px = pd.DataFrame({"a": np.linspace(100, 400, len(idx))}, index=idx)
    w = pd.DataFrame({"a": 1.0}, index=idx)
    r = simulate_inr(w, px, INR_2026)
    assert r.terminal_tax == pytest.approx(0.0)
    short = simulate_inr(w.iloc[:5 * 252], px.iloc[:5 * 252], INR_2026)
    assert short.terminal_tax > 0
    assert summarise(short)["regime"] == INR_2026.name


# ── data layer regressions ────────────────────────────────────────────────────

def test_proxy_chain_prefers_tracking_over_reach():
    """SPY and the MSCI World index both reach 1999. The index tracks the sleeve
    far better and its level gap is the dividend yield; SPY's gap is that US
    equities beat world equities. Picking on reach alone chooses SPY."""
    from shared.etf_data import recommend_chain
    quality = {
        "World|SPY": dict(first="1999-01-04", corr_1m=0.964, corr_1d=0.651,
                          grade="mesecno", drift_pp=-3.0),
        "World|^990100-USD-STRD": dict(first="1999-01-04", corr_1m=0.983,
                                       corr_1d=0.788, grade="mesecno", drift_pp=2.03),
    }
    chain = recommend_chain("World", quality)
    assert chain and chain[0]["ticker"] == "^990100-USD-STRD"


def test_rejected_proxies_never_enter_a_chain():
    from shared.etf_data import recommend_chain
    quality = {"InflLink|TIP": dict(first="2003-12-05", corr_1m=0.18, corr_1d=0.16,
                                    grade="zavrni", drift_pp=-2.2)}
    assert recommend_chain("InflLink", quality) == []
