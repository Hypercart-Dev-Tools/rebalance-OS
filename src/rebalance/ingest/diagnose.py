"""
Repo diagnostics — one tool to answer "is this repo watched?", "why isn't
it showing up?", and "why didn't this commit/PR show up?"

Composes the existing watched-repos / sync-status / ignore-list machinery
and adds an optional live GitHub probe so the user can tell apart "we
never synced" from "PAT can't see it".
"""

from __future__ import annotations

import urllib.error
from pathlib import Path
from typing import Any

from rebalance.ingest._http import GitHubClient, GitHubHTTPError
from rebalance.ingest.config import (
    get_github_ignored_repos,
    get_github_token,
    normalize_github_repo_name,
)
from rebalance.ingest.db import db_connection
from rebalance.ingest.index_ops import _activity_repos, _project_repos
from rebalance.ingest.registry import get_projects
from rebalance.lib.time_ops import now_utc, parse_utc_iso


# Mirrors github_knowledge.sync_github_repo's default lookback for issues/PRs.
DEFAULT_SYNC_WINDOW_DAYS = 90


def _days_since(iso: str | None) -> float | None:
    parsed = parse_utc_iso(iso)
    if parsed is None:
        return None
    delta = now_utc() - parsed
    return round(delta.total_seconds() / 86400.0, 2)


def _probe_get_json(client: GitHubClient, path: str) -> Any:
    """One shared-client GET for a live probe.

    The shared client retries 429/5xx with backoff and detects rate limits
    from response headers — a bare copy of the auth headers here previously
    turned one transient failure into a false "PAT cannot see this repo"
    verdict (the reason these probes no longer build their own requests).
    """
    return client.get_json(path)


def _probe_failure(key: str, exc: Exception) -> dict[str, Any]:
    """Map a probe exception to the backwards-stable error envelope."""
    if isinstance(exc, GitHubHTTPError):
        return {key: False, "status": exc.status, "error": str(exc)}
    reason = getattr(exc, "reason", None)
    return {key: False, "status": None, "error": str(reason if reason is not None else exc)}


def _live_probe_repo(repo: str, token: str) -> dict[str, Any]:
    """GET /repos/{owner}/{repo}; return {can_see, status, error}."""
    try:
        data = _probe_get_json(GitHubClient(token, job_label="diagnose"), f"/repos/{repo}")
    except (GitHubHTTPError, urllib.error.URLError, OSError) as exc:
        return _probe_failure("can_see", exc)
    return {
        "can_see": True,
        "status": 200,
        "default_branch": data.get("default_branch"),
        "private": bool(data.get("private")),
    }


def _live_probe_commit(repo: str, sha: str, token: str) -> dict[str, Any]:
    try:
        data = _probe_get_json(GitHubClient(token, job_label="diagnose"), f"/repos/{repo}/commits/{sha}")
    except (GitHubHTTPError, urllib.error.URLError, OSError) as exc:
        return _probe_failure("exists", exc)
    commit = data.get("commit") or {}
    committer = commit.get("committer") or {}
    return {
        "exists": True,
        "sha": data.get("sha"),
        "committed_at": committer.get("date"),
        "message_first_line": (commit.get("message") or "").splitlines()[0][:200],
    }


def _live_probe_pr(repo: str, pr: int, token: str) -> dict[str, Any]:
    try:
        data = _probe_get_json(GitHubClient(token, job_label="diagnose"), f"/repos/{repo}/pulls/{pr}")
    except (GitHubHTTPError, urllib.error.URLError, OSError) as exc:
        return _probe_failure("exists", exc)
    return {
        "exists": True,
        "state": data.get("state"),
        "merged": bool(data.get("merged")),
        "updated_at": data.get("updated_at"),
        "title": data.get("title"),
    }


