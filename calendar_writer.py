"""
Google Calendar writer.
Uses a Service Account to add events to the "Sydnet Activities" calendar.

Colour coding:
  🟢 Sage   (colorId 2) — free events
  🍊 Tangerine (colorId 6) — outdoor / walks
  🍌 Banana (colorId 5) — paid events

The calendar must be shared with the service account email (Editor role).
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from scrapers.base import Event

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Set in GitHub Secrets
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

# Google Calendar color IDs
COLOR_FREE    = "2"  # Sage (green)
COLOR_OUTDOOR = "6"  # Tangerine (orange)
COLOR_PAID    = "5"  # Banana (yellow)

EMOJI_FREE    = "🟢"
EMOJI_OUTDOOR = "🌿"
EMOJI_PAID    = "💰"

REGION_LABELS = {
    "sydney": "Sydney",
    "blue_mountains": "Blue Mountains",
    "southern_highlands": "Southern Highlands",
    "hunter_valley": "Hunter Valley",
    "illawarra": "Illawarra",
}


class CalendarWriter:
    def __init__(self):
        creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not creds_json:
            raise EnvironmentError(
                "GOOGLE_SERVICE_ACCOUNT_JSON is not set. "
                "See SETUP.md for instructions."
            )
        creds_dict = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=SCOPES
        )
        self.service = build("calendar", "v3", credentials=creds)
        self.calendar_id = CALENDAR_ID
        logger.info(f"[Calendar] Connected. Target calendar ID: {self.calendar_id}")

    def add_event(self, event: Event) -> str:
        """
        Add a single Event to Google Calendar.
        Returns the created calendar event ID.
        """
        # --- Determine colour and emoji ---
        if event.ai_category == "outdoor":
            emoji, color_id = EMOJI_OUTDOOR, COLOR_OUTDOOR
        elif event.is_free:
            emoji, color_id = EMOJI_FREE, COLOR_FREE
        else:
            emoji, color_id = EMOJI_PAID, COLOR_PAID

        # --- Build title ---
        region_label = REGION_LABELS.get(event.ai_location_region, "")
        region_suffix = f" [{region_label}]" if region_label and region_label != "Sydney" else ""
        summary = f"{emoji} {event.title}{region_suffix}"

        # --- Build description ---
        parts: list[str] = []
        if event.description:
            parts.append(event.description)

        meta_lines = []
        if event.price_text:
            meta_lines.append(f"💵 Price: {event.price_text}")
        if event.ai_category:
            meta_lines.append(f"📂 Category: {event.ai_category.title()}")
        if region_label:
            meta_lines.append(f"📍 Region: {region_label}")
        meta_lines.append(f"🔗 Source: {event.url}")
        meta_lines.append(f"📰 Via: {event.source}")

        if meta_lines:
            parts.append("\n".join(meta_lines))

        description = "\n\n".join(parts)

        # --- Build date/time ---
        start, end = _build_datetime(event)

        # --- Assemble event body ---
        body = {
            "summary": summary,
            "description": description,
            "location": event.location or "",
            "colorId": color_id,
            "start": start,
            "end": end,
        }

        try:
            created = self.service.events().insert(
                calendarId=self.calendar_id,
                body=body,
            ).execute()
            event_id = created["id"]
            logger.info(f"[Calendar] Added: {summary} → {event_id}")
            return event_id
        except HttpError as e:
            logger.error(f"[Calendar] Failed to add '{event.title}': {e}")
            raise


def _build_datetime(event: Event) -> tuple[dict, dict]:
    """
    Return (start, end) dicts for the Calendar API.
    Falls back to a sensible default if dates are missing.
    """
    tz = "Australia/Sydney"

    if event.date_start:
        dt = event.date_start
        # Treat midnight as "all-day" (no specific time)
        if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
            date_str = dt.strftime("%Y-%m-%d")
            end_dt = event.date_end or (dt + timedelta(days=1))
            end_str = end_dt.strftime("%Y-%m-%d")
            return {"date": date_str}, {"date": end_str}
        else:
            start_iso = dt.isoformat()
            end_dt = event.date_end or (dt + timedelta(hours=2))
            end_iso = end_dt.isoformat()
            return (
                {"dateTime": start_iso, "timeZone": tz},
                {"dateTime": end_iso,   "timeZone": tz},
            )
    else:
        # No date available — mark as an all-day event for today
        # (the AI filter should flag undated entries; this is a safety fallback)
        from datetime import date
        today = date.today().isoformat()
        return {"date": today}, {"date": today}
