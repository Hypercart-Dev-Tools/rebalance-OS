"""
GitHub Actions workflow-run ingestion.

Fills the gap left by ``github_knowledge.sync_github_repo``, which only
captures per-PR check runs (keyed by head SHA).  This module pulls the
full ``/repos/{owner}/{repo}/actions/runs`` feed so the web dashboard can
show CI pass/fail status for any push or schedule, not just PR heads.

Storage: ``github_workflow_runs`` table — see ``db.ensure_github_schema``.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from rebalance.ingest.db import db_connection, ensure_github_schema

GITHUB_API = "https://api.github.com"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "rebalance-os/0.1",
    }


def _get(url: str, token: str) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except urllib.error.URLError:
        return 0, None


def fetch_workflow_runs(
    repo_full_name: str,
    token: str,
    *,
    since_days: int = 7,
    per_page: int = 50,
    max_pages: int = 4,
) -> list[dict[str, Any]]:
    """Return raw workflow run dicts from the GitHub REST API.

    The ``created`` query filter keeps the response window predictable so
    we don't drag in months of history on first sync.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    runs: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode(
            {"per_page": per_page, "page": page, "created": f">={cutoff}"}
        )
        url = f"{GITHUB_API}/repos/{repo_full_name}/actions/runs?{params}"
        status, data = _get(url, token)
        if status != 200 or not isinstance(data, dict):
            break
        page_runs = data.get("workflow_runs") or []
        if not isinstance(page_runs, list) or not page_runs:
            break
        runs.extend(page_runs)
        if len(page_runs) < per_page:
            break
    return runs


def upsert_workflow_runs(
    database_path: Path,
    repo_full_name: str,
    runs: Iterable[dict[str, Any]],
) -> int:
    """Upsert workflow runs into ``github_workflow_runs``. Returns row count."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    rows: list[tuple[Any, ...]] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        actor = (run.get("actor") or {}).get("login")
        triggering_actor = (run.get("triggering_actor") or {}).get("login")
        rows.append(
            (
                repo_full_name,
                int(run.get("id") or 0),
                int(run.get("run_attempt") or 1),
                run.get("name"),
                run.get("event"),
                run.get("head_branch"),
                run.get("head_sha"),
                run.get("status"),
                run.get("conclusion"),
                actor,
                triggering_actor,
                run.get("html_url"),
                run.get("created_at"),
                run.get("updated_at"),
                run.get("run_started_at"),
                fetched_at,
            )
        )
    if not rows:
        return 0
    with db_connection(database_path, ensure_github_schema) as conn:
        conn.executemany(
            """
            INSERT INTO github_workflow_runs (
                repo_full_name, run_id, run_attempt, workflow_name, event,
                head_branch, head_sha, status, conclusion, actor_login,
                triggering_actor_login, run_url, created_at, updated_at,
                run_started_at, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def sync_workflow_runs(
    database_path: Path,
    repo_full_name: str,
    token: str,
    *,
    since_days: int = 7,
) -> int:
    """Fetch and upsert in one call. Returns the number of rows written."""
    runs = fetch_workflow_runs(repo_full_name, token, since_days=since_days)
    return upsert_workflow_runs(database_path, repo_full_name, runs)


def latest_run_for_sha(
    conn: sqlite3.Connection, repo_full_name: str, head_sha: str
) -> dict[str, Any] | None:
    """Return the most recent workflow run for a given commit SHA, or None."""
    if not head_sha:
        return None
    row = conn.execute(
        """
        SELECT workflow_name, status, conclusion, run_url, created_at
        FROM github_workflow_runs
        WHERE repo_full_name = ? AND head_sha = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (repo_full_name, head_sha),
    ).fetchone()
    return dict(row) if row else None


__all__ = [
    "fetch_workflow_runs",
    "upsert_workflow_runs",
    "sync_workflow_runs",
    "latest_run_for_sha",
]
