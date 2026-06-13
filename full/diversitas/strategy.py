"""Diversitas Pro v3 strategy engine — Python port of diversitas_pro_v3_200ma.pine.

Usage:
    result = run_strategy(daily, btc_daily, config)
    result.df       # full per-bar DataFrame with every signal column
    result.summary  # dict with latest-bar status (for dashboard panel)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math

import numpy as np
import pandas as pd

from shared import indicators as ind
from shared.data_source import to_weekly
from .config import Config, DEFAULT_CONFIG


# State codes — mirror Pine
S_BULL = 1
S_NEUTRAL = 2
S_BEAR = 3


@dataclass
class StrategyResult:
    df: pd.DataFrame
    summary: dict


def _align_weekly(weekly_value: pd.Series, daily_index: pd.DatetimeIndex) -> pd.Series:
    """Forward-fill weekly value onto daily index.

    Pine's request.security(tf='W', expr) returns the value of the *closed*
    weekly bar; intraweek it carries the prior weekly value. We replicate
    by shifting the weekly series by 1 bar before reindexing (so today
    sees the previous fully-closed week), then forward-fill.
    """
    shifted = weekly_value.shift(1).reindex(weekly_value.index.union(daily_index))
    return shifted.sort_index().ffill().reindex(daily_index)


def compute_features(daily: pd.DataFrame, btc_daily: Optional[pd.DataFrame],
                     cfg: Config) -> pd.DataFrame:
    """Compute all per-bar features required by the state machines."""
    df = daily.copy()
    high, low, close, volume = df["high"], df["low"], df["close"], df["volume"]

    # --- Trackline (Kijun) ---
    track_high = ind.highest(high, cfg.track_period)
    track_low = ind.lowest(low, cfg.track_period)
    df["trackline"] = (track_high + track_low) / 2.0
    df["track_rising"] = df["trackline"] > df["trackline"].shift(1)
    buf_amt = df["trackline"] * (cfg.track_buf_pct / 100.0)
    df["above_tl"] = close > (df["trackline"] + buf_amt)
    df["below_tl"] = close < (df["trackline"] - buf_amt)
    df["dist_pct"] = (close - df["trackline"]) / df["trackline"] * 100.0

    # --- Basic momentum ---
    df["rsi"] = ind.rsi(close, cfg.rsi_len)
    f_ema = ind.ema(close, cfg.ema_fast)
    s_ema = ind.ema(close, cfg.ema_slow)
    df["ema_fast"] = f_ema
    df["ema_slow"] = s_ema
    vol_ma = ind.sma(volume, cfg.vol_len)
    df["vol_ratio"] = (volume / vol_ma).where(vol_ma > 0, 1.0)

    # --- 200 MA bear filter ---
    sma200 = ind.sma(close, 200)
    df["sma200"] = sma200
    df["sma200_falling"] = sma200 < sma200.shift(1)
    df["below_sma200"] = close < sma200
    df["bear_market"] = df["below_sma200"] & df["sma200_falling"]

    # --- ADX normalized ---
    adx_val = ind.adx(high, low, close, cfg.adx_len)
    df["adx"] = adx_val
    df["adx_mean"] = ind.sma(adx_val, 100)
    df["adx_ok"] = adx_val > df["adx_mean"]

    # --- Market structure (HH/LL) ---
    hh = ind.highest(high, cfg.struct_len).shift(1)
    ll = ind.lowest(low, cfg.struct_len).shift(1)
    bars_last_hh = ind.bars_since(high >= hh)
    bars_last_ll = ind.bars_since(low <= ll)
    df["structure_bull"] = bars_last_ll > bars_last_hh

    # --- Weekly macro (computed on weekly, aligned back to daily) ---
    weekly = to_weekly(daily)
    wk_ema = ind.ema(weekly["close"], cfg.wk_ema_len)
    wk_sma = ind.sma(weekly["close"], cfg.wk_sma_len)
    wk_close = weekly["close"]
    wk_ema_20 = ind.ema(weekly["close"], 20)

    wk_ema_aligned = _align_weekly(wk_ema, df.index)
    wk_ema_prev_aligned = _align_weekly(wk_ema.shift(1), df.index)
    wk_sma_aligned = _align_weekly(wk_sma, df.index)
    wk_close_aligned = _align_weekly(wk_close, df.index)
    wk_ema20_aligned = _align_weekly(wk_ema_20, df.index)

    df["wk_ema"] = wk_ema_aligned
    df["wk_sma"] = wk_sma_aligned
    df["wk_close"] = wk_close_aligned
    df["wk_ema_rising"] = wk_ema_aligned > wk_ema_prev_aligned
    df["above_wk_sma"] = wk_close_aligned > wk_sma_aligned
    df["wk_close_above_wk_ema"] = wk_close_aligned > wk_ema_aligned
    df["htf_bull"] = wk_close_aligned > wk_ema20_aligned

    # --- BTC filter ---
    if cfg.use_btc_filter and btc_daily is not None and not btc_daily.empty:
        btc_close = btc_daily["close"]
        btc_ema50 = ind.ema(btc_close, 50)
        btc_bull = (btc_close > btc_ema50).reindex(df.index).ffill().fillna(False)
        df["btc_bull"] = btc_bull
        df["btc_filter_ok"] = btc_bull
    else:
        df["btc_bull"] = True
        df["btc_filter_ok"] = True

    # --- Volatility ---
    log_ret = np.log(close / close.shift(1))
    df["log_ret"] = log_ret
    daily_std = ind.stdev_pop(log_ret, cfg.vol_lookback)
    df["annual_vol"] = daily_std * math.sqrt(365) * 100.0
    vol_sma100 = ind.sma(df["annual_vol"], 100)
    vol_std100 = ind.stdev_pop(df["annual_vol"], 100)
    df["vol_z"] = ((df["annual_vol"] - vol_sma100) / vol_std100.replace(0, np.nan)).fillna(0.0)
    df["high_vol_regime"] = df["vol_z"] > 1.0
    df["low_vol_regime"] = df["vol_z"] < -1.0

    # --- Drawdown ---
    df["peak"] = close.cummax()
    df["dd_pct"] = (close - df["peak"]) / df["peak"] * 100.0

    # --- Emergency triggers ---
    df["blowoff"] = (df["dist_pct"] > cfg.blowoff_dist_pct) & (df["rsi"] > 80)
    vol_avg50 = ind.sma(df["annual_vol"], 50)
    df["vol_shock"] = df["annual_vol"] > (vol_avg50 * cfg.vol_shock_mul)

    # --- Conviction score components ---
    trend_raw = ((df["dist_pct"] + 5.0) / 10.0).clip(0.0, 1.0)
    trend_bonus = df["track_rising"].astype(float) * 0.1
    df["trend_score"] = (trend_raw + trend_bonus).clip(upper=1.0) * 30.0

    rsi_norm = ((df["rsi"] - 30.0) / 35.0).clip(0.0, 1.0)
    ema_spread = (f_ema - s_ema) / s_ema * 100.0
    ema_norm = ((ema_spread + 2.0) / 5.0).clip(0.0, 1.0)
    df["mom_score"] = (rsi_norm * 0.5 + ema_norm * 0.5) * 25.0

    df["macro_score"] = (
        df["wk_ema_rising"].astype(float) * 0.4
        + df["above_wk_sma"].astype(float) * 0.4
        + df["wk_close_above_wk_ema"].astype(float) * 0.2
    ) * 20.0

    vol_norm = ((df["vol_ratio"] - 0.5) / 1.5).clip(0.0, 1.0)
    df["vol_score"] = vol_norm * 15.0

    dd_norm = ((df["dd_pct"] + 30.0) / 30.0).clip(0.0, 1.0)
    dd_penalty = np.where(df["track_rising"], 0.3, 1.0)
    df["dd_score"] = dd_norm * 10.0 * dd_penalty

    df["raw_conviction"] = (
        df["trend_score"] + df["mom_score"] + df["macro_score"]
        + df["vol_score"] + df["dd_score"]
    )
    df["conviction"] = ind.sma(df["raw_conviction"], cfg.conv_smooth)

    # --- Trend persistence (for allocation only) ---
    up_close = (close > close.shift(1)).astype(float)
    df["trend_persistence"] = up_close.rolling(10, min_periods=10).mean()

    # --- Vol scale (kept for the dashboard volatility panel) ---
    vol_scale = np.where(
        df["annual_vol"] > 0,
        np.minimum(1.0, cfg.target_vol_pct / df["annual_vol"].replace(0, np.nan)),
        1.0,
    )
    df["vol_scale"] = vol_scale
    # Final allocation is BINARY (0 % or 100 %) — populated by the state
    # machine from signal_state. Initialised here so the column exists.
    # This is a DELIBERATE deviation from Pine: Pine's `finalAlloc` is the
    # continuous `conviction * volScale * trendPersistence` value, which
    # can be partial even when signalState == BEAR. We treat the signal as
    # the source of truth and allocate either all-in or all-out.
    df["final_alloc"] = 0.0

    # --- Dynamic threshold ---
    bear_penalty = np.where(df["bear_market"], 15.0, 0.0)
    base_thresh = np.where(
        df["high_vol_regime"], 70.0,
        np.where(df["low_vol_regime"], 55.0, 60.0),
    )
    df["dynamic_threshold"] = np.minimum(85.0, base_thresh + bear_penalty)

    # --- Weekend mask (crypto trades 24/7 but Pine optionally suppresses) ---
    if cfg.skip_weekend:
        dow = df.index.dayofweek  # Mon=0 .. Sun=6
        df["is_weekend"] = pd.Series((dow == 5) | (dow == 6), index=df.index)
    else:
        df["is_weekend"] = pd.Series(False, index=df.index)

    # --- Green / red dots ---
    df["green_dot"] = (
        df["above_tl"]
        & (df["conviction"] >= df["dynamic_threshold"])
        & df["adx_ok"]
        & df["structure_bull"]
        & df["btc_filter_ok"]
        & df["htf_bull"]
        & ~df["is_weekend"]
    ).fillna(False)
    df["red_dot"] = (df["below_tl"] & ~df["is_weekend"]).fillna(False)

    return df


def run_state_machines(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Forward pass replicating Pine's three var-int state machines:
        raw_state, display_state, signal_state
    plus the housekeeping counters.
    """
    n = len(df)
    raw_state = np.full(n, S_BEAR, dtype=np.int8)
    display_state = np.full(n, S_BEAR, dtype=np.int8)
    signal_state = np.full(n, S_BEAR, dtype=np.int8)
    bars_since_signal = np.zeros(n, dtype=np.int32)
    green_absent = np.zeros(n, dtype=np.int32)
    below_count = np.zeros(n, dtype=np.int32)
    raw_hold = np.zeros(n, dtype=np.int32)
    signal_changed = np.zeros(n, dtype=bool)
    # Binary allocation: 100 % when BULL, 0 % otherwise. See note in
    # compute_features about the deliberate deviation from Pine.
    final_alloc = np.zeros(n, dtype=np.float32)

    # Init mirrors Pine var defaults
    cur_raw = S_BEAR
    cur_disp = S_BEAR
    cur_sig = S_BEAR
    prev_raw = S_BEAR
    prev_sig = S_BEAR
    green_absent_c = 0
    below_c = 0
    raw_hold_c = 0
    bars_since_sig = 999

    below_arr = df["below_tl"].fillna(False).to_numpy()
    above_arr = df["above_tl"].fillna(False).to_numpy()
    green_arr = df["green_dot"].fillna(False).to_numpy()
    blowoff_arr = df["blowoff"].fillna(False).to_numpy()
    vol_shock_arr = df["vol_shock"].fillna(False).to_numpy()
    weekend_arr = df["is_weekend"].fillna(False).to_numpy()

    for i in range(n):
        is_we = bool(weekend_arr[i])

        # Pine increments barsSinceSignal unconditionally each bar
        bars_since_sig += 1

        if not is_we:
            # --- rawState ---
            if below_arr[i]:
                cur_raw = S_BEAR
            elif green_arr[i]:
                cur_raw = S_BULL
            elif above_arr[i]:
                cur_raw = S_NEUTRAL
            # else: hold

            # --- counters ---
            if not green_arr[i] and above_arr[i]:
                green_absent_c += 1
            else:
                green_absent_c = 0
            if below_arr[i]:
                below_c += 1
            else:
                below_c = 0
            if cur_raw == prev_raw:
                raw_hold_c += 1
            else:
                raw_hold_c = 1
            prev_raw = cur_raw

            # --- displayState ---
            if below_arr[i] and below_c >= cfg.exit_grace_bars:
                cur_disp = S_BEAR
            elif above_arr[i] and green_arr[i]:
                cur_disp = S_BULL
            elif above_arr[i] and (not green_arr[i]) and green_absent_c >= cfg.grace_bars:
                cur_disp = S_NEUTRAL
            # else: hold

            # --- signalState (BEAR conditions checked first) ---
            went_bear = False
            if cur_raw == S_BEAR and below_c >= cfg.exit_grace_bars and cur_sig != S_BEAR:
                cur_sig = S_BEAR
                went_bear = True
            elif blowoff_arr[i] and cur_sig == S_BULL:
                cur_sig = S_BEAR
                went_bear = True
            elif vol_shock_arr[i] and below_arr[i] and cur_sig != S_BEAR:
                cur_sig = S_BEAR
                went_bear = True
            elif (cur_raw == S_BULL
                  and cur_sig != S_BULL
                  and raw_hold_c >= cfg.confirm_bars
                  and bars_since_sig >= cfg.reentry_hold):
                cur_sig = S_BULL
                bars_since_sig = 0

        # Track signal change (Pine: signalChanged = signalState != prevSignal)
        signal_changed[i] = (cur_sig != prev_sig)
        prev_sig = cur_sig

        raw_state[i] = cur_raw
        display_state[i] = cur_disp
        signal_state[i] = cur_sig
        bars_since_signal[i] = bars_since_sig
        green_absent[i] = green_absent_c
        below_count[i] = below_c
        raw_hold[i] = raw_hold_c
        final_alloc[i] = 100.0 if cur_sig == S_BULL else 0.0

    df = df.copy()
    df["raw_state"] = raw_state
    df["display_state"] = display_state
    df["signal_state"] = signal_state
    df["bars_since_signal"] = bars_since_signal
    df["green_absent"] = green_absent
    df["below_count"] = below_count
    df["raw_hold"] = raw_hold
    df["signal_changed"] = signal_changed
    df["final_alloc"] = final_alloc  # overwrites the placeholder from compute_features
    return df


