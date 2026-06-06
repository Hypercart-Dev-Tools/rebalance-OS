from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP, database_path: Path) -> None:
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
                "email", "semantic", or "all". Defaults to ["all"].
                - vault: ingest vault notes -> embed chunks -> semantic backfill+embed (vault)
                - github: github-scan -> sync artifacts per repo -> embed -> semantic backfill+embed (github)
                - calendar: sync Google Calendar events
                - sleuth: pull Slack/Sleuth reminders
                - email: sync newest-100 inbox messages from Gmail (ADC auth)
                  and backfill them into the semantic index. Configure scope
                  via ``gmail_query_filter`` in temp/rbos.config.
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
    def diagnose_repo(
        repo: str,
        sha: str = "",
        pr: int | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """
        Walk the watched-repos + sync funnel for a single GitHub repo and
        report why it is (or isn't) showing up. Answers three questions:

          - Is this repo being monitored?
          - Why isn't this repo showing up?
          - Why didn't this specific commit / PR show up?

        DB-only by default — fast, offline-safe, and reads the same source
        of truth as list_watched_repos. Pass live=True to also probe
        GitHub directly: confirms PAT visibility on the repo and (if sha
        or pr is supplied) whether the commit / PR actually exists
        upstream. Useful for distinguishing "we never synced" from "PAT
        can't see it".

        Args:
            repo: "owner/name". Case-insensitive; validated against the
                same regex used elsewhere.
            sha: Optional commit SHA (full or short prefix). Reports
                whether the commit was ingested and which PR it was
                associated with.
            pr: Optional PR number. Reports whether the PR was ingested
                and its state / freshness.
            live: If True, hit GitHub for /repos, /commits/{sha}, and
                /pulls/{number}. Off by default to avoid network cost.

        Returns a dict with: verdict, summary, monitoring{}, sync{},
        commit{} | None, pr{} | None, pat{}, next_actions[].
        """
        from rebalance.ingest.diagnose import diagnose_repo as _diagnose_repo
        return _diagnose_repo(
            database_path,
            repo=repo,
            sha=sha,
            pr=pr,
            live=live,
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
    def list_ask_self_repos() -> dict[str, Any]:
        """
        Inventory every repo on this device that has an ask_self RAG index,
        cross-referenced against the watched-repos set.

        Each entry reports its local path, derived GitHub identity
        (owner/repo), whether the index is actually built, chunk/file counts,
        embedding model, last-ingest time, the device it lives on, and a
        ``watched`` flag (True when Rebalance already monitors that repo). The
        ``summary`` block totals built vs. watched and lists the devices seen.

        Read-only over the ``ask_self_indexes`` table. Populate/refresh it with
        refresh_index(scope=["ask_self"]) — this tool does not scan the disk.

        Use this to answer "which of my projects have a queryable local brain,
        and which machine is it on?".
        """
        from rebalance.ingest.ask_self_scan import summarize_ask_self_indexes
        return summarize_ask_self_indexes(database_path)

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
            Obsidian vault edits, Sleuth reminders assigned to you or by you,
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
        updated_after: str | None = None,
        repo: str | None = None,
        hybrid: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Vector search across the unified semantic index (vault chunks +
        GitHub issues/PRs/comments, and Gmail subject/snippet documents in
        one ranked result set).

        Prefer this over query_notes / query_github_context when you want a
        single ranked result set across every source. The older tools still
        work and read pre-unified per-source indexes.

        Args:
            query: Natural language query.
            sources: Filter to any of ["vault"], ["github"], ["email"], or
                any combination of them. Defaults to all indexed sources.
            top_k: Number of results.
            updated_after: ISO-8601 date/datetime string (e.g. "2026-05-01").
                Excludes documents updated before this point. Useful for
                date-bounded investigations without raw SQL fallback.
            repo: Restrict GitHub results to one repo in ``owner/name`` form.
                Non-GitHub results are unaffected.
        """
        from rebalance.ingest.semantic_index import query as _semantic_query
        return _semantic_query(
            database_path,
            query,
            top_k=top_k,
            source_filter=sources,
            updated_after=updated_after,
            repo=repo,
            hybrid=hybrid,
        )
