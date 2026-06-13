"""Live Streamlit dashboard — Diversitas Pro v3.  TradingView-style layout."""
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
from diversitas.config import Config, DEFAULT_CONFIG
from diversitas.strategy import run_strategy, build_summary, S_BULL, S_NEUTRAL, S_BEAR


TRADING_DAYS = 365  # crypto trades 365 d/yr

# ── accent colors (theme-independent) ────────────────────────────────────────
COL_BULL    = "#089981"   # TV teal-green
COL_BEAR    = "#f23645"   # TV red
COL_NEUTRAL = "#ffb74d"   # amber — hedged
COL_BLUE    = "#2962ff"   # TV blue — conviction / allocation
COL_MA200   = "#ff9800"   # orange — long MA

# ── theme colors (reassigned by _set_theme on every render) ──────────────────
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
def _run(symbol: str, bars: int, use_btc_filter: bool):
    cfg   = Config(use_btc_filter=use_btc_filter)
    daily = _load_candles(symbol, bars)
    btc   = _load_btc(bars) if use_btc_filter else None
    return cfg, daily, run_strategy(daily, btc_daily=btc, config=cfg)


# ── performance metrics ───────────────────────────────────────────────────────

def _compute_metrics(df: pd.DataFrame) -> dict:
    """Annualised risk/return metrics for the strategy and buy & hold."""
    close = df["close"]
    ret   = close.pct_change().fillna(0.0)
    sig   = df["signal_state"]
    strat_ret = ret * (sig == S_BULL).astype(float)
    bh_ret    = ret.copy()

    def _stats(r: pd.Series) -> dict:
        r = r.replace([np.inf, -np.inf], 0.0)
        eq    = (1.0 + r).cumprod()
        peak  = eq.cummax()
        dd    = (eq / peak - 1.0)
        max_dd = float(dd.min())
        years  = max(len(r) / TRADING_DAYS, 1e-9)
        final  = float(eq.iloc[-1]) if len(eq) else 1.0
        cagr   = final ** (1.0 / years) - 1.0
        ann_ret = r.mean() * TRADING_DAYS
        ann_std = r.std() * np.sqrt(TRADING_DAYS)
        neg     = r[r < 0]
        down_std = neg.std() * np.sqrt(TRADING_DAYS) if len(neg) > 1 else np.nan
        sharpe   = ann_ret / ann_std if ann_std > 1e-9 else np.nan
        sortino  = ann_ret / down_std if (not np.isnan(down_std) and down_std > 1e-9) else np.nan
        calmar   = cagr / abs(max_dd) if max_dd < -1e-6 else np.nan
        return dict(cagr=cagr, sharpe=sharpe, sortino=sortino,
                    max_dd=max_dd, calmar=calmar, eq=eq, dd=dd)

    return {"strategy": _stats(strat_ret), "bh": _stats(bh_ret)}


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
        tickfont=dict(color=COL_DIM, size=10),
        showspikes=True, spikecolor=COL_DIM, spikethickness=1, spikedash="dot",
    )


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _row(label: str, value: str, colour: str = "") -> str:
    vc = colour or COL_TEXT
    return (
        f'<div style="display:flex;justify-content:space-between;'
        f'padding:7px 0;border-bottom:1px solid {COL_BORDER}">'
        f'<span style="color:{COL_DIM};font-size:11px">{label}</span>'
        f'<span style="color:{vc};font-size:12px;font-weight:500;'
        f'font-family:monospace">{value}</span>'
        f'</div>'
    )


def _section_label(txt: str) -> str:
    return (
        f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
        f'letter-spacing:1.5px;margin:18px 0 8px 0">{txt}</div>'
    )


# ── status bar ────────────────────────────────────────────────────────────────

