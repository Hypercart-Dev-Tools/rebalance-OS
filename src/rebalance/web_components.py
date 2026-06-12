"""Shared HTML building blocks for the rebalance-OS web surfaces.

Kept dependency-light (stdlib only) so both the FastAPI app (:mod:`rebalance.web`)
and the static pulse mirror (``scripts/pulse_web.py``) can render identical
chrome from one place. Import the helper and include :data:`RB_BUTTON_CSS` once
inside each page's ``<style>``.
"""
from __future__ import annotations

import html

# The one design-token set every web page shares — the single source of truth for
# the palette. Lifted verbatim from the pulse dashboard (the only fully-tokenized
# surface). Inject it FIRST inside every page's <style> so var(--…) refs resolve to
# the same values everywhere (Focus 5 / Auth Log + the dashboard). Changing the
# palette is now this one block, not a grep across pages.
RB_TOKENS_CSS = """:root {
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
}"""

# The one button style every web page shares. ``color`` uses the page's
# ``--accent`` custom property when it defines one (the pulse dashboard theme)
# and falls back to the app blue otherwise, so the same class looks right on
# every surface — and a future theme/dark-mode change is one variable, not a
# grep across pages. Include this string once inside each page's <style>.
RB_BUTTON_CSS = """
.rb-btn { display:inline-flex; align-items:center; gap:4px; font-size:13px;
  font-weight:600; line-height:1.4; color:var(--accent,#1a73e8);
  text-decoration:none; cursor:pointer; background:none; border:none; padding:0;
  font-family:inherit; }
.rb-btn:hover { text-decoration:underline; }
.rb-btn:focus-visible { outline:2px solid var(--accent,#1a73e8); outline-offset:2px;
  border-radius:3px; }
.rb-btn .rb-btn-arrow { font-size:.9em; }
"""


_BADGE_VARIANTS = frozenset({"ok", "warn", "danger", "info", "neutral"})


def badge_html(variant: str, label: str) -> str:
    """Render a semantic pill badge: ``<span class="badge badge-{variant}">…</span>``.

    ``variant`` is validated against the five token-backed variants
    (``ok | warn | danger | info | neutral``); anything else degrades to
    ``neutral`` so a bad key can never emit an unstyled badge. ``label`` is
    HTML-escaped. The colour comes from the page's ``.badge-*`` rules (which map
    each variant to its design token), so no inline ``style`` hex is emitted.
    """
    v = variant if variant in _BADGE_VARIANTS else "neutral"
    return f'<span class="badge badge-{v}">{html.escape(label)}</span>'


def button_link(
    label: str,
    href: str,
    *,
    external: bool = False,
    title: str | None = None,
    arrow: bool = True,
    cls: str = "",
) -> str:
    """Render the standard ``Label ↗`` button shared across every web page.

    A restrained text-button matching the dashboard's existing open-links; the
    trailing ``↗`` (``arrow``) signals "opens / navigates out". Set ``external``
    for links that should open a new tab (adds ``target`` + ``rel``). Extra
    classes can be appended via ``cls``. All caller-supplied values are escaped.
    """
    target = ' target="_blank" rel="noopener noreferrer"' if external else ""
    title_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
    arrow_html = (
        ' <span class="rb-btn-arrow" aria-hidden="true">↗</span>' if arrow else ""
    )
    klass = ("rb-btn " + cls).strip()
    return (
        f'<a class="{html.escape(klass, quote=True)}" '
        f'href="{html.escape(href, quote=True)}"{target}{title_attr}>'
        f"{html.escape(label)}{arrow_html}</a>"
    )


