"""Phase 7 feature library — each Q&A improvement idea, testable in isolation.

Every function returns a **strategy daily-return series** for a given
(variant, asset), so the A/B harness can compare it to the baseline on identical
frozen data. Signal-level ideas are implemented as *column overlays* on the real
`compute_features → run_state_machine` path (see engine.run_overlay), so we never
touch the validated Pine port; position-level ideas post-process the position.

Implemented (mapped to the Q&A doc):
  atr_buffer       — dynamic ATR trackline buffer  (Q&A §2, "dynamic buffer")
  atr_blowoff      — ATR-normalized blow-off trigger (Q&A §8, "trigger=RSI>80 & (px-TL)/ATR>k")
  ema_volshock     — EMA instead of SMA for the vol-shock reference (Q&A §5)
  kelly            — half/quarter-Kelly position sizing (Q&A §1, Kelly Criterion)
  weekend_skip     — suppress signal changes on weekends (Q&A §8, "weekend skip")
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
from testing.scripts import engine, metrics


def _atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    tr = ind.true_range(df["high"], df["low"], df["close"])
    return ind.rma(tr, length)


# ── baseline ──────────────────────────────────────────────────────────────────

def baseline(variant, daily, btc, **ov):
    df = engine.run(variant, daily, btc=btc, **ov)
    sb = engine.s_bull(variant)
    return engine.strat_returns(df, s_bull_code=sb), df


# ── 1. Dynamic ATR trackline buffer ───────────────────────────────────────────

def atr_buffer(variant, daily, btc, k=2.0, k_down=None):
    """Replace the fixed % trackline buffer with k·ATR(14). Asymmetric if k_down set."""
    ku, kd = k, (k_down if k_down is not None else k)

    def override(df, cfg):
        atr = _atr(daily).reindex(df.index)
        tl = df["trackline"]
        close = df["close"]
        df = df.copy()
        df["above_tl"] = close > (tl + ku * atr)
        df["below_tl"] = close < (tl - kd * atr)
        return _rebuild_bull(df, cfg, variant)

    d2 = engine.run_overlay(variant, daily, btc, override_fn=override, use_btc_filter=False)
    sb = engine.s_bull(variant)
    return engine.strat_returns(d2, s_bull_code=sb), d2


# ── 2. ATR-normalized blow-off ────────────────────────────────────────────────

def atr_blowoff(variant, daily, btc, pct=97.5):
    """blowoff = RSI>80 AND (close-trackline)/ATR > percentile(ratio, pct)."""
    def override(df, cfg):
        atr = _atr(daily).reindex(df.index)
        ratio = (df["close"] - df["trackline"]) / atr.replace(0, np.nan)
        thr = np.nanpercentile(ratio.values[np.isfinite(ratio.values)], pct)
        df = df.copy()
        df["blowoff"] = (ratio > thr) & (df["rsi"] > 80)
        return df

    d2 = engine.run_overlay(variant, daily, btc, override_fn=override, use_btc_filter=False)
    sb = engine.s_bull(variant)
    return engine.strat_returns(d2, s_bull_code=sb), d2


# ── 3. EMA vol-shock reference ────────────────────────────────────────────────

def ema_volshock(variant, daily, btc):
    """Use EMA(50) of annual_vol as the vol-shock reference instead of SMA(50)."""
    def override(df, cfg):
        df = df.copy()
        ema_ref = ind.ema(df["annual_vol"], 50)
        mul = getattr(cfg, "vol_shock_mul", 1.5)
        df["vol_shock"] = (df["annual_vol"] > ema_ref * mul) & df["below_tl"]
        return df

    d2 = engine.run_overlay(variant, daily, btc, override_fn=override, use_btc_filter=False)
    sb = engine.s_bull(variant)
    return engine.strat_returns(d2, s_bull_code=sb), d2


# ── 4. Kelly position sizing (post-process) ───────────────────────────────────

def kelly(variant, daily, btc, fraction=0.5, lookback=20):
    """Scale the in-market position by a rolling (fraction·)Kelly computed from the
    trailing `lookback` closed trades. fraction=0.5 → half-Kelly, 0.25 → quarter."""
    _, df = baseline(variant, daily, btc)
    sb = engine.s_bull(variant)
    trades = [t for t in metrics.build_trades(df, s_bull=sb) if not t["open"]]
    # step function: after each trade close, Kelly for the next entry
    kelly_at = {}
    pnls = []
    for t in trades:
        p_arr = np.array(pnls[-lookback:]) if pnls else np.array([])
        if len(p_arr) >= 5:
            wins = p_arr[p_arr > 0]; losses = p_arr[p_arr <= 0]
            p = len(wins) / len(p_arr)
            b = (wins.mean() / abs(losses.mean())) if len(losses) and losses.mean() != 0 else 2.0
            kf = (p * b - (1 - p)) / b if b > 0 else 0.0
            kelly_at[t["entry_date"]] = float(np.clip(kf * fraction, 0.0, 1.0))
        pnls.append(t["pnl_pct"])
    # build per-bar multiplier: at each entry use its kelly, hold until exit
    mult = pd.Series(1.0, index=df.index)
    cur = 1.0
    entries = {t["entry_date"]: kelly_at.get(t["entry_date"], 1.0) for t in trades}
    changed = df["signal_changed"].fillna(False)
    for ts in df.index:
        if ts in entries:
            cur = entries[ts]
        mult.loc[ts] = cur
    base_ret = engine.strat_returns(df, s_bull_code=sb)
    scaled = base_ret * mult.shift(1).fillna(1.0)
    return scaled, df


# ── 5. Weekend skip ───────────────────────────────────────────────────────────

def weekend_skip(variant, daily, btc):
    """Suppress signal *changes* on Sat/Sun — hold the Friday position over weekends."""
    _, df = baseline(variant, daily, btc)
    sb = engine.s_bull(variant)
    is_wknd = df.index.dayofweek >= 5
    sig = df["signal_state"].copy().values
    # forward-hold across weekend bars
    for i in range(1, len(sig)):
        if is_wknd[i]:
            sig[i] = sig[i - 1]
    df2 = df.copy()
    df2["signal_state"] = sig
    df2["signal_changed"] = pd.Series(sig, index=df.index).ne(
        pd.Series(sig, index=df.index).shift(1)).fillna(False).values
    # position off held signal; target_alloc held too
    ta = df["target_alloc"].copy().values
    for i in range(1, len(ta)):
        if is_wknd[i]:
            ta[i] = ta[i - 1]
    df2["target_alloc"] = ta
    return engine.strat_returns(df2, s_bull_code=sb), df2


# ── 6-8. position post-processors (profit-taking, lean trailing, DD brake) ────

def _position_multiplier(df, sb, rule):
    """Walk bull runs; `rule(entry_px, peak, close, bars_in) -> multiplier in [0,1]`.
    Returns a per-bar multiplier series aligned to df.index (applied to next bar)."""
    close = df["close"].values
    sig = df["signal_state"].values
    mult = np.ones(len(df))
    entry_px = np.nan; peak = np.nan; bars_in = 0
    for i in range(len(df)):
        if sig[i] == sb:
            if np.isnan(entry_px) or (i > 0 and sig[i - 1] != sb):
                entry_px = close[i]; peak = close[i]; bars_in = 0
            peak = max(peak, close[i]); bars_in += 1
            mult[i] = rule(entry_px, peak, close[i], bars_in)
        else:
            entry_px = np.nan; peak = np.nan; bars_in = 0
            mult[i] = 1.0
    return pd.Series(mult, index=df.index)


def profit_taking(variant, daily, btc, l1=50.0, l2=100.0):
    """Scale out: 100%→75% above +l1% unrealized, →50% above +l2%. (Q&A 'profit taking')"""
    _, df = baseline(variant, daily, btc); sb = engine.s_bull(variant)
    def rule(e, pk, c, n):
        g = (c / e - 1) * 100
        return 0.5 if g >= l2 else 0.75 if g >= l1 else 1.0
    m = _position_multiplier(df, sb, rule)
    return engine.strat_returns(df, s_bull_code=sb) * m.shift(1).fillna(1.0), df


def add_trailing(variant, daily, btc, trail_pct=12.0):
    """Add a peak-trailing stop (Lean has none; Momentum already trails). Force flat
    for the rest of a run once close falls trail_pct% below the run peak."""
    _, df = baseline(variant, daily, btc); sb = engine.s_bull(variant)
    stopped = {"on": False}
    def rule(e, pk, c, n):
        if n == 1:
            stopped["on"] = False
        if c < pk * (1 - trail_pct / 100.0):
            stopped["on"] = True
        return 0.0 if stopped["on"] else 1.0
    m = _position_multiplier(df, sb, rule)
    return engine.strat_returns(df, s_bull_code=sb) * m.shift(1).fillna(1.0), df


def rolling_peak_brake(variant, daily, btc, dd_pct=30.0, window=365, cut=0.5):
    """Reduce position to `cut` when price is >dd_pct below its rolling `window`-day
    peak (bear-market brake). (Q&A §3, rolling 365d peak)."""
    _, df = baseline(variant, daily, btc); sb = engine.s_bull(variant)
    peak = df["close"].rolling(window, min_periods=100).max()
    dd = (df["close"] / peak - 1.0) * 100.0
    brake = np.where(dd < -dd_pct, cut, 1.0)
    m = pd.Series(brake, index=df.index)
    return engine.strat_returns(df, s_bull_code=sb) * m.shift(1).fillna(1.0), df


# ── helper: rebuild bull_condition after changing above_tl ────────────────────

def _rebuild_bull(df, cfg, variant):
    """Recompute bull_condition with the (possibly overridden) above_tl, matching
    each variant's gate structure."""
    df = df.copy()
    if variant == "momentum":
        regime_blocks = df["bear_regime"] & (getattr(cfg, "bear_size_cut", 50) <= 0.0)
        df["regime_blocks"] = regime_blocks
        df["bull_condition"] = (df["above_tl"] & df["above_ma_fast"] & df["momentum_ok"]
                                & df["track_rising_window"] & df["er_ok"]
                                & df["btc_filter_ok"] & ~regime_blocks).fillna(False)
    else:  # lean — exact factors from lean/diversitas/strategy.py:98
        df["bull_condition"] = (
            df["above_tl"] & df["above_ma_med"] & df["track_rising_window"]
            & df["dist_entry_ok"] & df["regime_ok"] & df["btc_filter_ok"]
            & df["er_ok"]).fillna(False)
    df["green_dot"] = df["bull_condition"]
    df["red_dot"] = df["below_tl"]
    return df


FEATURES = {
    "atr_buffer_k2":       lambda v, d, b: atr_buffer(v, d, b, k=2.0),
    "atr_buffer_k2.5":     lambda v, d, b: atr_buffer(v, d, b, k=2.5),
    "atr_buffer_asym":     lambda v, d, b: atr_buffer(v, d, b, k=2.5, k_down=1.5),
    "atr_blowoff_p97.5":   lambda v, d, b: atr_blowoff(v, d, b, pct=97.5),
    "ema_volshock":        lambda v, d, b: ema_volshock(v, d, b),
    "kelly_half":          lambda v, d, b: kelly(v, d, b, fraction=0.5),
    "kelly_quarter":       lambda v, d, b: kelly(v, d, b, fraction=0.25),
    "weekend_skip":        lambda v, d, b: weekend_skip(v, d, b),
    "profit_taking":       lambda v, d, b: profit_taking(v, d, b),
    "add_trailing_12":     lambda v, d, b: add_trailing(v, d, b, trail_pct=12.0),
    "rolling_peak_brake":  lambda v, d, b: rolling_peak_brake(v, d, b),
}
