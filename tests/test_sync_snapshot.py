"""Tests for sync_snapshot.py — hermetic, no network, no real DB."""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rebalance.ingest.sync_snapshot import (
    SCHEMA_VERSION,
    export_calendar_snapshot,
    export_email_snapshot,
    get_device_id,
    read_latest_snapshot,
    _update_latest_pointer,
)


def _seed_calendar(db: Path, events: list[dict]) -> None:
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY, summary TEXT, start_time TEXT NOT NULL,
            end_time TEXT, location TEXT, attendees_json TEXT,
            calendar_id TEXT NOT NULL DEFAULT 'primary',
            status TEXT, description TEXT, fetched_at TEXT NOT NULL
        )
    """)
    for ev in events:
        conn.execute(
            "INSERT OR REPLACE INTO calendar_events VALUES (?,?,?,?,?,?,?,?,?,?)",
            (ev["id"], ev.get("summary"), ev["start_time"], ev.get("end_time"),
             None, None, "primary", "confirmed", None, "2026-06-01T00:00:00Z"),
        )
    conn.commit()
    conn.close()


def _seed_email(db: Path, messages: list[dict]) -> None:
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_messages (
            message_id TEXT PRIMARY KEY, thread_id TEXT, from_address TEXT,
            from_name TEXT, subject TEXT, snippet TEXT, received_at TEXT,
            labels_json TEXT, synced_at TEXT NOT NULL
        )
    """)
    for msg in messages:
        conn.execute(
            "INSERT OR REPLACE INTO email_messages VALUES (?,?,?,?,?,?,?,?,?)",
            (msg["message_id"], msg.get("thread_id"), msg.get("from_address"),
             None, msg.get("subject"), msg.get("snippet"),
             msg.get("received_at"), '["INBOX"]', "2026-06-01T00:00:00Z"),
        )
    conn.commit()
    conn.close()


