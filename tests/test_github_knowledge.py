"""Tests for GitHub artifact sync, local document build, and semantic query."""

import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rebalance.ingest import config as config_module
from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_semantic_schema
from rebalance.ingest.github_knowledge import (
    purge_github_repo_data,
    embed_github_documents,
    sync_github_repo,
)
from rebalance.ingest.config import add_github_ignored_repo
from rebalance.ingest.embedder import _vec_to_bytes


# sync_github_repo filters the /pulls list client-side via stop_updated_before,
# so the PR-summary updated_at must stay inside the since_days window. Computed
# relative to now so the fixture never ages out — a hardcoded April-2026 date
# previously drifted past a 30-day cutoff and silently zeroed prs_synced.
_RECENT_ISO = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)


def _fake_github_api(url: str) -> object:
    if "page=2" in url:
        return []

    if url == "https://api.github.com/repos/AcmeOrg/sample-child-theme-oct-2024":
        return {
            "default_branch": "development",
            "pushed_at": "2026-04-17T13:00:00Z",
            "updated_at": "2026-04-17T13:00:00Z",
            "open_issues_count": 2,
            "has_issues": True,
            "has_projects": False,
        }

    if "/branches?" in url:
        return [
            {
                "name": "development",
                "protected": True,
                "commit": {"sha": "deadbeef"},
            },
            {
                "name": "main",
                "protected": True,
                "commit": {"sha": "feedface"},
            },
        ]

    if "/labels?" in url:
        return [
            {
                "name": "security",
                "color": "cc2244",
                "description": "Security work",
                "default": False,
            }
        ]

    if "/milestones?" in url:
        return [
            {
                "number": 6,
                "title": "Silver",
                "description": "Next release train",
                "state": "open",
                "open_issues": 2,
                "closed_issues": 0,
                "due_on": "2026-04-21T00:00:00Z",
                "created_at": "2026-04-17T00:00:00Z",
                "updated_at": "2026-04-17T01:00:00Z",
                "closed_at": None,
                "html_url": "https://github.example/milestone/6",
            }
        ]

    if "/releases?" in url:
        return [
            {
                "id": 5001,
                "tag_name": "v3.5.2",
                "name": "v3.5.2",
                "target_commitish": "main",
                "draft": False,
                "prerelease": False,
                "body": "Previous production release.",
                "created_at": "2026-04-15T00:00:00Z",
                "published_at": "2026-04-15T01:00:00Z",
                "html_url": "https://github.example/releases/v3.5.2",
            }
        ]

    if "/issues?" in url and "/issues/" not in url:
        return [
            {
                "number": 101,
                "id": 1001,
                "node_id": "ISSUE_101",
                "title": "Security hardening for AJAX nonce verification",
                "body": "The checkout AJAX endpoints need nonce validation to block CSRF.",
                "state": "open",
                "state_reason": None,
                "comments": 1,
                "created_at": "2026-04-17T08:00:00Z",
                "updated_at": "2026-04-17T12:00:00Z",
                "closed_at": None,
                "user": {"login": "alice"},
                "labels": [{"name": "security"}],
                "assignees": [{"login": "bob"}],
                "milestone": {"number": 6, "title": "Silver"},
                "html_url": "https://github.example/issues/101",
            }
        ]

    if "/pulls?" in url and "/pulls/" not in url:
        return [
            {
                "number": 202,
                "updated_at": _RECENT_ISO,
            }
        ]

    if url.endswith("/pulls/202"):
        return {
            "number": 202,
            "id": 2002,
            "node_id": "PR_202",
            "title": "Add nonce handling for checkout requests",
            "body": "Fixes #101 by adding AJAX nonce retrieval and validation.",
            "state": "open",
            "draft": False,
            "merged_at": None,
            "comments": 1,
            "review_comments": 1,
            "commits": 1,
            "additions": 42,
            "deletions": 5,
            "changed_files": 3,
            "created_at": "2026-04-17T09:00:00Z",
            "updated_at": "2026-04-17T13:00:00Z",
            "closed_at": None,
            "user": {"login": "bob"},
            "assignees": [{"login": "bob"}],
            "labels": [{"name": "security"}],
            "requested_reviewers": [{"login": "lead-dev"}],
            "milestone": {"number": 6, "title": "Silver"},
            "head": {"ref": "chore/nonce-security", "sha": "deadbeef"},
            "base": {"ref": "development"},
            "mergeable_state": "clean",
            "html_url": "https://github.example/pull/202",
        }

    if "/issues/101/comments?" in url:
        return [
            {
                "id": 3001,
                "body": "Please prioritize this before the next deploy window.",
                "user": {"login": "lead-dev"},
                "author_association": "MEMBER",
                "html_url": "https://github.example/issues/101#issuecomment-1",
                "created_at": "2026-04-17T12:30:00Z",
                "updated_at": "2026-04-17T12:30:00Z",
            }
        ]

    if "/issues/202/comments?" in url:
        return [
            {
                "id": 3002,
                "body": "Smoke tested on staging checkout.",
                "user": {"login": "qa-user"},
                "author_association": "MEMBER",
                "html_url": "https://github.example/pull/202#issuecomment-2",
                "created_at": "2026-04-17T13:15:00Z",
                "updated_at": "2026-04-17T13:15:00Z",
            }
        ]

    if "/pulls/202/reviews?" in url:
        return [
            {
                "id": 4001,
                "state": "APPROVED",
                "body": "Looks good. Nonce coverage is in place.",
                "user": {"login": "lead-dev"},
                "author_association": "MEMBER",
                "html_url": "https://github.example/pull/202#review-1",
                "submitted_at": "2026-04-17T14:00:00Z",
            }
        ]

    if "/pulls/202/comments?" in url:
        return [
            {
                "id": 4002,
                "body": "Consider centralizing nonce retrieval later.",
                "user": {"login": "lead-dev"},
                "author_association": "MEMBER",
                "html_url": "https://github.example/pull/202#discussion_r1",
                "created_at": "2026-04-17T13:30:00Z",
                "updated_at": "2026-04-17T13:30:00Z",
                "in_reply_to_id": None,
            }
        ]

    if "/pulls/202/commits?" in url:
        return [
            {
                "sha": "abc1234",
                "html_url": "https://github.example/commit/abc1234",
                "author": {"login": "bob"},
                "commit": {
                    "message": "feat: add nonce verification for checkout ajax",
                    "author": {"date": "2026-04-17T11:00:00Z"},
                },
            }
        ]

    if "/commits/deadbeef/check-runs?" in url:
        return {
            "check_runs": [
                {
                    "name": "Performance & Security Audit",
                    "status": "completed",
                    "conclusion": "success",
                    "details_url": "https://github.example/checks/1",
                    "started_at": "2026-04-17T14:05:00Z",
                    "completed_at": "2026-04-17T14:06:00Z",
                }
            ]
        }

    raise AssertionError(f"Unexpected GitHub API URL in test: {url}")


