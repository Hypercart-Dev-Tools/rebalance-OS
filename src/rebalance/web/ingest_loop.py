"""
Background ingest loop for the web dashboard.

Every ``REBALANCE_WEB_INGEST_SECS`` (default 600s = 10min) the loop:

1. Resolves the watch list — union of (a) registry-active repos, (b) any
   repo seen in the user's GitHub events feed in the last 14 days.
2. Calls ``sync_github_repo`` for each repo (issues, PRs, commits,
   check runs, links).
3. Calls ``sync_workflow_runs`` for each repo (Actions runs).
4. Records ``last_ingest`` timestamp + per-repo elapsed time.

The loop is also exposed via ``run_once()`` so the ``/api/refresh`` endpoint
can trigger an immediate cycle.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest import github_workflows
from rebalance.ingest.config import get_github_token
from rebalance.ingest.github_knowledge import sync_github_repo
from rebalance.ingest.github_scan import _fetch_events, _get_login
from rebalance.ingest.registry import get_projects

log = logging.getLogger(__name__)


@dataclass
class IngestState:
    last_started_at: str | None = None
    last_finished_at: str | None = None
    last_error: str | None = None
    last_repos: list[str] = field(default_factory=list)
    in_flight: bool = False
    cycles_completed: int = 0


def _resolve_watch_list(token: str, database_path: Path) -> list[str]:
    repos: set[str] = set()
    for project in get_projects(database_path, status="active"):
        for r in project.get("repos") or []:
            if isinstance(r, str) and "/" in r:
                repos.add(r.lower())

    try:
        login = _get_login(token)
        events = _fetch_events(login, token, days=14)
    except Exception as exc:  # noqa: BLE001 — we want to keep going on event-fetch errors
        log.warning("event fetch failed during watch-list discovery: %s", exc)
        events = []
    for ev in events:
        repo = (ev.get("repo") or {}).get("name")
        if isinstance(repo, str) and "/" in repo:
            repos.add(repo.lower())
    return sorted(repos)


def run_once(database_path: Path, state: IngestState) -> dict[str, Any]:
    """Run a single ingest cycle synchronously. Returns a summary dict."""
    if state.in_flight:
        return {"skipped": True, "reason": "ingest already in flight"}
    token = get_github_token()
    if not token:
        state.last_error = "no GitHub token (set GITHUB_TOKEN or run setup_github_token)"
        return {"ok": False, "error": state.last_error}

    state.in_flight = True
    started = datetime.now(timezone.utc).isoformat()
    state.last_started_at = started
    summary: dict[str, Any] = {"started_at": started, "repos": []}

    try:
        watch = _resolve_watch_list(token, database_path)
        state.last_repos = watch
        for repo in watch:
            entry: dict[str, Any] = {"repo": repo}
            try:
                sync_github_repo(database_path, repo, token, since_days=14)
                entry["github"] = "ok"
            except Exception as exc:  # noqa: BLE001
                entry["github"] = f"error: {exc}"
                log.exception("sync_github_repo failed for %s", repo)
            try:
                rows = github_workflows.sync_workflow_runs(
                    database_path, repo, token, since_days=7
                )
                entry["workflow_rows"] = rows
            except Exception as exc:  # noqa: BLE001
                entry["workflow_rows"] = f"error: {exc}"
                log.exception("sync_workflow_runs failed for %s", repo)
            summary["repos"].append(entry)
        state.last_error = None
        state.cycles_completed += 1
    except Exception as exc:  # noqa: BLE001
        state.last_error = str(exc)
        log.exception("ingest cycle failed")
        summary["error"] = str(exc)
    finally:
        state.in_flight = False
        state.last_finished_at = datetime.now(timezone.utc).isoformat()
        summary["finished_at"] = state.last_finished_at
    return summary


async def loop_forever(database_path: Path, state: IngestState) -> None:
    """Async loop driven by FastAPI's lifespan. Sleeps between cycles."""
    interval = int(os.environ.get("REBALANCE_WEB_INGEST_SECS", "600"))
    while True:
        try:
            await asyncio.to_thread(run_once, database_path, state)
        except Exception:  # noqa: BLE001
            log.exception("unexpected error in ingest loop")
        await asyncio.sleep(interval)


__all__ = ["IngestState", "run_once", "loop_forever", "_resolve_watch_list"]
