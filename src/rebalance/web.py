"""Minimal FastAPI web server for rebalance-OS local dashboards.

Start with:
    rebalance serve            # default port 8787
    rebalance serve --port 9000

Routes
------
GET /              — index with links to all pages
GET /focus-5       — top-5 device-local repos: tree health, newest PR, activity
GET /auth-log      — unified auth-activity log across all collectors (HTML table)
GET /auth-log/raw  — raw JSONL file download
"""

from __future__ import annotations

import base64
import html
import json
import logging
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import (
    HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse,
)
from pydantic import BaseModel

from rebalance.ingest.auth_log import read_log, _log_path
from rebalance.ingest import zapier_calendar, zapier_email
from rebalance.ingest.sleuth_grouping import grouped_reminders_from_db
from rebalance.lib.time_ops import format_relative, parse_utc_iso
from rebalance.paths import resolve_db, resolve_secret_path
from rebalance.web_components import badge_html, button_link, render_shell
logger = logging.getLogger(__name__)

# How long a persisted Focus 5 roster stays authoritative before a visit lazily
# recomputes it. Membership is snapshot-stable for this window; working-tree
# health is always re-probed live on load regardless.
FOCUS5_ROSTER_TTL_SECONDS = 24 * 3600

# The free-form note shown at the bottom of the Focus 5 Float card lives in the
# operator's Obsidian vault as ``focus5.md``. Cap the read so an oversized note
# can't balloon the JSON response (the file is hand-written, normally tiny).
FOCUS5_NOTE_FILENAME = "focus5.md"
FOCUS5_NOTE_MAX_CHARS = 64 * 1024

# A second bottom drawer in Focus 5 Float reads the operator's top open tasks
# from the vault-root ``0. Goals.md`` file. Keep the list short enough for the
# panel and only mutate the checkbox marker on completion.
FOCUS5_GOALS_FILENAME = "0. Goals.md"
FOCUS5_GOALS_MAX_ITEMS = 8

@asynccontextmanager
async def _app_lifespan(web_app: FastAPI):
    _refresh_zapier_secret_state(web_app, log_errors=True)
    yield


app = FastAPI(title="rebalance-OS", docs_url=None, redoc_url=None, lifespan=_app_lifespan)

ZAPIER_SECRET_NAME = "zapier-webhook-secret"
_ZAPIER_RATE_LIMIT_CAPACITY = 100.0
_ZAPIER_RATE_LIMIT_REFILL_PER_SECOND = _ZAPIER_RATE_LIMIT_CAPACITY / 60.0
_ZAPIER_RATE_LIMIT_BUCKETS: dict[str, tuple[float, float]] = {}
_ZAPIER_RATE_LIMIT_LOCK = threading.Lock()


def _load_zapier_secret(*, log_errors: bool) -> str | None:
    path = resolve_secret_path(ZAPIER_SECRET_NAME)
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        if log_errors:
            logger.error("zapier webhook secret missing: %s", path)
        return None
    except OSError as exc:
        if log_errors:
            logger.error("zapier webhook secret unreadable: %s (%s)", path, exc)
        return None
    if not secret:
        if log_errors:
            logger.error("zapier webhook secret empty: %s", path)
        return None
    return secret


def _refresh_zapier_secret_state(web_app: FastAPI, *, log_errors: bool) -> str | None:
    secret = _load_zapier_secret(log_errors=log_errors)
    web_app.state.zapier_webhook_secret = secret
    return secret


def _get_zapier_secret(web_app: FastAPI) -> str | None:
    if not hasattr(web_app.state, "zapier_webhook_secret"):
        return _refresh_zapier_secret_state(web_app, log_errors=False)
    return web_app.state.zapier_webhook_secret

