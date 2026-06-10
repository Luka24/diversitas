"""Live Streamlit dashboard for Diversitas Pro v3.

Run:
    streamlit run diversitas/dashboard.py

Features:
  - Symbol selector (BTC / ETH / SOL / ...)
  - Live price chart with trackline (color = trend), 200 MA, dots, BULL/BEAR labels
  - Background tint by display state (BULL green / HEDGED amber / BEAR red)
  - Status panel mirroring the Pine table
  - Conviction breakdown stacked bar
  - Volatility & allocation panel
  - Manual + automatic refresh
"""
from __future__ import annotations
import sys
from pathlib import Path

# Allow `streamlit run full/diversitas/dashboard.py` to work — Streamlit runs
# the file as __main__, so we add two sys.path entries:
#   1. `DIVERSITAS/`  → so `from shared import ...` resolves
#   2. `DIVERSITAS/full/` → so `from diversitas import ...` resolves to THIS variant
_VARIANT_ROOT = Path(__file__).resolve().parent.parent          # DIVERSITAS/full
_PROJECT_ROOT = _VARIANT_ROOT.parent                            # DIVERSITAS
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


# --------- caching ---------

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


# --------- plotting helpers ---------
#
# Muted, GitHub-dark-inspired palette. Goal: data first, decoration second.
# Hue carries meaning (green = bull, red = bear, amber = hedged, blue = info)
# but saturation/luminance are dialled back so nothing screams.

COL_BULL = "#3FB950"      # muted green
COL_BEAR = "#E5534B"      # muted red
COL_HEDGED = "#D29922"    # warm amber
COL_ACCENT = "#58A6FF"    # info blue — secondary lines only
COL_MA = "#8B949E"        # 200 MA: neutral grey, low priority
COL_BG = "#0D1117"        # deep page bg
COL_PANEL = "#161B22"     # card bg
COL_BORDER = "#21262D"    # divider lines
COL_GRID = "#1F262E"      # chart grid (barely visible)
COL_TEXT = "#E6EDF3"      # primary text
COL_DIM = "#7D8590"       # secondary text
COL_VERY_DIM = "#484F58"  # tertiary text


def _state_colour(code: int, alpha: float = 1.0) -> str:
    if code == S_BULL:
        rgb = (63, 185, 80)
    elif code == S_NEUTRAL:
        rgb = (210, 153, 34)
    else:
        rgb = (229, 83, 75)
    return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha})"


