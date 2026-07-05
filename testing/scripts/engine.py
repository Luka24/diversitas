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
        **overrides) -> pd.DataFrame:
    """Run a variant's strategy and return the annotated dataframe."""
    _switch_variant(variant)
    smod = importlib.import_module("diversitas.strategy")
    cfg = make_config(variant, **overrides)
    use_btc = getattr(cfg, "use_btc_filter", False)
    result = smod.run_strategy(daily, btc_daily=btc if use_btc else None, config=cfg)
    return result.df


def s_bull(variant: str) -> int:
    _switch_variant(variant)
    smod = importlib.import_module("diversitas.strategy")
    return int(smod.S_BULL)


def position(df: pd.DataFrame, bear_alloc_pct: float = 0.0,
             s_bull_code: int = 1) -> np.ndarray:
    """Next-bar position in [0,1]. Mirrors dashboards' `_pos_from_df`."""
    alloc   = df["target_alloc"].shift(1).fillna(0.0).to_numpy() / 100.0
    is_bull = (df["signal_state"].shift(1) == s_bull_code).to_numpy()
    bear_fl = np.where(is_bull, 0.0, bear_alloc_pct / 100.0)
    return np.minimum(alloc + bear_fl, 1.0)


def strat_returns(df: pd.DataFrame, bear_alloc_pct: float = 0.0,
                  fee_per_side_pct: float = 0.0, s_bull_code: int = 1) -> pd.Series:
    """Strategy daily returns with optional per-side fee on each signal change."""
    ret = df["close"].pct_change().fillna(0.0)
    pos = position(df, bear_alloc_pct, s_bull_code)
    sr  = pd.Series(ret.to_numpy() * pos, index=df.index)
    if fee_per_side_pct > 0:
        sr = sr - df["signal_changed"].fillna(False).astype(float) * (fee_per_side_pct / 100.0)
    return sr
