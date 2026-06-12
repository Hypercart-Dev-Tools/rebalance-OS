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
