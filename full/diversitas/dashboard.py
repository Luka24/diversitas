"""Live Streamlit dashboard — Diversitas Pro v3.  TradingView-style layout."""
from __future__ import annotations
import sys
from pathlib import Path

_VARIANT_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _VARIANT_ROOT.parent
for p in (_PROJECT_ROOT, _VARIANT_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from shared.data_source import fetch_candles, fetch_btc_daily
from diversitas.config import Config, DEFAULT_CONFIG
from diversitas.strategy import run_strategy, S_BULL, S_NEUTRAL, S_BEAR


# ── TradingView default dark-theme palette ────────────────────────────────────
COL_BULL     = "#089981"   # teal-green — bull state / bull candles
COL_BEAR     = "#f23645"   # red        — bear state / bear candles
COL_NEUTRAL  = "#ffb74d"   # amber      — hedged / threshold line
COL_BLUE     = "#2962ff"   # blue       — conviction / info lines
COL_MA200    = "#ff9800"   # orange     — 200 MA (TV convention)
COL_BG       = "#131722"   # page & chart background
COL_PANEL    = "#1e222d"   # panel / card background
COL_BORDER   = "#2a2e39"   # dividers and card borders
COL_GRID     = "#1e2230"   # chart grid (barely visible)
COL_TEXT     = "#d1d4dc"   # primary text
COL_DIM      = "#787b86"   # label / secondary text
COL_VERY_DIM = "#4c525e"   # timestamps / tertiary text


def _sig_hex(code: int) -> str:
    return COL_BULL if code == S_BULL else (COL_NEUTRAL if code == S_NEUTRAL else COL_BEAR)


# ── caching ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _load_candles(symbol: str, bars: int) -> pd.DataFrame:
    return fetch_candles(symbol, "1d", bars=bars)


@st.cache_data(ttl=60, show_spinner=False)
def _load_btc(bars: int) -> pd.DataFrame:
    return fetch_btc_daily(bars=bars)


@st.cache_data(ttl=60, show_spinner=False)
def _run(symbol: str, bars: int, use_btc_filter: bool):
    cfg = Config(use_btc_filter=use_btc_filter)
    daily = _load_candles(symbol, bars)
    btc = _load_btc(bars) if use_btc_filter else None
    return cfg, daily, run_strategy(daily, btc_daily=btc, config=cfg)


# ── shared chart style ────────────────────────────────────────────────────────

def _chart_layout(fig: go.Figure, height: int) -> None:
    fig.update_layout(
        template="plotly_dark",
        height=height,
        margin=dict(l=0, r=68, t=8, b=8),
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


# ── status bar (replaces hero cards) ─────────────────────────────────────────

def _status_bar(s: dict, symbol: str, use_btc_filter: bool) -> str:
    sig_col  = COL_BULL if s["signal"] == "BULL" else COL_BEAR
    reg_col  = {"BULL": COL_BULL, "HEDGED": COL_NEUTRAL, "BEAR": COL_BEAR}[s["regime"]]
    dist_col = COL_BULL if s["dist_pct"] > 0 else COL_BEAR
    alloc_val = s["final_alloc"] if not pd.isna(s["final_alloc"]) else 0.0
    thr_col  = (COL_BEAR if s["threshold"] >= 70
                else COL_BULL if s["threshold"] <= 55 else COL_NEUTRAL)

    def chip(txt: str, col: str, bold: bool = False) -> str:
        fw = "700" if bold else "500"
        return (f'<span style="color:{col};font-size:13px;font-weight:{fw};'
                f'font-family:monospace">{txt}</span>')

    def lbl(txt: str) -> str:
        return (f'<span style="color:{COL_DIM};font-size:10px;'
                f'text-transform:uppercase;letter-spacing:0.4px;'
                f'margin-right:4px">{txt}</span>')

    sep = (f'<span style="color:{COL_BORDER};padding:0 14px;'
           f'font-size:15px;vertical-align:middle">│</span>')

    warnings = ""
    if s.get("blowoff"):
        warnings += (f'<span style="color:{COL_BEAR};font-weight:700;'
                     f'font-size:11px;margin-left:14px">⚠ BLOW-OFF</span>')
    if s.get("vol_shock"):
        warnings += (f'<span style="color:{COL_BEAR};font-weight:700;'
                     f'font-size:11px;margin-left:8px">⚠ VOL SHOCK</span>')

    conv_txt = f'{s["conviction"]:.0f}'
    thr_txt  = f'{s["threshold"]:.0f}'

    content = (
        f'<span style="color:{COL_TEXT};font-size:15px;font-weight:700;'
        f'margin-right:10px">{symbol}/USD</span>'
        f'<span style="color:{COL_TEXT};font-size:15px;'
        f'font-family:monospace;margin-right:2px">${s["close"]:,.2f}</span>'
        f'{sep}'
        f'{lbl("Signal")}{chip(s["signal"], sig_col, bold=True)}'
        f'{sep}'
        f'{lbl("Regime")}{chip(s["regime"], reg_col)}'
        f'{sep}'
        f'{lbl("vs TL")}{chip(f\'{s["dist_pct"]:+.2f}%\', dist_col)}'
        f'{sep}'
        f'{lbl("Conv")}{chip(conv_txt, COL_TEXT)}'
        f'<span style="color:{COL_DIM};font-size:11px"> / </span>'
        f'{chip(thr_txt, thr_col)}'
        f'{sep}'
        f'{lbl("Alloc")}{chip(f"{alloc_val:.0f}%", COL_BLUE)}'
        f'{sep}'
        f'{lbl("Vol")}{chip(f\'{s["annual_vol"]:.1f}%\', COL_DIM)}'
        f'{warnings}'
    )
    if use_btc_filter:
        arrow = "▲" if s["btc_bull"] else "▼"
        btc_col = COL_BULL if s["btc_bull"] else COL_BEAR
        content += f'{sep}{chip(f"BTC {arrow}", btc_col)}'

    ts = (f'<span style="color:{COL_VERY_DIM};font-size:10px;'
          f'font-family:monospace;margin-left:auto">'
          f'{s["time"]:%Y-%m-%d}</span>')

    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-left:3px solid {sig_col};border-radius:3px;'
        f'padding:10px 16px;margin-bottom:8px;'
        f'display:flex;align-items:center;flex-wrap:wrap;gap:2px">'
        f'{content}{ts}'
        f'</div>'
    )


# ── price chart ───────────────────────────────────────────────────────────────

def _build_price_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.78, 0.22], vertical_spacing=0.03,
        specs=[[{"type": "xy"}], [{"type": "xy"}]],
    )

    # Very subtle vrect bands by display_state
    ds  = df["display_state"]
    grp = (ds != ds.shift(1)).cumsum()
    _rgb = {S_BULL: (8, 153, 129), S_NEUTRAL: (255, 183, 77), S_BEAR: (242, 54, 69)}
    for _, seg in df.groupby(grp):
        r, g, b = _rgb[int(seg["display_state"].iloc[0])]
        fig.add_vrect(
            x0=seg.index[0], x1=seg.index[-1],
            fillcolor=f"rgba({r},{g},{b},0.045)",
            line_width=0, layer="below", row=1, col=1,
        )

    # Candles
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color=COL_BULL, decreasing_line_color=COL_BEAR,
        increasing_fillcolor=COL_BULL, decreasing_fillcolor=COL_BEAR,
        line=dict(width=1),
        name="Price", showlegend=False,
    ), row=1, col=1)

    # Trackline — colour by direction
    rising = df["track_rising"].fillna(False).to_numpy()
    tl = df["trackline"].to_numpy()
    xs, seg_start, first = df.index, 0, True
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

    # 200 MA — orange dashed (TV convention)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["sma200"],
        mode="lines", line=dict(color=COL_MA200, width=1.2, dash="dot"),
        name="200 MA",
        hovertemplate="200 MA %{y:,.2f}<extra></extra>",
    ), row=1, col=1)

    # Condition dots — hollow circles
    green = df[df["green_dot"]]
    red   = df[df["red_dot"]]
    if len(green):
        fig.add_trace(go.Scatter(
            x=green.index, y=green["low"] * 0.985,
            mode="markers",
            marker=dict(color="rgba(0,0,0,0)", size=5, symbol="circle",
                        line=dict(color=COL_BULL, width=1.5)),
            name="Bull dot", showlegend=False,
            hovertemplate="BULL %{x|%Y-%m-%d}<extra></extra>",
        ), row=1, col=1)
    if len(red):
        fig.add_trace(go.Scatter(
            x=red.index, y=red["high"] * 1.015,
            mode="markers",
            marker=dict(color="rgba(0,0,0,0)", size=5, symbol="circle",
                        line=dict(color=COL_BEAR, width=1.5)),
            name="Bear dot", showlegend=False,
            hovertemplate="BEAR %{x|%Y-%m-%d}<extra></extra>",
        ), row=1, col=1)

    # Signal arrows — filled triangles with B / S text
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
            name="BULL signal", legendgroup="signals",
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
            name="BEAR signal", legendgroup="signals",
            hovertemplate="▼ BEAR  %{x|%Y-%m-%d}  $%{customdata:,.0f}<extra></extra>",
            customdata=bears["close"],
        ), row=1, col=1)

    # Conviction subplot
    fig.add_trace(go.Scatter(
        x=df.index, y=df["conviction"], mode="lines",
        line=dict(color=COL_BLUE, width=1.4),
        fill="tozeroy", fillcolor="rgba(41,98,255,0.10)",
        name="Conviction",
        hovertemplate="Conv %{y:.1f}<extra></extra>",
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["dynamic_threshold"], mode="lines",
        line=dict(color=COL_NEUTRAL, width=1, dash="dash"),
        name="Threshold",
        hovertemplate="Thr %{y:.0f}<extra></extra>",
    ), row=2, col=1)

    _chart_layout(fig, height=850)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), side="right",
                     row=1, col=1)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), side="right",
                     title_text="Conviction", title_font=dict(color=COL_DIM, size=10),
                     range=[0, 100], row=2, col=1)
    return fig


