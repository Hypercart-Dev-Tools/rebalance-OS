"""
Shared calendar helpers — canonical implementations for datetime parsing,
duration calculation, and database connection setup.

GUARD RAILS — DO NOT DUPLICATE THESE PATTERNS ELSEWHERE:

  - Raw `datetime.fromisoformat(x.replace('Z', ...))` → use parse_calendar_dt()
  - Raw `(end - start).total_seconds() / 60` → use event_duration_minutes()
  - Raw `get_connection() + ensure_calendar_schema()` → use calendar_connection()

CI enforces this via grep checks in .github/workflows/ci.yml.
If you need an exception, add `# raw-ok` on the same line.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator


def parse_calendar_dt(raw: str) -> datetime:
    """Parse a Google Calendar datetime string into a Python datetime.

    Handles both full ISO datetimes and the trailing-Z convention
    used by the Google Calendar API. Returns a timezone-aware datetime
    when possible; date-only strings (all-day events) return naive.
    """
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))  # raw-ok: canonical location


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
    """
    from rebalance.ingest.calendar import ensure_calendar_schema
    from rebalance.ingest.db import get_connection

    conn = get_connection(database_path)
    ensure_calendar_schema(conn)  # raw-ok: canonical location
    try:
        yield conn
    finally:
        conn.close()
