"""Tests for local project/client priority overlays."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from rebalance.ingest import config as config_module
from rebalance.ingest.calendar_config import CalendarConfig
from rebalance.ingest.config import set_project_priority_rule
from rebalance.ingest.note_builder import build_dashboard_payload
from rebalance.ingest.db import db_connection, ensure_calendar_schema, ensure_github_schema, ensure_project_schema
from rebalance.ingest.project_classifier import classify_event_project, load_project_matchers


def _calendar_config() -> CalendarConfig:
    return CalendarConfig(
        calendar_id="primary",
        exclude_titles=[],
        aggregator_skip_words=[],
        timezone="America/Los_Angeles",
        projects=[],
        hours_format="decimal",
    )


class ProjectPriorityOverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def _seed_db(self) -> Path:
        db_path = Path(self._tmp.name) / "rebalance.db"
        with db_connection(db_path) as conn:
            ensure_project_schema(conn)
            ensure_github_schema(conn)
            ensure_calendar_schema(conn)
            conn.executemany(
                """
                INSERT INTO project_registry
                    (name, status, summary, value_level, priority_tier, risk_level,
                     repos_json, tags_json, custom_fields_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "Client Alpha",
                        "active",
                        "Strategic project with explicit local priority.",
                        None,
                        None,
                        None,
                        "[]",
                        "[]",
                        json.dumps({"aliases": ["Alpha Site"]}),
                    ),
                    (
                        "Client Beta",
                        "active",
                        "Unprioritized active project.",
                        None,
                        None,
                        None,
                        "[]",
                        "[]",
                        json.dumps({}),
                    ),
                    (
                        "CG",
                        "active",
                        "Abbreviated registry row with a clearer local display name.",
                        None,
                        None,
                        None,
                        "[]",
                        "[]",
                        json.dumps({}),
                    ),
                ],
            )
            conn.commit()
        return db_path

    def test_dashboard_uses_priority_rules_and_virtual_priority_rows(self) -> None:
        db_path = self._seed_db()
        set_project_priority_rule(
            name="Client Alpha",
            aliases=["Alpha Site"],
            client="Account A",
            priority_tier=1,
            value_score=10,
            value_level="strategic",
            risk_level="high",
        )
        set_project_priority_rule(
            name="Client Gamma",
            aliases=["CG"],
            client="Account G",
            priority_tier=2,
            value_score=9,
            value_level="revenue-generating",
            risk_level="medium",
        )
        set_project_priority_rule(
            name="Client Delta",
            aliases=["Delta Work"],
            client="Account D",
            priority_tier=3,
            value_score=8,
            value_level="revenue-generating",
            risk_level="medium",
        )

        payload = build_dashboard_payload(
            db_path,
            target_date=date(2026, 5, 5),
            since_days=14,
            config=_calendar_config(),
            changelog_path=Path(self._tmp.name) / "missing-changelog.md",
            goals_path=Path(self._tmp.name) / "missing-4x4.md",
        )

        names = [project.name for project in payload.projects]
        self.assertEqual(names[:4], ["Client Alpha", "Client Gamma", "Client Delta", "Client Beta"])
        self.assertNotIn("CG", names)

        by_name = {project.name: project for project in payload.projects}
        self.assertEqual(by_name["Client Alpha"].priority_tier, 1)
        self.assertEqual(by_name["Client Alpha"].value_score, 10)
        self.assertEqual(by_name["Client Alpha"].client, "Account A")
        self.assertGreater(by_name["Client Alpha"].priority_score, by_name["Client Beta"].priority_score)

        self.assertEqual(by_name["Client Gamma"].priority_tier, 2)
        self.assertEqual(by_name["Client Gamma"].client, "Account G")

        self.assertEqual(by_name["Client Delta"].priority_tier, 3)
        self.assertIsInstance(payload.org_activity, dict)

    def test_priority_rules_extend_calendar_project_matching(self) -> None:
        db_path = self._seed_db()
        set_project_priority_rule(
            name="Client Gamma",
            aliases=["Gamma Work", "CG"],
            priority_tier=2,
            value_score=9,
        )

        matchers = load_project_matchers(db_path, config=_calendar_config())

        self.assertEqual(classify_event_project("CG launch prep", matchers), "Client Gamma")
        self.assertEqual(classify_event_project("Alpha Site sprint review", matchers), "Client Alpha")


if __name__ == "__main__":
    unittest.main()
