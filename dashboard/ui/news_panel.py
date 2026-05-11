import streamlit as st
import pandas as pd
from datetime import datetime


def render_news_feed(news_items: list[dict]) -> None:
    st.markdown("### 📰 Laatste Nieuws")
    if not news_items:
        st.info("Geen nieuwsitems beschikbaar (RSS feeds niet bereikbaar).")
        return

    for item in news_items[:15]:
        source = item.get("source", "Onbekend")
        title = item.get("title", "")
        link = item.get("link", "#")
        published = item.get("published", "")
        summary = item.get("summary", "")

        with st.container():
            st.markdown(
                f"""
                <div style="border-left:3px solid #3498db;padding:6px 10px;margin-bottom:8px;">
                    <span style="font-size:10px;color:#3498db;background:rgba(52,152,219,0.1);
                        padding:2px 6px;border-radius:4px;">{source}</span>
                    <span style="font-size:10px;color:#7f8c8d;margin-left:8px;">{published}</span>
                    <div style="margin-top:4px;">
                        <a href="{link}" target="_blank" style="color:#ecf0f1;text-decoration:none;
                            font-size:13px;font-weight:500;">{title}</a>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_economic_calendar(events: list[dict]) -> None:
    st.markdown("### 📅 Economische Kalender")
    if not events:
        st.info("Geen aankomende events in de komende 7 dagen.")
        return

    today_events = [e for e in events if e.get("today", False)]
    if today_events:
        for e in today_events:
            importance = e.get("importance", "MEDIUM")
            if importance == "HIGH":
                st.error(
                    f"🚨 **VANDAAG {e.get('time', '')} CET** — {e['event']} "
                    f"| Vorig: {e.get('previous', '?')} | Verwacht: {e.get('forecast', '?')}"
                )
            else:
                st.warning(
                    f"⚠️ **VANDAAG {e.get('time', '')} CET** — {e['event']}"
                )

    upcoming = [e for e in events if not e.get("today", False)]
    if upcoming:
        rows = []
        for e in upcoming[:10]:
            rows.append({
                "Datum": e.get("date", ""),
                "Tijd (CET)": e.get("time", ""),
                "Evenement": e.get("event", ""),
                "Belang": "🔴 HOOG" if e.get("importance") == "HIGH" else "🟡 MEDIUM",
                "Vorig": e.get("previous", "-"),
                "Verwacht": e.get("forecast", "-"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch", hide_index=True)
