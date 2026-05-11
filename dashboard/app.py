import sys
import os

# Ensure project root is on path so `dashboard.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import time
from datetime import datetime

from dashboard.data.market import fetch_dax_ohlcv, get_dax_day_stats
from dashboard.data.news import fetch_news_items, get_upcoming_events
from dashboard.indicators.signals import compute_signal, compute_mtf_signals, check_confluence
from dashboard.ui.chart import build_candlestick_chart
from dashboard.ui.signal_panel import (
    render_signal_badge,
    render_score_gauge,
    render_signal_breakdown,
    render_mtf_confluence,
)
from dashboard.ui.calculator_panel import render_calculator
from dashboard.ui.news_panel import render_news_feed, render_economic_calendar

REFRESH_SECONDS = 60
TIMEFRAMES = ["15m", "1h", "4h", "1d"]

st.set_page_config(
    page_title="DAX Turbo Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for dark professional feel
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .block-container { padding-top: 1rem; }
    div[data-testid="metric-container"] {
        background: #1e2329;
        border: 1px solid #2d3748;
        border-radius: 8px;
        padding: 10px 14px;
    }
    .stAlert { border-radius: 8px; }
    .disclaimer {
        background: rgba(255,152,0,0.1);
        border: 1px solid rgba(255,152,0,0.3);
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        color: #ff9800;
        text-align: center;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Instellingen")

    timeframe = st.selectbox(
        "Tijdframe grafiek",
        options=TIMEFRAMES,
        index=1,
        help="Selecteer het tijdframe voor de candlestick grafiek en het signaalalgoritme.",
    )

    direction = st.radio(
        "Turbo richting",
        options=["LONG", "SHORT"],
        horizontal=True,
        help="LONG = je verwacht een stijgende DAX. SHORT = dalende DAX.",
    )

    auto_refresh = st.toggle("Auto-refresh (60s)", value=True)
    show_ema = st.toggle("EMA lijnen", value=True)
    show_bb = st.toggle("Bollinger Bands", value=True)

    st.divider()
    st.markdown(
        "<small style='color:#7f8c8d;'>Data: Yahoo Finance<br>Vertraging: ~15 min</small>",
        unsafe_allow_html=True,
    )

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='text-align:center;margin-bottom:0;'>📊 DAX Turbo Pro</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='disclaimer'>⚠️ Koersen zijn ~15 minuten vertraagd. Niet geschikt voor directe orderuitvoering. "
    "Dit is geen beleggingsadvies.</div>",
    unsafe_allow_html=True,
)

# ── Session state for cached data ────────────────────────────────────────────
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = 0
if "dax_data_cache" not in st.session_state:
    st.session_state["dax_data_cache"] = {}
if "day_stats_cache" not in st.session_state:
    st.session_state["day_stats_cache"] = {}


@st.cache_data(ttl=60, show_spinner=False)
def _cached_fetch(tf: str):
    return fetch_dax_ohlcv(tf)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_day_stats():
    return get_dax_day_stats()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_news():
    return fetch_news_items(max_per_feed=5)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_calendar():
    return get_upcoming_events(days_ahead=7)


# ── Live data fragment (auto-refreshes independently) ────────────────────────
@st.fragment(run_every=REFRESH_SECONDS if auto_refresh else None)
def live_section():
    df = _cached_fetch(timeframe)
    day_stats = _cached_day_stats()

    # ── DAX stat bar ─────────────────────────────────────────────────────────
    if day_stats:
        price = day_stats.get("price", 0)
        change = day_stats.get("change", 0)
        change_pct = day_stats.get("change_pct", 0)
        color = "#26a69a" if change >= 0 else "#ef5350"
        arrow = "▲" if change >= 0 else "▼"

        c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
        c1.markdown(
            f"<div style='font-size:28px;font-weight:bold;color:{color};'>"
            f"DAX {price:,.0f} <span style='font-size:18px;'>{arrow} {change_pct:+.2f}%</span></div>",
            unsafe_allow_html=True,
        )
        c2.metric("Open", f"{day_stats.get('open', 0):,.0f}")
        c3.metric("Hoog", f"{day_stats.get('high', 0):,.0f}")
        c4.metric("Laag", f"{day_stats.get('low', 0):,.0f}")
        c5.metric(
            "Vorige sluit",
            f"{day_stats.get('prev_close', 0):,.0f}" if day_stats.get("prev_close") else "-",
        )

    st.markdown(
        f"<small style='color:#546e7a;'>Laatste update: {datetime.now().strftime('%H:%M:%S')}</small>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Three-column layout ───────────────────────────────────────────────────
    left, center, right = st.columns([1.2, 2.2, 1.2])

    # ── LEFT: Signal panel ────────────────────────────────────────────────────
    with left:
        st.markdown("### 🎯 Handelssignaal")

        if df is not None and not df.empty:
            signal = compute_signal(df, direction=direction)
            render_signal_badge(signal)
            render_score_gauge(signal.score)

            with st.expander("Indicator details", expanded=False):
                render_signal_breakdown(signal)

            # Multi-timeframe
            st.markdown("---")
            all_tf_data = {tf: _cached_fetch(tf) for tf in TIMEFRAMES}
            mtf = compute_mtf_signals(all_tf_data, direction=direction)
            render_mtf_confluence(mtf)
        else:
            st.warning("Geen DAX data beschikbaar. Controleer je internetverbinding.")

    # ── CENTER: Chart ─────────────────────────────────────────────────────────
    with center:
        st.markdown(f"### 📈 DAX — {timeframe}")
        fig = build_candlestick_chart(
            df if df is not None else __import__("pandas").DataFrame(),
            timeframe=timeframe,
            show_ema=show_ema,
            show_bb=show_bb,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── RIGHT: Calculator ─────────────────────────────────────────────────────
    with right:
        current_price = day_stats.get("price") if day_stats else None
        render_calculator(current_price)


# ── Static section: News + Calendar ──────────────────────────────────────────
def news_section():
    st.divider()
    news_col, cal_col = st.columns([1.5, 1])
    with news_col:
        news = _cached_news()
        render_news_feed(news)
    with cal_col:
        calendar = _cached_calendar()
        render_economic_calendar(calendar)


# ── Render ────────────────────────────────────────────────────────────────────
live_section()
news_section()
