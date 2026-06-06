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

import html
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse

from rebalance.ingest.auth_log import read_log, _log_path

app = FastAPI(title="rebalance-OS", docs_url=None, redoc_url=None)

_EVENT_BADGE = {
    # calendar
    "flow_started":         ("#1a73e8", "▶ flow started"),
    "flow_succeeded":       ("#34a853", "✓ flow succeeded"),
    "flow_failed":          ("#ea4335", "✗ flow failed"),
    "token_missing":        ("#fbbc05", "⚠ token missing"),
    "token_refreshed":      ("#34a853", "↻ token refreshed"),
    "token_refresh_failed": ("#ea4335", "✗ refresh failed"),
    # github
    "token_validated":      ("#34a853", "✓ token validated"),
    "token_set":            ("#1a73e8", "↻ token (re)set"),
    "token_invalid":        ("#ea4335", "✗ token invalid"),
    "auth_failed":          ("#ea4335", "✗ auth failed (401)"),
    "gh_fallback":          ("#34a853", "✓ healed via gh CLI"),
    # gmail
    "adc_missing":          ("#fbbc05", "⚠ ADC missing"),
    "scope_insufficient":   ("#ea4335", "✗ scope insufficient"),
}

_SOURCE_BADGE = {
    "calendar": ("#1a73e8", "calendar"),
    "github":   ("#24292f", "github"),
    "gmail":    ("#d93025", "gmail"),
}

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #f8f9fa; color: #202124; }
header { background: #fff; border-bottom: 1px solid #dadce0;
         padding: 14px 24px; display: flex; align-items: center; gap: 16px; }
