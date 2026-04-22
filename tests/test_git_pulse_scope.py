"""Unit tests for the git-pulse scope helper."""

from __future__ import annotations

import importlib.util
import sys
import textwrap
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1] / "experimental" / "git-pulse"
)


def _load():
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "scope", SCRIPT_DIR / "scope.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["scope"] = module
    spec.loader.exec_module(module)
    return module


scope = _load()


RECAP_FIXTURE = textwrap.dedent(
    """\
    # Git Pulse Executive Recap

    ## Summary
    - Generated at: `2026-04-22T00:00:00Z`
    - Window: `2026-04-01` to `2026-04-20` (11 active days)
    - Repos covered: repo-one | repo-two
    - Commits: 50 across 2 repos from 2 machines

    <!-- TLDR: placeholder -->

    ## By Repo

    ### `repo-one` — 40 commits · 2 machines · 2026-04-01 to 2026-04-20

    - **Machines:** Alpha Mac (25), Beta Mac (15)
    - **Branches:** `main`
    - **Active days:** 10

    <!-- FOCUS: placeholder -->

    **Commit themes:**
    - **feat (8):**
      - 2026-04-20 · `abc1234` · feat: add widget
      - 2026-04-19 · `def5678` · feat: improve thing
    - **fix (5):**
      - 2026-04-18 · `111aaaa` · fix: handle edge case
    - **docs (3):**
      - 2026-04-17 · `222bbbb` · docs: update README

    ### `repo-two` — 10 commits · 1 machine · 2026-04-15 to 2026-04-20

    - **Machines:** Alpha Mac (10)
    - **Branches:** `main`
    - **Active days:** 4

    <!-- FOCUS: placeholder -->

    **Commit themes:**
    - **chore (10):**
      - 2026-04-20 · `333cccc` · chore: bump deps

    ## Observations

    <!-- OBSERVATIONS: placeholder -->

    ## Appendix

    ### Source Reports
    - /tmp/fake.tsv

    ### Coverage
    | Device | Commits |
    |---|---:|
    | Alpha Mac | 35 |
    | Beta Mac | 15 |

    ### Machines Table
    | Device | Commits |
    |---|---:|
    | Alpha Mac | 35 |

    ### Repos Table
    | Repo | Commits |
    |---|---:|
    | repo-one | 40 |
    | repo-two | 10 |

    ### Cross-Machine Repos
    | Repo | Machines |
    |---|---:|
    | repo-one | 2 |

    ### Daily Activity
    | Local Day | Commits |
    |---|---:|
    | 2026-04-20 | 5 |

    ### Recent Activity
    | Local Day | SHA | Subject |
    |---|---|---|
    | 2026-04-20 | abc1234 | feat: add widget |

    ### Exceptions
    - Raw rows: 50
    - Unique rows: 50
    """
)


class ScopeTldrTests(unittest.TestCase):
    def test_returns_summary_block(self) -> None:
        result = scope.scope_tldr(RECAP_FIXTURE)
        self.assertIn("## Summary", result)
        self.assertIn("Repos covered", result)
        self.assertIn("<!-- TLDR:", result)
        # Must NOT leak the By Repo section
        self.assertNotIn("## By Repo", result)
        self.assertNotIn("**Commit themes", result)
        self.assertNotIn("abc1234", result)


class ScopeFocusTests(unittest.TestCase):
    def test_returns_repo_block_with_bucket_headers_but_no_commit_bullets(
        self,
    ) -> None:
        result = scope.scope_focus(RECAP_FIXTURE, "repo-one")
        # Repo header + stats present
        self.assertIn("### `repo-one`", result)
        self.assertIn("**Active days:** 10", result)
        # Bucket headers present
        self.assertIn("**feat (8):**", result)
        self.assertIn("**fix (5):**", result)
        self.assertIn("**docs (3):**", result)
        # Commit bullets stripped
        self.assertNotIn("abc1234", result)
        self.assertNotIn("def5678", result)
        self.assertNotIn("111aaaa", result)
        self.assertNotIn("222bbbb", result)
        # Must NOT leak the other repo's block
        self.assertNotIn("repo-two", result)

    def test_returns_empty_for_missing_repo(self) -> None:
        self.assertEqual(scope.scope_focus(RECAP_FIXTURE, "nonexistent"), "")


class ScopeObservationsTests(unittest.TestCase):
    def test_returns_four_appendix_tables(self) -> None:
        result = scope.scope_observations(RECAP_FIXTURE)
        self.assertIn("### Coverage", result)
        self.assertIn("### Cross-Machine Repos", result)
        self.assertIn("### Daily Activity", result)
        self.assertIn("### Exceptions", result)

    def test_excludes_recent_activity_and_repos_tables(self) -> None:
        result = scope.scope_observations(RECAP_FIXTURE)
        self.assertNotIn("### Recent Activity", result)
        self.assertNotIn("### Machines Table", result)
        self.assertNotIn("### Repos Table", result)
        # Scrubs individual SHAs from the recent-activity table
        self.assertNotIn("abc1234", result)


class StripCommitBulletsTests(unittest.TestCase):
    def test_keeps_bucket_headers_and_removes_indented_bullets(self) -> None:
        block = textwrap.dedent(
            """\
            **Commit themes:**
            - **feat (3):**
              - 2026-04-20 · `abc1234` · feat: x
              - 2026-04-19 · `def5678` · feat: y
            - **fix (1):**
              - 2026-04-18 · `111aaaa` · fix: z
            """
        )
        result = scope.strip_commit_bullets(block)
        self.assertIn("- **feat (3):**", result)
        self.assertIn("- **fix (1):**", result)
        self.assertNotIn("abc1234", result)
        self.assertNotIn("def5678", result)
        self.assertNotIn("111aaaa", result)


if __name__ == "__main__":
    unittest.main()
