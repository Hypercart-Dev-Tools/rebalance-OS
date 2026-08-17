"""
Google Calendar collector — fetches events via Google Calendar API,
persists to SQLite for historical queries (default window 30d back /
7d forward; 365-day backfill available; no automatic deletion), and
provides context for the ask tool.

Uses the google-api-python-client directly (not gcalcli) for reliable
non-interactive usage.

OAuth token stored at ~/.config/rebalance-os/google-calendar-oauth (pickle format).
Not embedded — structured data only. Calendar events are low-signal
for vector search but high-signal for scheduling context.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


from rebalance.ingest.calendar_config import OPERATOR_CALENDAR_ID
from rebalance.lib.time_ops import parse_date
from rebalance.paths import resolve_oauth_token_path
TOKEN_PATH = resolve_oauth_token_path("calendar")
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
    calendar_id: str = ""  # the calendar actually fetched/stored (post-resolution)


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
    """Return True if the credentials cover every required scope.

    Google Calendar OAuth scopes have a hierarchy: the full ``.../auth/calendar``
    scope (read/write) is a superset of every narrower calendar scope
    (e.g. ``.../calendar.readonly``, ``.../calendar.events``). A token that
    holds the full scope therefore satisfies any narrower requirement.
    """
    current = set(getattr(creds, "scopes", []) or [])
    if "https://www.googleapis.com/auth/calendar" in current:
        current |= {
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.events.readonly",
            "https://www.googleapis.com/auth/calendar.settings.readonly",
        }
    return all(scope in current for scope in required_scopes)


def _load_credentials(required_scopes: list[str] | None = None) -> Any:
    """Load OAuth2 credentials — keyring first, pickle file as the launchd fallback.

    Delegates the keyring→pickle→refresh→persist-both flow to
    :func:`rebalance.ingest.oauth_common.load_credentials`; only the
    Calendar-specific error messages and scope-superset rule live here.
    """
    from rebalance.ingest import oauth_common
    from rebalance.ingest.config import (
        get_calendar_oauth_token_json,
        set_calendar_oauth_token_json,
    )

    def _missing(token_path: str) -> Exception:
        return FileNotFoundError(
            f"Calendar OAuth token not found (keyring empty and no file at {token_path}). "
            "Run the OAuth flow first (see PROJECT.md — P2 Google Calendar)."
        )

    def _scope_error(creds: Any, required: list[str]) -> Exception:
        return PermissionError(
            "Calendar OAuth token does not include the required scopes. "
            f"Required: {required}. Current: {getattr(creds, 'scopes', []) or []}. "
            "Re-run the OAuth flow with write access enabled."
        )

    svc = oauth_common.OAuthService(
        name="calendar",
        token_path=TOKEN_PATH,
        get_token_json=get_calendar_oauth_token_json,
        set_token_json=set_calendar_oauth_token_json,
        has_scopes=_credentials_have_scopes,
        missing_error=_missing,
        scope_error=_scope_error,
    )
    return oauth_common.load_credentials(svc, required_scopes)


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


def refresh_calendar_source(
    database_path: Path,
    *,
    calendar_id: str = "",
    person: str | None = None,
    days_back: int = 30,
    days_forward: int = 7,
) -> CalendarSyncResult:
    """Source-owned entry point for the calendar sync.

    Resolves the calendar id (explicit arg, else ``CalendarConfig``) and runs
    :func:`sync_calendar`. The CLI (`calendar-sync`) uses this so no surface
    imports the leaf ``sync_calendar`` directly
    (COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2).

    The operator's *own default* calendar (no explicit ``calendar_id``, resolved
    from config) is stored as ``"primary"`` — Google's alias for the
    authenticated user's default calendar — so DB read/export filters stay
    correct. An EXPLICIT ``calendar_id`` (e.g. ``calendar-sync --calendar-id``)
    is synced verbatim under that id: the caller asked for a specific calendar
    and must get exactly that, not a silent rewrite to ``"primary"``.
    """
    from rebalance.ingest.calendar_config import CalendarConfig, OPERATOR_CALENDAR_ID

    explicit = bool(calendar_id)
    resolved = calendar_id or CalendarConfig.load().calendar_id
    if person is None and not explicit and resolved != OPERATOR_CALENDAR_ID:
        resolved = OPERATOR_CALENDAR_ID
    return sync_calendar(
        database_path=database_path,
        calendar_id=resolved,
        person=person,
        days_back=days_back,
        days_forward=days_forward,
    )


def sync_calendar(
    database_path: Path,
    *,
    # 'primary' here is Google's Calendar API alias for the authenticated user's
    # default calendar (the write/fetch target), NOT a DB read filter — left as a
    # literal on purpose (do not swap for OPERATOR_CALENDAR_ID).
    calendar_id: str = "primary",
    person: str | None = None,
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
        person: Attribution label stored in the ``person`` column. ``None`` = operator (self).
            Teammate calendars must supply a non-empty label (e.g. "matthew").
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
    from rebalance.ingest.db import run_migrations

    stored = 0
    with calendar_connection(database_path) as conn:
        # Ensure the schema is fully migrated before writing the ``person``
        # column (migration 0005). ``refresh_index`` migrates up front, but
        # direct callers — e.g. the ``calendar-sync`` CLI — reach this leaf
        # without that step and would otherwise hit a pre-0005 table and crash
        # with "no such column: person". This is the single writer of
        # calendar_events, so guaranteeing the schema here covers every path.
        # Idempotent: a cheap no-op once the database is at the latest version.
        run_migrations(conn)
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
                    calendar_id, status, description, fetched_at, person)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    person,
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
        calendar_id=calendar_id,
    )


def create_calendar_event(
    *,
    # 'primary' here is Google's Calendar API alias for the authenticated user's
    # default calendar (the create target), NOT a DB read filter — left as a
    # literal on purpose (do not swap for OPERATOR_CALENDAR_ID).
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


def _calendar_id_filter(calendar_id: str | None) -> tuple[str, tuple]:
    """SQL fragment + params to optionally restrict a query to one calendar.

    Callers default to ``"primary"`` (the operator's own calendar) so personal
    views never mix in teammate calendars; pass ``None`` to include every
    calendar (the team-blended views added in P2 Phase 2).
    """
    if calendar_id is None:
        return "", ()
    return "AND calendar_id = ?", (calendar_id,)


def _person_filter(persons: list[str] | None) -> tuple[str, tuple]:
    """SQL fragment + params to optionally restrict a query to named teammates.

    Privacy-sensitive sibling of :func:`_calendar_id_filter`: centralizes the
    ``person`` predicate so the single team-scoped reader is the only place that
    SELECTs by person. Returns ``("", ())`` when *persons* is ``None``/empty
    (no restriction); otherwise an ``AND person IN (?,?...)`` clause matching the
    given labels. Operator rows (``person IS NULL``) never match an ``IN`` list,
    so they are excluded by construction.
    """
    if not persons:
        return "", ()
    placeholders = ",".join("?" for _ in persons)
    return f"AND person IN ({placeholders})", tuple(persons)


def _query_events(
    database_path: Path,
    *,
    where: str,
    params: tuple,
    order: str = "ASC",
    limit: int = 30,
    include_person: bool = False,
) -> list[dict[str, Any]]:
    """Shared SELECT/window/row-map body for the upcoming-event readers.

    ``where`` is a fully-formed predicate already containing any optional
    calendar/person fragments; ``params`` carries its bound values. ``order`` is
    the ``start_time`` sort direction. ``include_person`` adds the privacy-
    sensitive ``person`` column to the SELECT and the mapped rows — set ONLY by
    the in-process team reader, never by operator/export-facing callers.
    """
    from rebalance.ingest.calendar_helpers import calendar_connection

    extra_cols = ", person, calendar_id, id" if include_person else ""
    with calendar_connection(database_path) as conn:
        rows = conn.execute(
            f"""SELECT summary, start_time, end_time, location, attendees_json,
                      description{extra_cols}
               FROM calendar_events
               WHERE {where}
               ORDER BY julianday(start_time) {order}
               LIMIT {limit}""",
            params,
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        mapped = {
            "summary": row["summary"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "location": row["location"],
            "attendees": json.loads(row["attendees_json"]) if row["attendees_json"] else [],
            "description": (row["description"] or "")[:200],
        }
        if include_person:
            mapped["person"] = row["person"]
            mapped["calendar_id"] = row["calendar_id"]
            mapped["id"] = row["id"]
        results.append(mapped)
    return results


def get_upcoming_events(
    database_path: Path,
    days_forward: int = 2,
    calendar_id: str | None = OPERATOR_CALENDAR_ID,
) -> list[dict[str, Any]]:
    """Return upcoming events from the calendar_events table.

    Defaults to the operator's own ``OPERATOR_CALENDAR_ID`` calendar; pass
    ``calendar_id=None`` to include all calendars (team views).
    """
    now = datetime.now(timezone.utc).isoformat()
    cutoff = (datetime.now(timezone.utc) + timedelta(days=days_forward)).isoformat()

    cal_clause, cal_params = _calendar_id_filter(calendar_id)
    where = (
        "julianday(start_time) >= julianday(?) "
        "AND julianday(start_time) <= julianday(?) "
        f"{cal_clause}"
    )
    return _query_events(
        database_path,
        where=where,
        params=(now, cutoff, *cal_params),
        order="ASC",
        limit=30,
    )


def get_team_upcoming_by_person(
    database_path: Path,
    persons: list[str],
    days_forward: int = 2,
) -> list[dict[str, Any]]:
    """Return upcoming teammate events for the named ``persons`` only.

    The ONLY reader that SELECTs the privacy-sensitive ``person`` column. Operator
    rows (``person IS NULL``) are excluded by construction — they never match the
    ``person IN (...)`` predicate. This reader is in-process/local-only (the v0.5
    "what next" team view); its output, which carries ``person``/``calendar_id``,
    must NEVER reach the export/pushed-pulse path.

    Returns ``[]`` for an empty ``persons`` list (no teammates → no rows), rather
    than falling back to an unrestricted scan.
    """
    if not persons:
        return []

    now = datetime.now(timezone.utc).isoformat()
    cutoff = (datetime.now(timezone.utc) + timedelta(days=days_forward)).isoformat()

    person_clause, person_params = _person_filter(persons)
    where = (
        "julianday(start_time) >= julianday(?) "
        "AND julianday(start_time) <= julianday(?) "
        f"{person_clause}"
    )
    return _query_events(
        database_path,
        where=where,
        params=(now, cutoff, *person_params),
        order="ASC",
        limit=30,
        include_person=True,
    )


def get_recent_events(
    database_path: Path,
    days_back: int = 7,
    calendar_id: str | None = OPERATOR_CALENDAR_ID,
) -> list[dict[str, Any]]:
    """Return past events for activity/meeting-load context.

    Defaults to the operator's own ``OPERATOR_CALENDAR_ID`` calendar; pass
    ``calendar_id=None`` to include all calendars (team views).
    """
    from rebalance.ingest.calendar_helpers import calendar_connection

    now = datetime.now(timezone.utc).isoformat()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    cal_clause, cal_params = _calendar_id_filter(calendar_id)
    with calendar_connection(database_path) as conn:
        rows = conn.execute(
            f"""SELECT summary, start_time, end_time, location, attendees_json
               FROM calendar_events
               WHERE julianday(start_time) >= julianday(?)
                 AND julianday(start_time) < julianday(?)
                 {cal_clause}
               ORDER BY julianday(start_time) DESC
               LIMIT 50""",
            (cutoff, now, *cal_params),
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
    calendar_id: str | None = OPERATOR_CALENDAR_ID,
) -> list[DailyEventTotal]:
    """Calculate event count and total duration per day.

    Defaults to the operator's own ``OPERATOR_CALENDAR_ID`` calendar so totals
    aren't inflated by teammate calendars; pass ``calendar_id=None`` to aggregate
    all calendars. Returns days sorted chronologically (oldest first).
    """
    from rebalance.ingest.calendar_helpers import (
        calendar_connection,
        event_duration_minutes,
        parse_calendar_dt,
    )

    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days_back)).date()
    end_date = (now + timedelta(days=days_forward)).date()

    cal_clause, cal_params = _calendar_id_filter(calendar_id)
    with calendar_connection(database_path) as conn:
        rows = conn.execute(
            f"""SELECT start_time, end_time
               FROM calendar_events
               WHERE DATE(start_time) >= ? AND DATE(start_time) <= ?
                 {cal_clause}
               ORDER BY start_time ASC""",
            (start_date.isoformat(), end_date.isoformat(), *cal_params),
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
        day_obj = parse_date(date_str)
        day_name = day_obj.strftime("%A") if day_obj else ""

        results.append(DailyEventTotal(
            date=date_str,
            day_name=day_name,
            event_count=count,
            total_minutes=max(0, total_mins),
        ))

    return results
