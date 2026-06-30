"""Tests for the Apple Reminders write-back orchestrator (Phase 5.1).

The orchestrator delegates the actual EventKit mutation to an out-of-process
signed helper bundle that only runs on macOS with a TCC grant. These tests inject
a FAKE invoker (and a fake reconcile fn) so the full orchestrator — scope,
confirmation gating, audit lifecycle, idempotency, partial failure — is exercised
headlessly on any platform, no macOS / EventKit / Full Disk Access required.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.apple_reminders_write import (
    STATE_APPLIED,
    STATE_FAILED,
    STATE_RECONCILED,
    STATE_SKIPPED,
    WRITE_SCHEMA_VERSION,
    AppleRemindersConfirmationError,
    AppleRemindersHelperError,
    AppleRemindersWriteScopeError,
    WriteOp,
    apply_reminder_writes,
    build_request,
    ensure_apple_reminders_write_schema,
)
from rebalance.ingest.db import db_connection

LIST = "Reminders"


def _resp(request, *, results, auth="authorized", host="com.test.helper"):
    """Build a wire response dict matching a request."""
    return {
        "schema_version": WRITE_SCHEMA_VERSION,
        "request_id": request["request_id"],
        "mode": request["mode"],
        "host_runtime": host,
        "authorization_status": auth,
        "started_at": "2026-06-27T00:00:00Z",
        "finished_at": "2026-06-27T00:00:01Z",
        "results": results,
    }


def _ok_create(client_token, reminder_id):
    return {
        "op": "create",
        "client_token": client_token,
        "reminder_id": reminder_id,
        "status": "ok",
        "readback_ok": True,
        "detail": "created",
    }


class _Recorder:
    """A fake invoker that echoes a canned response and counts calls."""

    def __init__(self, response_fn):
        self.calls = 0
        self._response_fn = response_fn
        self.last_request = None

    def __call__(self, request):
        self.calls += 1
        self.last_request = request
        return self._response_fn(request)


class WriteOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "index.db"

    def tearDown(self):
        self._tmp.cleanup()

    def _audit_rows(self):
        with db_connection(self.db, ensure_apple_reminders_write_schema) as conn:
            return conn.execute(
                "SELECT request_id, op_index, op, reminder_id, state, op_status, "
                "request_json, response_json FROM apple_reminders_write_audit "
                "ORDER BY op_index"
            ).fetchall()

    # --- scope ----------------------------------------------------------------

    def test_create_to_foreign_list_is_rejected(self):
        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name="Groceries",
                     fields={"title": "milk"})],
            mode="apply",
        )
        with self.assertRaises(AppleRemindersWriteScopeError):
            apply_reminder_writes(self.db, req, list_name=LIST,
                                  invoker=lambda r: {}, reconcile_fn=lambda: None)

    def test_create_to_configured_list_is_allowed(self):
        inv = _Recorder(lambda r: _resp(r, results=[_ok_create("c1", "RID-1")]))
        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name=LIST,
                     fields={"title": "milk"})],
            mode="apply",
        )
        res = apply_reminder_writes(self.db, req, list_name=LIST, invoker=inv,
                                    reconcile_fn=lambda: None)
        self.assertTrue(res.ok)
        self.assertEqual(inv.calls, 1)

    def test_complete_and_delete_are_not_scope_checked(self):
        inv = _Recorder(lambda r: _resp(r, results=[
            {"op": "complete", "reminder_id": "RID-9", "status": "ok",
             "readback_ok": True, "detail": ""}]))
        req = build_request([WriteOp(op="complete", reminder_id="RID-9")],
                            mode="apply")
        res = apply_reminder_writes(self.db, req, list_name=LIST, invoker=inv,
                                    reconcile_fn=lambda: None)
        self.assertTrue(res.ok)

    # --- confirmation ---------------------------------------------------------

    def test_apply_delete_without_confirm_raises(self):
        req = build_request([WriteOp(op="delete", reminder_id="RID-2")],
                            mode="apply", confirm_destructive=False)
        with self.assertRaises(AppleRemindersConfirmationError):
            apply_reminder_writes(self.db, req, list_name=LIST,
                                  invoker=lambda r: {}, reconcile_fn=lambda: None)

    def test_apply_delete_with_confirm_proceeds(self):
        inv = _Recorder(lambda r: _resp(r, results=[
            {"op": "delete", "reminder_id": "RID-2", "status": "ok",
             "readback_ok": True, "detail": "deleted"}]))
        req = build_request([WriteOp(op="delete", reminder_id="RID-2")],
                            mode="apply", confirm_destructive=True)
        res = apply_reminder_writes(self.db, req, list_name=LIST, invoker=inv,
                                    reconcile_fn=lambda: None)
        self.assertTrue(res.ok)
        self.assertEqual(inv.calls, 1)

    def test_plan_delete_does_not_require_confirm(self):
        inv = _Recorder(lambda r: _resp(r, results=[
            {"op": "delete", "reminder_id": "RID-2", "status": "ok",
             "readback_ok": False, "detail": "would delete"}]))
        req = build_request([WriteOp(op="delete", reminder_id="RID-2")],
                            mode="plan")
        res = apply_reminder_writes(self.db, req, list_name=LIST, invoker=inv,
                                    reconcile_fn=lambda: None)
        self.assertEqual(res.state, STATE_SKIPPED)

    # --- plan vs apply / reconcile -------------------------------------------

    def test_plan_does_not_reconcile(self):
        reconciled = {"n": 0}

        def recon():
            reconciled["n"] += 1

        inv = _Recorder(lambda r: _resp(r, results=[_ok_create("c1", "RID-3")]))
        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name=LIST,
                     fields={"title": "x"})],
            mode="plan",
        )
        res = apply_reminder_writes(self.db, req, list_name=LIST, invoker=inv,
                                    reconcile_fn=recon)
        self.assertEqual(res.state, STATE_SKIPPED)
        self.assertFalse(res.reconciled)
        self.assertEqual(reconciled["n"], 0)

    def test_apply_success_reconciles(self):
        reconciled = {"n": 0}

        def recon():
            reconciled["n"] += 1

        inv = _Recorder(lambda r: _resp(r, results=[_ok_create("c1", "RID-4")]))
        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name=LIST,
                     fields={"title": "x"})],
            mode="apply",
        )
        res = apply_reminder_writes(self.db, req, list_name=LIST, invoker=inv,
                                    reconcile_fn=recon)
        self.assertTrue(res.reconciled)
        self.assertEqual(res.state, STATE_RECONCILED)
        self.assertEqual(reconciled["n"], 1)

    def test_reconcile_failure_keeps_write_recorded(self):
        def recon():
            raise RuntimeError("FDA missing on this host")

        inv = _Recorder(lambda r: _resp(r, results=[_ok_create("c1", "RID-5")]))
        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name=LIST,
                     fields={"title": "x"})],
            mode="apply",
        )
        res = apply_reminder_writes(self.db, req, list_name=LIST, invoker=inv,
                                    reconcile_fn=recon)
        # The write itself succeeded; reconcile is best-effort.
        self.assertTrue(res.ok)
        self.assertFalse(res.reconciled)
        self.assertEqual(res.state, STATE_APPLIED)

    # --- idempotency ----------------------------------------------------------

    def test_replay_of_applied_request_does_not_reinvoke(self):
        inv = _Recorder(lambda r: _resp(r, results=[_ok_create("c1", "RID-6")]))
        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name=LIST,
                     fields={"title": "x"})],
            mode="apply",
        )
        first = apply_reminder_writes(self.db, req, list_name=LIST, invoker=inv,
                                      reconcile_fn=lambda: None)
        self.assertEqual(inv.calls, 1)

        # Replay the SAME request_id with an invoker that would explode if called.
        def explode(r):
            raise AssertionError("helper must not be re-invoked on replay")

        second = apply_reminder_writes(self.db, req, list_name=LIST,
                                       invoker=explode, reconcile_fn=lambda: None)
        self.assertEqual(inv.calls, 1)  # unchanged
        self.assertEqual(second.request_id, first.request_id)
        self.assertEqual(second.results[0].reminder_id, "RID-6")

    def test_failed_request_is_retryable(self):
        # A request that applied nothing (auth denied) is NOT cached as done.
        denied = _Recorder(lambda r: _resp(
            r, auth="denied",
            results=[{"op": "create", "client_token": "c1", "reminder_id": None,
                      "status": "error", "readback_ok": False,
                      "detail": "not authorized"}]))
        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name=LIST,
                     fields={"title": "x"})],
            mode="apply",
        )
        res1 = apply_reminder_writes(self.db, req, list_name=LIST, invoker=denied,
                                     reconcile_fn=lambda: None)
        self.assertFalse(res1.ok)
        self.assertEqual(res1.state, STATE_FAILED)

        # Retry with the same id now succeeds and DOES re-invoke (not cached).
        ok = _Recorder(lambda r: _resp(r, results=[_ok_create("c1", "RID-7")]))
        res2 = apply_reminder_writes(self.db, req, list_name=LIST, invoker=ok,
                                     reconcile_fn=lambda: None)
        self.assertEqual(ok.calls, 1)
        self.assertTrue(res2.ok)

    # --- partial failure ------------------------------------------------------

    def test_partial_failure_reports_per_op_and_still_reconciles(self):
        reconciled = {"n": 0}

        def recon():
            reconciled["n"] += 1

        def response(r):
            return _resp(r, results=[
                _ok_create("c1", "RID-8"),
                {"op": "update", "reminder_id": "RID-MISSING", "status": "error",
                 "readback_ok": False, "detail": "no such reminder"},
            ])

        req = build_request(
            [
                WriteOp(op="create", client_token="c1", list_name=LIST,
                        fields={"title": "x"}),
                WriteOp(op="update", reminder_id="RID-MISSING",
                        fields={"title": "y"}),
            ],
            mode="apply",
        )
        res = apply_reminder_writes(self.db, req, list_name=LIST,
                                    invoker=_Recorder(response), reconcile_fn=recon)
        self.assertFalse(res.ok)  # one op errored
        self.assertEqual(reconciled["n"], 1)  # but one applied -> still reconcile
        statuses = {r.op: r.status for r in res.results}
        self.assertEqual(statuses["create"], "ok")
        self.assertEqual(statuses["update"], "error")

    # --- helper failures ------------------------------------------------------

    def test_helper_launch_failure_records_failed_and_raises(self):
        def boom(r):
            raise AppleRemindersHelperError("bundle not found")

        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name=LIST,
                     fields={"title": "x"})],
            mode="apply",
        )
        with self.assertRaises(AppleRemindersHelperError):
            apply_reminder_writes(self.db, req, list_name=LIST, invoker=boom,
                                  reconcile_fn=lambda: None)
        rows = self._audit_rows()
        self.assertTrue(rows)
        self.assertEqual(rows[0][4], STATE_FAILED)  # state column

    def test_response_request_id_mismatch_raises(self):
        def wrong_id(r):
            resp = _resp(r, results=[_ok_create("c1", "RID-X")])
            resp["request_id"] = "TOTALLY-DIFFERENT"
            return resp

        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name=LIST,
                     fields={"title": "x"})],
            mode="apply",
        )
        with self.assertRaises(AppleRemindersHelperError):
            apply_reminder_writes(self.db, req, list_name=LIST, invoker=wrong_id,
                                  reconcile_fn=lambda: None)

    def test_schema_version_mismatch_raises(self):
        def bad_version(r):
            resp = _resp(r, results=[_ok_create("c1", "RID-X")])
            resp["schema_version"] = 999
            return resp

        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name=LIST,
                     fields={"title": "x"})],
            mode="apply",
        )
        with self.assertRaises(AppleRemindersHelperError):
            apply_reminder_writes(self.db, req, list_name=LIST,
                                  invoker=bad_version, reconcile_fn=lambda: None)

    # --- audit ----------------------------------------------------------------

    def test_audit_rows_capture_blobs_and_reminder_id(self):
        inv = _Recorder(lambda r: _resp(r, results=[_ok_create("c1", "RID-AUD")]))
        req = build_request(
            [WriteOp(op="create", client_token="c1", list_name=LIST,
                     fields={"title": "audit me"})],
            mode="apply",
        )
        apply_reminder_writes(self.db, req, list_name=LIST, invoker=inv,
                              reconcile_fn=lambda: None)
        rows = self._audit_rows()
        self.assertEqual(len(rows), 1)
        (request_id, op_index, op, reminder_id, state, op_status,
         request_json, response_json) = rows[0]
        self.assertEqual(op, "create")
        self.assertEqual(reminder_id, "RID-AUD")
        self.assertEqual(state, STATE_RECONCILED)
        self.assertEqual(op_status, "ok")
        self.assertIn("audit me", request_json)
        self.assertIn("RID-AUD", response_json)

    # --- request building -----------------------------------------------------

    def test_build_request_rejects_bad_op(self):
        with self.assertRaises(Exception):
            build_request([WriteOp(op="frobnicate")], mode="apply")

    def test_build_request_rejects_bad_mode(self):
        with self.assertRaises(Exception):
            build_request([WriteOp(op="create", client_token="c1",
                                   list_name=LIST)], mode="sideways")


if __name__ == "__main__":
    unittest.main()
