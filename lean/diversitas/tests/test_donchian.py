"""The Donchian channel is the ENTRY GATE as of 2026-08-10.

Until then it was an optional extra AND-condition, off by default, and these
tests asserted that the default was identical to switching it off. That contract
is gone: the channel now REPLACES the trackline band as the entry gate, so the
default is on, and turning it off is a different strategy rather than the same
one.

What is tested here is the new contract, plus the one thing that has not changed
— the trackline is still needed, it just guards the exit instead of the entry.
"""
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


def test_default_is_donchian_on_at_20():
    cfg = LeanConfig()
    assert cfg.use_donchian is True
    assert cfg.donchian_period == 20, (
        "20 is the classic Donchian/Turtle short-term length and is not to be "
        "tuned — PBO for selecting a period here was 0.672"
    )
    d = run_strategy(_synth(), config=cfg).df
    assert not (d["donchian_ok"] == True).all()   # noqa: E712 — must actually bind


def test_switching_the_gate_off_changes_the_strategy():
    """Negative control. If turning the gate off changed nothing, the gate would
    not be the gate, and the first test would be asserting a decoration."""
    daily = _synth()
    d_on = run_strategy(daily, config=LeanConfig()).df
    d_off = run_strategy(daily, config=LeanConfig(use_donchian=False)).df
    assert not np.array_equal(d_on["signal_state"].values,
                              d_off["signal_state"].values)


def test_entry_no_longer_depends_on_the_trackline_band():
    """above_tl is computed and displayed but must not decide entry any more.

    Widening the band to something absurd would once have blocked every entry.
    It must now leave the signal untouched, because the band guards the exit
    only — which the second half of this test then confirms does still respond.
    """
    daily = _synth()
    base = run_strategy(daily, config=LeanConfig()).df
    wide = run_strategy(daily, config=LeanConfig(track_buf_pct=25.0)).df
    entries_base = ((base["signal_state"] == 1) & base["signal_changed"]).sum()
    entries_wide = ((wide["signal_state"] == 1) & wide["signal_changed"]).sum()
    assert entries_base == entries_wide, (
        "widening track_buf_pct changed the number of entries, so the trackline "
        "band is still gating entry"
    )
    # ...but the exit does still read it, so the two runs are not identical
    assert not np.array_equal(base["signal_state"].values, wide["signal_state"].values), (
        "widening the band changed nothing at all, so the exit is not reading it "
        "either — that would mean track_buf_pct is dead"
    )


def test_trackline_is_still_computed_and_used_by_the_exit():
    d = run_strategy(_synth(), config=LeanConfig()).df
    for col in ("trackline", "above_tl", "below_tl", "track_rising_window"):
        assert col in d.columns
    assert d["trackline"].notna().any()
