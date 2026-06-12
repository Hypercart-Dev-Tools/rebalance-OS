"""Tests for chat_with_data — Phase 0 citations-first retrieval."""

import unittest
from pathlib import Path

from rebalance.chat import _rrf_merge, chat_with_data


def _fake_rows(_db, _query, top_k, _sources=None):
    rows = [
        {"source_type": "github", "title": "PR #12", "doc_kind": "pr",
         "body_preview": "fix the thing", "source_pk": "owner/repo#12",
         "metadata": {"url": "https://github.com/o/r/pull/12"}, "similarity_score": 0.91},
        {"source_type": "vault", "title": "Note A", "doc_kind": "note",
         "body_preview": "some note body", "source_pk": "vault/a.md",
         "metadata": {"path": "a.md"}, "similarity_score": 0.42},
    ]
    return rows[:top_k]


class ChatWithDataTests(unittest.TestCase):
    DB = Path("/nonexistent.db")  # never touched — query fn is injected

    def test_empty_query_returns_empty(self) -> None:
        out = chat_with_data(self.DB, "   ", work_query_fn=_fake_rows)
        self.assertEqual(out["citations"], [])
        self.assertEqual(out["used_sources"], [])

    def test_citations_mapped_and_sorted_by_score(self) -> None:
        out = chat_with_data(self.DB, "where is X", top_k=8, work_query_fn=_fake_rows)
        self.assertEqual([c["source"] for c in out["citations"]], ["github", "vault"])
        top = out["citations"][0]
        self.assertEqual(top["title"], "PR #12")
        self.assertEqual(top["path"], "https://github.com/o/r/pull/12")  # url preferred
        self.assertEqual(top["score"], 0.91)
        self.assertIn("semantic_index", out["used_sources"])
        self.assertIsNone(out["answer"])  # synthesis off by default
        self.assertIsInstance(out["elapsed_ms"], int)

    def test_top_k_is_respected(self) -> None:
        out = chat_with_data(self.DB, "q", top_k=1, work_query_fn=_fake_rows)
        self.assertEqual(len(out["citations"]), 1)

    def test_invalid_scope_falls_back_to_all(self) -> None:
        out = chat_with_data(self.DB, "q", scope="bogus", work_query_fn=_fake_rows)
        self.assertEqual(out["scope"], "all")

    def test_preview_truncated(self) -> None:
        def big(_db, _q, k, _sources=None):
            return [{"source_type": "vault", "title": "t", "body_preview": "x" * 500,
                     "source_pk": "p", "metadata": {}, "similarity_score": 0.5}]
        out = chat_with_data(self.DB, "q", work_query_fn=big)
        self.assertLessEqual(len(out["citations"][0]["preview"]), 280)


class RrfMergeTests(unittest.TestCase):
    def test_fuses_shared_result_to_top_and_dedupes(self) -> None:
        a = [{"source": "code", "path": "x.py", "title": "x"},
             {"source": "code", "path": "y.py", "title": "y"}]
        b = [{"source": "code", "path": "y.py", "title": "y"},
             {"source": "work", "path": "z", "title": "z"}]
        out = _rrf_merge([a, b], top_k=10)
        # y.py appears in both lists → fused to the top; deduped to one entry.
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0]["path"], "y.py")

    def test_respects_top_k(self) -> None:
        a = [{"source": "code", "path": f"{i}.py", "title": str(i)} for i in range(20)]
        self.assertEqual(len(_rrf_merge([a], top_k=5)), 5)


if __name__ == "__main__":
    unittest.main()
