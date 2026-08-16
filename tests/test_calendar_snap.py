"""Tests for calendar edge-snapping: overlap detection (read-only) and gapless default."""

import unittest
from datetime import date
from unittest.mock import MagicMock

from rebalance.ingest.calendar_snap import (
    _detect_overlaps,
    _is_allday_event,
    snap_day_edges,
)


# ---------------------------------------------------------------------------
# Test-data helpers
# ---------------------------------------------------------------------------


def _make_event(
    event_id: str,
    summary: str,
    start_iso: str,
    end_iso: str,
) -> dict:
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
        "status": "confirmed",
    }


def _make_allday_event(event_id: str, summary: str, date_str: str) -> dict:
    return {
        "id": event_id,
        "summary": summary,
        "start": {"date": date_str},
        "end": {"date": date_str},
        "status": "confirmed",
    }


# ---------------------------------------------------------------------------
# _is_allday_event
# ---------------------------------------------------------------------------


class IsAlldayEventTests(unittest.TestCase):
    def test_timed_event_is_not_allday(self) -> None:
        ev = _make_event("1", "Meeting", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00")
        self.assertFalse(_is_allday_event(ev))

    def test_allday_event_is_allday(self) -> None:
        ev = _make_allday_event("1", "Holiday", "2026-04-15")
        self.assertTrue(_is_allday_event(ev))


# ---------------------------------------------------------------------------
# _detect_overlaps
# ---------------------------------------------------------------------------


class DetectOverlapsTests(unittest.TestCase):
    def test_no_events(self) -> None:
        pairs, skipped, allday = _detect_overlaps([])
        self.assertEqual(pairs, [])
        self.assertEqual(skipped, [])
        self.assertEqual(allday, 0)

    def test_single_event(self) -> None:
        events = [_make_event("1", "Solo", "2026-04-15T09:00:00-07:00", "2026-04-15T10:00:00-07:00")]
        pairs, skipped, allday = _detect_overlaps(events)
        self.assertEqual(pairs, [])
        self.assertEqual(skipped, [])

    def test_no_overlap_adjacent(self) -> None:
        """Events that are exactly adjacent (end == start) should NOT overlap."""
        events = [
            _make_event("1", "A", "2026-04-15T09:00:00-07:00", "2026-04-15T10:00:00-07:00"),
            _make_event("2", "B", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
        ]
        pairs, skipped, _ = _detect_overlaps(events)
        self.assertEqual(pairs, [])
        self.assertEqual(skipped, [])

    def test_two_event_overlap_gapless_default(self) -> None:
        """Classic case: Event 1 ends 3 min into Event 2. Default is gapless —
        Event 1's suggested end equals Event 2's start (no time lost)."""
        events = [
            _make_event("1", "Standup", "2026-04-15T09:00:00-07:00", "2026-04-15T10:03:00-07:00"),
            _make_event("2", "Planning", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
        ]
        pairs, skipped, _ = _detect_overlaps(events)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].event1_id, "1")
        self.assertEqual(pairs[0].event2_id, "2")
        self.assertEqual(pairs[0].event1_new_end, "2026-04-15T10:00:00-07:00")
        self.assertEqual(pairs[0].overlap_minutes, 3)
        self.assertEqual(skipped, [])

    def test_gap_minutes_leaves_gap(self) -> None:
        """A positive gap_minutes trims to that many minutes before Event 2's
        start (the time-losing legacy behavior, now opt-in only)."""
        events = [
            _make_event("1", "Standup", "2026-04-15T09:00:00-07:00", "2026-04-15T10:03:00-07:00"),
            _make_event("2", "Planning", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
        ]
        pairs, _, _ = _detect_overlaps(events, gap_minutes=1)
        self.assertEqual(pairs[0].event1_new_end, "2026-04-15T09:59:00-07:00")

    def test_three_event_cluster_skipped(self) -> None:
        """3+ overlapping events should be skipped entirely."""
        events = [
            _make_event("1", "A", "2026-04-15T09:00:00-07:00", "2026-04-15T10:30:00-07:00"),
            _make_event("2", "B", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
            _make_event("3", "C", "2026-04-15T10:30:00-07:00", "2026-04-15T12:00:00-07:00"),
        ]
        pairs, skipped, _ = _detect_overlaps(events)
        self.assertEqual(pairs, [])
        self.assertEqual(len(skipped), 1)
        self.assertEqual(len(skipped[0].event_ids), 3)
        self.assertIn("manual resolution required", skipped[0].reason)

    def test_allday_events_filtered(self) -> None:
        """All-day events should be excluded from overlap detection."""
        events = [
            _make_allday_event("ad1", "Holiday", "2026-04-15"),
            _make_event("1", "A", "2026-04-15T09:00:00-07:00", "2026-04-15T10:05:00-07:00"),
            _make_event("2", "B", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
        ]
        pairs, skipped, allday = _detect_overlaps(events)
        self.assertEqual(allday, 1)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].event1_id, "1")

    def test_two_separate_overlap_pairs(self) -> None:
        """Two independent 2-event overlaps in the same day."""
        events = [
            _make_event("1", "A", "2026-04-15T09:00:00-07:00", "2026-04-15T10:02:00-07:00"),
            _make_event("2", "B", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
            _make_event("3", "C", "2026-04-15T14:00:00-07:00", "2026-04-15T15:05:00-07:00"),
            _make_event("4", "D", "2026-04-15T15:00:00-07:00", "2026-04-15T16:00:00-07:00"),
        ]
        pairs, skipped, _ = _detect_overlaps(events)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0].event1_id, "1")
        self.assertEqual(pairs[1].event1_id, "3")
        self.assertEqual(skipped, [])

    def test_contained_event_skipped(self) -> None:
        """Event B completely inside Event A — skipped, not auto-truncated."""
        events = [
            _make_event("1", "A", "2026-04-15T09:00:00-07:00", "2026-04-15T12:00:00-07:00"),
            _make_event("2", "B", "2026-04-15T10:00:00-07:00", "2026-04-15T10:30:00-07:00"),
        ]
        pairs, skipped, _ = _detect_overlaps(events)
        self.assertEqual(len(pairs), 0)
        self.assertEqual(len(skipped), 1)
        self.assertIn("fully contains", skipped[0].reason)

    def test_mixed_offsets_no_false_overlap(self) -> None:
        """Events with different UTC offsets that don't overlap in real time."""
        # 09:00-09:30 UTC is 09:00-09:30 real time
        # 10:00-10:30 +02:00 is 08:00-08:30 UTC — actually BEFORE the first event
        events = [
            _make_event("1", "A", "2026-04-15T09:00:00+00:00", "2026-04-15T09:30:00+00:00"),
            _make_event("2", "B", "2026-04-15T10:00:00+02:00", "2026-04-15T10:30:00+02:00"),
        ]
        pairs, skipped, _ = _detect_overlaps(events)
        self.assertEqual(len(pairs), 0)
        self.assertEqual(len(skipped), 0)

    def test_utc_z_suffix_handled(self) -> None:
        """Events with Z suffix should parse correctly."""
        events = [
            _make_event("1", "A", "2026-04-15T17:00:00Z", "2026-04-15T18:05:00Z"),
            _make_event("2", "B", "2026-04-15T18:00:00Z", "2026-04-15T19:00:00Z"),
        ]
        pairs, skipped, _ = _detect_overlaps(events)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].overlap_minutes, 5)


