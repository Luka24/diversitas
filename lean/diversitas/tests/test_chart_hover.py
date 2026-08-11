"""One hover reading per line per date.

The trackline is drawn as segments coloured by slope, and the segments overlap
by one point so the line has no gap where the colour flips. That overlap put the
flip bar in two traces at once, and `hovermode="x unified"` duly listed the
trackline twice on every one of them — 342 of 2700 dates on BTC.

The fix is that coloured segments no longer answer the hover; a single
transparent trace over the whole series does. These tests hold that line.
"""
import collections

import numpy as np
import pandas as pd
import pytest

from diversitas.config import LeanConfig
from diversitas.strategy import run_strategy
import diversitas.dashboard as D

HOVER_LINES = {"TL": "Trackline", "200 MA": "200 MA (regime)"}


@pytest.fixture(scope="module")
def fig():
    D._set_theme(True)
    rng = np.random.default_rng(3)
    n = 700
    idx = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    close = 100 * np.exp(np.linspace(0, 1, n) + np.cumsum(rng.normal(0, 0.03, n)))
    close = pd.Series(close, index=idx)
    daily = pd.DataFrame({"open": close, "high": close * 1.02, "low": close * 0.98,
                          "close": close, "volume": rng.uniform(1e6, 5e6, n)}, index=idx)
    df = run_strategy(daily, config=LeanConfig()).df
    return D._build_price_chart(df, "TEST"), df


def _hover_counts(figure, prefix: str) -> collections.Counter:
    c = collections.Counter()
    for tr in figure.data:
        if getattr(tr, "hoverinfo", None) == "skip":
            continue
        ht = getattr(tr, "hovertemplate", None) or ""
        if not ht.startswith(prefix):
            continue
        for x in tr.x:
            c[x] += 1
    return c


@pytest.mark.parametrize("prefix", sorted(HOVER_LINES))
def test_each_date_hovers_exactly_one_value(fig, prefix):
    figure, df = fig
    counts = _hover_counts(figure, prefix)
    dupes = {k: v for k, v in counts.items() if v > 1}
    assert not dupes, (
        f"{prefix} reports more than one value on {len(dupes)} dates, e.g. "
        f"{sorted(dupes)[:3]} — overlapping segments are answering the hover again"
    )
    assert len(counts) == len(df), (
        f"{prefix} hovers on {len(counts)} dates but the frame has {len(df)}; "
        f"the transparent hover trace does not span the series"
    )


@pytest.mark.parametrize("prefix,name", sorted(HOVER_LINES.items()))
def test_the_line_is_still_drawn_in_colour(fig, prefix, name):
    """Negative control: killing the hover must not have killed the colouring."""
    figure, _ = fig
    seg = [t for t in figure.data
           if t.name == name and getattr(t, "hoverinfo", None) == "skip"]
    assert len(seg) > 1, f"{name} is no longer drawn as coloured segments"
    colours = {t.line.color for t in seg}
    assert len(colours) == 2, (
        f"{name} uses {len(colours)} colours, expected two (rising / falling)"
    )
    # and the segments must overlap, or the line shows gaps at every flip
    ends = [(t.x[0], t.x[-1]) for t in seg]
    overlaps = sum(1 for a, b in zip(ends, ends[1:]) if a[1] == b[0])
    assert overlaps == len(ends) - 1, "segments no longer share their endpoints"


def test_only_one_legend_entry_per_line(fig):
    figure, _ = fig
    for name in HOVER_LINES.values():
        shown = [t for t in figure.data if t.name == name and t.showlegend]
        assert len(shown) <= 1, f"{name} appears {len(shown)} times in the legend"
