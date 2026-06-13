"""A team_calendars entry may not claim the reserved 'primary' calendar_id.

Regression for a privacy leak: _load_team_calendars only checked that person
and calendar_id were non-empty. An entry like {"person":"matthew",
"calendar_id":"primary"} was accepted, so teammate events were stored under
calendar_id='primary' and then matched export_calendar_snapshot's
WHERE calendar_id='primary' filter — pushing teammate data off-machine into
the committed pulse repo. Such entries must be rejected at config load.
"""

import json
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.calendar_config import CalendarConfig


class TestRejectPrimaryTeamCalendar(unittest.TestCase):
    def test_loader_drops_primary_entry(self) -> None:
        entries = CalendarConfig._load_team_calendars(
            [{"person": "matthew", "calendar_id": "primary"}]
        )
        self.assertEqual(entries, [], "a team entry with calendar_id='primary' must be dropped")

    def test_loader_drops_primary_case_insensitively(self) -> None:
        entries = CalendarConfig._load_team_calendars(
            [{"person": "matthew", "calendar_id": "Primary"}]
        )
        self.assertEqual(entries, [])

    def test_valid_entry_survives_alongside_primary(self) -> None:
        entries = CalendarConfig._load_team_calendars([
            {"person": "matthew", "calendar_id": "primary"},
            {"person": "jose", "calendar_id": "jose@group.calendar.google.com"},
        ])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].person, "jose")
        self.assertEqual(entries[0].calendar_id, "jose@group.calendar.google.com")

    def test_load_from_file_rejects_primary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calendar_config.json"
            path.write_text(json.dumps({
                "calendar_id": "primary",
                "team_calendars": [
                    {"person": "matthew", "calendar_id": "primary"},
                    {"person": "jose", "calendar_id": "jose@group.calendar.google.com"},
                ],
            }))
            config = CalendarConfig.load(path)

        people = {tc.person for tc in config.team_calendars}
        self.assertNotIn("matthew", people, "primary-keyed teammate entry must not load")
        self.assertIn("jose", people)

    def test_warns_when_dropping(self) -> None:
        with self.assertLogs("rebalance.ingest.calendar_config", level="WARNING") as cm:
            CalendarConfig._load_team_calendars(
                [{"person": "matthew", "calendar_id": "primary"}]
            )
        self.assertTrue(any("reserved" in line for line in cm.output))


if __name__ == "__main__":
    unittest.main()
