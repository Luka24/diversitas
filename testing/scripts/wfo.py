"""Professional walk-forward optimization (WFO) for Lean/Momentum.

The three upgrades over a single-window Optuna pass:
  1. Per-fold re-optimization + stitched OOS — each anchored fold optimizes on its
     own train window, is applied as-is to the next unseen OOS block, and the OOS
     returns are concatenated into one composite backtest.
  2. Plateau selection — pick the centre of the best-performing parameter region
     (neighbourhood-averaged objective), not the single best (overfit) trial.
  3. Multi-seed — repeat the whole WFO across seeds for a stability distribution.

Everything is forward-only: fold params are fitted on train, applied to OOS as-is.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

from testing.scripts import dataio, engine, metrics

TD = 365
EMBARGO_DAYS = 21

# Sensitive shortlist per variant (from Phase 3), with search ranges.
SPACE = {
    "lean":     {"track_period": (45, 90, 5), "track_buf_pct": (1.5, 5.0, 0.5),
                 "reentry_hold": (5, 25, 1)},
    "momentum": {"track_period": (25, 55, 5), "track_buf_pct": (1.0, 4.0, 0.5),
                 "reentry_hold": (2, 10, 1), "target_vol_pct": (40, 90, 10)},
}

# Anchored OOS blocks (train = inception → block_start − embargo).
OOS_BLOCKS = [
    ("2022-07-01", "2022-12-31"),
    ("2023-01-01", "2023-06-30"),
    ("2023-07-01", "2023-12-31"),
    ("2024-01-01", "2024-06-30"),
    ("2024-07-01", "2025-03-31"),
]


def _sortino(r: np.ndarray) -> float:
    r = np.asarray(r, float)
    if len(r) < 10:
        return np.nan
    dd = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(TD)
    return float(r.mean() * TD / dd) if dd > 1e-9 else np.nan


def _calmar(r: np.ndarray) -> float:
    r = np.asarray(r, float)
    if len(r) < 10:
        return np.nan
    eq = np.cumprod(1 + r)
    mdd = (eq / np.maximum.accumulate(eq) - 1).min()
    cagr = eq[-1] ** (1 / max(len(r) / TD, 1e-9)) - 1
    return cagr / abs(mdd) if mdd < -1e-6 else np.nan


def config_returns(variant, daily, btc, cfg) -> pd.Series:
    df = engine.run(variant, daily, btc=btc, **cfg)
    return engine.strat_returns(df, s_bull_code=engine.s_bull(variant))


def _suggest(trial, space):
    cfg = {}
    for k, (lo, hi, st) in space.items():
        cfg[k] = (trial.suggest_int(k, lo, hi, step=st) if isinstance(st, int)
                  else trial.suggest_float(k, lo, hi, step=st))
    return cfg


def plateau_select(trials_params, trials_values, space, k=8) -> dict:
    """Return the config at the centre of the best plateau: for each candidate,
    score = mean objective of its k nearest neighbours in normalized param space.
    Pick the neighbourhood-max (robust), not the single best trial (overfit)."""
    keys = list(space)
    P = np.array([[tp[key] for key in keys] for tp in trials_params], float)
    v = np.array(trials_values, float)
    ok = np.isfinite(v)
    P, v, tp_ok = P[ok], v[ok], [t for t, o in zip(trials_params, ok) if o]
    if len(v) == 0:
        return {}
    # normalize each param to [0,1] by its search range
    span = np.array([(space[key][1] - space[key][0]) or 1 for key in keys], float)
    lo = np.array([space[key][0] for key in keys], float)
    Pn = (P - lo) / span
    plateau = np.empty(len(v))
    for i in range(len(v)):
        d = np.sqrt(((Pn - Pn[i]) ** 2).sum(axis=1))
        nn = np.argsort(d)[:min(k, len(v))]
        plateau[i] = np.nanmean(v[nn])
    best = int(np.argmax(plateau))
    return dict(tp_ok[best])


def optimize_fold(variant, daily, btc, train_end, n_trials=80, seed=42) -> dict:
    """Optuna on the train slice, then plateau-select the robust config."""
    space = SPACE[variant]
    params, values = [], []

    def objective(trial):
        cfg = _suggest(trial, space)
        r = config_returns(variant, daily, btc, cfg)
        s = _sortino(r.loc[:train_end].values)
        params.append(cfg); values.append(s if np.isfinite(s) else -1e9)
        return -(s if np.isfinite(s) else -1e9)

    study = optuna.create_study(direction="minimize",
                                sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return plateau_select(params, values, space)


def stitched_oos(variant, asset, seed=42, n_trials=80):
    """Per-fold WFO: optimize on train, apply to OOS as-is, stitch OOS returns.
    Returns (stitched_optimized, stitched_default, fold_params)."""
    daily = dataio.load(asset, split="all")
    btc = dataio.load_btc(split="all")
    opt_parts, def_parts, fold_params = [], [], []
    default_r = config_returns(variant, daily, btc, {})
    for (ts, te) in OOS_BLOCKS:
        ts_, te_ = pd.Timestamp(ts, tz="UTC"), pd.Timestamp(te, tz="UTC")
        train_end = ts_ - pd.Timedelta(days=EMBARGO_DAYS)
        best = optimize_fold(variant, daily, btc, train_end, n_trials=n_trials, seed=seed)
        fold_params.append(best)
        r_opt = config_returns(variant, daily, btc, best) if best else default_r
        opt_parts.append(r_opt.loc[ts_:te_])
        def_parts.append(default_r.loc[ts_:te_])
    return pd.concat(opt_parts), pd.concat(def_parts), fold_params


def multi_seed_wfo(variant, asset, seeds=(42, 123, 7, 2024, 9999), n_trials=80):
    """Run the WFO across seeds; return per-seed stitched-OOS metrics + params."""
    rows, def_metrics = [], None
    for sd in seeds:
        opt, dflt, fps = stitched_oos(variant, asset, seed=sd, n_trials=n_trials)
        rows.append(dict(seed=sd,
                         opt_sortino=_sortino(opt.values), opt_calmar=_calmar(opt.values),
                         params=fps))
        if def_metrics is None:
            def_metrics = dict(def_sortino=_sortino(dflt.values), def_calmar=_calmar(dflt.values),
                               stitched_default=dflt, stitched_index=dflt.index)
    return rows, def_metrics
