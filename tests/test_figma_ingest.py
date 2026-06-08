"""Tests for Figma comment ingestion."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from rebalance.ingest.db import db_connection, run_migrations
from rebalance.ingest.figma import sync_figma_comments
from rebalance.ingest.semantic_index import backfill_semantic_documents


class _FakeFigmaClient:
    def __init__(self, comments_by_file: dict[str, list[dict[str, Any]]]) -> None:
        self.comments_by_file = comments_by_file
        self.calls: list[tuple[str, bool]] = []

    def get_comments(self, file_key: str, *, as_md: bool = True) -> list[dict[str, Any]]:
        self.calls.append((file_key, as_md))
        return self.comments_by_file[file_key]


def _comment(comment_id: str, *, message: str = "Looks good") -> dict[str, Any]:
    return {
        "id": comment_id,
        "message": message,
        "created_at": "2026-06-01T12:00:00Z",
        "resolved_at": None,
        "user": {"id": "u1", "handle": "Designer"},
        "client_meta": {"node_id": "1:2"},
        "reactions": [],
        "order_id": 1,
    }


class FigmaIngestTests(unittest.TestCase):
    def test_sync_figma_comments_inserts_and_deduplicates_file_keys(self) -> None:
        client = _FakeFigmaClient({"fileA": [_comment("c1"), _comment("c2")]})
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            result = sync_figma_comments(
                db_path,
                file_keys=["fileA", "fileA", ""],
                token="test-token",
                client=client,
            )

            self.assertEqual(result.files_requested, 1)
            self.assertEqual(result.files_synced, 1)
            self.assertEqual(result.comments_inserted, 2)
            self.assertEqual(result.comments_updated, 0)
            self.assertEqual(client.calls, [("fileA", True)])

            with db_connection(db_path) as conn:
                rows = conn.execute(
                    "SELECT comment_key, message, user_handle FROM figma_comments ORDER BY comment_key"
                ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["comment_key"], "fileA:c1")
            self.assertEqual(rows[0]["user_handle"], "Designer")

    def test_repeat_sync_updates_changed_comment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            first = _FakeFigmaClient({"fileA": [_comment("c1", message="Old")]})
            second = _FakeFigmaClient({"fileA": [_comment("c1", message="New")]})

            r1 = sync_figma_comments(db_path, file_keys=["fileA"], token="t", client=first)
            r2 = sync_figma_comments(db_path, file_keys=["fileA"], token="t", client=second)

            self.assertEqual(r1.comments_inserted, 1)
            self.assertEqual(r2.comments_inserted, 0)
            self.assertEqual(r2.comments_updated, 1)

            with db_connection(db_path) as conn:
                row = conn.execute(
                    "SELECT message FROM figma_comments WHERE comment_key = 'fileA:c1'"
                ).fetchone()
            self.assertEqual(row["message"], "New")

    def test_figma_comments_backfill_to_semantic_documents(self) -> None:
        client = _FakeFigmaClient({"fileA": [_comment("c1", message="Update CTA copy")]})
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            sync_figma_comments(db_path, file_keys=["fileA"], token="t", client=client)
            # figma rides the registry-driven provider path, so it must be
            # explicitly enabled (the strangler flag).
            result = backfill_semantic_documents(
                db_path, source_types=["figma"], use_registry_providers=True
            )

            self.assertEqual(result.inserted_count, 1)
            with db_connection(db_path) as conn:
                row = conn.execute(
                    """
                    SELECT source_type, source_table, source_pk, body, metadata_json
                    FROM semantic_documents
                    WHERE source_type = 'figma'
                    """
                ).fetchone()
            self.assertEqual(row["source_table"], "figma_comments")
            self.assertEqual(row["source_pk"], "fileA:c1")
            self.assertEqual(row["body"], "Update CTA copy")
            self.assertEqual(json.loads(row["metadata_json"])["file_key"], "fileA")

    def test_migration_creates_figma_comments_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                version = run_migrations(conn)
                cols = {row[1] for row in conn.execute("PRAGMA table_info(figma_comments)")}
            self.assertGreaterEqual(version, 4)
            self.assertIn("comment_key", cols)
            self.assertIn("message", cols)


if __name__ == "__main__":
    unittest.main()
