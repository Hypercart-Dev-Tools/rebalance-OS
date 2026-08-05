"""Tests for vector database invariants (orphans and backlog)."""

import os
import sqlite3
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
from rebalance.ingest.db import semantic as sem
from rebalance.doctor import _check_orphaned_vectors, _check_embedding_backlog, _check_database_bloat, OK, WARN, FAIL


class VectorInvariantsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "rebalance.db"
        with db_connection(self.db_path, ensure_github_schema) as conn:
            ensure_semantic_schema(conn)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_fixture_passes_orphan_check(self):
        checks = _check_orphaned_vectors(self.db_path)
        self.assertEqual(len(checks), 2)
        for check in checks:
            self.assertEqual(check.status, OK)

    def test_hand_inserted_vector_fails_orphan_check(self):
        with db_connection(self.db_path) as conn:
            # 1. Insert an orphaned vector into github_embeddings
            gh.upsert_github_embedding(conn, 999, struct.pack("1024f", *([0.0]*1024)))
            conn.commit()
        
        checks = _check_orphaned_vectors(self.db_path)
        gh_check = next(c for c in checks if c.name == "orphaned vectors:github")
        self.assertEqual(gh_check.status, FAIL)
        self.assertIn("1 orphaned vectors", gh_check.detail)
        self.assertIn("4096 bytes", gh_check.detail)
        
    def test_deleted_document_fails_orphan_check(self):
        with db_connection(self.db_path) as conn:
            # Insert a doc and its vector
            doc_id = gh.insert_github_document(
                conn, repo_full_name="Org/repo", source_type="issue", source_number=1,
                doc_type="item_body", source_key="Org/repo:i:1", title="t",
                body="x", content_hash="hash", updated_at="2026-05-20",
                fetched_at="2026-05-20",
            )
            gh.upsert_github_embedding(conn, doc_id, struct.pack("1024f", *([0.0]*1024)))
            
            # Now delete the document
            conn.execute("DELETE FROM github_documents WHERE id = ?", (doc_id,))
            conn.commit()
            
        checks = _check_orphaned_vectors(self.db_path)
        gh_check = next(c for c in checks if c.name == "orphaned vectors:github")
        self.assertEqual(gh_check.status, FAIL)
        self.assertIn("1 orphaned vectors", gh_check.detail)
        self.assertIn("4096 bytes", gh_check.detail)

    def test_backlog_sawtooth_guard_does_not_fail(self):
        with db_connection(self.db_path) as conn:
            # Insert a long doc to trigger the backlog
            gh.insert_github_document(
                conn, repo_full_name="Org/repo", source_type="issue", source_number=1,
                doc_type="item_body", source_key="Org/repo:i:1", title="t",
                body="x" * 60, content_hash="hash", updated_at="2026-05-20",
                fetched_at="2026-05-20",
            )
            conn.commit()
            # Freshly synced but unembedded
            
        check = _check_embedding_backlog(self.db_path)
        # Should be INFO/NOTICE (which is OK status), not WARN/FAIL
        self.assertEqual(check.status, OK)
        self.assertIn("1 unembedded documents pending", check.detail)

    def test_semantic_orphan_check(self):
        with db_connection(self.db_path) as conn:
            # Insert a doc and its vector
            doc_id = sem.insert_semantic_document(
                conn, source_type="vault", source_table="chunks", source_pk="c1",
                doc_kind="chunk", title="t", body="x", content_hash="hash",
                metadata_json="{}", created_at="2026-05-20", updated_at="2026-05-20"
            )
            sem.insert_semantic_embedding(conn, doc_id, struct.pack("1024f", *([0.0]*1024)))
            # Delete the doc
            conn.execute("DELETE FROM semantic_documents WHERE id = ?", (doc_id,))
            conn.commit()
            
        checks = _check_orphaned_vectors(self.db_path)
        sem_check = next(c for c in checks if c.name == "orphaned vectors:semantic")
        self.assertEqual(sem_check.status, FAIL)
        self.assertIn("1 orphaned vectors", sem_check.detail)
        self.assertIn("4096 bytes", sem_check.detail)

    def test_semantic_hand_inserted_fails_orphan_check(self):
        with db_connection(self.db_path) as conn:
            sem.insert_semantic_embedding(conn, 999, struct.pack("1024f", *([0.0]*1024)))
            conn.commit()
            
        checks = _check_orphaned_vectors(self.db_path)
        sem_check = next(c for c in checks if c.name == "orphaned vectors:semantic")
        self.assertEqual(sem_check.status, FAIL)
        self.assertIn("1 orphaned vectors", sem_check.detail)
        self.assertIn("4096 bytes", sem_check.detail)

    def test_database_bloat_reports_nonzero_size(self):
        with db_connection(self.db_path) as conn:
            gh.upsert_github_embedding(conn, 999, struct.pack("1024f", *([0.0]*1024)))
            conn.commit()
            size = gh.table_byte_size(conn, "github_embeddings")
            self.assertGreater(size, 0)
            
        check = _check_database_bloat(self.db_path)
        self.assertEqual(check.status, OK)
        self.assertNotIn("github_embeddings 0.0 MB (0.0% share)", check.detail)

    def test_readonly_connection(self):
        # Assert the checks perform no writes and succeed on a read-only connection
        os.chmod(self.db_path, 0o444)
        
        # The doctor queries shouldn't raise any sqlite readonly errors
        checks = _check_orphaned_vectors(self.db_path)
        for check in checks:
            self.assertEqual(check.status, OK)
            
        check = _check_embedding_backlog(self.db_path)
        self.assertEqual(check.status, OK)

if __name__ == "__main__":
    unittest.main()
