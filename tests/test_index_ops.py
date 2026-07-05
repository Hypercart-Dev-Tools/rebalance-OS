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

    def test_get_index_status_recent_row_count_7d(self) -> None:
        from rebalance.ingest.db import db_connection, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"

            # Initialize the database schema and migrations
            with db_connection(db_path) as conn:
                run_migrations(conn)

                # Seed vault (table vault_files)
                # 1 recent modified file, 1 stale modified file
                conn.execute(
                    "INSERT INTO vault_files (rel_path, content_hash, ingested_at, last_modified) "
                    "VALUES ('recent.md', 'hash1', datetime('now'), datetime('now', '-2 days'))"
                )
                conn.execute(
                    "INSERT INTO vault_files (rel_path, content_hash, ingested_at, last_modified) "
                    "VALUES ('stale.md', 'hash2', datetime('now'), datetime('now', '-10 days'))"
                )

                # Seed calendar (table calendar_events)
                # 1 recent past event, 1 recent future event, 1 stale past event, 1 stale future event
                conn.execute(
                    "INSERT INTO calendar_events (id, start_time, fetched_at) "
                    "VALUES ('event1', datetime('now', '-2 days'), datetime('now'))"
                )
                conn.execute(
                    "INSERT INTO calendar_events (id, start_time, fetched_at) "
                    "VALUES ('event2', datetime('now', '+2 days'), datetime('now'))"
                )
                conn.execute(
                    "INSERT INTO calendar_events (id, start_time, fetched_at) "
                    "VALUES ('event3', datetime('now', '-10 days'), datetime('now'))"
                )
                conn.execute(
                    "INSERT INTO calendar_events (id, start_time, fetched_at) "
                    "VALUES ('event4', datetime('now', '+10 days'), datetime('now'))"
                )
                conn.commit()

            # Query get_index_status
            status = get_index_status(db_path)

            # Verify keys are present for all sources
            sources = status.get("sources", {})
            expected_sources = [
                "vault", "github", "calendar", "sleuth",
                "apple_reminders", "email", "figma", "ask_self"
            ]
            for src in expected_sources:
                self.assertIn(src, sources)
                self.assertIn("recent_row_count_7d", sources[src])

            # Verify seeded sources have correct count
            self.assertEqual(sources["vault"]["recent_row_count_7d"], 1)
            self.assertEqual(sources["calendar"]["recent_row_count_7d"], 2)

            # Verify zero-volume sources return 0, not None
            self.assertEqual(sources["email"]["recent_row_count_7d"], 0)
            self.assertEqual(sources["github"]["recent_row_count_7d"], 0)

    def test_get_index_status_signal_health_marks_fresh_but_empty_source_degraded(self) -> None:
        from rebalance.ingest.db import db_connection, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                run_migrations(conn)
                conn.execute(
                    "INSERT INTO vault_files (rel_path, content_hash, ingested_at, last_modified) "
                    "VALUES ('stale.md', 'hash1', datetime('now'), datetime('now', '-10 days'))"
                )
                conn.commit()

            health = get_index_status(db_path)["freshness"]["signal_health"]["vault"]
            self.assertEqual(health["status"], "degraded")
            self.assertTrue(health["reason"])

    def test_get_index_status_signal_health_marks_healthy_source_ok(self) -> None:
        from rebalance.ingest.db import db_connection, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                run_migrations(conn)
                conn.execute(
                    "INSERT INTO vault_files (rel_path, content_hash, ingested_at, last_modified) "
                    "VALUES ('fresh.md', 'hash1', datetime('now'), datetime('now', '-2 days'))"
                )
                conn.commit()

            health = get_index_status(db_path)["freshness"]["signal_health"]["vault"]
            self.assertEqual(health["status"], "ok")
            self.assertNotIn("reason", health)

    def test_get_index_status_signal_health_warns_for_legitimately_quiet_source(self) -> None:
        from rebalance.ingest.db import db_connection, run_migrations
        from rebalance.ingest.index_ops import get_index_status
        from rebalance.ingest.sleuth_reminders import ensure_sleuth_schema

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path, ensure_sleuth_schema) as conn:
                run_migrations(conn)
                conn.execute(
                    """
                    INSERT INTO sleuth_reminders (
                        reminder_id, workspace_name, state, is_active,
                        created_on, should_post_on, reminder_message_text,
                        ignore_snooze, assignee_id, original_sender_id,
                        target_channel_id, original_channel_id, original_channel_name,
                        original_message_id, original_thread_ts, github_urls_json,
                        first_seen_at, last_seen_at, last_synced_at
                    ) VALUES (
                        'quiet-1', 'ops', 'scheduled', 1,
                        datetime('now', '-10 days'), datetime('now', '-9 days'), 'follow up',
                        0, 'U1', 'U2',
                        'C1', 'C2', 'eng',
                        '123.456', NULL, '[]',
                        datetime('now'), datetime('now'), datetime('now')
                    )
                    """
                )
                conn.commit()

            health = get_index_status(db_path)["freshness"]["signal_health"]["sleuth"]
            self.assertEqual(health["status"], "warn")
            self.assertTrue(health["reason"])


if __name__ == "__main__":
    unittest.main()
