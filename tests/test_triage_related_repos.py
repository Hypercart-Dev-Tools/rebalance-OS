"""Tests for triage related-repo tracking buckets."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema


def _load_triage_module() -> object:
    path = Path(__file__).resolve().parent.parent / "experimental" / "triage" / "spike.py"
    spec = importlib.util.spec_from_file_location("triage_spike", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load experimental triage module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _insert_item(
    conn: object,
    *,
    repo: str,
    item_type: str,
    number: int,
    title: str,
    body: str = "",
    updated_at: str,
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
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, 0, 0, '', '', '', '', '', '', '[]', 0, 0, 0, 0, 0, 0, ?, ?, ?, ?, ?, ?)
        """,
        (
            repo,
            item_type,
            number,
            f"{item_type}_{number}",
            number + 1000,
            title,
            body,
            None,
            "alice",
            json.dumps([]),
            json.dumps([]),
            None,
            None,
            f"https://github.com/{repo}/{'pull' if item_type == 'pull_request' else 'issues'}/{number}",
            "2026-05-05T08:00:00Z",
            updated_at,
            None,
            None,
            "2026-05-05T12:00:00Z",
        ),
    )


class TriageRelatedReposTests(unittest.TestCase):
    def test_related_repo_bucket_marks_tracked_and_missing_external_work(self) -> None:
        module = _load_triage_module()
        central = "binoidcbd/universal-child-theme-oct-2024"
        related = "kissplugins/kiss-woo-order-monitoring-alerts"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path, ensure_github_schema) as conn:
                _insert_item(
                    conn,
                    repo=central,
                    item_type="issue",
                    number=820,
                    title="Tracking: Woo Order Monitor HPOS warning on AcmeCorp",
                    body=f"External implementation: https://github.com/{related}/issues/27",
                    updated_at="2026-05-05T17:00:00Z",
                )
                _insert_item(
                    conn,
                    repo=related,
                    item_type="issue",
                    number=27,
                    title="Order monitor is triggering an HPOS warning",
                    updated_at="2026-05-05T16:28:57Z",
                )
                _insert_item(
                    conn,
                    repo=related,
                    item_type="pull_request",
                    number=28,
                    title="Feature/issue 27 hpos pass 2",
                    updated_at="2026-05-05T16:29:18Z",
                )
                conn.commit()

            with module.open_db(db_path) as conn:
                bucket = module.bucket_related_project_repos(
                    conn,
                    central,
                    related_repos=[related],
                )

        rendered = "\n".join(f"{item.title} {item.rationale}" for item in bucket.items)
        self.assertIn("Order monitor", rendered)
        self.assertIn("tracked centrally by [#820]", rendered)
        self.assertIn("Feature/issue 27 hpos pass 2", rendered)
        self.assertIn("missing central tracker link", rendered)


if __name__ == "__main__":
    unittest.main()
