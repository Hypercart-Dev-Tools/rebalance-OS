"""Tests for the `rebalance doctor` health check (src/rebalance/doctor.py).

The token / vault / launchd checks read live machine state and are not
asserted on; these tests cover the database-backed checks (driven by a temp
DB) and the report aggregation logic.
"""

import tempfile
import unittest
from pathlib import Path

from rebalance.doctor import (
    FAIL,
    OK,
    WARN,
    Check,
    DoctorReport,
    _check_calendar,
    _check_gmail,
    _check_pulse,
    _check_sleuth,
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


class IntegrationCheckTests(unittest.TestCase):
    """Sleuth / Gmail / Calendar credential checks."""

    def test_sleuth_missing_env_warns(self) -> None:
        import rebalance.paths as paths_mod

        original = paths_mod.resolve_secret_path
        with tempfile.TemporaryDirectory() as tmp:
            paths_mod.resolve_secret_path = lambda name: Path(tmp) / name
            try:
                check = _check_sleuth()
            finally:
                paths_mod.resolve_secret_path = original
        self.assertEqual(check.status, WARN)
        self.assertIn("env file", check.detail)

    def test_sleuth_incomplete_env_warns(self) -> None:
        import rebalance.paths as paths_mod

        original = paths_mod.resolve_secret_path
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / "sleuth-web-api-production.env"
            env.write_text("SLEUTH_WEB_API_BASE_URL=https://x\n", encoding="utf-8")
            paths_mod.resolve_secret_path = lambda name: Path(tmp) / name
            try:
                check = _check_sleuth()
            finally:
                paths_mod.resolve_secret_path = original
        self.assertEqual(check.status, WARN)
        self.assertIn("missing keys", check.detail)

    def test_sleuth_complete_env_ok(self) -> None:
        import rebalance.paths as paths_mod

        original = paths_mod.resolve_secret_path
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / "sleuth-web-api-production.env"
            env.write_text(
                "SLEUTH_WEB_API_BASE_URL=https://x\n"
                "SLEUTH_WEB_API_TOKEN=tok\n"
                "SLEUTH_WORKSPACE_NAME=ws\n",
                encoding="utf-8",
            )
            paths_mod.resolve_secret_path = lambda name: Path(tmp) / name
            try:
                check = _check_sleuth()
            finally:
                paths_mod.resolve_secret_path = original
        self.assertEqual(check.status, OK)

    def test_calendar_token_presence(self) -> None:
        import rebalance.ingest.calendar as cal_mod

        original = cal_mod.TOKEN_PATH
        with tempfile.TemporaryDirectory() as tmp:
            cal_mod.TOKEN_PATH = Path(tmp) / "oauth"
            try:
                self.assertEqual(_check_calendar().status, WARN)
                cal_mod.TOKEN_PATH.write_bytes(b"token-bytes")
                self.assertEqual(_check_calendar().status, OK)
            finally:
                cal_mod.TOKEN_PATH = original

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


if __name__ == "__main__":
    unittest.main()
