"""Tests for GH-124 commit-threshold auto-promotion of watched repos."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rebalance.ingest import config as config_module
from rebalance.ingest.config import set_github_ignored_repos, set_pulse_config
from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_project_schema
from rebalance.ingest.project_inference import (
    COMMIT_THRESHOLD_GENERATED_BY,
    sync_commit_threshold_promotions,
)
from rebalance.ingest.registry import sync_db


def _insert_commit(
    db: Path, *, repo: str, sha: str, author_login: str, committed_at: str = "2026-07-01T00:00:00Z"
) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO github_commits
            (repo_full_name, item_type, item_number, sha, author_login, message,
             committed_at, html_url, fetched_at)
        VALUES (?, 'commit', 0, ?, ?, 'msg', ?, ?, ?)
        """,
        (repo, sha, author_login, committed_at, f"https://github.example/{repo}/commit/{sha}", committed_at),
    )
    conn.commit()
    conn.close()


def _insert_activity(db: Path, *, repo: str, login: str = "tester") -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO github_activity
            (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
             issues_opened, issue_comments, reviews, last_active_at, scanned_at)
        VALUES (?, ?, '2026-07-01', 3, 3, 0, 0, 0, 0, 0, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')
        """,
        (login, repo),
    )
    conn.commit()
    conn.close()


class AutoPromoteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"
        self.db_path = Path(self._tmp.name) / "rebalance.db"
        with db_connection(self.db_path) as conn:
            ensure_github_schema(conn)
            ensure_project_schema(conn)
        set_pulse_config(github_login="tester")

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_promotes_repo_at_threshold(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo)
        for i in range(3):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertTrue(summary.enabled)
        self.assertEqual(summary.promoted_count, 1)
        self.assertEqual(summary.promoted[0]["repos"], [repo])
        marker = summary.promoted[0]["custom_fields"]["inference"]["generated_by"]
        self.assertEqual(marker, COMMIT_THRESHOLD_GENERATED_BY)

    def test_below_threshold_does_not_promote(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo)
        for i in range(2):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 0)

    def test_fork_with_zero_operator_commits_never_promotes(self) -> None:
        repo = "Acme/forked-widget"
        _insert_activity(self.db_path, repo=repo)
        for i in range(5):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="someone-else")

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 0)

    def test_cloud_agent_commits_count_toward_threshold(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo)
        _insert_commit(self.db_path, repo=repo, sha="sha0", author_login="tester")
        _insert_commit(self.db_path, repo=repo, sha="sha1", author_login="claude[bot]")
        _insert_commit(self.db_path, repo=repo, sha="sha2", author_login="claude[bot]")

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 1)

    def test_ignored_repo_never_promotes(self) -> None:
        repo = "Acme/widget"
        set_github_ignored_repos([repo])
        _insert_activity(self.db_path, repo=repo)
        for i in range(3):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 0)

    def test_curated_row_never_touched(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo)
        for i in range(3):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
        sync_db(
            self.db_path,
            {
                "projects": [
                    {
                        "name": "widget",
                        "status": "active",
                        "summary": "hand-curated",
                        "repos": [],
                        "tags": [],
                        "custom_fields": {},
                    }
                ]
            },
        )

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 0)
        self.assertIn("widget", summary.skipped_curated_names)
        with db_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT summary FROM project_registry WHERE name = 'widget'"
            ).fetchone()
        self.assertEqual(row["summary"], "hand-curated")

    def test_idempotent_rerun_does_not_duplicate(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo)
        for i in range(3):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")

        sync_commit_threshold_promotions(self.db_path)
        sync_commit_threshold_promotions(self.db_path)

        with db_connection(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM project_registry WHERE name = 'widget'"
            ).fetchone()["n"]
        self.assertEqual(count, 1)

    def test_disabled_is_a_no_op(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo)
        for i in range(3):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
        config_module._write_config(
            {**config_module._read_config(), "auto_promote_enabled": False}
        )

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertFalse(summary.enabled)
        self.assertEqual(summary.promoted_count, 0)

    def test_promotion_fires_auth_log_alert(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo)
        for i in range(3):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")

        with mock.patch(
            "rebalance.ingest.auth_log.log_project_auto_promoted"
        ) as mocked:
            sync_commit_threshold_promotions(self.db_path)

        mocked.assert_called_once_with(
            repo, project_name="widget", commit_count=3, threshold=3
        )

    def test_no_promotion_does_not_fire_auth_log_alert(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo)
        for i in range(2):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")

        with mock.patch(
            "rebalance.ingest.auth_log.log_project_auto_promoted"
        ) as mocked:
            sync_commit_threshold_promotions(self.db_path)

        mocked.assert_not_called()

    def test_no_github_login_configured_is_a_no_op(self) -> None:
        # set_pulse_config(github_login=None) is a no-op (None means "leave
        # unchanged"), so clear it directly at the raw-config layer instead.
        config_module._write_config(
            {**config_module._read_config(), "github_login": None}
        )
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo)
        for i in range(3):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 0)


if __name__ == "__main__":
    unittest.main()
