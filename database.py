"""
SQLite-backed deduplication store.
Tracks which event URLs have already been added to the calendar.
The events.db file is committed to the GitHub repo so state persists between runs.
"""
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

# Store DB next to this file (i.e. in the repo root)
DB_PATH = os.path.join(os.path.dirname(__file__), "events.db")


class EventDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_events (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    url               TEXT    UNIQUE NOT NULL,
                    title             TEXT,
                    source            TEXT,
                    category          TEXT,
                    is_free           INTEGER DEFAULT 0,
                    calendar_event_id TEXT,
                    processed_at      TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.commit()
        logger.debug(f"[DB] Initialised at {self.db_path}")

    def is_duplicate(self, url: str) -> bool:
        """Return True if this URL has already been processed."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT 1 FROM processed_events WHERE url = ?", (url,)
            )
            return cur.fetchone() is not None

    def mark_processed(
        self,
        url: str,
        title: str = "",
        source: str = "",
        category: str = "",
        is_free: bool = False,
        calendar_event_id: str = "",
    ):
        """Record that an event URL has been processed and added to the calendar."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO processed_events
                   (url, title, source, category, is_free, calendar_event_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (url, title, source, category, int(is_free), calendar_event_id),
            )
            conn.commit()
        logger.debug(f"[DB] Recorded: {title or url}")

    def stats(self) -> dict:
        """Return summary counts for logging."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM processed_events").fetchone()[0]
            free  = conn.execute(
                "SELECT COUNT(*) FROM processed_events WHERE is_free = 1"
            ).fetchone()[0]
        return {"total": total, "free": free}
