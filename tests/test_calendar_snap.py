"""Tests for calendar edge-snapping: overlap detection, patch calls, and CLI."""

import unittest
from datetime import date
from unittest.mock import MagicMock, call, patch

from rebalance.ingest.calendar_snap import (
    OverlapPair,
    SkippedCluster,
    SnapDayResult,
    _detect_overlaps,
    _is_allday_event,
    _patch_event_end,
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

    def test_two_event_overlap(self) -> None:
        """Classic case: Event 1 ends 3 min into Event 2."""
        events = [
            _make_event("1", "Standup", "2026-04-15T09:00:00-07:00", "2026-04-15T10:03:00-07:00"),
            _make_event("2", "Planning", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
        ]
        pairs, skipped, _ = _detect_overlaps(events)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].event1_id, "1")
        self.assertEqual(pairs[0].event2_id, "2")
        self.assertEqual(pairs[0].event1_new_end, "2026-04-15T09:59:00-07:00")
        self.assertEqual(pairs[0].overlap_minutes, 3)
        self.assertEqual(skipped, [])

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

    def test_contained_event_treated_as_pair(self) -> None:
        """Event B completely inside Event A — still a 2-event overlap."""
        events = [
            _make_event("1", "A", "2026-04-15T09:00:00-07:00", "2026-04-15T12:00:00-07:00"),
            _make_event("2", "B", "2026-04-15T10:00:00-07:00", "2026-04-15T10:30:00-07:00"),
        ]
        pairs, skipped, _ = _detect_overlaps(events)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].event1_id, "1")
        # Event A's end gets trimmed to 9:59 (1 min before B's start at 10:00)
        self.assertEqual(pairs[0].event1_new_end, "2026-04-15T09:59:00-07:00")

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
# _patch_event_end
# ---------------------------------------------------------------------------


class PatchEventEndTests(unittest.TestCase):
    def test_patch_called_with_correct_args(self) -> None:
        mock_service = MagicMock()
        mock_service.events.return_value.patch.return_value.execute.return_value = {"id": "evt-1"}

        _patch_event_end(
            mock_service,
            "cal@example.com",
            "evt-1",
            "2026-04-15T09:59:00-07:00",
        )

        mock_service.events.return_value.patch.assert_called_once_with(
            calendarId="cal@example.com",
            eventId="evt-1",
            body={"end": {"dateTime": "2026-04-15T09:59:00-07:00"}},
            sendUpdates="none",
        )

    def test_patch_preserves_timezone(self) -> None:
        mock_service = MagicMock()
        mock_service.events.return_value.patch.return_value.execute.return_value = {"id": "evt-1"}

        _patch_event_end(
            mock_service,
            "cal@example.com",
            "evt-1",
            "2026-04-15T09:59:00-07:00",
            original_end_timezone="America/Los_Angeles",
        )

        patch_kwargs = mock_service.events.return_value.patch.call_args.kwargs
        self.assertEqual(
            patch_kwargs["body"]["end"]["timeZone"],
            "America/Los_Angeles",
        )


# ---------------------------------------------------------------------------
# snap_day_edges (integration with mocked API)
# ---------------------------------------------------------------------------


class SnapDayEdgesTests(unittest.TestCase):
    def _mock_service_with_events(self, events: list[dict]) -> MagicMock:
        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": events,
        }
        mock_service.events.return_value.patch.return_value.execute.return_value = {}
        return mock_service

    def test_dry_run_does_not_patch(self) -> None:
        events = [
            _make_event("1", "A", "2026-04-15T09:00:00-07:00", "2026-04-15T10:05:00-07:00"),
            _make_event("2", "B", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
        ]
        mock_service = self._mock_service_with_events(events)

        result = snap_day_edges(
            mock_service, "primary", date(2026, 4, 15), "America/Los_Angeles", apply=False
        )

        self.assertEqual(len(result.snapped), 1)
        mock_service.events.return_value.patch.assert_not_called()

    def test_apply_calls_patch(self) -> None:
        events = [
            _make_event("1", "A", "2026-04-15T09:00:00-07:00", "2026-04-15T10:05:00-07:00"),
            _make_event("2", "B", "2026-04-15T10:00:00-07:00", "2026-04-15T11:00:00-07:00"),
        ]
        mock_service = self._mock_service_with_events(events)

        result = snap_day_edges(
            mock_service, "primary", date(2026, 4, 15), "America/Los_Angeles", apply=True
        )

        self.assertEqual(len(result.snapped), 1)
        mock_service.events.return_value.patch.assert_called_once()

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


if __name__ == "__main__":
    unittest.main()
