"""CLI tests for `rebalance apple-reminders *` (Phase 5.1 write-back).

These patch the orchestrator (`apply_reminder_writes`) so they exercise the CLI
wiring — flag parsing, plan/apply defaults, --yes -> confirm_destructive, request
shaping — without launching the real macOS helper.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from typer.testing import CliRunner

from rebalance.cli import app
from rebalance.ingest.apple_reminders_write import WriteOpResult, WriteResult


def _fake_result(request):
    return WriteResult(
        request_id=request["request_id"],
        mode=request["mode"],
        state="reconciled_locally" if request["mode"] == "apply" else "skipped",
        host_runtime="com.test.helper",
        authorization_status="authorized",
        results=[
            WriteOpResult(op=o["op"], status="ok", client_token=o.get("client_token"),
                          reminder_id=o.get("reminder_id") or "RID-NEW", readback_ok=True,
                          detail="ok")
            for o in request["operations"]
        ],
        started_at="t0",
        finished_at="t1",
    )


class AppleRemindersWriteCliTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "index.db"
        sqlite3.connect(self.db).close()  # valid empty DB so resolver accepts it

    def tearDown(self):
        self._tmp.cleanup()

    def _patch(self):
        # capture the request the CLI built; return a canned success
        captured = {}

        def fake(db_path, request, **kwargs):
            captured["db_path"] = db_path
            captured["request"] = request
            return _fake_result(request)

        return mock.patch(
            "rebalance.cli.apple_reminders.apply_reminder_writes", side_effect=fake
        ), captured

    def test_help_lists_subcommands(self):
        result = self.runner.invoke(app, ["apple-reminders", "--help"])
        self.assertEqual(result.exit_code, 0)
        for sub in ("create", "update", "complete", "delete", "audit"):
            self.assertIn(sub, result.output)

    def test_create_defaults_to_plan(self):
        patcher, captured = self._patch()
        with patcher, mock.patch(
            "rebalance.ingest.config.get_apple_reminders_list_name",
            return_value="Reminders",
        ):
            result = self.runner.invoke(
                app, ["apple-reminders", "create", "--title", "buy milk",
                      "--database", str(self.db)],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        req = captured["request"]
        self.assertEqual(req["mode"], "plan")
        self.assertEqual(req["operations"][0]["op"], "create")
        self.assertEqual(req["operations"][0]["list_name"], "Reminders")
        self.assertEqual(req["operations"][0]["fields"]["title"], "buy milk")

    def test_create_apply_sets_apply_mode(self):
        patcher, captured = self._patch()
        with patcher, mock.patch(
            "rebalance.ingest.config.get_apple_reminders_list_name",
            return_value="Reminders",
        ):
            result = self.runner.invoke(
                app, ["apple-reminders", "create", "--title", "x", "--apply",
                      "--database", str(self.db)],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(captured["request"]["mode"], "apply")

    def test_complete_builds_complete_op(self):
        patcher, captured = self._patch()
        with patcher:
            result = self.runner.invoke(
                app, ["apple-reminders", "complete", "RID-9", "--database", str(self.db)],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        op = captured["request"]["operations"][0]
        self.assertEqual(op["op"], "complete")
        self.assertEqual(op["reminder_id"], "RID-9")

    def test_delete_yes_sets_confirm_destructive(self):
        patcher, captured = self._patch()
        with patcher:
            result = self.runner.invoke(
                app, ["apple-reminders", "delete", "RID-2", "--apply", "--yes",
                      "--database", str(self.db)],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(captured["request"]["confirm_destructive"])

    def test_delete_without_yes_leaves_confirm_false(self):
        patcher, captured = self._patch()
        with patcher:
            self.runner.invoke(
                app, ["apple-reminders", "delete", "RID-2", "--apply",
                      "--database", str(self.db)],
            )
        # CLI builds the request; the real orchestrator would reject it, but here
        # we assert the CLI did NOT silently set confirm.
        self.assertFalse(captured["request"]["confirm_destructive"])

    def test_update_with_no_fields_errors(self):
        result = self.runner.invoke(
            app, ["apple-reminders", "update", "RID-3", "--database", str(self.db)],
        )
        self.assertEqual(result.exit_code, 2)
        self.assertIn("at least one", result.output)

    def test_audit_on_empty_db_returns_empty(self):
        result = self.runner.invoke(
            app, ["apple-reminders", "audit", "--database", str(self.db)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("[]", result.output)


if __name__ == "__main__":
    unittest.main()
