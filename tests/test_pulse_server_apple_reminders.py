"""Regression tests for the Phase 6 dashboard Apple Reminders write-back —
`POST /api/apple-reminders/complete` on the local pulse server.

Pins the contract from APPLE-REMINDERS-UNIFIED-PLAN.md Phase 6:
  * the endpoint builds exactly ONE `complete` op for the given reminder_id,
    in `apply` mode, and routes it through the Phase 5.1 orchestrator
    (`apply_reminder_writes`) — single-writer + audit preserved;
  * a helper / auth failure surfaces as a non-2xx so the row never falsely
    shows "done";
  * the web layer holds no EventKit/SQLite write code of its own.

Headless: `apply_reminder_writes` is patched, so no macOS / EventKit / helper
bundle is needed. Mirrors tests/test_pulse_server_figma.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pulse_server  # noqa: E402

from rebalance.ingest.apple_reminders_write import (  # noqa: E402
    AppleRemindersHelperError,
    WriteOpResult,
    WriteResult,
)


def _result(*, status: str, reminder_id: str) -> WriteResult:
    """A WriteResult shaped like the orchestrator's, for a single complete op."""
    return WriteResult(
        request_id="req-test",
        mode="apply",
        state="applied_in_eventkit" if status == "ok" else "failed",
        host_runtime="com.rebalanceos.apple-reminders-helper",
        authorization_status="authorized",
        results=[
            WriteOpResult(
                op="complete",
                status=status,
                reminder_id=reminder_id,
                readback_ok=(status == "ok"),
                detail="" if status == "ok" else "auth denied",
            )
        ],
        started_at="t0",
        finished_at="t1",
    )


class AppleRemindersCompleteApiTests(unittest.TestCase):
    def test_builds_single_complete_op_and_applies(self) -> None:
        captured: dict = {}

        def fake_apply(db_path, request, **kwargs):
            captured["db_path"] = db_path
            captured["request"] = request
            captured["kwargs"] = kwargs
            return _result(status="ok", reminder_id="R-1")

        client = TestClient(pulse_server.app)
        with patch.object(pulse_server, "apply_reminder_writes", side_effect=fake_apply), \
             patch.object(pulse_server, "resolve_database_path", return_value=Path("/tmp/rebalance.db")):
            res = client.post(
                "/api/apple-reminders/complete",
                json={"reminder_id": "R-1", "title": "Buy milk"},
            )

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["results"][0]["status"], "ok")

        # The wire request is the REAL build_request output (not mocked).
        req = captured["request"]
        self.assertEqual(req["mode"], "apply")
        self.assertEqual(
            req["operations"],
            [{"op": "complete", "reminder_id": "R-1"}],
            "must be exactly one complete op for the requested id",
        )
        # Reconcile is deferred to the next scoped sync (FDA-gated host).
        self.assertEqual(captured["kwargs"].get("reconcile"), False)

    def test_missing_reminder_id_returns_400(self) -> None:
        client = TestClient(pulse_server.app)
        with patch.object(pulse_server, "apply_reminder_writes") as apply_mock, \
             patch.object(pulse_server, "resolve_database_path", return_value=Path("/tmp/rebalance.db")):
            res = client.post("/api/apple-reminders/complete", json={"reminder_id": "   "})
        self.assertEqual(res.status_code, 400)
        apply_mock.assert_not_called()  # never reaches the writer

    def test_helper_failure_surfaces_as_502(self) -> None:
        client = TestClient(pulse_server.app)
        with patch.object(
            pulse_server,
            "apply_reminder_writes",
            side_effect=AppleRemindersHelperError("helper not built / not granted"),
        ), patch.object(pulse_server, "resolve_database_path", return_value=Path("/tmp/rebalance.db")):
            res = client.post("/api/apple-reminders/complete", json={"reminder_id": "R-9"})
        self.assertEqual(res.status_code, 502)

    def test_per_op_error_surfaces_non_2xx(self) -> None:
        client = TestClient(pulse_server.app)
        with patch.object(
            pulse_server,
            "apply_reminder_writes",
            return_value=_result(status="error", reminder_id="R-2"),
        ), patch.object(pulse_server, "resolve_database_path", return_value=Path("/tmp/rebalance.db")):
            res = client.post("/api/apple-reminders/complete", json={"reminder_id": "R-2"})
        self.assertEqual(res.status_code, 502)  # row must not falsely show done
        self.assertEqual(res.json()["results"][0]["status"], "error")

    def test_web_layer_holds_no_direct_eventkit_or_sqlite_write(self) -> None:
        """QA: every dashboard write flows through the orchestrator; the web
        layer carries no EventKit/private-framework or raw reminder-table write."""
        src = (SCRIPTS_DIR / "pulse_server.py").read_text(encoding="utf-8")
        self.assertIn("apply_reminder_writes", src)  # delegates to the one writer
        for forbidden in (
            "EKEventStore",
            "import EventKit",
            "INSERT INTO apple_reminders",
            "UPDATE apple_reminders",
        ):
            self.assertNotIn(forbidden, src, f"web layer must not contain {forbidden!r}")


if __name__ == "__main__":
    unittest.main()