def _fake_embed_texts(texts: list[str], _model_name: str) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * 1024
        lowered = text.lower()
        if "nonce" in lowered:
            vec[0] = 1.0
        elif "csrf" in lowered or "security" in lowered:
            vec[0] = 0.8
        elif "checkout" in lowered:
            vec[0] = 0.5
        else:
            vec[0] = 0.1
        vectors.append(vec)
    return vectors


class GitHubKnowledgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_sync_persists_github_artifacts_and_documents(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            result = sync_github_repo(
                database_path=db_path,
                repo_full_name="AcmeOrg/sample-child-theme-oct-2024",
                token="ghp_test",
                since_days=30,
                api_get_json=_fake_github_api,
            )

            self.assertEqual(result.issues_synced, 1)
            self.assertEqual(result.prs_synced, 1)
            self.assertEqual(result.comments_synced, 4)
            self.assertEqual(result.commits_synced, 1)
            self.assertEqual(result.checks_synced, 1)
            self.assertEqual(result.branches_synced, 2)
            self.assertGreaterEqual(result.docs_built, 6)

            with db_connection(db_path, ensure_github_schema) as conn:
                repo_meta = conn.execute(
                    """
                    SELECT default_branch, open_issues_count
                    FROM github_repo_meta
                    WHERE repo_full_name = ?
                    """,
                    ("AcmeOrg/sample-child-theme-oct-2024",),
                ).fetchone()
                self.assertIsNotNone(repo_meta)
                self.assertEqual(repo_meta["default_branch"], "development")
                self.assertEqual(repo_meta["open_issues_count"], 2)

                branch_rows = conn.execute(
                    """
                    SELECT name, is_default, is_protected
                    FROM github_branches
                    WHERE repo_full_name = ?
                    ORDER BY name
                    """
                    ,
                    ("AcmeOrg/sample-child-theme-oct-2024",),
                ).fetchall()
                self.assertEqual(len(branch_rows), 2)
                self.assertEqual(branch_rows[0]["name"], "development")
                self.assertEqual(branch_rows[0]["is_default"], 1)
                self.assertEqual(branch_rows[0]["is_protected"], 1)
                self.assertEqual(branch_rows[1]["name"], "main")

                item_rows = conn.execute("SELECT item_type, number, review_decision, check_status FROM github_items ORDER BY item_type, number").fetchall()
                self.assertEqual(len(item_rows), 2)
                self.assertEqual(item_rows[1]["item_type"], "pull_request")
                self.assertEqual(item_rows[1]["review_decision"], "APPROVED")
                self.assertEqual(item_rows[1]["check_status"], "success")

                link_rows = conn.execute(
                    """
                    SELECT source_type, source_number, target_type, target_number, link_kind
                    FROM github_links
                    ORDER BY source_number
                    """
                ).fetchall()
                self.assertEqual(len(link_rows), 1)
                self.assertEqual(link_rows[0]["source_number"], 202)
                self.assertEqual(link_rows[0]["target_number"], 101)
                self.assertEqual(link_rows[0]["link_kind"], "closes")

                doc_count = conn.execute("SELECT COUNT(*) FROM github_documents").fetchone()[0]
                self.assertGreaterEqual(doc_count, 6)
            with db_connection(db_path, ensure_semantic_schema) as conn:
                semantic_doc_count = conn.execute(
                    "SELECT COUNT(*) FROM semantic_documents WHERE source_type = 'github'"
                ).fetchone()[0]
                self.assertGreaterEqual(semantic_doc_count, 6)

    def test_sync_does_not_hold_write_lock_across_network_fetch(self) -> None:
        """GH-171 regression: sync_github_repo must not hold the SQLite write
        transaction open while blocked on a "network" call. A second writer
        (simulated with a raw connection here) must be able to land a write
        while sync_github_repo is mid-fetch, and it must do so quickly rather
        than waiting out the slow call's own duration.
        """
        block_started = threading.Event()
        slow_seconds = 0.6

        def _slow_api(url: str) -> object:
            if "/commits/deadbeef/check-runs" in url:
                block_started.set()
                # Simulate a slow GitHub API round-trip. If this call happens
                # inside an open write transaction (the pre-GH-171 bug), any
                # concurrent writer below is starved for this whole sleep.
                time.sleep(slow_seconds)
            return _fake_github_api(url)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            errors: list[BaseException] = []

            def _run_sync() -> None:
                try:
                    sync_github_repo(
                        database_path=db_path,
                        repo_full_name="AcmeOrg/sample-child-theme-oct-2024",
                        token="ghp_test",
                        since_days=30,
                        api_get_json=_slow_api,
                    )
                except BaseException as exc:  # noqa: BLE001 - surfaced via assertion below
                    errors.append(exc)

            sync_thread = threading.Thread(target=_run_sync)
            sync_thread.start()
            try:
                self.assertTrue(
                    block_started.wait(timeout=5),
                    "sync_github_repo never reached the simulated slow fetch",
                )

                # While the fetch is "in flight", a second connection should be
                # able to open and write immediately -- no write transaction
                # should be held across network I/O.
                start = time.monotonic()
                probe_conn = sqlite3.connect(str(db_path), timeout=2.0)
                try:
                    probe_conn.execute("CREATE TABLE IF NOT EXISTS gh171_probe (id INTEGER)")
                    probe_conn.execute("INSERT INTO gh171_probe (id) VALUES (1)")
                    probe_conn.commit()
                finally:
                    probe_conn.close()
                elapsed = time.monotonic() - start
            finally:
                sync_thread.join(timeout=10)

            self.assertFalse(sync_thread.is_alive(), "sync_github_repo did not finish in time")
            self.assertFalse(errors, f"sync_github_repo raised: {errors}")

            # Bounded window well under the slow call's own duration: proves
            # the concurrent write did not wait behind a held write lock.
            self.assertLess(
                elapsed,
                slow_seconds / 2,
                "concurrent write was blocked for close to the slow fetch's duration "
                "-- a write transaction is likely still spanning network I/O",
            )

    def test_sync_rejects_ignored_repo(self) -> None:
        add_github_ignored_repo("dlt-hub/dlt")
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with self.assertRaisesRegex(ValueError, "GitHub repo is ignored"):
                sync_github_repo(
                    database_path=db_path,
                    repo_full_name="DLT-HUB/dlt",
                    token="ghp_test",
                    since_days=30,
                    api_get_json=_fake_github_api,
                )

    def test_purge_removes_repo_github_and_semantic_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                ensure_github_schema(conn)
                ensure_semantic_schema(conn)
                conn.execute(
                    """
                    INSERT INTO github_documents
                        (repo_full_name, source_type, source_number, doc_type, source_key,
                         title, body, content_hash, embedded_hash, updated_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "dlt-hub/dlt",
                        "issue",
                        101,
                        "item_body",
                        "dlt-hub/dlt:issue:101:item",
                        "Title",
                        "Body",
                        "hash",
                        None,
                        "2026-04-28T00:00:00Z",
                        "2026-04-28T00:00:00Z",
                    ),
                )
                doc_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                conn.execute(
                    """
                    INSERT INTO semantic_documents
                        (source_type, source_table, source_pk, doc_kind, title, body, content_hash,
                         embedded_hash, embedded_model_version, embedded_at, metadata_json,
                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "github",
                        "github_documents",
                        "dlt-hub/dlt:issue:101:item",
                        "item_body",
                        "Title",
                        "Body",
                        "hash",
                        "hash",
                        "Qwen/Qwen3-Embedding-0.6B|1024",
                        "2026-04-28T00:00:00Z",
                        "{}",
                        "2026-04-28T00:00:00Z",
                        "2026-04-28T00:00:00Z",
                    ),
                )
                semantic_doc_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                conn.execute(
                    "INSERT INTO github_embeddings (doc_id, embedding) VALUES (?, ?)",
                    (doc_id, _vec_to_bytes([0.0] * 1024)),
                )
                conn.execute(
                    "INSERT INTO semantic_embeddings (rowid, embedding) VALUES (?, ?)",
                    (semantic_doc_id, _vec_to_bytes([0.0] * 1024)),
                )
                conn.commit()

            result = purge_github_repo_data(db_path, "DLT-HUB/dlt")
            self.assertGreaterEqual(result.deleted_rows, 4)

            with db_connection(db_path, ensure_github_schema) as conn:
                github_docs = conn.execute("SELECT COUNT(*) FROM github_documents").fetchone()[0]
                semantic_docs = conn.execute("SELECT COUNT(*) FROM semantic_documents").fetchone()[0]
                semantic_rows = conn.execute("SELECT COUNT(*) FROM semantic_embeddings_rowids").fetchone()[0]
            self.assertEqual(github_docs, 0)
            self.assertEqual(semantic_docs, 0)
            self.assertEqual(semantic_rows, 0)

    def test_embed_and_query_local_github_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            sync_github_repo(
                database_path=db_path,
                repo_full_name="AcmeOrg/sample-child-theme-oct-2024",
                token="ghp_test",
                since_days=30,
                api_get_json=_fake_github_api,
            )

            embed_result = embed_github_documents(
                database_path=db_path,
                model_name="fake-model",
                batch_size=4,
                embed_texts=_fake_embed_texts,
            )
            self.assertGreater(embed_result.embedded_docs, 0)

            from rebalance.ingest.semantic_index import query as semantic_query
            results = semantic_query(
                database_path=db_path,
                query_text="Which PR handles nonce security for checkout?",
                repo="AcmeOrg/sample-child-theme-oct-2024",
                top_k=3,
                model_name="fake-model",
                embed_texts=_fake_embed_texts,
                source_filter=["github"]
            )
            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(results[0]["metadata"]["repo_full_name"], "AcmeOrg/sample-child-theme-oct-2024")
            self.assertIn(results[0]["metadata"]["source_number"], {101, 202})
            self.assertIsNotNone(results[0].get("similarity_score") or results[0].get("doc_id"))


if __name__ == "__main__":
    unittest.main()
