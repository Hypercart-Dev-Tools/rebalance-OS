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


class SignalHealthQuietFilterTests(unittest.TestCase):
    """GH-145 / GH-141: a filtered collector that matches nothing is not broken.

    The live Gmail filter is ``in:inbox is:starred is:important`` — a three-way
    AND matching roughly one to three messages a month. The collector runs on
    schedule, authenticates, examines messages and retains none. That produced
    ``degraded`` forever by design, and contradicted doctor's own ``email data``
    check in the same output: one said ``ok``, the other ``degraded``.

    The distinguishing signal is whether the collector RAN, which current
    freshness already proves. These tests pin both halves — quiet-and-healthy
    stays ok, and a filter must never mask a collector that actually stopped.
    """

    def _email_health(self, db_path, *, synced: str, received: str | None):
        from rebalance.ingest.db import db_connection, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with db_connection(db_path) as conn:
            run_migrations(conn)
            if received is not None:
                conn.execute(
                    "INSERT INTO email_messages "
                    "(message_id, thread_id, from_address, from_name, subject, "
                    " snippet, received_at, synced_at) "
                    "VALUES ('old-1', NULL, 'a@b.co', 'A', 'Subject', 's', "
                    f"datetime('now', '{received}'), datetime('now', '{synced}'))"
                )
            conn.commit()
        return get_index_status(db_path)["freshness"]["signal_health"]["email"]

    def test_quiet_but_successfully_synced_email_is_ok_and_names_the_filter(self) -> None:
        """The live #141 shape: synced today, newest message 31 days old."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            health = self._email_health(db_path, synced="-1 hour", received="-31 days")

        self.assertEqual(
            health["status"], "ok",
            "a successful sync that retained nothing is the configured outcome, "
            "not silent data loss",
        )
        self.assertIn("no rows matched", health["reason"])
        self.assertIn(
            "Gmail filter:", health["reason"],
            "the operator must be able to see WHY it is quiet, or 'ok' is just "
            "as unactionable as the false 'degraded' was",
        )

    def test_a_stale_filtered_source_still_degrades(self) -> None:
        """The critical negative: a filter must not mask a collector that died.

        Same source, same filter — but the sync timestamp itself has stopped
        advancing. That is a real failure and must survive the GH-145 change.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            health = self._email_health(db_path, synced="-40 days", received="-40 days")

        self.assertEqual(
            health["status"], "degraded",
            "quiet_filter only excuses a zero-row window on a collector that "
            "demonstrably RAN; a stale freshness timestamp still degrades",
        )
        self.assertIn("last refresh advanced", health["reason"])

    def test_source_without_a_quiet_filter_still_applies_zero_status(self) -> None:
        """vault declares no quiet_filter, so its zero-row behaviour is unchanged.

        Guards against the fix being over-broad — it would be easy to excuse
        every quiet source and blind the whole check.
        """
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

    def test_quiet_filter_is_declarative_and_resolves_through_config(self) -> None:
        """The rule names a formatter in config; it must not embed a filter string.

        This is what keeps the filter to one home. If a future edit inlines the
        query text into the rules table, doctor and signal health can drift
        apart again — which was the whole of GH-145.
        """
        from rebalance.ingest.config import describe_gmail_query_filter
        from rebalance.ingest.index_ops import _SIGNAL_HEALTH_RULES

        rule = _SIGNAL_HEALTH_RULES["email"]
        self.assertEqual(rule.get("quiet_filter"), "describe_gmail_query_filter")
        self.assertTrue(
            callable(describe_gmail_query_filter),
            "the named formatter must exist in rebalance.ingest.config",
        )
        self.assertIn("Gmail filter:", describe_gmail_query_filter())

    def test_a_broken_formatter_does_not_crash_the_verdict(self) -> None:
        """A health check must never crash the status it reports on."""
        from rebalance.ingest.index_ops import _quiet_filter_description

        self.assertIsNone(_quiet_filter_description({}))
        self.assertIsNone(_quiet_filter_description({"quiet_filter": "no_such_formatter"}))


