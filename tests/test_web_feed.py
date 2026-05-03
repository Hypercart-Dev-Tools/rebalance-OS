"""Tests for the web dashboard's feed builder + device-pulse reader."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.web import feed, sources


def _seed(db: Path) -> None:
    with db_connection(db, ensure_github_schema) as conn:
        conn.execute(
            """
            INSERT INTO github_commits
                (repo_full_name, item_type, item_number, sha, author_login,
                 message, committed_at, html_url, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "o/r",
                "pull_request",
                1,
                "abc123",
                "noelsaw",
                "Refactor handler",
                "2026-05-02T10:00:00+00:00",
                "https://github.com/o/r/commit/abc123",
                "2026-05-02T10:01:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO github_workflow_runs
                (repo_full_name, run_id, run_attempt, workflow_name, event,
                 head_branch, head_sha, status, conclusion, actor_login,
                 triggering_actor_login, run_url, created_at, updated_at,
                 run_started_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "o/r", 999, 1, "ci", "push", "claude/abc", "abc123",
                "completed", "success", "noelsaw", "noelsaw",
                "https://github.com/o/r/actions/runs/999",
                "2026-05-02T10:02:00+00:00",
                "2026-05-02T10:05:00+00:00",
                "2026-05-02T10:02:30+00:00",
                "2026-05-02T10:06:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO github_items
                (repo_full_name, item_type, number, title, state, is_merged,
                 author_login, head_ref, head_sha, html_url, created_at,
                 updated_at, merged_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "o/r", "pull_request", 7, "Add dashboard", "closed", 1,
                "noelsaw", "claude/dashboard", "abc123",
                "https://github.com/o/r/pull/7",
                "2026-05-01T08:00:00+00:00",
                "2026-05-02T09:00:00+00:00",
                "2026-05-02T09:00:00+00:00",
                "2026-05-02T09:01:00+00:00",
            ),
        )
        conn.commit()


class FeedBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = Path(self._tmp.name) / "web.db"
        _seed(self.db)

    def test_feed_joins_commit_with_workflow_run(self) -> None:
        rows = feed.build_feed(self.db, None, since="7d")
        commit_rows = [r for r in rows if r["kind"] == "commit"]
        self.assertEqual(len(commit_rows), 1)
        commit = commit_rows[0]
        self.assertEqual(commit["repo"], "o/r")
        self.assertIsNotNone(commit["ci"])
        self.assertEqual(commit["ci"]["conclusion"], "success")
        self.assertEqual(commit["ci"]["color"], "green")

    def test_pr_merged_gets_classified_via_branch(self) -> None:
        rows = feed.build_feed(self.db, None, since="7d")
        pr_rows = [r for r in rows if r["kind"] == "pr_merged"]
        self.assertEqual(len(pr_rows), 1)
        self.assertEqual(pr_rows[0]["source_tag"], "claude-cloud")

    def test_workflow_row_color(self) -> None:
        rows = feed.build_feed(self.db, None, since="7d")
        wf = [r for r in rows if r["kind"] == "workflow_run"]
        self.assertEqual(len(wf), 1)
        self.assertEqual(wf[0]["ci"]["color"], "green")
        self.assertEqual(wf[0]["source_tag"], "claude-cloud")

    def test_since_filters_old_rows(self) -> None:
        rows = feed.build_feed(self.db, None, since="1h")
        self.assertEqual(rows, [])


class DevicePulseReaderTests(unittest.TestCase):
    def test_reads_tab_separated_lines(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mirror = Path(td)
            now = datetime.now(timezone.utc)
            recent = now - timedelta(minutes=5)
            old = now - timedelta(days=10)
            (mirror / "pulse-mac-studio.md").write_text(
                "# header line\n"
                f"{int(recent.timestamp())}\t{recent.isoformat()}\to/r\tmain\tabc\tFix things\n"
                f"{int(old.timestamp())}\t{old.isoformat()}\to/r\tmain\tdef\tStale\n",
                encoding="utf-8",
            )
            results = sources.read_device_pulses(mirror, now - timedelta(hours=1))
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].device, "mac-studio")
            self.assertEqual(results[0].subject, "Fix things")

    def test_missing_dir_returns_empty(self) -> None:
        self.assertEqual(
            sources.read_device_pulses(Path("/nonexistent-nope"),
                                       datetime.now(timezone.utc)),
            [],
        )


if __name__ == "__main__":
    unittest.main()
