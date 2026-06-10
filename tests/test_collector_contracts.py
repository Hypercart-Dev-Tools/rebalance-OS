"""Executable contract tests for the collector / write-path architecture.

These encode the decisions locked in
``PROJECT/2-WORKING/COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md`` and replace the
manual smell rows in ``DASHBOARD.md`` with guards that fail CI when the
architecture drifts (the prior "single writer per contract" / "one pipeline"
prose in AGENTS.md drifted precisely because nothing ran it).

Target-state contracts the refactor has not yet reached are marked ``xfail``
with the owning phase. They will report XPASS once that phase lands — at which
point the ``xfail`` marker should be removed so the contract is enforced strictly.

Row references are to DASHBOARD.md's compliance matrix.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rebalance"
INDEX_OPS = SRC / "ingest" / "index_ops.py"

# Decision A: the only scopes `all` should expand to are raw incoming sources.
RAW_SOURCES = {"vault", "github", "calendar", "sleuth", "email"}

# Leaf ingest functions that user-facing surfaces (CLI/MCP/web) must not call
# directly — they route through the orchestrator (`refresh_index`) instead.
LEAF_INGEST_FNS = {
    "sync_calendar", "sync_sleuth_reminders", "sync_gmail", "ingest_email_messages",
    "scan_github", "upsert_github_activity", "sync_github_repo", "embed_github_documents",
    "ingest_vault", "embed_chunks", "backfill_semantic_documents", "embed_pending",
    "sync_figma_comments",
}


def _imported_names(path: Path) -> set[str]:
    """Names brought into scope by ``import`` / ``from ... import`` (incl. local imports)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name.split(".")[-1] for a in node.names)
    return names


# --- DASHBOARD row 3 (YAGNI) — RESOLVED, guarded green ------------------------
def test_github_activity_and_commits_are_distinct_not_redundant():
    """github_activity (per-(login,repo,scan_date) scan snapshot) and github_commits
    (granular per-commit, keyed by committed_at) are intentionally distinct, not
    redundant. Resolved 2026-06-10; guard that the schema keeps both shapes."""
    schema = (SRC / "ingest" / "db" / "schema.py").read_text(encoding="utf-8")
    assert "github_activity" in schema
    assert "scan_date" in schema      # activity = scan-date snapshot
    assert "committed_at" in schema   # commits = real commit time


# --- Decision A / Phase 1 — `all` = raw sources only --------------------------
@pytest.mark.xfail(
    reason="Phase 1: `all` not yet narrowed to raw sources (still includes code/semantic/sync)",
    strict=False,
)
def test_all_expands_to_raw_sources_only():
    from rebalance.ingest.index_ops import _all_scope_names
    assert set(_all_scope_names()) == RAW_SOURCES


# --- Decision B / Phase 3 — semantic projection is single-writer (stage-owned) -
@pytest.mark.xfail(
    reason="Phase 3: semantic projection not yet stage-owned (multiple backfill call sites)",
    strict=False,
)
def test_semantic_projection_is_single_writer():
    """Only the `semantic` stage may project/embed into the semantic tables."""
    src = INDEX_OPS.read_text(encoding="utf-8")
    assert src.count("backfill_semantic_documents(") == 1
    assert src.count("embed_pending(") == 1


# --- DASHBOARD row 8 (SOLID/OCP) / Phase 2 — no leaf-ingest bypasses ----------
@pytest.mark.xfail(
    reason="Phase 2: CLI/MCP write surfaces still call leaf ingest fns directly",
    strict=False,
)
def test_user_surfaces_do_not_import_leaf_ingest_functions():
    surfaces = list((SRC / "cli").rglob("*.py")) + list((SRC / "mcp" / "tools").rglob("*.py"))
    offenders = {}
    for path in surfaces:
        bad = _imported_names(path) & LEAF_INGEST_FNS
        if bad:
            offenders[str(path.relative_to(REPO_ROOT))] = sorted(bad)
    assert not offenders, f"user-facing surfaces import leaf ingest fns directly: {offenders}"