def _build_breakdown_chart(df: pd.DataFrame) -> go.Figure:
    win = df.tail(120)
    fig = go.Figure()
    parts = [
        ("Trend (30)",    "trend_score",  COL_BULL),
        ("Momentum (25)", "mom_score",    COL_BLUE),
        ("Macro (20)",    "macro_score",  "#7b68ee"),
        ("Volume (15)",   "vol_score",    COL_NEUTRAL),
        ("DD brake (10)", "dd_score",     COL_DIM),
    ]
    for label, col, colour in parts:
        fig.add_trace(go.Scatter(
            x=win.index, y=win[col], name=label,
            mode="lines", stackgroup="one",
            line=dict(width=0.5, color=colour),
            fillcolor=colour,
            hovertemplate=f"{label} %{{y:.1f}}<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=win.index, y=win["dynamic_threshold"], mode="lines",
        line=dict(color=COL_TEXT, width=1, dash="dash"),
        name="Threshold",
    ))
    _chart_layout(fig, height=260)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10),
                     title_text="Score", title_font=dict(color=COL_DIM, size=10),
                     range=[0, 100], side="right")
    fig.update_layout(
        title=dict(
            text=(f'<span style="color:{COL_DIM};font-size:11px;'
                  f'text-transform:uppercase;letter-spacing:1px">'
                  f'Conviction breakdown · last 120 bars</span>'),
            x=0.01, y=0.97,
        ),
    )
    return fig


