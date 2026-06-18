"""Tests for the static pulse "what should we work on next" panel."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pulse_web  # noqa: E402


NOW = datetime(2026, 6, 17, 18, 0, tzinfo=timezone.utc)


class PulseWebWorkNextTests(unittest.TestCase):
    def test_render_work_next_renders_ranked_items(self) -> None:
        rows = [
            {
                "rank": 1,
                "title": "Ship the calendar export fix",
                "person": None,
                "source": "github",
                "project": "rebalance-OS",
                "evidence": ["https://example.com/pr/1"],
                "why": "open PR you authored",
            },
            {
                "rank": 2,
                "title": "Unblock Matt on the migration",
                "person": "Matt",
                "source": "calendar",
                "project": None,
                "evidence": ["Matt 14:00 (30m)"],
                "why": "cross-person signal you are not already tracking",
            },
        ]

        html = pulse_web.render_work_next(
            rows,
            NOW,
            computed_at="2026-06-17T17:30:00+00:00",
            blended=True,
            model_used="gemini-2.5-flash",
        )

        self.assertIn("What should we work on next", html)
        self.assertIn('class="card work-next"', html)
        self.assertIn("Ship the calendar export fix", html)
        # Teammate-attributed item with its person badge.
        self.assertIn("Unblock Matt on the migration", html)
        self.assertIn('class="wn-person">Matt</span>', html)
        # Meta indicators.
        self.assertIn("team-blended", html)
        self.assertIn("gemini-2.5-flash", html)
        self.assertIn("computed", html)
        # No empty-state when rows exist.
        self.assertNotIn("No ranked next actions yet", html)

    def test_render_work_next_escapes_hostile_input(self) -> None:
        rows = [
            {
                "rank": 1,
                "title": "<script>alert('xss')</script>",
                "person": "<b>evil</b>",
                "source": "github",
                "project": "<i>proj</i>",
                "evidence": [],
                "why": "look out <img src=x onerror=1>",
            },
        ]

        html = pulse_web.render_work_next(rows, NOW)

        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;alert", html)
        self.assertNotIn("<b>evil</b>", html)
        self.assertIn("&lt;b&gt;evil&lt;/b&gt;", html)
        self.assertNotIn("<i>proj</i>", html)
        self.assertNotIn("<img src=x", html)

    def test_render_work_next_empty_state_when_falsy(self) -> None:
        for rows in ([], None):
            html = pulse_web.render_work_next(rows, NOW)
            self.assertIn("What should we work on next", html)
            self.assertIn("No ranked next actions yet", html)
            self.assertIn('class="card work-next"', html)

    def test_render_work_next_omits_meta_when_absent(self) -> None:
        rows = [
            {
                "rank": 1,
                "title": "Solo task",
                "person": None,
                "source": "vault",
                "project": None,
                "evidence": [],
                "why": "",
            },
        ]

        html = pulse_web.render_work_next(rows, NOW)

        self.assertIn("Solo task", html)
        self.assertNotIn("team-blended", html)
        self.assertNotIn('class="card-head-meta"', html)


if __name__ == "__main__":
    unittest.main()
