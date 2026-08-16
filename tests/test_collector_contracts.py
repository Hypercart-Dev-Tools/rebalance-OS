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
from pathlib import Path


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


# --- Phase 1a — explicit collector taxonomy (`kind`) --------------------------
EXPECTED_KIND = {
    "vault": "raw_source", "github": "raw_source", "calendar": "raw_source",
    "sleuth": "raw_source", "email": "raw_source", "figma": "raw_source",
    "code": "derived_scan", "focus5": "derived_scan", "ask_self": "derived_scan",
    "semantic": "projection", "sync": "export",
}


def test_every_collector_has_valid_kind():
    from rebalance.ingest.index_ops import COLLECTORS, _COLLECTOR_KINDS
    for name, c in COLLECTORS.items():
        assert c.kind in _COLLECTOR_KINDS, f"{name} has invalid kind {c.kind!r}"


def test_known_collectors_are_classified_as_expected():
    from rebalance.ingest.index_ops import COLLECTORS
    for name, expected in EXPECTED_KIND.items():
        assert COLLECTORS[name].kind == expected, f"{name}: {COLLECTORS[name].kind!r} != {expected!r}"


def test_raw_source_membership_is_exactly_the_five():
    from rebalance.ingest.index_ops import _raw_source_scopes
    assert set(_raw_source_scopes()) == RAW_SOURCES


# --- Decision A / Phase 1b — `all` TOKEN = raw sources only (DONE) ------------
def test_all_expands_to_raw_sources_only():
    from rebalance.ingest.index_ops import _all_scope_names
    assert set(_all_scope_names()) == RAW_SOURCES


def test_default_refresh_recipe_preserves_follow_on_stages():
    """`all` is narrowed to raw sources, but the default (no-scope) recipe still
    runs the follow-on stages, so a full refresh behaves as before (Decision A)."""
    from rebalance.ingest.index_ops import _default_refresh_scopes
    recipe = set(_default_refresh_scopes())
    assert RAW_SOURCES <= recipe
    assert {"code", "semantic", "sync"} <= recipe


# --- Decision B / Phase 3 — semantic projection is single-writer (stage-owned) -
def test_semantic_projection_is_single_writer():
    """Only the `semantic` stage may project/embed into the semantic tables.

    _refresh_semantic_only is the single call site for both functions in index_ops.
    Any new source that wants semantic coverage must add itself to _ALL_SEMANTIC_SOURCES,
    NOT call backfill_semantic_documents / embed_pending inline.
    """
    src = INDEX_OPS.read_text(encoding="utf-8")
    assert src.count("backfill_semantic_documents(") == 1
    assert src.count("embed_pending(") == 1


# --- Phase 3 follow-up — semantic source list derived from registry (no second edit needed) -
def test_all_semantic_sources_includes_registry_providers():
    """Every collector with a semantic_docs provider must be in _all_semantic_sources().

    Guards against the drift where a new source is registered with semantic_docs
    but is never projected because the semantic stage's source list wasn't updated.
    _all_semantic_sources() is registry-derived so this should never fail — but
    the contract stays as a load-bearing regression guard.
    """
    from rebalance.ingest.index_ops import _all_semantic_sources, _semantic_source_names
    all_sem = set(_all_semantic_sources())
    missing = set(_semantic_source_names()) - all_sem
    assert not missing, (
        f"sources with semantic_docs not in _all_semantic_sources(): {missing}"
    )


# --- DASHBOARD row 8 (SOLID/OCP) / Phase 2 — no leaf-ingest bypasses (ENFORCED) -
# Phase 2 landed: every CLI/MCP write surface now routes through a source-owned
# helper, so this contract is enforced strictly (no xfail). A new bypass fails CI.
def test_user_surfaces_do_not_import_leaf_ingest_functions():
    surfaces = list((SRC / "cli").rglob("*.py")) + list((SRC / "mcp" / "tools").rglob("*.py"))
    offenders = {}
    for path in surfaces:
        bad = _imported_names(path) & LEAF_INGEST_FNS
        if bad:
            offenders[str(path.relative_to(REPO_ROOT))] = sorted(bad)
    assert not offenders, f"user-facing surfaces import leaf ingest fns directly: {offenders}"
