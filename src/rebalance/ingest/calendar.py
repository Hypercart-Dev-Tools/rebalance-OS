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
import pickle
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


TOKEN_PATH = Path.home() / ".config" / "gcalcli" / "oauth"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_WRITE_SCOPE = "https://www.googleapis.com/auth/calendar"


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


@dataclass
class CalendarCreateResult:
    event_id: str
    html_link: str
    calendar_id: str
    summary: str
    start_time: str
    end_time: str
    attendees_count: int


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _credentials_have_scopes(creds: Any, required_scopes: list[str]) -> bool:
    """Return True if the credentials cover every required scope."""
    current = set(getattr(creds, "scopes", []) or [])
    return all(scope in current for scope in required_scopes)


def _load_credentials(required_scopes: list[str] | None = None) -> Any:
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

    if required_scopes and not _credentials_have_scopes(creds, required_scopes):
        raise PermissionError(
            "Calendar OAuth token does not include the required scopes. "
            f"Required: {required_scopes}. Current: {getattr(creds, 'scopes', []) or []}. "
            "Re-run the OAuth flow with write access enabled."
        )

    return creds


def _build_service(required_scopes: list[str] | None = None) -> Any:
    """Build a Google Calendar API service client."""
    from googleapiclient.discovery import build
    creds = _load_credentials(required_scopes=required_scopes)
    return build("calendar", "v3", credentials=creds)


# Re-export so existing callers (e.g. tests) that import from here keep working.
from rebalance.ingest.db import ensure_calendar_schema  # noqa: F401


# ---------------------------------------------------------------------------
# Fetch + persist
# ---------------------------------------------------------------------------