class VaultIngestLagTests(unittest.TestCase):
    """GH-166: signal_health.vault must degrade on a meaningful ingest lag,
    not just a 7-day freshness window. last_ingested_at can be recent while
    the vault writer has moved further ahead than the ingester has caught
    up to — that gap is what these tests pin."""

    def _vault_health_and_lag(self, db_path, *, ingested_minutes_ago: int, modified_minutes_ago: int):
        from rebalance.ingest.db import db_connection, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with db_connection(db_path) as conn:
            run_migrations(conn)
            conn.execute(
                "INSERT INTO vault_files (rel_path, content_hash, ingested_at, last_modified) "
                "VALUES ('drift.md', 'hash1', "
                f"datetime('now', '-{ingested_minutes_ago} minutes'), "
                f"datetime('now', '-{modified_minutes_ago} minutes'))"
            )
            conn.commit()

        status = get_index_status(db_path)
        vault_source = status["sources"]["vault"]
        health = status["freshness"]["signal_health"]["vault"]
        return vault_source, health

    def test_lag_within_threshold_stays_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            vault_source, health = self._vault_health_and_lag(
                db_path, ingested_minutes_ago=15, modified_minutes_ago=5,
            )

        self.assertAlmostEqual(vault_source["ingest_lag_minutes"], 10.0, delta=1.0)
        self.assertEqual(health["status"], "ok")
        self.assertNotIn("reason", health)

    def test_lag_past_warn_threshold_warns(self) -> None:
        """The #166 shape: a ~130 minute drift the old 7-day window ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            vault_source, health = self._vault_health_and_lag(
                db_path, ingested_minutes_ago=130, modified_minutes_ago=0,
            )

        self.assertGreater(vault_source["ingest_lag_minutes"], 120)
        self.assertEqual(health["status"], "warn")
        self.assertIn("behind the vault writer", health["reason"])

    def test_lag_past_degraded_threshold_degrades(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            vault_source, health = self._vault_health_and_lag(
                db_path, ingested_minutes_ago=200, modified_minutes_ago=0,
            )

        self.assertGreater(vault_source["ingest_lag_minutes"], 180)
        self.assertEqual(health["status"], "degraded")
        self.assertIn("behind the vault writer", health["reason"])

    def test_ingest_after_modification_clamps_lag_to_zero(self) -> None:
        """Normal ordering (ingest runs after the edit) must never report a
        negative lag — clamp to 0, same as the pre-existing healthy-source
        fixture (ingested now, modified 2 days ago)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            vault_source, health = self._vault_health_and_lag(
                db_path, ingested_minutes_ago=0, modified_minutes_ago=2880,
            )

        self.assertEqual(vault_source["ingest_lag_minutes"], 0.0)
        self.assertEqual(health["status"], "ok")


class PendingEmbedStuckTests(unittest.TestCase):
    """GH-166: a semantic_documents row pending embed must be distinguished
    as "stuck" (sat unembedded past a reasonable threshold) vs. an in-flight
    run's normal tail (embed_chunks() runs synchronously right after ingest,
    so a fresh pending row is expected and not a problem)."""

    def _insert_pending_doc(self, conn, *, source_pk: str, updated_minutes_ago: int) -> None:
        conn.execute(
            "INSERT INTO semantic_documents "
            "(source_type, source_table, source_pk, doc_kind, title, body, "
            " content_hash, embedded_hash, embedded_model_version, embedded_at, "
            " created_at, updated_at) "
            "VALUES ('vault', 'chunks', ?, 'chunk', 'Title', 'body text', "
            " 'hash-current', NULL, NULL, NULL, "
            f" datetime('now', '-{updated_minutes_ago} minutes'), "
            f" datetime('now', '-{updated_minutes_ago} minutes'))",
            (source_pk,),
        )

    def test_freshly_pending_row_is_not_flagged_stuck(self) -> None:
        from rebalance.ingest.db import db_connection, ensure_semantic_schema, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path, ensure_semantic_schema) as conn:
                run_migrations(conn)
                self._insert_pending_doc(conn, source_pk="1", updated_minutes_ago=2)
                conn.commit()

            drift = get_index_status(db_path)["freshness"]
            self.assertEqual(drift["semantic_documents_pending_embed"], 1)
            self.assertEqual(drift["semantic_documents_pending_embed_stuck"], 0)
            self.assertNotIn("semantic_documents_pending_embed_reason", drift)

    def test_long_pending_row_is_flagged_stuck_with_a_reason(self) -> None:
        from rebalance.ingest.db import db_connection, ensure_semantic_schema, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path, ensure_semantic_schema) as conn:
                run_migrations(conn)
                self._insert_pending_doc(conn, source_pk="1", updated_minutes_ago=45)
                conn.commit()

            drift = get_index_status(db_path)["freshness"]
            self.assertEqual(drift["semantic_documents_pending_embed"], 1)
            self.assertEqual(drift["semantic_documents_pending_embed_stuck"], 1)
            self.assertGreaterEqual(drift["semantic_documents_pending_embed_oldest_minutes"], 45)
            self.assertIn("stuck/failed embed run", drift["semantic_documents_pending_embed_reason"])

    def test_mixed_pending_rows_only_flag_the_stuck_one(self) -> None:
        from rebalance.ingest.db import db_connection, ensure_semantic_schema, run_migrations
        from rebalance.ingest.index_ops import get_index_status

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path, ensure_semantic_schema) as conn:
                run_migrations(conn)
                self._insert_pending_doc(conn, source_pk="1", updated_minutes_ago=2)
                self._insert_pending_doc(conn, source_pk="2", updated_minutes_ago=60)
                conn.commit()

            drift = get_index_status(db_path)["freshness"]
            self.assertEqual(drift["semantic_documents_pending_embed"], 2)
            self.assertEqual(drift["semantic_documents_pending_embed_stuck"], 1)


class SignalHealthAgreesWithDoctorTests(unittest.TestCase):
    """GH-145 anti-drift: the two surfaces must not contradict each other."""

    def test_doctor_and_signal_health_read_the_same_filter_description(self) -> None:
        from rebalance.doctor import _active_gmail_filter
        from rebalance.ingest.config import describe_gmail_query_filter

        self.assertEqual(
            _active_gmail_filter(), describe_gmail_query_filter(),
            "doctor's freshness check and signal health must describe the "
            "active filter identically — two formatters is how they drifted",
        )


if __name__ == "__main__":
    unittest.main()
