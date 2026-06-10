"""Technical indicators — Pine-compatible (Wilder RMA where Pine uses ta.rma).

All functions take and return pandas.Series unless noted.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    """Standard EMA matching Pine's ta.ema (adjust=False, span=length)."""
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder's smoothing (Pine's ta.rma): alpha = 1/length, adjust=False."""
    return series.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def stdev_pop(series: pd.Series, length: int) -> pd.Series:
    """Population stdev — Pine's ta.stdev uses ddof=0."""
    return series.rolling(length, min_periods=length).std(ddof=0)


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder RSI matching Pine ta.rsi."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = rma(gain, length)
    avg_loss = rma(loss, length)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100.0 - (100.0 / (1.0 + rs))
    # When avg_loss == 0 (no losses), RSI = 100 (Pine behaviour)
    rsi_val = rsi_val.where(avg_loss != 0, 100.0)
    return rsi_val


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr


def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """ADX matching Pine implementation in the strategy:
        up   = change(high);  down = -change(low)
        pDM  = up   if up>down AND up>0   else 0
        nDM  = down if down>up AND down>0 else 0
        trur = rma(tr, len)
        pDI  = 100 * rma(pDM, len) / trur
        nDI  = 100 * rma(nDM, len) / trur
        dx   = 100 * |pDI-nDI| / (pDI+nDI)
        adx  = rma(dx, len)
    """
    up = high.diff()
    down = -low.diff()
    p_dm = np.where((up > down) & (up > 0), up, 0.0)
    n_dm = np.where((down > up) & (down > 0), down, 0.0)
    p_dm = pd.Series(p_dm, index=high.index)
    n_dm = pd.Series(n_dm, index=high.index)

    tr = true_range(high, low, close)
    trur = rma(tr, length)
    p_di = 100.0 * rma(p_dm, length) / trur.replace(0, np.nan)
    n_di = 100.0 * rma(n_dm, length) / trur.replace(0, np.nan)
    s = p_di + n_di
    dx = (100.0 * (p_di - n_di).abs() / s.replace(0, np.nan)).fillna(0.0)
    return rma(dx, length)


def highest(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).max()


def lowest(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).min()


def bars_since(condition: pd.Series) -> pd.Series:
    """Pine's ta.barssince: number of bars since condition was last True.
    Returns NaN before any True occurs. 0 on the bar the condition is True.
    """
    cond = condition.fillna(False).astype(bool).to_numpy()
    n = len(cond)
    out = np.full(n, np.nan)
    counter = -1  # not seen yet
    for i in range(n):
        if cond[i]:
            counter = 0
        elif counter >= 0:
            counter += 1
        if counter >= 0:
            out[i] = counter
    return pd.Series(out, index=condition.index)


def cummax_from_close(close: pd.Series) -> pd.Series:
    """Running peak from the first valid close — mirrors the var float peakPrice
    pattern in Pine where peakPrice := max(peakPrice, close)."""
    return close.cummax()