def _build_price_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.78, 0.22], vertical_spacing=0.04,
        specs=[[{"type": "xy"}], [{"type": "xy"}]],
    )

    # --- Background bands by display_state (very subtle) ---
    ds = df["display_state"]
    change = ds != ds.shift(1)
    grp = change.cumsum()
    for _, seg in df.groupby(grp):
        state = int(seg["display_state"].iloc[0])
        fig.add_vrect(
            x0=seg.index[0], x1=seg.index[-1],
            fillcolor=_state_colour(state, alpha=0.045),
            line_width=0, layer="below", row=1, col=1,
        )

    # --- Price candles (muted, no separate fill colour) ---
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color=COL_BULL, decreasing_line_color=COL_BEAR,
        increasing_fillcolor=COL_BULL, decreasing_fillcolor=COL_BEAR,
        line=dict(width=1),
        name="Price", showlegend=False,
    ), row=1, col=1)

    # --- Trackline (single trace, colour varies via marker line — simpler) ---
    rising = df["track_rising"].fillna(False).to_numpy()
    tl = df["trackline"].to_numpy()
    xs = df.index
    seg_start = 0
    first = True
    for i in range(1, len(df) + 1):
        if i == len(df) or rising[i] != rising[seg_start]:
            colour = COL_BULL if rising[seg_start] else COL_BEAR
            end = i + (0 if i == len(df) else 1)
            fig.add_trace(go.Scatter(
                x=xs[seg_start:end], y=tl[seg_start:end],
                mode="lines", line=dict(color=colour, width=1.8),
                name="Trackline", showlegend=first,
                legendgroup="trackline",
                hovertemplate="Trackline %{y:,.2f}<extra></extra>",
            ), row=1, col=1)
            first = False
            seg_start = i

    # --- 200 MA (neutral grey, low visual weight) ---
    fig.add_trace(go.Scatter(
        x=df.index, y=df["sma200"],
        mode="lines", line=dict(color=COL_MA, width=1, dash="dot"),
        name="200 MA",
        hovertemplate="200 MA %{y:,.2f}<extra></extra>",
    ), row=1, col=1)

    # --- Dots (smaller, hollow — less screaming) ---
    green = df[df["green_dot"]]
    red = df[df["red_dot"]]
    if len(green):
        fig.add_trace(go.Scatter(
            x=green.index, y=green["low"] * 0.985,
            mode="markers",
            marker=dict(color=COL_BULL, size=5, symbol="circle",
                        line=dict(color=COL_BG, width=0.5)),
            name="Green dot", hovertemplate="GREEN %{x|%Y-%m-%d}<extra></extra>",
        ), row=1, col=1)
    if len(red):
        fig.add_trace(go.Scatter(
            x=red.index, y=red["high"] * 1.015,
            mode="markers",
            marker=dict(color=COL_BEAR, size=5, symbol="circle",
                        line=dict(color=COL_BG, width=0.5)),
            name="Red dot", hovertemplate="RED %{x|%Y-%m-%d}<extra></extra>",
        ), row=1, col=1)

    # --- BULL / BEAR transitions: small triangle marker, no arrow ---
    changes = df[df["signal_changed"]]
    bulls = changes[changes["signal_state"] == S_BULL]
    bears = changes[changes["signal_state"] == S_BEAR]
    if len(bulls):
        fig.add_trace(go.Scatter(
            x=bulls.index, y=bulls["low"] * 0.96,
            mode="markers+text",
            marker=dict(color=COL_BULL, size=10, symbol="triangle-up",
                        line=dict(color=COL_BG, width=1)),
            text=["BULL"] * len(bulls), textposition="bottom center",
            textfont=dict(color=COL_BULL, size=10, family="monospace"),
            name="BULL signal", legendgroup="signals",
            hovertemplate="BULL %{x|%Y-%m-%d}<br>close %{customdata:,.0f}<extra></extra>",
            customdata=bulls["close"],
        ), row=1, col=1)
    if len(bears):
        fig.add_trace(go.Scatter(
            x=bears.index, y=bears["high"] * 1.04,
            mode="markers+text",
            marker=dict(color=COL_BEAR, size=10, symbol="triangle-down",
                        line=dict(color=COL_BG, width=1)),
            text=["BEAR"] * len(bears), textposition="top center",
            textfont=dict(color=COL_BEAR, size=10, family="monospace"),
            name="BEAR signal", legendgroup="signals",
            hovertemplate="BEAR %{x|%Y-%m-%d}<br>close %{customdata:,.0f}<extra></extra>",
            customdata=bears["close"],
        ), row=1, col=1)

    # --- Conviction subplot (filled area, threshold dashed) ---
    fig.add_trace(go.Scatter(
        x=df.index, y=df["conviction"], mode="lines",
        line=dict(color=COL_ACCENT, width=1.6),
        fill="tozeroy", fillcolor="rgba(88,166,255,0.12)",
        name="Conviction",
        hovertemplate="Conviction %{y:.1f}<extra></extra>",
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["dynamic_threshold"], mode="lines",
        line=dict(color=COL_HEDGED, width=1, dash="dash"),
        name="Threshold",
        hovertemplate="Threshold %{y:.0f}<extra></extra>",
    ), row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=720, margin=dict(l=10, r=20, t=50, b=10),
        title=dict(
            text=f"<span style='color:{COL_TEXT};font-size:18px;font-weight:600'>"
                 f"{symbol}/USD</span>"
                 f"<span style='color:{COL_DIM};font-size:13px'>"
                 f"   ·   Diversitas Pro v3</span>",
            x=0.01, y=0.97,
        ),
        paper_bgcolor=COL_BG, plot_bgcolor=COL_BG,
        font=dict(color=COL_TEXT, family="-apple-system, system-ui, sans-serif"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=COL_DIM),
        ),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        hoverlabel=dict(bgcolor=COL_PANEL, bordercolor=COL_BORDER,
                        font=dict(color=COL_TEXT, size=11)),
    )
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10),
                     title_text="Price (USD)",
                     title_font=dict(color=COL_DIM, size=10), row=1, col=1)
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10),
                     title_text="Conviction",
                     title_font=dict(color=COL_DIM, size=10),
                     range=[0, 100], row=2, col=1)
    fig.update_xaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), row=1, col=1)
    fig.update_xaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), row=2, col=1)
    return fig