# The reusable chrome shared by every full-page surface: the global base resets
# (box-sizing / body font / headings) + the sidebar/nav/footer shell that frames
# the page. Lifted from the pulse dashboard's <style> so the static mirror and the
# FastAPI app paint the same frame. The base resets sit first because that is their
# order in the dashboard's style block — keeping them here (rather than page-local)
# lets render_shell emit one fixed style order. The dashboard's rendered output is
# computed-style IDENTICAL after this relocation (proven against the pre-refactor
# snapshot) — not literally byte-identical, since `.main` moves here and a new
# `.main.narrow` rule is added (neither alters the dashboard, which is `class="main"`
# and shares no conflicting properties with the relocated rules). Page-specific CSS
# (hero/goals/health-banner/repo-pie/
# topbar/email/open-prs/charts and the responsive @media collapse, which is
# interleaved with page rules) stays LOCAL to each page. Inject this AFTER
# RB_TOKENS_CSS and BEFORE the page-local rules inside each page's <style>.
RB_CHROME_CSS = """
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
.nav-section-label.section-link { display: flex; align-items: center; justify-content: space-between; text-decoration: none; gap: 8px; }
.nav-section-label.section-link:hover { color: var(--accent); }
.nav-section-label.section-link .section-link-arrow { font-size: 12px; line-height: 1; opacity: .65; }
.nav-section-label.section-link:hover .section-link-arrow { opacity: 1; color: var(--accent); }
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
.side-row.has-link { padding: 0; }
.side-row-link { display: block; padding: 7px 8px; color: inherit; text-decoration: none; border-radius: 6px; }
.side-row-link:hover { background: rgba(124,196,255,.10); }
.side-row-link:hover .side-row-title { color: var(--info); }
.side-row-title { font-size: 12.5px; line-height: 1.35; color: var(--fg); font-weight: 500; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.side-row-meta { font-size: 11.5px; color: var(--fg-dim); margin-top: 2px; font-variant-numeric: tabular-nums; }
.side-row.empty .side-row-meta { font-style: italic; }

/* Streams: compact connector list */
.streams { list-style: none; margin: 0; padding: 0; }
.streams li { display: flex; align-items: center; gap: 8px; padding: 5px 8px; border-radius: 6px; }
.streams .badge { margin-left: auto; color: var(--fg-dim); font-variant-numeric: tabular-nums; font-size: 12px; }
.streams .kbd { display: inline-block; min-width: 16px; padding: 0 5px; font-size: 11px; color: var(--fg-dim); border: 1px solid var(--border); border-radius: 4px; background: #fff; text-align: center; }
.auth-log-link a { display: flex; align-items: center; gap: 8px; color: var(--fg-dim); text-decoration: none; font-size: 13px; width: 100%; }
.auth-log-link a:hover { color: var(--fg); }
.auth-log-icon { font-size: 13px; }

/* Content area — the <main> beside the sidebar. Shared chrome so every surface
   (dashboard + the FastAPI pages) gets the same padding/gap; the dashboard is
   `main` (full width), simpler pages are `main narrow` (capped for readability). */
.main { padding: 22px 28px; display: flex; flex-direction: column; gap: 18px; min-width: 0; }
.main.narrow { max-width: 1040px; }"""


# Per-page chrome strings: crumb label + active nav item, keyed by the ``active``
# marker render_sidebar accepts. Kept here (not in pulse_web) so every surface
# names the nav the same way.
_NAV_LINKS = (
    ("today", "/", "Today"),
    ("focus5", "/focus-5", "Focus 5"),
    ("authlog", "/auth-log", "System Log"),
    ("sleuthgraph", "/sleuth-graph", "Reminder Graph"),
)


