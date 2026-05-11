import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from dashboard.indicators.signals import SignalResult

_LABEL_CONFIG = {
    "STRONG BUY":  {"color": "#00c853", "emoji": "🟢", "bg": "#00c85322"},
    "BUY":         {"color": "#69f0ae", "emoji": "🟩", "bg": "#69f0ae22"},
    "NEUTRAL":     {"color": "#90a4ae", "emoji": "⬜", "bg": "#90a4ae22"},
    "SELL":        {"color": "#ff7043", "emoji": "🟧", "bg": "#ff704322"},
    "STRONG SELL": {"color": "#f44336", "emoji": "🔴", "bg": "#f4433622"},
}

_COMPONENT_NAMES_NL = {
    "EMA Crossover": "EMA Kruising",
    "RSI": "RSI",
    "MACD": "MACD",
    "Bollinger Bands": "Bollinger Bands",
    "Volume": "Volume",
}


def render_signal_badge(result: SignalResult) -> None:
    cfg = _LABEL_CONFIG.get(result.label, _LABEL_CONFIG["NEUTRAL"])
    direction_icon = "📈 LONG" if result.direction == "LONG" else "📉 SHORT"

    st.markdown(
        f"""
        <div style="
            background:{cfg['bg']};
            border:2px solid {cfg['color']};
            border-radius:12px;
            padding:16px 20px;
            text-align:center;
            margin-bottom:8px;
        ">
            <div style="font-size:13px;color:#90a4ae;margin-bottom:4px;">{direction_icon}</div>
            <div style="font-size:32px;font-weight:bold;color:{cfg['color']};">
                {cfg['emoji']} {result.label}
            </div>
            <div style="font-size:22px;color:{cfg['color']};margin-top:4px;">
                Score: {result.score:+.1f}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_score_gauge(score: float) -> None:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "", "font": {"size": 24, "color": "white"}},
            gauge={
                "axis": {"range": [-100, 100], "tickcolor": "white",
                         "tickfont": {"size": 10}},
                "bar": {"color": _score_color(score), "thickness": 0.3},
                "bgcolor": "#1e2329",
                "borderwidth": 0,
                "steps": [
                    {"range": [-100, -60], "color": "#4a1010"},
                    {"range": [-60, -25], "color": "#4a2010"},
                    {"range": [-25,  25], "color": "#1a2a1a"},
                    {"range": [ 25,  60], "color": "#10301a"},
                    {"range": [ 60, 100], "color": "#104a1a"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 2},
                    "thickness": 0.8,
                    "value": score,
                },
            },
        )
    )
    fig.update_layout(
        paper_bgcolor="#0e1117",
        font={"color": "white"},
        height=200,
        margin=dict(l=20, r=20, t=20, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _score_color(score: float) -> str:
    if score >= 60:
        return "#00c853"
    elif score >= 25:
        return "#69f0ae"
    elif score >= -25:
        return "#90a4ae"
    elif score >= -60:
        return "#ff7043"
    else:
        return "#f44336"


def render_signal_breakdown(result: SignalResult) -> None:
    if not result.components:
        return
    rows = []
    for name, score in result.components.items():
        direction = "Bullish 📈" if score > 0.1 else ("Bearish 📉" if score < -0.1 else "Neutraal ⬜")
        rows.append({
            "Indicator": _COMPONENT_NAMES_NL.get(name, name),
            "Score": f"{score:+.2f}",
            "Signaal": direction,
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_mtf_confluence(mtf_results: dict) -> None:
    if not mtf_results:
        return

    st.markdown("**Multi-Tijdframe Overzicht**")
    cols = st.columns(len(mtf_results))
    buy_count = 0
    sell_count = 0

    for col, (tf, result) in zip(cols, mtf_results.items()):
        cfg = _LABEL_CONFIG.get(result.label, _LABEL_CONFIG["NEUTRAL"])
        with col:
            st.markdown(
                f"""
                <div style="text-align:center;background:{cfg['bg']};
                    border:1px solid {cfg['color']};border-radius:8px;padding:8px;">
                    <div style="font-size:11px;color:#90a4ae;">{tf}</div>
                    <div style="font-size:13px;font-weight:bold;color:{cfg['color']};">
                        {cfg['emoji']} {result.label}
                    </div>
                    <div style="font-size:11px;color:{cfg['color']};">{result.score:+.0f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        if result.label in ("STRONG BUY", "BUY"):
            buy_count += 1
        elif result.label in ("STRONG SELL", "SELL"):
            sell_count += 1

    if buy_count >= 3:
        st.success(f"⚡ **CONFLUENTE LONG**: {buy_count}/4 tijdframes bullish — sterk instapmomentsignaal!")
    elif sell_count >= 3:
        st.error(f"⚡ **CONFLUENTE SHORT**: {sell_count}/4 tijdframes bearish — sterk verkoopsignaal!")
