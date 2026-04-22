#!/usr/bin/env python3
"""Emit a scoped slice of a git-pulse recap for a given section.

Agents filling TLDR / FOCUS / OBSERVATIONS tend to drift toward listing
commit specifics when shown the full recap — the Appendix is full of SHAs
and subject lines. This CLI extracts only the context each section
actually needs, so the agent sees shape (bucket counts, tables) rather
than specifics (commit bullets, subject text).

Examples:

    git-pulse-scope recap.md --section tldr
        → just the ## Summary block

    git-pulse-scope recap.md --section focus --repo rebalance-OS
        → that repo's ### header + stats bullets + Commit-themes bucket
          headers. The individual commit bullets under each bucket are
          stripped so the agent knows feat/fix/docs/etc. counts but not
          the specific commits.

    git-pulse-scope recap.md --section observations
        → the Coverage, Cross-Machine Repos, Daily Activity, and
          Exceptions tables from the Appendix. Recent Activity is
          deliberately excluded (too commit-specific).

Agent-agnostic. The skill rulebook still governs voice — this just trims
the document context so the agent's input isn't laden with commit noise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


SUMMARY_BLOCK_RE = re.compile(
    r"(## Summary\b.*?)(?=\n## [^#])",
    re.DOTALL,
)

# Matches an individual commit bullet: 2+ leading spaces, then "-".
COMMIT_BULLET_RE = re.compile(r"^\s{2,}-")


OBSERVATIONS_TABLES = (
    "Coverage",
    "Cross-Machine Repos",
    "Daily Activity",
    "Exceptions",
)


def extract_summary_block(text: str) -> str:
    m = SUMMARY_BLOCK_RE.search(text)
    return m.group(1).strip() if m else ""


def extract_repo_block(text: str, repo: str) -> str:
    r"""Return the ``### `<repo>` — ...`` block up to the next ### or ##
    heading (whichever comes first)."""
    pattern = (
        rf"(### `{re.escape(repo)}` — .*?)"
        rf"(?=\n### |\n## [^#]|\Z)"
    )
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def strip_commit_bullets(block: str) -> str:
    """Drop indented commit-bullet lines. Keeps the bucket-header bullets
    like `- **feat (8):**` intact so bucket shape is visible without the
    commit specifics."""
    kept: list[str] = []
    for line in block.split("\n"):
        if COMMIT_BULLET_RE.match(line):
            continue
        kept.append(line)
    # Collapse any trailing blank lines we may have produced
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept)


def extract_appendix_section(text: str, heading: str) -> str:
    """Return `### <heading>` section up to the next ### or ## heading."""
    pattern = (
        rf"(### {re.escape(heading)}\b.*?)"
        rf"(?=\n### |\n## [^#]|\Z)"
    )
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def scope_tldr(text: str) -> str:
    return extract_summary_block(text)


def scope_focus(text: str, repo: str) -> str:
    block = extract_repo_block(text, repo)
    if not block:
        return ""
    return strip_commit_bullets(block)


def scope_observations(text: str) -> str:
    pieces: list[str] = []
    for table in OBSERVATIONS_TABLES:
        piece = extract_appendix_section(text, table)
        if piece:
            pieces.append(piece)
    return "\n\n".join(pieces)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Emit a scoped slice of a git-pulse recap so an agent sees only "
            "the context its section actually needs."
        )
    )
    parser.add_argument(
        "recap",
        help="Path to the recap markdown file.",
    )
    parser.add_argument(
        "--section",
        required=True,
        choices=["tldr", "focus", "observations"],
        help="Which section's context to emit.",
    )
    parser.add_argument(
        "--repo",
        metavar="NAME",
        help="Repo name (required for --section focus).",
    )
    args = parser.parse_args()

    path = Path(args.recap).expanduser()
    if not path.is_file():
        print(f"recap not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text()

    if args.section == "tldr":
        output = scope_tldr(text)
    elif args.section == "focus":
        if not args.repo:
            print(
                "--section focus requires --repo <name>",
                file=sys.stderr,
            )
            return 2
        output = scope_focus(text, args.repo)
    else:
        output = scope_observations(text)

    if not output:
        print(
            f"No content found for --section {args.section}"
            + (f" --repo {args.repo}" if args.repo else ""),
            file=sys.stderr,
        )
        return 2

    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
