"""Unit tests for the git-pulse recap validator."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1] / "experimental" / "git-pulse"
)


def _load():
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "validators", SCRIPT_DIR / "validators.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["validators"] = module
    spec.loader.exec_module(module)
    return module


validators = _load()


class CheckShaTokensTests(unittest.TestCase):
    def test_passes_on_clean_prose(self) -> None:
        self.assertEqual(
            validators.check_sha_tokens(
                "A two-front fortnight anchored on rebalance-OS."
            ),
            [],
        )

    def test_flags_short_sha(self) -> None:
        result = validators.check_sha_tokens(
            "Merged abc1234 to close out the calendar rewrite."
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rule, "sha_token")
        self.assertEqual(result[0].fragment, "abc1234")

    def test_skips_sha_inside_backticks(self) -> None:
        # The backtick rule covers this; the SHA rule skips so violations
        # aren't double-counted.
        result = validators.check_sha_tokens(
            "Merged `abc1234` to close the calendar rewrite."
        )
        self.assertEqual(result, [])


class CheckBackticksWrapShaOrFilenameTests(unittest.TestCase):
    def test_passes_on_repo_name_in_backticks(self) -> None:
        # Skill explicitly uses repo names in backticks — must not flag.
        self.assertEqual(
            validators.check_backticks_wrap_sha_or_filename(
                "`repo-one` was the center of gravity."
            ),
            [],
        )

    def test_flags_sha_in_backticks(self) -> None:
        result = validators.check_backticks_wrap_sha_or_filename(
            "Noel merged `abc1234` late Friday."
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rule, "backtick_sha")

    def test_flags_filename_in_backticks(self) -> None:
        result = validators.check_backticks_wrap_sha_or_filename(
            "A sustained pass on `GOOGLE_CALENDAR.md` closed out the week."
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rule, "backtick_filename")


class CheckConvCommitPrefixTests(unittest.TestCase):
    def test_passes_on_theme_language(self) -> None:
        self.assertEqual(
            validators.check_conv_commit_prefix(
                "A hardening pass followed the feature burst."
            ),
            [],
        )

    def test_flags_prefix_with_colon(self) -> None:
        result = validators.check_conv_commit_prefix(
            "Landed feat: add widget on Tuesday."
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rule, "conv_commit_prefix")


class CheckFilenameTokenTests(unittest.TestCase):
    def test_passes_on_subsystem_reference(self) -> None:
        self.assertEqual(
            validators.check_filename_token(
                "The calendar docs got a sustained rewrite."
            ),
            [],
        )

    def test_flags_bare_filename(self) -> None:
        result = validators.check_filename_token(
            "The GOOGLE_CALENDAR.md rewrite closed the week."
        )
        self.assertTrue(any(v.rule == "filename" for v in result))


class CheckIsoDateTests(unittest.TestCase):
    def test_passes_on_human_readable_date(self) -> None:
        self.assertEqual(
            validators.check_iso_date(
                "Three quiet days mid-window (April 13, 18, and 19)."
            ),
            [],
        )

    def test_flags_iso_date(self) -> None:
        result = validators.check_iso_date(
            "Activity peaked on 2026-04-07 then tailed off."
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rule, "iso_date")


class CheckTldrLengthTests(unittest.TestCase):
    def test_passes_at_two_sentences(self) -> None:
        self.assertEqual(
            validators.check_tldr_length(
                "A two-front week. The WordPress repo stayed quiet."
            ),
            [],
        )

    def test_flags_three_sentences(self) -> None:
        result = validators.check_tldr_length(
            "One sentence. Two sentence. Three sentence."
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rule, "tldr_length")


class CheckFocusLengthTests(unittest.TestCase):
    def test_passes_at_three_sentences(self) -> None:
        text = "First observation. Second observation. Third observation."
        self.assertEqual(validators.check_focus_length(text), [])

    def test_flags_four_sentences(self) -> None:
        text = "One. Two. Three. Four."
        result = validators.check_focus_length(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rule, "focus_length")


class CheckObservationsLengthTests(unittest.TestCase):
    def test_passes_at_five_bullets(self) -> None:
        text = "\n".join(f"- bullet {i}." for i in range(1, 6))
        self.assertEqual(validators.check_observations_length(text), [])

    def test_flags_six_bullets(self) -> None:
        text = "\n".join(f"- bullet {i}." for i in range(1, 7))
        result = validators.check_observations_length(text)
        self.assertTrue(any(v.rule == "observations_bullets" for v in result))

    def test_flags_over_long_bullet(self) -> None:
        text = "- A long observation. Second sentence here. Third sentence."
        result = validators.check_observations_length(text)
        self.assertTrue(
            any(v.rule == "observations_bullet_length" for v in result)
        )


class ValidateSectionTests(unittest.TestCase):
    def test_disabled_rule_is_skipped(self) -> None:
        text = "Merged abc1234 to close the week."
        result_default = validators.validate_section(text, "tldr")
        self.assertTrue(any(v.rule == "sha_token" for v in result_default))

        result_disabled = validators.validate_section(
            text, "tldr", disabled_rules={"sha_token"}
        )
        self.assertFalse(any(v.rule == "sha_token" for v in result_disabled))


class ExtractSectionsTests(unittest.TestCase):
    def test_extracts_filled_tldr_and_focus_and_observations(self) -> None:
        recap = (
            "## Summary\n"
            "- Generated at: `2026-04-22T00:00:00Z`\n"
            "- Window: `2026-04-01` to `2026-04-20` (11 active days)\n"
            "\n"
            "The window split in two.\n"
            "\n"
            "## By Repo\n"
            "\n"
            "### `repo-one` — 40 commits · 3 machines · 2026-04-01 to 2026-04-20\n"
            "\n"
            "- **Machines:** Alpha (10)\n"
            "- **Branches:** `main`\n"
            "- **Active days:** 7\n"
            "\n"
            "repo-one was the center of gravity.\n"
            "\n"
            "**Commit themes:**\n"
            "\n"
            "## Observations\n"
            "\n"
            "- One observation about bus factor.\n"
            "\n"
            "## Appendix\n"
        )
        result = validators.extract_sections(recap)
        self.assertEqual(len(result["tldr"]), 1)
        self.assertIn("split in two", result["tldr"][0][1])
        self.assertEqual(len(result["focus"]), 1)
        self.assertEqual(result["focus"][0][0], "FOCUS:repo-one")
        self.assertEqual(len(result["observations"]), 1)

    def test_skips_placeholder_sections(self) -> None:
        recap = (
            "## Summary\n"
            "- Generated at: `2026-04-22T00:00:00Z`\n"
            "\n"
            "<!-- TLDR: Write 1-2 sentences... -->\n"
            "\n"
            "## By Repo\n"
            "\n"
            "## Observations\n"
            "\n"
            "<!-- OBSERVATIONS: 3-5 bullets... -->\n"
            "\n"
            "## Appendix\n"
        )
        result = validators.extract_sections(recap)
        self.assertEqual(result["tldr"], [])
        self.assertEqual(result["observations"], [])


if __name__ == "__main__":
    unittest.main()
