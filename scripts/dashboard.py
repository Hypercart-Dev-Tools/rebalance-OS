"""
rebalance pulse — terminal dashboard.

A Rich-styled live monitor of local + remote activity, backed by the
SQLite knowledge base. The DB is polled every 2 seconds (cheap); a
background thread runs a lightweight `refresh_index(scope=['github'])`
every 10 minutes so the data underneath actually changes without loading
the local embedding model into the terminal process.

    Run:   uv run python scripts/dashboard.py
    Quit:  q (or Ctrl+C)
    Force refresh now:  r

Optional environment:
    REBALANCE_DB     path to the SQLite db (default: ./rebalance.db)
    REBALANCE_TZ     IANA timezone for "now" rendering (default: America/Los_Angeles)
    PULSE_TICK       UI poll interval in seconds (default: 2)
    PULSE_AUTO_MIN   GitHub auto-refresh interval in minutes (default: 10; 0 = off)
    PULSE_INVERSE    1 = high-contrast light palette (default: refined dark)
"""

from __future__ import annotations

import os
import json
import select
import sys
import termios
import threading
import tty
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from rich.align import Align
from rich.box import ROUNDED
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Make `rebalance.*` importable when running the script straight from the repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rebalance.ingest.config import (  # noqa: E402
    get_calendar_ignored_summaries,
    get_github_ignored_repos,
    get_pulse_config,
)
from rebalance.ingest.db import db_connection  # noqa: E402
from rebalance.ingest.index_ops import (  # noqa: E402
    get_index_status,
    get_watched_repos,
    refresh_index,
)
from rebalance.ingest.slack_users import compact_sleuth_reminder  # noqa: E402


DB_PATH = Path(os.environ.get("REBALANCE_DB", "rebalance.db")).expanduser().resolve()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "temp" / "logs"
TZ = ZoneInfo(os.environ.get("REBALANCE_TZ", "America/Los_Angeles"))
TICK_SECONDS = float(os.environ.get("PULSE_TICK", "2"))
AUTO_REFRESH_MINUTES = int(os.environ.get("PULSE_AUTO_MIN", "10"))
INVERSE = os.environ.get("PULSE_INVERSE", "0") not in ("", "0", "false", "False")


# ---------------------------------------------------------------------------
# Palettes. The default keeps the "refined dark" mood: one signature accent
# (amber), semantic colours for content, and restrained chrome. Inverse mode is
# now an explicit light palette instead of ANSI ``reverse``; Rich's reverse
# semantics interact poorly with true-colour foregrounds and can produce
# off-white text on a white terminal.
# ---------------------------------------------------------------------------
DARK_PALETTE = {
    "bg": "#0e1013",
    "border": "#3a414b",
    "border_hi": "#515966",
    "fg": "#f2eee8",
    "fg_muted": "#bdb5ac",
    "fg_dim": "#928a81",
    "trough": "#23262b",
    "accent": "#e8b86a",  # amber — single signature colour
    "ok": "#88bd71",      # green — commits / fresh
    "info": "#75afea",    # blue — PRs / calendar
    "warn": "#e8b86a",    # amber — issues (alias of accent)
    "danger": "#e07171",  # red — never-synced / errors
}

LIGHT_PALETTE = {
    "bg": "#fbf8f1",
    "border": "#7f7468",
    "border_hi": "#5f574d",
    "fg": "#242629",
    "fg_muted": "#57534d",
    "fg_dim": "#746f67",
    "trough": "#e7dfd3",
    "accent": "#a65f00",
    "ok": "#2f7437",
    "info": "#1d6fa8",
    "warn": "#a65f00",
    "danger": "#b33a2e",
}

PALETTE = LIGHT_PALETTE if INVERSE else DARK_PALETTE


def _style(fg: str | None = None, *, bold: bool = False, italic: bool = False) -> str:
    tokens = []
    if bold:
        tokens.append("bold")
    if italic:
        tokens.append("italic")
    if fg:
        tokens.append(fg)
    tokens.append(f"on {PALETTE['bg']}")
    return " ".join(tokens)


def _panel_style(_unused: str = "") -> dict[str, Any]:
    """Style kwargs for a Panel.

    Every panel uses the same low-contrast border colour so the dashboard
    reads as a single composition; semantic colour goes on the content,
    not the chrome.
    """
    return {
        "border_style": _style(PALETTE["border"]),
        "style": _style(PALETTE["fg"]),
    }


