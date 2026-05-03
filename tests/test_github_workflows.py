"""Tests for the workflow-runs ingestion module."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rebalance.ingest import github_workflows
from rebalance.ingest.db import db_connection, ensure_github_schema


class WorkflowUpsertTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = Path(self._tmp.name) / "web.db"

    def _runs(self) -> list[dict]:
        return [
            {
                "id": 101,
                "run_attempt": 1,
                "name": "ci",
                "event": "push",
                "head_branch": "claude/foo",
                "head_sha": "abc123",
                "status": "completed",
                "conclusion": "success",
                "actor": {"login": "noelsaw"},
                "triggering_actor": {"login": "noelsaw"},
                "html_url": "https://github.com/o/r/actions/runs/101",
                "created_at": "2026-05-01T12:00:00Z",
                "updated_at": "2026-05-01T12:05:00Z",
                "run_started_at": "2026-05-01T12:00:30Z",
            },
            {
                "id": 101,
                "run_attempt": 2,  # rerun — distinct row
                "name": "ci",
                "event": "push",
                "head_branch": "claude/foo",
                "head_sha": "abc123",
                "status": "completed",
                "conclusion": "failure",
                "actor": {"login": "noelsaw"},
                "html_url": "https://github.com/o/r/actions/runs/101",
                "created_at": "2026-05-01T12:30:00Z",
                "updated_at": "2026-05-01T12:35:00Z",
            },
        ]

    def test_upsert_writes_two_rows_for_distinct_attempts(self) -> None:
        n = github_workflows.upsert_workflow_runs(self.db, "o/r", self._runs())
        self.assertEqual(n, 2)
        with db_connection(self.db, ensure_github_schema) as conn:
            rows = conn.execute(
                "SELECT run_id, run_attempt, conclusion FROM github_workflow_runs ORDER BY run_attempt"
            ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["conclusion"], "success")
        self.assertEqual(rows[1]["conclusion"], "failure")

    def test_upsert_replaces_on_conflict(self) -> None:
        # First write
        github_workflows.upsert_workflow_runs(self.db, "o/r", self._runs()[:1])
        # Same key, different conclusion — should overwrite
        updated = list(self._runs()[:1])
        updated[0]["conclusion"] = "cancelled"
        github_workflows.upsert_workflow_runs(self.db, "o/r", updated)
        with db_connection(self.db, ensure_github_schema) as conn:
            rows = conn.execute(
                "SELECT conclusion FROM github_workflow_runs WHERE run_id = 101 AND run_attempt = 1"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["conclusion"], "cancelled")

    def test_latest_run_for_sha(self) -> None:
        github_workflows.upsert_workflow_runs(self.db, "o/r", self._runs())
        with db_connection(self.db, ensure_github_schema) as conn:
            latest = github_workflows.latest_run_for_sha(conn, "o/r", "abc123")
        assert latest is not None
        self.assertEqual(latest["conclusion"], "failure")

    def test_empty_input_writes_nothing(self) -> None:
        self.assertEqual(github_workflows.upsert_workflow_runs(self.db, "o/r", []), 0)
        # Schema should still be created on first read
        with db_connection(self.db, ensure_github_schema) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM github_workflow_runs"
            ).fetchone()
        self.assertEqual(row["c"], 0)


if __name__ == "__main__":
    unittest.main()
