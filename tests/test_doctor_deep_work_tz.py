"""Regression coverage for the local-day deep-work health signal."""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from rebalance.doctor import OK, WARN, _check_deep_work_stalls


class DeepWorkStallTimezoneTests(unittest.TestCase):
    """The doctor must evaluate deep-work signals in the operator's local day."""

    operator_tz = "America/Los_Angeles"

    def _run_check(
        self,
        instant: datetime,
        signals: dict[str, dict[str, object]] | None = None,
        process_tz: str = "UTC",
    ) -> tuple[object, date]:
        captured: list[date] = []

        def compute(_db_path: Path, today: date, *, lookback_days: int) -> dict[str, dict[str, object]]:
            self.assertEqual(lookback_days, 7)
            captured.append(today)
            return signals or {}

        with (
            mock.patch.dict(
                os.environ,
                {"REBALANCE_TZ": self.operator_tz, "TZ": process_tz},
                clear=False,
            ),
            mock.patch("rebalance.doctor.datetime") as clock,
            mock.patch(
                "rebalance.ingest.next_actions.compute_deep_work_signals",
                side_effect=compute,
            ),
        ):
            clock.now.side_effect = lambda tz=None: instant.astimezone(tz)
            check = _check_deep_work_stalls(Path("/tmp/rebalance.db"))

        self.assertEqual(len(captured), 1)
        return check, captured[0]

    def test_evening_pacific_uses_current_local_day_not_next_utc_day(self) -> None:
        # 18:59 PDT is 01:59 UTC on the following date. This assertion fails
        # with the former datetime.now(timezone.utc).date() implementation.
        instant = datetime(2026, 7, 19, 1, 59, tzinfo=timezone.utc)

        check, observed_today = self._run_check(instant)

        self.assertEqual(check.status, OK)
        self.assertEqual(observed_today, date(2026, 7, 18))

    def test_morning_pacific_remains_current_local_day(self) -> None:
        instant = datetime(2026, 7, 18, 16, 0, tzinfo=timezone.utc)  # 09:00 PDT

        _check, observed_today = self._run_check(instant)

        self.assertEqual(observed_today, date(2026, 7, 18))

    def test_genuine_stall_still_warns(self) -> None:
        instant = datetime(2026, 7, 18, 16, 0, tzinfo=timezone.utc)
        signals = {
            "Stalled Project": {
                "project": "Stalled Project",
                "possible_stall": True,
                "evidence": {
                    "today_date": "2026-07-18",
                    "yesterday_date": "2026-07-17",
                    "yesterday_rows": ["commit abc123"],
                    "open_items": [
                        {"item_type": "pull_request", "number": 42, "title": "Finish work"}
                    ],
                },
            }
        }

        check, _observed_today = self._run_check(instant, signals)

        self.assertEqual(check.status, WARN)
        self.assertIn("Stalled Project: quiet 2026-07-18", check.detail)
        self.assertIn("pr #42 Finish work", check.detail)

    def test_process_timezone_does_not_change_operator_today(self) -> None:
        instant = datetime(2026, 7, 19, 1, 59, tzinfo=timezone.utc)

        _utc_check, utc_today = self._run_check(instant, process_tz="UTC")
        _tokyo_check, tokyo_today = self._run_check(instant, process_tz="Asia/Tokyo")

        self.assertEqual(utc_today, date(2026, 7, 18))
        self.assertEqual(tokyo_today, utc_today)


if __name__ == "__main__":
    unittest.main()
