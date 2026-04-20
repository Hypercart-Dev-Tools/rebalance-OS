"""Tests for issue <-> PR reconciliation and close recommendations."""

import json
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.ingest.github_reconciliation import infer_issue_pr_close_candidates


def _insert_issue(
    conn: object,
    *,
    repo: str,
    number: int,
    title: str,
    body: str = "",
    milestone_title: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO github_items
            (repo_full_name, item_type, number, node_id, github_id, title, body, state, state_reason,
             author_login, assignees_json, labels_json, milestone_number, milestone_title, is_draft,
             is_merged, base_ref, head_ref, head_sha, mergeable_state, review_decision, check_status,
             requested_reviewers_json, comments_count, review_comments_count, commits_count,
             additions, deletions, changed_files, html_url, created_at, updated_at, closed_at,
             merged_at, fetched_at)
        VALUES (?, 'issue', ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, 0, 0, '', '', '', '', '', '', '[]', 0, 0, 0, 0, 0, 0, ?, ?, ?, ?, ?, ?)
        """,
        (
            repo,
            number,
            f"ISSUE_{number}",
            number + 1000,
            title,
            body,
            None,
            "alice",
            json.dumps(["alice"]),
            json.dumps([]),
            number if milestone_title else None,
            milestone_title,
            f"https://github.example/issues/{number}",
            "2026-04-17T08:00:00Z",
            "2026-04-17T12:00:00Z",
            None,
            None,
            "2026-04-17T12:30:00Z",
        ),
    )


def _insert_pr(
    conn: object,
    *,
    repo: str,
    number: int,
    title: str,
    body: str = "",
    head_ref: str,
    base_ref: str = "development",
    milestone_title: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO github_items
            (repo_full_name, item_type, number, node_id, github_id, title, body, state, state_reason,
             author_login, assignees_json, labels_json, milestone_number, milestone_title, is_draft,
             is_merged, base_ref, head_ref, head_sha, mergeable_state, review_decision, check_status,
             requested_reviewers_json, comments_count, review_comments_count, commits_count,
             additions, deletions, changed_files, html_url, created_at, updated_at, closed_at,
             merged_at, fetched_at)
        VALUES (?, 'pull_request', ?, ?, ?, ?, ?, 'closed', ?, ?, ?, ?, ?, ?, 0, 1, ?, ?, ?, 'clean', 'APPROVED', 'success', '[]', 0, 0, 1, 10, 2, 1, ?, ?, ?, ?, ?, ?)
        """,
        (
            repo,
            number,
            f"PR_{number}",
            number + 2000,
            title,
            body,
            None,
            "bob",
            json.dumps(["bob"]),
            json.dumps([]),
            number if milestone_title else None,
            milestone_title,
            base_ref,
            head_ref,
            f"sha-{number}",
            f"https://github.example/pull/{number}",
            "2026-04-17T09:00:00Z",
            "2026-04-17T12:15:00Z",
            None,
            "2026-04-17T12:20:00Z",
            "2026-04-17T12:30:00Z",
        ),
    )


