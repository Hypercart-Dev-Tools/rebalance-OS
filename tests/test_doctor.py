"""Tests for the `rebalance doctor` health check (src/rebalance/doctor.py).

The token / vault / launchd checks read live machine state and are not
asserted on; these tests cover the database-backed checks (driven by a temp
DB) and the report aggregation logic.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from rebalance.cli import app
from rebalance.doctor import (
    FAIL,
    OK,
    WARN,
    Check,
    DoctorReport,
    _check_auth_failures,
    _check_calendar,
    _check_figma,
    _check_gmail,
    _check_pulse,
    _check_pulse_collectors,
    _check_sleuth,
    _diagnostics_index,
    run_doctor,
)
from rebalance.ingest.db import db_connection, ensure_baseline_schema, run_migrations


class DoctorReportTests(unittest.TestCase):
    def test_aggregation_properties(self) -> None:
        clean = DoctorReport(checks=[Check("a", OK, ""), Check("b", OK, "")])
        self.assertFalse(clean.failed)
        self.assertFalse(clean.warned)

        warned = DoctorReport(checks=[Check("a", OK, ""), Check("b", WARN, "")])
        self.assertFalse(warned.failed)
        self.assertTrue(warned.warned)

        failed = DoctorReport(checks=[Check("a", WARN, ""), Check("b", FAIL, "")])
        self.assertTrue(failed.failed)
        self.assertTrue(failed.warned)


class DoctorCheckTests(unittest.TestCase):
    def _by_name(self, report: DoctorReport) -> dict[str, Check]:
        return {c.name: c for c in report.checks}

    def test_fresh_db_warns_on_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "rebalance.db"
            # Baseline tables, but no schema_version stamp and no data.
            with db_connection(db, ensure_baseline_schema):
                pass
            checks = self._by_name(run_doctor(db))

            self.assertEqual(checks["database"].status, OK)
            self.assertEqual(checks["schema"].status, WARN)       # not stamped
            self.assertEqual(checks["projects"].status, WARN)     # 0 registered
            self.assertEqual(checks["github data"].status, WARN)  # no activity

    def test_migrated_db_reports_schema_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "rebalance.db"
            with db_connection(db) as conn:
                run_migrations(conn)  # baseline + schema_version stamp
            checks = self._by_name(run_doctor(db))
            self.assertEqual(checks["schema"].status, OK)
            self.assertIn("version", checks["schema"].detail)

    def test_populated_db_reports_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "rebalance.db"
            with db_connection(db) as conn:
                run_migrations(conn)
                conn.execute(
                    "INSERT INTO project_registry (name, status) VALUES ('demo', 'active')"
                )
                conn.execute(
                    "INSERT INTO github_activity "
                    "(login, repo_full_name, scan_date, scanned_at) "
                    "VALUES ('me', 'org/repo', date('now'), date('now'))"
                )
                conn.commit()
            checks = self._by_name(run_doctor(db))
            self.assertEqual(checks["projects"].status, OK)
            self.assertEqual(checks["projects"].detail, "1 registered")
            self.assertEqual(checks["github data"].status, OK)

    def test_stale_github_data_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "rebalance.db"
            with db_connection(db) as conn:
                run_migrations(conn)
                conn.execute(
                    "INSERT INTO github_activity "
                    "(login, repo_full_name, scan_date, scanned_at) "
                    "VALUES ('me', 'org/repo', date('now', '-10 days'), date('now'))"
                )
                conn.commit()
            checks = self._by_name(run_doctor(db))
            self.assertEqual(checks["github data"].status, WARN)
            self.assertIn("stale", checks["github data"].detail)

    def test_unresolvable_db_fails(self) -> None:
        # When no database can be resolved at all, the database check fails.
        import rebalance.paths as paths_mod

        original = paths_mod.resolve_database_path

        def _raise(explicit=None):  # noqa: ANN001 — test stub
            # DatabaseNotFoundError takes a candidates list; empty == none found.
            raise paths_mod.DatabaseNotFoundError([])

        paths_mod.resolve_database_path = _raise
        try:
            checks = self._by_name(run_doctor())
            self.assertEqual(checks["database"].status, FAIL)
        finally:
            paths_mod.resolve_database_path = original


class DoctorCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_doctor_cli_prints_degraded_signal_health_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "rebalance.db"
            with db_connection(db) as conn:
                run_migrations(conn)
                conn.execute(
                    "INSERT INTO vault_files (rel_path, content_hash, ingested_at, last_modified) "
                    "VALUES ('stale.md', 'hash1', datetime('now'), datetime('now', '-10 days'))"
                )
                conn.commit()

            report = DoctorReport(checks=[Check("database", OK, str(db))])
            with patch("rebalance.doctor.run_doctor", return_value=report):
                result = self.runner.invoke(app, ["doctor", "--database", str(db)])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("signal health", result.output)
        self.assertIn("vault", result.output)
        self.assertIn("0 rows landed", result.output)
        self.assertIn("last 7d", result.output)


class IntegrationCheckTests(unittest.TestCase):
    """Sleuth / Gmail / Calendar credential checks."""

    # _check_sleuth now resolves keyring → config → env file; these exercise the
    # env-file fallback with keyring/config explicitly empty.
    def test_sleuth_missing_env_warns(self) -> None:
        import rebalance.paths as paths_mod
        from rebalance.ingest import config as config_mod

        original = paths_mod.resolve_secret_path
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(config_mod, "_keyring_get", return_value=None), \
             patch.object(config_mod, "_read_config", return_value={}):
            paths_mod.resolve_secret_path = lambda name: Path(tmp) / name
            try:
                check = _check_sleuth()
            finally:
                paths_mod.resolve_secret_path = original
        self.assertEqual(check.status, WARN)
        self.assertIn("credentials", check.detail)

    def test_sleuth_incomplete_env_warns(self) -> None:
        import rebalance.paths as paths_mod
        from rebalance.ingest import config as config_mod

        original = paths_mod.resolve_secret_path
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(config_mod, "_keyring_get", return_value=None), \
             patch.object(config_mod, "_read_config", return_value={}):
            env = Path(tmp) / "sleuth-web-api-production.env"
            env.write_text("SLEUTH_WEB_API_BASE_URL=https://x\n", encoding="utf-8")
            paths_mod.resolve_secret_path = lambda name: Path(tmp) / name
            try:
                check = _check_sleuth()
            finally:
                paths_mod.resolve_secret_path = original
        self.assertEqual(check.status, WARN)
        self.assertIn("missing", check.detail)

    def test_sleuth_complete_keyring_ok(self) -> None:
        # Creds in keyring → OK regardless of env files (the new primary path).
        from rebalance.ingest import config as config_mod
        import json
        blob = json.dumps({
            "SLEUTH_WEB_API_BASE_URL": "https://x",
            "SLEUTH_WEB_API_TOKEN": "tok",
            "SLEUTH_WORKSPACE_NAME": "ws",
        })
        with patch.object(config_mod, "_keyring_get", return_value=blob):
            check = _check_sleuth()
        self.assertEqual(check.status, OK)
        self.assertIn("keyring", check.detail)

    def test_calendar_token_presence(self) -> None:
        # _check_calendar resolves keyring → secret-store JSON → legacy pickle.
        # Force keyring empty; secret store is conftest-isolated; seam the legacy
        # pickle path to a tmp dir so the real machine's token doesn't leak in.
        from rebalance.ingest import config as config_mod
        from rebalance.ingest import secret_store
        import rebalance.paths as paths_mod

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(config_mod, "get_calendar_oauth_token_json", return_value=None), \
             patch.object(paths_mod, "resolve_oauth_token_path", return_value=Path(tmp) / "legacy-pickle"):
            secret_store.delete_secret_file("google-calendar-oauth")  # ensure empty
            # keyring empty + secret store empty + no legacy pickle → WARN
            warn_check = _check_calendar()
            self.assertEqual(warn_check.status, WARN)
            self.assertIn("no Calendar OAuth credentials", warn_check.detail)
            self.assertTrue(warn_check.hint.startswith("🔧 "))
            # A JSON token in the (isolated) secret store → OK via secret-store JSON
            secret_store.write_secret_file("google-calendar-oauth", '{"token": "t"}')
            ok_check = _check_calendar()
            self.assertEqual(ok_check.status, OK)
            self.assertIn("secret-store JSON", ok_check.detail)

    def test_figma_unconfigured_is_clean_skip(self) -> None:
        # Opt-in source with neither token nor file keys → OK, not a nag.
        from rebalance.ingest import config as config_mod

        with patch.object(config_mod, "_get_secret_dual_store", return_value=(None, None)), \
             patch.object(config_mod, "get_figma_file_keys", return_value=[]):
            check = _check_figma()
        self.assertEqual(check.status, OK)
        self.assertIn("not configured", check.detail)

    def test_figma_token_and_files_reports_source(self) -> None:
        from rebalance.ingest import config as config_mod

        with patch.object(config_mod, "_get_secret_dual_store", return_value=("tok", "keyring")), \
             patch.object(config_mod, "get_figma_file_keys", return_value=["abc", "def"]):
            check = _check_figma()
        self.assertEqual(check.status, OK)
        self.assertIn("keyring", check.detail)
        self.assertIn("2 file", check.detail)

    def test_figma_file_keys_without_token_warns(self) -> None:
        from rebalance.ingest import config as config_mod

        with patch.object(config_mod, "_get_secret_dual_store", return_value=(None, None)), \
             patch.object(config_mod, "get_figma_file_keys", return_value=["abc"]):
            check = _check_figma()
        self.assertEqual(check.status, WARN)
        self.assertIn("no token", check.detail)

    def test_figma_token_without_file_keys_warns(self) -> None:
        from rebalance.ingest import config as config_mod

        with patch.object(config_mod, "_get_secret_dual_store", return_value=("tok", "config")), \
             patch.object(config_mod, "get_figma_file_keys", return_value=[]):
            check = _check_figma()
        self.assertEqual(check.status, WARN)
        self.assertIn("no file keys", check.detail)

    def test_pulse_missing_config_warns(self) -> None:
        import rebalance.ingest.config as config_mod

        original = config_mod.CONFIG_PATH
        with tempfile.TemporaryDirectory() as tmp:
            config_mod.CONFIG_PATH = Path(tmp) / "rbos.config"
            try:
                check = _check_pulse()
            finally:
                config_mod.CONFIG_PATH = original
        self.assertEqual(check.status, WARN)
        self.assertIn("pulse config missing keys", check.detail)

    def test_gmail_check_never_crashes(self) -> None:
        # ADC / MCP state is machine-dependent; assert only that the check is
        # well-formed and never raises.
        check = _check_gmail(None)
        self.assertEqual(check.name, "gmail")
        self.assertIn(check.status, (OK, WARN, FAIL))


class AuthFailureCheckTests(unittest.TestCase):
    """_check_auth_failures reads the unified auth log via auth_log."""

    def test_no_history_emits_no_checks(self) -> None:
        with patch("rebalance.ingest.auth_log.latest_event_by_source", return_value={}):
            self.assertEqual(_check_auth_failures(), [])

    def test_all_recovered_emits_single_ok(self) -> None:
        latest = {
            "github": {"event": "token_validated", "ts": "2026-06-02T10:00:00+00:00", "device": "mac"},
            "calendar": {"event": "token_refreshed", "ts": "2026-06-02T09:00:00+00:00", "device": "mac"},
        }
        with patch("rebalance.ingest.auth_log.latest_event_by_source", return_value=latest):
            checks = _check_auth_failures()
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, OK)
        self.assertEqual(checks[0].name, "auth log")

    def test_active_failure_warns_per_source(self) -> None:
        latest = {
            # github's latest event is a failure → active deauth
            "github": {"event": "auth_failed", "ts": "2026-06-02T12:00:00+00:00", "device": "studio"},
            # calendar recovered → no warn
            "calendar": {"event": "flow_succeeded", "ts": "2026-06-02T11:00:00+00:00", "device": "studio"},
        }
        with patch("rebalance.ingest.auth_log.latest_event_by_source", return_value=latest):
            checks = _check_auth_failures()
        names = {c.name: c for c in checks}
        self.assertIn("auth:github", names)
        self.assertEqual(names["auth:github"].status, WARN)
        self.assertIn("auth_failed", names["auth:github"].detail)
        self.assertIn("studio", names["auth:github"].detail)
        self.assertTrue(names["auth:github"].hint)  # per-source remediation hint
        self.assertNotIn("auth:calendar", names)  # recovered, not flagged

    def test_never_crashes_on_reader_error(self) -> None:
        with patch(
            "rebalance.ingest.auth_log.latest_event_by_source",
            side_effect=RuntimeError("boom"),
        ):
            self.assertEqual(_check_auth_failures(), [])


class PulseCollectorCheckTests(unittest.TestCase):
    """_check_pulse_collectors maps pulse_health states to OK/WARN checks."""

    def _health(self, name, state, *, healthy, age_hours, failures=0, examples=""):
        from rebalance.ingest.pulse_health import CollectorHealth

        # classify() derives age_hours FROM last_scan_utc, so a row carrying an
        # age always carries the scan timestamp it was computed from. Derive it
        # here for the same reason: pinning the two independently produced a
        # state read_collector_health() cannot emit — an age with no scan — and
        # the check only kept passing because it read the age directly.
        last_scan = datetime.now(timezone.utc) - timedelta(hours=age_hours)
        h = CollectorHealth(
            device_id=name, device_name=name, last_scan_utc=last_scan,
            repo_scan_failures=failures, scan_failure_examples=examples,
        )
        h.state, h.age_hours = state, age_hours
        return h

    def test_alive_is_ok_degraded_and_alert_warn(self) -> None:
        devices = [
            self._health("Broken", "DEGRADED", healthy=False, age_hours=0.3,
                         failures=4, examples="repo-a"),
            self._health("Stale", "ALERT", healthy=False, age_hours=30.0),
            self._health("Fine", "ALIVE", healthy=True, age_hours=1.0),
        ]
        with patch(
            "rebalance.ingest.pulse_health.read_collector_health",
            return_value=devices,
        ):
            checks = _check_pulse_collectors()
        by = {c.name: c for c in checks}
        self.assertEqual(by["pulse collector:Broken"].status, WARN)
        self.assertIn("4 repo scan failures", by["pulse collector:Broken"].detail)
        self.assertIn("repo-a", by["pulse collector:Broken"].detail)
        self.assertEqual(by["pulse collector:Stale"].status, WARN)
        # GH-189 re-sourced this from format_timestamp(relative=True), which
        # emits an absolute anchor plus the compact relative and returns ""
        # rather than a bare relative — so assert the anchor, not just the age.
        stale_detail = by["pulse collector:Stale"].detail
        self.assertIn("1d ago", stale_detail)  # 30h → days
        self.assertRegex(stale_detail, r"last scan \d{4}-\d{2}-\d{2} \d{1,2}:\d{2} [AP]M · ")
        self.assertEqual(by["pulse collector:Fine"].status, OK)

    def test_empty_when_no_collectors(self) -> None:
        with patch(
            "rebalance.ingest.pulse_health.read_collector_health", return_value=[]
        ):
            self.assertEqual(_check_pulse_collectors(), [])

    def test_never_crashes_on_reader_error(self) -> None:
        with patch(
            "rebalance.ingest.pulse_health.read_collector_health",
            side_effect=RuntimeError("boom"),
        ):
            self.assertEqual(_check_pulse_collectors(), [])


class DiagnosticsIndexTests(unittest.TestCase):
    """_diagnostics_index maps every observability surface as OK info rows."""

    def test_index_lists_surfaces_and_is_informational(self) -> None:
        checks = _diagnostics_index()
        names = {c.name for c in checks}
        # The map always includes the static surfaces.
        self.assertIn("diagnostics: git-pulse", names)
        self.assertIn("diagnostics: repo probes", names)
        self.assertIn("diagnostics: health reporter", names)
        # All informational — never gate exit status.
        self.assertTrue(all(c.status == OK for c in checks))

    def test_index_never_raises_if_auth_log_unavailable(self) -> None:
        with patch(
            "rebalance.ingest.auth_log.latest_event_by_source",
            side_effect=RuntimeError("boom"),
        ):
            checks = _diagnostics_index()
        # auth-log row is skipped on error, but the static surfaces remain.
        self.assertTrue(any(c.name == "diagnostics: git-pulse" for c in checks))


if __name__ == "__main__":
    unittest.main()