def _build_vol_alloc_chart(df: pd.DataFrame) -> go.Figure:
    win = df.tail(240).copy()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=win.index, y=win["annual_vol"], mode="lines",
        line=dict(color=COL_NEUTRAL, width=1.5),
        name="Annual vol %",
        hovertemplate="Vol %{y:.1f}%<extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=win.index, y=win["final_alloc"], mode="lines",
        line=dict(color=COL_BLUE, width=1.8, shape="hv"),
        fill="tozeroy", fillcolor="rgba(41,98,255,0.10)",
        name="Allocation %",
        hovertemplate="Alloc %{y:.0f}%<extra></extra>",
    ), secondary_y=True)
    _chart_layout(fig, height=220)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_NEUTRAL, size=10),
                     title_text="Vol %", title_font=dict(color=COL_NEUTRAL, size=10),
                     secondary_y=False)
    fig.update_yaxes(showgrid=False,
                     tickfont=dict(color=COL_BLUE, size=10),
                     title_text="Alloc %", title_font=dict(color=COL_BLUE, size=10),
                     range=[0, 105], secondary_y=True)
    fig.update_layout(
        title=dict(
            text=(f'<span style="color:{COL_DIM};font-size:11px;'
                  f'text-transform:uppercase;letter-spacing:1px">'
                  f'Volatility & allocation · last 240 bars</span>'),
            x=0.01, y=0.97,
        ),
    )
    return fig


