"""Tests for GH-124 commit-threshold auto-promotion of watched repos."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rebalance.ingest import config as config_module
from rebalance.ingest.calendar_config import CalendarConfig
from rebalance.ingest.config import set_github_ignored_repos, set_pulse_config
from rebalance.ingest.db import (
    db_connection,
    ensure_calendar_schema,
    ensure_github_schema,
    ensure_project_schema,
)
from rebalance.ingest.project_inference import (
    COMMIT_THRESHOLD_GENERATED_BY,
    sync_commit_threshold_promotions,
    sync_inferred_project_registry,
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


def _insert_activity(
    db: Path, *, repo: str, login: str = "tester", commits: int = 3, scan_date: str = "2026-07-01"
) -> None:
    """Seed github_activity — the operator's own push-events feed. ``commits``
    drives _count_operator_commits' primary signal; a fixed nonzero ``pushes``
    keeps the row a valid "candidate" (_activity_repos requires the summed
    counters to be > 0) even when ``commits=0`` (the fork-with-zero test)."""
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO github_activity
            (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
             issues_opened, issue_comments, reviews, last_active_at, scanned_at)
        VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0, ?, ?)
        """,
        (login, repo, scan_date, commits, f"{scan_date}T00:00:00Z", f"{scan_date}T00:00:00Z"),
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
        _insert_activity(self.db_path, repo=repo, commits=3)

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertTrue(summary.enabled)
        self.assertEqual(summary.promoted_count, 1)
        self.assertEqual(summary.promoted[0]["repos"], [repo])
        marker = summary.promoted[0]["custom_fields"]["inference"]["generated_by"]
        self.assertEqual(marker, COMMIT_THRESHOLD_GENERATED_BY)

    def test_below_threshold_does_not_promote(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo, commits=2)

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 0)

    def test_direct_push_commits_count_not_just_pr_commits(self) -> None:
        # Regression for a bug found in cross-model QA (GH-124): the original
        # implementation only counted github_commits (PR-commit listings only)
        # and silently undercounted any repo the operator pushes to directly.
        # github_activity.commits (PushEvent-sourced) must be the signal that
        # counts, with zero rows in github_commits at all.
        repo = "Acme/direct-push-widget"
        _insert_activity(self.db_path, repo=repo, commits=3)

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 1)

    def test_activity_commits_sum_across_scan_dates(self) -> None:
        # Each scan_date row is preserved (window-refetch semantics), so the
        # cumulative count must sum across days, not just read the latest.
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo, commits=1, scan_date="2026-06-30")
        _insert_activity(self.db_path, repo=repo, commits=1, scan_date="2026-07-01")
        _insert_activity(self.db_path, repo=repo, commits=1, scan_date="2026-07-02")

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 1)

    def test_fork_with_zero_operator_commits_never_promotes(self) -> None:
        repo = "Acme/forked-widget"
        # Repo is a visible "candidate" (nonzero pushes keeps it in
        # auto_discovered) but the operator has zero commits of their own —
        # someone else's commits on a shared/forked repo must not count.
        _insert_activity(self.db_path, repo=repo, commits=0)
        for i in range(5):
            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="someone-else")

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 0)

    def test_cloud_agent_commits_count_toward_threshold(self) -> None:
        repo = "Acme/widget"
        # Zero direct operator pushes; all 3 qualifying commits are bot-authored
        # PR commits, which only github_commits (not github_activity) can see.
        _insert_activity(self.db_path, repo=repo, commits=0)
        _insert_commit(self.db_path, repo=repo, sha="sha0", author_login="claude[bot]")
        _insert_commit(self.db_path, repo=repo, sha="sha1", author_login="claude[bot]")
        _insert_commit(self.db_path, repo=repo, sha="sha2", author_login="claude[bot]")

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 1)

    def test_operator_push_and_bot_commits_combine(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo, commits=2)
        _insert_commit(self.db_path, repo=repo, sha="sha0", author_login="claude[bot]")

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 1)
        self.assertEqual(summary.promoted[0]["custom_fields"]["inference"]["commit_count"], 3)

    def test_ignored_repo_never_promotes(self) -> None:
        repo = "Acme/widget"
        set_github_ignored_repos([repo])
        _insert_activity(self.db_path, repo=repo, commits=3)

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 0)

    def test_curated_row_never_touched(self) -> None:
        # A candidate whose natural display name collides with an existing
        # curated project must not overwrite or merge into it — disambiguation
        # (see test_name_collision_disambiguates_instead_of_overwriting) gives
        # it a distinct name instead, so the curated row's own content is the
        # invariant under test here, not whether the candidate gets dropped.
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo, commits=3)
        sync_db(
            self.db_path,
            {
                "projects": [
                    {
                        "name": "Widget",
                        "status": "active",
                        "summary": "hand-curated",
                        "repos": [],
                        "tags": [],
                        "custom_fields": {},
                    }
                ]
            },
        )

        sync_commit_threshold_promotions(self.db_path)

        with db_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT summary FROM project_registry WHERE name = 'Widget'"
            ).fetchone()
        self.assertEqual(row["summary"], "hand-curated")

    def test_name_collision_disambiguates_instead_of_overwriting(self) -> None:
        # Regression for a bug found in cross-model QA (GH-124): two different
        # repos sharing a slug (Acme/widget, Beta/widget) both derived the
        # bare name "widget"/"Widget", so the second promotion's sync_db()
        # upsert would silently overwrite the first row's repos_json.
        _insert_activity(self.db_path, repo="Acme/widget", commits=3)
        _insert_activity(self.db_path, repo="Beta/widget", commits=3)

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 2)
        names = {row["name"] for row in summary.promoted}
        self.assertEqual(len(names), 2, f"expected 2 distinct names, got {names}")
        with db_connection(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) AS n FROM project_registry").fetchone()["n"]
        self.assertEqual(count, 2)

    def test_idempotent_rerun_does_not_duplicate(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo, commits=3)

        sync_commit_threshold_promotions(self.db_path)
        sync_commit_threshold_promotions(self.db_path)

        with db_connection(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM project_registry WHERE name = 'Widget'"
            ).fetchone()["n"]
        self.assertEqual(count, 1)

    def test_disabled_is_a_no_op(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo, commits=3)
        config_module._write_config(
            {**config_module._read_config(), "auto_promote_enabled": False}
        )

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertFalse(summary.enabled)
        self.assertEqual(summary.promoted_count, 0)

    def test_promotion_fires_auth_log_alert(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo, commits=3)

        with mock.patch(
            "rebalance.ingest.auth_log.log_project_auto_promoted"
        ) as mocked:
            sync_commit_threshold_promotions(self.db_path)

        mocked.assert_called_once_with(
            repo, project_name="Widget", commit_count=3, threshold=3
        )

    def test_no_promotion_does_not_fire_auth_log_alert(self) -> None:
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo, commits=2)

        with mock.patch(
            "rebalance.ingest.auth_log.log_project_auto_promoted"
        ) as mocked:
            sync_commit_threshold_promotions(self.db_path)

        mocked.assert_not_called()

    def test_auto_promoted_row_survives_activity_inference_sync(self) -> None:
        # Regression for a bug found in cross-model QA (GH-124): generalizing
        # _is_inference_owned() to recognize commit_threshold_v1 alongside
        # activity_inference_v1 must NOT make sync_inferred_project_registry's
        # stale-row cleanup delete auto-promoted rows it didn't itself create.
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo, commits=3)
        with db_connection(self.db_path) as conn:
            ensure_calendar_schema(conn)
        promote_summary = sync_commit_threshold_promotions(self.db_path)
        self.assertEqual(promote_summary.promoted_count, 1)

        # A completely unrelated activity/calendar inference sync (e.g. the
        # operator manually running `rebalance ingest infer-project-registry`)
        # must not touch the auto-promoted row.
        sync_inferred_project_registry(
            self.db_path,
            calendar_config=CalendarConfig(
                calendar_id="primary",
                exclude_titles=[],
                aggregator_skip_words=[],
                timezone="America/Los_Angeles",
                projects=[],
                hours_format="decimal",
            ),
        )

        with db_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT name FROM project_registry WHERE name = 'Widget'"
            ).fetchone()
        self.assertIsNotNone(row, "auto-promoted row was deleted by activity inference cleanup")

    def test_no_github_login_configured_is_a_no_op(self) -> None:
        # set_pulse_config(github_login=None) is a no-op (None means "leave
        # unchanged"), so clear it directly at the raw-config layer instead.
        config_module._write_config(
            {**config_module._read_config(), "github_login": None}
        )
        repo = "Acme/widget"
        _insert_activity(self.db_path, repo=repo, commits=3)

        summary = sync_commit_threshold_promotions(self.db_path)

        self.assertEqual(summary.promoted_count, 0)


if __name__ == "__main__":
    unittest.main()