def _title(label: str) -> Text:
    """Panel titles: amber bullet + accented label, matching the design mock."""
    title = Text("●", style=_style(PALETTE["accent"], bold=True))
    title.append(f" {label}", style=_style(PALETTE["fg"], bold=True))
    return title


# ---------------------------------------------------------------------------
# Refresh state shared between the UI loop and the background worker
# ---------------------------------------------------------------------------


class RefreshState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.status = "idle"          # idle | running | ok | error
        self.last_finished: datetime | None = None
        self.last_started: datetime | None = None
        self.last_error: str = ""
        self.last_profile: dict[str, Any] | None = None

    def start(self) -> None:
        with self.lock:
            self.status = "running"
            self.last_started = datetime.now(timezone.utc)

    def succeed(self, profile: dict[str, Any] | None = None) -> None:
        with self.lock:
            self.status = "ok"
            self.last_finished = datetime.now(timezone.utc)
            self.last_error = ""
            self.last_profile = profile

    def fail(self, err: str) -> None:
        with self.lock:
            self.status = "error"
            self.last_finished = datetime.now(timezone.utc)
            self.last_error = err

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "status": self.status,
                "last_started": self.last_started,
                "last_finished": self.last_finished,
                "last_error": self.last_error,
                "last_profile": self.last_profile,
            }


REFRESH = RefreshState()
_stop_event = threading.Event()


def _github_scope_result(result: dict[str, Any]) -> dict[str, Any] | None:
    for entry in result.get("results") or []:
        if isinstance(entry, dict) and entry.get("scope") == "github":
            return entry
    return None


def _summarize_refresh_profile(result: dict[str, Any]) -> dict[str, Any]:
    github = _github_scope_result(result) or {}
    rows = [r for r in github.get("artifact_sync") or [] if isinstance(r, dict)]
    timed_rows = [
        r for r in rows
        if isinstance(r.get("elapsed_seconds"), (int, float))
    ]
    timed_rows.sort(key=lambda r: float(r["elapsed_seconds"]), reverse=True)
    slowest = timed_rows[0] if timed_rows else None
    return {
        "elapsed_seconds": result.get("elapsed_seconds"),
        "repo_count": len(rows),
        "slowest_repo": slowest.get("repo") if slowest else None,
        "slowest_seconds": slowest.get("elapsed_seconds") if slowest else None,
        "log_name": f"github_refresh_{datetime.now(TZ).date().isoformat()}.log",
    }


