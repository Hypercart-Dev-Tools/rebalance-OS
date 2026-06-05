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
    _local_source_path,
    get_export_generated_at,
    sync_sleuth_reminders,
)


def _fixture_reminder(**overrides):
    base = {
        "reminderId": "R-001",
        "state": "scheduled",
        "isActive": True,
        "createdOn": "2026-04-20T09:00:00Z",
        "shouldPostOn": "2026-04-22T15:30:00Z",
        "reminderMessageText": "Review the AcmeCorp PR",
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


def _file_payload(
    reminders=None,
    *,
    workspace="neochrome-dev",
    active_only=True,
    source_type="sleuth-reminders-file",
    export_generated_at="2026-06-05T14:00:00.000Z",
):
    """The published-file shape: the API's `data` object (no {success,data} wrapper),
    with the active-only export contract the consumer validates."""
    if reminders is None:
        reminders = [_fixture_reminder()]
    payload = {
        "workspaceName": workspace,
        "totalReminderCount": len(reminders),
        "returnedReminderCount": len(reminders),
        "filters": {"activeOnly": active_only, "states": []},
        "source": {"type": source_type, "relativePath": "data/runtime/reminders/x.json"},
        "reminders": reminders,
    }
    if export_generated_at is not None:
        payload["exportGeneratedAt"] = export_generated_at
    return payload


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

    # --- Retire-on-disappearance reconciliation --------------------------

    def test_full_pull_retires_disappeared_rows(self) -> None:
        """active_only=False with a reminder missing from the response retires it."""
        self._run_sync(_success_payload())  # seeds R-001 is_active=1

        empty_payload = _success_payload(reminders=[])
        result = self._run_sync(empty_payload, active_only=False)
        self.assertEqual(result.retired_count, 1)
        self.assertEqual(result.inserted_count, 0)
        self.assertEqual(result.updated_count, 0)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT is_active, state FROM sleuth_reminders WHERE reminder_id = 'R-001'"
            ).fetchone()
        self.assertEqual(row[0], 0)
        self.assertEqual(row[1], "stale")

    def test_active_only_pull_does_not_retire_disappeared_rows(self) -> None:
        """active_only=True preserves history; missing rows stay is_active=1."""
        self._run_sync(_success_payload())

        empty_payload = _success_payload(reminders=[])
        result = self._run_sync(empty_payload, active_only=True)
        self.assertEqual(result.retired_count, 0)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT is_active, state FROM sleuth_reminders WHERE reminder_id = 'R-001'"
            ).fetchone()
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], "scheduled")

    def test_retire_is_idempotent(self) -> None:
        """Already-retired rows are not retired again on subsequent empty pulls."""
        self._run_sync(_success_payload())
        first = self._run_sync(_success_payload(reminders=[]), active_only=False)
        self.assertEqual(first.retired_count, 1)
        second = self._run_sync(_success_payload(reminders=[]), active_only=False)
        self.assertEqual(second.retired_count, 0)

    def test_retire_only_targets_disappeared_rows(self) -> None:
        """A row still in the response is left alone; only missing ones retire."""
        # Seed two reminders, then drop R-002 from the response.
        self._run_sync(
            _success_payload(
                reminders=[
                    _fixture_reminder(reminderId="R-001"),
                    _fixture_reminder(reminderId="R-002"),
                ]
            )
        )
        result = self._run_sync(
            _success_payload(
                reminders=[_fixture_reminder(reminderId="R-001", state="overdue")]
            )
        )
        self.assertEqual(result.retired_count, 1)
        with sqlite3.connect(self.db_path) as conn:
            kept = conn.execute(
                "SELECT is_active, state FROM sleuth_reminders WHERE reminder_id = 'R-001'"
            ).fetchone()
            retired = conn.execute(
                "SELECT is_active, state FROM sleuth_reminders WHERE reminder_id = 'R-002'"
            ).fetchone()
        self.assertEqual(kept, (1, "overdue"))
        self.assertEqual(retired, (0, "stale"))

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


