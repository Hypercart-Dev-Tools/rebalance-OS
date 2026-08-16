"""Tests for the Phase 2 native code corpus: collector + sync_code_documents."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.code_collector import chunk_python_source, collect_code_chunks
from rebalance.ingest.db import semantic as sem
from rebalance.ingest.db.schema import ensure_semantic_schema
from rebalance.ingest.semantic_index import sync_code_documents

SAMPLE = '''"""Module that logs auth failures across collectors."""
import os
from pathlib import Path


def log_auth_failure(msg):
    return os.environ.get(msg)


class AuthLogger:
    def write(self):
        return None
'''


class ChunkTests(unittest.TestCase):
    def test_extracts_function_class_module(self) -> None:
        chunks = chunk_python_source("a/auth_log.py", SAMPLE, "2026-06-06T00:00:00+00:00")
        got = {(c.symbol, c.doc_kind) for c in chunks}
        self.assertIn(("log_auth_failure", "function"), got)
        self.assertIn(("AuthLogger", "class"), got)
        self.assertIn(("<module>", "module"), got)
        module = next(c for c in chunks if c.doc_kind == "module")
        self.assertIn("logs auth failures", module.body)
        self.assertIn("import os", module.body)

    def test_syntax_error_yields_nothing(self) -> None:
        self.assertEqual(chunk_python_source("x.py", "def (:", "t"), [])


class CollectTests(unittest.TestCase):
    def test_walks_include_dirs_and_skips_venv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "pkg").mkdir(parents=True)
            (root / "src" / "pkg" / "mod.py").write_text("def f():\n    return 1\n")
            (root / ".venv").mkdir()
            (root / ".venv" / "junk.py").write_text("def g():\n    return 2\n")
            chunks = collect_code_chunks(root, include_dirs=("src",))
            paths = {c.path for c in chunks}
            self.assertIn("src/pkg/mod.py", paths)
            self.assertFalse(any(".venv" in p for p in paths))


class SyncCodeTests(unittest.TestCase):
    def _repo(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "src" / "auth_log.py").write_text(SAMPLE)
        return root

    def test_sync_upserts_and_fts_finds_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            c = sqlite3.connect(":memory:")
            c.row_factory = sqlite3.Row
            ensure_semantic_schema(c)
            res = sync_code_documents(c, root)
            self.assertGreaterEqual(res["inserted"], 3)  # fn + class + module
            self.assertEqual(res["updated"], 0)
            # FTS surfaces the code by identifier and by filename
            hits = sem.search_semantic_documents_fts(c, "log_auth_failure", 5, ["code"])
            self.assertTrue(any("auth_log.py" in (r["title"] or "") for r in hits))

    def test_rerun_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            c = sqlite3.connect(":memory:")
            c.row_factory = sqlite3.Row
            ensure_semantic_schema(c)
            sync_code_documents(c, root)
            res2 = sync_code_documents(c, root)
            self.assertEqual(res2["inserted"], 0)
            self.assertEqual(res2["updated"], 0)
            self.assertEqual(res2["deleted"], 0)

    def test_deleted_symbol_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            c = sqlite3.connect(":memory:")
            c.row_factory = sqlite3.Row
            ensure_semantic_schema(c)
            sync_code_documents(c, root)
            (root / "src" / "auth_log.py").write_text('def kept():\n    return 1\n')
            res = sync_code_documents(c, root)
            self.assertGreaterEqual(res["deleted"], 1)  # log_auth_failure/AuthLogger gone
            remaining = {r["source_pk"] for r in sem.semantic_documents_for_source(c, "code")}
            self.assertNotIn("src/auth_log.py::log_auth_failure", remaining)
            self.assertNotIn("src/auth_log.py::AuthLogger", remaining)
            self.assertIn("src/auth_log.py::kept", remaining)


if __name__ == "__main__":
    unittest.main()
