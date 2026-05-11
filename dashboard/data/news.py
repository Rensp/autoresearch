import feedparser
import requests
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

RSS_FEEDS = {
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "ECB News": "https://www.ecb.europa.eu/rss/fservices/ecballnews.html",
    "Investing.com DAX": "https://www.investing.com/rss/news_301.rss",
    "Yahoo Finance": "https://finance.yahoo.com/rss/2.0/headline?s=%5EGDAXI&region=US&lang=en-US",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
}

# Economic calendar: key events affecting DAX
# Format: date as string (YYYY-MM-DD), time in CET, importance HIGH/MEDIUM
ECONOMIC_CALENDAR = [
    # ECB
    {"event": "ECB Rentebeslist", "date": "2026-06-05", "time": "14:15", "importance": "HIGH",
     "previous": "2.40%", "forecast": "2.15%"},
    {"event": "ECB Persconferentie", "date": "2026-06-05", "time": "14:45", "importance": "HIGH",
     "previous": "-", "forecast": "-"},
    {"event": "ECB Notulen", "date": "2026-05-22", "time": "13:30", "importance": "MEDIUM",
     "previous": "-", "forecast": "-"},
    # German macro
    {"event": "Duits IFO Ondernemersklimaat", "date": "2026-05-26", "time": "10:00", "importance": "HIGH",
     "previous": "86.9", "forecast": "87.5"},
    {"event": "Duits CPI (maand-op-maand)", "date": "2026-05-28", "time": "14:00", "importance": "HIGH",
     "previous": "+0.3%", "forecast": "+0.2%"},
    {"event": "Duits Handelssaldo", "date": "2026-06-09", "time": "08:00", "importance": "MEDIUM",
     "previous": "€17.7B", "forecast": "€16.5B"},
    {"event": "Duits BBP (Q1 definitief)", "date": "2026-05-23", "time": "10:00", "importance": "HIGH",
     "previous": "+0.2%", "forecast": "+0.2%"},
    # Eurozone
    {"event": "Eurozone PMI Industrie", "date": "2026-06-01", "time": "10:00", "importance": "HIGH",
     "previous": "49.2", "forecast": "49.8"},
    {"event": "Eurozone PMI Diensten", "date": "2026-06-04", "time": "10:00", "importance": "HIGH",
     "previous": "50.3", "forecast": "50.7"},
    {"event": "Eurozone CPI Flash (jaars)", "date": "2026-05-30", "time": "11:00", "importance": "HIGH",
     "previous": "+2.2%", "forecast": "+2.0%"},
    {"event": "Eurozone Detailhandel", "date": "2026-06-04", "time": "11:00", "importance": "MEDIUM",
     "previous": "+0.3%", "forecast": "+0.2%"},
    # US (impactvol voor DAX)
    {"event": "US Non-Farm Payrolls", "date": "2026-06-05", "time": "14:30", "importance": "HIGH",
     "previous": "+177K", "forecast": "+185K"},
    {"event": "US ISM Industrie PMI", "date": "2026-06-01", "time": "16:00", "importance": "HIGH",
     "previous": "49.0", "forecast": "49.6"},
    {"event": "FOMC Rentebeslist (Fed)", "date": "2026-06-17", "time": "20:00", "importance": "HIGH",
     "previous": "4.25-4.50%", "forecast": "4.00-4.25%"},
    {"event": "US CPI (jaars)", "date": "2026-06-11", "time": "14:30", "importance": "HIGH",
     "previous": "+3.4%", "forecast": "+3.2%"},
]


def fetch_news_items(max_per_feed: int = 5) -> list[dict]:
    items = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
            for entry in feed.entries[:max_per_feed]:
                published = ""
                if hasattr(entry, "published"):
                    try:
                        dt = parsedate_to_datetime(entry.published)
                        published = dt.strftime("%d-%m %H:%M")
                    except Exception:
                        published = entry.get("published", "")

                summary = entry.get("summary", "")
                if len(summary) > 200:
                    summary = summary[:200] + "..."

                items.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", "#"),
                    "published": published,
                    "source": source,
                    "summary": summary,
                })
        except Exception:
            continue

    # Sort by published (newest first, best-effort)
    items.sort(key=lambda x: x.get("published", ""), reverse=True)
    return items


def get_upcoming_events(days_ahead: int = 7) -> list[dict]:
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    results = []
    for event in ECONOMIC_CALENDAR:
        try:
            event_date = date.fromisoformat(event["date"])
            if today <= event_date <= cutoff:
                enriched = event.copy()
                enriched["today"] = event_date == today
                enriched["date"] = event_date.strftime("%d-%m-%Y")
                results.append(enriched)
        except Exception:
            continue
    results.sort(key=lambda x: x["date"])
    return results


def get_todays_events() -> list[dict]:
    return [e for e in get_upcoming_events(days_ahead=0) if e.get("today", False)]
