"""Improvement library — structural combinations (Part A) + swept tweaks (Part B).

Every function returns a **daily strategy return series** on the full frozen index
so the runner can slice design vs hold-out with proper warmup. Combinations reuse
the two production strategies unchanged (via engine); nothing here touches the
Pine ports.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared import indicators as ind
from testing.scripts import dataio, engine, features


# ── cached per-(asset,variant) run on the full frozen series ──────────────────

_CACHE: dict = {}


def variant(asset: str, variant_name: str):
    """(returns, df, s_bull) for a variant on the full series (fees=0)."""
    key = (asset, variant_name)
    if key not in _CACHE:
        daily = dataio.load(asset, split="all")
        btc = dataio.load_btc(split="all")
        df = engine.run(variant_name, daily, btc=btc)
        sb = engine.s_bull(variant_name)
        r = engine.strat_returns(df, s_bull_code=sb)
        _CACHE[key] = (r, df, sb)
    return _CACHE[key]


def asset_returns(asset: str) -> pd.Series:
    daily = dataio.load(asset, split="all")
    return daily["close"].pct_change().fillna(0.0)


# ── A1. Static ensemble ───────────────────────────────────────────────────────

def ensemble(asset: str, w_lean: float) -> pd.Series:
    rl, _, _ = variant(asset, "lean")
    rm, _, _ = variant(asset, "momentum")
    al = pd.concat([rl.rename("l"), rm.rename("m")], axis=1).fillna(0.0)
    return w_lean * al["l"] + (1 - w_lean) * al["m"]


# ── A2. Regime switch (Lean↔Momentum), 1-bar-lagged detector ──────────────────

def _detector(asset: str, kind: str) -> pd.Series:
    """True → 'bull/trending' → use Momentum; False → use Lean. Lagged 1 bar."""
    daily = dataio.load(asset, split="all")
    close = daily["close"]
    if kind == "btc200":
        btc = dataio.load_btc(split="all")["close"].reindex(close.index).ffill()
        det = btc > ind.sma(btc, 200)
    elif kind == "own200":
        det = close > ind.sma(close, 200)
    elif kind == "vol":
        logret = np.log(close / close.shift(1))
        av = ind.stdev_pop(logret, 20) * np.sqrt(365)
        det = av < av.rolling(200, min_periods=60).median()      # calm → momentum
    elif kind == "er":
        chg = close.diff(10).abs()
        vol = close.diff().abs().rolling(10).sum()
        er = np.where(vol > 0, chg / vol, 0.0)
        det = pd.Series(er, index=close.index) > 0.30            # trending → momentum
    else:
        raise ValueError(kind)
    return det.fillna(False).shift(1).fillna(False)


def regime_switch(asset: str, kind: str = "own200") -> pd.Series:
    rl, _, _ = variant(asset, "lean")
    rm, _, _ = variant(asset, "momentum")
    det = _detector(asset, kind)
    al = pd.concat([rl.rename("l"), rm.rename("m")], axis=1).fillna(0.0)
    d = det.reindex(al.index).fillna(False)
    return pd.Series(np.where(d.values, al["m"].values, al["l"].values), index=al.index)


# ── A3. Signal-agreement sizing ───────────────────────────────────────────────

def agreement(asset: str, half: float = 0.5) -> pd.Series:
    _, dl, sbl = variant(asset, "lean")
    _, dm, sbm = variant(asset, "momentum")
    ret = asset_returns(asset)
    lbull = (dl["signal_state"].shift(1) == sbl).reindex(ret.index).fillna(False)
    mbull = (dm["signal_state"].shift(1) == sbm).reindex(ret.index).fillna(False)
    pos = np.where(lbull & mbull, 1.0, np.where(lbull | mbull, half, 0.0))
    return pd.Series(ret.values * pos, index=ret.index)


# ── A5. Vol-weighted ensemble (risk parity between the two sleeves) ────────────

def vol_weighted(asset: str, lookback: int = 60) -> pd.Series:
    rl, _, _ = variant(asset, "lean")
    rm, _, _ = variant(asset, "momentum")
    al = pd.concat([rl.rename("l"), rm.rename("m")], axis=1).fillna(0.0)
    vl = al["l"].rolling(lookback, min_periods=20).std()
    vm = al["m"].rolling(lookback, min_periods=20).std()
    inv_l = 1.0 / vl.replace(0, np.nan)
    inv_m = 1.0 / vm.replace(0, np.nan)
    w_l = (inv_l / (inv_l + inv_m)).shift(1).fillna(0.5).clip(0, 1)
    return w_l * al["l"] + (1 - w_l) * al["m"]


# ── A4. Cross-sectional rotation (portfolio-level, returns ONE series) ─────────

def rotation(assets: list[str], k: int = 3, variant_name: str = "momentum") -> pd.Series:
    """Each day hold the top-k assets by signal strength (variants-bull count +
    normalized distance above trackline), equal weight, rest in cash."""
    strengths, rets = {}, {}
    idx = None
    for a in assets:
        _, dfm, sbm = variant(a, "momentum")
        _, dfl, sbl = variant(a, "lean")
        # strength = (#variants bull) + clipped dist above trackline
        mb = (dfm["signal_state"] == sbm).astype(float)
        lb = (dfl["signal_state"] == sbl).astype(float)
        dist = dfm["dist_pct"].clip(lower=0) / 20.0
        s = (mb + lb + dist).rename(a)
        # the sleeve return we earn if we hold this asset = chosen variant's return
        rr = variant(a, variant_name)[0].rename(a)
        strengths[a] = s
        rets[a] = rr
        idx = s.index if idx is None else idx.union(s.index)
    S = pd.DataFrame(strengths).reindex(idx).fillna(-1e9)
    R = pd.DataFrame(rets).reindex(idx).fillna(0.0)
    # pick top-k by yesterday's strength (no look-ahead)
    Slag = S.shift(1)
    port = pd.Series(0.0, index=idx)
    for ts in idx:
        row = Slag.loc[ts]
        valid = row[row > -1e8]
        if len(valid) == 0:
            continue
        top = valid.nlargest(min(k, len(valid))).index
        # only hold assets whose strength is actually bullish (>=1 → at least one variant bull)
        held = [a for a in top if row[a] >= 1.0]
        if held:
            port.loc[ts] = R.loc[ts, held].mean()
    return port


# ── Part B — per-variant sizing/signal tweaks ────────────────────────────────

def _daily_btc(asset):
    return dataio.load(asset, split="all"), dataio.load_btc(split="all")


def config_tweak(asset: str, variant_name: str, **ov) -> pd.Series:
    """Run a variant with config overrides (vol-target, reentry_hold, …)."""
    daily, btc = _daily_btc(asset)
    df = engine.run(variant_name, daily, btc=btc, **ov)
    return engine.strat_returns(df, s_bull_code=engine.s_bull(variant_name))


def parkinson_vol(asset: str, variant_name: str) -> pd.Series:
    """Override annual_vol with the Parkinson OHLC estimator (uses high/low, not
    close-to-close) — feeds both vol-sizing and vol-shock inside the state machine."""
    daily, btc = _daily_btc(asset)

    def override(df, cfg):
        hl = np.log(daily["high"] / daily["low"]).reindex(df.index)
        park_var = (hl ** 2) / (4.0 * np.log(2.0))
        park_daily = np.sqrt(park_var.rolling(cfg.vol_lookback, min_periods=cfg.vol_lookback).mean())
        df = df.copy()
        df["annual_vol"] = park_daily * np.sqrt(cfg.trading_days) * 100.0
        df["vol_avg50"] = ind.sma(df["annual_vol"], 50)
        mul = getattr(cfg, "vol_shock_mul", 1.5)
        df["vol_shock"] = (df["annual_vol"] > df["vol_avg50"] * mul) & df["below_tl"]
        return df

    df2 = engine.run_overlay(variant_name, daily, btc, override_fn=override, use_btc_filter=False)
    return engine.strat_returns(df2, s_bull_code=engine.s_bull(variant_name))


def graded_entry(asset: str, variant_name: str = "momentum") -> pd.Series:
    """Momentum: scale the in-market position by an RSI-based conviction
    (RSI 50→0.5, 70+→1.0) instead of the binary momentum_ok gate."""
    daily, btc = _daily_btc(asset)
    df = engine.run(variant_name, daily, btc=btc)
    sb = engine.s_bull(variant_name)
    base = engine.strat_returns(df, s_bull_code=sb)
    conv = ((df["rsi"] - 50.0) / 20.0).clip(0.5, 1.0)      # RSI 50→0.5, 70→1.0
    return base * conv.shift(1).fillna(1.0)


# thin adapters so features.py post-processors fit the (asset, variant) signature
def feat(asset, variant_name, fn, **kw):
    daily, btc = _daily_btc(asset)
    r, _ = fn(variant_name, daily, btc, **kw)
    return r
