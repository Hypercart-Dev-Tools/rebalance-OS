"""
Google Calendar collector — fetches events via Google Calendar API,
persists to SQLite for historical queries (1 year retention), and
provides context for the ask tool.

Uses the google-api-python-client directly (not gcalcli) for reliable
non-interactive usage.

OAuth token stored at ~/.config/gcalcli/oauth (pickle format).
Not embedded — structured data only. Calendar events are low-signal
for vector search but high-signal for scheduling context.
"""

from __future__ import annotations

import json
import os
import pickle
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


TOKEN_PATH = Path.home() / ".config" / "gcalcli" / "oauth"

CALENDAR_SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_events (
    id              TEXT PRIMARY KEY,
    summary         TEXT,
    start_time      TEXT NOT NULL,
    end_time        TEXT,
    location        TEXT,
    attendees_json  TEXT,
    calendar_id     TEXT NOT NULL DEFAULT 'primary',
    status          TEXT,
    description     TEXT,
    fetched_at      TEXT NOT NULL
)
"""

CALENDAR_INDEX = """
CREATE INDEX IF NOT EXISTS idx_calendar_start ON calendar_events(start_time)
"""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CalendarSyncResult:
    events_fetched: int
    events_stored: int
    window_start: str
    window_end: str
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _load_credentials() -> Any:
    """Load OAuth2 credentials from the stored token file."""
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"Calendar OAuth token not found at {TOKEN_PATH}. "
            "Run the OAuth flow first (see PROJECT.md — P2 Google Calendar)."
        )
    with open(TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return creds


def _build_service() -> Any:
    """Build a Google Calendar API service client."""
    from googleapiclient.discovery import build
    creds = _load_credentials()
    return build("calendar", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def ensure_calendar_schema(conn: sqlite3.Connection) -> None:
    """Create calendar_events table if it doesn't exist."""
    conn.execute(CALENDAR_SCHEMA)
    conn.execute(CALENDAR_INDEX)
    conn.commit()


# ---------------------------------------------------------------------------
# Fetch + persist
# ---------------------------------------------------------------------------


def sync_calendar(
    database_path: Path,
    *,
    days_back: int = 30,
    days_forward: int = 7,
) -> CalendarSyncResult:
    """Fetch calendar events and persist to SQLite.

    Default window: 30 days back + 7 days forward.
    For initial backfill, pass days_back=365.
    Retention: events are never auto-deleted. Run cleanup manually if needed.
    """
    start = time.monotonic()
    service = _build_service()

    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=days_back)).isoformat()
    time_max = (now + timedelta(days=days_forward)).isoformat()
    fetched_at = now.isoformat()

    # Paginate through events
    all_events: list[dict[str, Any]] = []
    page_token = None
    while True:
        result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=250,
            pageToken=page_token,
        ).execute()

        all_events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    # Persist
    from rebalance.ingest.db import get_connection
    conn = get_connection(database_path)
    ensure_calendar_schema(conn)

    stored = 0
    for event in all_events:
        event_id = event.get("id", "")
        summary = event.get("summary", "")
        start_dt = event.get("start", {})
        end_dt = event.get("end", {})
        start_time = start_dt.get("dateTime", start_dt.get("date", ""))
        end_time = end_dt.get("dateTime", end_dt.get("date", ""))
        location = event.get("location", "")
        description = event.get("description", "")
        status = event.get("status", "")

        attendees = []
        for a in event.get("attendees", []):
            attendees.append({
                "email": a.get("email", ""),
                "name": a.get("displayName", ""),
                "response": a.get("responseStatus", ""),
            })

        conn.execute(
            """INSERT OR REPLACE INTO calendar_events
               (id, summary, start_time, end_time, location, attendees_json,
                calendar_id, status, description, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                summary,
                start_time,
                end_time,
                location,
                json.dumps(attendees),
                "primary",
                status,
                description,
                fetched_at,
            ),
        )
        stored += 1

    conn.commit()
    conn.close()

    return CalendarSyncResult(
        events_fetched=len(all_events),
        events_stored=stored,
        window_start=time_min[:10],
        window_end=time_max[:10],
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


# ---------------------------------------------------------------------------
# Query (used by querier.py)
# ---------------------------------------------------------------------------


def get_upcoming_events(
    database_path: Path,
    days_forward: int = 2,
) -> list[dict[str, Any]]:
    """Return upcoming events from the calendar_events table."""
    from rebalance.ingest.db import get_connection
    conn = get_connection(database_path)
    ensure_calendar_schema(conn)

    now = datetime.now(timezone.utc).isoformat()
    cutoff = (datetime.now(timezone.utc) + timedelta(days=days_forward)).isoformat()

    rows = conn.execute(
        """SELECT summary, start_time, end_time, location, attendees_json, description
           FROM calendar_events
           WHERE start_time >= ? AND start_time <= ?
           ORDER BY start_time ASC
           LIMIT 30""",
        (now, cutoff),
    ).fetchall()
    conn.close()

    return [
        {
            "summary": row["summary"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "location": row["location"],
            "attendees": json.loads(row["attendees_json"]) if row["attendees_json"] else [],
            "description": (row["description"] or "")[:200],
        }
        for row in rows
    ]


def get_recent_events(
    database_path: Path,
    days_back: int = 7,
) -> list[dict[str, Any]]:
    """Return past events for activity/meeting-load context."""
    from rebalance.ingest.db import get_connection
    conn = get_connection(database_path)
    ensure_calendar_schema(conn)

    now = datetime.now(timezone.utc).isoformat()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    rows = conn.execute(
        """SELECT summary, start_time, end_time, location, attendees_json
           FROM calendar_events
           WHERE start_time >= ? AND start_time < ?
           ORDER BY start_time DESC
           LIMIT 50""",
        (cutoff, now),
    ).fetchall()
    conn.close()

    return [
        {
            "summary": row["summary"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "location": row["location"],
            "attendees": json.loads(row["attendees_json"]) if row["attendees_json"] else [],
        }
        for row in rows
    ]
