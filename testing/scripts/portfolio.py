"""Hierarchical Risk Parity (López de Prado) portfolio construction (D2).

HRP allocates across assets by clustering the correlation matrix (no matrix
inversion, unlike mean-variance) → more robust out-of-sample. Variants:
  - pure HRP over the 8 sleeves
  - momentum-tilted HRP: HRP weights, but zero the assets not currently BULL
All weights use only trailing data (rolling covariance, shifted) — no look-ahead.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from testing.scripts import dataio, improvements as imp


def _quasi_diag(link):
    link = link.astype(int)
    sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
    num_items = link[-1, 3]
    while sort_ix.max() >= num_items:
        sort_ix.index = range(0, sort_ix.shape[0] * 2, 2)
        df0 = sort_ix[sort_ix >= num_items]
        i = df0.index; j = df0.values - num_items
        sort_ix[i] = link[j, 0]
        df0 = pd.Series(link[j, 1], index=i + 1)
        sort_ix = pd.concat([sort_ix, df0]).sort_index()
        sort_ix.index = range(sort_ix.shape[0])
    return sort_ix.tolist()


def _rec_bisect(cov, sort_ix):
    w = pd.Series(1.0, index=sort_ix)
    clusters = [sort_ix]
    while clusters:
        clusters = [c[j:k] for c in clusters for j, k in
                    ((0, len(c) // 2), (len(c) // 2, len(c))) if len(c) > 1]
        for i in range(0, len(clusters), 2):
            c0, c1 = clusters[i], clusters[i + 1]
            v0 = _cluster_var(cov, c0); v1 = _cluster_var(cov, c1)
            alpha = 1 - v0 / (v0 + v1)
            w[c0] *= alpha; w[c1] *= (1 - alpha)
    return w


def _cluster_var(cov, items):
    c = cov.loc[items, items]
    ivp = 1.0 / np.diag(c); ivp /= ivp.sum()
    return float(ivp @ c @ ivp)


def hrp_weights(returns: pd.DataFrame) -> pd.Series:
    """HRP weights from a returns window (columns = assets)."""
    r = returns.dropna(axis=1, how="all").fillna(0.0)
    if r.shape[1] < 2:
        return pd.Series(1.0, index=r.columns)
    cov = r.cov(); corr = r.corr().fillna(0.0)
    dist = np.sqrt(((1 - corr) / 2).clip(0, 1))
    np.fill_diagonal(dist.values, 0.0)
    link = linkage(squareform(dist.values, checks=False), "single")
    sort_ix = _quasi_diag(link)
    sort_ix = [corr.index[i] for i in sort_ix]
    w = _rec_bisect(cov, sort_ix)
    return (w / w.sum()).reindex(returns.columns).fillna(0.0)


def hrp_portfolio(assets, tilt_momentum=False, lookback=120, rebalance=20) -> pd.Series:
    """Daily HRP portfolio return. If tilt_momentum, zero non-BULL assets each day
    (equal-weight the BULL survivors by HRP within them)."""
    rets = pd.concat([imp.variant(a, "momentum")[0].rename(a) for a in assets] if tilt_momentum
                     else [imp.asset_returns(a).rename(a) for a in assets], axis=1)
    idx = rets.index
    # BULL masks for the tilt
    bull = {}
    if tilt_momentum:
        for a in assets:
            _, dfm, sbm = imp.variant(a, "momentum")
            bull[a] = (dfm["signal_state"].shift(1) == sbm).reindex(idx).fillna(False)
    port = pd.Series(0.0, index=idx)
    w = pd.Series(0.0, index=rets.columns)
    raw = pd.concat([imp.asset_returns(a).rename(a) for a in assets], axis=1).reindex(idx)
    for t in range(len(idx)):
        if t % rebalance == 0 and t > lookback:
            win = raw.iloc[t - lookback:t]
            w = hrp_weights(win)
        if tilt_momentum:
            m = np.array([bull[a].iloc[t] for a in rets.columns], float)
            wt = w.values * m
            wt = wt / wt.sum() if wt.sum() > 0 else wt
            port.iloc[t] = float(np.nansum(wt * raw.iloc[t].values))
        else:
            port.iloc[t] = float(np.nansum(w.values * raw.iloc[t].values))
    return port
