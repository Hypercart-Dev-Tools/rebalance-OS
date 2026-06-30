"""Migration 0005: calendar_events composite PK (id, calendar_id) + person.

Exercises the realistic upgrade path — an existing v4 database (single-PK
calendar_events, with rows) receiving only the 0005 migration — and asserts the
load-bearing behaviour of a destructive table rebuild: every row is preserved
with its values intact in the right columns (not just the count), a non-primary
(teammate) row survives the copy (the copy is NOT implicitly primary-only), the
new `person` column is NULL on migrated rows, the composite PK lets the same
event id coexist across two calendars, INSERT OR REPLACE no longer
cross-calendar-overwrites, and the step is idempotent.
"""

import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_schema, run_migrations
from rebalance.ingest.db.migrate import discover_migrations
from rebalance.ingest.db.schema import (
    ensure_baseline_schema,
    ensure_schema_version_table,
)

_COLS = ("id", "summary", "start_time", "end_time", "location", "attendees_json",
         "calendar_id", "status", "description", "fetched_at")

# Distinct, checkable rows: 2 primary + 1 teammate. Distinct values let a
# column-mapping regression (a shifted/reordered copy) be caught by value, and
# the teammate row proves the rebuild copies all calendars, not just 'primary'.
_SEED = [
    ("own1", "My standup", "2026-06-01T10:00:00Z", "2026-06-01T10:15:00Z",
     "Zoom", '["a@x"]', "primary", "confirmed", "sprint sync", "2026-06-01T00:00:00Z"),
    ("own2", "My review", "2026-06-02T14:00:00Z", "2026-06-02T15:00:00Z",
     None, None, "primary", "confirmed", None, "2026-06-01T00:00:00Z"),
    ("mate1", "Their block", "2026-06-01T09:00:00Z", "2026-06-01T09:30:00Z",
     "Office", None, "teammate@group.calendar.google.com", "confirmed", None,
     "2026-06-01T00:00:00Z"),
]

_INSERT = (f"INSERT INTO calendar_events ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('?' for _ in _COLS)})")


def _teammate_row(id_: str, cal: str) -> tuple:
    return (id_, "x", "2026-06-03T10:00:00Z", "2026-06-03T11:00:00Z",
            None, None, cal, "confirmed", None, "2026-06-01T00:00:00Z")


class CalendarCompositePkMigrationTests(unittest.TestCase):
    def _v4_db_with_rows(self, conn, rows: list[tuple]) -> None:
        """Bring conn to the pre-0005 (v4) shape with seeded calendar rows.

        A faithful v4 DB actually HAS the objects migrations 0002..0004 create
        (e.g. focus5_repo_signals from 0003) — so we apply those migration files
        for real rather than merely stamping them, otherwise a later additive
        migration that ALTERs one of those tables hits a missing table. The point
        of stopping at v4 is unchanged: run_migrations() then applies 0005 onward,
        and the seeded rows let us assert 0005's rebuild preserves them.
        """
        ensure_baseline_schema(conn)          # single-PK calendar_events
        ensure_schema_version_table(conn)
        conn.execute("INSERT OR IGNORE INTO schema_version (version, applied_at) "
                     "VALUES (1, '2026-06-01T00:00:00Z')")
        for ver, path in discover_migrations():
            if ver > 4:
                break
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute("INSERT OR IGNORE INTO schema_version (version, applied_at) "
                         "VALUES (?, '2026-06-01T00:00:00Z')", (ver,))
        conn.executemany(_INSERT, rows)
        conn.commit()

    def test_data_preserved_with_values_and_teammate_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path, ensure_schema) as conn:
                self._v4_db_with_rows(conn, _SEED)
                # run_migrations returns the latest head version (0005 added the
                # composite PK + person; later migrations advance the head). This
                # test's invariant is 0005's effect, asserted below.
                self.assertGreaterEqual(run_migrations(conn), 5)

                # `person` column present and NULL on every migrated row.
                cols = [r[1] for r in conn.execute("PRAGMA table_info(calendar_events)")]
                self.assertIn("person", cols)
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM calendar_events WHERE person IS NOT NULL"
                ).fetchone()[0], 0)

                # All three rows preserved, incl. the teammate row (copy is NOT
                # implicitly primary-only).
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM calendar_events").fetchone()[0], 3)
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM calendar_events WHERE calendar_id != 'primary'"
                ).fetchone()[0], 1)

                # Full-tuple readback → columns mapped correctly (no shift/drop).
                got = conn.execute(
                    f"SELECT {', '.join(_COLS)} FROM calendar_events "
                    f"WHERE id='own1' AND calendar_id='primary'").fetchone()
                self.assertEqual(tuple(got), _SEED[0])

                # Composite PK lets the same id coexist across two calendars.
                conn.execute(_INSERT, _teammate_row("own1", "teammate@group.calendar.google.com"))
                conn.commit()
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM calendar_events WHERE id='own1'").fetchone()[0], 2)
                self.assertEqual(
                    conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_insert_or_replace_no_longer_cross_calendar_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path, ensure_schema) as conn:
                self._v4_db_with_rows(conn, [])
                run_migrations(conn)
                # The real writer uses INSERT OR REPLACE keyed on the PK; post-0005
                # the composite PK means the two calendars no longer clobber.
                for cal in ("primary", "teammate@group.calendar.google.com"):
                    conn.execute(
                        _INSERT.replace("INSERT INTO", "INSERT OR REPLACE INTO"),
                        _teammate_row("dup", cal))
                conn.commit()
                cals = [r[0] for r in conn.execute(
                    "SELECT calendar_id FROM calendar_events WHERE id='dup' "
                    "ORDER BY calendar_id")]
                self.assertEqual(cals, ["primary", "teammate@group.calendar.google.com"])

    def test_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path, ensure_schema) as conn:
                self._v4_db_with_rows(conn, [_SEED[0]])
                first = run_migrations(conn)
                second = run_migrations(conn)
                self.assertEqual(first, second)
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM calendar_events").fetchone()[0], 1)
                cols = [r[1] for r in conn.execute("PRAGMA table_info(calendar_events)")]
                self.assertIn("person", cols)


if __name__ == "__main__":
    unittest.main()
