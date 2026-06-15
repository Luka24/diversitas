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
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from shared.data_source import fetch_candles, fetch_btc_daily
from diversitas.config import LeanConfig, DEFAULT_CONFIG
from diversitas.strategy import run_strategy, build_summary, S_BULL, S_NEUTRAL, S_BEAR


TRADING_DAYS = 365

# ── accent colors (theme-independent) ────────────────────────────────────────
COL_BULL    = "#089981"
COL_BEAR    = "#f23645"
COL_NEUTRAL = "#ffb74d"
COL_BLUE    = "#2962ff"
COL_MA50    = "#2196f3"
COL_MA200   = "#ff9800"

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

@st.cache_data(ttl=60, show_spinner=False)
def _load_candles(symbol: str, bars: int) -> pd.DataFrame:
    return fetch_candles(symbol, "1d", bars=bars)


@st.cache_data(ttl=60, show_spinner=False)
def _load_btc(bars: int) -> pd.DataFrame:
    return fetch_btc_daily(bars=bars)


@st.cache_data(ttl=60, show_spinner=False)
def _run(symbol: str, bars: int, use_btc_filter: bool, use_er: bool):
    cfg   = LeanConfig(use_btc_filter=use_btc_filter, use_er=use_er)
    daily = _load_candles(symbol, bars)
    btc   = _load_btc(bars) if use_btc_filter else None
    return cfg, daily, run_strategy(daily, btc_daily=btc, config=cfg)


# ── performance metrics ───────────────────────────────────────────────────────

def _compute_metrics(df: pd.DataFrame) -> dict:
    close     = df["close"]
    ret       = close.pct_change().fillna(0.0)
    sig       = df["signal_state"]
    strat_ret = ret * (sig.shift(1) == S_BULL).astype(float)
    bh_ret    = ret.copy()

    def _stats(r: pd.Series) -> dict:
        r      = r.replace([np.inf, -np.inf], 0.0)
        eq     = (1.0 + r).cumprod()
        peak   = eq.cummax()
        dd     = (eq / peak - 1.0)
        max_dd = float(dd.min())
        years  = max(len(r) / TRADING_DAYS, 1e-9)
        final  = float(eq.iloc[-1]) if len(eq) else 1.0
        cagr   = final ** (1.0 / years) - 1.0
        ann_ret  = r.mean() * TRADING_DAYS
        ann_std  = r.std() * np.sqrt(TRADING_DAYS)
        neg      = r[r < 0]
        down_std = neg.std() * np.sqrt(TRADING_DAYS) if len(neg) > 1 else np.nan
        sharpe   = ann_ret / ann_std  if ann_std  > 1e-9 else np.nan
        sortino  = ann_ret / down_std if (not np.isnan(down_std) and down_std > 1e-9) else np.nan
        calmar   = cagr / abs(max_dd) if max_dd < -1e-6 else np.nan
        return dict(cagr=cagr, sharpe=sharpe, sortino=sortino,
                    max_dd=max_dd, calmar=calmar, eq=eq, dd=dd)

    return {"strategy": _stats(strat_ret), "bh": _stats(bh_ret)}


