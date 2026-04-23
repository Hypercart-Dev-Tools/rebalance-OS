"""Tests for the Sleuth reminders ingestor."""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from rebalance.ingest.sleuth_reminders import (
    SleuthApiError,
    sync_sleuth_reminders,
)


def _fixture_reminder(**overrides):
    base = {
        "reminderId": "R-001",
        "state": "scheduled",
        "isActive": True,
        "createdOn": "2026-04-20T09:00:00Z",
        "shouldPostOn": "2026-04-22T15:30:00Z",
        "reminderMessageText": "Review the Binoid PR",
        "ignoreSnooze": False,
        "assigneeId": "U123",
        "originalSenderId": "U999",
        "targetChannelId": "C1",
        "originalChannelId": "C2",
        "originalChannelName": "eng",
        "originalMessageId": "1234567.890",
        "originalThreadTs": None,
        "githubUrls": ["https://github.com/foo/bar/pull/42"],
    }
    base.update(overrides)
    return base


def _success_payload(reminders=None):
    if reminders is None:
        reminders = [_fixture_reminder()]
    return {
        "success": True,
        "data": {
            "workspaceName": "neochrome-dev",
            "fetchedAt": "2026-04-22T10:00:00Z",
            "totalReminderCount": len(reminders),
            "returnedReminderCount": len(reminders),
            "filters": {"activeOnly": False, "states": []},
            "source": {"type": "sleuth-reminders-file", "relativePath": "r.json"},
            "reminders": reminders,
        },
    }


class _FakeResponse:
    """Minimal stand-in for the object returned by urllib.request.urlopen."""

    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


class SleuthRemindersTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.db_path = Path(self._tmpdir.name) / "rebalance.db"

    def _patched_urlopen(self, payload: dict):
        return patch(
            "rebalance.ingest.sleuth_reminders.urllib.request.urlopen",
            return_value=_FakeResponse(json.dumps(payload)),
        )

    def _run_sync(self, payload: dict, *, active_only: bool = False):
        with self._patched_urlopen(payload):
            return sync_sleuth_reminders(
                base_url="http://example.test",
                token="not-a-real-token",
                workspace_name="neochrome-dev",
                database_path=self.db_path,
                active_only=active_only,
            )

    # --- Insert / unchanged / update -------------------------------------

    def test_first_sync_inserts_row(self) -> None:
        result = self._run_sync(_success_payload())
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.updated_count, 0)
        self.assertEqual(result.unchanged_count, 0)
        self.assertEqual(result.returned_reminder_count, 1)
        self.assertEqual(result.workspace_name, "neochrome-dev")

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT state, is_active, github_urls_json "
                "FROM sleuth_reminders WHERE reminder_id = 'R-001'"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "scheduled")
        self.assertEqual(row[1], 1)
        self.assertEqual(
            json.loads(row[2]),
            ["https://github.com/foo/bar/pull/42"],
        )

    def test_repeat_sync_marks_unchanged(self) -> None:
        self._run_sync(_success_payload())
        result = self._run_sync(_success_payload())
        self.assertEqual(result.inserted_count, 0)
        self.assertEqual(result.updated_count, 0)
        self.assertEqual(result.unchanged_count, 1)

    def test_state_change_updates_and_preserves_first_seen_at(self) -> None:
        self._run_sync(_success_payload())
        with sqlite3.connect(self.db_path) as conn:
            original_first_seen = conn.execute(
                "SELECT first_seen_at FROM sleuth_reminders WHERE reminder_id = 'R-001'"
            ).fetchone()[0]

        mutated = _success_payload(
            reminders=[_fixture_reminder(state="overdue", isActive=True)]
        )
        result = self._run_sync(mutated)
        self.assertEqual(result.inserted_count, 0)
        self.assertEqual(result.updated_count, 1)
        self.assertEqual(result.unchanged_count, 0)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT state, first_seen_at, last_seen_at, last_synced_at "
                "FROM sleuth_reminders WHERE reminder_id = 'R-001'"
            ).fetchone()
        self.assertEqual(row[0], "overdue")
        self.assertEqual(row[1], original_first_seen)
        # last_seen_at / last_synced_at should have advanced (or at least not regressed)
        self.assertGreaterEqual(row[2], original_first_seen)
        self.assertGreaterEqual(row[3], original_first_seen)

    # --- Error paths ------------------------------------------------------

    def test_success_false_raises_sleuth_api_error(self) -> None:
        failure_payload = {"success": False, "data": "Invalid bearer token"}
        with self.assertRaises(SleuthApiError) as ctx:
            self._run_sync(failure_payload)
        # Never include the bearer token in the error message.
        self.assertNotIn("not-a-real-token", str(ctx.exception))
        self.assertIn("Invalid bearer token", str(ctx.exception))

    def test_http_error_raises_sleuth_api_error(self) -> None:
        def _raise(*_args, **_kwargs):
            raise HTTPError(
                "http://example.test",
                500,
                "Server Error",
                {},
                io.BytesIO(b"boom"),
            )

        with patch(
            "rebalance.ingest.sleuth_reminders.urllib.request.urlopen",
            side_effect=_raise,
        ):
            with self.assertRaises(SleuthApiError) as ctx:
                sync_sleuth_reminders(
                    base_url="http://example.test",
                    token="not-a-real-token",
                    workspace_name="neochrome-dev",
                    database_path=self.db_path,
                )
        self.assertIn("500", str(ctx.exception))
        self.assertEqual(ctx.exception.status, 500)
        self.assertNotIn("not-a-real-token", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