def render_sidebar(active: str, nav_data: dict | None = None) -> str:
    """Render the shared sidebar shell.

    ``active`` marks the active nav item (``'today' | 'focus5' | 'authlog'``).

    When ``nav_data`` is ``None`` this returns a MINIMAL, I/O-free sidebar: the
    brand + the three nav links + the footer, with NO dynamic sections. This is
    the safe default for surfaces that have no live data to inject.

    When ``nav_data`` is a dict it carries the dashboard's already-rendered
    section HTML (built by the caller, which owns the DB/keyring/etc.) so this
    module stays stdlib-only. Recognised keys (all pre-escaped HTML strings or
    plain values):
        badge          – the active item's trailing badge (in-progress count)
        cal_html       – the calendar <li> rows
        sleuth_html    – the reminders <li> rows
        notices_html   – the optional Notices section block
        streams        – [{name, label, kbd, count}, ...] stream rows
        drift_total    – footer drift count
        semantic_total – footer doc count
    """
    if nav_data is None:
        links = []
        for key, href, label in _NAV_LINKS:
            cls = ' class="active"' if key == active else ""
            links.append(
                f'<li{cls}><a href="{html.escape(href, quote=True)}">'
                f"{html.escape(label)}</a></li>"
            )
        nav_links = "".join(links)
        return f"""
    <aside class="sidebar">
      <div class="brand">
        <div class="dot"></div>
        <div>
          <div class="crumb">rebalanceOS Pulse</div>
        </div>
      </div>
      <nav>
        <ul class="nav-list">{nav_links}</ul>
      </nav>
      <footer class="sidebar-foot subtle"></footer>
    </aside>
    """

    badge = nav_data.get("badge", 0)
    cal_html = nav_data.get("cal_html", "")
    sleuth_html = nav_data.get("sleuth_html", "")
    notices_html = nav_data.get("notices_html", "")
    streams = nav_data.get("streams") or []
    drift_total = nav_data.get("drift_total", 0)
    semantic_total = nav_data.get("semantic_total", 0)
    if isinstance(streams, dict):
        streams = [
            {"name": "github", "label": "GitHub", "kbd": "G", "count": streams.get("github", 0)},
            {"name": "vault", "label": "Vault", "kbd": "V", "count": streams.get("vault", 0)},
            {"name": "calendar", "label": "Calendar", "kbd": "C", "count": streams.get("calendar", 0)},
            {"name": "sleuth", "label": "Sleuth", "kbd": "S", "count": streams.get("sleuth", 0)},
        ]
    stream_items = []
    for row in streams:
        label = html.escape(str(row.get("label") or row.get("name") or "Stream"))
        kbd = html.escape(str(row.get("kbd") or "?")[:2])
        count = html.escape(str(row.get("count") if row.get("count") is not None else 0))
        stream_items.append(
            f'<li><span class="kbd">{kbd}</span><span>{label}</span><span class="badge">{count}</span></li>'
        )

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
          <li class="active"><span>Today</span><span class="badge">{badge}</span></li>
        </ul>

        <a class="nav-section-label section-link" href="https://calendar.google.com/calendar/u/0/r"
           target="_blank" rel="noopener noreferrer" title="Open Google Calendar">
          <span>Calendar</span><span class="section-link-arrow" aria-hidden="true">↗</span>
        </a>
        <ul class="side-list">{cal_html}</ul>

        <div class="nav-section-label">Reminders</div>
        <ul class="side-list">{sleuth_html}</ul>
        {notices_html}
        <div class="nav-section-label">Streams</div>
        <ul class="streams">{''.join(stream_items)}</ul>

        <div class="nav-section-label">System</div>
        <ul class="nav-list">
          <li class="auth-log-link">
            <a href="/focus-5" target="_blank" rel="noopener noreferrer"
               title="Open Focus 5 — the 5 repos you're actively working on (tree health, newest PR, recent commits)">
              <span class="auth-log-icon">🎯</span><span>Focus 5</span>
            </a>
          </li>
          <li class="auth-log-link">
            <a href="/auth-log" target="_blank" rel="noopener noreferrer"
               title="Open the Authorization Log (auth events across all collectors)">
              <span class="auth-log-icon">🔐</span><span>Authorization Log</span>
            </a>
          </li>
        </ul>
      </nav>
      <footer class="sidebar-foot subtle">Drift {drift_total} · {semantic_total:,} docs</footer>
    </aside>
    """


def render_shell(
    title: str,
    body: str,
    *,
    active: str,
    wide: bool = False,
    nav_data: dict | None = None,
    page_css: str = "",
    body_extra: str = "",
    head_extra: str = "",
) -> str:
    """Assemble a complete HTML document around a page ``body``.

    Pure (zero I/O). ``body`` is the inner content of ``<main>`` (its exact
    bytes, including leading/trailing whitespace). The page's ``<style>`` is
    composed as ``<style>\\n{RB_TOKENS_CSS}{RB_CHROME_CSS}{page_css}{RB_BUTTON_CSS}</style>``
    so tokens + chrome are single-sourced and the page-local rules slot in
    between. ``head_extra`` is emitted inside ``<head>`` immediately after the
    style block (e.g. a Chart.js ``<script>``); ``body_extra`` is emitted inside
    ``<body>`` after the app shell (e.g. a generated-at comment + the page's
    ``<script>``). ``wide`` widens the main column. ``nav_data`` is forwarded to
    :func:`render_sidebar`.
    """
    # The dashboard's wide layout IS the bare ``.main`` rule (there is no separate
    # ``.main.wide`` selector in the chrome), so ``wide`` maps to the plain class
    # to preserve the dashboard's computed layout; narrower pages get ``narrow``.
    main_cls = "main" if wide else "main narrow"
    sidebar = render_sidebar(active, nav_data)
    shell_body = (
        f'\n    <div class="app">\n      {sidebar}\n      '
        f'<main class="{main_cls}">{body}</main>\n    </div>\n    {body_extra}'
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
{RB_TOKENS_CSS}{RB_CHROME_CSS}{page_css}{RB_BUTTON_CSS}</style>{head_extra}
</head>
<body>
{shell_body}</body>
</html>
"""


# ---------------------------------------------------------------------------
# Shared glyph constants — single source of truth for kind/sub-kind characters.
# Both the TUI dashboard (dashboard.py) and the HTML surfaces (pulse_web.py)
# build their own colored tuples on top; the characters must match across both.
# ---------------------------------------------------------------------------

KIND_GLYPHS: dict[str, str] = {
    "commit":  "●",
    "item":    "◆",
    "comment": "○",
}

ITEM_SUB_GLYPHS: dict[str, str] = {
    "issue":        "✦",
    "pull_request": "⇡",
}
