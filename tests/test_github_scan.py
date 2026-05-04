"""Tests for GitHub activity scan filtering and persistence."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rebalance.ingest import config as config_module
from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.ingest.github_scan import (
    GitHubScanResult,
    RepoActivity,
    _summarize_by_repo,
    filter_ignored_repo_activity,
    upsert_github_activity,
)


class GitHubScanIgnoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_filter_ignored_repo_activity_removes_ignored_rows_before_persist(self) -> None:
        db_path = Path(self._tmp.name) / "rebalance.db"
        result = GitHubScanResult(
            login="tester",
            scanned_at="2026-04-28T12:00:00+00:00",
            days_fetched=30,
            total_events=9,
            repo_activity={
                "dlt-hub/dlt": RepoActivity(repo_full_name="dlt-hub/dlt", commits=5, pushes=2),
                "example/repo": RepoActivity(repo_full_name="example/repo", commits=3, pushes=1),
            },
        )

        skipped = filter_ignored_repo_activity(result, ["DLT-HUB/dlt"])
        self.assertEqual(skipped, ["dlt-hub/dlt"])
        self.assertEqual(sorted(result.repo_activity), ["example/repo"])

        upsert_github_activity(db_path, result)
        with db_connection(db_path, ensure_github_schema) as conn:
            rows = conn.execute(
                "SELECT repo_full_name, commits FROM github_activity ORDER BY repo_full_name"
            ).fetchall()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["repo_full_name"], "example/repo")
        self.assertEqual(rows[0]["commits"], 3)

    def test_watch_event_does_not_create_activity_repo(self) -> None:
        events = [
            {
                "type": "WatchEvent",
                "repo": {"name": "example/starred"},
                "payload": {"action": "started"},
                "created_at": "2026-05-04T12:00:00Z",
            },
            {
                "type": "PushEvent",
                "repo": {"name": "example/worked"},
                "payload": {"commits": [{"sha": "abc"}]},
                "created_at": "2026-05-04T13:00:00Z",
            },
        ]

        activity = _summarize_by_repo(events)

        self.assertNotIn("example/starred", activity)
        self.assertEqual(activity["example/worked"].commits, 1)

    def test_upsert_skips_zero_work_activity_rows(self) -> None:
        db_path = Path(self._tmp.name) / "rebalance.db"
        result = GitHubScanResult(
            login="tester",
            scanned_at="2026-05-04T12:00:00+00:00",
            days_fetched=30,
            total_events=2,
            repo_activity={
                "example/starred": RepoActivity(
                    repo_full_name="example/starred",
                    last_active_at="2026-05-04T12:00:00Z",
                ),
                "example/worked": RepoActivity(
                    repo_full_name="example/worked",
                    commits=1,
                    pushes=1,
                    last_active_at="2026-05-04T13:00:00Z",
                ),
            },
        )

        upsert_github_activity(db_path, result)
        with db_connection(db_path, ensure_github_schema) as conn:
            rows = conn.execute(
                "SELECT repo_full_name FROM github_activity ORDER BY repo_full_name"
            ).fetchall()

        self.assertEqual([row["repo_full_name"] for row in rows], ["example/worked"])
