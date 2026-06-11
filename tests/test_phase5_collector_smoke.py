"""Phase 5 smoke, auth-failure, and idempotency tests for the five raw-source collectors.

Each test exercises the source-owned refresh entry point (_refresh_* function or the
refresh_index dispatcher) rather than calling leaf ingest functions directly.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rebalance.ingest.index_ops import (
    _refresh_calendar,
    _refresh_email,
    _refresh_github,
    _refresh_sleuth,
    _refresh_vault,
    refresh_index,
)


def _error_scopes(result: dict) -> set[str]:
    return {e["scope"] for e in result.get("errors", [])}


# ---------------------------------------------------------------------------
# Smoke tests — dry_run, no DB or network needed
# ---------------------------------------------------------------------------

class CollectorSmokeTests(unittest.TestCase):
    """Dry-run smoke test per raw source: correct scope, expected steps, no side-effects."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.db = self.root / "test.db"

    def tearDown(self):
        self._tmp.cleanup()

    def test_vault_dry_run_plans_ingest_and_embed(self):
        vault = self.root / "vault"
        vault.mkdir()
        result = _refresh_vault(self.db, vault, dry_run=True)
        self.assertEqual(result["scope"], "vault")
        self.assertTrue(result["dry_run"])
        steps = " ".join(result["steps"])
        self.assertIn("ingest_vault", steps)
        self.assertIn("embed_chunks", steps)

    def test_calendar_dry_run_plans_sync(self):
        result = _refresh_calendar(self.db, since_days=7, dry_run=True)
        self.assertEqual(result["scope"], "calendar")
        self.assertTrue(result["dry_run"])
        self.assertTrue(any("sync_calendar" in s for s in result["steps"]))

    def test_sleuth_dry_run_plans_sync(self):
        result = _refresh_sleuth(self.db, dry_run=True)
        self.assertEqual(result["scope"], "sleuth")
        self.assertTrue(result["dry_run"])
        self.assertTrue(any("sync_sleuth" in s for s in result["steps"]))

    def test_email_dry_run_plans_sync_in_oauth_mode(self):
        with patch("rebalance.ingest.config.get_gmail_ingest_method", return_value="oauth"):
            result = _refresh_email(self.db, dry_run=True)
        self.assertEqual(result["scope"], "email")
        self.assertTrue(result["dry_run"])
        self.assertTrue(any("sync_gmail" in s for s in result["steps"]))

    def test_email_mcp_mode_skips_gracefully_on_dry_run(self):
        with patch("rebalance.ingest.config.get_gmail_ingest_method", return_value="mcp"):
            result = _refresh_email(self.db, dry_run=True)
        self.assertEqual(result["scope"], "email")
        self.assertTrue(result.get("skipped"))
        self.assertEqual(result.get("method"), "mcp")


# ---------------------------------------------------------------------------
# Auth / config failure tests — structured errors, not exceptions
# ---------------------------------------------------------------------------

