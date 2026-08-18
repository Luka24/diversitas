"""Live Streamlit dashboard — Diversitas Lean.  TradingView-style layout."""
from __future__ import annotations
import sys
from pathlib import Path

_VARIANT_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _VARIANT_ROOT.parent
for p in (_PROJECT_ROOT, _VARIANT_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import datetime
import math
import os
import time
import tomllib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from shared.data_source import fetch_candles, fetch_btc_daily, fetch_spx_daily
try:
    from shared.data_source import BINANCE_HOSTS
except ImportError:
    # A deployment can be mid-update: this file already asks for the constant
    # while the `shared` it imports still predates it. That used to take the
    # whole app down with an ImportError. One host is also the truthful answer
    # for that older module, and it is what the banner reads to tell you the
    # process is stale — so the degraded case reports itself.
    BINANCE_HOSTS = ("https://api.binance.com/api/v3/klines",)
from shared.warmup import trim_warmup, warmup_bars, required_history
from shared.costs import turnover as shared_turnover
from diversitas.config import LeanConfig, DEFAULT_CONFIG
from diversitas.strategy import (run_strategy, build_summary, position,
                                 traded_fraction, S_BULL, S_NEUTRAL, S_BEAR)


TRADING_DAYS = 365  # crypto default
STOCK_SYMBOLS: frozenset[str] = frozenset({"SPY", "QQQ", "GLD"})  # 252 trading days/yr

# ── accent colors (theme-independent) ────────────────────────────────────────
COL_BULL    = "#089981"
COL_BEAR    = "#f23645"
COL_NEUTRAL = "#ffb74d"
COL_BLUE    = "#2962ff"
COL_MA50    = "#2196f3"
COL_MA200   = "#ff9800"
COL_SPX     = "#f59e0b"   # gold — S&P 500 benchmark

# ── theme colors (reassigned by _set_theme each render) ──────────────────────
COL_BG = COL_PANEL = COL_BORDER = COL_GRID = ""
COL_TEXT = COL_DIM = COL_VERY_DIM = COL_TEMPLATE = ""

_DARK = dict(
    BG="#131722", PANEL="#1e222d", BORDER="#2a2e39",
    GRID="#1e2230", TEXT="#d1d4dc", DIM="#787b86", VERY_DIM="#4c525e",
    TEMPLATE="plotly_dark",
)
_LIGHT = dict(
    BG="#f8f9fe", PANEL="#ffffff", BORDER="#e0e3eb",
    GRID="#eaecf2", TEXT="#131722", DIM="#787b86", VERY_DIM="#adb0b8",
    TEMPLATE="plotly",
)


def _set_theme(dark: bool) -> None:
    global COL_BG, COL_PANEL, COL_BORDER, COL_GRID
    global COL_TEXT, COL_DIM, COL_VERY_DIM, COL_TEMPLATE
    t = _DARK if dark else _LIGHT
    COL_BG, COL_PANEL, COL_BORDER = t["BG"], t["PANEL"], t["BORDER"]
    COL_GRID, COL_TEXT, COL_DIM   = t["GRID"], t["TEXT"], t["DIM"]
    COL_VERY_DIM = t["VERY_DIM"]
    COL_TEMPLATE = t["TEMPLATE"]


# ── caching ───────────────────────────────────────────────────────────────────

# Yahoo left the crypto chain on 2026-08-11. It is a scraped composite, not an
# exchange, and it is not a near-substitute: on BTC 2020-07-14 to 2026-08-11 at
# 0.30 %/side it costs 7.8 points of CAGR and ten points of drawdown against
# Binance, with two extra trades. Coinbase costs 1.7 points and takes the same
# eleven trades (testing/scripts/source_impact.py). Falling back to Coinbase
# shows the same strategy on slightly different prices; falling back to Yahoo
# shows a different strategy, which is not a fallback — better to say there is
# no data than to draw that.
#
# Equities keep it because it is the only venue that has them at all.
CRYPTO_SOURCE_CHAIN = ("binance", "coinbase")
STOCK_SOURCE_CHAIN = ("yahoo",)
VENUES = ("binance", "coinbase", "yahoo")


def _pinned_source() -> str | None:
    """An explicitly chosen venue, from the env or Streamlit secrets.

    Binance geo-blocks datacenter IPs, so the hosted deployment gets HTTP 451
    where a laptop gets 200 — permanently, not as an outage. Waiting for it to
    come back is waiting for something that will not happen, and the banner
    saying so on every render is noise rather than news.

    Setting this makes the venue a decision instead: the page pins what is
    actually reachable, says which one it is, and stops crying wolf. It is read
    per deployment, so a laptop can stay on Binance while the cloud runs on
    Coinbase.

    Read from the environment, then Streamlit secrets, then deployment.toml at
    the repo root. The committed file is last so either of the other two can
    override it for a single session, and it exists at all because Streamlit
    Cloud has no way to set an environment variable without going through the
    secrets UI — this keeps the choice in version control, where the reasoning
    can sit next to it.
    """
    def _secret():
        try:
            return st.secrets.get("price_source")     # .streamlit/secrets.toml
        except Exception:                             # no secrets file at all
            return None

    # Each layer is validated on its own, so a typo in the environment falls
    # through to the file rather than silently disabling the deployed choice.
    for get in (lambda: os.environ.get("DIVERSITAS_PRICE_SOURCE"), _secret,
                lambda: _deployment_setting("price_source")):
        val = (get() or "").strip().lower()
        if val in VENUES:
            return val
    return None


@st.cache_data(ttl=300, show_spinner=False)
def _deployment_settings() -> dict:
    path = _PROJECT_ROOT / "deployment.toml"
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception:            # absent or malformed — fall back to defaults
        return {}


def _deployment_setting(key: str):
    return _deployment_settings().get(key)


def _source_chain(symbol: str) -> tuple[str, ...]:
    default = STOCK_SOURCE_CHAIN if symbol in STOCK_SYMBOLS else CRYPTO_SOURCE_CHAIN
    pin = _pinned_source()
    if pin is None or symbol in STOCK_SYMBOLS:
        return default
    # The pin leads; whatever else was in the chain stays behind it as backup.
    return (pin,) + tuple(s for s in default if s != pin)


@st.cache_data(ttl=60, show_spinner=False)
def _load_candles(symbol: str, bars: int) -> pd.DataFrame:
    """Try the venues in order and record which one answered.

    Order is deliberate: Binance and Coinbase are real exchanges whose prices you
    can actually trade at; Yahoo is a scraped composite and sits last. It matters
    which one you get — entry is a threshold, so ~0.1 % of price difference moves
    whole trades (3 percentage points of CAGR between Binance and Yahoo on BTC).
    A fallback is therefore allowed, but never silent: the caller marks it and the
    footer shows it.

    Two things were wrong here until 2026-08-11, and together they hid a fallback
    that had been running for weeks. Only `type(e).__name__` was kept, so the
    reason became the word "DataSourceError" — no status code, no body, nothing
    that says whether it was a timeout, a rate limit or a geo-block. And the
    string it went into, `attrs["source_errors"]`, was never rendered anywhere.
    The banner said Binance was unreachable and there was no way to learn why.
    Both are fixed: the real message is kept, and the banner prints it.

    The primary venue also gets one retry. A single 15-second timeout used to be
    enough to drop the whole session onto Coinbase.
    """
    errors = []
    chain = _source_chain(symbol)
    for i, src in enumerate(chain):
        attempts = 2 if i == 0 else 1     # retry the pinned source only
        for attempt in range(attempts):
            try:
                df = fetch_candles(symbol, "1d", bars=bars, config=DEFAULT_CONFIG,
                                   prefer=src, strict=True)
            except Exception as e:  # noqa: BLE001
                if attempt + 1 < attempts:
                    time.sleep(1.0)
                    continue
                errors.append(f"{src}: {type(e).__name__}: {str(e)[:300]}")
                df = None
            break
        if df is None:
            continue
        df.attrs["source"] = src
        if i:
            df.attrs["fell_back_from"] = chain[0]
            df.attrs["source_errors"] = " | ".join(errors)
            # A banner with no time on it cannot be told apart from a stale one
            # left on screen since the last failure — which is exactly how an
            # already-fixed outage kept looking live.
            df.attrs["failed_at"] = datetime.datetime.now(datetime.timezone.utc)
            df.attrs["binance_hosts"] = len(BINANCE_HOSTS)
        return df
    raise RuntimeError(f"{symbol}: noben vir ni odgovoril — {' | '.join(errors)}")


@st.cache_data(ttl=60, show_spinner=False)
def _run(symbol: str, bars: int, use_btc_filter: bool):
    _td   = 252 if symbol in STOCK_SYMBOLS else TRADING_DAYS
    cfg   = LeanConfig(use_btc_filter=use_btc_filter, trading_days=_td)
    daily = _load_candles(symbol, bars)
    btc   = _load_btc(bars) if use_btc_filter else None
    res   = run_strategy(daily, btc_daily=btc, config=cfg)
    # Keep the untrimmed frame. The first bar AFTER trimming needs the bar before
    # it to have a return at all, and that bar only exists here. Passing the
    # trimmed frame as `df_full` covers the user's date filter but not the
    # warm-up boundary, which silently zeroed a real day. Invisible while the
    # position on that bar was 0; the 5 % floor makes it never 0.
    res.untrimmed = res.df
    # Drop the bars on which the 200-day MA does not exist yet. Without this the
    # regime block is silently disabled there (see shared/warmup.py) and the
    # dashboard reports trades the strategy would never have taken.
    res.df = trim_warmup(res.df)
    return cfg, daily, res          # `daily` stays raw so the footer can show what was dropped


@st.cache_data(ttl=60, show_spinner=False)
def _run_b(symbol: str, bars: int):
    _td   = 252 if symbol in STOCK_SYMBOLS else TRADING_DAYS
    cfg   = LeanConfig(use_btc_filter=False, trading_days=_td)
    daily = _load_candles(symbol, bars)
    res   = run_strategy(daily, config=cfg)
    res.df = trim_warmup(res.df)
    return cfg, res


@st.cache_data(ttl=3600, show_spinner=False)
def _load_spx(bars: int) -> pd.Series:
    """S&P 500 daily close prices via direct Yahoo Finance API. Timezone-naive."""
    return fetch_spx_daily(bars)


# ── performance metrics ───────────────────────────────────────────────────────

def _stats(r: pd.Series, td: int = TRADING_DAYS) -> dict:
    r = r.replace([np.inf, -np.inf], 0.0)
    eq    = (1.0 + r).cumprod()
    peak  = eq.cummax()
    dd    = (eq / peak - 1.0)
    max_dd = float(dd.min())
    years  = max(len(r) / td, 1e-9)
    final  = float(eq.iloc[-1]) if len(eq) else 1.0
    cagr   = final ** (1.0 / years) - 1.0
    ann_ret = r.mean() * td
    ann_std = r.std() * np.sqrt(td)
    down_dev = np.sqrt(np.mean(np.minimum(r.values, 0.0) ** 2)) * np.sqrt(td)
    sharpe   = ann_ret / ann_std if ann_std > 1e-9 else np.nan
    sortino  = ann_ret / down_dev if down_dev > 1e-9 else np.nan
    calmar   = cagr / abs(max_dd) if max_dd < -1e-6 else np.nan
    return dict(cagr=cagr, sharpe=sharpe, sortino=sortino,
                max_dd=max_dd, calmar=calmar, eq=eq, dd=dd)


def _prev_state(df: pd.DataFrame) -> pd.Series:
    """Yesterday's signal. `trim_warmup` materialises this before slicing, so a
    trimmed frame keeps the right position on its first bar (shared/warmup.py)."""
    if "prev_signal_state" in df.columns:
        return df["prev_signal_state"]
    return df["signal_state"].shift(1)


# The cost model lives in shared/costs.py so the dashboard and the reports cannot
# use two different ones. See that module for why turnover, not `signal_changed`.
_turnover = shared_turnover


def _held_and_traded(src: pd.DataFrame, idx: pd.Index, bear_alloc_pct: float):
    """The held share and what was traded, aligned to `idx`.

    Every consumer on this page has to answer the same two questions, and each
    one used to answer them itself, picking the full position when long and the
    bare floor otherwise. That is correct only while the floor is rebalanced
    daily. Once it drifts, six hand-written copies means six different pictures
    of the same portfolio, and a page that disagrees with itself is worse than a
    page that is wrong in one place.

    `trim_warmup` is applied because during warm-up the regime filter is
    silently permissive, so those bars carry signals the strategy would never
    have acted on and the drift path would start from the wrong place.
    """
    cfg = LeanConfig(bear_alloc_pct=bear_alloc_pct)
    base = trim_warmup(src)
    held = position(base, cfg).reindex(idx)
    traded = traded_fraction(base, cfg).reindex(idx).fillna(0.0)
    return held, traded


# Defaults come from the config, not from a literal. They used to be 0.0 while
# LeanConfig said 5.0, so the live page was right (the slider is initialised from
# the config) but anyone calling these directly got a floorless number without
# being told. Two defaults for one setting is a way to be quietly wrong.
def _compute_metrics(df: pd.DataFrame, bear_alloc_pct: float = DEFAULT_CONFIG.bear_alloc_pct,
                     td: int = TRADING_DAYS,
                     df_full: "pd.DataFrame | None" = None,
                     fee_per_side_pct: float = 0.0) -> dict:
    # Compute returns on df_full (unfiltered) so the first bar of a date-filtered
    # window has the correct return instead of NaN→0.
    src          = df_full if df_full is not None else df
    ret_full     = src["close"].pct_change().fillna(0.0)
    ib_full      = (_prev_state(src) == S_BULL).astype(float)
    sig_ch_full  = src["signal_changed"].fillna(False)
    ret          = ret_full.reindex(df.index).fillna(0.0)
    is_bull      = ib_full.reindex(df.index).fillna(0.0)
    sig_ch       = sig_ch_full.reindex(df.index).fillna(False)
    pos, traded  = _held_and_traded(src, df.index, bear_alloc_pct)
    strat_ret    = pos * ret
    if fee_per_side_pct > 0:
        # Charge on the bar the position actually moves, not on the bar the signal
        # flips — trading happens the day after the signal. `signal_changed` is one
        # bar early, which made the dashboard disagree with the reports.
        # `traded`, not the change in `pos`. Drift moves the share without a
        # transaction, and billing it would charge for something nobody does.
        strat_ret = strat_ret - traded * (fee_per_side_pct / 100.0)
    return {"strategy": _stats(strat_ret, td), "bh": _stats(ret, td)}


def _compute_portfolio_metrics(df_a: pd.DataFrame, df_b: pd.DataFrame,
                                w_a: int, w_b: int,
                                bear_alloc_pct: float = DEFAULT_CONFIG.bear_alloc_pct,
                                td_a: int = TRADING_DAYS,
                                td_b: int = TRADING_DAYS,
                                df_a_full: "pd.DataFrame | None" = None,
                                df_b_full: "pd.DataFrame | None" = None,
                                fee_per_side_pct: float = 0.0):
    """Floating-weight portfolio metrics for A, B, and combined."""
    idx  = df_a.index.intersection(df_b.index)
    a, b = df_a.loc[idx], df_b.loc[idx]

    src_a = df_a_full if df_a_full is not None else df_a
    src_b = df_b_full if df_b_full is not None else df_b
    r_a_full      = src_a["close"].pct_change().fillna(0.0)
    pos_a_full    = (_prev_state(src_a) == S_BULL).astype(float)
    sig_ch_a_full = src_a["signal_changed"].fillna(False)
    r_b_full      = src_b["close"].pct_change().fillna(0.0)
    pos_b_full    = (_prev_state(src_b) == S_BULL).astype(float)
    sig_ch_b_full = src_b["signal_changed"].fillna(False)

    r_a      = r_a_full.reindex(idx).fillna(0.0)
    ib_a     = pos_a_full.reindex(idx).fillna(0.0)
    sig_ch_a = sig_ch_a_full.reindex(idx).fillna(False)
    pos_a, trd_a = _held_and_traded(src_a, idx, bear_alloc_pct)
    sr_a     = pos_a * r_a

    r_b      = r_b_full.reindex(idx).fillna(0.0)
    ib_b     = pos_b_full.reindex(idx).fillna(0.0)
    sig_ch_b = sig_ch_b_full.reindex(idx).fillna(False)
    pos_b, trd_b = _held_and_traded(src_b, idx, bear_alloc_pct)
    sr_b     = pos_b * r_b

    if fee_per_side_pct > 0:
        fee   = fee_per_side_pct / 100.0
        sr_a  = sr_a - trd_a * fee
        sr_b  = sr_b - trd_b * fee

    wa, wb     = w_a / 100.0, w_b / 100.0
    port_strat = wa * sr_a + wb * sr_b
    port_bh    = wa * r_a  + wb * r_b
    td_port    = td_a  # primary asset determines portfolio annualization

    m_a    = {"strategy": _stats(sr_a, td_a), "bh": _stats(r_a, td_a)}
    m_b    = {"strategy": _stats(sr_b, td_b), "bh": _stats(r_b, td_b)}
    m_port = {"strategy": _stats(port_strat, td_port), "bh": _stats(port_bh, td_port)}
    return m_a, m_b, m_port, a, b, port_strat


def _worst_windows_from_sr(sr: pd.Series, td: int, window: int = 365) -> dict:
    """Worst rolling `window`-bar period for each metric.

    Returns dict with keys: {metric}, {metric}_start, {metric}_end, _roll_cagr.
    All dates are Python date objects.
    """
    if len(sr) < window + 10:
        return {}

    sr = sr.replace([np.inf, -np.inf], 0.0)

    # ── rolling CAGR (annualised) ─────────────────────────────────────────────
    log_r     = np.log1p(sr.clip(lower=-0.999))
    roll_log  = log_r.rolling(window).sum()
    roll_cagr = np.exp(roll_log * (td / window)) - 1

    # ── rolling loop: Sharpe / Sortino / Max DD / Calmar ────────────────────
    # All use exactly the same formula as _stats() so "Worst yr" values match
    # the KPI cards when the user selects that date range.
    #   Sharpe  = ann_ret / std(all_returns, ddof=1)                    [pandas default]
    #   Sortino = ann_ret / sqrt(mean(min(r,0)^2)) * sqrt(td)          [standard semi-deviation]
    #   Max DD  = min(equity/cummax - 1)
    #   Calmar  = CAGR / |Max DD|
    arr         = sr.values
    n           = len(arr)
    sharpe_arr  = np.full(n, np.nan)
    sortino_arr = np.full(n, np.nan)
    mdd_arr     = np.full(n, np.nan)

    for i in range(window - 1, n):
        w    = arr[i - window + 1 : i + 1]
        ar   = w.mean() * td
        s    = w.std(ddof=1) * np.sqrt(td)
        if s > 1e-9:
            sharpe_arr[i] = ar / s
        ds = np.sqrt(np.mean(np.minimum(w, 0.0) ** 2)) * np.sqrt(td)
        if ds > 1e-9:
            sortino_arr[i] = ar / ds
        eq  = np.cumprod(1.0 + np.clip(w, -0.999, None))
        pk  = np.maximum.accumulate(eq)
        mdd_arr[i] = float((eq / pk - 1.0).min())

    roll_sharpe  = pd.Series(sharpe_arr,  index=sr.index)
    roll_sortino = pd.Series(sortino_arr, index=sr.index)
    roll_mdd     = pd.Series(mdd_arr,     index=sr.index)

    # ── rolling Calmar ────────────────────────────────────────────────────────
    roll_calmar = pd.Series(
        np.where(roll_mdd < -1e-6, roll_cagr / roll_mdd.abs(), np.nan),
        index=sr.index,
    )

    def _worst(series: pd.Series):
        valid = series.dropna()
        if valid.empty:
            return None, None, None
        end_idx = valid.idxmin()
        val     = float(valid.loc[end_idx])
        pos     = sr.index.get_loc(end_idx)
        start   = sr.index[max(0, pos - window + 1)]
        return val, start.date(), end_idx.date()

    result = {}
    for key, series in [
        ("cagr",    roll_cagr),
        ("sharpe",  roll_sharpe),
        ("sortino", roll_sortino),
        ("max_dd",  roll_mdd),
        ("calmar",  roll_calmar),
    ]:
        v, s, e = _worst(series)
        result[key]                = v
        result[f"{key}_start"]     = s
        result[f"{key}_end"]       = e
    result["_roll_cagr"] = roll_cagr
    return result


@st.cache_data(ttl=300, show_spinner=False)
def _compute_worst_window(symbol: str, bars: int, use_btc_filter: bool,
                           bear_alloc_pct: float,
                           td: int, window: int = 365,
                           fee_per_side_pct: float = 0.0) -> dict:
    """Cached entry point — derives sr from a fresh strategy run."""
    cfg    = LeanConfig(use_btc_filter=use_btc_filter, trading_days=td)
    daily  = _load_candles(symbol, bars)
    btc    = _load_btc(bars) if use_btc_filter else None
    result = run_strategy(daily, btc_daily=btc, config=cfg)
    df     = trim_warmup(result.df)
    ret    = df["close"].pct_change().fillna(0.0)
    pos, traded = _held_and_traded(df, df.index, bear_alloc_pct)
    sr = pos * ret
    if fee_per_side_pct > 0:
        sr = sr - traded * (fee_per_side_pct / 100.0)
    return _worst_windows_from_sr(sr, td, window)


def _render_kpi_cards(metrics: dict, trades: list[dict], exposure: float,
                      spx_m: "dict | None" = None,
                      worst_w: "dict | None" = None) -> str:
    strat = metrics["strategy"]
    bh = metrics["bh"]
    closed = [t for t in trades if not t["open"]]
    n = len(closed)
    wins = [t for t in closed if t["pnl_pct"] > 0]
    wr = len(wins) / n * 100 if n else None
    avg_pl = sum(t["pnl_pct"] for t in closed) / n if n else None
    avg_d = sum(t["duration_days"] for t in closed) / n if n else None
    best = max(closed, key=lambda t: t["pnl_pct"])["pnl_pct"] if closed else None
    worst = min(closed, key=lambda t: t["pnl_pct"])["pnl_pct"] if closed else None

    def _delta(sv, bv, is_pct: bool = True, positive_good: bool = True):
        """Returns (text, color) for strategy-vs-B&H delta badge."""
        try:
            if sv is None or bv is None or np.isnan(float(sv)) or np.isnan(float(bv)):
                return "", ""
        except (TypeError, ValueError):
            return "", ""
        d = float(sv) - float(bv)
        if abs(d) < 1e-9:
            return "", ""
        txt = f"{d * 100:+.1f}pp" if is_pct else f"{d:+.2f}"
        good = (d > 0) if positive_good else (d < 0)
        return txt, COL_BULL if good else COL_BEAR

    def _card(label: str, value: str, colour: str,
              bh_val: str = "", bh_col: str = "",
              spx_val: str = "", tip: str = "",
              worst_val: str = "", worst_tip: str = "",
              delta_str: str = "", delta_col: str = "") -> str:
        sub = ""
        if delta_str:
            sub += (
                f'<div style="margin-top:4px;font-size:10px;font-family:monospace">'
                f'<span style="background:{delta_col}22;color:{delta_col};'
                f'padding:1px 6px;border-radius:3px;font-weight:700">'
                f'{delta_str} vs B&H</span></div>'
            )
        if bh_val:
            sub += (
                f'<div style="margin-top:5px;font-size:11px;font-family:monospace">'
                f'<span style="color:{COL_DIM}">B&H </span>'
                f'<span style="color:{bh_col}">{bh_val}</span></div>'
            )
        if spx_val:
            sub += (
                f'<div style="margin-top:2px;font-size:11px;font-family:monospace">'
                f'<span style="color:{COL_SPX}">SPX </span>'
                f'<span style="color:{COL_SPX}">{spx_val}</span></div>'
            )
        if worst_val:
            sub += (
                f'<div style="margin-top:2px;font-size:11px;font-family:monospace;cursor:help"'
                f' title="{worst_tip}">'
                f'<span style="color:{COL_DIM}">Worst yr </span>'
                f'<span style="color:{COL_BEAR}">{worst_val}</span></div>'
            )
        return (
            f'<div style="flex:1;background:{COL_PANEL};border:1px solid {COL_BORDER};'
            f'border-radius:4px;padding:16px 10px;text-align:center;min-width:130px;cursor:help"'
            f' title="{tip}">'
            f'<div style="color:{COL_DIM};font-size:9px;text-transform:uppercase;'
            f'letter-spacing:1.2px;margin-bottom:8px">{label}</div>'
            f'<div style="color:{colour};font-size:24px;font-weight:700;'
            f'font-family:monospace;line-height:1.1">{value}</div>'
            f'{sub}</div>'
        )

    _s  = spx_m  or {}
    _ww = worst_w or {}

    def _wv(key: str, fmt_fn) -> str:
        v = _ww.get(key)
        return fmt_fn(v) if v is not None else ""

    def _wt(key: str) -> str:
        s, e = _ww.get(f"{key}_start"), _ww.get(f"{key}_end")
        return f"Worst 1-year window: {s} — {e}" if s and e else ""

    _dcagr,    _dcagr_c    = _delta(strat["cagr"],    bh["cagr"],    is_pct=True,  positive_good=True)
    _dsharpe,  _dsharpe_c  = _delta(strat["sharpe"],  bh["sharpe"],  is_pct=False, positive_good=True)
    _dsortino, _dsortino_c = _delta(strat["sortino"], bh["sortino"], is_pct=False, positive_good=True)
    _dmdd,     _dmdd_c     = _delta(strat["max_dd"],  bh["max_dd"],  is_pct=True,  positive_good=False)
    _dcalmar,  _dcalmar_c  = _delta(strat["calmar"],  bh["calmar"],  is_pct=False, positive_good=True)

    # Value of 100 units invested at the start of the window (compounded) — strategy vs B&H vs SPX
    _v_strat = float(strat["eq"].iloc[-1]) * 100 if len(strat["eq"]) else 100.0
    _v_bh    = float(bh["eq"].iloc[-1]) * 100 if len(bh["eq"]) else 100.0
    _v_spx   = (float(_s["eq"].iloc[-1]) * 100
                if _s.get("eq") is not None and len(_s["eq"]) else None)
    _v_mult  = (_v_strat / _v_bh) if _v_bh > 1e-9 else None
    _v_delta = (f"{_v_mult:.2f}×", COL_BULL if _v_strat >= _v_bh else COL_BEAR) if _v_mult else ("", "")

    row1 = [
        _card("Vrednost 100", f"{_v_strat:,.0f}", _val_col(strat["cagr"]),
              f"{_v_bh:,.0f}", _val_col(bh["cagr"]),
              f"{_v_spx:,.0f}" if _v_spx else "",
              "Končna vrednost 100 enot, vloženih na začetku obdobja, z reinvestiranjem donosa "
              "(compounding) — za strategijo, v primerjavi z Buy & Hold in S&P 500. Npr. 340 pomeni "
              "da bi 100 enot naraslo na 340. Delta (×) je večkratnik strategije glede na B&H.",
              delta_str=_v_delta[0], delta_col=_v_delta[1]),
        _card("CAGR", _fmt_pct(strat["cagr"]), _val_col(strat["cagr"]),
              _fmt_pct(bh["cagr"]), _val_col(bh["cagr"]),
              _fmt_pct(_s.get("cagr")) if _s else "",
              "Compound Annual Growth Rate",
              worst_val=_wv("cagr", _fmt_pct), worst_tip=_wt("cagr"),
              delta_str=_dcagr, delta_col=_dcagr_c),
        _card("Sharpe", _fmt_ratio(strat["sharpe"]), _val_col(strat["sharpe"]),
              _fmt_ratio(bh["sharpe"]), _val_col(bh["sharpe"]),
              _fmt_ratio(_s.get("sharpe")) if _s else "",
              "Risk-adjusted return (return / volatility)",
              worst_val=_wv("sharpe", _fmt_ratio), worst_tip=_wt("sharpe"),
              delta_str=_dsharpe, delta_col=_dsharpe_c),
        _card("Sortino", _fmt_ratio(strat["sortino"]), _val_col(strat["sortino"]),
              _fmt_ratio(bh["sortino"]), _val_col(bh["sortino"]),
              _fmt_ratio(_s.get("sortino")) if _s else "",
              "Return / downside volatility only",
              worst_val=_wv("sortino", _fmt_ratio), worst_tip=_wt("sortino"),
              delta_str=_dsortino, delta_col=_dsortino_c),
        _card("Max Drawdown", _fmt_pct(strat["max_dd"]),
              _val_col(strat["max_dd"], positive_good=False),
              _fmt_pct(bh["max_dd"]), _val_col(bh["max_dd"], positive_good=False),
              _fmt_pct(_s.get("max_dd")) if _s else "",
              "Largest peak-to-trough equity decline",
              worst_val=_wv("max_dd", _fmt_pct), worst_tip=_wt("max_dd"),
              delta_str=_dmdd, delta_col=_dmdd_c),
        _card("Calmar", _fmt_ratio(strat["calmar"]), _val_col(strat["calmar"]),
              _fmt_ratio(bh["calmar"]), _val_col(bh["calmar"]),
              _fmt_ratio(_s.get("calmar")) if _s else "",
              "CAGR / |Max Drawdown|",
              worst_val=_wv("calmar", _fmt_ratio), worst_tip=_wt("calmar"),
              delta_str=_dcalmar, delta_col=_dcalmar_c),
        _card("Win Rate",
              f"{wr:.0f}%" if wr is not None else "—",
              COL_BULL if (wr or 0) >= 50 else COL_NEUTRAL if (wr or 0) >= 40 else COL_BEAR,
              tip="Winning trades / total trades"),
    ]
    row2 = [
        _card("Trades", str(n) if n else "—", COL_TEXT,
              tip="Completed round-trip trades"),
        _card("Avg P&L",
              f"{avg_pl:+.2f}%" if avg_pl is not None else "—",
              _val_col(avg_pl), tip="Average profit/loss per trade"),
        _card("Avg Duration",
              f"{avg_d:.0f}d" if avg_d is not None else "—", COL_TEXT,
              tip="Average holding period in days"),
        _card("Best / Worst",
              f"{best:+.0f}% / {worst:+.0f}%" if best is not None else "—",
              COL_TEXT, tip="Best and worst single-trade P&amp;L"),
        _card("Exposure", f"{exposure:.0f}%", COL_BLUE,
              tip="Time invested (BULL signal active)"),
    ]

    def _row_html(cards: list[str]) -> str:
        return (f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
                f'{"".join(cards)}</div>')

    return (
        f'<div style="margin:8px 0 14px 0;display:flex;flex-direction:column;gap:10px">'
        f'{_row_html(row1)}{_row_html(row2)}</div>'
    )


def _render_kpi_cards_portfolio(sym_a: str, sym_b: str, w_a: int, w_b: int,
                                 m_a: dict, m_b: dict, m_port: dict,
                                 exp_a: float, exp_b: float,
                                 spx_m: "dict | None" = None,
                                 worst_w_a: "dict | None" = None,
                                 worst_w_b: "dict | None" = None) -> str:
    sa, sb, sp = m_a["strategy"], m_b["strategy"], m_port["strategy"]
    ba, bb, bp = m_a["bh"],      m_b["bh"],      m_port["bh"]

    def _cell(val: str, col: str, bh: str = "", bh_col: str = "",
              spx: str = "", worst: str = "", worst_tip: str = "") -> str:
        sub = ""
        if bh:
            sub += (f'<div style="margin-top:3px;font-size:10px;font-family:monospace">'
                    f'<span style="color:{COL_DIM}">B&amp;H </span>'
                    f'<span style="color:{bh_col}">{bh}</span></div>')
        if spx:
            sub += (f'<div style="margin-top:1px;font-size:10px;font-family:monospace">'
                    f'<span style="color:{COL_SPX}">SPX  </span>'
                    f'<span style="color:{COL_SPX}">{spx}</span></div>')
        if worst:
            sub += (f'<div style="margin-top:1px;font-size:10px;font-family:monospace;cursor:help"'
                    f' title="{worst_tip}">'
                    f'<span style="color:{COL_DIM}">Worst yr </span>'
                    f'<span style="color:{COL_BEAR}">{worst}</span></div>')
        return (f'<td style="padding:12px 16px;border-bottom:1px solid {COL_BORDER};text-align:right">'
                f'<span style="color:{col};font-size:20px;font-weight:700;font-family:monospace">{val}</span>'
                f'{sub}</td>')

    def _lbl(txt: str, tip: str = "") -> str:
        t = f' title="{tip}"' if tip else ""
        return (f'<td style="padding:12px 16px;border-bottom:1px solid {COL_BORDER};'
                f'color:{COL_DIM};font-size:10px;text-transform:uppercase;letter-spacing:1px;'
                f'white-space:nowrap;border-right:2px solid {COL_BORDER};cursor:help"{t}>{txt}</td>')

    def _get_worst(ww, key, fmt_fn):
        if not ww:
            return "", ""
        v = ww.get(key)
        s, e = ww.get(f"{key}_start"), ww.get(f"{key}_end")
        val_str = fmt_fn(v) if v is not None else ""
        tip     = f"Worst 365-day window: {s} — {e}" if s and e else ""
        return val_str, tip

    _METRIC_SPEC = [
        ("CAGR",    "Compound Annual Growth Rate",    "cagr",    True,  "pct"),
        ("Sharpe",  "Return / volatility",            "sharpe",  True,  "ratio"),
        ("Sortino", "Return / downside volatility",   "sortino", True,  "ratio"),
        ("Max DD",  "Largest peak-to-trough decline", "max_dd",  False, "pct"),
        ("Calmar",  "CAGR / |Max DD|",               "calmar",  True,  "ratio"),
    ]
    _WORST_KEYS = {"cagr", "sharpe", "sortino", "max_dd", "calmar"}
    rows = []
    for lbl, tip, key, pos_good, ftype in _METRIC_SPEC:
        fmt = (lambda v, _f=ftype: _fmt_pct(v) if _f == "pct" else _fmt_ratio(v))
        spx_val = fmt(spx_m[key]) if spx_m else ""
        if key in _WORST_KEYS:
            wa_str, wa_tip = _get_worst(worst_w_a, key, fmt)
            wb_str, wb_tip = _get_worst(worst_w_b, key, fmt)
        else:
            wa_str = wb_str = wa_tip = wb_tip = ""
        rows.append(
            f'<tr>'
            f'{_lbl(lbl, tip)}'
            f'{_cell(fmt(sa[key]), _val_col(sa[key], pos_good), fmt(ba[key]), _val_col(ba[key], pos_good), spx_val, wa_str, wa_tip)}'
            f'{_cell(fmt(sb[key]), _val_col(sb[key], pos_good), fmt(bb[key]), _val_col(bb[key], pos_good), spx_val, wb_str, wb_tip)}'
            f'{_cell(fmt(sp[key]), _val_col(sp[key], pos_good), fmt(bp[key]), _val_col(bp[key], pos_good), spx_val)}'
            f'</tr>'
        )

    exp_port = (w_a * exp_a + w_b * exp_b) / 100
    rows.append(
        f'<tr>'
        f'{_lbl("Exposure", "% time invested")}'
        f'{_cell(f"{exp_a:.0f}%", COL_BLUE)}'
        f'{_cell(f"{exp_b:.0f}%", COL_BLUE)}'
        f'{_cell(f"{exp_port:.0f}%", COL_BLUE)}'
        f'</tr>'
    )

    def _hdr(sym: str, weight: str, col: str) -> str:
        return (f'<th style="padding:10px 16px;background:{COL_PANEL};'
                f'border-bottom:2px solid {COL_BORDER};text-align:right;font-weight:normal">'
                f'<span style="color:{col};font-size:13px;font-weight:700;font-family:monospace">{sym}</span>'
                f'<span style="color:{COL_DIM};font-size:11px;margin-left:6px">{weight}</span>'
                f'</th>')

    header = (
        f'<tr>'
        f'<th style="padding:10px 16px;background:{COL_PANEL};'
        f'border-bottom:2px solid {COL_BORDER};border-right:2px solid {COL_BORDER}"></th>'
        f'{_hdr(f"{sym_a}/USD", f"{w_a}%", COL_BULL)}'
        f'{_hdr(f"{sym_b}/USD", f"{w_b}%", COL_BLUE)}'
        f'{_hdr("Portfolio", "", COL_NEUTRAL)}'
        f'</tr>'
    )
    return (
        f'<div style="margin:8px 0 14px 0;background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-radius:4px;overflow:hidden">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead>{header}</thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table></div>'
    )


# ── shared chart style ────────────────────────────────────────────────────────

def _chart_layout(fig: go.Figure, height: int) -> None:
    fig.update_layout(
        template=COL_TEMPLATE,
        height=height,
        margin=dict(l=0, r=70, t=42, b=8),
        paper_bgcolor=COL_BG, plot_bgcolor=COL_BG,
        font=dict(color=COL_TEXT, family="-apple-system,system-ui,sans-serif", size=11),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.005, x=0,
            bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=COL_DIM),
            itemsizing="constant",
        ),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        hoverlabel=dict(bgcolor=COL_PANEL, bordercolor=COL_BORDER,
                        font=dict(color=COL_TEXT, size=11)),
    )
    fig.update_xaxes(
        gridcolor=COL_GRID, zerolinecolor=COL_GRID,
        tickfont=dict(color=COL_TEXT, size=14),
        showspikes=True, spikecolor=COL_DIM, spikethickness=1, spikedash="dot",
    )


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _row(label: str, value: str, colour: str = "", tip: str = "") -> str:
    vc    = colour or COL_TEXT
    title = f' title="{tip}"' if tip else ""
    return (
        f'<div style="display:flex;justify-content:space-between;'
        f'padding:7px 0;border-bottom:1px solid {COL_BORDER}"{title}>'
        f'<span style="color:{COL_DIM};font-size:11px">{label}</span>'
        f'<span style="color:{vc};font-size:12px;font-weight:500;'
        f'font-family:monospace">{value}</span>'
        f'</div>'
    )


