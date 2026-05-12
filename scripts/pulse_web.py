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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Reuse the TUI's data layer so both views move in lockstep.
from dashboard import (  # type: ignore  # noqa: E402
    DB_PATH,
    TZ,
    fetch_calendar_upcoming,
    fetch_recent_github,
    fetch_sleuth_due,
    fetch_vault_recent,
    fetch_watched_summary,
    _ago,
    _parse_iso,
)
from rebalance.ingest.index_ops import get_index_status  # noqa: E402
from rebalance.ingest.slack_users import compact_sleuth_reminder  # noqa: E402

CONFIG_PATH = PROJECT_ROOT / "temp" / "rbos.config"
DEFAULT_OUT = PROJECT_ROOT / "web" / "pulse.html"


# ---------------------------------------------------------------------------
# Goals parser
# ---------------------------------------------------------------------------

CHECKBOX_RE = re.compile(r"^\s*-\s*\[(?P<mark>[ xX])\]\s*(?P<title>.*)$")


def parse_goals(path: Path, limit: int = 3) -> list[dict[str, Any]]:
    """Parse a Things-style checklist into [{done, title, description}, ...].

    Format:
        - [ ] Title line
        Optional description spanning until blank line or next checkbox.
    """
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        m = CHECKBOX_RE.match(raw)
        if m:
            if current is not None:
                items.append(current)
            is_done = m.group("mark").lower() == "x"
            if is_done:
                current = None
            else:
                current = {
                    "done": False,
                    "title": m.group("title").strip(),
                    "description": "",
                }
            continue
        if current is None:
            continue
        current["description"] = (current["description"] + " " + raw.strip()).strip()
    if current is not None:
        items.append(current)
    return items[:limit]


def load_vault_path() -> Path | None:
    if not CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    vp = data.get("vault_path")
    return Path(vp).expanduser() if vp else None


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

KIND_GLYPH = {
    "commit":  ("●", "ok"),
    "item":    ("◆", "info"),
    "comment": ("○", "muted"),
}

ITEM_SUB_GLYPH = {
    "issue":        ("✦", "warn"),
    "pull_request": ("⇡", "info"),
}


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _short_repo(full: str | None) -> str:
    if not full:
        return ""
    return full.split("/", 1)[1] if "/" in full else full


def _truncate(text: str, n: int) -> str:
    text = (text or "").splitlines()[0] if text else ""
    return text if len(text) <= n else text[: n - 1] + "…"


def _format_dt(value: str | datetime | None, *, tz: ZoneInfo) -> str:
    dt = _parse_iso(value) if isinstance(value, str) else value
    if dt is None:
        return "—"
    return dt.astimezone(tz).strftime("%a %b %d · %H:%M %Z")


