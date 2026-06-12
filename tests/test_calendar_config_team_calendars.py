"""CalendarConfig: team_calendars loading, round-trip save, and edge cases."""

import json
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.calendar_config import (
    CalendarConfig,
    TeamCalendarEntry,
)


class TestTeamCalendarsLoad(unittest.TestCase):
    def _config_with(self, team_calendars: list) -> CalendarConfig:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"team_calendars": team_calendars}, f)
            path = Path(f.name)
        try:
            return CalendarConfig.load(path)
        finally:
            path.unlink(missing_ok=True)

    def test_empty_list_is_default(self) -> None:
        config = self._config_with([])
        self.assertEqual(config.team_calendars, [])

    def test_single_entry_loaded(self) -> None:
        config = self._config_with([
            {"person": "matthew", "calendar_id": "matthew@group.calendar.google.com"}
        ])
        self.assertEqual(len(config.team_calendars), 1)
        self.assertEqual(config.team_calendars[0].person, "matthew")
        self.assertEqual(
            config.team_calendars[0].calendar_id,
            "matthew@group.calendar.google.com",
        )

    def test_multiple_entries_loaded(self) -> None:
        config = self._config_with([
            {"person": "matthew", "calendar_id": "m@cal.google.com"},
            {"person": "jose", "calendar_id": "j@cal.google.com"},
        ])
        self.assertEqual(len(config.team_calendars), 2)
        persons = [tc.person for tc in config.team_calendars]
        self.assertIn("matthew", persons)
        self.assertIn("jose", persons)

    def test_missing_person_skipped(self) -> None:
        config = self._config_with([
            {"calendar_id": "orphan@cal.google.com"},   # no person
            {"person": "matthew", "calendar_id": "m@cal.google.com"},
        ])
        self.assertEqual(len(config.team_calendars), 1)
        self.assertEqual(config.team_calendars[0].person, "matthew")

    def test_missing_calendar_id_skipped(self) -> None:
        config = self._config_with([
            {"person": "ghost"},                         # no calendar_id
            {"person": "matthew", "calendar_id": "m@cal.google.com"},
        ])
        self.assertEqual(len(config.team_calendars), 1)

    def test_non_dict_entries_skipped(self) -> None:
        config = self._config_with(["invalid", None, 42])
        self.assertEqual(config.team_calendars, [])

    def test_absent_key_gives_empty_list(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({}, f)
            path = Path(f.name)
        try:
            config = CalendarConfig.load(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(config.team_calendars, [])


class TestTeamCalendarsSave(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cal.json"
            config = CalendarConfig.load()  # defaults
            config.team_calendars = [
                TeamCalendarEntry(person="matthew", calendar_id="m@cal.google.com"),
                TeamCalendarEntry(person="jose", calendar_id="j@cal.google.com"),
            ]
            config.save(path)
            reloaded = CalendarConfig.load(path)
            self.assertEqual(len(reloaded.team_calendars), 2)
            self.assertEqual(reloaded.team_calendars[0].person, "matthew")
            self.assertEqual(reloaded.team_calendars[1].person, "jose")

    def test_empty_list_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cal.json"
            config = CalendarConfig.load()
            config.team_calendars = []
            config.save(path)
            reloaded = CalendarConfig.load(path)
            self.assertEqual(reloaded.team_calendars, [])


if __name__ == "__main__":
    unittest.main()
