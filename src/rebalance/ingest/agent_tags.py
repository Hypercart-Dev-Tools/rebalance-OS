"""
Classify a unit of GitHub activity by its likely originator.

Distinguishes between:
- ``claude-cloud`` — Claude Code cloud sessions (branch ``claude/*`` or
  Co-authored-by trailer naming Claude)
- ``codex-cloud`` — OpenAI Codex Cloud sessions (branch ``codex/*`` or the
  ``chatgpt-codex-connector[bot]`` author)
- ``lovable``     — Lovable UI editor (``lovable-dev[bot]`` / ``lovable[bot]``
  author, or branch starting with ``lovable-``)
- ``local-vscode``— Local VS Code agent sessions on user's Macs (commit
  message carries the git-pulse device marker injected by collect.sh)
- ``human``       — Anything else

Pure logic — no I/O, no database access. Easy to unit-test.
"""

from __future__ import annotations

import re
from typing import Iterable

LOVABLE_AUTHORS = {"lovable-dev[bot]", "lovable[bot]"}
CODEX_AUTHORS = {"chatgpt-codex-connector[bot]", "codex-bot[bot]"}
CLAUDE_AUTHORS = {"claude[bot]", "claude-bot[bot]"}

_DEVICE_MARKER_RE = re.compile(r"\[git-pulse:device=[A-Za-z0-9_.-]+\]")
_COAUTHOR_RE = re.compile(
    r"Co-authored-by:\s*([^<\n]+?)\s*<", re.IGNORECASE | re.MULTILINE
)


def _coauthor_names(message: str) -> list[str]:
    if not message:
        return []
    return [m.group(1).strip().lower() for m in _COAUTHOR_RE.finditer(message)]


def classify(
    *,
    branch: str | None = None,
    author_login: str | None = None,
    committer_login: str | None = None,
    commit_message: str | None = None,
    co_authors: Iterable[str] | None = None,
) -> str:
    """Return one of ``claude-cloud``, ``codex-cloud``, ``lovable``,
    ``local-vscode``, ``human``.
    """
    branch = (branch or "").strip()
    author = (author_login or "").strip()
    committer = (committer_login or "").strip()
    message = commit_message or ""

    explicit = [c.lower() for c in (co_authors or [])]
    parsed = _coauthor_names(message)
    coauthors = set(explicit) | set(parsed)

    if author in LOVABLE_AUTHORS or committer in LOVABLE_AUTHORS:
        return "lovable"
    if branch.startswith("lovable-") or branch.startswith("lovable/"):
        return "lovable"

    if author in CODEX_AUTHORS or committer in CODEX_AUTHORS:
        return "codex-cloud"
    if branch.startswith("codex/"):
        return "codex-cloud"

    if author in CLAUDE_AUTHORS or committer in CLAUDE_AUTHORS:
        return "claude-cloud"
    if branch.startswith("claude/"):
        return "claude-cloud"
    if any("claude" in name for name in coauthors):
        return "claude-cloud"

    if _DEVICE_MARKER_RE.search(message):
        return "local-vscode"

    return "human"


__all__ = ["classify"]