def _format_dt_short(value: str | datetime | None, *, tz: ZoneInfo) -> str:
    dt = _parse_iso(value) if isinstance(value, str) else value
    if dt is None:
        return ""
    return dt.astimezone(tz).strftime("%a %-I:%M %p").lower().replace("am", "am").replace("pm", "pm")


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


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def render_hero(
    goals: list[dict[str, Any]],
    pulled_from: str,
    now: datetime,
    obsidian_url: str | None,
) -> str:
    done = sum(1 for g in goals if g["done"])
    in_progress = len(goals) - done
    pct = int((done / len(goals)) * 100) if goals else 0
    rows = []
    for g in goals:
        cls = "done" if g["done"] else ""
        check = "checked" if g["done"] else ""
        rows.append(f"""
        <li class="goal {cls}">
          <span class="check {check}"></span>
          <div class="goal-body">
            <div class="goal-title">{_esc(g['title'])}</div>
            <div class="goal-desc">{_esc(g['description'])}</div>
          </div>
        </li>
        """)
    if not rows:
        rows.append('<li class="goal empty"><div class="goal-body"><div class="goal-title">No goals found</div><div class="goal-desc">Add checklist items to your Goals file.</div></div></li>')
    date_str = now.strftime("%A, %B %-d")
    open_link = (
        f'<a class="hero-open" href="{_esc(obsidian_url)}">Open in Obsidian ↗</a>'
        if obsidian_url else ""
    )
    return f"""
    <section class="hero card">
      <header class="hero-head">
        <div>
          <h1>Today's Goals</h1>
          <div class="subtle">{date_str} · pulled from <code>{_esc(pulled_from)}</code> {open_link}</div>
        </div>
        <div class="hero-stats">
          <div><b>{done}</b> done</div>
          <div><b>{in_progress}</b> in progress</div>
          <div class="bar"><span style="width:{pct}%"></span></div>
          <div class="pct">{pct}%</div>
        </div>
      </header>
      <ul class="goals">{''.join(rows)}</ul>
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
    for r in rows:
        kind = r.get("kind") or "item"
        sub = r.get("sub") or ""
        glyph, color = KIND_GLYPH.get(kind, ("·", "muted"))
        if kind == "item" and sub in ITEM_SUB_GLYPH:
            glyph, color = ITEM_SUB_GLYPH[sub]
        repo = _short_repo(r.get("repo_full_name"))
        num = r.get("num")
        detail = _truncate(r.get("detail") or "", 80)
        who = r.get("who") or ""
        ago = _ago(r.get("ts"), now=now)
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
                f'<a class="label {color}" href="{_esc(html_url)}" '
                f'target="_blank" rel="noopener noreferrer">{_esc(label)}</a>'
            )
        else:
            label_html = f'<span class="label {color}">{_esc(label)}</span>'
        items.append(f"""
        <li class="activity-row">
          <span class="ts">{_esc(ago)}</span>
          <span class="glyph {color}">{glyph}</span>
          {label_html}
          <span class="repo">{_esc(repo)}</span>
          <span class="who">{('@' + _esc(who)) if who else ''}</span>
          <div class="detail">{_esc(detail)}</div>
        </li>
        """)
    body = "".join(items) if items else '<li class="empty">No recent activity.</li>'
    foot = ""
    if last_vault:
        title = _esc(last_vault.get("title") or last_vault.get("rel_path") or "vault note")
        ago = _ago(last_vault.get("last_modified"), now=now)
        foot = (
            f'<footer class="card-foot subtle">'
            f'Last vault edit · <span class="strong">{title}</span> · {_esc(ago)}'
            f'{f" · {vault_recent_count} recent" if vault_recent_count else ""}'
            f'</footer>'
        )
    return f"""
    <section class="card activity">
      <header class="card-head"><h2>Recent activity</h2></header>
      <ol class="activity-list">{body}</ol>
      {foot}
    </section>
    """


def render_watched(summary: dict[str, Any], now: datetime) -> str:
    last = _ago(summary.get("last_synced"), now=now) if summary.get("last_synced") else "—"
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
      <footer class="card-foot subtle">Last sync activity · {_esc(last)}</footer>
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
        ("Semantic docs",    semantic.get("total_documents"),                              semantic.get("last_embedded_at"),                                  "ok"),
    ]
    items = []
    for label, count, last, tone in rows:
        ago = _ago(last, now=now) if last else "—"
        items.append(f"""
        <li>
          <span class="row-label">{_esc(label)}</span>
          <span class="row-value {tone}">{_esc(count if count is not None else '—')}</span>
          <span class="row-meta subtle">{_esc(ago)}</span>
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


