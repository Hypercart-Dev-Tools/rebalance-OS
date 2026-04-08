"""Tests for calendar report generation — duration formatting, daily reports, weekly reports,
and calendar-sync config resolution."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from rebalance.ingest.calendar import ensure_calendar_schema
from rebalance.ingest.calendar_config import CalendarConfig, CalendarProject
from rebalance.ingest.daily_report import (
    _format_duration,
    format_daily_markdown,
    generate_daily_report,
    get_day_data,
)
from rebalance.ingest.db import get_connection
from rebalance.ingest.weekly_report import generate_weekly_report


# ── Helpers ──────────────────────────────────────────────────────────────────


def _insert_events(database_path: Path, events: list[tuple], calendar_id: str = "primary") -> None:
    """Insert test events into a fresh calendar_events table."""
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
            (eid, summary, start, end, "", "[]", calendar_id, "confirmed", "", "2026-04-07T10:00:00+00:00")
            for eid, summary, start, end in events
        ],
    )
    conn.commit()
    conn.close()


SAMPLE_EVENTS = [
    ("e1", "Binoid - SEO audit", "2026-03-31T17:00:00+00:00", "2026-03-31T19:15:00+00:00"),
    ("e2", "CR - CC", "2026-03-31T19:30:00+00:00", "2026-03-31T20:00:00+00:00"),
    ("e3", "morning prep", "2026-03-31T16:45:00+00:00", "2026-03-31T17:00:00+00:00"),
]


def _make_config(hours_format: str = "decimal", **kwargs) -> CalendarConfig:
    defaults = dict(
        calendar_id="primary",
        exclude_titles=[],
        aggregator_skip_words=[],
        timezone="America/Los_Angeles",
        projects=[],
        hours_format=hours_format,
    )
    defaults.update(kwargs)
    return CalendarConfig(**defaults)


# ── Format duration ──────────────────────────────────────────────────────────


class FormatDurationTests(unittest.TestCase):
    """Unit tests for the _format_duration helper."""

    # Decimal mode
    def test_decimal_whole_hours(self) -> None:
        self.assertEqual(_format_duration(120, "decimal"), "2.00h")

    def test_decimal_fractional(self) -> None:
        self.assertEqual(_format_duration(90, "decimal"), "1.50h")

    def test_decimal_under_one_hour(self) -> None:
        self.assertEqual(_format_duration(35, "decimal"), "0.58h")

    def test_decimal_zero(self) -> None:
        self.assertEqual(_format_duration(0, "decimal"), "0.00h")

    def test_decimal_large_value(self) -> None:
        self.assertEqual(_format_duration(600, "decimal"), "10.00h")

    # hm mode
    def test_hm_whole_hours(self) -> None:
        self.assertEqual(_format_duration(120, "hm"), "2h")

    def test_hm_hours_and_minutes(self) -> None:
        self.assertEqual(_format_duration(90, "hm"), "1h 30m")

    def test_hm_under_one_hour(self) -> None:
        self.assertEqual(_format_duration(35, "hm"), "35m")

    def test_hm_zero(self) -> None:
        self.assertEqual(_format_duration(0, "hm"), "0m")

    # Default
    def test_default_is_decimal(self) -> None:
        self.assertEqual(_format_duration(60), "1.00h")


# ── Daily report ─────────────────────────────────────────────────────────────


class DailyReportTests(unittest.TestCase):
    """Daily report rendering with different hours formats."""

    def test_daily_report_decimal_format(self) -> None:
        config = _make_config("decimal")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, SAMPLE_EVENTS)
            report = generate_daily_report(db, date(2026, 3, 31), config)

        self.assertIn("3 events", report)
        # 2h15m = 2.25h, 30m = 0.50h, 15m = 0.25h → total 3h
        self.assertIn("3.00h", report)
        # No hm-style durations
        self.assertNotRegex(report, r"\d+h \d+m")

    def test_daily_report_hm_format(self) -> None:
        config = _make_config("hm")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, SAMPLE_EVENTS)
            report = generate_daily_report(db, date(2026, 3, 31), config)

        self.assertIn("3 events", report)
        self.assertIn("3h", report)
        # Should not contain decimal durations like "3.00h"
        self.assertNotIn(".00h", report)

    def test_daily_report_empty_day(self) -> None:
        config = _make_config("decimal")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, SAMPLE_EVENTS)
            report = generate_daily_report(db, date(2026, 4, 15), config)

        self.assertIn("0 events", report)
        self.assertIn("0.00h", report)

    def test_daily_report_excludes_keywords(self) -> None:
        config = _make_config("decimal", exclude_titles=["morning prep"])
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, SAMPLE_EVENTS)
            report = generate_daily_report(db, date(2026, 3, 31), config)

        self.assertIn("2 events", report)
        self.assertNotIn("morning prep", report)

    def test_daily_report_uses_config_timezone(self) -> None:
        config_la = _make_config("hm", timezone="America/Los_Angeles")
        config_ny = _make_config("hm", timezone="America/New_York")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, SAMPLE_EVENTS)
            report_la = generate_daily_report(db, date(2026, 3, 31), config_la)
            report_ny = generate_daily_report(db, date(2026, 3, 31), config_ny)

        # Same events should show different local times
        # 17:00 UTC = 10:00 AM LA = 1:00 PM NY
        self.assertIn("10:00 AM", report_la)
        self.assertIn("1:00 PM", report_ny)


# ── Weekly report ────────────────────────────────────────────────────────────


WEEK_EVENTS = [
    # Monday 2026-03-30
    ("w1", "Binoid - SEO", "2026-03-30T17:00:00+00:00", "2026-03-30T19:00:00+00:00"),
    # Tuesday 2026-03-31
    ("w2", "CR - CC", "2026-03-31T17:00:00+00:00", "2026-03-31T18:30:00+00:00"),
    # Wednesday 2026-04-01
    ("w3", "Binoid - theme update", "2026-04-01T17:00:00+00:00", "2026-04-01T18:00:00+00:00"),
    # Thursday 2026-04-02
    ("w4", "BW - account change", "2026-04-02T17:00:00+00:00", "2026-04-02T17:45:00+00:00"),
]


class WeeklyReportTests(unittest.TestCase):
    """Weekly report rendering and summary formatting."""

    def test_weekly_summary_decimal_format(self) -> None:
        config = _make_config("decimal")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, WEEK_EVENTS)
            report = generate_weekly_report(db, date(2026, 3, 31), config)

        # Total: 2h + 1.5h + 1h + 0.75h = 5.25h
        self.assertIn("**5.25h**", report)
        self.assertIn("Weekly Summary", report)
        self.assertIn("Weekly Project Aggregator", report)
        # No hm format in summary
        self.assertNotIn("5h 15m", report)

    def test_weekly_summary_hm_format(self) -> None:
        config = _make_config("hm")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, WEEK_EVENTS)
            report = generate_weekly_report(db, date(2026, 3, 31), config)

        self.assertIn("**5h 15m**", report)
        self.assertNotIn("5.25h", report)

    def test_weekly_project_aggregator_decimal(self) -> None:
        config = _make_config(
            "decimal",
            projects=[
                CalendarProject(name="Binoid - Bloomz", aliases=["Binoid"]),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, WEEK_EVENTS)
            report = generate_weekly_report(db, date(2026, 3, 31), config)

        # Binoid: 2h + 1h = 3h
        self.assertIn("| Binoid - Bloomz | 2 | 3.00h |", report)

    def test_weekly_project_aggregator_hm(self) -> None:
        config = _make_config(
            "hm",
            projects=[
                CalendarProject(name="Binoid - Bloomz", aliases=["Binoid"]),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, WEEK_EVENTS)
            report = generate_weekly_report(db, date(2026, 3, 31), config)

        self.assertIn("| Binoid - Bloomz | 2 | 3h |", report)

    def test_weekly_report_empty_week(self) -> None:
        config = _make_config("decimal")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            conn = get_connection(db)
            ensure_calendar_schema(conn)
            conn.close()
            report = generate_weekly_report(db, date(2026, 5, 1), config)

        self.assertIn("**0** | **0.00h**", report)
        self.assertNotIn("Weekly Project Aggregator", report)

    def test_weekly_avg_hours_decimal_format(self) -> None:
        config = _make_config("decimal")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, WEEK_EVENTS)
            report = generate_weekly_report(db, date(2026, 3, 31), config)

        self.assertIn("Working days: 4", report)
        # 315 total min / 4 = 78.75, int() truncates to 78 min = 1.30h
        self.assertIn("Avg hours/day: 1.30h", report)

    def test_weekly_avg_hours_hm_format(self) -> None:
        config = _make_config("hm")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, WEEK_EVENTS)
            report = generate_weekly_report(db, date(2026, 3, 31), config)

        self.assertIn("Working days: 4", report)
        # 315 total min / 4 = 78.75 → int(78) = 1h 18m
        self.assertIn("Avg hours/day: 1h 18m", report)


# ── Calendar-sync config resolution ─────────────────────────────────────────


class CalendarSyncConfigResolutionTests(unittest.TestCase):
    """Verify calendar-sync reads calendar_id from config file."""

    def test_config_calendar_id_used_when_no_cli_override(self) -> None:
        """CalendarConfig.load() should return the file's calendar_id."""
        data = {"calendar_id": "team@group.calendar.google.com"}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            with open(path, "w") as f:
                json.dump(data, f)
            config = CalendarConfig.load(path)

        self.assertEqual(config.calendar_id, "team@group.calendar.google.com")

    def test_default_calendar_id_is_primary(self) -> None:
        """When config file is missing, calendar_id should default to 'primary'."""
        config = CalendarConfig.load(Path("/nonexistent/config.json"))
        self.assertEqual(config.calendar_id, "primary")


# ── Filter by calendar_id ────────────────────────────────────────────────────


class CalendarIdFilterTests(unittest.TestCase):
    """Reports should only include events from the configured calendar_id."""

    def test_daily_report_filters_by_calendar_id(self) -> None:
        config = _make_config("decimal", calendar_id="team-cal")
        events_team = [
            ("t1", "Team event", "2026-04-01T17:00:00+00:00", "2026-04-01T18:00:00+00:00"),
        ]
        events_personal = [
            ("p1", "Personal event", "2026-04-01T17:00:00+00:00", "2026-04-01T18:00:00+00:00"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, events_team, calendar_id="team-cal")
            _insert_events(db, events_personal, calendar_id="primary")
            report = generate_daily_report(db, date(2026, 4, 1), config)

        self.assertIn("Team event", report)
        self.assertNotIn("Personal event", report)
        self.assertIn("1 event", report)


if __name__ == "__main__":
    unittest.main()
