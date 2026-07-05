"""Phase 0 gate — statistical toolkit sanity checks."""
import numpy as np
import pandas as pd
import pytest

from testing.scripts import stats as S


def test_deflated_sharpe_decreases_with_trials():
    rng = np.random.default_rng(1)
    r = rng.normal(0.001, 0.02, 1500)
    d1  = S.deflated_sharpe(r, n_trials=1)
    d50 = S.deflated_sharpe(r, n_trials=50)
    # more trials → higher SR0 hurdle → lower deflated probability
    assert d50["sr0_ann"] > d1["sr0_ann"]
    assert d50["dsr"] <= d1["dsr"] + 1e-9


def test_probabilistic_sharpe_in_unit_interval():
    rng = np.random.default_rng(2)
    r = rng.normal(0.002, 0.02, 2000)
    psr = S.probabilistic_sharpe(r, 0.0)
    assert 0.0 <= psr <= 1.0


def test_pure_noise_has_low_dsr():
    rng = np.random.default_rng(3)
    r = rng.normal(0.0, 0.02, 1500)        # zero-mean → no edge
    d = S.deflated_sharpe(r, n_trials=100)
    assert d["dsr"] < 0.95                  # should NOT look significant


def test_stationary_bootstrap_shape_and_mean():
    rng = np.random.default_rng(4)
    r = rng.normal(0.001, 0.02, 500)
    boot = S.stationary_bootstrap(r, n_boot=300, mean_block=20, seed=0)
    assert boot.shape == (300, 500)
    # bootstrap mean-of-means ≈ sample mean
    assert boot.mean() == pytest.approx(r.mean(), abs=0.002)


def test_bootstrap_ci_brackets_point():
    rng = np.random.default_rng(5)
    r = rng.normal(0.001, 0.02, 800)
    ci = S.bootstrap_ci(r, lambda x: float(np.mean(x)), n_boot=500)
    assert ci["lo"] <= ci["point"] <= ci["hi"]


def test_alpha_beta_recovers_known_beta():
    rng = np.random.default_rng(6)
    bench = pd.Series(rng.normal(0.001, 0.02, 1500))
    noise = pd.Series(rng.normal(0.0, 0.005, 1500))
    strat = 0.0003 + 1.5 * bench + noise           # true beta 1.5, alpha>0
    ab = S.alpha_beta(strat, bench, lags=10)
    assert ab["beta"] == pytest.approx(1.5, abs=0.1)
    assert ab["alpha_ann"] > 0


def test_hedged_removes_beta():
    rng = np.random.default_rng(7)
    bench = pd.Series(rng.normal(0.001, 0.02, 1500))
    strat = 0.0003 + 1.5 * bench + pd.Series(rng.normal(0, 0.004, 1500))
    hedged = S.hedged_returns(strat, bench)
    ab2 = S.alpha_beta(hedged, bench, lags=10)
    assert abs(ab2["beta"]) < 0.15                 # beta neutralized


def test_pbo_on_noise_near_half():
    rng = np.random.default_rng(8)
    # 20 configs of pure noise → IS winner is random → PBO should be ~0.5
    M = rng.normal(0, 0.02, (1000, 20))
    res = S.prob_backtest_overfit(M, n_splits=8)
    assert 0.25 <= res["pbo"] <= 0.75
