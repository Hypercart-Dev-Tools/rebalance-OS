"""sync_calendar must migrate the schema before writing, on any caller's path.

Regression for the calendar-sync crash: the standalone ``calendar-sync`` CLI
reaches ``sync_calendar`` without ``refresh_index``'s up-front ``run_migrations``
step. On a pre-0005 database (baseline ``calendar_events`` with NO ``person``
column) the INSERT used to raise ``OperationalError: no such column: person``.

This seeds a *realistic* pre-0005 database via the baseline schema (unlike
test_calendar_person_attribution, which hand-creates the table already carrying
``person`` + the composite PK and so never exercises the unmigrated path).
"""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from rebalance.ingest.calendar import sync_calendar
from rebalance.ingest.db.schema import ensure_calendar_schema


def _fake_event(event_id: str, summary: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": now.isoformat()},
        "end": {"dateTime": (now + timedelta(hours=1)).isoformat()},
        "status": "confirmed",
        "attendees": [],
    }


def _calendar_columns(db: Path) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(calendar_events)")}
    finally:
        conn.close()


class TestSyncCalendarMigratesPre0005(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "rebalance.db"
        # Seed a pre-0005 database: the baseline calendar_events table only,
        # with NO schema_version ledger — i.e. a DB that predates migrations.
        conn = sqlite3.connect(self.db)
        ensure_calendar_schema(conn)
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_sync(self, calendar_id: str, person: str | None, events: list[dict]) -> None:
        fake_service = MagicMock()
        fake_service.events().list().execute.return_value = {
            "items": events,
            "nextPageToken": None,
        }
        with patch("rebalance.ingest.calendar._build_service", return_value=fake_service):
            sync_calendar(self.db, calendar_id=calendar_id, person=person)

    def test_precondition_baseline_has_no_person_column(self) -> None:
        # Guards the test itself: prove we are exercising the unmigrated path.
        self.assertNotIn(
            "person",
            _calendar_columns(self.db),
            "baseline calendar_events must lack 'person' for this regression to be meaningful",
        )

    def test_operator_sync_on_pre_0005_db_does_not_crash(self) -> None:
        # Before the fix this raised OperationalError: no such column: person.
        self._run_sync("primary", None, [_fake_event("op1", "My Event")])

        self.assertIn(
            "person",
            _calendar_columns(self.db),
            "sync_calendar should have applied migration 0005 (added 'person')",
        )
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT calendar_id, person FROM calendar_events WHERE id = 'op1'"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, "the operator event must have been stored")
        self.assertEqual(row[0], "primary")
        self.assertIsNone(row[1], "operator rows carry person IS NULL")

    def test_teammate_sync_on_pre_0005_db_does_not_crash(self) -> None:
        self._run_sync(
            "matthew@group.calendar.google.com",
            "matthew",
            [_fake_event("tm1", "Team Meeting")],
        )
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT calendar_id, person FROM calendar_events WHERE id = 'tm1'"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "matthew@group.calendar.google.com")
        self.assertEqual(row[1], "matthew")


if __name__ == "__main__":
    unittest.main()
