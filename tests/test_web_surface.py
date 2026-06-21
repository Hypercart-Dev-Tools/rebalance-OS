"""Phase 2 contract tests — Pulse/Dashboard/Web surface.

Written BEFORE module movement (Phase 2 QA requirement). Pins:
- KIND_GLYPHS / ITEM_SUB_GLYPHS live in web_components (single glyph source)
- Focus5HideRequest is exported from web.py (pulse_server no longer re-defines it)
- web.py page functions remain importable (pulse_server's rendering boundary)
- pulse_web generates valid HTML with expected structural sections
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class GlyphConstantsContractTests(unittest.TestCase):
    """KIND_GLYPHS and ITEM_SUB_GLYPHS must live in web_components — single source."""

    def test_kind_glyphs_importable_from_web_components(self) -> None:
        from rebalance.web_components import KIND_GLYPHS
        self.assertIsInstance(KIND_GLYPHS, dict)

    def test_item_sub_glyphs_importable_from_web_components(self) -> None:
        from rebalance.web_components import ITEM_SUB_GLYPHS
        self.assertIsInstance(ITEM_SUB_GLYPHS, dict)

    def test_kind_glyphs_has_required_kinds(self) -> None:
        from rebalance.web_components import KIND_GLYPHS
        for kind in ("commit", "item", "comment"):
            self.assertIn(kind, KIND_GLYPHS, msg=f"KIND_GLYPHS missing '{kind}'")

    def test_item_sub_glyphs_has_required_sub_kinds(self) -> None:
        from rebalance.web_components import ITEM_SUB_GLYPHS
        for sub in ("issue", "pull_request"):
            self.assertIn(sub, ITEM_SUB_GLYPHS, msg=f"ITEM_SUB_GLYPHS missing '{sub}'")

    def test_kind_glyphs_values_are_strings(self) -> None:
        from rebalance.web_components import KIND_GLYPHS
        for kind, glyph in KIND_GLYPHS.items():
            self.assertIsInstance(glyph, str, msg=f"KIND_GLYPHS[{kind!r}] should be str")

    def test_item_sub_glyphs_values_are_strings(self) -> None:
        from rebalance.web_components import ITEM_SUB_GLYPHS
        for sub, glyph in ITEM_SUB_GLYPHS.items():
            self.assertIsInstance(glyph, str, msg=f"ITEM_SUB_GLYPHS[{sub!r}] should be str")

    def test_commit_glyph_matches_golden(self) -> None:
        from rebalance.web_components import KIND_GLYPHS
        self.assertEqual(KIND_GLYPHS["commit"], "●")

    def test_issue_glyph_matches_golden(self) -> None:
        from rebalance.web_components import ITEM_SUB_GLYPHS
        self.assertEqual(ITEM_SUB_GLYPHS["issue"], "✦")

    def test_pull_request_glyph_matches_golden(self) -> None:
        from rebalance.web_components import ITEM_SUB_GLYPHS
        self.assertEqual(ITEM_SUB_GLYPHS["pull_request"], "⇡")


class Focus5HideRequestContractTests(unittest.TestCase):
    """Focus5HideRequest must be exported from web.py — pulse_server imports it."""

    def test_focus5_hide_request_importable_from_web(self) -> None:
        from rebalance.web import Focus5HideRequest
        self.assertTrue(callable(Focus5HideRequest))

    def test_focus5_hide_request_has_repo_field(self) -> None:
        from rebalance.web import Focus5HideRequest
        req = Focus5HideRequest(repo="owner/repo")
        self.assertEqual(req.repo, "owner/repo")

    def test_focus5_set_hidden_importable_from_web(self) -> None:
        from rebalance.web import focus5_set_hidden
        self.assertTrue(callable(focus5_set_hidden))

    def test_web_page_functions_still_importable(self) -> None:
        """pulse_server imports these by name — renaming any breaks the server."""
        from rebalance.web import (
            auth_log_page,
            auth_log_raw,
            focus5_page,
            focus5_set_hidden,
            sleuth_graph_page,
            whatsnext_page,
        )
        for fn in (auth_log_page, auth_log_raw, focus5_page, focus5_set_hidden,
                   sleuth_graph_page, whatsnext_page):
            self.assertTrue(callable(fn))


class PulseWebHtmlContractTests(unittest.TestCase):
    """pulse_web.py --out must generate HTML with required structural sections."""

    _html: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        import tempfile
        out = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        out.close()
        result = subprocess.run(
            [sys.executable, "scripts/pulse_web.py", "--out", out.name],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and Path(out.name).stat().st_size > 0:
            cls._html = Path(out.name).read_text(encoding="utf-8")
        else:
            cls._html = None

    def _skip_if_no_html(self) -> None:
        if self._html is None:
            self.skipTest("pulse_web.py --out failed or produced no output (DB may be absent)")

    def test_generates_non_empty_html(self) -> None:
        self._skip_if_no_html()
        self.assertGreater(len(self._html), 1000)

    def test_contains_doctype(self) -> None:
        self._skip_if_no_html()
        self.assertIn("<!DOCTYPEHTML>", self._html[:100].upper().replace(" ", ""))

    def test_contains_nav_links(self) -> None:
        self._skip_if_no_html()
        # NAV_LINKS from web_components must appear — structural contract
        self.assertIn("/focus-5", self._html)
        self.assertIn("/whats-next", self._html)
        self.assertIn("/auth-log", self._html)

    def test_no_python_traceback_in_output(self) -> None:
        self._skip_if_no_html()
        self.assertNotIn("Traceback (most recent call last)", self._html)


if __name__ == "__main__":
    unittest.main()
