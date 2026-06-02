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
    def test_fresh_database_is_stamped_at_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path, ensure_schema) as conn:
                version = run_migrations(conn)
                self.assertGreaterEqual(version, BASELINE_SCHEMA_VERSION)
                self.assertEqual(current_schema_version(conn), version)

    def test_run_migrations_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path, ensure_schema) as conn:
                run_migrations(conn)
                second = run_migrations(conn)
                self.assertGreaterEqual(second, BASELINE_SCHEMA_VERSION)
                self.assertEqual(second, current_schema_version(conn))
                rows = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
                self.assertGreaterEqual(rows, 1)

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
