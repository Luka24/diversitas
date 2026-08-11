"""The dashboard and the reports must not be able to disagree.

Three independent paths produce the same numbers:
  A. the live dashboard's own functions (`lean/diversitas/dashboard.py`)
  B. the report/test harness (`testing/scripts/engine.py` + `metrics.py`)
  C. a from-scratch recomputation written here, importing neither

If any of them drifts, the parity assertions below fail.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
for p in (_ROOT, _ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared.warmup import trim_warmup, warmup_bars          # noqa: E402
from testing.scripts import dataio, engine, metrics          # noqa: E402

FEE = 0.30            # % per side, the dashboard's default
BARS = 2000           # the dashboard's default fetch


@pytest.fixture(scope="module")
def frozen():
    return dataio.load("BTC").iloc[-BARS:]


def _strategy_df(daily):
    """What both consumers start from: run the Pine-ported strategy, then trim."""
    from diversitas.config import LeanConfig
    from diversitas.strategy import run_strategy
    return trim_warmup(run_strategy(daily, btc_daily=None, config=LeanConfig()).df)


# ── C: written from scratch, no project helpers ──────────────────────────────
def _scratch(df, fee_pct):
    """The correct model, written out longhand: yesterday's signal is today's
    position, and a cost is paid on the bar the position actually moves. Uses the
    materialised `prev_signal_state` so the first bar of a trimmed frame keeps the
    position it was actually holding."""
    ret = df["close"].pct_change().fillna(0.0).to_numpy()
    bull = (df["prev_signal_state"] == 1).fillna(False).to_numpy().astype(float)
    turnover = np.abs(np.diff(bull, prepend=bull[0]))   # 0 on bar 1 by construction
    r = ret * bull - turnover * (fee_pct / 100.0)
    eq = np.cumprod(1.0 + r)
    dd = eq / np.maximum.accumulate(eq) - 1.0
    years = len(r) / 365.0
    cagr = eq[-1] ** (1 / years) - 1
    downside = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(365)
    return dict(final=eq[-1], cagr=cagr * 100, maxdd=dd.min() * 100,
                sortino=r.mean() * 365 / downside, expo=bull.mean() * 100)


def test_warmup_is_trimmed_and_regime_filter_is_live(frozen):
    raw = None
    from diversitas.config import LeanConfig
    from diversitas.strategy import run_strategy
    raw = run_strategy(frozen, btc_daily=None, config=LeanConfig()).df
    n = warmup_bars(raw)
    assert n == 199, "Lean's warm-up is the 200-day MA"
    # the actual failure mode: permissive, not undefined
    assert raw["regime_ok"].iloc[:n].all()
    assert not raw["bear_regime"].iloc[:n].any()
    # after trimming, the regime column is driven by a real MA
    trimmed = trim_warmup(raw)
    assert trimmed["ma_long"].notna().all()
    assert len(trimmed) == len(raw) - n


def test_dashboard_matches_scratch_recomputation(frozen):
    """Path A vs path C."""
    from diversitas import dashboard as dash
    df = _strategy_df(frozen)
    got = dash._compute_metrics(df, bear_alloc_pct=0.0, td=365, fee_per_side_pct=FEE)
    want = _scratch(df, FEE)
    s = got["strategy"]
    assert s["cagr"] * 100 == pytest.approx(want["cagr"], abs=1e-6)
    assert s["max_dd"] * 100 == pytest.approx(want["maxdd"], abs=1e-6)
    assert s["sortino"] == pytest.approx(want["sortino"], abs=1e-6)


def test_harness_matches_scratch_recomputation(frozen):
    """Path B vs path C. The harness prices costs off turnover, the dashboard off
    signal changes — for Lean's binary position these must be identical."""
    df = _strategy_df(frozen)
    r = engine.strat_returns(df, fee_per_side_pct=FEE, s_bull_code=1)
    c = metrics.core_stats(r)
    want = _scratch(df, FEE)
    assert c["cagr"] * 100 == pytest.approx(want["cagr"], abs=1e-6)
    assert c["max_dd"] * 100 == pytest.approx(want["maxdd"], abs=1e-6)
    assert c["sortino"] == pytest.approx(want["sortino"], abs=1e-6)


def test_fee_is_charged_when_the_position_moves_not_when_the_signal_flips(frozen):
    """`signal_changed` is one bar earlier than the position change, because the
    position is yesterday's signal. Charging off it (as the dashboard used to)
    prices the trade a day early — same total, different daily series, and a
    mismatch against every report."""
    df = _strategy_df(frozen)
    pos = pd.Series(engine.position(df, s_bull_code=1), index=df.index)
    turnover = pos.diff().abs().fillna(0.0)
    signal = df["signal_changed"].fillna(False).astype(float)
    assert float((turnover - signal).abs().max()) == 1.0, "the offset is real"
    # every turnover event sits exactly one bar after a signal change
    assert float((turnover - signal.shift(1).fillna(0.0)).abs().max()) == pytest.approx(0.0, abs=1e-12)


