"""The three rules removed on 2026-08-03 must stay removed — and stay harmless.

`test_reference.py` proves the position series did not move. That is the main
claim. This file guards the things that could rot afterwards:

  * the parameters must be gone from the config, not merely unused, otherwise
    someone sweeps a knob that cannot change a trade and reads meaning into the
    noise;
  * `make_config` must REJECT them rather than ignore them, because a silently
    ignored `vol_shock_mul=999` turns "vol-shock disabled" into "vol-shock still
    on" without a word — the older analysis scripts pass exactly that;
  * the warm-up must still be 220 bars, since the two removed lengths used to
    feed `required_history` and a shortened warm-up would silently move the
    start date and therefore every metric;
  * the columns the dashboard still draws must survive the removal.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "testing", ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared.warmup import required_history                  # noqa: E402
from testing.scripts import engine                          # noqa: E402
from testing.scripts import freeze_reference as fr          # noqa: E402

GONE_PARAMS = ("min_dist_entry_pct", "ma_med_len", "vol_shock_mul", "vol_lookback")
GONE_COLS = ("dist_entry_ok", "vol_shock")
# Removed from the signal path, still computed because the dashboard plots them.
KEPT_COLS = ("ma_med", "above_ma_med", "annual_vol", "vol_avg50", "rsi")


def test_removed_parameters_are_gone_from_config():
    d = engine.config_defaults("lean")
    still_there = [p for p in GONE_PARAMS if p in d]
    assert not still_there, f"še vedno v LeanConfig: {still_there}"


@pytest.mark.parametrize("param", GONE_PARAMS)
def test_make_config_rejects_removed_parameters(param):
    """Loud failure, not a silent no-op.

    Several scripts under testing/scripts/ disable rules by passing
    vol_shock_mul=999. If that were quietly accepted and ignored they would keep
    printing numbers, and the numbers would be for the rule still switched ON.
    """
    with pytest.raises(ValueError):
        engine.make_config("lean", **{param: 1})


def test_signal_path_no_longer_carries_the_dead_columns():
    cfg = engine.make_config("lean")
    idx = pd.date_range("2020-01-01", periods=400, freq="D")
    px = pd.Series(range(400), index=idx, dtype=float) + 100.0
    raw = pd.DataFrame({"open": px, "high": px * 1.01,
                        "low": px * 0.99, "close": px})
    df = engine.strategy_module("lean").compute_features(raw, None, cfg)
    assert not [c for c in GONE_COLS if c in df.columns]
    assert not [c for c in KEPT_COLS if c not in df.columns], (
        "odstranjen je bil tudi izračun, ne le pogoj — dashboard tega ne bo narisal"
    )


def test_warmup_is_unchanged():
    """220 bars. ma_med_len (50) and vol_lookback+50 (70) both sat under
    ma_long_len (200), so dropping them cannot move the maximum — but if it ever
    did, the trimmed window would start on a different date and every metric in
    the project would shift without any other test noticing."""
    assert required_history(engine.make_config("lean")) == 220


@pytest.mark.skipif(not fr.SRC.exists(), reason="zamrznjen posnetek cen ni na voljo")
def test_no_entry_while_an_exit_rule_is_firing():
    """The strategy must never buy on a bar its own blow-off rule is selling on.

    Run with the pause REMOVED (reentry_hold=0). With it in place the situation is
    unreachable — the pause blocks re-entry for 15 bars after a blow-off exit — so
    a test at the default settings would pass without the guard and prove nothing.

    The second half is the negative control: strip `~blowoff` back out of
    bull_condition and the same run must produce entries on blow-off bars. Without
    that, a green first half could just mean blow-off never coincides with an
    entry opportunity.
    """
    raw = pd.read_parquet(fr.SRC)
    smod = engine.strategy_module("lean")
    cfg = engine.make_config("lean", reentry_hold=0)
    feat = smod.compute_features(raw, None, cfg)
    bo = feat["blowoff"].fillna(False)

    def entries_on_blowoff(frame) -> int:
        st = smod.run_state_machine(frame, cfg)
        opened = st["signal_changed"] & (st["signal_state"] == smod.S_BULL)
        return int((opened & bo).sum())

    assert entries_on_blowoff(feat) == 0, (
        "vstop je padel na dan, ko se je sprožil izstop zaradi pregretja"
    )

    unguarded = feat.copy()
    bull = pd.Series(True, index=feat.index)
    for t in ("above_tl", "track_rising_window", "regime_ok",
              "btc_filter_ok", "donchian_ok"):
        bull &= feat[t]
    unguarded["bull_condition"] = bull.fillna(False)
    assert entries_on_blowoff(unguarded) > 0, (
        "brez varovalke bi moral test pasti; ker ne pade, nima moči in "
        "test_no_entry_while_an_exit_rule_is_firing ničesar ne dokazuje"
    )


@pytest.mark.skipif(not fr.SRC.exists(), reason="zamrznjen posnetek cen ni na voljo")
def test_no_exit_was_ever_attributed_to_vol_shock():
    """The reason the removal is safe, stated as a test rather than a claim.

    Every BULL→BEAR transition in the frozen history is either a trend break or
    a blow-off. If a third kind ever appears, the removal was not neutral.
    """
    raw = pd.read_parquet(fr.SRC)
    df = engine.run("lean", raw)
    smod = engine.strategy_module("lean")
    exits = df.index[df["signal_changed"] & (df["signal_state"] != smod.S_BULL)]
    for ts in exits:
        row = df.loc[ts]
        assert bool(row["blowoff"]) or int(row["below_count"]) >= 3, (
            f"izstop {ts.date()} ni razložen niti s trend-breakom niti z blow-offom"
        )
