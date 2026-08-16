"""Direct unit tests for the db/github.py typed query helpers.

These pin the column layouts the helpers own — a drift in any upsert helper's
column list is caught here rather than only through the broader ingest suite.
"""

import struct
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import (
    db_connection,
    ensure_github_schema,
    ensure_semantic_schema,
)
from rebalance.ingest.db import github as gh

# 35-column github_items record, in schema order. Tests override what they need.
_ITEM_COLUMNS = [
    "repo_full_name", "item_type", "number", "node_id", "github_id", "title",
    "body", "state", "state_reason", "author_login", "assignees_json",
    "labels_json", "milestone_number", "milestone_title", "is_draft",
    "is_merged", "base_ref", "head_ref", "head_sha", "mergeable_state",
    "review_decision", "check_status", "requested_reviewers_json",
    "comments_count", "review_comments_count", "commits_count", "additions",
    "deletions", "changed_files", "html_url", "created_at", "updated_at",
    "closed_at", "merged_at", "fetched_at",
]


def _item_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {col: 0 for col in _ITEM_COLUMNS}
    record.update(
        repo_full_name="Org/repo",
        item_type="issue",
        number=1,
        node_id="",
        title="",
        body="",
        state="open",
        state_reason="",
        author_login="",
        assignees_json="[]",
        labels_json="[]",
        milestone_title="",
        base_ref="",
        head_ref="",
        head_sha="",
        mergeable_state="",
        review_decision="",
        check_status="",
        requested_reviewers_json="[]",
        html_url="",
        created_at="2026-05-20",
        updated_at="2026-05-20",
        closed_at=None,
        merged_at=None,
        fetched_at="2026-05-20",
    )
    record.update(overrides)
    return record


class GitHubHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "rebalance.db"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- activity queries ---------------------------------------------------

    def test_activity_query_helpers(self) -> None:
        with db_connection(self.db_path, ensure_github_schema) as conn:
            conn.executemany(
                "INSERT INTO github_activity "
                "(login, repo_full_name, scan_date, commits, prs_opened, prs_merged, "
                "issues_opened, issue_comments, reviews, last_active_at, scanned_at) "
                "VALUES (?, ?, date('now'), ?, 0, 0, 0, 0, 0, ?, date('now'))",
                [
                    ("me", "org/hot", 10, "2026-05-20T10:00:00Z"),
                    ("me", "org/warm", 3, "2026-05-19T10:00:00Z"),
                    ("me", "org/cold", 0, None),
                ],
            )
            conn.execute(
                "INSERT INTO github_repo_meta (repo_full_name, fetched_at) "
                "VALUES (?, date('now'))",
                ("org/hot",),
            )
            conn.commit()

            # Zero-score repo excluded; ranked by score desc.
            self.assertEqual(gh.top_active_repos(conn, 5), ["org/hot", "org/warm"])
            self.assertEqual(gh.top_active_repos(conn, 1), ["org/hot"])

            # last_active: all, subset, empty subset; null last_active omitted.
            self.assertEqual(
                gh.repo_last_active(conn),
                {"org/hot": "2026-05-20T10:00:00Z", "org/warm": "2026-05-19T10:00:00Z"},
            )
            self.assertEqual(
                gh.repo_last_active(conn, ["org/hot"]),
                {"org/hot": "2026-05-20T10:00:00Z"},
            )
            self.assertEqual(gh.repo_last_active(conn, []), {})

            self.assertEqual(gh.repo_meta_names(conn), {"org/hot"})

    def test_top_active_repos_honours_since_days_window(self) -> None:
        with db_connection(self.db_path, ensure_github_schema) as conn:
            conn.execute(
                "INSERT INTO github_activity "
                "(login, repo_full_name, scan_date, commits, prs_opened, prs_merged, "
                "issues_opened, issue_comments, reviews, last_active_at, scanned_at) "
                "VALUES ('me', 'org/old', date('now','-40 days'), 9, 0, 0, 0, 0, 0, "
                "NULL, date('now'))"
            )
            conn.commit()
            # Inside a 90-day window, outside the default 7-day window.
            self.assertEqual(gh.top_active_repos(conn, 5, since_days=90), ["org/old"])
            self.assertEqual(gh.top_active_repos(conn, 5), [])

    # -- artifact upserts ---------------------------------------------------

    def test_artifact_upserts_round_trip(self) -> None:
        with db_connection(self.db_path, ensure_github_schema) as conn:
            R = "Org/repo"
            gh.upsert_repo_meta(conn, (R, "main", "p", "u", 4, 1, 0, "f"))
            gh.upsert_branch(conn, (R, "main", "sha", 1, 1, "f"))
            gh.upsert_label(conn, (R, "bug", "f00", "desc", 1))
            gh.upsert_milestone(
                conn, (R, 2, "M2", "d", "open", 3, 1, None, None, None, None, "url")
            )
            gh.upsert_release(
                conn, (R, 7, "v2", "v2", "main", 0, 1, "notes", None, None, "url")
            )
            gh.upsert_comment(
                conn,
                (R, "issue", 1, "issue_comment", 50, "me", "OWNER", "hi", "", None,
                 "url", None, None, "f"),
            )
            gh.upsert_link(conn, (R, "pull_request", 9, "issue", 8, "closes"))
            gh.upsert_commit(
                conn, (R, "pull_request", 9, "sha9", "me", "msg", "c", "url", "f")
            )
            gh.upsert_check_run(
                conn,
                (R, "pull_request", 9, "sha9", "ci", "completed", "success", "url",
                 None, None, "f"),
            )
            conn.commit()

            self.assertEqual(
                conn.execute(
                    "SELECT default_branch, open_issues_count FROM github_repo_meta"
                ).fetchone()["default_branch"],
                "main",
            )
            self.assertEqual(
                conn.execute("SELECT name FROM github_branches").fetchone()["name"],
                "main",
            )
            self.assertEqual(
                conn.execute("SELECT color FROM github_labels").fetchone()["color"],
                "f00",
            )
            self.assertEqual(
                conn.execute("SELECT title FROM github_milestones").fetchone()["title"],
                "M2",
            )
            self.assertEqual(
                conn.execute("SELECT tag_name FROM github_releases").fetchone()["tag_name"],
                "v2",
            )
            self.assertEqual(
                conn.execute("SELECT body FROM github_comments").fetchone()["body"],
                "hi",
            )
            self.assertEqual(
                conn.execute("SELECT link_kind FROM github_links").fetchone()["link_kind"],
                "closes",
            )
            self.assertEqual(
                conn.execute("SELECT sha FROM github_commits").fetchone()["sha"],
                "sha9",
            )
            self.assertEqual(
                conn.execute(
                    "SELECT conclusion FROM github_check_runs"
                ).fetchone()["conclusion"],
                "success",
            )

    def test_upsert_item_binds_by_name(self) -> None:
        with db_connection(self.db_path, ensure_github_schema) as conn:
            record = _item_record(
                item_type="pull_request",
                number=42,
                title="A PR",
                state="open",
                review_decision="APPROVED",
                check_status="success",
                is_merged=1,
            )
            gh.upsert_item(conn, record)
            conn.commit()
            row = conn.execute(
                "SELECT item_type, number, title, review_decision, check_status, "
                "is_merged FROM github_items"
            ).fetchone()
            self.assertEqual(row["item_type"], "pull_request")
            self.assertEqual(row["number"], 42)
            self.assertEqual(row["title"], "A PR")
            self.assertEqual(row["review_decision"], "APPROVED")
            self.assertEqual(row["check_status"], "success")
            self.assertEqual(row["is_merged"], 1)

    def test_upsert_item_replaces_on_conflict(self) -> None:
        with db_connection(self.db_path, ensure_github_schema) as conn:
            gh.upsert_item(conn, _item_record(number=5, title="first"))
            gh.upsert_item(conn, _item_record(number=5, title="second"))
            conn.commit()
            rows = conn.execute(
                "SELECT title FROM github_items WHERE number = 5"
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "second")

    # -- documents ----------------------------------------------------------

    def test_insert_document_and_delete_item_children(self) -> None:
        with db_connection(self.db_path, ensure_github_schema) as conn:
            R = "Org/repo"
            gh.upsert_item(conn, _item_record(item_type="pull_request", number=3))
            doc_id = gh.insert_github_document(
                conn,
                repo_full_name=R,
                source_type="pull_request",
                source_number=3,
                doc_type="item_body",
                source_key=f"{R}:pr:3:item",
                title="t",
                body="b" * 60,
                content_hash="h",
                updated_at="2026-05-20",
                fetched_at="2026-05-20",
            )
            self.assertIsInstance(doc_id, int)
            gh.upsert_commit(
                conn,
                (R, "pull_request", 3, "sha", "me", "m", "c", "url", "f"),
            )
            conn.commit()

            gh.delete_item_children(conn, R, "pull_request", 3)
            conn.commit()
            # Children gone; the item row itself is left intact.
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM github_documents").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM github_commits").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM github_items").fetchone()[0], 1
            )

    # -- embeddings ---------------------------------------------------------

    def test_embedding_helpers(self) -> None:
        with db_connection(self.db_path, ensure_github_schema) as conn:
            R = "Org/repo"
            doc_id = gh.insert_github_document(
                conn, repo_full_name=R, source_type="issue", source_number=1,
                doc_type="item_body", source_key=f"{R}:i:1", title="t",
                body="x" * 60, content_hash="hash-1", updated_at="2026-05-20",
                fetched_at="2026-05-20",
            )
            gh.insert_github_document(
                conn, repo_full_name=R, source_type="issue", source_number=2,
                doc_type="item_body", source_key=f"{R}:i:2", title="t",
                body="tiny", content_hash="hash-2", updated_at="2026-05-20",
                fetched_at="2026-05-20",
            )
            conn.commit()

            # Both docs exist; only one clears the 40-char embed threshold.
            self.assertEqual(gh.count_embeddable_github_documents(conn, 40), 1)
            pending = gh.github_documents_pending_embed(conn, 40)
            self.assertEqual([r["id"] for r in pending], [doc_id])

            gh.upsert_github_embedding(conn, doc_id, struct.pack("1024f", *([0.0] * 1024)))
            gh.mark_github_document_embedded(conn, doc_id)
            gh.set_github_embedding_meta(conn, "model_name", "test-model")
            conn.commit()

            # Marked fresh -> no longer pending.
            self.assertEqual(gh.github_documents_pending_embed(conn, 40), [])
            self.assertEqual(
                conn.execute(
                    "SELECT value FROM github_embedding_meta WHERE key='model_name'"
                ).fetchone()["value"],
                "test-model",
            )

            # force-reembed primitives.
            gh.clear_github_embeddings(conn)
            gh.reset_github_embedded_hashes(conn)
            conn.commit()
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM github_embeddings").fetchone()[0], 0
            )
            self.assertEqual(len(gh.github_documents_pending_embed(conn, 40)), 1)

    def test_search_github_documents(self) -> None:
        vec = struct.pack("1024f", *([0.1] * 1024))
        with db_connection(self.db_path, ensure_github_schema) as conn:
            R = "Org/repo"
            doc_id = gh.insert_github_document(
                conn, repo_full_name=R, source_type="issue", source_number=1,
                doc_type="item_body", source_key=f"{R}:i:1", title="T",
                body="b" * 60, content_hash="h", updated_at="2026-05-20",
                fetched_at="2026-05-20",
            )
            gh.upsert_github_embedding(conn, doc_id, vec)
            conn.commit()
            self.assertEqual(len(gh.search_github_documents(conn, vec, 8)), 1)
            self.assertEqual(
                len(gh.search_github_documents(conn, vec, 8, repo_full_name=R)), 1
            )
            self.assertEqual(
                gh.search_github_documents(conn, vec, 8, repo_full_name="Org/other"),
                [],
            )

    # -- per-repo purge -----------------------------------------------------

    def test_purge_helpers(self) -> None:
        with db_connection(self.db_path, ensure_github_schema) as conn:
            ensure_semantic_schema(conn)
            R = "Org/Repo"
            gh.upsert_item(conn, _item_record(repo_full_name=R, number=1))
            doc_id = gh.insert_github_document(
                conn, repo_full_name=R, source_type="issue", source_number=1,
                doc_type="item_body", source_key=f"{R}:i:1", title="t",
                body="x" * 60, content_hash="h", updated_at="2026-05-20",
                fetched_at="2026-05-20",
            )
            gh.upsert_github_embedding(conn, doc_id, struct.pack("1024f", *([0.0] * 1024)))
            conn.commit()

            # Case-insensitive repo match.
            self.assertEqual(gh.count_repo_rows(conn, "github_items", "org/repo"), 1)
            ids = gh.github_document_ids(conn, "org/repo")
            self.assertEqual(ids, [doc_id])
            self.assertEqual(
                gh.count_ids_in(conn, "github_embeddings", "doc_id", ids), 1
            )
            self.assertEqual(
                gh.count_ids_in(conn, "github_embeddings", "doc_id", []), 0
            )

            gh.delete_github_embeddings_for_docs(conn, ids)
            gh.delete_repo_rows(conn, "github_items", "org/repo")
            gh.delete_repo_table(conn, "github_documents", R)
            conn.commit()
            self.assertEqual(gh.count_repo_rows(conn, "github_items", "org/repo"), 0)
            self.assertEqual(gh.github_document_ids(conn, "org/repo"), [])
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM github_embeddings").fetchone()[0], 0
            )


if __name__ == "__main__":
    unittest.main()