def _gate_row(label: str, passed: bool, now: str = "", need: str = "") -> str:
    """One gate. `now` and `need` sit under the label and are always visible —
    the hover text carries the formula, but the two numbers that decide the gate
    should not require a hover to read."""
    icon = "PASS" if passed else "FAIL"
    col  = COL_BULL if passed else COL_BEAR
    bg   = f"{COL_BULL}11" if passed else f"{COL_BEAR}11"
    detail = ""
    if now or need:
        parts = []
        if now:
            parts.append(f'<span style="color:{COL_TEXT}">{now}</span>')
        if need:
            parts.append(f'<span style="color:{COL_DIM}">needs {need}</span>')
        detail = (
            f'<div style="font-family:monospace;font-size:10px;margin-top:3px;'
            f'line-height:1.35">{"  ·  ".join(parts)}</div>'
        )
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'gap:10px;padding:8px 12px;border-bottom:1px solid {COL_BORDER};background:{bg}">'
        f'<div style="min-width:0"><div style="color:{COL_TEXT};font-size:11px">{label}</div>'
        f'{detail}</div>'
        f'<span style="background:{col}22;color:{col};padding:2px 10px;'
        f'border-radius:3px;font-size:10px;font-weight:700;flex:none;'
        f'letter-spacing:0.5px;font-family:monospace">{icon}</span>'
        f'</div>'
    )


