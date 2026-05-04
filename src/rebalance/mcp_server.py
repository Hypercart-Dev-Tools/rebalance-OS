from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from rebalance.ingest.config import get_github_token, set_github_token, get_config_path
from rebalance.ingest.github_scan import get_github_balance, validate_github_token
from rebalance.ingest.preflight import discover_candidates, confirm_and_write
from rebalance.ingest.registry import get_projects


def _project_repos_map(database_path: Path) -> dict[str, list[str]]:
    """Return {project_name: [repo, ...]} for all active projects."""
    projects = get_projects(database_path, status="active")
    return {p["name"]: p.get("repos") or [] for p in projects}


def create_server(database_path: Path) -> FastMCP:
    mcp = FastMCP("rebalance")

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
                db_has_rows = len(get_projects(database_path)) > 0
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
    def query_github_context(query: str, repo_full_name: str = "", top_k: int = 8) -> list[dict[str, Any]]:
        """
        Semantic search over the local GitHub artifact corpus.

        Searches synced issues, pull requests, comments, reviews, and commit
        messages that have already been ingested into SQLite and embedded with
        the local model.
        """
        from rebalance.ingest.github_knowledge import query_github_documents

        return query_github_documents(
            database_path=database_path,
            query_text=query,
            repo_full_name=repo_full_name,
            top_k=top_k,
        )

    @mcp.tool()
    def github_release_readiness(repo_full_name: str, milestone_title: str = "") -> dict[str, Any]:
        """
        Infer current milestone/release readiness from the local GitHub corpus.

        Returns explicit status, confidence, blockers, evidence, and per-issue
        classifications using only locally synced GitHub signals.
        """
        from rebalance.ingest.github_readiness import infer_github_release_readiness

        result = infer_github_release_readiness(
            database_path=database_path,
            repo_full_name=repo_full_name,
            milestone_title=milestone_title,
        )
        return result.as_dict()

    @mcp.tool()
    def github_close_candidates(repo_full_name: str) -> dict[str, Any]:
        """
        Suggest open issues that likely map to merged PRs and may be ready to close.

        Returns explicit and inferred issue <-> PR matches grouped into
        high-confidence and medium-confidence recommendations.
        """
        from rebalance.ingest.github_reconciliation import infer_issue_pr_close_candidates

        report = infer_issue_pr_close_candidates(
            database_path=database_path,
            repo_full_name=repo_full_name,
        )
        return report.as_dict()

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
            "github_semantic_context": result.github_semantic_context,
            "project_context": result.project_context,
            "vault_activity": result.vault_activity,
            "calendar_context": result.calendar_context,
            "temporal_context": result.temporal_context,
            "model_used": result.model_used,
            "elapsed_seconds": result.elapsed_seconds,
        }

    # ------------------------------------------------------------------
    # Calendar tools
    # ------------------------------------------------------------------

    @mcp.tool()
    def create_calendar_event(
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        attendees: list[str] | None = None,
        calendar_id: str = "",
        timezone_name: str = "",
    ) -> dict[str, Any]:
        """
        Create a Google Calendar event using the local OAuth token.

        Args:
            summary: Event title.
            start_time: ISO datetime with timezone offset.
            end_time: ISO datetime with timezone offset.
            description: Optional body text.
            location: Optional location.
            attendees: Optional attendee email list.
            calendar_id: Optional calendar ID. Defaults to the local config calendar.
            timezone_name: Optional IANA timezone name to include in the event payload.
        """
        from rebalance.ingest.calendar import create_calendar_event as calendar_create_event
        from rebalance.ingest.calendar_config import CalendarConfig

        resolved_calendar_id = calendar_id.strip()
        if not resolved_calendar_id:
            resolved_calendar_id = CalendarConfig.load().calendar_id

        result = calendar_create_event(
            calendar_id=resolved_calendar_id,
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            description=description,
            location=location,
            attendees=attendees or [],
            timezone_name=timezone_name.strip() or None,
        )
        return {
            "event_id": result.event_id,
            "html_link": result.html_link,
            "calendar_id": result.calendar_id,
            "summary": result.summary,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "attendees_count": result.attendees_count,
            "status": "created",
        }

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

        from rebalance.ingest.calendar_helpers import event_duration_minutes

        review_items = []
        for event in day.needs_review:
            start_str = event.get("start_time", "")
            end_str = event.get("end_time", "")
            review_items.append({
                "summary": event.get("summary", ""),
                "start_time": start_str,
                "end_time": end_str,
                "duration_minutes": event_duration_minutes(start_str, end_str),
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
        from rebalance.ingest.calendar_config import save_review_decision, InvalidDecisionError

        try:
            save_review_decision(summary, decision.strip())
        except InvalidDecisionError as e:
            return {"error": str(e)}

        return {
            "summary": summary,
            "decision": decision.strip(),
            "status": "saved",
        }

    @mcp.tool()
    def snap_calendar_edges(
        date_str: str = "",
        days: int = 1,
        calendar_id: str = "",
        timezone_name: str = "",
        apply: bool = False,
    ) -> dict[str, Any]:
        """
        Detect and fix slightly overlapping calendar events by trimming
        Event 1's end to 1 minute before Event 2's start.

        Dry-run by default — set apply=True to actually patch Google Calendar.
        Skips all-day events and clusters of 3+ overlapping events.

        Args:
            date_str: Start date (YYYY-MM-DD). Defaults to today.
            days: Number of consecutive days to process (1-7).
            calendar_id: Calendar ID. Defaults to config calendar.
            timezone_name: IANA timezone. Defaults to config timezone.
            apply: If True, patches Google Calendar. Default False (dry-run).
        """
        import dataclasses
        from datetime import date as date_cls, datetime
        from zoneinfo import ZoneInfo

        from rebalance.ingest.calendar_config import CalendarConfig
        from rebalance.ingest.calendar_snap import snap_edges

        config = CalendarConfig.load()
        resolved_calendar_id = calendar_id.strip() or config.calendar_id
        resolved_timezone = timezone_name.strip() or config.timezone
        if date_str.strip():
            start_date = date_cls.fromisoformat(date_str)
        else:
            # Use the calendar timezone for "today", not the server's local date
            start_date = datetime.now(ZoneInfo(resolved_timezone)).date()

        result = snap_edges(
            calendar_id=resolved_calendar_id,
            start_date=start_date,
            num_days=days,
            timezone_name=resolved_timezone,
            apply=apply,
        )
        return dataclasses.asdict(result)

    # ------------------------------------------------------------------
    # Single-entry-point tools (index status + orchestrated refresh + unified query)
    #
    # These are the tools agents should reach for first. They wrap the
    # underlying ingest pipelines so callers do not need to know the order of
    # github-scan -> github-sync-artifacts -> semantic-backfill -> semantic-embed,
    # vault note ingest -> embed -> semantic backfill -> semantic embed, etc.
    # ------------------------------------------------------------------

    @mcp.tool()
    def index_status() -> dict[str, Any]:
        """
        Snapshot the SQLite knowledge base: per-source counts, last-synced
        timestamps, unified semantic index health, and drift between source
        tables and the semantic index.

        Use this before deciding whether to call refresh_index, and to answer
        "what data is available right now?" without scanning the repo.
        Read-only; cheap.
        """
        from rebalance.ingest.index_ops import get_index_status
        return get_index_status(database_path)

    @mcp.tool()
    def refresh_index(
        scope: list[str] | None = None,
        vault_path: str = "",
        since_days: int = 30,
        repos: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Orchestrated refresh of the local knowledge base. This is the single
        entry point for getting the SQLite vector DB up to date — agents
        should call this instead of running individual `rebalance ...` CLI
        commands.

        Args:
            scope: Any combination of "vault", "github", "calendar", "sleuth",
                "semantic", or "all". Defaults to ["all"].
                - vault: ingest vault notes -> embed chunks -> semantic backfill+embed (vault)
                - github: github-scan -> sync artifacts per repo -> embed -> semantic backfill+embed (github)
                - calendar: sync Google Calendar events
                - sleuth: pull Slack/Sleuth reminders
                - semantic: re-run unified backfill+embed only (assumes upstream syncs done)
            vault_path: Optional override; falls back to configured vault path.
            since_days: Lookback window for github-scan and calendar-sync (default 30).
            repos: Optional list of owner/name repos for github sync. Defaults
                to all active project repos.
            dry_run: If True, returns the planned steps without touching the
                DB or network. Useful for a "what would this do?" preview.

        Caveat: github sync hits the GitHub API for every active project repo
        and can take minutes. Use dry_run=True first if unsure.
        """
        from rebalance.ingest.index_ops import refresh_index as _refresh
        return _refresh(
            database_path,
            scope=scope,
            vault_path=vault_path,
            since_days=since_days,
            repos=repos,
            dry_run=dry_run,
        )

    @mcp.tool()
    def list_watched_repos(since_days: int = 14) -> dict[str, Any]:
        """
        Show which GitHub repos are currently being monitored, and where each
        one came from. The merged "watched" list = (project registry ∪ recent
        activity from github_activity) − ignored. This is the same set
        refresh_index syncs.

        Use this when:
          - The user asks "is X being monitored?"
          - You suspect coverage gaps (a repo with activity but no synced artifacts)
          - Before/after editing the active project list or ignored repos

        Args:
            since_days: Lookback window for the auto-discovered activity set.
                Default 14 — matches refresh_index defaults.
        """
        from rebalance.ingest.index_ops import get_watched_repos
        return get_watched_repos(database_path, since_days=since_days)

    @mcp.tool()
    def publish_pulse(
        dry_run: bool = False,
        push: bool = True,
    ) -> dict[str, Any]:
        """
        Render today's + yesterday's activity into a markdown status page and
        publish it to a private git repo (e.g. a personal "git-pulse-sync"
        working tree). Reads pulse settings from temp/rbos.config:
          - github_login, slack_user_id, pulse_target_path, pulse_filename,
            pulse_timezone

        The output covers:
          - Current Day: GitHub commits/issues/PRs/comments authored by you,
            Obsidian vault edits, Sleuth reminders assigned to you,
            upcoming Google Calendar events, and live-fetched GitHub issues
            assigned to you over the last 7 days (today's at the top).
          - Yesterday: a summarized version of the same.

        The commit + push only happens when the rendered markdown actually
        changed since the last run, so quiet hours don't create churn.

        Args:
            dry_run: If True, returns the rendered markdown but does not
                touch the target repo. Useful for previews from agents.
            push: If False, commit locally but don't push to origin.

        The hourly launchd job (com.rebalance-os.pulse-sync) calls this with
        dry_run=False, push=True between 6 AM and 11 PM local time.
        """
        from rebalance.ingest.pulse import publish_pulse as _publish_pulse
        return _publish_pulse(database_path, dry_run=dry_run, push=push)

    @mcp.tool()
    def semantic_query(
        query: str,
        sources: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Vector search across the unified semantic index (vault chunks +
        GitHub issues/PRs/comments in one ranked result set).

        Prefer this over query_notes / query_github_context when you want a
        single ranked result set across every source. The older tools still
        work and read pre-unified per-source indexes.

        Args:
            query: Natural language query.
            sources: Filter to ["vault"], ["github"], or both. Defaults to both.
            top_k: Number of results.
        """
        from rebalance.ingest.semantic_index import query as _semantic_query
        return _semantic_query(
            database_path,
            query,
            top_k=top_k,
            source_filter=sources,
        )

    # ------------------------------------------------------------------
    # Sleuth reminders
    # ------------------------------------------------------------------

    @mcp.tool()
    def sleuth_sync_reminders(active_only: bool = False) -> dict[str, Any]:
        """
        Pull Slack reminders from the Sleuth Web API and upsert them into SQLite.

        Credentials are loaded from ~/secrets/sleuth-web-api-development.env
        (operator-owned, mode 600). Set active_only=True to fetch only the
        currently active reminders; default pulls all states so completed
        reminders get their terminal state mirrored.
        """
        from rebalance.cli import _load_sleuth_env
        from rebalance.ingest.sleuth_reminders import sync_sleuth_reminders

        env_data = _load_sleuth_env()
        result = sync_sleuth_reminders(
            base_url=env_data["SLEUTH_WEB_API_BASE_URL"],
            token=env_data["SLEUTH_WEB_API_TOKEN"],
            workspace_name=env_data["SLEUTH_WORKSPACE_NAME"],
            database_path=database_path,
            active_only=active_only,
        )
        return result.as_dict()

    return mcp


def main() -> None:
    db_env = os.getenv("REBALANCE_DB", "rebalance.db")
    database_path = Path(db_env).expanduser().resolve()
    server = create_server(database_path=database_path)
    server.run()


if __name__ == "__main__":
    main()
