"""Reader scope (P2 gap #5): the personal calendar readers default to the
operator's own 'primary' calendar and must not mix in teammate calendars.
Passing calendar_id=None opts into all calendars (future team-blended views)."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rebalance.ingest.calendar import (
    _calendar_id_filter,
    get_daily_totals,
    get_recent_events,
    get_upcoming_events,
)


def _past(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _future(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _seed(db: Path, rows: list[dict]) -> None:
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY, summary TEXT, start_time TEXT NOT NULL,
            end_time TEXT, location TEXT, attendees_json TEXT,
            calendar_id TEXT NOT NULL DEFAULT 'primary',
            status TEXT, description TEXT, fetched_at TEXT NOT NULL
        )
    """)
    for r in rows:
        conn.execute(
            "INSERT OR REPLACE INTO calendar_events VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r["id"], r["summary"], r["start"], r["end"], None, None,
             r["cal"], "confirmed", None, "2026-06-01T00:00:00Z"),
        )
    conn.commit()
    conn.close()


class TestReaderScope(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "rebalance.db"
        _seed(self.db, [
            {"id": "mine", "summary": "My block",
             "start": _past(1), "end": _past(1), "cal": "primary"},
            {"id": "mate", "summary": "Teammate block",
             "start": _past(1), "end": _past(1),
             "cal": "teammate@group.calendar.google.com"},
        ])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_recent_events_default_primary_only(self) -> None:
        summaries = [e["summary"] for e in get_recent_events(self.db)]
        self.assertIn("My block", summaries)
        self.assertNotIn("Teammate block", summaries)

    def test_recent_events_none_includes_all(self) -> None:
        summaries = [e["summary"] for e in get_recent_events(self.db, calendar_id=None)]
        self.assertIn("My block", summaries)
        self.assertIn("Teammate block", summaries)

    def test_daily_totals_default_excludes_teammate(self) -> None:
        default_events = sum(d.event_count for d in get_daily_totals(self.db))
        all_events = sum(d.event_count for d in get_daily_totals(self.db, calendar_id=None))
        self.assertEqual(default_events, 1)
        self.assertEqual(all_events, 2)

    def test_upcoming_events_default_primary_only(self) -> None:
        _seed(self.db, [
            {"id": "up-mine", "summary": "My upcoming",
             "start": _future(1), "end": _future(1), "cal": "primary"},
            {"id": "up-mate", "summary": "Teammate upcoming",
             "start": _future(1), "end": _future(1),
             "cal": "teammate@group.calendar.google.com"},
        ])
        summaries = [e["summary"] for e in get_upcoming_events(self.db)]
        self.assertIn("My upcoming", summaries)
        self.assertNotIn("Teammate upcoming", summaries)

    def test_upcoming_events_none_includes_all(self) -> None:
        _seed(self.db, [
            {"id": "up-mine", "summary": "My upcoming",
             "start": _future(1), "end": _future(1), "cal": "primary"},
            {"id": "up-mate", "summary": "Teammate upcoming",
             "start": _future(1), "end": _future(1),
             "cal": "teammate@group.calendar.google.com"},
        ])
        summaries = [e["summary"] for e in get_upcoming_events(self.db, calendar_id=None)]
        self.assertIn("My upcoming", summaries)
        self.assertIn("Teammate upcoming", summaries)


class TestCalendarIdFilter(unittest.TestCase):
    """The shared helper that the readers default through (calendar.py)."""

    def test_none_is_no_restriction(self) -> None:
        self.assertEqual(_calendar_id_filter(None), ("", ()))

    def test_value_is_parameterized_clause(self) -> None:
        self.assertEqual(
            _calendar_id_filter("primary"), ("AND calendar_id = ?", ("primary",)))


if __name__ == "__main__":
    unittest.main()
