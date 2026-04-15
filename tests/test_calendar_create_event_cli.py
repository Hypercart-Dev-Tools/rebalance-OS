"""Tests for the calendar-create-event CLI command."""

import json
import pickle
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from rebalance.cli import app


class CalendarCreateEventCliTests(unittest.TestCase):
    """CLI tests for dry-run payload generation and scope enforcement."""

    def setUp(self) -> None:
        self.runner = CliRunner()

    def _write_env(self, tmpdir: str, token_path: Path, scope: str) -> Path:
        env_path = Path(tmpdir) / "google-calendar.env"
        env_path.write_text(
            "\n".join(
                [
                    "GOOGLE_CALENDAR_ACCESS_MODE=oauth_pickle_token",
                    f"GOOGLE_CALENDAR_TOKEN_PATH={token_path}",
                    f"GOOGLE_CALENDAR_CURRENT_SCOPE={scope}",
                    "GOOGLE_CALENDAR_REQUIRED_WRITE_SCOPE=https://www.googleapis.com/auth/calendar",
                    "GOOGLE_CALENDAR_REAUTH_COMMAND=python scripts/setup_calendar_oauth.py --write-access --test",
                ]
            ),
            encoding="utf-8",
        )
        return env_path

    def _write_token(self, tmpdir: str, scopes: list[str]) -> Path:
        token_path = Path(tmpdir) / "oauth"
        creds = SimpleNamespace(scopes=scopes, expired=False, refresh_token="rt")
        with open(token_path, "wb") as token_file:
            pickle.dump(creds, token_file)
        return token_path

    def test_dry_run_all_day_event_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = self._write_token(tmpdir, ["https://www.googleapis.com/auth/calendar"])
            env_path = self._write_env(tmpdir, token_path, "https://www.googleapis.com/auth/calendar")

            with patch("rebalance.cli.GOOGLE_CALENDAR_ENV_PATH", env_path):
                result = self.runner.invoke(
                    app,
                    [
                        "calendar-create-event",
                        "--title",
                        "Verify Binoid BQ candidate + staging dataset auto-deletion (2026-04-13 clone+swap cleanup)",
                        "--date",
                        "2026-04-21",
                        "--description",
                        "Auto-cleanup expirationTime on Binoid candidate datasets is 2026-04-21 ~18:37 UTC.",
                        "--calendar-id",
                        "primary",
                        "--dry-run",
                    ],
                )

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["calendar_id"], "primary")
        self.assertEqual(payload["summary"], "Verify Binoid BQ candidate + staging dataset auto-deletion (2026-04-13 clone+swap cleanup)")
        self.assertEqual(payload["start_time"], "2026-04-21T00:00:00-07:00")
        self.assertEqual(payload["end_time"], "2026-04-22T00:00:00-07:00")
        self.assertEqual(payload["timezone_name"], "America/Los_Angeles")
        self.assertEqual(payload["attendees"], [])

    def test_missing_write_scope_fails_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = self._write_token(tmpdir, ["https://www.googleapis.com/auth/calendar.readonly"])
            env_path = self._write_env(tmpdir, token_path, "https://www.googleapis.com/auth/calendar.readonly")

            with patch("rebalance.cli.GOOGLE_CALENDAR_ENV_PATH", env_path):
                result = self.runner.invoke(
                    app,
                    [
                        "calendar-create-event",
                        "--title",
                        "Needs scope",
                        "--date",
                        "2026-04-21",
                        "--dry-run",
                    ],
                )

        self.assertNotEqual(result.exit_code, 0)
        error_output = result.stderr or result.output
        self.assertIn("missing the required write scope", error_output)
        self.assertIn("setup_calendar_oauth.py --write-access", error_output)
        self.assertIn("--test", error_output)

    def test_duplicate_event_blocks_create_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = self._write_token(tmpdir, ["https://www.googleapis.com/auth/calendar"])
            env_path = self._write_env(tmpdir, token_path, "https://www.googleapis.com/auth/calendar")
            log_path = Path(tmpdir) / "calendar-event-create.jsonl"

            with (
                patch("rebalance.cli.GOOGLE_CALENDAR_ENV_PATH", env_path),
                patch("rebalance.cli.CALENDAR_EVENT_LOG_PATH", log_path),
                patch("rebalance.cli._find_existing_calendar_event", return_value={"event_id": "evt-1", "html_link": "https://example.com/e/1"}),
                patch("rebalance.ingest.calendar.create_calendar_event") as mock_create,
            ):
                result = self.runner.invoke(
                    app,
                    [
                        "calendar-create-event",
                        "--title",
                        "Duplicate",
                        "--date",
                        "2026-04-21",
                    ],
                )
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("Matching event already exists: evt-1", result.output)
                mock_create.assert_not_called()
                lines = log_path.read_text(encoding="utf-8").splitlines()
                self.assertEqual(json.loads(lines[-1])["action"], "blocked_duplicate")

    def test_skip_if_exists_returns_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = self._write_token(tmpdir, ["https://www.googleapis.com/auth/calendar"])
            env_path = self._write_env(tmpdir, token_path, "https://www.googleapis.com/auth/calendar")
            log_path = Path(tmpdir) / "calendar-event-create.jsonl"

            with (
                patch("rebalance.cli.GOOGLE_CALENDAR_ENV_PATH", env_path),
                patch("rebalance.cli.CALENDAR_EVENT_LOG_PATH", log_path),
                patch("rebalance.cli._find_existing_calendar_event", return_value={"event_id": "evt-2", "html_link": "https://example.com/e/2"}),
                patch("rebalance.ingest.calendar.create_calendar_event") as mock_create,
            ):
                result = self.runner.invoke(
                    app,
                    [
                        "calendar-create-event",
                        "--title",
                        "Duplicate",
                        "--date",
                        "2026-04-21",
                        "--skip-if-exists",
                        "--output",
                        "json",
                    ],
                )
                self.assertEqual(result.exit_code, 0)
                payload = json.loads(result.output)
                self.assertEqual(payload["status"], "skipped_existing")
                self.assertEqual(payload["event_id"], "evt-2")
                mock_create.assert_not_called()
                lines = log_path.read_text(encoding="utf-8").splitlines()
                self.assertEqual(json.loads(lines[-1])["action"], "skipped_existing")

    def test_dedupe_key_short_circuits_repeat_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = self._write_token(tmpdir, ["https://www.googleapis.com/auth/calendar"])
            env_path = self._write_env(tmpdir, token_path, "https://www.googleapis.com/auth/calendar")
            log_path = Path(tmpdir) / "calendar-event-create.jsonl"
            log_path.write_text(
                json.dumps(
                    {
                        "action": "created",
                        "dedupe_key": "binoid-cleanup-2026-04-21",
                        "event_id": "evt-3",
                        "html_link": "https://example.com/e/3",
                    }
                ) + "\n",
                encoding="utf-8",
            )

            with (
                patch("rebalance.cli.GOOGLE_CALENDAR_ENV_PATH", env_path),
                patch("rebalance.cli.CALENDAR_EVENT_LOG_PATH", log_path),
                patch("rebalance.cli._find_existing_calendar_event") as mock_find_existing,
                patch("rebalance.ingest.calendar.create_calendar_event") as mock_create,
            ):
                result = self.runner.invoke(
                    app,
                    [
                        "calendar-create-event",
                        "--title",
                        "Duplicate",
                        "--date",
                        "2026-04-21",
                        "--dedupe-key",
                        "binoid-cleanup-2026-04-21",
                        "--output",
                        "json",
                    ],
                )
                self.assertEqual(result.exit_code, 0)
                payload = json.loads(result.output)
                self.assertEqual(payload["status"], "idempotency_hit")
                self.assertEqual(payload["event_id"], "evt-3")
                self.assertEqual(payload["dedupe_key"], "binoid-cleanup-2026-04-21")
                mock_find_existing.assert_not_called()
                mock_create.assert_not_called()
                lines = log_path.read_text(encoding="utf-8").splitlines()
                self.assertEqual(json.loads(lines[-1])["action"], "idempotency_hit")


if __name__ == "__main__":
    unittest.main()