header h1 { font-size: 18px; font-weight: 600; }
nav a { color: #1a73e8; text-decoration: none; font-size: 14px; }
nav a:hover { text-decoration: underline; }
main { max-width: 1100px; margin: 32px auto; padding: 0 24px; }
h2 { font-size: 15px; font-weight: 600; color: #5f6368; margin-bottom: 16px; }
table { width: 100%; border-collapse: collapse; background: #fff;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,.12); }
th { background: #f1f3f4; font-size: 12px; font-weight: 600;
     color: #5f6368; text-align: left; padding: 10px 14px; }
td { padding: 10px 14px; font-size: 13px;
     border-top: 1px solid #f1f3f4; vertical-align: top; }
tr:hover td { background: #fafafa; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
         font-size: 11px; font-weight: 600; color: #fff; white-space: nowrap; }
.detail { font-family: "SF Mono", "Fira Code", monospace; font-size: 11px;
          color: #5f6368; word-break: break-all; }
.empty { text-align: center; padding: 48px; color: #5f6368; font-size: 14px; }
.raw-link { float: right; font-size: 12px; color: #1a73e8; text-decoration: none; }
.raw-link:hover { text-decoration: underline; }

/* Focus 5 */
main.wide { max-width: 1480px; }
.f5-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px;
           align-items: start; }
@media (max-width: 1100px) { .f5-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 620px)  { .f5-grid { grid-template-columns: 1fr; } }
.f5-card { background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.12);
           padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.f5-pos { font-size: 11px; font-weight: 700; color: #9aa0a6; }
.f5-name { font-size: 15px; font-weight: 600; color: #1a73e8; text-decoration: none;
           word-break: break-word; }
.f5-name:hover { text-decoration: underline; }
.f5-reason { font-size: 11px; color: #5f6368; }
.f5-sec { border-top: 1px solid #f1f3f4; padding-top: 8px; }
.f5-sec h4 { font-size: 10px; text-transform: uppercase; letter-spacing: .04em;
             color: #9aa0a6; font-weight: 700; margin-bottom: 5px; }
.f5-branch { font-family: "SF Mono", monospace; font-size: 11px; color: #202124; }
.f5-drift { font-size: 11px; color: #5f6368; margin-left: 6px; }
.f5-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
          margin-right: 5px; vertical-align: middle; }
.f5-pr a { color: #1a73e8; text-decoration: none; font-size: 12px; }
.f5-pr a:hover { text-decoration: underline; }
.f5-muted { font-size: 12px; color: #9aa0a6; }
.f5-act { list-style: none; display: flex; flex-direction: column; gap: 5px; }
.f5-act li { font-size: 12px; line-height: 1.35; }
.f5-act .when { color: #9aa0a6; font-size: 10px; }
.f5-meta { font-size: 12px; color: #5f6368; margin-bottom: 16px; }
"""


def _page(title: str, body: str, *, wide: bool = False) -> HTMLResponse:
    main_attr = ' class="wide"' if wide else ""
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title} — rebalance-OS</title>
<style>{_CSS}</style></head>
<body>
<header>
  <h1>rebalance-OS</h1>
  <nav>
    <a href="/">Home</a>&ensp;·&ensp;
    <a href="/focus-5">Focus 5</a>&ensp;·&ensp;
    <a href="/auth-log">Auth Log</a>
  </nav>
</header>
<main{main_attr}>{body}</main>
</body></html>"""
    return HTMLResponse(html_doc)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    body = """
<h2>Local dashboards</h2>
<ul style="margin-top:16px;line-height:2;list-style:none;">
  <li><a href="/focus-5" style="color:#1a73e8;font-size:15px;">
      🎯 Focus 5</a>
      <span style="color:#5f6368;font-size:13px;margin-left:8px;">
      — the 5 repos you're actively working on: working-tree health, newest PR,
      and recent local commits, ranked by uncommitted/unpushed work first</span>
  </li>
  <li><a href="/auth-log" style="color:#1a73e8;font-size:15px;">
      📋 Auth Activity Log</a>
      <span style="color:#5f6368;font-size:13px;margin-left:8px;">
      — per-device auth events across all collectors (calendar, github, gmail):
      flow start/success/failure, token refresh, validation, deauthorization</span>
  </li>
</ul>"""
    return _page("Home", body)


def _rel_time(iso: str | None) -> str:
    """Render an ISO-8601 timestamp as a compact relative age (e.g. '3h ago')."""
    if not iso:
        return ""
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    secs = max(0, int((datetime.now(timezone.utc) - ts).total_seconds()))
    for label, unit in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= unit:
            return f"{secs // unit}{label} ago"
    return "just now"


def _f5_health(card: dict[str, Any]) -> str:
    """Working-tree health: dirty/clean dot + counts + branch + ahead/behind drift."""
    if card["is_dirty"]:
        dot, parts = "#ea4335", []
        if card["modified_count"]:
            parts.append(f"{card['modified_count']} modified")
        if card["untracked_count"]:
            parts.append(f"{card['untracked_count']} untracked")
        state = ", ".join(parts) or "dirty"
    else:
        dot, state = "#34a853", "clean"
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
    vsurl = html.escape(card.get("vscode_url") or "#")
    reason = html.escape(card.get("rank_reason") or "")
    return (
        f"<div class='f5-card'>"
        f"<div><div class='f5-pos'>#{card['position']}</div>"
        f"<a class='f5-name' href='{vsurl}' title='Open in VS Code'>{name}</a>"
        f"<div class='f5-reason'>{reason}</div></div>"
        f"{_f5_health(card)}{_f5_pr(card)}{_f5_activity(card)}"
        f"</div>"
    )


def _focus5_body(data: dict[str, Any]) -> str:
    """Render the Focus 5 page body from a summarize_focus5() dict (pure)."""
    roster = data.get("roster") or []
    if not roster:
        return (
            "<h2>🎯 Focus 5</h2>"
            "<div class='empty'>No active repos found yet. The roster builds from "
            "your local git activity — make a commit or leave uncommitted work in a "
            "repo under your dev folders, then reload. "
            "You can also run <code>rebalance refresh-index</code> after a sync.</div>"
        )
    mode = html.escape(data.get("ranking_mode") or "")
    computed = _rel_time(data.get("computed_at"))
    meta = (
        f"<div class='f5-meta'>Roster computed {computed} · ranked by "
        f"<b>{mode}</b> · {data['summary']['discovered']} repos discovered</div>"
    )
    cards = "".join(_f5_card(c) for c in roster)
    return f"<h2>🎯 Focus 5</h2>{meta}<div class='f5-grid'>{cards}</div>"


@app.get("/focus-5", response_class=HTMLResponse)
def focus5_page() -> HTMLResponse:
    from rebalance.ingest.focus5_scan import summarize_focus5, sync_focus5
    from rebalance.paths import DatabaseNotFoundError, resolve_database_path

    try:
        db = resolve_database_path()
    except DatabaseNotFoundError:
        body = ("<h2>🎯 Focus 5</h2><div class='empty'>No rebalance database found. "
                "Run <code>rebalance refresh-index</code> first.</div>")
        return _page("Focus 5", body, wide=True)

    data = summarize_focus5(db)
    # Lazy bootstrap: first visit has an empty roster, so build it once on load.
    # (The full 24h-TTL recompute + manual refresh button land in Phase 3.)
    if not data["roster"]:
        try:
            sync_focus5(db)
            data = summarize_focus5(db)
        except Exception:  # noqa: BLE001 — a scan failure must not 500 the page
            pass

    return _page("Focus 5", _focus5_body(data), wide=True)


@app.get("/auth-log", response_class=HTMLResponse)
def auth_log_page() -> HTMLResponse:
    import json
    entries = read_log(limit=200)

    raw_link = '<a class="raw-link" href="/auth-log/raw">⬇ raw JSONL</a>'

    if not entries:
        body = f"<h2>Auth Activity Log {raw_link}</h2><div class='empty'>No entries yet. Run an OAuth flow, validate the GitHub token, or run a collector sync to populate this log.</div>"
        return _page("Auth Log", body)

    rows = []
    for e in entries:
        event = e.get("event", "unknown")
        color, label = _EVENT_BADGE.get(event, ("#9aa0a6", event))
        badge = f'<span class="badge" style="background:{color}">{label}</span>'
        source = e.get("source", "")
        s_color, s_label = _SOURCE_BADGE.get(source, ("#9aa0a6", source or "—"))
        source_badge = f'<span class="badge" style="background:{s_color}">{s_label}</span>'
        detail = e.get("detail", {})
        detail_str = "<br>".join(f"<b>{k}</b>: {v}" for k, v in detail.items()) if detail else "—"
        rows.append(
            f"<tr>"
            f"<td>{e.get('ts','')[:19].replace('T',' ')}</td>"
            f"<td>{e.get('device','')}</td>"
            f"<td>{source_badge}</td>"
            f"<td>{badge}</td>"
            f"<td class='detail'>{detail_str}</td>"
            f"</tr>"
        )

    table = (
        f"<table><thead><tr>"
        f"<th>Timestamp (UTC)</th><th>Device</th><th>Source</th><th>Event</th><th>Detail</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )
    body = f"<h2>Auth Activity Log {raw_link}</h2>{table}"
    return _page("Auth Log", body)


@app.get("/auth-log/raw", response_class=PlainTextResponse)
def auth_log_raw() -> PlainTextResponse:
    path = _log_path()
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")