def render_sidebar(
    *,
    in_progress: int,
    cal_rows: list[dict[str, Any]],
    sleuth_rows: list[dict[str, Any]],
    streams: dict[str, int],
    drift_total: int,
    semantic_total: int,
    tz: ZoneInfo,
    now: datetime,
) -> str:
    cal_items = []
    for ev in cal_rows:
        when = _format_dt_short(ev.get("start_time"), tz=tz)
        loc = _esc(ev.get("location") or "")
        title = _esc(ev.get("summary") or "event")
        cal_items.append(f"""
          <li class="side-row">
            <div class="side-row-title">{title}</div>
            <div class="side-row-meta">{_esc(when)}{(" · " + loc) if loc else ""}</div>
          </li>
        """)
    if not cal_items:
        cal_items.append('<li class="side-row empty"><div class="side-row-meta">No upcoming events.</div></li>')

    sleuth_items = []
    for s in sleuth_rows:
        msg = compact_sleuth_reminder(s.get("reminder_message_text") or "")
        msg = _truncate(msg, 90)
        when = _format_dt_short(s.get("should_post_on"), tz=tz) if s.get("should_post_on") else ""
        role = "from me" if s.get("sleuth_role") == "assigned_by_me" else "for me"
        meta_bits = [b for b in [when, role] if b]
        sleuth_items.append(f"""
          <li class="side-row">
            <div class="side-row-title">{_esc(msg)}</div>
            <div class="side-row-meta">{_esc(' · '.join(meta_bits))}</div>
          </li>
        """)
    if not sleuth_items:
        sleuth_items.append('<li class="side-row empty"><div class="side-row-meta">Inbox clear.</div></li>')

    return f"""
    <aside class="sidebar">
      <div class="brand">
        <div class="dot"></div>
        <div>
          <div class="crumb">rebalanceOS Pulse <span class="sep">›</span> Today</div>
        </div>
      </div>
      <nav>
        <ul class="nav-list">
          <li class="active"><span>Today</span><span class="badge">{in_progress}</span></li>
        </ul>

        <div class="nav-section-label">Calendar</div>
        <ul class="side-list">{''.join(cal_items)}</ul>

        <div class="nav-section-label">Reminders</div>
        <ul class="side-list">{''.join(sleuth_items)}</ul>

        <div class="nav-section-label">Streams</div>
        <ul class="streams">
          <li><span class="kbd">G</span><span>GitHub</span><span class="badge">{streams.get('github', 0)}</span></li>
          <li><span class="kbd">V</span><span>Vault</span><span class="badge">{streams.get('vault', 0)}</span></li>
          <li><span class="kbd">C</span><span>Calendar</span><span class="badge">{streams.get('calendar', 0)}</span></li>
          <li><span class="kbd">S</span><span>Sleuth</span><span class="badge">{streams.get('sleuth', 0)}</span></li>
        </ul>
      </nav>
      <footer class="sidebar-foot subtle">Drift {drift_total} · {semantic_total:,} docs</footer>
    </aside>
    """


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------

