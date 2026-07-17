"""Tests for the timezone display/resolution helpers.

Covers `local_tz()` resolution order (env override, /etc/localtime, UTC
fallback — previously untested), `to_local()` and `parse_utc_iso()`
(previously untested), and the new shared display formatters `format_local()`
and `format_relative()` added under GH-130 to replace 5+ ad-hoc
parse-guard-convert-format implementations. See
PROJECT/2-WORKING/GH-130-CENTRALIZE-LOCAL-TIME-DISPLAY.md.
"""

from __future__ import annotations
import unittest
from datetime import datetime, timezone
from unittest import mock
from zoneinfo import ZoneInfo

from rebalance.tz_utils import format_local, format_relative, local_tz, parse_utc_iso, to_local


class LocalTzTests(unittest.TestCase):
    def test_env_override_wins(self) -> None:
        with mock.patch.dict("os.environ", {"REBALANCE_TZ": "America/New_York"}, clear=False):
            self.assertEqual(local_tz(), ZoneInfo("America/New_York"))

    def test_invalid_env_override_falls_through_to_localtime_or_utc(self) -> None:
        with mock.patch.dict("os.environ", {"REBALANCE_TZ": "Not/A_Real_Zone"}, clear=False):
            # Falls through past the bad env value to /etc/localtime or UTC —
            # either way it must resolve to a ZoneInfo, never raise.
            self.assertIsInstance(local_tz(), ZoneInfo)

    def test_no_env_and_unreadable_localtime_falls_back_to_utc(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True), \
             mock.patch("os.readlink", side_effect=OSError("no such file")):
            self.assertEqual(local_tz(), ZoneInfo("UTC"))

    def test_localtime_symlink_resolves_zone(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True), \
             mock.patch("os.readlink", return_value="/usr/share/zoneinfo/Europe/Berlin"):
            self.assertEqual(local_tz(), ZoneInfo("Europe/Berlin"))


class ToLocalTests(unittest.TestCase):
    def test_naive_datetime_treated_as_utc(self) -> None:
        naive = datetime(2026, 1, 1, 12, 0, 0)
        local = to_local(naive, ZoneInfo("America/Los_Angeles"))
        self.assertEqual(local, datetime(2026, 1, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")))

    def test_aware_datetime_converts(self) -> None:
        aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        local = to_local(aware, ZoneInfo("America/Los_Angeles"))
        self.assertEqual(local.hour, 4)

    def test_defaults_to_local_tz_when_none(self) -> None:
        with mock.patch.dict("os.environ", {"REBALANCE_TZ": "UTC"}, clear=False):
            aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            self.assertEqual(to_local(aware).hour, 12)


class ParseUtcIsoTests(unittest.TestCase):
    def test_trailing_z(self) -> None:
        parsed = parse_utc_iso("2026-01-01T12:00:00Z")
        self.assertEqual(parsed, datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    def test_offset_form(self) -> None:
        parsed = parse_utc_iso("2026-01-01T12:00:00+00:00")
        self.assertEqual(parsed, datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    def test_naive_assumed_utc(self) -> None:
        parsed = parse_utc_iso("2026-01-01T12:00:00")
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_empty_and_none_return_none(self) -> None:
        self.assertIsNone(parse_utc_iso(""))
        self.assertIsNone(parse_utc_iso(None))

    def test_malformed_returns_none(self) -> None:
        self.assertIsNone(parse_utc_iso("not a date"))


class FormatLocalTests(unittest.TestCase):
    def test_string_input(self) -> None:
        result = format_local("2026-01-01T12:00:00Z", "%Y-%m-%d %H:%M", tz=ZoneInfo("America/Los_Angeles"))
        self.assertEqual(result, "2026-01-01 04:00")

    def test_datetime_input_naive_treated_as_utc(self) -> None:
        naive = datetime(2026, 1, 1, 12, 0, 0)
        result = format_local(naive, "%H:%M", tz=ZoneInfo("America/Los_Angeles"))
        self.assertEqual(result, "04:00")

    def test_datetime_input_aware_passthrough(self) -> None:
        aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = format_local(aware, "%H:%M", tz=ZoneInfo("UTC"))
        self.assertEqual(result, "12:00")

    def test_none_returns_empty_string(self) -> None:
        self.assertEqual(format_local(None, "%Y-%m-%d"), "")

    def test_malformed_string_returns_empty_string(self) -> None:
        self.assertEqual(format_local("not a date", "%Y-%m-%d"), "")

    def test_default_tz_when_unspecified(self) -> None:
        with mock.patch.dict("os.environ", {"REBALANCE_TZ": "UTC"}, clear=False):
            result = format_local("2026-01-01T12:00:00Z", "%H:%M")
            self.assertEqual(result, "12:00")


class FormatRelativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_just_now(self) -> None:
        result = format_relative(datetime(2026, 1, 1, 11, 59, 45, tzinfo=timezone.utc), now=self.now)
        self.assertEqual(result, "just now")

    def test_minutes_ago(self) -> None:
        result = format_relative(datetime(2026, 1, 1, 11, 55, 0, tzinfo=timezone.utc), now=self.now)
        self.assertEqual(result, "5m ago")

    def test_hours_ago(self) -> None:
        result = format_relative(datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc), now=self.now)
        self.assertEqual(result, "3h ago")

    def test_days_ago(self) -> None:
        result = format_relative(datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone.utc), now=self.now)
        self.assertEqual(result, "2d ago")

    def test_string_input(self) -> None:
        result = format_relative("2026-01-01T11:00:00Z", now=self.now)
        self.assertEqual(result, "1h ago")

    def test_none_returns_empty_string(self) -> None:
        self.assertEqual(format_relative(None), "")

    def test_malformed_string_returns_empty_string(self) -> None:
        self.assertEqual(format_relative("not a date"), "")

    def test_future_clamps_to_zero_not_negative(self) -> None:
        future = self.now.replace(year=2027)
        result = format_relative(future, now=self.now)
        self.assertEqual(result, "just now")


if __name__ == "__main__":
    unittest.main()
