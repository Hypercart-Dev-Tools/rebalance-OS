"""Tests for the static pulse "what's next" teaser.

The full ranked list lives on its own page (the FastAPI ``/whats-next`` route);
the static dashboard renders only a slim pointer (top item + count + link).
"""

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


class PulseWebWorkNextTeaserTests(unittest.TestCase):
    def test_teaser_shows_top_item_count_link_and_automation(self) -> None:
        rows = [
            {
                "rank": 1,
                "title": "Ship the calendar export fix",
                "person": None,
                "source": "github",
                "project": "rebalance-OS",
                "evidence": ["https://example.com/pr/1"],
                "why": "open PR you authored",
                "automation": True,
            },
            {
                "rank": 2,
                "title": "Unblock Matt on the migration",
                "person": "Matt",
                "source": "calendar",
                "project": None,
                "evidence": ["Matt 14:00 (30m)"],
                "why": "cross-person signal",
                "automation": False,
            },
            {
                "rank": 3,
                "title": "Review the ingest backfill",
                "person": None,
                "source": "github",
                "project": "rebalance-OS",
                "evidence": ["https://example.com/pr/2"],
                "why": "review requested",
                "automation": False,
            },
            {
                "rank": 4,
                "title": "Below the teaser cut line",
                "person": None,
                "source": "github",
                "project": None,
                "evidence": [],
                "why": "ranked but not surfaced",
                "automation": False,
            },
        ]

        html = pulse_web.render_work_next(
            rows, NOW, computed_at="2026-06-17T17:30:00+00:00", blended=True,
        )

        self.assertIn('class="card work-next work-next-teaser"', html)
        # Top THREE items shown (GH-135) — was top 1; the link points at the dedicated page.
        self.assertIn("Ship the calendar export fix", html)
        self.assertIn("Unblock Matt on the migration", html)
        self.assertIn("Review the ingest backfill", html)
        self.assertIn('href="/whats-next"', html)
        self.assertIn("Open What", html)
        # Count + automation-ready count + blend + freshness in the meta.
        self.assertIn("4 ranked", html)
        self.assertIn("automation-ready", html)
        self.assertIn("team-blended", html)
        self.assertIn("computed", html)
        # The teaser is still a POINTER — it does NOT dump the full list. GH-135 raised the
        # cut from 1 to 3, so this guards the CAP (4th item excluded), not a specific count.
        self.assertNotIn("Below the teaser cut line", html)
        self.assertNotIn("No ranked next actions yet", html)

    def test_teaser_top_person_badge_and_escaping(self) -> None:
        rows = [
            {
                "rank": 1,
                "title": "<script>alert('xss')</script>",
                "person": "<b>evil</b>",
                "source": "github",
                "project": None,
                "evidence": [],
                "why": "",
                "automation": True,
            },
        ]

        html = pulse_web.render_work_next(rows, NOW)

        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;alert", html)
        self.assertNotIn("<b>evil</b>", html)
        self.assertIn('class="wn-person"', html)
        # Automation indicator on the top item.
        self.assertIn("wn-auto", html)

    def test_teaser_empty_state_links_to_page(self) -> None:
        for rows in ([], None):
            html = pulse_web.render_work_next(rows, NOW)
            self.assertIn("No ranked next actions yet", html)
            self.assertIn('href="/whats-next"', html)
            self.assertIn('class="card work-next work-next-teaser"', html)

    def test_teaser_omits_automation_count_when_none(self) -> None:
        rows = [
            {
                "rank": 1,
                "title": "Plan the Q3 offsite",
                "person": None,
                "source": "calendar",
                "project": None,
                "evidence": [],
                "why": "",
                "automation": False,
            },
        ]

        html = pulse_web.render_work_next(rows, NOW)

        self.assertIn("1 ranked", html)
        self.assertNotIn("automation-ready", html)


if __name__ == "__main__":
    unittest.main()
