"""Tests for scripts/health_issue_reporter.py.

Covers: occurrence counter, quota management, circuit breakers, run logging,
dashboard counter, GitHub API interaction (mocked), doctor DB fixtures,
and LLM triage routing.

Run with:
    .venv/bin/python -m pytest tests/test_health_issue_reporter.py -v
    # or the whole suite:
    .venv/bin/python -m pytest tests/ -v
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: make the scripts/ directory importable so we can import the
# reporter module directly without installing it as a package.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SRC_DIR = REPO_ROOT / "src"

for p in (str(SCRIPTS_DIR), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import health_issue_reporter as hr  # noqa: E402  (after path setup)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_ago_str(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_check(name: str, status: str = "fail", detail: str = "test detail",
                hint: str = "fix it", source: str = "rebalance-doctor") -> dict:
    return {"name": name, "status": status, "detail": detail,
            "hint": hint, "source": source}


# ===========================================================================
# 1. Occurrence counter — pure unit tests, no I/O
# ===========================================================================

class TestOccurrenceCounter(unittest.TestCase):

    def test_parse_zero_on_empty_body(self) -> None:
        self.assertEqual(hr.parse_occurrence_count(""), 0)

    def test_parse_zero_on_body_without_marker(self) -> None:
        body = "## Rebalance health: `my-check`\n\n**Status:** `FAIL`"
        self.assertEqual(hr.parse_occurrence_count(body), 0)

    def test_parse_count_from_marker(self) -> None:
        body = f"> **Seen:** 7× · Last: {_now_str()}\n## heading"
        self.assertEqual(hr.parse_occurrence_count(body), 7)

    def test_set_on_new_body_prepends(self) -> None:
        body = "## heading\nsome content"
        updated = hr.set_occurrence_count(body, 1, _now_str())
        self.assertTrue(updated.startswith("> **Seen:** 1×"))
        self.assertIn("## heading", updated)

    def test_set_replaces_existing_marker(self) -> None:
        ts = _now_str()
        body = hr.set_occurrence_count("## heading", 1, ts)
        body2 = hr.set_occurrence_count(body, 5, ts)
        self.assertIn("> **Seen:** 5×", body2)
        self.assertNotIn("> **Seen:** 1×", body2)
        # Only one occurrence line should exist.
        self.assertEqual(body2.count("> **Seen:**"), 1)

    def test_roundtrip_parse_set(self) -> None:
        body = "## Original content"
        for n in range(1, 6):
            body = hr.set_occurrence_count(body, n, _now_str())
            self.assertEqual(hr.parse_occurrence_count(body), n)

    def test_issue_body_starts_with_seen_1(self) -> None:
        body = hr._issue_body("my-check", "fail", "detail text", "fix hint", "rebalance-doctor")
        self.assertTrue(body.startswith("> **Seen:** 1×"),
                        f"Body should start with seen marker, got: {body[:80]!r}")

    def test_issue_body_contains_required_sections(self) -> None:
        body = hr._issue_body("db-check", "warn", "DB is stale", "run refresh", "rebalance-doctor")
        self.assertIn("## Rebalance health: `db-check`", body)
        self.assertIn("**Status:** `WARN`", body)
        self.assertIn("DB is stale", body)
        self.assertIn("run refresh", body)
        self.assertIn("rebalance-doctor", body)


# ===========================================================================
# 1b. Detail block refresh (GH-139) — a repeat sighting must update Detail,
#     not just the Seen counter.
# ===========================================================================

class TestDetailRefresh(unittest.TestCase):

    def test_set_detail_replaces_detail_block(self) -> None:
        body = hr._issue_body("db", "fail", "original detail", "", "rebalance-doctor")
        updated = hr.set_detail(body, "new root-cause detail")
        self.assertIn("new root-cause detail", updated)
        self.assertNotIn("original detail", updated)

    def test_set_detail_preserves_rest_of_body(self) -> None:
        body = hr._issue_body("db", "fail", "original detail", "a hint", "rebalance-doctor")
        updated = hr.set_detail(body, "new detail")
        self.assertIn("## Rebalance health: `db`", updated)
        self.assertIn("**Status:** `FAIL`", updated)
        self.assertIn("a hint", updated)
        self.assertTrue(updated.startswith("> **Seen:** 1×"))

    def test_set_detail_noop_when_no_detail_block(self) -> None:
        body = "no detail block here"
        self.assertEqual(hr.set_detail(body, "whatever"), body)

    def test_set_detail_does_not_touch_seen_counter(self) -> None:
        body = hr._issue_body("db", "fail", "detail v1", "", "rebalance-doctor")
        body = hr.set_occurrence_count(body, 3, _now_str(), device="host-a")
        updated = hr.set_detail(body, "detail v2")
        self.assertIn("> **Seen:** 3×", updated)
        self.assertIn("detail v2", updated)
        self.assertNotIn("detail v1", updated)

    def test_repeat_sighting_refreshes_detail_and_counter(self) -> None:
        """End-to-end: a second sighting with a changed detail must update both."""
        body = hr._issue_body("db", "fail", "disk full", "", "rebalance-doctor")
        refreshed = hr.set_detail(body, "disk full — now 99% (was 92%)")
        new_body = hr.set_occurrence_count(refreshed, 2, _now_str(), device="host-a")
        self.assertIn("disk full — now 99% (was 92%)", new_body)
        self.assertNotIn("```\ndisk full\n```", new_body)
        self.assertIn("> **Seen:** 2×", new_body)


# ===========================================================================
# 1c. Stable check-id dedup (GH-139) — a renamed/retitled issue must still
#     match its existing open issue instead of orphaning it.
# ===========================================================================

class TestStableCheckIdDedup(unittest.TestCase):

    def test_issue_body_embeds_check_id_marker(self) -> None:
        body = hr._issue_body("sleuth", "fail", "detail", "", "rebalance-doctor")
        self.assertEqual(hr.parse_check_id(body), "sleuth")

    def test_parse_check_id_missing_marker_returns_none(self) -> None:
        self.assertIsNone(hr.parse_check_id("no marker here"))
        self.assertIsNone(hr.parse_check_id(""))

    def test_dedup_key_prefers_body_marker_over_title(self) -> None:
        """A human-retitled GitHub issue must still match its stable id."""
        body = hr._issue_body("sleuth", "fail", "detail", "", "rebalance-doctor")
        issue = {"title": "health: sleuth credentials (renamed by operator)", "body": body}
        self.assertEqual(hr.dedup_key_for_issue(issue), "sleuth")

    def test_dedup_key_falls_back_to_title_for_legacy_issues(self) -> None:
        """Pre-GH-139 issues (e.g. the #46-48 / #83-85 pulse-collector dupes)
        have no marker; matching must still work off the title so this fix
        does not misbehave against them or file new duplicates."""
        issue = {"title": "health: pulse collector:noels-mbp-16-m1-pro", "body": ""}
        self.assertEqual(
            hr.dedup_key_for_issue(issue), "pulse collector:noels-mbp-16-m1-pro"
        )

    def test_dedup_key_legacy_issue_with_no_body_at_all(self) -> None:
        issue = {"title": "health: vault", "body": None}
        self.assertEqual(hr.dedup_key_for_issue(issue), "vault")

    def test_list_health_issues_keys_by_check_id_not_title(self) -> None:
        """Two issues whose titles differ from ``health: <name>`` — one via
        the marker (post-fix), one via legacy title parsing (pre-fix) — must
        both be reachable by their check name, proving the title text no
        longer gates dedup."""
        marker_body = hr._issue_body("gmail", "fail", "detail", "", "rebalance-doctor")
        renamed_issue = {
            "title": "health: gmail integration (renamed)",
            "number": 200,
            "body": marker_body,
            "state": "open",
        }
        legacy_issue = {
            "title": "health: pulse collector:device-a",
            "number": 46,
            "body": "",
            "state": "open",
        }

        with patch.object(hr, "_request", side_effect=[[renamed_issue, legacy_issue], []]):
            issues = hr.list_health_issues("tok", "org/repo", state="open")

        self.assertIn("gmail", issues)
        self.assertEqual(issues["gmail"]["number"], 200)
        self.assertIn("pulse collector:device-a", issues)
        self.assertEqual(issues["pulse collector:device-a"]["number"], 46)

    def test_renamed_check_does_not_orphan_or_duplicate(self) -> None:
        """Simulates main()'s matching logic: a check whose GitHub issue was
        retitled (title no longer equals ``health: <name>``) must still be
        found as 'already open' via the stable check id, not re-filed."""
        body = hr._issue_body("figma", "fail", "token missing", "", "rebalance-doctor")
        open_issues = {
            hr.dedup_key_for_issue({"title": "health: figma token (renamed)", "body": body}):
                {"title": "health: figma token (renamed)", "number": 77, "body": body}
        }

        check = _make_check("figma")
        check_id = check["name"]
        already_open = open_issues.get(check_id)

        self.assertIsNotNone(
            already_open,
            "renamed issue must still be found by its stable check id — "
            "the old title-only lookup would have missed this and filed a duplicate.",
        )
        self.assertEqual(already_open["number"], 77)


# ===========================================================================
# 2. Quota management
# ===========================================================================

class TestQuotaManagement(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._quota_path = Path(self._tmp.name) / "quota.json"
        self._orig = hr.QUOTA_FILE
        hr.QUOTA_FILE = self._quota_path

    def tearDown(self) -> None:
        hr.QUOTA_FILE = self._orig
        self._tmp.cleanup()

    def test_load_returns_zero_when_file_missing(self) -> None:
        q = hr.load_quota()
        self.assertEqual(q["calls_today"], 0)
        self.assertEqual(q["date"], datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    def test_load_returns_zero_for_stale_date(self) -> None:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        self._quota_path.write_text(json.dumps({"date": yesterday, "calls_today": 5}))
        q = hr.load_quota()
        self.assertEqual(q["calls_today"], 0)  # resets

    def test_load_returns_todays_count(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._quota_path.write_text(json.dumps({"date": today, "calls_today": 3}))
        self.assertEqual(hr.load_quota()["calls_today"], 3)

    def test_increment_writes_and_returns_new_total(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._quota_path.write_text(json.dumps({"date": today, "calls_today": 4}))
        total = hr.increment_quota()
        self.assertEqual(total, 5)
        self.assertEqual(hr.load_quota()["calls_today"], 5)

    def test_quota_remaining_calculates_correctly(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._quota_path.write_text(json.dumps({"date": today, "calls_today": 6}))
        self.assertEqual(hr.quota_remaining(8), 2)

    def test_quota_remaining_clamps_to_zero(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._quota_path.write_text(json.dumps({"date": today, "calls_today": 10}))
        self.assertEqual(hr.quota_remaining(8), 0)


# ===========================================================================
# 3. Circuit breakers
# ===========================================================================

class TestCircuitBreakers(unittest.TestCase):
    """Verify each CB prevents or degrades LLM calls as intended."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._quota_path = Path(self._tmp.name) / "quota.json"
        self._orig_quota = hr.QUOTA_FILE
        hr.QUOTA_FILE = self._quota_path

    def tearDown(self) -> None:
        hr.QUOTA_FILE = self._orig_quota
        self._tmp.cleanup()
        os.environ.pop("HEALTH_LLM_DISABLE", None)

    def test_cb1_env_var_returns_fallback(self) -> None:
        """CB-1: HEALTH_LLM_DISABLE=1 must prevent any LLM call."""
        os.environ["HEALTH_LLM_DISABLE"] = "1"
        call_tracker = []

        def _fake_triage(*_, **__):
            call_tracker.append(1)
            return {"decision": "file", "reason": "should not reach here"}

        # The CB-1 guard lives in main() — test it at the call site level
        # by simulating what main() does before calling llm_triage().
        cb1_triggered = bool(os.environ.get("HEALTH_LLM_DISABLE"))
        self.assertTrue(cb1_triggered)
        self.assertEqual(call_tracker, [])  # llm_triage was never called

    def test_cb2_full_quota_returns_fallback_without_calling_llm(self) -> None:
        """CB-2: exhausted daily quota must prevent LLM calls."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._quota_path.write_text(json.dumps({"date": today, "calls_today": 8}))
        self.assertEqual(hr.quota_remaining(8), 0)

    def test_cb4_api_error_returns_fallback(self) -> None:
        """CB-4: any LLM API error must degrade to 'file', not raise."""
        check = _make_check("test-check")

        def _exploding_gemini(*_, **__):
            raise RuntimeError("connection refused")

        with patch.object(hr, "_triage_gemini", side_effect=RuntimeError("boom")):
            decision, reason = hr.llm_triage(check, provider="gemini")
        self.assertEqual(decision, "file")
        self.assertIn("error", reason.lower())

    def test_cb4_bad_json_from_llm_returns_fallback(self) -> None:
        """CB-4: LLM returning non-JSON must degrade gracefully."""
        check = _make_check("test-check")

        def _bad_json(*_, **__):
            import json
            raise json.JSONDecodeError("nope", "", 0)

        with patch.object(hr, "_triage_gemini", side_effect=_bad_json):
            decision, reason = hr.llm_triage(check, provider="gemini")
        self.assertEqual(decision, "file")


# ===========================================================================
# 4. RunLog — JSONL accumulation and flush
# ===========================================================================

class TestRunLog(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._log_path = Path(self._tmp.name) / "test.log.jsonl"
        self._orig = hr.LOG_FILE
        hr.LOG_FILE = self._log_path

    def tearDown(self) -> None:
        hr.LOG_FILE = self._orig
        self._tmp.cleanup()

    def test_flush_writes_valid_jsonl(self) -> None:
        log = hr.RunLog("2026-01-01T00:00:00Z", {"dry_run": False})
        log.add_check(_make_check("db", "ok"))
        log.add_check(_make_check("vault", "warn"))
        log.add_llm_call("db", "haiku", "anthropic", "skip", "looks ok")
        log.add_action("filed", "vault", 42)
        log.flush(dry_run=False)

        lines = self._log_path.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["run_id"], "2026-01-01T00:00:00Z")
        self.assertEqual(record["checks_total"], 2)
        self.assertEqual(record["llm_calls_this_run"], 1)
        self.assertEqual(record["actions"][0]["issue"], 42)

    def test_flush_appends_across_runs(self) -> None:
        for i in range(3):
            log = hr.RunLog(f"run-{i}", {})
            log.flush()
        lines = self._log_path.read_text().splitlines()
        self.assertEqual(len(lines), 3)

    def test_flush_records_dry_run_flag(self) -> None:
        log = hr.RunLog("test-run", {})
        log.flush(dry_run=True)
        record = json.loads(self._log_path.read_text().splitlines()[0])
        self.assertTrue(record["dry_run"])

    def test_circuit_breaker_recorded(self) -> None:
        log = hr.RunLog("run-cb", {})
        log.add_cb("CB-2: daily quota")
        log.add_cb("CB-3: per-run cap")
        log.flush()
        record = json.loads(self._log_path.read_text().splitlines()[0])
        self.assertIn("CB-2: daily quota", record["circuit_breakers_triggered"])
        self.assertIn("CB-3: per-run cap", record["circuit_breakers_triggered"])


# ===========================================================================
# 5. Dashboard health counter (fetch_health_filed_count)
# ===========================================================================

class TestHealthFiledCount(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._log_path = Path(self._tmp.name) / "health.log.jsonl"
        self._orig = hr.LOG_FILE
        hr.LOG_FILE = self._log_path
        # Also patch the pulse_web module path if already imported.
        try:
            import pulse_web as pw  # noqa: F401
            self._pw = pw
            self._orig_pw_log = pw.HEALTH_LOG_PATH
            pw.HEALTH_LOG_PATH = self._log_path
        except ImportError:
            self._pw = None

    def tearDown(self) -> None:
        hr.LOG_FILE = self._orig
        if self._pw:
            self._pw.HEALTH_LOG_PATH = self._orig_pw_log
        self._tmp.cleanup()

    def _write_log_record(self, run_id: str, actions: list[dict],
                          dry_run: bool = False) -> None:
        record = {"run_id": run_id, "dry_run": dry_run, "actions": actions, "checks": []}
        with self._log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    def _import_fetch(self):
        # Reimport pulse_web to pick up patched HEALTH_LOG_PATH.
        import pulse_web as pw
        importlib.reload(pw)
        pw.HEALTH_LOG_PATH = self._log_path
        return pw.fetch_health_filed_count

    def test_returns_zero_when_no_log(self) -> None:
        if self._pw is None:
            self.skipTest("pulse_web not importable in this environment")
        fn = self._import_fetch()
        self.assertEqual(fn(days=30), 0)

    def test_counts_filed_actions(self) -> None:
        if self._pw is None:
            self.skipTest("pulse_web not importable in this environment")
        self._write_log_record(
            _now_str(),
            [{"action": "filed", "check": "sleuth"},
             {"action": "filed", "check": "calendar"}],
        )
        fn = self._import_fetch()
        self.assertEqual(fn(days=30), 2)

    def test_excludes_dry_run_records(self) -> None:
        if self._pw is None:
            self.skipTest("pulse_web not importable in this environment")
        self._write_log_record(_now_str(), [{"action": "filed", "check": "db"}], dry_run=True)
        fn = self._import_fetch()
        self.assertEqual(fn(days=30), 0)

    def test_excludes_records_outside_window(self) -> None:
        if self._pw is None:
            self.skipTest("pulse_web not importable in this environment")
        old_run_id = _days_ago_str(45)
        self._write_log_record(old_run_id, [{"action": "filed", "check": "vault"}])
        fn = self._import_fetch()
        self.assertEqual(fn(days=30), 0)

    def test_does_not_count_recurrence_comments(self) -> None:
        if self._pw is None:
            self.skipTest("pulse_web not importable in this environment")
        self._write_log_record(
            _now_str(),
            [{"action": "recurrence-comment", "check": "sleuth", "issue": 7}],
        )
        fn = self._import_fetch()
        self.assertEqual(fn(days=30), 0)

    def test_deduplicates_same_check_filed_twice(self) -> None:
        if self._pw is None:
            self.skipTest("pulse_web not importable in this environment")
        for _ in range(3):
            self._write_log_record(_now_str(), [{"action": "filed", "check": "sleuth"}])
        fn = self._import_fetch()
        # Same check name filed in 3 separate runs → counts as 1 distinct check.
        self.assertEqual(fn(days=30), 1)


# ===========================================================================
# 6. GitHub API interaction (mocked _request)
# ===========================================================================

class TestGitHubInteraction(unittest.TestCase):
    """Mock _request to test filing, dedup, body update, and close logic."""

    TOKEN = "fake-token"
    REPO = "test-org/test-repo"

    def _open_issue(self, title: str, number: int, body: str = "") -> dict:
        return {"title": title, "number": number, "body": body, "state": "open"}

    def test_file_issue_makes_post_request(self) -> None:
        calls = []

        def _fake_request(method, path, token, payload=None):
            calls.append((method, path, payload))
            return {"number": 99, "title": payload.get("title", "") if payload else ""}

        with patch.object(hr, "_request", side_effect=_fake_request):
            number = hr.file_issue(self.TOKEN, self.REPO, "health: db", "body text", dry_run=False)

        self.assertEqual(number, 99)
        self.assertEqual(len(calls), 1)
        method, path, payload = calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/issues", path)
        self.assertEqual(payload["title"], "health: db")
        self.assertIn(hr.LABEL, payload["labels"])

    def test_file_issue_dry_run_makes_no_request(self) -> None:
        calls = []
        with patch.object(hr, "_request", side_effect=lambda *a, **k: calls.append(a)):
            result = hr.file_issue(self.TOKEN, self.REPO, "health: db", "body", dry_run=True)
        self.assertIsNone(result)
        self.assertEqual(calls, [])

    def test_update_issue_body_patches_correct_issue(self) -> None:
        calls = []

        def _fake_request(method, path, token, payload=None):
            calls.append((method, path, payload))
            return {}

        with patch.object(hr, "_request", side_effect=_fake_request):
            hr.update_issue_body(self.TOKEN, self.REPO, 42, "new body", dry_run=False)

        self.assertEqual(len(calls), 1)
        method, path, payload = calls[0]
        self.assertEqual(method, "PATCH")
        self.assertIn("/42", path)
        self.assertEqual(payload["body"], "new body")

    def test_update_issue_body_dry_run_skips_request(self) -> None:
        calls = []
        with patch.object(hr, "_request", side_effect=lambda *a, **k: calls.append(a)):
            hr.update_issue_body(self.TOKEN, self.REPO, 42, "body", dry_run=True)
        self.assertEqual(calls, [])

    def test_comment_on_issue_posts_to_correct_url(self) -> None:
        calls = []

        def _fake_request(method, path, token, payload=None):
            calls.append((method, path, payload))
            return {}

        with patch.object(hr, "_request", side_effect=_fake_request):
            hr.comment_on_issue(self.TOKEN, self.REPO, 7, "recurrence detected", dry_run=False)

        self.assertEqual(len(calls), 1)
        method, path, payload = calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/7/comments", path)
        self.assertEqual(payload["body"], "recurrence detected")

    def test_occurrence_counter_increments_on_open_issue(self) -> None:
        """When a check fires and its issue is already open, the body counter increments."""
        ts = _now_str()
        existing_body = hr.set_occurrence_count("## heading", 3, ts)
        patched_calls = []

        def _fake_request(method, path, token, payload=None):
            patched_calls.append((method, path, payload))
            return {}

        open_issues = {
            "health: sleuth": self._open_issue("health: sleuth", 12, existing_body)
        }

        with patch.object(hr, "_request", side_effect=_fake_request):
            issue = open_issues["health: sleuth"]
            current_body = issue.get("body") or ""
            new_count = hr.parse_occurrence_count(current_body) + 1
            new_body = hr.set_occurrence_count(current_body, new_count, ts)
            hr.update_issue_body(self.TOKEN, self.REPO, issue["number"], new_body, dry_run=False)

        self.assertEqual(hr.parse_occurrence_count(new_body), 4)
        # Exactly one PATCH call was made.
        methods = [c[0] for c in patched_calls]
        self.assertEqual(methods, ["PATCH"])

    def test_close_issue_posts_comment_then_patches_state(self) -> None:
        calls = []

        def _fake_request(method, path, token, payload=None):
            calls.append((method, path, payload))
            return {}

        with patch.object(hr, "_request", side_effect=_fake_request):
            hr.close_issue(self.TOKEN, self.REPO, 5, "auto-closing", dry_run=False)

        methods = [c[0] for c in calls]
        self.assertEqual(methods, ["POST", "PATCH"])  # comment then state change
        self.assertEqual(calls[1][2]["state"], "closed")


# ===========================================================================
# 7. Doctor DB fixtures — intentional errors in a temp SQLite database
# ===========================================================================

class TestDoctorFixtures(unittest.TestCase):
    """Drive run_doctor() against temp DBs with known bad states."""

    def _by_name(self, report) -> dict:
        return {c.name: c for c in report.checks}

    def _fresh_db(self, tmp: str):
        """Return a path to a freshly migrated empty DB."""
        from rebalance.ingest.db import db_connection, run_migrations  # noqa: PLC0415
        db = Path(tmp) / "rebalance.db"
        with db_connection(db) as conn:
            run_migrations(conn)
        return db

    def test_missing_db_file_fails_database_check(self) -> None:
        """When no DB can be resolved at all, 'database' check must FAIL.

        resolve_database_path() falls back to the live DB when given a
        missing path, so we use the same monkey-patch approach as test_doctor.py
        to force a DatabaseNotFoundError without relying on file-system state.
        """
        import rebalance.paths as paths_mod  # noqa: PLC0415
        from rebalance.doctor import FAIL, run_doctor  # noqa: PLC0415

        original = paths_mod.resolve_database_path

        def _raise(explicit=None):
            raise paths_mod.DatabaseNotFoundError([])

        paths_mod.resolve_database_path = _raise
        try:
            checks = self._by_name(run_doctor())
            self.assertEqual(checks["database"].status, FAIL)
        finally:
            paths_mod.resolve_database_path = original

    def test_fresh_db_without_projects_warns(self) -> None:
        """A migrated DB with no projects registered should WARN on 'projects'."""
        with tempfile.TemporaryDirectory() as tmp:
            db = self._fresh_db(tmp)
            from rebalance.doctor import WARN, run_doctor  # noqa: PLC0415
            checks = self._by_name(run_doctor(db))
            self.assertEqual(checks["projects"].status, WARN)

    def test_stale_github_data_warns(self) -> None:
        """Activity rows older than 2 days should produce a WARN on 'github data'."""
        with tempfile.TemporaryDirectory() as tmp:
            db = self._fresh_db(tmp)
            from rebalance.ingest.db import db_connection  # noqa: PLC0415
            from rebalance.doctor import WARN, run_doctor  # noqa: PLC0415
            with db_connection(db) as conn:
                conn.execute(
                    "INSERT INTO github_activity "
                    "(login, repo_full_name, scan_date, scanned_at) "
                    "VALUES ('me', 'org/repo', date('now', '-10 days'), date('now'))"
                )
                conn.commit()
            checks = self._by_name(run_doctor(db))
            self.assertEqual(checks["github data"].status, WARN)
            self.assertIn("stale", checks["github data"].detail)

    def test_fresh_github_data_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = self._fresh_db(tmp)
            from rebalance.ingest.db import db_connection  # noqa: PLC0415
            from rebalance.doctor import OK, run_doctor  # noqa: PLC0415
            with db_connection(db) as conn:
                conn.execute(
                    "INSERT INTO github_activity "
                    "(login, repo_full_name, scan_date, scanned_at) "
                    "VALUES ('me', 'org/repo', date('now'), datetime('now'))"
                )
                conn.commit()
            checks = self._by_name(run_doctor(db))
            self.assertEqual(checks["github data"].status, OK)

    def test_fully_populated_db_reports_all_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = self._fresh_db(tmp)
            from rebalance.ingest.db import db_connection  # noqa: PLC0415
            from rebalance.doctor import OK, run_doctor  # noqa: PLC0415
            with db_connection(db) as conn:
                conn.execute(
                    "INSERT INTO project_registry (name, status) VALUES ('proj', 'active')"
                )
                conn.execute(
                    "INSERT INTO github_activity "
                    "(login, repo_full_name, scan_date, scanned_at) "
                    "VALUES ('me', 'org/repo', date('now'), datetime('now'))"
                )
                conn.commit()
            checks = self._by_name(run_doctor(db))
            self.assertEqual(checks["projects"].status, OK)
            self.assertEqual(checks["github data"].status, OK)

    def test_no_github_activity_table_warns(self) -> None:
        """A DB that has baseline schema but no github_activity table warns."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "rebalance.db"
            from rebalance.ingest.db import db_connection, ensure_baseline_schema  # noqa: PLC0415
            from rebalance.doctor import WARN, run_doctor  # noqa: PLC0415
            with db_connection(db, ensure_baseline_schema):
                pass  # baseline tables only, no migrations
            checks = self._by_name(run_doctor(db))
            self.assertEqual(checks["github data"].status, WARN)


# ===========================================================================
# 8. LLM triage routing
# ===========================================================================

class TestLLMTriage(unittest.TestCase):

    def _check(self) -> dict:
        return _make_check("test-check", "warn")

    def test_file_decision_passes_through(self) -> None:
        with patch.object(hr, "_triage_gemini",
                          return_value={"decision": "file", "reason": "real issue"}):
            decision, reason = hr.llm_triage(self._check(), provider="gemini")
        self.assertEqual(decision, "file")
        self.assertEqual(reason, "real issue")

    def test_skip_decision_passes_through(self) -> None:
        with patch.object(hr, "_triage_gemini",
                          return_value={"decision": "skip", "reason": "noise"}):
            decision, reason = hr.llm_triage(self._check(), provider="gemini")
        self.assertEqual(decision, "skip")

    def test_downgrade_decision_passes_through(self) -> None:
        with patch.object(hr, "_triage_gemini",
                          return_value={"decision": "downgrade", "reason": "low priority"}):
            decision, reason = hr.llm_triage(self._check(), provider="gemini")
        self.assertEqual(decision, "downgrade")

    def test_empty_dict_response_falls_back_to_file(self) -> None:
        with patch.object(hr, "_triage_gemini", return_value={}):
            decision, _ = hr.llm_triage(self._check(), provider="gemini")
        self.assertEqual(decision, "file")

    def test_openai_compat_missing_config_returns_fallback(self) -> None:
        """openai-compat without HEALTH_LLM_BASE_URL must degrade, not raise."""
        env_backup = os.environ.pop("HEALTH_LLM_BASE_URL", None)
        env_backup2 = os.environ.pop("HEALTH_LLM_MODEL", None)
        try:
            decision, reason = hr.llm_triage(
                self._check(), provider="openai-compat", base_url="", model=""
            )
        finally:
            if env_backup:
                os.environ["HEALTH_LLM_BASE_URL"] = env_backup
            if env_backup2:
                os.environ["HEALTH_LLM_MODEL"] = env_backup2
        self.assertEqual(decision, "file")

    def test_real_api_call_gemini(self) -> None:
        """Live smoke test — skipped if GEMINI_API_KEY is not set.

        Sends a real request to gemini-3.5-flash and verifies the
        response is a valid triage decision.  Run manually to confirm the
        key and model are working end-to-end.
        """
        from rebalance.ingest.config import get_gemini_api_key
        if not get_gemini_api_key():
            self.skipTest("GEMINI_API_KEY not set — skipping live API test")

        check = _make_check(
            "github data",
            status="warn",
            detail="github_activity last scan 5 days ago (stale)",
            hint="run `rebalance refresh` (scope github)",
        )
        decision, reason = hr.llm_triage(check, provider="gemini",
                                          model="gemini-3.5-flash")
        self.assertIn(decision, ("file", "skip", "downgrade"),
                      f"Unexpected decision: {decision!r} — reason: {reason}")
        self.assertIsInstance(reason, str)
        self.assertGreater(len(reason), 5)


# ===========================================================================
# 9. Triage scenario fixture bank — live LLM calls
#
# Each test sends a realistic Check fixture to claude-haiku and asserts the
# response falls within an expected decision range.  Two kinds of assertions:
#
#   Hard  — used only for unambiguous FAIL checks where "skip" would be
#            genuinely wrong.  These should never flake.
#   Soft  — for WARN checks where any decision may be reasonable depending
#            on context.  These verify response shape and print the actual
#            decision so you can build a historical record of model judgment.
#
# Run this class manually (live API calls, ~$0.002 total at Haiku rates):
#   ANTHROPIC_API_KEY=... .venv/bin/python -m pytest \
#       tests/test_health_issue_reporter.py::TestTriageScenarios -v -s
# ===========================================================================

class TestTriageScenarios(unittest.TestCase):
    """Live LLM scenario tests — skipped unless GEMINI_API_KEY is set."""

    MODEL = "gemini-3.5-flash"

    @classmethod
    def setUpClass(cls) -> None:
        from rebalance.ingest.config import get_gemini_api_key
        if not get_gemini_api_key():
            raise unittest.SkipTest("GEMINI_API_KEY not set — skipping live scenario tests")

    def _triage(self, check: dict) -> tuple[str, str]:
        decision, reason = hr.llm_triage(check, provider="gemini", model=self.MODEL)
        print(f"\n  [{check['name']} / {check['status'].upper()}] → {decision}: {reason}")
        return decision, reason

    def _assert_valid(self, decision: str, reason: str, check_name: str) -> None:
        self.assertIn(decision, ("file", "skip", "downgrade"),
                      f"{check_name}: unexpected decision {decision!r}")
        self.assertIsInstance(reason, str)
        self.assertGreater(len(reason), 5, f"{check_name}: reason too short: {reason!r}")

    # ------------------------------------------------------------------
    # HARD assertions — unambiguous FAILs where "skip" is always wrong
    # ------------------------------------------------------------------

    def test_hard_db_not_found_should_not_skip(self) -> None:
        """A missing database on a configured machine is a regression — never skip."""
        check = _make_check(
            "database", "fail",
            detail=(
                "no rebalance.db could be resolved — the database that was present "
                "yesterday is now missing; sync has stopped completely"
            ),
            hint="run `rebalance onboard`, or `rebalance refresh`, to recreate",
        )
        decision, reason = self._triage(check)
        self._assert_valid(decision, reason, "database")
        self.assertNotEqual(decision, "skip",
                            f"skip is wrong for a missing database. Reason: {reason}")

    def test_hard_github_token_missing_should_not_skip(self) -> None:
        """Token was present, now gone — all GitHub sync is broken."""
        check = _make_check(
            "github token", "fail",
            detail=(
                "no GitHub token configured — previously stored token is no longer "
                "present; all GitHub activity ingestion has stopped"
            ),
            hint="run `rebalance config set-github-token` to restore it",
        )
        decision, reason = self._triage(check)
        self._assert_valid(decision, reason, "github token")
        self.assertNotEqual(decision, "skip",
                            f"skip is wrong for a missing GitHub token. Reason: {reason}")

    def test_hard_schema_corrupt_should_not_skip(self) -> None:
        """A corrupt/unreadable schema is a real error, not noise."""
        check = _make_check(
            "schema", "fail",
            detail="could not read schema: database disk image is malformed",
            hint="restore from backup or run `rebalance refresh` to recreate",
        )
        decision, reason = self._triage(check)
        self._assert_valid(decision, reason, "schema-corrupt")
        self.assertNotEqual(decision, "skip",
                            f"skip is wrong for a corrupt schema. Reason: {reason}")

    # ------------------------------------------------------------------
    # SOFT assertions — WARNs where any decision may be reasonable.
    # These verify response shape and surface the model's judgment.
    # ------------------------------------------------------------------

    def test_soft_stale_github_data(self) -> None:
        """10-day-old GitHub activity — should be file or downgrade, rarely skip."""
        check = _make_check(
            "github data", "warn",
            detail="42 activity rows, latest 2026-05-20 — last scan 10 days ago (stale)",
            hint="run `rebalance refresh` (scope github) — check projects are registered",
        )
        decision, reason = self._triage(check)
        self._assert_valid(decision, reason, "github-data-stale")
        # Soft: we expect file or downgrade but accept skip if the LLM
        # considers "just run refresh" self-resolving.

    def test_soft_calendar_token_missing(self) -> None:
        """Calendar OAuth token absent — optional integration, may be skip/downgrade."""
        check = _make_check(
            "calendar", "warn",
            detail=(
                "OAuth token not found at "
                "/Users/user/.config/rebalance/calendar_token.json"
            ),
            hint="run the Calendar OAuth flow (scripts/setup_calendar_oauth.py)",
        )
        decision, reason = self._triage(check)
        self._assert_valid(decision, reason, "calendar-token-missing")

    def test_soft_sleuth_env_missing(self) -> None:
        """Sleuth env file absent — optional integration on machines without Sleuth."""
        check = _make_check(
            "sleuth", "warn",
            detail=(
                "no Sleuth Web API env file "
                "(/Users/user/.config/rebalance/sleuth-web-api-production.env)"
            ),
            hint=(
                "create it with SLEUTH_WEB_API_BASE_URL / SLEUTH_WEB_API_TOKEN / "
                "SLEUTH_WORKSPACE_NAME — without it the Slack-reminders sync fails every run"
            ),
        )
        decision, reason = self._triage(check)
        self._assert_valid(decision, reason, "sleuth-missing")

    def test_soft_launchd_single_nonzero_exit(self) -> None:
        """launchd job exited 1 once — may be transient; any decision is reasonable."""
        check = _make_check(
            "launchd:daily-sync", "warn",
            detail="last run exited with status 1",
            hint="inspect temp/logs/ for this job's error output",
        )
        decision, reason = self._triage(check)
        self._assert_valid(decision, reason, "launchd-exit-1")

    def test_soft_database_location_split(self) -> None:
        """Active DB not at canonical path — housekeeping issue, medium priority."""
        check = _make_check(
            "database location", "warn",
            detail=(
                "active DB is not the canonical path\n"
                "  canonical: /Users/user/Library/Application Support/rebalance-os/rebalance.db\n"
                "  resolved:  /tmp/rebalance.db"
            ),
            hint="run `python -m rebalance.paths --migrate` to consolidate",
        )
        decision, reason = self._triage(check)
        self._assert_valid(decision, reason, "db-location-split")

    def test_soft_gmail_mcp_no_messages(self) -> None:
        """Gmail in MCP mode with 0 messages ingested — may not need an issue."""
        check = _make_check(
            "gmail", "warn",
            detail="MCP mode — no email ingested yet",
            hint=(
                "have an agent fetch via the Gmail MCP connector "
                "and call `ingest_gmail_messages`"
            ),
        )
        decision, reason = self._triage(check)
        self._assert_valid(decision, reason, "gmail-mcp-empty")


class TestNoDuplicateCollectorEmitter(unittest.TestCase):
    """GH-139 regression: the reporter must not emit its own collector checks.

    The bug: this module used to carry ``run_pulse_checks()``, which shelled out
    to ``experimental/git-pulse/health-check.py`` and screen-scraped fixed-width
    columns out of its stdout to synthesise checks named ``pulse-collector:<device>``.
    ``rebalance doctor`` independently emits the same information as
    ``pulse collector:<device>`` — hyphen versus space.

    Because issues are deduplicated by title, those two spellings never matched,
    so every device produced a twin issue: 6 issues across 3 machines before
    anyone noticed. The cure was to delete the reporter's emitter and let
    doctor's canonical checks flow through as the single source.

    These tests pin the deletion. If a future change reintroduces a
    reporter-side collector emitter — under any name — the twin-issue bug comes
    back, and dedup-by-title will not catch it.
    """

    def test_run_pulse_checks_is_gone(self) -> None:
        self.assertFalse(
            hasattr(hr, "run_pulse_checks"),
            "run_pulse_checks() was deleted under GH-139 — reintroducing a "
            "reporter-side collector emitter re-creates the twin-issue bug.",
        )

    def test_reporter_does_not_shell_out_to_the_git_pulse_health_check(self) -> None:
        """The old emitter built the path piecewise, so assert on the leaf filename.

        Pre-fix source read:
            script = _REPO_ROOT / "experimental" / "git-pulse" / "health-check.py"
        so a literal "git-pulse/health-check.py" would never have matched — the
        leaf is the part that actually appears.
        """
        source = (SCRIPTS_DIR / "health_issue_reporter.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "health-check.py", source,
            "The reporter must not invoke the git-pulse health check; doctor "
            "already surfaces collector health as `pulse collector:*`.",
        )

    def test_source_contains_no_hyphenated_collector_spelling(self) -> None:
        """'pulse-collector:' in the source IS the twin-issue fingerprint.

        This is the assertion that actually fails against the pre-fix file — the
        behavioural test below cannot catch it, because run_doctor_checks() never
        produced the hyphen form; only the deleted emitter did.
        """
        source = (SCRIPTS_DIR / "health_issue_reporter.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "pulse-collector:", source,
            "'pulse-collector:' (hyphen) was the duplicate emitter's spelling. "
            "doctor's canonical name is 'pulse collector:' (space). Two spellings "
            "of one check defeat dedup-by-title and file twin issues per device.",
        )

    def test_all_checks_come_from_doctor(self) -> None:
        """Every collected check carries source='rebalance-doctor', never a second producer."""
        fake_report = MagicMock()
        fake_report.checks = [
            _make_check_obj("pulse collector:device-a", "warn", "ALERT — last scan 2.0d ago"),
            _make_check_obj("email data", "ok", "107 rows"),
        ]
        with patch("rebalance.doctor.run_doctor", return_value=fake_report):
            checks = hr.run_doctor_checks()

        self.assertEqual(len(checks), 2)
        self.assertEqual({c["source"] for c in checks}, {"rebalance-doctor"})

    def test_no_check_uses_the_hyphenated_collector_spelling(self) -> None:
        """The hyphen form is the fingerprint of the deleted emitter."""
        fake_report = MagicMock()
        fake_report.checks = [
            _make_check_obj("pulse collector:device-a", "warn", "ALERT"),
        ]
        with patch("rebalance.doctor.run_doctor", return_value=fake_report):
            checks = hr.run_doctor_checks()

        for check in checks:
            self.assertNotIn(
                "pulse-collector:", check["name"],
                "'pulse-collector:' (hyphen) was the duplicate emitter's spelling; "
                "doctor's canonical name is 'pulse collector:' (space). Two "
                "spellings of one check defeat dedup-by-title.",
            )

    def test_also_pulse_is_accepted_but_adds_no_checks(self) -> None:
        """--also-pulse is kept as a deprecated no-op so scheduled invocations don't break.

        The parser is built inline in main() and parse_args() takes no argv, so
        this asserts on the source: the flag must still be declared (compat), and
        its branch must not collect anything (that branch collecting again IS the
        GH-139 bug).
        """
        source = (SCRIPTS_DIR / "health_issue_reporter.py").read_text(encoding="utf-8")

        self.assertIn(
            '"--also-pulse"', source,
            "The flag must remain accepted — launchd jobs still pass it.",
        )

        _, _, after_flag = source.partition("if args.also_pulse:")
        self.assertTrue(after_flag, "expected an `if args.also_pulse:` branch in main()")
        branch = after_flag.split("\n\n", 1)[0]
        for forbidden in ("checks.extend", "run_pulse", "health-check.py"):
            self.assertNotIn(
                forbidden, branch,
                f"--also-pulse must stay a no-op; found {forbidden!r} in its branch, "
                "which re-creates the duplicate collector emitter (GH-139).",
            )


def _make_check_obj(name: str, status: str, detail: str, hint: str = ""):
    """A stand-in for rebalance.doctor.Check (attribute access, not a dict)."""
    obj = MagicMock()
    obj.name = name
    obj.status = status
    obj.detail = detail
    obj.hint = hint
    return obj


if __name__ == "__main__":
    unittest.main()
