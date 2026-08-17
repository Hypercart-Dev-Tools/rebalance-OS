"""
rebalance pulse — static web mirror of the terminal dashboard.

Renders a single self-contained HTML page (web/pulse.html) from the same
SQLite knowledge base the TUI reads. The page uses a `<meta refresh>` tag
so any browser tab pointed at file:// reloads on a cadence; pair that with
`--watch` here and the file is regenerated on disk in lockstep.

    One shot:    uv run python scripts/pulse_web.py
    Watch mode:  uv run python scripts/pulse_web.py --watch
    Open:        open web/pulse.html  (file://)

Optional:
    --goals PATH        Override Goals markdown path (default: {vault_path}/0. Goals.md)
    --out PATH          Override output HTML path (default: web/pulse.html)
    --interval SECONDS  Watch-mode regen cadence (default: 30)
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.parse
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Canonical path shared with pulse_server.py — must stay in sync
ACTIVE_JSON_PATH = PROJECT_ROOT / "temp" / "apple-reminders" / "active.json"
import _bootstrap  # noqa: E402, F401  — puts src/ and scripts/ on sys.path

from rebalance.tz_utils import format_timestamp, parse_utc_iso  # noqa: E402

# Reuse the TUI's data layer so both views move in lockstep.
from dashboard import (  # type: ignore  # noqa: E402
    DB_PATH,
    TZ,
    fetch_calendar_today,
    fetch_calendar_upcoming,
    fetch_open_prs,
    fetch_org_activity,
    fetch_recent_auto_promotion,
    fetch_recent_emails,
    fetch_recent_figma,
    fetch_recent_github,
    fetch_repo_activity_counts,
    fetch_sleuth_display_sections,
    fetch_sleuth_due,
    fetch_vault_recent,
    fetch_watched_summary,
    _parse_iso,
    _truncate,
)
from rebalance.doctor import FAIL, WARN, Check, run_doctor  # noqa: E402
from rebalance.health import HealthStatus, compute_health_status  # noqa: E402
from rebalance.ingest.apple_reminders import list_apple_reminders  # noqa: E402
from rebalance.ingest.config import get_figma_file_keys  # noqa: E402
from rebalance.ingest.goals_file import (  # noqa: E402
    CHECKBOX_RE,
    complete_goal_in_file,
    goal_completion_still_applied as _goal_completion_still_applied,
    parse_goals,
    undo_goal_completion_in_file,
)
from rebalance.ingest.index_ops import COLLECTORS, get_index_status  # noqa: E402
from rebalance.ingest import next_actions  # noqa: E402
from rebalance.ingest.slack_users import compact_sleuth_reminder  # noqa: E402
from rebalance.web_components import (  # noqa: E402
    RB_BUTTON_CSS,
    RB_CHROME_CSS,
    RB_TOKENS_CSS,
    badge_html,
    button_link,
    data_row,
    render_shell,
)

CONFIG_PATH = PROJECT_ROOT / "temp" / "rbos.config"
DEFAULT_OUT = PROJECT_ROOT / "web" / "pulse.html"
GOAL_HISTORY_PATH = PROJECT_ROOT / "temp" / "pulse_goal_history.json"
HEALTH_LOG_PATH = PROJECT_ROOT / "temp" / "health-reporter.log.jsonl"
HEALTH_ISSUES_URL = (
    "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues"
    "?labels=rebalance-health&state=open"
)
MAX_GOAL_HISTORY = 3
PRIMARY_GOAL_LIMIT = 3
SECONDARY_TODO_LIMIT = 6
APPLE_REMINDER_LIMIT = 6  # read-only column; soonest-due active reminders
STREAM_SOURCE_EXCLUDE = frozenset({"ask_self", "code", "focus5", "semantic", "sync"})
STREAM_DISPLAY = {
    "github": {"label": "GitHub", "kbd": "G", "sort": 10},
    "vault": {"label": "Vault", "kbd": "V", "sort": 20},
    "calendar": {"label": "Calendar", "kbd": "C", "sort": 30},
    "sleuth": {"label": "Sleuth", "kbd": "S", "sort": 40},
    "email": {"label": "Email", "kbd": "E", "sort": 50},
    "figma": {"label": "Figma", "kbd": "F", "sort": 60},
}
STREAM_COUNT_KEYS = (
    "messages",
    "comments",
    "reminders",
    "events",
    "items",
    "chunks",
    "files",
    "repos",
    "documents",
    "activity_records",
)


def resolve_goals_path(explicit: Path | None = None) -> Path | None:
    """Resolve the active Goals.md path the same way `main()` does.

    Priority: explicit arg → PULSE_GOALS env → {vault_path}/0. Goals.md.
    Returns None only if no vault is configured and no override is provided.
    """
    if explicit is not None:
        return explicit.expanduser()
    env = os.environ.get("PULSE_GOALS")
    if env:
        return Path(env).expanduser()
    vault = load_vault_path()
    if vault is None:
        return None
    return vault / "0. Goals.md"


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def load_goal_history(*, goals_path: Path | None = None, history_path: Path = GOAL_HISTORY_PATH) -> list[dict[str, Any]]:
    entries = _read_json_list(history_path)
    if goals_path is None:
        return entries[:MAX_GOAL_HISTORY]
    wanted = str(goals_path.expanduser().resolve())
    kept = [
        entry for entry in entries
        if isinstance(entry, dict) and entry.get("goals_path") == wanted
    ]
    fresh = [entry for entry in kept if _goal_completion_still_applied(goals_path, entry)]
    stale_ids = {str(entry.get("id") or "") for entry in kept if entry not in fresh}
    if stale_ids:
        remaining = [
            entry for entry in entries
            if isinstance(entry, dict) and str(entry.get("id") or "") not in stale_ids
        ]
        _write_goal_history(remaining, history_path=history_path)
    return fresh[:MAX_GOAL_HISTORY]


def _write_goal_history(entries: Iterable[dict[str, Any]], *, history_path: Path = GOAL_HISTORY_PATH) -> list[dict[str, Any]]:
    compact = list(entries)[:MAX_GOAL_HISTORY]
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(compact, indent=2), encoding="utf-8")
    return compact


def remember_goal_completion(entry: dict[str, Any], *, history_path: Path = GOAL_HISTORY_PATH) -> list[dict[str, Any]]:
    entries = [entry]
    for existing in _read_json_list(history_path):
        if not isinstance(existing, dict):
            continue
        if existing.get("id") == entry.get("id"):
            continue
        if (
            existing.get("goals_path") == entry.get("goals_path")
            and existing.get("title") == entry.get("title")
        ):
            continue
        entries.append(existing)
    return _write_goal_history(entries, history_path=history_path)


def forget_goal_completion(entry_id: str, *, history_path: Path = GOAL_HISTORY_PATH) -> list[dict[str, Any]]:
    kept = [
        entry for entry in _read_json_list(history_path)
        if isinstance(entry, dict) and entry.get("id") != entry_id
    ]
    return _write_goal_history(kept, history_path=history_path)


def load_vault_path() -> Path | None:
    if not CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    vp = data.get("vault_path")
    return Path(vp).expanduser() if vp else None


def _stream_sort_key(name: str) -> tuple[int, str]:
    meta = STREAM_DISPLAY.get(name) or {}
    return int(meta.get("sort") or 999), name


def _stream_label(name: str) -> str:
    meta = STREAM_DISPLAY.get(name) or {}
    label = str(meta.get("label") or "").strip()
    return label or name.replace("_", " ").title()


def _stream_kbd(name: str) -> str:
    meta = STREAM_DISPLAY.get(name) or {}
    kbd = str(meta.get("kbd") or "").strip()
    if kbd:
        return kbd[:2]
    for char in _stream_label(name):
        if char.isalnum():
            return char.upper()
    return "?"


def _stream_count(source_status: dict[str, Any]) -> int:
    for key in STREAM_COUNT_KEYS:
        value = source_status.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def build_stream_rows(
    status: dict[str, Any],
    *,
    live_counts: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Return the sidebar stream rows from registered user-facing collectors.

    The list is derived from the collector registry plus the ``index_status``
    source blocks, so opt-in connectors such as email and figma render even
    before they are configured or synced. For streams the page already renders
    directly, ``live_counts`` can override the stored totals so the sidebar
    badges stay aligned with the visible feed lengths.
    """
    sources = status.get("sources") or {}
    names = [
        name for name in COLLECTORS
        if name not in STREAM_SOURCE_EXCLUDE and name in sources
    ]
    names.sort(key=_stream_sort_key)
    return [
        {
            "name": name,
            "label": _stream_label(name),
            "kbd": _stream_kbd(name),
            "count": int((live_counts or {}).get(name, _stream_count(sources.get(name) or {}))),
        }
        for name in names
    ]


# ---------------------------------------------------------------------------
# Health report counter — reads local JSONL log, no GitHub API call
# ---------------------------------------------------------------------------

