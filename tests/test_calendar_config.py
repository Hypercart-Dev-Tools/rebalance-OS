"""Tests for CalendarConfig loading, defaults, validation, and hours_format."""

import json
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.calendar_config import CalendarConfig, CalendarProject


def _write_config(tmpdir: str, data: dict) -> Path:
    """Write a config dict to a JSON file inside tmpdir and return the path."""
    path = Path(tmpdir) / "calendar_config.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return path


class CalendarConfigLoadTests(unittest.TestCase):
    """Config loading from file, defaults, and field validation."""

    def test_load_returns_defaults_when_file_missing(self) -> None:
        config = CalendarConfig.load(Path("/nonexistent/path/config.json"))
        self.assertEqual(config.calendar_id, "primary")
        self.assertEqual(config.timezone, "America/New_York")
        self.assertEqual(config.hours_format, "decimal")
        self.assertEqual(config.projects, [])
        self.assertIn("Lunch", config.exclude_keywords)

    def test_load_reads_all_fields_from_file(self) -> None:
        data = {
            "calendar_id": "team@group.calendar.google.com",
            "exclude_keywords": ["Stand-up"],
            "timezone": "America/Los_Angeles",
            "hours_format": "hm",
            "projects": [
                {"name": "Acme", "aliases": ["AC", "Acme Corp"]}
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_config(tmpdir, data)
            config = CalendarConfig.load(path)

        self.assertEqual(config.calendar_id, "team@group.calendar.google.com")
        self.assertEqual(config.timezone, "America/Los_Angeles")
        self.assertEqual(config.hours_format, "hm")
        self.assertEqual(config.exclude_keywords, ["Stand-up"])
        self.assertEqual(len(config.projects), 1)
        self.assertEqual(config.projects[0].name, "Acme")
        self.assertEqual(config.projects[0].aliases, ["AC", "Acme Corp"])

    def test_load_defaults_hours_format_when_missing_from_file(self) -> None:
        data = {"calendar_id": "primary", "timezone": "America/Chicago"}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_config(tmpdir, data)
            config = CalendarConfig.load(path)

        self.assertEqual(config.hours_format, "decimal")

    def test_load_rejects_invalid_hours_format(self) -> None:
        data = {"hours_format": "invalid_value"}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_config(tmpdir, data)
            config = CalendarConfig.load(path)

        self.assertEqual(config.hours_format, "decimal")

    def test_load_ignores_malformed_projects(self) -> None:
        data = {
            "projects": [
                {"name": "Valid", "aliases": ["V"]},
                {"aliases": ["no-name"]},          # missing name
                "not-a-dict",                       # wrong type
                {"name": "", "aliases": []},        # blank name
                {"name": "AlsoValid"},              # no aliases key
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_config(tmpdir, data)
            config = CalendarConfig.load(path)

        self.assertEqual(len(config.projects), 2)
        self.assertEqual(config.projects[0].name, "Valid")
        self.assertEqual(config.projects[1].name, "AlsoValid")

    def test_save_round_trips_all_fields(self) -> None:
        original = CalendarConfig(
            calendar_id="test@group.calendar.google.com",
            exclude_keywords=["Lunch", "Break"],
            timezone="America/Denver",
            projects=[CalendarProject(name="Foo", aliases=["F", "FOO"])],
            hours_format="hm",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            original.save(path)
            loaded = CalendarConfig.load(path)

        self.assertEqual(loaded.calendar_id, original.calendar_id)
        self.assertEqual(loaded.timezone, original.timezone)
        self.assertEqual(loaded.hours_format, original.hours_format)
        self.assertEqual(loaded.exclude_keywords, original.exclude_keywords)
        self.assertEqual(len(loaded.projects), 1)
        self.assertEqual(loaded.projects[0].name, "Foo")
        self.assertEqual(loaded.projects[0].aliases, ["F", "FOO"])


if __name__ == "__main__":
    unittest.main()
