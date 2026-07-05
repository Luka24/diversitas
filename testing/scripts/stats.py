"""Statistical rigor toolkit — the methods that answer the 6 criticisms.

- deflated_sharpe   : Bailey & López de Prado (2014) — corrects Sharpe for the
                      number of trials, skew and kurtosis (multiple-testing).
- stationary_bootstrap : Politis–Romano block bootstrap; preserves volatility
                      clustering (naive IID shuffle understates tail risk).
- bootstrap_ci      : CI for any metric via the block bootstrap.
- alpha_beta        : OLS of strategy on benchmark returns with Newey–West HAC
                      t-stats (honest under autocorrelation/heteroskedasticity).
- prob_backtest_overfit : PBO via combinatorial train/test splits.
- whites_reality_check : data-snooping p-value across a family of configs.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

import numpy as np
import pandas as pd
from scipy import stats as sps

_SQRT_TD = 365.0


# ── Deflated / Probabilistic Sharpe ───────────────────────────────────────────

def _sharpe(r: np.ndarray) -> float:
    sd = r.std(ddof=1)
    return float(r.mean() / sd) if sd > 1e-12 else 0.0


def expected_max_sharpe(n_trials: int, var_sharpe: float) -> float:
    """E[max Sharpe] over `n_trials` independent strategies with given variance
    of the Sharpe estimates (Bailey & López de Prado, eq. for SR0)."""
    if n_trials < 2:
        return 0.0
    e = np.euler_gamma
    z1 = sps.norm.ppf(1.0 - 1.0 / n_trials)
    z2 = sps.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(np.sqrt(var_sharpe) * ((1 - e) * z1 + e * z2))


def probabilistic_sharpe(r: np.ndarray, sr_benchmark: float = 0.0) -> float:
    """PSR: P(true SR > benchmark) given skew/kurtosis of the sample (per-bar SR)."""
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 8:
        return np.nan
    sr = _sharpe(r)                       # per-bar Sharpe
    g3 = sps.skew(r, bias=False)
    g4 = sps.kurtosis(r, fisher=False, bias=False)   # non-excess
    denom = np.sqrt(1 - g3 * sr + (g4 - 1) / 4.0 * sr ** 2)
    if denom <= 1e-12:
        return np.nan
    z = (sr - sr_benchmark) * np.sqrt(n - 1) / denom
    return float(sps.norm.cdf(z))


def deflated_sharpe(r: np.ndarray, n_trials: int,
                    trials_sharpe_std: Optional[float] = None) -> dict:
    """Deflated Sharpe Ratio. Returns {sr_ann, sr0_ann, dsr, p_value}.

    `trials_sharpe_std` = std of the (per-bar) Sharpe ratios across all configs
    tried on this asset. If unknown, a conservative default of 0.5/sqrt(n) is used
    on the annualized scale, converted back to per-bar.
    """
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 8:
        return dict(sr_ann=np.nan, sr0_ann=np.nan, dsr=np.nan, p_value=np.nan)
    sr_bar = _sharpe(r)
    if trials_sharpe_std is None:
        var_sr = (1.0 + 0.5 * sr_bar ** 2) / n         # analytic SR variance approx
    else:
        var_sr = float(trials_sharpe_std) ** 2
    sr0 = expected_max_sharpe(n_trials, var_sr)          # per-bar benchmark
    dsr = probabilistic_sharpe(r, sr_benchmark=sr0)
    return dict(sr_ann=sr_bar * np.sqrt(_SQRT_TD),
                sr0_ann=sr0 * np.sqrt(_SQRT_TD),
                dsr=dsr, p_value=(1.0 - dsr) if np.isfinite(dsr) else np.nan)


# ── Stationary (block) bootstrap ──────────────────────────────────────────────

def stationary_bootstrap(r: np.ndarray, n_boot: int = 5000,
                         mean_block: float = 20.0, seed: int = 42) -> np.ndarray:
    """Politis–Romano stationary bootstrap. Returns (n_boot, len(r)) resamples.

    Geometric block lengths with mean `mean_block` preserve autocorrelation /
    volatility clustering, unlike an IID shuffle.
    """
    r = np.asarray(r, float)
    n = len(r)
    rng = np.random.default_rng(seed)
    p = 1.0 / mean_block
    out = np.empty((n_boot, n), float)
    for b in range(n_boot):
        idx = np.empty(n, dtype=np.int64)
        i = rng.integers(0, n)
        for t in range(n):
            idx[t] = i
            if rng.random() < p:
                i = rng.integers(0, n)          # start a new block
            else:
                i = (i + 1) % n                 # continue block
        out[b] = r[idx]
    return out


def bootstrap_ci(r: np.ndarray, metric_fn: Callable[[np.ndarray], float],
                 n_boot: int = 5000, mean_block: float = 20.0,
                 seed: int = 42, alpha: float = 0.05) -> dict:
    samples = stationary_bootstrap(r, n_boot, mean_block, seed)
    vals = np.array([metric_fn(s) for s in samples])
    vals = vals[np.isfinite(vals)]
    return dict(point=float(metric_fn(np.asarray(r, float))),
                lo=float(np.percentile(vals, 100 * alpha / 2)),
                hi=float(np.percentile(vals, 100 * (1 - alpha / 2))),
                mean=float(vals.mean()), std=float(vals.std()))


# ── Alpha / Beta vs benchmark (Newey–West HAC) ────────────────────────────────

def alpha_beta(strat_ret: pd.Series, bench_ret: pd.Series,
               lags: int = 10, td: int = 365) -> dict:
    """OLS r_strat = α + β r_bench + ε with Newey–West HAC standard errors."""
    import statsmodels.api as sm
    df = pd.concat([strat_ret.rename("s"), bench_ret.rename("b")], axis=1).dropna()
    if len(df) < 30:
        return dict(alpha_ann=np.nan, beta=np.nan, r2=np.nan,
                    t_alpha=np.nan, p_alpha=np.nan, corr=np.nan, n=len(df))
    X = sm.add_constant(df["b"].values)
    model = sm.OLS(df["s"].values, X).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    a, b = model.params
    return dict(alpha_ann=float(a * td), beta=float(b), r2=float(model.rsquared),
                t_alpha=float(model.tvalues[0]), p_alpha=float(model.pvalues[0]),
                corr=float(df["s"].corr(df["b"])), n=int(len(df)))


def hedged_returns(strat_ret: pd.Series, bench_ret: pd.Series) -> pd.Series:
    """r_strat − β·r_bench — the BTC-beta-hedged series (edge beyond beta)."""
    ab = alpha_beta(strat_ret, bench_ret)
    beta = ab["beta"] if np.isfinite(ab["beta"]) else 0.0
    aligned = pd.concat([strat_ret, bench_ret], axis=1).dropna()
    return aligned.iloc[:, 0] - beta * aligned.iloc[:, 1]


# ── Probability of Backtest Overfitting (CSCV-style) ──────────────────────────

def prob_backtest_overfit(perf_matrix: np.ndarray, n_splits: int = 12) -> dict:
    """PBO via combinatorially-symmetric cross-validation.

    `perf_matrix`: shape (T, C) — per-bar (or per-block) return of each of C
    configs over T observations. Splits time into `n_splits` blocks, forms all
    balanced train/test partitions, and measures how often the in-sample-best
    config lands below the OOS median (logit → PBO).
    """
    from itertools import combinations
    M = np.asarray(perf_matrix, float)
    T, C = M.shape
    if C < 2:
        return dict(pbo=np.nan, n_paths=0)
    s = n_splits - (n_splits % 2)
    edges = np.linspace(0, T, s + 1, dtype=int)
    blocks = [np.arange(edges[i], edges[i + 1]) for i in range(s)]
    logits = []
    for train_sel in combinations(range(s), s // 2):
        test_sel = [i for i in range(s) if i not in train_sel]
        tr = np.concatenate([blocks[i] for i in train_sel])
        te = np.concatenate([blocks[i] for i in test_sel])
        is_perf = M[tr].mean(axis=0)
        oos_perf = M[te].mean(axis=0)
        best = int(np.argmax(is_perf))
        rank = sps.rankdata(oos_perf)[best] / C          # (0,1]
        rank = min(max(rank, 1e-6), 1 - 1e-6)
        logits.append(np.log(rank / (1 - rank)))
    logits = np.array(logits)
    return dict(pbo=float((logits <= 0).mean()), n_paths=len(logits),
                logit_mean=float(logits.mean()))


# ── White's Reality Check (data snooping across a config family) ──────────────

def whites_reality_check(strat_rets: Sequence[np.ndarray], bench_ret: np.ndarray,
                         n_boot: int = 2000, mean_block: float = 20.0,
                         seed: int = 42) -> dict:
    """Bootstrap p-value that the *best* of many configs beats the benchmark by
    chance. strat_rets: list of per-bar return arrays (same length as bench)."""
    bench = np.asarray(bench_ret, float)
    diffs = [np.asarray(s, float) - bench for s in strat_rets]
    f_bar = np.array([d.mean() for d in diffs])
    v_obs = np.sqrt(len(bench)) * f_bar.max()
    idx_boot = stationary_bootstrap(np.arange(len(bench)), n_boot, mean_block, seed).astype(int)
    v_star = np.empty(n_boot)
    for b in range(n_boot):
        ii = idx_boot[b]
        vals = [np.sqrt(len(bench)) * (d[ii].mean() - d.mean()) for d in diffs]
        v_star[b] = max(vals)
    return dict(stat=float(v_obs), p_value=float((v_star >= v_obs).mean()))
