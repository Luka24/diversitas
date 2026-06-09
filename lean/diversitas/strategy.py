"""Diversitas Lean strategy engine — Python port of `diversitas_lean.pine`.

Lean is the stripped-down variant of Diversitas Pro v3:
  - Kijun trackline (direction)
  - 50 MA (trend MA — price must be above)
  - 200 MA (regime MA — hard block when below + falling)
  - Blow-off + vol shock exits
  - Range filter via trackline slope over N bars
  - One state machine (BULL / BEAR) — no conviction score, no separate display
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math

import numpy as np
import pandas as pd

from . import indicators as ind
from .config import LeanConfig, DEFAULT_CONFIG


# State codes
S_BULL = 1
S_NEUTRAL = 2  # only used for displayState (HEDGED background)
S_BEAR = 3


@dataclass
class StrategyResult:
    df: pd.DataFrame
    summary: dict


def compute_features(daily: pd.DataFrame, btc_daily: Optional[pd.DataFrame],
                     cfg: LeanConfig) -> pd.DataFrame:
    """Compute every per-bar feature used by the state machine."""
    df = daily.copy()
    high, low, close = df["high"], df["low"], df["close"]

    # --- Trackline (Kijun) ---
    track_high = ind.highest(high, cfg.track_period)
    track_low = ind.lowest(low, cfg.track_period)
    df["trackline"] = (track_high + track_low) / 2.0
    df["track_rising"] = df["trackline"] > df["trackline"].shift(1)
    df["track_rising_window"] = df["trackline"] > df["trackline"].shift(cfg.track_slope_bars)
    buf_amt = df["trackline"] * (cfg.track_buf_pct / 100.0)
    df["above_tl"] = close > (df["trackline"] + buf_amt)
    df["below_tl"] = close < (df["trackline"] - buf_amt)
    df["dist_pct"] = (close - df["trackline"]) / df["trackline"] * 100.0

    # --- Moving averages ---
    ma_med = ind.sma(close, cfg.ma_med_len)
    ma_long = ind.sma(close, cfg.ma_long_len)
    df["ma_med"] = ma_med
    df["ma_long"] = ma_long
    df["above_ma_med"] = close > ma_med
    df["above_ma_long"] = close > ma_long
    df["ma_long_rising"] = ma_long > ma_long.shift(cfg.ma_slope)
    df["ma_long_falling"] = ma_long < ma_long.shift(cfg.ma_slope)
    df["bear_regime"] = (~df["above_ma_long"]) & df["ma_long_falling"]
    df["regime_ok"] = ~df["bear_regime"]

    # --- RSI (only used by blow-off detector) ---
    df["rsi"] = ind.rsi(close, cfg.rsi_len)

    # --- Volatility ---
    log_ret = np.log(close / close.shift(1))
    df["log_ret"] = log_ret
    daily_std = ind.stdev_pop(log_ret, cfg.vol_lookback)
    df["annual_vol"] = daily_std * math.sqrt(365) * 100.0
    vol_avg50 = ind.sma(df["annual_vol"], 50)
    df["vol_avg50"] = vol_avg50

    # --- BTC filter (optional) ---
    if cfg.use_btc_filter and btc_daily is not None and not btc_daily.empty:
        btc_close = btc_daily["close"]
        btc_ema50 = ind.ema(btc_close, 50)
        btc_bull = (btc_close > btc_ema50).reindex(df.index).ffill().fillna(False)
        df["btc_bull"] = btc_bull
        df["btc_filter_ok"] = btc_bull
    else:
        df["btc_bull"] = True
        df["btc_filter_ok"] = True

    # --- Entry / exit conditions ---
    # Entry distance: must be > buf + extra
    df["dist_entry_ok"] = df["dist_pct"] >= (cfg.track_buf_pct + cfg.min_dist_entry_pct)

    df["bull_condition"] = (
        df["above_tl"]
        & df["above_ma_med"]
        & df["track_rising_window"]
        & df["dist_entry_ok"]
        & df["regime_ok"]
        & df["btc_filter_ok"]
    ).fillna(False)

    df["trend_break"] = df["below_tl"]
    df["blowoff"] = (df["dist_pct"] > cfg.blowoff_dist_pct) & (df["rsi"] > 80)
    df["vol_shock"] = (df["annual_vol"] > (vol_avg50 * cfg.vol_shock_mul)) & df["below_tl"]

    # --- Convenience for dashboard ---
    df["green_dot"] = df["bull_condition"]
    df["red_dot"] = df["below_tl"]
    return df


def run_state_machine(df: pd.DataFrame, cfg: LeanConfig) -> pd.DataFrame:
    """Forward pass — replicates the Lean state machine.

    Differences from the Full state machine:
      - Only one signal state (BULL/BEAR), no separate raw/display logic
      - bars_since_signal resets on BOTH BULL and BEAR transitions
      - bullHoldCount resets to 0 (not 1)
      - No weekend filter
      - displayState evaluated each bar from instantaneous conditions
    """
    n = len(df)
    signal_state = np.full(n, S_BEAR, dtype=np.int8)
    display_state = np.full(n, S_BEAR, dtype=np.int8)
    bars_since_signal = np.zeros(n, dtype=np.int32)
    below_count = np.zeros(n, dtype=np.int32)
    bull_hold = np.zeros(n, dtype=np.int32)
    signal_changed = np.zeros(n, dtype=bool)
    target_alloc = np.zeros(n, dtype=np.float32)

    cur_sig = S_BEAR
    cur_disp = S_BEAR
    prev_sig = S_BEAR
    bars_since_sig = 999
    below_c = 0
    bull_hold_c = 0

    below_arr = df["below_tl"].fillna(False).to_numpy()
    above_arr = df["above_tl"].fillna(False).to_numpy()
    bull_arr = df["bull_condition"].fillna(False).to_numpy()
    blowoff_arr = df["blowoff"].fillna(False).to_numpy()
    vol_shock_arr = df["vol_shock"].fillna(False).to_numpy()
    annual_vol_arr = df["annual_vol"].fillna(0.0).to_numpy()

    for i in range(n):
        bars_since_sig += 1

        # --- Counters (run every bar) ---
        if below_arr[i]:
            below_c += 1
        else:
            below_c = 0
        if bull_arr[i]:
            bull_hold_c += 1
        else:
            bull_hold_c = 0

        # --- Transitions ---
        if cur_sig == S_BULL:
            # BEAR exits — instant, but trend_break needs grace bars
            if below_arr[i] and below_c >= cfg.exit_grace_bars:
                cur_sig = S_BEAR
                bars_since_sig = 0
            elif blowoff_arr[i]:
                cur_sig = S_BEAR
                bars_since_sig = 0
            elif vol_shock_arr[i]:
                cur_sig = S_BEAR
                bars_since_sig = 0
        elif cur_sig == S_BEAR:
            if (bull_arr[i]
                    and bull_hold_c >= cfg.confirm_bars
                    and bars_since_sig >= cfg.reentry_hold):
                cur_sig = S_BULL
                bars_since_sig = 0

        # --- Display state (no confirm bars on BULL/NEUTRAL transitions) ---
        if below_arr[i] and below_c >= cfg.exit_grace_bars:
            cur_disp = S_BEAR
        elif above_arr[i] and bull_arr[i]:
            cur_disp = S_BULL
        elif above_arr[i] and not bull_arr[i]:
            cur_disp = S_NEUTRAL
        # else: hold

        # --- Allocation (additive, applied after signal) ---
        if cur_sig == S_BULL:
            if cfg.use_vol_sizing and annual_vol_arr[i] > 0:
                vol_scale = min(1.0, cfg.target_vol_pct / annual_vol_arr[i])
            else:
                vol_scale = 1.0
            target_alloc[i] = round(min(100.0, max(0.0, 100.0 * vol_scale)))
        else:
            target_alloc[i] = 0.0

        signal_changed[i] = (cur_sig != prev_sig)
        prev_sig = cur_sig

        signal_state[i] = cur_sig
        display_state[i] = cur_disp
        bars_since_signal[i] = bars_since_sig
        below_count[i] = below_c
        bull_hold[i] = bull_hold_c

    df = df.copy()
    df["signal_state"] = signal_state
    df["display_state"] = display_state
    df["bars_since_signal"] = bars_since_signal
    df["below_count"] = below_count
    df["bull_hold"] = bull_hold
    df["signal_changed"] = signal_changed
    df["target_alloc"] = target_alloc
    return df


def _state_label(code: int, display: bool = False) -> str:
    if code == S_BULL:
        return "BULL"
    if code == S_NEUTRAL:
        return "HEDGED" if display else "NEUTRAL"
    return "BEAR"


def build_summary(df: pd.DataFrame) -> dict:
    """Latest-bar status — mirrors Pine table layout."""
    last = df.iloc[-1]
    bear = bool(last["bear_regime"])
    above_long = bool(last["above_ma_long"])
    if bear:
        ma_status = "BEAR (blocked)"
    elif above_long:
        ma_status = "ABOVE"
    else:
        ma_status = "BELOW"
    return {
        "time": last.name,
        "close": float(last["close"]),
        "signal": _state_label(int(last["signal_state"])),
        "regime": _state_label(int(last["display_state"]), display=True),
        "ma_long_status": ma_status,
        "bear_regime": bear,
        "above_ma_med": bool(last["above_ma_med"]),
        "trackline": float(last["trackline"]),
        "track_rising_window": bool(last["track_rising_window"]),
        "dist_pct": float(last["dist_pct"]),
        "annual_vol": float(last["annual_vol"]),
        "target_alloc": float(last["target_alloc"]),
        "blowoff": bool(last["blowoff"]),
        "vol_shock": bool(last["vol_shock"]),
        "btc_bull": bool(last["btc_bull"]),
        "rsi": float(last["rsi"]) if pd.notna(last["rsi"]) else float("nan"),
    }


def run_strategy(daily: pd.DataFrame,
                 btc_daily: Optional[pd.DataFrame] = None,
                 config: LeanConfig = DEFAULT_CONFIG) -> StrategyResult:
    df = compute_features(daily, btc_daily, config)
    df = run_state_machine(df, config)
    return StrategyResult(df=df, summary=build_summary(df))
