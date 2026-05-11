"""
Claude AI trading analysis for the DAX Turbo dashboard.

Reads live market context (price, signals, news) and streams an analysis
via the Anthropic API. Requires ANTHROPIC_API_KEY in environment / .env.
"""

import logging
import os
from typing import Iterator

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Je bent een ervaren technisch analist gespecialiseerd in DAX derivaten en turbo-certificaten.
Je analyseert real-time marktdata en geeft beknopt, gestructureerd handelsadvies in het Nederlands.

Richtlijnen:
- Wees direct en concreet — geen uitgebreide uitleg, focus op actionable inzichten
- Benoem altijd het risico van knock-out voor turbo's bij hoge volatiliteit
- Gebruik ▲ en ▼ voor koersrichting
- Eindig altijd met een duidelijke conclusie: HOUD AAN / OVERWEEG UIT / BEWAAK NIVEAU
- Dit is geen officieel beleggingsadvies — vermeld dit kort onderaan

Structuur van je antwoord (gebruik markdown headers):
## Marktoverzicht
## Technisch signaal
## Jouw Turbo Short (DE000BB3S888)
## Risico's & prijsniveaus
## Conclusie
"""


def build_market_context(
    dax_price: float | None,
    signal_score: float,
    signal_label: str,
    signal_components: dict,
    day_stats: dict,
    news_headlines: list[str],
    calendar_events: list[dict],
    turbo_info: dict | None = None,
) -> str:
    """Build a structured prompt with current market data."""
    lines = []

    lines.append(f"**DAX koers**: {dax_price:,.1f}" if dax_price else "**DAX koers**: onbekend")

    if day_stats:
        open_p = day_stats.get("open", 0)
        high_p = day_stats.get("high", 0)
        low_p = day_stats.get("low", 0)
        prev = day_stats.get("prev_close", 0)
        if dax_price and prev:
            change_pct = (dax_price - prev) / prev * 100
            lines.append(f"**Dagverandering**: {change_pct:+.2f}% (vorige sluit: {prev:,.0f})")
        lines.append(f"**Dag range**: {low_p:,.0f} – {high_p:,.0f} | Open: {open_p:,.0f}")

    lines.append(f"\n**Signaalalgoritme score**: {signal_score:+.1f} → **{signal_label}**")

    if signal_components:
        comps = []
        for name, score in signal_components.items():
            indicator = "▲" if score > 0.1 else ("▼" if score < -0.1 else "→")
            comps.append(f"{name}: {indicator} {score:+.2f}")
        lines.append("**Indicatoren**: " + " | ".join(comps))

    if turbo_info:
        lines.append(
            f"\n**Jouw Turbo Short (DE000BB3S888)**:"
            f" STR {turbo_info.get('str', '25827.26')} | SL {turbo_info.get('sl', '25568.98')}"
            f" | Ratio 1:500"
        )
        if dax_price:
            sl = float(turbo_info.get("sl", 25568.983))
            str_level = float(turbo_info.get("str", 25827.2556))
            dist_sl = dax_price - sl
            dist_str = str_level - dax_price
            intrinsic = (str_level - dax_price) / 500 if dax_price < str_level else 0
            lines.append(
                f"  → Afstand tot KO (SL): {dist_sl:+,.1f} pt | "
                f"Afstand tot STR: {dist_str:+,.1f} pt | "
                f"Intrinsieke waarde: €{intrinsic:.4f}"
            )

    if news_headlines:
        lines.append("\n**Actueel nieuws** (top 5):")
        for h in news_headlines[:5]:
            lines.append(f"- {h}")

    if calendar_events:
        today_ev = [e for e in calendar_events if e.get("today")]
        upcoming_ev = [e for e in calendar_events if not e.get("today")][:3]
        if today_ev:
            lines.append("\n**Events VANDAAG**:")
            for e in today_ev:
                lines.append(f"- 🔴 {e.get('time', '')} — {e.get('event', '')} (vorig: {e.get('previous', '?')})")
        if upcoming_ev:
            lines.append("**Aankomende events**:")
            for e in upcoming_ev:
                lines.append(f"- {e.get('date', '')} {e.get('time', '')} — {e.get('event', '')}")

    return "\n".join(lines)


def stream_ai_analysis(market_context: str) -> Iterator[str]:
    """
    Stream Claude's trading analysis as text chunks.
    Yields empty string immediately if API key is missing.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        yield (
            "**⚠️ Geen ANTHROPIC_API_KEY gevonden.**\n\n"
            "Voeg `ANTHROPIC_API_KEY=sk-ant-...` toe aan je `.env` bestand "
            "en herstart de app. Haal je sleutel op via "
            "[console.anthropic.com](https://console.anthropic.com)."
        )
        return

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Analyseer de volgende marktdata en geef advies over mijn DAX Turbo Short positie:\n\n"
                        + market_context
                    ),
                }
            ],
        ) as stream:
            for text in stream.text_stream:
                yield text

    except ImportError:
        yield "**⚠️ `anthropic` pakket niet geïnstalleerd.** Voer `uv sync --extra dashboard` uit."
    except Exception as exc:
        logger.error("AI analysis error: %s", exc)
        yield f"**⚠️ AI analyse mislukt:** {exc}"