class SleuthFileSourceTests(unittest.TestCase):
    """The published-file source: read a locally-synced rebalance JSON, no HTTP."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.db_path = self.root / "rebalance.db"
        self.export_path = self.root / "reminders-neochrome.json"
        self._write_export(_file_payload())

    def _write_export(self, payload: dict) -> None:
        self.export_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _sync(self, *, workspace="neochrome-dev"):
        return sync_sleuth_reminders(
            base_url=f"file://{self.export_path}",
            token="unused",
            workspace_name=workspace,
            database_path=self.db_path,
            active_only=True,
        )

    def test_local_source_path_detects_file_vs_http(self) -> None:
        # http(s) endpoints are NOT a file source.
        self.assertIsNone(_local_source_path("http://127.0.0.1:12020"))
        self.assertIsNone(_local_source_path("https://example.test/api"))
        # file:// URLs, absolute paths, and ~ paths are.
        self.assertEqual(_local_source_path("file:///tmp/x.json"), Path("/tmp/x.json"))
        self.assertEqual(_local_source_path("/abs/x.json"), Path("/abs/x.json"))
        self.assertEqual(
            _local_source_path("~/git-pulse-sync/r.json"),
            Path("~/git-pulse-sync/r.json").expanduser(),
        )

    def test_file_source_rejects_relative_path(self) -> None:
        with self.assertRaises(SleuthApiError) as ctx:
            sync_sleuth_reminders(
                base_url="file://relative/reminders.json",
                token="unused",
                workspace_name="neochrome",
                database_path=self.db_path,
                active_only=True,
            )
        self.assertIn("absolute", str(ctx.exception))

    def test_file_source_ingests_without_http(self) -> None:
        # urlopen must never be called for a file source.
        with patch(
            "rebalance.ingest.sleuth_reminders.urllib.request.urlopen",
            side_effect=AssertionError("HTTP must not be used for a file source"),
        ):
            result = self._sync()
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.workspace_name, "neochrome-dev")
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT is_active FROM sleuth_reminders WHERE reminder_id = 'R-001'"
            ).fetchone()
        self.assertEqual(row[0], 1)

    # --- contract validation: a bad payload must NOT reconcile/retire -----------

    def _assert_no_reconcile(self, payload, *, workspace="neochrome-dev", needle=""):
        """A contract violation must raise AND leave the DB untouched (no table/rows)."""
        self._write_export(payload)
        with self.assertRaises(SleuthApiError) as ctx:
            self._sync(workspace=workspace)
        if needle:
            self.assertIn(needle, str(ctx.exception))
        # No write should have happened — the sleuth_reminders table must not exist yet.
        with sqlite3.connect(self.db_path) as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sleuth_reminders'"
            ).fetchone()
        self.assertIsNone(tbl)

    def test_file_source_wrong_workspace_refuses(self) -> None:
        self._assert_no_reconcile(_file_payload(workspace="some-other-ws"), needle="workspace")

    def test_file_source_not_active_only_refuses(self) -> None:
        self._assert_no_reconcile(_file_payload(active_only=False), needle="activeOnly")

    def test_file_source_wrong_source_type_refuses(self) -> None:
        self._assert_no_reconcile(_file_payload(source_type="something-else"), needle="source.type")

    def test_file_source_non_dict_entry_refuses(self) -> None:
        payload = _file_payload(reminders=[_fixture_reminder(), "not-a-dict"])
        self._assert_no_reconcile(payload, needle="index 1")

    def test_file_source_missing_reminder_id_refuses(self) -> None:
        bad = _fixture_reminder()
        del bad["reminderId"]
        self._assert_no_reconcile(_file_payload(reminders=[bad]), needle="reminderId")

    def test_file_source_persists_export_heartbeat(self) -> None:
        self._write_export(_file_payload(export_generated_at="2026-06-05T14:00:00.000Z"))
        self._sync()
        beat = get_export_generated_at(self.db_path)
        self.assertIsNotNone(beat)
        self.assertEqual(beat.year, 2026)
        self.assertEqual(beat.hour, 14)

    def test_get_export_generated_at_absent_returns_none(self) -> None:
        # Fresh DB that has never synced — no heartbeat persisted.
        self.assertIsNone(get_export_generated_at(self.root / "never.db"))

    def test_file_source_missing_file_raises_clearly(self) -> None:
        with self.assertRaises(SleuthApiError) as ctx:
            sync_sleuth_reminders(
                base_url=f"file://{self.root / 'does-not-exist.json'}",
                token="unused",
                workspace_name="neochrome",
                database_path=self.db_path,
                active_only=True,
            )
        self.assertIn("not found", str(ctx.exception))

    def test_file_source_invalid_json_raises(self) -> None:
        self.export_path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(SleuthApiError) as ctx:
            sync_sleuth_reminders(
                base_url=f"file://{self.export_path}",
                token="unused",
                workspace_name="neochrome",
                database_path=self.db_path,
                active_only=True,
            )
        self.assertIn("invalid JSON", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