def _verify_zapier_auth(request: Request, secret: str) -> bool:
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("basic "):
        token = auth.split(" ", 1)[1].strip()
        try:
            decoded = base64.b64decode(token, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        username, sep, password = decoded.partition(":")
        if sep and username and secrets.compare_digest(password, secret):
            return True

    fallback = request.query_params.get("zapier_secret")
    return bool(fallback) and secrets.compare_digest(fallback, secret)


def _zapier_rate_limit_allows(client_ip: str, *, now: float | None = None) -> bool:
    current = time.monotonic() if now is None else now
    key = client_ip or "unknown"
    with _ZAPIER_RATE_LIMIT_LOCK:
        tokens, updated_at = _ZAPIER_RATE_LIMIT_BUCKETS.get(
            key, (_ZAPIER_RATE_LIMIT_CAPACITY, current),
        )
        tokens = min(
            _ZAPIER_RATE_LIMIT_CAPACITY,
            tokens + max(0.0, current - updated_at) * _ZAPIER_RATE_LIMIT_REFILL_PER_SECOND,
        )
        allowed = tokens >= 1.0
        if allowed:
            tokens -= 1.0
        _ZAPIER_RATE_LIMIT_BUCKETS[key] = (tokens, current)
    return allowed


def _zapier_is_dry_run(request: Request) -> bool:
    return (request.query_params.get("dry_run") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _zapier_handler_for(source: str) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
    if source == "email":
        return zapier_email.handle_email_event
    if source == "calendar":
        return zapier_calendar.handle_calendar_event
    return None


def _zapier_is_database_locked(exc: Exception) -> bool:
    return "database is locked" in str(exc).lower()


def _zapier_log_request(
    *,
    request_id: str,
    source: str | None,
    dry_run: bool,
    status: int,
    duration_ms: int,
) -> None:
    logger.info(
        "zapier_webhook %s",
        json.dumps(
            {
                "request_id": request_id,
                "source": source,
                "dry_run": dry_run,
                "status": status,
                "duration_ms": duration_ms,
            },
            sort_keys=True,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> PlainTextResponse:
    """Local dashboard: show the real traceback in-browser instead of a bare
    'Internal Server Error'. Gated by ``app.state.show_tracebacks`` (default
    True; serve.py turns it off when bound to a non-loopback host so tracebacks
    never leak off-box). The traceback is always logged regardless."""
    import traceback

    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    if getattr(request.app.state, "show_tracebacks", True):
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return PlainTextResponse(tb, status_code=500)
    return PlainTextResponse("Internal Server Error", status_code=500)


app.add_exception_handler(Exception, unhandled_exception_handler)

# Auth-log badges keyed to a semantic variant (ok|warn|danger|info|neutral),
# resolved to a design token by web_components.badge_html — no inline hex.
_EVENT_BADGE = {
    # calendar
    "flow_started":         ("info",    "▶ flow started"),
    "flow_succeeded":       ("ok",      "✓ flow succeeded"),
    "flow_failed":          ("danger",  "✗ flow failed"),
    "token_missing":        ("warn",    "⚠ token missing"),
    "token_refreshed":      ("ok",      "↻ token refreshed"),
    "token_refresh_failed": ("danger",  "✗ refresh failed"),
    # github
    "token_validated":      ("ok",      "✓ token validated"),
    "token_set":            ("info",    "↻ token (re)set"),
    "token_invalid":        ("danger",  "✗ token invalid"),
    "auth_failed":          ("danger",  "✗ auth failed (401)"),
    "gh_fallback":          ("ok",      "✓ healed via gh CLI"),
    # sleuth
    "sync_succeeded":       ("ok",      "✓ sync succeeded"),
    # gmail
    "adc_missing":          ("warn",    "⚠ ADC missing"),
    "scope_insufficient":   ("danger",  "✗ scope insufficient"),
    # launchd jobs
    "job_started":          ("info",    "▶ started"),
    "job_completed":        ("ok",      "✓ completed"),
    "job_failed":           ("danger",  "✗ failed"),
    # watch-list coverage guard (only emitted on a concerning drop)
    "watched_repos_reduced": ("warn",   "⚠ watched repos reduced"),
    # GH-124: commit-threshold auto-promotion
    "project_auto_promoted": ("ok",     "✓ project auto-added"),
}

_SOURCE_BADGE = {
    "calendar": ("info",    "calendar"),
    "github":   ("neutral", "github"),
    "gmail":    ("neutral", "gmail"),
    "sleuth":   ("neutral", "sleuth"),
    "launchd":  ("neutral", "launchd"),
    "registry": ("neutral", "registry"),
}

# Page-local CSS for the FastAPI surfaces (Focus 5 / Auth Log / Home). The base
# resets + the .app/.sidebar shell + global h1/h2/h3 now come from
# RB_CHROME_CSS (injected by render_shell), so only the BODY-specific rules live
# here. All colours are design tokens (var(--…)) so the palette is single-sourced;
# none of these rules touch the dashboard (which never includes _CSS).
_CSS = """
h2 { font-size: 15px; font-weight: 600; color: var(--muted); margin-bottom: 16px; }
table { width: 100%; border-collapse: collapse; background: var(--card);
        border-radius: 8px; overflow: hidden;
        box-shadow: var(--shadow); }
th { background: var(--border); font-size: 12px; font-weight: 600;
     color: var(--muted); text-align: left; padding: 10px 14px; }
td { padding: 10px 14px; font-size: 13px;
     border-top: 1px solid var(--border); vertical-align: top; }
tr:hover td { background: var(--zebra); }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
         font-size: 11px; font-weight: 600; color: #fff; white-space: nowrap; }
.badge-ok      { background: var(--ok);     color: #fff; }
.badge-warn    { background: var(--warn);   color: #fff; }
.badge-danger  { background: var(--danger); color: #fff; }
.badge-info    { background: var(--info);   color: #fff; }
.badge-neutral { background: var(--fg-dim); color: #fff; }
.detail { font-family: "SF Mono", "Fira Code", monospace; font-size: 11px;
          color: var(--muted); word-break: break-all; }
.empty { text-align: center; padding: 48px; color: var(--muted); font-size: 14px; }
.raw-link { float: right; font-size: 12px; color: var(--accent); text-decoration: none; }
.raw-link:hover { text-decoration: underline; }

/* Sleuth reminder groups (home page) */
.sr-search-bar { display:flex; align-items:center; gap:12px; margin-bottom:16px; }
.sr-input { flex:1; max-width:340px; padding:6px 10px; border:1px solid var(--border);
            border-radius:6px; background:var(--card); color:var(--ink); font-size:13px; }
.sr-count-label { font-size:12px; color:var(--muted); }
.sr-groups { display:flex; flex-direction:column; gap:12px; }
.sr-group  { background:var(--card); border-radius:8px;
             box-shadow:var(--shadow); overflow:hidden; }
.sr-group-header { display:flex; align-items:center; gap:8px; padding:10px 14px;
                   border-bottom:1px solid var(--border); font-size:13px; font-weight:600; }
.sr-group-name  { flex:1; }
.sr-group-count { font-size:11px; font-weight:400; color:var(--muted); }
.sr-tasks { list-style:none; padding:0; margin:0; }
.sr-task  { padding:8px 14px; font-size:13px; border-top:1px solid var(--border); }
.sr-task:first-child { border-top:none; }
.sr-task:hover { background:var(--zebra); }

/* Focus 5 — sits inside the .app 280px-sidebar grid, so it has ~280px less width
   than the old centred 1480px <main>. Breakpoints retuned for that frame. */
.f5-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px;
           align-items: start; }
@media (max-width: 1400px) { .f5-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 1000px) { .f5-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 680px)  { .f5-grid { grid-template-columns: 1fr; } }
.f5-card { background: var(--card); border-radius: 8px; box-shadow: var(--shadow);
           padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.f5-pos { font-size: 11px; font-weight: 700; color: var(--fg-dim); }
.f5-name { font-size: 12px; font-weight: 600; color: var(--accent); text-decoration: none;
           word-break: break-word; }
.f5-name:hover { text-decoration: underline; }
.f5-reason { font-size: 11px; color: var(--muted); }
.f5-sec { border-top: 1px solid var(--border); padding-top: 8px; }
.f5-sec h4 { font-size: 10px; text-transform: uppercase; letter-spacing: .04em;
             color: var(--fg-dim); font-weight: 700; margin-bottom: 5px; }
.f5-branch { font-family: "SF Mono", monospace; font-size: 11px; color: var(--ink); }
.f5-drift { font-size: 11px; color: var(--muted); margin-left: 6px; }
.f5-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
          margin-right: 5px; vertical-align: middle; }
.f5-pr a { color: var(--accent); text-decoration: none; font-size: 12px; }
.f5-pr a:hover { text-decoration: underline; }
.f5-muted { font-size: 12px; color: var(--fg-dim); }
.f5-act { list-style: none; display: flex; flex-direction: column; gap: 5px; }
.f5-act li { font-size: 12px; line-height: 1.35; }
.f5-act .when { color: var(--timestamp); font-size: 10px; }
.f5-meta { font-size: 12px; color: var(--muted); margin-bottom: 16px; }
.f5-live { color: var(--ok); }
.f5-stale { color: var(--warn); font-weight: 700; }
.f5-refresh { font-size: 13px; font-weight: 600; color: var(--accent); text-decoration: none;
              margin-left: 10px; }
.f5-refresh:hover { text-decoration: underline; }
.f5-warn { background: rgba(166,95,0,.08); border: 1px solid rgba(166,95,0,.28); color: var(--warn);
           border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; font-size: 13px;
           line-height: 1.5; }
.f5-warn b { color: var(--warn); }
/* GH-105: a slim, friendly (non-alarm) nudge — deliberately lighter than
   .f5-warn so it reads as "BTW" rather than a risk warning. */
.f5-dirty-banner { background: var(--zebra); border: 1px solid var(--border);
                    color: var(--muted); border-radius: 8px; padding: 6px 14px;
                    margin-bottom: 12px; font-size: 12px; line-height: 1.4; }
.f5-dirty-banner b { color: var(--ink); }
/* GH-81 Phase 2: a fallback-basis badge on a rostered card (reflog disabled). */
.f5-basis { color: var(--muted); font-weight: 400; font-size: 12px; }
/* Focus 5 / Dirty Five view toggle — a small segmented control. */
.f5-views { display: inline-flex; gap: 4px; padding: 3px; margin-bottom: 16px;
            background: var(--card); border: 1px solid var(--border); border-radius: 8px; }
.f5-view { font-size: 13px; font-weight: 600; color: var(--muted); text-decoration: none;
           padding: 4px 12px; border-radius: 6px; }
.f5-view:hover { color: var(--ink); }
.f5-view.active { background: var(--zebra); color: var(--accent); }

/* What's Next — the single ranked "work on next" list. Reuses the shared
   .badge/.empty rules; only the list/row chrome is page-local. */
.wn-refresh { font-size: 13px; font-weight: 600; color: var(--accent); text-decoration: none;
              margin-left: 10px; }
.wn-refresh:hover { text-decoration: underline; }
.wn-meta { font-size: 12px; color: var(--muted); margin-bottom: 16px; }
.wn-blended { color: var(--ok); }
.wn-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.wn-item { background: var(--card); border-radius: 8px; box-shadow: var(--shadow);
           padding: 12px 14px; display: flex; gap: 12px; align-items: flex-start; }
.wn-rank { font-size: 13px; font-weight: 700; color: var(--fg-dim); min-width: 28px;
           font-variant-numeric: tabular-nums; }
.wn-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.wn-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.wn-title { font-size: 14px; font-weight: 600; color: var(--ink); word-break: break-word; }
.wn-why { font-size: 12px; color: var(--muted); line-height: 1.4; }
.wn-ev { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 3px; }
.wn-ev li { font-size: 11px; color: var(--fg-dim); word-break: break-word; }
.wn-src { font-size: 11px; color: var(--fg-dim); text-transform: uppercase; letter-spacing: .04em; }
"""


def _auth_event_badge(entry: dict[str, Any]) -> tuple[str, str]:
    """Resolve the auth-log badge, allowing source-specific labels per event."""
    event = str(entry.get("event") or "unknown")
    detail = entry.get("detail")
    detail = detail if isinstance(detail, dict) else {}
    if event == "sync_succeeded" and entry.get("source") == "sleuth":
        source_mode = str(detail.get("source_mode") or "").strip().lower()
        if source_mode == "file-source":
            return ("ok", "✓ file source synced")
    return _EVENT_BADGE.get(event, ("neutral", event))


def _auth_detail_html(detail: dict[str, Any]) -> str:
    if not detail:
        return "—"
    lines = []
    for key, value in detail.items():
        lines.append(f"<b>{html.escape(str(key))}</b>: {html.escape(str(value))}")
    return "<br>".join(lines)


def _page(title: str, body: str, *, active: str, wide: bool = False, extra_css: str = "") -> HTMLResponse:
    """Wrap a page body in the shared sidebar shell (tokens + chrome + buttons).

    The nav/sidebar comes from render_shell (minimal, I/O-free sidebar); ``active``
    marks the current nav item (``'today' | 'focus5' | 'authlog'``).
    """
    return HTMLResponse(
        render_shell(title, body, active=active, wide=wide, page_css=_CSS + "\n" + extra_css)
    )


_KIND_BADGE = {
    "github":  ("info",    "GH"),
    "client":  ("ok",      "client"),
    "channel": ("neutral", "channel"),
    "other":   ("neutral", "other"),
}


def _render_sleuth_groups() -> str:
    """Return the Sleuth reminder groups section HTML, or an empty string on error."""
    try:
        groups = grouped_reminders_from_db(resolve_db())
    except Exception:
        return ""
    if not groups:
        return ""

    total_tasks = sum(len(g.reminders) for g in groups)
    rows: list[str] = []
    for g in groups:
        variant, badge_label = _KIND_BADGE.get(g.kind, ("neutral", g.kind))
        tasks_html = "".join(
            f"<li class='sr-task' data-text='{html.escape(r['task_text'].lower())}'>"
            f"{html.escape(r['task_text']) or '<em style=\"color:var(--fg-dim)\">—</em>'}"
            f"</li>"
            for r in g.reminders
        )
        rows.append(
            f"<div class='sr-group'>"
            f"<div class='sr-group-header'>"
            f"{badge_html(badge_label, variant)}"
            f"<span class='sr-group-name'>{html.escape(g.label)}</span>"
            f"<span class='sr-group-count'>{len(g.reminders)} reminder{'s' if len(g.reminders) != 1 else ''}</span>"
            f"</div>"
            f"<ul class='sr-tasks'>{tasks_html}</ul>"
            f"</div>"
        )

    groups_html = "\n".join(rows)
    return (
        f"<h2 style='margin-top:28px;'>Reminders"
        f"<span style='font-size:12px;font-weight:400;color:var(--muted);margin-left:10px;'>"
        f"{total_tasks} active across {len(groups)} group{'s' if len(groups) != 1 else ''}"
        f"</span></h2>"
        f"<div class='sr-search-bar'>"
        f"<input id='srSearch' class='sr-input' type='search' autocomplete='off'"
        f"  oninput='srFilter()' placeholder='Search reminders…'>"
        f"<span id='srCountLabel' class='sr-count-label'></span>"
        f"</div>"
        f"<div id='srGroups' class='sr-groups'>{groups_html}</div>"
        f"<script>"
        f"function srFilter(){{"
        f"var q=(document.getElementById('srSearch').value||'').trim().toLowerCase();"
        f"var vis=0;"
        f"document.querySelectorAll('.sr-group').forEach(function(g){{"
        f"var n=0;"
        f"g.querySelectorAll('.sr-task').forEach(function(t){{"
        f"var m=!q||t.dataset.text.includes(q);"
        f"t.style.display=m?'':'none'; if(m)n++;"
        f"}});"
        f"g.style.display=n?'':'none'; vis+=n;"
        f"}});"
        f"var el=document.getElementById('srCountLabel');"
        f"el.textContent=q?(vis+' task'+(vis!==1?'s':'')+' matching'):'';"
        f"}}"
        f"</script>"
    )


# The rich "Today" dashboard is rendered by the pulse server (web/pulse.html on
# :8767). This web app exists mainly to serve JSON (e.g. /focus-5.json) and the
# sub-pages; its bare "/" used to render a sparse near-duplicate landing, which
# read as a "reverted" home. Redirect to the canonical pulse dashboard so both
# servers present one coherent home. (:8767 is the documented pulse-server port;
# the pulse server is the always-running launchd job.)
PULSE_DASHBOARD_URL = "http://127.0.0.1:8767/"


@app.get("/")
def index() -> RedirectResponse:
    return RedirectResponse(PULSE_DASHBOARD_URL, status_code=307)


def _rel_time(iso: str | None) -> str:
    """Render an ISO-8601 timestamp as a compact relative age (e.g. '3h ago')."""
    return format_relative(iso)


def _f5_health(card: dict[str, Any]) -> str:
    """Working-tree health (re-probed live): dot + counts + branch + drift."""
    if not card.get("health_available", True):
        return ("<div class='f5-sec'><h4>Tree health · live</h4>"
                "<span class='f5-muted'>⚠ unavailable (repo not readable)</span></div>")
    if card["is_dirty"]:
        dot, parts = "var(--danger)", []
        if card["modified_count"]:
            parts.append(f"{card['modified_count']} modified")
        if card["untracked_count"]:
            parts.append(f"{card['untracked_count']} untracked")
        state = ", ".join(parts) or "dirty"
    else:
        dot, state = "var(--ok)", "clean"
    branch = html.escape(card["branch"] or "(detached)")
    drift = ""
    if card["has_upstream"] and (card["ahead"] or card["behind"]):
        drift = f"<span class='f5-drift'>↑{card['ahead']} ↓{card['behind']}</span>"
    elif not card["has_upstream"]:
        drift = "<span class='f5-drift'>no upstream</span>"
    return (
        f"<div class='f5-sec'><h4>Tree health</h4>"
        f"<span class='f5-dot' style='background:{dot}'></span>"
        f"<span>{state}</span><br>"
        f"<span class='f5-branch'>{branch}</span>{drift}</div>"
    )


def _f5_warning_strip(data: dict[str, Any]) -> str:
    """Hidden-attention strip: repos outside the top 5 that still need care.

    Sourced from the cached signals (not a live sweep), so it carries the roster
    snapshot's freshness, made explicit in the label.
    """
    warns = data.get("off_roster_warnings") or []
    if not warns:
        return ""
    # GH-81 Phase 2: each repo carries its rank explanation (recency + basis vs the
    # #5 cutoff) so "why isn't this in Focus 5?" is answered inline, not via git log.
    # The explain copy is recent_activity-specific ("below the #5 cutoff", "Focus
    # 5"), so it's only rendered on the headline board — the Dirty Five view ranks
    # under dirty_first and would be mislabelled by it. (Codex relay r2.)
    from rebalance.ingest.focus5_scan import explain_recency
    explain_on = data.get("ranking_mode") == "recent_activity"
    cutoff = (data.get("summary") or {}).get("rank_cutoff_ts")
    now_ts = int(datetime.now(timezone.utc).timestamp())
    shown, items = warns[:8], []
    for w in shown:
        reason = w.get("warning_reason")
        if not reason:
            from rebalance.ingest.focus5_scan import off_roster_reason
            reason = off_roster_reason(w)
        item = f"<b>{html.escape(w['repo_name'])}</b> ({html.escape(reason)})"
        if explain_on:
            why = html.escape(
                explain_recency(w.get("recency_basis"), w.get("my_local_commit_ts"),
                                cutoff, now_ts)
            )
            item += f" <span class='f5-muted'>— {why}</span>"
        items.append(item)
    more = f" · +{len(warns) - len(shown)} more" if len(warns) > len(shown) else ""
    age = _rel_time(data.get("computed_at"))
    return (
        f"<div class='f5-warn'>⚠ <b>{len(warns)}</b> repo(s) outside the top 5 need "
        f"attention <span class='f5-muted'>(as of roster computed {age})</span>: "
        f"{' · '.join(items)}{more}</div>"
    )


def _f5_dirty_banner(data: dict[str, Any]) -> str:
    """Slim single-row "BTW, this went dirty" nudge above card #1 (GH-105).

    Deliberately shows at most one repo (the single most-recently-touched
    dirty one, per ``pick_newest_dirty_off_roster``) so it stays a passive
    nudge rather than duplicating ``_f5_warning_strip``'s full off-roster
    list. ``dirty_banner`` is already ``None`` on the Dirty Five transient
    rerank (every dirty repo is a full card there — see ``summarize_focus5``),
    so no view check is needed here.
    """
    banner = data.get("dirty_banner")
    if not banner:
        return ""
    name = html.escape(banner["repo_name"])
    when = _rel_time(
        datetime.fromtimestamp(banner["my_local_commit_ts"], tz=timezone.utc).isoformat()
    )
    bits = []
    if banner.get("modified_count"):
        bits.append(f"{banner['modified_count']} modified")
    if banner.get("untracked_count"):
        bits.append(f"{banner['untracked_count']} untracked")
    detail = ", ".join(bits) or "uncommitted changes"
    return (
        f"<div class='f5-dirty-banner'>👋 BTW, recent work on <b>{name}</b> left it "
        f"dirty ({detail}) — last commit {when}</div>"
    )


def _f5_pr(card: dict[str, Any]) -> str:
    """Newest remote PR, or an explicit unavailable state (never drop the repo)."""
    pr = card.get("newest_pr")
    if pr:
        tag = " · draft" if pr.get("is_draft") else (" · merged" if pr.get("is_merged") else "")
        title = html.escape(pr["title"] or "")
        inner = (
            f"<a href='{html.escape(pr['html_url'] or '#')}' target='_blank' rel='noopener'>"
            f"#{pr['number']} {title}</a>"
            f"<span class='f5-muted'> ({html.escape(pr.get('state') or '')}{tag})</span>"
        )
    elif card.get("repo_full_name"):
        inner = "<span class='f5-muted'>no open PR synced yet</span>"
    elif card.get("remote_url"):
        inner = "<span class='f5-muted'>non-GitHub remote</span>"
    else:
        inner = "<span class='f5-muted'>no remote configured</span>"
    return f"<div class='f5-sec f5-pr'><h4>Newest PR</h4>{inner}</div>"


def _f5_activity(card: dict[str, Any]) -> str:
    items = card.get("recent_activity") or []
    if not items:
        return "<div class='f5-sec'><h4>Recent activity</h4><span class='f5-muted'>no local commits</span></div>"
    lis = "".join(
        f"<li>{html.escape(c['subject'])}<br>"
        f"<span class='when'>{html.escape(c['sha'])} · {_rel_time(c.get('committed_at'))}</span></li>"
        for c in items
    )
    return f"<div class='f5-sec'><h4>Recent activity</h4><ul class='f5-act'>{lis}</ul></div>"


def _f5_card(card: dict[str, Any]) -> str:
    name = html.escape(card["repo_name"])
    vs_href = card.get("vscode_url") or "#"
    vsurl = html.escape(vs_href)
    reason = html.escape(card.get("rank_reason") or "")
    # GH-81 Phase 2: when a card ranked by a FALLBACK basis (reflog disabled), show
    # it — a degraded basis must never be silent, even for a rostered repo.
    from rebalance.ingest.focus5_scan import basis_badge
    badge = basis_badge(card.get("recency_basis"))
    reason_badge = f" <span class='f5-basis'>({html.escape(badge)})</span>" if badge else ""
    # Hide identity: owner/repo when there's a remote, else the device-local path
    # (matches focus5_repo_identity / the focus5_hidden_repos config list).
    identity = html.escape(
        card.get("repo_full_name") or card.get("local_path") or "", quote=True
    )
    # Top-right action cluster: the standard "Open ↗" button (shared helper, so it
    # matches the dashboard home) next to the ✕ hide control. `data-f5-open` carries
    # the repo identity so the click JS can POST it to /api/focus5/open (focus-if-
    # open via the server's `code <folder>`); the vscode:// href stays as the no-JS
    # / failure fallback so the button is never dead.
    open_btn = button_link(
        "Open", vs_href, title="Open repo in VS Code",
        attrs=f'data-f5-open="{identity}"',
    )
    hide_btn = (
        f"<button class='f5-hide' data-f5-hide=\"{identity}\" "
        f"title='Hide from Focus 5' aria-label='Hide {name} from Focus 5'>✕</button>"
    )
    actions = f"<div class='f5-actions'>{open_btn}{hide_btn}</div>"
    return (
        f"<div class='f5-card'>"
        f"{actions}"
        f"<div><div class='f5-pos'>#{card['position']}</div>"
        f"<a class='f5-name' href='{vsurl}' title='Open in VS Code' data-f5-open=\"{identity}\">{name}</a>"
        f"<div class='f5-reason'>{reason}{reason_badge}</div></div>"
        f"{_f5_health(card)}{_f5_pr(card)}{_f5_activity(card)}"
        f"</div>"
    )


def _focus5_body(data: dict[str, Any], *, view: str = "focus5") -> str:
    """Render the Focus 5 page body from a summarize_focus5() dict (pure).

    *view* selects the headline board (``"focus5"`` → recent_activity) or the
    safety board (``"dirty"`` → dirty_first). Both reuse this renderer; only the
    title, the refresh target, the active toggle, and the empty-state copy differ.
    """
    is_dirty_view = view == "dirty"
    title = "🧹 Dirty Five" if is_dirty_view else "🎯 Focus 5"
    # &amp; — this is an href in an HTML attribute, so the ampersand is entity-encoded.
    refresh_href = "/focus-5?refresh=1&amp;view=dirty" if is_dirty_view else "/focus-5?refresh=1"
    refresh_btn = f"<a class='f5-refresh' href='{refresh_href}' title='Re-rank now'>↻ Refresh</a>"
    # Segmented Focus 5 / Dirty Five toggle (active view highlighted).
    tabs = (("focus5", "/focus-5", "🎯 Focus 5"), ("dirty", "/focus-5?view=dirty", "🧹 Dirty Five"))
    toggle = "<div class='f5-views'>" + "".join(
        f"<a class='f5-view{' active' if k == view else ''}' href='{href}'>{label}</a>"
        for k, href, label in tabs
    ) + "</div>"
    head = f"<h2>{title} {refresh_btn}</h2>{toggle}"
    roster = data.get("roster") or []
    if not roster:
        empty = (
            "Nothing at risk — no uncommitted or unpushed work outside the top 5. "
            "Clean desk."
            if is_dirty_view else
            "No active repos found yet. The roster builds from your local git "
            "activity — make a commit or leave uncommitted work in a repo under "
            "your dev folders, then reload."
        )
        return f"{head}<div class='empty'>{empty}</div>"
    mode = html.escape(data.get("ranking_mode") or "")
    computed = _rel_time(data.get("computed_at"))
    # Roster membership is a snapshot (≤24h); tree health is re-probed live. Say
    # so, and flag the rare stale case (e.g. a refresh that failed) explicitly.
    stale = "<span class='f5-stale'>⚠ stale</span> " if _roster_stale(data.get("computed_at")) else ""
    meta = (
        f"<div class='f5-meta'>{stale}Roster computed <b>{computed}</b> · ranked by "
        f"<b>{mode}</b> · {data['summary']['discovered']} repos discovered · "
        f"<span class='f5-live'>● tree health checked live</span></div>"
    )
    strip = _f5_warning_strip(data)
    banner = _f5_dirty_banner(data)
    cards = "".join(_f5_card(c) for c in roster)
    return f"{head}{meta}{strip}{banner}<div class='f5-grid'>{cards}</div>{_FOCUS5_HIDE_ASSETS}{_FOCUS5_OPEN_ASSETS}"


# Scoped CSS + JS for the per-card hide (✕) control. Kept in the Focus 5 body so
# it doesn't touch the shared page chrome. The ✕ POSTs to /api/focus5/hide, which
# adds the repo to focus5_hidden_repos and re-ranks from cache, then we reload so
# the board refills with the next candidate(s).
_FOCUS5_HIDE_ASSETS = """
<style>
.f5-card { position: relative; }
.f5-actions { position:absolute; top:8px; right:10px; display:flex;
  align-items:center; gap:8px; }
.f5-hide { width:24px; height:24px; border:none; border-radius:50%;
  background:transparent; color:var(--fg-dim); font-size:15px; line-height:24px;
  text-align:center; cursor:pointer; padding:0;
  transition:background .12s, color .12s; }
.f5-hide:hover { background:rgba(192,57,43,.10); color:var(--danger); }
.f5-hide:focus-visible { outline:2px solid var(--danger); outline-offset:1px; }
.f5-hide[disabled] { opacity:.4; cursor:default; }
</style>
<script>
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.f5-hide');
  if (!btn || btn.disabled) return;
  const repo = btn.getAttribute('data-f5-hide');
  if (!repo) return;
  btn.disabled = true;
  try {
    const res = await fetch('/api/focus5/hide', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo }),
    });
    if (res.ok) { window.location.reload(); return; }
  } catch (_) { /* fall through to re-enable */ }
  btn.disabled = false;
  btn.title = 'Hide failed — try again';
});
</script>
"""


# Scoped JS for the "Open ↗" focus-if-open action. Any element carrying
# `data-f5-open="<identity>"` (the Open button AND the repo-name link) POSTs that
# identity to /api/focus5/open, which runs `code <folder>` server-side so an
# already-open VS Code window is focused instead of clobbered. On ANY failure
# (no-JS, server down, `code` missing → 409, unknown id → 404) it falls through to
# the element's vscode:// href, so the action is never dead.
_FOCUS5_OPEN_ASSETS = """
<script>
document.addEventListener('click', async (e) => {
  const el = e.target.closest('[data-f5-open]');
  if (!el) return;
  const repo = el.getAttribute('data-f5-open');
  if (!repo) return;
  e.preventDefault();
  try {
    const res = await fetch('/api/focus5/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo }),
    });
    if (res.ok) return;
  } catch (_) { /* fall through to the vscode:// fallback */ }
  const href = el.getAttribute('href');
  if (href && href !== '#') window.location.href = href;
});
</script>
"""


def _roster_stale(computed_at: str | None) -> bool:
    """True if the roster snapshot is missing or older than the TTL."""
    if not computed_at:
        return True
    ts = parse_utc_iso(computed_at)
    if ts is None:
        return True
    return (datetime.now(timezone.utc) - ts).total_seconds() > FOCUS5_ROSTER_TTL_SECONDS


@app.get("/focus-5")
def focus5_page(refresh: bool = False, view: str = "focus5"):
    from rebalance.ingest.focus5_scan import (
        get_roster_meta, summarize_focus5, sync_focus5,
    )
    from rebalance.paths import DatabaseNotFoundError, resolve_database_path

    # Two views over the SAME device-local snapshot: the default headline board
    # (recent_activity, persisted in focus5_roster) and the transient "Dirty Five"
    # safety board (dirty_first, re-ranked from the cached signals on the fly).
    # Dirty Five never overwrites the persisted roster, so /focus-5 still defaults
    # to recent_activity afterwards.
    dirty_view = view == "dirty"
    page_title = "Dirty Five" if dirty_view else "Focus 5"

    try:
        db = resolve_database_path()
    except DatabaseNotFoundError:
        body = (f"<h2>🎯 {page_title}</h2><div class='empty'>No rebalance database found. "
                "Run <code>rebalance refresh-index</code> first.</div>")
        return _page(page_title, body, active="focus5", wide=True)

    # Recompute the roster only when forced (↻ Refresh) or never built — NOT on a
    # stale TTL. sync_focus5() is a ~30s synchronous device-local git scan; running
    # it inline on a stale page load blocked the request and made the page look
    # broken. A stale roster now renders instantly with the "⚠ stale" badge; the
    # operator re-ranks on demand via the Refresh button (?refresh=1). The scan
    # always rebuilds the default (recent_activity) snapshot; the Dirty Five view
    # then re-ranks that same fresh signal cache.
    meta = get_roster_meta(db)
    if refresh or not meta["roster_size"]:
        try:
            sync_focus5(db)
        except Exception:  # noqa: BLE001 — a scan failure must not 500 the page
            pass
        if refresh:
            # Post/redirect/get: drop ?refresh so a browser reload doesn't re-scan,
            # but keep the view the operator was on.
            target = "/focus-5?view=dirty" if dirty_view else "/focus-5"
            return RedirectResponse(target, status_code=303)

    # mode=None → persisted recent_activity roster; mode="dirty_first" → transient
    # re-rank from the cached signals (no write). Health is re-probed live in both.
    data = summarize_focus5(db, mode="dirty_first" if dirty_view else None)
    return _page(page_title, _focus5_body(data, view=view), active="focus5", wide=True)


# --------------------------------------------------------------------------- #
# 3-Eyes fleet job-health tile (GH-195) — a synthetic Focus 5 roster card.
#
# 3-Eyes (utils/3-eyes) is the optional local job supervisor. When it is ACTIVE on
# this machine, /focus-5.json appends ONE extra roster card summarizing whether the
# catalogued scheduled jobs are healthy — so the "a job is failing" signal rides
# along on the panel the operator already watches. The card renders through the
# app's existing dynamic ForEach (no native-app change; CONTRACT.md documents the
# additive 6th tile). It is:
#   * additive + fully defensive — ANY failure (3-Eyes absent, import error,
#     launchctl error) yields no card and the roster is served unchanged;
#   * gated on 3-Eyes being active — a downstream/inert clone never shows it; and
#   * cached (short TTL) so this read-only, frequently-polled route never spawns
#     `launchctl list` on every request.
# --------------------------------------------------------------------------- #

_THREE_EYES_DIR = Path(__file__).resolve().parents[2] / "utils" / "3-eyes"
_TE_HEALTH_TTL_S = 20.0
_te_health_lock = threading.Lock()
_te_health_cache: dict[str, Any] = {"at": -1e9, "card": None}


def _three_eyes_health_scan() -> dict | None:
    """Return ``three_eyes.health.scan()`` when 3-Eyes is ACTIVE here, else None.

    Isolated so the import + activation gate + subprocess all live behind the one
    try/except in the caller: a problem here must never break /focus-5.json.
    """
    import sys

    d = str(_THREE_EYES_DIR)
    if d not in sys.path:
        sys.path.insert(0, d)
    from three_eyes import config as te_config, health as te_health

    if not te_config.three_eyes_active():
        return None
    return te_health.scan()


def _build_three_eyes_card(report: dict) -> dict:
    """Shape a 3-Eyes health report into a RepoCard-compatible dict (snake_case).

    Mapping: the verdict rides in ``repo_name`` (the card title) and ``rank_reason``
    (which the app shows as the always-visible subtitle when the commit timestamps
    are null); ``is_dirty`` drives the red StatusDot when anything is failing.
    """
    ok = int(report.get("ok", 0))
    failing = int(report.get("failing", 0))
    not_loaded = int(report.get("not_loaded", 0))
    unknown = int(report.get("unknown", 0))
    probe_ok = bool(report.get("launchctl_available", True))
    fail_rows = [r for r in report.get("rows", []) if "FAIL" in r.get("health", "")]
    verdict = f"{ok} ok · {failing} failing · {not_loaded} not-loaded"
    if not probe_ok:
        # The probe could not run. Never render this as a clean bill of health —
        # an unreadable fleet must look like it needs attention, not like it is green.
        title = "3-Eyes — job health UNKNOWN"
        why = report.get("probe_error") or "launchctl could not be consulted"
        reason = f"3-Eyes could not read launchd job state ({why}). Health is unknown, not confirmed healthy."
    elif failing:
        title = f"3-Eyes — {failing} job{'s' if failing != 1 else ''} FAILING"
        detail = "; ".join(f"{r['label']} {r['health']}" for r in fail_rows[:6])
        reason = f"3-Eyes fleet job health — {verdict}. Failing: {detail}."
    else:
        title = "3-Eyes — all jobs OK"
        reason = f"3-Eyes fleet job health — {verdict}. All catalogued jobs healthy."
    now_iso = datetime.now(timezone.utc).isoformat()
    path = str(_THREE_EYES_DIR)
    return {
        "position": 0,                      # re-stamped by the caller
        "repo_name": title,
        "repo_full_name": None,
        "local_path": path,                 # unique → stable Identifiable card id
        "remote_url": None,
        "vscode_url": f"vscode://file{path}",
        "rank_reason": reason,              # commitLine falls back to this → subtitle
        "ranking_mode": "three_eyes_health",
        "computed_at": now_iso,
        "branch": None,
        "upstream": None,
        "has_upstream": None,
        "ahead": 0,
        "behind": 0,
        "modified_count": failing,          # failing count in the "M" slot
        "untracked_count": not_loaded if probe_ok else unknown,
        "is_dirty": (failing > 0) or not probe_ok,   # red StatusDot: failing OR unreadable
        "health_available": probe_ok,
        "health_probed_at": now_iso,
        "last_commit_at": None,             # null → commitLine shows rank_reason
        "last_commit_ts": None,
        "my_last_commit_ts": None,
        "probed_at": now_iso,
        "newest_pr": None,
        "recent_activity": [],
    }


def _three_eyes_health_card(position: int) -> dict | None:
    """Build the synthetic 3-Eyes health roster card, or None. Cached + defensive."""
    now = time.monotonic()
    with _te_health_lock:
        if (now - _te_health_cache["at"]) >= _TE_HEALTH_TTL_S:
            card = None
            try:
                report = _three_eyes_health_scan()
                if report is not None:
                    card = _build_three_eyes_card(report)
            except Exception:               # never break the roster endpoint
                logger.debug("3-Eyes health tile skipped", exc_info=True)
                card = None
            _te_health_cache["at"] = now
            _te_health_cache["card"] = card
        card = _te_health_cache["card"]
    if card is None:
        return None
    return {**card, "position": position}


@app.get("/focus-5.json")
def focus5_json(view: str = "focus5") -> JSONResponse:
    """Read-only JSON projection of the Focus 5 roster for native/desktop clients.

    Same data as ``GET /focus-5``, as JSON instead of HTML — the single contract a
    macOS/desktop client decodes. **Strictly read-only:** it never runs the device
    git scan (``sync_focus5``) and never rewrites the persisted roster. ``?view=dirty``
    only re-ranks the cached signals in memory (the Dirty Five board), exactly like
    the HTML view. Forcing a fresh device walk is a *mutation* and is deliberately
    NOT reachable here — a client that must rebuild calls a separate explicit POST
    action, never this GET.

    LOCAL-ONLY: cards carry operator-local fields (``local_path``, ``vscode_url``,
    absolute ``remote_url``). This serves the localhost desktop client; a remote
    mirror must use a separate sanitized projection, not this route.
    """
    from rebalance.ingest.focus5_scan import summarize_focus5
    from rebalance.paths import DatabaseNotFoundError, resolve_database_path

    try:
        db = resolve_database_path()
    except DatabaseNotFoundError:
        # Brand-new machine: return the empty contract shape (not a 404) so the
        # polling client always decodes the same structure.
        return JSONResponse({
            "roster": [], "off_roster_warnings": [], "dirty_banner": None,
            "computed_at": None, "ranking_mode": None,
            "summary": {"discovered": 0, "roster_size": 0,
                        "off_roster_attention": 0, "rank_cutoff_ts": None},
        })

    data = summarize_focus5(db, mode="dirty_first" if view == "dirty" else None)
    logger.info("focus5.json: view=%s roster=%d", view, data["summary"]["roster_size"])
    # GH-195: append the 3-Eyes fleet-health tile when 3-Eyes is active here. Additive
    # and defensive — None when 3-Eyes is inert/absent, leaving the roster untouched.
    tile = _three_eyes_health_card(len(data["roster"]) + 1)
    if tile is not None:
        data["roster"].append(tile)
    return JSONResponse(data)


@app.get("/focus-5/note")
def focus5_note() -> JSONResponse:
    """Read-only projection of the operator's Obsidian ``focus5.md`` note.

    Surfaces a free-form markdown note — kept at the root of the configured
    Obsidian vault — at the bottom of the Focus 5 Float card. **Strictly
    read-only:** it never creates or writes the file; it only reads it.

    LOCAL-ONLY: the note lives on the operator's machine and may hold private
    context, so this serves the localhost desktop client only — never a remote
    mirror.

    Always returns ``{exists, content, path}`` with HTTP 200 (never a 404), so
    the client decodes one shape. ``exists`` is False with empty ``content`` when
    no vault is configured, the vault has no ``focus5.md``, or the file can't be
    read — the client then shows its "add a focus5.md to your vault" hint.
    """
    from rebalance.ingest.config import get_vault_path

    vault = get_vault_path()
    if not vault:
        return JSONResponse({"exists": False, "content": "", "path": None})

    note = Path(vault).expanduser() / FOCUS5_NOTE_FILENAME
    try:
        if not note.is_file():
            return JSONResponse({"exists": False, "content": "", "path": None})
        content = note.read_text(encoding="utf-8", errors="replace")[:FOCUS5_NOTE_MAX_CHARS]
    except OSError as exc:
        logger.warning("focus5.note: could not read %s: %s", note, exc)
        return JSONResponse({"exists": False, "content": "", "path": None})

    logger.info("focus5.note: served %d chars from %s", len(content), note)
    return JSONResponse({"exists": True, "content": content, "path": str(note)})


def _focus5_goals_payload() -> dict[str, Any]:
    from rebalance.ingest.config import get_vault_path
    from rebalance.ingest.goals_file import parse_goals

    vault = get_vault_path()
    if not vault:
        return {
            "exists": False,
            "items": [],
            "path": None,
            "total_open": 0,
            "reason": "vault_not_configured",
            "message": "vault_path is not configured",
        }

    goals = Path(vault).expanduser() / FOCUS5_GOALS_FILENAME
    try:
        if not goals.is_file():
            return {
                "exists": False,
                "items": [],
                "path": str(goals),
                "total_open": 0,
                "reason": "file_missing",
                "message": f"{FOCUS5_GOALS_FILENAME} not found in the configured vault",
            }
        all_items = parse_goals(goals, limit=None)
    except OSError as exc:
        logger.warning("focus5.goals: could not read %s: %s", goals, exc)
        return {
            "exists": False,
            "items": [],
            "path": str(goals),
            "total_open": 0,
            "reason": "read_failed",
            "message": str(exc),
        }

    items = [
        {
            "title": str(item.get("title") or ""),
            "description": str(item.get("description") or ""),
            "line_index": item.get("line_index"),
        }
        for item in all_items[:FOCUS5_GOALS_MAX_ITEMS]
    ]
    logger.info(
        "focus5.goals: served %d of %d open tasks from %s",
        len(items), len(all_items), goals,
    )
    return {
        "exists": True,
        "items": items,
        "path": str(goals),
        "total_open": len(all_items),
        "reason": None,
        "message": None,
    }


@app.get("/focus-5/goals")
def focus5_goals() -> JSONResponse:
    """Read-only projection of the operator's top open tasks from ``0. Goals.md``.

    Always returns ``{exists, items, path, total_open}`` at HTTP 200 so the
    native client decodes one shape. ``items`` are the first 8 unchecked tasks
    in file order, each with ``title``, ``description``, and ``line_index``.
    """
    return JSONResponse(_focus5_goals_payload())


class Focus5GoalCompleteRequest(BaseModel):
    title: str
    line_index: int | None = None


@app.post("/api/focus5/goals/complete")
def focus5_complete_goal(req: Focus5GoalCompleteRequest, request: Request) -> JSONResponse:
    """Flip one ``0. Goals.md`` checkbox from open to complete, then re-read."""
    from rebalance.ingest.goals_file import complete_goal_in_file

    if not _request_is_local(request):
        logger.warning("focus5 goals: rejected non-local request from %s", request.client)
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)

    title = (req.title or "").strip()
    if not title:
        return JSONResponse({"ok": False, "error": "title is required"}, status_code=400)

    payload = _focus5_goals_payload()
    path = payload.get("path")
    if not path:
        return JSONResponse(
            {"ok": False, "error": "goals file missing"},
            status_code=404,
        )

    completion = complete_goal_in_file(
        Path(path),
        title,
        line_index=req.line_index,
    )
    if not completion:
        return JSONResponse(
            {"ok": False, "error": "goal not found", "title": title},
            status_code=404,
        )

    refreshed = _focus5_goals_payload()
    return JSONResponse({
        "ok": True,
        "title": title,
        "line_index": completion["line_index"],
        **refreshed,
    })


class Focus5HideRequest(BaseModel):
    repo: str


def focus5_set_hidden(repo: str, *, hidden: bool) -> dict[str, Any]:
    """Hide / un-hide a repo from the Focus 5 roster, then re-rank from cache.

    Shared by this server and the always-running pulse server so both ``/focus-5``
    surfaces handle the ✕ the same way. Adds (or removes) the repo identity in
    ``focus5_hidden_repos`` and rewrites the roster from the already-probed
    signals — no git re-probe — so the board refills with the next candidate(s).
    Never raises: a missing DB or a re-rank hiccup degrades to ``reranked: False``.
    """
    from rebalance.ingest.config import (
        add_focus5_hidden_repo, remove_focus5_hidden_repo,
    )
    from rebalance.ingest.focus5_scan import rerank_focus5_from_cache
    from rebalance.paths import DatabaseNotFoundError, resolve_database_path

    identity = (repo or "").strip()
    if not identity:
        return {"ok": False, "error": "empty repo identity"}
    changed = (
        add_focus5_hidden_repo(identity) if hidden
        else remove_focus5_hidden_repo(identity)
    )
    try:
        db = resolve_database_path()
        roster_size = rerank_focus5_from_cache(db)
        return {"ok": True, "changed": changed, "reranked": True, "roster_size": roster_size}
    except DatabaseNotFoundError:
        return {"ok": True, "changed": changed, "reranked": False, "roster_size": None}
    except Exception:  # noqa: BLE001 — the config change stuck; don't 500 the click
        return {"ok": True, "changed": changed, "reranked": False, "roster_size": None}


@app.post("/api/focus5/hide")
def focus5_hide(req: Focus5HideRequest) -> JSONResponse:
    return JSONResponse(focus5_set_hidden(req.repo, hidden=True))


@app.post("/api/focus5/unhide")
def focus5_unhide(req: Focus5HideRequest) -> JSONResponse:
    return JSONResponse(focus5_set_hidden(req.repo, hidden=False))


# ---------------------------------------------------------------------------
# Focus 5 "Open ↗" focus-if-open (VSCODE-OPEN-WORKSPACE Phase 2).
#
# The browser can't run `code <folder>`, so the dashboard POSTs a repo IDENTITY
# here and the local server runs it. The path is NEVER client-supplied: the id is
# resolved to a local_path from the server's own freshly-summarized roster (the
# allowlist), unknown ids are rejected (404, logged as a tripwire), and the launch
# is a direct-argv subprocess (shell=False) so there is no command-injection class.
# Bound to loopback + same-origin only — this executes a binary, so it refuses any
# request that isn't from the local dashboard itself.
# ---------------------------------------------------------------------------

# Same fixed candidate order as the Mac app's VSCodeLauncher (Homebrew arm64 →
# Intel → app bundle); the order is part of the contract.
_VSCODE_CODE_CANDIDATES = (
    "/opt/homebrew/bin/code",
    "/usr/local/bin/code",
    "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
)


def _resolve_code_binary() -> str | None:
    """Resolve the ``code`` executable: ``VSCODE_BIN`` override → known locations →
    PATH lookup. Returns None when none is found (caller returns 409)."""
    import os
    import shutil

    # `os.access(.., X_OK)` is true for a directory (execute == traverse), so guard
    # with isfile — else a VSCODE_BIN pointing at a dir would later raise IsADirectoryError.
    override = os.environ.get("VSCODE_BIN")
    if override and os.path.isfile(override) and os.access(override, os.X_OK):
        return override
    for cand in _VSCODE_CODE_CANDIDATES:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return shutil.which("code")


def _focus5_open_allowlist(db: Path) -> dict[str, str]:
    """Build ``identity → local_path`` from the server's own roster — the allowlist.

    Unions the default (Focus 5) and dirty (Dirty Five) boards so a card visible in
    either view resolves. The identity is the same key the card renders
    (``repo_full_name`` or, lacking a remote, ``local_path``). Only the server's
    scanned data is trusted; a client-supplied path never reaches the launcher.
    """
    from rebalance.ingest.focus5_scan import summarize_focus5

    allow: dict[str, str] = {}
    for mode in (None, "dirty_first"):
        try:
            data = summarize_focus5(db, mode=mode)
        except Exception:  # noqa: BLE001 — a probe hiccup must not break resolution
            continue
        for card in data.get("roster") or []:
            identity = card.get("repo_full_name") or card.get("local_path")
            local_path = card.get("local_path")
            if identity and local_path:
                allow[identity] = local_path
    return allow


def focus5_open_repo(repo: str) -> tuple[int, dict[str, Any]]:
    """Resolve *repo* (a card identity) to its local_path via the allowlist and run
    ``code <local_path>``. Returns ``(http_status, body)``. Never raises."""
    identity = (repo or "").strip()
    if not identity:
        return 400, {"ok": False, "error": "empty repo identity"}

    from rebalance.paths import DatabaseNotFoundError, resolve_database_path

    try:
        db = resolve_database_path()
    except DatabaseNotFoundError:
        return 404, {"ok": False, "error": "no database"}

    local_path = _focus5_open_allowlist(db).get(identity)
    if not local_path:
        # Tripwire: a miss means a caller asked for an id the server never issued.
        logger.warning("focus5 open: allowlist MISS for identity=%r", identity)
        return 404, {"ok": False, "error": "unknown repo"}

    code_bin = _resolve_code_binary()
    if not code_bin:
        logger.info("focus5 open: no `code` binary — client falls back to vscode://")
        return 409, {"ok": False, "error": "code binary not found"}

    import subprocess

    try:
        # Direct argv — no shell, no string interpolation. `code <folder>` returns
        # promptly (it talks to VS Code over IPC); cap it so a hung launch can't pin
        # the request.
        proc = subprocess.run(  # noqa: S603 — argv list, allowlisted path, no shell
            [code_bin, local_path],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001 — surface as 500, client falls back
        logger.error("focus5 open: launch failed for %s: %s", local_path, exc)
        return 500, {"ok": False, "error": "launch failed"}

    logger.info(
        "focus5 open: identity=%r path=%s bin=%s exit=%s",
        identity, local_path, code_bin, proc.returncode,
    )
    return 200, {"ok": True, "exit_code": proc.returncode}


def _request_is_local(request: Request) -> bool:
    """Two-layer local-only gate for the exec endpoint (defense in depth).

    1. **Client host must be loopback.** ``rebalance serve`` *can* bind a non-loopback
       host (web.py turns off tracebacks in that mode), so the bind alone is not a
       guarantee. Without this check a LAN client could POST with no ``Origin``
       (e.g. ``curl``) and trigger ``code`` opens on the host. (Per agy QA r1.)
    2. **Same-origin.** A cross-origin browser fetch always carries an ``Origin``
       header, so reject any ``Origin`` whose host isn't loopback — defeats a
       malicious page CSRF-ing the browser into POSTing here.

    Returns False to refuse. NOTE: Starlette's ``TestClient`` reports a non-loopback
    client host, so route tests bypass this guard (patch ``_request_is_local``) and
    the gate itself is covered by dedicated unit tests over a fake request.
    """
    from urllib.parse import urlparse

    loopback = {"127.0.0.1", "::1", "localhost"}
    client_host = (request.client.host if request.client else "") or ""
    if client_host not in loopback:
        return False
    origin = request.headers.get("origin")
    if origin and (urlparse(origin).hostname or "") not in loopback:
        return False
    return True


@app.post("/api/focus5/open")
def focus5_open(req: Focus5HideRequest, request: Request) -> JSONResponse:
    if not _request_is_local(request):
        logger.warning("focus5 open: rejected non-local request from %s", request.client)
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    status, body = focus5_open_repo(req.repo)
    return JSONResponse(body, status_code=status)


# ---------------------------------------------------------------------------
# Zapier ingest — Phase 1 webhook receiver.
# ---------------------------------------------------------------------------


@app.get("/api/zapier/health")
def zapier_health(request: Request) -> JSONResponse:
    return JSONResponse({
        "ok": True,
        "secret_configured": bool(_get_zapier_secret(request.app)),
    })


@app.post("/api/zapier/ingest")
async def zapier_ingest(request: Request) -> JSONResponse:
    request_id = uuid.uuid4().hex
    source: str | None = None
    dry_run = _zapier_is_dry_run(request)
    started_at = time.monotonic()
    status_code = 500

    try:
        secret = _get_zapier_secret(request.app)
        if not secret:
            status_code = 503
            return JSONResponse(
                {"ok": False, "error": "secret_not_configured", "request_id": request_id},
                status_code=status_code,
            )

        if not _verify_zapier_auth(request, secret):
            status_code = 403
            return JSONResponse(
                {"ok": False, "error": "forbidden", "request_id": request_id},
                status_code=status_code,
            )

        client_ip = (request.client.host if request.client else "") or "unknown"
        if not _zapier_rate_limit_allows(client_ip):
            status_code = 429
            return JSONResponse(
                {"ok": False, "error": "rate_limited", "request_id": request_id},
                status_code=status_code,
            )

        try:
            payload = await request.json()
        except json.JSONDecodeError:
            status_code = 400
            return JSONResponse(
                {"ok": False, "error": "invalid_json", "request_id": request_id},
                status_code=status_code,
            )

        if not isinstance(payload, dict):
            status_code = 400
            return JSONResponse(
                {"ok": False, "error": "invalid_payload", "request_id": request_id},
                status_code=status_code,
            )

        source = str(payload.get("source") or "").strip().lower()
        handler = _zapier_handler_for(source)
        if handler is None:
            status_code = 400
            return JSONResponse(
                {
                    "ok": False,
                    "error": "unknown_source",
                    "request_id": request_id,
                    "source": source or None,
                },
                status_code=status_code,
            )

        if dry_run:
            status_code = 200
            return JSONResponse(
                {
                    "ok": True,
                    "request_id": request_id,
                    "source": source,
                    "dry_run": True,
                },
                status_code=status_code,
            )

        result = handler(payload)
        body: dict[str, Any] = {"ok": True, "request_id": request_id, "source": source}
        if isinstance(result, dict):
            body.update(result)
        else:
            body["result"] = result
        status_code = 200
        return JSONResponse(body, status_code=status_code)
    except NotImplementedError as exc:
        status_code = 501
        return JSONResponse(
            {
                "ok": False,
                "error": "not_implemented",
                "request_id": request_id,
                "source": source,
                "detail": str(exc),
            },
            status_code=status_code,
        )
    except sqlite3.OperationalError as exc:
        if _zapier_is_database_locked(exc):
            status_code = 503
            return JSONResponse(
                {
                    "ok": False,
                    "error": "database_locked",
                    "request_id": request_id,
                    "source": source,
                },
                status_code=status_code,
            )
        raise
    finally:
        _zapier_log_request(
            request_id=request_id,
            source=source,
            dry_run=dry_run,
            status=status_code,
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )


# ---------------------------------------------------------------------------
# What's Next — the single ranked "what should we work on next" view.
#
# Pure renderer over a RankedNextActions.as_dict() shape; the handler is
# control-flow only. Person labels are LOCAL-DISPLAY-ONLY and html.escape'd here
# (this is the local dashboard, never an export/pushed-pulse path).
# ---------------------------------------------------------------------------


def _wn_person_badge(person: str | None) -> str:
    """Attribution badge: operator's own items vs a teammate-labelled one.

    ``person`` is None for the operator's own signals (info badge "You") and a
    teammate label otherwise (neutral badge). The label is html.escape'd by
    badge_html — it is local-display-only and never exported.
    """
    if not person:
        return badge_html("info", "You")
    return badge_html("neutral", str(person))


def _wn_item(action: dict[str, Any]) -> str:
    """Render one ranked next-action row (pure). Escapes ALL untrusted text."""
    rank = action.get("rank") or 0
    title = html.escape(str(action.get("title") or "(untitled)"))
    source = html.escape(str(action.get("source") or ""))
    project = action.get("project")
    why = str(action.get("why") or "").strip()

    head_bits = [f"<span class='wn-title'>{title}</span>", _wn_person_badge(action.get("person"))]
    if source:
        head_bits.append(f"<span class='wn-src'>{source}</span>")
    if project:
        head_bits.append(badge_html("neutral", str(project)))
    if action.get("automation"):
        # Candidate for a GitHub issue → coding-agent (Codex / Claude Code) hook.
        head_bits.append(badge_html("warn", "⚙ automation"))
    head = "<div class='wn-head'>" + "".join(head_bits) + "</div>"

    why_html = f"<div class='wn-why'>{html.escape(why)}</div>" if why else ""

    ev_items = [str(e) for e in (action.get("evidence") or []) if e]
    if ev_items:
        ev_lis = "".join(f"<li>{html.escape(e)}</li>" for e in ev_items)
        ev_html = f"<ul class='wn-ev'>{ev_lis}</ul>"
    else:
        ev_html = ""

    return (
        f"<li class='wn-item'>"
        f"<div class='wn-rank'>#{int(rank)}</div>"
        f"<div class='wn-body'>{head}{why_html}{ev_html}</div>"
        f"</li>"
    )


def _wn_meta(data: dict[str, Any]) -> str:
    """The 'last computed <relative>' freshness line + synthesis/blended indicator."""
    computed = _rel_time(data.get("computed_at"))
    model = html.escape(str(data.get("model_used") or ""))
    if data.get("blended"):
        blend = "<span class='wn-blended'>● team-blended</span>"
    else:
        blend = "<span class='wn-src'>operator-only</span>"
    synth = f" · synthesized by <b>{model}</b>" if model else " · deterministic order"
    when = f"last computed <b>{computed}</b>" if computed else "not computed yet"
    return f"<div class='wn-meta'>{when} · {blend}{synth}</div>"


def _whatsnext_body(data: dict[str, Any]) -> str:
    """Render the What's Next page body from a RankedNextActions dict (pure)."""
    refresh_btn = (
        "<a class='wn-refresh' href='/whats-next?refresh=1' "
        "title='Recompute now'>↻ Refresh</a>"
    )
    ranked = data.get("ranked") or []
    if not ranked:
        note = html.escape(str(data.get("note") or "")) if data.get("note") else ""
        note_html = f"<div class='subtle'>{note}</div>" if note else ""
        return (
            f"<h2>🧭 What's Next {refresh_btn}</h2>"
            "<div class='empty'>Nothing ranked yet. The list builds from your "
            "calendar, GitHub, vault, reminders and email — blended with teammate "
            "signal. Hit ↻ Refresh to compute it.</div>"
            f"{note_html}"
        )
    meta = _wn_meta(data)
    rows = "".join(_wn_item(a) for a in ranked)
    return (
        f"<h2>🧭 What's Next {refresh_btn}</h2>{meta}"
        f"<ul class='wn-list'>{rows}</ul>"
    )


@app.get("/whats-next")
def whatsnext_page(refresh: bool = False):
    """Render the ranked 'what should we work on next' view.

    Reads the PRECOMPUTED result via ``load_ranked_next_actions``. On ``?refresh``
    (or when no precomputed result exists) it recomputes LIVE via
    ``rank_next_actions`` — the only network-allowed synthesis path — persists it,
    and Post/Redirect/Get's to drop ``?refresh``. Control-flow only; zero HTML
    built here. A compute/IO failure degrades to whatever is renderable rather
    than 500ing.
    """
    from rebalance.ingest.next_actions import (
        get_ranked_meta, load_ranked_next_actions,
        persist_ranked_next_actions, rank_next_actions,
    )
    from rebalance.paths import DatabaseNotFoundError, resolve_database_path

    try:
        db = resolve_database_path()
    except DatabaseNotFoundError:
        body = ("<h2>🧭 What's Next</h2><div class='empty'>No rebalance database found. "
                "Run <code>rebalance refresh-index</code> first.</div>")
        return _page("What's Next", body, active="whatsnext", wide=True)

    # Recompute live only when forced or never precomputed — this is the
    # network-allowed synthesis path. Otherwise read the precomputed cache.
    meta = get_ranked_meta(db)
    if refresh or not meta.get("row_count"):
        try:
            # rank_next_actions never raises (it degrades to an empty-but-noted
            # result). ALWAYS persist whatever it returns — even an empty/degraded
            # result — so a row exists (row_count>0) and subsequent NORMAL loads
            # read the cache instead of recomputing live Gemini on every hit
            # (the ?refresh path stays the explicit recompute path).
            result = rank_next_actions(db, blend_team=True)
            persist_ranked_next_actions(db, result)
        except Exception:  # noqa: BLE001 — a compute/persist failure must not 500 the page
            logger.warning("whatsnext_page: live compute/persist failed", exc_info=True)
        if refresh:
            # Post/redirect/get: drop ?refresh so a reload doesn't recompute.
            return RedirectResponse("/whats-next", status_code=303)

    result = load_ranked_next_actions(db)
    data = result.as_dict() if result is not None else {"ranked": []}
    return _page("What's Next", _whatsnext_body(data), active="whatsnext", wide=True)


_SYSLOG_TOGGLE_CSS = (
    "<style>"
    ".syslog-bar{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin:.75rem 0}"
    ".syslog-toggles{display:flex;gap:.3rem;flex-wrap:wrap}"
    ".syslog-toggle{padding:.3rem .75rem;border:1px solid var(--border);border-radius:2rem;"
    "background:var(--card);cursor:pointer;font:inherit;font-size:.85rem;color:var(--ink)}"
    ".syslog-toggle.active{background:var(--accent);border-color:var(--accent);color:var(--accent-ink);font-weight:600}"
    ".syslog-input{flex:1;min-width:14rem;padding:.4rem .6rem;font:inherit;"
    "border:1px solid var(--border);border-radius:6px}"
    ".syslog-count{color:var(--muted);font-size:.85rem;white-space:nowrap}"
    "</style>"
)

_AUTH_LOG_SEARCH = (
    _SYSLOG_TOGGLE_CSS
    + "<div class='syslog-bar'>"
    + "<div class='syslog-toggles'>"
    + "<button class='syslog-toggle active' data-filter='all'    onclick='syslogToggle(this)'>All</button>"
    + "<button class='syslog-toggle'         data-filter='auth'  onclick='syslogToggle(this)'>Auth</button>"
    + "<button class='syslog-toggle'         data-filter='jobs'  onclick='syslogToggle(this)'>Jobs</button>"
    + "<button class='syslog-toggle'         data-filter='errors' onclick='syslogToggle(this)'>Errors &amp; Warnings</button>"
    + "</div>"
    + "<input id='syslogSearch' class='syslog-input' type='search' autocomplete='off' "
    +   "oninput='syslogFilter()' placeholder='Search…'>"
    + "<span class='syslog-count' id='syslogCount'></span>"
    + "</div>"
)

_AUTH_LOG_FILTER_JS = """
<script>
(function () {
  var AUTH_SOURCES = new Set(["github","calendar","gmail","sleuth"]);
  var _activeFilter = "all";

  function applyFilter() {
    var q = (document.getElementById("syslogSearch").value || "").trim().toLowerCase();
    var rows = document.querySelectorAll("#authLogTable tbody tr");
    var shown = 0;
    rows.forEach(function (tr) {
      var sev = tr.getAttribute("data-severity") || "";
      var src = tr.getAttribute("data-source") || "";
      var filterMatch;
      switch (_activeFilter) {
        case "auth":   filterMatch = AUTH_SOURCES.has(src); break;
        case "jobs":   filterMatch = (src === "launchd"); break;
        case "errors": filterMatch = (sev === "danger" || sev === "warn"); break;
        default:       filterMatch = true;
      }
      var textMatch = !q || tr.textContent.toLowerCase().indexOf(q) !== -1;
      var visible = filterMatch && textMatch;
      tr.style.display = visible ? "" : "none";
      if (visible) shown++;
    });
    var el = document.getElementById("syslogCount");
    if (el) el.textContent = shown + " / " + rows.length + " shown";
  }

  window.syslogToggle = function (btn) {
    document.querySelectorAll(".syslog-toggle").forEach(function (b) {
      b.classList.remove("active");
    });
    btn.classList.add("active");
    _activeFilter = btn.getAttribute("data-filter");
    applyFilter();
  };

  window.syslogFilter = applyFilter;
  document.addEventListener("DOMContentLoaded", applyFilter);
})();
</script>
"""


@app.get("/auth-log", response_class=HTMLResponse)
def auth_log_page() -> HTMLResponse:
    import json
    entries = read_log(limit=500)

    raw_link = '<a class="raw-link" href="/auth-log/raw">⬇ raw JSONL</a>'

    if not entries:
        body = f"<h2>System Log {raw_link}</h2><div class='empty'>No entries yet. Run an OAuth flow, validate the GitHub token, or run a collector sync to populate this log.</div>"
        return _page("System Log", body, active="authlog")

    rows = []
    for e in entries:
        variant, label = _auth_event_badge(e)
        badge = badge_html(variant, label)
        source = e.get("source", "")
        s_variant, s_label = _SOURCE_BADGE.get(source, ("neutral", source or "—"))
        source_badge = badge_html(s_variant, s_label)
        detail = e.get("detail", {})
        detail = detail if isinstance(detail, dict) else {}
        detail_str = _auth_detail_html(detail)
        rows.append(
            f"<tr data-severity='{variant}' data-source='{source}'>"
            f"<td>{html.escape(str(e.get('ts','')[:19].replace('T',' ')))}</td>"
            f"<td>{html.escape(str(e.get('device','')))}</td>"
            f"<td>{source_badge}</td>"
            f"<td>{badge}</td>"
            f"<td class='detail'>{detail_str}</td>"
            f"</tr>"
        )

    table = (
        f"<table id='authLogTable'><thead><tr>"
        f"<th>Timestamp (UTC)</th><th>Device</th><th>Source</th><th>Event</th><th>Detail</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )
    body = f"<h2>System Log {raw_link}</h2>{_AUTH_LOG_SEARCH}{table}{_AUTH_LOG_FILTER_JS}"
    return _page("System Log", body, active="authlog")


@app.get("/auth-log/raw", response_class=PlainTextResponse)
def auth_log_raw() -> PlainTextResponse:
    path = _log_path()
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# /sleuth-graph  — Cytoscape.js force-directed reminder relationship graph
# ---------------------------------------------------------------------------

_KIND_COLOR = {
    "client":  {"bg": "#2f7437", "border": "#1e4d25"},  # green
    "github":  {"bg": "#1d6fa8", "border": "#134d75"},  # blue
    "channel": {"bg": "#6f3fa8", "border": "#4d2a75"},  # purple
    "other":   {"bg": "#8a857c", "border": "#5b5750"},  # muted
}


def _build_graph_elements(
    groups: list,
    all_reminders: list[dict[str, Any]],
    clients: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return Cytoscape elements list (nodes + edges) for the reminder graph.

    Structure:
    - One compound parent node per group (hub)
    - One child node per reminder, parented to its group
    - Edges between reminders that share a GitHub URL (cross-group connections)
    """
    from rebalance.ingest.sleuth_grouping import find_connections

    elements: list[dict[str, Any]] = []
    reminder_to_group: dict[str, str] = {}

    # Group (parent) nodes
    for i, group in enumerate(groups):
        gid = f"g{i}"
        colors = _KIND_COLOR.get(group.kind, _KIND_COLOR["other"])
        elements.append({
            "data": {
                "id": gid,
                "label": group.label,
                "kind": group.kind,
                "count": len(group.reminders),
                "bg": colors["bg"],
                "border": colors["border"],
            },
        })
        for r in group.reminders:
            reminder_to_group[r["reminder_id"]] = gid

    # Reminder (child) nodes
    for i, group in enumerate(groups):
        gid = f"g{i}"
        for r in group.reminders:
            rid = f"r_{r['reminder_id']}"
            label = r["task_text"][:55] + "…" if len(r["task_text"]) > 55 else r["task_text"]
            elements.append({
                "data": {
                    "id": rid,
                    "parent": gid,
                    "label": label,
                    "full_text": r["task_text"],
                    "reminder_id": r["reminder_id"],
                    "channel": r.get("original_channel_name") or "",
                    "state": r.get("state") or "",
                },
            })

    # Cross-group edges: only GitHub URL connections (to avoid edge clutter)
    seen_pairs: set[frozenset[str]] = set()
    for r in all_reminders:
        if not r.get("github_urls"):
            continue
        connections = find_connections(r, all_reminders, clients=clients)
        for c in connections:
            # Only emit edges where the connection reason is a shared GitHub URL
            if not (set(r.get("github_urls") or []) & set(c.get("github_urls") or [])):
                continue
            pair = frozenset({r["reminder_id"], c["reminder_id"]})
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            elements.append({
                "data": {
                    "id": f"e_{'_'.join(sorted(pair))}",
                    "source": f"r_{r['reminder_id']}",
                    "target": f"r_{c['reminder_id']}",
                    "kind": "github",
                },
            })

    return elements


@app.get("/sleuth-graph", response_class=HTMLResponse)
def sleuth_graph_page() -> HTMLResponse:
    import json as _json
    from rebalance.ingest.sleuth_grouping import (
        grouped_reminders_from_db,
        load_active_reminders,
        load_client_mapping,
    )

    try:
        db = resolve_db()
        clients = load_client_mapping()
        groups = grouped_reminders_from_db(db, clients=clients)
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(db)
        try:
            all_reminders = load_active_reminders(conn)
        finally:
            conn.close()
        elements = _build_graph_elements(groups, all_reminders, clients)
        total = len(all_reminders)
        error_msg = ""
    except Exception as exc:
        elements = []
        total = 0
        groups = []
        error_msg = html.escape(str(exc))

    elements_json = _json.dumps(elements, ensure_ascii=False)
    group_count = len([g for g in groups if g.kind != "other"])

    _legend_entries = [("client", "Client"), ("github", "GitHub issue/PR"),
                        ("channel", "Channel"), ("other", "Other")]
    legend_items = "".join(
        "<span style='display:inline-flex;align-items:center;gap:5px;margin-right:14px;font-size:12px;color:var(--ink);'>"
        f"<span style='width:10px;height:10px;border-radius:50%;background:{_KIND_COLOR[k]['bg']};display:inline-block;'></span>"
        f"{lbl}</span>"
        for k, lbl in _legend_entries
    )

    error_html = (
        f"<div style='color:var(--danger);padding:16px;font-size:13px;'>"
        f"Error loading graph: {error_msg}</div>"
        if error_msg else ""
    )

    body = f"""
{error_html}
<div style="display:flex;align-items:center;gap:16px;margin-bottom:12px;flex-wrap:wrap;">
  <span style="font-size:13px;color:var(--muted);">
    {total} active reminders · {len(groups)} groups
  </span>
  <span style="margin-left:auto;">{legend_items}</span>
</div>
<div id="cy" style="width:100%;height:calc(100vh - 160px);min-height:500px;
     background:var(--card);border-radius:8px;
     box-shadow:var(--shadow);"></div>
<div id="cy-tooltip" style="display:none;position:fixed;background:var(--card);
     border:1px solid var(--border);border-radius:6px;padding:8px 12px;
     font-size:12px;max-width:320px;box-shadow:var(--shadow);
     pointer-events:none;z-index:100;line-height:1.5;"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.33.1/cytoscape.min.js"
        integrity="sha512-kHAY8XzRfLVMcLuowdk91552RD+Nb2/1uHamfHMdLejNqlZnbEJLl1wYnsNnqIFCEZ++WaOcOlfokC6p9JWrLw=="
        crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script>
(function() {{
  var elements = {elements_json};

  var rootStyle = getComputedStyle(document.documentElement);
  var getVar = function(prop) {{ return rootStyle.getPropertyValue(prop).trim(); }};



  var cy = cytoscape({{
    container: document.getElementById('cy'),
    elements: elements,
    style: [
      // compound group parent
      {{
        selector: 'node[kind]',
        style: {{
          'background-color': 'data(bg)',
          'border-color': getVar('--border'),
          'border-width': 2,
          'label': 'data(label)',
          'font-size': 13,
          'font-weight': 600,
          'color': getVar('--ink'),
          'text-valign': 'top',
          'text-halign': 'center',
          'text-margin-y': -6,
          'padding': 18,
          'shape': 'round-rectangle',
          'text-background-color': getVar('--card'),
          'text-background-opacity': 0.85,
          'text-background-padding': '3px',
          'text-background-shape': 'round-rectangle',
        }},
      }},
      // reminder child nodes
      {{
        selector: 'node[reminder_id]',
        style: {{
          'background-color': getVar('--card'),
          'border-color': getVar('--border'),
          'border-width': 1.5,
          'label': 'data(label)',
          'font-size': 10,
          'color': getVar('--ink'),
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 4,
          'width': 18,
          'height': 18,
          'shape': 'ellipse',
          'text-wrap': 'wrap',
          'text-max-width': 120,
        }},
      }},
      // github connection edges
      {{
        selector: 'edge[kind="github"]',
        style: {{
          'line-color': getVar('--info'),
          'width': 2,
          'line-style': 'dashed',
          'target-arrow-shape': 'none',
          'curve-style': 'bezier',
          'opacity': 0.7,
        }},
      }},
      // hover highlight
      {{
        selector: 'node:selected, node.highlighted',
        style: {{
          'border-width': 3,
          'border-color': getVar('--accent'),
          'z-index': 10,
        }},
      }},
    ],
    layout: {{
      name: 'cose',
      animate: true,
      animationDuration: 1000,
      randomize: true,
      nodeRepulsion: function() {{ return 450000; }},
      idealEdgeLength: function() {{ return 120; }},
      edgeElasticity: function() {{ return 100; }},
      nestingFactor: 1.5,
      gravity: 0.08,
      numIter: 2500,
      initialTemp: 1000,
      coolingFactor: 0.99,
      minTemp: 1.0,
      padding: 48,
      fit: true,
    }},
  }});

  // Tooltip on reminder node hover
  var tooltip = document.getElementById('cy-tooltip');
  cy.on('mouseover', 'node[reminder_id]', function(e) {{
    var d = e.target.data();
    tooltip.innerHTML =
      '<b style="display:block;margin-bottom:4px;">' + escHtml(d.full_text || d.label) + '</b>' +
      (d.channel ? '<span style="color:var(--muted);">#' + escHtml(d.channel) + '</span>' : '') +
      (d.state ? ' &nbsp;·&nbsp; <code>' + escHtml(d.state) + '</code>' : '');
    tooltip.style.display = 'block';
  }});
  cy.on('mouseout', 'node[reminder_id]', function() {{
    tooltip.style.display = 'none';
  }});
  cy.on('mousemove', function(e) {{
    if (tooltip.style.display === 'none') return;
    tooltip.style.left = (e.originalEvent.clientX + 14) + 'px';
    tooltip.style.top  = (e.originalEvent.clientY - 10) + 'px';
  }});
  cy.on('tap', 'node[reminder_id]', function(e) {{
    cy.elements().removeClass('highlighted');
    e.target.addClass('highlighted');
    e.target.neighborhood().addClass('highlighted');
  }});
  cy.on('tap', function(e) {{
    if (e.target === cy) cy.elements().removeClass('highlighted');
  }});

  function escHtml(s) {{
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }}
}})();
</script>"""

    return _page("Reminder Graph", body, active="sleuthgraph", wide=True)

def settings_page() -> HTMLResponse:
    from rebalance.web_components import data_row

    sample_rows = "".join(
        data_row(
            marker_html='<span style="width:15px;height:15px;border:1.5px solid var(--muted);border-radius:4px;display:inline-block;opacity:0.6;"></span>',
            title_html=title,
            timestamp=ts,
            stripe_index=i
        )
        for i, (title, ts) in enumerate([
            ("Invoice Taiwo", "2026-07-18T09:00:00Z"),
            ("Rebalance PRs", "2026-07-18T13:45:00Z"),
            ("Team Call", "2026-07-19T13:45:00Z"),
            ("Submit Sleuth to Product Hunt", "2026-07-20T09:00:00Z"),
        ])
    )

    page_css = """
.settings-section { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 22px; display: flex; flex-direction: column; gap: 18px; transition: background 0.25s, border-color 0.25s; }
.settings-section h2 { margin: 0; font-size: 16px; font-weight: 700; color: var(--ink); }
.settings-presets { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.preset-card { border: 2px solid var(--border); border-radius: 10px; padding: 6px; cursor: pointer; display: flex; flex-direction: column; gap: 8px; background: var(--card); transition: border-color 0.15s; }
.preset-card:hover { border-color: var(--muted); }
.preset-card.active { border-color: var(--accent); }
.preset-preview { border-radius: 6px; overflow: hidden; height: 84px; padding: 8px; display: flex; flex-direction: column; gap: 5px; }
.preset-label { display: flex; align-items: center; gap: 7px; padding: 0 4px 4px; font-weight: 600; font-size: 12.5px; color: var(--ink); }
.preset-dot { width: 14px; height: 14px; border-radius: 99px; flex-shrink: 0; border: 2px solid var(--muted); background: transparent; transition: border-color 0.15s, background 0.15s; }
.preset-card.active .preset-dot { border-color: var(--accent); background: var(--accent); }
.fine-tune-header { font-size: 11px; letter-spacing: 0.08em; font-weight: 600; color: var(--muted); text-transform: uppercase; border-top: 1px solid var(--border); padding-top: 16px; }
.fine-tune-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.color-field { display: flex; align-items: center; gap: 10px; border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; cursor: pointer; }
.color-field input[type="color"] { width: 28px; height: 28px; border: none; padding: 0; background: none; cursor: pointer; }
.color-field-label { display: flex; flex-direction: column; gap: 1px; }
.color-field-name { font-weight: 600; font-size: 12px; color: var(--ink); }
.color-field-val { font-family: "SF Mono", Menlo, monospace; font-size: 10.5px; color: var(--muted); }
.btn-primary { background: var(--accent); color: var(--accent-ink); font-weight: 600; font-size: 12px; border-radius: 7px; padding: 7px 18px; cursor: pointer; border: none; display: inline-flex; align-items: center; justify-content: center; }
.btn-secondary { background: var(--card); border: 1px solid var(--border); color: var(--ink); font-weight: 600; font-size: 12px; border-radius: 7px; padding: 7px 18px; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
.cal-preview { position: relative; border: 1px solid var(--border); border-radius: 8px; height: 56px; margin: 2px 0 6px; }
.cal-preview-time1 { position: absolute; left: 10px; top: 8px; font-size: 10.5px; color: var(--timestamp); }
.cal-preview-line1 { position: absolute; left: 48px; right: 10px; top: 12px; border-top: 1px solid var(--border); }
.cal-preview-time2 { position: absolute; left: 10px; bottom: 8px; font-size: 10.5px; color: var(--timestamp); }
.cal-preview-line2 { position: absolute; left: 48px; right: 10px; bottom: 12px; border-top: 1px solid var(--border); }
.cal-preview-now { position: absolute; left: 48px; right: 10px; top: 27px; display: flex; align-items: center; }
.cal-preview-now-dot { width: 11px; height: 11px; border-radius: 99px; background: var(--nowline); margin-left: -5px; flex-shrink: 0; }
.cal-preview-now-line { flex: 1; height: 2px; background: var(--nowline); }
"""
    body = f"""
<h2>Pulse / Settings</h2>
<div style="display: flex; flex-direction: column; gap: 20px; max-width: 760px; padding-bottom: 64px;">
  <section class="settings-section">
    <div>
      <h2>Color theme</h2>
      <div style="color: var(--muted); font-size: 13px; margin-top: 3px;">Applies to all Pulse dashboard pages and modules.</div>
    </div>
    
    <div class="settings-presets" id="presetsGrid"></div>
    
    <div class="fine-tune-header">Fine-tune colors</div>
    <div class="fine-tune-grid" id="fineTuneGrid"></div>
    
    <div style="display: flex; gap: 10px; align-items: center; margin-top: 4px;">
      <button id="btnSave" class="btn-primary">Save</button>
      <button id="btnReset" class="btn-secondary">Reset</button>
      <span style="font-size: 11.5px; color: var(--muted);">Reset returns to the selected theme's defaults.</span>
    </div>
  </section>
  
  <section class="settings-section">
    <div style="display: flex; align-items: baseline; gap: 12px;">
      <h2>Preview</h2>
      <span style="font-family: 'SF Mono', Menlo, monospace; font-size: 11px; color: var(--muted);" id="lblThemeName">theme: default</span>
    </div>
    
    <ul class="rb-data-list" style="border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-top: -4px;">
      {sample_rows}
    </ul>
    
    <div class="cal-preview">
      <span class="cal-preview-time1">1 PM</span>
      <span class="cal-preview-line1"></span>
      <span class="cal-preview-time2">2 PM</span>
      <span class="cal-preview-line2"></span>
      <span class="cal-preview-now">
        <span class="cal-preview-now-dot"></span>
        <span class="cal-preview-now-line"></span>
      </span>
    </div>
  </section>
</div>
<script>
(function() {{
  const PRESETS = {{
    default:  {{ name: 'Current default', page: '#f3efe7', card: '#ffffff', ink: '#1d2024', accent: '#1f6feb', border: '#e3ddd0', nowline: '#d43d2a', timestamp: '#8a857c' }},
    dark:     {{ name: 'Dark mode',       page: '#191713', card: '#242019', ink: '#f0ece1', accent: '#6f97ea', border: '#3a3529', nowline: '#e05a48', timestamp: '#8f887a' }},
    grey:     {{ name: 'Grey mode',       page: '#ececec', card: '#ffffff', ink: '#1e1e1e', accent: '#444444', border: '#dcdcdc', nowline: '#d43d2a', timestamp: '#8a8a8a' }},
    lightblue:{{ name: 'Light blue',      page: '#e9f0f7', card: '#ffffff', ink: '#16283c', accent: '#1d6fd1', border: '#d3e0ee', nowline: '#d43d2a', timestamp: '#7d90a5' }},
  }};
  
  const FIELD_LABELS = {{ page: 'Page background', card: 'Card background', ink: 'Text', accent: 'Accent', border: 'Borders', nowline: 'Calendar time line', timestamp: 'Date + time text' }};
  const FIELDS = window.__pulseTheme.FIELDS;
  
  let currentTheme = 'default';
  let currentColors = null; // null means using preset unmodified
  let lastPreset = 'default';
  
  function extractFields(obj) {{
    const res = {{}};
    FIELDS.forEach(f => res[f] = obj[f]);
    return res;
  }}
  
  function getWorkingColors() {{
    return currentColors || extractFields(PRESETS[currentTheme === 'custom' ? 'default' : currentTheme]);
  }}
  
  function setColors(newColors) {{
    window.__pulseTheme.apply(newColors);
  }}
  
  function renderUI() {{
    const working = getWorkingColors();
    const presetsGrid = document.getElementById('presetsGrid');
    presetsGrid.innerHTML = '';
    
    ['default', 'dark', 'grey', 'lightblue'].forEach(k => {{
      const p = PRESETS[k];
      const mix = window.__pulseTheme.mix;
      const pMuted = mix(p.ink, p.page, 0.45);
      
      const el = document.createElement('div');
      el.className = 'preset-card' + (currentTheme === k ? ' active' : '');
      el.onclick = () => {{ currentTheme = k; lastPreset = k; currentColors = null; setColors(getWorkingColors()); renderUI(); }};
      
      el.innerHTML = `
        <div class="preset-preview" style="background: ${{p.page}}; border: 1px solid ${{p.border}};">
          <div style="display: flex; gap: 4px; align-items: center;">
            <span style="width: 8px; height: 8px; border-radius: 3px; background: ${{p.accent}};"></span>
            <span style="width: 34px; height: 4px; border-radius: 99px; background: ${{p.ink}}; opacity: 0.75;"></span>
          </div>
          <div style="flex: 1; border-radius: 4px; background: ${{p.card}}; border: 1px solid ${{p.border}}; padding: 5px 6px; display: flex; flex-direction: column; gap: 4px;">
            <span style="width: 60%; height: 4px; border-radius: 99px; background: ${{p.ink}}; opacity: 0.7;"></span>
            <span style="width: 85%; height: 4px; border-radius: 99px; background: ${{pMuted}};"></span>
            <span style="width: 75%; height: 4px; border-radius: 99px; background: ${{pMuted}};"></span>
          </div>
        </div>
        <div class="preset-label">
          <span class="preset-dot"></span>
          <span>${{p.name}}</span>
        </div>
      `;
      presetsGrid.appendChild(el);
    }});
    
    const fineTuneGrid = document.getElementById('fineTuneGrid');
    fineTuneGrid.innerHTML = '';
    
    FIELDS.forEach(f => {{
      const el = document.createElement('label');
      el.className = 'color-field';
      
      const inp = document.createElement('input');
      inp.type = 'color';
      inp.value = working[f];
      inp.oninput = (e) => {{
        if (!currentColors) currentColors = {{ ...working }};
        if (currentTheme !== 'custom') {{
           lastPreset = currentTheme;
           currentTheme = 'custom';
        }}
        currentColors[f] = e.target.value;
        setColors(currentColors);
        renderUI();
      }};
      
      const textWrap = document.createElement('span');
      textWrap.className = 'color-field-label';
      textWrap.innerHTML = `<span class="color-field-name">${{FIELD_LABELS[f]}}</span><span class="color-field-val">${{working[f]}}</span>`;
      
      el.appendChild(inp);
      el.appendChild(textWrap);
      fineTuneGrid.appendChild(el);
    }});
    
    let displayName = currentTheme === 'custom' ? 'Custom' : PRESETS[currentTheme].name;
    if (currentTheme !== 'custom' && JSON.stringify(working) !== JSON.stringify(extractFields(PRESETS[currentTheme]))) {{
      displayName += ' (modified)';
    }}
    document.getElementById('lblThemeName').textContent = 'theme: ' + displayName;
    
    let saved = null;
    try {{
      const raw = localStorage.getItem(window.__pulseTheme.KEY);
      if (raw && window.__pulseTheme.parse(raw)) {{
        saved = JSON.parse(raw);
      }}
    }} catch(e) {{}}
    
    let isDirty = true;
    if (saved) {{
      isDirty = (saved.preset !== currentTheme) || (JSON.stringify(saved.inputs) !== JSON.stringify(working));
    }} else {{
      isDirty = (currentTheme !== 'default') || (JSON.stringify(working) !== JSON.stringify(extractFields(PRESETS.default)));
    }}
    
    const btnSave = document.getElementById('btnSave');
    btnSave.style.opacity = isDirty ? '1' : '0.5';
    btnSave.style.cursor = isDirty ? 'pointer' : 'default';
  }}
  
  document.getElementById('btnReset').onclick = () => {{
    if (currentTheme === 'custom') currentTheme = lastPreset;
    currentColors = null;
    setColors(getWorkingColors());
    renderUI();
  }};
  
  document.getElementById('btnSave').onclick = () => {{
    const working = getWorkingColors();
    const payload = window.__pulseTheme.record(currentTheme, extractFields(working));
    localStorage.setItem(window.__pulseTheme.KEY, JSON.stringify(payload));
    renderUI();
  }};
  
  try {{
    const raw = localStorage.getItem(window.__pulseTheme.KEY);
    const parsed = window.__pulseTheme.parse(raw);
    if (parsed) {{
      const saved = JSON.parse(raw);
      currentTheme = saved.preset || 'default';
      lastPreset = currentTheme === 'custom' ? 'default' : currentTheme;
      const filteredParsed = extractFields(parsed);
      if (currentTheme !== 'custom' && PRESETS[currentTheme]) {{
         currentColors = (JSON.stringify(filteredParsed) === JSON.stringify(extractFields(PRESETS[currentTheme]))) ? null : filteredParsed;
      }} else {{
         currentColors = filteredParsed;
      }}
    }}
  }} catch(e) {{}}
  
  setColors(getWorkingColors());
  renderUI();
}})();
</script>
"""
    return _page("Settings", body, active="settings", wide=True, extra_css=page_css)
