"""Index operations: status snapshot and orchestrated refresh.

This module is the single entry point that MCP tools (and any agent embedding
the SDK) should use instead of the discrete CLI commands. It composes the
underlying ingest pipelines so callers do not have to know the order of
``github-scan`` -> ``github-sync-artifacts`` -> ``semantic-backfill`` ->
``semantic-embed`` etc.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable

from rebalance.ingest.config import (
    get_github_token,
    get_vault_path,
)
from rebalance.ingest.db import db_connection, ensure_semantic_schema, run_migrations
from rebalance.ingest.registry import get_projects

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Collector:
    """A single data-source ingest pipeline registered with :data:`COLLECTORS`.

    External integrators add new data sources by constructing a :class:`Collector`
    and calling :func:`register_collector`. The dispatcher in :func:`refresh_index`
    routes the user's ``scope=[...]`` list through the registry — no edits to
    the dispatch chain are required.

    Fields
    ------
    name:
        The user-facing scope key. Must be unique. Reserved: ``"all"``.
    refresh:
        Callable executed for live runs. Receives ``(db_path, **opts)`` where
        ``opts`` includes every refresh_index kwarg the collector might want
        (since_days, vault_path, token, repos, include_semantic, ...). Unknown
        keys must be ignored. Must return a ``dict`` whose first key is
        ``"scope": "<name>"`` so the caller can correlate results.
    requires:
        Optional iterable of precondition names — currently ``"vault_path"``,
        ``"github_token"``. Failures surface as structured errors rather than
        exceptions, mirroring the legacy refresh_index error envelope.
    included_in_all:
        If True (default), the collector runs when the user requests
        ``scope=["all"]``. Set False for opt-in collectors (e.g. heavy or
        narrowly-scoped sources).
    """

    name: str
    refresh: Callable[..., dict[str, Any]]
    requires: tuple[str, ...] = ()
    included_in_all: bool = True


COLLECTORS: dict[str, Collector] = {}


def register_collector(collector: Collector, *, replace: bool = False) -> None:
    """Add a :class:`Collector` to the registry.

    Set ``replace=True`` when an external integrator deliberately overrides a
    built-in. Otherwise duplicate names raise to surface accidental shadowing.
    """
    if not collector.name or collector.name != collector.name.lower():
        raise ValueError(
            f"Collector name must be non-empty and lowercase: {collector.name!r}"
        )
    if collector.name == "all":
        raise ValueError(f"Reserved collector name: {collector.name!r}")
    if collector.name in COLLECTORS and not replace:
        raise ValueError(
            f"Collector {collector.name!r} already registered; pass replace=True to override."
        )
    COLLECTORS[collector.name] = collector
    logger.debug("Registered collector: %s (requires=%s)", collector.name, collector.requires)


def _scope_values() -> tuple[str, ...]:
    """Return the supported scope keys, plus the meta-scope ``"all"``."""
    return tuple(COLLECTORS.keys()) + ("all",)


def _all_scope_names() -> list[str]:
    """Return the collector names that run for ``scope=["all"]``."""
    return [name for name, c in COLLECTORS.items() if c.included_in_all]


# Legacy SCOPE_VALUES: retained so callers importing the constant continue to
# work. New code should call _scope_values() since registered collectors may
# extend the set at runtime.
SCOPE_VALUES = ("vault", "github", "calendar", "sleuth", "email", "semantic", "all")


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
    valid = _scope_values()
    for raw in items:
        v = (raw or "").strip().lower()
        if not v:
            continue
        if v not in valid:
            raise ValueError(f"Unsupported scope: {raw!r}. Expected one of {valid}.")
        if v not in cleaned:
            cleaned.append(v)
    if not cleaned:
        return ["all"]
    if "all" in cleaned:
        return _all_scope_names()
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

        payload["sources"]["email"] = {
            "messages": _safe_count(conn, "email_messages"),
            "last_synced_at": _safe_max(conn, "email_messages", "synced_at"),
            "newest_received_at": _safe_max(conn, "email_messages", "received_at"),
        }

        try:
            built = conn.execute(
                "SELECT COUNT(*) FROM ask_self_indexes WHERE index_built = 1"
            ).fetchone()[0]
        except Exception:
            built = None
        payload["sources"]["ask_self"] = {
            "repos": _safe_count(conn, "ask_self_indexes"),
            "built_indexes": built,
            "last_scanned_at": _safe_max(conn, "ask_self_indexes", "scanned_at"),
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
            "touched_files": ingest_result.touched_files,
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

    These are repos the user has *actually worked in* on GitHub in the last
    *since_days*, regardless of whether they appear in the project registry.
    Passive events such as starring/watching a repo may create GitHub Events
    API entries, but they must not auto-monitor a repo.
    """
    repos: list[str] = []
    try:
        with db_connection(database_path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT repo_full_name
                FROM github_activity
                WHERE scan_date >= date('now', ?)
                  AND (
                    commits + pushes + prs_opened + prs_merged
                    + issues_opened + issue_comments + reviews
                  ) > 0
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


def _pushed_repos(database_path: Path, *, since_days: int = 14) -> list[str]:
    """Repos discovered via /user/repos?sort=pushed with a recent pushed_at.

    Read from the github_pushed_repos table populated by sync_pushed_repos().
    Catches activity that the events feed misses — pushes by collaborators
    on private org repos, pushes dropped by the events API's 300-event
    pagination cap, eventual-consistency gaps, and non-default-branch /
    force-push edge cases. The events feed and this signal are
    complementary; the union goes into the watched set.
    """
    from datetime import datetime, timedelta, timezone

    repos: list[str] = []
    try:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=int(since_days))
        ).isoformat()
        with db_connection(database_path) as conn:
            rows = conn.execute(
                """
                SELECT repo_full_name FROM github_pushed_repos
                WHERE pushed_at >= ?
                  AND archived = 0 AND disabled = 0
                ORDER BY pushed_at DESC
                """,
                (cutoff,),
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

    The merged ``watched`` list = (project_repos ∪ activity_repos ∪
    pushed_repos) − ignored. Callers (``refresh_index``,
    ``list_watched_repos`` MCP tool, the ``raw`` diagnostic) consume the
    same source of truth so the user can never wonder "what's actually
    being synced?"
    """
    from rebalance.ingest.config import get_github_ignored_repos

    project = _project_repos(database_path)
    activity = _activity_repos(database_path, since_days=since_days)
    pushed = _pushed_repos(database_path, since_days=since_days)
    ignored = sorted(get_github_ignored_repos())
    # Ignored entries are stored lowercased (CLI normalizes on add);
    # watched-set sources keep GitHub's original casing. Compare on lowercase
    # so e.g. an "xpressbase/athenacomply" entry blocks "xpressbase/athenaComply".
    ignored_lower = {r.lower() for r in ignored}

    project_set = set(project)
    activity_set = set(activity)
    pushed_set = set(pushed)

    watched: list[str] = []
    for repo in project + activity + pushed:
        if repo.lower() in ignored_lower:
            continue
        if repo not in watched:
            watched.append(repo)

    auto_discovered = sorted(
        repo for repo in (activity_set | pushed_set) - project_set
        if repo.lower() not in ignored_lower
    )

    return {
        "watched": watched,
        "project_repos": project,
        "activity_repos": activity,
        "pushed_repos": pushed,
        "auto_discovered": auto_discovered,
        "ignored": ignored,
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
    include_semantic: bool = True,
) -> dict[str, Any]:
    initial_target_repos = _resolve_repos_for_refresh(database_path, repos)
    plan_steps = [
        "sync_pushed_repos()",
        f"github_scan(days={since_days})",
        f"sync_github_repo() x ~{len(initial_target_repos)} repos (after auto-discovery)",
    ]
    if include_semantic:
        plan_steps.extend([
            "embed_github_documents()",
            "semantic_backfill(source=['github'])",
            "semantic_embed(source=['github'])",
        ])
    else:
        plan_steps.append("skip semantic embedding")
    if dry_run:
        return {
            "scope": "github",
            "dry_run": True,
            "target_repos": initial_target_repos,
            "steps": plan_steps,
        }

    from rebalance.ingest.github_scan import (
        filter_ignored_repo_activity,
        scan_github,
        sync_pushed_repos,
        upsert_github_activity,
    )
    from rebalance.ingest.config import get_github_ignored_repos
    from rebalance.ingest.github_knowledge import sync_github_repo

    # Auto-discovery: fetch /user/repos?sort=pushed and upsert into
    # github_pushed_repos BEFORE resolving target repos, so newly-pushed
    # repos enter the watched set on this refresh rather than the next one.
    pushed_result = sync_pushed_repos(database_path, token=token)
    target_repos = _resolve_repos_for_refresh(database_path, repos)

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

    result: dict[str, Any] = {
        "scope": "github",
        "dry_run": False,
        "pushed_repos_sync": {
            "fetched": pushed_result.fetched,
            "inserted": pushed_result.inserted,
            "updated": pushed_result.updated,
            "unchanged": pushed_result.unchanged,
            "skipped_archived": pushed_result.skipped_archived,
            "error": pushed_result.error,
        },
        "github_scan": {
            "login": scan_result.login,
            "events": scan_result.total_events,
            "repos": len(scan_result.repo_activity),
            "skipped_ignored": len(skipped),
        },
        "artifact_sync": repo_results,
    }
    if not include_semantic:
        result["semantic"] = {
            "skipped": True,
            "reason": "include_semantic=False",
        }
        return result

    from rebalance.ingest.github_knowledge import embed_github_documents
    from rebalance.ingest.semantic_index import (
        backfill_semantic_documents,
        embed_pending,
    )

    gh_embed = embed_github_documents(database_path=database_path)
    backfill = backfill_semantic_documents(database_path, source_types=["github"])
    sem_embed = embed_pending(database_path, source_types=["github"])
    result.update({
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
    })
    return result


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
    # For a file source, sync_sleuth_reminders refreshes the export clone itself
    # (best-effort, non-destructive) and reports it as `source_refresh`.
    result = sync_sleuth_reminders(
        base_url=env["SLEUTH_WEB_API_BASE_URL"],
        token=env["SLEUTH_WEB_API_TOKEN"],
        workspace_name=env["SLEUTH_WORKSPACE_NAME"],
        database_path=database_path,
        active_only=False,
    )
    return {"scope": "sleuth", "dry_run": False, **result.as_dict()}


def _refresh_code(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Refresh the native code corpus (source_type='code') from the source tree.

    FTS-only: the AST collector + backfill keep ``semantic_documents`` and the
    trigger-synced FTS index current. Embedding code chunks (the vector half) is
    intentionally skipped here — the hybrid FTS already answers code questions,
    and embedding ~1k chunks every refresh would be slow for little gain.
    """
    if dry_run:
        return {"scope": "code", "dry_run": True, "steps": ["semantic_backfill(source=['code'])"]}

    from rebalance.ingest.semantic_index import backfill_semantic_documents

    backfill = backfill_semantic_documents(database_path, source_types=["code"])
    return {
        "scope": "code",
        "dry_run": False,
        "semantic_backfill": {
            "total": backfill.total_documents,
            "inserted": backfill.inserted_count,
            "updated": backfill.updated_count,
            "deleted": backfill.deleted_count,
            "elapsed_seconds": backfill.elapsed_seconds,
        },
    }


def _refresh_email(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    from rebalance.ingest.config import get_gmail_ingest_method

    if get_gmail_ingest_method() == "mcp":
        # MCP mode: email_messages is populated by an agent via the Gmail MCP
        # connector. A scheduled (launchd) job cannot reach an MCP connector,
        # so this step is a deliberate no-op — reported honestly, neither as a
        # success nor as an error.
        return {
            "scope": "email",
            "dry_run": dry_run,
            "method": "mcp",
            "skipped": True,
            "note": (
                "Gmail is in MCP mode — email_messages is ingested by an agent "
                "via the Gmail MCP connector, not by this job."
            ),
        }

    if dry_run:
        return {
            "scope": "email",
            "dry_run": True,
            "steps": ["sync_gmail()", "semantic_backfill(email)"],
        }

    from rebalance.ingest.gmail import GmailAuthError, sync_gmail
    from rebalance.ingest.semantic_index import backfill_semantic_documents

    try:
        sync_result = sync_gmail(database_path=database_path)
    except GmailAuthError as exc:
        return {"scope": "email", "dry_run": False, "error": str(exc)}

    semantic = backfill_semantic_documents(database_path, source_types=["email"])
    return {
        "scope": "email",
        "dry_run": False,
        "messages_listed": sync_result.messages_listed,
        "messages_stored": sync_result.messages_stored,
        "messages_inserted": sync_result.messages_inserted,
        "messages_updated": sync_result.messages_updated,
        "query_filter": sync_result.query_filter,
        "elapsed_seconds": sync_result.elapsed_seconds,
        "semantic_backfill": {
            "total": semantic.total_documents,
            "inserted": semantic.inserted_count,
            "updated": semantic.updated_count,
            "elapsed_seconds": semantic.elapsed_seconds,
        },
    }


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
    backfill = backfill_semantic_documents(database_path, source_types=["vault", "github", "email"])
    sem_embed = embed_pending(database_path, source_types=["vault", "github", "email"])
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


def _refresh_dashboard_note(
    database_path: Path,
    *,
    vault_path: Path,
    since_days: int,
    dry_run: bool,
    note_path: str = "Dashboards/rebalanceOS Dashboard.md",
) -> dict[str, Any]:
    output_path = (vault_path / note_path).resolve()
    plan = {
        "scope": "dashboard",
        "dry_run": dry_run,
        "output_path": str(output_path),
        "steps": [
            "build_dashboard_note_content()",
            "write_dashboard_note()",
            "ingest_vault()",
            "embed_chunks()",
            "semantic_backfill(source=['vault'])",
            "semantic_embed(source=['vault'])",
        ],
    }
    if dry_run:
        return plan

    from rebalance.ingest.calendar_config import CalendarConfig
    from rebalance.ingest.note_builder import build_dashboard_note_content, write_dashboard_note
    from rebalance.ingest.embedder import embed_chunks
    from rebalance.ingest.note_ingester import ingest_vault
    from rebalance.ingest.semantic_index import backfill_semantic_documents, embed_pending

    markdown = build_dashboard_note_content(
        database_path,
        target_date=date.today(),
        since_days=since_days,
        config=CalendarConfig.load(),
    )
    note_file = write_dashboard_note(output_path, markdown)
    ingest_result = ingest_vault(vault_path=vault_path, database_path=database_path)
    embed_result = embed_chunks(database_path=database_path)
    backfill = backfill_semantic_documents(database_path, source_types=["vault"])
    sem_embed = embed_pending(database_path, source_types=["vault"])

    return {
        "scope": "dashboard",
        "dry_run": False,
        "output_path": str(note_file),
        "ingest": {
            "total_files": ingest_result.total_files,
            "new_files": ingest_result.new_files,
            "updated_files": ingest_result.updated_files,
            "touched_files": ingest_result.touched_files,
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


def refresh_index(
    database_path: Path,
    *,
    scope: Iterable[str] | str | None = None,
    vault_path: str = "",
    since_days: int = 30,
    repos: list[str] | None = None,
    dry_run: bool = False,
    include_semantic: bool = True,
    update_dashboard_note: bool = True,
) -> dict[str, Any]:
    """Run the configured ingest pipelines for ``scope`` and return a summary.

    ``scope`` accepts any combination of ``vault``, ``github``, ``calendar``,
    ``sleuth``, ``email``, ``semantic``, or ``all``. ``dry_run=True`` returns
    the planned steps without touching the DB or network.
    """
    db_path = Path(database_path).expanduser().resolve()
    requested_scopes = _normalize_scope(scope)
    full_refresh_requested = scope is None or "all" in (scope or [])
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
        elif not dry_run:
            # If the stored PAT is deauthorized (401), fall back to the gh CLI
            # token and persist it so this and the launchd jobs recover. No-op
            # when the PAT is valid or gh is unavailable (e.g. under launchd).
            from rebalance.ingest.github_scan import resolve_working_token
            resolved_token = resolve_working_token(resolved_token)

    repos_list = list(repos or [])

    # Per-collector kwargs bundle. Each collector ignores keys it doesn't need.
    collector_opts: dict[str, Any] = {
        "vault_path": resolved_vault,
        "token": resolved_token,
        "since_days": since_days,
        "repos": repos_list,
        "dry_run": dry_run,
        "include_semantic": include_semantic,
    }

    # Bring the database schema to the latest version before any collector
    # writes to it. Skipped on dry runs, which must not touch the DB.
    if not dry_run:
        try:
            with db_connection(db_path) as conn:
                run_migrations(conn)
        except Exception as e:  # noqa: BLE001 — error envelope mirrors collector contract
            errors.append({"scope": "migrations", "error": str(e)})

    for s in requested_scopes:
        collector = COLLECTORS.get(s)
        if collector is None:
            errors.append({"scope": s, "error": f"no collector registered for scope {s!r}"})
            continue
        # Enforce declared preconditions.
        missing_reqs: list[str] = []
        if "vault_path" in collector.requires and not collector_opts.get("vault_path"):
            missing_reqs.append("vault_path")
        if "github_token" in collector.requires and not collector_opts.get("token"):
            missing_reqs.append("github_token")
        if missing_reqs:
            errors.append({"scope": s, "error": f"missing required options: {missing_reqs}"})
            continue
        try:
            results.append(collector.refresh(db_path, **collector_opts))
        except Exception as e:  # noqa: BLE001 — error envelope mirrors legacy contract
            errors.append({"scope": s, "error": str(e)})

    if update_dashboard_note and full_refresh_requested and resolved_vault is not None:
        if errors and not dry_run:
            results.append({
                "scope": "dashboard",
                "dry_run": False,
                "skipped": True,
                "reason": "upstream refresh errors",
            })
        else:
            try:
                results.append(_refresh_dashboard_note(
                    db_path,
                    vault_path=resolved_vault,
                    since_days=since_days,
                    dry_run=dry_run,
                ))
            except Exception as e:
                errors.append({"scope": "dashboard", "error": str(e)})

    return {
        "database_path": str(db_path),
        "requested_scopes": requested_scopes,
        "dry_run": dry_run,
        "results": results,
        "errors": errors,
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }


# ---------------------------------------------------------------------------
# Built-in collectors
# ---------------------------------------------------------------------------
#
# Adapter functions normalize each per-source refresh function to the Collector
# signature (db_path, **opts). Unknown keys are ignored; required keys are
# extracted by name. The legacy ``_refresh_*`` private functions remain the
# single source of truth for the ingest pipelines — these adapters are 3-line
# shims.

def _vault_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    vault_path = opts.get("vault_path")
    assert vault_path is not None, "vault collector requires vault_path"
    return _refresh_vault(db_path, vault_path, dry_run=opts["dry_run"])


def _github_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    return _refresh_github(
        db_path,
        token=opts["token"],
        since_days=opts["since_days"],
        repos=opts.get("repos") or [],
        dry_run=opts["dry_run"],
        include_semantic=opts.get("include_semantic", True),
    )


def _calendar_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    return _refresh_calendar(db_path, since_days=opts["since_days"], dry_run=opts["dry_run"])


def _sleuth_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    return _refresh_sleuth(db_path, dry_run=opts["dry_run"])


def _email_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    return _refresh_email(db_path, dry_run=opts["dry_run"])


def _code_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    return _refresh_code(db_path, dry_run=opts["dry_run"])


def _semantic_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    return _refresh_semantic_only(db_path, dry_run=opts["dry_run"])


def _refresh_sync(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Export calendar + email snapshots to the sync subfolder in the pulse repo."""
    from rebalance.ingest.config import get_pulse_config, get_sync_subdir
    from rebalance.ingest.sync_snapshot import (
        commit_and_push_sync,
        export_calendar_snapshot,
        export_email_snapshot,
        get_device_id,
    )

    cfg = get_pulse_config()
    pulse_target = cfg.get("pulse_target_path", "")
    if not pulse_target:
        return {
            "scope": "sync",
            "dry_run": dry_run,
            "error": "pulse_target_path not configured — run: rebalance config set-pulse-config pulse_target_path=<path>",
        }

    target_repo = Path(pulse_target).expanduser().resolve()
    sync_subdir = get_sync_subdir()
    sync_dir = target_repo / sync_subdir
    device_id = get_device_id()

    if dry_run:
        return {
            "scope": "sync",
            "dry_run": True,
            "steps": [
                f"export_calendar_snapshot(window_days=90) → {sync_dir}/calendar/{device_id}.json",
                f"export_email_snapshot(limit=1000) → {sync_dir}/email/{device_id}.json",
                f"git add {sync_subdir}/ && git commit && git push → {target_repo}",
            ],
        }

    import time
    started = time.monotonic()
    cal_path = export_calendar_snapshot(database_path, sync_dir, device_id=device_id)
    email_path = export_email_snapshot(database_path, sync_dir, device_id=device_id)

    import json as _json
    generated_at = _json.loads(cal_path.read_text(encoding="utf-8"))["generated_at"]
    git_result = commit_and_push_sync(
        target_repo, sync_subdir, device_id=device_id, generated_at=generated_at
    )

    return {
        "scope": "sync",
        "dry_run": False,
        "device_id": device_id,
        "calendar_snapshot": str(cal_path.relative_to(target_repo)),
        "email_snapshot": str(email_path.relative_to(target_repo)),
        "git": git_result,
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }


def _sync_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    return _refresh_sync(db_path, dry_run=opts["dry_run"])


def _refresh_ask_self(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Walk this device for ask_self-enabled repos and record their indexes.

    Discovery-only: reads each repo's ask_self harness + index metadata
    (read-only) and upserts one row per repo into ``ask_self_indexes``. Does not
    build or refresh any RAG index itself. Opt-in (``included_in_all=False``)
    because it walks the filesystem; run explicitly via
    ``refresh_index(scope=["ask_self"])``.
    """
    from rebalance.ingest.config import get_ask_self_scan_roots

    roots = get_ask_self_scan_roots()
    if dry_run:
        return {
            "scope": "ask_self",
            "dry_run": True,
            "scan_roots": roots,
            "steps": [
                f"scan_ask_self_repos(roots={roots})",
                "read each ask_self index repo_metadata (read-only)",
                "upsert ask_self_indexes (keyed by device_id, local_path)",
            ],
        }

    from rebalance.ingest.ask_self_scan import sync_ask_self_indexes

    result = sync_ask_self_indexes(database_path, roots=roots)
    return {"scope": "ask_self", "dry_run": False, **result.as_dict()}


def _ask_self_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    return _refresh_ask_self(db_path, dry_run=opts["dry_run"])


def _refresh_focus5(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Scan device-local git repos and rebuild the Focus 5 roster.

    Discovers active local repos (bounded zero-config walk), probes per-repo
    git signals, and persists both the full signal cache and the ranked top-5
    roster. Local-git-first: the GitHub corpus is enrichment only. Opt-in
    (``included_in_all=False``) because it walks the filesystem and shells git;
    run explicitly via ``refresh_index(scope=["focus5"])`` or lazily from the
    web view when the roster TTL has expired.
    """
    from rebalance.ingest.config import get_focus5_ranking_mode, get_focus5_scan_roots

    roots = get_focus5_scan_roots()
    mode = get_focus5_ranking_mode()
    if dry_run:
        return {
            "scope": "focus5",
            "dry_run": True,
            "scan_roots": roots,
            "ranking_mode": mode,
            "steps": [
                f"iter_git_repos(roots={roots})",
                "probe per-repo signals (read-only git status/log + .git stats)",
                "replace focus5_repo_signals for this device (off-roster cache)",
                f"rank via {mode!r} strategy and replace focus5_roster (top 5)",
            ],
        }

    from rebalance.ingest.focus5_scan import sync_focus5

    result = sync_focus5(database_path, roots=roots, mode=mode)
    return {"scope": "focus5", "dry_run": False, **result.as_dict()}


def _focus5_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    return _refresh_focus5(db_path, dry_run=opts["dry_run"])


register_collector(Collector("vault", _vault_adapter, requires=("vault_path",)))
register_collector(Collector("github", _github_adapter, requires=("github_token",)))
register_collector(Collector("calendar", _calendar_adapter))
register_collector(Collector("sleuth", _sleuth_adapter))
register_collector(Collector("email", _email_adapter))
register_collector(Collector("code", _code_adapter))
register_collector(Collector("semantic", _semantic_adapter))
register_collector(Collector("sync", _sync_adapter))
register_collector(Collector("focus5", _focus5_adapter, included_in_all=False))
register_collector(Collector("ask_self", _ask_self_adapter, included_in_all=False))