def _state_label(code: int, display: bool = False) -> str:
    if code == S_BULL:
        return "BULL"
    if code == S_NEUTRAL:
        return "HEDGED" if display else "NEUTRAL"
    return "BEAR"


def build_summary(df: pd.DataFrame) -> dict:
    """Latest-bar status table — mirrors Pine table.cell layout."""
    last = df.iloc[-1]
    bear_market = bool(last["bear_market"])
    bear_penalty = 15 if bear_market else 0
    if bear_market:
        ma_status = f"BEAR MKT (thr +{bear_penalty})"
    elif bool(last["below_sma200"]):
        ma_status = "BELOW"
    else:
        ma_status = "ABOVE"
    return {
        "time": last.name,
        "close": float(last["close"]),
        "signal": _state_label(int(last["signal_state"])),
        "regime": _state_label(int(last["display_state"]), display=True),
        "ma200_status": ma_status,
        "bear_market": bear_market,
        "threshold": float(last["dynamic_threshold"]),
        "conviction": float(last["conviction"]),
        "trackline": float(last["trackline"]),
        "track_rising": bool(last["track_rising"]),
        "dist_pct": float(last["dist_pct"]),
        "trend_quality_pct": float(last["trend_persistence"] * 100.0) if pd.notna(last["trend_persistence"]) else float("nan"),
        "annual_vol": float(last["annual_vol"]),
        "final_alloc": float(last["final_alloc"]) if pd.notna(last["final_alloc"]) else float("nan"),
        "high_vol_regime": bool(last["high_vol_regime"]),
        "low_vol_regime": bool(last["low_vol_regime"]),
        "blowoff": bool(last["blowoff"]),
        "vol_shock": bool(last["vol_shock"]),
        "btc_bull": bool(last["btc_bull"]),
    }


def run_strategy(daily: pd.DataFrame,
                 btc_daily: Optional[pd.DataFrame] = None,
                 config: Config = DEFAULT_CONFIG) -> StrategyResult:
    """Full pipeline: features → state machines → summary."""
    df = compute_features(daily, btc_daily, config)
    df = run_state_machines(df, config)
    return StrategyResult(df=df, summary=build_summary(df))
