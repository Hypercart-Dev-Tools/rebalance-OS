"""Phase 2: non-mocked dashboard refresh / re-ingest integration test.

The dashboard refresh path (``_refresh_dashboard_note``) chains four real calls
— build note content, write the note, re-ingest the vault, embed the new chunks.
Existing coverage mocked the whole path, so a stale call signature on any link
could pass unnoticed. This drives the REAL chain against a real on-disk vault and
SQLite DB, faking only the embedding *model* (mlx) at the lowest seam so the real
``embed_chunks`` body — its DB queries and inserts — still executes.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest import config as config_mod
from rebalance.ingest import embedder
from rebalance.ingest.db import db_connection, ensure_baseline_schema, run_migrations
from rebalance.ingest.index_ops import _refresh_dashboard_note


def _fake_embed_batch(_model, _tokenizer, texts):
    return [[0.0] * embedder.EMBEDDING_DIM for _ in texts]


class DashboardRefreshIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._root = Path(self._tmp.name)
        self._vault = self._root / "vault"
        (self._vault / "Notes").mkdir(parents=True)
        (self._vault / "Notes" / "seed.md").write_text(
            "# Seed Note\n\nReal vault content for the re-ingest path.\n",
            encoding="utf-8",
        )
        self._db = self._root / "rebalance.db"
        with db_connection(self._db) as conn:
            ensure_baseline_schema(conn)
            run_migrations(conn)
        # Hermetic config so CalendarConfig.load() uses defaults, not the operator's.
        self._orig_config = config_mod.CONFIG_PATH
        config_mod.CONFIG_PATH = self._root / "rbos.config"
        self.addCleanup(self._restore_config)

    def _restore_config(self) -> None:
        config_mod.CONFIG_PATH = self._orig_config

    def test_dry_run_reports_plan_without_touching_fs(self) -> None:
        result = _refresh_dashboard_note(
            self._db, vault_path=self._vault, since_days=30, dry_run=True
        )
        self.assertEqual(result["scope"], "dashboard")
        self.assertTrue(result["dry_run"])
        self.assertIn("ingest_vault()", result["steps"])
        # No note written on a dry run.
        self.assertFalse((self._vault / "Dashboards" / "rebalanceOS Dashboard.md").exists())

    def test_real_chain_writes_note_reingests_and_embeds(self) -> None:
        with patch.object(embedder, "_load_model", return_value=(object(), object())), \
             patch.object(embedder, "_embed_batch", side_effect=_fake_embed_batch):
            result = _refresh_dashboard_note(
                self._db, vault_path=self._vault, since_days=30, dry_run=False
            )

        # The real chain returned the live ingest/embed result shapes.
        self.assertEqual(result["scope"], "dashboard")
        self.assertFalse(result["dry_run"])
        self.assertIn("ingest", result)
        self.assertIn("embed_chunks", result)

        # The dashboard note was actually written into the vault…
        note = Path(result["output_path"])
        self.assertTrue(note.exists())
        self.assertEqual(note.name, "rebalanceOS Dashboard.md")

        # …the vault re-ingest saw real files (seed note + the dashboard note)…
        self.assertGreaterEqual(result["ingest"]["total_files"], 1)
        self.assertGreaterEqual(result["ingest"]["total_chunks"], 1)

        # …and the real embed_chunks body ran, writing embeddings rows.
        self.assertGreaterEqual(result["embed_chunks"]["embedded"], 1)
        with db_connection(self._db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        self.assertEqual(count, result["embed_chunks"]["embedded"])


if __name__ == "__main__":
    unittest.main()
