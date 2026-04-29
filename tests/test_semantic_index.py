"""Tests for the unified semantic index layer."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest import config as config_module
from rebalance.ingest.config import add_github_ignored_repo
from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_schema, ensure_semantic_schema
from rebalance.ingest.semantic_index import backfill_semantic_documents, embed_pending, query


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fake_embed_texts(texts: list[str], _model_name: str) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        lowered = text.lower()
        vec = [0.0] * 1024
        if "nonce" in lowered:
            vec[0] = 1.0
        elif "oauth" in lowered:
            vec[0] = 0.8
        elif "calendar" in lowered:
            vec[0] = 0.6
        else:
            vec[0] = 0.1
        vectors.append(vec)
    return vectors


class SemanticIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_backfill_embed_and_query_across_vault_and_github(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                ensure_schema(conn)
                ensure_github_schema(conn)

                conn.execute(
                    """
                    INSERT INTO vault_files
                        (rel_path, title, content_hash, frontmatter_json, tags_json,
                         ingested_at, file_size_bytes, last_modified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Projects/Auth.md",
                        "Auth Notes",
                        "file-hash",
                        "{}",
                        json.dumps(["security"]),
                        "2026-04-24T10:00:00+00:00",
                        128,
                        "2026-04-24T10:05:00+00:00",
                    ),
                )
                file_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                vault_body = "Nonce handling notes for the checkout flow."
                conn.execute(
                    """
                    INSERT INTO chunks
                        (file_id, chunk_index, heading, heading_level, body, char_count, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        0,
                        "Checkout",
                        2,
                        vault_body,
                        len(vault_body),
                        _hash_text(vault_body),
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO github_items
                        (repo_full_name, item_type, number, title, body, state, labels_json,
                         milestone_title, review_decision, check_status, html_url, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "example/repo",
                        "issue",
                        101,
                        "Add nonce validation",
                        "The API needs nonce checks.",
                        "open",
                        json.dumps(["security"]),
                        "Q2",
                        "",
                        "",
                        "https://github.example/issues/101",
                        "2026-04-24T10:10:00+00:00",
                    ),
                )
                github_body = "Issue #101 requires nonce validation on checkout AJAX."
                conn.execute(
                    """
                    INSERT INTO github_documents
                        (repo_full_name, source_type, source_number, doc_type, source_key,
                         title, body, content_hash, embedded_hash, updated_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "example/repo",
                        "issue",
                        101,
                        "item_body",
                        "example/repo:issue:101:item",
                        "Add nonce validation",
                        github_body,
                        _hash_text(github_body),
                        None,
                        "2026-04-24T10:12:00+00:00",
                        "2026-04-24T10:12:00+00:00",
                    ),
                )
                conn.commit()

            backfill_result = backfill_semantic_documents(
                db_path,
                source_types=["vault", "github"],
            )
            self.assertEqual(backfill_result.inserted_count, 2)
            self.assertEqual(backfill_result.deleted_count, 0)

            embed_result = embed_pending(
                db_path,
                source_types=["vault", "github"],
                embed_texts=_fake_embed_texts,
            )
            self.assertEqual(embed_result.embedded_docs, 2)

            vault_results = query(
                db_path,
                "nonce checkout",
                source_filter=["vault"],
                embed_texts=_fake_embed_texts,
            )
            github_results = query(
                db_path,
                "nonce checkout",
                source_filter=["github"],
                embed_texts=_fake_embed_texts,
            )

            self.assertEqual(vault_results[0]["source_type"], "vault")
            self.assertEqual(vault_results[0]["metadata"]["file_path"], "Projects/Auth.md")
            self.assertEqual(github_results[0]["source_type"], "github")
            self.assertEqual(github_results[0]["metadata"]["repo_full_name"], "example/repo")
            self.assertEqual(github_results[0]["doc_kind"], "item_body")

    def test_embed_pending_only_reembeds_changed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                ensure_schema(conn)
                ensure_semantic_schema(conn)
                conn.execute(
                    """
                    INSERT INTO vault_files
                        (rel_path, title, content_hash, frontmatter_json, tags_json,
                         ingested_at, file_size_bytes, last_modified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Projects/Index.md",
                        "Index",
                        "file-hash",
                        "{}",
                        "[]",
                        "2026-04-24T09:00:00+00:00",
                        64,
                        "2026-04-24T09:00:00+00:00",
                    ),
                )
                file_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                body_one = "OAuth rollout checklist"
                body_two = "Calendar cleanup notes"
                conn.execute(
                    """
                    INSERT INTO chunks
                        (file_id, chunk_index, heading, heading_level, body, char_count, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?), (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        0,
                        "OAuth",
                        2,
                        body_one,
                        len(body_one),
                        _hash_text(body_one),
                        file_id,
                        1,
                        "Calendar",
                        2,
                        body_two,
                        len(body_two),
                        _hash_text(body_two),
                    ),
                )
                conn.commit()

            backfill_semantic_documents(db_path, source_types=["vault"])
            first_embed = embed_pending(
                db_path,
                source_types=["vault"],
                embed_texts=_fake_embed_texts,
            )
            self.assertEqual(first_embed.embedded_docs, 2)

            second_embed = embed_pending(
                db_path,
                source_types=["vault"],
                embed_texts=_fake_embed_texts,
            )
            self.assertEqual(second_embed.embedded_docs, 0)
            self.assertEqual(second_embed.skipped_unchanged, 2)

            with db_connection(db_path, ensure_schema) as conn:
                new_body = "OAuth rollout checklist with nonce validation"
                conn.execute(
                    """
                    UPDATE chunks
                    SET body = ?, char_count = ?, content_hash = ?
                    WHERE chunk_index = 0
                    """,
                    (new_body, len(new_body), _hash_text(new_body)),
                )
                conn.execute(
                    """
                    UPDATE vault_files
                    SET last_modified = ?
                    WHERE id = ?
                    """,
                    ("2026-04-24T11:00:00+00:00", file_id),
                )
                conn.commit()

            backfill_semantic_documents(db_path, source_types=["vault"])
            third_embed = embed_pending(
                db_path,
                source_types=["vault"],
                embed_texts=_fake_embed_texts,
            )
            self.assertEqual(third_embed.embedded_docs, 1)

    def test_github_backfill_skips_ignored_repos(self) -> None:
        add_github_ignored_repo("dlt-hub/dlt")
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                ensure_github_schema(conn)
                conn.execute(
                    """
                    INSERT INTO github_items
                        (repo_full_name, item_type, number, title, body, state, labels_json,
                         milestone_title, review_decision, check_status, html_url, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "dlt-hub/dlt",
                        "issue",
                        1,
                        "Ignored",
                        "Ignored body",
                        "open",
                        "[]",
                        "",
                        "",
                        "",
                        "https://github.example/issues/1",
                        "2026-04-28T00:00:00Z",
                    ),
                )
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
                        1,
                        "item_body",
                        "dlt-hub/dlt:issue:1:item",
                        "Ignored",
                        "Ignored body",
                        _hash_text("Ignored body"),
                        None,
                        "2026-04-28T00:00:00Z",
                        "2026-04-28T00:00:00Z",
                    ),
                )
                conn.commit()

            result = backfill_semantic_documents(db_path, source_types=["github"])
            self.assertEqual(result.total_documents, 0)

            with db_connection(db_path, ensure_semantic_schema) as conn:
                doc_count = conn.execute("SELECT COUNT(*) FROM semantic_documents").fetchone()[0]
            self.assertEqual(doc_count, 0)


if __name__ == "__main__":
    unittest.main()
