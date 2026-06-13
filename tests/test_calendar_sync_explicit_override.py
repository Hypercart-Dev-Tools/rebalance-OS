"""calendar-sync must honor an explicit --calendar-id, not silently rewrite it.

Regression: refresh_calendar_source canonicalised ANY non-'primary' calendar to
'primary' whenever person was None. Since the CLI passes the operator-supplied
--calendar-id with person=None, `calendar-sync --calendar-id team@...` printed
that it was syncing team@... but actually fetched/stored 'primary'. An explicit
calendar id must be synced verbatim; only the operator's own *default* calendar
(no override, resolved from config) is canonicalised to 'primary'.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest import calendar as calmod
from rebalance.ingest.calendar import CalendarSyncResult, refresh_calendar_source
from rebalance.ingest.calendar_config import CalendarConfig


def _result(calendar_id: str) -> CalendarSyncResult:
    return CalendarSyncResult(
        events_fetched=1,
        events_stored=1,
        window_start="2026-01-01",
        window_end="2026-01-08",
        elapsed_seconds=0.1,
        calendar_id=calendar_id,
    )


class TestRefreshCalendarSourceResolution(unittest.TestCase):
    def _capture_calendar_id(self):
        captured = {}

        def fake_sync(database_path, *, calendar_id, person=None, days_back, days_forward):
            captured["calendar_id"] = calendar_id
            captured["person"] = person
            return _result(calendar_id)

        return captured, fake_sync

    def test_explicit_calendar_id_synced_verbatim(self) -> None:
        captured, fake_sync = self._capture_calendar_id()
        with patch.object(calmod, "sync_calendar", side_effect=fake_sync):
            result = refresh_calendar_source(Path("/tmp/x.db"), calendar_id="team@group.calendar.google.com")
        self.assertEqual(captured["calendar_id"], "team@group.calendar.google.com")
        self.assertEqual(result.calendar_id, "team@group.calendar.google.com")

    def test_default_operator_calendar_canonicalised_to_primary(self) -> None:
        captured, fake_sync = self._capture_calendar_id()
        # No explicit id; config resolves to a non-'primary' email which must be
        # canonicalised to 'primary' for the operator's own calendar.
        cfg = CalendarConfig(
            calendar_id="noel@neochro.me", exclude_titles=[], aggregator_skip_words=[],
            timezone="UTC", projects=[], hours_format="decimal", team_calendars=[],
        )
        with patch.object(calmod, "sync_calendar", side_effect=fake_sync), \
             patch("rebalance.ingest.calendar_config.CalendarConfig.load", return_value=cfg):
            refresh_calendar_source(Path("/tmp/x.db"))  # no calendar_id => operator default
        self.assertEqual(captured["calendar_id"], "primary")

    def test_explicit_primary_stays_primary(self) -> None:
        captured, fake_sync = self._capture_calendar_id()
        with patch.object(calmod, "sync_calendar", side_effect=fake_sync):
            refresh_calendar_source(Path("/tmp/x.db"), calendar_id="primary")
        self.assertEqual(captured["calendar_id"], "primary")

    def test_teammate_with_person_is_verbatim(self) -> None:
        captured, fake_sync = self._capture_calendar_id()
        with patch.object(calmod, "sync_calendar", side_effect=fake_sync):
            refresh_calendar_source(
                Path("/tmp/x.db"), calendar_id="matt@group.calendar.google.com", person="matt"
            )
        self.assertEqual(captured["calendar_id"], "matt@group.calendar.google.com")
        self.assertEqual(captured["person"], "matt")


class TestCalendarSyncCliWiring(unittest.TestCase):
    def test_cli_passes_explicit_override_through(self) -> None:
        from typer.testing import CliRunner

        from rebalance.cli.calendar import app

        captured = {}

        def fake_refresh(database_path, *, calendar_id, days_back, days_forward):
            captured["calendar_id"] = calendar_id
            return _result(calendar_id or "primary")

        with patch("rebalance.cli.calendar.resolve_database_path", return_value=Path("/tmp/x.db")), \
             patch("rebalance.ingest.calendar.refresh_calendar_source", side_effect=fake_refresh):
            result = CliRunner().invoke(
                app, ["calendar-sync", "--calendar-id", "team@group.calendar.google.com"]
            )
        self.assertEqual(result.exit_code, 0, result.output)
        # The explicit override reaches refresh_calendar_source verbatim (not pre-rewritten).
        self.assertEqual(captured["calendar_id"], "team@group.calendar.google.com")
        # And the completion line reports the calendar actually synced.
        self.assertIn("team@group.calendar.google.com", result.output)

    def test_cli_no_override_syncs_operator_default(self) -> None:
        from typer.testing import CliRunner

        from rebalance.cli.calendar import app

        captured = {}

        def fake_refresh(database_path, *, calendar_id, days_back, days_forward):
            captured["calendar_id"] = calendar_id
            return _result("primary")

        with patch("rebalance.cli.calendar.resolve_database_path", return_value=Path("/tmp/x.db")), \
             patch("rebalance.ingest.calendar.refresh_calendar_source", side_effect=fake_refresh):
            result = CliRunner().invoke(app, ["calendar-sync"])
        self.assertEqual(result.exit_code, 0, result.output)
        # No override => empty calendar_id passed; the function resolves the default.
        self.assertEqual(captured["calendar_id"], "")
        self.assertIn("your own calendar", result.output)


if __name__ == "__main__":
    unittest.main()
