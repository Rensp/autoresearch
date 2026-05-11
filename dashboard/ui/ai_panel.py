import streamlit as st

from dashboard.data.ai_analysis import build_market_context, stream_ai_analysis


_DEFAULT_TURBO = {
    "str": 25827.2556,
    "sl": 25568.983,
    "ratio": 500,
    "isin": "DE000BB3S888",
}


def render_ai_analysis(
    dax_price: float | None,
    signal_score: float,
    signal_label: str,
    signal_components: dict,
    day_stats: dict,
    news_headlines: list[str],
    calendar_events: list[dict],
) -> None:
    st.markdown("### 🤖 AI Handelsadvies")

    import os
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY", ""))

    if not has_key:
        st.info(
            "Voeg `ANTHROPIC_API_KEY=sk-ant-...` toe aan je `.env` bestand voor AI-analyse. "
            "Haal je sleutel op via [console.anthropic.com](https://console.anthropic.com).",
            icon="🔑",
        )
        return

    if st.button("🔍 Analyseer nu", type="primary", width="stretch"):
        context = build_market_context(
            dax_price=dax_price,
            signal_score=signal_score,
            signal_label=signal_label,
            signal_components=signal_components,
            day_stats=day_stats,
            news_headlines=news_headlines,
            calendar_events=calendar_events,
            turbo_info=_DEFAULT_TURBO,
        )

        with st.spinner("Claude analyseert de markt..."):
            output_box = st.empty()
            full_text = ""
            for chunk in stream_ai_analysis(context):
                full_text += chunk
                output_box.markdown(full_text)

    elif "ai_last_analysis" in st.session_state:
        st.markdown(st.session_state["ai_last_analysis"])