def _status_bar(s: dict, symbol: str, use_btc_filter: bool) -> str:
    sig_col   = COL_BULL if s["signal"] == "BULL" else COL_BEAR
    reg_col   = {"BULL": COL_BULL, "HEDGED": COL_NEUTRAL, "BEAR": COL_BEAR}[s["regime"]]
    dist_txt  = f'{s["dist_pct"]:+.2f}%'
    dist_col  = COL_BULL if s["dist_pct"] > 0 else COL_BEAR
    conv_txt  = f'{s["conviction"]:.0f}'
    thr_txt   = f'{s["threshold"]:.0f}'
    thr_col   = COL_BEAR if s["threshold"] >= 70 else COL_BULL if s["threshold"] <= 55 else COL_NEUTRAL
    alloc_val = s["final_alloc"] if not pd.isna(s["final_alloc"]) else 0.0
    alloc_txt = f"{alloc_val:.0f}%"
    vol_txt   = f'{s["annual_vol"]:.1f}%'
    close_txt = f'${s["close"]:,.2f}'
    date_txt  = f'{s["time"]:%Y-%m-%d}'

    def chip(txt: str, col: str, bold: bool = False) -> str:
        fw = "700" if bold else "500"
        return (f'<span style="color:{col};font-size:13px;font-weight:{fw};'
                f'font-family:monospace">{txt}</span>')

    def lbl(txt: str) -> str:
        return (f'<span style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
                f'letter-spacing:0.4px;margin-right:4px">{txt}</span>')

    sep = (f'<span style="color:{COL_BORDER};padding:0 14px;'
           f'font-size:15px;vertical-align:middle">│</span>')

    warnings = ""
    if s.get("blowoff"):
        warnings += f'<span style="color:{COL_BEAR};font-weight:700;font-size:11px;margin-left:14px">⚠ BLOW-OFF</span>'
    if s.get("vol_shock"):
        warnings += f'<span style="color:{COL_BEAR};font-weight:700;font-size:11px;margin-left:8px">⚠ VOL SHOCK</span>'

    btc_part = ""
    if use_btc_filter:
        arrow   = "▲" if s["btc_bull"] else "▼"
        btc_col = COL_BULL if s["btc_bull"] else COL_BEAR
        btc_part = sep + chip("BTC " + arrow, btc_col)

    content = (
        f'<span style="color:{COL_TEXT};font-size:15px;font-weight:700;margin-right:10px">{symbol}/USD</span>'
        f'<span style="color:{COL_TEXT};font-size:15px;font-family:monospace;margin-right:2px">{close_txt}</span>'
        f'{sep}{lbl("Signal")}{chip(s["signal"], sig_col, bold=True)}'
        f'{sep}{lbl("Regime")}{chip(s["regime"], reg_col)}'
        f'{sep}{lbl("vs TL")}{chip(dist_txt, dist_col)}'
        f'{sep}{lbl("Conv")}{chip(conv_txt, COL_TEXT)}'
        f'<span style="color:{COL_DIM};font-size:11px"> / </span>{chip(thr_txt, thr_col)}'
        f'{sep}{lbl("Alloc")}{chip(alloc_txt, COL_BLUE)}'
        f'{sep}{lbl("Vol")}{chip(vol_txt, COL_DIM)}'
        f'{btc_part}{warnings}'
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
        row_heights=[0.78, 0.22], vertical_spacing=0.03,
        specs=[[{"type": "xy"}], [{"type": "xy"}]],
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

    rising = df["track_rising"].fillna(False).to_numpy()
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

    fig.add_trace(go.Scatter(
        x=df.index, y=df["sma200"],
        mode="lines", line=dict(color=COL_MA200, width=1.2, dash="dot"),
        name="200 MA", hovertemplate="200 MA %{y:,.2f}<extra></extra>",
    ), row=1, col=1)

    green = df[df["green_dot"]]
    red   = df[df["red_dot"]]
    _dot_style = dict(color="rgba(0,0,0,0)", size=5, symbol="circle")
    if len(green):
        fig.add_trace(go.Scatter(
            x=green.index, y=green["low"] * 0.985, mode="markers",
            marker={**_dot_style, "line": dict(color=COL_BULL, width=1.5)},
            name="Bull dot", showlegend=False,
            hovertemplate="BULL %{x|%Y-%m-%d}<extra></extra>",
        ), row=1, col=1)
    if len(red):
        fig.add_trace(go.Scatter(
            x=red.index, y=red["high"] * 1.015, mode="markers",
            marker={**_dot_style, "line": dict(color=COL_BEAR, width=1.5)},
            name="Bear dot", showlegend=False,
            hovertemplate="BEAR %{x|%Y-%m-%d}<extra></extra>",
        ), row=1, col=1)

    changes = df[df["signal_changed"]]
    bulls   = changes[changes["signal_state"] == S_BULL]
    bears   = changes[changes["signal_state"] == S_BEAR]
    if len(bulls):
        fig.add_trace(go.Scatter(
            x=bulls.index, y=bulls["low"] * 0.957,
            mode="markers+text",
            marker=dict(color=COL_BULL, size=14, symbol="triangle-up",
                        line=dict(color=COL_BG, width=1)),
            text=["B"] * len(bulls), textposition="bottom center",
            textfont=dict(color=COL_BG, size=8, family="monospace"),
            name="BULL signal", showlegend=False,
            hovertemplate="▲ BULL  %{x|%Y-%m-%d}  $%{customdata:,.0f}<extra></extra>",
            customdata=bulls["close"],
        ), row=1, col=1)
    if len(bears):
        fig.add_trace(go.Scatter(
            x=bears.index, y=bears["high"] * 1.043,
            mode="markers+text",
            marker=dict(color=COL_BEAR, size=14, symbol="triangle-down",
                        line=dict(color=COL_BG, width=1)),
            text=["S"] * len(bears), textposition="top center",
            textfont=dict(color=COL_BG, size=8, family="monospace"),
            name="BEAR signal", showlegend=False,
            hovertemplate="▼ BEAR  %{x|%Y-%m-%d}  $%{customdata:,.0f}<extra></extra>",
            customdata=bears["close"],
        ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["conviction"], mode="lines",
        line=dict(color=COL_BLUE, width=1.4),
        fill="tozeroy", fillcolor="rgba(41,98,255,0.10)",
        name="Conviction", hovertemplate="Conv %{y:.1f}<extra></extra>",
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["dynamic_threshold"], mode="lines",
        line=dict(color=COL_NEUTRAL, width=1, dash="dash"),
        name="Threshold", hovertemplate="Thr %{y:.0f}<extra></extra>",
    ), row=2, col=1)

    _chart_layout(fig, height=820)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), side="right", row=1, col=1)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), side="right",
                     title_text="Conviction", title_font=dict(color=COL_DIM, size=10),
                     range=[0, 100], row=2, col=1)
    return fig


