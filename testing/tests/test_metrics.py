"""Phase 0 gate — metrics correctness against hand-computed fixtures + look-ahead audit."""
import numpy as np
import pandas as pd
import pytest

from testing.scripts import metrics as M
from testing.scripts import engine as E


# ── hand-computed toy fixtures ────────────────────────────────────────────────

def test_max_drawdown_known():
    r = pd.Series([0.10, -0.20, 0.05])
    # eq = [1.1, 0.88, 0.924]; peak=1.1; dd_min = 0.88/1.1 - 1 = -0.20
    c = M.core_stats(r, td=365)
    assert c["max_dd"] == pytest.approx(-0.20, abs=1e-9)


def test_cagr_known():
    # 1% per bar for 365 bars, td=365 → final ≈ 1.01**365, CAGR ≈ that - 1
    r = pd.Series([0.01] * 365)
    c = M.core_stats(r, td=365)
    expected = 1.01 ** 365 - 1.0
    assert c["cagr"] == pytest.approx(expected, rel=1e-9)


def test_sharpe_zero_vol_is_nan():
    r = pd.Series([0.001] * 100)
    c = M.core_stats(r, td=365)
    assert np.isnan(c["sharpe"])


def test_sortino_ge_sharpe_for_positively_skewed():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.001, 0.02, 2000))
    c = M.core_stats(r, td=365)
    # downside dev <= total std → sortino magnitude >= sharpe
    assert abs(c["sortino"]) >= abs(c["sharpe"]) - 1e-9


def test_calmar_is_cagr_over_maxdd():
    r = pd.Series([0.02, -0.05, 0.03, -0.10, 0.04] * 60)
    c = M.core_stats(r, td=365)
    assert c["calmar"] == pytest.approx(c["cagr"] / abs(c["max_dd"]), rel=1e-9)


# ── trade ledger ──────────────────────────────────────────────────────────────

def _toy_df():
    idx = pd.date_range("2023-01-01", periods=6, freq="D", tz="UTC")
    close = [100, 110, 121, 100, 90, 99]
    sig   = [3, 1, 1, 3, 3, 1]          # BEAR, BULL, BULL, BEAR, BEAR, BULL
    chg   = [False, True, False, True, False, True]
    return pd.DataFrame({"close": close, "signal_state": sig,
                         "signal_changed": chg, "target_alloc": [0,100,100,0,0,100]},
                        index=idx)


def test_trade_ledger_pnl():
    trades = M.build_trades(_toy_df())
    # entry@110 (bar1) → exit@100 (bar3): pnl = (100/110-1)*100 = -9.09%
    closed = [t for t in trades if not t["open"]]
    assert len(closed) == 1
    assert closed[0]["pnl_pct"] == pytest.approx((100/110 - 1) * 100, rel=1e-6)
    # last bar re-enters BULL → one open trade remains
    assert any(t["open"] for t in trades)


# ── look-ahead audit — position at t uses only signals up to t-1 ──────────────

def test_position_is_shifted():
    df = _toy_df()
    pos = E.position(df, bear_alloc_pct=0.0, s_bull_code=1)
    # bar0 has no prior → 0; bar1 pos = target_alloc[bar0]/100 = 0
    assert pos[0] == 0.0
    assert pos[1] == pytest.approx(df["target_alloc"].iloc[0] / 100.0)
    # bar2 pos = target_alloc[bar1]/100 = 1.0
    assert pos[2] == pytest.approx(1.0)


def test_no_lookahead_shuffle_future():
    """Mutating a future bar must not change today's position."""
    df = _toy_df()
    pos_a = E.position(df, s_bull_code=1)
    df2 = df.copy()
    df2.iloc[-1, df2.columns.get_loc("target_alloc")] = 42.0   # change the future
    pos_b = E.position(df2, s_bull_code=1)
    assert np.allclose(pos_a[:-1], pos_b[:-1])                 # past unchanged
