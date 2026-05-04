"""Index operations: status snapshot and orchestrated refresh.

This module is the single entry point that MCP tools (and any agent embedding
the SDK) should use instead of the discrete CLI commands. It composes the
underlying ingest pipelines so callers do not have to know the order of
``github-scan`` -> ``github-sync-artifacts`` -> ``semantic-backfill`` ->
``semantic-embed`` etc.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterable

from rebalance.ingest.config import (
    get_github_token,
    get_vault_path,
)
from rebalance.ingest.db import db_connection, ensure_semantic_schema
from rebalance.ingest.registry import get_projects


SCOPE_VALUES = ("vault", "github", "calendar", "sleuth", "semantic", "all")


def _safe_count(conn: Any, table: str) -> int | None:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return None


def _safe_max(conn: Any, table: str, column: str) -> str | None:
    try:
        row = conn.execute(f"SELECT MAX({column}) FROM {table}").fetchone()
        return row[0] if row and row[0] else None
    except Exception:
        return None


def _safe_meta(conn: Any, table: str) -> dict[str, str]:
    try:
        rows = conn.execute(f"SELECT key, value FROM {table}").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


def _normalize_scope(scope: Iterable[str] | str | None) -> list[str]:
    if scope is None:
        return ["all"]
    if isinstance(scope, str):
        items = [scope]
    else:
        items = list(scope)
    cleaned: list[str] = []
    for raw in items:
        v = (raw or "").strip().lower()
        if not v:
            continue
        if v not in SCOPE_VALUES:
            raise ValueError(f"Unsupported scope: {raw!r}. Expected one of {SCOPE_VALUES}.")
        if v not in cleaned:
            cleaned.append(v)
    if not cleaned:
        return ["all"]
    if "all" in cleaned:
        return ["vault", "github", "calendar", "sleuth", "semantic"]
    return cleaned


def get_index_status(database_path: Path) -> dict[str, Any]:
    """Return a structured snapshot of every source + the unified semantic index.

    Read-only. Safe to call frequently; no schema migrations beyond the standard
    semantic schema bootstrap done elsewhere.
    """
    db_path = Path(database_path).expanduser().resolve()
    payload: dict[str, Any] = {
        "database_path": str(db_path),
        "database_exists": db_path.exists(),
        "sources": {},
        "semantic_index": {},
        "freshness": {},
    }

    if not db_path.exists():
        payload["error"] = "database file does not exist"
        return payload

    with db_connection(db_path, ensure_semantic_schema) as conn:
        payload["sources"]["vault"] = {
            "files": _safe_count(conn, "vault_files"),
            "chunks": _safe_count(conn, "chunks"),
            "last_ingested_at": _safe_max(conn, "vault_files", "ingested_at"),
            "last_modified_in_vault": _safe_max(conn, "vault_files", "last_modified"),
        }

        payload["sources"]["github"] = {
            "items": _safe_count(conn, "github_items"),
            "documents": _safe_count(conn, "github_documents"),
            "activity_records": _safe_count(conn, "github_activity"),
            "activity_last_scanned_at": _safe_max(conn, "github_activity", "scanned_at"),
            "documents_last_fetched_at": _safe_max(conn, "github_documents", "fetched_at"),
            "documents_last_updated_at": _safe_max(conn, "github_documents", "updated_at"),
        }

        payload["sources"]["calendar"] = {
            "events": _safe_count(conn, "calendar_events"),
            "last_fetched_at": _safe_max(conn, "calendar_events", "fetched_at"),
            "earliest_event_start": _safe_max(conn, "calendar_events", "start_time"),
        }

        payload["sources"]["sleuth"] = {
            "reminders": _safe_count(conn, "sleuth_reminders"),
            "last_synced_at": _safe_max(conn, "sleuth_reminders", "last_synced_at"),
        }

        # Semantic index
        sem_total = _safe_count(conn, "semantic_documents")
        sem_meta = _safe_meta(conn, "semantic_embedding_meta")
        by_source: dict[str, dict[str, int]] = {}
        try:
            rows = conn.execute(
                """
                SELECT source_type,
                       COUNT(*) AS docs,
                       SUM(CASE WHEN embedded_hash IS NOT NULL
                                 AND embedded_hash = content_hash
                                THEN 1 ELSE 0 END) AS embedded
                FROM semantic_documents
                GROUP BY source_type
                """
            ).fetchall()
            for r in rows:
                by_source[r["source_type"]] = {
                    "documents": int(r["docs"] or 0),
                    "embedded": int(r["embedded"] or 0),
                    "pending": int((r["docs"] or 0) - (r["embedded"] or 0)),
                }
        except Exception:
            pass

        try:
            embeddings_rows = conn.execute(
                "SELECT COUNT(*) FROM semantic_embeddings"
            ).fetchone()[0]
        except Exception:
            embeddings_rows = None

        payload["semantic_index"] = {
            "total_documents": sem_total,
            "by_source": by_source,
            "embeddings_rows": embeddings_rows,
            "model_name": sem_meta.get("model_name"),
            "embedding_dim": sem_meta.get("embedding_dim"),
            "embedder_version": sem_meta.get("embedder_version"),
            "last_embedded_at": sem_meta.get("last_embed_at"),
        }

        # Freshness drift checks: source rows that are NOT in semantic_documents
        drift: dict[str, Any] = {}
        try:
            vault_drift = conn.execute(
                """
                SELECT COUNT(*) FROM chunks c
                LEFT JOIN semantic_documents sd
                  ON sd.source_type = 'vault' AND sd.source_pk = CAST(c.id AS TEXT)
                WHERE sd.id IS NULL
                """
            ).fetchone()[0]
            drift["vault_chunks_missing_from_semantic"] = int(vault_drift)
        except Exception:
            drift["vault_chunks_missing_from_semantic"] = None

        try:
            gh_drift = conn.execute(
                """
                SELECT COUNT(*) FROM github_documents gd
                LEFT JOIN semantic_documents sd
                  ON sd.source_type = 'github' AND sd.source_pk = gd.source_key
                WHERE sd.id IS NULL
                """
            ).fetchone()[0]
            drift["github_documents_missing_from_semantic"] = int(gh_drift)
        except Exception:
            drift["github_documents_missing_from_semantic"] = None

        try:
            pending_embed = conn.execute(
                """
                SELECT COUNT(*) FROM semantic_documents
                WHERE embedded_hash IS NULL OR embedded_hash != content_hash
                """
            ).fetchone()[0]
            drift["semantic_documents_pending_embed"] = int(pending_embed)
        except Exception:
            drift["semantic_documents_pending_embed"] = None

        payload["freshness"] = drift

    return payload


def _refresh_vault(
    database_path: Path,
    vault_path: Path,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    plan = {
        "steps": [
            f"ingest_vault(vault={vault_path})",
            "embed_chunks()",
            "semantic_backfill(source=['vault'])",
            "semantic_embed(source=['vault'])",
        ]
    }
    if dry_run:
        return {"scope": "vault", "dry_run": True, **plan}

    from rebalance.ingest.note_ingester import ingest_vault
    from rebalance.ingest.embedder import embed_chunks
    from rebalance.ingest.semantic_index import (
        backfill_semantic_documents,
        embed_pending,
    )

    ingest_result = ingest_vault(
        vault_path=vault_path,
        database_path=database_path,
        exclude_patterns=[".obsidian/*", ".trash/*", "node_modules/*", ".git/*", ".venv/*", "*/.venv/*"],
        dry_run=False,
    )
    embed_result = embed_chunks(database_path=database_path)
    backfill = backfill_semantic_documents(database_path, source_types=["vault"])
    sem_embed = embed_pending(database_path, source_types=["vault"])

    return {
        "scope": "vault",
        "dry_run": False,
        "ingest": {
            "total_files": ingest_result.total_files,
            "new_files": ingest_result.new_files,
            "updated_files": ingest_result.updated_files,
            "deleted_files": ingest_result.deleted_files,
            "total_chunks": ingest_result.total_chunks,
            "elapsed_seconds": ingest_result.elapsed_seconds,
        },
        "embed_chunks": {
            "total_chunks": embed_result.total_chunks,
            "embedded": embed_result.embedded_chunks,
            "skipped_unchanged": embed_result.skipped_unchanged,
            "elapsed_seconds": embed_result.elapsed_seconds,
        },
        "semantic_backfill": {
            "total": backfill.total_documents,
            "inserted": backfill.inserted_count,
            "updated": backfill.updated_count,
            "deleted": backfill.deleted_count,
            "elapsed_seconds": backfill.elapsed_seconds,
        },
        "semantic_embed": {
            "total": sem_embed.total_docs,
            "embedded": sem_embed.embedded_docs,
            "skipped_unchanged": sem_embed.skipped_unchanged,
            "elapsed_seconds": sem_embed.elapsed_seconds,
        },
    }


def _project_repos(database_path: Path) -> list[str]:
    """Repos drawn from the active project registry (operator-curated)."""
    repos: list[str] = []
    try:
        for project in get_projects(database_path, status="active"):
            for repo in project.get("repos") or []:
                r = repo.strip()
                if r and r not in repos:
                    repos.append(r)
    except Exception:
        pass
    return repos


def _activity_repos(database_path: Path, *, since_days: int = 14) -> list[str]:
    """Repos with recent activity according to ``github_activity``.

    These are repos the user has *actually touched* on GitHub in the last
    *since_days*, regardless of whether they appear in the project registry.
    Auto-discovered, used to close coverage gaps.
    """
    repos: list[str] = []
    try:
        with db_connection(database_path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT repo_full_name
                FROM github_activity
                WHERE scan_date >= date('now', ?)
                ORDER BY repo_full_name
                """,
                (f"-{int(since_days)} days",),
            ).fetchall()
            for r in rows:
                repo = (r["repo_full_name"] or "").strip()
                if repo and repo not in repos:
                    repos.append(repo)
    except Exception:
        pass
    return repos


