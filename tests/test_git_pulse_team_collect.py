"""Unit tests for team-collect pure helpers (no network)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1] / "experimental" / "git-pulse"
)
SCRIPT_PATH = SCRIPT_DIR / "team-collect.py"


def _load_module():
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("team_collect", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["team_collect"] = module
    spec.loader.exec_module(module)
    return module


team_collect = _load_module()


class SanitizeTsvTests(unittest.TestCase):
    def test_strips_tabs_newlines_and_carriage_returns(self) -> None:
        self.assertEqual(
            team_collect.sanitize_tsv("a\tb\nc\rd"),
            "a b c d",
        )

    def test_preserves_regular_text(self) -> None:
        self.assertEqual(
            team_collect.sanitize_tsv("feat: add thing"),
            "feat: add thing",
        )


class ParseLinkNextTests(unittest.TestCase):
    def test_returns_next_url(self) -> None:
        header = (
            '<https://api.github.com/x?page=2>; rel="next", '
            '<https://api.github.com/x?page=5>; rel="last"'
        )
        self.assertEqual(
            team_collect.parse_link_next(header),
            "https://api.github.com/x?page=2",
        )

    def test_returns_none_when_no_next(self) -> None:
        header = '<https://api.github.com/x?page=5>; rel="last"'
        self.assertIsNone(team_collect.parse_link_next(header))

    def test_handles_empty_header(self) -> None:
        self.assertIsNone(team_collect.parse_link_next(""))


class ResolveSinceTests(unittest.TestCase):
    def test_default_is_about_30_days_ago(self) -> None:
        result = team_collect.resolve_since(None)
        expected_rough = datetime.now(timezone.utc) - timedelta(days=30)
        self.assertLess(abs((result - expected_rough).total_seconds()), 60)

    def test_parses_explicit_date(self) -> None:
        result = team_collect.resolve_since("2026-04-01")
        self.assertEqual(
            result,
            datetime(2026, 4, 1, tzinfo=timezone.utc),
        )

    def test_rejects_bad_format(self) -> None:
        with self.assertRaises(SystemExit):
            team_collect.resolve_since("04/01/2026")


class TeamRowSerializationTests(unittest.TestCase):
    def test_to_tsv_matches_header_order(self) -> None:
        row = team_collect.TeamRow(
            local_day="2026-04-20",
            local_time="14:30 PDT",
            utc_time="2026-04-20T21:30:00Z",
            author_login="octocat",
            author_name="The Octocat",
            repo="octo/hello-world",
            branch="(default)",
            short_sha="abc1234",
            subject="feat: add widget",
            kind="commit",
            pr_number="",
        )
        fields = row.to_tsv().split("\t")
        self.assertEqual(len(fields), len(team_collect.HEADER))
        self.assertEqual(fields[0], "2026-04-20")
        self.assertEqual(fields[3], "octocat")
        self.assertEqual(fields[5], "octo/hello-world")
        self.assertEqual(fields[8], "feat: add widget")
        self.assertEqual(fields[9], "commit")


class ResolveTokenTests(unittest.TestCase):
    def test_errors_when_no_source_provided(self) -> None:
        import os

        original = {
            key: os.environ.pop(key, None)
            for key in ("GITHUB_TOKEN", "GH_TOKEN")
        }
        try:
            with self.assertRaises(SystemExit):
                team_collect.resolve_token(None)
        finally:
            for key, value in original.items():
                if value is not None:
                    os.environ[key] = value

    def test_accepts_cli_token(self) -> None:
        self.assertEqual(
            team_collect.resolve_token("ghp_abc"),
            "ghp_abc",
        )


if __name__ == "__main__":
    unittest.main()
