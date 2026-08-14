"""Call sites that consume `semantic_index.query()` must read its actual shape.

GH-266 Phase 3 repointed `rebalance query`, `rebalance github-query`, and
`querier.ask()` at the unified `semantic_index.query()`. That function returns
per-source fields nested under `metadata` -- not flat, the way the deleted
`embedder.query_similar` / `github_knowledge.query_github_documents` did. Every
one of the three consumers still indexed the flat keys and raised KeyError on
the first result.

These tests drive the real render paths with a row shaped exactly like
`semantic_index.query()` builds one (see semantic_index.py:786-806, with
metadata per :256-266 for vault and :312-322 for github).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from rebalance.cli import app
from rebalance.ingest.querier import _build_prompt


def _vault_row() -> dict:
    """One result as semantic_index.query() returns it for source_type=vault."""
    return {
        "doc_id": 11,
        "source_type": "vault",
        "source_table": "chunks",
        "source_pk": "501",
        "doc_kind": "chunk",
        "title": "Weekly Review",
        "body_preview": "Shipped the retrieval consolidation and cut the release.",
        "metadata": {
            "file_id": 7,
            "file_path": "notes/weekly-review.md",
            "heading": "What shipped",
            "heading_level": 2,
            "chunk_index": 0,
            "char_count": 420,
            "tags": ["review"],
        },
        "updated_at": "2026-08-11T09:00:00+00:00",
        "similarity_score": 0.8123,
    }


def _github_row() -> dict:
    """One result as semantic_index.query() returns it for source_type=github."""
    return {
        "doc_id": 12,
        "source_type": "github",
        "source_table": "github_documents",
        "source_pk": "gh-266",
        "doc_kind": "issue_body",
        "title": "Architectural Audit: Complexity, DRY, and System Stability",
        "body_preview": "This issue captures an architectural audit covering complexity.",
        "metadata": {
            "repo_full_name": "AcmeOrg/rebalance-OS",
            "item_type": "issue",
            "source_number": 266,
            "state": "open",
            "milestone_title": "0.69.0",
            "labels": ["architecture", "tech-debt"],
            "review_decision": "",
            "check_status": "",
            "html_url": "https://github.com/AcmeOrg/rebalance-OS/issues/266",
        },
        "updated_at": "2026-08-11T09:00:00+00:00",
        "similarity_score": 0.7710,
    }


class QueryCliRendersUnifiedResults(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "rebalance.db"
        self.db.touch()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_query_cmd_renders_vault_result(self) -> None:
        with patch("rebalance.ingest.semantic_index.query", return_value=[_vault_row()]):
            result = self.runner.invoke(app, ["query", "retrieval", "--database", str(self.db)])
        self.assertIsNone(result.exception, f"query raised: {result.exception!r}")
        self.assertEqual(result.exit_code, 0)
        # heading and file_path live in metadata; both must reach the output.
        self.assertIn("What shipped", result.stdout)
        self.assertIn("notes/weekly-review.md", result.stdout)
        self.assertIn("Weekly Review", result.stdout)

    def test_github_query_cmd_renders_github_result(self) -> None:
        with patch("rebalance.ingest.semantic_index.query", return_value=[_github_row()]):
            result = self.runner.invoke(
                app, ["github-query", "audit", "--database", str(self.db)]
            )
        self.assertIsNone(result.exception, f"github-query raised: {result.exception!r}")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AcmeOrg/rebalance-OS", result.stdout)
        self.assertIn("#266", result.stdout)
        self.assertIn("architecture", result.stdout)          # labels
        self.assertIn("open", result.stdout)                  # state
        self.assertIn("0.69.0", result.stdout)                # milestone_title
        self.assertIn("issues/266", result.stdout)            # html_url
        # The artifact kind must survive: source_type is now "github" for every
        # row, so the issue/pr distinction has to come from metadata.item_type.
        self.assertIn("issue", result.stdout)


class BuildPromptRendersUnifiedResults(unittest.TestCase):
    def test_build_prompt_renders_github_semantic_context(self) -> None:
        prompt = _build_prompt(
            "what is the audit about",
            vault_context=[_vault_row()],
            github_context=[],
            github_semantic_context=[_github_row()],
            project_context=[],
            vault_activity=[],
        )
        self.assertIn("AcmeOrg/rebalance-OS", prompt)
        self.assertIn("#266", prompt)
        self.assertIn("(open)", prompt)
        self.assertIn("milestone=0.69.0", prompt)
        # Vault citations must keep their section anchor rather than silently
        # degrading to a bare title.
        self.assertIn("What shipped", prompt)


if __name__ == "__main__":
    unittest.main()