# ---------------------------------------------------------------------------
# snap_day_edges (integration with mocked API) — read-only, never patches
# ---------------------------------------------------------------------------


class SnapDayEdgesTests(unittest.TestCase):
    def _mock_service_with_events(self, events: list[dict]) -> MagicMock:
        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": events,
        }
        mock_service.events.return_value.patch.return_value.execute.return_value = {}
        return mock_service

    def test_detects_overlap_without_patching(self) -> None:
        """Overlaps are detected and reported; the calendar is never patched."""
        events = [
            _make_event("1", "A", "2026-04-15T09:00:00-07:00", "2026-04-15T10:05:00-07:00"),
            _make_event("2", "B", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
        ]
        mock_service = self._mock_service_with_events(events)

        result = snap_day_edges(
            mock_service, "primary", date(2026, 4, 15), "America/Los_Angeles"
        )

        self.assertEqual(len(result.snapped), 1)
        # Gapless suggested boundary (no time lost), and NO write-back.
        self.assertEqual(result.snapped[0].event1_new_end, "2026-04-15T10:00:00-07:00")
        mock_service.events.return_value.patch.assert_not_called()

    def test_no_overlaps_clean_day(self) -> None:
        events = [
            _make_event("1", "A", "2026-04-15T09:00:00-07:00", "2026-04-15T10:00:00-07:00"),
            _make_event("2", "B", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
        ]
        mock_service = self._mock_service_with_events(events)

        result = snap_day_edges(
            mock_service, "primary", date(2026, 4, 15), "America/Los_Angeles"
        )

        self.assertEqual(len(result.snapped), 0)
        self.assertEqual(len(result.skipped_clusters), 0)
        self.assertEqual(result.total_events_examined, 2)
        mock_service.events.return_value.patch.assert_not_called()


# ---------------------------------------------------------------------------
# snap_edges (num_days validation)
# ---------------------------------------------------------------------------


class SnapEdgesValidationTests(unittest.TestCase):
    def test_num_days_zero_raises(self) -> None:
        from rebalance.ingest.calendar_snap import snap_edges

        with self.assertRaises(ValueError):
            snap_edges(
                calendar_id="primary",
                start_date=date(2026, 4, 15),
                num_days=0,
                timezone_name="America/Los_Angeles",
            )

    def test_num_days_eight_raises(self) -> None:
        from rebalance.ingest.calendar_snap import snap_edges

        with self.assertRaises(ValueError):
            snap_edges(
                calendar_id="primary",
                start_date=date(2026, 4, 15),
                num_days=8,
                timezone_name="America/Los_Angeles",
            )


# ---------------------------------------------------------------------------
# snap_calendar_edges MCP tool — days range validation (GH-9)
# ---------------------------------------------------------------------------


class SnapCalendarEdgesMCPDaysValidationTests(unittest.TestCase):
    """The MCP tool must return a structured error dict for out-of-range days,
    never propagate the raw ValueError from snap_edges().

    snap_calendar_edges is defined inside register(), so we extract it by
    calling register() with a mock FastMCP that captures decorated functions.
    The guard fires before CalendarConfig.load(), so no config mocking is
    needed for the invalid-day cases.
    """

    def _get_snap_fn(self):
        """Call register() with a capturing mock FastMCP; return the tool fn."""
        from pathlib import Path
        from unittest.mock import MagicMock

        captured: dict = {}

        mock_mcp = MagicMock()

        def _tool_decorator():
            def _wrap(fn):
                captured[fn.__name__] = fn
                return fn
            return _wrap

        mock_mcp.tool = _tool_decorator

        import rebalance.mcp.tools.calendar as cal_mod
        cal_mod.register(mock_mcp, Path("/fake/db.sqlite"))
        return captured["snap_calendar_edges"]

    def test_days_zero_returns_error_dict(self) -> None:
        result = self._get_snap_fn()(date_str="", days=0, calendar_id="", timezone_name="")
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("status"), "error")
        self.assertIn("days", result.get("error", ""))

    def test_days_eight_returns_error_dict(self) -> None:
        result = self._get_snap_fn()(date_str="", days=8, calendar_id="", timezone_name="")
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("status"), "error")
        self.assertIn("days", result.get("error", ""))

    def test_days_valid_boundary_does_not_error(self) -> None:
        """days=1 and days=7 must not hit the validation guard."""
        import dataclasses
        from unittest.mock import MagicMock, patch

        @dataclasses.dataclass
        class _FakeSnap:
            snapped: list = dataclasses.field(default_factory=list)
            skipped_clusters: list = dataclasses.field(default_factory=list)
            total_events_examined: int = 0
            allday_count: int = 0

        snap_fn = self._get_snap_fn()
        for valid in (1, 7):
            with patch(
                "rebalance.ingest.calendar_config.CalendarConfig"
            ) as mock_cfg, patch(
                "rebalance.ingest.calendar_snap.snap_edges",
                return_value=_FakeSnap(),
            ):
                mock_cfg.load.return_value = MagicMock(
                    calendar_id="primary",
                    timezone="America/Los_Angeles",
                    snap_gap_minutes=0,
                )
                result = snap_fn(
                    date_str="2026-04-15", days=valid, calendar_id="", timezone_name=""
                )
                self.assertNotEqual(
                    result.get("status"),
                    "error",
                    msg=f"days={valid} should not return an error dict",
                )


if __name__ == "__main__":
    unittest.main()