def _future(days: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

def _past(days: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


class TestGetDeviceId(unittest.TestCase):
    def test_returns_non_empty_string(self) -> None:
        dev = get_device_id()
        self.assertIsInstance(dev, str)
        self.assertTrue(len(dev) > 0)

    def test_slug_is_filesystem_safe(self) -> None:
        dev = get_device_id()
        for ch in dev:
            self.assertTrue(ch.isalnum() or ch == "-", f"unsafe char: {ch!r}")


class TestCalendarSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "rebalance.db"
        self.sync_dir = self.tmp / "sync"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_writes_snapshot_file(self) -> None:
        _seed_calendar(self.db, [
            {"id": "evt1", "summary": "Standup", "start_time": _future(1)},
        ])
        out = export_calendar_snapshot(self.db, self.sync_dir, device_id="test-device")
        self.assertTrue(out.exists())
        self.assertEqual(out, self.sync_dir / "calendar" / "test-device.json")

    def test_snapshot_schema(self) -> None:
        _seed_calendar(self.db, [
            {"id": "evt1", "summary": "Meeting", "start_time": _future(1)},
            {"id": "evt2", "summary": "Old event", "start_time": _past(200)},  # outside window
        ])
        out = export_calendar_snapshot(
            self.db, self.sync_dir, window_days=90, device_id="mac"
        )
        data = json.loads(out.read_text())
        self.assertEqual(data["schema_version"], SCHEMA_VERSION)
        self.assertEqual(data["source"], "calendar")
        self.assertEqual(data["device_id"], "mac")
        self.assertIn("generated_at", data)
        self.assertEqual(data["window_days"], 90)
        # Old event outside 90-day window should be excluded
        self.assertEqual(data["row_count"], 1)
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["rows"][0]["summary"], "Meeting")

    def test_row_contains_all_columns(self) -> None:
        _seed_calendar(self.db, [
            {"id": "evt1", "summary": "Review", "start_time": _future(1)},
        ])
        out = export_calendar_snapshot(self.db, self.sync_dir, device_id="mac")
        row = json.loads(out.read_text())["rows"][0]
        for col in ("id", "summary", "start_time", "end_time", "location",
                    "attendees_json", "calendar_id", "status", "description", "fetched_at"):
            self.assertIn(col, row)

    def test_excludes_non_primary_calendars(self) -> None:
        # Default deny (P2 decision #3): teammate (non-'primary') calendars must
        # never be exported to the pulse repo.
        _seed_calendar(self.db, [
            {"id": "mine", "summary": "My block", "start_time": _future(1)},
        ])
        conn = sqlite3.connect(self.db)
        conn.execute(
            "INSERT OR REPLACE INTO calendar_events VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("teammate-evt", "Teammate block", _future(1), None, None, None,
             "teammate@group.calendar.google.com", "confirmed", None,
             "2026-06-01T00:00:00Z"),
        )
        conn.commit()
        conn.close()
        out = export_calendar_snapshot(self.db, self.sync_dir, device_id="mac")
        data = json.loads(out.read_text())
        self.assertEqual(data["row_count"], 1)
        self.assertEqual({r["calendar_id"] for r in data["rows"]}, {"primary"})
        summaries = [r["summary"] for r in data["rows"]]
        self.assertIn("My block", summaries)
        self.assertNotIn("Teammate block", summaries)

    def test_person_label_never_exported(self) -> None:
        # Hard invariant (P2 decision #3): the `person` teammate-identity label
        # (migration 0005) must NEVER leave the machine. It is enforced today by
        # _CALENDAR_COLUMNS omitting `person`; this locks it so a future edit that
        # re-adds `person` to the export columns fails loudly here. Uses the
        # post-0005 schema (person + composite PK) directly.
        conn = sqlite3.connect(self.db)
        conn.execute("""
            CREATE TABLE calendar_events (
                id TEXT, summary TEXT, start_time TEXT NOT NULL,
                end_time TEXT, location TEXT, attendees_json TEXT,
                calendar_id TEXT NOT NULL DEFAULT 'primary',
                status TEXT, description TEXT, fetched_at TEXT NOT NULL,
                person TEXT, PRIMARY KEY (id, calendar_id)
            )
        """)
        # Adversarial: a 'primary' row that still carries a person label, plus a
        # teammate row. Neither the teammate row nor either label may survive.
        conn.executemany(
            "INSERT INTO calendar_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [("mine", "My block", _future(1), None, None, None,
              "primary", "confirmed", None, "2026-06-01T00:00:00Z", "OPERATOR_LABEL"),
             ("mate", "Teammate block", _future(1), None, None, None,
              "teammate@group.calendar.google.com", "confirmed", None,
              "2026-06-01T00:00:00Z", "matthew")],
        )
        conn.commit()
        conn.close()

        out = export_calendar_snapshot(self.db, self.sync_dir, device_id="mac")
        raw = out.read_text()
        data = json.loads(raw)

        # Only the operator's own row is exported, and `person` is never a key.
        self.assertEqual({r["calendar_id"] for r in data["rows"]}, {"primary"})
        self.assertNotIn("Teammate block", [r["summary"] for r in data["rows"]])
        for row in data["rows"]:
            self.assertNotIn("person", row)
        # Defense in depth: no person label survives anywhere in the serialized
        # payload (catches person leaking via any field, not just a `person` key).
        self.assertNotIn("OPERATOR_LABEL", raw)
        self.assertNotIn("matthew", raw)

    def test_empty_db_writes_zero_rows(self) -> None:
        _seed_calendar(self.db, [])
        out = export_calendar_snapshot(self.db, self.sync_dir, device_id="mac")
        data = json.loads(out.read_text())
        self.assertEqual(data["row_count"], 0)
        self.assertEqual(data["rows"], [])

    def test_missing_db_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            export_calendar_snapshot(self.tmp / "missing.db", self.sync_dir)

    def test_writes_latest_pointer(self) -> None:
        _seed_calendar(self.db, [
            {"id": "e1", "summary": "X", "start_time": _future(1)},
        ])
        export_calendar_snapshot(self.db, self.sync_dir, device_id="mac")
        latest = json.loads((self.sync_dir / "calendar" / "latest.json").read_text())
        self.assertEqual(latest["device_id"], "mac")
        self.assertEqual(latest["snapshot_file"], "mac.json")


class TestEmailSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "rebalance.db"
        self.sync_dir = self.tmp / "sync"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_writes_snapshot_file(self) -> None:
        _seed_email(self.db, [
            {"message_id": "m1", "subject": "Hello", "received_at": _past(1)},
        ])
        out = export_email_snapshot(self.db, self.sync_dir, device_id="mac")
        self.assertTrue(out.exists())
        self.assertEqual(out, self.sync_dir / "email" / "mac.json")

    def test_snapshot_schema(self) -> None:
        _seed_email(self.db, [
            {"message_id": f"m{i}", "subject": f"msg {i}", "received_at": _past(i)}
            for i in range(5)
        ])
        out = export_email_snapshot(self.db, self.sync_dir, limit=3, device_id="mac")
        data = json.loads(out.read_text())
        self.assertEqual(data["schema_version"], SCHEMA_VERSION)
        self.assertEqual(data["source"], "email")
        self.assertEqual(data["limit"], 3)
        # Respects limit
        self.assertEqual(data["row_count"], 3)
        self.assertEqual(len(data["rows"]), 3)

    def test_row_contains_all_columns(self) -> None:
        _seed_email(self.db, [
            {"message_id": "m1", "subject": "Hi", "received_at": _past(1)},
        ])
        out = export_email_snapshot(self.db, self.sync_dir, device_id="mac")
        row = json.loads(out.read_text())["rows"][0]
        for col in ("message_id", "thread_id", "from_address", "from_name",
                    "subject", "snippet", "received_at", "labels_json", "synced_at"):
            self.assertIn(col, row)

    def test_missing_db_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            export_email_snapshot(self.tmp / "missing.db", self.sync_dir)


class TestLatestPointer(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.source_dir = Path(self._tmp.name) / "calendar"
        self.source_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_first_device_always_written(self) -> None:
        _update_latest_pointer(self.source_dir, "mac", "2026-06-01T10:00:00Z")
        data = json.loads((self.source_dir / "latest.json").read_text())
        self.assertEqual(data["device_id"], "mac")

    def test_newer_device_replaces_pointer(self) -> None:
        _update_latest_pointer(self.source_dir, "mac", "2026-06-01T09:00:00Z")
        _update_latest_pointer(self.source_dir, "studio", "2026-06-01T10:00:00Z")
        data = json.loads((self.source_dir / "latest.json").read_text())
        self.assertEqual(data["device_id"], "studio")

    def test_older_device_does_not_replace_pointer(self) -> None:
        _update_latest_pointer(self.source_dir, "studio", "2026-06-01T10:00:00Z")
        _update_latest_pointer(self.source_dir, "mac", "2026-06-01T09:00:00Z")
        data = json.loads((self.source_dir / "latest.json").read_text())
        self.assertEqual(data["device_id"], "studio")

    def test_corrupt_latest_json_is_overwritten(self) -> None:
        (self.source_dir / "latest.json").write_text("not json", encoding="utf-8")
        _update_latest_pointer(self.source_dir, "mac", "2026-06-01T10:00:00Z")
        data = json.loads((self.source_dir / "latest.json").read_text())
        self.assertEqual(data["device_id"], "mac")


class TestReadLatestSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.sync_dir = Path(self._tmp.name) / "sync"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_none_when_no_snapshots(self) -> None:
        self.assertIsNone(read_latest_snapshot(self.sync_dir, "calendar"))

    def test_returns_snapshot_after_export(self) -> None:
        db = Path(self._tmp.name) / "db.sqlite"
        _seed_calendar(db, [
            {"id": "e1", "summary": "Meeting", "start_time": _future(1)},
        ])
        export_calendar_snapshot(db, self.sync_dir, device_id="mac")
        result = read_latest_snapshot(self.sync_dir, "calendar")
        self.assertIsNotNone(result)
        self.assertEqual(result["device_id"], "mac")
        self.assertEqual(len(result["rows"]), 1)


if __name__ == "__main__":
    unittest.main()