def get_watched_repos(
    database_path: Path,
    *,
    since_days: int = 14,
) -> dict[str, list[str]]:
    """Return the canonical view of which repos are monitored.

    The merged ``watched`` list = (project_repos ∪ activity_repos) − ignored.
    Callers (``refresh_index``, ``list_watched_repos`` MCP tool) consume the
    same source of truth so the user can never wonder "what's actually
    being synced?"
    """
    from rebalance.ingest.config import get_github_ignored_repos

    project = _project_repos(database_path)
    activity = _activity_repos(database_path, since_days=since_days)
    ignored = set(get_github_ignored_repos())

    project_set = set(project)
    activity_set = set(activity)

    watched: list[str] = []
    for repo in project + activity:
        if repo in ignored:
            continue
        if repo not in watched:
            watched.append(repo)

    return {
        "watched": watched,
        "project_repos": project,
        "activity_repos": activity,
        "auto_discovered": sorted(activity_set - project_set - ignored),
        "ignored": sorted(ignored),
        "since_days": since_days,
    }


def _resolve_repos_for_refresh(database_path: Path, repos: list[str]) -> list[str]:
    if repos:
        return [r.strip() for r in repos if r.strip()]
    return get_watched_repos(database_path)["watched"]


def _refresh_github(
    database_path: Path,
    *,
    token: str,
    since_days: int,
    repos: list[str],
    dry_run: bool,
) -> dict[str, Any]:
    target_repos = _resolve_repos_for_refresh(database_path, repos)
    plan_steps = [
        f"github_scan(days={since_days})",
        f"sync_github_repo() x {len(target_repos)} repos",
        "embed_github_documents()",
        "semantic_backfill(source=['github'])",
        "semantic_embed(source=['github'])",
    ]
    if dry_run:
        return {
            "scope": "github",
            "dry_run": True,
            "target_repos": target_repos,
            "steps": plan_steps,
        }

    from rebalance.ingest.github_scan import (
        filter_ignored_repo_activity,
        scan_github,
        upsert_github_activity,
    )
    from rebalance.ingest.config import get_github_ignored_repos
    from rebalance.ingest.github_knowledge import (
        embed_github_documents,
        sync_github_repo,
    )
    from rebalance.ingest.semantic_index import (
        backfill_semantic_documents,
        embed_pending,
    )

    scan_result = scan_github(token=token, days=since_days)
    skipped = filter_ignored_repo_activity(scan_result, get_github_ignored_repos())
    upsert_github_activity(database_path, scan_result)

    repo_results: list[dict[str, Any]] = []
    for repo in target_repos:
        try:
            r = sync_github_repo(
                database_path=database_path,
                repo_full_name=repo,
                token=token,
                since_days=since_days,
            )
            repo_results.append({
                "repo": repo,
                "branches": r.branches_synced,
                "issues": r.issues_synced,
                "prs": r.prs_synced,
                "comments": r.comments_synced,
                "commits": r.commits_synced,
                "checks": r.checks_synced,
                "docs_built": r.docs_built,
                "elapsed_seconds": r.elapsed_seconds,
            })
        except Exception as e:
            repo_results.append({"repo": repo, "error": str(e)})

    gh_embed = embed_github_documents(database_path=database_path)
    backfill = backfill_semantic_documents(database_path, source_types=["github"])
    sem_embed = embed_pending(database_path, source_types=["github"])

    return {
        "scope": "github",
        "dry_run": False,
        "github_scan": {
            "login": scan_result.login,
            "events": scan_result.total_events,
            "repos": len(scan_result.repo_activity),
            "skipped_ignored": len(skipped),
        },
        "artifact_sync": repo_results,
        "github_embed": {
            "total": gh_embed.total_docs,
            "embedded": gh_embed.embedded_docs,
            "skipped_unchanged": gh_embed.skipped_unchanged,
            "elapsed_seconds": gh_embed.elapsed_seconds,
        },
        "semantic_backfill": {
            "total": backfill.total_documents,
            "inserted": backfill.inserted_count,
            "updated": backfill.updated_count,
            "deleted": backfill.deleted_count,
            "elapsed_seconds": backfill.elapsed_seconds,
        },
        "semantic_embed": {
            "total": sem_embed.total_docs,
            "embedded": sem_embed.embedded_docs,
            "skipped_unchanged": sem_embed.skipped_unchanged,
            "elapsed_seconds": sem_embed.elapsed_seconds,
        },
    }