def test_position_survives_the_trim_boundary(frozen):
    """The strategy is often still in a position when the warm-up ends. Deriving
    the position from a trimmed frame with a naive shift(1) drops that day and
    invents an entry cost; `trim_warmup` materialises `prev_*` to prevent it."""
    from diversitas.config import LeanConfig
    from diversitas.strategy import run_strategy
    raw = run_strategy(frozen, btc_daily=None, config=LeanConfig()).df
    n = warmup_bars(raw)
    assert int(raw["signal_state"].iloc[n - 1]) == 1, "fixture must straddle the boundary"

    trimmed = trim_warmup(raw)
    on_trimmed = pd.Series(engine.position(trimmed, s_bull_code=1), index=trimmed.index)
    on_full = pd.Series(engine.position(raw, s_bull_code=1), index=raw.index).loc[trimmed.index]
    assert on_trimmed.iloc[0] == 1.0, "position carried across the boundary"
    assert float((on_trimmed - on_full).abs().max()) == pytest.approx(0.0, abs=1e-12)


def test_price_source_chain_is_ordered_and_never_falls_back_silently():
    """Entry is a threshold, so ~0.1 % of price moves whole trades. Measured on
    BTC 2020-07-14 to 2026-08-11 at 0.30 %/side, Coinbase costs 1.7 points of
    CAGR against Binance and takes the same eleven trades; Yahoo costs 7.6 and
    nine points of drawdown, and takes thirteen. Coinbase is the same strategy
    on slightly different prices, Yahoo is a different one — so Yahoo left the
    crypto chain on 2026-08-11 and stays only where it is the sole venue."""
    import inspect
    from diversitas import dashboard as dash
    assert dash.CRYPTO_SOURCE_CHAIN == ("binance", "coinbase"), \
        "crypto falls back only to another real exchange"
    assert "yahoo" not in dash.CRYPTO_SOURCE_CHAIN, \
        "a Yahoo fallback silently draws a different strategy"
    assert dash._source_chain("BTC") == dash.CRYPTO_SOURCE_CHAIN
    # equities have no other venue, so they must keep it
    assert dash._source_chain("SPY") == ("yahoo",), \
        "SPY/QQQ/GLD exist only on Yahoo; dropping it would break them"
    src = inspect.getsource(dash._load_candles)
    assert "strict=True" in src, "each venue must be tried without a hidden fallback"
    assert "_source_chain(" in src, "the order must come from the named chain"
    assert 'attrs["source"]' in src, "the venue that answered must be recorded"
    assert "fell_back_from" in src, "a fallback must be marked so the UI can warn"
    assert "failed_at" in src, "a banner with no time cannot be told from a stale one"
    main = inspect.getsource(dash)
    assert 'attrs.get("fell_back_from")' in main and "st.error(" in main, \
        "a fallback must surface as a visible error, not pass silently"
    assert 'attrs.get("source_errors")' in main, \
        "the reason was recorded but never rendered for weeks; keep it rendered"


def test_a_pinned_source_leads_the_chain_and_silences_the_fallback_banner():
    """Binance geo-blocks datacenter IPs, so the hosted deployment gets HTTP 451
    permanently while a laptop gets 200. Telling the user to wait for it to come
    back is telling them to wait for nothing, so the venue can be pinned per
    deployment and the page then reports a choice rather than a failure."""
    import os
    from diversitas import dashboard as dash
    prev = os.environ.get("DIVERSITAS_PRICE_SOURCE")
    try:
        os.environ.pop("DIVERSITAS_PRICE_SOURCE", None)
        assert dash._source_chain("BTC") == ("binance", "coinbase")

        os.environ["DIVERSITAS_PRICE_SOURCE"] = "coinbase"
        assert dash._source_chain("BTC") == ("coinbase", "binance"), \
            "the pin must lead, with the rest of the chain kept behind it"
        # equities have one venue; a crypto pin must not redirect them
        assert dash._source_chain("SPY") == ("yahoo",)

        # garbage must not silently become the source
        os.environ["DIVERSITAS_PRICE_SOURCE"] = "not-a-venue"
        assert dash._source_chain("BTC") == ("binance", "coinbase")
    finally:
        os.environ.pop("DIVERSITAS_PRICE_SOURCE", None)
        if prev is not None:
            os.environ["DIVERSITAS_PRICE_SOURCE"] = prev


def test_every_symbol_that_claims_a_fallback_actually_has_one():
    """LeanConfig's symbol_map overrides the shared default. When it omitted the
    `coinbase` ids, that branch raised and was skipped, so the chain was really
    binance → yahoo with no middle step and nothing said so."""
    from diversitas.config import DEFAULT_CONFIG
    from shared.data_source import DEFAULT_SYMBOL_MAP
    for sym, ids in DEFAULT_SYMBOL_MAP.items():
        if sym not in DEFAULT_CONFIG.symbol_map:
            continue
        missing = set(ids) - set(DEFAULT_CONFIG.symbol_map[sym])
        assert not missing, f"{sym}: LeanConfig drops {missing} that the shared map has"


def test_engine_run_and_dashboard_see_the_same_frame(frozen):
    """The harness `engine.run` and the dashboard path must return the identical
    trimmed frame — same index, same signal, same allocation."""
    a = engine.run("lean", frozen)
    b = _strategy_df(frozen)
    assert a.index.equals(b.index)
    assert (a["signal_state"].to_numpy() == b["signal_state"].to_numpy()).all()
    assert (a["target_alloc"].to_numpy() == b["target_alloc"].to_numpy()).all()
