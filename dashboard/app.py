import sys
import os

# Ensure project root is on path so `dashboard.*` imports resolve
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# Load .env with explicit path so env vars are available everywhere
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"), override=False)

import streamlit as st
import time
from datetime import datetime

from dashboard.data.market import fetch_dax_ohlcv, get_dax_day_stats, get_current_dax_price
from dashboard.data.news import fetch_news_items, get_upcoming_events
from dashboard.data import degiro as degiro_feed
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
from dashboard.ui.ai_panel import render_ai_analysis

REFRESH_SECONDS = 15  # 15 seconden voor live prijs; grafiek/signalen via 60s cache
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

    auto_refresh = st.toggle("Auto-refresh (15s)", value=True)
    show_ema = st.toggle("EMA lijnen", value=True)
    show_bb = st.toggle("Bollinger Bands", value=True)

    st.divider()
    st.markdown("**📡 DEGIRO Live Feed**")

    dg_status = degiro_feed.get_status()
    if dg_status["connected"]:
        st.success("✅ Verbonden — real-time data")
        if dg_status["last_update"]:
            st.markdown(
                f"<small style='color:#7f8c8d;'>Bijgewerkt: {dg_status['last_update'].strftime('%H:%M:%S')}</small>",
                unsafe_allow_html=True,
            )
    elif dg_status["error"] and "inloggegevens" in dg_status["error"]:
        st.warning("🔑 Geen .env bestand")
        st.markdown(
            "<small>Maak `autoresearch/.env` aan met je DEGIRO gebruikersnaam en wachtwoord "
            "(zie `.env.example`). Herstart de app daarna.</small>",
            unsafe_allow_html=True,
        )
    elif dg_status["error"]:
        st.error(f"❌ {dg_status['error']}")
    else:
        st.info("⏳ Verbinden...")

    st.divider()
    st.markdown(
        "<small style='color:#7f8c8d;'>Grafiek data: Yahoo Finance</small>",
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown("**🤖 AI Handelsadvies**")
    import os as _os
    if not _os.environ.get("ANTHROPIC_API_KEY"):
        st.caption("Voeg ANTHROPIC_API_KEY toe aan .env")
    else:
        if st.button("🔍 Analyseer", type="primary", use_container_width=True):
            st.session_state["_ai_run"] = True

# ── Start DEGIRO feed once per process ───────────────────────────────────────
# start_feed() is idempotent — safe to call on every Streamlit rerun.
# It checks internally whether the thread is already running.
if "degiro_started" not in st.session_state:
    st.session_state["degiro_started"] = True
    degiro_feed.start_feed(extra_isins=["DE000BB3S888"])

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='text-align:center;margin-bottom:0;'>📊 DAX Turbo Pro</h1>",
    unsafe_allow_html=True,
)

# Show data source disclaimer based on connection status
_dg = degiro_feed.get_status()
if _dg["connected"]:
    st.markdown(
        "<div class='disclaimer' style='border-color:rgba(38,166,154,0.4);background:rgba(38,166,154,0.08);color:#26a69a;'>"
        "📡 DEGIRO real-time data actief — koersen bijgewerkt elke ~2 seconden</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div class='disclaimer'>⚠️ DEGIRO niet verbonden — koersen via Yahoo Finance (~1-5 min vertraging). "
        "Niet geschikt voor directe orderuitvoering. Dit is geen beleggingsadvies.</div>",
        unsafe_allow_html=True,
    )

# ── Session state ─────────────────────────────────────────────────────────────
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


# Live prijs: TTL 10s — meest actuele beschikbare data
@st.cache_data(ttl=10, show_spinner=False)
def _cached_live_price():
    return get_current_dax_price()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_news():
    return fetch_news_items(max_per_feed=5)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_calendar():
    return get_upcoming_events(days_ahead=7)