def _refresh_calendar(database_path: Path, *, since_days: int, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"scope": "calendar", "dry_run": True, "steps": [f"sync_calendar(days_back={since_days})"]}

    from rebalance.ingest.calendar import sync_calendar
    from rebalance.ingest.calendar_config import CalendarConfig

    config = CalendarConfig.load()
    result = sync_calendar(
        database_path=database_path,
        calendar_id=config.calendar_id,
        days_back=since_days,
        days_forward=7,
    )
    return {
        "scope": "calendar",
        "dry_run": False,
        "calendar_id": config.calendar_id,
        "events_fetched": result.events_fetched,
        "events_stored": result.events_stored,
        "window_start": result.window_start,
        "window_end": result.window_end,
        "elapsed_seconds": result.elapsed_seconds,
    }


def _refresh_sleuth(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"scope": "sleuth", "dry_run": True, "steps": ["sync_sleuth_reminders()"]}

    from rebalance.cli import _load_sleuth_env
    from rebalance.ingest.sleuth_reminders import sync_sleuth_reminders

    env = _load_sleuth_env()
    result = sync_sleuth_reminders(
        base_url=env["SLEUTH_WEB_API_BASE_URL"],
        token=env["SLEUTH_WEB_API_TOKEN"],
        workspace_name=env["SLEUTH_WORKSPACE_NAME"],
        database_path=database_path,
        active_only=False,
    )
    return {"scope": "sleuth", "dry_run": False, **result.as_dict()}


