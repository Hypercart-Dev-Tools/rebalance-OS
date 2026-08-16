"""Regression coverage for GH-155 direct branch-push collection."""

from __future__ import annotations

import tempfile
import unittest
import sqlite3
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
        # GH-169 changed this assertion deliberately. It previously read
        # `events_deferred == 1`, which counted a cap deferral as a deferral
        # like any other -- and that conflation is precisely what let 20 live
        # events be evicted while the refresh summary looked healthy. Running
        # out of per-run budget is now counted separately from failing.
        self.assertEqual(result.events_over_budget, 1)
        self.assertEqual(result.events_deferred, 0)
        with db_connection(self.db_path, ensure_github_schema) as conn:
            row = conn.execute(
                "SELECT state, failure_reason, deferral_kind, attempt_count "
                "FROM github_push_events WHERE event_id = 'push-155'"
            ).fetchone()
        self.assertEqual(row["state"], "deferred")
        self.assertIn("cap", row["failure_reason"])
        self.assertEqual(row["deferral_kind"], "budget")
        # The receipt is durable in the sense that matters: it kept its
        # eligibility. Charging it here is what made "durable" untrue.
        self.assertEqual(row["attempt_count"], 0)

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


class DirectCommitEmbeddingPruningTests(unittest.TestCase):
    """GH-248: re-syncing direct commits must not orphan their vectors.

    Before this phase, ``sync_direct_commit_documents`` deleted every
    ``direct_commit`` document and re-inserted it with a fresh autoincrement
    id, leaving old ``github_embeddings`` rows behind (keyed to ids that no
    longer existed). vec0 never reclaims those slots, so the vector table grew
    without bound.

    Now, unchanged direct commits are idempotent (keeping their row id and
    existing vector), changed commits re-embed but keep their id, and vanished
    commits cleanly delete their vectors before deleting the document.

    The invariant these tests pin is the one the reclaim plan needs: after any
    number of syncs, every vector's ``doc_id`` resolves to a live document.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "rebalance.db"

    def _seed_direct_commit(self, sha: str) -> None:
        """Land one non-PR-overlapping direct commit so a document is produced."""
        with db_connection(self.db_path, ensure_github_schema) as conn:
            gh.upsert_direct_commit(
                conn,
                (
                    REPO,                            # repo_full_name
                    sha,                             # sha
                    f"push-{sha[:7]}",               # event_id
                    "refs/heads/main",               # ref
                    "noelsaw1",                      # author_login
                    "Noel",                          # author_name
                    f"direct commit {sha[:7]}",      # message
                    "2026-07-18T03:06:18Z",          # committed_at
                    f"https://github.com/{REPO}/commit/{sha}",
                    "complete",                      # path_coverage
                    "2026-07-18T03:06:20Z",          # discovered_at
                    "2026-07-18T03:06:20Z",          # fetched_at
                ),
            )
            conn.commit()

    def _embed_all_pending(self) -> int:
        """Stand in for the embedder: give every pending document a vector."""
        with db_connection(self.db_path, ensure_github_schema) as conn:
            pending = gh.github_documents_pending_embed(conn, min_chars=0)
            for row in pending:
                doc_id = row["id"]
                gh.upsert_github_embedding(conn, doc_id, b"\x00" * (1024 * 4))
                gh.mark_github_document_embedded(conn, doc_id)
            conn.commit()
        return len(pending)

    def _counts(self) -> tuple[int, int, int]:
        """(documents, vectors, orphaned vectors)."""
        with db_connection(self.db_path, ensure_github_schema) as conn:
            docs = conn.execute(
                "SELECT COUNT(*) FROM github_documents WHERE doc_type = 'direct_commit'"
            ).fetchone()[0]
            vectors = conn.execute(
                "SELECT COUNT(*) FROM github_embeddings"
            ).fetchone()[0]
            orphans = conn.execute(
                """
                SELECT COUNT(*) FROM github_embeddings e
                WHERE NOT EXISTS (
                    SELECT 1 FROM github_documents d WHERE d.id = e.doc_id
                )
                """
            ).fetchone()[0]
        return docs, vectors, orphans

    def _get_doc(self, sha: str) -> dict | None:
        with db_connection(self.db_path, ensure_github_schema) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM github_documents WHERE source_key = ?",
                (f"{REPO}:direct_commit:{sha}",)
            ).fetchone()
            return dict(row) if row else None

    def test_idempotence_and_vector_stability(self) -> None:
        """1. Idempotence & 2. Vector stability"""
        self._seed_direct_commit(SHA)
        self.assertEqual(sync_direct_commit_documents(self.db_path), 1)
        self.assertEqual(self._embed_all_pending(), 1)

        first_doc = self._get_doc(SHA)
        self.assertIsNotNone(first_doc)
        self.assertIsNotNone(first_doc["embedded_hash"])

        # Sync twice more
        for _round_number in range(1, 3):
            self.assertEqual(sync_direct_commit_documents(self.db_path), 1)
            # Pending embed count must be 0
            with db_connection(self.db_path, ensure_github_schema) as conn:
                pending = len(gh.github_documents_pending_embed(conn, min_chars=0))
                self.assertEqual(pending, 0, "No re-embedding should be scheduled")

            doc = self._get_doc(SHA)
            self.assertEqual(doc, first_doc, "Complete row must not churn across repeat syncs")

            docs, vectors, orphans = self._counts()
            self.assertEqual(vectors, 1)
            self.assertEqual(orphans, 0)

    def test_changed_content_does_reembed(self) -> None:
        """3. Changed content does re-embed."""
        self._seed_direct_commit(SHA)
        self.assertEqual(sync_direct_commit_documents(self.db_path), 1)
        self.assertEqual(self._embed_all_pending(), 1)

        first_doc = self._get_doc(SHA)

        # Mutate commit message
        with db_connection(self.db_path, ensure_github_schema) as conn:
            conn.execute(
                "UPDATE github_direct_commits SET message = 'mutated message' WHERE sha = ?",
                (SHA,)
            )
            conn.commit()

        self.assertEqual(sync_direct_commit_documents(self.db_path), 1)

        doc = self._get_doc(SHA)
        self.assertEqual(doc["id"], first_doc["id"], "Document id must stay the same to replace vector")
        self.assertIsNone(doc["embedded_hash"], "embedded_hash must be NULL to trigger re-embed")

        # Re-embed exactly 1
        self.assertEqual(self._embed_all_pending(), 1)

        docs, vectors, orphans = self._counts()
        self.assertEqual(vectors, 1)
        self.assertEqual(orphans, 0)

    def test_vanished_commit_prunes_both(self) -> None:
        """4. Vanished commit prunes both (PR overlap scenario)."""
        self._seed_direct_commit(SHA)
        self.assertEqual(sync_direct_commit_documents(self.db_path), 1)
        self.assertEqual(self._embed_all_pending(), 1)

        # Add idempotence interaction to prove the new upsert path is exercised
        self.assertEqual(sync_direct_commit_documents(self.db_path), 1)
        with db_connection(self.db_path, ensure_github_schema) as conn:
            pending = len(gh.github_documents_pending_embed(conn, min_chars=0))
            self.assertEqual(pending, 0)

        # Make PR-overlapping
        with db_connection(self.db_path, ensure_github_schema) as conn:
            gh.upsert_commit(
                conn,
                (REPO, "pull_request", 999, SHA, "noelsaw1", "msg", "2026-07-18T03:06:18Z", "", "now")
            )
            conn.commit()

        self.assertEqual(sync_direct_commit_documents(self.db_path), 0)

        doc = self._get_doc(SHA)
        self.assertIsNone(doc)

        docs, vectors, orphans = self._counts()
        self.assertEqual(docs, 0)
        self.assertEqual(vectors, 0)
        self.assertEqual(orphans, 0)

    def test_scale(self) -> None:
        """5. Scale: 5 commits, sync 3x."""
        shas = [f"{i:040x}" for i in range(1, 6)]
        for sha in shas:
            self._seed_direct_commit(sha)

        self.assertEqual(sync_direct_commit_documents(self.db_path), 5)
        self.assertEqual(self._embed_all_pending(), 5)
        self.assertEqual(self._counts(), (5, 5, 0))

        # Sync twice more
        for _ in range(2):
            self.assertEqual(sync_direct_commit_documents(self.db_path), 5)
            # Pending embed count must be 0 after first cycle
            with db_connection(self.db_path, ensure_github_schema) as conn:
                pending = len(gh.github_documents_pending_embed(conn, min_chars=0))
                self.assertEqual(pending, 0)

            docs, vectors, orphans = self._counts()
            self.assertEqual(orphans, 0)
            self.assertEqual(vectors, 5)
            self.assertEqual(docs, 5)
