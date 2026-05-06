"""Tests for refresh orchestration options."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.index_ops import _refresh_github


class IndexOpsTests(unittest.TestCase):
    def test_github_dry_run_can_skip_semantic_embedding(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _refresh_github(
                Path(tmpdir) / "rebalance.db",
                token="test-token",
                since_days=30,
                repos=["example/repo"],
                dry_run=True,
                include_semantic=False,
            )

        self.assertIn("skip semantic embedding", result["steps"])
        self.assertNotIn("semantic_embed(source=['github'])", result["steps"])

    def test_github_dry_run_keeps_semantic_embedding_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _refresh_github(
                Path(tmpdir) / "rebalance.db",
                token="test-token",
                since_days=30,
                repos=["example/repo"],
                dry_run=True,
            )

        self.assertIn("semantic_embed(source=['github'])", result["steps"])


if __name__ == "__main__":
    unittest.main()