def fetch_health_filed_count(days: int = 30) -> int:
    """Count distinct checks that had a 'filed' action in the last *days* days.

    Reads temp/health-reporter.log.jsonl locally so the dashboard never makes
    a live API call. Returns 0 if the log doesn't exist yet.
    """
    from datetime import timedelta  # noqa: PLC0415
    if not HEALTH_LOG_PATH.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    seen: set[str] = set()
    try:
        for raw in HEALTH_LOG_PATH.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            run_id = record.get("run_id", "")
            try:
                run_dt = datetime.fromisoformat(run_id.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if run_dt < cutoff:
                continue
            if record.get("dry_run"):
                continue
            for action in record.get("actions", []):
                if action.get("action") == "filed":
                    seen.add(action.get("check", ""))
    except OSError:
        return 0
    return len(seen)


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _timestamp_html(
    value: str | datetime | None,
    *,
    tz: ZoneInfo,
    relative: bool = False,
    fallback: str = "",
    cls: str = "timestamp-block",
) -> str:
    text = format_timestamp(value, relative=relative, tz=tz)
    if not text:
        return _esc(fallback)
    return f'<span class="{_esc(cls)}">{_esc(text)}</span>'


def _normalize_html_text(value: str | None) -> str:
    return html.unescape((value or "").strip())


def _compact_whitespace(text: str | None) -> str:
    return " ".join((text or "").split())


def _short_text(text: str | None, n: int) -> str:
    compact = _compact_whitespace(text)
    return compact if len(compact) <= n else compact[: n - 1] + "…"


def _health_banner_copy_text(
    problems: list[Check],
    *,
    status_text: str,
    activity_text: str,
) -> str:
    lines = [
        f"Collector attention needed",
        f"Status: {status_text}",
        f"Last collector activity: {activity_text}",
    ]
    for check in problems:
        lines.append(f"{check.name}: {_compact_whitespace(check.detail)}")
        if check.hint:
            lines.append(f"Hint: {_compact_whitespace(check.hint)}")
    return "\n".join(lines)


def _clipboard_icon_svg() -> str:
    return (
        '<svg class="health-banner-copy-icon" viewBox="0 0 20 20" fill="none" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<path d="M7 3.5H6.25A2.25 2.25 0 0 0 4 5.75v8A2.25 2.25 0 0 0 6.25 16h7.5A2.25 2.25 0 0 0 16 13.75v-8A2.25 2.25 0 0 0 13.75 3.5H13" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M8 3h4a1 1 0 0 1 1 1v1.25H7V4a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M8 8.5h4M8 11h3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>'
        "</svg>"
    )


def _latest_collector_activity(status: dict[str, Any]) -> str | None:
    sources = status.get("sources") or {}
    semantic = status.get("semantic_index") or {}
    candidates = [
        (sources.get("vault") or {}).get("last_ingested_at"),
        (sources.get("github") or {}).get("activity_last_scanned_at"),
        (sources.get("github") or {}).get("documents_last_fetched_at"),
        (sources.get("calendar") or {}).get("last_fetched_at"),
        (sources.get("sleuth") or {}).get("last_synced_at"),
        (sources.get("email") or {}).get("last_synced_at"),
        semantic.get("last_embedded_at"),
    ]
    latest: datetime | None = None
    latest_raw: str | None = None
    for raw in candidates:
        dt = _parse_iso(raw)
        if dt is None:
            continue
        if latest is None or dt > latest:
            latest = dt
            latest_raw = raw
    return latest_raw


def render_health_banner(
    health: HealthStatus,
    now: datetime,
    last_activity: str | None,
) -> str:
    problems = health.problems
    if not problems:
        return ""

    tone = "danger" if health.failures else "warn"
    status_text = health.status_text
    activity_text = format_timestamp(last_activity, relative=True, tz=TZ) or "never"
    activity_html = _timestamp_html(last_activity, tz=TZ, relative=True, fallback="never")
    copy_text = _health_banner_copy_text(
        problems,
        status_text=status_text,
        activity_text=activity_text,
    )

    items = []
    for check in problems[:4]:
        fix = (
            f'<span class="health-banner-fix">→ {_esc(_short_text(check.hint, 120))}</span>'
            if check.hint
            else ""
        )
        items.append(
            f'<span class="health-banner-item">'
            f'<span class="health-banner-name">{_esc(check.name)}</span>'
            f'<span class="health-banner-detail">{_esc(_short_text(check.detail, 120))}</span>'
            f"{fix}"
            f"</span>"
        )
    if len(problems) > 4:
        items.append(
            f'<span class="health-banner-item more">+{len(problems) - 4} more</span>'
        )

    return f"""
    <section class="health-banner health-banner-{tone}" aria-live="polite">
      <div class="health-banner-lead">
        <span class="health-banner-badge">{_esc(status_text)}</span>
        <span class="health-banner-summary">Collector attention needed</span>
        <span class="health-banner-activity">Last collector activity {activity_html}</span>
        <button
          type="button"
          class="health-banner-copy-btn"
          data-copy-text="{_esc(copy_text)}"
          aria-label="Copy collector warning text"
          title="Copy collector warning text"
        >{_clipboard_icon_svg()}<span class="visually-hidden">Copy collector warning text</span></button>
      </div>
      <div class="health-banner-items">{''.join(items)}</div>
    </section>
    """


def render_sync_chip(
    health: HealthStatus,
    last_activity: str | None,
    now: datetime,
) -> str:
    activity_text = format_timestamp(last_activity, relative=True, tz=TZ) or "—"
    if health.verdict == FAIL:
        tone = "danger"
        label = f"Collector degraded · {activity_text}"
    elif health.verdict == WARN:
        tone = "warn"
        label = f"Collector warnings · {activity_text}"
    else:
        tone = "ok"
        label = f"Collector active {activity_text}"
    return (
        f'<span class="synced synced-{tone}">'
        f'<span class="ok-dot"></span>{_esc(label)}'
        f"</span>"
    )


def build_obsidian_url(vault_path: Path | None, file_path: Path) -> str | None:
    """Return an obsidian:// URL for file_path, or None if no vault is known.

    Uses the ?vault=&file= form. The file is given relative to the vault
    without its .md extension (Obsidian accepts either; relative is more
    portable). Falls back to the file stem if file_path isn't under vault.
    """
    if vault_path is None:
        return None
    vault_name = vault_path.name
    try:
        rel = file_path.relative_to(vault_path).with_suffix("")
        rel_str = rel.as_posix()
    except ValueError:
        rel_str = file_path.stem
    return f"obsidian://open?vault={urllib.parse.quote(vault_name)}&file={urllib.parse.quote(rel_str)}"


def build_slack_url(reminder: dict[str, Any]) -> str | None:
    """Return a slack.com permalink for a sleuth reminder.

    Uses https://<workspace>.slack.com/archives/<channel>/p<ts-no-dot>. macOS
    Slack registers slack.com as a Universal Link and opens these in the app
    when it's installed. Falls back to a channel-only URL if no message ts is
    available; returns None if there's no channel at all.
    """
    workspace = reminder.get("workspace_name")
    channel = reminder.get("original_channel_id") or reminder.get("target_channel_id")
    if not workspace or not channel:
        return None
    base = f"https://{workspace}.slack.com/archives/{channel}"
    msg_ts = reminder.get("original_message_id") or reminder.get("original_thread_ts")
    if msg_ts:
        # Slack's permalink ts strips the dot: 1774287154.212369 → 1774287154212369
        return f"{base}/p{str(msg_ts).replace('.', '')}"
    return base


def build_gmail_thread_url(row: dict[str, Any]) -> str | None:
    thread_id = (row.get("thread_id") or "").strip()
    if thread_id:
        return f"https://mail.google.com/mail/u/0/#all/{urllib.parse.quote(thread_id)}"
    message_id = (row.get("message_id") or "").strip()
    if message_id:
        return f"https://mail.google.com/mail/u/0/#all/{urllib.parse.quote(message_id)}"
    return None


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _linkify(text: str) -> str:
    """Convert URLs in text to clickable links that open in new tabs."""
    if not text:
        return ""
    # Match http:// https:// and file:// URLs
    url_pattern = re.compile(r'(https?://[^\s<>"{}|\\^`\[\]]*[^\s<>"{}|\\^`\[\].,;:!?\)])')

    def replace_url(match):
        url = match.group(1)
        escaped_url = _esc(url)
        return f'<a href="{escaped_url}" target="_blank" rel="noopener noreferrer">{escaped_url}</a>'

    return url_pattern.sub(replace_url, _esc(text))


def _join_row_bits(bits: Iterable[str]) -> str:
    parts = [str(bit) for bit in bits if bit]
    return f' <span class="rb-data-row-sep">·</span> '.join(parts)


def _subsection_label(label: str, *, count: int | None = None, extra_class: str = "") -> str:
    count_html = (
        f'<span class="section-label-count"> · {_esc(count)}</span>'
        if count is not None
        else ""
    )
    cls = "section-label"
    if extra_class:
        cls += f" {extra_class}"
    return f'<div class="{cls}">{_esc(label)}{count_html}</div>'


def _reminder_marker_text(label: str | None) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", label or "").upper()
    return cleaned[:1] or "R"


def _age_chip(days: int) -> str:
    if days <= 0:
        return ""
    suffix = "day" if days == 1 else "days"
    return f'<span class="side-age-chip">{days} {suffix} old</span>'


def _repo_short_name(repo: str) -> str:
    if "/" not in repo:
        return repo
    return repo.split("/", 1)[1]


def _activity_kind_meta(kind: str, sub: str) -> tuple[str, str]:
    if kind == "commit":
        return ("ok", "Commit")
    if kind == "item" and sub == "pull_request":
        return ("info", "PR")
    if kind == "item":
        return ("warn", "Issue")
    return ("danger", "Comment")


def _figma_file_link(file_key: str) -> str:
    key = _normalize_html_text(file_key)
    if not key:
        return ""
    href = f"https://www.figma.com/design/{urllib.parse.quote(key)}"
    return (
        f'<a class="figma-row-link" href="{_esc(href)}" target="_blank" '
        'rel="noopener noreferrer" title="Open Figma file">Open file</a>'
    )


def _badge_marker(label: str, *, tone: str = "") -> str:
    cls = f"rb-data-marker-badge {tone}".strip()
    return f'<span class="{cls}">{_esc(label)}</span>'


def _avatar_marker(label: str) -> str:
    alnum = re.sub(r"[^A-Za-z0-9]", "", label or "")
    initial = (alnum[:1] or "?").upper()
    return f'<span class="rb-data-marker-avatar">{_esc(initial)}</span>'


def _render_recent_completion_row(item: dict[str, Any], *, stripe_index: int = 0) -> str:
    title = str(item.get("title") or "").strip() or "completed task"
    item_id = str(item.get("id") or "")
    return data_row(
        marker_html='<span class="rb-data-marker-badge ok">✓</span>',
        title_html=_esc(title),
        timestamp=item.get("completed_at"),
        tz=TZ,
        relative=True,
        fallback_timestamp="just now",
        row_class="goal-undo-item",
        body_class="goal-undo-copy",
        title_class="goal-undo-title",
        stripe_index=stripe_index,
        trailing_html=button_link(
            "Undo",
            "#",
            arrow=False,
            cls="goal-undo-btn",
            attrs=(
                f'data-goal-undo-id="{_esc(item_id)}" '
                'role="button"'
            ),
        ),
    )


def _render_goal_rows(goals: list[dict[str, Any]], *, empty_html: str, compact: bool = False) -> str:
    rows = []
    for idx, g in enumerate(goals):
        cls = "done" if g["done"] else ""
        if compact:
            cls = f"{cls} goal-compact".strip()
        check = "checked" if g["done"] else ""
        title_html = _linkify(g['title'])
        desc_html = _linkify(g['description'])
        rows.append(
            data_row(
                marker_html=(
                    f'<span class="check {check}" role="checkbox" tabindex="0" '
                    f'aria-label="Complete: {_esc(g["title"])}"></span>'
                ),
                title_html=title_html,
                meta_html=desc_html,
                row_class=f"goal {cls}".strip(),
                body_class="goal-body",
                title_class="goal-title",
                meta_class="goal-desc",
                stripe_index=idx,
                attrs=f'data-goal-title="{_esc(g["title"])}"',
            )
        )
    if not rows:
        rows.append(empty_html)
    return "".join(rows)


def _render_reminder_rows(
    reminders: list[dict[str, Any]], *, tz: ZoneInfo, empty_html: str
) -> str:
    """Rows for the Apple Reminders column. Each row with a `reminder_id` gets a
    clickable complete check that POSTs to `/api/apple-reminders/complete`
    (Phase 6 dashboard write-back). The write itself routes through the Phase 5.1
    orchestrator (single writer + audit); this layer only renders the affordance
    and carries the id. A row missing an id degrades to read-only."""
    rows = []
    for idx, r in enumerate(reminders):
        rid = r.get("reminder_id") or ""
        title = r.get("title") or ""
        due = r.get("due_at")
        if rid:
            marker_html = (
                f'<span class="check" role="checkbox" tabindex="0" '
                f'aria-label="Complete: {_esc(title)}"></span>'
            )
            row_class = "goal goal-compact goal-reminder"
            attrs = (
                f'data-reminder-id="{_esc(rid)}" '
                f'data-reminder-title="{_esc(title)}"'
            )
        else:
            marker_html = _badge_marker("R")
            row_class = "goal goal-compact goal-readonly"
            attrs = ""
        rows.append(
            data_row(
                marker_html=marker_html,
                title_html=_linkify(title),
                timestamp=due,
                tz=tz,
                row_class=row_class,
                body_class="goal-body",
                title_class="goal-title",
                stripe_index=idx,
                attrs=attrs,
            )
        )
    if not rows:
        rows.append(empty_html)
    return "".join(rows)


def render_hero(
    goals: list[dict[str, Any]],
    pulled_from: str,
    now: datetime,
    obsidian_url: str | None,
    recent_completions: list[dict[str, Any]],
    secondary_todos: list[dict[str, Any]] | None = None,
    apple_reminders: list[dict[str, Any]] | None = None,
) -> str:
    secondary_todos = secondary_todos or []
    apple_reminders = apple_reminders or []
    visible_goals = [*goals, *secondary_todos]
    done = len(recent_completions)
    in_progress = len(visible_goals)
    total = done + in_progress
    pct = int((done / total) * 100) if total else 0
    primary_rows = _render_goal_rows(
        goals,
        empty_html='<li class="goal empty"><div class="goal-body"><div class="goal-title">No goals found</div><div class="goal-desc">Add checklist items to your Goals file.</div></div></li>',
    )
    secondary_rows = _render_goal_rows(
        secondary_todos,
        empty_html='<li class="goal empty goal-compact"><div class="goal-body"><div class="goal-title">No more open todos</div><div class="goal-desc">Everything else is clear.</div></div></li>',
        compact=True,
    )
    reminder_rows = _render_reminder_rows(
        apple_reminders,
        tz=TZ,
        empty_html='<li class="goal empty goal-compact goal-readonly"><div class="goal-body"><div class="goal-title">No active reminders</div><div class="goal-desc">Apple Reminders.</div></div></li>',
    )
    date_str = now.strftime("%A, %B %-d")
    open_link = (
        button_link("Open in Obsidian", obsidian_url, cls="hero-open")
        if obsidian_url else ""
    )
    undo_html = ""
    if recent_completions:
        undo_rows = [
            _render_recent_completion_row(item, stripe_index=idx)
            for idx, item in enumerate(recent_completions[:MAX_GOAL_HISTORY])
        ]
        undo_html = f"""
        <div id="goal-undo-tray" class="goal-undo-tray">
          {_subsection_label("Recently completed", count=len(undo_rows), extra_class="goal-undo-label")}
          <ul class="goal-undo-list rb-data-list">{''.join(undo_rows)}</ul>
        </div>
        """
    else:
        undo_html = '<div id="goal-undo-tray" class="goal-undo-tray is-empty" hidden></div>'
    return f"""
    <section class="hero card">
      <header class="hero-head">
        <div>
          <h1>Today's goals</h1>
          <div class="subtle">{date_str} · pulled from <code>{_esc(pulled_from)}</code> {open_link}</div>
        </div>
        <div class="hero-stats">
          <div><b>{done}</b> done</div>
          <div><b>{in_progress}</b> in progress</div>
          <div class="bar"><span style="width:{pct}%"></span></div>
        </div>
      </header>
      <div class="hero-goal-board">
        <div class="hero-goal-column">
          {_subsection_label("Goals", count=len(goals), extra_class="hero-column-label")}
          <ul class="goals rb-data-list">{primary_rows}</ul>
        </div>
        <div class="hero-goal-column hero-goal-column-secondary">
          {_subsection_label("Next open todos", count=len(secondary_todos), extra_class="hero-column-label")}
          <ul class="goals goals-secondary rb-data-list">{secondary_rows}</ul>
        </div>
        <div class="hero-goal-column hero-goal-column-reminders">
          {_subsection_label("Apple reminders", count=len(apple_reminders), extra_class="hero-column-label")}
          <ul class="goals goals-secondary rb-data-list">{reminder_rows}</ul>
        </div>
      </div>
      {undo_html}
    </section>
    """


def render_recent_activity(
    rows: list[dict[str, Any]],
    now: datetime,
    *,
    last_vault: dict[str, Any] | None = None,
    vault_recent_count: int = 0,
) -> str:
    items = []
    for idx, r in enumerate(rows):
        kind = r.get("kind") or "item"
        sub = r.get("sub") or ""
        badge_variant, badge_label = _activity_kind_meta(kind, sub)
        repo = r.get("repo_full_name") or ""
        repo_short = _repo_short_name(repo)
        num = r.get("num")
        detail = _truncate(r.get("detail") or "", 80)
        who = r.get("who") or ""
        ago = format_timestamp(r.get("ts"), relative=True, tz=TZ) or "—"
        if kind == "commit":
            ref = (str(num)[:7] if num else "")
            label = f"commit {ref}" if ref else "commit"
        elif kind == "item":
            label = f"{'PR' if sub == 'pull_request' else 'Issue'} #{num}" if num else (sub or "item")
        else:
            label = f"comment on #{num}" if num else "comment"
        html_url = r.get("html_url") or ""
        if html_url:
            label_html = (
                f'<a class="label" href="{_esc(html_url)}" '
                f'target="_blank" rel="noopener noreferrer">{_esc(label)}</a>'
            )
        else:
            label_html = f'<span class="label">{_esc(label)}</span>'
        meta_html = _join_row_bits(
            [
                (
                    f'<span class="repo" title="{_esc(repo)}">{_esc(repo_short)}</span>'
                    if repo else ""
                ),
                f'<span class="who">{("@" + _esc(who)) if who else ""}</span>' if who else "",
                f'<span class="detail">{_esc(detail)}</span>' if detail else "",
            ]
        )
        items.append(
            data_row(
                marker_html=badge_html(badge_variant, badge_label),
                title_html=label_html,
                meta_html=meta_html,
                timestamp=r.get("ts"),
                tz=TZ,
                relative=True,
                fallback_timestamp=ago,
                row_class="activity-row",
                marker_class="activity-type-marker",
                title_class="activity-label",
                meta_class="activity-meta",
                stripe_index=idx,
            )
        )
    body = "".join(items) if items else '<li class="empty">No recent activity.</li>'
    foot = ""
    if last_vault:
        title = _esc(last_vault.get("title") or last_vault.get("rel_path") or "vault note")
        ago = _timestamp_html(last_vault.get("last_modified"), tz=TZ, relative=True, fallback="—")
        foot = (
            f'<footer class="card-foot subtle">'
            f'Last vault edit · <span class="strong">{title}</span> · {ago}'
            f'{f" · {vault_recent_count} recent" if vault_recent_count else ""}'
            f'</footer>'
        )
    return f"""
    <section class="card activity">
      <header class="card-head"><h2>Recent GitHub activity</h2></header>
      <ol class="activity-list rb-data-list">{body}</ol>
      {foot}
    </section>
    """


def render_work_next(
    ranked_rows: list[dict[str, Any]],
    now: datetime,
    *,
    computed_at: str | None = None,
    blended: bool = False,
    model_used: str | None = None,
) -> str:
    """Render a SLIM teaser pointing at the dedicated "What's Next" page.

    The full ranked list lives on its OWN page — the FastAPI ``/whats-next`` route,
    served by pulse_server — so this static dashboard shows only a compact teaser
    (up to three rows + summary metadata + link) and does not crowd the main view.
    PURE: takes PRE-FETCHED rows (each ``RankedAction.as_dict()``) — never fetches.
    ``person`` labels are LOCAL-DISPLAY-ONLY (local dashboard, never the pushed
    pulse); all untrusted text is ``_esc``-ed.
    """
    link = button_link(
        f"Open What's Next → {len(ranked_rows)} ranked",
        "/whats-next",
        arrow=False,
        cls="wn-open",
    ) if ranked_rows else button_link("Open What's Next", "/whats-next", arrow=False, cls="wn-open")
    if not ranked_rows:
        return f"""
    <section class="card work-next work-next-teaser">
      <header class="card-head"><h2>What&#39;s next</h2></header>
      <div class="empty">No ranked next actions yet. {link}</div>
    </section>
    """

    auto = sum(1 for r in ranked_rows if r.get("automation"))
    computed_html = _timestamp_html(computed_at, tz=TZ, relative=True) if computed_at else ""
    when_html = f"computed {computed_html}" if computed_html else "not computed yet"
    meta_bits = []
    if auto:
        meta_bits.append(f'<span class="wn-auto">&#9881; {auto} automation-ready</span>')
    if blended:
        meta_bits.append("team-blended")
    meta_bits.append(when_html)
    teaser_rows = []
    for idx, top in enumerate(ranked_rows[:3]):
        top_title = _esc(top.get("title") or "")
        top_person = top.get("person")
        person_html = (
            f'<span class="wn-person">{_esc(top_person)}</span>' if top_person else ""
        )
        top_auto = (
            '<span class="wn-auto" aria-label="automation ready">&#9881;</span>'
            if top.get("automation") else ""
        )
        meta_html = _join_row_bits(
            [
                f'<span class="wn-source">{_esc((top.get("source") or "").upper())}</span>' if top.get("source") else "",
                f'<span class="wn-project">{_esc(top.get("project") or "")}</span>' if top.get("project") else "",
            ]
        )
        teaser_rows.append(
            data_row(
                marker_html=f'<span class="rb-data-marker-rank">{idx + 1}</span>',
                title_html=f'{top_title} {person_html} {top_auto}'.strip(),
                meta_html=meta_html,
                timestamp=computed_at,
                tz=TZ,
                relative=True,
                row_class="wn-row",
                title_class="wn-title",
                meta_class="wn-meta",
                stripe_index=idx,
            )
        )

    return f"""
    <section class="card work-next work-next-teaser">
      <header class="card-head">
        <h2>What&#39;s next</h2>
        <span class="card-head-meta">{' · '.join(meta_bits)}</span>
      </header>
      <ol class="wn-list rb-data-list">{''.join(teaser_rows)}</ol>
      <div class="wn-teaser-foot">{link}</div>
    </section>
    """


def render_org_activity(by_org: dict[str, list[dict[str, Any]]], *, days: int) -> str:
    """Doughnut chart of per-repo event counts, sourced from github_activity (no project_registry gate)."""
    if not by_org:
        return ""

    flat: list[tuple[str, int]] = []
    for org, repos in by_org.items():
        total = sum(
            int(r.get("commits") or 0)
            + int(r.get("prs_opened") or 0)
            + int(r.get("prs_merged") or 0)
            + int(r.get("issues_opened") or 0)
            for r in repos
        )
        flat.append((org, total))
    flat.sort(key=lambda t: t[1], reverse=True)

    if not flat:
        return ""

    labels = [t[0] for t in flat]
    values = [t[1] for t in flat]
    colors = [PIE_PALETTE[i % len(PIE_PALETTE)] for i in range(len(flat))]
    total = sum(values)
    payload = json.dumps({"labels": labels, "values": values, "colors": colors})

    return f"""
    <section class="card repo-pie">
      <header class="card-head">
        <h2>GitHub activity by org <span class="subtle">({days}d)</span></h2>
        <span class="card-head-meta">{total} events · {len(flat)} orgs</span>
      </header>
      <div class="repo-pie-wrap">
        <canvas id="org-activity-canvas" height="320"></canvas>
      </div>
      <script type="application/json" id="org-activity-data">{payload}</script>
    </section>
    """


# Stable, accessible palette — repeats if there are more repos than colors.
PIE_PALETTE = [
    "#7cc4ff", "#b388ff", "#ffb86b", "#7be08a", "#ff8aa1",
    "#ffd166", "#06d6a0", "#118ab2", "#ef476f", "#8d99ae",
    "#f4a261", "#c77dff",
]


def _render_repo_pie_new_badge(recent_promotion: dict[str, Any] | None) -> str:
    """GH-124: 'New repo added: X' banner when a commit-threshold auto-promotion
    landed within the repo-pie's own display window. Absent otherwise — this is
    an additive annotation, not a permanent chart feature."""
    if not recent_promotion:
        return ""
    project_name = recent_promotion.get("project_name") or recent_promotion.get("repo") or ""
    if not project_name:
        return ""
    return (
        '<div class="repo-pie-new-badge">New repo added: '
        f"{_esc(project_name)}</div>"
    )


def render_repo_pie(
    rows: list[dict[str, Any]], *, days: int, recent_promotion: dict[str, Any] | None = None
) -> str:
    """Doughnut chart of per-repo event counts over the last N days."""
    new_badge = _render_repo_pie_new_badge(recent_promotion)

    if not rows:
        return f"""
    <section class="card repo-pie">
      <header class="card-head"><h2>Repo activity ({_esc(days)}d)</h2></header>
      {new_badge}
      <div class="empty" style="padding:18px 4px;">No GitHub activity in the last {_esc(days)} days.</div>
    </section>
    """

    labels = [(r.get("repo_full_name") or "").split("/")[-1] for r in rows]
    values = [int(r.get("events") or 0) for r in rows]
    colors = [PIE_PALETTE[i % len(PIE_PALETTE)] for i in range(len(rows))]
    total = sum(values)

    payload = json.dumps({"labels": labels, "values": values, "colors": colors})

    return f"""
    <section class="card repo-pie">
      <header class="card-head">
        <h2>Repo activity ({_esc(days)}d)</h2>
        <span class="card-head-meta">{total} events · {len(rows)} repos</span>
      </header>
      {new_badge}
      <div class="repo-pie-wrap">
        <canvas id="repo-pie-canvas" height="320"></canvas>
      </div>
      <script type="application/json" id="repo-pie-data">{payload}</script>
    </section>
    """


def render_open_prs(rows: list[dict[str, Any]], now: datetime) -> str:
    if not rows:
        return """
    <section class="card open-prs">
      <header class="card-head"><h2>Open PRs</h2></header>
      <div class="empty">No open pull requests found.</div>
    </section>
    """
    items = []
    for pr in rows:
        age = pr["age_days"]
        if age <= 2:
            age_cls = "fresh"
        elif age <= 7:
            age_cls = "stale"
        else:
            age_cls = "danger"
        age_label = f"{age}d"

        title = _truncate(pr["title"], 72)
        url = _esc(pr["html_url"])
        repo = _esc(pr["repo_full_name"].split("/")[-1])  # short repo name
        num = pr["number"]
        author = _esc(pr["author_login"] or "")

        badges = []
        if pr["is_draft"]:
            badges.append('<span class="pr-badge draft">draft</span>')
        rd = (pr["review_decision"] or "").lower()
        if rd == "approved":
            badges.append('<span class="pr-badge approved">approved</span>')
        elif rd in ("changes_requested", "review_required"):
            badges.append('<span class="pr-badge review">review</span>')
        cs = pr.get("check_status") or ""
        if cs == "failing":
            badges.append('<span class="pr-badge ci-fail">✗ CI</span>')
        elif cs == "mixed":
            badges.append('<span class="pr-badge ci-mixed">~ CI</span>')
        elif cs == "pending":
            badges.append('<span class="pr-badge ci-pending">⟳ CI</span>')

        badge_html = " ".join(badges)
        title_html = f'<a href="{url}" target="_blank" rel="noopener noreferrer">#{num} {_esc(title)}</a>'

        row_attrs = ''
        if not pr["is_stale"]:
            row_attrs += ' data-fresh'
        if pr.get("ci_failing"):
            row_attrs += ' data-ci-fail'
        items.append(f"""
        <li class="pr-row"{row_attrs}>
          <span class="pr-age {age_cls}">{age_label}</span>
          <div>
            <div class="pr-title">{title_html} {badge_html}</div>
            <div class="pr-repo">{_esc(pr["repo_full_name"])}</div>
          </div>
          <span class="pr-meta">{author}</span>
          <span class="pr-meta timestamp-block">{_esc(format_timestamp(pr["updated_at"], relative=True, tz=TZ) or "—")}</span>
        </li>
        """)

    stale_count = sum(1 for pr in rows if pr["is_stale"])
    fail_count  = sum(1 for pr in rows if pr.get("ci_failing"))
    stale_btn = (
        f' · <button class="pr-filter-btn" data-pr-filter-stale>'
        f'{stale_count} stale</button>'
        if stale_count else ""
    )
    fail_btn = (
        f' · <button class="pr-filter-btn ci" data-pr-filter-ci>'
        f'{fail_count} failing CI</button>'
        if fail_count else ""
    )
    return f"""
    <section class="card open-prs" id="open-prs-card">
      <header class="card-head">
        <h2>Open PRs</h2>
        <span class="card-head-meta">{len(rows)} open{stale_btn}{fail_btn}</span>
      </header>
      <ol class="open-prs-list">{''.join(items)}</ol>
    </section>
    """


def render_watched(summary: dict[str, Any], now: datetime) -> str:
    last_html = _timestamp_html(summary.get("last_synced"), tz=TZ, relative=True, fallback="—")
    rows = [
        ("Watched",          summary.get("total", 0),         "neutral"),
        ("Fresh",            summary.get("fresh", 0),         "ok"),
        ("Stale",            summary.get("stale", 0),         "neutral"),
        ("Never synced",     summary.get("never", 0),         "danger" if summary.get("never") else "neutral"),
        ("Auto-discovered",  summary.get("auto_discovered", 0),"neutral"),
        ("Ignored",          summary.get("ignored", 0),       "muted"),
    ]
    items = []
    for label, value, tone in rows:
        items.append(f'<li><span class="row-label">{_esc(label)}</span><span class="row-value {tone}">{_esc(value)}</span></li>')
    return f"""
    <section class="card watched">
      <header class="card-head"><h2>Watched repos</h2></header>
      <ul class="kv-list">{''.join(items)}</ul>
      <footer class="card-foot subtle">Last sync activity · {last_html}</footer>
    </section>
    """


def render_index_health(status: dict[str, Any], now: datetime) -> str:
    sources = status.get("sources") or {}
    semantic = status.get("semantic_index") or {}
    freshness = status.get("freshness") or {}
    drift_total = sum(int(v) for v in freshness.values() if isinstance(v, int))
    rows = [
        ("Vault chunks",     (sources.get("vault")    or {}).get("chunks"),                (sources.get("vault")    or {}).get("last_ingested_at"),         "ok"),
        ("GitHub items",     (sources.get("github")   or {}).get("items"),                 (sources.get("github")   or {}).get("documents_last_fetched_at"), "warn"),
        ("GitHub docs",      (sources.get("github")   or {}).get("documents"),             (sources.get("github")   or {}).get("documents_last_updated_at"), "warn"),
        ("Calendar events",  (sources.get("calendar") or {}).get("events"),                (sources.get("calendar") or {}).get("last_fetched_at"),           "info"),
        ("Sleuth reminders", (sources.get("sleuth")   or {}).get("reminders"),             (sources.get("sleuth")   or {}).get("last_synced_at"),            "info"),
        ("Email messages",   (sources.get("email")    or {}).get("messages"),              (sources.get("email")    or {}).get("last_synced_at"),            "info"),
        ("Figma comments",   (sources.get("figma")    or {}).get("comments"),              (sources.get("figma")    or {}).get("last_synced_at"),            "info"),
        ("Semantic docs",    semantic.get("total_documents"),                              semantic.get("last_embedded_at"),                                  "ok"),
    ]
    items = []
    for label, count, last, tone in rows:
        ago = format_timestamp(last, relative=True, tz=TZ) if last else ""
        ago_html = (
            f'<span class="row-meta subtle timestamp-block">{_esc(ago)}</span>'
            if ago
            else '<span class="row-meta subtle">—</span>'
        )
        items.append(f"""
        <li>
          <span class="row-label">{_esc(label)}</span>
          <span class="row-value {tone}">{_esc(count if count is not None else '—')}</span>
          {ago_html}
        </li>
        """)
    drift_tone = "ok" if drift_total == 0 else "warn"
    drift_text = "in sync" if drift_total == 0 else "rows pending"
    items.append(f"""
    <li class="drift">
      <span class="row-label">Semantic drift</span>
      <span class="row-value {drift_tone}">{drift_total}</span>
      <span class="row-meta subtle">{drift_text}</span>
    </li>
    """)
    return f"""
    <section class="card health">
      <header class="card-head"><h2>Index health</h2></header>
      <ul class="kv-list">{''.join(items)}</ul>
    </section>
    """


def render_recent_emails(
    rows: list[dict[str, Any]],
    now: datetime,
    *,
    tz: ZoneInfo,
    limit: int,
    stored_total: int,
) -> str:
    if not rows:
        return f"""
    <section class="card recent-emails">
      <header class="card-head">
        <h2>Recent email</h2>
        <span class="card-head-meta">0 messages</span>
      </header>
      <div class="empty">No stored email messages yet.</div>
    </section>
    """

    items = []
    for idx, row in enumerate(rows):
        sender = _normalize_html_text(row.get("from_name") or "") or _normalize_html_text(row.get("from_address") or "") or "unknown sender"
        subject = _normalize_html_text(row.get("subject") or "") or "(no subject)"
        snippet = _truncate(_normalize_html_text(row.get("snippet") or ""), 180)
        when = format_timestamp(row.get("received_at"), relative=True, tz=tz) or "—"
        when_abs = format_timestamp(row.get("received_at"), tz=tz)
        gmail_url = build_gmail_thread_url(row)
        labels_raw = row.get("labels_json") or "[]"
        try:
            labels = json.loads(labels_raw)
        except json.JSONDecodeError:
            labels = []
        label_bits = []
        if "STARRED" in labels:
            label_bits.append('<span class="mail-badge starred">starred</span>')
        if "IMPORTANT" in labels:
            label_bits.append('<span class="mail-badge important">important</span>')

        subject_html = (
            f'<a class="email-row-link" href="{_esc(gmail_url)}" target="_blank" rel="noopener noreferrer">{_esc(subject)}</a>'
            if gmail_url else _esc(subject)
        )
        reply_html = (
            f'<a class="email-row-open" href="{_esc(gmail_url)}" target="_blank" rel="noopener noreferrer" aria-label="Open email thread in Gmail" title="Open in Gmail">'
            f'<span class="gmail-icon" aria-hidden="true">✉</span>'
            f'</a>'
            if gmail_url else ""
        )

        items.append(f"""
        <li class="email-row">
          <div class="email-row-main">
            <div class="email-row-subject">{subject_html}</div>
            <div class="email-row-meta">
              <span class="email-row-from">{_esc(sender)}</span>
              <span class="email-row-dot">·</span>
              <span class="email-row-when timestamp-block">{_esc(when)}</span>
              {f'<span class="email-row-dot">·</span>{"".join(label_bits)}' if label_bits else ""}
            </div>
            <div class="email-row-snippet">{_esc(snippet)}</div>
          </div>
          <div class="email-row-side">
            <div class="email-row-time timestamp-block">{_esc(when_abs)}</div>
            {reply_html}
          </div>
        </li>
        """)

    return f"""
    <section class="card recent-emails">
      <header class="card-head">
        <h2>Recent email</h2>
        <span class="card-head-meta">latest {min(len(rows), limit)} shown · {stored_total} stored</span>
      </header>
      <ol class="email-list">{''.join(items)}</ol>
    </section>
    """


def render_recent_figma(
    rows: list[dict[str, Any]],
    now: datetime,
    *,
    tz: ZoneInfo,
    limit: int,
    stored_total: int,
    configured_keys: list[str],
    last_synced_at: str | None,
) -> str:
    configured_total = len(configured_keys)
    sync_html = _timestamp_html(last_synced_at, tz=tz, relative=True, fallback="never synced")
    chips = "".join(
        f'<span class="figma-key-chip" title="{_esc(key)}">{_esc(key)}</span>'
        for key in configured_keys
    ) or '<span class="figma-key-empty">No Figma project IDs configured yet.</span>'

    form = f"""
      <form id="figma-project-form" class="figma-config-form">
        {_subsection_label("Add Figma project ID", extra_class="figma-config-label")}
        <div class="figma-config-help">Paste a Figma file key or full design URL. rebalance adds it to <code>figma_file_keys</code> and syncs comments.</div>
        <div class="figma-config-row">
          <input
            id="figma-project-input"
            class="figma-project-input"
            type="text"
            placeholder="Figma file key or design URL"
            autocomplete="off"
            spellcheck="false"
          >
          <button id="figma-project-submit" class="figma-project-btn" type="submit">Add + sync</button>
        </div>
        <div id="figma-project-status" class="figma-project-status subtle">
          Tracking {configured_total} project ID{'s' if configured_total != 1 else ''} · last sync {sync_html}
        </div>
        <div class="figma-key-list">{chips}</div>
      </form>
    """

    if not rows:
        return f"""
    <section class="card figma-comments">
      <header class="card-head">
        <h2>Recent Figma comments</h2>
        <span class="card-head-meta">{stored_total} stored · {configured_total} project{'s' if configured_total != 1 else ''}</span>
      </header>
      <div class="empty">No stored Figma comments yet.</div>
      <footer class="card-foot">{form}</footer>
    </section>
    """

    sorted_rows = sorted(
        rows,
        key=lambda row: _parse_iso(row.get("created_at") or row.get("synced_at"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    items = []
    for idx, row in enumerate(sorted_rows):
        author = _normalize_html_text(row.get("user_handle") or "") or _normalize_html_text(row.get("user_id") or "") or "Figma user"
        message = _truncate(_normalize_html_text(row.get("message") or ""), 220) or "(empty comment)"
        stamp_value = row.get("created_at") or row.get("synced_at")
        resolved = bool(row.get("resolved_at"))
        resolved_badge = '<span class="figma-badge resolved">resolved</span>' if resolved else ""
        file_key = _normalize_html_text(row.get("file_key") or "")
        file_link = _figma_file_link(file_key)
        title_html = _join_row_bits(
            [
                f'<span class="figma-row-author">{_esc(author)}</span>',
                resolved_badge,
            ]
        )
        meta_html = "".join(
            [
                f'<div class="figma-row-body">{_linkify(message)}</div>',
                f'<div class="figma-row-footer">{file_link}</div>' if file_link else "",
            ]
        )
        items.append(
            data_row(
                marker_html=_avatar_marker(author),
                title_html=title_html,
                meta_html=meta_html,
                timestamp=stamp_value,
                tz=tz,
                relative=True,
                fallback_timestamp="—",
                row_class="figma-row",
                title_class="figma-row-head",
                meta_class="figma-row-meta",
                stripe_index=idx,
            )
        )

    return f"""
    <section class="card figma-comments">
      <header class="card-head">
        <h2>Recent Figma comments</h2>
        <span class="card-head-meta">latest {min(len(rows), limit)} shown · {stored_total} stored</span>
      </header>
      <ol class="figma-list rb-data-list">{''.join(items)}</ol>
      <footer class="card-foot">{form}</footer>
    </section>
    """


# Calendar day-grid geometry. Constants, not literals sprinkled through the
# markup, so the grid can be retuned in one place (the design brief asks for
# 44px/hour by default). CAL_END_HOUR is inclusive — the 9 PM rule is drawn.
CAL_START_HOUR = 8
CAL_END_HOUR = 21
CAL_HOUR_PX = 44
CAL_GUTTER_PX = 44
CAL_MIN_EVENT_PX = 20
CAL_SHOW_TIME_PX = 36
CAL_UPCOMING_LIMIT = 5


def _cal_y(hour: float) -> float:
    """Vertical offset in px for a decimal hour, relative to the grid top."""
    return (hour - CAL_START_HOUR) * CAL_HOUR_PX


def _cal_clock(dt: datetime) -> str:
    """`1:45 PM` / `2 PM` — the compact in-block time label."""
    return dt.strftime("%-I:%M %p") if dt.minute else dt.strftime("%-I %p")


def render_calendar_module(
    today_rows: list[dict[str, Any]],
    upcoming_rows: list[dict[str, Any]],
    now: datetime,
    *,
    tz: ZoneInfo,
) -> str:
    """Render the sidebar Calendar module: a day grid plus an Upcoming list.

    Replaces the old flat text list with a Google-Calendar-style day view for
    TODAY (``CAL_START_HOUR``–``CAL_END_HOUR``), followed by the next
    ``CAL_UPCOMING_LIMIT`` events on later days.

    PURE: takes pre-fetched rows (``summary``/``start_time``/``end_time``/
    ``location``) and never queries. All time math is done in ``tz``; events
    outside the grid's hour range deliberately do not render as blocks — they
    surface in Upcoming instead, so nothing is silently dropped.
    """
    local_now = now.astimezone(tz)
    today = local_now.date()

    def _hydrate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for ev in rows:
            start = parse_utc_iso(ev.get("start_time"))
            if start is None:
                continue
            start = start.astimezone(tz)
            end = parse_utc_iso(ev.get("end_time"))
            # A missing end is assumed to be a 30-minute block — enough to render
            # a visible, correctly-placed block rather than dropping the event.
            end = end.astimezone(tz) if end else start + timedelta(minutes=30)
            out.append({**ev, "_start": start, "_end": end})
        return out

    # The grid needs today's WHOLE day (including finished events, which the
    # upcoming fetch cannot return); Upcoming needs strictly later days.
    todays = [e for e in _hydrate(today_rows) if e["_start"].date() == today]
    later = [e for e in _hydrate(upcoming_rows) if e["_start"].date() > today]

    # --- hour gutter + rules -------------------------------------------------
    hour_rows = []
    for hour in range(CAL_START_HOUR, CAL_END_HOUR + 1):
        ap = "PM" if hour >= 12 else "AM"
        h12 = hour % 12 or 12
        hour_rows.append(
            f'<div class="cal-hour" style="top:{_cal_y(hour):.0f}px">'
            f'<span class="cal-hour-label">{h12} {ap}</span>'
            f'<span class="cal-hour-rule"></span>'
            f"</div>"
        )

    # --- positioned event blocks --------------------------------------------
    blocks = []
    for ev in todays:
        start, end = ev["_start"], ev["_end"]
        start_h = start.hour + start.minute / 60
        end_h = end.hour + end.minute / 60
        # Outside the rendered window: skip the block, Upcoming/other surfaces cover it.
        if end_h <= CAL_START_HOUR or start_h >= CAL_END_HOUR:
            continue
        top = _cal_y(max(start_h, CAL_START_HOUR))
        height = max(_cal_y(min(end_h, CAL_END_HOUR)) - top, CAL_MIN_EVENT_PX)
        state = "past" if end < local_now else "upcoming"
        title = _esc(ev.get("summary") or "event")
        time_line = (
            f'<span class="cal-event-time">{_cal_clock(start)} – {_cal_clock(end)}</span>'
            if height >= CAL_SHOW_TIME_PX
            else ""
        )
        blocks.append(
            f'<div class="cal-event {state}" style="top:{top:.0f}px;height:{height:.0f}px"'
            f' data-cal-end-min="{end.hour * 60 + end.minute}" title="{title}">'
            f'<span class="cal-event-title">{title}</span>{time_line}'
            f"</div>"
        )

    # --- now indicator -------------------------------------------------------
    now_h = local_now.hour + local_now.minute / 60
    now_html = ""
    if CAL_START_HOUR <= now_h <= CAL_END_HOUR:
        now_html = (
            f'<div class="cal-now" id="cal-now" style="top:{_cal_y(now_h):.0f}px">'
            f'<span class="cal-now-dot"></span><span class="cal-now-line"></span>'
            f"</div>"
        )

    # --- upcoming ------------------------------------------------------------
    up_rows = []
    for idx, ev in enumerate(later[:CAL_UPCOMING_LIMIT]):
        title = ev.get("summary") or "event"
        loc = ev.get("location") or ""
        label = f"{title} · {_truncate(loc, 28)}" if loc else title
        stamp = format_timestamp(ev["_start"], month_day=True, tz=tz)
        stripe = "even" if idx % 2 else "odd"
        up_rows.append(
            f'<div class="cal-up-row" data-rb-stripe="{stripe}">'
            f'<span class="cal-up-time timestamp-block">{_esc(stamp)}</span>'
            f'<span class="cal-up-title" title="{_esc(label)}">{_esc(label)}</span>'
            f"</div>"
        )
    upcoming_html = (
        f'<div class="cal-upcoming">'
        f'{_subsection_label("Upcoming", count=len(later[:CAL_UPCOMING_LIMIT]))}'
        f'<div class="cal-up-list">{"".join(up_rows)}</div></div>'
        if up_rows
        else ""
    )

    grid_height = _cal_y(CAL_END_HOUR) + 1
    date_line = local_now.strftime("%A · %Y-%m-%d")
    return (
        f'<div class="cal-module">'
        f'<div class="cal-date timestamp-block">{_esc(date_line)}</div>'
        f'<div class="cal-grid" style="height:{grid_height:.0f}px"'
        f' data-cal-start="{CAL_START_HOUR}" data-cal-end="{CAL_END_HOUR}"'
        f' data-cal-hour-px="{CAL_HOUR_PX}">'
        f'{"".join(hour_rows)}'
        f'<div class="cal-gutter-rule"></div>'
        f'{"".join(blocks)}{now_html}'
        f"</div>{upcoming_html}</div>"
    )


def build_nav_data(
    *,
    in_progress: int,
    cal_rows: list[dict[str, Any]],
    cal_today_rows: list[dict[str, Any]],
    sleuth_rows: list[dict[str, Any]],
    sleuth_synced: bool,
    sleuth_sections: list[dict[str, Any]] | None = None,
    streams: list[dict[str, Any]],
    drift_total: int,
    semantic_total: int,
    notices: list[Check] | None = None,
    tz: ZoneInfo,
    now: datetime,
) -> dict[str, Any]:
    """Render the sidebar's dynamic sections to HTML and bundle them for
    ``render_sidebar``.

    This is the data/I-O-aware half that lives in pulse_web (it uses the Slack /
    Sleuth helpers and the DB-derived rows). The pure shell that frames these
    strings lives in :func:`rebalance.web_components.render_sidebar`, which keeps
    that module free of I/O.

    When ``sleuth_sections`` is provided (from ``fetch_sleuth_display_sections``),
    reminders are rendered with the same section/label/assignee format as the
    Slack "show reminders" command. Falls back to the flat ``sleuth_rows`` path
    when the published file is unavailable.
    """
    cal_html = render_calendar_module(cal_today_rows, cal_rows, now, tz=tz)

    sleuth_items = []
    if sleuth_sections:
        # Published-file path: section headers + canonical "show reminders" format.
        reminder_idx = 0
        for section in sleuth_sections:
            section_label = section.get("sectionLabel", "")
            reminder_count = len(section.get("reminders") or [])
            sleuth_items.append(
                f'<li class="section-label nav-list-section-label">'
                f'{_esc(section_label)}'
                f'<span class="section-label-count"> · {_esc(reminder_count)}</span>'
                f'</li>'
            )
            for r in section.get("reminders") or []:
                label    = r.get("label", "")
                summary  = _truncate(r.get("summary", ""), 90)
                age_days = int(r.get("ageDays") or 0)
                assignee = r.get("assigneeName", "")
                permalink = r.get("permalink", "")
                meta_html = _join_row_bits(
                    [
                        _esc(assignee) if assignee else "",
                        _age_chip(age_days),
                    ]
                )
                sleuth_items.append(
                    data_row(
                        marker_html=_badge_marker(_reminder_marker_text(str(label))),
                        title_html=_esc(summary),
                        meta_html=meta_html,
                        timestamp=r.get("shouldPostOn"),
                        tz=tz,
                        row_class="side-row has-link" if permalink else "side-row",
                        title_class="side-row-title",
                        meta_class="side-row-meta",
                        stripe_index=reminder_idx,
                        href=permalink or None,
                        link_title="Open in Slack",
                        external=bool(permalink),
                        link_class="side-row-link",
                    )
                )
                reminder_idx += 1
    else:
        # Fallback: flat list from SQLite (no display fields available).
        for idx, s in enumerate(sleuth_rows):
            msg = compact_sleuth_reminder(s.get("reminder_message_text") or "")
            msg = _truncate(msg, 90)
            role = "from me" if s.get("sleuth_role") == "assigned_by_me" else "for me"
            slack_url = build_slack_url(s)
            sleuth_items.append(
                data_row(
                    marker_html=_badge_marker("R"),
                    title_html=_esc(msg),
                    meta_html=_esc(role),
                    timestamp=s.get("should_post_on"),
                    tz=tz,
                    row_class="side-row has-link" if slack_url else "side-row",
                    title_class="side-row-title",
                    meta_class="side-row-meta",
                    stripe_index=idx,
                    href=slack_url,
                    link_title="Open in Slack",
                    external=bool(slack_url),
                    link_class="side-row-link",
                )
            )
    if not sleuth_items:
        if sleuth_synced:
            # Genuinely empty — Sleuth synced and there is nothing pending.
            sleuth_items.append(
                '<li class="side-row empty"><div class="side-row-meta">Inbox clear.</div></li>'
            )
        else:
            # Sleuth has never synced — do not pass this off as "all clear".
            sleuth_items.append(
                '<li class="side-row empty">'
                '<div class="side-row-meta warn">Not configured 🛠️</div>'
                '</li>'
            )

    # Notices — intentional / non-actionable WARNs, demoted off the verdict but
    # kept visible in a scrollable module.
    notice_items = []
    for c in (notices or []):
        detail = _truncate(_compact_whitespace(c.detail), 140)
        hint = _truncate(_compact_whitespace(c.hint), 140) if c.hint else ""
        hint_html = f'<div class="side-row-hint">→ {_esc(hint)}</div>' if hint else ""
        notice_items.append(f"""
          <li class="side-row notice-row">
            <div class="side-row-title">{_esc(c.name)}</div>
            <div class="side-row-meta">{_esc(detail)}</div>
            {hint_html}
          </li>
        """)
    notices_section = ""
    if notice_items:
        notices_section = f"""
        {_subsection_label("Notices", count=len(notice_items), extra_class="nav-section-label")}
        <ul class="side-list notices-scroll">{''.join(notice_items)}</ul>
        """

    return {
        "badge": in_progress,
        "cal_html": cal_html,
        "sleuth_html": "".join(sleuth_items),
        "notices_html": notices_section,
        "streams": streams,
        "drift_total": drift_total,
        "semantic_total": semantic_total,
    }


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------

# Page-LOCAL CSS for the dashboard only: hero/goals/health-banner/repo-pie/
# topbar/email/open-prs/charts + the responsive @media collapse (which is
# interleaved with page rules and so stays here). The shared tokens + chrome
# come from RB_TOKENS_CSS + RB_CHROME_CSS; render_shell() injects this slice
# between them and RB_BUTTON_CSS. Leading "\n\n" reproduces the blank line the
# original single CSS literal had between the chrome and the hero rules.
PAGE_CSS = """

/* Hero "Open in Obsidian" link */
.hero-open { margin-left: 8px; }  /* visual styling now from the shared .rb-btn */
.card-foot .strong { color: var(--fg); font-weight: 500; }

/* Main */
.topbar { display: flex; align-items: flex-start; justify-content: space-between; }
.topbar .crumb { color: var(--fg-muted); font-weight: 500; padding-top: 4px; }
.topbar-right { display: flex; flex-direction: column; gap: 6px; align-items: flex-end; }
.topbar-row { display: flex; gap: 10px; align-items: center; }
.synced { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border: 1px solid var(--border); border-radius: 999px; background: var(--card); font-size: 12px; color: var(--fg-muted); }
.synced .ok-dot { width: 8px; height: 8px; background: var(--ok); border-radius: 50%; }
.synced.synced-warn { border-color: color-mix(in srgb, var(--warn) 22%, transparent); color: var(--warn); background: color-mix(in srgb, var(--warn) 8%, transparent); }
.synced.synced-warn .ok-dot { background: var(--warn); }
.synced.synced-danger { border-color: color-mix(in srgb, var(--danger) 18%, transparent); color: var(--danger); background: color-mix(in srgb, var(--danger) 8%, transparent); }
.synced.synced-danger .ok-dot { background: var(--danger); }

/* Status dot glow pulse */
@keyframes glow-ok {
  0%, 100% { box-shadow: 0 0 0   0   transparent; }
  50%       { box-shadow: 0 0 5px 3px color-mix(in srgb, var(--ok) 40%, transparent); }
}
@keyframes glow-warn {
  0%, 100% { box-shadow: 0 0 0   0   transparent; }
  50%       { box-shadow: 0 0 5px 3px color-mix(in srgb, var(--warn) 40%, transparent); }
}
.ok-dot                        { animation: glow-ok   2.8s ease-in-out infinite; }
.health-dot                    { animation: glow-ok   2.8s ease-in-out infinite; }
.health-pill.has-issues .health-dot { animation: glow-warn 2.8s ease-in-out infinite; }
.system-now { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border: 1px dashed var(--border); border-radius: 999px; background: var(--card); font-size: 12px; color: var(--fg-muted); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; cursor: help; }
.system-now .tz-key { color: var(--fg); }
.system-now.tz-fallback { border-color: var(--warn); color: var(--warn); }
.refresh-btn { font: inherit; padding: 6px 14px; border: 0; border-radius: 8px; background: var(--accent); color: var(--accent-ink); cursor: pointer; font-weight: 500; }
.refresh-btn:disabled { opacity: .55; cursor: progress; }
.pulse-filter { font: inherit; padding: 6px 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--card); color: var(--fg); width: 220px; }
.pulse-filter:focus { outline: none; border-color: var(--accent); }
/* Search mode toggle (Filter | Ask) + chat results */
.search-wrap { position: relative; display: inline-flex; align-items: center; gap: 8px; }
.search-mode { display: inline-flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--card); }
.search-mode-btn { font: inherit; font-size: 12px; line-height: 1; padding: 6px 10px; border: 0; background: transparent; color: var(--fg-muted); cursor: pointer; }
.search-mode-btn + .search-mode-btn { border-left: 1px solid var(--border); }
.search-mode-btn.is-active { background: var(--accent); color: var(--accent-ink); }
.search-wrap.mode-ask .pulse-filter { width: 300px; border-color: var(--accent); }
.chat-results { position: absolute; top: calc(100% + 6px); right: 0; width: 480px; max-width: 70vw; max-height: 62vh; overflow-y: auto; background: var(--card); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow); padding: 10px; z-index: 60; text-align: left; }
.chat-meta, .chat-status { font-size: 12px; color: var(--fg-dim); padding: 2px 4px 8px; }
.chat-status.error { color: var(--danger); }
.chat-cite-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.chat-cite { border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; }
.chat-cite-head { display: flex; align-items: baseline; gap: 8px; }
.chat-cite-source { font-size: 10px; text-transform: uppercase; letter-spacing: .06em; color: var(--accent-ink); background: var(--fg-dim); border-radius: 999px; padding: 1px 7px; white-space: nowrap; }
.chat-cite-title { font-weight: 600; font-size: 13px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fg); }
.chat-cite-score { font-size: 11px; color: var(--fg-dim); white-space: nowrap; }
.chat-cite-preview { font-size: 12px; color: var(--fg-muted); margin-top: 4px; line-height: 1.4; }
.is-hidden-by-filter { display: none !important; }
.timestamp-block {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
  color: var(--timestamp);
}
.health-banner {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  align-items: center;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.health-banner-warn {
  border-color: color-mix(in srgb, var(--warn) 22%, transparent);
  background: linear-gradient(90deg, color-mix(in srgb, var(--warn) 10%, transparent), color-mix(in srgb, var(--page) 96%, transparent));
}
.health-banner-danger {
  border-color: color-mix(in srgb, var(--danger) 18%, transparent);
  background: linear-gradient(90deg, color-mix(in srgb, var(--danger) 11%, transparent), color-mix(in srgb, var(--page) 96%, transparent));
}
/* Sidebar Notices module — scrollable viewer for demoted WARNs */
.notices-scroll {
  max-height: 168px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}
.notices-scroll::-webkit-scrollbar { width: 7px; }
.notices-scroll::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--muted) 32%, transparent); border-radius: 4px;
}
.side-row.notice-row .side-row-hint {
  color: var(--fg-dim); font-size: 11px; margin-top: 2px;
}
.health-banner-lead {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
}
.health-banner-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--card) 88%, transparent);
  border: 1px solid color-mix(in srgb, var(--ink) 6%, transparent);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
}
.health-banner-summary {
  font-weight: 700;
  color: var(--fg);
}
.health-banner-activity {
  color: var(--fg-muted);
  font-size: 12px;
}
.health-banner-copy-btn {
  font: inherit;
  border: 1px solid color-mix(in srgb, var(--ink) 8%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--card) 92%, transparent);
  color: var(--fg);
  width: 34px;
  height: 34px;
  padding: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}
.health-banner-copy-btn:hover {
  background: var(--card);
}
.health-banner-copy-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.health-banner-copy-icon {
  width: 16px;
  height: 16px;
}
.health-banner-copy-btn.is-copied {
  color: var(--ok);
  border-color: color-mix(in srgb, var(--ok) 18%, transparent);
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.health-banner-items {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  overflow-x: auto;
  padding-bottom: 2px;
}
.health-banner-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--card) 78%, transparent);
  border: 1px solid color-mix(in srgb, var(--ink) 5%, transparent);
  white-space: nowrap;
  flex: 0 0 auto;
}
.health-banner-name {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: var(--fg);
}
.health-banner-detail {
  color: var(--fg-muted);
  font-size: 12px;
}
.health-banner-item.more {
  color: var(--fg-muted);
  font-weight: 600;
}

/* Card */
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow); overflow: hidden; }
.card-head { display: flex; align-items: baseline; justify-content: space-between; padding: 14px 18px 10px; }
.card-head-meta { color: var(--fg-dim); font-size: 12px; font-variant-numeric: tabular-nums; }
.card-foot { padding: 10px 18px 14px; border-top: 1px solid var(--border); }
.section-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--fg-dim);
}
.section-label-count { font-variant-numeric: tabular-nums; }
.nav-list-section-label {
  list-style: none;
  padding: 10px 8px 3px;
  pointer-events: none;
}

/* What should we work on next */
.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}
.badge-ok      { background: color-mix(in srgb, var(--ok) 12%, transparent); color: var(--ok); }
.badge-warn    { background: color-mix(in srgb, var(--warn) 12%, transparent); color: var(--warn); }
.badge-danger  { background: color-mix(in srgb, var(--danger) 12%, transparent); color: var(--danger); }
.badge-info    { background: color-mix(in srgb, var(--info) 12%, transparent); color: var(--info); }
.badge-neutral { background: color-mix(in srgb, var(--fg-dim) 14%, transparent); color: var(--fg-muted); }

.work-next .wn-list { margin: 0; padding: 4px 0 10px; }
.wn-row[data-rb-row] { padding: 10px 18px; }
.wn-row .rb-data-row-marker { padding-top: 0; align-items: center; }
.wn-row .rb-data-row-trailing { min-width: 72px; }
.wn-title { color: var(--fg); font-weight: 600; }
.wn-person {
  margin-left: 6px; padding: 1px 7px; border-radius: 999px;
  background: var(--border); color: var(--fg-muted);
  font-size: 11px; font-weight: 600; vertical-align: middle;
}
.wn-meta { color: var(--fg-dim); font-size: 12px; margin-top: 2px; }
.wn-source { text-transform: uppercase; letter-spacing: 0.04em; }
.work-next-teaser .wn-teaser-foot { margin-top: 6px; padding: 0 18px 14px; }
.wn-open { color: var(--accent); font-weight: 600; font-size: 13px; text-decoration: none; }
.wn-open:hover { text-decoration: underline; }
.wn-auto { color: var(--warn); font-weight: 600; }

/* Hero */
.hero { padding: 22px 24px; }
.hero-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.hero-stats { display: flex; align-items: center; gap: 14px; color: var(--fg-muted); font-size: 13px; }
.hero-stats b { color: var(--fg); font-weight: 600; }
.hero-stats .bar { width: 80px; height: 6px; background: var(--border); border-radius: 999px; overflow: hidden; }
.hero-stats .bar span { display: block; height: 100%; background: var(--accent); }
.hero-stats .pct { font-variant-numeric: tabular-nums; min-width: 32px; text-align: right; }

.hero-goal-board { display: grid; grid-template-columns: minmax(0, 1fr) minmax(240px, 1fr) minmax(240px, 1fr); gap: 14px; align-items: stretch; }
.hero-goal-column { min-width: 0; }
.goal-readonly { padding-left: 6px; }
.hero-column-label { margin: 0 6px 4px; }
.goals { padding: 0; margin: 0; }
.goal[data-rb-row] { padding: 12px 6px; gap: 14px; }
.goal .check { width: 18px; height: 18px; border-radius: 5px; border: 1.5px solid var(--border); margin-top: 2px; flex-shrink: 0; background: var(--card); cursor: pointer; transition: border-color .12s, background .12s; }
.goal .check[role="checkbox"]:hover { border-color: var(--accent); }
.goal .check[role="checkbox"]:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.goal.is-busy .check { opacity: .55; cursor: progress; }
.goal.is-completing { opacity: 0; transition: opacity .18s ease-out; pointer-events: none; }
.goal .check.checked { background: var(--accent); border-color: var(--accent); position: relative; }
.goal .check.checked::after { content: ""; position: absolute; left: 4px; top: 1px; width: 5px; height: 9px; border: solid var(--accent-ink); border-width: 0 2px 2px 0; transform: rotate(45deg); }
.goal-title { font-weight: 600; color: var(--fg); }
.goal-desc { color: var(--fg-muted); font-size: 12.5px; margin-top: 2px; }
.goal-title a, .goal-desc a { color: var(--accent); text-decoration: none; }
.goal-title a:hover, .goal-desc a:hover { text-decoration: underline; }
.goal.done .goal-title { text-decoration: line-through; color: var(--fg-dim); }
.goal.done .goal-desc { color: var(--fg-dim); }
.goal-compact[data-rb-row] { padding: 12px 6px; gap: 14px; }
.goal-compact .check { width: 18px; height: 18px; border-radius: 5px; }
.goal-compact .check.checked::after { left: 4px; top: 1px; width: 5px; height: 9px; }
.goal-compact .goal-title { font-size: 13px; line-height: 1.35; }
.goal-compact .goal-desc { font-size: 12.5px; }
.goal-readonly .rb-data-row-marker { padding-top: 0; }
.goal-readonly .rb-data-marker-badge { width: 18px; height: 18px; font-size: 10px; }
.goal-undo-tray {
  border-top: 1px solid var(--border);
  margin-top: 8px;
  padding: 14px 6px 4px;
}
.goal-undo-tray.is-empty { display: none; }
.goal-undo-label { margin-bottom: 10px; }
.goal-undo-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.goal-undo-item {
  padding: 10px 6px;
}
.goal-undo-item .rb-data-row-trailing { min-width: 74px; gap: 8px; }
.goal-undo-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--fg-dim);
  text-decoration: line-through;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.goal-undo-btn {
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--card);
  color: var(--accent);
  padding: 5px 11px;
  font-size: 11.5px;
  font-weight: 600;
  flex-shrink: 0;
  text-decoration: none;
}
.goal-undo-btn:hover {
  border-color: color-mix(in srgb, var(--accent) 28%, transparent);
  background: color-mix(in srgb, var(--accent) 7%, transparent);
  text-decoration: none;
}
.goal-undo-btn[aria-disabled="true"] {
  opacity: .55;
  cursor: progress;
  pointer-events: none;
}

/* Two-column body */
.grid { display: grid; grid-template-columns: minmax(0,2fr) minmax(0,1fr); gap: 16px; }
.grid .col { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.full-row { margin-top: 16px; }

/* Repo activity doughnut */
.repo-pie .card-head { display: flex; align-items: baseline; justify-content: space-between; }
.repo-pie .card-head-meta { color: var(--fg-dim); font-size: 12px; font-variant-numeric: tabular-nums; }
.repo-pie-wrap { padding: 8px 14px 16px; }
.repo-pie-wrap canvas { max-width: 100%; }
/* GH-124: commit-threshold auto-promotion top-item annotation */
.repo-pie-new-badge { margin: 4px 14px 0; padding: 6px 10px; border-radius: 8px; background: color-mix(in srgb, var(--ok) 14%, transparent); color: var(--ok); font-size: 12px; font-weight: 600; }

/* Activity */
.activity-list { list-style: none; padding: 0 4px 14px; margin: 0; }
.activity-row[data-rb-row] { padding: 10px 14px; }
.activity-row .rb-data-row-marker.activity-type-marker {
  width: auto;
  min-width: 56px;
  justify-content: flex-start;
  padding-top: 0;
}
.activity-row .rb-data-row-trailing { min-width: 72px; }
.activity-row .label { font-weight: 500; }
.activity-row a.label { text-decoration: none; }
.activity-row a.label:hover { text-decoration: underline; }
.activity-meta { font-size: 12px; }
.activity-row .repo { color: var(--fg-muted); }
.activity-row .who { color: var(--fg-dim); }
.activity-row .detail { color: var(--fg-muted); font-size: 12.5px; }

/* Recent email */
.recent-emails .card-head { align-items: center; }
.email-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 740px;
  overflow-y: auto;
}
.email-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  padding: 12px 18px;
  border-top: 1px solid var(--border);
  align-items: start;
}
.email-row:first-child { border-top: 0; }
.email-row-main { min-width: 0; }
.email-row-subject {
  font-weight: 600;
  color: var(--fg);
  margin-bottom: 3px;
}
.email-row-link {
  color: inherit;
  text-decoration: none;
}
.email-row-link:hover {
  color: var(--accent);
  text-decoration: underline;
}
.email-row-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  color: var(--fg-dim);
  font-size: 11.5px;
  margin-bottom: 4px;
}
.email-row-from { color: var(--fg-muted); }
.email-row-dot { color: var(--fg-dim); }
.email-row-snippet {
  color: var(--fg-muted);
  font-size: 12.5px;
  line-height: 1.4;
}
.email-row-time {
  color: var(--timestamp);
  font-size: 11.5px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.email-row-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.email-row-open {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  text-decoration: none;
  white-space: nowrap;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--card);
  box-shadow: 0 1px 2px color-mix(in srgb, var(--ink) 3%, transparent);
}
.email-row-open:hover {
  text-decoration: none;
  border-color: color-mix(in srgb, var(--accent) 28%, transparent);
  background: color-mix(in srgb, var(--accent) 7%, transparent);
}
.gmail-icon {
  font-size: 14px;
  line-height: 1;
}
.mail-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .01em;
  border: 1px solid var(--border);
  background: var(--card);
}
.mail-badge.starred {
  color: var(--warn);
  border-color: color-mix(in srgb, var(--warn) 22%, transparent);
  background: color-mix(in srgb, var(--warn) 8%, transparent);
}
.mail-badge.important {
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 20%, transparent);
  background: color-mix(in srgb, var(--danger) 8%, transparent);
}

/* Recent Figma comments */
.figma-comments .card-head { align-items: center; }
.figma-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 540px;
  overflow-y: auto;
}
.figma-row[data-rb-row] { gap: 14px; padding: 12px 18px; }
.figma-row .rb-data-row-trailing { min-width: 72px; }
.figma-row-head {
  color: var(--fg-muted);
  font-size: 11.75px;
  font-weight: 600;
}
.figma-row-meta { color: var(--fg-dim); font-size: 11.5px; }
.figma-row-body {
  color: var(--fg);
  font-size: 12.75px;
  line-height: 1.45;
}
.figma-row-footer { margin-top: 6px; }
.figma-row-author { color: var(--fg-muted); font-weight: 600; }
.figma-row-link { color: var(--accent); font-size: 11.5px; text-decoration: none; }
.figma-row-link:hover { text-decoration: underline; }
.figma-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 600;
  border: 1px solid var(--border);
  background: var(--card);
}
.figma-badge.resolved {
  color: var(--ok);
  border-color: color-mix(in srgb, var(--ok) 22%, transparent);
  background: color-mix(in srgb, var(--ok) 8%, transparent);
}
.side-age-chip {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--fg-dim) 24%, transparent);
  background: color-mix(in srgb, var(--fg-dim) 8%, transparent);
  color: var(--fg-dim);
  font-size: 10.5px;
  font-weight: 600;
}
.figma-config-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.figma-config-help {
  color: var(--fg-muted);
  font-size: 12px;
  line-height: 1.45;
}
.figma-config-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}
.figma-project-input {
  font: inherit;
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--card);
  color: var(--fg);
}
.figma-project-input:focus {
  outline: none;
  border-color: var(--accent);
}
.figma-project-btn {
  font: inherit;
  padding: 9px 14px;
  border: 0;
  border-radius: 10px;
  background: var(--accent);
  color: var(--accent-ink);
  cursor: pointer;
  font-weight: 600;
  white-space: nowrap;
}
.figma-project-btn:disabled {
  opacity: .55;
  cursor: progress;
}
.figma-project-status.is-error { color: var(--danger); }
.figma-project-status.is-success { color: var(--ok); }
.figma-key-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.figma-key-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--fg-muted);
  font-size: 11.5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.figma-key-empty {
  color: var(--fg-dim);
  font-size: 11.5px;
}

/* KV lists (watched / health) */
.kv-list { list-style: none; padding: 6px 18px 10px; margin: 0; }
.kv-list li { display: grid; grid-template-columns: 1fr auto auto; gap: 10px; padding: 6px 0; align-items: baseline; }
.kv-list .row-label { color: var(--fg); }
.kv-list .row-value { font-variant-numeric: tabular-nums; font-weight: 600; }
.kv-list .row-meta { font-variant-numeric: tabular-nums; }
.kv-list li.drift { border-top: 1px dashed var(--border); margin-top: 6px; padding-top: 10px; }

/* Tones */
.ok      { color: var(--ok); }
.warn    { color: var(--warn); }
.danger  { color: var(--danger); }
.info    { color: var(--info); }
.muted   { color: var(--fg-dim); }
.neutral { color: var(--fg); }

/* Strip */
.strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; padding: 4px 4px 24px; }
.strip-title { font-weight: 500; }
.empty { color: var(--fg-dim); padding: 14px 18px; }

@media (max-width: 1100px) {
  .app { grid-template-columns: 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid var(--border); }
  .grid { grid-template-columns: 1fr; }
  .hero-goal-board { grid-template-columns: 1fr; }
  .hero-goal-column-secondary,
  .hero-goal-column-reminders { border-left: 0; border-top: 1px solid var(--border); padding-left: 0; padding-top: 10px; }
  .email-row { grid-template-columns: 1fr; }
  .email-row-side { align-items: flex-start; }
  .email-row-time { white-space: normal; }
  .figma-config-row { grid-template-columns: 1fr; }
  .topbar { flex-direction: column; align-items: stretch; gap: 12px; }
  .topbar > div:last-child { flex-wrap: wrap; }
  .health-banner { grid-template-columns: 1fr; }
  .health-banner-lead { flex-wrap: wrap; white-space: normal; }
}

/* Open PRs card */
.open-prs-list { list-style: none; margin: 0; padding: 0; }
.pr-row {
  display: grid;
  grid-template-columns: 48px minmax(0,1fr) 80px minmax(180px, 220px);
  gap: 10px;
  padding: 10px 18px;
  border-top: 1px solid var(--border);
  align-items: baseline;
}
.pr-row:first-child { border-top: 0; }
.pr-age { font-variant-numeric: tabular-nums; font-size: 12px; font-weight: 600; text-align: right; }
.pr-age.fresh  { color: var(--ok); }
.pr-age.stale  { color: var(--warn); }
.pr-age.danger { color: var(--danger); }
.pr-title { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pr-title a { color: var(--fg); text-decoration: none; }
.pr-title a:hover { color: var(--accent); text-decoration: underline; }
.pr-repo { font-size: 11.5px; color: var(--fg-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pr-meta { font-size: 11.5px; text-align: right; line-height: 1.35; }
.pr-badge {
  display: inline-block; padding: 1px 6px; border-radius: 999px;
  font-size: 10.5px; font-weight: 600; border: 1px solid var(--border);
  background: var(--card); color: var(--fg-muted); vertical-align: middle;
}
.pr-badge.draft  { color: var(--fg-dim); border-color: var(--border); }
.pr-badge.review { color: var(--warn); border-color: color-mix(in srgb, var(--warn) 25%, transparent); background: color-mix(in srgb, var(--warn) 7%, transparent); }
.pr-badge.approved { color: var(--ok); border-color: color-mix(in srgb, var(--ok) 25%, transparent); background: color-mix(in srgb, var(--ok) 7%, transparent); }
/* CI check-status badges */
.pr-badge.ci-fail    { color: var(--danger); border-color: color-mix(in srgb, var(--danger) 25%, transparent); background: color-mix(in srgb, var(--danger) 7%, transparent); }
.pr-badge.ci-mixed   { color: var(--warn);   border-color: color-mix(in srgb, var(--warn) 25%, transparent);  background: color-mix(in srgb, var(--warn) 7%, transparent);  }
.pr-badge.ci-pending { color: var(--fg-dim); border-color: var(--border); }
/* Stale / CI filter toggles */
.pr-filter-btn {
  font: inherit; font-size: 12px; font-weight: 600;
  padding: 2px 8px; border-radius: 999px; cursor: pointer;
  border: 1px solid color-mix(in srgb, var(--warn) 30%, transparent); background: color-mix(in srgb, var(--warn) 8%, transparent);
  color: var(--warn); transition: background .12s, color .12s;
}
.pr-filter-btn:hover  { background: color-mix(in srgb, var(--warn) 16%, transparent); }
.pr-filter-btn.active { background: var(--warn); color: var(--accent-ink); border-color: var(--warn); }
.pr-filter-btn.ci              { border-color: color-mix(in srgb, var(--danger) 30%, transparent); background: color-mix(in srgb, var(--danger) 8%, transparent); color: var(--danger); }
.pr-filter-btn.ci:hover        { background: color-mix(in srgb, var(--danger) 16%, transparent); }
.pr-filter-btn.ci.active       { background: var(--danger); color: var(--accent-ink); border-color: var(--danger); }
.open-prs.filter-stale .pr-row[data-fresh]    { display: none; }
.open-prs.filter-ci    .pr-row:not([data-ci-fail]) { display: none; }

/* Health pill */
.health-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 999px; font-size: 12px;
  border: 1px solid var(--border); background: var(--card);
  color: var(--fg-muted); text-decoration: none;
  font-variant-numeric: tabular-nums;
  transition: border-color .12s, background .12s;
}
.health-pill:hover { border-color: color-mix(in srgb, var(--accent) 28%, transparent); background: color-mix(in srgb, var(--accent) 6%, transparent); }
.health-pill .health-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--ok); flex-shrink: 0;
}
.health-pill.has-issues .health-dot { background: var(--warn); }
.health-pill.has-issues { border-color: color-mix(in srgb, var(--warn) 25%, transparent); color: var(--warn); }
/* Activity metric (auto-filed count), not a health verdict: neutral dot, no
   glow, so it never reads as a green "all-clear" next to the collector chip. */
.health-pill.metric:not(.has-issues) .health-dot { background: var(--fg-dim); animation: none; }
.health-pill.metric:not(.has-issues) { color: var(--fg-dim); }
"""

# Full page stylesheet, single-sourced: shared tokens + shared chrome (incl. the
# base resets) by reference, then this page's local rules. Same bytes the old
# inline literal produced; render_shell() composes the live <style> the same way
# (it appends RB_BUTTON_CSS after page_css), so this constant is the documented
# whole and the assembler is the live path.
CSS = RB_TOKENS_CSS + RB_CHROME_CSS + PAGE_CSS


PULSE_JS = r"""
(() => {
  // Calendar now-indicator. The page is a STATIC generated file that can sit open
  // for hours, so the red line has to move on its own or it silently lies about
  // the current time. Geometry constants come from the grid's data-* attributes
  // so the hour height is defined in exactly one place (pulse_web's CAL_HOUR_PX).
  const calGrid = document.querySelector('.cal-grid');
  const calNow = document.getElementById('cal-now');
  if (calGrid && calNow) {
    const start = Number(calGrid.dataset.calStart);
    const end = Number(calGrid.dataset.calEnd);
    const hourPx = Number(calGrid.dataset.calHourPx);
    const placeNow = () => {
      const d = new Date();
      const h = d.getHours() + d.getMinutes() / 60;
      // Outside the rendered window the indicator is meaningless — hide it
      // rather than pinning it to an edge and implying "now" is 8 AM.
      if (h < start || h > end) { calNow.style.display = 'none'; return; }
      calNow.style.display = '';
      calNow.style.top = ((h - start) * hourPx).toFixed(0) + 'px';
      // Re-age the blocks too, so an event that ends while the page is open fades.
      const mins = d.getHours() * 60 + d.getMinutes();
      document.querySelectorAll('.cal-event[data-cal-end-min]').forEach((el) => {
        const past = Number(el.dataset.calEndMin) <= mins;
        el.classList.toggle('past', past);
        el.classList.toggle('upcoming', !past);
      });
    };
    placeNow();
    setInterval(placeNow, 60000);
  }

  const FILTER_TARGETS = '.rb-data-row, [data-rb-row], .email-row, .strip > div, .kv-list li, .pr-row';
  const input = document.getElementById('pulse-filter');
  const btn = document.getElementById('pulse-refresh');
  const undoTray = document.getElementById('goal-undo-tray');
  const copyBtn = document.querySelector('.health-banner-copy-btn[data-copy-text]');

  const escapeHtml = (value) => {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  };

  const renderUndoTray = (entries) => {
    if (!undoTray) return;
    if (!Array.isArray(entries) || entries.length === 0) {
      undoTray.innerHTML = '';
      undoTray.hidden = true;
      undoTray.classList.add('is-empty');
      return;
    }
    const items = entries.slice(0, 3).map((entry, index) => {
      const title = escapeHtml(entry.title || 'completed task');
      const ago = escapeHtml(entry.completed_ago || 'just now');
      const entryId = escapeHtml(entry.id || '');
      const stripe = (index % 2 === 1) ? 'even' : 'odd';
      return `
        <li class="goal-undo-item" data-rb-row="1" data-rb-stripe="${stripe}">
          <span class="rb-data-row-marker"><span class="rb-data-marker-badge ok">✓</span></span>
          <div class="rb-data-row-body goal-undo-copy">
            <div class="rb-data-row-title goal-undo-title">${title}</div>
          </div>
          <div class="rb-data-row-trailing">
            <div class="rb-data-row-time timestamp-block">${ago}</div>
            <a class="rb-btn goal-undo-btn" href="#" data-goal-undo-id="${entryId}" role="button">Undo</a>
          </div>
        </li>
      `;
    });
    undoTray.innerHTML = `
      <div class="section-label goal-undo-label">Recently completed<span class="section-label-count"> · ${items.length}</span></div>
      <ul class="goal-undo-list rb-data-list">${items.join('')}</ul>
    `;
    undoTray.hidden = false;
    undoTray.classList.remove('is-empty');
    bindUndoButtons();
  };

  const copyTextToClipboard = async (text) => {
    if (!text) return false;
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    const probe = document.createElement('textarea');
    probe.value = text;
    probe.setAttribute('readonly', '');
    probe.style.position = 'absolute';
    probe.style.left = '-9999px';
    document.body.appendChild(probe);
    probe.select();
    probe.setSelectionRange(0, probe.value.length);
    try {
      return document.execCommand('copy');
    } finally {
      document.body.removeChild(probe);
    }
  };

  const setCopyButtonStatus = (label, copied = false) => {
    if (!copyBtn) return;
    copyBtn.setAttribute('aria-label', label);
    copyBtn.setAttribute('title', label);
    const sr = copyBtn.querySelector('.visually-hidden');
    if (sr) sr.textContent = label;
    copyBtn.classList.toggle('is-copied', copied);
  };

  if (input) {
    const rows = Array.from(document.querySelectorAll(FILTER_TARGETS));
    const haystacks = rows.map(r => (r.textContent || '').toLowerCase());
    const wrap = input.closest('.search-wrap');
    const chatResults = document.getElementById('chat-results');
    const modeBtns = Array.from(document.querySelectorAll('.search-mode-btn'));
    let mode = 'filter';

    const clearFilter = () => rows.forEach(r => r.classList.remove('is-hidden-by-filter'));
    const apply = () => {
      const q = input.value.trim().toLowerCase();
      for (let i = 0; i < rows.length; i++) {
        rows[i].classList.toggle('is-hidden-by-filter', q !== '' && !haystacks[i].includes(q));
      }
    };
    const hideChat = () => { if (chatResults) { chatResults.hidden = true; chatResults.innerHTML = ''; } };

    const renderChat = (data) => {
      if (!chatResults) return;
      if (data && data.error) {
        chatResults.innerHTML = `<div class="chat-status error">${escapeHtml(data.error)}</div>`;
        return;
      }
      const cites = (data && data.citations) || [];
      if (!cites.length) { chatResults.innerHTML = '<div class="chat-status">No matches.</div>'; return; }
      const items = cites.map((c) => {
        const score = (c.score != null) ? `<span class="chat-cite-score">${Math.round(c.score * 100)}%</span>` : '';
        const title = escapeHtml(c.title || c.path || '(untitled)');
        const preview = escapeHtml((c.preview || '').slice(0, 240));
        return `<li class="chat-cite">
            <div class="chat-cite-head">
              <span class="chat-cite-source">${escapeHtml(c.source || '')}</span>
              <span class="chat-cite-title" title="${escapeHtml(c.path || '')}">${title}</span>
              ${score}
            </div>
            <div class="chat-cite-preview">${preview}</div>
          </li>`;
      }).join('');
      const ms = (data.elapsed_ms != null) ? ` · ${data.elapsed_ms} ms` : '';
      chatResults.innerHTML = `<div class="chat-meta">${cites.length} result${cites.length !== 1 ? 's' : ''}${ms}</div><ul class="chat-cite-list">${items}</ul>`;
    };

    const runChat = async () => {
      const q = input.value.trim();
      if (!q || !chatResults) return;
      chatResults.hidden = false;
      chatResults.innerHTML = '<div class="chat-status">Searching… (first query loads the model)</div>';
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q, scope: 'all', top_k: 8 }),
        });
        renderChat(await res.json());
      } catch (err) {
        chatResults.innerHTML = `<div class="chat-status error">${escapeHtml(String(err))}</div>`;
      }
    };

    const setMode = (m) => {
      mode = (m === 'ask') ? 'ask' : 'filter';
      modeBtns.forEach(b => b.classList.toggle('is-active', b.dataset.mode === mode));
      if (wrap) wrap.classList.toggle('mode-ask', mode === 'ask');
      input.placeholder = (mode === 'ask') ? 'Ask your data…  (Enter)' : 'Filter visible rows…';
      if (mode === 'ask') { clearFilter(); } else { hideChat(); apply(); }
    };

    modeBtns.forEach(b => b.addEventListener('click', () => { setMode(b.dataset.mode); input.focus(); }));
    input.addEventListener('input', () => { if (mode === 'filter') apply(); });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && mode === 'ask') { e.preventDefault(); runChat(); }
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement !== input) { e.preventDefault(); input.focus(); }
      if (e.key === 'Escape' && document.activeElement === input) {
        if (mode === 'ask') { hideChat(); } else { input.value = ''; apply(); }
        input.blur();
      }
    });
    document.addEventListener('click', (e) => {
      if (mode === 'ask' && wrap && !wrap.contains(e.target)) hideChat();
    });
  }

  // Today's Goals — clickable check spans. POST /api/goals/complete, then
  // hide the row (mirrors the server-side "ignore completed" behavior so the
  // view matches what a full reload would render).
  const completeGoal = async (li) => {
    if (!li || li.classList.contains('is-busy')) return;
    const title = li.dataset.goalTitle || '';
    if (!title) return;
    li.classList.add('is-busy');
    const check = li.querySelector('.check');
    const doneEl = document.querySelector('.hero-stats div:nth-child(1) b');
    const ipEl = document.querySelector('.hero-stats div:nth-child(2) b');
    const barEl = document.querySelector('.hero-stats .bar span');
    try {
      const res = await fetch('/api/goals/complete', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error('complete failed: ' + res.status);
      const data = await res.json();
      if (check) check.classList.add('checked');
      // Brief tick, then collapse out.
      setTimeout(() => {
        li.classList.add('is-completing');
        setTimeout(() => { li.style.display = 'none'; }, 220);
      }, 140);
      if (ipEl) {
        const n = parseInt(ipEl.textContent || '0', 10);
        if (!Number.isNaN(n) && n > 0) ipEl.textContent = String(n - 1);
      }
      if (doneEl) {
        const n = parseInt(doneEl.textContent || '0', 10);
        if (!Number.isNaN(n)) doneEl.textContent = String(n + 1);
      }
      if (barEl && doneEl && ipEl) {
        const doneCount = parseInt(doneEl.textContent || '0', 10);
        const progressCount = parseInt(ipEl.textContent || '0', 10);
        const total = doneCount + progressCount;
        const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0;
        barEl.style.width = `${pct}%`;
      }
      renderUndoTray(data.history || []);
    } catch (err) {
      console.warn('goal complete failed:', err);
      li.classList.remove('is-busy');
      alert('Could not mark goal complete — check the server log.');
    }
  };

  const undoGoal = async (button) => {
    const undoId = button?.dataset?.goalUndoId || '';
    if (!undoId) return;
    button.setAttribute('aria-disabled', 'true');
    try {
      const res = await fetch('/api/goals/undo', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ id: undoId }),
      });
      if (!res.ok) throw new Error('undo failed: ' + res.status);
      location.reload();
    } catch (err) {
      console.warn('goal undo failed:', err);
      button.removeAttribute('aria-disabled');
      alert('Could not undo completion — check the server log.');
    }
  };

  function bindUndoButtons() {
    document.querySelectorAll('.goal-undo-btn[data-goal-undo-id]').forEach((button) => {
      if (button.dataset.undoBound === '1') return;
      button.dataset.undoBound = '1';
      button.addEventListener('click', (event) => {
        event.preventDefault();
        if (button.getAttribute('aria-disabled') === 'true') return;
        undoGoal(button);
      });
    });
  }

  document.querySelectorAll('.goal[data-goal-title] .check').forEach((el) => {
    el.addEventListener('click', () => completeGoal(el.closest('.goal')));
    el.addEventListener('keydown', (e) => {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        completeGoal(el.closest('.goal'));
      }
    });
  });

  // Apple Reminders — clickable check spans. POST /api/apple-reminders/complete
  // (Phase 6 dashboard write-back), then optimistically collapse the row. The
  // local table reconciles on the next scoped sync, so we only update the UI.
  const completeReminder = async (li) => {
    if (!li || li.classList.contains('is-busy')) return;
    const reminderId = li.dataset.reminderId || '';
    const title = li.dataset.reminderTitle || '';
    if (!reminderId) return;
    li.classList.add('is-busy');
    const check = li.querySelector('.check');
    // Optimistic: check + collapse the row IMMEDIATELY, then fire the write in
    // the background. The EventKit op is ~1s; the lag is the audit-row INSERT
    // waiting on the rebalance.db write lock during a concurrent sync (up to
    // busy_timeout=30s). Awaiting that would freeze the row, so we don't —
    // a real failure rolls the row back instead.
    if (check) check.classList.add('checked');
    setTimeout(() => {
      li.classList.add('is-completing');
      setTimeout(() => { li.style.display = 'none'; }, 220);
    }, 140);
    try {
      const res = await fetch('/api/apple-reminders/complete', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ reminder_id: reminderId, title }),
      });
      if (!res.ok) throw new Error('complete failed: ' + res.status);
    } catch (err) {
      console.warn('reminder complete failed:', err);
      li.style.display = '';
      li.classList.remove('is-busy', 'is-completing');
      if (check) check.classList.remove('checked');
      alert('Could not complete reminder — check the server log.');
    }
  };

  document.querySelectorAll('.goal-reminder[data-reminder-id] .check').forEach((el) => {
    el.addEventListener('click', () => completeReminder(el.closest('.goal-reminder')));
    el.addEventListener('keydown', (e) => {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        completeReminder(el.closest('.goal-reminder'));
      }
    });
  });
  bindUndoButtons();

  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      try {
        const ok = await copyTextToClipboard(copyBtn.dataset.copyText || '');
        if (!ok) throw new Error('clipboard copy returned false');
        setCopyButtonStatus('Copied collector warning text', true);
        window.setTimeout(() => {
          setCopyButtonStatus('Copy collector warning text');
        }, 1500);
      } catch (err) {
        console.warn('copy banner text failed:', err);
        setCopyButtonStatus('Copy failed', false);
        window.setTimeout(() => {
          setCopyButtonStatus('Copy collector warning text');
        }, 1800);
      }
    });
  }

  if (btn) {
    btn.addEventListener('click', async () => {
      const original = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Refreshing…';
      try {
        const res = await fetch('/api/refresh', { method: 'POST' });
        if (!res.ok) throw new Error('refresh failed: ' + res.status);
        const data = await res.json().catch(() => null);
        if (data && data.helper_error) {
          // Helper failed — last-good active.json preserved; surface the error.
          btn.textContent = '⚠ Reminders stale';
          btn.title = 'Helper error: ' + data.helper_error;
          await new Promise(r => setTimeout(r, 2500));
        }
        location.reload();
      } catch (err) {
        // Static-file mode (no server) or refresh failed — fall back to a plain reload.
        console.warn('pulse refresh fallback:', err);
        location.reload();
      } finally {
        btn.disabled = false;
        btn.textContent = original;
      }
    });
  }

  const figmaForm = document.getElementById('figma-project-form');
  const figmaInput = document.getElementById('figma-project-input');
  const figmaSubmit = document.getElementById('figma-project-submit');
  const figmaStatus = document.getElementById('figma-project-status');

  const setFigmaStatus = (message, state = '') => {
    if (!figmaStatus) return;
    figmaStatus.textContent = message;
    figmaStatus.classList.remove('is-error', 'is-success');
    if (state) figmaStatus.classList.add(state);
  };

  if (figmaForm && figmaInput && figmaSubmit) {
    figmaForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const project = figmaInput.value.trim();
      if (!project) {
        setFigmaStatus('Enter a Figma project ID or paste a Figma URL.', 'is-error');
        figmaInput.focus();
        return;
      }

      const original = figmaSubmit.textContent;
      figmaSubmit.disabled = true;
      figmaSubmit.textContent = 'Adding…';
      setFigmaStatus('Saving project ID and syncing Figma comments…');

      try {
        const res = await fetch('/api/figma/projects', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ project }),
        });
        const data = await res.json();
        if (!res.ok) {
          const detail = data?.detail || data?.error || ('request failed: ' + res.status);
          throw new Error(String(detail));
        }

        if (data.sync_ok === false) {
          const reason = data.sync_error ? ` Sync issue: ${data.sync_error}` : '';
          setFigmaStatus(`Stored ${data.file_key}.${reason} Reloading…`, 'is-error');
        } else {
          const prefix = data.already_present ? 'Re-synced' : 'Added';
          const comments = Number(data.comments_fetched || 0);
          setFigmaStatus(`${prefix} ${data.file_key} · ${comments} comment${comments === 1 ? '' : 's'} fetched. Reloading…`, 'is-success');
        }
        figmaInput.value = '';
        window.setTimeout(() => location.reload(), 700);
      } catch (err) {
        console.warn('figma add project failed:', err);
        setFigmaStatus(`Could not add Figma project: ${String(err)}`, 'is-error');
      } finally {
        figmaSubmit.disabled = false;
        figmaSubmit.textContent = original;
      }
    });
  }

  // Repo activity doughnut (Chart.js, loaded via CDN with defer).
  const initRepoPie = () => {
    const canvas = document.getElementById('repo-pie-canvas');
    const dataEl = document.getElementById('repo-pie-data');
    if (!canvas || !dataEl || typeof Chart === 'undefined') return false;
    let payload;
    try { payload = JSON.parse(dataEl.textContent || '{}'); }
    catch (e) { console.warn('repo-pie payload parse failed', e); return true; }
    const { labels = [], values = [], colors = [] } = payload;
    if (!labels.length) return true;
    const total = values.reduce((a, b) => a + b, 0) || 1;
    const rootStyle = getComputedStyle(document.documentElement);
    const chartBorder = rootStyle.getPropertyValue('--card').trim() || '#ffffff';
    const chartText = rootStyle.getPropertyValue('--ink').trim() || '#1d2024';
    new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: chartBorder,
          borderWidth: 1,
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '58%',
        plugins: {
          legend: {
            position: 'right',
            labels: { color: chartText, boxWidth: 10, boxHeight: 10, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const v = ctx.parsed || 0;
                const pct = ((v / total) * 100).toFixed(1);
                return `${ctx.label}: ${v} (${pct}%)`;
              },
            },
          },
        },
      },
    });
    return true;
  };
  if (!initRepoPie()) {
    window.addEventListener('load', initRepoPie, { once: true });
  }

  // Org activity doughnut — same pattern, different canvas/data IDs.
  const initOrgPie = () => {
    const canvas = document.getElementById('org-activity-canvas');
    const dataEl = document.getElementById('org-activity-data');
    if (!canvas || !dataEl || typeof Chart === 'undefined') return false;
    let payload;
    try { payload = JSON.parse(dataEl.textContent || '{}'); }
    catch (e) { console.warn('org-activity payload parse failed', e); return true; }
    const { labels = [], values = [], colors = [] } = payload;
    if (!labels.length) return true;
    const total = values.reduce((a, b) => a + b, 0) || 1;
    const rootStyle = getComputedStyle(document.documentElement);
    const chartBorder = rootStyle.getPropertyValue('--card').trim() || '#ffffff';
    const chartText = rootStyle.getPropertyValue('--ink').trim() || '#1d2024';
    new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: chartBorder,
          borderWidth: 1,
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '58%',
        plugins: {
          legend: {
            position: 'right',
            labels: { color: chartText, boxWidth: 10, boxHeight: 10, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const v = ctx.parsed || 0;
                const pct = ((v / total) * 100).toFixed(1);
                return `${ctx.label}: ${v} (${pct}%)`;
              },
            },
          },
        },
      },
    });
    return true;
  };
  if (!initOrgPie()) {
    window.addEventListener('load', initOrgPie, { once: true });
  }

  // PR filter toggles (stale + failing CI — independent, composable)
  const prCard = document.getElementById('open-prs-card');
  if (prCard) {
    const staleBtn = prCard.querySelector('[data-pr-filter-stale]');
    if (staleBtn) {
      staleBtn.addEventListener('click', () => {
        const active = prCard.classList.toggle('filter-stale');
        staleBtn.classList.toggle('active', active);
        staleBtn.textContent = active
          ? staleBtn.textContent.replace('stale', 'stale ✕')
          : staleBtn.textContent.replace(' ✕', '');
      });
    }
    const ciBtn = prCard.querySelector('[data-pr-filter-ci]');
    if (ciBtn) {
      ciBtn.addEventListener('click', () => {
        const active = prCard.classList.toggle('filter-ci');
        ciBtn.classList.toggle('active', active);
        ciBtn.textContent = active
          ? ciBtn.textContent.replace('failing CI', 'failing CI ✕')
          : ciBtn.textContent.replace(' ✕', '');
      });
    }
  }
})();
"""


def _resolve_tz_source() -> tuple[str, bool]:
    """Mirror local_tz()'s resolution order. Returns (label, is_fallback)."""
    if os.environ.get("REBALANCE_TZ"):
        return (f"REBALANCE_TZ={os.environ['REBALANCE_TZ']}", False)
    try:
        lt = os.readlink("/etc/localtime")
        if "zoneinfo/" in lt:
            return ("/etc/localtime", False)
    except OSError:
        pass
    return ("UTC fallback", True)


def build_page(*, goals_path: Path, vault_path: Path | None, refresh_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(TZ)

    all_goals = parse_goals(goals_path, limit=PRIMARY_GOAL_LIMIT + SECONDARY_TODO_LIMIT)
    goals = all_goals[:PRIMARY_GOAL_LIMIT]
    secondary_todos = all_goals[PRIMARY_GOAL_LIMIT:]
    # Read-only Apple Reminders column.
    # Design choice (QA-R F3): DB-less rendering. The column reads only from
    # ACTIVE_JSON_PATH written by /api/refresh (via the signed EventKit helper).
    # On cold-start (file absent), the column renders empty with a prompt to
    # click Refresh — this is intentional and tested. We do NOT fall back to
    # the DB because the DB apple_reminders table is written by a separate
    # FDA-gated sync path, while this column is specifically the FDA-free path.
    apple_reminders = []
    if ACTIVE_JSON_PATH.exists():
        try:
            with open(ACTIVE_JSON_PATH, encoding="utf-8") as fh:
                payload = json.load(fh)
                # Support both old bare-list format and new versioned envelope
                # {"schema_version": 1, "items": [...]} written by pulse_server.py.
                items = payload.get("items", payload) if isinstance(payload, dict) else payload
                items.sort(key=lambda x: x.get("due_at") or "9999-12-31T23:59:59Z")
                apple_reminders = items[:APPLE_REMINDER_LIMIT]
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    recent_completions = load_goal_history(goals_path=goals_path)
    for item in recent_completions:
        completed_at = item.get("completed_at")
        item["completed_ago"] = format_timestamp(completed_at, relative=True, tz=TZ) or "just now"
    pulled_from = goals_path.name if goals_path.exists() else f"missing: {goals_path}"
    obsidian_url = build_obsidian_url(vault_path, goals_path) if goals_path.exists() else None

    watched = fetch_watched_summary(now)
    open_pr_rows = fetch_open_prs(limit=10, stale_days=2)
    gh_rows = fetch_recent_github(limit=10)
    org_activity_days = 14
    org_activity_rows = fetch_org_activity(days=org_activity_days)
    vault_rows = fetch_vault_recent(limit=6)
    cal_today_rows = fetch_calendar_today(now, TZ)
    cal_rows = fetch_calendar_upcoming(now, limit=6)
    sleuth_sections, sleuth_total = fetch_sleuth_display_sections()
    # Fallback to the DB-backed flat list when the published file is unavailable.
    sleuth_rows = fetch_sleuth_due(limit=6) if not sleuth_sections else []
    email_rows = fetch_recent_emails(limit=30)
    figma_rows = fetch_recent_figma(limit=12)
    repo_pie_days = 7
    repo_pie_rows = fetch_repo_activity_counts(days=repo_pie_days, limit=12)
    repo_pie_recent_promotion = fetch_recent_auto_promotion(days=repo_pie_days)
    status = get_index_status(DB_PATH)

    # "What should we work on next" — READ the precomputed ranking only. This
    # path runs in the NO-NETWORK launchd context, so never call rank_next_actions
    # / Gemini here; the live synthesis happens on the refresh path (stage D). A
    # missing table on a fresh DB must never break page generation.
    work_next_rows: list[dict[str, Any]] = []
    work_next_computed_at: str | None = None
    work_next_blended = False
    work_next_model: str | None = None
    try:
        ranked = next_actions.load_ranked_next_actions(DB_PATH)
        if ranked is not None:
            work_next_rows = [a.as_dict() for a in ranked.ranked]
            work_next_computed_at = ranked.computed_at or None
            work_next_blended = ranked.blended
            work_next_model = ranked.model_used or None
    except Exception:  # noqa: BLE001 — never let a missing cache break the page
        work_next_rows = []

    doctor_report = run_doctor(DB_PATH)
    figma_keys = get_figma_file_keys()
    # Sleuth has synced at least once iff sources.sleuth.last_synced_at is set.
    # Lets the sidebar tell a genuinely empty inbox apart from a sync that has
    # never run (e.g. missing Sleuth credentials) — no false "Inbox clear".
    sleuth_synced = bool(
        ((status.get("sources") or {}).get("sleuth") or {}).get("last_synced_at")
    )

    in_progress = sum(1 for g in goals if not g["done"])
    _sleuth_count = sleuth_total if sleuth_sections else len(sleuth_rows)
    streams = build_stream_rows(
        status,
        live_counts={
            "github": len(gh_rows),
            "vault": len(vault_rows),
            "calendar": len(cal_rows),
            "sleuth": _sleuth_count,
            "email": len(email_rows),
        },
    )
    semantic_total = ((status.get("semantic_index") or {}).get("total_documents")) or 0
    email_total = int(((status.get("sources") or {}).get("email") or {}).get("messages") or 0)
    figma_source = (status.get("sources") or {}).get("figma") or {}
    figma_total = int(figma_source.get("comments") or 0)
    freshness = status.get("freshness") or {}
    drift_total = sum(int(v) for v in freshness.values() if isinstance(v, int))

    last_activity = _latest_collector_activity(status)
    last_vault = vault_rows[0] if vault_rows else None
    health_filed_30d = fetch_health_filed_count(days=1)
    # One reconciled verdict drives every health pill, so they can't contradict.
    health_status = compute_health_status(doctor_report.checks, status, now)

    tz_source_label, tz_is_fallback = _resolve_tz_source()
    offset = local_now.strftime("%z")
    offset_pretty = f"{offset[:3]}:{offset[3:]}" if offset else ""
    system_now_str = local_now.strftime("%a %b %-d · %H:%M:%S")
    system_now_tz = f"{local_now.tzname() or ''} {offset_pretty}".strip()
    system_now_title = (
        f"System clock (resolved via: {tz_source_label})\n"
        f"UTC now: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"Resolution order: REBALANCE_TZ env → /etc/localtime → UTC fallback"
    )
    system_now_class = "system-now tz-fallback" if tz_is_fallback else "system-now"

    nav_data = build_nav_data(
        in_progress=in_progress,
        cal_rows=cal_rows,
        cal_today_rows=cal_today_rows,
        sleuth_rows=sleuth_rows,
        sleuth_synced=sleuth_synced,
        sleuth_sections=sleuth_sections or None,
        streams=streams,
        drift_total=drift_total,
        semantic_total=semantic_total,
        notices=health_status.notices,
        tz=TZ,
        now=now,
    )
    main_inner = f"""
        <div class="topbar">
          <div class="crumb">Pulse <span style="color:var(--fg-dim); margin:0 4px">›</span> Today</div>
          <div class="topbar-right">
            <div class="topbar-row">
              <div class="search-wrap">
                <div class="search-mode" role="group" aria-label="Search mode">
                  <button type="button" class="search-mode-btn is-active" data-mode="filter">Filter</button>
                  <button type="button" class="search-mode-btn" data-mode="ask">Ask</button>
                </div>
                <input id="pulse-filter" class="pulse-filter" type="search" placeholder="Filter visible rows…" autocomplete="off" spellcheck="false">
                <div id="chat-results" class="chat-results" hidden></div>
              </div>
              <span class="{system_now_class}" title="{_esc(system_now_title)}">System: {_esc(system_now_str)} <span class="tz-key">{_esc(system_now_tz)} · {_esc(TZ.key)}</span></span>
            </div>
            <div class="topbar-row">
              {render_sync_chip(health_status, last_activity, now)}
              <a href="{_esc(HEALTH_ISSUES_URL)}" target="_blank" rel="noopener noreferrer"
                 class="health-pill metric{' has-issues' if health_filed_30d else ''}"
                 title="GitHub issues the health reporter auto-filed in the last day — click to view on GitHub">
                <span class="health-dot"></span>
                Auto-filed: {health_filed_30d} issue{'s' if health_filed_30d != 1 else ''} (1d)
              </a>
              <button id="pulse-refresh" class="refresh-btn">Refresh</button>
            </div>
          </div>
        </div>
        {render_health_banner(health_status, now, last_activity)}
        {render_hero(goals, pulled_from, local_now, obsidian_url, recent_completions, secondary_todos=secondary_todos, apple_reminders=apple_reminders)}
        <div class="full-row">
          {render_work_next(work_next_rows, now, computed_at=work_next_computed_at, blended=work_next_blended, model_used=work_next_model)}
        </div>
        <div class="grid">
          <div class="col">
            {render_recent_activity(gh_rows, now, last_vault=last_vault, vault_recent_count=len(vault_rows))}
          </div>
          <div class="col">
            {render_watched(watched, now)}
            {render_recent_figma(
                figma_rows,
                now,
                tz=TZ,
                limit=12,
                stored_total=figma_total,
                configured_keys=figma_keys,
                last_synced_at=figma_source.get("last_synced_at"),
            )}
            {render_repo_pie(repo_pie_rows, days=repo_pie_days, recent_promotion=repo_pie_recent_promotion)}
          </div>
        </div>
        <div class="full-row">
          {render_org_activity(org_activity_rows, days=org_activity_days)}
        </div>
        <div class="full-row">
          {render_open_prs(open_pr_rows, now)}
        </div>
        <div class="full-row">
          {render_recent_emails(email_rows, now, tz=TZ, limit=30, stored_total=email_total)}
        </div>
        <div class="full-row">
          {render_index_health(status, now)}
        </div>
      """
    head_extra = (
        '\n  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js" defer></script>'
    )
    body_extra = f"\n<!-- generated {now.isoformat()} -->\n<script>{PULSE_JS}</script>\n"
    return render_shell(
        "rebalance pulse · Today",
        main_inner,
        active="today",
        wide=True,
        nav_data=nav_data,
        page_css=PAGE_CSS,
        head_extra=head_extra,
        body_extra=body_extra,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def write_page(
    out: Path,
    *,
    goals_path: Path,
    vault_path: Path | None,
    refresh_seconds: int,
) -> Path:
    html_text = build_page(
        goals_path=goals_path,
        vault_path=vault_path,
        refresh_seconds=refresh_seconds,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(html_text, encoding="utf-8")
    tmp.replace(out)  # atomic on POSIX
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Render web/pulse.html from the same data the TUI dashboard reads.")
    parser.add_argument("--goals", type=Path, help="Path to Goals markdown file")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output HTML path")
    parser.add_argument("--watch", action="store_true", help="Regenerate continuously")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between regenerations in --watch mode")
    args = parser.parse_args()

    vault_path = load_vault_path()
    goals_path = resolve_goals_path(args.goals)
    if goals_path is None:
        print("error: no --goals path and vault_path not set in temp/rbos.config", file=sys.stderr)
        return 2

    if not args.watch:
        out = write_page(args.out, goals_path=goals_path, vault_path=vault_path, refresh_seconds=args.interval)
        print(f"wrote {out}")
        return 0

    print(f"watching · regenerating {args.out} every {args.interval}s · ctrl+c to stop")
    try:
        while True:
            try:
                write_page(args.out, goals_path=goals_path, vault_path=vault_path, refresh_seconds=args.interval)
            except Exception as exc:  # don't kill the watcher on a transient DB read
                print(f"[{datetime.now().strftime('%H:%M:%S')}] regen failed: {exc}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
