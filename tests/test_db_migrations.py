"""Tests for the forward-only schema migration runner (db/migrate.py)."""

import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import (
    BASELINE_SCHEMA_VERSION,
    current_schema_version,
    db_connection,
    ensure_schema,
    run_migrations,
)
from rebalance.ingest.db import migrate


class MigrationRunnerTests(unittest.TestCase):
    def test_fresh_database_is_stamped_then_migrated_to_latest(self) -> None:
        # A fresh DB is stamped at the baseline, then brought up to the latest
        # available migration. The expected final version is the highest
        # NNNN_*.sql prefix (or the baseline if no migrations exist yet), so this
        # stays correct as migrations accrue without hardcoding a number.
        expected = max(
            [v for v, _ in migrate.discover_migrations()] + [BASELINE_SCHEMA_VERSION]
        )
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path, ensure_schema) as conn:
                version = run_migrations(conn)
                self.assertEqual(version, expected)
                self.assertEqual(current_schema_version(conn), expected)
                # The baseline is always recorded, regardless of later migrations.
                recorded = {
                    int(r[0]) for r in conn.execute("SELECT version FROM schema_version")
                }
                self.assertIn(BASELINE_SCHEMA_VERSION, recorded)

    def test_run_migrations_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path, ensure_schema) as conn:
                first = run_migrations(conn)
                rows_first = conn.execute(
                    "SELECT COUNT(*) FROM schema_version"
                ).fetchone()[0]
                second = run_migrations(conn)
                rows_second = conn.execute(
                    "SELECT COUNT(*) FROM schema_version"
                ).fetchone()[0]
                # Re-running changes nothing: same version, no new rows.
                self.assertEqual(second, first)
                self.assertEqual(rows_second, rows_first)
                # One row per applied version: baseline + each migration.
                self.assertEqual(rows_first, 1 + len(migrate.discover_migrations()))

    def test_pending_migration_is_applied_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mig_dir = Path(tmp) / "migrations"
            mig_dir.mkdir()
            (mig_dir / "0002_add_probe.sql").write_text(
                "CREATE TABLE migration_probe (id INTEGER PRIMARY KEY);",
                encoding="utf-8",
            )
            db_path = Path(tmp) / "rebalance.db"
            original_dir = migrate.MIGRATIONS_DIR
            migrate.MIGRATIONS_DIR = mig_dir
            try:
                with db_connection(db_path, ensure_schema) as conn:
                    version = run_migrations(conn)
                    self.assertEqual(version, 2)
                    # The migration's table exists.
                    conn.execute("SELECT COUNT(*) FROM migration_probe")
                    # Re-running applies nothing further.
                    self.assertEqual(run_migrations(conn), 2)
                    recorded = {
                        int(r[0])
                        for r in conn.execute("SELECT version FROM schema_version")
                    }
                    self.assertEqual(recorded, {BASELINE_SCHEMA_VERSION, 2})
            finally:
                migrate.MIGRATIONS_DIR = original_dir

    def test_failed_bare_migration_rolls_back_atomically(self) -> None:
        # A BARE multi-statement migration (no BEGIN/COMMIT — the form the README
        # endorses) that fails mid-script must still be atomic: the runner wraps
        # it in a transaction and rolls back, so the ORIGINAL table and data
        # survive and the version does not advance. Before the runner owned the
        # transaction, executescript auto-committed each statement and the early
        # statements (the dropped/renamed table) were lost — this is the gap.
        with tempfile.TemporaryDirectory() as tmp:
            mig_dir = Path(tmp) / "migrations"
            mig_dir.mkdir()
            (mig_dir / "0002_bad_rebuild.sql").write_text(
                "CREATE TABLE keepme_new (id TEXT NOT NULL, v TEXT, PRIMARY KEY(id));\n"
                "INSERT INTO keepme_new (id, v) SELECT id, v FROM keepme;\n"
                "DROP TABLE keepme;\n"
                "ALTER TABLE keepme_new RENAME TO keepme;\n"
                "INSERT INTO keepme (nonexistent_col) VALUES ('x');\n",  # fails here
                encoding="utf-8",
            )
            db_path = Path(tmp) / "rebalance.db"
            original_dir = migrate.MIGRATIONS_DIR
            migrate.MIGRATIONS_DIR = mig_dir
            try:
                with db_connection(db_path, ensure_schema) as conn:
                    conn.execute("CREATE TABLE keepme (id TEXT PRIMARY KEY, v TEXT)")
                    conn.executemany(
                        "INSERT INTO keepme VALUES (?, ?)", [("a", "1"), ("b", "2")])
                    conn.commit()
                    with self.assertRaises(Exception):
                        run_migrations(conn)
                    # Original table + data fully intact after the rollback — the
                    # DROP/RENAME earlier in the script must NOT have stuck.
                    rows = conn.execute(
                        "SELECT id, v FROM keepme ORDER BY id").fetchall()
                    self.assertEqual([tuple(r) for r in rows], [("a", "1"), ("b", "2")])
                    # The scratch table must not survive either.
                    leftover = conn.execute(
                        "SELECT name FROM sqlite_master WHERE name = 'keepme_new'"
                    ).fetchall()
                    self.assertEqual(leftover, [])
                    # Version did not advance past the baseline.
                    self.assertEqual(
                        current_schema_version(conn), BASELINE_SCHEMA_VERSION)
            finally:
                migrate.MIGRATIONS_DIR = original_dir

    def test_bare_multi_statement_migration_applies_atomically(self) -> None:
        # The happy path for the README-endorsed bare form: a successful
        # multi-statement migration applies fully and advances the version.
        with tempfile.TemporaryDirectory() as tmp:
            mig_dir = Path(tmp) / "migrations"
            mig_dir.mkdir()
            (mig_dir / "0002_two_tables.sql").write_text(
                "CREATE TABLE alpha (id INTEGER PRIMARY KEY);\n"
                "CREATE TABLE beta (id INTEGER PRIMARY KEY);\n",
                encoding="utf-8",
            )
            db_path = Path(tmp) / "rebalance.db"
            original_dir = migrate.MIGRATIONS_DIR
            migrate.MIGRATIONS_DIR = mig_dir
            try:
                with db_connection(db_path, ensure_schema) as conn:
                    self.assertEqual(run_migrations(conn), 2)
                    conn.execute("SELECT COUNT(*) FROM alpha")
                    conn.execute("SELECT COUNT(*) FROM beta")
            finally:
                migrate.MIGRATIONS_DIR = original_dir

    def test_self_wrapped_migration_is_rejected_and_rolls_back(self) -> None:
        # A migration that opens its own BEGIN now hits a nested-transaction error
        # under the runner's wrapper and is rolled back rather than applied — the
        # README forbids self-wrapping, and the failure must be safe (no partial
        # apply, version unchanged).
        with tempfile.TemporaryDirectory() as tmp:
            mig_dir = Path(tmp) / "migrations"
            mig_dir.mkdir()
            (mig_dir / "0002_self_wrapped.sql").write_text(
                "BEGIN;\n"
                "CREATE TABLE should_not_exist (id INTEGER PRIMARY KEY);\n"
                "COMMIT;\n",
                encoding="utf-8",
            )
            db_path = Path(tmp) / "rebalance.db"
            original_dir = migrate.MIGRATIONS_DIR
            migrate.MIGRATIONS_DIR = mig_dir
            try:
                with db_connection(db_path, ensure_schema) as conn:
                    with self.assertRaises(Exception):
                        run_migrations(conn)
                    leftover = conn.execute(
                        "SELECT name FROM sqlite_master WHERE name = 'should_not_exist'"
                    ).fetchall()
                    self.assertEqual(leftover, [])
                    self.assertEqual(
                        current_schema_version(conn), BASELINE_SCHEMA_VERSION)
            finally:
                migrate.MIGRATIONS_DIR = original_dir

    def test_discover_migrations_ignores_non_numeric_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mig_dir = Path(tmp) / "migrations"
            mig_dir.mkdir()
            (mig_dir / "0002_real.sql").write_text("SELECT 1;", encoding="utf-8")
            (mig_dir / "notes.sql").write_text("SELECT 1;", encoding="utf-8")
            (mig_dir / "README.md").write_text("ignored", encoding="utf-8")
            original_dir = migrate.MIGRATIONS_DIR
            migrate.MIGRATIONS_DIR = mig_dir
            try:
                discovered = migrate.discover_migrations()
                self.assertEqual([v for v, _ in discovered], [2])
            finally:
                migrate.MIGRATIONS_DIR = original_dir


if __name__ == "__main__":
    unittest.main()