def _render_kpi_cards(metrics: dict, trades: list[dict], exposure: float) -> str:
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
    gross_profit = sum(t["pnl_pct"] for t in closed if t["pnl_pct"] > 0)
    gross_loss = abs(sum(t["pnl_pct"] for t in closed if t["pnl_pct"] < 0))
    pf = gross_profit / gross_loss if gross_loss > 1e-9 else None

    def _card(label: str, value: str, colour: str,
              bh_val: str = "", bh_col: str = "", tip: str = "") -> str:
        bh_html = ""
        if bh_val:
            bh_html = (
                f'<div style="margin-top:5px;font-size:11px;font-family:monospace">'
                f'<span style="color:{COL_DIM}">B&H </span>'
                f'<span style="color:{bh_col}">{bh_val}</span></div>'
            )
        return (
            f'<div style="flex:1;background:{COL_PANEL};border:1px solid {COL_BORDER};'
            f'border-radius:4px;padding:16px 10px;text-align:center;min-width:130px;cursor:help"'
            f' title="{tip}">'
            f'<div style="color:{COL_DIM};font-size:9px;text-transform:uppercase;'
            f'letter-spacing:1.2px;margin-bottom:8px">{label}</div>'
            f'<div style="color:{colour};font-size:24px;font-weight:700;'
            f'font-family:monospace;line-height:1.1">{value}</div>'
            f'{bh_html}</div>'
        )

    row1 = [
        _card("CAGR", _fmt_pct(strat["cagr"]), _val_col(strat["cagr"]),
              _fmt_pct(bh["cagr"]), _val_col(bh["cagr"]),
              "Compound Annual Growth Rate"),
        _card("Sharpe", _fmt_ratio(strat["sharpe"]), _val_col(strat["sharpe"]),
              _fmt_ratio(bh["sharpe"]), _val_col(bh["sharpe"]),
              "Risk-adjusted return (return / volatility)"),
        _card("Sortino", _fmt_ratio(strat["sortino"]), _val_col(strat["sortino"]),
              _fmt_ratio(bh["sortino"]), _val_col(bh["sortino"]),
              "Return / downside volatility only"),
        _card("Max Drawdown", _fmt_pct(strat["max_dd"]),
              _val_col(strat["max_dd"], positive_good=False),
              _fmt_pct(bh["max_dd"]), _val_col(bh["max_dd"], positive_good=False),
              "Largest peak-to-trough equity decline"),
        _card("Calmar", _fmt_ratio(strat["calmar"]), _val_col(strat["calmar"]),
              _fmt_ratio(bh["calmar"]), _val_col(bh["calmar"]),
              "CAGR / |Max Drawdown|"),
        _card("Win Rate",
              f"{wr:.0f}%" if wr is not None else "—",
              COL_BULL if (wr or 0) >= 50 else COL_NEUTRAL if (wr or 0) >= 40 else COL_BEAR,
              tip="Winning trades / total trades"),
    ]
    row2 = [
        _card("Profit Factor",
              _fmt_ratio(pf) if pf is not None else "—",
              _val_col(pf) if pf is not None else COL_TEXT,
              tip="Gross profit / gross loss"),
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


def _gate_row(label: str, passed: bool) -> str:
    icon = "PASS" if passed else "FAIL"
    col  = COL_BULL if passed else COL_BEAR
    bg   = f"{COL_BULL}11" if passed else f"{COL_BEAR}11"
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'padding:8px 12px;border-bottom:1px solid {COL_BORDER};background:{bg}">'
        f'<span style="color:{COL_TEXT};font-size:11px">{label}</span>'
        f'<span style="background:{col}22;color:{col};padding:2px 10px;'
        f'border-radius:3px;font-size:10px;font-weight:700;'
        f'letter-spacing:0.5px;font-family:monospace">{icon}</span>'
        f'</div>'
    )


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
    if s.get("vol_shock"):
        warnings += f'<span style="color:{COL_BEAR};font-weight:700;font-size:11px;margin-left:8px">⚠ VOL SHOCK</span>'

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

def _build_price_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
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

    # Trackline coloured by slope filter
    rising = df["track_rising_window"].fillna(False).to_numpy()
    tl     = df["trackline"].to_numpy()
    xs     = df.index
    seg_start, first = 0, True
    for i in range(1, len(df) + 1):
        if i == len(df) or rising[i] != rising[seg_start]:
            col = COL_BULL if rising[seg_start] else COL_BEAR
            end = i + (0 if i == len(df) else 1)
            fig.add_trace(go.Scatter(
                x=xs[seg_start:end], y=tl[seg_start:end],
                mode="lines", line=dict(color=col, width=1.6),
                name="Trackline", showlegend=first, legendgroup="tl",
                hovertemplate="TL %{y:,.2f}<extra></extra>",
            ), row=1, col=1)
            first = False
            seg_start = i

    # 50 MA (trend filter)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["ma_med"], mode="lines",
        line=dict(color=COL_MA50, width=1.2),
        name="50 MA (trend)", hovertemplate="50 MA %{y:,.2f}<extra></extra>",
    ), row=1, col=1)

    # 200 MA coloured by direction
    rising_long = (df["ma_long"] > df["ma_long"].shift(5)).fillna(False).to_numpy()
    ml          = df["ma_long"].to_numpy()
    seg2, fl2   = 0, True
    for i in range(1, len(df) + 1):
        if i == len(df) or rising_long[i] != rising_long[seg2]:
            col = COL_MA200 if rising_long[seg2] else COL_BEAR
            end = i + (0 if i == len(df) else 1)
            fig.add_trace(go.Scatter(
                x=xs[seg2:end], y=ml[seg2:end], mode="lines",
                line=dict(color=col, width=1.2, dash="dot"),
                name="200 MA (regime)", showlegend=fl2, legendgroup="ma200",
                hovertemplate="200 MA %{y:,.2f}<extra></extra>",
            ), row=1, col=1)
            fl2  = False
            seg2 = i

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
    fig.add_trace(go.Scatter(
        x=df.index, y=df["target_alloc"], mode="lines",
        line=dict(color=COL_BLUE, width=1.8, shape="hv"),
        fill="tozeroy", fillcolor="rgba(41,98,255,0.12)",
        name="Allocation %", hovertemplate="Alloc %{y:.0f}%<extra></extra>",
    ), row=2, col=1)

    _chart_layout(fig, height=820)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), side="right", row=1, col=1)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), side="right",
                     title_text="Alloc %", title_font=dict(color=COL_DIM, size=10),
                     range=[0, 110], row=2, col=1)
    return fig


