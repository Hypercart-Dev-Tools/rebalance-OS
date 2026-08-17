"""
GitHub activity scanner — ported from gitdaily (TypeScript → Python).

Design notes mirrored from gitdaily/src/lib/github-api.ts:
- PAT auth via "Authorization: token {token}" header
- GitHub Events API caps at 3 pages (300 events); page 4 returns 422
- Cutoff: don't collect events older than `days` days
- Rate-limit detection: HTTP 403 or 429

Usage:
    from rebalance.ingest.github_scan import scan_github, upsert_github_activity
    result = scan_github(token="ghp_...", days=14)
    upsert_github_activity(Path("rebalance.db"), result)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from rebalance.ingest.config import normalize_github_repo_name
from rebalance.ingest._http import GITHUB_API, GitHubClient, _is_rate_limit

logger = logging.getLogger(__name__)

MAX_EVENT_PAGES = 3  # Hard limit documented by GitHub

# Activity band definitions — shared with preflight.py for segmentation.
#   A = last 7 days   (hot)
#   B = 8-14 days ago  (warm)
#   C = 15-30 days ago (cooling)
BAND_A_DAYS = 7
BAND_B_DAYS = 14
BAND_C_DAYS = 30


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RepoActivity:
    repo_full_name: str
    commits: int = 0
    pushes: int = 0
    prs_opened: int = 0
    prs_merged: int = 0
    issues_opened: int = 0
    issue_comments: int = 0
    reviews: int = 0
    last_active_at: str | None = None  # ISO 8601
    active_bands: set[str] = field(default_factory=set)  # A=0-7d, B=8-14d, C=15-30d

    def as_dict(self) -> dict[str, Any]:
        return {
            "repo_full_name": self.repo_full_name,
            "commits": self.commits,
            "pushes": self.pushes,
            "prs_opened": self.prs_opened,
            "prs_merged": self.prs_merged,
            "issues_opened": self.issues_opened,
            "issue_comments": self.issue_comments,
            "reviews": self.reviews,
            "last_active_at": self.last_active_at,
        }

    def work_event_count(self) -> int:
        """Count contribution-style events; passive events like stars do not qualify."""
        return (
            self.commits
            + self.pushes
            + self.prs_opened
            + self.prs_merged
            + self.issues_opened
            + self.issue_comments
            + self.reviews
        )


@dataclass
class GitHubScanResult:
    login: str
    scanned_at: str          # ISO 8601
    days_fetched: int
    total_events: int
    repo_activity: dict[str, RepoActivity] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


class GitHubApiError(Exception):
    def __init__(self, message: str, status: int, is_rate_limit: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.is_rate_limit = is_rate_limit


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _client(token: str) -> GitHubClient:
    """Return a GitHubClient — wrapper kept so callers needn't import the type."""
    return GitHubClient(token)


def _get(url: str, token: str) -> tuple[int, Any]:
    """Minimal HTTP GET — returns (status_code, parsed_json_or_None).

    Thin wrapper retained for callers within this module; new code should use
    a long-lived :class:`GitHubClient` instead.
    """
    return _client(token).get(url)


