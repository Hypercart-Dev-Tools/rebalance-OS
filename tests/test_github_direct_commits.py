"""Regression coverage for GH-155 direct branch-push collection."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_schema
from rebalance.ingest.db import github as gh
from rebalance.ingest.github_direct_commits import (
    capture_direct_commits,
    sync_direct_commit_documents,
)
from rebalance.ingest.next_actions import OperatorBundle, github_candidates
from rebalance.ingest.pulse import _query_day_activity


REPO = "Hypercart-Dev-Tools/rebalance-OS"
SHA = "cfeafe4f564cf8f8fa5b161bad80642ae8752d16"
BEFORE = "383d61cfb631998d55d7e33856b7fb7cdd55a01a"


def _event() -> dict:
    # Deliberately mirrors production observations: no payload.commits list.
    return {
        "id": "push-155",
        "type": "PushEvent",
        "repo": {"name": REPO},
        "created_at": "2026-07-18T03:06:20Z",
        "payload": {"ref": "refs/heads/main", "before": BEFORE, "head": SHA},
    }


def _commit() -> dict:
    return {
        "sha": SHA,
        "html_url": f"https://github.com/{REPO}/commit/{SHA}",
        "author": {"login": "noelsaw1"},
        "commit": {
            "message": "feat: bring CLIO into rebalance-OS as its canonical home",
            "author": {"name": "Noel", "date": "2026-07-18T03:06:18Z"},
            "committer": {"date": "2026-07-18T03:06:18Z"},
        },
        "files": [
            {"filename": "utils/CLIO/INSTALL.md", "status": "added", "additions": 10, "deletions": 0, "changes": 10},
            {"filename": "utils/CLIO/LICENSE", "status": "added", "additions": 1, "deletions": 0, "changes": 1},
            {"filename": "utils/CLIO/README.md", "status": "added", "additions": 570, "deletions": 0, "changes": 570},
        ],
    }


class DirectCommitCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "rebalance.db"

    def test_event_without_payload_commits_resolves_paths_and_is_idempotent(self) -> None:
        calls: list[str] = []
        commit = _commit()

        def fetch(url: str):
            calls.append(url)
            if "/compare/" in url:
                return 200, {"ahead_by": 1, "commits": [dict(commit, files=[])]}
            if f"/commits/{SHA}" in url:
                return 200, commit
            return 404, {}

        result = capture_direct_commits(
            self.db_path, token="unused", events=[_event()], watched_repos=[REPO], api_get=fetch,
        )
        self.assertEqual(result.events_new, 1)
        self.assertEqual(result.commits_captured, 1)
        self.assertEqual(result.api_calls_used, 2)
        with db_connection(self.db_path, ensure_github_schema) as conn:
            row = conn.execute(
                "SELECT message, path_coverage FROM github_direct_commits WHERE sha = ?", (SHA,)
            ).fetchone()
            paths = [r["path"] for r in conn.execute(
                "SELECT path FROM github_direct_commit_files WHERE sha = ? ORDER BY path", (SHA,)
            ).fetchall()]
            event = conn.execute("SELECT state FROM github_push_events WHERE event_id = 'push-155'").fetchone()
        self.assertEqual(row["path_coverage"], "complete")
        self.assertIn("CLIO", row["message"])
        self.assertEqual(paths, ["utils/CLIO/INSTALL.md", "utils/CLIO/LICENSE", "utils/CLIO/README.md"])
        self.assertEqual(event["state"], "enriched")

        calls.clear()
        again = capture_direct_commits(
            self.db_path, token="unused", events=[_event()], watched_repos=[REPO], api_get=fetch,
        )
        self.assertEqual(again.events_new, 0)
        self.assertEqual(again.api_calls_used, 0)
        self.assertEqual(calls, [])

    def test_compare_cap_leaves_durable_deferred_receipt(self) -> None:
        result = capture_direct_commits(
            self.db_path, token="unused", events=[_event()], watched_repos=[REPO],
            api_get=lambda _url: self.fail("cap must prevent API calls"), compare_cap=0,
        )
        self.assertEqual(result.events_deferred, 1)
        with db_connection(self.db_path, ensure_github_schema) as conn:
            row = conn.execute(
                "SELECT state, failure_reason FROM github_push_events WHERE event_id = 'push-155'"
            ).fetchone()
        self.assertEqual(row["state"], "deferred")
        self.assertIn("cap", row["failure_reason"])

    def test_pr_overlap_removes_direct_document_but_keeps_raw_provenance(self) -> None:
        commit = _commit()

        def fetch(url: str):
            if "/compare/" in url:
                return 200, {"ahead_by": 1, "commits": [dict(commit, files=[])]}
            return 200, commit

        capture_direct_commits(
            self.db_path, token="unused", events=[_event()], watched_repos=[REPO], api_get=fetch,
        )
        self.assertEqual(sync_direct_commit_documents(self.db_path), 1)
        with db_connection(self.db_path, ensure_github_schema) as conn:
            gh.upsert_commit(conn, (REPO, "pull_request", 155, SHA, "noelsaw1", "PR version", "2026-07-18T03:06:18Z", "", "now"))
            conn.commit()
        self.assertEqual(sync_direct_commit_documents(self.db_path), 0)
        with db_connection(self.db_path, ensure_github_schema) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM github_direct_commits").fetchone()[0], 1)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM github_documents WHERE doc_type = 'direct_commit'").fetchone()[0],
                0,
            )

    def test_direct_commit_reaches_activity_and_hiqs_with_path_evidence(self) -> None:
        commit = _commit()

        def fetch(url: str):
            if "/compare/" in url:
                return 200, {"ahead_by": 1, "commits": [dict(commit, files=[])]}
            return 200, commit

        capture_direct_commits(
            self.db_path, token="unused", events=[_event()], watched_repos=[REPO], api_get=fetch,
        )
        with db_connection(self.db_path, ensure_github_schema) as conn:
            ensure_schema(conn)
            activity = _query_day_activity(
                conn,
                label="incident",
                start=datetime(2026, 7, 18, tzinfo=timezone.utc),
                end=datetime(2026, 7, 19, tzinfo=timezone.utc),
                github_login="noelsaw1",
                slack_user_id=None,
            )
        self.assertEqual(len(activity.gh_commits), 1)
        direct = activity.gh_commits[0]
        self.assertEqual(direct["source_kind"], "direct_push")
        self.assertIn("utils/CLIO/README.md", direct["paths"])
        candidates = github_candidates(OperatorBundle(local_day="incident", gh_commits=[direct]))
        self.assertEqual(len(candidates), 1)
        self.assertIn("utils/CLIO/README.md", candidates[0]["evidence"])
        self.assertIn("direct branch push", candidates[0]["why"])