def _build_breakdown_chart(df: pd.DataFrame) -> go.Figure:
    """Stacked area of the 5 conviction components — easier to read than bars."""
    win = df.tail(120)
    fig = go.Figure()
    parts = [
        ("Trend (30)",    "trend_score",  "#3FB950"),  # bull green
        ("Momentum (25)", "mom_score",    "#58A6FF"),  # accent blue
        ("Macro (20)",    "macro_score",  "#9D7CD8"),  # muted purple
        ("Volume (15)",   "vol_score",    "#D29922"),  # warm amber
        ("DD brake (10)", "dd_score",     "#7D8590"),  # neutral grey
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
    fig.update_layout(
        template="plotly_dark",
        height=280, margin=dict(l=10, r=20, t=40, b=10),
        title=dict(
            text=f"<span style='color:{COL_DIM};font-size:12px;"
                 f"text-transform:uppercase;letter-spacing:1px'>"
                 f"Conviction breakdown · last 120 bars</span>",
            x=0.01, y=0.96,
        ),
        paper_bgcolor=COL_BG, plot_bgcolor=COL_BG,
        font=dict(color=COL_TEXT, family="-apple-system, system-ui, sans-serif"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=COL_DIM),
        ),
        hoverlabel=dict(bgcolor=COL_PANEL, bordercolor=COL_BORDER,
                        font=dict(color=COL_TEXT, size=11)),
    )
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10), range=[0, 100])
    fig.update_xaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_DIM, size=10))
    return fig


def _hero_card(label: str, value: str, colour: str = None, sub: str = None) -> str:
    """Big-number 'hero' card for the top row.

    Colour is applied to a thin top accent bar (not the value text itself),
    so the colour codes the meaning without shouting.
    """
    accent = colour or COL_DIM
    val_color = colour or COL_TEXT
    sub_html = (
        f'<div style="color:{COL_DIM};font-size:11px;margin-top:2px;'
        f'font-family:monospace">{sub}</div>'
    ) if sub else ""
    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-top:2px solid {accent};border-radius:4px;'
        f'padding:12px 14px;margin-bottom:8px;">'
        f'<div style="color:{COL_DIM};font-size:10px;'
        f'text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">{label}</div>'
        f'<div style="color:{val_color};font-size:20px;font-weight:600;'
        f'font-family:monospace">{value}</div>'
        f'{sub_html}'
        f"</div>"
    )


def _row(label: str, value: str, value_colour: str = None) -> str:
    """A label : value row inside the detail panel — no colour blocks,
    just typographic separation."""
    vc = value_colour or COL_TEXT
    return (
        f'<div style="display:flex;justify-content:space-between;'
        f'padding:8px 0;border-bottom:1px solid {COL_BORDER};">'
        f'<span style="color:{COL_DIM};font-size:12px">{label}</span>'
        f'<span style="color:{vc};font-size:13px;font-weight:500;'
        f'font-family:monospace">{value}</span>'
        f"</div>"
    )


def _build_trade_ledger(df: pd.DataFrame) -> list[dict]:
    """Convert the signal_state series into completed trades (BULL→BEAR pairs)
    plus the currently-open position if any.

    Each entry: dict with entry_date, exit_date, entry_px, exit_px, pnl_pct,
    duration_days, entry_conv, signal_at_entry, open (bool).
    """
    changes = df[df["signal_changed"]]
    trades: list[dict] = []
    open_entry = None
    for ts, row in changes.iterrows():
        sig = int(row["signal_state"])
        if sig == S_BULL:
            open_entry = {
                "entry_date": ts, "entry_px": float(row["close"]),
                "entry_conv": float(row["conviction"]),
                "entry_thr": float(row["dynamic_threshold"]),
            }
        elif sig == S_BEAR and open_entry is not None:
            duration = (ts - open_entry["entry_date"]).days
            pnl = (row["close"] / open_entry["entry_px"] - 1.0) * 100.0
            trades.append({
                **open_entry,
                "exit_date": ts, "exit_px": float(row["close"]),
                "duration_days": duration, "pnl_pct": pnl,
                "open": False,
            })
            open_entry = None
    # Currently open trade
    last = df.iloc[-1]
    if open_entry is not None and int(last["signal_state"]) == S_BULL:
        duration = (last.name - open_entry["entry_date"]).days
        pnl = (last["close"] / open_entry["entry_px"] - 1.0) * 100.0
        trades.append({
            **open_entry,
            "exit_date": last.name, "exit_px": float(last["close"]),
            "duration_days": duration, "pnl_pct": pnl,
            "open": True,
        })
    return trades


