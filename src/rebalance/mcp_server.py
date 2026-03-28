from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from rebalance.ingest.github_scan import get_github_balance


def _fetch_projects(database_path: Path, status: str | None = None) -> list[dict[str, Any]]:
    if not database_path.exists():
        return []

    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT name, status, summary, value_level, priority_tier, risk_level, repos_json FROM project_registry"
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY name ASC"

        rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            # repos_json is stored as JSON array string; decode and rename for callers
            raw_repos = d.pop("repos_json", None)
            if isinstance(raw_repos, str):
                try:
                    d["repos"] = json.loads(raw_repos)
                except (json.JSONDecodeError, ValueError):
                    d["repos"] = []
            else:
                d["repos"] = []
            result.append(d)
        return result
    finally:
        conn.close()


def _project_repos_map(database_path: Path) -> dict[str, list[str]]:
    """Return {project_name: [repo, ...]} for all active projects."""
    projects = _fetch_projects(database_path, status="active")
    return {p["name"]: p.get("repos") or [] for p in projects}


def create_server(database_path: Path) -> FastMCP:
    mcp = FastMCP("rebalance")

    @mcp.tool()
    def list_projects(status: str = "active") -> list[dict[str, Any]]:
        """List projects from the local project_registry table."""
        normalized = status.strip().lower() if status else ""
        return _fetch_projects(database_path=database_path, status=normalized or None)

    @mcp.tool()
    def github_balance(since_days: int = 14) -> list[dict[str, Any]]:
        """
        Show GitHub activity balance across active projects.

        Returns one row per project with commit/PR/issue counts over the last
        `since_days` days.  Projects with no GitHub activity are flagged as
        idle (is_idle=true).  Requires a prior `rebalance github-scan` run.
        """
        project_repos = _project_repos_map(database_path)
        return get_github_balance(
            database_path=database_path,
            project_repos=project_repos,
            since_days=since_days,
        )

    return mcp


def main() -> None:
    db_env = os.getenv("REBALANCE_DB", "rebalance.db")
    database_path = Path(db_env).expanduser().resolve()
    server = create_server(database_path=database_path)
    server.run()


if __name__ == "__main__":
    main()
