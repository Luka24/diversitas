"""Unit tests for the advanced-technique building blocks (D1/D2)."""
import numpy as np
import pandas as pd
import pytest

from testing.scripts import ml
from testing.scripts import portfolio as P


def test_triple_barrier_take_profit():
    # rises 2 units (k*atr=2) on bar 1 → label 1
    close = pd.Series([100, 102, 101, 99], dtype=float)
    atr = pd.Series([2.0] * 4)
    lab = ml.triple_barrier_labels(close, atr, np.array([True] * 4), k=1.0, horizon=3)
    assert lab.iloc[0] == 1.0


def test_triple_barrier_stop():
    # falls 2 units first → label 0
    close = pd.Series([100, 98, 97, 96], dtype=float)
    atr = pd.Series([2.0] * 4)
    lab = ml.triple_barrier_labels(close, atr, np.array([True] * 4), k=1.0, horizon=3)
    assert lab.iloc[0] == 0.0


def test_triple_barrier_skips_flat():
    close = pd.Series([100, 102, 104], dtype=float)
    atr = pd.Series([2.0] * 3)
    lab = ml.triple_barrier_labels(close, atr, np.array([False, False, False]), k=1.0, horizon=2)
    assert lab.isna().all()


def test_purged_kfold_no_overlap_and_embargo():
    pk = ml.PurgedKFold(n_splits=5, horizon=20, embargo=10)
    for tr, te in pk.split(1000):
        assert len(set(tr) & set(te)) == 0                  # no overlap
        # nothing in train within [test_start - horizon, test_end + embargo]
        lo, hi = te[0] - 20, te[-1] + 10
        assert not ((tr >= lo) & (tr <= hi)).any()


def test_hrp_weights_sum_to_one():
    rng = np.random.default_rng(0)
    R = pd.DataFrame(rng.normal(0, 0.02, (300, 4)), columns=list("ABCD"))
    w = P.hrp_weights(R)
    assert w.sum() == pytest.approx(1.0, abs=1e-9)
    assert (w >= 0).all()


def test_hrp_equal_for_uncorrelated_equal_vol():
    # 4 iid equal-vol assets → HRP weights should be ~equal
    rng = np.random.default_rng(1)
    R = pd.DataFrame(rng.normal(0, 0.02, (2000, 4)), columns=list("ABCD"))
    w = P.hrp_weights(R)
    assert w.max() - w.min() < 0.15                          # roughly equal
