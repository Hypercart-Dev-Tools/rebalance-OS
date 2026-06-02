"""Minimal FastAPI web server for rebalance-OS local dashboards.

Start with:
    rebalance serve            # default port 8787
    rebalance serve --port 9000

Routes
------
GET /              — index with links to all pages
GET /auth-log      — Google Calendar OAuth activity log (HTML table)
GET /auth-log/raw  — raw JSONL file download
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse

from rebalance.ingest.auth_log import read_log, _log_path

app = FastAPI(title="rebalance-OS", docs_url=None, redoc_url=None)

_EVENT_BADGE = {
    "flow_started":         ("#1a73e8", "▶ flow started"),
    "flow_succeeded":       ("#34a853", "✓ flow succeeded"),
    "flow_failed":          ("#ea4335", "✗ flow failed"),
    "token_missing":        ("#fbbc05", "⚠ token missing"),
    "token_refreshed":      ("#34a853", "↻ token refreshed"),
    "token_refresh_failed": ("#ea4335", "✗ refresh failed"),
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
"""


def _page(title: str, body: str) -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title} — rebalance-OS</title>
<style>{_CSS}</style></head>
<body>
<header>
  <h1>rebalance-OS</h1>
  <nav>
    <a href="/">Home</a>&ensp;·&ensp;
    <a href="/auth-log">Auth Log</a>
  </nav>
</header>
<main>{body}</main>
</body></html>"""
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    body = """
<h2>Local dashboards</h2>
<ul style="margin-top:16px;line-height:2;list-style:none;">
  <li><a href="/auth-log" style="color:#1a73e8;font-size:15px;">
      📋 Google Calendar OAuth Activity Log</a>
      <span style="color:#5f6368;font-size:13px;margin-left:8px;">
      — per-device auth events (flow start/success/failure, token refresh)</span>
  </li>
</ul>"""
    return _page("Home", body)


@app.get("/auth-log", response_class=HTMLResponse)
def auth_log_page() -> HTMLResponse:
    import json
    entries = read_log(limit=200)

    raw_link = '<a class="raw-link" href="/auth-log/raw">⬇ raw JSONL</a>'

    if not entries:
        body = f"<h2>OAuth Activity Log {raw_link}</h2><div class='empty'>No entries yet. Run the OAuth flow or a calendar sync to populate this log.</div>"
        return _page("Auth Log", body)

    rows = []
    for e in entries:
        event = e.get("event", "unknown")
        color, label = _EVENT_BADGE.get(event, ("#9aa0a6", event))
        badge = f'<span class="badge" style="background:{color}">{label}</span>'
        detail = e.get("detail", {})
        detail_str = "<br>".join(f"<b>{k}</b>: {v}" for k, v in detail.items()) if detail else "—"
        rows.append(
            f"<tr>"
            f"<td>{e.get('ts','')[:19].replace('T',' ')}</td>"
            f"<td>{e.get('device','')}</td>"
            f"<td>{badge}</td>"
            f"<td class='detail'>{detail_str}</td>"
            f"</tr>"
        )

    table = (
        f"<table><thead><tr>"
        f"<th>Timestamp (UTC)</th><th>Device</th><th>Event</th><th>Detail</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )
    body = f"<h2>OAuth Activity Log {raw_link}</h2>{table}"
    return _page("Auth Log", body)


@app.get("/auth-log/raw", response_class=PlainTextResponse)
def auth_log_raw() -> PlainTextResponse:
    path = _log_path()
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")