def _cutoff_key(days: int) -> str:
    """Return YYYY-MM-DD threshold for event filtering (local timezone)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%d")


def _event_day_key(created_at: str) -> str:
    """Parse ISO 8601 event timestamp to YYYY-MM-DD (UTC)."""
    return created_at[:10]


def _compute_band_cutoffs(now: datetime) -> tuple[str, str, str]:
    """Return (cutoff_A, cutoff_B, cutoff_C) as YYYY-MM-DD strings."""
    fmt = "%Y-%m-%d"
    return (
        (now - timedelta(days=BAND_A_DAYS)).strftime(fmt),
        (now - timedelta(days=BAND_B_DAYS)).strftime(fmt),
        (now - timedelta(days=BAND_C_DAYS)).strftime(fmt),
    )


def _band_for_event(event_day: str, cutoff_7d: str, cutoff_14d: str) -> str:
    """
    Classify an event into a time band.
      A = last 7 days
      B = 8-14 days ago
      C = 15-30 days ago (events older than 30d are already filtered by _fetch_events)
    """
    if event_day >= cutoff_7d:
        return "A"
    if event_day >= cutoff_14d:
        return "B"
    return "C"


def _extract_commit_title(message: Any) -> str | None:
    """First non-empty line of a commit message (mirrors gitdaily extractCommitTitle)."""
    if not isinstance(message, str):
        return None
    first_line = message.split("\n")[0].strip()
    return first_line if first_line else None


def _get_login(token: str) -> str:
    status, data, headers = _client(token).get_with_headers(f"{GITHUB_API}/user")
    if status == 403 or status == 429:
        # A 403 is NOT necessarily a rate limit — GitHub also returns it for
        # SAML/SSO authorization, missing scopes, and IP allowlist blocks.
        # _is_rate_limit() reads the headers that actually distinguish them
        # (x-ratelimit-remaining: 0 = primary, retry-after = secondary).
        # Log the discriminating fields either way so the next failure is
        # diagnosable from the log rather than re-derived from scratch.
        rate_limited = _is_rate_limit(status, headers)
        logger.warning(
            "GitHub /user -> %s (rate_limit=%s) remaining=%s used=%s "
            "retry_after=%s reset=%s resource=%s",
            status,
            rate_limited,
            headers.get("x-ratelimit-remaining", "?"),
            headers.get("x-ratelimit-used", "?"),
            headers.get("retry-after", "-"),
            headers.get("x-ratelimit-reset", "?"),
            headers.get("x-ratelimit-resource", "?"),
        )
        if rate_limited:
            kind = "secondary" if "retry-after" in headers else "primary"
            raise GitHubApiError(
                f"Rate limited fetching /user ({kind}; "
                f"remaining={headers.get('x-ratelimit-remaining', '?')}, "
                f"retry_after={headers.get('retry-after', '-')})",
                status,
                is_rate_limit=True,
            )
        raise GitHubApiError(
            f"Forbidden fetching /user: HTTP {status} — not a rate limit "
            f"(check SSO authorization, PAT scopes, IP allowlist)",
            status,
        )
    if status == 401:
        # Authoritative deauth signal: the PAT was revoked, expired, or lost a
        # required scope. Log it to the unified auth trail before raising.
        from rebalance.ingest import auth_log
        auth_log.log_github_auth_failed(status, endpoint="/user")
    if status != 200 or not isinstance(data, dict):
        raise GitHubApiError(f"Failed to fetch /user: HTTP {status}", status)
    login = data.get("login")
    if not login:
        raise GitHubApiError("No login in /user response", 500)
    return login


def _fetch_events(login: str, token: str, days: int = 30) -> list[dict[str, Any]]:
    """
    Fetch paginated user events up to MAX_EVENT_PAGES.
    Stops early once events older than `days` days are encountered.
    Mirrors gitdaily fetchEvents().
    """
    cutoff = _cutoff_key(days)
    all_events: list[dict[str, Any]] = []
    reached_cutoff = False

    for page in range(1, MAX_EVENT_PAGES + 1):
        if reached_cutoff:
            break

        url = f"{GITHUB_API}/users/{login}/events?per_page=100&page={page}"
        status, data = _get(url, token)

        # GitHub returns 422 when page limit is exceeded
        if status == 422:
            break

        if status == 403 or status == 429:
            raise GitHubApiError(
                f"Rate limited fetching events page {page}", status, is_rate_limit=True
            )

        if status != 200 or not isinstance(data, list):
            raise GitHubApiError(f"Failed to fetch events page {page}: HTTP {status}", status)

        page_events: list[dict[str, Any]] = data

        for event in page_events:
            day_key = _event_day_key(event.get("created_at", ""))
            if day_key < cutoff:
                reached_cutoff = True
                break
            all_events.append(event)

        if len(page_events) < 100:
            break  # last page

    return all_events


# ---------------------------------------------------------------------------
# Event aggregation
# ---------------------------------------------------------------------------

def _summarize_by_repo(
    events: list[dict[str, Any]],
    cutoff_7d: str | None = None,
    cutoff_14d: str | None = None,
) -> dict[str, RepoActivity]:
    """
    Aggregate raw GitHub events into per-repo activity counters.
    Event type mapping mirrors gitdaily getEventTypeLabel() + activity-mappers.ts.

    If cutoff_7d and cutoff_14d are provided, each event is classified into a
    time band (A/B/C) and recorded in RepoActivity.active_bands.
    """
    activity: dict[str, RepoActivity] = {}

    work_event_types = {
        "PushEvent",
        "PullRequestEvent",
        "IssuesEvent",
        "IssueCommentEvent",
        "PullRequestReviewEvent",
        "PullRequestReviewCommentEvent",
    }

    for event in events:
        repo_full_name: str = event.get("repo", {}).get("name", "unknown/unknown")
        event_type: str = event.get("type", "")
        payload: dict[str, Any] = event.get("payload", {})
        created_at: str | None = event.get("created_at")

        if event_type not in work_event_types:
            continue

        if repo_full_name not in activity:
            activity[repo_full_name] = RepoActivity(repo_full_name=repo_full_name)

        r = activity[repo_full_name]

        # Update last_active_at (events are newest-first from GitHub API)
        if created_at and (r.last_active_at is None or created_at > r.last_active_at):
            r.last_active_at = created_at

        # Track which time band this event falls in
        if created_at and cutoff_7d and cutoff_14d:
            day_key = _event_day_key(created_at)
            r.active_bands.add(_band_for_event(day_key, cutoff_7d, cutoff_14d))

        if event_type == "PushEvent":
            r.pushes += 1
            commits = payload.get("commits")
            if isinstance(commits, list):
                r.commits += len(commits)
            elif isinstance(payload.get("size"), int) and payload["size"] > 0:
                r.commits += payload["size"]
            else:
                r.commits += 1  # at least one commit implied by push

        elif event_type == "PullRequestEvent":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            if action == "opened":
                r.prs_opened += 1
            elif action == "closed" and pr.get("merged_at"):
                r.prs_merged += 1

        elif event_type == "IssuesEvent":
            if payload.get("action") == "opened":
                r.issues_opened += 1

        elif event_type == "IssueCommentEvent":
            r.issue_comments += 1

        elif event_type in ("PullRequestReviewEvent", "PullRequestReviewCommentEvent"):
            r.reviews += 1

    return activity


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_github_token(token: str) -> dict[str, Any]:
    """
    Validate a GitHub PAT against /user and return login + scopes.

    Returns:
        {"valid": True, "login": "...", "scopes": ["repo", ...]}
        or {"valid": False, "login": "", "scopes": [], "error": "..."}
    """
    # No retries: a bad token should fail fast for the onboarding flow.
    from rebalance.ingest import auth_log

    status, data, headers = GitHubClient(token, retries=1).get_with_headers("/user")
    if status == 200 and isinstance(data, dict):
        scopes_header = headers.get("x-oauth-scopes", "")
        scopes = [s.strip() for s in scopes_header.split(",") if s.strip()]
        login = data.get("login", "")
        auth_log.log_github_token_validated(login, scopes)
        return {"valid": True, "login": login, "scopes": scopes, "status": status}
    auth_log.log_github_token_invalid(status)
    return {"valid": False, "login": "", "scopes": [], "error": f"HTTP {status}", "status": status}


def token_visibility_warning(token: str, scopes: list[str]) -> str | None:
    """Warn when a valid token likely can't see private repositories.

    The docs used to name a nonexistent ``repo:read`` scope, which steered
    users to public-only tokens (classic ``public_repo``, or the fine-grained
    "Public repositories" default) — discovery then silently missed all
    their private work. Heuristics:

    - classic tokens report scopes via ``x-oauth-scopes``: anything without
      ``repo`` is public-only for our purposes
    - fine-grained tokens (``github_pat_``) report NO scopes header, so
      visibility can't be verified remotely — surface the default-trap
      advisory instead
    """
    if scopes:  # classic token — scopes are authoritative
        if "repo" in scopes:
            return None
        return (
            f"classic token without the `repo` scope (has: {', '.join(scopes)}) — "
            "private repositories are INVISIBLE to discovery and github-scan. "
            "Re-issue with the `repo` scope, or use a fine-grained token with "
            "All-repos read-only Contents/Metadata."
        )
    if token.startswith("github_pat_"):
        return (
            "fine-grained token — GitHub doesn't expose its repository access "
            "remotely. Confirm Repository access was changed from the default "
            "'Public repositories' to All/selected repositories, or your "
            "private work stays invisible to discovery."
        )
    return None  # gho_/other ambient tokens: no scopes header, no verdict


def resolve_working_token(primary_token: str) -> str:
    """Return a GitHub token that currently authenticates, falling back to gh CLI.

    If *primary_token* validates, it is returned unchanged. If it is rejected
    with **401** (revoked / expired / deauthorized PAT) *and* the host is
    authorized for the ``gh`` CLI, fall back to gh's token (option A), then
    persist it to keyring + ``rbos.config`` so background launchd jobs recover
    too (option D), and return it. Any other failure (rate-limit 403/429, no gh
    login, gh token also invalid, network error) returns the primary token
    unchanged so the caller surfaces the real error — this never makes a refresh
    worse than before.

    The gh fallback only resolves interactively: launchd's stripped environment
    cannot run ``gh``, so background jobs get the persisted token from a prior
    interactive heal instead.
    """
    if not primary_token:
        return primary_token
    try:
        check = validate_github_token(primary_token)
        if check.get("valid"):
            return primary_token
        if check.get("status") != 401:
            return primary_token  # rate-limit / transient — not a deauth
        from rebalance.ingest import auth_log, config

        gh_token = config.get_github_token_via_gh()
        if not gh_token or gh_token == primary_token:
            return primary_token  # no usable backup
        gh_check = validate_github_token(gh_token)
        if not gh_check.get("valid"):
            return primary_token  # gh's token is no good either
        logger.warning(
            "GitHub PAT rejected (401); fell back to the gh CLI token and "
            "persisted it (keyring + config) so background jobs recover."
        )
        auth_log.log_github_gh_fallback(gh_check.get("login", ""))
        config.set_github_token(gh_token, source="gh-fallback")  # option D: heal the persisted copy
        return gh_token
    except Exception:  # noqa: BLE001 — resolution must never break the refresh
        return primary_token


def scan_and_store_github_activity(
    database_path: Path,
    *,
    token: str,
    since_days: int,
    ignored_repos: list[str] | None = None,
) -> tuple[GitHubScanResult, list[str]]:
    """Source-owned entry point for the GitHub activity scan: scan -> filter
    ignored repos -> upsert. CLI `github-scan` (and any collector) share this so
    no surface imports the leaf scan_github / upsert_github_activity directly
    (COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2). Returns (result, skipped_repos).
    """
    if ignored_repos is None:
        from rebalance.ingest.config import get_github_ignored_repos
        ignored_repos = get_github_ignored_repos()
    result = scan_github(token=token, days=since_days)
    skipped = filter_ignored_repo_activity(result, ignored_repos)
    upsert_github_activity(database_path, result)
    return result, skipped


def scan_github(token: str, days: int = 30) -> GitHubScanResult:
    """
    Authenticate, fetch events, and return aggregated per-repo activity.

    Args:
        token: GitHub Personal Access Token (read:user + repo scopes).
        days:  How many calendar days to look back. Defaults to 30 to support
               A/B/C band classification (0-7d, 8-14d, 15-30d).

    Returns:
        GitHubScanResult with per-repo activity breakdown.
    """
    login = _get_login(token)
    now = datetime.now(timezone.utc)
    cutoff_7d, cutoff_14d, _ = _compute_band_cutoffs(now)
    events = _fetch_events(login, token, days=days)
    repo_activity = _summarize_by_repo(events, cutoff_7d=cutoff_7d, cutoff_14d=cutoff_14d)

    return GitHubScanResult(
        login=login,
        scanned_at=datetime.now(timezone.utc).isoformat(),
        days_fetched=days,
        total_events=len(events),
        repo_activity=repo_activity,
        events=events,
    )


# ---------------------------------------------------------------------------
# SQLite persistence
# ---------------------------------------------------------------------------

_UPSERT_SQL = """
INSERT OR REPLACE INTO github_activity
    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def upsert_github_activity(database_path: Path, result: GitHubScanResult) -> None:
    """Persist a GitHubScanResult into the github_activity SQLite table."""
    from rebalance.ingest.db import db_connection, ensure_github_schema

    scan_date = result.scanned_at[:10]  # YYYY-MM-DD

    with db_connection(database_path, ensure_github_schema) as conn:
        for r in result.repo_activity.values():
            if r.work_event_count() <= 0:
                continue
            conn.execute(
                _UPSERT_SQL,
                (
                    result.login,
                    r.repo_full_name,
                    scan_date,
                    r.commits,
                    r.pushes,
                    r.prs_opened,
                    r.prs_merged,
                    r.issues_opened,
                    r.issue_comments,
                    r.reviews,
                    r.last_active_at,
                    result.scanned_at,
                ),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Pushed-repos discovery — more reliable than the events feed for catching
# pushes the operator wasn't the actor on, or that the events API dropped.
# ---------------------------------------------------------------------------

@dataclass
class PushedRepoRecord:
    repo_full_name: str
    pushed_at: str  # ISO 8601 from GitHub
    private: bool = False
    fork: bool = False
    archived: bool = False
    disabled: bool = False


@dataclass
class PushedReposSyncResult:
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_archived: int = 0
    error: str | None = None


def fetch_pushed_repos(token: str, *, per_page: int = 30) -> list[PushedRepoRecord]:
    """Fetch the most-recently-pushed repos accessible to the PAT.

    Hits /user/repos?sort=pushed&direction=desc&per_page=N. One API request.
    Returns up to *per_page* repos sorted by pushed_at desc, including
    archived/disabled — the caller decides what to do with them.

    Used for auto-discovery (sync_pushed_repos) and for the `rebalance raw`
    diagnostic. More reliable than /users/{login}/events for catching recent
    pushes: it returns repos regardless of actor and is unaffected by the
    300-event pagination cap or eventual-consistency gaps on private org
    repos that the events feed exhibits.
    """
    status, data = _get(
        f"{GITHUB_API}/user/repos?sort=pushed&direction=desc&per_page={per_page}",
        token,
    )
    if status != 200 or not isinstance(data, list):
        raise GitHubApiError(
            f"Failed to fetch /user/repos?sort=pushed: HTTP {status}",
            status,
            is_rate_limit=(status in (403, 429)),
        )
    out: list[PushedRepoRecord] = []
    for r in data:
        full = r.get("full_name") or ""
        pushed = r.get("pushed_at") or ""
        if not full or not pushed:
            continue
        out.append(PushedRepoRecord(
            repo_full_name=full,
            pushed_at=pushed,
            private=bool(r.get("private")),
            fork=bool(r.get("fork")),
            archived=bool(r.get("archived")),
            disabled=bool(r.get("disabled")),
        ))
    return out


def sync_pushed_repos(
    database_path: Path,
    token: str,
    *,
    per_page: int = 30,
) -> PushedReposSyncResult:
    """Fetch /user/repos?sort=pushed and upsert into github_pushed_repos.

    Skips archived/disabled repos — we don't want them in the auto-discovery
    watched set. Idempotent: re-running with the same data yields all-unchanged
    counts. Errors are returned in the result rather than raised so callers in
    the refresh pipeline don't have to wrap individual sources in try/except.
    """
    from rebalance.ingest.db import db_connection, ensure_github_schema

    result = PushedReposSyncResult()
    try:
        records = fetch_pushed_repos(token, per_page=per_page)
    except Exception as exc:
        result.error = f"fetch failed: {exc}"
        return result

    result.fetched = len(records)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with db_connection(database_path, ensure_github_schema) as conn:
        for rec in records:
            if rec.archived or rec.disabled:
                result.skipped_archived += 1
                continue
            existing = conn.execute(
                "SELECT pushed_at, private, fork FROM github_pushed_repos "
                "WHERE repo_full_name = ?",
                (rec.repo_full_name,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO github_pushed_repos
                        (repo_full_name, pushed_at, private, fork,
                         archived, disabled, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rec.repo_full_name, rec.pushed_at,
                        int(rec.private), int(rec.fork),
                        int(rec.archived), int(rec.disabled),
                        now, now,
                    ),
                )
                result.inserted += 1
                continue
            same = (
                existing["pushed_at"] == rec.pushed_at
                and bool(existing["private"]) == rec.private
                and bool(existing["fork"]) == rec.fork
            )
            if same:
                conn.execute(
                    "UPDATE github_pushed_repos SET last_seen_at = ? "
                    "WHERE repo_full_name = ?",
                    (now, rec.repo_full_name),
                )
                result.unchanged += 1
            else:
                conn.execute(
                    """
                    UPDATE github_pushed_repos
                    SET pushed_at = ?, private = ?, fork = ?,
                        archived = ?, disabled = ?, last_seen_at = ?
                    WHERE repo_full_name = ?
                    """,
                    (
                        rec.pushed_at, int(rec.private), int(rec.fork),
                        int(rec.archived), int(rec.disabled),
                        now, rec.repo_full_name,
                    ),
                )
                result.updated += 1
        conn.commit()

    return result


def filter_ignored_repo_activity(result: GitHubScanResult, ignored_repos: list[str]) -> list[str]:
    """Remove ignored repos from a scan result in place and return the skipped set."""
    ignored = {normalize_github_repo_name(repo) for repo in ignored_repos}
    if not ignored:
        return []

    kept: dict[str, RepoActivity] = {}
    skipped: list[str] = []
    for repo_full_name, activity in result.repo_activity.items():
        normalized = normalize_github_repo_name(repo_full_name)
        if normalized in ignored:
            if normalized not in skipped:
                skipped.append(normalized)
            continue
        kept[repo_full_name] = activity

    result.repo_activity = kept
    return sorted(skipped)


# ---------------------------------------------------------------------------
# Balance query — used by MCP tool
# ---------------------------------------------------------------------------

def get_github_balance(
    database_path: Path,
    project_repos: dict[str, list[str]],
    since_days: int = 14,
) -> list[dict[str, Any]]:
    """
    Return GitHub activity summary per project using the project→repos mapping.

    Args:
        database_path:  Path to the SQLite database.
        project_repos:  {project_name: [repo_full_name, ...]} mapping.
        since_days:     How many days back to aggregate.

    Returns:
        List of dicts with project_name, total_commits, prs_opened, prs_merged,
        issues_opened, last_active_at, repos_touched.
    """
    if not database_path.exists():
        return []

    from rebalance.ingest.db import db_connection, ensure_github_schema

    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")

    with db_connection(database_path, ensure_github_schema) as conn:
        rows = conn.execute(
            """
            SELECT repo_full_name,
                   SUM(commits)       AS commits,
                   SUM(pushes)        AS pushes,
                   SUM(prs_opened)    AS prs_opened,
                   SUM(prs_merged)    AS prs_merged,
                   SUM(issues_opened) AS issues_opened,
                   SUM(issue_comments) AS issue_comments,
                   SUM(reviews)       AS reviews,
                   MAX(last_active_at) AS last_active_at
            FROM github_activity
            WHERE scan_date >= ?
            GROUP BY repo_full_name
            """,
            (since_date,),
        ).fetchall()

    # Build lookup: repo_full_name → aggregated activity row
    repo_stats: dict[str, dict[str, Any]] = {
        row["repo_full_name"]: dict(row) for row in rows
    }

    results: list[dict[str, Any]] = []
    for project_name, repos in project_repos.items():
        total_commits = 0
        total_prs_opened = 0
        total_prs_merged = 0
        total_issues = 0
        repos_touched: list[str] = []
        last_active: str | None = None

        for repo in repos:
            stats = repo_stats.get(repo)
            if not stats:
                continue
            repos_touched.append(repo)
            total_commits += stats.get("commits") or 0
            total_prs_opened += stats.get("prs_opened") or 0
            total_prs_merged += stats.get("prs_merged") or 0
            total_issues += stats.get("issues_opened") or 0
            la = stats.get("last_active_at")
            if la and (last_active is None or la > last_active):
                last_active = la

        results.append({
            "project_name": project_name,
            "repos_linked": repos,
            "repos_touched": repos_touched,
            "total_commits": total_commits,
            "prs_opened": total_prs_opened,
            "prs_merged": total_prs_merged,
            "issues_opened": total_issues,
            "last_active_at": last_active,
            "is_idle": len(repos_touched) == 0,
        })

    # Sort: active projects first, then by last_active_at descending
    results.sort(key=lambda x: (x["is_idle"], -(len(x["repos_touched"]))), reverse=False)
    return results


# ---------------------------------------------------------------------------
# Preflight discovery — GitHub repositories
# ---------------------------------------------------------------------------

@dataclass
class RepoCandidate:
    """A repository discovered from recent GitHub activity."""
    repo_full_name: str
    last_active_at: str | None
    activity_score: int  # Total events in scan window
    commit_count: int
    bands: list[str] = field(default_factory=list)  # e.g. ["A", "B", "C"]


def discover_repos_from_activity(
    token: str,
    days: int = 30,
) -> list[RepoCandidate]:
    """
    Scan GitHub activity for the past N days and return discovered repositories
    as candidates for the project registry.

    Defaults to 30 days to support A/B/C band classification:
      A = last 7 days, B = 8-14 days ago, C = 15-30 days ago.

    Returns:
        List of RepoCandidate sorted by activity_score (descending).
    """
    result = scan_github(token=token, days=days)

    candidates: list[RepoCandidate] = []
    for repo_name, activity in result.repo_activity.items():
        score = (
            activity.commits
            + activity.pushes
            + activity.prs_opened
            + activity.prs_merged
            + activity.issues_opened
            + activity.issue_comments
            + activity.reviews
        )

        candidates.append(
            RepoCandidate(
                repo_full_name=repo_name,
                last_active_at=activity.last_active_at,
                activity_score=score,
                commit_count=activity.commits,
                bands=sorted(activity.active_bands),
            )
        )

    # Sort by activity score descending
    candidates.sort(key=lambda x: x.activity_score, reverse=True)
    return candidates
