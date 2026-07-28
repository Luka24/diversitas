"""Variant-agnostic strategy runner for the testing campaign.

Lean and Momentum each ship a `diversitas` package under their own folder with
identical public surface: a `*Config` dataclass, `run_strategy(daily, btc_daily,
config)`, and `S_BULL`. This module switches `sys.path` so `import diversitas`
resolves to the requested variant (same trick as `regression_test.py`), then
exposes one uniform API:

    run(variant, daily, btc=None, **overrides) -> pd.DataFrame   # strategy df
    position(df, bear_alloc_pct=0.0)           -> np.ndarray     # shift(1) alloc
    config_defaults(variant)                    -> dict

The position model matches the dashboards' `_pos_from_df` (momentum/…/dashboard.py:117):
next-bar allocation = target_alloc.shift(1)/100 (vol-scaled in Momentum, binary in
Lean) plus a bear floor. Everything uses shift(1) — no look-ahead.

Indicator warm-up
-----------------
`run()` and `run_overlay()` drop the leading bars on which the slowest indicator is
not yet defined (Lean: SMA200 → 199 bars; Momentum: SMA100 → 99 bars). This is not
cosmetic. While `ma_long` is NaN, pandas evaluates `close > NaN` and `NaN < NaN` as
False, so

    bear_regime = (~False) & False = False   ->   regime_ok = True

i.e. the regime block is silently *disabled* rather than NaN — no exception, no NaN
in the signal column, nothing to notice downstream. Campaign results produced before
this was added therefore contain a leading stretch in which the strategy ran without
its main filter (verified: SOL entered its two largest winning trades before SMA200
existed). Pass `trim_warmup=False` to reproduce those older numbers.
"""
from __future__ import annotations

import importlib
import sys
from dataclasses import fields
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_VARIANT_DIRS = {
    "lean":     _ROOT / "lean",
    "momentum": _ROOT / "momentum",
    "full":     _ROOT / "full",     # reference only
}
VARIANTS = ("lean", "momentum")


def _switch_variant(variant: str):
    """Make `import diversitas` resolve to the given variant; return its module."""
    if variant not in _VARIANT_DIRS:
        raise ValueError(f"unknown variant {variant!r}")
    target = _VARIANT_DIRS[variant]
    others = [str(d) for v, d in _VARIANT_DIRS.items() if v != variant]
    sys.path[:] = [p for p in sys.path if p not in others]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))          # keep `shared` importable
    if str(target) not in sys.path:
        sys.path.insert(0, str(target))
    for mod in list(sys.modules):
        if mod == "diversitas" or mod.startswith("diversitas."):
            del sys.modules[mod]
    return importlib.import_module("diversitas")


# Warm-up trimming lives in `shared/warmup.py` so the dashboards and this harness
# can never drift apart. Re-exported here for the existing call sites and tests.
from shared.warmup import WARMUP_COLS as _WARMUP_COLS, warmup_bars, trim_warmup  # noqa: E402
from shared.costs import turnover, net_returns  # noqa: E402

# Alias so `run(..., trim_warmup=...)` can still reach the function it shadows.
_trim = trim_warmup


def _config_cls(variant: str):
    _switch_variant(variant)
    cfg_mod = importlib.import_module("diversitas.config")
    # LeanConfig / MomentumConfig — pick the dataclass that isn't the alias
    for name in ("LeanConfig", "MomentumConfig", "Config"):
        if hasattr(cfg_mod, name):
            return getattr(cfg_mod, name)
    raise RuntimeError(f"no Config class found for {variant}")


def config_defaults(variant: str) -> dict:
    cls = _config_cls(variant)
    inst = cls()
    return {f.name: getattr(inst, f.name) for f in fields(inst)
            if f.name != "symbol_map"}


def make_config(variant: str, **overrides):
    cls = _config_cls(variant)
    valid = {f.name for f in fields(cls)}
    bad = set(overrides) - valid
    if bad:
        raise ValueError(f"{variant}: unknown config keys {bad}")
    return cls(**overrides)


def run(variant: str, daily: pd.DataFrame, btc: Optional[pd.DataFrame] = None,
        *, trim_warmup: bool = True, **overrides) -> pd.DataFrame:
    """Run a variant's strategy and return the annotated dataframe.

    `trim_warmup=True` (default) drops the leading bars on which the slowest
    indicator is undefined — see the module docstring for why this matters.
    """
    _switch_variant(variant)
    smod = importlib.import_module("diversitas.strategy")
    cfg = make_config(variant, **overrides)
    use_btc = getattr(cfg, "use_btc_filter", False)
    result = smod.run_strategy(daily, btc_daily=btc if use_btc else None, config=cfg)
    return _trim(result.df) if trim_warmup else result.df


def s_bull(variant: str) -> int:
    _switch_variant(variant)
    smod = importlib.import_module("diversitas.strategy")
    return int(smod.S_BULL)


def strategy_module(variant: str):
    """Return the variant's `diversitas.strategy` module (compute_features,
    run_state_machine, S_BULL/S_BEAR) for feature-overlay A/B testing."""
    _switch_variant(variant)
    return importlib.import_module("diversitas.strategy")


def run_overlay(variant: str, daily: pd.DataFrame, btc: Optional[pd.DataFrame],
                override_fn=None, *, trim_warmup: bool = True,
                **overrides) -> pd.DataFrame:
    """Run compute_features → (optional column override) → run_state_machine.

    `override_fn(df, cfg) -> df` mutates feature columns *before* the real state
    machine runs, so we test signal-level Q&A ideas against the actual, validated
    state machine instead of touching the Pine port.
    """
    smod = strategy_module(variant)
    cfg = make_config(variant, **overrides)
    use_btc = getattr(cfg, "use_btc_filter", False)
    df = smod.compute_features(daily, btc if use_btc else None, cfg)
    if override_fn is not None:
        df = override_fn(df, cfg)
    out = smod.run_state_machine(df, cfg)
    return _trim(out) if trim_warmup else out


def position(df: pd.DataFrame, bear_alloc_pct: float = 0.0,
             s_bull_code: int = 1) -> np.ndarray:
    """Next-bar position in [0,1]. Mirrors dashboards' `_pos_from_df`.

    Uses the `prev_*` columns that `trim_warmup` materialises when they exist, so
    a trimmed frame keeps the correct position on its first bar (see
    `shared/warmup.py`); falls back to shifting on an untrimmed frame.
    """
    prev_alloc = (df["prev_target_alloc"] if "prev_target_alloc" in df.columns
                  else df["target_alloc"].shift(1))
    prev_state = (df["prev_signal_state"] if "prev_signal_state" in df.columns
                  else df["signal_state"].shift(1))
    alloc   = prev_alloc.fillna(0.0).to_numpy() / 100.0
    is_bull = (prev_state == s_bull_code).to_numpy()
    bear_fl = np.where(is_bull, 0.0, bear_alloc_pct / 100.0)
    return np.minimum(alloc + bear_fl, 1.0)


def strat_returns(df: pd.DataFrame, bear_alloc_pct: float = 0.0,
                  fee_per_side_pct: float = 0.0, s_bull_code: int = 1) -> pd.Series:
    """Strategy daily returns, net of trading cost.

    Cost model is `shared.costs` — the same one the dashboards use, so a report and
    the live UI cannot disagree. It charges on the bar the position moves, not on
    the bar the signal flips (those differ by one bar), and never charges for a
    position inherited at the start of the window.
    """
    ret = df["close"].pct_change().fillna(0.0)
    pos = pd.Series(position(df, bear_alloc_pct, s_bull_code), index=df.index)
    return net_returns(pos, ret, fee_per_side_pct)