CSS = """
:root {
  --bg: #f3efe7;
  --panel: #ffffff;
  --border: #e3ddd0;
  --fg: #1d2024;
  --fg-muted: #5b5750;
  --fg-dim: #8a857c;
  --accent: #1f6feb;
  --ok: #2f7437;
  --warn: #a65f00;
  --danger: #c0392b;
  --info: #1d6fa8;
  --shadow: 0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(0,0,0,.04);
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font: 13px/1.45 -apple-system, "SF Pro Text", "Segoe UI", system-ui, sans-serif;
  color: var(--fg);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
}
code { font-family: "SF Mono", ui-monospace, Menlo, monospace; font-size: 12px; color: var(--fg-muted); }
.subtle { color: var(--fg-dim); font-size: 12px; }
h1, h2, h3 { margin: 0; font-weight: 600; letter-spacing: -.01em; }
h1 { font-size: 22px; }
h2 { font-size: 14px; color: var(--fg); }

.app { display: grid; grid-template-columns: 280px 1fr; min-height: 100vh; }

/* Sidebar */
.sidebar {
  border-right: 1px solid var(--border);
  padding: 20px 14px;
  display: flex; flex-direction: column;
  background: linear-gradient(180deg, #f8f4ec 0%, #f3efe7 100%);
}
.brand { display: flex; align-items: center; gap: 8px; padding: 0 6px 22px; }
.brand .dot { width: 22px; height: 22px; background: var(--accent); border-radius: 5px; }
.crumb { font-weight: 600; }
.crumb .sep { color: var(--fg-dim); margin: 0 4px; font-weight: 400; }
.nav-section-label { font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--fg-dim); padding: 18px 8px 6px; }
.nav-list { list-style: none; margin: 0; padding: 0; }
.nav-list li { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; color: var(--fg); cursor: default; }
.nav-list li.active { background: rgba(31,111,235,.10); color: var(--fg); font-weight: 500; }
.nav-list .badge { margin-left: auto; color: var(--fg-dim); font-variant-numeric: tabular-nums; font-size: 12px; }
.nav-list .kbd { display: inline-block; min-width: 16px; padding: 0 5px; font-size: 11px; color: var(--fg-dim); border: 1px solid var(--border); border-radius: 4px; background: #fff; text-align: center; }
.sidebar-foot { margin-top: auto; padding: 8px; font-variant-numeric: tabular-nums; }

/* Sidebar lists (calendar + reminders) */
.side-list { list-style: none; margin: 0; padding: 0; }
.side-row { padding: 7px 8px; border-radius: 6px; }
.side-row + .side-row { margin-top: 1px; }
.side-row:hover { background: rgba(0,0,0,.03); }
.side-row-title { font-size: 12.5px; line-height: 1.35; color: var(--fg); font-weight: 500; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.side-row-meta { font-size: 11.5px; color: var(--fg-dim); margin-top: 2px; font-variant-numeric: tabular-nums; }
.side-row.empty .side-row-meta { font-style: italic; }

/* Streams: compact 4-row list */
.streams { list-style: none; margin: 0; padding: 0; }
.streams li { display: flex; align-items: center; gap: 8px; padding: 5px 8px; border-radius: 6px; }
.streams .badge { margin-left: auto; color: var(--fg-dim); font-variant-numeric: tabular-nums; font-size: 12px; }
.streams .kbd { display: inline-block; min-width: 16px; padding: 0 5px; font-size: 11px; color: var(--fg-dim); border: 1px solid var(--border); border-radius: 4px; background: #fff; text-align: center; }

/* Hero "Open in Obsidian" link */
.hero-open { color: var(--accent); text-decoration: none; margin-left: 8px; font-size: 12px; }
.hero-open:hover { text-decoration: underline; }
.card-foot .strong { color: var(--fg); font-weight: 500; }

/* Main */
.main { padding: 22px 28px; display: flex; flex-direction: column; gap: 18px; min-width: 0; }
.topbar { display: flex; align-items: center; justify-content: space-between; }
.topbar .crumb { color: var(--fg-muted); font-weight: 500; }
.synced { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border: 1px solid var(--border); border-radius: 999px; background: #fff; font-size: 12px; color: var(--fg-muted); }
.synced .ok-dot { width: 8px; height: 8px; background: var(--ok); border-radius: 50%; }
.refresh-btn { font: inherit; padding: 6px 14px; border: 0; border-radius: 8px; background: var(--accent); color: #fff; cursor: pointer; font-weight: 500; }

/* Card */
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow); overflow: hidden; }
.card-head { display: flex; align-items: baseline; justify-content: space-between; padding: 14px 18px 10px; }
.card-foot { padding: 10px 18px 14px; border-top: 1px solid var(--border); }

/* Hero */
.hero { padding: 22px 24px; }
.hero-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.hero-stats { display: flex; align-items: center; gap: 14px; color: var(--fg-muted); font-size: 13px; }
.hero-stats b { color: var(--fg); font-weight: 600; }
.hero-stats .bar { width: 80px; height: 6px; background: var(--border); border-radius: 999px; overflow: hidden; }
.hero-stats .bar span { display: block; height: 100%; background: var(--accent); }
.hero-stats .pct { font-variant-numeric: tabular-nums; min-width: 32px; text-align: right; }

.goals { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 2px; }
.goal { display: flex; align-items: flex-start; gap: 14px; padding: 12px 6px; border-top: 1px solid var(--border); }
.goal:first-child { border-top: 0; }
.goal .check { width: 18px; height: 18px; border-radius: 5px; border: 1.5px solid #c8c2b3; margin-top: 2px; flex-shrink: 0; background: #fff; }
.goal .check.checked { background: var(--accent); border-color: var(--accent); position: relative; }
.goal .check.checked::after { content: ""; position: absolute; left: 4px; top: 1px; width: 5px; height: 9px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg); }
.goal-title { font-weight: 600; color: var(--fg); }
.goal-desc { color: var(--fg-muted); font-size: 12.5px; margin-top: 2px; }
.goal.done .goal-title { text-decoration: line-through; color: var(--fg-dim); }
.goal.done .goal-desc { color: var(--fg-dim); }

/* Two-column body */
.grid { display: grid; grid-template-columns: minmax(0,2fr) minmax(0,1fr); gap: 16px; }
.grid .col { display: flex; flex-direction: column; gap: 16px; min-width: 0; }

/* Activity */
.activity-list { list-style: none; padding: 0 4px 14px; margin: 0; }
.activity-row { display: grid; grid-template-columns: 56px 18px auto auto 1fr; column-gap: 8px; row-gap: 2px; padding: 10px 14px; border-top: 1px solid var(--border); align-items: baseline; }
.activity-row:first-child { border-top: 0; }
.activity-row .ts { color: var(--fg-dim); font-variant-numeric: tabular-nums; font-size: 12px; }
.activity-row .glyph { font-size: 13px; }
.activity-row .label { font-weight: 500; }
.activity-row a.label { text-decoration: none; }
.activity-row a.label:hover { text-decoration: underline; }
.activity-row .repo { color: var(--fg-muted); }
.activity-row .who { color: var(--fg-dim); }
.activity-row .detail { grid-column: 3 / -1; color: var(--fg-muted); font-size: 12.5px; }

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
.strip-label { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--fg-dim); margin-bottom: 4px; }
.strip-title { font-weight: 500; }
.empty { color: var(--fg-dim); padding: 14px 18px; }
"""