# ── Live data fragment (auto-refreshes every REFRESH_SECONDS) ────────────────
@st.fragment(run_every=REFRESH_SECONDS if auto_refresh else None)
def live_section():
    # Prijsprioriteit: 1. DEGIRO (real-time) → 2. Yahoo fast_info (~1min) → 3. dag-stats
    degiro_price = degiro_feed.get_dax_price()
    day_stats = _cached_day_stats()
    df = _cached_fetch(timeframe)

    if degiro_price:
        live_price = degiro_price
        price_source = "DEGIRO (real-time)"
    else:
        live_price, price_source = _cached_live_price()

    display_price = live_price or (day_stats.get("price") if day_stats else None)

    # ── Header: live prijs + vernieuwen knop ─────────────────────────────────
    header_left, header_right = st.columns([5, 1])
    with header_right:
        if st.button("🔄 Vernieuwen", width="stretch"):
            st.cache_data.clear()
            st.rerun()

    with header_left:
        if display_price and day_stats:
            change = day_stats.get("change", 0)
            change_pct = day_stats.get("change_pct", 0)
            # Herbereken change t.o.v. live prijs als beschikbaar
            if live_price and day_stats.get("prev_close"):
                change = live_price - day_stats["prev_close"]
                change_pct = change / day_stats["prev_close"] * 100

            color = "#26a69a" if change >= 0 else "#ef5350"
            arrow = "▲" if change >= 0 else "▼"

            # Data freshness indicator
            freshness_color = "#26a69a" if price_source in ("Yahoo (fast)", "Stooq") else "#ff9800"
            freshness_label = {
                "Yahoo (fast)": "~1-2 min vertraging",
                "Stooq": "~1-5 min vertraging",
                "Yahoo (1m)": "~5-15 min vertraging",
            }.get(price_source, "vertraging onbekend")

            st.markdown(
                f"<div style='display:flex;align-items:baseline;gap:16px;'>"
                f"<span style='font-size:30px;font-weight:bold;color:{color};'>"
                f"DAX {display_price:,.1f}</span>"
                f"<span style='font-size:20px;color:{color};'>{arrow} {change_pct:+.2f}%</span>"
                f"<span style='font-size:11px;color:{freshness_color};background:rgba(0,0,0,0.3);"
                f"padding:2px 8px;border-radius:10px;'>📡 {price_source} · {freshness_label}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            f"<small style='color:#546e7a;'>Bijgewerkt: {datetime.now().strftime('%H:%M:%S')} "
            f"· Auto-refresh: {REFRESH_SECONDS}s</small>",
            unsafe_allow_html=True,
        )

    # ── Dag statistieken ──────────────────────────────────────────────────────
    if day_stats:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Open", f"{day_stats.get('open', 0):,.0f}")
        c2.metric("Hoog", f"{day_stats.get('high', 0):,.0f}")
        c3.metric("Laag", f"{day_stats.get('low', 0):,.0f}")
        c4.metric("Vorige sluit", f"{day_stats.get('prev_close', 0):,.0f}" if day_stats.get("prev_close") else "-")

    st.divider()

    # ── Three-column layout ───────────────────────────────────────────────────
    left, center, right = st.columns([1.2, 2.2, 1.2])

    # ── LEFT: Signal panel ────────────────────────────────────────────────────
    with left:
        st.markdown("### 🎯 Handelssignaal")

        if df is not None and not df.empty:
            signal = compute_signal(df, direction=direction)
            # Store for AI panel (session_state survives fragment re-runs)
            st.session_state["_ai_signal"] = signal
            st.session_state["_ai_day_stats"] = day_stats
            st.session_state["_ai_dax_price"] = display_price
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
        st.plotly_chart(fig, width="stretch")

    # ── RIGHT: Calculator ─────────────────────────────────────────────────────
    with right:
        render_calculator(display_price)


# ── Bottom tabs: News / AI ───────────────────────────────────────────────────
def bottom_section():
    st.divider()
    tab_news, tab_ai = st.tabs(["📰 Nieuws & Kalender", "🤖 AI Handelsadvies"])

    news = _cached_news()
    calendar = _cached_calendar()

    with tab_news:
        news_col, cal_col = st.columns([1.5, 1])
        with news_col:
            render_news_feed(news)
        with cal_col:
            render_economic_calendar(calendar)

    with tab_ai:
        signal = st.session_state.get("_ai_signal")
        day_stats = st.session_state.get("_ai_day_stats") or {}
        dax_price = st.session_state.get("_ai_dax_price")
        headlines = [item.get("title", "") for item in (news or [])[:8]]

        render_ai_analysis(
            dax_price=dax_price,
            signal_score=signal.score if signal else 0.0,
            signal_label=signal.label if signal else "NEUTRAL",
            signal_components=signal.components if signal else {},
            day_stats=day_stats,
            news_headlines=headlines,
            calendar_events=calendar or [],
        )


# ── Render ────────────────────────────────────────────────────────────────────
live_section()
bottom_section()

# ── AI analyse uitvoer (buiten fragment zodat streaming werkt) ────────────────
if st.session_state.get("_ai_run"):
    st.session_state["_ai_run"] = False
    from dashboard.data.ai_analysis import build_market_context, stream_ai_analysis
    from dashboard.data.news import fetch_news_items, get_upcoming_events

    _sig = st.session_state.get("_ai_signal")
    _day = st.session_state.get("_ai_day_stats") or {}
    _price = st.session_state.get("_ai_dax_price")
    _news = _cached_news() or []
    _cal = _cached_calendar() or []

    _ctx = build_market_context(
        dax_price=_price,
        signal_score=_sig.score if _sig else 0.0,
        signal_label=_sig.label if _sig else "NEUTRAL",
        signal_components=_sig.components if _sig else {},
        day_stats=_day,
        news_headlines=[n.get("title", "") for n in _news[:8]],
        calendar_events=_cal,
        turbo_info={"str": 25827.2556, "sl": 25568.983},
    )

    st.markdown("---")
    st.markdown("### 🤖 AI Handelsadvies")
    _box = st.empty()
    _text = ""
    with st.spinner("Claude analyseert..."):
        for _chunk in stream_ai_analysis(_ctx):
            _text += _chunk
            _box.markdown(_text)
