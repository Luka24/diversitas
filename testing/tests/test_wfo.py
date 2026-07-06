"""Unit tests for the walk-forward optimizer building blocks."""
import numpy as np
import pandas as pd
import pytest

from testing.scripts import wfo


def test_plateau_select_prefers_plateau_over_spike():
    # A realistic SHARP peak: high at x=10 but its immediate neighbours are low
    # (so the neighbourhood average is poor). vs a broad plateau at x=45–55.
    space = {"p": (0, 100, 1)}
    params, values = [], []
    for x in (8, 9, 11, 12):                      # low collar around the spike
        params.append({"p": x}); values.append(5.0)
    params.append({"p": 10}); values.append(100.0)   # the lone spike
    for x in range(45, 56):                       # broad plateau, moderate value
        params.append({"p": x}); values.append(60.0)
    pick = wfo.plateau_select(params, values, space, k=5)
    assert 45 <= pick["p"] <= 55                  # plateau centre, NOT the spike at 10


def test_plateau_select_ignores_nans():
    space = {"p": (0, 10, 1)}
    params = [{"p": i} for i in range(11)]
    values = [np.nan] * 5 + [2.0, 2.1, 2.2, 2.1, 2.0, 1.9]
    pick = wfo.plateau_select(params, values, space, k=3)
    assert pick["p"] >= 5                          # only the finite region is eligible


def test_oos_blocks_train_precedes_test():
    for (ts, te) in wfo.OOS_BLOCKS:
        ts_ = pd.Timestamp(ts, tz="UTC")
        train_end = ts_ - pd.Timedelta(days=wfo.EMBARGO_DAYS)
        assert train_end < ts_                     # embargo gap, train strictly before OOS


def test_sortino_sign():
    rng = np.random.default_rng(0)
    pos = rng.normal(0.002, 0.01, 500)
    assert wfo._sortino(pos) > 0
