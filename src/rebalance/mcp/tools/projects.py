from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from rebalance.ingest.github_scan import get_github_balance
from rebalance.ingest.registry import get_projects


def _project_repos_map(database_path: Path) -> dict[str, list[str]]:
    """Return {project_name: [repo, ...]} for all active projects."""
    projects = get_projects(database_path, status="active")
    return {p["name"]: p.get("repos") or [] for p in projects}


def register(mcp: FastMCP, database_path: Path) -> None:
    @mcp.tool()
    def list_projects(status: str = "active") -> list[dict[str, Any]]:
        """List projects from the local project_registry table."""
        normalized = status.strip().lower() if status else ""
        return get_projects(database_path, status=normalized or None)

    @mcp.tool()
    def github_balance(since_days: int = 30) -> list[dict[str, Any]]:
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
