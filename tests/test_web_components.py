"""Tests for the shared web button helper (rebalance.web_components)."""
from __future__ import annotations

import unittest

from rebalance.web_components import RB_BUTTON_CSS, button_link


class ButtonLinkTests(unittest.TestCase):
    def test_renders_label_href_and_arrow(self) -> None:
        out = button_link("Open", "vscode://file/x")
        self.assertIn('class="rb-btn"', out)
        self.assertIn('href="vscode://file/x"', out)
        self.assertIn("Open", out)
        self.assertIn("↗", out)                                  # the standard affordance
        self.assertIn('class="rb-btn-arrow"', out)

    def test_external_adds_new_tab_rel(self) -> None:
        out = button_link("Open in Gmail", "https://mail.google.com", external=True)
        self.assertIn('target="_blank"', out)
        self.assertIn('rel="noopener noreferrer"', out)

    def test_internal_has_no_target(self) -> None:
        self.assertNotIn("target=", button_link("Refresh", "/focus-5"))

    def test_arrow_can_be_suppressed(self) -> None:
        self.assertNotIn("↗", button_link("Plain", "/x", arrow=False))

    def test_extra_class_is_appended(self) -> None:
        self.assertIn('class="rb-btn hero-open"',
                      button_link("Open in Obsidian", "obsidian://x", cls="hero-open"))

    def test_title_and_values_are_escaped(self) -> None:
        out = button_link('a"b', 'https://x/?q="&z', title='t"<>')
        self.assertNotIn('q="&z"', out)            # href quote/amp escaped
        self.assertIn("&amp;", out)
        self.assertIn("&quot;", out)               # the quote in label/href/title
        self.assertNotIn("<>", out)                # title angle brackets escaped

    def test_css_targets_the_class_and_themes_via_accent(self) -> None:
        self.assertIn(".rb-btn", RB_BUTTON_CSS)
        self.assertIn("var(--accent", RB_BUTTON_CSS)  # falls back to app blue off-theme


if __name__ == "__main__":
    unittest.main()
