"""Strategy 1 of 3 — trend following on a single ETF sleeve.

Structurally the Momentum port with three substitutions, kept structurally
identical on purpose: the state machine is the part of this project that has
been audited against Pine line by line and stress-tested for look-ahead, and
rewriting it for a new asset class would throw that away to gain nothing.

What changed, and why it had to:

  Momentum (crypto)                 ETF
  ---------------------------------------------------------------------------
  entry buffer = 2 % of trackline   entry buffer = 0.5 x ATR
  trailing stop = 12 % from peak    trailing stop = 3 x ATR from peak
  Efficiency Ratio > 0.25           ADX > 18
  vol sizing target 60 %            target 12 %, floored, capped at 1x
  365-day annualisation             252

Public surface is identical to `lean`/`momentum` — `S_BULL`, `compute_features`,
`run_state_machine`, `run_strategy(daily, btc_daily=None, config=...)` — so
`testing/scripts/engine.py` can drive it as a third variant and every existing
evaluation script works unchanged.

No look-ahead: every column is a function of bars up to and including t, and the
position taken on day t is `target_alloc` from t-1 (applied by `engine.position`
via the `prev_*` columns that `shared.warmup.trim_warmup` materialises).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from shared import indicators as ind
from .config import DEFAULT_CONFIG, ETFConfig

S_BULL = 1
S_NEUTRAL = 2
S_BEAR = 3


@dataclass
class StrategyResult:
    df: pd.DataFrame
    summary: dict


def compute_features(daily: pd.DataFrame,
                     anchor_daily: Optional[pd.DataFrame],
                     cfg: ETFConfig) -> pd.DataFrame:
    df = daily.copy()
    high, low, close = df["high"], df["low"], df["close"]

    # ── ATR first: three other features are expressed in it ───────────────────
    df["atr"] = ind.atr(high, low, close, cfg.atr_len)
    df["atr_pct"] = df["atr"] / close * 100.0

    # ── trend anchor ──────────────────────────────────────────────────────────
    df["trackline"] = ind.donchian_mid(high, low, cfg.track_period)
    df["track_rising"] = df["trackline"] > df["trackline"].shift(1)
    df["track_rising_window"] = df["trackline"] > df["trackline"].shift(cfg.track_slope_bars)

    if cfg.use_atr_buffer:
        buf = df["atr"] * cfg.atr_buf_mult
    else:
        buf = df["trackline"] * (cfg.track_buf_pct / 100.0)
    df["buffer"] = buf
    df["above_tl"] = close > (df["trackline"] + buf)
    df["below_tl"] = close < (df["trackline"] - buf)
    df["dist_pct"] = (close - df["trackline"]) / df["trackline"] * 100.0
    # Distance in ATR units. `dist_pct` is not comparable across a bond fund and
    # a small-cap fund; this is, and it is what the rotation layer ranks on.
    df["dist_atr"] = (close - df["trackline"]) / df["atr"].replace(0, np.nan)

    # ── moving averages / regime ──────────────────────────────────────────────
    df["ma_fast"] = ind.sma(close, cfg.ma_fast_len)
    df["ma_reg"] = ind.sma(close, cfg.ma_reg_len)
    df["above_ma_fast"] = close > df["ma_fast"]
    df["above_ma_reg"] = close > df["ma_reg"]
    df["ma_reg_falling"] = df["ma_reg"] < df["ma_reg"].shift(cfg.ma_slope)
    df["bear_regime"] = (~df["above_ma_reg"]) & df["ma_reg_falling"]

    # ── momentum filter ───────────────────────────────────────────────────────
    df["rsi"] = ind.rsi(close, cfg.rsi_len)
    df["ema_slow"] = ind.ema(close, cfg.ema_slow_len)
    df["momentum_ok"] = (df["rsi"] > cfg.rsi_entry) & (close > df["ema_slow"])

    # ── trend quality ─────────────────────────────────────────────────────────
    df["adx"] = ind.adx(high, low, close, cfg.adx_len)
    adx_ok = (df["adx"] > cfg.adx_thresh) if cfg.use_adx else pd.Series(True, index=df.index)

    er_change = close.diff(cfg.er_len).abs()
    er_vol = close.diff(1).abs().rolling(cfg.er_len, min_periods=cfg.er_len).sum()
    df["er"] = np.where(er_vol > 0, er_change / er_vol, 0.0)
    er_ok = (df["er"] > cfg.er_thresh) if cfg.use_er else pd.Series(True, index=df.index)

    df["adx_ok"] = adx_ok.fillna(False)
    df["er_ok"] = er_ok if isinstance(er_ok, pd.Series) else pd.Series(er_ok, index=df.index)
    df["quality_ok"] = df["adx_ok"] & df["er_ok"]

    # ── volatility, for sizing ────────────────────────────────────────────────
    log_ret = np.log(close / close.shift(1))
    df["log_ret"] = log_ret
    df["annual_vol"] = (ind.stdev_pop(log_ret, cfg.vol_lookback)
                        * math.sqrt(cfg.trading_days) * 100.0)

    # ── cross-asset (broad-market) filter ─────────────────────────────────────
    if cfg.use_anchor_filter and anchor_daily is not None and not anchor_daily.empty:
        a_close = anchor_daily["close"]
        a_bull = (a_close > ind.sma(a_close, cfg.anchor_ma_len))
        a_bull = a_bull.reindex(df.index).ffill().fillna(False)
        df["anchor_bull"] = a_bull
    else:
        df["anchor_bull"] = True
    df["anchor_ok"] = df["anchor_bull"]

    # ── entry / exit ──────────────────────────────────────────────────────────
    regime_blocks = df["bear_regime"] & (cfg.bear_size_cut <= 0.0)
    df["regime_blocks"] = regime_blocks

    df["bull_condition"] = (
        df["above_tl"]
        & df["above_ma_fast"]
        & df["momentum_ok"]
        & df["track_rising_window"]
        & df["quality_ok"]
        & df["anchor_ok"]
        & ~regime_blocks
    ).fillna(False)

    df["trend_break"] = df["below_tl"]
    if cfg.blowoff_dist_pct > 0:
        df["blowoff"] = (df["dist_pct"] > cfg.blowoff_dist_pct) & (df["rsi"] > 80)
    else:
        df["blowoff"] = pd.Series(False, index=df.index)

    df["green_dot"] = df["bull_condition"]
    df["red_dot"] = df["below_tl"]
    return df


def run_state_machine(df: pd.DataFrame, cfg: ETFConfig) -> pd.DataFrame:
    """Forward pass. Mirrors `momentum.strategy.run_state_machine`; the trailing
    stop is the only behavioural change and it is `peak - k x ATR` rather than
    `peak x (1 - p)`.

    Pine parity is preserved where it was deliberate: `entry_peak` is NOT set on
    the entry bar. Setting it there moves the trail reference one bar early and
    trips the stop a day sooner than the reference strategy — a difference that
    is invisible in aggregate and changes individual trades.
    """
    n = len(df)
    signal_state = np.full(n, S_BEAR, dtype=np.int8)
    display_state = np.full(n, S_BEAR, dtype=np.int8)
    bars_since_signal = np.zeros(n, dtype=np.int32)
    below_count = np.zeros(n, dtype=np.int32)
    bull_hold = np.zeros(n, dtype=np.int32)
    signal_changed = np.zeros(n, dtype=bool)
    target_alloc = np.zeros(n, dtype=np.float64)
    entry_peak_arr = np.full(n, np.nan)
    trail_stop_arr = np.full(n, np.nan)
    trail_exit_arr = np.zeros(n, dtype=bool)
    exit_reason_trail = np.zeros(n, dtype=bool)
    vol_scale_arr = np.ones(n, dtype=np.float64)

    cur_sig = cur_disp = prev_sig = S_BEAR
    bars_since_sig = 999
    below_c = bull_hold_c = 0
    entry_peak = np.nan

    below_arr = df["below_tl"].fillna(False).to_numpy()
    above_arr = df["above_tl"].fillna(False).to_numpy()
    bull_arr = df["bull_condition"].fillna(False).to_numpy()
    blowoff_arr = df["blowoff"].fillna(False).to_numpy()
    vol_arr = df["annual_vol"].to_numpy()
    close_arr = df["close"].to_numpy()
    atr_arr = df["atr"].to_numpy()
    bear_arr = df["bear_regime"].fillna(False).to_numpy()

    use_atr_trail = cfg.use_trail and cfg.trail_atr_mult > 0
    use_pct_trail = cfg.use_trail and cfg.trail_pct > 0

    for i in range(n):
        bars_since_sig += 1
        below_c = below_c + 1 if below_arr[i] else 0
        bull_hold_c = bull_hold_c + 1 if bull_arr[i] else 0

        if cur_sig == S_BULL:
            entry_peak = close_arr[i] if np.isnan(entry_peak) else max(entry_peak, close_arr[i])
        else:
            entry_peak = np.nan

        trail_stop = np.nan
        if not np.isnan(entry_peak):
            if use_atr_trail and not np.isnan(atr_arr[i]):
                trail_stop = entry_peak - cfg.trail_atr_mult * atr_arr[i]
            elif use_pct_trail:
                trail_stop = entry_peak * (1.0 - cfg.trail_pct / 100.0)
        trail_exit = (cur_sig == S_BULL and not np.isnan(trail_stop)
                      and close_arr[i] < trail_stop)

        entry_peak_arr[i] = entry_peak
        trail_stop_arr[i] = trail_stop
        trail_exit_arr[i] = trail_exit

        if cur_sig == S_BULL:
            if below_arr[i] and below_c >= cfg.exit_grace_bars:
                cur_sig, bars_since_sig, entry_peak = S_BEAR, 0, np.nan
            elif trail_exit:
                cur_sig, bars_since_sig, entry_peak = S_BEAR, 0, np.nan
                exit_reason_trail[i] = True
            elif blowoff_arr[i]:
                cur_sig, bars_since_sig, entry_peak = S_BEAR, 0, np.nan
        elif cur_sig == S_BEAR:
            if (bull_arr[i] and bull_hold_c >= cfg.confirm_bars
                    and bars_since_sig >= cfg.reentry_hold):
                cur_sig, bars_since_sig = S_BULL, 0

        if below_arr[i] and below_c >= cfg.exit_grace_bars:
            cur_disp = S_BEAR
        elif above_arr[i] and bull_arr[i]:
            cur_disp = S_BULL
        elif above_arr[i] and not bull_arr[i]:
            cur_disp = S_NEUTRAL

        if cur_sig == S_BULL:
            av = vol_arr[i]
            if cfg.use_vol_sizing and np.isfinite(av):
                av = max(av, cfg.vol_floor_pct)      # a 4 %-vol bond fund must
                vs = min(cfg.max_leverage, cfg.target_vol_pct / av)   # not become 3x
            else:
                vs = 1.0
            regime_scale = (cfg.bear_size_cut / 100.0) if bear_arr[i] else 1.0
            vol_scale_arr[i] = vs
            target_alloc[i] = round(max(0.0, min(100.0 * cfg.max_leverage,
                                                 100.0 * vs * regime_scale)))
        else:
            target_alloc[i] = 0.0

        signal_changed[i] = (cur_sig != prev_sig)
        prev_sig = cur_sig
        signal_state[i] = cur_sig
        display_state[i] = cur_disp
        bars_since_signal[i] = bars_since_sig
        below_count[i] = below_c
        bull_hold[i] = bull_hold_c

    out = df.copy()
    out["signal_state"] = signal_state
    out["display_state"] = display_state
    out["bars_since_signal"] = bars_since_signal
    out["below_count"] = below_count
    out["bull_hold"] = bull_hold
    out["signal_changed"] = signal_changed
    out["target_alloc"] = target_alloc
    out["vol_scale"] = vol_scale_arr
    out["entry_peak"] = entry_peak_arr
    out["trail_stop"] = trail_stop_arr
    out["trail_exit"] = trail_exit_arr
    out["exit_reason_trail"] = exit_reason_trail
    return out


def _state_label(code: int, display: bool = False) -> str:
    if code == S_BULL:
        return "BULL"
    if code == S_NEUTRAL:
        return "HEDGED" if display else "NEUTRAL"
    return "BEAR"


def build_summary(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    bear = bool(last["bear_regime"])
    return {
        "time": last.name,
        "close": float(last["close"]),
        "signal": _state_label(int(last["signal_state"])),
        "regime": _state_label(int(last["display_state"]), display=True),
        "ma_reg_status": "BEAR (soft cut)" if bear else ("ABOVE" if last["above_ma_reg"] else "BELOW"),
        "bear_regime": bear,
        "above_ma_fast": bool(last["above_ma_fast"]),
        "above_ma_reg": bool(last["above_ma_reg"]),
        "trackline": float(last["trackline"]),
        "dist_pct": float(last["dist_pct"]),
        "dist_atr": float(last["dist_atr"]) if pd.notna(last["dist_atr"]) else float("nan"),
        "atr_pct": float(last["atr_pct"]) if pd.notna(last["atr_pct"]) else float("nan"),
        "adx": float(last["adx"]) if pd.notna(last["adx"]) else float("nan"),
        "adx_ok": bool(last["adx_ok"]),
        "rsi": float(last["rsi"]) if pd.notna(last["rsi"]) else float("nan"),
        "momentum_ok": bool(last["momentum_ok"]),
        "annual_vol": float(last["annual_vol"]) if pd.notna(last["annual_vol"]) else float("nan"),
        "vol_scale": float(last["vol_scale"]),
        "target_alloc": float(last["target_alloc"]),
        "trail_stop": float(last["trail_stop"]) if pd.notna(last["trail_stop"]) else None,
        "anchor_bull": bool(last["anchor_bull"]),
    }


def run_strategy(daily: pd.DataFrame,
                 btc_daily: Optional[pd.DataFrame] = None,
                 config: ETFConfig = DEFAULT_CONFIG,
                 anchor_daily: Optional[pd.DataFrame] = None) -> StrategyResult:
    """`btc_daily` is accepted under that name only so `engine.run()` can call
    this variant with no special case. For an ETF it carries the broad-market
    anchor (World), not Bitcoin; `anchor_daily` is the honest alias and wins
    when both are given."""
    anchor = anchor_daily if anchor_daily is not None else btc_daily
    df = compute_features(daily, anchor, config)
    df = run_state_machine(df, config)
    return StrategyResult(df=df, summary=build_summary(df))
