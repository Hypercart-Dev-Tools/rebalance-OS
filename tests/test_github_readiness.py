"""Tests for explicit GitHub release-readiness inference."""

import json
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.ingest.github_readiness import infer_github_release_readiness


class GitHubReadinessTests(unittest.TestCase):
    def test_returns_no_local_data_when_repo_has_not_been_synced(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            result = infer_github_release_readiness(
                database_path=db_path,
                repo_full_name="BinoidCBD/universal-child-theme-oct-2024",
            )

            self.assertEqual(result.status, "no_local_data")
            self.assertEqual(result.confidence, 0.0)
            self.assertIn("Sync artifacts first", result.summary)

    def test_flags_release_blockers_from_reviews_and_missing_release_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"

            with db_connection(db_path, ensure_github_schema) as conn:
                conn.execute(
                    """
                    INSERT INTO github_repo_meta
                        (repo_full_name, default_branch, pushed_at, updated_at, open_issues_count,
                         has_issues, has_projects, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "BinoidCBD/universal-child-theme-oct-2024",
                        "development",
                        "2026-04-17T12:00:00Z",
                        "2026-04-17T12:30:00Z",
                        4,
                        1,
                        0,
                        "2026-04-17T12:30:00Z",
                    ),
                )

                for name, is_default in [("development", 1), ("main", 0), ("release/3.5.2", 0)]:
                    conn.execute(
                        """
                        INSERT INTO github_branches
                            (repo_full_name, name, head_sha, is_protected, is_default, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "BinoidCBD/universal-child-theme-oct-2024",
                            name,
                            f"sha-{name}",
                            1,
                            is_default,
                            "2026-04-17T12:30:00Z",
                        ),
                    )

                conn.execute(
                    """
                    INSERT INTO github_milestones
                        (repo_full_name, number, title, description, state, open_issues, closed_issues,
                         due_on, created_at, updated_at, closed_at, html_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "BinoidCBD/universal-child-theme-oct-2024",
                        6,
                        "Silver",
                        "Next release train",
                        "open",
                        3,
                        0,
                        "2026-04-21T00:00:00Z",
                        "2026-04-10T00:00:00Z",
                        "2026-04-17T12:30:00Z",
                        None,
                        "https://github.example/milestones/6",
                    ),
                )

                issue_rows = [
                    (753, "Cart quantity fix", "open", "Silver"),
                    (755, "Checkout polish", "open", "Silver"),
                    (768, "Security hardening", "open", "Silver"),
                    (778, "Deployment: Silver, 04-21-2026", "open", None),
                ]
                for number, title, state, milestone_title in issue_rows:
                    conn.execute(
                        """
                        INSERT INTO github_items
                            (repo_full_name, item_type, number, node_id, github_id, title, body, state, state_reason,
                             author_login, assignees_json, labels_json, milestone_number, milestone_title, is_draft,
                             is_merged, base_ref, head_ref, head_sha, mergeable_state, review_decision, check_status,
                             requested_reviewers_json, comments_count, review_comments_count, commits_count,
                             additions, deletions, changed_files, html_url, created_at, updated_at, closed_at,
                             merged_at, fetched_at)
                        VALUES (?, 'issue', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "BinoidCBD/universal-child-theme-oct-2024",
                            number,
                            f"ISSUE_{number}",
                            number + 1000,
                            title,
                            "Deployment body references release/3.5.3 for staging and production."
                            if number == 778
                            else f"Issue body for #{number}",
                            state,
                            None,
                            "alice",
                            json.dumps(["alice"]),
                            json.dumps(["focus:release"]) if number != 778 else json.dumps(["deploy"]),
                            6 if milestone_title else None,
                            milestone_title,
                            0,
                            0,
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "[]",
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            f"https://github.example/issues/{number}",
                            "2026-04-17T08:00:00Z",
                            "2026-04-17T12:00:00Z",
                            None,
                            None,
                            "2026-04-17T12:30:00Z",
                        ),
                    )

                pr_rows = [
                    (759, "Fix cart quantity bug", "CHANGES_REQUESTED", "success", "fix/cart-qty"),
                    (769, "Polish checkout UX", "REVIEW_REQUIRED", "success", "feature/checkout-polish"),
                    (775, "Harden security checks", "REVIEW_REQUIRED", "success", "feature/security-hardening"),
                ]
                for number, title, review_decision, check_status, head_ref in pr_rows:
                    issue_number = 753 if number == 759 else 755 if number == 769 else 768
                    conn.execute(
                        """
                        INSERT INTO github_items
                            (repo_full_name, item_type, number, node_id, github_id, title, body, state, state_reason,
                             author_login, assignees_json, labels_json, milestone_number, milestone_title, is_draft,
                             is_merged, base_ref, head_ref, head_sha, mergeable_state, review_decision, check_status,
                             requested_reviewers_json, comments_count, review_comments_count, commits_count,
                             additions, deletions, changed_files, html_url, created_at, updated_at, closed_at,
                             merged_at, fetched_at)
                        VALUES (?, 'pull_request', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "BinoidCBD/universal-child-theme-oct-2024",
                            number,
                            f"PR_{number}",
                            number + 2000,
                            title,
                            f"Closes #{issue_number}",
                            "open",
                            None,
                            "bob",
                            json.dumps(["bob"]),
                            json.dumps(["PR: needs testing"]),
                            6,
                            "Silver",
                            0,
                            0,
                            "development",
                            head_ref,
                            f"sha-{number}",
                            "clean",
                            review_decision,
                            check_status,
                            json.dumps(["lead-dev"]),
                            1,
                            1,
                            1,
                            12,
                            2,
                            1,
                            f"https://github.example/pull/{number}",
                            "2026-04-17T09:00:00Z",
                            "2026-04-17T12:15:00Z",
                            None,
                            None,
                            "2026-04-17T12:30:00Z",
                        ),
                    )

                for pr_number, issue_number in [(759, 753), (769, 755), (775, 768)]:
                    conn.execute(
                        """
                        INSERT INTO github_links
                            (repo_full_name, source_type, source_number, target_type, target_number, link_kind)
                        VALUES (?, 'pull_request', ?, 'issue', ?, ?)
                        """,
                        (
                            "BinoidCBD/universal-child-theme-oct-2024",
                            pr_number,
                            issue_number,
                            "closes",
                        ),
                    )

                conn.execute(
                    """
                    INSERT INTO github_releases
                        (repo_full_name, github_id, tag_name, name, target_commitish, is_draft, is_prerelease,
                         body, created_at, published_at, html_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "BinoidCBD/universal-child-theme-oct-2024",
                        5001,
                        "v3.5.2",
                        "v3.5.2",
                        "main",
                        0,
                        0,
                        "Previous release",
                        "2026-04-15T00:00:00Z",
                        "2026-04-15T01:00:00Z",
                        "https://github.example/releases/v3.5.2",
                    ),
                )

                conn.commit()

            result = infer_github_release_readiness(
                database_path=db_path,
                repo_full_name="BinoidCBD/universal-child-theme-oct-2024",
                milestone_title="Silver",
            )

            self.assertEqual(result.status, "release_blocked")
            self.assertEqual(result.milestone_title, "Silver")
            self.assertEqual(result.release_branch, "release/3.5.3")
            self.assertFalse(result.release_branch_exists)
            self.assertGreaterEqual(result.confidence, 0.9)
            self.assertIn("changes requested", " ".join(result.blockers).lower())
            self.assertIn("release branch", " ".join(result.blockers).lower())
            self.assertEqual(result.counts["blocked_review_changes"], 1)
            self.assertEqual(result.counts["awaiting_review"], 2)
            self.assertEqual(len(result.issue_states), 3)
            self.assertIn("deployment issue", " ".join(result.evidence).lower())


if __name__ == "__main__":
    unittest.main()
