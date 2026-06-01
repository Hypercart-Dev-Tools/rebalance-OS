"""Tests for the pulse web goals parser and hero rendering."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rebalance.doctor import Check, FAIL, WARN


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pulse_web  # noqa: E402


class PulseWebGoalTests(unittest.TestCase):
    def test_parse_goals_keeps_uppermost_open_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            goals_path = Path(tmpdir) / "0. Goals.md"
            goals_path.write_text(
                "\n".join(
                    [
                        "- [x] Completed item",
                        *[f"- [ ] Open item {i}" for i in range(1, 11)],
                    ]
                ),
                encoding="utf-8",
            )

            goals = pulse_web.parse_goals(goals_path, limit=9)

        self.assertEqual([goal["title"] for goal in goals], [f"Open item {i}" for i in range(1, 10)])

    def test_render_hero_shows_secondary_todo_column(self) -> None:
        all_goals = [
            {"done": False, "title": f"Open item {i}", "description": ""}
            for i in range(1, 10)
        ]

        html = pulse_web.render_hero(
            all_goals[:3],
            "0. Goals.md",
            datetime(2026, 5, 14, tzinfo=timezone.utc),
            None,
            [],
            secondary_todos=all_goals[3:],
        )

        self.assertIn("Next open todos", html)
        self.assertIn("Open item 4", html)
        self.assertIn("Open item 9", html)
        self.assertIn("<b>9</b> in progress", html)
        self.assertEqual(html.count('class="goal goal-compact"'), 6)

    def test_render_health_banner_prioritizes_failures(self) -> None:
        checks = [
            Check("launchd:github-sync", WARN, "last run exited with status 1"),
            Check("gmail", WARN, "ADC token is missing the Gmail readonly scope"),
            Check("github token", FAIL, "no GitHub token configured"),
            Check("vault", FAIL, "no vault path configured"),
            Check("sleuth", WARN, "no Sleuth Web API env file"),
        ]

        html = pulse_web.render_health_banner(
            checks,
            {"sources": {}},
            datetime(2026, 5, 28, 18, 0, tzinfo=timezone.utc),
            "2026-05-28T17:55:00+00:00",
        )

        self.assertIn("2 errors", html)
        self.assertIn("Collector attention needed", html)
        self.assertIn("github token", html)
        self.assertIn("vault", html)
        self.assertIn("+1 more", html)
        self.assertIn("health-banner-copy-btn", html)
        self.assertIn("data-copy-text=", html)
        self.assertNotIn("launchd:github-sync</span><span class=\"health-banner-detail\"", html)

    def test_render_sync_chip_uses_warning_state(self) -> None:
        chip = pulse_web.render_sync_chip(
            [Check("gmail", WARN, "scope missing")],
            {"sources": {}},
            "2026-05-28T17:55:00+00:00",
            datetime(2026, 5, 28, 18, 0, tzinfo=timezone.utc),
        )

        self.assertIn("synced-warn", chip)
        self.assertIn("Collector warnings", chip)


if __name__ == "__main__":
    unittest.main()