def _refresh_semantic_only(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {
            "scope": "semantic",
            "dry_run": True,
            "steps": ["semantic_backfill(all)", "semantic_embed(all)"],
        }
    from rebalance.ingest.semantic_index import (
        backfill_semantic_documents,
        embed_pending,
    )
    backfill = backfill_semantic_documents(database_path, source_types=["vault", "github"])
    sem_embed = embed_pending(database_path, source_types=["vault", "github"])
    return {
        "scope": "semantic",
        "dry_run": False,
        "semantic_backfill": {
            "total": backfill.total_documents,
            "inserted": backfill.inserted_count,
            "updated": backfill.updated_count,
            "deleted": backfill.deleted_count,
            "elapsed_seconds": backfill.elapsed_seconds,
        },
        "semantic_embed": {
            "total": sem_embed.total_docs,
            "embedded": sem_embed.embedded_docs,
            "skipped_unchanged": sem_embed.skipped_unchanged,
            "elapsed_seconds": sem_embed.elapsed_seconds,
        },
    }


def refresh_index(
    database_path: Path,
    *,
    scope: Iterable[str] | str | None = None,
    vault_path: str = "",
    since_days: int = 30,
    repos: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the configured ingest pipelines for ``scope`` and return a summary.

    ``scope`` accepts any combination of ``vault``, ``github``, ``calendar``,
    ``sleuth``, ``semantic``, or ``all``. ``dry_run=True`` returns the planned
    steps without touching the DB or network.
    """
    db_path = Path(database_path).expanduser().resolve()
    requested_scopes = _normalize_scope(scope)
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    resolved_vault: Path | None = None
    if "vault" in requested_scopes:
        candidate = (vault_path or "").strip() or get_vault_path() or ""
        if candidate:
            resolved_vault = Path(candidate).expanduser().resolve()
        if resolved_vault is None or not resolved_vault.exists():
            errors.append({
                "scope": "vault",
                "error": (
                    "vault path not configured or missing. Pass vault_path or run "
                    "`rebalance config set-vault-path`."
                ),
            })
            requested_scopes = [s for s in requested_scopes if s != "vault"]

    resolved_token = ""
    if "github" in requested_scopes:
        resolved_token = (get_github_token() or "").strip()
        if not resolved_token:
            errors.append({
                "scope": "github",
                "error": (
                    "GitHub token not configured. Use setup_github_token MCP tool "
                    "or `rebalance config set-github-token`."
                ),
            })
            requested_scopes = [s for s in requested_scopes if s != "github"]

    repos_list = list(repos or [])

    for s in requested_scopes:
        try:
            if s == "vault":
                assert resolved_vault is not None
                results.append(_refresh_vault(db_path, resolved_vault, dry_run=dry_run))
            elif s == "github":
                results.append(_refresh_github(
                    db_path,
                    token=resolved_token,
                    since_days=since_days,
                    repos=repos_list,
                    dry_run=dry_run,
                ))
            elif s == "calendar":
                results.append(_refresh_calendar(db_path, since_days=since_days, dry_run=dry_run))
            elif s == "sleuth":
                results.append(_refresh_sleuth(db_path, dry_run=dry_run))
            elif s == "semantic":
                results.append(_refresh_semantic_only(db_path, dry_run=dry_run))
        except Exception as e:
            errors.append({"scope": s, "error": str(e)})

    return {
        "database_path": str(db_path),
        "requested_scopes": requested_scopes,
        "dry_run": dry_run,
        "results": results,
        "errors": errors,
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
