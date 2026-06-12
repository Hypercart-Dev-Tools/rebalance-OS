"""Tests for external/watched GitHub repo monitoring.

Covers the registry ``external: true`` flag flowing into the watched set, the
whole-repo activity rollup derivation under the sentinel login, and the
idempotent + bidirectional de-dupe reconcile (suppress when worked locally,
resume when it goes quiet).
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rebalance.ingest import config as config_module
from rebalance.ingest.db import (
    db_connection,
    ensure_github_schema,
    ensure_project_schema,
)
from rebalance.ingest.github_watch import (
    WATCHED_LOGIN,
    derive_watched_repo_activity,
    reconcile_watched_repo,
    watched_repo_is_active_work,
)
from rebalance.ingest.index_ops import get_watched_repos
from rebalance.ingest.registry import get_external_repos

REPO = "upstream/widget"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _insert_external_project(conn, repos=(REPO,)) -> None:
    import json

    conn.execute(
        """
        INSERT INTO project_registry
            (name, status, summary, value_level, priority_tier, risk_level,
             repos_json, tags_json, custom_fields_json)
        VALUES (?, 'active', '', NULL, NULL, NULL, ?, '[]', ?)
        """,
        ("Watched — upstream", json.dumps(list(repos)), json.dumps({"external": True})),
    )


def _seed_artifacts(conn) -> None:
    """A merged PR, an open issue, and a comment — all within the window."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO github_items
            (repo_full_name, item_type, number, title, state, is_merged,
             created_at, updated_at, merged_at, fetched_at)
        VALUES (?, 'pull_request', 7, 'Add feature', 'closed', 1, ?, ?, ?, ?)
        """,
        (REPO, now, now, now, now),
    )
    conn.execute(
        """
        INSERT INTO github_items
            (repo_full_name, item_type, number, title, state, is_merged,
             created_at, updated_at, fetched_at)
        VALUES (?, 'issue', 8, 'A bug', 'open', 0, ?, ?, ?)
        """,
        (REPO, now, now, now),
    )
    conn.execute(
        """
        INSERT INTO github_comments
            (repo_full_name, item_type, item_number, comment_type,
             github_comment_id, author_login, body, created_at, fetched_at)
        VALUES (?, 'issue', 8, 'issue', 1, 'someone', 'hi', ?, ?)
        """,
        (REPO, now, now),
    )
    conn.commit()


def _two_commits_fetcher():
    """Fake GitHub fetcher: 2 commits on the first page, then empty."""
    calls = {"n": 0}

    def fetch(url: str):
        calls["n"] += 1
        if "page=1" in url:
            stamp = datetime.now(timezone.utc).isoformat()
            return [
                {"commit": {"committer": {"date": stamp}}},
                {"commit": {"committer": {"date": stamp}}},
            ]
        return []

    return fetch


class ExternalWatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"
        self.db = Path(self._tmp.name) / "rebalance.db"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig

    def test_external_project_enters_watched_set(self) -> None:
        with db_connection(self.db) as conn:
            ensure_project_schema(conn)
            _insert_external_project(conn)
            conn.commit()

        self.assertEqual(get_external_repos(self.db), [REPO])
        watched = get_watched_repos(self.db)
        self.assertIn(REPO, watched["watched"])
        self.assertEqual(watched["external_repos"], [REPO])

    def test_derive_writes_sentinel_rollup(self) -> None:
        with db_connection(self.db) as conn:
            ensure_github_schema(conn)
            _seed_artifacts(conn)

        summary = derive_watched_repo_activity(
            self.db, REPO, "tok", since_days=90, api_get_json=_two_commits_fetcher()
        )
        self.assertEqual(summary["commits"], 2)
        self.assertEqual(summary["prs_opened"], 1)
        self.assertEqual(summary["prs_merged"], 1)
        self.assertEqual(summary["issues_opened"], 1)
        self.assertEqual(summary["issue_comments"], 1)

        with db_connection(self.db) as conn:
            row = conn.execute(
                "SELECT login, commits, prs_merged FROM github_activity "
                "WHERE repo_full_name=?",
                (REPO,),
            ).fetchone()
        self.assertEqual(row["login"], WATCHED_LOGIN)
        self.assertEqual(row["commits"], 2)
        self.assertEqual(row["prs_merged"], 1)

    def test_activity_repos_excludes_sentinel(self) -> None:
        # A sentinel-only repo must not masquerade as the operator's own work.
        with db_connection(self.db) as conn:
            ensure_github_schema(conn)
            conn.execute(
                """
                INSERT INTO github_activity
                    (login, repo_full_name, scan_date, commits, pushes, prs_opened,
                     prs_merged, issues_opened, issue_comments, reviews,
                     last_active_at, scanned_at)
                VALUES (?, ?, date('now'), 5, 0, 0, 0, 0, 0, 0, ?, ?)
                """,
                (WATCHED_LOGIN, REPO, "2026-06-07T00:00:00Z", "2026-06-07T00:00:00Z"),
            )
            conn.commit()

        watched = get_watched_repos(self.db)
        self.assertNotIn(REPO, watched["activity_repos"])

    def test_reconcile_suppresses_when_worked_locally(self) -> None:
        with db_connection(self.db) as conn:
            ensure_github_schema(conn)
            _seed_artifacts(conn)
            # Operator has push/collab access → active work signal.
            conn.execute(
                """
                INSERT INTO github_pushed_repos
                    (repo_full_name, pushed_at, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?)
                """,
                (REPO, "2026-06-07T00:00:00Z", "2026-06-01T00:00:00Z", "2026-06-07T00:00:00Z"),
            )
            conn.commit()

        self.assertTrue(watched_repo_is_active_work(self.db, REPO, since_days=14))
        # Pre-seed a stale sentinel row, then reconcile should purge it.
        with db_connection(self.db) as conn:
            conn.execute(
                """
                INSERT INTO github_activity
                    (login, repo_full_name, scan_date, commits, pushes, prs_opened,
                     prs_merged, issues_opened, issue_comments, reviews,
                     last_active_at, scanned_at)
                VALUES (?, ?, date('now'), 9, 0, 0, 0, 0, 0, 0, ?, ?)
                """,
                (WATCHED_LOGIN, REPO, "2026-06-07T00:00:00Z", "2026-06-07T00:00:00Z"),
            )
            conn.commit()

        result = reconcile_watched_repo(
            self.db, REPO, "tok", since_days=14, api_get_json=_two_commits_fetcher()
        )
        self.assertEqual(result["mode"], "active")
        self.assertGreaterEqual(result["purged"], 1)
        with db_connection(self.db) as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM github_activity WHERE login=? AND repo_full_name=?",
                (WATCHED_LOGIN, REPO),
            ).fetchone()[0]
        self.assertEqual(n, 0)

    def test_reconcile_resumes_when_quiet(self) -> None:
        # No active-work signal → reconcile derives the rollup.
        with db_connection(self.db) as conn:
            ensure_github_schema(conn)
            _seed_artifacts(conn)

        result = reconcile_watched_repo(
            self.db, REPO, "tok", since_days=90, api_get_json=_two_commits_fetcher()
        )
        self.assertEqual(result["mode"], "external")
        self.assertEqual(result["commits"], 2)
        with db_connection(self.db) as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM github_activity WHERE login=? AND repo_full_name=?",
                (WATCHED_LOGIN, REPO),
            ).fetchone()[0]
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