class CollectorAuthConfigFailureTests(unittest.TestCase):
    """Missing credentials / API errors produce structured error envelopes, not uncaught exceptions."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.db = self.root / "test.db"

    def tearDown(self):
        self._tmp.cleanup()

    def test_vault_missing_path_appears_in_error_envelope(self):
        with patch("rebalance.ingest.index_ops.get_vault_path", return_value=""):
            result = refresh_index(
                self.db, scope=["vault"], vault_path="", update_dashboard_note=False
            )
        self.assertIn("vault", _error_scopes(result), "vault error missing from errors list")
        result_scopes = {r.get("scope") for r in result.get("results", [])}
        self.assertNotIn("vault", result_scopes, "vault must not appear in results on missing path")

    def test_github_missing_token_appears_in_error_envelope(self):
        with patch("rebalance.ingest.index_ops.get_github_token", return_value=""):
            result = refresh_index(self.db, scope=["github"], update_dashboard_note=False)
        self.assertIn("github", _error_scopes(result), "github error missing from errors list")

    def test_calendar_api_exception_goes_to_error_envelope(self):
        with (
            patch("rebalance.ingest.calendar.sync_calendar", side_effect=RuntimeError("API down")),
            patch("rebalance.ingest.calendar_config.CalendarConfig.load") as mock_cfg,
        ):
            mock_cfg.return_value.calendar_id = "primary"
            result = refresh_index(self.db, scope=["calendar"], update_dashboard_note=False)
        self.assertIn("calendar", _error_scopes(result))

    def test_sleuth_api_exception_goes_to_error_envelope(self):
        with patch(
            "rebalance.ingest.sleuth_reminders.sync_sleuth",
            side_effect=RuntimeError("API down"),
        ):
            result = refresh_index(self.db, scope=["sleuth"], update_dashboard_note=False)
        self.assertIn("sleuth", _error_scopes(result))

    def test_email_auth_error_returned_inline_not_raised(self):
        # GmailAuthError is caught inside _refresh_email and returned as a result
        # dict with an "error" key — it must not propagate as an exception.
        from rebalance.ingest.gmail import GmailAuthError
        with (
            patch("rebalance.ingest.config.get_gmail_ingest_method", return_value="oauth"),
            patch("rebalance.ingest.gmail.sync_gmail", side_effect=GmailAuthError("no token")),
        ):
            result = _refresh_email(self.db, dry_run=False)
        self.assertEqual(result["scope"], "email")
        self.assertIn("error", result)


# ---------------------------------------------------------------------------
# Idempotency tests — repeated refreshes with unchanged input do not drift
# ---------------------------------------------------------------------------

class CollectorIdempotencyTests(unittest.TestCase):
    """Repeated refreshes prove that unchanged inputs produce stable counts with no duplicate writes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.db = self.root / "test.db"

    def tearDown(self):
        self._tmp.cleanup()

    def test_vault_second_run_reports_zero_new_files(self):
        vault = self.root / "vault"
        vault.mkdir()
        (vault / "note.md").write_text("# Hello\nThis is a test note.")

        fake_embed_r1 = SimpleNamespace(
            total_chunks=1, embedded_chunks=1, skipped_unchanged=0, elapsed_seconds=0.01
        )
        fake_embed_r2 = SimpleNamespace(
            total_chunks=1, embedded_chunks=0, skipped_unchanged=1, elapsed_seconds=0.01
        )
        with (
            patch("rebalance.ingest.index_ops.get_vault_path", return_value=str(vault)),
            patch("rebalance.ingest.embedder.embed_chunks") as mock_embed,
        ):
            mock_embed.side_effect = [fake_embed_r1, fake_embed_r2]
            r1 = refresh_index(self.db, scope=["vault"], update_dashboard_note=False)
            r2 = refresh_index(self.db, scope=["vault"], update_dashboard_note=False)

        v1 = next(r for r in r1["results"] if r.get("scope") == "vault")
        v2 = next(r for r in r2["results"] if r.get("scope") == "vault")
        self.assertEqual(v1["ingest"]["new_files"], 1, "first run: 1 new file expected")
        self.assertEqual(v2["ingest"]["new_files"], 0, "second run: file unchanged, 0 new")
        self.assertEqual(v2["ingest"]["updated_files"], 0, "second run: file unchanged, 0 updated")

    def test_calendar_repeated_sync_result_shape_is_stable(self):
        """Same events from the source produce consistent result keys and counts across calls."""
        from rebalance.ingest.calendar import CalendarSyncResult

        sync_result = CalendarSyncResult(
            events_fetched=3,
            events_stored=3,
            window_start="2026-06-03T00:00:00+00:00",
            window_end="2026-06-10T00:00:00+00:00",
            elapsed_seconds=0.05,
        )
        with (
            patch("rebalance.ingest.calendar.sync_calendar", return_value=sync_result),
            patch("rebalance.ingest.calendar_config.CalendarConfig.load") as mock_cfg,
        ):
            mock_cfg.return_value.calendar_id = "primary"
            r1 = _refresh_calendar(self.db, since_days=7, dry_run=False)
            r2 = _refresh_calendar(self.db, since_days=7, dry_run=False)

        for key in ("scope", "events_fetched", "events_stored"):
            self.assertEqual(r1[key], r2[key], f"result[{key!r}] drifted between identical syncs")

    def test_github_dry_run_planning_is_idempotent(self):
        """Repeated dry-run calls with the same repo list produce an identical step list and targets."""
        with (
            patch(
                "rebalance.ingest.index_ops._resolve_repos_for_refresh",
                return_value=["owner/repo"],
            ),
            patch("rebalance.ingest.index_ops._external_repos", return_value=[]),
        ):
            r1 = _refresh_github(self.db, token="tok", since_days=7, repos=[], dry_run=True)
            r2 = _refresh_github(self.db, token="tok", since_days=7, repos=[], dry_run=True)

        self.assertEqual(r1["steps"], r2["steps"])
        self.assertEqual(r1["target_repos"], r2["target_repos"])


if __name__ == "__main__":
    unittest.main()
