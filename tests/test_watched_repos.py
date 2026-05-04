"""Tests for canonical GitHub watched-repo selection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rebalance.ingest import config as config_module
from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_project_schema
from rebalance.ingest.index_ops import get_watched_repos


class WatchedReposTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_config_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_config_path

    def test_zero_work_activity_does_not_auto_watch_repo(self) -> None:
        db_path = Path(self._tmp.name) / "rebalance.db"
        with db_connection(db_path) as conn:
            ensure_github_schema(conn)
            conn.execute(
                """
                INSERT INTO github_activity
                    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
                     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
                VALUES (?, ?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "tester",
                    "example/starred",
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    "2026-05-04T12:00:00Z",
                    "2026-05-04T12:05:00Z",
                ),
            )
            conn.execute(
                """
                INSERT INTO github_activity
                    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
                     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
                VALUES (?, ?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "tester",
                    "example/worked",
                    1,
                    1,
                    0,
                    0,
                    0,
                    0,
                    0,
                    "2026-05-04T13:00:00Z",
                    "2026-05-04T13:05:00Z",
                ),
            )
            conn.commit()

        watched = get_watched_repos(db_path)

        self.assertNotIn("example/starred", watched["watched"])
        self.assertNotIn("example/starred", watched["activity_repos"])
        self.assertEqual(watched["watched"], ["example/worked"])

    def test_active_project_repo_is_watched_even_without_recent_activity(self) -> None:
        db_path = Path(self._tmp.name) / "rebalance.db"
        with db_connection(db_path) as conn:
            ensure_project_schema(conn)
            conn.execute(
                """
                INSERT INTO project_registry
                    (name, status, summary, value_level, priority_tier, risk_level,
                     repos_json, tags_json, custom_fields_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Owned Repo",
                    "active",
                    "",
                    None,
                    None,
                    None,
                    '["example/owned"]',
                    "[]",
                    "{}",
                ),
            )
            conn.commit()

        watched = get_watched_repos(db_path)

        self.assertEqual(watched["watched"], ["example/owned"])


if __name__ == "__main__":
    unittest.main()