def _build_breakdown_chart(df: pd.DataFrame) -> go.Figure:
    win  = df.tail(120)
    fig  = go.Figure()
    parts = [
        ("Trend (30)",    "trend_score",  COL_BULL),
        ("Momentum (25)", "mom_score",    COL_BLUE),
        ("Macro (20)",    "macro_score",  "#7b68ee"),
        ("Volume (15)",   "vol_score",    COL_NEUTRAL),
        ("DD brake (10)", "dd_score",     COL_DIM),
    ]
    for label, col, colour in parts:
        fig.add_trace(go.Scatter(
            x=win.index, y=win[col], name=label, mode="lines",
            stackgroup="one", line=dict(width=0.5, color=colour),
            fillcolor=colour, hovertemplate=f"{label} %{{y:.1f}}<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=win.index, y=win["dynamic_threshold"], mode="lines",
        line=dict(color=COL_TEXT, width=1, dash="dash"), name="Threshold",
    ))
    _chart_layout(fig, height=260)
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     range=[0, 100], side="right",
                     title_text="Score", title_font=dict(color=COL_DIM, size=10))
    fig.update_layout(title=dict(
        text=f'<span style="color:{COL_DIM};font-size:11px;text-transform:uppercase;letter-spacing:1px">Conviction breakdown · last 120 bars</span>',
        x=0.01, y=0.97))
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

    _chart_layout(fig, height=340)
    fig.update_layout(title=dict(
        text=f'<span style="color:{COL_DIM};font-size:11px;text-transform:uppercase;letter-spacing:1px">Equity curve · strategy vs buy & hold (indexed to 100)</span>',
        x=0.01, y=0.99))
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     side="right", title_text="Equity",
                     title_font=dict(color=COL_DIM, size=10), row=1, col=1)
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     side="right", title_text="DD %",
                     title_font=dict(color=COL_BEAR, size=10), row=2, col=1)
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


