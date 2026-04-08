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
    def test_group_similar_events_skips_common_verbs_and_config_tokens(self) -> None:
        events = [
            {
                "summary": "CR - if I can make progress",
                "start_time": "2026-03-31T16:00:00+00:00",
                "end_time": "2026-03-31T16:30:00+00:00",
            },
            {
                "summary": "BW - change test account bailiwik",
                "start_time": "2026-03-31T16:30:00+00:00",
                "end_time": "2026-03-31T17:00:00+00:00",
            },
            {
                "summary": "Check Slack Binoid handoff",
                "start_time": "2026-03-31T17:00:00+00:00",
                "end_time": "2026-03-31T17:30:00+00:00",
            },
            {
                "summary": "Test new Smart Coupons code",
                "start_time": "2026-03-31T17:30:00+00:00",
                "end_time": "2026-03-31T18:00:00+00:00",
            },
        ]

        groups = group_similar_events(events, ["Check Slack"])

        self.assertIn("Cr", groups)
        self.assertIn("Bw", groups)
        self.assertIn("Binoid", groups)
        self.assertIn("Smart", groups)
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
                        "CR - if I can make progress",
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
                        "BW - change test account bailiwik",
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
                        "Test new Smart Coupons code",
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
            )

        self.assertIn("| Cr | 1 | 30m |", report)
        self.assertIn("| Bw | 1 | 30m |", report)
        self.assertIn("| Smart | 1 | 30m |", report)
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
                            "name": "CreditRegistry",
                            "status": "active",
                            "summary": "",
                            "value_level": None,
                            "priority_tier": 1,
                            "risk_level": None,
                            "repos": ["credit-registry"],
                            "tags": ["#project-credit-registry"],
                            "custom_fields": {
                                "calendar_aliases": ["CR"],
                            },
                        }
                    ]
                },
            )

            matchers = load_project_matchers(database_path)

        self.assertEqual(classify_event_project("CR - CC", matchers), "CreditRegistry")
        self.assertEqual(
            classify_event_project("Work on credit registry backlog", matchers),
            "CreditRegistry",
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
                            "name": "CreditRegistry",
                            "status": "active",
                            "summary": "",
                            "value_level": None,
                            "priority_tier": 1,
                            "risk_level": None,
                            "repos": ["credit-registry"],
                            "tags": ["#project-credit-registry"],
                            "custom_fields": {"calendar_aliases": ["CR"]},
                        },
                        {
                            "name": "NeoNook",
                            "status": "active",
                            "summary": "",
                            "value_level": None,
                            "priority_tier": 2,
                            "risk_level": None,
                            "repos": ["neo-nook"],
                            "tags": ["#project-neo-nook"],
                            "custom_fields": {"calendar_aliases": ["NN"]},
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
                        "CR - CC",
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
                        "NN - iOS React Native library update",
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
                        "Test new Smart Coupons code",
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
            )

        self.assertIn("| CreditRegistry | 1 | 30m |", report)
        self.assertIn("| NeoNook | 1 | 1h |", report)
        self.assertIn("| Smart | 1 | 30m |", report)
        self.assertNotIn("| Cr |", report)
        self.assertNotIn("| Nn |", report)

    def test_weekly_report_uses_calendar_config_projects_when_registry_is_missing(self) -> None:
        config = CalendarConfig(
            calendar_id="primary",
            exclude_titles=[],
            aggregator_skip_words=[],
            timezone="America/Los_Angeles",
            projects=[
                CalendarProject(name="Bailiwik", aliases=["BW"]),
                CalendarProject(name="Normans Nursery", aliases=["NN", "Norman's Nursery"]),
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
                        "BW - change account workflow",
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
                        "NN - iOS React Native library update",
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
            )

        self.assertIn("| Bailiwik | 1 | 30m |", report)
        self.assertIn("| Normans Nursery | 1 | 1h |", report)
        self.assertNotIn("| Bw |", report)
        self.assertNotIn("| Nn |", report)


if __name__ == "__main__":
    unittest.main()
