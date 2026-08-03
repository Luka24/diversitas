"""The simplification is only provably neutral if this test is green.

Two tests, and the second is the one that gives the first any meaning. A
comparison that cannot fail proves nothing, so the negative control perturbs a
single parameter and requires the comparison to notice.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "testing", ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared.warmup import trim_warmup                      # noqa: E402
from testing.scripts import engine                         # noqa: E402
from testing.scripts import freeze_reference as fr         # noqa: E402

pytestmark = pytest.mark.skipif(
    not fr.SRC.exists(), reason="zamrznjen posnetek cen ni na voljo")


def _positions(**overrides) -> pd.Series:
    raw = pd.read_parquet(fr.SRC)
    cfg = engine.make_config("lean", **overrides)
    df = trim_warmup(engine.strategy_module("lean")
                     .run_strategy(raw, btc_daily=None, config=cfg).df)
    return pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)


def test_positions_match_reference():
    """Today's code must reproduce the frozen series bar for bar.

    Metrics are deliberately not compared: two different paths can share a
    Sortino, but they cannot share a position series.
    """
    assert fr.REF.exists(), "reference ni — poženi freeze_reference.py freeze"
    assert fr.do_verify(quiet=True) == 0, (
        "pozicijska serija se ne ujema z zamrznjeno referenco. "
        "To pomeni spremenjeno logiko, ne odstranjeno mrtvo kodo."
    )


def test_reference_check_would_notice_a_change():
    """Negative control: perturb one parameter and require a difference.

    Without this, a comparison that silently always passes would look like proof.
    confirm_bars is used because it shifts entry timing without touching warm-up,
    so the two series stay the same length and the difference is unambiguous.
    """
    base = _positions()
    moved = _positions(confirm_bars=2)
    assert base.index.equals(moved.index)
    n = int((np.abs(base.to_numpy() - moved.to_numpy()) > 1e-12).sum())
    assert n > 0, (
        "sprememba confirm_bars 3 -> 2 ni premaknila nobene pozicije; "
        "primerjava nima moči in test_positions_match_reference ničesar ne dokazuje"
    )


def test_reference_metadata_is_complete():
    """The reference is worth nothing without knowing what produced it."""
    import json
    meta = json.loads(fr.META.read_text(encoding="utf-8"))
    for key in ("created_utc", "git", "sha256", "n_bars", "from", "to", "metrics"):
        assert meta.get(key), f"manjka {key}"
    assert len(meta["sha256"]) == 64
    assert meta["git"] != "?", "commit ni zabeležen"