def render_page(*, title: str, body_html: str, now: datetime, refresh_seconds: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="{refresh_seconds}">
  <title>{_esc(title)}</title>
  <style>{CSS}</style>
</head>
<body>
{body_html}
<!-- generated {now.isoformat()} -->
</body>
</html>
"""


def build_page(*, goals_path: Path, vault_path: Path | None, refresh_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(TZ)

    goals = parse_goals(goals_path, limit=3)
    pulled_from = goals_path.name if goals_path.exists() else f"missing: {goals_path}"
    obsidian_url = build_obsidian_url(vault_path, goals_path) if goals_path.exists() else None

    watched = fetch_watched_summary(now)
    gh_rows = fetch_recent_github(limit=9)
    vault_rows = fetch_vault_recent(limit=6)
    cal_rows = fetch_calendar_upcoming(now, limit=6)
    sleuth_rows = fetch_sleuth_due(limit=6)
    status = get_index_status(DB_PATH)

    in_progress = sum(1 for g in goals if not g["done"])
    streams = {
        "github": len(gh_rows),
        "vault": len(vault_rows),
        "calendar": len(cal_rows),
        "sleuth": len(sleuth_rows),
    }
    semantic_total = ((status.get("semantic_index") or {}).get("total_documents")) or 0
    freshness = status.get("freshness") or {}
    drift_total = sum(int(v) for v in freshness.values() if isinstance(v, int))

    last_synced = watched.get("last_synced")
    synced_ago = _ago(last_synced, now=now) if last_synced else "—"
    last_vault = vault_rows[0] if vault_rows else None

    body = f"""
    <div class="app">
      {render_sidebar(
          in_progress=in_progress,
          cal_rows=cal_rows,
          sleuth_rows=sleuth_rows,
          streams=streams,
          drift_total=drift_total,
          semantic_total=semantic_total,
          tz=TZ,
          now=now,
      )}
      <main class="main">
        <div class="topbar">
          <div class="crumb">Pulse <span style="color:var(--fg-dim); margin:0 4px">›</span> Today</div>
          <div style="display:flex; gap:10px; align-items:center;">
            <span class="synced"><span class="ok-dot"></span>Synced {_esc(synced_ago)}</span>
            <button class="refresh-btn" onclick="location.reload()">Refresh</button>
          </div>
        </div>
        {render_hero(goals, pulled_from, local_now, obsidian_url)}
        <div class="grid">
          <div class="col">
            {render_recent_activity(gh_rows, now, last_vault=last_vault, vault_recent_count=len(vault_rows))}
          </div>
          <div class="col">
            {render_watched(watched, now)}
            {render_index_health(status, now)}
          </div>
        </div>
      </main>
    </div>
    """
    return render_page(title="rebalance pulse · Today", body_html=body, now=now, refresh_seconds=refresh_seconds)


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
    goals_path: Path
    if args.goals:
        goals_path = args.goals.expanduser()
    elif env := os.environ.get("PULSE_GOALS"):
        goals_path = Path(env).expanduser()
    else:
        if vault_path is None:
            print("error: no --goals path and vault_path not set in temp/rbos.config", file=sys.stderr)
            return 2
        goals_path = vault_path / "0. Goals.md"

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
