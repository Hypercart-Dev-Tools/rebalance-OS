"""Tests for refresh orchestration options."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest.index_ops import (
    _github_adapter,
    _refresh_dashboard_note,
    _refresh_github,
    _retry_on_db_locked,
    refresh_index,
)


class RetryOnDbLockedTests(unittest.TestCase):
    """GH-131: the github-scope writer retries a transient SQLite lock (the
    hourly github-sync job colliding with daily-sync's window) instead of
    failing the whole scope on the first busy_timeout expiry."""

    def test_succeeds_immediately_when_fn_does_not_raise(self) -> None:
        calls = []
        result = _retry_on_db_locked(lambda: calls.append(1) or "ok", sleep_fn=lambda s: None)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 1)

    def test_retries_on_locked_then_succeeds(self) -> None:
        attempts = {"n": 0}

        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return "recovered"

        sleeps: list[float] = []
        result = _retry_on_db_locked(flaky, attempts=3, base_delay_seconds=5.0, sleep_fn=sleeps.append)

        self.assertEqual(result, "recovered")
        self.assertEqual(attempts["n"], 3)
        self.assertEqual(sleeps, [5.0, 10.0])  # linear backoff before attempts 2 and 3

    def test_bounded_ceiling_reraises_after_final_attempt(self) -> None:
        # Hard invariant: a persistent lock is never silently swallowed.
        def always_locked():
            raise sqlite3.OperationalError("database is locked")

        with self.assertRaises(sqlite3.OperationalError):
            _retry_on_db_locked(always_locked, attempts=3, sleep_fn=lambda s: None)

    def test_non_lock_operational_error_is_not_retried(self) -> None:
        calls = {"n": 0}

        def other_error():
            calls["n"] += 1
            raise sqlite3.OperationalError("no such table: foo")

        with self.assertRaises(sqlite3.OperationalError):
            _retry_on_db_locked(other_error, attempts=3, sleep_fn=lambda s: None)
        self.assertEqual(calls["n"], 1)  # no retry — not a lock error

    def test_non_operational_exception_propagates_immediately(self) -> None:
        def boom():
            raise ValueError("unrelated")

        with self.assertRaises(ValueError):
            _retry_on_db_locked(boom, attempts=3, sleep_fn=lambda s: None)


class GithubAdapterRetryTests(unittest.TestCase):
    """_github_adapter wires _refresh_github through the GH-131 retry wrapper."""

    def test_github_adapter_retries_transient_lock(self) -> None:
        attempts = {"n": 0}

        def flaky_refresh(db_path, **kwargs):
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise sqlite3.OperationalError("database is locked")
            return {"scope": "github", "recovered": True}

        with patch("rebalance.ingest.index_ops._refresh_github", side_effect=flaky_refresh), \
             patch("rebalance.ingest.index_ops.time.sleep") as mock_sleep:
            result = _github_adapter(
                Path("/tmp/fake.db"),
                token="t", since_days=7, repos=[], dry_run=False,
            )

        self.assertEqual(result, {"scope": "github", "recovered": True})
        self.assertEqual(attempts["n"], 2)
        mock_sleep.assert_called_once()

    def test_github_adapter_dry_run_never_touches_retry_sleep(self) -> None:
        with patch("rebalance.ingest.index_ops._refresh_github", return_value={"scope": "github", "dry_run": True}), \
             patch("rebalance.ingest.index_ops.time.sleep") as mock_sleep:
            result = _github_adapter(
                Path("/tmp/fake.db"),
                token="t", since_days=7, repos=[], dry_run=True,
            )
        self.assertEqual(result, {"scope": "github", "dry_run": True})
        mock_sleep.assert_not_called()


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

    def test_github_refresh_wires_auto_promote_after_watchlist_guard(self) -> None:
        # GH-124: a real (non-dry-run) github refresh must call
        # sync_commit_threshold_promotions after the watchlist guard and fold
        # its summary into the result under "auto_promote".
        from rebalance.ingest.project_inference import AutoPromoteSummary

        fake_promoted_row = {
            "name": "widget",
            "custom_fields": {"inference": {"repo_full_name": "Acme/widget"}},
        }
        fake_summary = AutoPromoteSummary(
            enabled=True, threshold=3, candidates_evaluated=2, promoted=[fake_promoted_row]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with (
                patch(
                    "rebalance.ingest.index_ops._resolve_repos_for_refresh",
                    return_value=[],
                ),
                patch(
                    "rebalance.ingest.github_scan.sync_pushed_repos"
                ) as mock_pushed,
                patch("rebalance.ingest.github_scan.scan_github") as mock_scan,
                patch(
                    "rebalance.ingest.github_scan.filter_ignored_repo_activity",
                    return_value=[],
                ),
                patch("rebalance.ingest.github_scan.upsert_github_activity"),
                patch(
                    "rebalance.ingest.github_knowledge.embed_github_documents"
                ) as mock_embed,
                patch(
                    "rebalance.ingest.watchlist_guard.snapshot_and_detect",
                    return_value={"ok": True},
                ),
                patch(
                    "rebalance.ingest.project_inference.sync_commit_threshold_promotions",
                    return_value=fake_summary,
                ) as mock_auto_promote,
            ):
                mock_pushed.return_value.fetched = 0
                mock_pushed.return_value.inserted = 0
                mock_pushed.return_value.updated = 0
                mock_pushed.return_value.unchanged = 0
                mock_pushed.return_value.skipped_archived = 0
                mock_pushed.return_value.error = None
                mock_scan.return_value.login = "tester"
                mock_scan.return_value.total_events = 0
                mock_scan.return_value.repo_activity = []
                mock_embed.return_value.total_docs = 0
                mock_embed.return_value.embedded_docs = 0
                mock_embed.return_value.skipped_unchanged = 0
                mock_embed.return_value.elapsed_seconds = 0.0

                result = _refresh_github(
                    db_path, token="test-token", since_days=14, repos=[], dry_run=False
                )

        mock_auto_promote.assert_called_once_with(db_path)
        self.assertEqual(result["auto_promote"]["promoted_count"], 1)
        self.assertEqual(result["auto_promote"]["promoted_repos"], ["Acme/widget"])
        self.assertEqual(result["auto_promote"]["candidates_evaluated"], 2)

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

    def test_get_index_status_signal_health_email_content_predicate_degrades_empty_rows(
        self,
    ) -> None:
        """GH-127: the exact #125 scenario — fresh timestamps and a healthy
        row count, but the rows are husks with no sender or subject. Before
        GH-127 this reported `ok` for 3 weeks; the content predicate must now
        catch it and report `degraded`."""
        from rebalance.ingest.db import db_connection, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                run_migrations(conn)
                for i in range(5):
                    conn.execute(
                        "INSERT INTO email_messages "
                        "(message_id, thread_id, from_address, from_name, subject, "
                        " snippet, received_at, synced_at) "
                        "VALUES (?, NULL, NULL, NULL, NULL, NULL, datetime('now'), datetime('now'))",
                        (f"husk-{i}",),
                    )
                conn.commit()

            health = get_index_status(db_path)["freshness"]["signal_health"]["email"]
            self.assertEqual(health["status"], "degraded")
            self.assertIn("sender or subject", health["reason"])

    def test_get_index_status_signal_health_email_with_real_content_stays_ok(self) -> None:
        """A source with a content_predicate but rows that actually carry
        content (sender + subject present) must still report `ok` — the
        predicate only escalates, it never demotes a genuinely healthy row."""
        from rebalance.ingest.db import db_connection, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                run_migrations(conn)
                for i in range(5):
                    conn.execute(
                        "INSERT INTO email_messages "
                        "(message_id, thread_id, from_address, from_name, subject, "
                        " snippet, received_at, synced_at) "
                        "VALUES (?, NULL, ?, ?, ?, NULL, datetime('now'), datetime('now'))",
                        (f"real-{i}", f"sender{i}@example.com", f"Sender {i}", f"Subject {i}"),
                    )
                conn.commit()

            health = get_index_status(db_path)["freshness"]["signal_health"]["email"]
            self.assertEqual(health["status"], "ok")
            self.assertNotIn("reason", health)

    def test_get_index_status_signal_health_github_content_predicate_degrades_empty_titles(
        self,
    ) -> None:
        """GH-127 second registered source: github_items with fresh
        fetched_at but empty titles must degrade github's signal_health, even
        though github_activity (the table behind recent_row_count_7d/
        freshness) has no content field at all."""
        from rebalance.ingest.db import db_connection, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path) as conn:
                run_migrations(conn)
                # Recent activity so the freshness/zero-rows checks pass and
                # execution reaches the content-predicate override.
                conn.execute(
                    "INSERT INTO github_activity "
                    "(login, repo_full_name, scan_date, commits, scanned_at) "
                    "VALUES ('me', 'org/repo', date('now'), 1, datetime('now'))"
                )
                for i in range(5):
                    conn.execute(
                        "INSERT INTO github_items "
                        "(repo_full_name, item_type, number, title, fetched_at) "
                        "VALUES ('org/repo', 'issue', ?, '', datetime('now'))",
                        (i + 1,),
                    )
                conn.commit()

            health = get_index_status(db_path)["freshness"]["signal_health"]["github"]
            self.assertEqual(health["status"], "degraded")
            self.assertIn("title", health["reason"])


if __name__ == "__main__":
    unittest.main()
