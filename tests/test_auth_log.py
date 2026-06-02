"""Tests for the unified auth-activity log (ingest/auth_log.py).

Covers the post-unification behavior: the ``source`` field, the GitHub/Gmail
typed helpers, the generic ``log_event`` entry point, legacy calendar-file
merge in ``read_log``, and ``latest_failure_by_source`` (what the doctor will
use to surface "last auth failure" per integration).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest import auth_log


class AuthLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.log_dir = Path(self._tmp.name)
        # Redirect both the unified and legacy paths into the temp dir so the
        # real temp/logs/ is never touched.
        patcher = patch.object(auth_log, "_log_dir", return_value=self.log_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def _read_raw(self) -> list[dict]:
        path = self.log_dir / "auth_activity.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    # -- source field ------------------------------------------------------

    def test_calendar_helper_stamps_source(self) -> None:
        auth_log.log_flow_started(["scope.a"])
        rows = self._read_raw()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "calendar")
        self.assertEqual(rows[0]["event"], "flow_started")
        self.assertEqual(rows[0]["detail"]["scopes"], ["scope.a"])
        self.assertIn("ts", rows[0])
        self.assertIn("device", rows[0])

    def test_github_helpers_stamp_source_and_event(self) -> None:
        auth_log.log_github_token_validated("octocat", ["repo", "read:user"])
        auth_log.log_github_token_invalid(401)
        auth_log.log_github_auth_failed(401, endpoint="/user")
        rows = self._read_raw()
        self.assertEqual([r["source"] for r in rows], ["github"] * 3)
        self.assertEqual(
            [r["event"] for r in rows],
            ["token_validated", "token_invalid", "auth_failed"],
        )
        self.assertEqual(rows[0]["detail"]["login"], "octocat")
        self.assertEqual(rows[2]["detail"]["endpoint"], "/user")

    def test_gmail_helpers_stamp_source_and_event(self) -> None:
        auth_log.log_gmail_adc_missing("no ADC")
        auth_log.log_gmail_scope_insufficient("missing scope")
        rows = self._read_raw()
        self.assertEqual([r["source"] for r in rows], ["gmail", "gmail"])
        self.assertEqual(
            [r["event"] for r in rows], ["adc_missing", "scope_insufficient"]
        )

    def test_generic_log_event(self) -> None:
        auth_log.log_event("sleuth", "token_invalid", {"status": 403})
        rows = self._read_raw()
        self.assertEqual(rows[0]["source"], "sleuth")
        self.assertEqual(rows[0]["event"], "token_invalid")

    # -- readers -----------------------------------------------------------

    def test_read_log_newest_first(self) -> None:
        auth_log.log_flow_started(["a"])
        auth_log.log_github_token_validated("octocat", [])
        entries = auth_log.read_log()
        self.assertEqual(entries[0]["source"], "github")  # newest first
        self.assertEqual(entries[1]["source"], "calendar")

    def test_read_log_merges_legacy_calendar_file_and_backfills_source(self) -> None:
        # A pre-unification legacy entry has no "source" key.
        legacy = self.log_dir / "calendar_oauth_activity.jsonl"
        legacy.write_text(
            json.dumps({
                "ts": "2026-05-01T00:00:00+00:00",
                "device": "old-mac",
                "event": "flow_succeeded",
                "detail": {},
            }) + "\n"
        )
        auth_log.log_github_token_validated("octocat", [])  # newer, unified file
        entries = auth_log.read_log()
        sources = [e["source"] for e in entries]
        self.assertIn("calendar", sources)  # backfilled on the legacy row
        self.assertIn("github", sources)
        # Sorted by ts: github (2026-06...) newer than legacy (2026-05-01)
        self.assertEqual(entries[0]["source"], "github")

    def test_latest_failure_by_source(self) -> None:
        auth_log.log_github_token_validated("octocat", [])   # success — ignored
        auth_log.log_github_auth_failed(401, endpoint="/user")  # failure
        auth_log.log_gmail_adc_missing("no ADC")               # failure
        auth_log.log_flow_succeeded(None, [], "/tok")          # success — ignored

        latest = auth_log.latest_failure_by_source()
        self.assertEqual(set(latest), {"github", "gmail"})
        self.assertEqual(latest["github"]["event"], "auth_failed")
        self.assertEqual(latest["gmail"]["event"], "adc_missing")

    def test_latest_failure_by_source_filters(self) -> None:
        auth_log.log_github_auth_failed(401)
        auth_log.log_gmail_adc_missing()
        latest = auth_log.latest_failure_by_source(["gmail"])
        self.assertEqual(set(latest), {"gmail"})

    def test_failure_events_membership(self) -> None:
        self.assertIn("auth_failed", auth_log.FAILURE_EVENTS)
        self.assertIn("token_refresh_failed", auth_log.FAILURE_EVENTS)
        self.assertNotIn("token_validated", auth_log.FAILURE_EVENTS)
        self.assertNotIn("flow_succeeded", auth_log.FAILURE_EVENTS)


if __name__ == "__main__":
    unittest.main()
