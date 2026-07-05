"""Campaign-wide trial counter — feeds the Deflated Sharpe Ratio.

Every distinct config scored on a given asset counts as one trial. The DSR uses
this so we can never quietly "find one good run in 500" and call it significant.
Persisted as JSON so it survives across phase scripts.
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PATH = _ROOT / "testing" / "results" / "trial_counter.json"


def _load() -> dict:
    if _PATH.exists():
        return json.loads(_PATH.read_text())
    return {}


def _save(d: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(d, indent=2, sort_keys=True))


def add(asset: str, variant: str, n: int = 1, phase: str = "") -> int:
    """Add `n` trials for (asset, variant); return the new cumulative total."""
    d = _load()
    key = f"{asset}:{variant}"
    rec = d.get(key, {"total": 0, "by_phase": {}})
    rec["total"] += n
    rec["by_phase"][phase] = rec["by_phase"].get(phase, 0) + n
    d[key] = rec
    _save(d)
    return rec["total"]


def get(asset: str, variant: str) -> int:
    return _load().get(f"{asset}:{variant}", {}).get("total", 0)


def snapshot() -> dict:
    return _load()
