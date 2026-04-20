"""Tests for the experimental deterministic GH close-candidates script."""

import importlib.util
import sys
import unittest
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parent.parent / "experimental" / "gh_close_candidates_action.py"
    spec = importlib.util.spec_from_file_location("gh_close_candidates_action", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ExperimentalCloseCandidatesActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def test_explicit_close_keyword_is_high_confidence(self) -> None:
        report = self.module.build_close_candidates_report(
            "BinoidCBD/universal-child-theme-oct-2024",
            "development",
            [
                {
                    "number": 101,
                    "title": "Fix mini-cart hydration bug",
                    "body": "",
                    "html_url": "https://example.com/issues/101",
                }
            ],
            [
                {
                    "number": 202,
                    "title": "Fix mini-cart hydration bug",
                    "body": "Fixes #101 by shipping the final AJAX hydration patch.",
                    "headRefName": "fix/101-mini-cart",
                    "baseRefName": "development",
                    "mergedAt": "2026-04-20T12:00:00Z",
                    "html_url": "https://example.com/pull/202",
                }
            ],
        )

        self.assertEqual(report.counts["high_confidence"], 1)
        candidate = report.high_confidence[0]
        self.assertEqual(candidate.issue_number, 101)
        self.assertEqual(candidate.pr_number, 202)
        self.assertEqual(candidate.recommendation, "auto_close_recommended")

    def test_branch_plus_issue_reference_can_be_medium_or_high(self) -> None:
        report = self.module.build_close_candidates_report(
            "BinoidCBD/universal-child-theme-oct-2024",
            "development",
            [
                {
                    "number": 761,
                    "title": 'Out of stock product should show "Sold Out" button',
                    "body": "Tracked in #766 after the production hotfix was merged.",
                    "html_url": "https://example.com/issues/761",
                }
            ],
            [
                {
                    "number": 766,
                    "title": "Use variation.is_in_stock for sold out button state",
                    "body": "Production hotfix for sold out button state.",
                    "headRefName": "hotfix/761-Out-of-Stock-product-showing-disabled-Add-to-Cart",
                    "baseRefName": "main",
                    "mergedAt": "2026-04-15T06:45:15Z",
                    "html_url": "https://example.com/pull/766",
                }
            ],
        )

        self.assertEqual(report.counts["high_confidence"], 1)
        candidate = report.high_confidence[0]
        self.assertEqual(candidate.issue_number, 761)
        self.assertEqual(candidate.pr_number, 766)
        self.assertEqual(candidate.recommendation, "close_recommended")


if __name__ == "__main__":
    unittest.main()