class GitHubReconciliationTests(unittest.TestCase):
    def test_explicit_closing_keyword_becomes_auto_close_recommendation(self) -> None:
        repo = "BinoidCBD/universal-child-theme-oct-2024"
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path, ensure_github_schema) as conn:
                conn.execute(
                    """
                    INSERT INTO github_repo_meta
                        (repo_full_name, default_branch, pushed_at, updated_at, open_issues_count,
                         has_issues, has_projects, fetched_at)
                    VALUES (?, 'development', ?, ?, 1, 1, 0, ?)
                    """,
                    (repo, "2026-04-17T12:00:00Z", "2026-04-17T12:00:00Z", "2026-04-17T12:30:00Z"),
                )
                _insert_issue(conn, repo=repo, number=101, title="Fix mini-cart hydration bug", milestone_title="Silver")
                _insert_pr(
                    conn,
                    repo=repo,
                    number=202,
                    title="Fix mini-cart hydration bug",
                    body="Fixes #101 by shipping the final AJAX hydration patch.",
                    head_ref="fix/101-mini-cart",
                    milestone_title="Silver",
                )
                conn.execute(
                    """
                    INSERT INTO github_links
                        (repo_full_name, source_type, source_number, target_type, target_number, link_kind)
                    VALUES (?, 'pull_request', 202, 'issue', 101, 'closes')
                    """,
                    (repo,),
                )
                conn.commit()

            report = infer_issue_pr_close_candidates(db_path, repo)
            self.assertEqual(report.counts["high_confidence"], 1)
            self.assertEqual(report.counts["explicit_auto_close"], 1)
            candidate = report.high_confidence[0]
            self.assertEqual(candidate.issue_number, 101)
            self.assertEqual(candidate.pr_number, 202)
            self.assertEqual(candidate.recommendation, "auto_close_recommended")
            self.assertTrue(candidate.explicit_close)

    def test_inferred_branch_and_issue_reference_becomes_high_confidence_close(self) -> None:
        repo = "BinoidCBD/universal-child-theme-oct-2024"
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path, ensure_github_schema) as conn:
                conn.execute(
                    """
                    INSERT INTO github_repo_meta
                        (repo_full_name, default_branch, pushed_at, updated_at, open_issues_count,
                         has_issues, has_projects, fetched_at)
                    VALUES (?, 'development', ?, ?, 1, 1, 0, ?)
                    """,
                    (repo, "2026-04-17T12:00:00Z", "2026-04-17T12:00:00Z", "2026-04-17T12:30:00Z"),
                )
                _insert_issue(
                    conn,
                    repo=repo,
                    number=761,
                    title='Out of stock product should show "Sold Out" button',
                    body="Tracked in #766 after the production hotfix was merged.",
                )
                _insert_pr(
                    conn,
                    repo=repo,
                    number=766,
                    title='Use variation.is_in_stock for sold out button state',
                    body="Production hotfix for sold out button state.",
                    head_ref="hotfix/761-Out-of-Stock-product-showing-disabled-Add-to-Cart",
                    base_ref="main",
                )
                conn.commit()

            report = infer_issue_pr_close_candidates(db_path, repo)
            self.assertEqual(report.counts["high_confidence"], 1)
            candidate = report.high_confidence[0]
            self.assertEqual(candidate.issue_number, 761)
            self.assertEqual(candidate.pr_number, 766)
            self.assertEqual(candidate.recommendation, "close_recommended")
            self.assertFalse(candidate.explicit_close)
            self.assertGreaterEqual(candidate.confidence, 0.85)

    def test_commit_message_plus_title_overlap_becomes_medium_confidence_review(self) -> None:
        repo = "BinoidCBD/universal-child-theme-oct-2024"
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path, ensure_github_schema) as conn:
                conn.execute(
                    """
                    INSERT INTO github_repo_meta
                        (repo_full_name, default_branch, pushed_at, updated_at, open_issues_count,
                         has_issues, has_projects, fetched_at)
                    VALUES (?, 'development', ?, ?, 1, 1, 0, ?)
                    """,
                    (repo, "2026-04-17T12:00:00Z", "2026-04-17T12:00:00Z", "2026-04-17T12:30:00Z"),
                )
                _insert_issue(
                    conn,
                    repo=repo,
                    number=300,
                    title="Cache rate verification",
                    milestone_title="Silver",
                )
                _insert_pr(
                    conn,
                    repo=repo,
                    number=301,
                    title="Cache rate metrics update",
                    body="Implements the remaining cache-rate follow-up for #300.",
                    head_ref="perf/cache-metrics-followup",
                    milestone_title="Silver",
                )
                conn.execute(
                    """
                    INSERT INTO github_commits
                        (repo_full_name, item_type, item_number, sha, author_login, message,
                         committed_at, html_url, fetched_at)
                    VALUES (?, 'pull_request', 301, 'abc123', 'bob', ?, ?, ?, ?)
                    """,
                    (
                        repo,
                        "follow-up for #300 after cache metrics review",
                        "2026-04-17T12:10:00Z",
                        "https://github.example/commit/abc123",
                        "2026-04-17T12:30:00Z",
                    ),
                )
                conn.commit()

            report = infer_issue_pr_close_candidates(db_path, repo)
            self.assertEqual(report.counts["medium_confidence"], 1)
            candidate = report.medium_confidence[0]
            self.assertEqual(candidate.issue_number, 300)
            self.assertEqual(candidate.pr_number, 301)
            self.assertEqual(candidate.recommendation, "manual_review_recommended")
            self.assertGreaterEqual(candidate.confidence, 0.65)
            self.assertLess(candidate.confidence, 0.85)


if __name__ == "__main__":
    unittest.main()
