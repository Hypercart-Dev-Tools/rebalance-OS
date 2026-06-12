"""Tests for inferred project registry generation from GitHub and Calendar activity."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest import config as config_module
from rebalance.ingest.calendar_config import CalendarConfig
from rebalance.ingest.config import set_github_ignored_repos
from rebalance.ingest.db import (
    db_connection,
    ensure_calendar_schema,
    ensure_github_schema,
    ensure_project_schema,
)
from rebalance.ingest.project_inference import infer_project_registry, sync_inferred_project_registry


class ProjectInferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def _calendar_config(self) -> CalendarConfig:
        return CalendarConfig(
            calendar_id="primary",
            exclude_titles=[],
            aggregator_skip_words=[],
            timezone="America/Los_Angeles",
            projects=[],
            hours_format="decimal",
        )

    def test_infers_binoid_from_github_and_ltvera_from_calendar_only(self) -> None:
        db_path = Path(self._tmp.name) / "rebalance.db"
        set_github_ignored_repos(["dlt-hub/dlt"])

        with db_connection(db_path) as conn:
            ensure_github_schema(conn)
            ensure_calendar_schema(conn)
            conn.execute(
                """
                INSERT INTO github_activity
                    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
                     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "tester",
                    "AcmeTeam/sample-child-theme-oct-2024",
                    "2026-04-28",
                    5,
                    5,
                    1,
                    0,
                    2,
                    0,
                    0,
                    "2026-04-27T20:18:42Z",
                    "2026-04-28T14:47:36Z",
                ),
            )
            conn.execute(
                """
                INSERT INTO github_activity
                    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
                     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "tester",
                    "dlt-hub/dlt",
                    "2026-04-28",
                    99,
                    99,
                    0,
                    0,
                    0,
                    0,
                    0,
                    "2026-04-27T20:18:42Z",
                    "2026-04-28T14:47:36Z",
                ),
            )
            conn.executemany(
                """
                INSERT INTO calendar_events
                    (id, summary, start_time, end_time, location, attendees_json,
                     calendar_id, status, description, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "evt-1",
                        "Post Acme Kanban screenshot for Charlie",
                        "2026-04-28T11:00:00-07:00",
                        "2026-04-28T11:15:00-07:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-28T15:12:24Z",
                    ),
                    (
                        "evt-2",
                        "BetaReport Weekly",
                        "2026-04-24T14:00:00-07:00",
                        "2026-04-24T14:25:00-07:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-28T15:12:24Z",
                    ),
                    (
                        "evt-3",
                        "BetaReport Weekly",
                        "2026-04-17T14:00:00-07:00",
                        "2026-04-17T14:25:00-07:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-28T15:12:24Z",
                    ),
                ],
            )
            conn.commit()

        projects, summary = infer_project_registry(
            db_path,
            calendar_config=self._calendar_config(),
            calendar_days_back=90,
            calendar_days_forward=14,
        )

        self.assertEqual(summary.github_backed_count, 1)
        names = [project["name"] for project in projects]
        self.assertIn("Acme", names)
        self.assertIn("BetaReport", names)
        self.assertNotIn("Dlt", " ".join(names))

        by_name = {project["name"]: project for project in projects}
        self.assertEqual(
            by_name["Acme"]["repos"],
            ["AcmeTeam/sample-child-theme-oct-2024"],
        )
        self.assertIn("source:github", by_name["Acme"]["tags"])
        self.assertIn("source:calendar", by_name["Acme"]["tags"])
        self.assertEqual(by_name["BetaReport"]["repos"], [])
        self.assertIn("source:calendar", by_name["BetaReport"]["tags"])

    def test_sync_replaces_stale_inferred_rows(self) -> None:
        db_path = Path(self._tmp.name) / "rebalance.db"
        with db_connection(db_path) as conn:
            ensure_github_schema(conn)
            ensure_calendar_schema(conn)
            ensure_project_schema(conn)
            conn.execute(
                """
                INSERT INTO github_activity
                    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
                     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "tester",
                    "Hypercart-Dev-Tools/rebalance-OS",
                    "2026-04-28",
                    10,
                    10,
                    0,
                    0,
                    0,
                    0,
                    0,
                    "2026-04-27T19:11:32Z",
                    "2026-04-28T14:47:36Z",
                ),
            )
            conn.execute(
                """
                INSERT INTO project_registry
                    (name, status, summary, value_level, priority_tier, risk_level,
                     repos_json, tags_json, custom_fields_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Old Project",
                    "active",
                    "",
                    None,
                    None,
                    None,
                    "[]",
                    "[]",
                    json.dumps({"inference": {"generated_by": "activity_inference_v1"}}),
                ),
            )
            conn.commit()

        summary = sync_inferred_project_registry(
            db_path,
            calendar_config=self._calendar_config(),
        )
        self.assertGreaterEqual(summary.updated_count, 1)
        self.assertEqual(summary.deleted_stale_inferred_count, 1)

        with db_connection(db_path, ensure_project_schema) as conn:
            names = [row["name"] for row in conn.execute("SELECT name FROM project_registry ORDER BY name").fetchall()]
        self.assertIn("Rebalance OS", names)
        self.assertNotIn("Old Project", names)


