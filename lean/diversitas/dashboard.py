"""Live Streamlit dashboard for Diversitas Lean.

Run:
    streamlit run lean/diversitas/dashboard.py

Lean dashboard is intentionally simpler than the Full one — there is no
conviction breakdown because Lean has no conviction score. Instead the
gate panel shows each entry condition as PASS/FAIL.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

# Add project subdir to sys.path so `from diversitas...` works when this file
# is invoked as `streamlit run lean/diversitas/dashboard.py`.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from diversitas.config import LeanConfig, DEFAULT_CONFIG
from diversitas.data_source import fetch_candles, fetch_btc_daily
from diversitas.strategy import run_strategy, S_BULL, S_NEUTRAL, S_BEAR


# ---------- palette (same as Full for visual consistency) ----------

COL_BULL = "#3FB950"
COL_BEAR = "#E5534B"
COL_HEDGED = "#D29922"
COL_ACCENT = "#58A6FF"
COL_MA = "#8B949E"
COL_BG = "#0D1117"
COL_PANEL = "#161B22"
COL_BORDER = "#21262D"
COL_GRID = "#1F262E"
COL_TEXT = "#E6EDF3"
COL_DIM = "#7D8590"
COL_VERY_DIM = "#484F58"


def _state_colour(code: int) -> str:
    if code == S_BULL:
        return COL_BULL
    if code == S_NEUTRAL:
        return COL_HEDGED
    return COL_BEAR


# ---------- caching ----------

@st.cache_data(ttl=60, show_spinner=False)
def _load_candles(symbol: str, bars: int) -> pd.DataFrame:
    return fetch_candles(symbol, "1d", bars=bars)


@st.cache_data(ttl=60, show_spinner=False)
def _load_btc(bars: int) -> pd.DataFrame:
    return fetch_btc_daily(bars=bars)


@st.cache_data(ttl=60, show_spinner=False)
def _run(symbol: str, bars: int, use_btc_filter: bool):
    cfg = LeanConfig(use_btc_filter=use_btc_filter)
    daily = _load_candles(symbol, bars)
    btc = _load_btc(bars) if use_btc_filter else None
    return cfg, daily, run_strategy(daily, btc_daily=btc, config=cfg)


# ---------- chart ----------

def _build_price_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.80, 0.20], vertical_spacing=0.04,
    )

    # Background bands by display_state — very subtle
    ds = df["display_state"]
    grp = (ds != ds.shift(1)).cumsum()
    for _, seg in df.groupby(grp):
        st_code = int(seg["display_state"].iloc[0])
        rgb = {S_BULL: (63, 185, 80), S_NEUTRAL: (210, 153, 34),
               S_BEAR: (229, 83, 75)}[st_code]
        fig.add_vrect(
            x0=seg.index[0], x1=seg.index[-1],
            fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.045)",
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

    # Trackline — segmented by track_rising_window (slope filter that gates entries)
    rising = df["track_rising_window"].fillna(False).to_numpy()
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
                name="Trackline (slope filter)", showlegend=first,
                legendgroup="trackline",
                hovertemplate="TL %{y:,.2f}<extra></extra>",
            ), row=1, col=1)
            first = False
            seg_start = i

    # 50 MA (trend MA — must be above for BULL)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["ma_med"],
        mode="lines", line=dict(color=COL_ACCENT, width=1.2),
        name="50 MA (trend)",
        hovertemplate="50 MA %{y:,.2f}<extra></extra>",
    ), row=1, col=1)

    # 200 MA — colour by rising/falling (hard regime filter)
    rising_long = (df["ma_long"] > df["ma_long"].shift(5)).fillna(False).to_numpy()
    ml = df["ma_long"].to_numpy()
    seg_start = 0
    first_ml = True
    for i in range(1, len(df) + 1):
        if i == len(df) or rising_long[i] != rising_long[seg_start]:
            colour = COL_BULL if rising_long[seg_start] else COL_BEAR
            end = i + (0 if i == len(df) else 1)
            fig.add_trace(go.Scatter(
                x=xs[seg_start:end], y=ml[seg_start:end],
                mode="lines",
                line=dict(color=colour, width=1.2, dash="dot"),
                name="200 MA (regime)", showlegend=first_ml,
                legendgroup="ma200",
                hovertemplate="200 MA %{y:,.2f}<extra></extra>",
            ), row=1, col=1)
            first_ml = False
            seg_start = i

    # Dots
    green = df[df["green_dot"]]
    red = df[df["red_dot"]]
    if len(green):
        fig.add_trace(go.Scatter(
            x=green.index, y=green["low"] * 0.985,
            mode="markers",
            marker=dict(color=COL_BULL, size=5, symbol="circle",
                        line=dict(color=COL_BG, width=0.5)),
            name="Green dot", legendgroup="dots",
            hovertemplate="GREEN %{x|%Y-%m-%d}<extra></extra>",
        ), row=1, col=1)
    if len(red):
        fig.add_trace(go.Scatter(
            x=red.index, y=red["high"] * 1.015,
            mode="markers",
            marker=dict(color=COL_BEAR, size=5, symbol="circle",
                        line=dict(color=COL_BG, width=0.5)),
            name="Red dot", legendgroup="dots",
            hovertemplate="RED %{x|%Y-%m-%d}<extra></extra>",
        ), row=1, col=1)

    # Signal markers — triangles
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

    # Allocation subplot (stepline — mirrors Pine targetAlloc)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["target_alloc"],
        mode="lines", line=dict(color=COL_ACCENT, width=1.8, shape="hv"),
        fill="tozeroy", fillcolor="rgba(88,166,255,0.15)",
        name="Allocation %",
        hovertemplate="Alloc %{y:.0f}%<extra></extra>",
    ), row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=720, margin=dict(l=10, r=20, t=50, b=10),
        title=dict(
            text=f"<span style='color:{COL_TEXT};font-size:18px;font-weight:600'>"
                 f"{symbol}/USD</span>"
                 f"<span style='color:{COL_DIM};font-size:13px'>"
                 f"   ·   Diversitas Lean</span>",
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
                     title_text="Alloc %",
                     title_font=dict(color=COL_DIM, size=10),
                     range=[0, 105], row=2, col=1)
    fig.update_xaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     row=1, col=1)
    fig.update_xaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     row=2, col=1)
    return fig


def _build_vol_chart(df: pd.DataFrame) -> go.Figure:
    """Bottom-half mini chart: annual vol % over time, with vol-shock threshold."""
    win = df.tail(360).copy()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=win.index, y=win["annual_vol"],
        mode="lines", line=dict(color=COL_HEDGED, width=1.5),
        name="Annual vol %",
        hovertemplate="Vol %{y:.1f}%<extra></extra>",
    ))
    if "vol_avg50" in win.columns:
        fig.add_trace(go.Scatter(
            x=win.index, y=win["vol_avg50"] * 1.5,
            mode="lines", line=dict(color=COL_BEAR, width=1, dash="dash"),
            name="Vol-shock threshold (1.5 × 50-bar avg)",
            hovertemplate="Threshold %{y:.1f}%<extra></extra>",
        ))
    fig.update_layout(
        template="plotly_dark",
        height=240, margin=dict(l=10, r=20, t=40, b=10),
        title=dict(
            text=f"<span style='color:{COL_DIM};font-size:12px;"
                 f"text-transform:uppercase;letter-spacing:1px'>"
                 f"Annualized volatility · last 360 bars</span>",
            x=0.01, y=0.94,
        ),
        paper_bgcolor=COL_BG, plot_bgcolor=COL_BG,
        font=dict(color=COL_TEXT, family="-apple-system, system-ui, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=COL_DIM)),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=COL_PANEL, bordercolor=COL_BORDER,
                        font=dict(color=COL_TEXT, size=11)),
    )
    fig.update_yaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10),
                     title_text="Vol %", title_font=dict(color=COL_DIM, size=10))
    fig.update_xaxes(gridcolor=COL_GRID, tickfont=dict(color=COL_DIM, size=10))
    return fig


# ---------- HTML helpers ----------

def _hero_card(label: str, value: str, colour: str = None, sub: str = None) -> str:
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


def _gate_row(label: str, passed: bool) -> str:
    """A pass/fail row for the entry-gate panel — Lean's signature visual.

    The user sees at a glance which conditions are missing for BULL entry.
    """
    icon = "PASS" if passed else "FAIL"
    colour = COL_BULL if passed else COL_BEAR
    bg = (f"{COL_BULL}11" if passed else f"{COL_BEAR}11")
    return (
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:center;padding:8px 12px;border-bottom:1px solid {COL_BORDER};'
        f'background:{bg}">'
        f'<span style="color:{COL_TEXT};font-size:12px">{label}</span>'
        f'<span style="background:{colour}22;color:{colour};'
        f'padding:2px 10px;border-radius:3px;font-size:10px;'
        f'font-weight:700;letter-spacing:0.5px;font-family:monospace">{icon}</span>'
        f"</div>"
    )


def _build_trade_ledger(df: pd.DataFrame) -> list[dict]:
    """Convert signal transitions into BULL→BEAR trade pairs.

    Annotate each closed trade with the trigger (trend-break / blow-off / vol-shock).
    """
    changes = df[df["signal_changed"]]
    trades: list[dict] = []
    open_entry = None
    for ts, row in changes.iterrows():
        sig = int(row["signal_state"])
        if sig == S_BULL:
            open_entry = {
                "entry_date": ts, "entry_px": float(row["close"]),
                "entry_dist": float(row["dist_pct"]),
            }
        elif sig == S_BEAR and open_entry is not None:
            duration = (ts - open_entry["entry_date"]).days
            pnl = (row["close"] / open_entry["entry_px"] - 1.0) * 100.0
            if bool(row["blowoff"]):
                exit_reason = "blow-off"
            elif bool(row["vol_shock"]):
                exit_reason = "vol-shock"
            else:
                exit_reason = "trend-break"
            trades.append({
                **open_entry,
                "exit_date": ts, "exit_px": float(row["close"]),
                "duration_days": duration, "pnl_pct": pnl,
                "exit_reason": exit_reason, "open": False,
            })
            open_entry = None
    last = df.iloc[-1]
    if open_entry is not None and int(last["signal_state"]) == S_BULL:
        duration = (last.name - open_entry["entry_date"]).days
        pnl = (last["close"] / open_entry["entry_px"] - 1.0) * 100.0
        trades.append({
            **open_entry,
            "exit_date": last.name, "exit_px": float(last["close"]),
            "duration_days": duration, "pnl_pct": pnl,
            "exit_reason": "—", "open": True,
        })
    return trades


def _render_trade_ledger(trades: list[dict], n: int = 12) -> str:
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
        status = (
            f'<span style="background:{COL_ACCENT}22;color:{COL_ACCENT};'
            f'padding:2px 8px;border-radius:3px;font-size:10px;'
            f'font-weight:600;letter-spacing:0.5px">OPEN</span>'
        ) if is_open else (
            f'<span style="color:{COL_DIM};font-size:11px">{t["exit_reason"]}</span>'
        )
        exit_date_txt = "—" if is_open else t["exit_date"].strftime("%Y-%m-%d")
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
            f'<td style="padding:10px 12px;color:{pnl_colour};font-family:monospace;'
            f'font-size:13px;font-weight:600;text-align:right">{pnl:+.2f}%</td>'
            f'<td style="padding:10px 12px;text-align:center">{status}</td>'
            f"</tr>"
        )
    headers = [
        ("ENTRY", "left"), ("EXIT", "left"),
        ("ENTRY PX", "right"), ("EXIT PX", "right"),
        ("DUR", "right"), ("P&L", "right"), ("EXIT TRIGGER", "center"),
    ]
    header_html = "".join(
        f'<th style="padding:8px 12px;color:{COL_DIM};font-size:10px;'
        f'text-transform:uppercase;letter-spacing:1px;text-align:{align};'
        f'border-bottom:1px solid {COL_BORDER};font-weight:600">{lbl}</th>'
        for lbl, align in headers
    )
    return (
        f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
        f'border-radius:6px;overflow:hidden">'
        f'<table style="width:100%;border-collapse:collapse">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _render_signal_stats(trades: list[dict], df: pd.DataFrame) -> str:
    closed = [t for t in trades if not t["open"]]
    n_total = len(closed)
    if n_total == 0:
        return (
            f'<div style="color:{COL_DIM};padding:14px;background:{COL_PANEL};'
            f'border:1px solid {COL_BORDER};border-radius:6px;text-align:center">'
            f"No completed trades yet.</div>"
        )
    wins = [t for t in closed if t["pnl_pct"] > 0]
    win_rate = len(wins) / n_total * 100
    avg_pnl = sum(t["pnl_pct"] for t in closed) / n_total
    avg_dur = sum(t["duration_days"] for t in closed) / n_total
    best = max(closed, key=lambda t: t["pnl_pct"])
    worst = min(closed, key=lambda t: t["pnl_pct"])
    eq = 1.0
    for t in closed:
        eq *= (1.0 + t["pnl_pct"] / 100.0)
    cum_pnl = (eq - 1.0) * 100.0

    bh_first = df["close"].iloc[0]
    bh_last = df["close"].iloc[-1]
    bh_pnl = (bh_last / bh_first - 1.0) * 100.0

    pnl_colour = COL_BULL if avg_pnl > 0 else COL_BEAR
    wr_colour = (COL_BULL if win_rate >= 50
                 else COL_HEDGED if win_rate >= 40 else COL_BEAR)
    cum_colour = COL_BULL if cum_pnl > 0 else COL_BEAR
    bh_colour = COL_BULL if bh_pnl > 0 else COL_BEAR

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


# ---------- main app ----------

def main() -> None:
    st.set_page_config(
        page_title="Diversitas Lean — Live",
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
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            f"<div style='color:{COL_TEXT};font-size:18px;font-weight:700;"
            f"letter-spacing:2px;margin-bottom:0px'>DIVERSITAS</div>"
            f"<div style='color:{COL_DIM};font-size:11px;letter-spacing:1px;"
            f"text-transform:uppercase;margin-bottom:18px'>Lean · Live</div>",
            unsafe_allow_html=True,
        )
        symbol = st.selectbox("Symbol",
                              options=list(DEFAULT_CONFIG.symbol_map.keys()), index=0)
        bars = st.slider("History (daily bars)", 400, 2000, 1000, 100)
        use_btc_filter = st.checkbox(
            "BTC cross-asset filter",
            value=False,
            help="OFF by default in Lean. Turn on for altcoins.",
        )
        auto_refresh = st.checkbox("Auto-refresh (60 s)", value=True)
        if st.button("Refresh now", type="primary", use_container_width=True):
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

    # Load data
    try:
        cfg, daily, result = _run(symbol, bars, use_btc_filter)
    except Exception as e:
        st.error(f"Failed to load data for {symbol}: {e}")
        st.stop()

    s = result.summary
    df = result.df

    # --- Hero row ---
    sig_colour = COL_BULL if s["signal"] == "BULL" else COL_BEAR
    regime_colour = {"BULL": COL_BULL, "HEDGED": COL_HEDGED,
                     "BEAR": COL_BEAR}[s["regime"]]
    dist_colour = COL_BULL if s["dist_pct"] > 0 else COL_BEAR

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(_hero_card("Signal", s["signal"], sig_colour,
                           sub=f"since {s['time']:%Y-%m-%d}"),
                unsafe_allow_html=True)
    c2.markdown(_hero_card("Regime", s["regime"], regime_colour),
                unsafe_allow_html=True)
    c3.markdown(_hero_card("Close", f"${s['close']:,.2f}",
                           sub=f"{symbol}/USD"),
                unsafe_allow_html=True)
    c4.markdown(_hero_card("Price vs Trackline", f"{s['dist_pct']:+.2f}%",
                           dist_colour,
                           sub=f"TL ${s['trackline']:,.0f}"),
                unsafe_allow_html=True)
    c5.markdown(_hero_card("Allocation", f"{s['target_alloc']:.0f}%",
                           COL_ACCENT,
                           sub=f"vol {s['annual_vol']:.1f}%"),
                unsafe_allow_html=True)

    # --- Main chart ---
    st.plotly_chart(_build_price_chart(df, symbol), use_container_width=True)

    # --- Detail row: entry gates + numeric panel ---
    left, right = st.columns([1, 1], gap="medium")

    with left:
        st.markdown(
            f"<div style='color:{COL_DIM};font-size:11px;"
            f"text-transform:uppercase;letter-spacing:1.5px;"
            f"margin:6px 0 8px 0'>Entry gates · all must PASS for BULL</div>",
            unsafe_allow_html=True,
        )
        last = df.iloc[-1]
        gates = [
            ("Above trackline + buffer", bool(last["above_tl"])),
            ("Above 50 MA (trend)", bool(last["above_ma_med"])),
            ("Trackline rising (10-bar slope)", bool(last["track_rising_window"])),
            (f"Distance ≥ {cfg.track_buf_pct + cfg.min_dist_entry_pct:.1f}%",
             bool(last["dist_entry_ok"])),
            ("Regime OK (not bear)", bool(last["regime_ok"])),
        ]
        if cfg.use_btc_filter:
            gates.append(("BTC bull (cross-asset)", bool(last["btc_filter_ok"])))
        st.markdown(
            f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
            f'border-radius:6px;overflow:hidden">'
            + "".join(_gate_row(lbl, ok) for lbl, ok in gates) +
            f"</div>",
            unsafe_allow_html=True,
        )

        # Warnings
        wrn = []
        if s["blowoff"]:
            wrn.append("BLOW-OFF top")
        if s["vol_shock"]:
            wrn.append("Volatility shock")
        if wrn:
            st.markdown(
                f'<div style="background:{COL_PANEL};border:1px solid {COL_BEAR};'
                f'border-radius:6px;padding:10px 14px;margin-top:8px;'
                f'color:{COL_BEAR};font-size:12px;font-weight:600;'
                f'letter-spacing:0.5px;text-transform:uppercase">'
                f'  {" · ".join(wrn)}'
                f"</div>",
                unsafe_allow_html=True,
            )

    with right:
        st.markdown(
            f"<div style='color:{COL_DIM};font-size:11px;"
            f"text-transform:uppercase;letter-spacing:1.5px;"
            f"margin:6px 0 8px 0'>Status detail</div>",
            unsafe_allow_html=True,
        )
        ma_colour = (COL_BEAR if s["bear_regime"]
                     else COL_HEDGED if s["ma_long_status"] == "BELOW"
                     else COL_BULL)
        tl_dir = "RISING" if s["track_rising_window"] else "FLAT/FALLING"
        tl_colour = COL_BULL if s["track_rising_window"] else COL_BEAR
        rows = [
            ("200 MA (regime)", s["ma_long_status"], ma_colour),
            ("50 MA (trend)",
             "ABOVE" if s["above_ma_med"] else "BELOW",
             COL_BULL if s["above_ma_med"] else COL_BEAR),
            ("Trackline slope", tl_dir, tl_colour),
            ("RSI", f"{s['rsi']:.1f}", COL_TEXT),
            ("Volatility", f"{s['annual_vol']:.1f}%", COL_HEDGED),
        ]
        if cfg.use_btc_filter:
            rows.append(("BTC filter",
                         "BTC BULL" if s["btc_bull"] else "BTC BEAR",
                         COL_BULL if s["btc_bull"] else COL_BEAR))
        items = "".join(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:8px 12px;border-bottom:1px solid {COL_BORDER}">'
            f'<span style="color:{COL_DIM};font-size:12px">{lbl}</span>'
            f'<span style="color:{c};font-size:13px;font-weight:500;'
            f'font-family:monospace">{v}</span></div>'
            for lbl, v, c in rows
        )
        st.markdown(
            f'<div style="background:{COL_PANEL};border:1px solid {COL_BORDER};'
            f'border-radius:6px;overflow:hidden">{items}</div>',
            unsafe_allow_html=True,
        )

    # --- Performance summary + vol chart ---
    trades = _build_trade_ledger(df)
    st.markdown(
        f"<div style='color:{COL_DIM};font-size:11px;"
        f"text-transform:uppercase;letter-spacing:1.5px;"
        f"margin:24px 0 8px 0'>Performance summary · loaded window</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_render_signal_stats(trades, df), unsafe_allow_html=True)
    st.plotly_chart(_build_vol_chart(df), use_container_width=True)

    # --- Trade ledger ---
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
        f"Naive long-flat backtest · no slippage / fees · Lean variant"
        f"</div>",
        unsafe_allow_html=True,
    )

    if auto_refresh:
        time.sleep(60)
        st.rerun()


if __name__ == "__main__":
    main()
