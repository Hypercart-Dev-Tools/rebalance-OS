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
    _person_filter,
    get_daily_totals,
    get_recent_events,
    get_team_upcoming_by_person,
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


class TestPersonFilter(unittest.TestCase):
    """Privacy-sensitive sibling helper: the only place person is SELECTed by."""

    def test_none_is_no_restriction(self) -> None:
        self.assertEqual(_person_filter(None), ("", ()))

    def test_empty_list_is_no_restriction(self) -> None:
        self.assertEqual(_person_filter([]), ("", ()))

    def test_labels_become_parameterized_in_clause(self) -> None:
        self.assertEqual(
            _person_filter(["a", "b"]),
            ("AND person IN (?,?)", ("a", "b")),
        )


def _seed_with_person(db: Path, rows: list[dict]) -> None:
    """Seed including the privacy-sensitive person column (operator => NULL)."""
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY, summary TEXT, start_time TEXT NOT NULL,
            end_time TEXT, location TEXT, attendees_json TEXT,
            calendar_id TEXT NOT NULL DEFAULT 'primary',
            status TEXT, description TEXT, person TEXT, fetched_at TEXT NOT NULL
        )
    """)
    for r in rows:
        conn.execute(
            "INSERT OR REPLACE INTO calendar_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (r["id"], r["summary"], r["start"], r["end"], None, None,
             r["cal"], "confirmed", None, r.get("person"), "2026-06-01T00:00:00Z"),
        )
    conn.commit()
    conn.close()


class TestTeamUpcomingByPerson(unittest.TestCase):
    """get_team_upcoming_by_person: the ONLY reader that SELECTs person, and it
    must return person-labelled teammate rows only (operator person-IS-NULL
    rows excluded by construction)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "rebalance.db"
        _seed_with_person(self.db, [
            {"id": "op", "summary": "Operator block",
             "start": _future(1), "end": _future(1),
             "cal": "primary", "person": None},
            {"id": "matt", "summary": "Matt block",
             "start": _future(1), "end": _future(1),
             "cal": "matt@group.calendar.google.com", "person": "Matt"},
            {"id": "jose", "summary": "Jose block",
             "start": _future(1), "end": _future(1),
             "cal": "jose@group.calendar.google.com", "person": "Jose"},
        ])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_only_named_teammates(self) -> None:
        events = get_team_upcoming_by_person(self.db, ["Matt"])
        summaries = [e["summary"] for e in events]
        self.assertEqual(summaries, ["Matt block"])
        self.assertEqual(events[0]["person"], "Matt")

    def test_operator_rows_excluded_by_construction(self) -> None:
        events = get_team_upcoming_by_person(self.db, ["Matt", "Jose"])
        summaries = {e["summary"] for e in events}
        self.assertEqual(summaries, {"Matt block", "Jose block"})
        self.assertNotIn("Operator block", summaries)
        self.assertTrue(all(e["person"] is not None for e in events))

    def test_empty_persons_returns_no_rows(self) -> None:
        self.assertEqual(get_team_upcoming_by_person(self.db, []), [])


if __name__ == "__main__":
    unittest.main()
