"""Tests for the watch-list coverage guard (snapshot + silent-reduction alarm).

Covers the pure helpers (diff/classify) and the snapshot_and_detect single
writer: baseline-safe first run, a concerning (project) reduction emitting one
event, rolling-window churn staying quiet, a just-ignored repo suppressed, a
re-add emitting nothing, and 30-day pruning. See
PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rebalance.ingest import config as config_module
from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_project_schema
from rebalance.ingest.watchlist_guard import classify_removal, snapshot_and_detect

_DAY = 86400


class ClassifyRemovalTests(unittest.TestCase):
    def test_project_is_warn(self) -> None:
        self.assertEqual(classify_removal({"project"}), "warn")

    def test_external_is_warn(self) -> None:
        self.assertEqual(classify_removal({"external"}), "warn")

    def test_window_only_is_info(self) -> None:
        self.assertEqual(classify_removal({"activity"}), "info")
        self.assertEqual(classify_removal({"pushed"}), "info")
        self.assertEqual(classify_removal({"activity", "pushed"}), "info")

    def test_mixed_membership_warns(self) -> None:
        # A repo held by both a window and the registry is durable-intent.
        self.assertEqual(classify_removal({"activity", "project"}), "warn")

    def test_empty_is_info(self) -> None:
        self.assertEqual(classify_removal(set()), "info")


class SnapshotAndDetectTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_config_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"
        self.db_path = Path(self._tmp.name) / "rebalance.db"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_config_path

    # -- seed helpers ---------------------------------------------------------

    def _add_project_repo(self, repo: str, name: str = "Proj") -> None:
        with db_connection(self.db_path) as conn:
            ensure_project_schema(conn)
            conn.execute(
                "INSERT INTO project_registry "
                "(name, status, summary, value_level, priority_tier, risk_level, "
                " repos_json, tags_json, custom_fields_json) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (name, "active", "", None, None, None, f'["{repo}"]', "[]", "{}"),
            )
            conn.commit()

    def _remove_project_repo(self, name: str = "Proj") -> None:
        with db_connection(self.db_path) as conn:
            conn.execute("DELETE FROM project_registry WHERE name=?", (name,))
            conn.commit()

    def _add_activity_repo(self, repo: str) -> None:
        with db_connection(self.db_path) as conn:
            ensure_github_schema(conn)
            conn.execute(
                "INSERT INTO github_activity "
                "(login, repo_full_name, scan_date, commits, pushes, prs_opened, "
                " prs_merged, issues_opened, issue_comments, reviews, last_active_at, "
                " scanned_at) VALUES (?,?,date('now'),?,?,?,?,?,?,?,?,?)",
                ("collaborator", repo, 1, 1, 0, 0, 0, 0, 0,
                 "2026-06-20T12:00:00Z", "2026-06-20T12:05:00Z"),
            )
            conn.commit()

    def _remove_activity_repo(self, repo: str) -> None:
        with db_connection(self.db_path) as conn:
            conn.execute(
                "DELETE FROM github_activity WHERE repo_full_name=?", (repo,)
            )
            conn.commit()

    def _snapshot_rows(self, ts: int) -> list[str]:
        with db_connection(self.db_path) as conn:
            return [
                r["repo"] for r in conn.execute(
                    "SELECT repo FROM watched_repos_snapshot WHERE snapshot_ts=?",
                    (ts,),
                ).fetchall()
            ]

    # -- tests ----------------------------------------------------------------

    def test_first_run_is_baseline_no_event(self) -> None:
        self._add_project_repo("example/owned")
        with mock.patch(
            "rebalance.ingest.auth_log.log_watched_repos_reduced"
        ) as emit:
            res = snapshot_and_detect(self.db_path, now_ts=1_000_000)
        emit.assert_not_called()
        self.assertTrue(res["baseline"])
        self.assertEqual(self._snapshot_rows(1_000_000), ["example/owned"])

    def test_project_repo_removal_emits_one_warn_event(self) -> None:
        self._add_project_repo("example/owned")
        self._add_activity_repo("example/window")
        snapshot_and_detect(self.db_path, now_ts=2_000_000)  # baseline

        self._remove_project_repo()  # durable-intent repo drops off
        with mock.patch(
            "rebalance.ingest.auth_log.log_watched_repos_reduced"
        ) as emit:
            res = snapshot_and_detect(self.db_path, now_ts=2_000_100)

        emit.assert_called_once()
        (removed,), kwargs = emit.call_args
        self.assertEqual([r["repo"] for r in removed], ["example/owned"])
        self.assertEqual(removed[0]["last_buckets"], ["project"])
        self.assertEqual(kwargs["info_churn"], [])
        self.assertEqual(res["removed"], ["example/owned"])
        # The window repo is untouched and still present.
        self.assertIn("example/window", self._snapshot_rows(2_000_100))

    def test_window_only_churn_stays_quiet(self) -> None:
        self._add_project_repo("example/owned")
        self._add_activity_repo("example/window")
        snapshot_and_detect(self.db_path, now_ts=3_000_000)  # baseline

        self._remove_activity_repo("example/window")  # rolling-window aging out
        with mock.patch(
            "rebalance.ingest.auth_log.log_watched_repos_reduced"
        ) as emit:
            res = snapshot_and_detect(self.db_path, now_ts=3_000_100)

        emit.assert_not_called()  # info-only churn does not alarm
        self.assertEqual(res["info_churn"], ["example/window"])
        self.assertEqual(res["warn_removed"], [])

    def test_just_ignored_repo_is_suppressed(self) -> None:
        self._add_project_repo("example/owned")
        snapshot_and_detect(self.db_path, now_ts=4_000_000)  # baseline

        # Operator intentionally ignores it, then it leaves the watched set.
        config_module.add_github_ignored_repo("example/owned")
        self._remove_project_repo()
        with mock.patch(
            "rebalance.ingest.auth_log.log_watched_repos_reduced"
        ) as emit:
            res = snapshot_and_detect(self.db_path, now_ts=4_000_100)

        emit.assert_not_called()  # an intentional opt-out is not a coverage loss
        self.assertEqual(res["warn_removed"], [])

    def test_readd_emits_nothing(self) -> None:
        self._add_project_repo("example/owned")
        self._add_activity_repo("example/window")  # keeps the set non-empty throughout
        snapshot_and_detect(self.db_path, now_ts=5_000_000)  # baseline
        self._remove_project_repo()
        with mock.patch("rebalance.ingest.auth_log.log_watched_repos_reduced"):
            snapshot_and_detect(self.db_path, now_ts=5_000_100)  # removal (warn)

        self._add_project_repo("example/owned")  # comes back
        with mock.patch(
            "rebalance.ingest.auth_log.log_watched_repos_reduced"
        ) as emit:
            res = snapshot_and_detect(self.db_path, now_ts=5_000_200)

        emit.assert_not_called()
        self.assertEqual(res["removed"], [])
        self.assertEqual(res["added"], ["example/owned"])

    def test_old_snapshots_are_pruned(self) -> None:
        self._add_project_repo("example/owned")
        snapshot_and_detect(self.db_path, now_ts=6_000_000)  # baseline (old)
        # Next snapshot 31 days later → the baseline is beyond the 30-day window.
        snapshot_and_detect(self.db_path, now_ts=6_000_000 + 31 * _DAY)

        self.assertEqual(self._snapshot_rows(6_000_000), [])  # pruned
        self.assertEqual(
            self._snapshot_rows(6_000_000 + 31 * _DAY), ["example/owned"]
        )


if __name__ == "__main__":
    unittest.main()
