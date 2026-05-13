import tempfile
import unittest
from datetime import date
from pathlib import Path

from rebalance.ingest.calendar import ensure_calendar_schema
from rebalance.ingest.calendar_config import CalendarConfig, CalendarProject
from rebalance.ingest.daily_report import group_similar_events
from rebalance.ingest.db import get_connection
from rebalance.ingest.project_classifier import classify_event_project, load_project_matchers
from rebalance.ingest.registry import sync_db
from rebalance.ingest.weekly_report import generate_weekly_report


class CalendarAggregatorTests(unittest.TestCase):
    """Aggregator + classifier tests using fictional projects.

    All fixtures use placeholder names (AcmeCorp, BetaCorp, AcmeReg, DeltaApp,
    GammaGardens) so the tests stay independent of the operator's real
    project list. Each call into the classifier or a report generator
    passes ``priority_rules=[]`` so `_build_matchers_from_priority_rules`
    cannot silently pull operator-local priority rules into the test corpus.
    """

    def test_group_similar_events_skips_common_verbs_and_config_tokens(self) -> None:
        events = [
            {
                "summary": "AR - if I can make progress",
                "start_time": "2026-03-31T16:00:00+00:00",
                "end_time": "2026-03-31T16:30:00+00:00",
            },
            {
                "summary": "BC - change test account betacorp",
                "start_time": "2026-03-31T16:30:00+00:00",
                "end_time": "2026-03-31T17:00:00+00:00",
            },
            {
                "summary": "Check Slack AcmeCorp handoff",
                "start_time": "2026-03-31T17:00:00+00:00",
                "end_time": "2026-03-31T17:30:00+00:00",
            },
            {
                "summary": "Test new Tango Widgets code",
                "start_time": "2026-03-31T17:30:00+00:00",
                "end_time": "2026-03-31T18:00:00+00:00",
            },
        ]

        groups = group_similar_events(events)

        self.assertIn("Ar", groups)
        self.assertIn("Bc", groups)
        self.assertIn("Acmecorp", groups)
        self.assertIn("Tango", groups)
        self.assertNotIn("can", groups)
        self.assertNotIn("change", groups)
        self.assertNotIn("check", groups)
        self.assertNotIn("slack", groups)
        self.assertNotIn("test", groups)

    def test_weekly_report_skips_low_signal_group_labels(self) -> None:
        config = CalendarConfig(
            calendar_id="primary",
            exclude_titles=["Check Slack"],
            aggregator_skip_words=[],
            timezone="America/Los_Angeles",
            projects=[],
            hours_format="hm",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "calendar.db"
            conn = get_connection(database_path)
            ensure_calendar_schema(conn)
            conn.executemany(
                """
                INSERT INTO calendar_events
                (id, summary, start_time, end_time, location, attendees_json,
                 calendar_id, status, description, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "event-1",
                        "AR - if I can make progress",
                        "2026-03-31T16:00:00+00:00",
                        "2026-03-31T16:30:00+00:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-07T10:00:00+00:00",
                    ),
                    (
                        "event-2",
                        "BC - change test account betacorp",
                        "2026-04-01T16:00:00+00:00",
                        "2026-04-01T16:30:00+00:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-07T10:00:00+00:00",
                    ),
                    (
                        "event-3",
                        "Test new Tango Widgets code",
                        "2026-04-02T16:00:00+00:00",
                        "2026-04-02T16:30:00+00:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-07T10:00:00+00:00",
                    ),
                    (
                        "event-4",
                        "Weekly Recap & Timesheet",
                        "2026-04-03T16:00:00+00:00",
                        "2026-04-03T16:30:00+00:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-07T10:00:00+00:00",
                    ),
                ],
            )
            conn.commit()
            conn.close()

            report = generate_weekly_report(
                database_path,
                target_date=date(2026, 3, 31),
                config=config,
                priority_rules=[],
            )

        self.assertIn("| Ar | 1 | 30m |", report)
        self.assertIn("| Bc | 1 | 30m |", report)
        self.assertIn("| Tango | 1 | 30m |", report)
        self.assertIn("| Timesheet | 1 | 30m |", report)
        self.assertNotIn("| Can |", report)
        self.assertNotIn("| Change |", report)
        self.assertNotIn("| Check |", report)
        self.assertNotIn("| Slack |", report)
        self.assertNotIn("| Weekly |", report)

    def test_project_classifier_uses_registry_aliases_as_ssot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "calendar.db"
            sync_db(
                database_path,
                {
                    "projects": [
                        {
                            "name": "AcmeReg",
                            "status": "active",
                            "summary": "",
                            "value_level": None,
                            "priority_tier": 1,
                            "risk_level": None,
                            "repos": ["acme-reg"],
                            "tags": ["#project-acme-reg"],
                            "custom_fields": {
                                "calendar_aliases": ["AR"],
                            },
                        }
                    ]
                },
            )

            matchers = load_project_matchers(database_path, priority_rules=[])

        self.assertEqual(classify_event_project("AR - CC", matchers), "AcmeReg")
        self.assertEqual(
            classify_event_project("Work on acme reg backlog", matchers),
            "AcmeReg",
        )

    def test_weekly_report_prefers_registry_project_names_before_heuristics(self) -> None:
        config = CalendarConfig(
            calendar_id="primary",
            exclude_titles=[],
            aggregator_skip_words=[],
            timezone="America/Los_Angeles",
            projects=[],
            hours_format="hm",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "calendar.db"
            sync_db(
                database_path,
                {
                    "projects": [
                        {
                            "name": "AcmeReg",
                            "status": "active",
                            "summary": "",
                            "value_level": None,
                            "priority_tier": 1,
                            "risk_level": None,
                            "repos": ["acme-reg"],
                            "tags": ["#project-acme-reg"],
                            "custom_fields": {"calendar_aliases": ["AR"]},
                        },
                        {
                            "name": "DeltaApp",
                            "status": "active",
                            "summary": "",
                            "value_level": None,
                            "priority_tier": 2,
                            "risk_level": None,
                            "repos": ["delta-app"],
                            "tags": ["#project-delta-app"],
                            "custom_fields": {"calendar_aliases": ["DA"]},
                        },
                    ]
                },
            )
            conn = get_connection(database_path)
            ensure_calendar_schema(conn)
            conn.executemany(
                """
                INSERT INTO calendar_events
                (id, summary, start_time, end_time, location, attendees_json,
                 calendar_id, status, description, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "event-1",
                        "AR - CC",
                        "2026-03-31T16:00:00+00:00",
                        "2026-03-31T16:30:00+00:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-07T10:00:00+00:00",
                    ),
                    (
                        "event-2",
                        "DA - iOS React Native library update",
                        "2026-04-01T16:00:00+00:00",
                        "2026-04-01T17:00:00+00:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-07T10:00:00+00:00",
                    ),
                    (
                        "event-3",
                        "Test new Tango Widgets code",
                        "2026-04-02T16:00:00+00:00",
                        "2026-04-02T16:30:00+00:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-07T10:00:00+00:00",
                    ),
                ],
            )
            conn.commit()
            conn.close()

            report = generate_weekly_report(
                database_path,
                target_date=date(2026, 3, 31),
                config=config,
                priority_rules=[],
            )

        self.assertIn("| AcmeReg | 1 | 30m |", report)
        self.assertIn("| DeltaApp | 1 | 1h |", report)
        self.assertIn("| Tango | 1 | 30m |", report)
        self.assertNotIn("| Ar |", report)
        self.assertNotIn("| Da |", report)

    def test_weekly_report_uses_calendar_config_projects_when_registry_is_missing(self) -> None:
        config = CalendarConfig(
            calendar_id="primary",
            exclude_titles=[],
            aggregator_skip_words=[],
            timezone="America/Los_Angeles",
            projects=[
                CalendarProject(name="BetaCorp", aliases=["BC"]),
                CalendarProject(name="GammaGardens", aliases=["GG", "Gamma's Gardens"]),
            ],
            hours_format="hm",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "calendar.db"
            conn = get_connection(database_path)
            ensure_calendar_schema(conn)
            conn.executemany(
                """
                INSERT INTO calendar_events
                (id, summary, start_time, end_time, location, attendees_json,
                 calendar_id, status, description, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "event-1",
                        "BC - change account workflow",
                        "2026-03-31T16:00:00+00:00",
                        "2026-03-31T16:30:00+00:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-07T10:00:00+00:00",
                    ),
                    (
                        "event-2",
                        "GG - iOS React Native library update",
                        "2026-04-01T16:00:00+00:00",
                        "2026-04-01T17:00:00+00:00",
                        "",
                        "[]",
                        "primary",
                        "confirmed",
                        "",
                        "2026-04-07T10:00:00+00:00",
                    ),
                ],
            )
            conn.commit()
            conn.close()

            report = generate_weekly_report(
                database_path,
                target_date=date(2026, 3, 31),
                config=config,
                priority_rules=[],
            )

        self.assertIn("| BetaCorp | 1 | 30m |", report)
        self.assertIn("| GammaGardens | 1 | 1h |", report)
        self.assertNotIn("| Bc |", report)
        self.assertNotIn("| Gg |", report)


if __name__ == "__main__":
    unittest.main()
