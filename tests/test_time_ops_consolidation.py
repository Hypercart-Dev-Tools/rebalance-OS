"""Contract for the consolidated ISO parser (GH-266 Phase 1).

Four separate ISO-8601 readers were collapsed into `rebalance.lib.time_ops._parse_iso`:
`health._parse_iso`, `tz_utils.parse_utc_iso`, `index_ops`'s private parser, and
`calendar_helpers.parse_calendar_dt`. They did *not* agree at the edges — one accepted
space-separated timestamps, one raised instead of returning None, one preserved a
non-UTC offset. Consolidation is only safe if the survivor honours each caller's
contract, and the suite did not pin those edges before.

These tests exist so a future edit to the shared parser cannot silently change one
caller's semantics while the other three keep passing.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from rebalance.health import _parse_iso as health_parse
from rebalance.ingest.calendar_helpers import parse_calendar_dt
from rebalance.lib.time_ops import _parse_iso
from rebalance.tz_utils import parse_utc_iso


class SharedParserContract(unittest.TestCase):
    def test_rejects_non_strings_instead_of_raising(self) -> None:
        # health.py fed this arbitrary JSON values; a raise here would crash doctor.
        for bad in (None, 0, 17, [], {}, object()):
            self.assertIsNone(_parse_iso(bad), f"expected None for {bad!r}")

    def test_trailing_z_is_utc(self) -> None:
        parsed = _parse_iso("2026-08-14T12:00:00Z")
        self.assertEqual(parsed, datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc))

    def test_space_separated_form_is_accepted(self) -> None:
        # index_ops' parser accepted this; the other three did not. The survivor must.
        parsed = _parse_iso("2026-08-14 12:00:00+00:00")
        self.assertEqual(parsed, datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc))

    def test_naive_input_is_assumed_utc(self) -> None:
        parsed = _parse_iso("2026-08-14T12:00:00")
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.hour, 12)

    def test_force_utc_preserves_the_instant_not_the_offset(self) -> None:
        # tz_utils.parse_utc_iso previously returned the original offset. It now
        # normalises to UTC. That is only safe because every caller compares
        # instants; this pins that the *instant* is unchanged.
        parsed = _parse_iso("2026-08-14T09:00:00-07:00")
        self.assertEqual(parsed, datetime(2026, 8, 14, 16, 0, tzinfo=timezone.utc))
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)

    def test_force_utc_false_preserves_naive(self) -> None:
        # All-day calendar events must stay naive — calendar_dt_utc keys off this.
        parsed = _parse_iso("2026-08-14", force_utc=False)
        self.assertIsNone(parsed.tzinfo)

    def test_garbage_returns_none(self) -> None:
        for bad in ("", "   ", "not-a-date", "2026-13-45T99:99:99"):
            self.assertIsNone(_parse_iso(bad), f"expected None for {bad!r}")


class CallerContractsPreserved(unittest.TestCase):
    def test_parse_calendar_dt_still_raises_on_bad_input(self) -> None:
        # Its callers catch (TypeError, ValueError). Returning None instead of
        # raising would silently produce a None where a datetime is required.
        with self.assertRaises(ValueError):
            parse_calendar_dt("not-a-date")

    def test_parse_calendar_dt_keeps_all_day_events_naive(self) -> None:
        self.assertIsNone(parse_calendar_dt("2026-08-14").tzinfo)

    def test_parse_utc_iso_returns_none_not_raises(self) -> None:
        self.assertIsNone(parse_utc_iso("not-a-date"))
        self.assertIsNone(parse_utc_iso(None))

    def test_health_parse_tolerates_arbitrary_json_values(self) -> None:
        self.assertIsNone(health_parse({"nested": "object"}))
        self.assertEqual(
            health_parse("2026-08-14T12:00:00Z"),
            datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
        )


class GitOpsTimeout(unittest.TestCase):
    def test_git_returns_none_on_timeout_rather_than_hanging(self) -> None:
        import subprocess
        from unittest.mock import patch

        from rebalance.lib.git_ops import _git

        with patch("rebalance.lib.git_ops.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="git", timeout=30.0)):
            self.assertIsNone(_git(__import__("pathlib").Path("/tmp"), "status"))


if __name__ == "__main__":
    unittest.main()
