"""Hourly pulse: render today's + yesterday's activity into a markdown
status page and publish it to a private git repo.

Reusable design — every per-user value (Slack ID, GitHub login, target repo
path, timezone) comes from ``temp/rbos.config``. Other people forking this
repo can populate their own config and point at their own private pulse repo;
no per-user data is hardcoded here.

Data sources:
  - Vault edits:        ``vault_files.last_modified``
  - GitHub commits:     ``github_commits`` (authored by ``github_login``)
  - GitHub issues/PRs:  ``github_items`` created or updated today by user
  - GitHub comments:    ``github_comments`` posted by user
  - Sleuth reminders:   assigned to the operator OR assigned by the operator
  - Calendar events:    ``calendar_events`` (today's upcoming)
  - Assigned issues:    GitHub search API, fetched fresh each run
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from rebalance.repair import RepairFSM, RepairResult, RepairStatus
from rebalance.ingest.agent_tags import classify as classify_source
from rebalance.ingest.calendar_config import OPERATOR_CALENDAR_ID
from rebalance.ingest.calendar_helpers import calendar_dt_utc, normalize_aware_utc
from rebalance.ingest.config import get_github_token, get_pulse_config
from rebalance.ingest.db import db_connection
from rebalance.ingest.slack_users import compact_sleuth_reminder
from rebalance.tz_utils import format_local, local_tz, parse_utc_iso
from rebalance.lib.time_ops import _parse_iso


# Author logins of known cloud-agent bots. Mirrors agent_tags.py — kept here
# for SQL-side prefiltering so we don't fetch every bot row in the DB.
CLOUD_AGENT_AUTHORS: tuple[str, ...] = (
    "lovable-dev[bot]",
    "lovable[bot]",
    "chatgpt-codex-connector[bot]",
    "codex-bot[bot]",
    "claude[bot]",
    "claude-bot[bot]",
)


class PulseReconcileError(RuntimeError):
    """The pulse export mirror could not be reconciled with origin (GH-152)."""


def reconcile_pulse_mirror(target_path: Path) -> None:
    """Fetch origin and rebase the local pulse mirror onto it.

    Keeps the dashboard-read mirror fresh without discarding local pulse-write
    commits (rebase replays them onto origin). Without this, ``pulse_sync`` only
    writes/commits/pushes and never pulls, so the mirror freezes and every
    freshness signal read from it reports live collectors as stale (GH-152).

    Raises ``PulseReconcileError`` on any failure so the caller can surface it
    loudly — never a silent "fresh" state. The caller decides whether that is
    fatal; a reconcile failure does not corrupt the working tree (a failed
    rebase is aborted here before raising).
    """
    git_dir = target_path / ".git"
    if not git_dir.exists():
        raise PulseReconcileError(f"pulse_target_path is not a git repo: {target_path}")
    # Defer to an operator's in-progress rebase rather than trampling it.
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        raise PulseReconcileError(
            f"a git rebase is already in progress in {target_path}; deferring to operator"
        )
    proc = subprocess.run(
        ["git", "pull", "--rebase"],
        cwd=str(target_path),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        # Restore the repo so a conflicted rebase does not linger for the next run.
        subprocess.run(
            ["git", "rebase", "--abort"], cwd=str(target_path), capture_output=True
        )
        detail = (proc.stderr or proc.stdout).strip()
        raise PulseReconcileError(
            f"git pull --rebase failed (code {proc.returncode}) in {target_path}: {detail}"
        )


def _author_filter_sql(column: str) -> str:
    """SQL fragment matching the user OR any cloud-agent bot author."""
    placeholders = ", ".join("?" for _ in CLOUD_AGENT_AUTHORS)
    return f"(LOWER({column}) = LOWER(?) OR {column} IN ({placeholders}))"


GITHUB_API_ROOT = "https://api.github.com"


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def _resolve_timezone(name: str | None) -> ZoneInfo:
    if name:
        return ZoneInfo(name)
    return local_tz()


def _local_day_bounds(tz: ZoneInfo, now: datetime | None = None) -> tuple[datetime, datetime, datetime]:
    """Return (yesterday_start, today_start, tomorrow_start) in *tz*."""
    now = now or datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    tomorrow_start = today_start + timedelta(days=1)
    return yesterday_start, today_start, tomorrow_start


def _table_exists(conn: Any, name: str) -> bool:
    """True if *name* is a table in the connected DB.

    ``_query_day_activity`` runs on a plain connection whose schema is not
    guaranteed migrated (e.g. a partial-schema fixture, or a DB predating a
    source's table). Optional sources gate their SELECT on this so an absent
    table degrades to "no rows" instead of raising and aborting the whole snapshot.
    """
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _in_window(value: str | None, start: datetime, end: datetime) -> bool:
    """True if *value* (ISO string with TZ) falls in [start, end)."""
    parsed = parse_utc_iso(value)
    if parsed is None:
        return False
    return start <= parsed < end


def _utc_iso_floor(dt: datetime) -> str:
    """Return *dt* as a UTC ISO 8601 string suitable for >= comparisons."""
    return dt.astimezone(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------------------


@dataclass
class DayActivity:
    label: str  # "today" or "yesterday"
    vault_edits: list[dict[str, Any]] = field(default_factory=list)
    gh_commits: list[dict[str, Any]] = field(default_factory=list)
    gh_items: list[dict[str, Any]] = field(default_factory=list)
    gh_comments: list[dict[str, Any]] = field(default_factory=list)
    sleuth_activity: list[dict[str, Any]] = field(default_factory=list)
    email_activity: list[dict[str, Any]] = field(default_factory=list)
    figma_activity: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PulseSnapshot:
    generated_at: datetime
    timezone_name: str
    github_login: str
    today: DayActivity
    yesterday: DayActivity
    today_calendar_upcoming: list[dict[str, Any]]
    assigned_issues: list[dict[str, Any]]  # last 7 days, sorted today-first
    notes: list[str]  # diagnostics / soft-warnings (e.g. "search rate-limited")
    # Whole-repo (all-author) activity today on external/watched repos — the repos
    # the operator monitors but doesn't author. Empty when none are configured.
    watched_repos: list[dict[str, Any]] = field(default_factory=list)


def _query_day_activity(
    conn: Any,
    *,
    label: str,
    start: datetime,
    end: datetime,
    github_login: str,
    slack_user_id: str | None,
) -> DayActivity:
    activity = DayActivity(label=label)

    # Pre-filter by a generous UTC window in SQL, refine in Python by tz-aware compare.
    sql_floor = _utc_iso_floor(start - timedelta(hours=2))

    rows = conn.execute(
        """
        SELECT rel_path, title, last_modified
        FROM vault_files
        WHERE last_modified >= ?
        ORDER BY last_modified DESC
        """,
        (sql_floor,),
    ).fetchall()
    for r in rows:
        if _in_window(r["last_modified"], start, end):
            activity.vault_edits.append({
                "rel_path": r["rel_path"],
                "title": r["title"] or r["rel_path"],
                "last_modified": r["last_modified"],
            })

    commit_filter = _author_filter_sql("c.author_login")
    rows = conn.execute(
        f"""
        SELECT c.repo_full_name, c.sha, c.message, c.committed_at, c.html_url,
               c.author_login, gi.head_ref
        FROM github_commits c
        LEFT JOIN github_items gi
          ON gi.repo_full_name = c.repo_full_name
         AND gi.item_type = c.item_type
         AND gi.number = c.item_number
        WHERE c.committed_at >= ?
          AND {commit_filter}
        ORDER BY c.committed_at DESC
        """,
        (sql_floor, github_login, *CLOUD_AGENT_AUTHORS),
    ).fetchall()
    for r in rows:
        if _in_window(r["committed_at"], start, end):
            first_line = (r["message"] or "").splitlines()[0] if r["message"] else ""
            tag = classify_source(
                branch=r["head_ref"],
                author_login=r["author_login"],
                commit_message=r["message"],
            )
            activity.gh_commits.append({
                "repo": r["repo_full_name"],
                "sha": r["sha"][:7] if r["sha"] else "",
                "subject": first_line[:160],
                "committed_at": r["committed_at"],
                "html_url": r["html_url"] or "",
                "author_login": r["author_login"] or "",
                "source_tag": tag,
                "source_kind": "pull_request",
            })

    # Direct branch commits are a distinct raw source. The anti-join means a
    # later-discovered PR commit replaces the visible signal without deleting
    # the direct-push receipt/provenance.
    direct_filter = _author_filter_sql("d.author_login")
    rows = conn.execute(
        f"""
        SELECT d.repo_full_name, d.sha, d.message, d.committed_at, d.html_url,
               d.author_login, d.ref,
               (SELECT GROUP_CONCAT(path, char(10))
                  FROM github_direct_commit_files f
                 WHERE f.repo_full_name = d.repo_full_name AND f.sha = d.sha) AS paths
        FROM github_direct_commits d
        WHERE d.committed_at >= ?
          AND {direct_filter}
          AND NOT EXISTS (
              SELECT 1 FROM github_commits p
              WHERE p.repo_full_name = d.repo_full_name AND p.sha = d.sha
          )
        ORDER BY d.committed_at DESC
        """,
        (sql_floor, github_login, *CLOUD_AGENT_AUTHORS),
    ).fetchall()
    for r in rows:
        if _in_window(r["committed_at"], start, end):
            message = r["message"] or ""
            activity.gh_commits.append({
                "repo": r["repo_full_name"],
                "sha": r["sha"][:7] if r["sha"] else "",
                "subject": message.splitlines()[0][:160] if message else "direct commit",
                "committed_at": r["committed_at"],
                "html_url": r["html_url"] or "",
                "author_login": r["author_login"] or "",
                "paths": (r["paths"] or "").splitlines(),
                "source_tag": classify_source(
                    branch=r["ref"], author_login=r["author_login"], commit_message=message,
                ),
                "source_kind": "direct_push",
            })

    item_filter = _author_filter_sql("author_login")
    rows = conn.execute(
        f"""
        SELECT repo_full_name, item_type, number, title, state, html_url,
               created_at, updated_at, author_login, head_ref, body
        FROM github_items
        WHERE (created_at >= ? OR updated_at >= ?)
          AND (
                {item_filter}
                OR head_ref LIKE 'claude/%'
                OR head_ref LIKE 'codex/%'
                OR head_ref LIKE 'lovable-%'
                OR head_ref LIKE 'lovable/%'
          )
        ORDER BY COALESCE(updated_at, created_at) DESC
        """,
        (sql_floor, sql_floor, github_login, *CLOUD_AGENT_AUTHORS),
    ).fetchall()
    for r in rows:
        created_in = _in_window(r["created_at"], start, end)
        updated_in = _in_window(r["updated_at"], start, end)
        if not (created_in or updated_in):
            continue
        tag = classify_source(
            branch=r["head_ref"],
            author_login=r["author_login"],
            commit_message=r["body"] or "",
        )
        activity.gh_items.append({
            "repo": r["repo_full_name"],
            "item_type": r["item_type"],
            "number": r["number"],
            "title": r["title"] or "",
            "state": r["state"] or "",
            "html_url": r["html_url"] or "",
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "author_login": r["author_login"] or "",
            "head_ref": r["head_ref"] or "",
            "is_new": created_in,
            "source_tag": tag,
        })

    comment_filter = _author_filter_sql("author_login")
    rows = conn.execute(
        f"""
        SELECT repo_full_name, item_type, item_number, comment_type, body,
               html_url, created_at, author_login
        FROM github_comments
        WHERE created_at >= ?
          AND {comment_filter}
        ORDER BY created_at DESC
        """,
        (sql_floor, github_login, *CLOUD_AGENT_AUTHORS),
    ).fetchall()
    for r in rows:
        if _in_window(r["created_at"], start, end):
            body = (r["body"] or "").strip().replace("\r", "")
            preview = body.split("\n", 1)[0][:160]
            tag = classify_source(
                author_login=r["author_login"],
                commit_message=body,
            )
            activity.gh_comments.append({
                "repo": r["repo_full_name"],
                "item_type": r["item_type"],
                "item_number": r["item_number"],
                "comment_type": r["comment_type"] or "",
                "preview": preview,
                "html_url": r["html_url"] or "",
                "created_at": r["created_at"],
                "author_login": r["author_login"] or "",
                "source_tag": tag,
            })

    if slack_user_id and _table_exists(conn, "sleuth_reminders"):
        rows = conn.execute(
            """
            SELECT reminder_id, state, is_active, reminder_message_text,
                   should_post_on, last_seen_at, original_channel_name,
                   github_urls_json, assignee_id, original_sender_id
            FROM sleuth_reminders
            WHERE (assignee_id = ? OR original_sender_id = ?)
              AND last_seen_at >= ?
            ORDER BY last_seen_at DESC
            """,
            (slack_user_id, slack_user_id, sql_floor),
        ).fetchall()
        for r in rows:
            if _in_window(r["last_seen_at"], start, end):
                msg = compact_sleuth_reminder(
                    (r["reminder_message_text"] or "").replace("\n", " ").strip()
                )
                gh_urls = []
                if r["github_urls_json"]:
                    try:
                        gh_urls = json.loads(r["github_urls_json"]) or []
                    except json.JSONDecodeError:
                        gh_urls = []
                activity.sleuth_activity.append({
                    "reminder_id": r["reminder_id"],
                    "state": r["state"] or "",
                    "is_active": bool(r["is_active"]),
                    "message_preview": msg[:200],
                    "channel": r["original_channel_name"] or "",
                    "github_urls": gh_urls,
                    "should_post_on": r["should_post_on"],
                    "last_seen_at": r["last_seen_at"],
                    "assignee_id": r["assignee_id"] or "",
                    "original_sender_id": r["original_sender_id"] or "",
                    "sleuth_role": (
                        "assigned_to_me"
                        if r["assignee_id"] == slack_user_id
                        else "assigned_by_me"
                    ),
                })

    # Email — Gmail-synced messages received in the window. Mirrors the sleuth
    # block: SQL prefilter on the UTC floor, then a tz-aware [start, end) refine.
    # ponytail: `snippet` (message body preview) is deliberately NOT selected. The
    # candidate arm ranks on subject + sender, so the body would be dead weight —
    # and it is the one field here that carries message CONTENT, which the ranker
    # forwards to a cloud model. Not collected until a consumer actually needs it.
    if _table_exists(conn, "email_messages"):
        rows = conn.execute(
            """
            SELECT message_id, from_name, from_address, subject, received_at
            FROM email_messages
            WHERE received_at >= ?
            ORDER BY received_at DESC
            """,
            (sql_floor,),
        ).fetchall()
        for r in rows:
            if _in_window(r["received_at"], start, end):
                activity.email_activity.append({
                    "message_id": r["message_id"],
                    "from_name": r["from_name"] or "",
                    "from_address": r["from_address"] or "",
                    "subject": (r["subject"] or "").replace("\r", " ").strip()[:200],
                    "received_at": r["received_at"],
                })

    # Figma — UNRESOLVED comments created in the window (resolved_at IS NULL).
    # Legitimately empty on the operator's machine until a figma_file_keys
    # allow-list is configured; the collector is opt-in.
    if _table_exists(conn, "figma_comments"):
        rows = conn.execute(
            """
            SELECT comment_key, file_key, message, user_handle, created_at
            FROM figma_comments
            WHERE created_at >= ? AND resolved_at IS NULL
            ORDER BY created_at DESC
            """,
            (sql_floor,),
        ).fetchall()
        for r in rows:
            if _in_window(r["created_at"], start, end):
                activity.figma_activity.append({
                    "comment_key": r["comment_key"],
                    "file_key": r["file_key"],
                    "message": (r["message"] or "").replace("\r", " ").strip()[:200],
                    "user_handle": r["user_handle"] or "",
                    "created_at": r["created_at"],
                })

    return activity


def _query_calendar_upcoming(
    conn: Any,
    *,
    today_start: datetime,
    tomorrow_start: datetime,
    now: datetime,
) -> list[dict[str, Any]]:
    """Today's events with start_time >= now (i.e. still upcoming)."""
    now_utc = normalize_aware_utc(now)
    # Default deny (P2 decision #3): the pulse is committed + pushed off-machine,
    # so only the operator's own calendar (OPERATOR_CALENDAR_ID) may appear here —
    # never a teammate calendar.
    # NOTE (0.40.1, F1): this site previously inlined the literal 'primary' with a
    # "do not parameterize to a wider scope" guard. It was unified to the
    # OPERATOR_CALENDAR_ID constant for single-source-of-truth. The original intent
    # is preserved: the bound value is a FIXED module constant (NOT a caller-
    # supplied parameter), and 'primary' is reserved/enforced at config load
    # (finding D), so the scope still cannot be widened.
    # REVERT PATH: if defense-in-depth at this pushed-render site is ever preferred
    # over DRY, inline the literal 'primary' again and restore the original
    # "do not parameterize to a wider scope" guard comment.
    rows = conn.execute(
        """
        SELECT summary, start_time, end_time, location, status
        FROM calendar_events
        WHERE calendar_id = ?
          AND julianday(start_time) >= julianday(?)
          AND julianday(start_time) < julianday(?)
        ORDER BY julianday(start_time)
        """,
        (OPERATOR_CALENDAR_ID, today_start.isoformat(), tomorrow_start.isoformat()),
    ).fetchall()
    upcoming: list[dict[str, Any]] = []
    for r in rows:
        start = calendar_dt_utc(r["start_time"])
        if start is None:
            continue
        if start < now_utc:
            continue
        end = calendar_dt_utc(r["end_time"])
        upcoming.append({
            "summary": r["summary"] or "",
            "start_time": r["start_time"],
            "end_time": r["end_time"],
            "location": r["location"] or "",
            "status": r["status"] or "",
            "_start_dt": start,
            "_end_dt": end,
        })
    return upcoming


# ---------------------------------------------------------------------------
# Live GitHub assigned-issues fetch
# ---------------------------------------------------------------------------


def fetch_assigned_issues(
    *,
    github_login: str,
    token: str,
    since_date: datetime,
    timeout_seconds: int = 15,
) -> list[dict[str, Any]]:
    """Search GitHub for open issues assigned to *github_login* updated in the
    last ~7 days. One request, deterministic ordering done by caller.
    """
    since_str = since_date.date().isoformat()
    query = f"assignee:{github_login} is:issue is:open updated:>={since_str}"
    params = {"q": query, "per_page": 100, "sort": "updated", "order": "desc"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API_ROOT}/search/issues?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 403 and "rate limit" in body.lower():
            raise RuntimeError("GitHub search rate limit hit") from exc
        raise
    items = payload.get("items") or []
    out: list[dict[str, Any]] = []
    for item in items:
        repo_url = item.get("repository_url") or ""
        repo_full_name = repo_url.replace(f"{GITHUB_API_ROOT}/repos/", "") if repo_url else ""
        out.append({
            "repo": repo_full_name,
            "number": item.get("number"),
            "title": item.get("title") or "",
            "state": item.get("state") or "",
            "html_url": item.get("html_url") or "",
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "labels": [l.get("name") for l in item.get("labels") or [] if l.get("name")],
        })
    return out


def _sort_assigned_issues(
    issues: list[dict[str, Any]],
    *,
    today_start: datetime,
) -> list[dict[str, Any]]:
    """Issues created today first, then everything else, each group sorted by updated_at desc."""
    def created_today(it: dict[str, Any]) -> bool:
        created = _parse_iso(it.get("created_at"))
        if created is None:
            return False
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return created >= today_start

    new_today = [i for i in issues if created_today(i)]
    older = [i for i in issues if not created_today(i)]
    new_today.sort(key=lambda i: i.get("updated_at") or "", reverse=True)
    older.sort(key=lambda i: i.get("updated_at") or "", reverse=True)
    return new_today + older


# ---------------------------------------------------------------------------
# Snapshot collector
# ---------------------------------------------------------------------------


def _query_watched_activity(
    conn: Any,
    external_repos: list[str],
    *,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Whole-repo (all-author) activity for watched external repos in [start, end).

    Mirrors the personal day-activity queries but WITHOUT the author filter and
    scoped to the external repos — so the pulse surfaces everyone's commits/PRs on
    the repos the operator monitors. Repos with no activity in the window are omitted.
    """
    if not external_repos:
        return []
    repos_lower = [r.lower() for r in external_repos]
    placeholders = ",".join("?" * len(repos_lower))
    sql_floor = _utc_iso_floor(start - timedelta(hours=2))

    activity: dict[str, dict[str, Any]] = {
        r: {"repo": r, "commits": 0, "items": [], "comments": 0} for r in repos_lower
    }

    rows = conn.execute(
        f"""
        SELECT repo_full_name, committed_at FROM github_commits
        WHERE LOWER(repo_full_name) IN ({placeholders}) AND committed_at >= ?
        """,
        (*repos_lower, sql_floor),
    ).fetchall()
    for r in rows:
        if _in_window(r["committed_at"], start, end):
            activity[r["repo_full_name"].lower()]["commits"] += 1

    rows = conn.execute(
        f"""
        SELECT repo_full_name, item_type, number, title, state, html_url,
               created_at, updated_at
        FROM github_items
        WHERE LOWER(repo_full_name) IN ({placeholders})
          AND (created_at >= ? OR updated_at >= ?)
        ORDER BY COALESCE(updated_at, created_at) DESC
        """,
        (*repos_lower, sql_floor, sql_floor),
    ).fetchall()
    for r in rows:
        created_in = _in_window(r["created_at"], start, end)
        if not (created_in or _in_window(r["updated_at"], start, end)):
            continue
        activity[r["repo_full_name"].lower()]["items"].append({
            "item_type": r["item_type"],
            "number": r["number"],
            "title": r["title"] or "",
            "state": r["state"] or "",
            "html_url": r["html_url"] or "",
            "is_new": created_in,
        })

    rows = conn.execute(
        f"""
        SELECT repo_full_name, created_at FROM github_comments
        WHERE LOWER(repo_full_name) IN ({placeholders}) AND created_at >= ?
        """,
        (*repos_lower, sql_floor),
    ).fetchall()
    for r in rows:
        if _in_window(r["created_at"], start, end):
            activity[r["repo_full_name"].lower()]["comments"] += 1

    out = [a for a in activity.values() if a["commits"] or a["items"] or a["comments"]]
    out.sort(key=lambda a: (len(a["items"]), a["commits"], a["comments"]), reverse=True)
    return out


def collect_pulse_snapshot(
    database_path: Path,
    *,
    github_login: str,
    slack_user_id: str | None,
    timezone_name: str,
    github_token: str | None,
    now: datetime | None = None,
) -> PulseSnapshot:
    tz = _resolve_timezone(timezone_name)
    now = now or datetime.now(tz)
    yesterday_start, today_start, tomorrow_start = _local_day_bounds(tz, now=now)

    notes: list[str] = []
    assigned_issues: list[dict[str, Any]] = []

    # Passively-monitored externals only — a watched repo that's become active
    # local/cloud work already surfaces in "What I've been working on", so it must
    # not also appear in the watched section (the same de-dupe the rollup applies).
    try:
        from rebalance.ingest.registry import get_external_repos
        from rebalance.ingest.github_watch import watched_repo_is_active_work

        external_repos = [
            r for r in get_external_repos(database_path)
            if not watched_repo_is_active_work(database_path, r)
        ]
    except Exception as exc:  # noqa: BLE001
        external_repos = []
        notes.append(f"watched_repos skipped: {exc}")

    with db_connection(database_path) as conn:
        today = _query_day_activity(
            conn,
            label="today",
            start=today_start,
            end=tomorrow_start,
            github_login=github_login,
            slack_user_id=slack_user_id,
        )
        watched_repos = _query_watched_activity(
            conn, external_repos, start=today_start, end=tomorrow_start
        )
        yesterday = _query_day_activity(
            conn,
            label="yesterday",
            start=yesterday_start,
            end=today_start,
            github_login=github_login,
            slack_user_id=slack_user_id,
        )
        upcoming = _query_calendar_upcoming(
            conn,
            today_start=today_start,
            tomorrow_start=tomorrow_start,
            now=now,
        )

    if github_token:
        try:
            assigned_issues = fetch_assigned_issues(
                github_login=github_login,
                token=github_token,
                since_date=today_start - timedelta(days=7),
            )
            assigned_issues = _sort_assigned_issues(assigned_issues, today_start=today_start)
        except Exception as exc:
            notes.append(f"assigned_issues fetch failed: {exc}")
    else:
        notes.append("assigned_issues skipped: no GitHub token configured")

    return PulseSnapshot(
        generated_at=now,
        timezone_name=timezone_name,
        github_login=github_login,
        today=today,
        yesterday=yesterday,
        today_calendar_upcoming=upcoming,
        assigned_issues=assigned_issues,
        notes=notes,
        watched_repos=watched_repos,
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


_TAG_DISPLAY = {
    "claude-cloud": "🤖cloud-claude",
    "codex-cloud": "🤖cloud-codex",
    "lovable": "💜lovable",
    "local-vscode": "💻local",
    "human": "",  # no chip — keeps the line uncluttered for normal human work
}


def _tag_chip(tag: str | None) -> str:
    """Inline label rendered before each row. Empty for plain human work."""
    label = _TAG_DISPLAY.get(tag or "human", "")
    return f"`{label}` " if label else ""


def _group_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        v = r.get(key) or "human"
        counts[v] = counts.get(v, 0) + 1
    return counts


def _tag_summary(counts: dict[str, int]) -> str:
    """Compact tag breakdown shown next to the section header, e.g. (12 — 8 local · 4 cloud-claude)."""
    if not counts:
        return ""
    total = sum(counts.values())
    parts = []
    for tag, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        label = _TAG_DISPLAY.get(tag, tag) or "human"
        parts.append(f"{n} {label}")
    return f"({total} — {' · '.join(parts)})"


def _fmt_local(dt_value: str | None, tz: ZoneInfo, *, time_only: bool = False) -> str:
    fmt = "%-I:%M %p" if time_only else "%b %-d %-I:%M %p"
    return format_local(dt_value, fmt, tz=tz)


def _render_section_today_work(today: DayActivity, tz: ZoneInfo) -> str:
    lines: list[str] = []
    if not (today.vault_edits or today.gh_commits or today.gh_items or today.gh_comments or today.sleuth_activity):
        return "_Nothing recorded yet today._"

    if today.gh_commits:
        by_tag = _group_counts(today.gh_commits, "source_tag")
        lines.append(f"**GitHub commits** {_tag_summary(by_tag)}")
        for c in today.gh_commits[:25]:
            url_part = f" ([{c['sha']}]({c['html_url']}))" if c.get("html_url") else f" (`{c['sha']}`)"
            tag_chip = _tag_chip(c.get("source_tag"))
            lines.append(f"- {tag_chip}`{c['repo']}` {c['subject']}{url_part}")
        if len(today.gh_commits) > 25:
            lines.append(f"- _…and {len(today.gh_commits) - 25} more_")
        lines.append("")

    if today.gh_items:
        by_tag = _group_counts(today.gh_items, "source_tag")
        lines.append(f"**Issues / PRs created or updated** {_tag_summary(by_tag)}")
        for it in today.gh_items[:20]:
            new_marker = "NEW " if it.get("is_new") else ""
            kind = it.get("item_type") or "item"
            tag_chip = _tag_chip(it.get("source_tag"))
            lines.append(
                f"- {tag_chip}{new_marker}`{it['repo']}` [{kind} #{it['number']}]({it['html_url']}) "
                f"({it.get('state','')}) — {it['title']}"
            )
        if len(today.gh_items) > 20:
            lines.append(f"- _…and {len(today.gh_items) - 20} more_")
        lines.append("")

    if today.gh_comments:
        by_tag = _group_counts(today.gh_comments, "source_tag")
        lines.append(f"**Comments posted** {_tag_summary(by_tag)}")
        for c in today.gh_comments[:15]:
            kind = c.get("comment_type") or "comment"
            tag_chip = _tag_chip(c.get("source_tag"))
            lines.append(
                f"- {tag_chip}`{c['repo']}` [{kind} on #{c['item_number']}]({c['html_url']}) — "
                f"{c['preview']}"
            )
        if len(today.gh_comments) > 15:
            lines.append(f"- _…and {len(today.gh_comments) - 15} more_")
        lines.append("")

    if today.vault_edits:
        lines.append("**Obsidian vault edits**")
        for v in today.vault_edits[:25]:
            lines.append(f"- {v['title']} (`{v['rel_path']}`) — {_fmt_local(v['last_modified'], tz, time_only=True)}")
        if len(today.vault_edits) > 25:
            lines.append(f"- _…and {len(today.vault_edits) - 25} more_")
        lines.append("")

    if today.sleuth_activity:
        lines.append("**Sleuth/Slack reminders touched**")
        for s in today.sleuth_activity[:15]:
            url_part = f" — links: {' '.join(s['github_urls'])}" if s["github_urls"] else ""
            role = "assigned by me" if s.get("sleuth_role") == "assigned_by_me" else "assigned to me"
            lines.append(f"- [{s['state']} / {role}] {s['message_preview']}{url_part}")
        if len(today.sleuth_activity) > 15:
            lines.append(f"- _…and {len(today.sleuth_activity) - 15} more_")
        lines.append("")

    return "\n".join(lines).rstrip()


def _render_section_yesterday(yesterday: DayActivity, tz: ZoneInfo) -> str:
    if not (yesterday.vault_edits or yesterday.gh_commits or yesterday.gh_items or yesterday.gh_comments):
        return "_No recorded activity yesterday._"
    parts: list[str] = []
    if yesterday.gh_commits:
        by_repo: dict[str, int] = {}
        for c in yesterday.gh_commits:
            by_repo[c["repo"]] = by_repo.get(c["repo"], 0) + 1
        repo_summary = ", ".join(f"`{r}` ({n})" for r, n in sorted(by_repo.items(), key=lambda kv: -kv[1]))
        parts.append(f"**Commits ({len(yesterday.gh_commits)}):** {repo_summary}")
    if yesterday.gh_items:
        parts.append(f"**Issues/PRs touched:** {len(yesterday.gh_items)}")
        for it in yesterday.gh_items[:10]:
            kind = it.get("item_type") or "item"
            parts.append(
                f"- `{it['repo']}` [{kind} #{it['number']}]({it['html_url']}) — {it['title']}"
            )
    if yesterday.gh_comments:
        parts.append(f"**Comments posted:** {len(yesterday.gh_comments)}")
    if yesterday.vault_edits:
        parts.append(f"**Vault edits:** {len(yesterday.vault_edits)} files")
        for v in yesterday.vault_edits[:8]:
            parts.append(f"- {v['title']} (`{v['rel_path']}`)")
    return "\n".join(parts)


def _render_section_calendar(events: list[dict[str, Any]], tz: ZoneInfo) -> str:
    if not events:
        return "_No upcoming meetings today._"
    lines: list[str] = []
    for e in events[:15]:
        when = format_local(e["_start_dt"], "%-I:%M %p", tz=tz)
        end_dt = e.get("_end_dt")
        end_part = ""
        if end_dt:
            try:
                end_str = format_local(end_dt, "%-I:%M %p", tz=tz)
                end_part = f"–{end_str}" if end_str else ""
            except Exception:
                end_part = ""
        loc = f" @ {e['location']}" if e.get("location") else ""
        lines.append(f"- **{when}{end_part}** — {e['summary']}{loc}")
    if len(events) > 15:
        lines.append(f"- _…and {len(events) - 15} more_")
    return "\n".join(lines)


def _render_section_assigned_issues(
    issues: list[dict[str, Any]],
    *,
    today_start: datetime,
    tz: ZoneInfo,
) -> str:
    if not issues:
        return "_No open issues assigned in the last 7 days._"
    lines: list[str] = []
    for it in issues[:25]:
        created = _parse_iso(it.get("created_at"))
        is_new = False
        if created is not None:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            is_new = created >= today_start
        prefix = "**NEW** " if is_new else ""
        labels = (
            " " + " ".join(f"`{l}`" for l in it.get("labels") or [])
        ) if it.get("labels") else ""
        updated = _fmt_local(it.get("updated_at"), tz)
        lines.append(
            f"- {prefix}`{it['repo']}` [#{it['number']}]({it['html_url']}) "
            f"— {it['title']}{labels} _(updated {updated})_"
        )
    if len(issues) > 25:
        lines.append(f"- _…and {len(issues) - 25} more_")
    return "\n".join(lines)


def _render_section_watched(watched: list[dict[str, Any]], tz: ZoneInfo) -> str:
    if not watched:
        return "_No external/watched-repo activity today._"
    lines: list[str] = []
    for w in watched:
        bits: list[str] = []
        if w["commits"]:
            bits.append(f"{w['commits']} commit{'s' if w['commits'] != 1 else ''}")
        if w["items"]:
            bits.append(f"{len(w['items'])} PR/issue")
        if w["comments"]:
            bits.append(f"{w['comments']} comment{'s' if w['comments'] != 1 else ''}")
        lines.append(f"**`{w['repo']}`** — {' · '.join(bits)}")
        for it in w["items"][:6]:
            chip = "🆕 " if it.get("is_new") else ""
            kind = "PR" if it["item_type"] == "pull_request" else "issue"
            url_part = f" — {it['html_url']}" if it["html_url"] else ""
            state = f" ({it['state']})" if it["state"] else ""
            lines.append(f"- {chip}{kind} #{it['number']} {it['title']}{state}{url_part}")
        if len(w["items"]) > 6:
            lines.append(f"- _…and {len(w['items']) - 6} more_")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_pulse_markdown(snapshot: PulseSnapshot) -> str:
    tz = _resolve_timezone(snapshot.timezone_name)
    today_start = snapshot.generated_at.replace(hour=0, minute=0, second=0, microsecond=0)
    if snapshot.generated_at.tzinfo is None:
        today_start = today_start.replace(tzinfo=tz)

    header_date = snapshot.generated_at.strftime("%A, %B %-d, %Y")
    header_time = snapshot.generated_at.strftime("%-I:%M %p %Z")

    sections = [
        f"# Live Pulse — {header_date}",
        f"_Last updated: {header_time} ({snapshot.timezone_name}) for `{snapshot.github_login}`_",
        "",
        "## Current Day",
        "",
        "### What I've been working on",
        _render_section_today_work(snapshot.today, tz),
        "",
        "### Watched repos (external activity)",
        _render_section_watched(snapshot.watched_repos, tz),
        "",
        "### Upcoming Meetings",
        _render_section_calendar(snapshot.today_calendar_upcoming, tz),
        "",
        "### GitHub Issues assigned to me (last 7 days)",
        _render_section_assigned_issues(snapshot.assigned_issues, today_start=today_start, tz=tz),
        "",
        "### Sleuth (Slack) reminders assigned to/by me",
        _render_section_today_sleuth(snapshot.today, tz),
        "",
        "## Yesterday",
        "",
        "### What I worked on yesterday",
        _render_section_yesterday(snapshot.yesterday, tz),
        "",
    ]
    if snapshot.notes:
        sections.append("---")
        sections.append("")
        sections.append("**Diagnostics**")
        for note in snapshot.notes:
            sections.append(f"- {note}")
        sections.append("")
    return "\n".join(sections).rstrip() + "\n"


def _render_section_today_sleuth(today: DayActivity, tz: ZoneInfo) -> str:
    if not today.sleuth_activity:
        return "_No active reminders touched today._"
    lines: list[str] = []
    for s in today.sleuth_activity[:20]:
        active = "active" if s["is_active"] else "inactive"
        role = "assigned by me" if s.get("sleuth_role") == "assigned_by_me" else "assigned to me"
        url_part = f" — links: {' '.join(s['github_urls'])}" if s["github_urls"] else ""
        chan = f" #{s['channel']}" if s["channel"] else ""
        lines.append(f"- [{s['state']} / {active} / {role}]{chan} {s['message_preview']}{url_part}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Git ops
# ---------------------------------------------------------------------------


def _run_git(args: list[str], *, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _commit_and_push_if_changed(
    target_repo: Path,
    file_rel: str,
    new_content: str,
    *,
    push: bool,
    commit_message: str,
) -> dict[str, Any]:
    """Write *new_content* to file_rel inside *target_repo*; commit+push only if changed."""
    target_file = target_repo / file_rel
    target_file.parent.mkdir(parents=True, exist_ok=True)

    existing = target_file.read_text(encoding="utf-8") if target_file.exists() else ""
    if existing == new_content:
        return {
            "wrote_file": False,
            "committed": False,
            "pushed": False,
            "reason": "no content change",
        }

    target_file.write_text(new_content, encoding="utf-8")

    rc, out, err = _run_git(["add", file_rel], cwd=target_repo)
    if rc != 0:
        return {"wrote_file": True, "committed": False, "pushed": False, "git_error": err or out}

    rc_status, status_out, _ = _run_git(["status", "--porcelain", file_rel], cwd=target_repo)
    if rc_status != 0 or not status_out:
        return {"wrote_file": True, "committed": False, "pushed": False, "reason": "nothing staged"}

    rc, out, err = _run_git(["commit", "-m", commit_message], cwd=target_repo)
    if rc != 0:
        return {"wrote_file": True, "committed": False, "pushed": False, "git_error": err or out}

    if not push:
        return {"wrote_file": True, "committed": True, "pushed": False}

    rc, out, err = _run_git(["push"], cwd=target_repo)
    if rc != 0:
        git_error = err or out
        if "fetch first" in git_error or "rejected" in git_error:
            fsm = RepairFSM(
                actions=_push_repair_actions(target_repo),
                action_descriptions=_PUSH_ACTION_DESCRIPTIONS,
                error_context="git push to pulse target repo failed with non-fast-forward rejection",
                preferred_action="pull_rebase",
            )
            repair_state = fsm.run(git_error)
            base = {"wrote_file": True, "committed": True, "repair_log": repair_state.log}
            if repair_state.status == RepairStatus.REPAIRED:
                if not _verify_remote_content(target_repo, file_rel, new_content):
                    return {
                        **base,
                        "pushed": False,
                        "git_error": "repair reported success but remote content does not match",
                        "repair_status": "content_mismatch",
                    }
                return {**base, "pushed": True, "repaired": True}
            return {
                **base,
                "pushed": False,
                "git_error": git_error,
                "repair_status": repair_state.status.value,
                "repair_error": repair_state.final_error,
            }
        return {"wrote_file": True, "committed": True, "pushed": False, "git_error": git_error}
    return {"wrote_file": True, "committed": True, "pushed": True}


# reset_hard is intentionally absent from the autonomous menu — it discards the
# local commit that contains the new pulse content, producing a false "pushed=True"
# while silently dropping the update. Destructive repairs require explicit operator action.
_PUSH_ACTION_DESCRIPTIONS: dict[str, str] = {
    "pull_rebase": "run git pull --rebase to integrate remote commits, then retry push",
    "abort_rebase": "abort a stuck rebase with git rebase --abort, then pull --rebase and push",
    "notify_only": "do not attempt further repair — report the failure and stop",
}


def _push_repair_actions(target_repo: Path) -> dict[str, Any]:
    """Build the bounded action menu for autonomous push-failure repair.

    reset_hard is excluded: it would discard the local commit containing the
    new pulse content and report a false success. Operator must handle that case.
    """

    def pull_rebase() -> RepairResult:
        rc, _, err = _run_git(["pull", "--rebase"], cwd=target_repo)
        if rc != 0:
            return RepairResult(ok=False, error=err)
        rc, _, err = _run_git(["push"], cwd=target_repo)
        return RepairResult(ok=rc == 0, error=err if rc != 0 else "")

    def abort_rebase() -> RepairResult:
        _run_git(["rebase", "--abort"], cwd=target_repo)  # best-effort
        rc, _, err = _run_git(["pull", "--rebase"], cwd=target_repo)
        if rc != 0:
            return RepairResult(ok=False, error=err)
        rc, _, err = _run_git(["push"], cwd=target_repo)
        return RepairResult(ok=rc == 0, error=err if rc != 0 else "")

    def notify_only() -> RepairResult:
        return RepairResult(ok=False, error="notify_only: repair deferred to operator")

    return {
        "pull_rebase": pull_rebase,
        "abort_rebase": abort_rebase,
        "notify_only": notify_only,
    }


def _verify_remote_content(target_repo: Path, file_rel: str, expected: str) -> bool:
    """Return True if the branch just pushed now contains exactly the expected file content.

    GH-233: this used to read ``origin/HEAD``, which is the remote's *default* branch — not
    necessarily the branch ``git push`` just wrote to. Two ways that went wrong:

    * **Wrong ref.** ``_commit_and_push_if_changed`` runs a bare ``git push``, which pushes the
      current branch to its upstream. On any branch other than the remote default, the check read
      a different branch than the one that was written — reporting a mismatch for a good push, or
      passing because some other branch happened to match.
    * **Missing ref.** ``origin/HEAD`` is created at clone time from the remote's HEAD. A clone of
      an empty remote never gets one, and pushing afterwards does not create it, so
      ``git show origin/HEAD:<path>`` fails with "invalid object name" however correct the push was.

    ``@{u}`` is by definition the ref the bare push targeted, so resolving it removes both cases.
    A missing upstream is still a genuine failure: without one there is nothing to have pushed to.
    """
    rc, upstream, _ = _run_git(["rev-parse", "--abbrev-ref", "@{u}"], cwd=target_repo)
    if rc != 0 or not upstream:
        return False
    rc, out, _ = _run_git(["show", f"{upstream}:{file_rel}"], cwd=target_repo)
    return rc == 0 and out == expected.strip()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def publish_pulse(
    database_path: Path,
    *,
    dry_run: bool = False,
    push: bool = True,
) -> dict[str, Any]:
    """Render the live-pulse markdown and (unless dry_run) commit+push it.

    Reads pulse config from temp/rbos.config. Returns a structured summary
    that includes the rendered markdown so agents can preview it.
    """
    started = time.monotonic()
    cfg = get_pulse_config()
    missing = [k for k in ("github_login", "pulse_target_path") if not cfg.get(k)]
    if missing:
        return {
            "ok": False,
            "error": f"pulse config missing keys: {missing}. "
                     "Set them via rebalance.ingest.config.set_pulse_config().",
            "config": cfg,
        }

    target_path = Path(cfg["pulse_target_path"]).expanduser().resolve()
    if not (target_path / ".git").exists():
        return {
            "ok": False,
            "error": f"pulse_target_path is not a git repo: {target_path}",
            "config": cfg,
        }

    snapshot = collect_pulse_snapshot(
        database_path=Path(database_path).expanduser().resolve(),
        github_login=cfg["github_login"],
        slack_user_id=cfg.get("slack_user_id"),
        timezone_name=cfg.get("pulse_timezone") or "UTC",
        github_token=get_github_token(),
    )
    markdown = render_pulse_markdown(snapshot)

    git_result: dict[str, Any] = {"skipped_dry_run": True}
    if not dry_run:
        commit_message = (
            f"pulse: {snapshot.generated_at.strftime('%Y-%m-%d %H:%M %Z')} update"
        )
        git_result = _commit_and_push_if_changed(
            target_repo=target_path,
            file_rel=cfg.get("pulse_filename") or "live-pulse.md",
            new_content=markdown,
            push=push,
            commit_message=commit_message,
        )

    return {
        "ok": True,
        "dry_run": dry_run,
        "generated_at": snapshot.generated_at.isoformat(),
        "timezone": snapshot.timezone_name,
        "github_login": snapshot.github_login,
        "target_path": str(target_path),
        "target_filename": cfg.get("pulse_filename") or "live-pulse.md",
        "counts": {
            "today_commits": len(snapshot.today.gh_commits),
            "today_items": len(snapshot.today.gh_items),
            "today_comments": len(snapshot.today.gh_comments),
            "today_vault_edits": len(snapshot.today.vault_edits),
            "today_sleuth": len(snapshot.today.sleuth_activity),
            "yesterday_commits": len(snapshot.yesterday.gh_commits),
            "upcoming_meetings": len(snapshot.today_calendar_upcoming),
            "assigned_issues_7d": len(snapshot.assigned_issues),
        },
        "notes": snapshot.notes,
        "markdown": markdown,
        "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        "git": git_result,
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