def _render_trade_ledger(trades: list[dict], n: int = 12) -> str:
    """HTML table of recent trades — colour-coded by P&L, with badges for state."""
    if not trades:
        return (
            f'<div style="color:{COL_DIM};padding:24px;text-align:center;'
            f'background:{COL_PANEL};border:1px solid {COL_BORDER};border-radius:6px">'
            f"No completed trades in the loaded window.</div>"
        )

    show = trades[-n:]
    rows = []
    for t in show:
        is_open = t["open"]
        pnl = t["pnl_pct"]
        pnl_colour = COL_BULL if pnl > 0 else COL_BEAR if pnl < 0 else COL_DIM
        pnl_txt = f"{pnl:+.2f}%"
        status_badge = (
            f'<span style="background:{COL_ACCENT}22;color:{COL_ACCENT};'
            f'padding:2px 8px;border-radius:3px;font-size:10px;'
            f'font-weight:600;letter-spacing:0.5px">OPEN</span>'
        ) if is_open else (
            f'<span style="color:{COL_DIM};font-size:11px">closed</span>'
        )
        exit_date_txt = (
            "—" if is_open else t["exit_date"].strftime("%Y-%m-%d")
        )
        rows.append(
            f'<tr style="border-bottom:1px solid {COL_BORDER}">'
            f'<td style="padding:10px 12px;color:{COL_TEXT};font-family:monospace;'
            f'font-size:12px">{t["entry_date"].strftime("%Y-%m-%d")}</td>'
            f'<td style="padding:10px 12px;color:{COL_DIM};font-family:monospace;'
            f'font-size:12px">{exit_date_txt}</td>'
            f'<td style="padding:10px 12px;color:{COL_TEXT};font-family:monospace;'
            f'font-size:12px;text-align:right">${t["entry_px"]:,.2f}</td>'
            f'<td style="padding:10px 12px;color:{COL_DIM};font-family:monospace;'
            f'font-size:12px;text-align:right">${t["exit_px"]:,.2f}</td>'
            f'<td style="padding:10px 12px;color:{COL_DIM};font-family:monospace;'
            f'font-size:12px;text-align:right">{t["duration_days"]}d</td>'
            f'<td style="padding:10px 12px;color:{COL_DIM};font-family:monospace;'
            f'font-size:12px;text-align:right">{t["entry_conv"]:.0f}/{t["entry_thr"]:.0f}</td>'
            f'<td style="padding:10px 12px;color:{pnl_colour};font-family:monospace;'
            f'font-size:13px;font-weight:600;text-align:right">{pnl_txt}</td>'
            f'<td style="padding:10px 12px;text-align:center">{status_badge}</td>'
            f"</tr>"
        )
    header_cells = [
        ("ENTRY", "left"), ("EXIT", "left"),
        ("ENTRY PX", "right"), ("EXIT PX", "right"),
        ("DUR", "right"), ("CONV/THR", "right"),
        ("P&L", "right"), ("STATUS", "center"),
    ]
    header = "".join(
        f'<th style="padding:8px 12px;color:{COL_DIM};font-size:10px;'
        f'text-transform:uppercase;letter-spacing:1px;text-align:{align};'
        f'border-bottom:1px solid {COL_BORDER};font-weight:600">{label}</th>'
        for label, align in header_cells
    )
    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-radius:6px;overflow:hidden">'
        f'<table style="width:100%;border-collapse:collapse">'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        f"</table></div>"
    )


