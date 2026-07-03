"""Tests for the XYZ harness pin — GH-102 seam #2.

Covers the reader (``rebalance.xyz_pin.read_pin``) and the doctor check
(``_check_xyz_pin``): an absent pin is a healthy OK skip (mutual independence),
a valid pin surfaces its commit, and a pin missing its ``commit`` key warns.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.doctor import OK, WARN, _check_xyz_pin
from rebalance.xyz_pin import read_pin


class ReadPinTest(unittest.TestCase):
    def test_absent_pin_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(read_pin(Path(d)))

    def test_valid_pin_parses_keys(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".xyz-pin").write_text(
                "# a comment\n"
                "\n"
                "commit=c829000bad5e196392e5ffbff5838cc558877f67\n"
                "pinned_at=2026-07-03\n",
                encoding="utf-8",
            )
            pin = read_pin(Path(d))
            self.assertIsNotNone(pin)
            self.assertEqual(pin["commit"], "c829000bad5e196392e5ffbff5838cc558877f67")
            self.assertEqual(pin["pinned_at"], "2026-07-03")

    def test_malformed_lines_are_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".xyz-pin").write_text(
                "this line has no equals sign\n"
                "commit=abc123\n",
                encoding="utf-8",
            )
            pin = read_pin(Path(d))
            self.assertEqual(pin, {"commit": "abc123"})


class CheckXyzPinTest(unittest.TestCase):
    def test_absent_pin_is_ok_skip(self):
        with patch("rebalance.xyz_pin.read_pin", return_value=None):
            check = _check_xyz_pin()
        self.assertEqual(check.status, OK)
        self.assertIn("no XYZ harness pinned", check.detail)

    def test_valid_pin_surfaces_commit(self):
        pin = {"commit": "c829000bad5e196392e5ffbff5838cc558877f67", "pinned_at": "2026-07-03"}
        with patch("rebalance.xyz_pin.read_pin", return_value=pin):
            check = _check_xyz_pin()
        self.assertEqual(check.status, OK)
        self.assertIn("c829000bad5e", check.detail)
        self.assertIn("2026-07-03", check.detail)

    def test_pin_without_commit_warns(self):
        with patch("rebalance.xyz_pin.read_pin", return_value={"pinned_at": "2026-07-03"}):
            check = _check_xyz_pin()
        self.assertEqual(check.status, WARN)
        self.assertIn("no `commit=`", check.detail)


if __name__ == "__main__":
    unittest.main()