def diagnose_repo(
    database_path: Path,
    *,
    repo: str,
    sha: str = "",
    pr: int | None = None,
    live: bool = False,
) -> dict[str, Any]:
    """Walk the watched-repos + sync funnel for a single repo and report.

    See spike doc for the funnel; output shape stays backwards-stable as
    new checks get added (everything lives under named keys).
    """
    # Stage 1 — identity & config -----------------------------------------
    try:
        repo_norm = normalize_github_repo_name(repo)
    except ValueError as exc:
        return {
            "repo": repo,
            "verdict": "invalid_input",
            "summary": str(exc),
            "next_actions": [],
        }

    ignored = set(get_github_ignored_repos())
    is_ignored = repo_norm in ignored

    # Find the project that claims this repo (case-insensitive on owner/name).
    claimed_by_project: str | None = None
    project_status: str | None = None
    try:
        for project in get_projects(database_path):
            for r in project.get("repos") or []:
                if r and r.strip().lower() == repo_norm:
                    claimed_by_project = project.get("name")
                    project_status = project.get("status")
                    break
            if claimed_by_project:
                break
    except Exception:
        pass

    # Stage 2 — discovery membership --------------------------------------
    project_repos_lower = {r.lower() for r in _project_repos(database_path)}
    activity_repos_lower = {r.lower() for r in _activity_repos(database_path, since_days=14)}
    in_registry = repo_norm in project_repos_lower
    in_recent_activity = repo_norm in activity_repos_lower
    watched = (in_registry or in_recent_activity) and not is_ignored

    monitoring_reason: str | None = None
    if not watched:
        if is_ignored:
            monitoring_reason = f"{repo_norm} is on github_ignored_repos"
        elif claimed_by_project and project_status and project_status != "active":
            monitoring_reason = (
                f"claimed by project '{claimed_by_project}' but status="
                f"{project_status!r} (only active projects sync)"
            )
        elif not in_registry and not in_recent_activity:
            monitoring_reason = (
                "not in any active project's repos and no events in github_activity "
                "in the last 14 days"
            )
        else:
            monitoring_reason = "not in watched set"

    # Stage 3 — sync freshness --------------------------------------------
    counts = {"items": 0, "commits": 0, "comments": 0, "documents": 0}
    last_synced: str | None = None
    default_branch: str | None = None
    repo_meta_fetched_at: str | None = None
    try:
        with db_connection(database_path) as conn:
            row = conn.execute(
                "SELECT default_branch, fetched_at FROM github_repo_meta "
                "WHERE LOWER(repo_full_name) = ?",
                (repo_norm,),
            ).fetchone()
            if row:
                default_branch = row["default_branch"]
                repo_meta_fetched_at = row["fetched_at"]

            for table, key in (
                ("github_items", "items"),
                ("github_commits", "commits"),
                ("github_comments", "comments"),
                ("github_documents", "documents"),
            ):
                row = conn.execute(
                    f"SELECT COUNT(*) AS c, MAX(fetched_at) AS m FROM {table} "
                    f"WHERE LOWER(repo_full_name) = ?",
                    (repo_norm,),
                ).fetchone()
                if row:
                    counts[key] = int(row["c"] or 0)
                    candidate = row["m"]
                    if candidate and (not last_synced or candidate > last_synced):
                        last_synced = candidate
    except Exception as exc:
        # Don't blow up — surface as a diagnostic.
        last_synced = None
        counts["__db_error__"] = str(exc)  # type: ignore[assignment]

    if not last_synced and repo_meta_fetched_at:
        last_synced = repo_meta_fetched_at

    staleness_days = _days_since(last_synced)
    if last_synced is None:
        freshness = "never_synced"
    elif staleness_days is not None and staleness_days > DEFAULT_SYNC_WINDOW_DAYS:
        freshness = "stale"
    else:
        freshness = "fresh"

    # Stage 4 — sha lookup -------------------------------------------------
    commit_block: dict[str, Any] | None = None
    if sha:
        sha_clean = sha.strip().lower()
        commit_block = {"sha_query": sha_clean, "found_in_db": False}
        try:
            with db_connection(database_path) as conn:
                rows = conn.execute(
                    "SELECT sha, item_type, item_number, author_login, "
                    "       committed_at, message, html_url "
                    "FROM github_commits "
                    "WHERE LOWER(repo_full_name) = ? AND LOWER(sha) LIKE ? "
                    "LIMIT 5",
                    (repo_norm, f"{sha_clean}%"),
                ).fetchall()
                if rows:
                    commit_block["found_in_db"] = True
                    commit_block["matches"] = [
                        {
                            "sha": r["sha"],
                            "associated": f"{r['item_type']}#{r['item_number']}",
                            "author": r["author_login"],
                            "committed_at": r["committed_at"],
                            "message_first_line": (r["message"] or "").splitlines()[0][:200] if r["message"] else "",
                            "html_url": r["html_url"],
                        }
                        for r in rows
                    ]
                    if len(rows) > 1:
                        commit_block["ambiguous"] = True
        except Exception as exc:
            commit_block["db_error"] = str(exc)

        if not commit_block["found_in_db"]:
            if not watched:
                commit_block["likely_cause"] = (
                    "repo is not watched, so its commits are never ingested"
                )
            elif freshness == "never_synced":
                commit_block["likely_cause"] = (
                    "repo is watched but has never been synced — "
                    "run refresh_index(scope=['github'])"
                )
            else:
                commit_block["likely_cause"] = (
                    "current pipeline only ingests commits referenced by PRs in the "
                    f"{DEFAULT_SYNC_WINDOW_DAYS}-day lookback. A bare commit on a "
                    "branch with no PR (or one outside the window) will not appear."
                )

    # Stage 5 — pr lookup --------------------------------------------------
    pr_block: dict[str, Any] | None = None
    if pr is not None:
        try:
            pr_num = int(pr)
        except (TypeError, ValueError):
            pr_block = {"error": f"pr must be an integer, got {pr!r}"}
        else:
            pr_block = {"number": pr_num, "found_in_db": False}
            try:
                with db_connection(database_path) as conn:
                    row = conn.execute(
                        "SELECT title, state, is_merged, author_login, created_at, "
                        "       updated_at, merged_at, comments_count, "
                        "       commits_count, fetched_at, html_url "
                        "FROM github_items "
                        "WHERE LOWER(repo_full_name) = ? "
                        "  AND item_type = 'pull_request' AND number = ?",
                        (repo_norm, pr_num),
                    ).fetchone()
                    if row:
                        pr_block["found_in_db"] = True
                        pr_block["state"] = row["state"]
                        pr_block["merged"] = bool(row["is_merged"])
                        pr_block["title"] = row["title"]
                        pr_block["author"] = row["author_login"]
                        pr_block["created_at"] = row["created_at"]
                        pr_block["updated_at"] = row["updated_at"]
                        pr_block["merged_at"] = row["merged_at"]
                        pr_block["comments_count"] = row["comments_count"]
                        pr_block["commits_count"] = row["commits_count"]
                        pr_block["fetched_at"] = row["fetched_at"]
                        pr_block["html_url"] = row["html_url"]
            except Exception as exc:
                pr_block["db_error"] = str(exc)

            if not pr_block.get("found_in_db"):
                if not watched:
                    pr_block["likely_cause"] = (
                        "repo is not watched, so its PRs are never ingested"
                    )
                elif freshness == "never_synced":
                    pr_block["likely_cause"] = (
                        "repo is watched but has never been synced — "
                        "run refresh_index(scope=['github'])"
                    )
                else:
                    pr_block["likely_cause"] = (
                        f"PR may have last been updated more than "
                        f"{DEFAULT_SYNC_WINDOW_DAYS} days ago and fallen outside the "
                        "sync window, or the repo wasn't watched at the time of the "
                        "last refresh"
                    )

    # Stage 6 — live PAT visibility --------------------------------------
    pat_block: dict[str, Any] = {"checked": False}
    if live:
        token = get_github_token()
        if not token:
            pat_block = {"checked": True, "can_see": False, "error": "no GitHub token configured"}
        else:
            probe = _live_probe_repo(repo_norm, token)
            pat_block = {"checked": True, **probe}
            if sha and isinstance(commit_block, dict):
                commit_block["live"] = _live_probe_commit(repo_norm, sha.strip(), token)
            if pr is not None and isinstance(pr_block, dict) and "error" not in pr_block:
                try:
                    pr_block["live"] = _live_probe_pr(repo_norm, int(pr), token)
                except (TypeError, ValueError):
                    pass

    # Verdict + summary ---------------------------------------------------
    next_actions: list[str] = []
    if is_ignored:
        verdict = "not_watched_ignored"
        summary = f"{repo_norm} is on the ignored list — remove it to start syncing."
        next_actions.append("remove_github_ignored_repo(repo)")
    elif claimed_by_project and project_status and project_status != "active":
        verdict = "not_watched_inactive_project"
        summary = (
            f"{repo_norm} is claimed by project {claimed_by_project!r} but its "
            f"status is {project_status!r}; only active projects are synced."
        )
        next_actions.append(f"set project {claimed_by_project!r} status to 'active'")
    elif not watched:
        verdict = "not_watched_no_signal"
        summary = (
            f"{repo_norm} is not watched: not in any active project's repos and no "
            "events seen in the last 14 days."
        )
        next_actions.append(
            "add the repo to an active project's repos[] in the registry"
        )
    elif freshness == "never_synced":
        verdict = "watched_never_synced"
        summary = f"{repo_norm} is watched but has never been synced."
        next_actions.append("refresh_index(scope=['github'])")
    elif freshness == "stale":
        verdict = "watched_but_stale"
        summary = (
            f"{repo_norm} is watched; last synced {staleness_days} days ago "
            f"(> {DEFAULT_SYNC_WINDOW_DAYS}d window)."
        )
        next_actions.append(f"refresh_index(scope=['github'], repos=['{repo_norm}'])")
    else:
        verdict = "watched_and_fresh"
        summary = (
            f"{repo_norm} is watched; last synced {staleness_days} days ago. "
            f"items={counts['items']} commits={counts['commits']} "
            f"comments={counts['comments']} documents={counts['documents']}."
        )

    if live and pat_block.get("checked") and pat_block.get("can_see") is False:
        next_actions.insert(
            0,
            "GitHub PAT cannot see this repo — check token scopes or org SSO authorization",
        )

    return {
        "repo": repo_norm,
        "verdict": verdict,
        "summary": summary,
        "monitoring": {
            "watched": watched,
            "in_registry": in_registry,
            "in_recent_activity": in_recent_activity,
            "ignored": is_ignored,
            "claimed_by_project": claimed_by_project,
            "project_status": project_status,
            "reason": monitoring_reason,
        },
        "sync": {
            "last_synced": last_synced,
            "staleness_days": staleness_days,
            "freshness": freshness,
            "counts": counts,
            "default_branch": default_branch,
            "sync_window_days": DEFAULT_SYNC_WINDOW_DAYS,
        },
        "commit": commit_block,
        "pr": pr_block,
        "pat": pat_block,
        "next_actions": next_actions,
    }