def sync_calendar(
    database_path: Path,
    *,
    calendar_id: str = "primary",
    days_back: int = 30,
    days_forward: int = 7,
) -> CalendarSyncResult:
    """Fetch calendar events and persist to SQLite.

    Default window: 30 days back + 7 days forward.
    For initial backfill, pass days_back=365.
    Retention: events are never auto-deleted. Run cleanup manually if needed.

    Args:
        database_path: Path to SQLite database
        calendar_id: Calendar to fetch from (default: "primary"). Use calendar email or group ID for other calendars.
        days_back: How many days back to fetch (default 30)
        days_forward: How many days forward to fetch (default 7)
    """
    start = time.monotonic()
    service = _build_service(required_scopes=[CALENDAR_READONLY_SCOPE])

    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=days_back)).isoformat()
    time_max = (now + timedelta(days=days_forward)).isoformat()
    fetched_at = now.isoformat()

    # Paginate through events
    all_events: list[dict[str, Any]] = []
    page_token = None
    while True:
        result = service.events().list(
            calendarId=calendar_id,
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
    from rebalance.ingest.calendar_helpers import calendar_connection

    stored = 0
    with calendar_connection(database_path) as conn:
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
                    calendar_id,
                    status,
                    description,
                    fetched_at,
                ),
            )
            stored += 1

        conn.commit()

    return CalendarSyncResult(
        events_fetched=len(all_events),
        events_stored=stored,
        window_start=time_min[:10],
        window_end=time_max[:10],
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


def create_calendar_event(
    *,
    calendar_id: str = "primary",
    summary: str,
    start_time: str,
    end_time: str,
    timezone_name: str | None = None,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
) -> CalendarCreateResult:
    """Create a Google Calendar event using the local OAuth token."""
    if not summary.strip():
        raise ValueError("summary is required")
    if not start_time.strip() or not end_time.strip():
        raise ValueError("start_time and end_time are required")

    from rebalance.ingest.calendar_helpers import parse_calendar_dt

    start_dt = parse_calendar_dt(start_time)
    end_dt = parse_calendar_dt(end_time)
    if end_dt <= start_dt:
        raise ValueError("end_time must be after start_time")
    if start_dt.tzinfo is None or end_dt.tzinfo is None:
        raise ValueError("start_time and end_time must be timezone-aware ISO datetimes")

    service = _build_service(required_scopes=[CALENDAR_WRITE_SCOPE])

    payload: dict[str, Any] = {
        "summary": summary.strip(),
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
    }
    if timezone_name:
        payload["start"]["timeZone"] = timezone_name
        payload["end"]["timeZone"] = timezone_name
    if description.strip():
        payload["description"] = description.strip()
    if location.strip():
        payload["location"] = location.strip()

    normalized_attendees = [{"email": email.strip()} for email in (attendees or []) if email.strip()]
    if normalized_attendees:
        payload["attendees"] = normalized_attendees

    event = (
        service.events()
        .insert(calendarId=calendar_id, body=payload, sendUpdates="all" if normalized_attendees else "none")
        .execute()
    )

    return CalendarCreateResult(
        event_id=event.get("id", ""),
        html_link=event.get("htmlLink", ""),
        calendar_id=calendar_id,
        summary=event.get("summary", summary.strip()),
        start_time=event.get("start", {}).get("dateTime", start_dt.isoformat()),
        end_time=event.get("end", {}).get("dateTime", end_dt.isoformat()),
        attendees_count=len(event.get("attendees", normalized_attendees)),
    )


# ---------------------------------------------------------------------------
# Query (used by querier.py)
# ---------------------------------------------------------------------------


def get_upcoming_events(
    database_path: Path,
    days_forward: int = 2,
) -> list[dict[str, Any]]:
    """Return upcoming events from the calendar_events table."""
    from rebalance.ingest.calendar_helpers import calendar_connection

    now = datetime.now(timezone.utc).isoformat()
    cutoff = (datetime.now(timezone.utc) + timedelta(days=days_forward)).isoformat()

    with calendar_connection(database_path) as conn:
        rows = conn.execute(
            """SELECT summary, start_time, end_time, location, attendees_json, description
               FROM calendar_events
               WHERE start_time >= ? AND start_time <= ?
               ORDER BY start_time ASC
               LIMIT 30""",
            (now, cutoff),
        ).fetchall()

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
    from rebalance.ingest.calendar_helpers import calendar_connection

    now = datetime.now(timezone.utc).isoformat()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    with calendar_connection(database_path) as conn:
        rows = conn.execute(
            """SELECT summary, start_time, end_time, location, attendees_json
               FROM calendar_events
               WHERE start_time >= ? AND start_time < ?
               ORDER BY start_time DESC
               LIMIT 50""",
            (cutoff, now),
        ).fetchall()

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


@dataclass
class DailyEventTotal:
    """Summary of events for a single day."""
    date: str  # YYYY-MM-DD format
    day_name: str  # Monday, Tuesday, etc.
    event_count: int
    total_minutes: int  # Sum of event durations

    @property
    def total_hours(self) -> float:
        """Total hours as decimal (e.g., 2.5 for 2h 30m)."""
        return self.total_minutes / 60.0

    def __str__(self) -> str:
        hours = int(self.total_hours)
        minutes = self.total_minutes % 60
        if hours > 0:
            duration = f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        else:
            duration = f"{minutes}m"
        return f"{self.date} ({self.day_name}): {self.event_count} events, {duration} booked"


def get_daily_totals(
    database_path: Path,
    days_back: int = 30,
    days_forward: int = 0,
) -> list[DailyEventTotal]:
    """Calculate event count and total duration per day (raw, unfiltered).

    Returns days sorted chronologically (oldest first).
    """
    from rebalance.ingest.calendar_helpers import (
        calendar_connection,
        event_duration_minutes,
        parse_calendar_dt,
    )

    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days_back)).date()
    end_date = (now + timedelta(days=days_forward)).date()

    with calendar_connection(database_path) as conn:
        rows = conn.execute(
            """SELECT start_time, end_time
               FROM calendar_events
               WHERE DATE(start_time) >= ? AND DATE(start_time) <= ?
               ORDER BY start_time ASC""",
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

    # Aggregate by day
    daily_data: dict[str, tuple[int, int]] = {}  # date -> (count, total_minutes)

    for row in rows:
        start_str = row["start_time"]
        end_str = row["end_time"]

        try:
            start_dt = parse_calendar_dt(start_str)
        except Exception:
            continue

        minutes = event_duration_minutes(start_str, end_str)
        date_str = start_dt.date().isoformat()
        count, total_mins = daily_data.get(date_str, (0, 0))
        daily_data[date_str] = (count + 1, total_mins + minutes)

    # Convert to result objects
    results = []
    for date_str in sorted(daily_data.keys()):
        count, total_mins = daily_data[date_str]
        day_obj = datetime.fromisoformat(date_str).date()  # raw-ok: date-only string, no Z
        day_name = day_obj.strftime("%A")

        results.append(DailyEventTotal(
            date=date_str,
            day_name=day_name,
            event_count=count,
            total_minutes=max(0, total_mins),
        ))

    return results
