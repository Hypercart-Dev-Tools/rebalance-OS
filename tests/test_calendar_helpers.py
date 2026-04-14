"""Tests for the canonical calendar helpers: datetime parsing, duration
calculation, database connection context manager, and calendar auth helpers."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from rebalance.ingest import calendar
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


class CalendarAuthAndWriteTests(unittest.TestCase):
    """Tests for calendar OAuth scope enforcement and event creation."""

    def test_credentials_have_scopes(self) -> None:
        creds = type("Creds", (), {"scopes": [calendar.CALENDAR_READONLY_SCOPE, calendar.CALENDAR_WRITE_SCOPE]})()
        self.assertTrue(calendar._credentials_have_scopes(creds, [calendar.CALENDAR_READONLY_SCOPE]))
        self.assertTrue(calendar._credentials_have_scopes(creds, [calendar.CALENDAR_WRITE_SCOPE]))

    @patch("rebalance.ingest.calendar.pickle.load")
    @patch("builtins.open")
    @patch("pathlib.Path.exists", return_value=True)
    def test_load_credentials_rejects_missing_scope(self, _exists: MagicMock, _open_file: MagicMock, mock_pickle: MagicMock) -> None:
        creds = type("Creds", (), {"expired": False, "refresh_token": "x", "scopes": [calendar.CALENDAR_READONLY_SCOPE]})()
        mock_pickle.return_value = creds

        with self.assertRaises(PermissionError):
            calendar._load_credentials(required_scopes=[calendar.CALENDAR_WRITE_SCOPE])

    @patch("rebalance.ingest.calendar._build_service")
    def test_create_calendar_event_rejects_naive_datetimes(self, _build_service: MagicMock) -> None:
        with self.assertRaises(ValueError):
            calendar.create_calendar_event(
                summary="Planning",
                start_time="2026-04-14T10:00:00",
                end_time="2026-04-14T11:00:00",
            )

    @patch("rebalance.ingest.calendar._build_service")
    def test_create_calendar_event_inserts_with_attendees(self, mock_build_service: MagicMock) -> None:
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "id": "evt-123",
            "htmlLink": "https://calendar.google.com/event?eid=evt-123",
            "summary": "Planning",
            "start": {"dateTime": "2026-04-14T10:00:00-07:00"},
            "end": {"dateTime": "2026-04-14T11:00:00-07:00"},
            "attendees": [{"email": "a@example.com"}],
        }

        result = calendar.create_calendar_event(
            calendar_id="team@example.com",
            summary="Planning",
            start_time="2026-04-14T10:00:00-07:00",
            end_time="2026-04-14T11:00:00-07:00",
            timezone_name="America/Los_Angeles",
            attendees=["a@example.com"],
            location="Office",
            description="Agenda",
        )

        mock_build_service.assert_called_once_with(required_scopes=[calendar.CALENDAR_WRITE_SCOPE])
        mock_service.events.return_value.insert.assert_called_once()
        insert_kwargs = mock_service.events.return_value.insert.call_args.kwargs
        self.assertEqual(insert_kwargs["calendarId"], "team@example.com")
        self.assertEqual(insert_kwargs["sendUpdates"], "all")
        self.assertEqual(insert_kwargs["body"]["start"]["timeZone"], "America/Los_Angeles")
        self.assertEqual(insert_kwargs["body"]["location"], "Office")
        self.assertEqual(insert_kwargs["body"]["description"], "Agenda")
        self.assertEqual(insert_kwargs["body"]["attendees"], [{"email": "a@example.com"}])
        self.assertEqual(result.event_id, "evt-123")
        self.assertEqual(result.attendees_count, 1)


if __name__ == "__main__":
    unittest.main()
