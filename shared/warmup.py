"""Indicator warm-up trimming — one implementation, used by every consumer.

Why this exists as shared code rather than a helper inside the test harness:
while a long moving average is still NaN, pandas evaluates `close > NaN` and
`NaN < NaN` as False, so in Lean

    bear_regime = (~False) & False = False   ->   regime_ok = True

The regime block is therefore *silently disabled* during warm-up rather than
undefined — no exception, no NaN in the signal column, nothing a caller can
detect. Any consumer that forgets to trim silently reports a strategy that ran
without its main filter for the first `warmup_bars(df)` bars.

The dashboards and `testing/scripts/engine.py` both import from here so they can
never drift apart; a disagreement between the live dashboard and a report must
not be caused by two different definitions of "usable history".
"""
from __future__ import annotations

import pandas as pd

# Indicator columns that define the warm-up. Deliberately excludes state-machine
# outputs (`entry_peak`, `trail_stop`, ...), which are NaN until the first trade
# and would otherwise throw away real history.
WARMUP_COLS: tuple[str, ...] = (
    "ma_long", "ma_med", "ma_reg", "ma_fast", "ema_slow",
    "trackline", "vol_avg50", "annual_vol", "rsi", "er",
)


def warmup_bars(df: pd.DataFrame) -> int:
    """Number of leading bars on which some indicator is still undefined.

    Equals the position of the first bar where every `WARMUP_COLS` column present
    in `df` has a value — i.e. the first bar the strategy is fully specified on.
    """
    first = 0
    for col in WARMUP_COLS:
        if col not in df.columns:
            continue
        fv = df[col].first_valid_index()
        if fv is None:
            raise ValueError(
                f"column {col!r} is NaN over the whole sample ({len(df)} bars) — "
                f"the history is shorter than its lookback; cannot trim warm-up")
        first = max(first, df.index.get_loc(fv))
    return int(first)


def trim_warmup(df: pd.DataFrame) -> pd.DataFrame:
    """Drop the warm-up prefix returned by `warmup_bars`.

    Before slicing, the previous bar's state is materialised into
    `prev_target_alloc` / `prev_signal_state`. Position is "yesterday's signal", so
    a consumer that calls `.shift(1)` *after* the slice loses the first bar's
    predecessor — and the strategy is frequently still in a position across the
    boundary. That silently drops a day of exposure and invents an entry cost.
    Consumers should prefer these columns over shifting themselves.
    """
    out = df.copy()
    for col, prev in (("target_alloc", "prev_target_alloc"),
                      ("signal_state", "prev_signal_state")):
        if col in out.columns:
            out[prev] = out[col].shift(1)
    return out.iloc[warmup_bars(out):]