def _render_signal_stats(trades: list[dict], df: pd.DataFrame) -> str:
    """Aggregate stats: total trades, win rate, avg duration, avg PnL,
    best/worst trade, current streak."""
    closed = [t for t in trades if not t["open"]]
    n_total = len(closed)
    if n_total == 0:
        return (
            f'<div style="color:{COL_DIM};padding:14px;background:{COL_PANEL};'
            f'border:1px solid {COL_BORDER};border-radius:6px;text-align:center">'
            f"No completed trades yet.</div>"
        )
    wins = [t for t in closed if t["pnl_pct"] > 0]
    losses = [t for t in closed if t["pnl_pct"] <= 0]
    win_rate = len(wins) / n_total * 100
    avg_pnl = sum(t["pnl_pct"] for t in closed) / n_total
    avg_dur = sum(t["duration_days"] for t in closed) / n_total
    best = max(closed, key=lambda t: t["pnl_pct"])
    worst = min(closed, key=lambda t: t["pnl_pct"])
    # Cumulative compounded equity (BULL-only)
    eq = 1.0
    for t in closed:
        eq *= (1.0 + t["pnl_pct"] / 100.0)
    cum_pnl = (eq - 1.0) * 100.0
    cum_colour = COL_BULL if cum_pnl > 0 else COL_BEAR

    # Buy-and-hold over the loaded window
    bh_first = df["close"].iloc[0]
    bh_last = df["close"].iloc[-1]
    bh_pnl = (bh_last / bh_first - 1.0) * 100.0
    bh_colour = COL_BULL if bh_pnl > 0 else COL_BEAR

    pnl_colour = COL_BULL if avg_pnl > 0 else COL_BEAR
    wr_colour = COL_BULL if win_rate >= 50 else COL_HEDGED if win_rate >= 40 else COL_BEAR

    cells = [
        ("Trades", f"{n_total}", COL_TEXT),
        ("Win rate", f"{win_rate:.0f}%", wr_colour),
        ("Avg P&L", f"{avg_pnl:+.2f}%", pnl_colour),
        ("Avg duration", f"{avg_dur:.0f}d", COL_TEXT),
        ("Best", f"{best['pnl_pct']:+.1f}%", COL_BULL),
        ("Worst", f"{worst['pnl_pct']:+.1f}%", COL_BEAR),
        ("Strategy total", f"{cum_pnl:+.1f}%", cum_colour),
        ("Buy & hold", f"{bh_pnl:+.1f}%", bh_colour),
    ]
    items = "".join(
        f'<div style="flex:1;padding:12px 14px;border-right:1px solid {COL_BORDER}">'
        f'<div style="color:{COL_DIM};font-size:10px;text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:3px">{label}</div>'
        f'<div style="color:{colour};font-size:16px;font-weight:600;'
        f'font-family:monospace">{value}</div></div>'
        for label, value, colour in cells
    )
    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-radius:6px;display:flex;overflow:hidden">{items}</div>'
    )


def _build_vol_alloc_chart(df: pd.DataFrame) -> go.Figure:
    """Bottom mini-chart: annual vol % + final allocation %.
    Two-line panel that complements the breakdown chart."""
    win = df.tail(240).copy()
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(
        x=win.index, y=win["annual_vol"], mode="lines",
        line=dict(color=COL_HEDGED, width=1.5),
        name="Annual vol %",
        hovertemplate="Vol %{y:.1f}%<extra></extra>",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=win.index, y=win["final_alloc"], mode="lines",
        line=dict(color=COL_ACCENT, width=1.5),
        fill="tozeroy", fillcolor="rgba(88,166,255,0.10)",
        name="Allocation %",
        hovertemplate="Alloc %{y:.1f}%<extra></extra>",
    ), secondary_y=True)

    fig.update_layout(
        template="plotly_dark",
        height=240, margin=dict(l=10, r=20, t=40, b=10),
        title=dict(
            text=f"<span style='color:{COL_DIM};font-size:12px;"
                 f"text-transform:uppercase;letter-spacing:1px'>"
                 f"Volatility & allocation · last 240 bars</span>",
            x=0.01, y=0.94,
        ),
        paper_bgcolor=COL_BG, plot_bgcolor=COL_BG,
        font=dict(color=COL_TEXT, family="-apple-system, system-ui, sans-serif"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=COL_DIM),
        ),
        hoverlabel=dict(bgcolor=COL_PANEL, bordercolor=COL_BORDER,
                        font=dict(color=COL_TEXT, size=11)),
        hovermode="x unified",
    )
    fig.update_yaxes(gridcolor=COL_GRID, zerolinecolor=COL_GRID,
                     tickfont=dict(color=COL_HEDGED, size=10),
                     title_text="Vol %", title_font=dict(color=COL_HEDGED, size=10),
                     secondary_y=False)
    fig.update_yaxes(showgrid=False,
                     tickfont=dict(color=COL_ACCENT, size=10),
                     title_text="Alloc %", title_font=dict(color=COL_ACCENT, size=10),
                     range=[0, 100], secondary_y=True)
    fig.update_xaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10))
    return fig


# --------- main app ---------

