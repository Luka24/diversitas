"""Meta-labeling (López de Prado) — triple-barrier labels + purged CV + bet sizing.

The primary model is the existing Lean/Momentum strategy (it decides the *side*).
The secondary model decides the *size*: for each bar the strategy is in a BULL
position, we label whether that position ended up profitable (triple barrier), train
a classifier on lagged strategy features, and scale the position by the calibrated
probability. Trained inside a Purged K-Fold to avoid the label-overlap leakage that
ordinary CV misses.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared import indicators as ind
from testing.scripts import engine


# ── triple-barrier labels ─────────────────────────────────────────────────────

def triple_barrier_labels(close: pd.Series, atr: pd.Series, in_pos: np.ndarray,
                          k: float = 2.0, horizon: int = 20) -> pd.Series:
    """For each bar where in_pos is True, look forward up to `horizon` bars: label 1
    if price first rises by k·ATR (take-profit), 0 if it first falls by k·ATR (stop)
    or the horizon expires below entry. Forward-only (no look-ahead in the label)."""
    c = close.values
    a = atr.values
    n = len(c)
    lab = np.full(n, np.nan)
    for i in range(n):
        if not in_pos[i] or not np.isfinite(a[i]) or a[i] <= 0:
            continue
        up = c[i] + k * a[i]
        dn = c[i] - k * a[i]
        end = min(i + horizon, n - 1)
        outcome = 0
        for j in range(i + 1, end + 1):
            if c[j] >= up:
                outcome = 1; break
            if c[j] <= dn:
                outcome = 0; break
        else:
            outcome = 1 if c[end] > c[i] else 0
        lab[i] = outcome
    return pd.Series(lab, index=close.index)


# ── feature assembly (all lagged) ─────────────────────────────────────────────

FEATURES = ["dist_pct", "rsi", "annual_vol", "er", "bars_since_signal"]


def assemble_features(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for f in FEATURES:
        if f in df.columns:
            X[f] = df[f]
    # a couple of derived, all from columns present in both variants
    if "trackline" in df.columns:
        X["tl_slope"] = df["trackline"].pct_change(5)
    if "above_ma_reg" in df.columns:
        X["above_reg"] = df["above_ma_reg"].astype(float)
    elif "above_ma_long" in df.columns:
        X["above_reg"] = df["above_ma_long"].astype(float)
    return X.shift(1)                    # lag every feature by 1 bar


# ── Purged K-Fold ─────────────────────────────────────────────────────────────

class PurgedKFold:
    """Time-series K-fold that purges training samples whose label window overlaps
    the test fold and applies an embargo after it (López de Prado, AFML ch. 7)."""

    def __init__(self, n_splits: int = 5, horizon: int = 20, embargo: int = 10):
        self.n_splits = n_splits
        self.horizon = horizon
        self.embargo = embargo

    def split(self, n: int):
        idx = np.arange(n)
        folds = np.array_split(idx, self.n_splits)
        for f in folds:
            test = f
            t0, t1 = test[0], test[-1]
            purge_lo = t0 - self.horizon
            purge_hi = t1 + self.embargo
            train = idx[(idx < purge_lo) | (idx > purge_hi)]
            if len(train) > 50 and len(test) > 10:
                yield train, test


# ── meta-labeled returns ──────────────────────────────────────────────────────

def meta_label_returns(variant: str, daily: pd.DataFrame, btc, k: float = 2.0,
                       horizon: int = 20, threshold: float = 0.5,
                       model: str = "logit") -> pd.Series:
    """Return the meta-labeled (probability-sized) strategy returns for one asset."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler

    df = engine.run(variant, daily, btc=btc)
    sb = engine.s_bull(variant)
    base_ret = engine.strat_returns(df, s_bull_code=sb)
    in_pos = (df["signal_state"] == sb).values

    atr = ind.rma(ind.true_range(daily["high"], daily["low"], daily["close"]), 14).reindex(df.index)
    y = triple_barrier_labels(df["close"], atr, in_pos, k=k, horizon=horizon)
    X = assemble_features(df)

    mask = y.notna() & X.notna().all(axis=1)
    Xv, yv = X[mask], y[mask].astype(int)
    proba = pd.Series(1.0, index=df.index)      # default: full size (no info → trust primary)
    if mask.sum() < 100 or yv.nunique() < 2:
        return base_ret                          # not enough labels → primary unchanged

    pk = PurgedKFold(n_splits=5, horizon=horizon, embargo=10)
    Xarr, yarr = Xv.values, yv.values
    oos = np.full(len(Xv), np.nan)
    for tr, te in pk.split(len(Xv)):
        if yarr[tr].sum() in (0, len(tr)):
            continue
        sc = StandardScaler().fit(Xarr[tr])
        if model == "gbm":
            clf = GradientBoostingClassifier(n_estimators=60, max_depth=2, random_state=0)
            clf.fit(sc.transform(Xarr[tr]), yarr[tr])
        else:
            clf = LogisticRegression(max_iter=500, C=0.5)
            clf.fit(sc.transform(Xarr[tr]), yarr[tr])
        oos[te] = clf.predict_proba(sc.transform(Xarr[te]))[:, 1]
    p = pd.Series(oos, index=Xv.index).reindex(df.index)
    proba.loc[p.notna().index] = p.fillna(method="ffill").fillna(1.0)
    # size = probability above threshold, else 0 (meta-label filters weak signals)
    size = np.where(proba.values >= threshold, proba.values, 0.0)
    size = pd.Series(size, index=df.index).clip(0, 1)
    return base_ret * size.shift(1).fillna(1.0)
