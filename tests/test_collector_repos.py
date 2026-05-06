"""Tests for the collector-repo concept: hidden from `github_balance`, surfaced as
a heartbeat in `index_status`.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rebalance.ingest import config as config_module
from rebalance.ingest.config import (
    add_github_collector_repo,
    get_github_collector_repos,
    is_github_repo_collector,
    remove_github_collector_repo,
    set_github_collector_repos,
)
from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.ingest.github_scan import get_github_balance
from rebalance.ingest.index_ops import get_index_status


def _seed_activity(db_path: Path, repo: str, last_active_at: str) -> None:
    with db_connection(db_path) as conn:
        ensure_github_schema(conn)
        conn.execute(
            "INSERT INTO github_activity (login, repo_full_name, scan_date, commits, "
            "pushes, prs_opened, prs_merged, issues_opened, issue_comments, reviews, "
            "last_active_at, scanned_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "tester",
                repo,
                "2026-05-05",
                1,
                1,
                0,
                0,
                0,
                0,
                0,
                last_active_at,
                "2026-05-05T00:00:00Z",
            ),
        )
        conn.commit()


class _RedirectedConfigPathTestCase(unittest.TestCase):
    """Base class that redirects rbos.config to a scratch path for the test."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path


class GitHubCollectorReposConfigTests(_RedirectedConfigPathTestCase):
    def test_round_trip_normalizes_dedupes_and_sorts(self) -> None:
        set_github_collector_repos(
            ["Hypercart-Dev-Tools/rebalance-git-pulse", "example/repo", "hypercart-dev-tools/REBALANCE-GIT-PULSE"]
        )
        self.assertEqual(
            get_github_collector_repos(),
            ["example/repo", "hypercart-dev-tools/rebalance-git-pulse"],
        )

    def test_add_remove_membership_case_insensitive(self) -> None:
        self.assertTrue(add_github_collector_repo("Hypercart-Dev-Tools/rebalance-git-pulse"))
        self.assertFalse(add_github_collector_repo("hypercart-dev-tools/REBALANCE-GIT-PULSE"))
        self.assertTrue(is_github_repo_collector("HYPERCART-DEV-TOOLS/rebalance-git-pulse"))
        self.assertTrue(remove_github_collector_repo("Hypercart-Dev-Tools/rebalance-git-pulse"))
        self.assertFalse(is_github_repo_collector("hypercart-dev-tools/rebalance-git-pulse"))


class GitHubBalanceCollectorFilteringTests(_RedirectedConfigPathTestCase):
    def test_collector_repo_dropped_from_balance_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            db_path = Path(workdir) / "rebalance.db"
            _seed_activity(db_path, "hypercart-dev-tools/rebalance-git-pulse", "2026-05-05T12:00:00Z")
            _seed_activity(db_path, "neochrometeam/sleuth-app", "2026-05-05T12:00:00Z")
            add_github_collector_repo("hypercart-dev-tools/rebalance-git-pulse")

            project_repos = {
                "Rebalance Git Pulse": ["hypercart-dev-tools/rebalance-git-pulse"],
                "Neochrome": ["neochrometeam/sleuth-app"],
            }
            results = get_github_balance(db_path, project_repos, since_days=30)

        names = [r["project_name"] for r in results]
        # Collector-only project disappears entirely from the balance view.
        self.assertNotIn("Rebalance Git Pulse", names)
        self.assertIn("Neochrome", names)

    def test_include_collectors_flag_keeps_them_visible(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            db_path = Path(workdir) / "rebalance.db"
            _seed_activity(db_path, "hypercart-dev-tools/rebalance-git-pulse", "2026-05-05T12:00:00Z")
            add_github_collector_repo("hypercart-dev-tools/rebalance-git-pulse")

            project_repos = {
                "Rebalance Git Pulse": ["hypercart-dev-tools/rebalance-git-pulse"],
            }
            results = get_github_balance(
                db_path, project_repos, since_days=30, include_collectors=True
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["project_name"], "Rebalance Git Pulse")
        self.assertEqual(results[0]["total_commits"], 1)

    def test_mixed_project_keeps_non_collector_repos(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            db_path = Path(workdir) / "rebalance.db"
            _seed_activity(db_path, "hypercart-dev-tools/rebalance-git-pulse", "2026-05-05T12:00:00Z")
            _seed_activity(db_path, "neochrometeam/sleuth-app", "2026-05-05T12:00:00Z")
            add_github_collector_repo("hypercart-dev-tools/rebalance-git-pulse")

            project_repos = {
                "Mixed": [
                    "hypercart-dev-tools/rebalance-git-pulse",
                    "neochrometeam/sleuth-app",
                ],
            }
            results = get_github_balance(db_path, project_repos, since_days=30)

        self.assertEqual(len(results), 1)
        # The collector repo is removed from repos_linked; only the real repo remains.
        self.assertEqual(results[0]["repos_linked"], ["neochrometeam/sleuth-app"])
        self.assertEqual(results[0]["repos_touched"], ["neochrometeam/sleuth-app"])
        self.assertEqual(results[0]["total_commits"], 1)


class IndexStatusCollectorHeartbeatTests(_RedirectedConfigPathTestCase):
    def test_collectors_block_present_with_last_active_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            db_path = Path(workdir) / "rebalance.db"
            _seed_activity(db_path, "hypercart-dev-tools/rebalance-git-pulse", "2026-05-05T12:00:00Z")
            add_github_collector_repo("hypercart-dev-tools/rebalance-git-pulse")

            status = get_index_status(db_path)

        self.assertIn("collectors", status)
        self.assertIn("hypercart-dev-tools/rebalance-git-pulse", status["collectors"])
        self.assertEqual(
            status["collectors"]["hypercart-dev-tools/rebalance-git-pulse"],
            "2026-05-05T12:00:00Z",
        )

    def test_collectors_block_reports_none_when_repo_has_no_activity(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            db_path = Path(workdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                ensure_github_schema(conn)  # create empty table
            add_github_collector_repo("example/some-collector")

            status = get_index_status(db_path)

        self.assertIsNone(status["collectors"]["example/some-collector"])

    def test_collectors_block_empty_when_no_collectors_configured(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            db_path = Path(workdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                ensure_github_schema(conn)

            status = get_index_status(db_path)

        self.assertEqual(status["collectors"], {})


if __name__ == "__main__":
    unittest.main()
