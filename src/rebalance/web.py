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
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import (
    HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse,
)
from pydantic import BaseModel

from rebalance.ingest.auth_log import read_log, _log_path
from rebalance.ingest.sleuth_grouping import grouped_reminders_from_db
from rebalance.paths import resolve_db
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

app = FastAPI(title="rebalance-OS", docs_url=None, redoc_url=None)

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
}

_SOURCE_BADGE = {
    "calendar": ("info",    "calendar"),
    "github":   ("neutral", "github"),
    "gmail":    ("neutral", "gmail"),
    "sleuth":   ("neutral", "sleuth"),
    "launchd":  ("neutral", "launchd"),
}

# Page-local CSS for the FastAPI surfaces (Focus 5 / Auth Log / Home). The base
# resets + the .app/.sidebar shell + global h1/h2/h3 now come from
# RB_CHROME_CSS (injected by render_shell), so only the BODY-specific rules live
# here. All colours are design tokens (var(--…)) so the palette is single-sourced;
# none of these rules touch the dashboard (which never includes _CSS).
_CSS = """
h2 { font-size: 15px; font-weight: 600; color: var(--fg-muted); margin-bottom: 16px; }
table { width: 100%; border-collapse: collapse; background: var(--panel);
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,.12); }
th { background: var(--border); font-size: 12px; font-weight: 600;
     color: var(--fg-muted); text-align: left; padding: 10px 14px; }
td { padding: 10px 14px; font-size: 13px;
     border-top: 1px solid var(--border); vertical-align: top; }
tr:hover td { background: rgba(0,0,0,.03); }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
         font-size: 11px; font-weight: 600; color: #fff; white-space: nowrap; }
.badge-ok      { background: var(--ok);     color: #fff; }
.badge-warn    { background: var(--warn);   color: #fff; }
.badge-danger  { background: var(--danger); color: #fff; }
.badge-info    { background: var(--info);   color: #fff; }
.badge-neutral { background: var(--fg-dim); color: #fff; }
.detail { font-family: "SF Mono", "Fira Code", monospace; font-size: 11px;
          color: var(--fg-muted); word-break: break-all; }
.empty { text-align: center; padding: 48px; color: var(--fg-muted); font-size: 14px; }
.raw-link { float: right; font-size: 12px; color: var(--accent); text-decoration: none; }
.raw-link:hover { text-decoration: underline; }

/* Sleuth reminder groups (home page) */
.sr-search-bar { display:flex; align-items:center; gap:12px; margin-bottom:16px; }
.sr-input { flex:1; max-width:340px; padding:6px 10px; border:1px solid var(--border);
            border-radius:6px; background:var(--panel); color:var(--fg); font-size:13px; }
.sr-count-label { font-size:12px; color:var(--fg-muted); }
.sr-groups { display:flex; flex-direction:column; gap:12px; }
.sr-group  { background:var(--panel); border-radius:8px;
             box-shadow:0 1px 3px rgba(0,0,0,.12); overflow:hidden; }
.sr-group-header { display:flex; align-items:center; gap:8px; padding:10px 14px;
                   border-bottom:1px solid var(--border); font-size:13px; font-weight:600; }
.sr-group-name  { flex:1; }
.sr-group-count { font-size:11px; font-weight:400; color:var(--fg-muted); }
.sr-tasks { list-style:none; padding:0; margin:0; }
.sr-task  { padding:8px 14px; font-size:13px; border-top:1px solid var(--border); }
.sr-task:first-child { border-top:none; }
.sr-task:hover { background:rgba(0,0,0,.03); }

/* Focus 5 — sits inside the .app 280px-sidebar grid, so it has ~280px less width
   than the old centred 1480px <main>. Breakpoints retuned for that frame. */
.f5-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px;
           align-items: start; }
@media (max-width: 1400px) { .f5-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 1000px) { .f5-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 680px)  { .f5-grid { grid-template-columns: 1fr; } }
.f5-card { background: var(--panel); border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.12);
           padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.f5-pos { font-size: 11px; font-weight: 700; color: var(--fg-dim); }
.f5-name { font-size: 15px; font-weight: 600; color: var(--accent); text-decoration: none;
           word-break: break-word; }
.f5-name:hover { text-decoration: underline; }
.f5-reason { font-size: 11px; color: var(--fg-muted); }
.f5-sec { border-top: 1px solid var(--border); padding-top: 8px; }
.f5-sec h4 { font-size: 10px; text-transform: uppercase; letter-spacing: .04em;
             color: var(--fg-dim); font-weight: 700; margin-bottom: 5px; }
.f5-branch { font-family: "SF Mono", monospace; font-size: 11px; color: var(--fg); }
.f5-drift { font-size: 11px; color: var(--fg-muted); margin-left: 6px; }
.f5-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
          margin-right: 5px; vertical-align: middle; }
.f5-pr a { color: var(--accent); text-decoration: none; font-size: 12px; }
.f5-pr a:hover { text-decoration: underline; }
.f5-muted { font-size: 12px; color: var(--fg-dim); }
.f5-act { list-style: none; display: flex; flex-direction: column; gap: 5px; }
.f5-act li { font-size: 12px; line-height: 1.35; }
.f5-act .when { color: var(--fg-dim); font-size: 10px; }
.f5-meta { font-size: 12px; color: var(--fg-muted); margin-bottom: 16px; }
.f5-live { color: var(--ok); }
.f5-stale { color: var(--warn); font-weight: 700; }
.f5-refresh { font-size: 13px; font-weight: 600; color: var(--accent); text-decoration: none;
              margin-left: 10px; }
.f5-refresh:hover { text-decoration: underline; }
.f5-warn { background: rgba(166,95,0,.08); border: 1px solid rgba(166,95,0,.28); color: var(--warn);
           border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; font-size: 13px;
           line-height: 1.5; }
.f5-warn b { color: var(--warn); }
/* GH-81 Phase 2: a fallback-basis badge on a rostered card (reflog disabled). */
.f5-basis { color: var(--fg-muted); font-weight: 400; font-size: 12px; }
/* Focus 5 / Dirty Five view toggle — a small segmented control. */
.f5-views { display: inline-flex; gap: 4px; padding: 3px; margin-bottom: 16px;
            background: var(--panel); border: 1px solid var(--border); border-radius: 8px; }
.f5-view { font-size: 13px; font-weight: 600; color: var(--fg-muted); text-decoration: none;
           padding: 4px 12px; border-radius: 6px; }
.f5-view:hover { color: var(--fg); }
.f5-view.active { background: rgba(31,111,235,.12); color: var(--accent); }

/* What's Next — the single ranked "work on next" list. Reuses the shared
   .badge/.empty rules; only the list/row chrome is page-local. */
.wn-refresh { font-size: 13px; font-weight: 600; color: var(--accent); text-decoration: none;
              margin-left: 10px; }
.wn-refresh:hover { text-decoration: underline; }
.wn-meta { font-size: 12px; color: var(--fg-muted); margin-bottom: 16px; }
.wn-blended { color: var(--ok); }
.wn-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.wn-item { background: var(--panel); border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.12);
           padding: 12px 14px; display: flex; gap: 12px; align-items: flex-start; }
.wn-rank { font-size: 13px; font-weight: 700; color: var(--fg-dim); min-width: 28px;
           font-variant-numeric: tabular-nums; }
.wn-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.wn-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.wn-title { font-size: 14px; font-weight: 600; color: var(--fg); word-break: break-word; }
.wn-why { font-size: 12px; color: var(--fg-muted); line-height: 1.4; }
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


def _page(title: str, body: str, *, active: str, wide: bool = False) -> HTMLResponse:
    """Wrap a page body in the shared sidebar shell (tokens + chrome + buttons).

    The nav/sidebar comes from render_shell (minimal, I/O-free sidebar); ``active``
    marks the current nav item (``'today' | 'focus5' | 'authlog'``).
    """
    return HTMLResponse(
        render_shell(title, body, active=active, wide=wide, page_css=_CSS)
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
        f"<span style='font-size:12px;font-weight:400;color:var(--fg-muted);margin-left:10px;'>"
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


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    sleuth_section = _render_sleuth_groups()
    body = (
        """
