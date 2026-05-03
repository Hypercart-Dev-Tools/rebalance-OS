"""
Data readers for the web dashboard.

Two sources, both read-only at query time:

1. GitHub data already in the SQLite db (commits, items, workflow runs)
   — populated by the periodic ingest loop in ``ingest_loop.py``.
2. Local device pulse files (``pulse-<device>.md``) checked out into
   the mirror directory by a systemd timer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest.db import db_connection, ensure_github_schema


@dataclass(frozen=True)
class DevicePulseLine:
    when: str
    device: str
    repo: str
    branch: str
    sha: str
    subject: str


def _parse_since(since: str | None) -> datetime:
    """Accept ``24h`` / ``7d`` / ISO-8601; default to 24h."""
    now = datetime.now(timezone.utc)
    if not since:
        return now - timedelta(hours=24)
    s = since.strip().lower()
    if s.endswith("h") and s[:-1].isdigit():
        return now - timedelta(hours=int(s[:-1]))
    if s.endswith("d") and s[:-1].isdigit():
        return now - timedelta(days=int(s[:-1]))
    try:
        parsed = datetime.fromisoformat(s.replace("z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return now - timedelta(hours=24)


def read_github_commits(database_path: Path, since: datetime) -> list[dict[str, Any]]:
    """Return commit rows joined with the latest workflow run per head_sha."""
    cutoff = since.isoformat()
    with db_connection(database_path, ensure_github_schema) as conn:
        rows = conn.execute(
            """
            SELECT
                c.repo_full_name AS repo,
                c.sha            AS sha,
                c.author_login   AS author,
                c.message        AS message,
                c.committed_at   AS committed_at,
                c.html_url       AS commit_url,
                c.item_type      AS item_type,
                c.item_number    AS item_number,
                w.workflow_name  AS run_name,
                w.status         AS run_status,
                w.conclusion     AS run_conclusion,
                w.run_url        AS run_url,
                w.head_branch    AS run_branch
            FROM github_commits c
            LEFT JOIN (
                SELECT repo_full_name, head_sha, workflow_name, status,
                       conclusion, run_url, head_branch,
                       ROW_NUMBER() OVER (
                           PARTITION BY repo_full_name, head_sha
                           ORDER BY created_at DESC
                       ) AS rn
                FROM github_workflow_runs
            ) w
              ON w.repo_full_name = c.repo_full_name
             AND w.head_sha = c.sha
             AND w.rn = 1
            WHERE c.committed_at >= ?
            ORDER BY c.committed_at DESC
            LIMIT 500
            """,
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def read_pull_requests(database_path: Path, since: datetime) -> list[dict[str, Any]]:
    cutoff = since.isoformat()
    with db_connection(database_path, ensure_github_schema) as conn:
        rows = conn.execute(
            """
            SELECT
                repo_full_name AS repo,
                number,
                title,
                state,
                is_merged,
                author_login  AS author,
                head_ref      AS branch,
                head_sha,
                html_url,
                created_at,
                updated_at,
                merged_at
            FROM github_items
            WHERE item_type = 'pull_request' AND updated_at >= ?
            ORDER BY updated_at DESC
            LIMIT 200
            """,
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def read_workflow_runs(database_path: Path, since: datetime) -> list[dict[str, Any]]:
    cutoff = since.isoformat()
    with db_connection(database_path, ensure_github_schema) as conn:
        rows = conn.execute(
            """
            SELECT repo_full_name AS repo, run_id, workflow_name, event,
                   head_branch, head_sha, status, conclusion, actor_login,
                   run_url, created_at
            FROM github_workflow_runs
            WHERE created_at >= ?
            ORDER BY created_at DESC
            LIMIT 200
            """,
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def read_device_pulses(mirror_path: Path, since: datetime) -> list[DevicePulseLine]:
    """Read TSV-style pulse files emitted by ``experimental/git-pulse/collect.sh``.

    Expected format per line (tab-separated):
        <epoch>\t<iso8601>\t<repo>\t<branch>\t<sha>\t<subject>
    Lines starting with ``#`` are ignored. Missing directory → empty list.
    """
    if not mirror_path or not mirror_path.exists():
        return []
    cutoff_epoch = int(since.timestamp())
    out: list[DevicePulseLine] = []
    for pulse_file in sorted(mirror_path.glob("pulse-*.md")):
        device = pulse_file.stem.removeprefix("pulse-")
        try:
            text = pulse_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            try:
                epoch = int(parts[0])
            except ValueError:
                continue
            if epoch < cutoff_epoch:
                continue
            out.append(
                DevicePulseLine(
                    when=parts[1],
                    device=device,
                    repo=parts[2],
                    branch=parts[3],
                    sha=parts[4],
                    subject=parts[5],
                )
            )
    out.sort(key=lambda p: p.when, reverse=True)
    return out


def health(database_path: Path, mirror_path: Path | None) -> dict[str, Any]:
    """Lightweight health snapshot for ``/api/health``."""
    info: dict[str, Any] = {
        "ok": True,
        "db_path": str(database_path),
        "db_exists": database_path.exists(),
        "db_size_bytes": database_path.stat().st_size if database_path.exists() else 0,
        "mirror_path": str(mirror_path) if mirror_path else None,
        "mirror_exists": bool(mirror_path and mirror_path.exists()),
    }
    if database_path.exists():
        with db_connection(database_path, ensure_github_schema) as conn:
            row = conn.execute(
                "SELECT MAX(fetched_at) AS last FROM github_workflow_runs"
            ).fetchone()
            info["last_workflow_fetch"] = row["last"] if row else None
            row = conn.execute(
                "SELECT MAX(fetched_at) AS last FROM github_items"
            ).fetchone()
            info["last_items_fetch"] = row["last"] if row else None
    info["server_time"] = datetime.now(timezone.utc).isoformat()
    info["pid"] = os.getpid()
    return info


__all__ = [
    "DevicePulseLine",
    "_parse_since",
    "read_github_commits",
    "read_pull_requests",
    "read_workflow_runs",
    "read_device_pulses",
    "health",
]
