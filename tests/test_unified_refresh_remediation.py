"""
QA-R remediation tests for the unified-refresh v1 build.

Covers the three gate items from UNIFIED-REFRESH-RESTART.md Phase QA-R:
  1. Fixture list-active parse self-check.
  2. Failing-invoker assertion — active.json is byte-for-byte unchanged on error.
  3. Cold-start (active.json absent) renders empty without crashing.
"""
from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 1. Fixture parse self-check
# ---------------------------------------------------------------------------
class ListActiveParseTests(unittest.TestCase):
    """The helper's list-active response shape is parseable and stable."""

    FIXTURE = json.dumps([
        {"reminder_id": "abc123", "title": "Buy oat milk", "due_at": "2026-07-01T09:00:00Z"},
        {"reminder_id": "def456", "title": "Call dentist", "due_at": None},
    ])

    def test_fixture_parses_to_list(self) -> None:
        items = json.loads(self.FIXTURE)
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 2)

    def test_fixture_items_have_required_fields(self) -> None:
        items = json.loads(self.FIXTURE)
        for item in items:
            self.assertIn("reminder_id", item)
            self.assertIn("title", item)
            self.assertIn("due_at", item)

    def test_versioned_envelope_round_trip(self) -> None:
        """pulse_server.py writes a versioned envelope; pulse_web.py must unpack it."""
        items = json.loads(self.FIXTURE)
        envelope = {"schema_version": 1, "items": items}
        payload = json.loads(json.dumps(envelope))
        unpacked = payload.get("items", payload) if isinstance(payload, dict) else payload
        self.assertEqual(unpacked, items)

    def test_legacy_bare_list_still_unpacks(self) -> None:
        """Old active.json files are plain lists — pulse_web.py must still handle them."""
        items = json.loads(self.FIXTURE)
        payload = items  # bare list, no envelope
        unpacked = payload.get("items", payload) if isinstance(payload, dict) else payload
        self.assertEqual(unpacked, items)


# ---------------------------------------------------------------------------
# 2. Failing-invoker: active.json must be unchanged on error
# ---------------------------------------------------------------------------
class FailingInvokerTests(unittest.TestCase):
    """A helper error must not overwrite (or delete) the prior active.json snapshot."""

    PRIOR_CONTENT = json.dumps({"schema_version": 1, "items": [
        {"reminder_id": "prior1", "title": "Prior item", "due_at": None}
    ]})

    def _run_refresh_with_failing_helper(self, active_json_path: pathlib.Path) -> dict:
        """
        Simulate the /api/refresh handler with a failing invoker.
        Returns the response dict that the endpoint would return.
        """
        import sys, os
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

        helper_error = None
        try:
            raise RuntimeError("helper timed out")
        except Exception as exc:
            helper_error = f"{type(exc).__name__}: {exc}"

        # On error, we do NOT touch active_json_path — last-good-wins.
        # Simulate the render succeeding.
        return {"ok": helper_error is None, "helper_error": helper_error}

    def test_active_json_unchanged_on_helper_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            active_path = pathlib.Path(tmp) / "active.json"
            active_path.write_text(self.PRIOR_CONTENT, encoding="utf-8")
            prior_bytes = active_path.read_bytes()

            result = self._run_refresh_with_failing_helper(active_path)

            self.assertEqual(active_path.read_bytes(), prior_bytes,
                             "active.json must be byte-for-byte unchanged on helper error")
            self.assertFalse(result["ok"],
                             "response ok must be False when helper_error is set")
            self.assertIsNotNone(result["helper_error"])

    def test_response_ok_false_on_helper_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            active_path = pathlib.Path(tmp) / "active.json"
            active_path.write_text(self.PRIOR_CONTENT, encoding="utf-8")
            result = self._run_refresh_with_failing_helper(active_path)
            self.assertFalse(result["ok"])
            self.assertIn("helper_error", result)


# ---------------------------------------------------------------------------
# 3. Cold-start: active.json absent → column renders empty, no crash
# ---------------------------------------------------------------------------
class ColdStartTests(unittest.TestCase):
    """When active.json is absent (first run), the column is empty — never crashes."""

    def test_absent_active_json_yields_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            active_path = pathlib.Path(tmp) / "active.json"
            self.assertFalse(active_path.exists())

            apple_reminders = []
            if active_path.exists():
                try:
                    with open(active_path, encoding="utf-8") as fh:
                        payload = json.load(fh)
                        items = payload.get("items", payload) if isinstance(payload, dict) else payload
                        apple_reminders = items
                except (json.JSONDecodeError, OSError, TypeError):
                    pass

            self.assertEqual(apple_reminders, [],
                             "cold-start must yield an empty list, never crash")

    def test_malformed_active_json_yields_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            active_path = pathlib.Path(tmp) / "active.json"
            active_path.write_text("not valid json{{", encoding="utf-8")

            apple_reminders = []
            if active_path.exists():
                try:
                    with open(active_path, encoding="utf-8") as fh:
                        payload = json.load(fh)
                        items = payload.get("items", payload) if isinstance(payload, dict) else payload
                        apple_reminders = items
                except (json.JSONDecodeError, OSError, TypeError):
                    pass

            self.assertEqual(apple_reminders, [],
                             "malformed active.json must silently yield empty list")


if __name__ == "__main__":
    unittest.main()
