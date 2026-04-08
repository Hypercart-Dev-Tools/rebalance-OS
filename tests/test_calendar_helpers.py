"""Tests for the canonical calendar helpers: datetime parsing, duration
calculation, and database connection context manager."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rebalance.ingest.calendar_helpers import (
    calendar_connection,
    event_duration_minutes,
    parse_calendar_dt,
)


class ParseCalendarDtTests(unittest.TestCase):
    """Tests for parse_calendar_dt — the canonical Z-replace implementation."""

    def test_parses_utc_z_suffix(self) -> None:
        dt = parse_calendar_dt("2026-04-07T17:00:00Z")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.hour, 17)
        self.assertIsNotNone(dt.tzinfo)

    def test_parses_offset_aware(self) -> None:
        dt = parse_calendar_dt("2026-04-07T10:00:00-07:00")
        self.assertEqual(dt.hour, 10)
        self.assertIsNotNone(dt.tzinfo)

    def test_parses_utc_plus_zero(self) -> None:
        dt = parse_calendar_dt("2026-04-07T17:00:00+00:00")
        self.assertEqual(dt.hour, 17)

    def test_date_only_returns_naive(self) -> None:
        dt = parse_calendar_dt("2026-04-07")
        self.assertEqual(dt.year, 2026)
        self.assertIsNone(dt.tzinfo)

    def test_invalid_string_raises(self) -> None:
        with self.assertRaises(Exception):
            parse_calendar_dt("not-a-date")


class EventDurationMinutesTests(unittest.TestCase):
    """Tests for event_duration_minutes — safe duration with naive guard."""

    def test_normal_duration(self) -> None:
        self.assertEqual(
            event_duration_minutes(
                "2026-04-07T17:00:00+00:00",
                "2026-04-07T19:30:00+00:00",
            ),
            150,
        )

    def test_z_suffix_duration(self) -> None:
        self.assertEqual(
            event_duration_minutes(
                "2026-04-07T17:00:00Z",
                "2026-04-07T18:00:00Z",
            ),
            60,
        )

    def test_zero_duration(self) -> None:
        self.assertEqual(
            event_duration_minutes(
                "2026-04-07T17:00:00Z",
                "2026-04-07T17:00:00Z",
            ),
            0,
        )

    def test_all_day_event_returns_zero(self) -> None:
        """Date-only strings (naive datetimes) should return 0, not crash."""
        self.assertEqual(
            event_duration_minutes("2026-04-07", "2026-04-08"),
            0,
        )

    def test_mixed_naive_aware_returns_zero(self) -> None:
        """Mixing date-only with full datetime should return 0, not crash."""
        self.assertEqual(
            event_duration_minutes("2026-04-07", "2026-04-07T18:00:00Z"),
            0,
        )

    def test_empty_strings_return_zero(self) -> None:
        self.assertEqual(event_duration_minutes("", ""), 0)

    def test_none_like_empty_return_zero(self) -> None:
        self.assertEqual(event_duration_minutes("", "2026-04-07T18:00:00Z"), 0)

    def test_invalid_strings_return_zero(self) -> None:
        self.assertEqual(event_duration_minutes("garbage", "also-garbage"), 0)

    def test_negative_duration_returns_zero(self) -> None:
        """End before start should return 0 (max clamp)."""
        self.assertEqual(
            event_duration_minutes(
                "2026-04-07T19:00:00Z",
                "2026-04-07T17:00:00Z",
            ),
            0,
        )


class CalendarConnectionTests(unittest.TestCase):
    """Tests for the calendar_connection context manager."""

    def test_connection_opens_and_closes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "test.db"
            with calendar_connection(db) as conn:
                # Should be able to query the calendar_events table
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='calendar_events'"
                ).fetchall()
                self.assertEqual(len(rows), 1)

    def test_connection_closed_after_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "test.db"
            with calendar_connection(db) as conn:
                pass
            # Connection should be closed — attempting to use it should fail
            with self.assertRaises(Exception):
                conn.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
