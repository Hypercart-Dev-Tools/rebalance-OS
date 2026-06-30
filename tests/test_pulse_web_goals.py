"""Tests for the pulse web goals parser and hero rendering."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rebalance.doctor import Check, FAIL, WARN
from rebalance.health import compute_health_status
from rebalance.web_components import render_sidebar


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

    def test_parse_goals_exposes_source_line_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            goals_path = Path(tmpdir) / "0. Goals.md"
            goals_path.write_text(
                "\n".join(
                    [
                        "# Header",
                        "- [ ] First open",
                        "  details",
                        "- [x] Done",
                        "- [ ] Second open",
                    ]
                ),
                encoding="utf-8",
            )

            goals = pulse_web.parse_goals(goals_path, limit=None)

        self.assertEqual([goal["line_index"] for goal in goals], [1, 4])
        self.assertEqual(goals[0]["description"], "details")

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

        now = datetime(2026, 5, 28, 18, 0, tzinfo=timezone.utc)
        health = compute_health_status(checks, {"sources": {}}, now)
        html = pulse_web.render_health_banner(
            health,
            now,
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
        now = datetime(2026, 5, 28, 18, 0, tzinfo=timezone.utc)
        health = compute_health_status(
            [Check("gmail", WARN, "scope missing")], {"sources": {}}, now
        )
        chip = pulse_web.render_sync_chip(
            health,
            "2026-05-28T17:55:00+00:00",
            now,
        )

        self.assertIn("synced-warn", chip)
        self.assertIn("Collector warnings", chip)

    def test_build_stream_rows_includes_email_and_figma(self) -> None:
        rows = pulse_web.build_stream_rows(
            {
                "sources": {
                    "github": {"items": 10},
                    "vault": {"chunks": 6},
                    "calendar": {"events": 6},
                    "sleuth": {"reminders": 6},
                    "email": {"messages": 2},
                    "figma": {"comments": 0},
                    "ask_self": {"repos": 4},
                }
            }
        )

        self.assertEqual(
            [row["name"] for row in rows],
            ["github", "vault", "calendar", "sleuth", "email", "figma"],
        )
        self.assertEqual(
            [row["count"] for row in rows],
            [10, 6, 6, 6, 2, 0],
        )

    def test_render_sidebar_renders_dynamic_stream_rows(self) -> None:
        html = render_sidebar(
            "today",
            {
                "badge": 0,
                "cal_html": "",
                "sleuth_html": "",
                "notices_html": "",
                "streams": [
                    {"name": "github", "label": "GitHub", "kbd": "G", "count": 10},
                    {"name": "email", "label": "Email", "kbd": "E", "count": 2},
                    {"name": "figma", "label": "Figma", "kbd": "F", "count": 0},
                ],
                "drift_total": 0,
                "semantic_total": 0,
            },
        )

        self.assertIn(">Email</span><span class=\"badge\">2</span>", html)
        self.assertIn(">Figma</span><span class=\"badge\">0</span>", html)
        self.assertNotIn(">Sleuth</span><span class=\"badge\">", html)

    def test_render_recent_figma_shows_comments_and_add_form(self) -> None:
        html = pulse_web.render_recent_figma(
            [
                {
                    "message": "Update hero CTA spacing before handoff.",
                    "user_handle": "designer",
                    "file_key": "VoQWc0fhO020JoxOyqeE1P",
                    "created_at": "2026-06-09T04:20:19.496Z",
                    "resolved_at": "",
                    "synced_at": "2026-06-09T04:52:51.992193+00:00",
                }
            ],
            datetime(2026, 6, 9, 5, 0, tzinfo=timezone.utc),
            tz=timezone.utc,
            limit=12,
            stored_total=686,
            configured_keys=["VoQWc0fhO020JoxOyqeE1P"],
            last_synced_at="2026-06-09T04:52:51.992193+00:00",
        )

        self.assertIn("Recent Figma comments", html)
        self.assertIn("Add Figma project ID", html)
        self.assertIn("Update hero CTA spacing before handoff.", html)
        self.assertIn("designer", html)
        self.assertIn("figma-project-form", html)


if __name__ == "__main__":
    unittest.main()