# ── detail row helpers ────────────────────────────────────────────────────────

def _row(label: str, value: str, colour: str = None) -> str:
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
        f'<div style="color:{COL_DIM};font-size:10px;'
        f'text-transform:uppercase;letter-spacing:1.5px;'
        f'margin:16px 0 7px 0">{txt}</div>'
    )


# ── trade ledger ──────────────────────────────────────────────────────────────

def _build_trade_ledger(df: pd.DataFrame) -> list[dict]:
    changes = df[df["signal_changed"]]
    trades: list[dict] = []
    open_entry = None
    for ts, row in changes.iterrows():
        sig = int(row["signal_state"])
        if sig == S_BULL:
            open_entry = {
                "entry_date": ts, "entry_px": float(row["close"]),
                "entry_conv": float(row["conviction"]),
                "entry_thr":  float(row["dynamic_threshold"]),
            }
        elif sig == S_BEAR and open_entry is not None:
            pnl = (row["close"] / open_entry["entry_px"] - 1.0) * 100.0
            trades.append({
                **open_entry,
                "exit_date": ts, "exit_px": float(row["close"]),
                "duration_days": (ts - open_entry["entry_date"]).days,
                "pnl_pct": pnl, "open": False,
            })
            open_entry = None
    last = df.iloc[-1]
    if open_entry is not None and int(last["signal_state"]) == S_BULL:
        pnl = (last["close"] / open_entry["entry_px"] - 1.0) * 100.0
        trades.append({
            **open_entry,
            "exit_date": last.name, "exit_px": float(last["close"]),
            "duration_days": (last.name - open_entry["entry_date"]).days,
            "pnl_pct": pnl, "open": True,
        })
    return trades


