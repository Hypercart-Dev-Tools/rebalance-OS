"""Local git checkout discovery (Phase 6.1).

The git-pulse local scanner promoted from ``experimental/git-pulse/`` into
the candidate pipeline: walk operator-configured roots for git checkouts,
resolve their GitHub identity from the origin remote, and measure unpushed
work. Two consumers:

- ``discover_candidates`` (preflight) — local checkouts whose GitHub repo is
  not already a candidate/registered project surface as candidates with
  ``provenance="local-scan"`` ("we found these repos on disk — promote
  them?").
- the doctor's unpushed-work check — commits sitting on a local branch that
  never reached the remote are an ongoing signal, not a one-time onboarding
  check.

Roots come from the ``local_repo_roots`` config key (list of folders, e.g.
``["~/Documents/GH Repos"]``). No roots configured = scanning is off; every
consumer treats that as an empty result, never an error. Read-only: this
module runs ``git`` queries only, never mutates repos or registry state.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from rebalance.lib.git_ops import _git

GITHUB_REMOTE_MARKERS = ("github.com:", "github.com/")

_FULL_NAME_RE = re.compile(
    r"github\.com[:/](?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


@dataclass(frozen=True)
class LocalRepo:
    path: Path
    origin_url: str
    full_name: str | None  # owner/repo when origin is GitHub, else None
    branch: str
    # Commits on HEAD not on its upstream. None = no upstream configured
    # (which is itself unpushed work — nothing on the remote tracks it).
    unpushed_commits: int | None


def parse_github_full_name(origin_url: str) -> str | None:
    """``owner/repo`` from an SSH or HTTPS GitHub remote URL, else None."""
    match = _FULL_NAME_RE.search(origin_url or "")
    return f"{match.group('owner')}/{match.group('repo')}" if match else None


def walk_repo_candidates(root: Path, max_depth: int = 2) -> list[Path]:
    """Find git checkouts under *root* (same walk the git-pulse scanner uses:
    stop descending at a ``.git`` dir, skip dot-dirs, bounded depth)."""
    if not root.exists() or not root.is_dir():
        return []

    candidates: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        if (current / ".git").is_dir():
            candidates.append(current)
            continue
        if depth >= max_depth:
            continue
        try:
            children = sorted(
                child for child in current.iterdir()
                if child.is_dir() and not child.name.startswith(".")
            )
        except OSError:
            continue
        for child in reversed(children):
            stack.append((child, depth + 1))
    return candidates


def inspect_repo(repo_path: Path) -> LocalRepo:
    origin = _git(repo_path, "remote", "get-url", "origin") or ""
    branch = _git(repo_path, "rev-parse", "--abbrev-ref", "HEAD") or ""
    ahead = _git(repo_path, "rev-list", "--count", "@{upstream}..HEAD")
    return LocalRepo(
        path=repo_path,
        origin_url=origin,
        full_name=parse_github_full_name(origin),
        branch=branch,
        unpushed_commits=int(ahead) if ahead is not None and ahead.isdigit() else None,
    )


def scan_local_repos(
    roots: list[str] | None = None,
    *,
    max_depth: int = 2,
    github_only: bool = True,
) -> list[LocalRepo]:
    """Scan *roots* (default: the ``local_repo_roots`` config key) and return
    inspected checkouts, sorted by path. Empty roots → empty list."""
    if roots is None:
        from rebalance.ingest.config import get_local_repo_roots

        roots = get_local_repo_roots()
    if not roots:
        return []

    seen: set[Path] = set()
    repos: list[LocalRepo] = []
    for root in roots:
        for path in walk_repo_candidates(Path(root).expanduser(), max_depth):
            if path in seen:
                continue
            seen.add(path)
            repo = inspect_repo(path)
            if github_only and repo.full_name is None:
                continue
            repos.append(repo)
    return sorted(repos, key=lambda r: str(r.path).lower())


def unpushed_work(repos: list[LocalRepo] | None = None) -> list[LocalRepo]:
    """Repos carrying unpushed work: commits ahead of upstream, or a NAMED
    branch with no upstream at all. Detached HEADs are excluded — they can't
    have an upstream by definition, so flagging them is noise, not signal
    (review finding). The ongoing doctor/pulse signal."""
    if repos is None:
        repos = scan_local_repos()
    return [
        r for r in repos
        if (r.unpushed_commits or 0) > 0
        or (r.unpushed_commits is None and r.branch not in ("", "HEAD"))
    ]
