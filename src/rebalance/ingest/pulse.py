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
  - Sleuth reminders:   ``sleuth_reminders`` where assignee_id == slack_user_id
  - Calendar events:    ``calendar_events`` (today's upcoming)
  - Assigned issues:    GitHub search API, fetched fresh each run
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from rebalance.ingest.agent_tags import classify as classify_source
from rebalance.ingest.config import get_github_token, get_pulse_config
from rebalance.ingest.db import db_connection


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
    return ZoneInfo("UTC")


def _local_day_bounds(tz: ZoneInfo, now: datetime | None = None) -> tuple[datetime, datetime, datetime]:
    """Return (yesterday_start, today_start, tomorrow_start) in *tz*."""
    now = now or datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    tomorrow_start = today_start + timedelta(days=1)
    return yesterday_start, today_start, tomorrow_start


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _in_window(value: str | None, start: datetime, end: datetime) -> bool:
    """True if *value* (ISO string with TZ) falls in [start, end)."""
    parsed = _parse_iso(value)
    if parsed is None:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
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

    if slack_user_id:
        rows = conn.execute(
            """
            SELECT reminder_id, state, is_active, reminder_message_text,
                   should_post_on, last_seen_at, original_channel_name,
                   github_urls_json
            FROM sleuth_reminders
            WHERE assignee_id = ? AND last_seen_at >= ?
            ORDER BY last_seen_at DESC
            """,
            (slack_user_id, sql_floor),
        ).fetchall()
        for r in rows:
            if _in_window(r["last_seen_at"], start, end):
                msg = (r["reminder_message_text"] or "").replace("\n", " ").strip()
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
    floor = _utc_iso_floor(today_start - timedelta(hours=2))
    rows = conn.execute(
        """
        SELECT summary, start_time, end_time, location, status
        FROM calendar_events
        WHERE start_time >= ?
        ORDER BY start_time
        """,
        (floor,),
    ).fetchall()
    upcoming: list[dict[str, Any]] = []
    for r in rows:
        start = _parse_iso(r["start_time"])
        if start is None:
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if start < now or start >= tomorrow_start:
            continue
        end = _parse_iso(r["end_time"])
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
    response = requests.get(
        f"{GITHUB_API_ROOT}/search/issues",
        params=params,
        headers=headers,
        timeout=timeout_seconds,
    )
    if response.status_code == 403 and "rate limit" in response.text.lower():
        raise RuntimeError("GitHub search rate limit hit")
    response.raise_for_status()
    payload = response.json()
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

    with db_connection(database_path) as conn:
        today = _query_day_activity(
            conn,
            label="today",
            start=today_start,
            end=tomorrow_start,
            github_login=github_login,
            slack_user_id=slack_user_id,
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
    parsed = _parse_iso(dt_value)
    if parsed is None:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(tz)
    if time_only:
        return local.strftime("%-I:%M %p")
    return local.strftime("%b %-d %-I:%M %p")


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
            lines.append(f"- [{s['state']}] {s['message_preview']}{url_part}")
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
        when = e["_start_dt"].astimezone(tz).strftime("%-I:%M %p")
        end_dt = e.get("_end_dt")
        end_part = ""
        if end_dt:
            try:
                end_part = f"–{end_dt.astimezone(tz).strftime('%-I:%M %p')}"
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
        "### Upcoming Meetings",
        _render_section_calendar(snapshot.today_calendar_upcoming, tz),
        "",
        "### GitHub Issues assigned to me (last 7 days)",
        _render_section_assigned_issues(snapshot.assigned_issues, today_start=today_start, tz=tz),
        "",
        "### Sleuth (Slack) reminders assigned to me",
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
        url_part = f" — links: {' '.join(s['github_urls'])}" if s["github_urls"] else ""
        chan = f" #{s['channel']}" if s["channel"] else ""
        lines.append(f"- [{s['state']} / {active}]{chan} {s['message_preview']}{url_part}")
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
        return {"wrote_file": True, "committed": True, "pushed": False, "git_error": err or out}
    return {"wrote_file": True, "committed": True, "pushed": True}


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
