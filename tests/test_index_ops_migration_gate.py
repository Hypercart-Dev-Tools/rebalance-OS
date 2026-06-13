"""A failed run_migrations must gate the collectors, not just record an error.

Regression: refresh_index recorded a {"scope":"migrations"} error when
run_migrations raised but then still ran every collector against the
unknown/half-migrated schema — producing confusing secondary errors (e.g. a
collector writing a column the migration was meant to add) and wasting API
calls. When migrations fail, collectors must be skipped behind the single
migrations error.
"""

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from rebalance.ingest.index_ops import (
    COLLECTORS,
    Collector,
    refresh_index,
    register_collector,
)


class MigrationGateTests(unittest.TestCase):
    def test_collectors_skipped_when_migrations_fail(self) -> None:
        calls: list[dict[str, Any]] = []

        def _mock_refresh(db: Path, **opts: Any) -> dict[str, Any]:
            calls.append(opts)
            return {"scope": "gate_test", "synced": 1}

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            try:
                register_collector(
                    Collector("gate_test", _mock_refresh, included_in_all=False)
                )
                with patch(
                    "rebalance.ingest.index_ops.run_migrations",
                    side_effect=RuntimeError("disk full during 0005 rebuild"),
                ):
                    result = refresh_index(
                        db_path,
                        scope=["gate_test"],
                        dry_run=False,
                        update_dashboard_note=False,
                    )

                # The collector must NOT have run against the bad schema.
                self.assertEqual(calls, [], "collector ran despite failed migrations")

                # Exactly one clear migrations error is reported.
                migration_errors = [
                    e for e in result["errors"] if e.get("scope") == "migrations"
                ]
                self.assertEqual(len(migration_errors), 1)
                self.assertIn("disk full", migration_errors[0]["error"])

                # The scope is recorded as skipped (informative, not silent), and
                # there is no derivative collector error for it.
                gate_results = [
                    r for r in result["results"] if r.get("scope") == "gate_test"
                ]
                self.assertEqual(len(gate_results), 1)
                self.assertTrue(gate_results[0].get("skipped"))
                self.assertIn("migration", gate_results[0].get("reason", ""))
                self.assertNotIn(
                    "gate_test",
                    [e.get("scope") for e in result["errors"]],
                    "no confusing secondary collector error when migrations failed",
                )
            finally:
                COLLECTORS.pop("gate_test", None)

    def test_collectors_run_when_migrations_succeed(self) -> None:
        # Control: with migrations healthy the collector runs normally (proves the
        # gate only triggers on failure).
        calls: list[dict[str, Any]] = []

        def _mock_refresh(db: Path, **opts: Any) -> dict[str, Any]:
            calls.append(opts)
            return {"scope": "gate_test_ok", "synced": 1}

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            try:
                register_collector(
                    Collector("gate_test_ok", _mock_refresh, included_in_all=False)
                )
                result = refresh_index(
                    db_path,
                    scope=["gate_test_ok"],
                    dry_run=False,
                    update_dashboard_note=False,
                )
                self.assertEqual(len(calls), 1, "collector did not run on a healthy migration")
                scopes = [r.get("scope") for r in result["results"]]
                self.assertIn("gate_test_ok", scopes)
            finally:
                COLLECTORS.pop("gate_test_ok", None)


if __name__ == "__main__":
    unittest.main()
