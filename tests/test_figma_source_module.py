"""End-to-end test for the Figma SourceModule (registry-driven strangler path).

Everything is injected — a fake Figma client (no PAT/network) and a fake
embedder (no mlx). Asserts the full path: sync -> registry-provider backfill ->
embed -> query, including that an empty-message comment is skipped.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from rebalance.ingest.db import db_connection
from rebalance.ingest.figma import sync_figma_comments
from rebalance.ingest.semantic_index import (
    backfill_semantic_documents,
    embed_pending,
    query,
)


class _FakeFigmaClient:
    """Returns canned comments per file key — no network, no PAT used."""

    def __init__(self, comments_by_file: dict[str, list[dict[str, Any]]]) -> None:
        self.comments_by_file = comments_by_file

    def get_comments(self, file_key: str, *, as_md: bool = True) -> list[dict[str, Any]]:
        return self.comments_by_file[file_key]


def _fake_embed_texts(texts: list[str], _model_name: str) -> list[list[float]]:
    """Deterministic 1024-dim vectors keyed on a marker word — no mlx loads."""
    vectors: list[list[float]] = []
    for text in texts:
        lowered = text.lower()
        vec = [0.0] * 1024
        if "checkout" in lowered:
            vec[0] = 1.0
        else:
            vec[0] = 0.1
        vectors.append(vec)
    return vectors


def _comment(comment_id: str, *, message: str) -> dict[str, Any]:
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


class FigmaSourceModuleTests(unittest.TestCase):
    def test_backfill_embed_query_end_to_end(self) -> None:
        # One real comment + one empty-message comment (must be skipped).
        client = _FakeFigmaClient(
            {
                "fileA": [
                    _comment("c1", message="Fix the checkout button copy"),
                    _comment("c2", message="   "),
                ]
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"

            sync_result = sync_figma_comments(
                db_path, file_keys=["fileA"], token="injected", client=client
            )
            self.assertEqual(sync_result.comments_inserted, 2)

            # Registry-driven provider path (strangler flag). Empty body skipped.
            backfill = backfill_semantic_documents(
                db_path, source_types=["figma"], use_registry_providers=True
            )
            self.assertEqual(backfill.inserted_count, 1)

            with db_connection(db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT source_type, source_table, source_pk
                    FROM semantic_documents
                    WHERE source_type = 'figma'
                    """
                ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source_type"], "figma")
            self.assertEqual(rows[0]["source_table"], "figma_comments")
            self.assertEqual(rows[0]["source_pk"], "fileA:c1")

            embed = embed_pending(
                db_path, source_types=["figma"], embed_texts=_fake_embed_texts
            )
            self.assertEqual(embed.embedded_docs, 1)

            hits = query(
                db_path,
                "checkout button",
                source_filter=["figma"],
                embed_texts=_fake_embed_texts,
            )
            self.assertTrue(hits)
            self.assertEqual(hits[0]["source_type"], "figma")
            self.assertEqual(hits[0]["source_pk"], "fileA:c1")
            self.assertEqual(hits[0]["title"], "Figma comment by Designer")
            self.assertIn("checkout", hits[0]["body_preview"].lower())
            self.assertEqual(hits[0]["metadata"]["file_key"], "fileA")


if __name__ == "__main__":
    unittest.main()
