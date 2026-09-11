"""Strategy 2 of 3 — mean reversion, but only with the macro trend.

The brief asks for "RSI with dynamic Bollinger Bands, entering oversold in the
direction of the macro trend". That last clause is the whole strategy; without
it this is a machine for buying bear markets. Every gate below exists to keep a
dip-buy from becoming a trend-fight.

Three choices worth defending:

**Short RSI, not RSI(14).** RSI(14) is a trend filter that happens to be bounded;
by the time it reads 30 on a daily equity ETF the move is usually over. The
short-horizon literature (Connors, and the ETF mean-reversion work that follows
it) uses 2 to 4 periods, and the effect it documents is a 1-5 day reversal, not
a 3-week one. `rsi_len = 3` here.

**Adaptive bands, not 2 sigma.** A fixed 2-sigma band is not a fixed event rate.
In a calm tape it is touched constantly; in a stressed one almost never. So the
same rule fires far too often exactly when dip-buying is safe and almost never
when it pays most. `ind.adaptive_bb_mult` scales the multiplier with the
volatility percentile, which keeps the touch rate roughly stationary.

**An explicit time stop.** A trend rule can hold a winner forever; a reversion
rule cannot, because its edge has a half-life. Without a time stop, a reversion
trade that does not revert silently turns into a buy-and-hold position with a
mean-reversion label on it, and the backtest attributes the market's return to
the signal.

Honest prior, from this project's own crypto work: the altcoin campaign rejected
every one of nineteen candidates that was not the base trend rule. Nothing here
should be believed before it passes `testing/scripts` phase protocol. This module
exists so the idea is *testable*, not because it is expected to win.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from shared import indicators as ind
from .config import DEFAULT_CONFIG, ETFConfig
from .strategy import S_BEAR, S_BULL, S_NEUTRAL, StrategyResult, _state_label


@dataclass
class MeanReversionConfig:
    # macro gate — no long below the long MA, no exceptions
    trend_ma_len: int = 200
    require_rising_ma: bool = False     # stricter: MA must also be rising

    # entry
    rsi_len: int = 3
    rsi_entry: float = 15.0
    bb_len: int = 20
    bb_vol_len: int = 100
    bb_mult_lo: float = 1.5
    bb_mult_hi: float = 3.0
    pctb_entry: float = 0.05            # at or below the lower adaptive band

    # exit
    rsi_exit: float = 60.0
    exit_on_mid: bool = True            # close back above the band midline
    max_hold_bars: int = 10             # the time stop
    atr_len: int = 14
    stop_atr_mult: float = 2.5          # hard stop from the entry close

    # sizing
    use_vol_sizing: bool = True
    target_vol_pct: float = 12.0
    vol_lookback: int = 60
    vol_floor_pct: float = 3.0
    max_leverage: float = 1.0
    trading_days: int = 252


DEFAULT_MR_CONFIG = MeanReversionConfig()


def compute_features(daily: pd.DataFrame, cfg: MeanReversionConfig) -> pd.DataFrame:
    df = daily.copy()
    high, low, close = df["high"], df["low"], df["close"]

    df["ma_reg"] = ind.sma(close, cfg.trend_ma_len)
    df["above_ma_reg"] = close > df["ma_reg"]
    df["ma_reg_rising"] = df["ma_reg"] > df["ma_reg"].shift(cfg.trend_ma_len // 10)
    df["macro_ok"] = df["above_ma_reg"] & (df["ma_reg_rising"] if cfg.require_rising_ma else True)

    df["rsi"] = ind.rsi(close, cfg.rsi_len)
    df["bb_mult"] = ind.adaptive_bb_mult(close, cfg.bb_len, cfg.bb_vol_len,
                                         cfg.bb_mult_lo, cfg.bb_mult_hi)

    # %B against a per-bar multiplier: bbands() takes a scalar, so the band is
    # rebuilt here from its parts rather than calling it with a Series.
    mid = ind.sma(close, cfg.bb_len)
    sd = ind.stdev_pop(close, cfg.bb_len)
    lower = mid - df["bb_mult"] * sd
    upper = mid + df["bb_mult"] * sd
    df["bb_lower"], df["bb_mid"], df["bb_upper"] = lower, mid, upper
    width = (upper - lower).replace(0, np.nan)
    df["pctb"] = (close - lower) / width

    df["atr"] = ind.atr(high, low, close, cfg.atr_len)
    df["annual_vol"] = ind.realized_vol(close, cfg.vol_lookback, cfg.trading_days)

    df["entry_signal"] = (df["macro_ok"]
                          & (df["rsi"] < cfg.rsi_entry)
                          & (df["pctb"] <= cfg.pctb_entry)).fillna(False)
    df["exit_signal"] = ((df["rsi"] > cfg.rsi_exit)
                         | (df["pctb"] >= 0.5 if cfg.exit_on_mid else False)).fillna(False)
    return df


def run_state_machine(df: pd.DataFrame, cfg: MeanReversionConfig) -> pd.DataFrame:
    """Long-flat state machine with four exits: signal, time, stop, macro break.

    `exit_reason` is recorded per bar. Which exit fires is the single most
    diagnostic number this strategy produces: a reversion rule whose trades
    mostly end on the time stop has no edge and is being carried by drift.
    """
    n = len(df)
    sig = np.full(n, S_BEAR, dtype=np.int8)
    alloc = np.zeros(n, dtype=np.float64)
    changed = np.zeros(n, dtype=bool)
    held = np.zeros(n, dtype=np.int32)
    reason = np.array([""] * n, dtype=object)
    stop_arr = np.full(n, np.nan)

    entry = df["entry_signal"].to_numpy()
    exit_s = df["exit_signal"].to_numpy()
    macro = df["macro_ok"].fillna(False).to_numpy()
    close = df["close"].to_numpy()
    atr = df["atr"].to_numpy()
    vol = df["annual_vol"].to_numpy()

    in_pos, bars_held, stop_px = False, 0, np.nan
    prev = S_BEAR
    for i in range(n):
        if in_pos:
            bars_held += 1
            why = ""
            if not np.isnan(stop_px) and close[i] < stop_px:
                why = "stop"
            elif not macro[i]:
                why = "macro"
            elif exit_s[i]:
                why = "signal"
            elif bars_held >= cfg.max_hold_bars:
                why = "time"
            if why:
                in_pos, bars_held, stop_px = False, 0, np.nan
                reason[i] = why
        elif entry[i] and np.isfinite(atr[i]):
            in_pos, bars_held = True, 0
            stop_px = close[i] - cfg.stop_atr_mult * atr[i]

        stop_arr[i] = stop_px
        sig[i] = S_BULL if in_pos else S_BEAR
        held[i] = bars_held
        if in_pos:
            av = vol[i]
            if cfg.use_vol_sizing and np.isfinite(av):
                vs = min(cfg.max_leverage, cfg.target_vol_pct / max(av, cfg.vol_floor_pct))
            else:
                vs = 1.0
            alloc[i] = round(100.0 * vs)
        changed[i] = sig[i] != prev
        prev = sig[i]

    out = df.copy()
    out["signal_state"] = sig
    out["display_state"] = np.where(sig == S_BULL, S_BULL,
                                    np.where(df["macro_ok"].fillna(False), S_NEUTRAL, S_BEAR))
    out["signal_changed"] = changed
    out["target_alloc"] = alloc
    out["bars_held"] = held
    out["exit_reason"] = reason
    out["stop_px"] = stop_arr
    return out


def build_summary(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    reasons = pd.Series([r for r in df["exit_reason"] if r])
    return {
        "time": last.name,
        "close": float(last["close"]),
        "signal": _state_label(int(last["signal_state"])),
        "macro_ok": bool(last["macro_ok"]),
        "rsi": float(last["rsi"]) if pd.notna(last["rsi"]) else float("nan"),
        "pctb": float(last["pctb"]) if pd.notna(last["pctb"]) else float("nan"),
        "bb_mult": float(last["bb_mult"]) if pd.notna(last["bb_mult"]) else float("nan"),
        "target_alloc": float(last["target_alloc"]),
        "bars_held": int(last["bars_held"]),
        "exit_reason_mix": reasons.value_counts().to_dict() if len(reasons) else {},
    }


def run_strategy(daily: pd.DataFrame,
                 btc_daily: Optional[pd.DataFrame] = None,
                 config: MeanReversionConfig = DEFAULT_MR_CONFIG) -> StrategyResult:
    df = compute_features(daily, config)
    df = run_state_machine(df, config)
    return StrategyResult(df=df, summary=build_summary(df))
