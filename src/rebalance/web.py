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
from fastapi.responses import (
    HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse,
)
from pydantic import BaseModel

from rebalance.ingest.auth_log import read_log, _log_path
from rebalance.web_components import badge_html, button_link, render_shell

# How long a persisted Focus 5 roster stays authoritative before a visit lazily
# recomputes it. Membership is snapshot-stable for this window; working-tree
# health is always re-probed live on load regardless.
FOCUS5_ROSTER_TTL_SECONDS = 24 * 3600

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
"""


def _page(title: str, body: str, *, active: str, wide: bool = False) -> HTMLResponse:
    """Wrap a page body in the shared sidebar shell (tokens + chrome + buttons).

    The nav/sidebar comes from render_shell (minimal, I/O-free sidebar); ``active``
    marks the current nav item (``'today' | 'focus5' | 'authlog'``).
    """
    return HTMLResponse(
        render_shell(title, body, active=active, wide=wide, page_css=_CSS)
    )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    body = """
<h2>Local dashboards</h2>
<ul style="margin-top:16px;line-height:2;list-style:none;">
  <li><a href="/focus-5" style="color:var(--accent);font-size:15px;">
      🎯 Focus 5</a>
      <span style="color:var(--fg-muted);font-size:13px;margin-left:8px;">
      — the 5 repos you're actively working on: working-tree health, newest PR,
      and recent local commits, ranked by uncommitted/unpushed work first</span>
  </li>
  <li><a href="/auth-log" style="color:var(--accent);font-size:15px;">
      📋 System Log</a>
      <span style="color:var(--fg-muted);font-size:13px;margin-left:8px;">
      — unified event stream: auth events (calendar, github, gmail) and background
      job starts, completions, and failures — filterable by type</span>
  </li>
</ul>"""
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
    shown, items = warns[:8], []
    for w in shown:
        bits = []
        if w.get("modified_count"):
            bits.append(f"{w['modified_count']} modified")
        if w.get("untracked_count"):
            bits.append(f"{w['untracked_count']} untracked")
        if w.get("ahead"):
            bits.append(f"{w['ahead']} unpushed")
        items.append(f"<b>{html.escape(w['repo_name'])}</b> ({', '.join(bits) or 'attention'})")
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
        f"<div class='f5-reason'>{reason}</div></div>"
        f"{_f5_health(card)}{_f5_pr(card)}{_f5_activity(card)}"
        f"</div>"
    )


def _focus5_body(data: dict[str, Any]) -> str:
    """Render the Focus 5 page body from a summarize_focus5() dict (pure)."""
    refresh_btn = "<a class='f5-refresh' href='/focus-5?refresh=1' title='Re-rank now'>↻ Refresh</a>"
    roster = data.get("roster") or []
    if not roster:
        return (
            f"<h2>🎯 Focus 5 {refresh_btn}</h2>"
            "<div class='empty'>No active repos found yet. The roster builds from "
            "your local git activity — make a commit or leave uncommitted work in a "
            "repo under your dev folders, then reload.</div>"
        )
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
    return (
        f"<h2>🎯 Focus 5 {refresh_btn}</h2>{meta}{strip}"
        f"<div class='f5-grid'>{cards}</div>{_FOCUS5_HIDE_ASSETS}"
    )


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
def focus5_page(refresh: bool = False):
    from rebalance.ingest.focus5_scan import (
        get_roster_meta, summarize_focus5, sync_focus5,
    )
    from rebalance.paths import DatabaseNotFoundError, resolve_database_path

    try:
        db = resolve_database_path()
    except DatabaseNotFoundError:
        body = ("<h2>🎯 Focus 5</h2><div class='empty'>No rebalance database found. "
                "Run <code>rebalance refresh-index</code> first.</div>")
        return _page("Focus 5", body, active="focus5", wide=True)

    # Recompute the roster when forced, never built, or past its 24h TTL. The
    # meta check is a cheap DB read so we don't pay the live-probe render twice.
    meta = get_roster_meta(db)
    if refresh or not meta["roster_size"] or _roster_stale(meta["computed_at"]):
        try:
            sync_focus5(db)
        except Exception:  # noqa: BLE001 — a scan failure must not 500 the page
            pass
        if refresh:
            # Post/redirect/get: drop ?refresh so a browser reload doesn't re-scan.
            return RedirectResponse("/focus-5", status_code=303)

    data = summarize_focus5(db)  # roster from snapshot; health re-probed live
    return _page("Focus 5", _focus5_body(data), active="focus5", wide=True)


class _Focus5HideRequest(BaseModel):
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
def focus5_hide(req: _Focus5HideRequest) -> JSONResponse:
    return JSONResponse(focus5_set_hidden(req.repo, hidden=True))


@app.post("/api/focus5/unhide")
def focus5_unhide(req: _Focus5HideRequest) -> JSONResponse:
    return JSONResponse(focus5_set_hidden(req.repo, hidden=False))


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
        event = e.get("event", "unknown")
        variant, label = _EVENT_BADGE.get(event, ("neutral", event))
        badge = badge_html(variant, label)
        source = e.get("source", "")
        s_variant, s_label = _SOURCE_BADGE.get(source, ("neutral", source or "—"))
        source_badge = badge_html(s_variant, s_label)
        detail = e.get("detail", {})
        detail_str = "<br>".join(f"<b>{k}</b>: {v}" for k, v in detail.items()) if detail else "—"
        rows.append(
            f"<tr data-severity='{variant}' data-source='{source}'>"
            f"<td>{e.get('ts','')[:19].replace('T',' ')}</td>"
            f"<td>{e.get('device','')}</td>"
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
