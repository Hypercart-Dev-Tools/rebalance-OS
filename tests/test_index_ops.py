"""Tests for refresh orchestration options."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest.index_ops import _refresh_dashboard_note, _refresh_github, refresh_index


class IndexOpsTests(unittest.TestCase):
    def test_github_dry_run_embeds_github_documents(self) -> None:
        # Phase 3: github refresh embeds github_documents (source-table enrichment),
        # but semantic projection is owned by the semantic stage, not this collector.
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _refresh_github(
                Path(tmpdir) / "rebalance.db",
                token="test-token",
                since_days=30,
                repos=["example/repo"],
                dry_run=True,
            )

        self.assertIn("embed_github_documents()", result["steps"])
        self.assertNotIn("semantic_backfill(source=['github'])", result["steps"])
        self.assertNotIn("semantic_embed(source=['github'])", result["steps"])

    def test_full_refresh_dry_run_plans_dashboard_note_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vault = root / "vault"
            vault.mkdir()

            with (
                patch("rebalance.ingest.index_ops.get_vault_path", return_value=str(vault)),
                patch("rebalance.ingest.index_ops.get_github_token", return_value="test-token"),
                patch("rebalance.ingest.index_ops.get_watched_repos", return_value={"watched": ["example/repo"]}),
            ):
                result = refresh_index(root / "rebalance.db", scope=["all"], dry_run=True)

        scopes = [item["scope"] for item in result["results"]]
        self.assertIn("dashboard", scopes)
        dashboard = next(item for item in result["results"] if item["scope"] == "dashboard")
        self.assertTrue(dashboard["dry_run"])
        self.assertIn("write_dashboard_note()", dashboard["steps"])

    def test_dashboard_note_dry_run_targets_obsidian_dashboard_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = _refresh_dashboard_note(
                root / "rebalance.db",
                vault_path=root / "vault",
                since_days=14,
                dry_run=True,
            )

        self.assertEqual(result["scope"], "dashboard")
        self.assertTrue(result["dry_run"])
        self.assertTrue(result["output_path"].endswith("Dashboards/rebalanceOS Dashboard.md"))


if __name__ == "__main__":
    unittest.main()
