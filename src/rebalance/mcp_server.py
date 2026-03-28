from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from rebalance.ingest.config import get_github_token, set_github_token, get_config_path
from rebalance.ingest.github_scan import get_github_balance, validate_github_token
from rebalance.ingest.preflight import discover_candidates, confirm_and_write


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

    # ------------------------------------------------------------------
    # Onboarding tools
    # ------------------------------------------------------------------

    @mcp.tool()
    def onboarding_status(vault_path: str) -> dict[str, Any]:
        """
        Check which onboarding steps are complete.

        Returns a list of steps with completion status so the host agent
        knows where to resume.  DB path is resolved from REBALANCE_DB
        (same as all server tools).
        """
        vp = Path(vault_path).expanduser().resolve()
        registry_path = vp / "Projects" / "00-project-registry.md"
        projects_yaml_path = vp / "projects.yaml"

        steps: list[dict[str, Any]] = []

        # Step 1: Config file exists
        config_path = get_config_path()
        steps.append({
            "name": "config_exists",
            "complete": config_path.exists(),
            "detail": str(config_path),
        })

        # Step 2: GitHub token present
        token = get_github_token()
        steps.append({
            "name": "github_token_set",
            "complete": token is not None,
            "detail": "Token is configured" if token else "No token found",
        })

        # Step 3: Registry file exists
        steps.append({
            "name": "registry_exists",
            "complete": registry_path.exists(),
            "detail": str(registry_path),
        })

        # Step 4: projects.yaml projection exists
        steps.append({
            "name": "projection_exists",
            "complete": projects_yaml_path.exists(),
            "detail": str(projects_yaml_path),
        })

        # Step 5: SQLite DB has project_registry rows
        db_has_rows = False
        if database_path.exists():
            try:
                conn = sqlite3.connect(database_path)
                count = conn.execute(
                    "SELECT COUNT(*) FROM project_registry"
                ).fetchone()[0]
                db_has_rows = count > 0
                conn.close()
            except Exception:
                pass
        steps.append({
            "name": "db_synced",
            "complete": db_has_rows,
            "detail": str(database_path),
        })

        return {"steps": steps}

    @mcp.tool()
    def setup_github_token(token: str) -> dict[str, Any]:
        """
        Validate a GitHub PAT against the /user endpoint and store it.

        Returns validation result with login and scopes.  If invalid,
        the token is not stored.
        """
        result = validate_github_token(token)
        if result["valid"]:
            set_github_token(token)
        return result

    @mcp.tool()
    def run_preflight(vault_path: str) -> dict[str, Any]:
        """
        Discover project candidates from vault note titles and GitHub
        activity.  Read-only — does not write to the registry.

        Returns candidates segmented by activity recency.  The host agent
        presents these to the user, then sends the curated list to
        confirm_projects.
        """
        vp = Path(vault_path).expanduser().resolve()
        registry_path = vp / "Projects" / "00-project-registry.md"
        token = get_github_token()

        discovery = discover_candidates(
            vault_path=vp,
            registry_path=registry_path,
            github_token=token,
        )

        return {
            "most_likely_active_projects": discovery.most_likely_active_projects,
            "semi_active_projects": discovery.semi_active_projects,
            "dormant_projects": discovery.dormant_projects,
            "potential_projects": discovery.potential_projects,
            "scanned_files": discovery.scanned_files,
            "github_error": discovery.github_error,
        }

    @mcp.tool()
    def confirm_projects(projects: list[dict[str, Any]], vault_path: str) -> dict[str, Any]:
        """
        Write confirmed projects to the canonical registry and run pull
        sync to materialize projects.yaml and the SQLite project_registry
        table.  Creates standard vault directories if missing.

        Pass the curated project list from run_preflight (with any
        user-edited fields like summary, priority_tier, tags).
        """
        vp = Path(vault_path).expanduser().resolve()
        registry_path = vp / "Projects" / "00-project-registry.md"
        projects_yaml_path = vp / "projects.yaml"

        result = confirm_and_write(
            projects=projects,
            vault_path=vp,
            registry_path=registry_path,
            projects_yaml_path=projects_yaml_path,
            database_path=database_path,
        )

        return {
            "registry_path": result.registry_path,
            "project_count": result.project_count,
            "sync_ok": result.sync_ok,
        }

    return mcp


def main() -> None:
    db_env = os.getenv("REBALANCE_DB", "rebalance.db")
    database_path = Path(db_env).expanduser().resolve()
    server = create_server(database_path=database_path)
    server.run()


if __name__ == "__main__":
    main()