<h2>Local dashboards</h2>
<ul style="margin-top:16px;line-height:2;list-style:none;">
  <li><a href="/focus-5" style="color:var(--accent);font-size:15px;">
      Focus 5</a>
      <span style="color:var(--fg-muted);font-size:13px;margin-left:8px;">
      — the 5 repos you're actively working on, ranked by your most recent
      commits: working-tree health, newest PR, and recent local commits
      (with a Dirty Five view for uncommitted/unpushed work)</span>
  </li>
  <li><a href="/auth-log" style="color:var(--accent);font-size:15px;">
      System Log</a>
      <span style="color:var(--fg-muted);font-size:13px;margin-left:8px;">
      — unified event stream: auth events (calendar, github, gmail) and background
      job starts, completions, and failures — filterable by type</span>
  </li>
</ul>"""
        + sleuth_section
    )
    return _page("Home", body, active="today")


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
        bits = []
        if w.get("modified_count"):
            bits.append(f"{w['modified_count']} modified")
        if w.get("untracked_count"):
            bits.append(f"{w['untracked_count']} untracked")
        if w.get("ahead"):
            bits.append(f"{w['ahead']} unpushed")
        item = f"<b>{html.escape(w['repo_name'])}</b> ({', '.join(bits) or 'attention'})"
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
    # matches the dashboard home) next to the ✕ hide control.
    open_btn = button_link("Open", vs_href, title="Open repo in VS Code")
    hide_btn = (
        f"<button class='f5-hide' data-f5-hide=\"{identity}\" "
        f"title='Hide from Focus 5' aria-label='Hide {name} from Focus 5'>✕</button>"
    )
    actions = f"<div class='f5-actions'>{open_btn}{hide_btn}</div>"
    return (
        f"<div class='f5-card'>"
        f"{actions}"
        f"<div><div class='f5-pos'>#{card['position']}</div>"
        f"<a class='f5-name' href='{vsurl}' title='Open in VS Code'>{name}</a>"
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
    cards = "".join(_f5_card(c) for c in roster)
    return f"{head}{meta}{strip}<div class='f5-grid'>{cards}</div>{_FOCUS5_HIDE_ASSETS}"


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


def _roster_stale(computed_at: str | None) -> bool:
    """True if the roster snapshot is missing or older than the TTL."""
    if not computed_at:
        return True
    try:
        ts = datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
    except ValueError:
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
            "roster": [], "off_roster_warnings": [],
            "computed_at": None, "ranking_mode": None,
            "summary": {"discovered": 0, "roster_size": 0,
                        "off_roster_attention": 0, "rank_cutoff_ts": None},
        })

    data = summarize_focus5(db, mode="dirty_first" if view == "dirty" else None)
    logger.info("focus5.json: view=%s roster=%d", view, data["summary"]["roster_size"])
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
    ".syslog-toggle{padding:.3rem .75rem;border:1px solid #d0d7de;border-radius:2rem;"
    "background:#f6f8fa;cursor:pointer;font:inherit;font-size:.85rem;color:#24292f}"
    ".syslog-toggle.active{background:#0969da;border-color:#0969da;color:#fff;font-weight:600}"
    ".syslog-input{flex:1;min-width:14rem;padding:.4rem .6rem;font:inherit;"
    "border:1px solid #d0d7de;border-radius:6px}"
    ".syslog-count{color:#57606a;font-size:.85rem;white-space:nowrap}"
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
        "<span style='display:inline-flex;align-items:center;gap:5px;margin-right:14px;font-size:12px;'>"
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
  <span style="font-size:13px;color:var(--fg-muted);">
    {total} active reminders · {len(groups)} groups
  </span>
  <span style="margin-left:auto;">{legend_items}</span>
</div>
<div id="cy" style="width:100%;height:calc(100vh - 160px);min-height:500px;
     background:var(--panel);border-radius:8px;
     box-shadow:0 1px 3px rgba(0,0,0,.12);"></div>
<div id="cy-tooltip" style="display:none;position:fixed;background:var(--panel);
     border:1px solid var(--border);border-radius:6px;padding:8px 12px;
     font-size:12px;max-width:320px;box-shadow:0 4px 12px rgba(0,0,0,.15);
     pointer-events:none;z-index:100;line-height:1.5;"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.33.1/cytoscape.min.js"
        integrity="sha512-kHAY8XzRfLVMcLuowdk91552RD+Nb2/1uHamfHMdLejNqlZnbEJLl1wYnsNnqIFCEZ++WaOcOlfokC6p9JWrLw=="
        crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script>
(function() {{
  var elements = {elements_json};

  var kindColor = {{
    client:  {{ bg: '#2f7437', border: '#1e4d25' }},
    github:  {{ bg: '#1d6fa8', border: '#134d75' }},
    channel: {{ bg: '#6f3fa8', border: '#4d2a75' }},
    other:   {{ bg: '#8a857c', border: '#5b5750' }},
  }};

  var cy = cytoscape({{
    container: document.getElementById('cy'),
    elements: elements,
    style: [
      // compound group parent
      {{
        selector: 'node[kind]',
        style: {{
          'background-color': 'data(bg)',
          'border-color': 'data(border)',
          'border-width': 2,
          'label': 'data(label)',
          'font-size': 13,
          'font-weight': 600,
          'color': '#fff',
          'text-valign': 'top',
          'text-halign': 'center',
          'text-margin-y': -6,
          'padding': 18,
          'shape': 'round-rectangle',
          'text-background-color': 'data(bg)',
          'text-background-opacity': 0.85,
          'text-background-padding': '3px',
          'text-background-shape': 'round-rectangle',
        }},
      }},
      // reminder child nodes
      {{
        selector: 'node[reminder_id]',
        style: {{
          'background-color': '#ffffff',
          'border-color': '#c8c0b4',
          'border-width': 1.5,
          'label': 'data(label)',
          'font-size': 10,
          'color': '#1d2024',
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
          'line-color': '#1d6fa8',
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
          'border-color': '#1f6feb',
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
      (d.channel ? '<span style="color:#5b5750;">#' + escHtml(d.channel) + '</span>' : '') +
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
