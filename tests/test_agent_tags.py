"""Unit tests for the activity-source classifier."""

from __future__ import annotations

import unittest

from rebalance.ingest.agent_tags import classify


class AgentTagsTests(unittest.TestCase):
    def test_claude_branch_pattern(self) -> None:
        self.assertEqual(
            classify(branch="claude/monitor-github-vscode-activity-nAeik",
                     author_login="noelsaw"),
            "claude-cloud",
        )

    def test_codex_branch_pattern(self) -> None:
        self.assertEqual(
            classify(branch="codex/refactor-foo", author_login="noelsaw"),
            "codex-cloud",
        )

    def test_codex_bot_author(self) -> None:
        self.assertEqual(
            classify(branch="main", author_login="chatgpt-codex-connector[bot]"),
            "codex-cloud",
        )

    def test_lovable_bot_author(self) -> None:
        self.assertEqual(
            classify(branch="main", author_login="lovable-dev[bot]"),
            "lovable",
        )

    def test_lovable_branch_prefix(self) -> None:
        self.assertEqual(
            classify(branch="lovable-update-readme", author_login="noelsaw"),
            "lovable",
        )

    def test_local_vscode_via_marker(self) -> None:
        msg = "wip: refactor handler\n\n[git-pulse:device=mac-studio]"
        self.assertEqual(
            classify(branch="feature/foo", author_login="noelsaw",
                     commit_message=msg),
            "local-vscode",
        )

    def test_claude_via_co_author_trailer(self) -> None:
        msg = "Fix bug\n\nCo-authored-by: Claude <noreply@anthropic.com>"
        self.assertEqual(
            classify(branch="main", author_login="noelsaw", commit_message=msg),
            "claude-cloud",
        )

    def test_human_default(self) -> None:
        self.assertEqual(
            classify(branch="main", author_login="noelsaw",
                     commit_message="chore: bump deps"),
            "human",
        )

    def test_lovable_takes_precedence_over_codex_branch(self) -> None:
        # Author is the lovable bot — that should win even if branch
        # incidentally starts with codex/.
        self.assertEqual(
            classify(branch="codex/auto", author_login="lovable[bot]"),
            "lovable",
        )

    def test_empty_inputs_return_human(self) -> None:
        self.assertEqual(classify(), "human")
        self.assertEqual(classify(branch="", author_login=None), "human")


if __name__ == "__main__":
    unittest.main()
