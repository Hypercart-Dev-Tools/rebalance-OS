"""Tests for the sidebar Calendar module (day grid + Upcoming list).

The grid is absolutely positioned from a decimal-hour → pixel mapping, so these
tests pin the geometry (top/height), the past-vs-upcoming state derivation, the
now-indicator's clamping, and the year-less Upcoming timestamp format. The clock
is always passed in explicitly — never `datetime.now()` — so the assertions are
stable regardless of when the suite runs.
"""

from __future__ import annotations

import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pulse_web  # noqa: E402

TZ = ZoneInfo("America/Los_Angeles")
# 2026-07-18 13:30 local (Saturday) — mid-grid, so "past" and "upcoming" both exist.
NOW = datetime(2026, 7, 18, 20, 30, tzinfo=timezone.utc)


def _event(summary, start, end, location=None):
    return {
        "summary": summary,
        "start_time": start,
        "end_time": end,
        "location": location,
    }


def _top(html, title):
    """Pull the inline `top:` px value off the block whose title matches."""
    m = re.search(
        r'<div class="cal-event [^"]*" style="top:(\d+)px;height:(\d+)px"'
        r'[^>]*>.*?<span class="cal-event-title">' + re.escape(title),
        html,
        re.S,
    )
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


class CalendarGridGeometryTests(unittest.TestCase):
    def test_event_top_and_height_follow_the_hour_scale(self) -> None:
        rows = [_event("Team Call", "2026-07-18T20:45:00Z", "2026-07-18T21:45:00Z")]
        html = pulse_web.render_calendar_module(rows, [], NOW, tz=TZ)
        # 1:45 PM local → (13.75 - 8) * 44 = 253px; 1h → 44px.
        top, height = _top(html, "Team Call")
        self.assertEqual(top, 253)
        self.assertEqual(height, pulse_web.CAL_HOUR_PX)

    def test_short_event_respects_min_height(self) -> None:
        # A 5-minute event would be ~4px; the floor keeps it clickable/legible.
        rows = [_event("Standup", "2026-07-18T17:00:00Z", "2026-07-18T17:05:00Z")]
        html = pulse_web.render_calendar_module(rows, [], NOW, tz=TZ)
        _, height = _top(html, "Standup")
        self.assertEqual(height, pulse_web.CAL_MIN_EVENT_PX)

    def test_time_line_only_on_tall_enough_blocks(self) -> None:
        short = [_event("Quick", "2026-07-18T17:00:00Z", "2026-07-18T17:15:00Z")]
        tall = [_event("Long", "2026-07-18T17:00:00Z", "2026-07-18T19:00:00Z")]
        self.assertNotIn("cal-event-time", pulse_web.render_calendar_module(short, [], NOW, tz=TZ))
        self.assertIn("cal-event-time", pulse_web.render_calendar_module(tall, [], NOW, tz=TZ))

    def test_events_outside_the_window_do_not_render_as_blocks(self) -> None:
        # 6:00 AM local is before the 8 AM grid start.
        rows = [_event("Dawn run", "2026-07-18T13:00:00Z", "2026-07-18T13:30:00Z")]
        html = pulse_web.render_calendar_module(rows, [], NOW, tz=TZ)
        self.assertNotIn("Dawn run", html)

    def test_missing_end_time_falls_back_to_thirty_minutes(self) -> None:
        rows = [_event("No end", "2026-07-18T18:00:00Z", None)]
        html = pulse_web.render_calendar_module(rows, [], NOW, tz=TZ)
        _, height = _top(html, "No end")
        self.assertEqual(height, int(pulse_web.CAL_HOUR_PX / 2))


class CalendarEventStateTests(unittest.TestCase):
    def test_finished_event_is_past_and_future_event_is_upcoming(self) -> None:
        rows = [
            _event("Earlier", "2026-07-18T19:00:00Z", "2026-07-18T19:30:00Z"),  # ended 12:30
            _event("Later", "2026-07-18T22:00:00Z", "2026-07-18T22:30:00Z"),    # starts 3:00
        ]
        html = pulse_web.render_calendar_module(rows, [], NOW, tz=TZ)
        self.assertRegex(html, r'class="cal-event past"[^>]*>.*?Earlier')
        self.assertRegex(html, r'class="cal-event upcoming"[^>]*>.*?Later')


class CalendarNowIndicatorTests(unittest.TestCase):
    def test_now_line_positioned_at_the_current_time(self) -> None:
        html = pulse_web.render_calendar_module([], [], NOW, tz=TZ)
        # 13:30 local → (13.5 - 8) * 44 = 242px
        self.assertIn('id="cal-now" style="top:242px"', html)

    def test_now_line_hidden_outside_the_grid_window(self) -> None:
        # 5:30 AM local — before the window opens.
        early = datetime(2026, 7, 18, 12, 30, tzinfo=timezone.utc)
        self.assertNotIn("cal-now", pulse_web.render_calendar_module([], [], early, tz=TZ))


class CalendarUpcomingTests(unittest.TestCase):
    def test_upcoming_uses_the_year_less_month_day_format(self) -> None:
        later = [_event("Coffee", "2026-07-19T18:00:00Z", "2026-07-19T19:00:00Z")]
        html = pulse_web.render_calendar_module([], later, NOW, tz=TZ)
        self.assertIn("July 19 11:00 AM", html)
        self.assertNotIn("2026-07-19", html)

    def test_upcoming_excludes_today_and_caps_the_list(self) -> None:
        today = _event("Today thing", "2026-07-18T22:00:00Z", "2026-07-18T23:00:00Z")
        later = [
            _event(f"Day {i}", f"2026-07-{19 + i}T18:00:00Z", f"2026-07-{19 + i}T19:00:00Z")
            for i in range(pulse_web.CAL_UPCOMING_LIMIT + 2)
        ]
        html = pulse_web.render_calendar_module([], [today, *later], NOW, tz=TZ)
        self.assertNotIn("Today thing", html.split('class="cal-upcoming"')[-1])
        self.assertEqual(html.count("cal-up-row"), pulse_web.CAL_UPCOMING_LIMIT)

    def test_location_is_appended_and_zebra_alternates(self) -> None:
        later = [
            _event("Noel/Russ", "2026-07-19T18:00:00Z", "2026-07-19T19:00:00Z", "Philz Coffee"),
            _event("Walking", "2026-07-19T19:00:00Z", "2026-07-19T19:30:00Z"),
        ]
        html = pulse_web.render_calendar_module([], later, NOW, tz=TZ)
        self.assertIn("Noel/Russ · Philz Coffee", html)
        self.assertIn('data-rb-stripe="odd"', html)
        self.assertIn('data-rb-stripe="even"', html)

    def test_no_upcoming_block_when_there_is_nothing_later(self) -> None:
        self.assertNotIn("cal-upcoming", pulse_web.render_calendar_module([], [], NOW, tz=TZ))


if __name__ == "__main__":
    unittest.main()
