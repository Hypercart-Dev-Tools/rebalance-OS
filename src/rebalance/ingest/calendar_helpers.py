"""
Shared calendar helpers — canonical implementations for datetime parsing,
duration calculation, and database connection setup.

GUARD RAILS — DO NOT DUPLICATE THESE PATTERNS ELSEWHERE:

  - Raw `datetime.fromisoformat(x.replace('Z', ...))` → use parse_calendar_dt()
  - Raw `(end - start).total_seconds() / 60` → use event_duration_minutes()
  - Raw `get_connection() + ensure_calendar_schema()` → use calendar_connection()
  - Raw ISO text comparisons for upcoming events → use upcoming_calendar_rows()
    after a julianday() SQL prefilter. Calendar rows preserve source offsets,
    so string sorting/comparison will make local morning events look stale
    once the UTC clock reaches afternoon.

CI enforces this via grep checks in .github/workflows/ci.yml.
If you need an exception, add `# raw-ok` on the same line.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator


def parse_calendar_dt(raw: str) -> datetime:
    """Parse a Google Calendar datetime string into a Python datetime.

    Handles both full ISO datetimes and the trailing-Z convention
    used by the Google Calendar API. Returns a timezone-aware datetime
    when possible; date-only strings (all-day events) return naive.
    """
    from rebalance.lib.time_ops import _parse_iso
    parsed = _parse_iso(raw, force_utc=False)  # raw-ok: canonical location
    if parsed is None:
        raise ValueError(f"Invalid isoformat string: '{raw}'")
    return parsed


def calendar_dt_utc(raw: str | None) -> datetime | None:
    """Parse a calendar timestamp and normalize aware datetimes to UTC.

    Google Calendar stores timed events with their original offset
    (for example ``09:00:00-07:00``). Viewer queries must compare those
    values by instant, not lexicographic text order, or local morning
    events appear to be in the past once the UTC clock reaches afternoon.
    Date-only all-day values are returned as ``None`` because they do not
    identify a display-time instant.
    """
    if not raw:
        return None
    try:
        parsed = parse_calendar_dt(raw)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def normalize_aware_utc(dt: datetime) -> datetime:
    """Return *dt* in UTC, treating naive datetimes as UTC storage values."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def upcoming_calendar_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    now: datetime,
    limit: int | None = None,
    end_before: datetime | None = None,
    ignored_summaries: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Filter and sort calendar rows by absolute event start time.

    This is the shared viewer-side policy for "upcoming": parse each stored
    calendar offset, compare in UTC, apply optional ignore patterns, and only
    then return the requested number of rows. With no ``end_before`` this is a
    rolling window from ``now`` into the future, not a "today only" query.
    """
    now_utc = normalize_aware_utc(now)
    end_utc = normalize_aware_utc(end_before) if end_before is not None else None
    ignored = [pat.lower() for pat in ignored_summaries if pat]
    upcoming: list[tuple[datetime, dict[str, Any]]] = []

    for row in rows:
        item = dict(row)
        summary = str(item.get("summary") or "")
        if ignored and any(pat in summary.lower() for pat in ignored):
            continue
        start_utc = calendar_dt_utc(str(item.get("start_time") or ""))
        if start_utc is None or start_utc < now_utc:
            continue
        if end_utc is not None and start_utc >= end_utc:
            continue
        upcoming.append((start_utc, item))

    upcoming.sort(key=lambda pair: pair[0])
    if limit is not None:
        upcoming = upcoming[:limit]
    return [item for _, item in upcoming]


def event_duration_minutes(start_str: str, end_str: str) -> int:
    """Calculate event duration in minutes, returning 0 for unparseable
    or all-day events (naive datetimes without timezone info)."""
    if not start_str or not end_str:
        return 0
    try:
        start = parse_calendar_dt(start_str)
        end = parse_calendar_dt(end_str)
        if start.tzinfo is None or end.tzinfo is None:
            return 0
        return max(0, int((end - start).total_seconds() / 60))  # raw-ok: canonical location
    except Exception:
        return 0


@contextmanager
def calendar_connection(database_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Open a database connection with the calendar schema ensured.

    Usage:
        with calendar_connection(db_path) as conn:
            rows = conn.execute("SELECT ...").fetchall()

    Thin wrapper around :func:`db_connection` for callers that only need
    the calendar_events table.
    """
    from rebalance.ingest.db import db_connection, ensure_calendar_schema

    with db_connection(database_path, ensure_calendar_schema) as conn:  # raw-ok: canonical location
        yield conn