def main() -> None:
    st.set_page_config(
        page_title="Diversitas Pro v3 — Live",
        page_icon=" ",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        f"""
        <style>
        div.block-container {{ padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1400px; }}
        section.main {{ background: {COL_BG}; }}
        h1, h2, h3, h4 {{ color: {COL_TEXT}; font-weight: 600; }}
        .stApp {{ background: {COL_BG}; }}
        section[data-testid="stSidebar"] {{ background: {COL_PANEL};
            border-right: 1px solid {COL_BORDER}; }}
        /* tighter dataframe */
        .stDataFrame {{ font-size: 12px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            f"<div style='color:{COL_TEXT};font-size:18px;font-weight:700;"
            f"letter-spacing:2px;margin-bottom:0px'>DIVERSITAS</div>"
            f"<div style='color:{COL_DIM};font-size:11px;letter-spacing:1px;"
            f"text-transform:uppercase;margin-bottom:18px'>Pro v3 · Live</div>",
            unsafe_allow_html=True,
        )
        symbol = st.selectbox(
            "Symbol",
            options=list(DEFAULT_CONFIG.symbol_map.keys()),
            index=0,
        )
        bars = st.slider(
            "History (daily bars)",
            min_value=400, max_value=2000, value=1000, step=100,
        )
        use_btc_filter = st.checkbox(
            "BTC cross-asset filter",
            value=(symbol != "BTC"),
            help="Disable on BTC itself.",
        )
        auto_refresh = st.checkbox("Auto-refresh (60 s)", value=True)
        refresh_now = st.button("Refresh now", type="primary", use_container_width=True)
        if refresh_now:
            _load_candles.clear()
            _load_btc.clear()
            _run.clear()

        st.divider()
        st.markdown(
            f"<div style='color:{COL_VERY_DIM};font-size:10px;line-height:1.5'>"
            f"Data · Binance primary, yfinance fallback<br>"
            f"Cache TTL · 60 s</div>",
            unsafe_allow_html=True,
        )

    # --- load data ---
    try:
        cfg, daily, result = _run(symbol, bars, use_btc_filter)
    except Exception as e:  # noqa: BLE001
        st.error(f"Failed to load data for {symbol}: {e}")
        st.stop()

    s = result.summary
    df = result.df

    # --- top hero row: 5 cards, all uniform — colour as accent only ---
    sig_colour = COL_BULL if s["signal"] == "BULL" else COL_BEAR
    regime_colour = {
        "BULL": COL_BULL, "HEDGED": COL_HEDGED, "BEAR": COL_BEAR,
    }[s["regime"]]
    dist_colour = COL_BULL if s["dist_pct"] > 0 else COL_BEAR
    alloc_val = s["final_alloc"] if not pd.isna(s["final_alloc"]) else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(_hero_card(
        "Signal", s["signal"], sig_colour,
        sub=f"since {s['time']:%Y-%m-%d}",
    ), unsafe_allow_html=True)
    c2.markdown(_hero_card(
        "Regime", s["regime"], regime_colour,
    ), unsafe_allow_html=True)
    c3.markdown(_hero_card(
        "Close", f"${s['close']:,.2f}",
        sub=f"{symbol}/USD",
    ), unsafe_allow_html=True)
    c4.markdown(_hero_card(
        "Price vs Trackline", f"{s['dist_pct']:+.2f}%", dist_colour,
        sub=f"TL ${s['trackline']:,.0f}",
    ), unsafe_allow_html=True)
    c5.markdown(_hero_card(
        "Allocation", f"{alloc_val:.1f}%", COL_ACCENT,
        sub=f"conv {s['conviction']:.0f} / {s['threshold']:.0f}",
    ), unsafe_allow_html=True)

    # --- main chart ---
    st.plotly_chart(_build_price_chart(df, symbol), use_container_width=True)

    # --- detail row: status panel + breakdown ---
    left, right = st.columns([1, 2], gap="medium")

    with left:
        st.markdown(
            f"<div style='color:{COL_DIM};font-size:11px;"
            f"text-transform:uppercase;letter-spacing:1.5px;"
            f"margin:6px 0 8px 0'>Status detail</div>",
            unsafe_allow_html=True,
        )
        rows = []

        # 200 MA
        ma_colour = (COL_BEAR if s["bear_market"]
                     else COL_HEDGED if s["ma200_status"] == "BELOW"
                     else COL_BULL)
        rows.append(_row("200 MA", s["ma200_status"], ma_colour))

        # Threshold / conviction
        thr_colour = (COL_BEAR if s["threshold"] >= 70
                      else COL_BULL if s["threshold"] <= 55
                      else COL_HEDGED)
        rows.append(_row(
            "Threshold / Conviction",
            f"{s['threshold']:.0f}  ·  {s['conviction']:.1f}",
            thr_colour,
        ))

        # Trackline direction
        tl_colour = COL_BULL if s["track_rising"] else COL_BEAR
        tl_dir = "RISING" if s["track_rising"] else "FALLING"
        rows.append(_row("Trackline", f"${s['trackline']:,.0f} {tl_dir}", tl_colour))

        # Trend quality
        tq = s["trend_quality_pct"]
        tq_colour = (COL_BULL if tq >= 60 else COL_HEDGED if tq >= 40 else COL_BEAR)
        rows.append(_row("Trend quality", f"{tq:.0f}%", tq_colour))

        # Vol regime
        vol_label = "HIGH" if s["high_vol_regime"] else "LOW" if s["low_vol_regime"] else "NORMAL"
        vol_colour = (COL_BEAR if s["high_vol_regime"]
                      else COL_BULL if s["low_vol_regime"]
                      else COL_DIM)
        rows.append(_row("Volatility", f"{s['annual_vol']:.1f}%  {vol_label}", vol_colour))

        # BTC filter (only when used)
        if use_btc_filter:
            btc_status = "BTC BULL" if s["btc_bull"] else "BTC BEAR"
            btc_colour = COL_BULL if s["btc_bull"] else COL_BEAR
            rows.append(_row("BTC filter", btc_status, btc_colour))

        st.markdown(
            f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
            f'border-radius:6px;padding:4px 16px;">'
            + "".join(rows) +
            f"</div>",
            unsafe_allow_html=True,
        )

        # Warnings (only when active)
        warnings_list = []
        if s["blowoff"]:
            warnings_list.append("BLOW-OFF top")
        if s["vol_shock"]:
            warnings_list.append("Volatility shock")
        if warnings_list:
            st.markdown(
                f'<div style="background:{COL_PANEL};'
                f'border:1px solid {COL_BEAR};border-radius:6px;'
                f'padding:10px 14px;margin-top:8px;'
                f'color:{COL_BEAR};font-size:12px;font-weight:600;'
                f'letter-spacing:0.5px;text-transform:uppercase">'
                f'  {" · ".join(warnings_list)}'
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<div style="color:{COL_VERY_DIM};font-size:10px;'
            f'margin-top:10px;font-family:monospace">'
            f'Last bar  ·  {s["time"]:%Y-%m-%d %H:%M UTC}'
            f"</div>",
            unsafe_allow_html=True,
        )

    with right:
        st.plotly_chart(_build_breakdown_chart(df), use_container_width=True)

    # ===== BOTTOM HALF: trade history =====

    # --- Signal stats summary bar ---
    trades = _build_trade_ledger(df)
    st.markdown(
        f"<div style='color:{COL_DIM};font-size:11px;"
        f"text-transform:uppercase;letter-spacing:1.5px;"
        f"margin:24px 0 8px 0'>Performance summary · loaded window</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_render_signal_stats(trades, df), unsafe_allow_html=True)

    # --- Volatility & allocation history (full width) ---
    st.plotly_chart(_build_vol_alloc_chart(df), use_container_width=True)

    # --- Trade ledger (entry/exit pairs with P&L) ---
    st.markdown(
        f"<div style='color:{COL_DIM};font-size:11px;"
        f"text-transform:uppercase;letter-spacing:1.5px;"
        f"margin:20px 0 8px 0'>Trade ledger · last 12</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_render_trade_ledger(trades, n=12), unsafe_allow_html=True)

    st.markdown(
        f'<div style="color:{COL_VERY_DIM};font-size:10px;margin-top:10px;'
        f'font-family:monospace;text-align:right">'
        f"Naive long-flat backtest · no slippage / fees"
        f"</div>",
        unsafe_allow_html=True,
    )

    # --- non-blocking auto-refresh ---
    # st_autorefresh schedules a rerun every `interval` ms on the client side
    # without blocking the Python thread. Keeps the UI responsive to clicks.
    if auto_refresh:
        st_autorefresh(interval=60_000, key="auto_refresh_tick")


if __name__ == "__main__":
    main()
