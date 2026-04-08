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

    # ------------------------------------------------------------------
    # Retrieval tools
    # ------------------------------------------------------------------

    @mcp.tool()
    def query_notes(query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """
        Semantic search over chunked vault notes via sqlite-vec.

        Embeds the query using the same model used for indexing, then
        runs ANN search to find the most similar chunks.
        Requires: `rebalance ingest notes` + `rebalance ingest embed`.
        """
        from rebalance.ingest.embedder import query_similar
        return query_similar(database_path=database_path, query_text=query, top_k=top_k)

    @mcp.tool()
    def search_vault(keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Full-text keyword search over vault files via TF-IDF index.

        Searches the keywords table and returns ranked results.
        Requires: `rebalance ingest notes`.
        """
        from rebalance.ingest.note_ingester import search_by_keyword
        return search_by_keyword(database_path=database_path, keyword=keyword, limit=limit)

    @mcp.tool()
    def ask(query: str, since_days: int = 7, skip_synthesis: bool = False) -> dict[str, Any]:
        """
        General-purpose natural language query across all data sources.

        Gathers context from vault embeddings, GitHub activity, project
        registry, and recent vault modifications. Optionally synthesizes
        a first-pass answer via a local Qwen LLM.

        Returns both the synthesis and raw context so the host agent can
        review, adapt, and present a refined answer.

        Set skip_synthesis=True to get raw context only (faster, no model load).
        """
        from rebalance.ingest.querier import ask as querier_ask
        result = querier_ask(
            query=query,
            database_path=database_path,
            since_days=since_days,
            skip_synthesis=skip_synthesis,
        )
        return {
            "query": result.query,
            "synthesis": result.synthesis,
            "vault_context": result.vault_context,
            "github_context": result.github_context,
            "project_context": result.project_context,
            "vault_activity": result.vault_activity,
            "calendar_context": result.calendar_context,
            "temporal_context": result.temporal_context,
            "model_used": result.model_used,
            "elapsed_seconds": result.elapsed_seconds,
        }

    # ------------------------------------------------------------------
    # Calendar review tools
    # ------------------------------------------------------------------

    @mcp.tool()
    def review_timesheet(date_str: str = "") -> dict[str, Any]:
        """
        Return unclassified calendar events for a given date that need
        human or agent review.

        These are events that passed the exclude filter but did not match
        any configured project. The agent can recommend classifying them
        under a project, marking as "include" (real work, no project),
        or "exclude" (filler).

        Args:
            date_str: ISO date (YYYY-MM-DD). Defaults to today.

        Returns:
            needs_review: list of {summary, start_time, end_time, duration_minutes}
            available_projects: list of project names for classification
        """
        from datetime import date as date_cls

        from rebalance.ingest.calendar_config import CalendarConfig
        from rebalance.ingest.daily_report import get_day_data
        from rebalance.ingest.project_classifier import load_project_matchers

        config = CalendarConfig.load()
        target = date_cls.fromisoformat(date_str) if date_str else date_cls.today()
        matchers = load_project_matchers(database_path, config=config)
        day = get_day_data(database_path, target, config, project_matchers=matchers)

        review_items = []
        for event in day.needs_review:
            start_str = event.get("start_time", "")
            end_str = event.get("end_time", "")
            try:
                from datetime import datetime
                s = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                e = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                mins = int((e - s).total_seconds() / 60)
            except Exception:
                mins = 0
            review_items.append({
                "summary": event.get("summary", ""),
                "start_time": start_str,
                "end_time": end_str,
                "duration_minutes": mins,
            })

        project_names = [m.name for m in matchers]
        return {
            "date": target.isoformat(),
            "needs_review": review_items,
            "available_projects": project_names,
        }

    @mcp.tool()
    def classify_event(summary: str, decision: str) -> dict[str, Any]:
        """
        Persist a classification decision for an unmatched calendar event.

        After review_timesheet surfaces events, call this to record how
        each one should be handled in future reports.

        Args:
            summary: The event title (exact text from the calendar).
            decision: One of:
              - "include" — real work, keep in reports (no project assignment)
              - "exclude" — filler, remove from future reports
              - "project:<Name>" — assign to a specific project (e.g. "project:Binoid - Bloomz")

        Returns confirmation of the stored decision.
        """
        from rebalance.ingest.calendar_config import save_review_decision

        decision = decision.strip()
        valid_prefixes = ("include", "exclude", "project:")
        if not any(decision.startswith(p) for p in valid_prefixes):
            return {
                "error": f"Invalid decision '{decision}'. Must be 'include', 'exclude', or 'project:<Name>'.",
            }

        save_review_decision(summary, decision)
        return {
            "summary": summary,
            "decision": decision,
            "status": "saved",
        }

    return mcp


def main() -> None:
    db_env = os.getenv("REBALANCE_DB", "rebalance.db")
    database_path = Path(db_env).expanduser().resolve()
    server = create_server(database_path=database_path)
    server.run()


if __name__ == "__main__":
    main()
