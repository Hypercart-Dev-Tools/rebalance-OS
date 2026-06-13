"""A single inaccessible teammate calendar must not abort the calendar refresh.

Regression for the team_calendars loop in _refresh_calendar: it called
sync_calendar per teammate with no per-calendar guard, unlike the sibling
_refresh_github loop. A revoked share / 404 / transient 5xx on one teammate
calendar would propagate out of _refresh_calendar, discarding the operator's
own already-committed sync result and (downstream) suppressing the dashboard
note. The failure must instead be isolated and recorded per calendar.
"""

import types
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest.calendar_config import CalendarConfig, TeamCalendarEntry
from rebalance.ingest.index_ops import _refresh_calendar


def _ok_result() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        events_fetched=5,
        events_stored=5,
        window_start="2026-01-01",
        window_end="2026-01-08",
        elapsed_seconds=0.1,
    )


def _config(team: list[TeamCalendarEntry]) -> CalendarConfig:
    return CalendarConfig(
        calendar_id="primary",
        exclude_titles=[],
        aggregator_skip_words=[],
        timezone="UTC",
        projects=[],
        hours_format="decimal",
        team_calendars=team,
    )


class TestTeamCalendarLoopIsolation(unittest.TestCase):
    def test_one_failing_team_calendar_does_not_abort(self) -> None:
        cfg = _config([
            TeamCalendarEntry("matthew", "matthew@group.calendar.google.com"),
            TeamCalendarEntry("jose", "jose@group.calendar.google.com"),
        ])

        def fake_sync(database_path, *, calendar_id, person=None, days_back, days_forward):
            if person is None:
                return _ok_result()  # operator's own calendar succeeds + commits
            if person == "matthew":
                raise RuntimeError("HttpError 403: calendar inaccessible")
            return _ok_result()  # a later teammate still gets synced

        with patch("rebalance.ingest.calendar_config.CalendarConfig.load", return_value=cfg), \
             patch("rebalance.ingest.calendar.sync_calendar", side_effect=fake_sync):
            # Must NOT raise.
            result = _refresh_calendar(Path("/tmp/unused.db"), since_days=30, dry_run=False)

        # The operator's own result survives the teammate failure.
        self.assertEqual(result["scope"], "calendar")
        self.assertEqual(result["events_fetched"], 5)
        self.assertEqual(result["events_stored"], 5)

        team = {t["person"]: t for t in result["team_calendars"]}
        # The failing calendar is isolated and recorded, not raised.
        self.assertIn("matthew", team)
        self.assertIn("error", team["matthew"])
        self.assertIn("403", team["matthew"]["error"])
        # A teammate after the failing one is still synced (loop did not abort).
        self.assertIn("jose", team)
        self.assertNotIn("error", team["jose"])
        self.assertEqual(team["jose"]["events_stored"], 5)

    def test_all_team_calendars_succeed_unchanged(self) -> None:
        cfg = _config([TeamCalendarEntry("matthew", "matthew@group.calendar.google.com")])

        with patch("rebalance.ingest.calendar_config.CalendarConfig.load", return_value=cfg), \
             patch("rebalance.ingest.calendar.sync_calendar", return_value=_ok_result()):
            result = _refresh_calendar(Path("/tmp/unused.db"), since_days=30, dry_run=False)

        team = {t["person"]: t for t in result["team_calendars"]}
        self.assertNotIn("error", team["matthew"])
        self.assertEqual(team["matthew"]["events_fetched"], 5)
        self.assertEqual(team["matthew"]["events_stored"], 5)


if __name__ == "__main__":
    unittest.main()