class CuratedRowProtectionTests(unittest.TestCase):
    """machine_owned contract: inference never creates, updates, or deletes
    a row the operator curated — even on a name collision."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def _calendar_config(self) -> CalendarConfig:
        return CalendarConfig(
            calendar_id="primary",
            exclude_titles=[],
            aggregator_skip_words=[],
            timezone="America/Los_Angeles",
            projects=[],
            hours_format="decimal",
        )

    def test_curated_row_with_colliding_name_is_never_overwritten(self) -> None:
        db_path = Path(self._tmp.name) / "rebalance.db"
        curated_fields = {"aliases": ["rebalance"], "priority_source": "operator"}
        with db_connection(db_path) as conn:
            ensure_github_schema(conn)
            ensure_calendar_schema(conn)
            ensure_project_schema(conn)
            conn.execute(
                """
                INSERT INTO github_activity
                    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
                     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "tester",
                    "Hypercart-Dev-Tools/rebalance-OS",
                    "2026-04-28",
                    10, 10, 0, 0, 0, 0, 0,
                    "2026-04-27T19:11:32Z",
                    "2026-04-28T14:47:36Z",
                ),
            )
            # Operator-curated row whose name collides with the inferred seed.
            conn.execute(
                """
                INSERT INTO project_registry
                    (name, status, summary, value_level, priority_tier, risk_level,
                     repos_json, tags_json, custom_fields_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Rebalance OS",
                    "active",
                    "CURATED - operator owned",
                    "high",
                    1,
                    None,
                    json.dumps(["Hypercart-Dev-Tools/rebalance-OS"]),
                    json.dumps(["curated"]),
                    json.dumps(curated_fields),
                ),
            )
            conn.commit()

        summary = sync_inferred_project_registry(
            db_path,
            calendar_config=self._calendar_config(),
        )

        self.assertIn("Rebalance OS", summary.project_names)  # still inferred...
        self.assertEqual(summary.skipped_curated_names, ["Rebalance OS"])  # ...but skipped
        self.assertEqual(summary.skipped_curated_count, 1)
        self.assertEqual(summary.updated_count, 0)
        self.assertEqual(summary.deleted_stale_inferred_count, 0)

        with db_connection(db_path, ensure_project_schema) as conn:
            row = conn.execute(
                "SELECT * FROM project_registry WHERE name = ?", ("Rebalance OS",)
            ).fetchone()
        self.assertEqual(row["summary"], "CURATED - operator owned")
        self.assertEqual(row["priority_tier"], 1)
        self.assertEqual(row["value_level"], "high")
        self.assertEqual(json.loads(row["custom_fields_json"]), curated_fields)

        # Repeat sync is idempotent: curated row still untouched, never deleted.
        summary2 = sync_inferred_project_registry(
            db_path,
            calendar_config=self._calendar_config(),
        )
        self.assertEqual(summary2.skipped_curated_names, ["Rebalance OS"])
        self.assertEqual(summary2.deleted_stale_inferred_count, 0)
        with db_connection(db_path, ensure_project_schema) as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM project_registry WHERE summary = ?",
                ("CURATED - operator owned",),
            ).fetchone()["c"]
        self.assertEqual(count, 1)
