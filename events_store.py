"""
JSON-backed events store.

Persists all approved events across scrape runs so the website always
shows the full catalogue, not just what was found in the latest run.
"""
import json
import os
from datetime import datetime
from typing import List

from scrapers.base import Event

STORE_FILE = os.path.join(os.path.dirname(__file__), "events_data.json")


def _event_to_dict(e: Event) -> dict:
    return {
        "title":              e.title,
        "description":        e.description,
        "url":                e.url,
        "source":             e.source,
        "location":           e.location,
        "date_start":         e.date_start.isoformat() if e.date_start else None,
        "date_end":           e.date_end.isoformat()   if e.date_end   else None,
        "price_text":         e.price_text,
        "is_free":            e.is_free,
        "categories":         e.categories,
        "image_url":          e.image_url,
        "ai_category":        e.ai_category,
        "ai_priority":        e.ai_priority,
        "ai_location_region": e.ai_location_region,
    }


def _dict_to_event(d: dict) -> Event:
    return Event(
        title=              d.get("title", ""),
        description=        d.get("description", ""),
        url=                d.get("url", ""),
        source=             d.get("source", ""),
        location=           d.get("location", ""),
        date_start=         datetime.fromisoformat(d["date_start"]) if d.get("date_start") else None,
        date_end=           datetime.fromisoformat(d["date_end"])   if d.get("date_end")   else None,
        price_text=         d.get("price_text", ""),
        is_free=            d.get("is_free", False),
        categories=         d.get("categories", []),
        image_url=          d.get("image_url"),
        ai_category=        d.get("ai_category", ""),
        ai_priority=        d.get("ai_priority", 2),
        ai_location_region= d.get("ai_location_region", ""),
    )


def load_all() -> List[Event]:
    """Return all persisted events (empty list if store doesn't exist yet)."""
    if not os.path.exists(STORE_FILE):
        return []
    with open(STORE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return [_dict_to_event(d) for d in data]


def append_new(new_events: List[Event]) -> List[Event]:
    """
    Add new_events to the store (deduplicating by URL) and return
    the full list of all stored events.
    """
    existing = load_all()
    existing_urls = {e.url for e in existing}

    added = [e for e in new_events if e.url not in existing_urls]
    all_events = existing + added

    # Sort: events with dates first (soonest first), then undated
    def sort_key(e: Event):
        return e.date_start or datetime(9999, 12, 31)

    all_events.sort(key=sort_key)

    with open(STORE_FILE, "w", encoding="utf-8") as f:
        json.dump([_event_to_dict(e) for e in all_events], f, indent=2, ensure_ascii=False)

    print(f"[Store] +{len(added)} new events. Total: {len(all_events)}")
    return all_events
