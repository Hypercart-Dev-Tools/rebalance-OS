"""Phase 2: explicit gating of the opt-in Figma source.

The Figma happy path is already hermetically covered (test_figma_ingest.py,
test_figma_source_module.py inject a fake client — no network, no PAT). What was
untested is the *gate*: when Figma is unconfigured, the collector must return an
honest structured envelope and touch neither the network nor the DB — never a
crash, never silent success. That is the "verify opt-in paths or gate them
explicitly" contract; these tests pin it so the gate can't quietly regress.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest import index_ops

# A path that would error loudly if any branch under test actually opened the DB.
_UNUSED_DB = Path("/nonexistent/should-not-be-opened.db")


class FigmaGatingTests(unittest.TestCase):
    def test_missing_token_returns_clean_error_envelope(self) -> None:
        with patch.object(index_ops, "get_figma_token", return_value=""), \
             patch.object(index_ops, "get_figma_file_keys", return_value=["abc"]):
            result = index_ops._refresh_figma(_UNUSED_DB, dry_run=False)
        self.assertEqual(result["scope"], "figma")
        self.assertIn("token", result["error"].lower())
        self.assertNotIn("skipped", result)  # an error, not a silent skip

    def test_token_without_file_keys_skips_with_reason(self) -> None:
        with patch.object(index_ops, "get_figma_token", return_value="figd_fake"), \
             patch.object(index_ops, "get_figma_file_keys", return_value=[]):
            result = index_ops._refresh_figma(_UNUSED_DB, dry_run=False)
        self.assertTrue(result["skipped"])
        self.assertIn("file key", result["reason"].lower())

    def test_dry_run_lists_plan_without_credentials(self) -> None:
        with patch.object(index_ops, "get_figma_file_keys", return_value=["abc", "def"]):
            result = index_ops._refresh_figma(_UNUSED_DB, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["file_keys"], ["abc", "def"])
        self.assertTrue(any("sync_figma_comments" in s for s in result["steps"]))


if __name__ == "__main__":
    unittest.main()
