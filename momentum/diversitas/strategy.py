"""Diversitas Momentum strategy engine — Python port of `diversitas_momentum.pine`.

Key differences from Lean:
  - Fast trackline (35 bars vs 75)
  - Bear regime is SOFT (reduces position size, does not block entries unless bear_size_cut=0)
  - Trailing stop tracks peak close since entry; exits if price < peak * (1 - trail_pct%)
  - momentumOK = RSI > 50 AND close > slowEMA (55)
  - Vol-targeted allocation is real (partial in bear regime), not binary
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math

import numpy as np
import pandas as pd

from shared import indicators as ind
from .config import MomentumConfig, DEFAULT_CONFIG


S_BULL = 1
S_NEUTRAL = 2
S_BEAR = 3


@dataclass
class StrategyResult:
    df: pd.DataFrame
    summary: dict


def compute_features(daily: pd.DataFrame, btc_daily: Optional[pd.DataFrame],
                     cfg: MomentumConfig) -> pd.DataFrame:
    df = daily.copy()
    high, low, close = df["high"], df["low"], df["close"]

    # --- Trackline ---
    track_high = ind.highest(high, cfg.track_period)
    track_low  = ind.lowest(low,  cfg.track_period)
    df["trackline"] = (track_high + track_low) / 2.0
    df["track_rising"] = df["trackline"] > df["trackline"].shift(1)
    df["track_rising_window"] = df["trackline"] > df["trackline"].shift(cfg.track_slope_bars)
    buf_amt = df["trackline"] * (cfg.track_buf_pct / 100.0)
    df["above_tl"] = close > (df["trackline"] + buf_amt)
    df["below_tl"] = close < (df["trackline"] - buf_amt)
    df["dist_pct"] = (close - df["trackline"]) / df["trackline"] * 100.0

    # --- Moving averages ---
    ma_fast = ind.sma(close, cfg.ma_fast_len)
    ma_reg  = ind.sma(close, cfg.ma_reg_len)
    df["ma_fast"] = ma_fast
    df["ma_reg"]  = ma_reg
    df["above_ma_fast"] = close > ma_fast
    df["above_ma_reg"]  = close > ma_reg
    df["ma_reg_falling"] = ma_reg < ma_reg.shift(cfg.ma_slope)
    df["bear_regime"] = (~df["above_ma_reg"]) & df["ma_reg_falling"]

    # --- RSI ---
    df["rsi"] = ind.rsi(close, cfg.rsi_len)

    # --- Slow EMA (momentum filter) ---
    df["ema_slow"] = ind.ema(close, cfg.ema_slow_len)
    df["momentum_ok"] = (df["rsi"] > 50) & (close > df["ema_slow"])

    # --- Volatility ---
    log_ret = np.log(close / close.shift(1))
    df["log_ret"] = log_ret
    daily_std = ind.stdev_pop(log_ret, cfg.vol_lookback)
    df["annual_vol"] = daily_std * math.sqrt(cfg.trading_days) * 100.0
    df["vol_avg50"]  = ind.sma(df["annual_vol"], 50)

    # --- BTC filter ---
    if cfg.use_btc_filter and btc_daily is not None and not btc_daily.empty:
        btc_close = btc_daily["close"]
        btc_ema50 = ind.ema(btc_close, 50)
        btc_bull  = (btc_close > btc_ema50).reindex(df.index).ffill().fillna(False)
        df["btc_bull"] = btc_bull
        df["btc_filter_ok"] = btc_bull
    else:
        df["btc_bull"] = True
        df["btc_filter_ok"] = True

    # --- Efficiency Ratio ---
    er_change = close.diff(cfg.er_len).abs()
    er_vol    = close.diff(1).abs().rolling(cfg.er_len, min_periods=cfg.er_len).sum()
    df["er"]    = np.where(er_vol > 0, er_change / er_vol, 0.0)
    df["er_ok"] = (not cfg.use_er) | (df["er"] > cfg.er_thresh)

    # --- Entry / exit conditions ---
    # Bear regime blocks entry only if bear_size_cut == 0 (full block)
    regime_blocks = df["bear_regime"] & (cfg.bear_size_cut <= 0.0)
    df["regime_blocks"] = regime_blocks

    df["bull_condition"] = (
        df["above_tl"]
        & df["above_ma_fast"]
        & df["momentum_ok"]
        & df["track_rising_window"]
        & df["er_ok"]
        & df["btc_filter_ok"]
        & ~regime_blocks
    ).fillna(False)

    df["trend_break"] = df["below_tl"]
    df["blowoff"]     = (df["dist_pct"] > cfg.blowoff_dist_pct) & (df["rsi"] > 80)
    df["vol_shock"]   = (df["annual_vol"] > (df["vol_avg50"] * cfg.vol_shock_mul)) & df["below_tl"]

    df["green_dot"] = df["bull_condition"]
    df["red_dot"]   = df["below_tl"]
    return df


def run_state_machine(df: pd.DataFrame, cfg: MomentumConfig) -> pd.DataFrame:
    """Forward pass — replicates the Momentum state machine.

    Key difference from Lean: trailing stop tracks the highest close since
    entry and exits if price falls trail_pct% below that peak.
    Allocation is vol-scaled and reduced in bear regime (not binary).
    """
    n = len(df)
    signal_state  = np.full(n, S_BEAR, dtype=np.int8)
    display_state = np.full(n, S_BEAR, dtype=np.int8)
    bars_since_signal = np.zeros(n, dtype=np.int32)
    below_count   = np.zeros(n, dtype=np.int32)
    bull_hold     = np.zeros(n, dtype=np.int32)
    signal_changed = np.zeros(n, dtype=bool)
    target_alloc  = np.zeros(n, dtype=np.float64)
    entry_peak_arr = np.full(n, np.nan)
    trail_stop_arr = np.full(n, np.nan)
    trail_exit_arr = np.zeros(n, dtype=bool)
    exit_reason_trail = np.zeros(n, dtype=bool)

    cur_sig  = S_BEAR
    cur_disp = S_BEAR
    prev_sig = S_BEAR
    bars_since_sig = 999
    below_c  = 0
    bull_hold_c = 0
    entry_peak = np.nan

    below_arr    = df["below_tl"].fillna(False).to_numpy()
    above_arr    = df["above_tl"].fillna(False).to_numpy()
    bull_arr     = df["bull_condition"].fillna(False).to_numpy()
    blowoff_arr  = df["blowoff"].fillna(False).to_numpy()
    vol_shock_arr = df["vol_shock"].fillna(False).to_numpy()
    annual_vol_arr = df["annual_vol"].fillna(0.0).to_numpy()
    close_arr    = df["close"].to_numpy()
    bear_arr     = df["bear_regime"].fillna(False).to_numpy()

    for i in range(n):
        bars_since_sig += 1

        if below_arr[i]:
            below_c += 1
        else:
            below_c = 0
        if bull_arr[i]:
            bull_hold_c += 1
        else:
            bull_hold_c = 0

        # Track peak since entry for trailing stop
        if cur_sig == S_BULL:
            if np.isnan(entry_peak):
                entry_peak = close_arr[i]
            else:
                entry_peak = max(entry_peak, close_arr[i])
        else:
            entry_peak = np.nan

        trail_stop = np.nan if np.isnan(entry_peak) else entry_peak * (1.0 - cfg.trail_pct / 100.0)
        trail_exit = (cfg.use_trail and cur_sig == S_BULL
                      and not np.isnan(trail_stop)
                      and close_arr[i] < trail_stop)

        entry_peak_arr[i] = entry_peak
        trail_stop_arr[i] = trail_stop
        trail_exit_arr[i] = trail_exit

        # --- Transitions ---
        if cur_sig == S_BULL:
            if below_arr[i] and below_c >= cfg.exit_grace_bars:
                cur_sig = S_BEAR
                bars_since_sig = 0
                entry_peak = np.nan
            elif trail_exit:
                cur_sig = S_BEAR
                bars_since_sig = 0
                entry_peak = np.nan
                exit_reason_trail[i] = True
            elif blowoff_arr[i]:
                cur_sig = S_BEAR
                bars_since_sig = 0
                entry_peak = np.nan
            elif vol_shock_arr[i]:
                cur_sig = S_BEAR
                bars_since_sig = 0
                entry_peak = np.nan
        elif cur_sig == S_BEAR:
            if (bull_arr[i]
                    and bull_hold_c >= cfg.confirm_bars
                    and bars_since_sig >= cfg.reentry_hold):
                cur_sig = S_BULL
                bars_since_sig = 0
                entry_peak = close_arr[i]

        # --- Display state ---
        if below_arr[i] and below_c >= cfg.exit_grace_bars:
            cur_disp = S_BEAR
        elif above_arr[i] and bull_arr[i]:
            cur_disp = S_BULL
        elif above_arr[i] and not bull_arr[i]:
            cur_disp = S_NEUTRAL

        # --- Allocation: vol-scaled, reduced in bear regime ---
        if cur_sig == S_BULL:
            av = annual_vol_arr[i]
            vol_scale    = min(1.0, cfg.target_vol_pct / av) if (cfg.use_vol_sizing and av > 1e-9) else 1.0
            regime_scale = (cfg.bear_size_cut / 100.0) if bear_arr[i] else 1.0
            target_alloc[i] = round(max(0.0, min(100.0, 100.0 * vol_scale * regime_scale)))
        else:
            target_alloc[i] = 0.0

        signal_changed[i] = (cur_sig != prev_sig)
        prev_sig = cur_sig

        signal_state[i]       = cur_sig
        display_state[i]      = cur_disp
        bars_since_signal[i]  = bars_since_sig
        below_count[i]        = below_c
        bull_hold[i]          = bull_hold_c

    df = df.copy()
    df["signal_state"]     = signal_state
    df["display_state"]    = display_state
    df["bars_since_signal"] = bars_since_signal
    df["below_count"]      = below_count
    df["bull_hold"]        = bull_hold
    df["signal_changed"]   = signal_changed
    df["target_alloc"]     = target_alloc
    df["entry_peak"]       = entry_peak_arr
    df["trail_stop"]       = trail_stop_arr
    df["trail_exit"]       = trail_exit_arr
    df["exit_reason_trail"] = exit_reason_trail
    return df


def _state_label(code: int, display: bool = False) -> str:
    if code == S_BULL:
        return "BULL"
    if code == S_NEUTRAL:
        return "HEDGED" if display else "NEUTRAL"
    return "BEAR"


def build_summary(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    bear   = bool(last["bear_regime"])
    ab_reg = bool(last["above_ma_reg"])
    if bear:
        ma_status = "BEAR (soft cut)"
    elif ab_reg:
        ma_status = "ABOVE"
    else:
        ma_status = "BELOW"
    trail_stop_val = float(last["trail_stop"]) if pd.notna(last["trail_stop"]) else None
    return {
        "time":             last.name,
        "close":            float(last["close"]),
        "signal":           _state_label(int(last["signal_state"])),
        "regime":           _state_label(int(last["display_state"]), display=True),
        "ma_reg_status":    ma_status,
        "bear_regime":      bear,
        "above_ma_fast":    bool(last["above_ma_fast"]),
        "above_ma_reg":     ab_reg,
        "trackline":        float(last["trackline"]),
        "track_rising_window": bool(last["track_rising_window"]),
        "dist_pct":         float(last["dist_pct"]),
        "annual_vol":       float(last["annual_vol"]),
        "target_alloc":     float(last["target_alloc"]),
        "blowoff":          bool(last["blowoff"]),
        "vol_shock":        bool(last["vol_shock"]),
        "btc_bull":         bool(last["btc_bull"]),
        "rsi":              float(last["rsi"]) if pd.notna(last["rsi"]) else float("nan"),
        "er":               float(last["er"]) if pd.notna(last["er"]) else float("nan"),
        "er_ok":            bool(last["er_ok"]),
        "momentum_ok":      bool(last["momentum_ok"]),
        "trail_stop":       trail_stop_val,
    }


def run_strategy(daily: pd.DataFrame,
                 btc_daily: Optional[pd.DataFrame] = None,
                 config: MomentumConfig = DEFAULT_CONFIG) -> StrategyResult:
    df = compute_features(daily, btc_daily, config)
    df = run_state_machine(df, config)
    return StrategyResult(df=df, summary=build_summary(df))
