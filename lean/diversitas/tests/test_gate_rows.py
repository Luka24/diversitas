"""The gate rows state a formula. These tests check the engine agrees with it.

The dashboard used to describe `track_rising_window` as "a positive slope over
the last 10 bars", which reads as "rising on each of those bars". The column is
one comparison of today against the bar 10 back, and a trackline that falls on
nine of ten days still passes. Nothing caught that, because the wording lived
only in a tooltip.

So each test here rebuilds a gate from the description now shown to the user and
asserts it reproduces the boolean the state machine actually reads, bar for bar.
If someone changes a formula without changing the text, or the other way round,
these fail.
"""
import numpy as np
import pandas as pd
import pytest

from diversitas.config import LeanConfig
from diversitas.strategy import run_strategy
from diversitas.dashboard import entry_gates, exit_gates


@pytest.fixture(scope="module")
def d():
    rng = np.random.default_rng(7)
    n = 900
    idx = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    close = 100 * np.exp(np.linspace(0, 1, n) + np.cumsum(rng.normal(0, 0.03, n)))
    close = pd.Series(close, index=idx)
    daily = pd.DataFrame({"open": close, "high": close * 1.02, "low": close * 0.98,
                          "close": close, "volume": rng.uniform(1e6, 5e6, n)}, index=idx)
    return run_strategy(daily, config=LeanConfig()).df


def test_donchian_price_trigger_reproduces_the_gate(d):
    """`close > LL + 0.75 x (HH - LL)` must equal `donchian_ok`."""
    stated = d["close"] > d["donchian_trigger"]
    assert stated.equals(d["donchian_ok"].astype(bool)), (
        "the price level shown to the user does not flip with the gate it claims "
        "to describe"
    )


def test_trackline_gate_is_one_comparison_not_a_run(d):
    """Today vs 10 bars back — NOT rising on each of the 10 bars."""
    cfg = LeanConfig()
    stated = d["trackline"] > d["trackline"].shift(cfg.track_slope_bars)
    assert stated.equals(d["track_rising_window"])

    # And the two readings really are different, so the distinction the tooltip
    # draws is worth drawing. `track_rising` is the every-bar version.
    every_bar = d["track_rising"].rolling(cfg.track_slope_bars).min().astype(bool)
    both = d["track_rising_window"].notna() & every_bar.notna()
    assert not d.loc[both, "track_rising_window"].equals(every_bar[both]), (
        "the every-bar reading and the endpoint reading agree everywhere, so the "
        "tooltip is warning about a distinction that does not exist"
    )
    # specifically: bars that pass the gate while the trackline fell at least once
    fell = (~d["track_rising"].fillna(True)) & d["track_rising_window"].fillna(False)
    assert fell.sum() > 0


def test_regime_needs_both_halves_to_fail(d):
    cfg = LeanConfig()
    bear = (~(d["close"] > d["ma_long"])) & (d["ma_long"] < d["ma_long_ref"])
    assert (~bear).equals(d["regime_ok"])
    # below the 200 MA while it still rises must NOT block
    lenient = (d["close"] <= d["ma_long"]) & (d["ma_long"] >= d["ma_long_ref"])
    assert lenient.sum() > 0 and d.loc[lenient, "regime_ok"].all()


def test_blowoff_needs_both_halves_to_fire(d):
    cfg = LeanConfig()
    stated = (d["dist_pct"] > cfg.blowoff_dist_pct) & (d["rsi"] > 80)
    assert stated.fillna(False).equals(d["blowoff"].fillna(False))


def test_exit_band_level_reproduces_below_tl(d):
    assert (d["close"] < d["tl_lower"]).equals(d["below_tl"])


def test_rows_carry_a_value_and_a_threshold(d):
    """Every row must show today's number and the trigger without a hover."""
    cfg = LeanConfig()
    last = d.iloc[-1]
    rows = entry_gates(last, cfg) + exit_gates(last, cfg)
    assert len(rows) == 6
    for lbl, ok, now, need, tip in rows:
        assert isinstance(ok, bool)
        assert now.strip(), f"{lbl} shows no current value"
        assert need.strip(), f"{lbl} shows no threshold"
        assert "n/a" not in now, f"{lbl} could not read its value"
        assert '"' not in tip and '"' not in now and '"' not in need, (
            f"{lbl} would break the title attribute it is interpolated into"
        )
        assert "&#10;" in tip, f"{lbl} has no multi-line formula in its hover"


def test_hover_shows_the_formula_not_just_prose(d):
    cfg = LeanConfig()
    rows = {r[0]: r[4] for r in entry_gates(d.iloc[-1], cfg)}
    donchian = next(v for k, v in rows.items() if "20-day range" in k)
    assert "(close &minus; LL) / (HH &minus; LL)" in donchian
    trackline = next(v for k, v in rows.items() if "10 bars ago" in k)
    assert "does NOT require" in trackline