def _build_equity_chart(metrics: dict) -> go.Figure:
    strat = metrics["strategy"]
    bh    = metrics["bh"]
    s_eq  = strat["eq"] * 100
    b_eq  = bh["eq"]   * 100
    s_dd  = strat["dd"] * 100

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.65, 0.35], vertical_spacing=0.03,
    )
    fig.add_trace(go.Scatter(
        x=b_eq.index, y=b_eq, mode="lines",
        line=dict(color=COL_DIM, width=1.5),
        name="Buy & Hold", hovertemplate="B&H %{y:.1f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=s_eq.index, y=s_eq, mode="lines",
        line=dict(color=COL_BULL, width=2),
        name="Strategy", hovertemplate="Strategy %{y:.1f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=s_dd.index, y=s_dd, mode="lines",
        fill="tozeroy", line=dict(color=COL_BEAR, width=1),
        fillcolor="rgba(242,54,69,0.18)",
        name="Drawdown %", hovertemplate="DD %{y:.1f}%<extra></extra>",
    ), row=2, col=1)

    _chart_layout(fig, height=420)
    fig.update_layout(margin=dict(t=56), title=dict(
        text=f'<span style="color:{COL_TEXT};font-size:12px;text-transform:uppercase;letter-spacing:1px">Equity curve · strategy vs buy & hold (indexed to 100)</span>',
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

def _build_monthly_heatmap(df: pd.DataFrame) -> go.Figure:
    ret = df["close"].pct_change().fillna(0.0)
    strat_ret = ret * (df["signal_state"].shift(1) == S_BULL).astype(float)
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
                 f'letter-spacing:1px">Monthly returns · strategy (%)</span>',
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


def _build_rolling_sharpe(df: pd.DataFrame) -> go.Figure:
    ret = df["close"].pct_change().fillna(0.0)
    strat_ret = ret * (df["signal_state"].shift(1) == S_BULL).astype(float)
    window = 90
    rm = strat_ret.rolling(window, min_periods=window).mean() * TRADING_DAYS
    rs = strat_ret.rolling(window, min_periods=window).std() * np.sqrt(TRADING_DAYS)
    sharpe = (rm / rs).replace([np.inf, -np.inf], np.nan).dropna()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sharpe.index, y=sharpe, mode="lines",
        line=dict(color=COL_BLUE, width=1.5),
        fill="tozeroy", fillcolor="rgba(41,98,255,0.08)",
        name="Rolling 90d Sharpe",
        hovertemplate="Sharpe %{y:.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=COL_DIM, line_width=0.5)
    fig.add_hline(y=1, line_dash="dot", line_color=COL_BULL, line_width=0.5)
    _chart_layout(fig, height=280)
    fig.update_layout(margin=dict(t=56), title=dict(
        text=f'<span style="color:{COL_TEXT};font-size:12px;text-transform:uppercase;'
             f'letter-spacing:1px">Rolling 90-day Sharpe ratio</span>',
        x=0.01, y=0.98, yanchor="top"))
    fig.update_xaxes(dtick="M3", tickformat="%b\n%Y")
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10), side="right")
    return fig


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
            reason = ("blow-off" if bool(row["blowoff"])
                      else "vol-shock" if bool(row["vol_shock"])
                      else "trend-break")
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
        rows_html.append(
            f'<tr style="border-bottom:1px solid {COL_BORDER}">'
            f'<td style="padding:9px 12px;color:{COL_TEXT};font-family:monospace;font-size:12px">{t["entry_date"].strftime("%Y-%m-%d")}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px">{ex}</td>'
            f'<td style="padding:9px 12px;color:{COL_TEXT};font-family:monospace;font-size:12px;text-align:right">${t["entry_px"]:,.2f}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px;text-align:right">${t["exit_px"]:,.2f}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px;text-align:right">{t["duration_days"]}d</td>'
            f'<td style="padding:9px 12px;color:{pc};font-family:monospace;font-size:13px;font-weight:600;text-align:right">{pnl:+.2f}%</td>'
            f'<td style="padding:9px 12px;text-align:center">{status}</td>'
            f'</tr>'
        )
    cols = [("ENTRY","left"),("EXIT","left"),("ENTRY PX","right"),("EXIT PX","right"),
            ("DUR","right"),("P&L","right"),("EXIT TRIGGER","center")]
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


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Diversitas Lean",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Read theme from session_state BEFORE rendering sidebar so COL_TEXT is correct
    # when we inject inline color into the sidebar title HTML.
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
        section[data-testid="stSidebar"] div[data-baseweb="select"] span {{color:#4fc3f7 !important;font-weight:600 !important}}
        section[data-testid="stSidebar"] div[data-baseweb="select"] svg {{fill:#4fc3f7 !important}}
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
        symbol         = st.selectbox(
            "Symbol", list(DEFAULT_CONFIG.symbol_map.keys()), index=0,
            help="Asset to analyze. Data fetched from Binance (primary) or yfinance (fallback).",
        )
        use_btc_filter = st.checkbox(
            "BTC cross-asset filter", value=False,
            help="When ON the strategy only signals BULL if BTC is also in a bull regime. "
                 "Reduces false entries during broad crypto downturns. OFF by default in Lean.",
        )
        use_er = st.checkbox(
            "Efficiency Ratio filter", value=True,
            help="Kaufman Efficiency Ratio: ER = |net change over N bars| / sum(|daily changes|). "
                 "Near 1 = clean trend, near 0 = sideways chop. "
                 "When ON, entries are blocked during choppy markets (ER < 0.30).",
        )
        st.divider()
        st.markdown(
            f"<div style='color:{COL_DIM};font-size:10px;text-transform:uppercase;"
            f"letter-spacing:1.2px;margin-bottom:6px'>Backtest window</div>",
            unsafe_allow_html=True,
        )
        _today = datetime.date.today()
        _period = st.selectbox(
            "Period", ["Custom", "All time", "2 years", "1 year",
                       "Year to date", "6 months", "3 months"],
            index=0, label_visibility="collapsed",
            help="Quick period selector. Choose 'Custom' to set exact Od/Do dates.",
        )
        _period_days = {"2 years": 730, "1 year": 365, "6 months": 180, "3 months": 90}
        if _period == "Custom":
            date_from = st.date_input(
                "Od", value=None, max_value=_today, format="YYYY-MM-DD",
                help="Start date of the analysis window.",
            )
            date_to = st.date_input(
                "Do", value=_today, max_value=_today, format="YYYY-MM-DD",
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
                f"<span style='color:{COL_DIM};font-size:10px'>Od</span> {_from_txt}"
                f"<span style='color:{COL_DIM};font-size:10px;margin-left:14px'>Do</span> {date_to}"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.divider()
        st.checkbox("Dark theme", value=True, key="lean_dark_theme",
                    help="Toggle between dark (TradingView-style) and light background.")
        dark_mode      = st.session_state.get("lean_dark_theme", True)
        auto_refresh   = st.checkbox("Auto-refresh (60 s)", value=True,
                                     help="Automatically reload data every 60 seconds.")
        if st.button("↺  Refresh now", type="primary", use_container_width=True):
            _load_candles.clear()
            _load_btc.clear()
            _run.clear()
        st.divider()
        st.markdown(
            f"<div style='color:{COL_VERY_DIM};font-size:10px;line-height:1.6'>"
            f"Data · Binance primary, yfinance fallback<br>Cache · 60 s TTL</div>",
            unsafe_allow_html=True,
        )

    # Re-apply theme in case checkbox changed this run (takes effect next rerun for sidebar)
    _set_theme(dark_mode)

    if date_from is not None:
        _days = (datetime.date.today() - date_from).days + 200
        bars  = max(600, ((_days // 100) + 1) * 100)
    else:
        bars = 2000

    try:
        cfg, daily, result = _run(symbol, bars, use_btc_filter, use_er)
    except Exception as e:
        st.error(f"Data load failed for {symbol}: {e}")
        st.stop()

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
    metrics  = _compute_metrics(df)
    exposure = (df["signal_state"].shift(1) == S_BULL).mean() * 100

    # ── status bar ────────────────────────────────────────────────────────────
    st.markdown(_status_bar(s, symbol, cfg), unsafe_allow_html=True)

    # ── KPI hero cards ────────────────────────────────────────────────────────
    st.markdown(_render_kpi_cards(metrics, trades, exposure), unsafe_allow_html=True)

    # ── price chart (full width) ──────────────────────────────────────────────
    st.plotly_chart(_build_price_chart(df, symbol), use_container_width=True)

    # ── detail row: entry gates + status ─────────────────────────────────────
    last = df.iloc[-1]
    left, mid, right = st.columns([4, 4, 4], gap="medium")
    with left:
        st.markdown(
            f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
            f'letter-spacing:1.5px;margin:0 0 7px 0" '
            f'title="All conditions must be PASS simultaneously for a BULL entry signal.">'
            f'Entry gates · all must PASS for BULL</div>',
            unsafe_allow_html=True,
        )
        er_val = float(last["er"]) if pd.notna(last["er"]) else 0.0
        er_txt = f"ER {er_val:.2f} {'TREND' if s['er_ok'] else 'CHOP'}"
        gates = [
            ("Above trackline + buffer",
             bool(last["above_tl"]),
             "Price must be above the adaptive trackline plus a safety buffer. "
             "The trackline is a dynamic support line derived from swing lows."),
            ("Above 50 MA (trend)",
             bool(last["above_ma_med"]),
             "Price must be above the 50-day moving average, confirming the medium-term uptrend."),
            (f"Trackline rising ({cfg.track_slope_bars}-bar slope)",
             bool(last["track_rising_window"]),
             f"The trackline must have a positive slope over the last {cfg.track_slope_bars} bars, "
             f"indicating momentum is building rather than decaying."),
            (f"Distance >= {cfg.track_buf_pct + cfg.min_dist_entry_pct:.1f}%",
             bool(last["dist_entry_ok"]),
             "Price must be far enough above the trackline to avoid entering on a weak bounce. "
             "Prevents whipsaw entries near the trackline."),
            ("Regime OK (not bear block)",
             bool(last["regime_ok"]),
             "The 200-day MA regime must not be in a confirmed bear market. "
             "Bear regime blocks all entries to avoid catching falling knives."),
            (er_txt if cfg.use_er else "ER filter (OFF)",
             bool(last["er_ok"]),
             "Efficiency Ratio (Kaufman): ER = |net change over 10 bars| / sum(|daily changes|). "
             "Near 1.0 = clean directional trend. Near 0 = sideways chop. "
             f"Threshold: {cfg.er_thresh:.2f}. Entry blocked when ER is below threshold. "
             "Disable in sidebar to allow entries in choppy conditions."),
        ]
        if cfg.use_btc_filter:
            gates.append((
                "BTC bull (cross-asset)",
                bool(last["btc_filter_ok"]),
                "BTC itself must be in a bull regime (above its own trackline). "
                "Broad crypto bear markets suppress altcoin entries.",
            ))
        gate_html = "".join(
            f'<div title="{tip}">{_gate_row(lbl, ok)}</div>'
            for lbl, ok, tip in gates
        )
        st.markdown(
            f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
            f'border-radius:4px;overflow:hidden">{gate_html}</div>',
            unsafe_allow_html=True,
        )
        wrn = []
        if s["blowoff"]:   wrn.append("BLOW-OFF top")
        if s["vol_shock"]: wrn.append("Volatility shock")
        if wrn:
            st.markdown(
                f'<div style="background:{COL_PANEL};border:1px solid {COL_BEAR};'
                f'border-radius:4px;padding:9px 14px;margin-top:8px;'
                f'color:{COL_BEAR};font-size:12px;font-weight:700;'
                f'letter-spacing:0.5px;text-transform:uppercase">{"  ·  ".join(wrn)}</div>',
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
        exit_gates = [
            ("Above trackline",
             bool(last["above_tl"]),
             "Primary exit trigger: if price closes below the trackline the strategy exits "
             "immediately to protect capital. This is the main stop-loss mechanism."),
            ("Regime OK (no bear block)",
             bool(last["regime_ok"]),
             "A confirmed bear market (price below 200 MA for an extended period) forces an exit "
             "even if price is still above the trackline."),
            ("No blow-off top",
             not bool(last["blowoff"]),
             "A parabolic blow-off top (extreme rapid price spike) triggers an exit — "
             "blow-offs historically precede sharp reversals."),
            ("No volatility shock",
             not bool(last["vol_shock"]),
             "A sudden volatility spike (e.g. flash crash or black swan) triggers an exit "
             "to limit drawdown during chaotic market conditions."),
        ]
        exit_html = "".join(
            f'<div title="{tip}">{_gate_row(lbl, ok)}</div>'
            for lbl, ok, tip in exit_gates
        )
        st.markdown(
            f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
            f'border-radius:4px;overflow:hidden">{exit_html}</div>',
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
            f'letter-spacing:1.5px;margin:0 0 7px 0" '
            f'title="Key indicator values as of the last bar in the selected window.">'
            f'Status detail</div>',
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
            _row("200 MA (regime)", s["ma_long_status"], ma_col,
                 "200-day moving average regime. ABOVE = price in long-term bull zone (entries allowed). "
                 "BELOW = caution zone. BEAR (blocked) = confirmed downtrend; all entries are blocked."),
            _row("50 MA (trend)", "ABOVE" if s["above_ma_med"] else "BELOW",
                 COL_BULL if s["above_ma_med"] else COL_BEAR,
                 "50-day moving average trend filter. Price must be ABOVE the 50 MA to enter BULL. "
                 "Ensures the medium-term trend supports the position."),
            _row("Trackline slope", tl_dir, tl_col,
                 "Direction of the adaptive trackline over the slope window. "
                 "RISING = momentum building, entry conditions improving. "
                 "FLAT / FALLING = trend weakening; entry not possible."),
            _row("RSI", rsi_fmt, rsi_col,
                 "Relative Strength Index (14-period). Measures momentum on a 0–100 scale. "
                 "Above 70 = overbought (potential reversal risk). "
                 "Below 35 = oversold (potential bounce). Secondary signal only."),
            _row("Annual vol", f'{s["annual_vol"]:.1f}%', COL_NEUTRAL,
                 "Annualised 30-day rolling volatility of daily returns (std × √365). "
                 "HIGH vol regime increases risk of false breakouts and reduces allocation. "
                 "LOW vol favours trend continuation."),
            _row("Efficiency Ratio",
                 f'{s["er"]:.2f}  {"TREND" if s["er_ok"] else "CHOP"}',
                 COL_BULL if s["er_ok"] else COL_BEAR,
                 "Kaufman Efficiency Ratio over 10 bars. "
                 "Formula: |close − close[10]| / sum(|daily changes|, 10). "
                 "TREND (≥ 0.30) = directional move, entries allowed. "
                 "CHOP (< 0.30) = sideways noise, entries blocked (when filter ON)."),
        ]
        if cfg.use_btc_filter:
            detail.append(_row("BTC filter",
                               "BTC BULL" if s["btc_bull"] else "BTC BEAR",
                               COL_BULL if s["btc_bull"] else COL_BEAR,
                               "BTC cross-asset regime. BULL = BTC above its own trackline (entries allowed). "
                               "BEAR = BTC in downtrend; altcoin entries are blocked regardless of own signal."))
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

    # ── signal timeline ───────────────────────────────────────────────────────
    st.markdown(_section_label("Signal timeline"), unsafe_allow_html=True)
    st.plotly_chart(_build_signal_timeline(df), use_container_width=True)

    # ── equity curve (full width) ─────────────────────────────────────────────
    st.markdown(_section_label("Performance · strategy vs buy & hold"), unsafe_allow_html=True)
    st.plotly_chart(_build_equity_chart(metrics), use_container_width=True)

    # ── rolling sharpe + monthly heatmap ──────────────────────────────────────
    a_left, a_right = st.columns(2, gap="medium")
    with a_left:
        st.plotly_chart(_build_rolling_sharpe(df), use_container_width=True)
    with a_right:
        st.plotly_chart(_build_monthly_heatmap(df), use_container_width=True)

    # ── trade ledger ──────────────────────────────────────────────────────────
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

    # ── trade analytics ───────────────────────────────────────────────────────
    t_left, t_right = st.columns(2, gap="medium")
    with t_left:
        st.plotly_chart(_build_trade_distribution(trades), use_container_width=True)
    with t_right:
        st.plotly_chart(_build_trade_scatter(trades), use_container_width=True)
    st.markdown(
        f'<div style="color:{COL_VERY_DIM};font-size:10px;margin-top:8px;'
        f'font-family:monospace;text-align:right">'
        f'Naive long-flat backtest · no slippage / fees · Lean</div>',
        unsafe_allow_html=True,
    )

    if auto_refresh:
        st_autorefresh(interval=60_000, key="auto_refresh_tick_lean")


if __name__ == "__main__":
    main()
