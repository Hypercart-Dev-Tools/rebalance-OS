"""Tests for the Apple Reminders read-only extractor.

These exercise the extractor against a synthetic REMCD-shaped SQLite store, so
they run on any platform without Full Disk Access or a real Reminders database.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rebalance.ingest.apple_reminders import (
    CORE_DATA_EPOCH_OFFSET,
    AppleRemindersSchemaError,
    core_data_timestamp,
    extract_reminders,
    parse_hashtags,
    pick_active_store,
)

# 2026-06-22 12:00:00 UTC expressed in Core Data (seconds since 2001-01-01).
_CD_2026 = datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc).timestamp() - CORE_DATA_EPOCH_OFFSET


def _make_store(path: Path, *, with_optional: bool = True) -> None:
    """Build a minimal REMCD-shaped store. When ``with_optional`` is False, the
    reminder table omits every optional column (notes/dates/parent/etc.) to
    prove the mapper degrades gracefully."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE ZREMCDBASELIST (Z_PK INTEGER PRIMARY KEY, ZNAME TEXT)")
    conn.execute("INSERT INTO ZREMCDBASELIST (Z_PK, ZNAME) VALUES (1, 'Groceries')")

    if with_optional:
        conn.execute(
            """
            CREATE TABLE ZREMCDREMINDER (
                Z_PK INTEGER PRIMARY KEY,
                ZTITLE TEXT,
                ZCKIDENTIFIER TEXT,
                ZNOTES TEXT,
                ZNOTESDOCUMENT BLOB,
                ZCOMPLETED INTEGER,
                ZDUEDATE TIMESTAMP,
                ZCOMPLETIONDATE TIMESTAMP,
                ZCREATIONDATE TIMESTAMP,
                ZLASTMODIFIEDDATE TIMESTAMP,
                ZLIST INTEGER,
                ZPARENTREMINDER INTEGER,
                ZCKPARENTREMINDERIDENTIFIER TEXT,
                ZICSDISPLAYORDER INTEGER,
                ZMARKEDFORDELETION INTEGER
            )
            """
        )
        rows = [
            # parent task, due-dated, tagged in title
            (1, "Buy milk #grocery", "CK-1", "skim only", None, 0, _CD_2026, None,
             _CD_2026, _CD_2026, 1, None, None, 10, 0),
            # subtask -> parent via local Z_PK
            (2, "2% backup", "CK-2", None, None, 0, None, None,
             _CD_2026, _CD_2026, 1, 1, None, 20, 0),
            # completed
            (3, "Eggs", "CK-3", None, None, 1, None, _CD_2026,
             _CD_2026, _CD_2026, 1, None, None, 30, 0),
            # marked for deletion -> must be skipped
            (4, "ghost", "CK-4", None, None, 0, None, None,
             _CD_2026, _CD_2026, 1, None, None, 40, 1),
            # missing stable id -> must be skipped
            (5, "no-ckid", None, None, None, 0, None, None,
             _CD_2026, _CD_2026, 1, None, None, 50, 0),
        ]
        conn.executemany(
            "INSERT INTO ZREMCDREMINDER VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
        )
    else:
        conn.execute(
            "CREATE TABLE ZREMCDREMINDER (Z_PK INTEGER PRIMARY KEY, "
            "ZTITLE TEXT, ZCKIDENTIFIER TEXT)"
        )
        conn.executemany(
            "INSERT INTO ZREMCDREMINDER (Z_PK, ZTITLE, ZCKIDENTIFIER) VALUES (?,?,?)",
            [(1, "Minimal", "CK-1"), (2, "Another", "CK-2")],
        )
    conn.commit()
    conn.close()


class CoreDataTimestampTests(unittest.TestCase):
    def test_converts_2001_relative_seconds_to_utc(self):
        dt = core_data_timestamp(_CD_2026)
        self.assertEqual(dt, datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc))

    def test_zero_is_the_reference_date(self):
        self.assertEqual(
            core_data_timestamp(0),
            datetime(2001, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )

    def test_none_and_garbage_return_none(self):
        self.assertIsNone(core_data_timestamp(None))
        self.assertIsNone(core_data_timestamp("not-a-number"))


class HashtagTests(unittest.TestCase):
    def test_extracts_unique_ordered_tags(self):
        self.assertEqual(
            parse_hashtags("call #work then #home", "again #work"),
            ("work", "home"),
        )

    def test_no_tags(self):
        self.assertEqual(parse_hashtags("plain title", None), ())


class ExtractRemindersTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_full_extraction_with_linking_and_skips(self):
        db = self.dir / "store.sqlite"
        _make_store(db, with_optional=True)
        reminders, skipped, fallbacks = extract_reminders(db)

        by_id = {r.reminder_id: r for r in reminders}
        # ghost (marked-for-deletion) + no-ckid row are both skipped.
        self.assertEqual(skipped, 2)
        self.assertEqual(set(by_id), {"CK-1", "CK-2", "CK-3"})

        # parent-child linking resolves the local Z_PK to the parent's stable id.
        self.assertEqual(by_id["CK-2"].parent_reminder_id, "CK-1")
        self.assertIsNone(by_id["CK-1"].parent_reminder_id)

        # list join, completion, due date, tags.
        self.assertEqual(by_id["CK-1"].list_name, "Groceries")
        self.assertEqual(by_id["CK-1"].tags, ("grocery",))
        self.assertEqual(by_id["CK-1"].notes, "skim only")
        self.assertTrue(by_id["CK-3"].is_completed)
        self.assertEqual(
            by_id["CK-1"].due_at,
            datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(fallbacks, [])

    def test_graceful_degradation_when_optional_columns_absent(self):
        db = self.dir / "minimal.sqlite"
        _make_store(db, with_optional=False)
        reminders, skipped, fallbacks = extract_reminders(db)

        self.assertEqual(len(reminders), 2)
        self.assertEqual(skipped, 0)
        # Optional fields default cleanly rather than raising.
        r = reminders[0]
        self.assertIsNone(r.due_at)
        self.assertIsNone(r.notes)
        self.assertFalse(r.is_completed)
        # The missing optional columns are reported as fallbacks, not hidden.
        self.assertTrue(any("missing_optional_column:ZNOTES" in f for f in fallbacks))

    def test_missing_required_column_raises(self):
        db = self.dir / "broken.sqlite"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE ZREMCDREMINDER (Z_PK INTEGER, ZTITLE TEXT)")
        conn.commit()
        conn.close()
        with self.assertRaises(AppleRemindersSchemaError):
            extract_reminders(db)

    def test_pick_active_store_chooses_store_with_most_reminders(self):
        empty = self.dir / "empty.sqlite"
        _make_store(empty, with_optional=False)
        # wipe its rows so it has zero reminders
        conn = sqlite3.connect(empty)
        conn.execute("DELETE FROM ZREMCDREMINDER")
        conn.commit()
        conn.close()

        active = self.dir / "active.sqlite"
        _make_store(active, with_optional=True)

        self.assertEqual(pick_active_store([empty, active]), active)


if __name__ == "__main__":
    unittest.main()
