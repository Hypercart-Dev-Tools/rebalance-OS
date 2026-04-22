"""Unit tests for pulse_common helpers."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1] / "experimental" / "git-pulse"
)


def _load_module():
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "pulse_common", SCRIPT_DIR / "pulse_common.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["pulse_common"] = module
    spec.loader.exec_module(module)
    return module


pulse_common = _load_module()


class DailyActivityWithGapsTests(unittest.TestCase):
    def test_empty_dict_returns_empty(self) -> None:
        self.assertEqual(pulse_common.daily_activity_with_gaps({}), [])

    def test_no_gaps_returns_all_active_reverse_chrono(self) -> None:
        day_rows = {
            "2026-04-19": ["a"],
            "2026-04-20": ["b"],
            "2026-04-21": ["c"],
        }
        result = pulse_common.daily_activity_with_gaps(day_rows)
        self.assertEqual(
            result,
            [
                ("active", "2026-04-21", ["c"]),
                ("active", "2026-04-20", ["b"]),
                ("active", "2026-04-19", ["a"]),
            ],
        )

    def test_single_day_gap_collapses_to_count_one(self) -> None:
        day_rows = {
            "2026-04-18": ["a"],
            "2026-04-20": ["c"],
        }
        result = pulse_common.daily_activity_with_gaps(day_rows)
        self.assertEqual(
            result,
            [
                ("active", "2026-04-20", ["c"]),
                ("gap", ("2026-04-19", "2026-04-19"), 1),
                ("active", "2026-04-18", ["a"]),
            ],
        )

    def test_multi_day_gap_collapses_to_range(self) -> None:
        day_rows = {
            "2026-04-12": ["start"],
            "2026-04-17": ["end"],
        }
        result = pulse_common.daily_activity_with_gaps(day_rows)
        self.assertEqual(
            result,
            [
                ("active", "2026-04-17", ["end"]),
                ("gap", ("2026-04-13", "2026-04-16"), 4),
                ("active", "2026-04-12", ["start"]),
            ],
        )

    def test_multiple_gap_runs(self) -> None:
        day_rows = {
            "2026-04-10": ["a"],
            "2026-04-13": ["b"],
            "2026-04-20": ["c"],
        }
        result = pulse_common.daily_activity_with_gaps(day_rows)
        self.assertEqual(
            result,
            [
                ("active", "2026-04-20", ["c"]),
                ("gap", ("2026-04-14", "2026-04-19"), 6),
                ("active", "2026-04-13", ["b"]),
                ("gap", ("2026-04-11", "2026-04-12"), 2),
                ("active", "2026-04-10", ["a"]),
            ],
        )

    def test_malformed_keys_fallback(self) -> None:
        day_rows = {"not-a-date": ["x"]}
        result = pulse_common.daily_activity_with_gaps(day_rows)
        self.assertEqual(result, [("active", "not-a-date", ["x"])])


if __name__ == "__main__":
    unittest.main()
