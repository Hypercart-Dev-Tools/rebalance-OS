"""sync_calendar must write the person column correctly.

- Operator sync (person=None) → person IS NULL in the DB.
- Teammate sync (person="matthew") → person = "matthew" in the DB.
- Both can coexist with distinct composite PKs (id, calendar_id).
"""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from rebalance.ingest.calendar import sync_calendar


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


def _seed_db(db: Path) -> None:
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE calendar_events (
            id TEXT NOT NULL, summary TEXT, start_time TEXT NOT NULL,
            end_time TEXT, location TEXT, attendees_json TEXT,
            calendar_id TEXT NOT NULL DEFAULT 'primary',
            status TEXT, description TEXT, fetched_at TEXT NOT NULL,
            person TEXT,
            PRIMARY KEY (id, calendar_id)
        )
    """)
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER)")
    conn.commit()
    conn.close()


class TestPersonAttribution(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "rebalance.db"
        _seed_db(self.db)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_sync(self, calendar_id: str, person: str | None, events: list[dict]) -> None:
        fake_service = MagicMock()
        fake_service.events().list().execute.return_value = {
            "items": events,
            "nextPageToken": None,
        }
        # Only mock the Google API service; let calendar_connection use the real
        # seeded temp DB so the person column write can be verified.
        with patch("rebalance.ingest.calendar._build_service", return_value=fake_service):
            sync_calendar(
                self.db,
                calendar_id=calendar_id,
                person=person,
            )

    def test_operator_person_is_null(self) -> None:
        self._run_sync("primary", None, [_fake_event("op1", "My Event")])
        conn = sqlite3.connect(self.db)
        row = conn.execute(
            "SELECT person FROM calendar_events WHERE id = 'op1'"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertIsNone(row[0], "operator rows must have person IS NULL")

    def test_teammate_person_stored(self) -> None:
        self._run_sync(
            "matthew@group.calendar.google.com",
            "matthew",
            [_fake_event("tm1", "Team Meeting")],
        )
        conn = sqlite3.connect(self.db)
        row = conn.execute(
            "SELECT person, calendar_id FROM calendar_events WHERE id = 'tm1'"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "matthew")
        self.assertEqual(row[1], "matthew@group.calendar.google.com")

    def test_operator_and_teammate_coexist(self) -> None:
        self._run_sync("primary", None, [_fake_event("shared-id", "Operator View")])
        self._run_sync(
            "matthew@group.calendar.google.com",
            "matthew",
            [_fake_event("shared-id", "Matthew View")],
        )
        conn = sqlite3.connect(self.db)
        rows = conn.execute(
            "SELECT id, calendar_id, person FROM calendar_events ORDER BY calendar_id"
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), 2, "composite PK (id, calendar_id) should keep both rows")
        persons = {row[1]: row[2] for row in rows}
        self.assertIsNone(persons["primary"])
        self.assertEqual(persons["matthew@group.calendar.google.com"], "matthew")


if __name__ == "__main__":
    unittest.main()
