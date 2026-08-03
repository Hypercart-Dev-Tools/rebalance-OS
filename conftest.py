"""Root conftest — worktree import isolation (GH-170).

A linked git worktree has .git as a FILE containing a "gitdir:" pointer;
the main checkout has .git as a DIRECTORY.  The editable install registered
from the main checkout's .pth file adds the main checkout's src/ to sys.path.
When pytest runs inside a worktree that same .pth entry wins, silently importing
the main checkout's code instead of the worktree's local changes — a green suite
in a worktree proves nothing about what was actually edited.

Inserting the worktree's own src/ at sys.path[0] before any test file is
imported fixes the shadowing.  The main-checkout case is unchanged (.git is a
directory, so the early-return fires).

Manual regression repro
-----------------------
  git worktree add /tmp/wt-regression development
  cd /tmp/wt-regression
  # Patch any exported symbol in src/rebalance/, e.g.:
  #   echo '__WORKTREE_SENTINEL__ = "wt-only"' >> src/rebalance/__init__.py
  .venv/bin/python -m pytest tests/ -q
  # Confirm import sees __WORKTREE_SENTINEL__.
  # In the main checkout, the same import must NOT see it.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _worktree_src_fixup() -> None:
    """Prepend this worktree's src/ to sys.path when running inside a linked worktree."""
    here = Path(__file__).parent
    git_marker = here / ".git"
    if not git_marker.is_file():
        return  # main checkout: .git is a directory — nothing to do

    src = here / "src"
    if not src.is_dir():
        return

    src_str = str(src)
    if sys.path and sys.path[0] == src_str:
        return  # already at position 0 — idempotent

    try:
        sys.path.remove(src_str)
    except ValueError:
        pass
    sys.path.insert(0, src_str)


_worktree_src_fixup()
