"""Tests for Phase 1 hybrid retrieval: FTS5 lexical index + RRF fusion."""

import sqlite3
import unittest

from rebalance.ingest.db import semantic as sem
from rebalance.ingest.db.schema import ensure_semantic_schema
from rebalance.ingest.db.semantic import _fts_match_query
from rebalance.ingest.semantic_index import _rrf_fuse


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    ensure_semantic_schema(c)
    return c


def _add(c, i, source_type, title, body, pk="p"):
    c.execute(
        "INSERT INTO semantic_documents(id,source_type,source_table,source_pk,doc_kind,"
        "title,body,content_hash,metadata_json,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (i, source_type, source_type, f"{pk}{i}", "doc", title, body, "h", "{}",
         "2026-06-06", "2026-06-06"),
    )
    c.commit()


class FtsMatchQueryTests(unittest.TestCase):
    def test_tokenizes_and_quotes(self) -> None:
        # underscores split (FTS5 unicode61), de-duped, lowercased
        self.assertEqual(_fts_match_query("pulse_web.py generates"), '"pulse" OR "web" OR "py" OR "generates"')

    def test_drops_single_chars_and_empty(self) -> None:
        self.assertEqual(_fts_match_query("a b cc"), '"cc"')
        self.assertEqual(_fts_match_query("   "), "")
        self.assertEqual(_fts_match_query("!!! ??"), "")


class FtsSearchTests(unittest.TestCase):
    def test_finds_by_lexical_token_and_respects_source(self) -> None:
        c = _conn()
        _add(c, 1, "vault", "auth notes", "the auth_log module logs auth failures")
        _add(c, 2, "github", "refactor", "general logging cleanup")
        hits = sem.search_semantic_documents_fts(c, "which module logs auth failures", 5, ["vault", "github"])
        self.assertEqual([r["doc_id"] for r in hits][:1], [1])
        # source filter excludes vault
        only_gh = sem.search_semantic_documents_fts(c, "auth failures", 5, ["github"])
        self.assertTrue(all(r["source_type"] == "github" for r in only_gh))

    def test_triggers_keep_fts_in_sync(self) -> None:
        c = _conn()
        _add(c, 1, "vault", "t", "alpha auth_log beta")
        self.assertEqual(len(sem.search_semantic_documents_fts(c, "auth_log", 5, ["vault"])), 1)
        c.execute("DELETE FROM semantic_documents WHERE id=1")
        c.commit()
        self.assertEqual(sem.search_semantic_documents_fts(c, "auth_log", 5, ["vault"]), [])
        # update re-indexes
        _add(c, 2, "vault", "t2", "nothing relevant")
        c.execute("UPDATE semantic_documents SET body='now mentions widget' WHERE id=2")
        c.commit()
        self.assertEqual(len(sem.search_semantic_documents_fts(c, "widget", 5, ["vault"])), 1)

    def test_backfill_rebuilds_for_preexisting_docs(self) -> None:
        # Simulate a DB that had docs before the FTS table existed: insert with
        # the FTS triggers dropped, then re-run ensure_semantic_schema → rebuild.
        c = _conn()
        c.execute("DROP TABLE semantic_documents_fts")
        for trig in ("ai", "ad", "au"):
            c.execute(f"DROP TRIGGER IF EXISTS semantic_documents_fts_{trig}")
        _add(c, 1, "vault", "t", "preexisting auth_log content")
        ensure_semantic_schema(c)  # should create FTS + backfill
        self.assertEqual(len(sem.search_semantic_documents_fts(c, "auth_log", 5, ["vault"])), 1)

    def test_empty_query_returns_empty(self) -> None:
        c = _conn()
        _add(c, 1, "vault", "t", "body")
        self.assertEqual(sem.search_semantic_documents_fts(c, "!! ??", 5, ["vault"]), [])


class RrfFuseTests(unittest.TestCase):
    def test_shared_doc_ranks_top_and_prefers_vector_row(self) -> None:
        vec = [{"doc_id": 1, "distance": 0.1}, {"doc_id": 2, "distance": 0.2}]
        fts = [{"doc_id": 2, "distance": None}, {"doc_id": 3, "distance": None}]
        fused = _rrf_fuse([vec, fts], top_k=10)
        ids = [r["doc_id"] for r in fused]
        self.assertEqual(ids[0], 2)              # in both lists → highest fused score
        self.assertEqual(set(ids), {1, 2, 3})    # deduped
        # doc 2 kept as the vector row (carries a distance for scoring)
        self.assertEqual(next(r for r in fused if r["doc_id"] == 2)["distance"], 0.2)

    def test_respects_top_k(self) -> None:
        vec = [{"doc_id": i, "distance": 0.1 * i} for i in range(20)]
        self.assertEqual(len(_rrf_fuse([vec, []], top_k=5)), 5)


if __name__ == "__main__":
    unittest.main()
