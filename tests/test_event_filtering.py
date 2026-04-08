"""Tests for Phase B+C: split exclude/aggregator config, exact-match filtering,
needs_review segment, review decisions persistence, and backwards compatibility."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from rebalance.ingest.calendar import ensure_calendar_schema
from rebalance.ingest.calendar_config import (
    CalendarConfig,
    CalendarProject,
    filter_events,
    load_review_decisions,
    save_review_decision,
    should_exclude_event,
)
from rebalance.ingest.daily_report import (
    generate_daily_report,
    get_day_data,
)
from rebalance.ingest.db import get_connection
from rebalance.ingest.project_classifier import load_project_matchers


def _insert_events(database_path: Path, events: list[tuple], calendar_id: str = "primary") -> None:
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


def _make_config(**kwargs) -> CalendarConfig:
    defaults = dict(
        calendar_id="primary",
        exclude_titles=[],
        aggregator_skip_words=[],
        timezone="America/Los_Angeles",
        projects=[],
        hours_format="decimal",
    )
    defaults.update(kwargs)
    return CalendarConfig(**defaults)


# ── Exact-match filtering ────────────────────────────────────────────────────


class ExactMatchFilterTests(unittest.TestCase):
    """Verify exclude_titles uses exact title matching, not substring."""

    def test_exact_match_excludes_exact_title(self) -> None:
        self.assertTrue(should_exclude_event("Lunch", ["Lunch"]))

    def test_exact_match_is_case_insensitive(self) -> None:
        self.assertTrue(should_exclude_event("lunch", ["Lunch"]))
        self.assertTrue(should_exclude_event("LUNCH", ["Lunch"]))

    def test_exact_match_does_not_match_substring(self) -> None:
        """'wrap' should NOT exclude 'Wrap up Countdown Timer'."""
        self.assertFalse(should_exclude_event("Wrap up Countdown Timer", ["wrap"]))

    def test_exact_match_does_not_match_setup_in_task(self) -> None:
        """'setup' should NOT exclude 'Setup rebalance local Google Timesheet app'."""
        self.assertFalse(
            should_exclude_event("Setup rebalance local Google Timesheet app", ["setup"])
        )

    def test_exact_match_strips_whitespace(self) -> None:
        self.assertTrue(should_exclude_event("  Lunch  ", ["Lunch"]))

    def test_filter_events_exact_match(self) -> None:
        events = [
            {"summary": "Check Slack"},
            {"summary": "Wrap up Countdown Timer"},
            {"summary": "Setup rebalance app"},
            {"summary": "Lunch"},
        ]
        filtered = filter_events(events, ["Check Slack", "Lunch", "wrap", "setup"])
        summaries = [e["summary"] for e in filtered]
        self.assertIn("Wrap up Countdown Timer", summaries)
        self.assertIn("Setup rebalance app", summaries)
        self.assertNotIn("Check Slack", summaries)
        self.assertNotIn("Lunch", summaries)


# ── Backwards compatibility ──────────────────────────────────────────────────


class BackwardsCompatTests(unittest.TestCase):
    """Legacy exclude_keywords in config file should map to exclude_titles."""

    def test_legacy_exclude_keywords_mapped_to_exclude_titles(self) -> None:
        data = {
            "calendar_id": "primary",
            "exclude_keywords": ["Lunch", "Check Slack"],
            "timezone": "America/New_York",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            with open(path, "w") as f:
                json.dump(data, f)
            config = CalendarConfig.load(path)

        self.assertEqual(config.exclude_titles, ["Lunch", "Check Slack"])

    def test_exclude_titles_takes_precedence_over_exclude_keywords(self) -> None:
        data = {
            "exclude_titles": ["Lunch"],
            "exclude_keywords": ["Lunch", "Break", "Admin"],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            with open(path, "w") as f:
                json.dump(data, f)
            config = CalendarConfig.load(path)

        self.assertEqual(config.exclude_titles, ["Lunch"])

    def test_exclude_keywords_property_returns_exclude_titles(self) -> None:
        config = _make_config(exclude_titles=["A", "B"])
        self.assertEqual(config.exclude_keywords, ["A", "B"])


# ── Aggregator skip words ───────────────────────────────────────────────────


class AggregatorSkipWordsTests(unittest.TestCase):
    """aggregator_skip_words affects grouping labels but not event filtering."""

    def test_aggregator_skip_words_do_not_filter_events(self) -> None:
        config = _make_config(aggregator_skip_words=["wrap", "setup"])
        events = [
            ("e1", "Wrap up Countdown Timer", "2026-04-01T17:00:00+00:00", "2026-04-01T18:00:00+00:00"),
            ("e2", "Setup rebalance app", "2026-04-01T18:00:00+00:00", "2026-04-01T18:50:00+00:00"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, events)
            report = generate_daily_report(db, date(2026, 4, 1), config)

        # Both events should appear in the report
        self.assertIn("Wrap up Countdown Timer", report)
        self.assertIn("Setup rebalance app", report)
        self.assertIn("2 events", report)


# ── Needs review segment ────────────────────────────────────────────────────


class NeedsReviewTests(unittest.TestCase):
    """Events not matched to any project appear in Needs Review."""

    def test_unmatched_events_in_needs_review(self) -> None:
        config = _make_config()
        events = [
            ("e1", "Mystery task", "2026-04-01T17:00:00+00:00", "2026-04-01T18:00:00+00:00"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, events)
            report = generate_daily_report(db, date(2026, 4, 1), config)

        self.assertIn("### Needs Review", report)
        self.assertIn("Mystery task", report)

    def test_matched_events_not_in_needs_review(self) -> None:
        config = _make_config(
            projects=[CalendarProject(name="Binoid - Bloomz", aliases=["Binoid"])],
        )
        events = [
            ("e1", "Binoid - SEO audit", "2026-04-01T17:00:00+00:00", "2026-04-01T18:00:00+00:00"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cal.db"
            _insert_events(db, events)
            matchers = load_project_matchers(db, config=config)
            day = get_day_data(db, date(2026, 4, 1), config, project_matchers=matchers)

        self.assertEqual(len(day.needs_review), 0)


# ── Review decisions persistence ─────────────────────────────────────────────


class ReviewDecisionsTests(unittest.TestCase):
    """Review decisions persist and affect future reports."""

    def test_save_and_load_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.json"
            save_review_decision("Mystery task", "include", path)
            decisions = load_review_decisions(path)

        self.assertEqual(decisions["mystery task"], "include")

    def test_load_returns_empty_when_file_missing(self) -> None:
        decisions = load_review_decisions(Path("/nonexistent/decisions.json"))
        self.assertEqual(decisions, {})

    def test_multiple_decisions_accumulate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.json"
            save_review_decision("Task A", "include", path)
            save_review_decision("Task B", "exclude", path)
            save_review_decision("Task C", "project:Binoid", path)
            decisions = load_review_decisions(path)

        self.assertEqual(len(decisions), 3)
        self.assertEqual(decisions["task a"], "include")
        self.assertEqual(decisions["task b"], "exclude")
        self.assertEqual(decisions["task c"], "project:Binoid")


if __name__ == "__main__":
    unittest.main()