def _write_refresh_profile(result: dict[str, Any]) -> None:
    """Append dashboard-triggered GitHub refresh timings for profile-sync."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"github_refresh_{datetime.now(TZ).date().isoformat()}.log"
    record = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "source": "dashboard",
        "result": result,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")


def _do_refresh() -> None:
    REFRESH.start()
    try:
        result = refresh_index(DB_PATH, scope=["github"], include_semantic=False)
        _write_refresh_profile(result)
        REFRESH.succeed(_summarize_refresh_profile(result))
    except Exception as exc:  # noqa: BLE001
        REFRESH.fail(f"{type(exc).__name__}: {exc}")


def _auto_refresh_loop() -> None:
    """Run refresh_index(scope=['github']) every AUTO_REFRESH_MINUTES."""
    if AUTO_REFRESH_MINUTES <= 0:
        return
    interval = AUTO_REFRESH_MINUTES * 60
    # Wait the interval before the first tick — startup snapshot is enough.
    while not _stop_event.wait(interval):
        if REFRESH.snapshot()["status"] == "running":
            continue
        _do_refresh()


def _trigger_manual_refresh() -> None:
    if REFRESH.snapshot()["status"] == "running":
        return
    threading.Thread(target=_do_refresh, daemon=True).start()


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ago(value: str | datetime | None, now: datetime | None = None) -> str:
    if value is None:
        return "—"
    dt = _parse_iso(value) if isinstance(value, str) else value
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    n = now or datetime.now(timezone.utc)
    delta = n - dt
    secs = int(delta.total_seconds())
    if secs < 0:
        secs = -secs
        future = True
    else:
        future = False
    if secs < 60:
        s = f"{secs}s"
    elif secs < 3600:
        s = f"{secs // 60}m"
    elif secs < 86400:
        s = f"{secs // 3600}h"
    else:
        s = f"{secs // 86400}d"
    return f"in {s}" if future else f"{s} ago"


# ---------------------------------------------------------------------------
# Data fetchers — every read goes through here, so the UI loop stays clean
# ---------------------------------------------------------------------------


def fetch_watched_summary(now: datetime) -> dict[str, Any]:
    watched_info = get_watched_repos(DB_PATH)
    watched = watched_info["watched"]
    ignored = watched_info["ignored"]

    fresh = stale = never = 0
    last_synced_overall: datetime | None = None
    if watched:
        with db_connection(DB_PATH) as conn:
            placeholders = ",".join("?" * len(watched))
            rows = conn.execute(
                f"""
                SELECT repo_full_name, MAX(fetched_at) AS last_synced
                FROM (
                    SELECT repo_full_name, fetched_at FROM github_items
                    UNION ALL
                    SELECT repo_full_name, fetched_at FROM github_commits
                    UNION ALL
                    SELECT repo_full_name, fetched_at FROM github_repo_meta
                )
                WHERE LOWER(repo_full_name) IN ({placeholders})
                GROUP BY LOWER(repo_full_name)
                """,
                tuple(r.lower() for r in watched),
            ).fetchall()
        seen = {r["repo_full_name"].lower(): r["last_synced"] for r in rows}
        for repo in watched:
            ts = seen.get(repo.lower())
            dt = _parse_iso(ts)
            if dt is None:
                never += 1
                continue
            if last_synced_overall is None or dt > last_synced_overall:
                last_synced_overall = dt
            hours = (now - dt).total_seconds() / 3600.0
            if hours <= 24:
                fresh += 1
            else:
                stale += 1

    return {
        "total": len(watched),
        "fresh": fresh,
        "stale": stale,
        "never": never,
        "ignored": len(ignored),
        "auto_discovered": len(watched_info["auto_discovered"]),
        "last_synced": last_synced_overall,
    }


def fetch_recent_github(limit: int = 9) -> list[dict[str, Any]]:
    """Union of recent items, commits, and comments — sorted by recency."""
    ignored = get_github_ignored_repos()
    ignored_clause = ""
    params: list[Any] = []
    if ignored:
        placeholders = ",".join("?" * len(ignored))
        ignored_clause = f"WHERE LOWER(repo_full_name) NOT IN ({placeholders})"
        params.extend(ignored)

    with db_connection(DB_PATH) as conn:
        rows = conn.execute(
            f"""
            SELECT kind, sub, repo_full_name, num, detail, ts, who, html_url FROM (
                SELECT 'item' AS kind, item_type AS sub, repo_full_name,
                       number AS num, title AS detail, updated_at AS ts,
                       author_login AS who, html_url
                FROM github_items
                WHERE updated_at IS NOT NULL
                UNION ALL
                SELECT 'commit', '', repo_full_name, item_number, message,
                       committed_at, author_login, html_url
                FROM github_commits
                WHERE committed_at IS NOT NULL
                UNION ALL
                SELECT 'comment', comment_type, repo_full_name, item_number,
                       body, created_at, author_login, html_url
                FROM github_comments
                WHERE created_at IS NOT NULL
            )
            {ignored_clause}
            ORDER BY ts DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_vault_recent(limit: int = 6) -> list[dict[str, Any]]:
    with db_connection(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT title, rel_path, last_modified
            FROM vault_files
            WHERE last_modified IS NOT NULL
            ORDER BY last_modified DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_calendar_upcoming(now: datetime, limit: int = 4) -> list[dict[str, Any]]:
    ignored = [pat.lower() for pat in get_calendar_ignored_summaries()]
    overfetch = max(limit * 3, limit + len(ignored)) if ignored else limit
    with db_connection(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT summary, start_time, end_time, location
            FROM calendar_events
            WHERE start_time >= ?
            ORDER BY start_time ASC
            LIMIT ?
            """,
            (now.isoformat(), overfetch),
        ).fetchall()
    out = [dict(r) for r in rows]
    if ignored:
        out = [
            r for r in out
            if not any(pat in (r.get("summary") or "").lower() for pat in ignored)
        ]
    return out[:limit]


def fetch_sleuth_due(limit: int = 4) -> list[dict[str, Any]]:
    slack_user_id = get_pulse_config().get("slack_user_id")
    with db_connection(DB_PATH) as conn:
        if slack_user_id:
            rows = conn.execute(
                """
                SELECT reminder_id, reminder_message_text, should_post_on, state,
                       assignee_id, original_sender_id
                FROM sleuth_reminders
                WHERE is_active = 1
                  AND (assignee_id = ? OR original_sender_id = ?)
                ORDER BY should_post_on ASC NULLS LAST
                LIMIT ?
                """,
                (slack_user_id, slack_user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT reminder_id, reminder_message_text, should_post_on, state,
                       assignee_id, original_sender_id
                FROM sleuth_reminders
                WHERE is_active = 1
                ORDER BY should_post_on ASC NULLS LAST
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        row = dict(r)
        row["sleuth_role"] = (
            "assigned_by_me"
            if slack_user_id
            and row.get("assignee_id") != slack_user_id
            and row.get("original_sender_id") == slack_user_id
            else "assigned_to_me"
        )
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


KIND_GLYPH = {
    "commit": ("●", PALETTE["ok"]),
    "item": ("◆", PALETTE["info"]),
    "comment": ("○", PALETTE["fg_muted"]),
}

ITEM_SUB_GLYPH = {
    "issue": ("✦", PALETTE["warn"]),
    "pull_request": ("⇡", PALETTE["info"]),
}


def _truncate(text: str, n: int) -> str:
    text = (text or "").splitlines()[0] if text else ""
    if len(text) <= n:
        return text
    return text[: n - 1] + "…"


def render_header(now: datetime) -> Panel:
    title = Text("rebalance ", style=f"bold {PALETTE['fg']}")
    title.append("pulse", style=f"bold {PALETTE['accent']}")
    right = Text(
        now.astimezone(TZ).strftime("%a %b %d · %H:%M:%S %Z"),
        style=PALETTE["fg_muted"],
    )

    table = Table.grid(expand=True)
    table.add_column(justify="left", ratio=1)
    table.add_column(justify="right", ratio=1)
    table.add_row(title, right)
    return Panel(table, box=ROUNDED, padding=(0, 1), **_panel_style())


def render_watched(summary: dict[str, Any]) -> Panel:
    body = Table.grid(padding=(0, 1))
    body.add_column(justify="left")
    body.add_column(justify="right")

    stale_color = PALETTE["fg_dim"] if summary["stale"] == 0 else PALETTE["warn"]
    never_color = PALETTE["fg_dim"] if summary["never"] == 0 else PALETTE["danger"]

    body.add_row(
        Text("watched", style=f"bold {PALETTE['fg']}"),
        Text(str(summary["total"]), style=f"bold {PALETTE['fg']}"),
    )
    body.add_row(
        Text("  fresh", style=PALETTE["ok"]),
        Text(str(summary["fresh"]), style=PALETTE["ok"]),
    )
    body.add_row(
        Text("  stale", style=stale_color),
        Text(str(summary["stale"]), style=stale_color),
    )
    body.add_row(
        Text("  never synced", style=never_color),
        Text(str(summary["never"]), style=never_color),
    )
    body.add_row(
        Text("auto-discovered", style=PALETTE["fg_muted"]),
        Text(str(summary["auto_discovered"]), style=PALETTE["fg_muted"]),
    )
    body.add_row(
        Text("ignored", style=PALETTE["fg_dim"]),
        Text(str(summary["ignored"]), style=PALETTE["fg_dim"]),
    )
    body.add_row("", "")
    body.add_row(
        Text("last sync", style=PALETTE["fg_muted"]),
        Text(_ago(summary["last_synced"]), style=f"bold {PALETTE['fg']}"),
    )

    return Panel(
        body,
        title=_title("watched repos"),
        title_align="left",
        box=ROUNDED,
        padding=(1, 1),
        **_panel_style(),
    )


def render_github_feed(rows: list[dict[str, Any]], now: datetime) -> Panel:
    table = Table.grid(padding=(0, 1), expand=True)
    table.add_column(justify="left", width=6)
    table.add_column(justify="left", width=2)
    table.add_column(justify="left", ratio=1)

    if not rows:
        table.add_row(
            Text("—", style=PALETTE["fg_dim"]),
            Text("", style=PALETTE["fg_dim"]),
            Text("no recent activity in local index", style=f"italic {PALETTE['fg_dim']}"),
        )
    for r in rows:
        ts = _parse_iso(r.get("ts"))
        ago_str = _ago(ts, now=now) if ts else "—"
        kind = r.get("kind") or ""
        sub = r.get("sub") or ""
        if kind == "item" and sub in ITEM_SUB_GLYPH:
            glyph, glyph_style = ITEM_SUB_GLYPH[sub]
        else:
            glyph, glyph_style = KIND_GLYPH.get(kind, ("·", PALETTE["fg_muted"]))

        repo = r.get("repo_full_name") or ""
        repo_short = repo.split("/")[-1] if "/" in repo else repo

        if kind == "commit":
            label = f"commit · {repo_short}"
        elif kind == "item":
            label = f"{sub or 'item'}#{r.get('num')} · {repo_short}"
        elif kind == "comment":
            label = f"comment · {repo_short}#{r.get('num')}"
        else:
            label = repo_short

        detail = _truncate(r.get("detail") or "", 60)

        line = Text()
        line.append(label, style=f"bold {PALETTE['fg']}")
        if r.get("who"):
            line.append(f"  @{r['who']}", style=PALETTE["fg_muted"])
        if detail:
            line.append("\n  ", style="")
            line.append(detail, style=PALETTE["fg_muted"])

        table.add_row(
            Text(ago_str.rjust(6), style=PALETTE["fg_dim"]),
            Text(glyph, style=glyph_style),
            line,
        )

    return Panel(
        table,
        title=_title("recent github"),
        title_align="left",
        box=ROUNDED,
        padding=(1, 1),
        **_panel_style(),
    )


def render_vault_calendar(
    vault_rows: list[dict[str, Any]],
    cal_rows: list[dict[str, Any]],
    sleuth_rows: list[dict[str, Any]],
    now: datetime,
) -> Panel:
    sections: list[Any] = []

    # Vault
    vault_table = Table.grid(padding=(0, 1), expand=True)
    vault_table.add_column(justify="left", width=6)
    vault_table.add_column(justify="left", ratio=1)
    if vault_rows:
        for v in vault_rows:
            vault_table.add_row(
                Text(_ago(v.get("last_modified"), now=now).rjust(6), style=PALETTE["fg_dim"]),
                Text(v.get("title") or v.get("rel_path") or "?", style=PALETTE["fg"]),
            )
    else:
        vault_table.add_row(
            Text("—", style=PALETTE["fg_dim"]),
            Text("no recent vault edits", style=f"italic {PALETTE['fg_dim']}"),
        )
    sections.append(Text(f"vault edits", style=f"bold {PALETTE['accent']}"))
    sections.append(vault_table)

    # Calendar
    cal_table = Table.grid(padding=(0, 1), expand=True)
    cal_table.add_column(justify="left", width=6)
    cal_table.add_column(justify="left", ratio=1)
    if cal_rows:
        for c in cal_rows:
            start_dt = _parse_iso(c.get("start_time"))
            when = (
                start_dt.astimezone(TZ).strftime("%H:%M")
                if start_dt is not None
                else "—"
            )
            summary_txt = _truncate(c.get("summary") or "(no title)", 50)
            cal_table.add_row(
                Text(when.rjust(6), style=f"bold {PALETTE['accent']}"),
                Text(summary_txt, style=PALETTE["fg"]),
            )
    else:
        cal_table.add_row(
            Text("—", style=PALETTE["fg_dim"]),
            Text("no upcoming events", style=f"italic {PALETTE['fg_dim']}"),
        )
    sections.append(Text("upcoming calendar", style=f"bold {PALETTE['accent']}"))
    sections.append(cal_table)

    # Sleuth
    sleuth_table = Table.grid(padding=(0, 1), expand=True)
    sleuth_table.add_column(justify="left", width=6)
    sleuth_table.add_column(justify="left", ratio=1)
    if sleuth_rows:
        for s in sleuth_rows:
            msg = compact_sleuth_reminder(s.get("reminder_message_text") or "")
            role = "by me" if s.get("sleuth_role") == "assigned_by_me" else "to me"
            sleuth_table.add_row(
                Text(_ago(s.get("should_post_on"), now=now).rjust(6), style=PALETTE["fg_dim"]),
                Text(_truncate(f"{role} · {msg}", 60), style=PALETTE["fg"]),
            )
    else:
        sleuth_table.add_row(
            Text("—", style=PALETTE["fg_dim"]),
            Text("no active reminders", style=f"italic {PALETTE['fg_dim']}"),
        )
    sections.append(Text("sleuth reminders", style=f"bold {PALETTE['accent']}"))
    sections.append(sleuth_table)

    body = Group(*[Group(s, Text("")) for s in _interleave(sections)])
    return Panel(
        body,
        title=_title("vault · calendar · reminders"),
        title_align="left",
        box=ROUNDED,
        padding=(1, 1),
        **_panel_style(),
    )


def _interleave(items: list[Any]) -> list[Any]:
    """Pair (header, table) groups but skip the trailing blank line."""
    return items


def render_index_health(status: dict[str, Any]) -> Panel:
    body = Table.grid(padding=(0, 1), expand=True)
    body.add_column(justify="left")
    body.add_column(justify="right")
    body.add_column(justify="right")

    sources = status.get("sources", {})
    semantic = status.get("semantic_index") or {}

    def row(label: str, count: Any, last: Any, color: str) -> None:
        body.add_row(
            Text(label, style=PALETTE["fg"]),
            Text(str(count if count is not None else "—"), style=f"bold {color}"),
            Text(_ago(last) if last else "—", style=PALETTE["fg_dim"]),
        )

    vault = sources.get("vault") or {}
    github = sources.get("github") or {}
    calendar = sources.get("calendar") or {}
    sleuth = sources.get("sleuth") or {}

    row("vault chunks", vault.get("chunks"), vault.get("last_ingested_at"), PALETTE["ok"])
    row("github items", github.get("items"), github.get("documents_last_fetched_at"), PALETTE["accent"])
    row("github docs", github.get("documents"), github.get("documents_last_updated_at"), PALETTE["accent"])
    row("calendar events", calendar.get("events"), calendar.get("last_fetched_at"), PALETTE["info"])
    row("sleuth reminders", sleuth.get("reminders"), sleuth.get("last_synced_at"), PALETTE["info"])
    body.add_row("", "", "")
    row(
        "semantic docs",
        semantic.get("total_documents"),
        semantic.get("last_embedded_at"),
        PALETTE["ok"],
    )

    freshness = status.get("freshness") or {}
    drift_total = sum(int(v) for v in freshness.values() if isinstance(v, int))
    drift_color = PALETTE["ok"] if drift_total == 0 else PALETTE["warn"]
    body.add_row(
        Text("semantic drift", style=PALETTE["fg"]),
        Text(str(drift_total), style=f"bold {drift_color}"),
        Text(
            "rows pending" if drift_total else "in sync",
            style=drift_color if drift_total == 0 else PALETTE["fg_muted"],
        ),
    )

    return Panel(
        body,
        title=_title("index health"),
        title_align="left",
        box=ROUNDED,
        padding=(1, 1),
        **_panel_style(),
    )


def render_footer(refresh_snapshot: dict[str, Any], now: datetime) -> Panel:
    bits: list[Text] = []

    status = refresh_snapshot["status"]
    if status == "running":
        bits.append(Text("● refreshing github…", style=f"bold {PALETTE['accent']}"))
    elif status == "ok":
        last = refresh_snapshot["last_finished"]
        profile = refresh_snapshot.get("last_profile") or {}
        slowest_repo = profile.get("slowest_repo")
        slowest_seconds = profile.get("slowest_seconds")
        if slowest_repo and isinstance(slowest_seconds, (int, float)):
            repo_short = str(slowest_repo).split("/")[-1]
            bits.append(Text(
                f"● github refreshed {_ago(last, now=now)} · slowest {repo_short} {slowest_seconds:.1f}s",
                style=PALETTE["ok"],
            ))
        else:
            bits.append(Text(f"● github refreshed {_ago(last, now=now)}", style=PALETTE["ok"]))
    elif status == "error":
        err = refresh_snapshot["last_error"][:60]
        bits.append(Text(f"✗ refresh failed: {err}", style=PALETTE["danger"]))
    else:
        bits.append(Text("○ idle", style=PALETTE["fg_dim"]))

    auto = (
        f"auto-refresh every {AUTO_REFRESH_MINUTES}m"
        if AUTO_REFRESH_MINUTES > 0
        else "auto-refresh off"
    )

    sep = Text("  ·  ", style=PALETTE["fg_dim"])

    line = Text()
    for i, b in enumerate(bits):
        if i:
            line.append_text(sep)
        line.append_text(b)
    line.append_text(sep)
    line.append(auto, style=PALETTE["fg_muted"])
    line.append_text(sep)
    line.append("[r]", style=f"bold {PALETTE['accent']}")
    line.append(" refresh now", style=PALETTE["fg_muted"])
    line.append_text(sep)
    line.append("[q]", style=f"bold {PALETTE['accent']}")
    line.append(" quit", style=PALETTE["fg_muted"])

    return Panel(line, box=ROUNDED, padding=(0, 1), **_panel_style())


def build_layout() -> Layout:
    layout = Layout(name="root")
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1),
    )
    layout["left"].split(
        Layout(name="watched", size=14),
        Layout(name="vault", ratio=1),
    )
    layout["right"].split(
        Layout(name="github", ratio=1),
        Layout(name="health", size=14),
    )
    return layout


def render(layout: Layout) -> Layout:
    now = datetime.now(timezone.utc)

    try:
        watched = fetch_watched_summary(now)
    except Exception as exc:
        watched = {
            "total": 0, "fresh": 0, "stale": 0, "never": 0,
            "ignored": 0, "auto_discovered": 0, "last_synced": None,
            "_err": f"{type(exc).__name__}: {exc}",
        }

    try:
        github_rows = fetch_recent_github()
    except Exception:
        github_rows = []

    try:
        vault_rows = fetch_vault_recent()
    except Exception:
        vault_rows = []

    try:
        cal_rows = fetch_calendar_upcoming(now)
    except Exception:
        cal_rows = []

    try:
        sleuth_rows = fetch_sleuth_due()
    except Exception:
        sleuth_rows = []

    try:
        status = get_index_status(DB_PATH)
    except Exception as exc:
        status = {"_err": f"{type(exc).__name__}: {exc}", "sources": {}, "semantic": {}, "drift": {}}

    layout["header"].update(render_header(now))
    layout["watched"].update(render_watched(watched))
    layout["github"].update(render_github_feed(github_rows, now))
    layout["vault"].update(render_vault_calendar(vault_rows, cal_rows, sleuth_rows, now))
    layout["health"].update(render_index_health(status))
    layout["footer"].update(render_footer(REFRESH.snapshot(), now))
    return layout


# ---------------------------------------------------------------------------
# Keyboard input — single-char reads in cbreak mode
# ---------------------------------------------------------------------------


class CbreakStdin:
    def __init__(self) -> None:
        self.fd: int | None = None
        self.old: list[Any] | None = None
        self.enabled = sys.stdin.isatty()

    def __enter__(self) -> "CbreakStdin":
        if not self.enabled:
            return self
        self.fd = sys.stdin.fileno()
        self.old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, *exc: Any) -> None:
        if self.enabled and self.fd is not None and self.old is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    def poll_char(self) -> str | None:
        if not self.enabled:
            return None
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return None
        return sys.stdin.read(1)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> int:
    if not DB_PATH.exists():
        print(f"REBALANCE_DB not found: {DB_PATH}", file=sys.stderr)
        return 1

    console = Console(style=f"on {PALETTE['bg']}")
    layout = build_layout()

    threading.Thread(target=_auto_refresh_loop, daemon=True).start()

    with CbreakStdin() as kb, Live(
        render(layout),
        console=console,
        refresh_per_second=4,
        screen=True,
    ) as live:
        try:
            while True:
                if _stop_event.wait(TICK_SECONDS):
                    break
                ch = kb.poll_char()
                if ch:
                    if ch in ("q", "Q", "\x03", "\x04"):
                        break
                    if ch in ("r", "R"):
                        _trigger_manual_refresh()
                live.update(render(layout))
        except KeyboardInterrupt:
            pass
        finally:
            _stop_event.set()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