def _render_metrics_panel(metrics: dict, trades: list[dict]) -> str:
    strat  = metrics["strategy"]
    bh     = metrics["bh"]
    closed = [t for t in trades if not t["open"]]
    n      = len(closed)
    wins   = [t for t in closed if t["pnl_pct"] > 0]
    wr     = len(wins) / n * 100 if n else None
    avg_pl = sum(t["pnl_pct"] for t in closed) / n if n else None
    avg_d  = sum(t["duration_days"] for t in closed) / n if n else None
    best   = max(closed, key=lambda t: t["pnl_pct"])["pnl_pct"] if closed else None
    worst  = min(closed, key=lambda t: t["pnl_pct"])["pnl_pct"] if closed else None

    rows_def = [
        # (label, strat_val, strat_col, bh_val, bh_col)
        ("CAGR",
         _fmt_pct(strat.get("cagr")), _val_col(strat.get("cagr")),
         _fmt_pct(bh.get("cagr")),   _val_col(bh.get("cagr"))),
        ("Sharpe Ratio",
         _fmt_ratio(strat.get("sharpe")), _val_col(strat.get("sharpe")),
         _fmt_ratio(bh.get("sharpe")),    _val_col(bh.get("sharpe"))),
        ("Sortino Ratio",
         _fmt_ratio(strat.get("sortino")), _val_col(strat.get("sortino")),
         _fmt_ratio(bh.get("sortino")),    _val_col(bh.get("sortino"))),
        ("Max Drawdown",
         _fmt_pct(strat.get("max_dd")), _val_col(strat.get("max_dd"), positive_good=False),
         _fmt_pct(bh.get("max_dd")),    _val_col(bh.get("max_dd"),    positive_good=False)),
        ("Calmar Ratio",
         _fmt_ratio(strat.get("calmar")), _val_col(strat.get("calmar")),
         _fmt_ratio(bh.get("calmar")),    _val_col(bh.get("calmar"))),
        ("Total Trades",
         str(n) if n else "—",            COL_TEXT,
         "—",                             COL_VERY_DIM),
        ("Win Rate",
         f"{wr:.0f}%" if wr is not None else "—",
         COL_BULL if (wr or 0) >= 50 else COL_NEUTRAL if (wr or 0) >= 40 else COL_BEAR,
         "—", COL_VERY_DIM),
        ("Avg Trade P&L",
         f"{avg_pl:+.2f}%" if avg_pl is not None else "—",
         _val_col(avg_pl),
         "—", COL_VERY_DIM),
        ("Avg Duration",
         f"{avg_d:.0f} d" if avg_d is not None else "—", COL_TEXT,
         "—", COL_VERY_DIM),
        ("Best / Worst",
         f"{best:+.1f}%  /  {worst:+.1f}%" if best is not None else "—",
         COL_TEXT, "—", COL_VERY_DIM),
    ]

    hdr = (
        f'<tr>'
        f'<th style="padding:8px 14px;color:{COL_DIM};font-size:10px;text-transform:uppercase;letter-spacing:0.8px;text-align:left;border-bottom:2px solid {COL_BORDER}">Metric</th>'
        f'<th style="padding:8px 14px;color:{COL_BULL};font-size:10px;text-transform:uppercase;letter-spacing:0.8px;text-align:right;border-bottom:2px solid {COL_BORDER}">Strategy</th>'
        f'<th style="padding:8px 14px;color:{COL_DIM};font-size:10px;text-transform:uppercase;letter-spacing:0.8px;text-align:right;border-bottom:2px solid {COL_BORDER}">Buy & Hold</th>'
        f'</tr>'
    )
    body = "".join(
        f'<tr style="border-bottom:1px solid {COL_BORDER}">'
        f'<td style="padding:8px 14px;color:{COL_DIM};font-size:11px">{lbl}</td>'
        f'<td style="padding:8px 14px;color:{sc};font-size:13px;font-weight:600;font-family:monospace;text-align:right">{sv}</td>'
        f'<td style="padding:8px 14px;color:{bc};font-size:12px;font-family:monospace;text-align:right">{bv}</td>'
        f'</tr>'
        for lbl, sv, sc, bv, bc in rows_def
    )
    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-radius:4px;overflow:hidden">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr>{hdr}</tr></thead>'
        f'<tbody>{body}</tbody>'
        f'</table></div>'
    )


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
                "entry_conv": float(row["conviction"]),
                "entry_thr":  float(row["dynamic_threshold"]),
            }
        elif sig == S_BEAR and open_entry is not None:
            pnl = (row["close"] / open_entry["entry_px"] - 1.0) * 100.0
            trades.append({**open_entry,
                           "exit_date":     ts,
                           "exit_px":       float(row["close"]),
                           "duration_days": (ts - open_entry["entry_date"]).days,
                           "pnl_pct": pnl, "open": False})
            open_entry = None
    last = df.iloc[-1]
    if open_entry is not None and int(last["signal_state"]) == S_BULL:
        pnl = (last["close"] / open_entry["entry_px"] - 1.0) * 100.0
        trades.append({**open_entry,
                       "exit_date":     last.name,
                       "exit_px":       float(last["close"]),
                       "duration_days": (last.name - open_entry["entry_date"]).days,
                       "pnl_pct": pnl, "open": True})
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
    show     = trades[-n:]
    rows_html = []
    for t in show:
        pnl   = t["pnl_pct"]
        pc    = COL_BULL if pnl > 0 else COL_BEAR if pnl < 0 else COL_DIM
        status = (f'<span style="color:{COL_BLUE};font-size:11px;font-weight:600">OPEN</span>'
                  if t["open"] else
                  f'<span style="color:{COL_DIM};font-size:11px">closed</span>')
        ex = "—" if t["open"] else t["exit_date"].strftime("%Y-%m-%d")
        rows_html.append(
            f'<tr style="border-bottom:1px solid {COL_BORDER}">'
            f'<td style="padding:9px 12px;color:{COL_TEXT};font-family:monospace;font-size:12px">{t["entry_date"].strftime("%Y-%m-%d")}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px">{ex}</td>'
            f'<td style="padding:9px 12px;color:{COL_TEXT};font-family:monospace;font-size:12px;text-align:right">${t["entry_px"]:,.2f}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px;text-align:right">${t["exit_px"]:,.2f}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px;text-align:right">{t["duration_days"]}d</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px;text-align:right">{t["entry_conv"]:.0f}/{t["entry_thr"]:.0f}</td>'
            f'<td style="padding:9px 12px;color:{pc};font-family:monospace;font-size:13px;font-weight:600;text-align:right">{pnl:+.2f}%</td>'
            f'<td style="padding:9px 12px;text-align:center">{status}</td>'
            f'</tr>'
        )
    cols = [("ENTRY","left"),("EXIT","left"),("ENTRY PX","right"),("EXIT PX","right"),
            ("DUR","right"),("CONV/THR","right"),("P&L","right"),("","center")]
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
        page_title="Diversitas Pro v3",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Read theme from session_state BEFORE rendering sidebar so COL_TEXT is correct
    # when we inject inline color into the sidebar title HTML.
    _set_theme(st.session_state.get("full_dark_theme", True))

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
        section[data-testid="stSidebar"] div[data-baseweb="select"] span {{color:{COL_TEXT} !important}}
        section[data-testid="stSidebar"] div[data-baseweb="select"] svg {{fill:{COL_DIM} !important}}
        div[data-baseweb="popover"] ul {{background:{COL_PANEL} !important}}
        div[data-baseweb="popover"] li {{color:{COL_TEXT} !important}}
        div[data-baseweb="popover"] li:hover {{background:{COL_BORDER} !important}}
        section[data-testid="stSidebar"] div[data-baseweb="input"]>div {{background:{COL_PANEL} !important;border-color:{COL_BORDER} !important}}
        section[data-testid="stSidebar"] div[data-baseweb="input"] input {{color:{COL_TEXT} !important}}
        section[data-testid="stSidebar"] [data-testid="stCheckbox"] label p {{color:{COL_TEXT} !important}}
        </style>""",
        unsafe_allow_html=True,
    )

    # ── sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            f"<div style='color:{COL_TEXT};font-size:17px;font-weight:700;"
            f"letter-spacing:2px;margin-bottom:0'>DIVERSITAS</div>"
            f"<div style='color:{COL_DIM};font-size:10px;letter-spacing:1.5px;"
            f"text-transform:uppercase;margin-bottom:16px'>Pro v3 · Live</div>",
            unsafe_allow_html=True,
        )
        symbol         = st.selectbox(
            "Symbol", list(DEFAULT_CONFIG.symbol_map.keys()), index=0,
            help="Asset to analyze. Data fetched from Binance (primary) or yfinance (fallback).",
        )
        use_btc_filter = st.checkbox(
            "BTC cross-asset filter", value=(symbol != "BTC"),
            help="When ON the strategy only signals BULL if BTC is also in a bull regime. "
                 "Reduces false entries during broad crypto downturns. Disable on BTC itself.",
        )
        st.divider()
        st.markdown(
            f"<div style='color:{COL_DIM};font-size:10px;text-transform:uppercase;"
            f"letter-spacing:1.2px;margin-bottom:6px'>Backtest window</div>",
            unsafe_allow_html=True,
        )
        _today = datetime.date.today()
        date_from = st.date_input(
            "Od", value=None, max_value=_today, format="YYYY-MM-DD",
            help="Start date of the analysis window. Leave empty to use all available history.",
        )
        date_to = st.date_input(
            "Do", value=_today, max_value=_today, format="YYYY-MM-DD",
            help="End date of the analysis window. Defaults to today.",
        )
        st.divider()
        st.checkbox("Dark theme", value=True, key="full_dark_theme",
                    help="Toggle between dark (TradingView-style) and light background.")
        dark_mode      = st.session_state.get("full_dark_theme", True)
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
        cfg, daily, result = _run(symbol, bars, use_btc_filter)
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
    trades  = _build_trade_ledger(df)
    metrics = _compute_metrics(df)

    # ── status bar ────────────────────────────────────────────────────────────
    st.markdown(_status_bar(s, symbol, use_btc_filter), unsafe_allow_html=True)

    # ── price chart (full width) ──────────────────────────────────────────────
    st.plotly_chart(_build_price_chart(df, symbol), use_container_width=True)

    # ── detail row: status + exit gates + conviction breakdown ───────────────
    left, mid, right = st.columns([3, 3, 6], gap="medium")
    with left:
        st.markdown(
            f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
            f'letter-spacing:1.5px;margin:0 0 8px 0" '
            f'title="Key indicator values as of the last bar in the selected window.">'
            f'Status detail</div>',
            unsafe_allow_html=True,
        )
        ma_colour  = (COL_BEAR if s["bear_market"]
                      else COL_NEUTRAL if s["ma200_status"] == "BELOW" else COL_BULL)
        thr_colour = (COL_BEAR if s["threshold"] >= 70
                      else COL_BULL if s["threshold"] <= 55 else COL_NEUTRAL)
        tl_colour  = COL_BULL if s["track_rising"] else COL_BEAR
        tq         = s["trend_quality_pct"]
        vol_label  = "HIGH" if s["high_vol_regime"] else "LOW" if s["low_vol_regime"] else "NORMAL"
        vol_colour = COL_BEAR if s["high_vol_regime"] else COL_BULL if s["low_vol_regime"] else COL_DIM

        detail_rows = [
            _row("200 MA",           s["ma200_status"], ma_colour),
            _row("Conviction / Thr", f'{s["conviction"]:.1f}  ·  {s["threshold"]:.0f}', thr_colour),
            _row("Trackline",        f'${s["trackline"]:,.0f}  {"RISING" if s["track_rising"] else "FALLING"}', tl_colour),
            _row("Trend quality",    f"{tq:.0f}%",
                 COL_BULL if tq >= 60 else COL_NEUTRAL if tq >= 40 else COL_BEAR),
            _row("Annual vol",       f'{s["annual_vol"]:.1f}%  {vol_label}', vol_colour),
        ]
        if use_btc_filter:
            detail_rows.append(_row("BTC filter",
                                    "BTC BULL" if s["btc_bull"] else "BTC BEAR",
                                    COL_BULL if s["btc_bull"] else COL_BEAR))
        st.markdown(
            f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
            f'border-radius:4px;padding:4px 16px">{"".join(detail_rows)}</div>',
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
        st.markdown(
            f'<div style="color:{COL_VERY_DIM};font-size:10px;margin-top:8px;'
            f'font-family:monospace">Last bar · {s["time"]:%Y-%m-%d %H:%M UTC}</div>',
            unsafe_allow_html=True,
        )
    with mid:
        st.markdown(
            f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
            f'letter-spacing:1.5px;margin:0 0 8px 0" '
            f'title="If any exit gate becomes FAIL the conviction score has dropped '
            f'below the dynamic threshold and the strategy exits to cash.">'
            f'Exit gates · any FAIL triggers exit</div>',
            unsafe_allow_html=True,
        )
        thr = s["threshold"]
        conv = s["conviction"]
        exit_gates = [
            ("Conviction above threshold",
             conv >= thr,
             f"Conviction ({conv:.1f}) must stay above the dynamic threshold ({thr:.0f}). "
             f"When it falls below, the trend is no longer strong enough to stay long."),
            ("No bear market (200 MA)",
             not s["bear_market"],
             "A confirmed bear market forces an exit regardless of conviction. "
             "The 200-day MA regime filter prevents holding through macro downturns."),
            ("No blow-off top",
             not s["blowoff"],
             "A parabolic blow-off top triggers an exit — blow-offs historically precede "
             "sharp and violent reversals."),
            ("No volatility shock",
             not s["vol_shock"],
             "A sudden volatility spike (flash crash or black swan event) triggers an exit "
             "to limit drawdown during chaotic conditions."),
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
        st.plotly_chart(_build_breakdown_chart(df), use_container_width=True)

    # ── performance: metrics table + equity curve ─────────────────────────────
    st.markdown(_section_label("Performance · strategy vs buy & hold"), unsafe_allow_html=True)
    m_col, eq_col = st.columns([35, 65], gap="medium")
    with m_col:
        st.markdown(_render_metrics_panel(metrics, trades), unsafe_allow_html=True)
    with eq_col:
        st.plotly_chart(_build_equity_chart(metrics), use_container_width=True)

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
            "⬇  Export CSV", data=_trades_to_csv(trades),
            file_name=f"trades_{symbol}_{pd.Timestamp.now():%Y%m%d}.csv",
            mime="text/csv", use_container_width=True,
        )
    st.markdown(_render_trade_ledger(trades, n=n_trades), unsafe_allow_html=True)
    st.markdown(
        f'<div style="color:{COL_VERY_DIM};font-size:10px;margin-top:8px;'
        f'font-family:monospace;text-align:right">'
        f'Naive long-flat backtest · no slippage / fees · Pro v3</div>',
        unsafe_allow_html=True,
    )

    if auto_refresh:
        st_autorefresh(interval=60_000, key="auto_refresh_tick")


if __name__ == "__main__":
    main()
