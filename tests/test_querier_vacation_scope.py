"""querier vacation/OOO detection must use the operator's own ('primary')
calendar only — a teammate's PTO must never flip the operator's day to
'vacation' and suppress work recommendations (P2 privacy / no-contamination)."""

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from rebalance.ingest.querier import _gather_temporal_context

_TABLE = """
    CREATE TABLE IF NOT EXISTS calendar_events (
        id TEXT PRIMARY KEY, summary TEXT, start_time TEXT NOT NULL,
        end_time TEXT, location TEXT, attendees_json TEXT,
        calendar_id TEXT NOT NULL DEFAULT 'primary',
        status TEXT, description TEXT, fetched_at TEXT NOT NULL
    )
"""

DAY = datetime(2026, 6, 15)


def _vacation_row(id_: str, cal: str) -> tuple:
    # Spans the whole target day so the querier's range check matches.
    return (id_, "Vacation - out of office", "2026-06-15T00:00:00",
            "2026-06-15T23:59:59", None, None, cal, "confirmed", None,
            "2026-06-01T00:00:00Z")


def _seed(db: Path, rows: list[tuple]) -> None:
    conn = sqlite3.connect(db)
    conn.execute(_TABLE)
    conn.executemany(
        "INSERT OR REPLACE INTO calendar_events VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


class TestVacationScope(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "rebalance.db"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_teammate_vacation_does_not_mark_operator(self) -> None:
        _seed(self.db, [_vacation_row("v1", "teammate@group.calendar.google.com")])
        ctx = _gather_temporal_context(self.db, DAY)
        self.assertFalse(ctx["is_vacation"])
        self.assertNotEqual(ctx["day_type"], "vacation")

    def test_primary_vacation_marks_operator(self) -> None:
        _seed(self.db, [_vacation_row("v1", "primary")])
        ctx = _gather_temporal_context(self.db, DAY)
        self.assertTrue(ctx["is_vacation"])
        self.assertEqual(ctx["day_type"], "vacation")


if __name__ == "__main__":
    unittest.main()