def _num(v, dec: int = 0, suffix: str = "") -> str:
    """Format a possibly-NaN scalar for the gate rows."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(f):
        return "n/a"
    return f"{f:,.{dec}f}{suffix}"


def _coloured_line(fig, xs, ys, flags, colours, name: str, group: str,
                   hover: str, width: float = 1.6, dash=None, row: int = 1) -> None:
    """A line whose colour switches with `flags`, hovering exactly once per date.

    The segments have to overlap by one point or the line shows a gap at every
    colour change. That overlap used to be the whole story, and it meant the bar
    where the colour flips belonged to two traces — so `hovermode="x unified"`
    listed the trackline twice on those dates, with the same number repeated.

    So the coloured segments no longer answer the hover at all. One transparent
    trace spanning the whole series owns it, which also keeps the reading
    identical on every date rather than depending on which segment you are over.
    """
    n = len(ys)
    start, first = 0, True
    for i in range(1, n + 1):
        if i == n or flags[i] != flags[start]:
            end = i + (0 if i == n else 1)      # overlap by one: no visual gap
            fig.add_trace(go.Scatter(
                x=xs[start:end], y=ys[start:end], mode="lines",
                line=dict(color=colours[int(bool(flags[start]))], width=width,
                          dash=dash),
                name=name, showlegend=first, legendgroup=group,
                hoverinfo="skip",
            ), row=row, col=1)
            first = False
            start = i
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines",
        line=dict(color="rgba(0,0,0,0)", width=max(width, 6)),
        name=name, legendgroup=group, showlegend=False,
        hovertemplate=hover,
    ), row=row, col=1)


def _section_label(txt: str) -> str:
    return (
        f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
        f'letter-spacing:1.5px;margin:18px 0 8px 0">{txt}</div>'
    )


# ── status bar ────────────────────────────────────────────────────────────────

def _status_bar(s: dict, symbol: str, cfg: LeanConfig) -> str:
    sig_col  = COL_BULL if s["signal"] == "BULL" else COL_BEAR
    reg_col  = {"BULL": COL_BULL, "HEDGED": COL_NEUTRAL, "BEAR": COL_BEAR}[s["regime"]]
    dist_txt = f'{s["dist_pct"]:+.2f}%'
    dist_col = COL_BULL if s["dist_pct"] > 0 else COL_BEAR
    rsi_val  = s["rsi"]
    rsi_txt  = f"{rsi_val:.1f}" if not pd.isna(rsi_val) else "—"
    rsi_col  = COL_BEAR if rsi_val > 70 else COL_BULL if rsi_val < 35 else COL_DIM
    alloc_txt = f'{s["target_alloc"]:.0f}%'
    vol_txt  = f'{s["annual_vol"]:.1f}%'
    close_txt = f'${s["close"]:,.2f}'
    date_txt = f'{s["time"]:%Y-%m-%d}'

    def chip(txt: str, col: str, bold: bool = False) -> str:
        fw = "700" if bold else "500"
        return (f'<span style="color:{col};font-size:13px;font-weight:{fw};'
                f'font-family:monospace">{txt}</span>')

    def lbl(txt: str) -> str:
        return (f'<span style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
                f'letter-spacing:0.4px;margin-right:4px">{txt}</span>')

    def item(label_txt: str, chip_html: str, tooltip: str) -> str:
        return (f'{sep}<span title="{tooltip}" style="cursor:help">'
                f'{lbl(label_txt)}{chip_html}</span>')

    sep = (f'<span style="color:{COL_BORDER};padding:0 14px;'
           f'font-size:15px;vertical-align:middle">│</span>')

    warnings = ""
    if s.get("blowoff"):
        warnings += f'<span style="color:{COL_BEAR};font-weight:700;font-size:11px;margin-left:14px">⚠ BLOW-OFF</span>'

    btc_part = ""
    if cfg.use_btc_filter:
        arrow   = "▲" if s["btc_bull"] else "▼"
        btc_col = COL_BULL if s["btc_bull"] else COL_BEAR
        btc_part = item("BTC", chip("BTC " + arrow, btc_col),
                        "BTC cross-asset filter. ▲ = BTC is in a bull regime (entries allowed). "
                        "▼ = BTC bear regime (entries blocked).")

    content = (
        f'<span title="Asset being analyzed. Price is the last close in the selected window."'
        f' style="color:{COL_TEXT};font-size:15px;font-weight:700;margin-right:10px;cursor:help">{symbol}/USD</span>'
        f'<span title="Last daily close price in USD."'
        f' style="color:{COL_TEXT};font-size:15px;font-family:monospace;margin-right:2px;cursor:help">{close_txt}</span>'
        + item("Signal", chip(s["signal"], sig_col, bold=True),
               "Current trading signal. BULL = strategy is 100% long. BEAR = 0% (cash). "
               "Flips only when all entry conditions are met simultaneously (BULL) "
               "or any exit condition triggers (BEAR).")
        + item("Regime", chip(s["regime"], reg_col),
               "Display regime from the longer-term state machine. "
               "BULL = confirmed uptrend. BEAR = confirmed downtrend. "
               "HEDGED = transitional period between states.")
        + item("vs TL", chip(dist_txt, dist_col),
               "Distance of the current close price from the adaptive trackline, in %. "
               "Positive (+) = above the trackline (safe zone). "
               "Negative (−) = below the trackline — primary exit trigger if signal was BULL.")
        + item("RSI", chip(rsi_txt, rsi_col),
               "Relative Strength Index over 14 periods. "
               "Above 70 = overbought (red). Below 35 = oversold (green). "
               "Used as a secondary indicator — RSI alone does not trigger entries or exits.")
        + item("Alloc", chip(alloc_txt, COL_BLUE),
               "Target allocation. Binary: 100% = fully long (BULL signal), 0% = cash (BEAR). "
               "No partial positions — the strategy is always either fully in or fully out.")
        + item("Vol", chip(vol_txt, COL_DIM),
               "Annualised historical volatility (30-day rolling std of daily returns × √365). "
               "HIGH vol regime can suppress entries. LOW vol favours continuation.")
        + btc_part + warnings
    )
    ts = f'<span style="color:{COL_VERY_DIM};font-size:10px;font-family:monospace;margin-left:auto">{date_txt}</span>'

    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-left:3px solid {sig_col};border-radius:3px;'
        f'padding:10px 16px;margin-bottom:8px;'
        f'display:flex;align-items:center;flex-wrap:wrap;gap:2px">'
        f'{content}{ts}</div>'
    )


# ── price chart ───────────────────────────────────────────────────────────────

def _build_price_chart(df: pd.DataFrame, symbol: str,
                       bear_alloc_pct: float = DEFAULT_CONFIG.bear_alloc_pct) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.80, 0.20], vertical_spacing=0.03,
    )

    ds  = df["display_state"]
    grp = (ds != ds.shift(1)).cumsum()
    _rgb = {S_BULL: (8, 153, 129), S_NEUTRAL: (255, 183, 77), S_BEAR: (242, 54, 69)}
    for _, seg in df.groupby(grp):
        r, g, b = _rgb[int(seg["display_state"].iloc[0])]
        fig.add_vrect(x0=seg.index[0], x1=seg.index[-1],
                      fillcolor=f"rgba({r},{g},{b},0.04)",
                      line_width=0, layer="below", row=1, col=1)

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color=COL_BULL, decreasing_line_color=COL_BEAR,
        increasing_fillcolor=COL_BULL, decreasing_fillcolor=COL_BEAR,
        line=dict(width=1), name="Price", showlegend=False,
    ), row=1, col=1)

    # Trackline coloured by 1-bar slope — matches Pine `plot(trackline,
    # color=trackRising ? green : red)` (diversitas_lean.pine:173). The status
    # table separately uses the 10-bar `track_rising_window`, as Pine does at :226.
    xs = df.index
    _coloured_line(
        fig, xs, df["trackline"].to_numpy(),
        df["track_rising"].fillna(False).to_numpy(),
        (COL_BEAR, COL_BULL), "Trackline", "tl", "TL %{y:,.2f}<extra></extra>",
        width=1.6,
    )

    # 50 MA (trend filter)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["ma_med"], mode="lines",
        line=dict(color=COL_MA50, width=1.2),
        name="50 MA (trend)", hovertemplate="50 MA %{y:,.2f}<extra></extra>",
    ), row=1, col=1)

    # 200 MA coloured by direction — reuse the column the strategy already computed
    # (it honours cfg.ma_slope; the previous inline expression hard-coded 5).
    _coloured_line(
        fig, xs, df["ma_long"].to_numpy(),
        df["ma_long_rising"].fillna(False).to_numpy(),
        (COL_BEAR, COL_MA200), "200 MA (regime)", "ma200",
        "200 MA %{y:,.2f}<extra></extra>", width=1.2, dash="dot",
    )

    # Condition dots — hollow
    green = df[df["green_dot"]]
    red   = df[df["red_dot"]]
    _dot  = dict(color="rgba(0,0,0,0)", size=5, symbol="circle")
    if len(green):
        fig.add_trace(go.Scatter(
            x=green.index, y=green["low"] * 0.985, mode="markers",
            marker={**_dot, "line": dict(color=COL_BULL, width=1.5)},
            name="Bull dot", showlegend=False,
            hovertemplate="BULL %{x|%Y-%m-%d}<extra></extra>",
        ), row=1, col=1)
    if len(red):
        fig.add_trace(go.Scatter(
            x=red.index, y=red["high"] * 1.015, mode="markers",
            marker={**_dot, "line": dict(color=COL_BEAR, width=1.5)},
            name="Bear dot", showlegend=False,
            hovertemplate="BEAR %{x|%Y-%m-%d}<extra></extra>",
        ), row=1, col=1)

    # Signal arrows
    changes = df[df["signal_changed"]]
    bulls   = changes[changes["signal_state"] == S_BULL]
    bears   = changes[changes["signal_state"] == S_BEAR]
    if len(bulls):
        fig.add_trace(go.Scatter(
            x=bulls.index, y=bulls["low"] * 0.940,
            mode="markers+text",
            marker=dict(color=COL_BULL, size=22, symbol="triangle-up",
                        line=dict(color="white", width=2)),
            text=["BUY"] * len(bulls), textposition="bottom center",
            textfont=dict(color=COL_BULL, size=11, family="monospace"),
            name="BULL signal", showlegend=False,
            hovertemplate="▲ BUY  %{x|%Y-%m-%d}  $%{customdata:,.0f}<extra></extra>",
            customdata=bulls["close"],
        ), row=1, col=1)
    if len(bears):
        fig.add_trace(go.Scatter(
            x=bears.index, y=bears["high"] * 1.060,
            mode="markers+text",
            marker=dict(color=COL_BEAR, size=22, symbol="triangle-down",
                        line=dict(color="white", width=2)),
            text=["SELL"] * len(bears), textposition="top center",
            textfont=dict(color=COL_BEAR, size=11, family="monospace"),
            name="BEAR signal", showlegend=False,
            hovertemplate="▼ SELL  %{x|%Y-%m-%d}  $%{customdata:,.0f}<extra></extra>",
            customdata=bears["close"],
        ), row=1, col=1)

    # Allocation subplot (step line)
    # The REAL held share, bar by bar, not the instruction. While flat the
    # holding is a fixed number of coins, so its share slides with the price.
    alloc = (position(trim_warmup(df),
                      LeanConfig(bear_alloc_pct=bear_alloc_pct))
             .reindex(df.index).to_numpy() * 100.0)
    fig.add_trace(go.Scatter(
        x=df.index, y=alloc, mode="lines",
        line=dict(color=COL_BLUE, width=1.8),
        fill="tozeroy", fillcolor="rgba(41,98,255,0.12)",
        name="Allocation %", hovertemplate="Alloc %{y:.2f}%<extra></extra>",
    ), row=2, col=1)

    _chart_layout(fig, height=820)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), side="right", row=1, col=1)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), side="right",
                     title_text="Alloc %", title_font=dict(color=COL_DIM, size=10),
                     range=[0, 110], row=2, col=1)
    return fig


def _build_spx_chart(spx_eq: pd.Series) -> go.Figure:
    """Standalone S&P 500 B&H equity curve + drawdown."""
    dd = (spx_eq / spx_eq.cummax() - 1) * 100
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.68, 0.32], vertical_spacing=0.03,
    )
    fig.add_trace(go.Scatter(
        x=spx_eq.index, y=spx_eq,
        mode="lines", line=dict(color=COL_SPX, width=2),
        name="S&P 500 B&H",
        fill="tozeroy", fillcolor="rgba(245,158,11,0.08)",
        hovertemplate="SPX %{y:.2f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd,
        mode="lines", line=dict(color=COL_BEAR, width=1),
        name="Drawdown", fill="tozeroy", fillcolor="rgba(242,54,69,0.15)",
        hovertemplate="DD %{y:.1f}%<extra></extra>",
    ), row=2, col=1)
    _chart_layout(fig, height=480)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), side="right", row=1, col=1)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), side="right",
                     title_text="DD %", title_font=dict(color=COL_DIM, size=10),
                     row=2, col=1)
    return fig


def _render_spx_bar(spx_m: dict) -> str:
    """One-line metrics summary bar for the S&P 500 tab."""
    items = [
        ("CAGR",    _fmt_pct(spx_m["cagr"])),
        ("Sharpe",  _fmt_ratio(spx_m["sharpe"])),
        ("Sortino", _fmt_ratio(spx_m["sortino"])),
        ("Max DD",  _fmt_pct(spx_m["max_dd"])),
        ("Calmar",  _fmt_ratio(spx_m["calmar"])),
    ]
    chips = "".join(
        f'<span style="margin-right:20px;font-family:monospace">'
        f'<span style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
        f'letter-spacing:1px">{lbl} </span>'
        f'<span style="color:{COL_SPX};font-size:14px;font-weight:700">{val}</span>'
        f'</span>'
        for lbl, val in items
    )
    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-left:3px solid {COL_SPX};border-radius:3px;'
        f'padding:10px 16px;margin-bottom:8px;display:flex;align-items:center;flex-wrap:wrap;gap:4px">'
        f'<span style="color:{COL_SPX};font-size:15px;font-weight:700;'
        f'margin-right:20px;font-family:monospace">S&amp;P 500</span>'
        f'{chips}'
        f'<span style="color:{COL_VERY_DIM};font-size:10px;margin-left:auto;font-family:monospace">'
        f'Buy &amp; Hold · no trading · 100% invested</span>'
        f'</div>'
    )


def _build_equity_chart(metrics: dict, symbol: str = "",
                         spx_eq: "pd.Series | None" = None) -> go.Figure:
    strat = metrics["strategy"]
    bh    = metrics["bh"]
    s_eq  = strat["eq"] * 100
    b_eq  = bh["eq"]   * 100
    s_dd  = strat["dd"] * 100
    b_dd  = bh["dd"]   * 100
    sym_label = f" · {symbol}" if symbol else ""

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.65, 0.35], vertical_spacing=0.03,
    )
    fig.add_trace(go.Scatter(
        x=b_eq.index, y=b_eq, mode="lines",
        line=dict(color=COL_DIM, width=1.5),
        name=f"Buy & Hold{sym_label}", hovertemplate="B&H %{y:.1f}<extra></extra>",
    ), row=1, col=1)
    if spx_eq is not None and not spx_eq.empty:
        fig.add_trace(go.Scatter(
            x=spx_eq.index, y=spx_eq, mode="lines",
            line=dict(color=COL_SPX, width=1.5, dash="dot"),
            name="S&P 500 B&H", hovertemplate="SPX %{y:.1f}<extra></extra>",
        ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=s_eq.index, y=s_eq, mode="lines",
        line=dict(color=COL_BULL, width=2),
        name=f"Strategy{sym_label}", hovertemplate="Strategy %{y:.1f}<extra></extra>",
    ), row=1, col=1)
    # Drawdown subplot — both strategy (filled) and B&H (line only) for comparison
    fig.add_trace(go.Scatter(
        x=b_dd.index, y=b_dd, mode="lines",
        line=dict(color=COL_DIM, width=1, dash="dot"),
        name="B&H DD", hovertemplate="B&H DD %{y:.1f}%<extra></extra>",
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=s_dd.index, y=s_dd, mode="lines",
        fill="tozeroy", line=dict(color=COL_BEAR, width=1),
        fillcolor="rgba(242,54,69,0.18)",
        name="Strategy DD", hovertemplate="Strategy DD %{y:.1f}%<extra></extra>",
    ), row=2, col=1)

    _chart_layout(fig, height=420)
    fig.update_layout(margin=dict(t=56), title=dict(
        text=f'<span style="color:{COL_TEXT};font-size:12px;text-transform:uppercase;letter-spacing:1px">Equity curve{sym_label} · strategy vs buy &amp; hold (indexed to 100)</span>',
        x=0.01, y=0.98, yanchor="top"))
    fig.update_xaxes(dtick="M3", tickformat="%b\n%Y")
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     side="right", title_text="Equity",
                     title_font=dict(color=COL_DIM, size=10), row=1, col=1)
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     side="right", title_text="DD %",
                     title_font=dict(color=COL_BEAR, size=10), row=2, col=1)
    return fig


def _build_equity_chart_portfolio(sym_a: str, sym_b: str,
                                   m_a: dict, m_b: dict, m_port: dict,
                                   spx_eq: "pd.Series | None" = None) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.65, 0.35], vertical_spacing=0.03)

    bh_port = m_port["bh"]["eq"] * 100
    eq_a    = m_a["strategy"]["eq"] * 100
    eq_b    = m_b["strategy"]["eq"] * 100
    eq_port = m_port["strategy"]["eq"] * 100
    dd_port = m_port["strategy"]["dd"] * 100

    fig.add_trace(go.Scatter(
        x=bh_port.index, y=bh_port, name="B&H Portfolio",
        line=dict(color=COL_VERY_DIM, width=1.2, dash="dot"),
        hovertemplate="B&H %{y:.1f}<extra></extra>",
    ), row=1, col=1)
    if spx_eq is not None and not spx_eq.empty:
        fig.add_trace(go.Scatter(
            x=spx_eq.index, y=spx_eq, name="S&P 500 B&H",
            line=dict(color=COL_SPX, width=1.5, dash="dot"),
            hovertemplate="SPX %{y:.1f}<extra></extra>",
        ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=eq_a.index, y=eq_a, name=sym_a,
        line=dict(color=COL_BULL, width=1.5),
        hovertemplate=f"{sym_a} %{{y:.1f}}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=eq_b.index, y=eq_b, name=sym_b,
        line=dict(color=COL_BLUE, width=1.5),
        hovertemplate=f"{sym_b} %{{y:.1f}}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=eq_port.index, y=eq_port, name="Portfolio",
        line=dict(color=COL_NEUTRAL, width=2.5),
        hovertemplate="Portfolio %{y:.1f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dd_port.index, y=dd_port, fill="tozeroy",
        line=dict(color=COL_BEAR, width=1),
        fillcolor="rgba(242,54,69,0.18)",
        name="Portfolio DD",
        hovertemplate="DD %{y:.1f}%<extra></extra>",
    ), row=2, col=1)

    _chart_layout(fig, height=420)
    fig.update_layout(margin=dict(t=56), title=dict(
        text=(f'<span style="color:{COL_TEXT};font-size:12px;text-transform:uppercase;'
              f'letter-spacing:1px">Portfolio equity · {sym_a} + {sym_b} vs buy &amp; hold'
              f' (indexed to 100)</span>'),
        x=0.01, y=0.98, yanchor="top"))
    fig.update_xaxes(dtick="M3", tickformat="%b\n%Y")
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     side="right", title_text="Equity",
                     title_font=dict(color=COL_DIM, size=10), row=1, col=1)
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     side="right", title_text="DD %",
                     title_font=dict(color=COL_BEAR, size=10), row=2, col=1)
    return fig


# ── analytics charts ──────────────────────────────────────────────────────────

def _build_monthly_heatmap(df: pd.DataFrame, bear_alloc_pct: float = DEFAULT_CONFIG.bear_alloc_pct,
                            port_ret: "pd.Series | None" = None,
                            title: str = "Monthly returns · strategy (%)") -> go.Figure:
    if port_ret is not None:
        strat_ret = port_ret
    else:
        ret = df["close"].pct_change().fillna(0.0)
        pos, _ = _held_and_traded(df, df.index, bear_alloc_pct)
        strat_ret = pd.Series(ret.values * pos.to_numpy(), index=ret.index)
    monthly = strat_ret.resample("ME").apply(lambda x: (1 + x).prod() - 1) * 100
    years = sorted(monthly.index.year.unique())
    mlabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    z, txt = [], []
    for y in years:
        rz, rt = [], []
        for m in range(1, 13):
            vals = monthly[(monthly.index.year == y) & (monthly.index.month == m)]
            if len(vals):
                v = float(vals.iloc[0])
                rz.append(v); rt.append(f"{v:+.1f}%")
            else:
                rz.append(None); rt.append("")
        z.append(rz); txt.append(rt)
    flat = [v for row in z for v in row if v is not None]
    zmax = max(abs(v) for v in flat) if flat else 10
    fig = go.Figure(data=go.Heatmap(
        z=z, x=mlabels, y=[str(y) for y in years],
        text=txt, texttemplate="%{text}",
        textfont=dict(size=10, color=COL_TEXT),
        colorscale=[[0, COL_BEAR], [0.5, COL_BG], [1, COL_BULL]],
        zmin=-zmax, zmax=zmax, showscale=False,
        hovertemplate="%{y} %{x}: %{text}<extra></extra>",
    ))
    _chart_layout(fig, height=max(200, len(years) * 34 + 80))
    fig.update_layout(
        margin=dict(t=56),
        title=dict(
            text=f'<span style="color:{COL_TEXT};font-size:12px;text-transform:uppercase;'
                 f'letter-spacing:1px">{title}</span>',
            x=0.01, y=0.98, yanchor="top"),
        yaxis=dict(autorange="reversed"),
    )
    fig.update_xaxes(side="top", tickfont=dict(color=COL_DIM, size=9))
    fig.update_yaxes(tickfont=dict(color=COL_DIM, size=10))
    return fig


def _build_signal_timeline(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    sig = df["signal_state"]
    grp = (sig != sig.shift(1)).cumsum()
    shown: set = set()
    for _, seg in df.groupby(grp):
        state = int(seg["signal_state"].iloc[0])
        col = COL_BULL if state == S_BULL else COL_BEAR
        label = "BULL" if state == S_BULL else "BEAR"
        fig.add_trace(go.Scatter(
            x=[seg.index[0], seg.index[-1]], y=[1, 1],
            mode="lines", line=dict(color=col, width=28),
            name=label, showlegend=(state not in shown),
            legendgroup=label,
            hovertemplate=f"{label}  %{{x|%Y-%m-%d}}<extra></extra>",
        ))
        shown.add(state)
    _chart_layout(fig, height=130)
    fig.update_yaxes(visible=False, range=[0.5, 1.5])
    fig.update_xaxes(dtick="M3", tickformat="%b\n%Y", tickfont=dict(color=COL_TEXT, size=12))
    fig.update_layout(margin=dict(l=0, r=70, t=10, b=30), showlegend=False)
    return fig


def _build_signal_timeline_dual(df_a: pd.DataFrame, df_b: pd.DataFrame,
                                  sym_a: str, sym_b: str) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.5, 0.5], vertical_spacing=0.08)

    def _add_row(df: pd.DataFrame, row: int) -> None:
        sig = df["signal_state"]
        grp = (sig != sig.shift(1)).cumsum()
        for _, seg in df.groupby(grp):
            state = int(seg["signal_state"].iloc[0])
            col   = COL_BULL if state == S_BULL else COL_BEAR
            label = "BULL" if state == S_BULL else "BEAR"
            fig.add_trace(go.Scatter(
                x=[seg.index[0], seg.index[-1]], y=[1, 1],
                mode="lines", line=dict(color=col, width=22),
                name=label, showlegend=False,
                hovertemplate=f"{label}  %{{x|%Y-%m-%d}}<extra></extra>",
            ), row=row, col=1)

    _add_row(df_a, 1)
    _add_row(df_b, 2)

    _chart_layout(fig, height=180)
    fig.update_yaxes(visible=False, range=[0.5, 1.5])
    fig.update_xaxes(dtick="M3", tickformat="%b\n%Y",
                     tickfont=dict(color=COL_TEXT, size=12))
    fig.update_layout(margin=dict(l=0, r=70, t=10, b=30), showlegend=False)
    for sym, yref in [(sym_a, "y"), (sym_b, "y2")]:
        fig.add_annotation(
            xref="paper", yref=yref, x=0.0, y=1.35,
            text=f"<b>{sym}</b>",
            showarrow=False, font=dict(color=COL_DIM, size=10),
            xanchor="left",
        )
    return fig


def _build_rolling_sharpe(df: pd.DataFrame, bear_alloc_pct: float = DEFAULT_CONFIG.bear_alloc_pct,
                           port_ret: "pd.Series | None" = None,
                           title: str = "Rolling 90-day Sharpe ratio",
                           td: int = TRADING_DAYS) -> go.Figure:
    if port_ret is not None:
        strat_ret = port_ret
    else:
        ret = df["close"].pct_change().fillna(0.0)
        pos, _ = _held_and_traded(df, df.index, bear_alloc_pct)
        strat_ret = pd.Series(ret.values * pos.to_numpy(), index=ret.index)
    bh_ret = df["close"].pct_change().fillna(0.0)
    window = 90

    def _roll_sharpe(sr):
        rm = sr.rolling(window, min_periods=window).mean() * td
        rs = sr.rolling(window, min_periods=window).std() * np.sqrt(td)
        return (rm / rs).replace([np.inf, -np.inf], np.nan)

    sharpe    = _roll_sharpe(strat_ret)
    bh_sharpe = _roll_sharpe(bh_ret)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=bh_sharpe.index, y=bh_sharpe, mode="lines",
        line=dict(color=COL_DIM, width=1.2, dash="dot"),
        name="B&H 90d Sharpe",
        hovertemplate="B&H Sharpe %{y:.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=sharpe.index, y=sharpe, mode="lines",
        line=dict(color=COL_BLUE, width=1.5),
        fill="tozeroy", fillcolor="rgba(41,98,255,0.08)",
        name="Strategy 90d Sharpe",
        hovertemplate="Strategy Sharpe %{y:.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=COL_DIM, line_width=0.5)
    fig.add_hline(y=1, line_dash="dot", line_color=COL_BULL, line_width=0.5)
    _chart_layout(fig, height=280)
    fig.update_layout(margin=dict(t=56), title=dict(
        text=f'<span style="color:{COL_TEXT};font-size:12px;text-transform:uppercase;'
             f'letter-spacing:1px">{title}</span>',
        x=0.01, y=0.98, yanchor="top"))
    fig.update_xaxes(dtick="M3", tickformat="%b\n%Y")
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10), side="right")
    return fig


def _build_stress_test_chart(roll_cagr: pd.Series,
                              worst_start, worst_end,
                              symbol: str) -> go.Figure:
    """Rolling 1-year CAGR line with the worst window highlighted."""
    rc_pct = roll_cagr * 100

    fig = go.Figure()

    # Split into positive / negative fill
    pos = rc_pct.clip(lower=0)
    neg = rc_pct.clip(upper=0)
    fig.add_trace(go.Scatter(
        x=rc_pct.index, y=pos, mode="lines",
        line=dict(color=COL_BULL, width=0), showlegend=False,
        fill="tozeroy", fillcolor="rgba(8,153,129,0.12)",
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=rc_pct.index, y=neg, mode="lines",
        line=dict(color=COL_BEAR, width=0), showlegend=False,
        fill="tozeroy", fillcolor="rgba(242,54,69,0.12)",
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=rc_pct.index, y=rc_pct,
        mode="lines", line=dict(color=COL_TEXT, width=1.6),
        name="Rolling 365d CAGR",
        hovertemplate="CAGR %{y:.1f}%<extra></extra>",
    ))

    if worst_start and worst_end:
        fig.add_vrect(
            x0=pd.Timestamp(worst_start), x1=pd.Timestamp(worst_end),
            fillcolor="rgba(242,54,69,0.10)", line_width=1,
            line_color=COL_BEAR, line_dash="dot",
            annotation_text=f"Worst · {worst_start} — {worst_end}",
            annotation_position="top left",
            annotation_font=dict(color=COL_BEAR, size=10),
        )

    fig.add_hline(y=0, line_color=COL_DIM, line_width=1, line_dash="dot")

    _chart_layout(fig, height=300)
    fig.update_layout(
        title=dict(
            text=f'<span style="color:{COL_TEXT};font-size:12px;text-transform:uppercase;'
                 f'letter-spacing:1px">Rolling 1-year CAGR · {symbol}</span>',
            x=0.01, y=0.98, yanchor="top",
        ),
        margin=dict(t=56),
    )
    fig.update_yaxes(gridcolor=COL_GRID, tickformat=".0f", ticksuffix="%",
                     side="right", tickfont=dict(color=COL_DIM, size=10))
    return fig


def _render_stress_test_table(worst_w: dict, symbol: str) -> str:
    """HTML table: worst 1-year value + period for each metric."""
    if not worst_w:
        return ""

    _METRIC_SPEC = [
        ("CAGR",    "cagr",    "pct",   True,  "Compound Annual Growth Rate"),
        ("Sharpe",  "sharpe",  "ratio", True,  "Return / volatility"),
        ("Sortino", "sortino", "ratio", True,  "Return / downside volatility"),
        ("Max DD",  "max_dd",  "pct",   False, "Largest peak-to-trough decline"),
        ("Calmar",  "calmar",  "ratio", True,  "CAGR / |Max DD|"),
    ]

    def _fmt(v, ftype):
        if v is None:
            return "—"
        return _fmt_pct(v) if ftype == "pct" else _fmt_ratio(v)

    th = (f'<th style="padding:10px 14px;background:{COL_PANEL};'
          f'border-bottom:2px solid {COL_BORDER};text-align:right;'
          f'font-weight:normal;color:{COL_DIM};font-size:10px;'
          f'text-transform:uppercase;letter-spacing:1px">')

    header = (
        f'<tr>'
        f'<th style="padding:10px 14px;background:{COL_PANEL};'
        f'border-bottom:2px solid {COL_BORDER};border-right:2px solid {COL_BORDER}"></th>'
        f'{th}Worst value</th>'
        f'{th}Window start</th>'
        f'{th}Window end</th>'
        f'{th}Length</th>'
        f'</tr>'
    )

    rows = []
    for lbl, key, ftype, pos_good, tip in _METRIC_SPEC:
        v  = worst_w.get(key)
        s  = worst_w.get(f"{key}_start")
        e  = worst_w.get(f"{key}_end")
        vstr = _fmt(v, ftype)
        vcol = _val_col(v, pos_good) if v is not None else COL_DIM
        length = f"{(pd.Timestamp(e) - pd.Timestamp(s)).days}d" if s and e else "—"
        td_lbl = (
            f'<td style="padding:10px 14px;border-bottom:1px solid {COL_BORDER};'
            f'border-right:2px solid {COL_BORDER};color:{COL_DIM};font-size:10px;'
            f'text-transform:uppercase;letter-spacing:1px;cursor:help" title="{tip}">{lbl}</td>'
        )
        def _td(content, color=COL_TEXT, mono=False):
            fs = "font-family:monospace;" if mono else ""
            return (f'<td style="padding:10px 14px;border-bottom:1px solid {COL_BORDER};'
                    f'text-align:right;{fs}color:{color};font-size:13px">{content}</td>')
        rows.append(
            f'<tr>'
            f'{td_lbl}'
            f'{_td(vstr, vcol, mono=True)}'
            f'{_td(str(s) if s else "—", COL_DIM)}'
            f'{_td(str(e) if e else "—", COL_DIM)}'
            f'{_td(length, COL_DIM)}'
            f'</tr>'
        )

    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-radius:4px;overflow:hidden;margin-bottom:10px">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead>{header}</thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table></div>'
    )


def _build_trade_distribution(trades: list[dict]) -> go.Figure:
    closed = [t for t in trades if not t["open"]]
    fig = go.Figure()
    if closed:
        losses = [t["pnl_pct"] for t in closed if t["pnl_pct"] <= 0]
        wins = [t["pnl_pct"] for t in closed if t["pnl_pct"] > 0]
        if losses:
            fig.add_trace(go.Histogram(
                x=losses, name="Losses", marker_color=COL_BEAR, opacity=0.8,
                hovertemplate="P&L: %{x:.1f}%<br>Count: %{y}<extra></extra>"))
        if wins:
            fig.add_trace(go.Histogram(
                x=wins, name="Wins", marker_color=COL_BULL, opacity=0.8,
                hovertemplate="P&L: %{x:.1f}%<br>Count: %{y}<extra></extra>"))
    fig.update_layout(barmode="stack")
    _chart_layout(fig, height=300)
    fig.update_layout(margin=dict(t=56), title=dict(
        text=f'<span style="color:{COL_TEXT};font-size:12px;text-transform:uppercase;'
             f'letter-spacing:1px">Trade P&L distribution</span>',
        x=0.01, y=0.98, yanchor="top"))
    fig.update_xaxes(title_text="P&L %", title_font=dict(color=COL_DIM, size=10))
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     side="right", title_text="Count",
                     title_font=dict(color=COL_DIM, size=10))
    return fig


def _build_trade_scatter(trades: list[dict]) -> go.Figure:
    closed = [t for t in trades if not t["open"]]
    fig = go.Figure()
    if closed:
        fig.add_trace(go.Scatter(
            x=[t["duration_days"] for t in closed],
            y=[t["pnl_pct"] for t in closed],
            mode="markers",
            marker=dict(
                color=[COL_BULL if t["pnl_pct"] > 0 else COL_BEAR for t in closed],
                size=10, line=dict(color=COL_BORDER, width=1)),
            text=[t["entry_date"].strftime("%Y-%m-%d") for t in closed],
            hovertemplate="Entry: %{text}<br>Duration: %{x}d<br>"
                          "P&L: %{y:+.1f}%<extra></extra>",
            showlegend=False,
        ))
    fig.add_hline(y=0, line_dash="dash", line_color=COL_DIM, line_width=0.5)
    _chart_layout(fig, height=300)
    fig.update_layout(margin=dict(t=56), title=dict(
        text=f'<span style="color:{COL_TEXT};font-size:12px;text-transform:uppercase;'
             f'letter-spacing:1px">Trade scatter · duration vs P&L</span>',
        x=0.01, y=0.98, yanchor="top"))
    fig.update_xaxes(title_text="Duration (days)", title_font=dict(color=COL_DIM, size=10))
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     side="right", title_text="P&L %",
                     title_font=dict(color=COL_DIM, size=10))
    return fig


# ── metrics panel ─────────────────────────────────────────────────────────────

def _fmt_pct(v, dec: int = 1) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v * 100:+.{dec}f}%"


def _fmt_ratio(v, dec: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{dec}f}"


def _val_col(v, positive_good: bool = True) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)) or abs(v) < 1e-9:
        return COL_TEXT
    good = v > 0 if positive_good else v < 0
    return COL_BULL if good else COL_BEAR


# ── trade ledger ──────────────────────────────────────────────────────────────

def _build_trade_ledger(df: pd.DataFrame) -> list[dict]:
    changes    = df[df["signal_changed"]]
    trades: list[dict] = []
    open_entry = None
    for ts, row in changes.iterrows():
        sig = int(row["signal_state"])
        if sig == S_BULL:
            open_entry = {
                "entry_date": ts,
                "entry_px":   float(row["close"]),
                "entry_dist": float(row["dist_pct"]),
            }
        elif sig == S_BEAR and open_entry is not None:
            pnl = (row["close"] / open_entry["entry_px"] - 1.0) * 100.0
            reason = "blow-off" if bool(row["blowoff"]) else "trend-break"
            trades.append({**open_entry,
                           "exit_date":     ts,
                           "exit_px":       float(row["close"]),
                           "duration_days": (ts - open_entry["entry_date"]).days,
                           "pnl_pct": pnl, "exit_reason": reason, "open": False})
            open_entry = None
    last = df.iloc[-1]
    if open_entry is not None and int(last["signal_state"]) == S_BULL:
        pnl = (last["close"] / open_entry["entry_px"] - 1.0) * 100.0
        trades.append({**open_entry,
                       "exit_date":     last.name,
                       "exit_px":       float(last["close"]),
                       "duration_days": (last.name - open_entry["entry_date"]).days,
                       "pnl_pct": pnl, "exit_reason": "—", "open": True})
    return trades


def _trades_to_csv(trades: list[dict]) -> bytes:
    if not trades:
        cols = ["entry_date", "exit_date", "entry_px", "exit_px",
                "duration_days", "pnl_pct", "exit_reason", "open"]
        return pd.DataFrame(columns=cols).to_csv(index=False).encode("utf-8")
    rows = [
        {
            "entry_date":    t["entry_date"].strftime("%Y-%m-%d"),
            "exit_date":     t["exit_date"].strftime("%Y-%m-%d"),
            "entry_px":      round(t["entry_px"], 2),
            "exit_px":       round(t["exit_px"], 2),
            "duration_days": t["duration_days"],
            "pnl_pct":       round(t["pnl_pct"], 2),
            "exit_reason":   t["exit_reason"],
            "open":          t["open"],
        }
        for t in trades
    ]
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def _render_trade_ledger(trades: list[dict], n: int = 12) -> str:
    if not trades:
        return (f'<div style="color:{COL_DIM};padding:24px;text-align:center;'
                f'background:{COL_PANEL};border:1px solid {COL_BORDER};'
                f'border-radius:4px">No completed trades in loaded window.</div>')
    show      = trades[-n:]
    rows_html = []
    for t in show:
        pnl   = t["pnl_pct"]
        pc    = COL_BULL if pnl > 0 else COL_BEAR if pnl < 0 else COL_DIM
        status = (f'<span style="color:{COL_BLUE};font-size:11px;font-weight:600">OPEN</span>'
                  if t["open"] else
                  f'<span style="color:{COL_DIM};font-size:11px">{t["exit_reason"]}</span>')
        ex = "—" if t["open"] else t["exit_date"].strftime("%Y-%m-%d")
        dist = t.get("entry_dist")
        dist_col = COL_BULL if (dist or 0) > 5 else COL_NEUTRAL if (dist or 0) > 0 else COL_BEAR
        dist_txt = f"{dist:+.1f}%" if dist is not None else "—"
        rows_html.append(
            f'<tr style="border-bottom:1px solid {COL_BORDER}">'
            f'<td style="padding:9px 12px;color:{COL_TEXT};font-family:monospace;font-size:12px">{t["entry_date"].strftime("%Y-%m-%d")}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px">{ex}</td>'
            f'<td style="padding:9px 12px;color:{COL_TEXT};font-family:monospace;font-size:12px;text-align:right">${t["entry_px"]:,.2f}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px;text-align:right">${t["exit_px"]:,.2f}</td>'
            f'<td style="padding:9px 12px;color:{dist_col};font-family:monospace;font-size:12px;text-align:right" title="Distance above trackline at entry">{dist_txt}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px;text-align:right">{t["duration_days"]}d</td>'
            f'<td style="padding:9px 12px;color:{pc};font-family:monospace;font-size:13px;font-weight:600;text-align:right">{pnl:+.2f}%</td>'
            f'<td style="padding:9px 12px;text-align:center">{status}</td>'
            f'</tr>'
        )
    cols = [("ENTRY","left"),("EXIT","left"),("ENTRY PX","right"),("EXIT PX","right"),
            ("DIST TL","right"),("DUR","right"),("P&L","right"),("EXIT TRIGGER","center")]
    hdr = "".join(
        f'<th style="padding:7px 12px;color:{COL_DIM};font-size:10px;text-transform:uppercase;'
        f'letter-spacing:0.8px;text-align:{a};border-bottom:1px solid {COL_BORDER};font-weight:600">{lbl}</th>'
        for lbl, a in cols
    )
    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-radius:4px;overflow:hidden">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr>{hdr}</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        f'</table></div>'
    )


# ── gates + status panel (reusable for A and B) ──────────────────────────────

def entry_gates(last: pd.Series, cfg: LeanConfig) -> list:
    """(label, passed, now, needed, hover) per entry gate, for the last bar.

    Split out of the renderer so it can be exercised without Streamlit — see
    `tests/test_gate_rows.py`, which checks the stated formulas against the
    columns they claim to describe.
    """
    # Entry gate changed 2026-08-10: the trackline band no longer decides
    # entry, the Donchian channel does. The trackline row would misreport.
    px  = 0 if float(last["close"]) >= 100 else 2   # majors vs cheap alts
    nl  = "&#10;"
    pct = cfg.donchian_top_frac * 100.0
    tl, tref = float(last["trackline"]), float(last["track_ref"])
    tl_chg = (tl / tref - 1.0) * 100.0 if math.isfinite(tref) and tref else float("nan")
    mal, maref = float(last["ma_long"]), float(last["ma_long_ref"])

    gates = [
        (f"Close in top {100 - pct:.0f} % of {cfg.donchian_period}-day range",
         bool(last["donchian_ok"]),
         f"pos {_num(float(last['donchian_pos']) * 100, 1, ' %')}",
         f"&gt; {pct:.0f} %  (close &gt; {_num(last['donchian_trigger'], px)})",
         nl.join([
             "ENTRY GATE.",
             "",
             f"  HH = highest high of the last {cfg.donchian_period} bars (today included)",
             f"  LL = lowest low   of the last {cfg.donchian_period} bars (today included)",
             "  pos = (close &minus; LL) / (HH &minus; LL)",
             "",
             f"  PASS when pos &gt; {cfg.donchian_top_frac:.2f}",
             "",
             f"Today:  HH = {_num(last['dc_hi'], px)}   LL = {_num(last['dc_lo'], px)}"
             f"   close = {_num(last['close'], px)}",
             f"        pos = {_num(float(last['donchian_pos']) * 100, 1, ' %')}",
             "",
             "Solved for price, the same rule reads",
             f"  close &gt; LL + {cfg.donchian_top_frac:.2f} &times; (HH &minus; LL) "
             f"= {_num(last['donchian_trigger'], px)}",
             "",
             "This replaced the trackline band as the entry gate on 2026-08-10.",
             "The trackline still drives the EXIT.",
         ])),
        (f"Trackline higher than {cfg.track_slope_bars} bars ago",
         bool(last["track_rising_window"]),
         f"{_num(tl, px)} vs {_num(tref, px)} ({tl_chg:+.2f} %)",
         f"&gt; {_num(tref, px)}",
         nl.join([
             "ENTRY GATE.",
             "",
             f"  TL = (highest high of {cfg.track_period} bars"
             f" + lowest low of {cfg.track_period} bars) / 2",
             f"  PASS when TL(today) &gt; TL({cfg.track_slope_bars} bars ago)",
             "",
             "This is ONE comparison: today against the bar "
             f"{cfg.track_slope_bars} days back.",
             "It does NOT require the trackline to rise on each of those days.",
             f"It may fall on {cfg.track_slope_bars - 1} of them and still PASS,",
             "as long as today sits above where it was then.",
             "",
             f"Today:  TL = {_num(tl, px)}"
             f"   TL {cfg.track_slope_bars} bars ago = {_num(tref, px)}"
             f"   change {tl_chg:+.2f} %",
         ])),
        (f"Close above MA{cfg.ma_long_len}, or MA{cfg.ma_long_len} not falling",
         bool(last["regime_ok"]),
         f"close {_num(last['close'], px)} "
         f"{'above' if bool(last['above_ma_long']) else 'below'} MA{cfg.ma_long_len} "
         f"{_num(mal, px)}  ·  MA{cfg.ma_long_len} "
         f"{'falling' if bool(last['ma_long_falling']) else 'not falling'}",
         "either one",
         nl.join([
             "ENTRY GATE.",
             "",
             f"  MA{cfg.ma_long_len} = simple average of the last {cfg.ma_long_len} closes",
             "",
             f"  PASS when  close &gt; MA{cfg.ma_long_len}",
             f"        OR   MA{cfg.ma_long_len}(today) &ge; MA{cfg.ma_long_len}"
             f"({cfg.ma_slope} bars ago)",
             "",
             "Either one on its own is enough. Entry is blocked only when BOTH",
             "fail at once &mdash; price below the average AND the average falling.",
             "A dip below a still-rising average does not block anything.",
             "",
             f"Today:  close = {_num(last['close'], px)}"
             f"   MA{cfg.ma_long_len} = {_num(mal, px)}"
             f"   &rarr; {'above &mdash; PASS' if bool(last['above_ma_long']) else 'below'}",
             f"        MA{cfg.ma_long_len} = {_num(mal, px)}"
             f"   {cfg.ma_slope} bars ago = {_num(maref, px)}"
             f"   &rarr; {'falling' if bool(last['ma_long_falling']) else 'not falling &mdash; PASS'}",
             "",
             f"  &rarr; {'PASS' if bool(last['regime_ok']) else 'BLOCKED (both failed)'}",
             "",
             "This blocks ENTRY only. The strategy holds through it once long.",
         ])),
        ("No blow-off top",
         not bool(last["blowoff"]),
         f"dist {_num(last['dist_pct'], 1, ' %')}  ·  RSI {_num(last['rsi'], 1)}",
         f"not (dist &gt; {cfg.blowoff_dist_pct:.0f} % AND RSI &gt; 80)",
         nl.join([
             "ENTRY GATE and EXIT RULE &mdash; the same test does both jobs.",
             "",
             "  dist = (close &minus; TL) / TL &times; 100",
             f"  blowoff = (dist &gt; {cfg.blowoff_dist_pct:.0f} %) AND (RSI{cfg.rsi_len} &gt; 80)",
             "  PASS when NOT blowoff",
             "",
             "BOTH must hold to fire. A stretched price with a calm RSI does",
             "nothing, and so does a hot RSI close to the trackline.",
             "",
             f"Today:  dist = {_num(last['dist_pct'], 2, ' %')}"
             f"   RSI{cfg.rsi_len} = {_num(last['rsi'], 1)}",
             "",
             "It sits on the entry side too so the strategy never buys on a bar",
             "it would sell on.",
         ])),
    ]
    if cfg.use_btc_filter:
        gates.append((
            "BTC bull (cross-asset)",
            bool(last["btc_filter_ok"]),
            f"BTC {'above' if bool(last['btc_bull']) else 'below'} its 50-day EMA",
            "BTC above EMA50",
            nl.join([
                "ENTRY GATE &mdash; optional, off by default in Lean.",
                "",
                "  PASS when BTC close &gt; EMA50 of BTC close",
                "",
                f"Today:  BTC is {'above' if bool(last['btc_bull']) else 'below'} its EMA50.",
            ]),
        ))
    return gates


def exit_gates(last: pd.Series, cfg: LeanConfig) -> list:
    """(label, passed, now, needed, hover) per exit gate, for the last bar.

    These are the ONLY two exits the state machine has. `regime_ok` used to be
    listed here as a third, described as forcing an exit in a bear market — it
    does not. It sits in bull_condition, so it blocks ENTRY only, and the
    strategy holds through it: 4412 bars across the parameter grid are BULL
    while regime_ok is false. It is listed under the entry gates instead.
    """
    px = 0 if float(last["close"]) >= 100 else 2
    nl = "&#10;"
    below_n = int(last["below_count"])
    gates = [
        (f"Not below trackline band {cfg.exit_grace_bars} days running",
         not (bool(last["below_tl"]) and below_n >= cfg.exit_grace_bars),
         f"{_num(last['close'], px)} vs {_num(last['tl_lower'], px)}"
         f"  ·  {below_n} day{'' if below_n == 1 else 's'} below",
         f"&lt; {cfg.exit_grace_bars} days below",
         nl.join([
             "EXIT RULE &mdash; trend break.",
             "",
             f"  TL    = (highest high of {cfg.track_period} bars"
             f" + lowest low of {cfg.track_period} bars) / 2",
             f"  lower = TL &times; (1 &minus; {cfg.track_buf_pct:.0f} / 100)"
             f" = {_num(last['tl_lower'], px)}",
             "  below = close &lt; lower",
             f"  EXIT when below has held {cfg.exit_grace_bars} consecutive days",
             "",
             "One day below is not enough, and the count resets the moment the",
             "close comes back above the band.",
             "",
             f"Today:  close = {_num(last['close'], px)}"
             f"   lower = {_num(last['tl_lower'], px)}"
             f"   &rarr; {'below' if bool(last['below_tl']) else 'not below'}",
             f"        consecutive days below = {below_n} of {cfg.exit_grace_bars}",
             "",
             "The trackline band no longer gates entry, only this exit.",
         ])),
        ("No blow-off top",
         not bool(last["blowoff"]),
         f"dist {_num(last['dist_pct'], 1, ' %')}  ·  RSI {_num(last['rsi'], 1)}",
         f"not (dist &gt; {cfg.blowoff_dist_pct:.0f} % AND RSI &gt; 80)",
         nl.join([
             "EXIT RULE &mdash; fires immediately, no grace period.",
             "",
             "  dist = (close &minus; TL) / TL &times; 100",
             f"  blowoff = (dist &gt; {cfg.blowoff_dist_pct:.0f} %) AND (RSI{cfg.rsi_len} &gt; 80)",
             "",
             "BOTH must hold. Unlike the trend break this needs no confirmation:",
             "the bar it fires on is the bar the strategy sells on.",
             "",
             f"Today:  dist = {_num(last['dist_pct'], 2, ' %')}"
             f"   RSI{cfg.rsi_len} = {_num(last['rsi'], 1)}",
             "",
             "It also blocks entry, so the strategy never buys on a bar it",
             "would sell on.",
         ])),
    ]
    return gates


def _render_gates_and_status(df: pd.DataFrame, s: dict, cfg: LeanConfig,
                              symbol: str) -> None:
    """Entry gates · exit gates · status detail — 3-column layout."""
    last = df.iloc[-1]
    left, mid, right = st.columns([4, 4, 4], gap="medium")

    def panel(rows: list) -> str:
        inner = "".join(
            f'<div title="{tip}" style="cursor:help">{_gate_row(lbl, ok, now, need)}</div>'
            for lbl, ok, now, need, tip in rows
        )
        return (f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
                f'border-radius:4px;overflow:hidden">{inner}</div>')

    with left:
        st.markdown(
            f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
            f'letter-spacing:1.5px;margin:0 0 7px 0" '
            f'title="All conditions must be PASS simultaneously for a BULL entry signal.">'
            f'Entry gates · {symbol} · all must PASS for BULL</div>',
            unsafe_allow_html=True,
        )
        st.markdown(panel(entry_gates(last, cfg)), unsafe_allow_html=True)
        if s["blowoff"]:
            st.markdown(
                f'<div style="background:{COL_PANEL};border:1px solid {COL_BEAR};'
                f'border-radius:4px;padding:9px 14px;margin-top:8px;'
                f'color:{COL_BEAR};font-size:12px;font-weight:700;'
                f'letter-spacing:0.5px;text-transform:uppercase">BLOW-OFF top</div>',
                unsafe_allow_html=True,
            )

    with mid:
        st.markdown(
            f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
            f'letter-spacing:1.5px;margin:0 0 7px 0" '
            f'title="If any exit condition becomes FAIL the strategy exits to cash (BEAR).">'
            f'Exit gates · any FAIL triggers exit</div>',
            unsafe_allow_html=True,
        )
        st.markdown(panel(exit_gates(last, cfg)), unsafe_allow_html=True)

    with right:
        st.markdown(
            f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
            f'letter-spacing:1.5px;margin:0 0 7px 0" '
            f'title="Key indicator values as of the last bar in the selected window.">'
            f'Status detail · {symbol}</div>',
            unsafe_allow_html=True,
        )
        ma_col  = (COL_BEAR if s["bear_regime"]
                   else COL_NEUTRAL if s["ma_long_status"] == "BELOW" else COL_BULL)
        tl_dir  = "RISING" if s["track_rising_window"] else "FLAT / FALLING"
        tl_col  = COL_BULL if s["track_rising_window"] else COL_BEAR
        rsi_val = s["rsi"]
        rsi_col = COL_BEAR if rsi_val > 70 else COL_BULL if rsi_val < 35 else COL_TEXT
        rsi_fmt = f"{rsi_val:.1f}" if not pd.isna(rsi_val) else "—"
        detail  = [
            _row("200 MA (regime)", s["ma_long_status"], ma_col),
            # Informational only since 2026-08-03 — the 50 MA no longer gates entry,
            # so it is drawn in neutral rather than bull/bear colours.
            _row("50 MA (info)", "ABOVE" if s["above_ma_med"] else "BELOW",
                 COL_NEUTRAL),
            _row("Trackline slope", tl_dir, tl_col),
            _row("RSI", rsi_fmt, rsi_col),
            _row("Annual vol", f'{s["annual_vol"]:.1f}%', COL_NEUTRAL),
        ]
        if cfg.use_btc_filter:
            detail.append(_row("BTC filter",
                               "BTC BULL" if s["btc_bull"] else "BTC BEAR",
                               COL_BULL if s["btc_bull"] else COL_BEAR))
        st.markdown(
            f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
            f'border-radius:4px;padding:4px 16px">{"".join(detail)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="color:{COL_VERY_DIM};font-size:10px;margin-top:8px;'
            f'font-family:monospace">Last bar · {s["time"]:%Y-%m-%d %H:%M UTC}</div>',
            unsafe_allow_html=True,
        )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Diversitas Lean",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _set_theme(st.session_state.get("lean_dark_theme", True))

    st.markdown(
        f"""<style>
        header[data-testid="stHeader"] {{display:none !important}}
        div.block-container {{padding-top:0.5rem;padding-bottom:0.8rem;max-width:1600px}}
        .stApp {{background:{COL_BG}}}
        section.main {{background:{COL_BG}}}
        section[data-testid="stSidebar"] {{background:{COL_PANEL};border-right:1px solid {COL_BORDER}}}
        h1,h2,h3,h4 {{color:{COL_TEXT};font-weight:600}}
        section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{color:{COL_TEXT} !important;font-size:11px}}
        section[data-testid="stSidebar"] div[data-baseweb="select"]>div:first-child {{background:{COL_PANEL} !important;border-color:{COL_BORDER} !important}}
        section[data-testid="stSidebar"] div[data-baseweb="select"] span,
        section[data-testid="stSidebar"] div[data-baseweb="select"] div,
        section[data-testid="stSidebar"] div[data-baseweb="select"] p {{color:#ffffff !important;font-weight:600 !important}}
        section[data-testid="stSidebar"] div[data-baseweb="select"] svg {{fill:#ffffff !important}}
        div[data-baseweb="popover"] ul {{background:{COL_PANEL} !important}}
        div[data-baseweb="popover"] li {{color:{COL_TEXT} !important}}
        div[data-baseweb="popover"] li:hover {{background:{COL_BORDER} !important}}
        section[data-testid="stSidebar"] div[data-baseweb="input"]>div {{background:{COL_PANEL} !important;border-color:{COL_BORDER} !important}}
        section[data-testid="stSidebar"] div[data-baseweb="input"] input {{color:{COL_TEXT} !important}}
        section[data-testid="stSidebar"] [data-testid="stCheckbox"] label p {{color:{COL_TEXT} !important}}
        </style>""",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            f"<div style='color:{COL_TEXT};font-size:17px;font-weight:700;"
            f"letter-spacing:2px;margin-bottom:0'>DIVERSITAS</div>"
            f"<div style='color:{COL_DIM};font-size:10px;letter-spacing:1.5px;"
            f"text-transform:uppercase;margin-bottom:16px'>Lean · Live</div>",
            unsafe_allow_html=True,
        )

        # ── Asset ──────────────────────────────────────────────────────────────
        symbol = st.selectbox(
            "Symbol", list(DEFAULT_CONFIG.symbol_map.keys()), index=0,
            help="Asset to analyze. Data fetched from Binance (primary) or yfinance (fallback).",
        )
        st.markdown(
            f'<div style="background:{COL_BULL}1a;border-left:3px solid {COL_BULL};'
            f'border-radius:3px;padding:6px 12px;margin:2px 0 10px 0;'
            f'font-family:monospace;font-size:15px;font-weight:700;letter-spacing:1.5px;'
            f'color:{COL_BULL}">{symbol} / USD</div>',
            unsafe_allow_html=True,
        )

        # ── Strategy filters ───────────────────────────────────────────────────
        with st.expander("Strategy filters", expanded=True):
            use_btc_filter = st.checkbox(
                "BTC cross-asset filter", value=False,
                help="When ON the strategy only signals BULL if BTC is also in a bull regime. "
                     "Reduces false entries during broad crypto downturns. OFF by default in Lean.",
            )
            bear_alloc = st.slider(
                "Min BEAR allocation %", min_value=0, max_value=50,
                value=int(DEFAULT_CONFIG.bear_alloc_pct), step=5,
                help="Percent of capital kept invested while the signal says out. "
                     "The strategy default is 5 %, so an exit sells 95 %. Set to 0 "
                     "to be fully out, which scored better on every metric from "
                     "2021 onward; see config.py for the numbers.",
            )
            fee_per_side = st.slider(
                "Fee & slippage per side %", min_value=0.0, max_value=1.0, value=0.3, step=0.05,
                help="Combined fee + slippage per trade side (entry OR exit). "
                     "Round trip = 2×. Binance VIP0 + BNB: 0.075% fee. "
                     "Retail slippage: BTC ~0.02%, SOL ~0.05%. Default 0.30% is conservative.",
            )

        # ── Portfolio (optional) ───────────────────────────────────────────────
        with st.expander("Portfolio (optional)", expanded=False):
            _sym_b_options = ["—"] + list(DEFAULT_CONFIG.symbol_map.keys())
            sym_b = st.selectbox(
                "Asset B", _sym_b_options, index=0,
                help="Add a second asset for portfolio mode. '—' = single-asset mode. "
                     "Each asset is traded independently; weights are fixed at start (floating, no daily rebalancing).",
            )
            portfolio_mode = sym_b != "—"
            if portfolio_mode:
                st.markdown(
                    f'<div style="background:#4fc3f71a;border-left:3px solid #4fc3f7;'
                    f'border-radius:3px;padding:6px 12px;margin:2px 0 8px 0;'
                    f'font-family:monospace;font-size:15px;font-weight:700;letter-spacing:1.5px;'
                    f'color:#4fc3f7">{sym_b} / USD</div>',
                    unsafe_allow_html=True,
                )
                w_a = st.slider(
                    "Asset A weight %", min_value=5, max_value=95, value=60, step=5,
                    help=f"% of starting capital in {symbol}. {sym_b} receives the remainder.",
                )
                w_b = 100 - w_a
                st.markdown(
                    f'<div style="display:flex;gap:8px;margin:4px 0 2px 0">'
                    f'<div style="flex:1;background:{COL_BULL}1a;border-radius:3px;padding:5px 8px;'
                    f'text-align:center;font-family:monospace;font-size:12px;font-weight:700;color:{COL_BULL}">'
                    f'{symbol}  {w_a}%</div>'
                    f'<div style="flex:1;background:#4fc3f71a;border-radius:3px;padding:5px 8px;'
                    f'text-align:center;font-family:monospace;font-size:12px;font-weight:700;color:#4fc3f7">'
                    f'{sym_b}  {w_b}%</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                w_a, w_b = 100, 0

        # ── Backtest window ────────────────────────────────────────────────────
        with st.expander("Backtest window", expanded=True):
            _today = datetime.date.today()
            _period = st.selectbox(
                "Period", ["Custom", "All time", "3 years", "2 years", "1 year",
                           "Year to date", "6 months", "3 months"],
                index=0, label_visibility="collapsed",
                help="Quick period selector. Choose 'Custom' to set exact From/To dates.",
            )
            _period_days = {"3 years": 1095, "2 years": 730, "1 year": 365, "6 months": 180, "3 months": 90}
            _default_od = _today - datetime.timedelta(days=1095)
            if _period == "Custom":
                date_from = st.date_input(
                    "From", value=_default_od, max_value=_today, format="YYYY-MM-DD",
                    help="Start date of the analysis window.",
                )
                date_to = st.date_input(
                    "To", value=_today, max_value=_today, format="YYYY-MM-DD",
                    help="End date of the analysis window.",
                )
            else:
                if _period == "All time":
                    date_from, date_to = None, _today
                elif _period == "Year to date":
                    date_from = datetime.date(_today.year, 1, 1)
                    date_to = _today
                else:
                    date_from = _today - datetime.timedelta(days=_period_days[_period])
                    date_to = _today
                _from_txt = str(date_from) if date_from else "all"
                st.markdown(
                    f"<div style='color:{COL_TEXT};font-family:monospace;font-size:12px;"
                    f"background:{COL_BG};border:1px solid {COL_BORDER};border-radius:4px;"
                    f"padding:6px 10px;margin:4px 0'>"
                    f"<span style='color:{COL_DIM};font-size:10px'>From</span> {_from_txt}"
                    f"<span style='color:{COL_DIM};font-size:10px;margin-left:14px'>To</span> {date_to}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── Display & refresh ──────────────────────────────────────────────────
        st.divider()
        st.checkbox("Dark theme", value=True, key="lean_dark_theme",
                    help="Toggle between dark (TradingView-style) and light background.")
        dark_mode    = st.session_state.get("lean_dark_theme", True)
        auto_refresh = st.checkbox("Auto-refresh (60 s)", value=True,
                                   help="Automatically reload data every 60 seconds.")
        if st.button("↺  Refresh now", type="primary", use_container_width=True):
            _load_candles.clear()
            _load_btc.clear()
            _run.clear()
            _run_b.clear()
        st.divider()
        st.markdown(
            f"<div style='color:{COL_VERY_DIM};font-size:10px;line-height:1.6'>"
            f"Data · Binance primary, yfinance fallback<br>Cache · 60 s TTL</div>",
            unsafe_allow_html=True,
        )

    _set_theme(dark_mode)

    # Fetch the window the user asked for PLUS the history its indicators need, so
    # every displayed bar is fully defined and none of the requested window is lost
    # to warm-up. `required_history` reads the lookbacks off the config, so this
    # cannot drift if a moving average is lengthened.
    _warm = required_history(LeanConfig())
    if date_from is not None:
        _days = (datetime.date.today() - date_from).days + _warm
        bars  = max(600, ((_days // 100) + 1) * 100)
    else:
        bars = 2000 + _warm

    # trading-day calendar (252 for stocks/ETFs, 365 for crypto)
    td = 252 if symbol in STOCK_SYMBOLS else TRADING_DAYS

    try:
        cfg, daily, result = _run(symbol, bars, use_btc_filter)
    except Exception as e:
        st.error(f"Data load failed for {symbol}: {e}")
        st.stop()

    # A fallback venue is usable but the numbers are NOT comparable to anything
    # computed on the pinned one — entry is a threshold, so ~0.1 % of price
    # difference moves whole trades (3 pp of CAGR between Binance and Yahoo on
    # BTC). Say so loudly rather than let the page look normal.
    if daily.attrs.get("fell_back_from"):
        st.error(
            f"⚠️ **{daily.attrs['fell_back_from'].upper()} ni bil dosegljiv — "
            f"prikazani podatki so z vira `{daily.attrs.get('source', '?')}`.**  \n"
            f"Številke na tej strani **niso primerljive** s poročili, ki so "
            f"računana na `{daily.attrs['fell_back_from']}`. Na BTC znaša razlika "
            f"med viroma do 3 odstotne točke CAGR, ker je vstopni pogoj prag in "
            f"že desetinka odstotka premakne cel posel. Za primerjavo s poročilom "
            f"počakaj, da je `{daily.attrs['fell_back_from']}` spet dosegljiv."
        )
        # Without this the banner says only THAT it failed. A timeout, a rate
        # limit and a geo-block all need different responses, and the difference
        # was being thrown away.
        when = daily.attrs.get("failed_at")
        if when is not None:
            age = (datetime.datetime.now(datetime.timezone.utc) - when).total_seconds()
            st.caption(
                f"Poskus ob {when:%H:%M:%S UTC} — pred {age:.0f} s."
                + ("  ⚠️ Če je to precej v preteklosti, banner je zastal: "
                   "stran ni bila ponovno pognana." if age > 180 else "")
            )
        # A process that predates the multi-host failover reports one host and
        # looks identical to one where both hosts are blocked. Say which it is.
        n_hosts = daily.attrs.get("binance_hosts", 1)
        if n_hosts < 2:
            st.caption(
                "⚠️ Ta proces še nima podpore za drugi Binance gostitelj. "
                "**Do konca ustavi Streamlit (Ctrl+C) in ga zaženi znova** — "
                "osvežitev brskalnika ne zadošča, ker Streamlit ne uvozi na "
                "novo spremenjenih modulov."
            )
        err = daily.attrs.get("source_errors")
        if err:
            st.caption(f"Razlog: `{err}`")
            if ("451" in err or "403" in err) and n_hosts >= 2:
                st.caption(
                    "HTTP 451/403 je geo-blokada, ne izpad — in odpovedala sta "
                    "oba Binance gostitelja. Poženi "
                    "`python testing/scripts/check_data_sources.py`."
                )

    # `df_full` is what returns are differenced on, so it must reach back before
    # the warm-up cut, not merely before the user's date filter.
    df_full = getattr(result, "untrimmed", result.df)
    df = result.df
    if date_from is not None:
        df = df.loc[str(date_from):]
    if date_to is not None:
        df = df.loc[:str(date_to)]
    if df.empty:
        st.warning("No data in the selected date range — widen the window.")
        st.stop()

    s = build_summary(df)
    trades   = _build_trade_ledger(df)
    metrics  = _compute_metrics(df, bear_alloc_pct=bear_alloc, td=td, df_full=df_full,
                                fee_per_side_pct=fee_per_side)
    is_bull  = (_prev_state(df) == S_BULL).astype(float)
    exposure = (is_bull * 100 + (1 - is_bull) * bear_alloc).mean()

    # ── portfolio mode: load & compute Asset B ────────────────────────────────
    m_a = m_b = m_port = None
    df_b = df_a_al = df_b_al = port_ret = None
    cfg_b = s_b = None
    exp_b = 0.0
    trades_b: list[dict] = []
    if portfolio_mode:
        try:
            cfg_b, result_b = _run_b(sym_b, bars)
        except Exception as e:
            st.error(f"Data load failed for {sym_b}: {e}")
            st.stop()
        df_b_full = result_b.df
        df_b = df_b_full
        if date_from is not None:
            df_b = df_b.loc[str(date_from):]
        if date_to is not None:
            df_b = df_b.loc[:str(date_to)]
        if df_b.empty:
            st.warning(f"No data for {sym_b} in the selected date range.")
            st.stop()
        s_b = build_summary(df_b)
        td_b_val = 252 if sym_b in STOCK_SYMBOLS else TRADING_DAYS
        m_a, m_b, m_port, df_a_al, df_b_al, port_ret = _compute_portfolio_metrics(
            df, df_b, w_a, w_b, bear_alloc, td_a=td, td_b=td_b_val,
            df_a_full=df_full, df_b_full=df_b_full,
            fee_per_side_pct=fee_per_side)
        is_bull_b = (_prev_state(df_b_al) == S_BULL).astype(float)
        exp_b = (is_bull_b * 100 + (1 - is_bull_b) * bear_alloc).mean()
        trades_b = _build_trade_ledger(df_b)

    # ── S&P 500 benchmark (skip when SPY is selected — SPY already IS the index)
    spx_eq = spx_m = None
    if symbol != "SPY":
        try:
            _spx_raw = _load_spx(bars)
            if not _spx_raw.empty:
                _df_dates = df.index.normalize()
                if _df_dates.tz is not None:
                    _df_dates = _df_dates.tz_localize(None)
                _spx_al = _spx_raw.reindex(_df_dates, method="ffill")
                _spx_al.index = df.index
                _spx_ret = _spx_al.pct_change().fillna(0.0)
                spx_eq = (1 + _spx_ret).cumprod() * 100
                spx_m  = _stats(_spx_ret, td=252)
        except Exception:
            pass  # SPX unavailable — continue without benchmark

    # ── worst 1-year windows ──────────────────────────────────────────────────
    worst_w = worst_w_b = {}
    try:
        worst_w = _compute_worst_window(
            symbol, bars, use_btc_filter, float(bear_alloc), td,
            window=td, fee_per_side_pct=fee_per_side)
    except Exception:
        pass
    if portfolio_mode and sym_b:
        try:
            td_b_worst = 252 if sym_b in STOCK_SYMBOLS else TRADING_DAYS
            worst_w_b = _compute_worst_window(
                sym_b, bars, False, float(bear_alloc), td_b_worst,
                window=td_b_worst, fee_per_side_pct=fee_per_side)
        except Exception:
            pass

    # ── status bar ────────────────────────────────────────────────────────────
    st.markdown(_status_bar(s, symbol, cfg), unsafe_allow_html=True)

    # ── KPI cards ─────────────────────────────────────────────────────────────
    if portfolio_mode:
        st.markdown(
            _render_kpi_cards_portfolio(symbol, sym_b, w_a, w_b,
                                        m_a, m_b, m_port, exposure, exp_b,
                                        spx_m=spx_m,
                                        worst_w_a=worst_w, worst_w_b=worst_w_b),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(_render_kpi_cards(metrics, trades, exposure,
                                      spx_m=spx_m, worst_w=worst_w),
                    unsafe_allow_html=True)

    # ── info bar ──────────────────────────────────────────────────────────────
    _n_bars = len(df)
    _first = df.index[0].strftime("%Y-%m-%d")
    _last = df.index[-1].strftime("%Y-%m-%d")
    _bear_txt = f"  ·  BEAR alloc {bear_alloc}%" if bear_alloc > 0 else ""
    _stock_badge = (
        f'  ·  <span style="color:{COL_SPX};font-weight:600">⚠ Stock mode · {td}d/yr · params not tuned for equities</span>'
        if td == 252 else ""
    )
    if portfolio_mode:
        st.markdown(
            f'<div style="color:{COL_DIM};font-size:11px;font-family:monospace;'
            f'text-align:right;margin:-6px 0 6px 0">'
            f'{_n_bars} bars  ·  {_first}  →  {_last}  ·  '
            f'<span style="color:{COL_BULL}">{symbol}</span> {w_a}%'
            f' + <span style="color:#4fc3f7">{sym_b}</span> {w_b}%'
            f'{_bear_txt}{_stock_badge}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="color:{COL_DIM};font-size:11px;font-family:monospace;'
            f'text-align:right;margin:-6px 0 6px 0">'
            f'{_n_bars} bars  ·  {_first}  →  {_last}{_bear_txt}{_stock_badge}</div>',
            unsafe_allow_html=True,
        )

    # ── price charts (tabs; SPX always added as last tab when available) ────────
    _spx_tab_label = "S&P 500" if (spx_eq is not None and spx_m is not None) else None
    if portfolio_mode and df_b is not None:
        st.markdown(_section_label(f"Price chart · {symbol} (A, {w_a}%) + {sym_b} (B, {w_b}%)"),
                    unsafe_allow_html=True)
        _pc_labels = [f"▲ {symbol} / USD  ·  Asset A ({w_a}%)",
                      f"▲ {sym_b} / USD  ·  Asset B ({w_b}%)"]
        if _spx_tab_label:
            _pc_labels.append(_spx_tab_label)
        _pc_tabs = st.tabs(_pc_labels)
        with _pc_tabs[0]:
            st.plotly_chart(_build_price_chart(df, symbol, bear_alloc),
                            use_container_width=True, key="pc_a")
        with _pc_tabs[1]:
            st.plotly_chart(_build_price_chart(df_b_al, sym_b, bear_alloc),
                            use_container_width=True, key="pc_b")
        if _spx_tab_label:
            with _pc_tabs[2]:
                st.markdown(_render_spx_bar(spx_m), unsafe_allow_html=True)
                st.plotly_chart(_build_spx_chart(spx_eq), use_container_width=True, key="pc_spx_port")
    else:
        st.markdown(_section_label(f"Price chart · {symbol}/USD"), unsafe_allow_html=True)
        _pc_labels = [f"▲ {symbol} / USD"]
        if _spx_tab_label:
            _pc_labels.append(_spx_tab_label)
        if len(_pc_labels) > 1:
            _pc_tabs = st.tabs(_pc_labels)
            with _pc_tabs[0]:
                st.plotly_chart(_build_price_chart(df, symbol, bear_alloc),
                                use_container_width=True, key="pc_single")
            with _pc_tabs[1]:
                st.markdown(_render_spx_bar(spx_m), unsafe_allow_html=True)
                st.plotly_chart(_build_spx_chart(spx_eq), use_container_width=True, key="pc_spx_single")
        else:
            st.plotly_chart(_build_price_chart(df, symbol, bear_alloc),
                            use_container_width=True, key="pc_only")

    # ── gates + status (tabs in portfolio mode) ───────────────────────────────
    if portfolio_mode and s_b is not None:
        _tab_g_a, _tab_g_b = st.tabs([f"Entry / Exit gates · {symbol}",
                                        f"Entry / Exit gates · {sym_b}"])
        with _tab_g_a:
            _render_gates_and_status(df, s, cfg, symbol)
        with _tab_g_b:
            _render_gates_and_status(df_b_al, s_b, cfg_b, sym_b)
    else:
        _render_gates_and_status(df, s, cfg, symbol)

    # ── signal timeline ───────────────────────────────────────────────────────
    if portfolio_mode:
        st.markdown(
            _section_label(f"Signal timeline · {symbol} (A, {w_a}%) + {sym_b} (B, {w_b}%)"),
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            _build_signal_timeline_dual(df_a_al, df_b_al, symbol, sym_b),
            use_container_width=True, key="timeline_port",
        )
    else:
        st.markdown(_section_label(f"Signal timeline · {symbol}"), unsafe_allow_html=True)
        st.plotly_chart(_build_signal_timeline(df), use_container_width=True, key="timeline_single")

    # ── equity curve ──────────────────────────────────────────────────────────
    if portfolio_mode:
        st.markdown(
            _section_label(f"Portfolio equity · {symbol} {w_a}% + {sym_b} {w_b}% vs buy & hold"),
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            _build_equity_chart_portfolio(symbol, sym_b, m_a, m_b, m_port, spx_eq=spx_eq),
            use_container_width=True, key="equity_port",
        )
    else:
        st.markdown(_section_label(f"Performance · {symbol} strategy vs buy & hold"),
                    unsafe_allow_html=True)
        st.plotly_chart(_build_equity_chart(metrics, symbol=symbol, spx_eq=spx_eq),
                        use_container_width=True, key="equity_single")

    # ── stress test expander ─────────────────────────────────────────────────
    if worst_w:
        with st.expander("📊 Stress test · worst 1-year window", expanded=False):
            st.markdown(
                f'<div style="color:{COL_DIM};font-size:11px;margin-bottom:10px">'
                f'Rolling analysis across all available history — the worst consecutive '
                f'1-year rolling window for each risk metric, strategy returns only '
                f'(fee + slippage {fee_per_side:.2f}%/stran). Hover metric names for tooltip.'
                f'</div>',
                unsafe_allow_html=True,
            )
            if portfolio_mode and worst_w_b:
                _st_a, _st_b = st.tabs([f"{symbol} · Asset A", f"{sym_b} · Asset B"])
            else:
                _st_a = None

            def _render_stress_panel(ww, sym, td_val, tab_ctx=None):
                rc = ww.get("_roll_cagr")
                def _body():
                    st.markdown(_render_stress_test_table(ww, sym),
                                unsafe_allow_html=True)
                    if rc is not None and not rc.dropna().empty:
                        st.plotly_chart(
                            _build_stress_test_chart(
                                rc, ww.get("cagr_start"), ww.get("cagr_end"), sym
                            ),
                            use_container_width=True,
                            key=f"stress_{sym}",
                        )
                if tab_ctx is not None:
                    with tab_ctx:
                        _body()
                else:
                    _body()

            if _st_a is not None:
                _render_stress_panel(worst_w,   symbol, td,           _st_a)
                _render_stress_panel(worst_w_b, sym_b,  td_b_val if portfolio_mode else td, _st_b)
            else:
                _render_stress_panel(worst_w, symbol, td)

    # ── rolling sharpe + monthly heatmap ──────────────────────────────────────
    if portfolio_mode:
        _sharpe_title = f"Rolling 90-day Sharpe · {symbol} {w_a}% + {sym_b} {w_b}% portfolio"
        _heat_title   = f"Monthly returns · {symbol} {w_a}% + {sym_b} {w_b}% portfolio (%)"
    else:
        _sharpe_title = f"Rolling 90-day Sharpe · {symbol}"
        _heat_title   = f"Monthly returns · {symbol} (%)"
    a_left, a_right = st.columns(2, gap="medium")
    with a_left:
        st.plotly_chart(
            _build_rolling_sharpe(df, bear_alloc, port_ret=port_ret,
                                  title=_sharpe_title, td=td),
            use_container_width=True, key="sharpe",
        )
    with a_right:
        st.plotly_chart(
            _build_monthly_heatmap(df, bear_alloc, port_ret=port_ret, title=_heat_title),
            use_container_width=True, key="heatmap",
        )

    # ── trade ledger ──────────────────────────────────────────────────────────
    if portfolio_mode:
        tab_a, tab_b = st.tabs([f"{symbol} trades", f"{sym_b} trades"])
        with tab_a:
            n_a = len(trades)
            hc_a, dc_a = st.columns([8, 2])
            with hc_a:
                st.markdown(
                    _section_label(f"Trade ledger · {symbol} · {n_a} trade{'s' if n_a != 1 else ''}"),
                    unsafe_allow_html=True,
                )
            with dc_a:
                st.download_button(
                    "Export CSV", data=_trades_to_csv(trades),
                    file_name=f"trades_{symbol}_{pd.Timestamp.now():%Y%m%d}.csv",
                    mime="text/csv", use_container_width=True, key="dl_a",
                )
            st.markdown(_render_trade_ledger(trades, n=n_a), unsafe_allow_html=True)
            tl, tr = st.columns(2, gap="medium")
            with tl:
                st.plotly_chart(_build_trade_distribution(trades),
                                use_container_width=True, key="tdist_a")
            with tr:
                st.plotly_chart(_build_trade_scatter(trades),
                                use_container_width=True, key="tscat_a")
        with tab_b:
            n_b = len(trades_b)
            hc_b, dc_b = st.columns([8, 2])
            with hc_b:
                st.markdown(
                    _section_label(f"Trade ledger · {sym_b} · {n_b} trade{'s' if n_b != 1 else ''}"),
                    unsafe_allow_html=True,
                )
            with dc_b:
                st.download_button(
                    "Export CSV", data=_trades_to_csv(trades_b),
                    file_name=f"trades_{sym_b}_{pd.Timestamp.now():%Y%m%d}.csv",
                    mime="text/csv", use_container_width=True, key="dl_b",
                )
            st.markdown(_render_trade_ledger(trades_b, n=n_b), unsafe_allow_html=True)
            tl2, tr2 = st.columns(2, gap="medium")
            with tl2:
                st.plotly_chart(_build_trade_distribution(trades_b),
                                use_container_width=True, key="tdist_b")
            with tr2:
                st.plotly_chart(_build_trade_scatter(trades_b),
                                use_container_width=True, key="tscat_b")
    else:
        n_trades = len(trades)
        hdr_col, dl_col = st.columns([8, 2])
        with hdr_col:
            st.markdown(
                _section_label(f"Trade ledger · {n_trades} trade{'s' if n_trades != 1 else ''}"),
                unsafe_allow_html=True,
            )
        with dl_col:
            st.download_button(
                "Export CSV", data=_trades_to_csv(trades),
                file_name=f"trades_{symbol}_{pd.Timestamp.now():%Y%m%d}.csv",
                mime="text/csv", use_container_width=True,
            )
        st.markdown(_render_trade_ledger(trades, n=n_trades), unsafe_allow_html=True)

        t_left, t_right = st.columns(2, gap="medium")
        with t_left:
            st.plotly_chart(_build_trade_distribution(trades),
                            use_container_width=True, key="tdist_single")
        with t_right:
            st.plotly_chart(_build_trade_scatter(trades),
                            use_container_width=True, key="tscat_single")

    # Spell out the exact window the numbers above were computed on. Without this
    # the dashboard (live data, rolling `bars` fetch) and a written report (frozen
    # snapshot, fixed dates) silently disagree and neither side can tell why.
    _w_from, _w_to = df.index[0].date(), df.index[-1].date()
    _raw_from = daily.index[0].date()
    _src = daily.attrs.get("source", "?")
    st.markdown(
        f'<div style="color:{COL_VERY_DIM};font-size:10px;margin-top:8px;'
        f'font-family:monospace;text-align:right">'
        f'Vir cen: {_src} · Okno: {_w_from} → {_w_to} ({len(df)} barov) · '
        f'ogrevanje zavrženo od {_raw_from} · '
        f'fee+slip {fee_per_side:.2f}%/stran ({fee_per_side*2:.2f}% RT) · Lean</div>',
        unsafe_allow_html=True,
    )

    if auto_refresh:
        st_autorefresh(interval=60_000, key="auto_refresh_tick_lean")


if __name__ == "__main__":
    main()