def _render_trade_ledger(trades: list[dict], n: int = 12) -> str:
    if not trades:
        return (f'<div style="color:{COL_DIM};padding:24px;text-align:center;'
                f'background:{COL_PANEL};border:1px solid {COL_BORDER};'
                f'border-radius:4px">No completed trades in the loaded window.</div>')
    show = trades[-n:]
    rows_html = []
    for t in show:
        pnl = t["pnl_pct"]
        pc  = COL_BULL if pnl > 0 else COL_BEAR if pnl < 0 else COL_DIM
        status = (
            f'<span style="color:{COL_BLUE};font-size:11px;font-weight:600">OPEN</span>'
            if t["open"] else
            f'<span style="color:{COL_DIM};font-size:11px">closed</span>'
        )
        exit_txt = "—" if t["open"] else t["exit_date"].strftime("%Y-%m-%d")
        rows_html.append(
            f'<tr style="border-bottom:1px solid {COL_BORDER}">'
            f'<td style="padding:9px 12px;color:{COL_TEXT};font-family:monospace;font-size:12px">{t["entry_date"].strftime("%Y-%m-%d")}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px">{exit_txt}</td>'
            f'<td style="padding:9px 12px;color:{COL_TEXT};font-family:monospace;font-size:12px;text-align:right">${t["entry_px"]:,.2f}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px;text-align:right">${t["exit_px"]:,.2f}</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px;text-align:right">{t["duration_days"]}d</td>'
            f'<td style="padding:9px 12px;color:{COL_DIM};font-family:monospace;font-size:12px;text-align:right">{t["entry_conv"]:.0f}/{t["entry_thr"]:.0f}</td>'
            f'<td style="padding:9px 12px;color:{pc};font-family:monospace;font-size:13px;font-weight:600;text-align:right">{pnl:+.2f}%</td>'
            f'<td style="padding:9px 12px;text-align:center">{status}</td>'
            f'</tr>'
        )
    cols = [("ENTRY","left"),("EXIT","left"),("ENTRY PX","right"),("EXIT PX","right"),
            ("DUR","right"),("CONV/THR","right"),("P&L","right"),("STATUS","center")]
    hdr = "".join(
        f'<th style="padding:7px 12px;color:{COL_DIM};font-size:10px;'
        f'text-transform:uppercase;letter-spacing:0.8px;text-align:{a};'
        f'border-bottom:1px solid {COL_BORDER};font-weight:600">{lbl}</th>'
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


def _render_signal_stats(trades: list[dict], df: pd.DataFrame) -> str:
    closed = [t for t in trades if not t["open"]]
    n_total = len(closed)
    if n_total == 0:
        return (f'<div style="color:{COL_DIM};padding:14px;background:{COL_PANEL};'
                f'border:1px solid {COL_BORDER};border-radius:4px;text-align:center">'
                f'No completed trades yet.</div>')
    wins    = [t for t in closed if t["pnl_pct"] > 0]
    win_rate = len(wins) / n_total * 100
    avg_pnl  = sum(t["pnl_pct"] for t in closed) / n_total
    avg_dur  = sum(t["duration_days"] for t in closed) / n_total
    best     = max(closed, key=lambda t: t["pnl_pct"])
    worst    = min(closed, key=lambda t: t["pnl_pct"])
    eq = 1.0
    for t in closed:
        eq *= (1.0 + t["pnl_pct"] / 100.0)
    cum_pnl  = (eq - 1.0) * 100.0
    bh_pnl   = (df["close"].iloc[-1] / df["close"].iloc[0] - 1.0) * 100.0

    cells = [
        ("Trades",         f"{n_total}",                  COL_TEXT),
        ("Win rate",       f"{win_rate:.0f}%",            COL_BULL if win_rate >= 50 else COL_NEUTRAL if win_rate >= 40 else COL_BEAR),
        ("Avg P&L",        f"{avg_pnl:+.2f}%",           COL_BULL if avg_pnl > 0 else COL_BEAR),
        ("Avg duration",   f"{avg_dur:.0f}d",             COL_TEXT),
        ("Best trade",     f"{best['pnl_pct']:+.1f}%",   COL_BULL),
        ("Worst trade",    f"{worst['pnl_pct']:+.1f}%",  COL_BEAR),
        ("Strategy total", f"{cum_pnl:+.1f}%",           COL_BULL if cum_pnl > 0 else COL_BEAR),
        ("Buy & hold",     f"{bh_pnl:+.1f}%",            COL_BULL if bh_pnl > 0 else COL_BEAR),
    ]
    items = "".join(
        f'<div style="flex:1;padding:11px 14px;border-right:1px solid {COL_BORDER}">'
        f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
        f'letter-spacing:0.8px;margin-bottom:3px">{lbl}</div>'
        f'<div style="color:{col};font-size:16px;font-weight:600;'
        f'font-family:monospace">{val}</div></div>'
        for lbl, val, col in cells
    )
    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-radius:4px;display:flex;overflow:hidden">{items}</div>'
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Diversitas Pro v3",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        f"""<style>
        div.block-container {{padding-top:0.8rem;padding-bottom:0.8rem;max-width:1600px}}
        .stApp {{background:{COL_BG}}}
        section.main {{background:{COL_BG}}}
        section[data-testid="stSidebar"] {{
            background:{COL_PANEL};border-right:1px solid {COL_BORDER}}}
        h1,h2,h3,h4 {{color:{COL_TEXT};font-weight:600}}
        </style>""",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            f"<div style='color:{COL_TEXT};font-size:17px;font-weight:700;"
            f"letter-spacing:2px;margin-bottom:0'>DIVERSITAS</div>"
            f"<div style='color:{COL_DIM};font-size:10px;letter-spacing:1.5px;"
            f"text-transform:uppercase;margin-bottom:16px'>Pro v3 · Live</div>",
            unsafe_allow_html=True,
        )
        symbol = st.selectbox("Symbol",
                               options=list(DEFAULT_CONFIG.symbol_map.keys()), index=0)
        bars = st.slider("History (bars)", 400, 2000, 1000, 100)
        use_btc_filter = st.checkbox("BTC cross-asset filter",
                                     value=(symbol != "BTC"),
                                     help="Disable on BTC itself.")
        auto_refresh = st.checkbox("Auto-refresh (60 s)", value=True)
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

    try:
        cfg, daily, result = _run(symbol, bars, use_btc_filter)
    except Exception as e:
        st.error(f"Data load failed for {symbol}: {e}")
        st.stop()

    s  = result.summary
    df = result.df

    # ── compact status bar ────────────────────────────────────────────────────
    st.markdown(_status_bar(s, symbol, use_btc_filter), unsafe_allow_html=True)

    # ── main chart (full width) ───────────────────────────────────────────────
    st.plotly_chart(_build_price_chart(df, symbol), use_container_width=True)

    # ── detail row: status + conviction breakdown ─────────────────────────────
    left, right = st.columns([4, 6], gap="medium")

    with left:
        st.markdown(_section_label("Status detail"), unsafe_allow_html=True)
        ma_colour = (COL_BEAR if s["bear_market"]
                     else COL_NEUTRAL if s["ma200_status"] == "BELOW"
                     else COL_BULL)
        thr_colour = (COL_BEAR if s["threshold"] >= 70
                      else COL_BULL if s["threshold"] <= 55 else COL_NEUTRAL)
        tl_colour  = COL_BULL if s["track_rising"] else COL_BEAR
        tq         = s["trend_quality_pct"]
        vol_label  = ("HIGH" if s["high_vol_regime"] else
                      "LOW"  if s["low_vol_regime"]  else "NORMAL")
        vol_colour = (COL_BEAR if s["high_vol_regime"] else
                      COL_BULL if s["low_vol_regime"]  else COL_DIM)
        detail_rows = [
            _row("200 MA",            s["ma200_status"],                  ma_colour),
            _row("Conviction / Thr",  f'{s["conviction"]:.1f}  ·  {s["threshold"]:.0f}', thr_colour),
            _row("Trackline",         f'${s["trackline"]:,.0f}  {"RISING" if s["track_rising"] else "FALLING"}', tl_colour),
            _row("Trend quality",     f"{tq:.0f}%",  COL_BULL if tq >= 60 else COL_NEUTRAL if tq >= 40 else COL_BEAR),
            _row("Annual vol",        f'{s["annual_vol"]:.1f}%  {vol_label}',  vol_colour),
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

        warnings_list = []
        if s["blowoff"]:
            warnings_list.append("BLOW-OFF top")
        if s["vol_shock"]:
            warnings_list.append("Volatility shock")
        if warnings_list:
            st.markdown(
                f'<div style="background:{COL_PANEL};border:1px solid {COL_BEAR};'
                f'border-radius:4px;padding:9px 14px;margin-top:8px;'
                f'color:{COL_BEAR};font-size:12px;font-weight:700;'
                f'letter-spacing:0.5px;text-transform:uppercase">'
                f'{"  ·  ".join(warnings_list)}</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<div style="color:{COL_VERY_DIM};font-size:10px;margin-top:8px;'
            f'font-family:monospace">Last bar · {s["time"]:%Y-%m-%d %H:%M UTC}</div>',
            unsafe_allow_html=True,
        )

    with right:
        st.plotly_chart(_build_breakdown_chart(df), use_container_width=True)

    # ── performance summary bar ───────────────────────────────────────────────
    st.markdown(_section_label("Performance · loaded window"), unsafe_allow_html=True)
    trades = _build_trade_ledger(df)
    st.markdown(_render_signal_stats(trades, df), unsafe_allow_html=True)

    # ── vol / alloc mini chart ────────────────────────────────────────────────
    st.plotly_chart(_build_vol_alloc_chart(df), use_container_width=True)

    # ── trade ledger ──────────────────────────────────────────────────────────
    st.markdown(_section_label("Trade ledger · last 12"), unsafe_allow_html=True)
    st.markdown(_render_trade_ledger(trades, n=12), unsafe_allow_html=True)
    st.markdown(
        f'<div style="color:{COL_VERY_DIM};font-size:10px;margin-top:8px;'
        f'font-family:monospace;text-align:right">'
        f'Naive long-flat backtest · no slippage / fees</div>',
        unsafe_allow_html=True,
    )

    if auto_refresh:
        st_autorefresh(interval=60_000, key="auto_refresh_tick")


if __name__ == "__main__":
    main()
