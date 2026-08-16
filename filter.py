"""
AI-powered event filter using Google Gemini (free tier).
Reads raw scraped events and decides what to include in the calendar,
assigning category, priority, and region.
"""
import asyncio
import json
import logging
import os
from typing import List

import google.generativeai as genai

from scrapers.base import Event

logger = logging.getLogger(__name__)

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config={"temperature": 0.1, "response_mime_type": "application/json"},
)

SYSTEM_PROMPT = """You are a Sydney activities curator for a calendar called "What's on Sydney".

Your job: decide which scraped events/activities to include, and classify them.

INCLUDE events that are:
- Physically located in or reachable from Sydney within ~2 hours drive:
  Sydney metro, Blue Mountains, Southern Highlands, Hawkesbury, Hunter Valley, Illawarra
- Festivals: film, comedy, writers, cultural, food, flower/tulip, music, art
- Markets: general, artisan, vintage, second-hand, flea markets
- Art events: exhibitions, gallery openings, public art, theatre, performances
- Outdoor activities: walking tracks, new pools, nature parks, gardens
- Community events: free public events, cultural celebrations

PRIORITISE (priority 1 = highest):
- priority 1: Free events, outdoor/nature events, unique seasonal events
- priority 2: Affordable paid events, recurring markets/festivals worth highlighting
- priority 3: Paid events that are still relevant to include

EXCLUDE:
- Events outside geographic scope (interstate, overseas)
- Sports matches/fixtures (unless it's a festival atmosphere)
- Corporate or private events
- Articles/listicles (not actual events)
- Duplicate or near-identical entries

Return a JSON array with exactly one object per event (in the same order):
[
  {
    "include": true,
    "category": "festival|market|art|outdoor|food|community|other",
    "is_free": true,
    "priority": 1,
    "region": "sydney|blue_mountains|southern_highlands|hunter_valley|illawarra|other",
    "reason": "one-line reason"
  }
]

Only return the JSON array. No explanation, no markdown fences."""


async def filter_events(events: List[Event], batch_size: int = 15) -> List[Event]:
    """
    Filter and classify events using Gemini.
    Returns approved events sorted by priority (1 = best).
    National Parks events skip AI filter (already pre-classified).
    """
    if not events:
        return []

    # Separate pre-classified (National Parks) from events needing AI review
    pre_approved: List[Event] = []
    needs_review: List[Event] = []

    for e in events:
        if e.source == "National Parks NSW" and e.ai_category == "outdoor":
            e.ai_priority = 1
            e.ai_location_region = "sydney"  # will be refined by region in URL
            pre_approved.append(e)
        else:
            needs_review.append(e)

    approved_from_ai: List[Event] = []

    for i in range(0, len(needs_review), batch_size):
        batch = needs_review[i : i + batch_size]
        logger.info(f"[Filter] Processing batch {i // batch_size + 1} ({len(batch)} events)")

        results = await _filter_batch(batch)

        for event, result in zip(batch, results):
            if not isinstance(result, dict):
                continue
            if not result.get("include", False):
                logger.debug(f"[Filter] Excluded: {event.title} — {result.get('reason', '')}")
                continue
            region = result.get("region", "other")
            if region == "other":
                logger.debug(f"[Filter] Out of region: {event.title}")
                continue

            event.ai_category = result.get("category", "other")
            event.ai_priority = int(result.get("priority", 2))
            event.ai_location_region = region
            if result.get("is_free"):
                event.is_free = True
                if not event.price_text:
                    event.price_text = "Free"

            approved_from_ai.append(event)
            logger.debug(f"[Filter] Included (p{event.ai_priority}): {event.title}")

        # Polite delay between API calls
        if i + batch_size < len(needs_review):
            await asyncio.sleep(0.5)

    all_approved = pre_approved + approved_from_ai
    # Sort: priority ascending (1 = best first), then free events first within same priority
    all_approved.sort(key=lambda e: (e.ai_priority, 0 if e.is_free else 1))

    logger.info(f"[Filter] {len(all_approved)} events approved out of {len(events)} scraped")
    return all_approved


async def _filter_batch(events: List[Event]) -> List[dict]:
    """Send a batch to Gemini and parse the JSON response."""
    lines = []
    for i, e in enumerate(events, 1):
        lines.append(
            f"Event {i}:\n"
            f"  Title: {e.title}\n"
            f"  Description: {(e.description or '')[:250]}\n"
            f"  Location: {e.location or 'Unknown'}\n"
            f"  Price: {e.price_text or 'Unknown'}\n"
            f"  Source URL: {e.url}\n"
            f"  Source: {e.source}"
        )

    prompt = (
        SYSTEM_PROMPT
        + f"\n\nClassify these {len(events)} events. "
        + f"Return a JSON array of exactly {len(events)} objects.\n\n"
        + "\n\n".join(lines)
    )

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Strip accidental markdown fences
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        results = json.loads(text)
        if not isinstance(results, list):
            raise ValueError("Expected a JSON array")
        # Pad with exclude stubs if response is shorter than batch
        while len(results) < len(events):
            results.append({"include": False, "reason": "missing from response"})
        return results[:len(events)]

    except Exception as e:
        logger.error(f"[Filter] API/parse error: {e}")
        return [{"include": False, "reason": f"error: {e}"}] * len(events)
