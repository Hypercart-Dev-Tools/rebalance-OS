"""Shared HTML building blocks for the rebalance-OS web surfaces.

Kept dependency-light so both the FastAPI app (:mod:`rebalance.web`) and the
static pulse mirror (``scripts/pulse_web.py``) can render identical chrome from
one place. Import the helper and include :data:`RB_BUTTON_CSS` once inside each
page's ``<style>``.
"""
from __future__ import annotations

import html

from rebalance.tz_utils import format_timestamp

# The one design-token set every web page shares — the single source of truth for
# the palette. Lifted verbatim from the pulse dashboard (the only fully-tokenized
# surface). Inject it FIRST inside every page's <style> so var(--…) refs resolve to
# the same values everywhere (Focus 5 / Auth Log + the dashboard). Changing the
# palette is now this one block, not a grep across pages.
#
# Token Vocabulary:
# Tier 1 (settable):
#   --page: Page background (default: #f3efe7)
#   --card: Card background (default: #ffffff)
#   --ink: Text (default: #1d2024)
#   --accent: Accent (default: #1f6feb)
#   --border: Borders (default: #e3ddd0)
#   --nowline: Calendar time line (default: #d43d2a)
#   --timestamp: Date + time text (default: #8a857c — what timestamps render today)
#
# Tier 2 (derived):
#   --muted: mix(ink, page, 0.45) (default preset exception: #5b5750)
#   --accent-ink: #ffffff if isDark(accent) else #111111 (default: #ffffff)
#   --zebra: mix(card, isDark(page) ? #ffffff : #000000, 0.96) (default: #f5f5f5)
#   --shadow: 0 1px 2px rgba(29, 32, 36, 0.04), 0 8px 24px rgba(29, 32, 36, 0.04) (derived from --ink at each layer's alpha)
#   --fg-dim: mix(ink, page, 0.5) (uncollapsed legacy, default preset exception: #8a857c)
#
# Tier 3 (theme-invariant, unchanged):
#   --ok: #2f7437
#   --warn: #a65f00
#   --danger: #c0392b
#   --info: #1d6fa8
RB_TOKENS_CSS = """:root {
  /* Tier 1 */
  --page: #f3efe7;
  --card: #ffffff;
  --ink: #1d2024;
  --accent: #1f6feb;
  --border: #e3ddd0;
  --nowline: #d43d2a;
  --timestamp: #8a857c;

  /* Tier 2 */
  --muted: #5b5750;
  --accent-ink: #ffffff;
  --zebra: #f5f5f5;
  --shadow: 0 1px 2px rgba(29, 32, 36, 0.04), 0 8px 24px rgba(29, 32, 36, 0.04);
  --fg-dim: #8a857c;

  /* Tier 3 */
  --ok: #2f7437;
  --warn: #a65f00;
  --danger: #c0392b;
  --info: #1d6fa8;

  /* Tier 3b — tokenized but NOT exposed in the picker. Values are today's literals, so
     rendering is unchanged. These encode calendar event STATE (upcoming vs past), which may
     be semantic (like --ok/--danger) or themeable — that call is deliberately deferred.
     Tokenizing without exposing keeps all three futures open: promote to tier 1 (settable),
     demote to tier 2 (derived from --accent/--page), or leave fixed. See GH-154 D7. */
  --cal-upcoming: #e8b93a;
  --cal-upcoming-ink: #3d3006;
  --cal-past: #f5edd8;
  --cal-past-ink: #a49a76;

  /* Legacy aliases for P1/P2/P3 to rewrite. Temporary compatibility bridge. To be removed after P3. */
  --bg: var(--page);
  --panel: var(--card);
  --fg: var(--ink);
  --fg-muted: var(--muted);
}"""

# The one button style every web page shares. ``color`` uses the page's
# ``--accent`` custom property when it defines one (the pulse dashboard theme)
# and falls back to the app blue otherwise, so the same class looks right on
# every surface — and a future theme/dark-mode change is one variable, not a
# grep across pages. Include this string once inside each page's <style>.
RB_BUTTON_CSS = """
.rb-btn { display:inline-flex; align-items:center; gap:4px; font-size:13px;
  font-weight:600; line-height:1.4; color:var(--accent);
  text-decoration:none; cursor:pointer; background:none; border:none; padding:0;
  font-family:inherit; }
.rb-btn:hover { text-decoration:underline; }
.rb-btn:focus-visible { outline:2px solid var(--accent); outline-offset:2px;
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
    attrs: str = "",
) -> str:
    """Render the standard ``Label ↗`` button shared across every web page.

    A restrained text-button matching the dashboard's existing open-links; the
    trailing ``↗`` (``arrow``) signals "opens / navigates out". Set ``external``
    for links that should open a new tab (adds ``target`` + ``rel``). Extra
    classes can be appended via ``cls``. All caller-supplied values are escaped.
    """
    target = ' target="_blank" rel="noopener noreferrer"' if external else ""
    title_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
    # `attrs` is emitted verbatim (caller-escaped) — used for data-* hooks.
    extra_attrs = f" {attrs}" if attrs else ""
    arrow_html = (
        ' <span class="rb-btn-arrow" aria-hidden="true">↗</span>' if arrow else ""
    )
    klass = ("rb-btn " + cls).strip()
    return (
        f'<a class="{html.escape(klass, quote=True)}" '
        f'href="{html.escape(href, quote=True)}"{target}{title_attr}{extra_attrs}>'
        f"{html.escape(label)}{arrow_html}</a>"
    )


def data_row(
    *,
    marker_html: str,
    title_html: str,
    meta_html: str = "",
    timestamp: object | None = None,
    tz: object | None = None,
    relative: bool = False,
    fallback_timestamp: str = "",
    row_class: str = "",
    body_class: str = "",
    marker_class: str = "",
    title_class: str = "",
    meta_class: str = "",
    trailing_class: str = "",
    time_class: str = "",
    stripe_index: int | None = None,
    attrs: str = "",
    href: str | None = None,
    link_title: str | None = None,
    external: bool = False,
    link_class: str = "",
    trailing_html: str = "",
) -> str:
    """Render the shared dashboard/sidebar row primitive.

    Caller-supplied ``*_html`` fragments are inserted verbatim and must already
    be escaped/sanitised. When ``timestamp`` is provided this helper formats it
    through :func:`rebalance.tz_utils.format_timestamp`, so every adopting row
    shares one timestamp contract.
    """

    def _classes(*parts: str) -> str:
        return " ".join(part for part in parts if part)

    ts_text = ""
    if timestamp is not None:
        ts_text = format_timestamp(timestamp, relative=relative, tz=tz) or fallback_timestamp

    title_cls = _classes("rb-data-row-title", title_class)
    meta_cls = _classes("rb-data-row-meta", meta_class)
    marker_cls = _classes("rb-data-row-marker", marker_class)
    body_cls = _classes("rb-data-row-body", body_class)
    trailing_cls = _classes("rb-data-row-trailing", trailing_class)
    time_cls = _classes("rb-data-row-time", "timestamp-block", time_class)

    meta_block = f'<div class="{html.escape(meta_cls, quote=True)}">{meta_html}</div>' if meta_html else ""
    time_block = f'<div class="{html.escape(time_cls, quote=True)}">{html.escape(ts_text)}</div>' if ts_text else ""
    trailing_bits = "".join(bit for bit in (time_block, trailing_html) if bit)
    trailing_block = (
        f'<div class="{html.escape(trailing_cls, quote=True)}">{trailing_bits}</div>'
        if trailing_bits else ""
    )
    content = (
        f'<span class="{html.escape(marker_cls, quote=True)}">{marker_html}</span>'
        f'<div class="{html.escape(body_cls, quote=True)}">'
        f'<div class="{html.escape(title_cls, quote=True)}">{title_html}</div>'
        f"{meta_block}</div>{trailing_block}"
    )

    if href:
        target = ' target="_blank" rel="noopener noreferrer"' if external else ""
        title_attr = f' title="{html.escape(link_title, quote=True)}"' if link_title else ""
        link_cls = _classes("rb-data-row-link", link_class)
        content = (
            f'<a class="{html.escape(link_cls, quote=True)}" '
            f'href="{html.escape(href, quote=True)}"{target}{title_attr}>{content}</a>'
        )

    klass = row_class or "rb-data-row-item"
    extra_attrs = f" {attrs}" if attrs else ""
    stripe_attr = ""
    if stripe_index is not None:
        stripe = "even" if stripe_index % 2 == 1 else "odd"
        stripe_attr = f' data-rb-stripe="{stripe}"'
    return (
        f'<li class="{html.escape(klass, quote=True)}" data-rb-row="1"{stripe_attr}{extra_attrs}>'
        f"{content}</li>"
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
  color: var(--ink);
  background: var(--page);
  -webkit-font-smoothing: antialiased;
}
code { font-family: "SF Mono", ui-monospace, Menlo, monospace; font-size: 12px; color: var(--muted); }
.subtle { color: var(--fg-dim); font-size: 12px; }
h1, h2, h3 { margin: 0; font-weight: 600; letter-spacing: -.01em; }
h1 { font-size: 22px; }
h2 { font-size: 14px; color: var(--ink); }

.app { display: grid; grid-template-columns: 280px 1fr; min-height: 100vh; }

/* Sidebar */
.sidebar {
  border-right: 1px solid var(--border);
  /* No bottom padding: it would sit BELOW the sticky .nav-foot, and scrolling content
     shows through that gap. The equivalent breathing room lives on .nav-foot instead. */
  padding: 20px 14px 0;
  display: flex; flex-direction: column;
  background: var(--page);
  /* Pinned to the viewport, not to the document. Without this the sidebar grows with the
     page (the grid is min-height:100vh), so `.nav-foot`'s margin-top:auto pins Settings to
     the bottom of a very tall column — i.e. below the fold on the dashboard, which is not a
     bottom-left nav in any useful sense. overflow-y keeps a content-heavy sidebar (calendar
     + reminders + streams) scrollable on its own rather than clipping it. */
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
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
.nav-list li { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; color: var(--ink); cursor: default; }
/* Nav anchors had NO colour rule, so they fell back to the UA default link blue. That reads
   acceptably on the light default but is near-invisible on a dark theme (GH-154 P4). */
.nav-list li a { color: inherit; text-decoration: none; }
.nav-list li a:hover { color: var(--accent); text-decoration: underline; }
.nav-list li.active { background: color-mix(in srgb, var(--accent) 10%, transparent); color: var(--ink); font-weight: 500; }
.nav-list .badge { margin-left: auto; color: var(--fg-dim); font-variant-numeric: tabular-nums; font-size: 12px; }
.nav-list .kbd { display: inline-block; min-width: 16px; padding: 0 5px; font-size: 11px; color: var(--fg-dim); border: 1px solid var(--border); border-radius: 4px; background: var(--card); text-align: center; }
/* Bottom-pinned nav (Settings). margin-top:auto pushes this — and the footer below it — to the
   bottom of the sidebar flex column; the rule above it marks it off from the scan-path nav. */
/* sticky bottom, not just margin-top:auto — the dashboard sidebar's own content (calendar +
   reminders + streams) is taller than 100vh, so auto-margin alone parks Settings at the end of
   the sidebar's internal scroll, still out of view. Sticky pins it to the visible bottom edge.
   The background is required: transparent would let scrolled content run underneath it. */
.nav-foot {
  margin-top: auto; position: sticky; bottom: 0; z-index: 2;
  padding: 8px 0 20px; background: var(--page); border-top: 1px solid var(--border);
}
.sidebar-foot { margin-top: 0; padding: 8px; font-variant-numeric: tabular-nums; }

/* Sidebar lists (calendar + reminders) */
.side-list { list-style: none; margin: 0; padding: 0; }
.side-row { padding: 7px 8px; border-radius: 6px; }
.side-row + .side-row { margin-top: 1px; }
.side-row:hover { background: var(--zebra); }
.side-row.has-link { padding: 0; }
.side-row-link { display: block; padding: 7px 8px; color: inherit; text-decoration: none; border-radius: 6px; }
.side-row-link:hover { background: color-mix(in srgb, var(--accent) 10%, transparent); }
.side-row-link:hover .side-row-title { color: var(--info); }
.side-row-title { font-size: 12.5px; line-height: 1.35; color: var(--ink); font-weight: 500; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.side-row-meta { font-size: 11.5px; color: var(--fg-dim); margin-top: 2px; font-variant-numeric: tabular-nums; }
.side-row.empty .side-row-meta { font-style: italic; }

/* Shared data rows */
.rb-data-list { list-style: none; margin: 0; padding: 0; container-type: inline-size; }

/* The 3-column anatomy (marker | body | right-aligned time) only works while the
   container is wide. `.rb-data-row-time` is nowrap, so an absolute+relative stamp
   like "2026-06-07 9:20 PM · 40d ago" claims ~215px no matter how narrow the list
   gets — and `minmax(0, 1fr)` obligingly collapses the BODY to 0px. Titles then
   render zero-width, and meta/chips overflow into very tall stacks. Measured in a
   307px Figma card: grid-template-columns resolved to "28px 0px 215.344px".

   So stack below a width where all three columns can coexist: marker + title on
   the first line, meta and timestamp beneath, left-aligned. A container query (not
   a viewport media query) is what's correct here — the trigger is how wide the
   LIST is, which varies per card at a single viewport width. */
@container (max-width: 500px) {
  .rb-data-list > [data-rb-row],
  .rb-data-list .rb-data-row-link {
    grid-template-columns: 28px minmax(0, 1fr);
    column-gap: 10px;
    row-gap: 3px;
  }
  .rb-data-list .rb-data-row-trailing {
    grid-column: 2;
    min-width: 0;
    align-items: flex-start;
    gap: 2px;
  }
  .rb-data-list .rb-data-row-time { text-align: left; }
}
.rb-data-list > [data-rb-row] {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 10px 14px;
  border-top: 1px solid var(--border);
}
.rb-data-list > [data-rb-row]:first-child { border-top: 0; }
.rb-data-list > [data-rb-row][data-rb-stripe="even"],
.rb-data-list > [data-rb-row]:nth-child(even):not([data-rb-stripe]) { background: var(--zebra); }
/* A linked row delegates the whole grid to its <a>. The wrapper must therefore
   STOP being a grid itself — otherwise its single <a> child is placed into the
   28px marker track, and the <a>'s own `minmax(0, 1fr)` body column collapses to
   zero width (titles render 0px wide, meta and chips overflow into tall stacks). */
.rb-data-list > [data-rb-row].has-link { display: block; padding: 0; }
.rb-data-row-link {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  width: 100%;
  padding: inherit;
  color: inherit;
  text-decoration: none;
}
.rb-data-row-marker {
  width: 28px;
  min-width: 28px;
  display: inline-flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 2px;
}
.rb-data-row-body { min-width: 0; }
.rb-data-row-title {
  color: var(--ink);
  font-size: 13px;
  line-height: 1.35;
  font-weight: 500;
}
.rb-data-row-title a {
  color: inherit;
  text-decoration: none;
}
.rb-data-row-title a:hover {
  color: var(--accent);
  text-decoration: underline;
}
.rb-data-row-meta {
  color: var(--muted);
  font-size: 11.75px;
  line-height: 1.4;
  margin-top: 3px;
}
.rb-data-row-sep { color: var(--fg-dim); }
.rb-data-row-trailing {
  min-width: 92px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: flex-start;
  gap: 6px;
}
.rb-data-row-time { text-align: right; white-space: nowrap; }
.rb-data-marker-badge,
.rb-data-marker-rank,
.rb-data-marker-avatar {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--muted);
}
.rb-data-marker-rank {
  border-color: color-mix(in srgb, var(--accent) 18%, transparent);
  background: color-mix(in srgb, var(--accent) 8%, transparent);
  color: var(--accent);
}
.rb-data-marker-avatar {
  border-color: color-mix(in srgb, var(--info) 18%, transparent);
  background: color-mix(in srgb, var(--info) 8%, transparent);
  color: var(--info);
}
.rb-data-marker-glyph {
  font-size: 14px;
  line-height: 1;
}
.side-list.rb-data-list > .side-row[data-rb-row] {
  padding: 7px 8px;
  gap: 10px;
  border-top: 0;
  border-radius: 6px;
}
.side-list.rb-data-list > .side-row[data-rb-row].has-link { padding: 0; }
.side-list.rb-data-list > .side-row[data-rb-row][data-rb-stripe="even"],
.side-list.rb-data-list > .side-row[data-rb-row]:nth-child(even):not([data-rb-stripe]) { background: var(--zebra); }
.side-list .rb-data-row-link { padding: 7px 8px; border-radius: 6px; }

/* The sidebar is always narrow, so it always resolves to the stacked form above
   via the container query — no sidebar-specific grid override is needed here. */

/* Calendar module — a day grid for today + an Upcoming list. Geometry constants
   live in pulse_web (CAL_HOUR_PX etc.); positions arrive as inline `top`/`height`
   so the layout math has exactly one home. Reuses the existing tokens, the
   `.timestamp-block` monospace treatment, and the shared zebra tint. */
.cal-module { margin: 2px 0 4px; }
.cal-date { font-size: 11px; color: var(--timestamp); padding: 0 8px 8px; }
.cal-grid { position: relative; margin: 0 4px 0 0; }
.cal-hour { position: absolute; left: 0; right: 0; display: flex; align-items: flex-start; }
.cal-hour-label {
  width: 44px;
  flex-shrink: 0;
  text-align: right;
  padding-right: 8px;
  font-size: 10px;
  color: var(--fg-dim);
  transform: translateY(-6px);
  font-variant-numeric: tabular-nums;
}
.cal-hour-rule { flex: 1; border-top: 1px solid var(--border); }
.cal-gutter-rule { position: absolute; left: 44px; top: 0; bottom: 0; border-left: 1px solid var(--border); }
.cal-event {
  position: absolute;
  left: 50px;
  right: 2px;
  border-radius: 6px;
  padding: 2px 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 1px;
  z-index: 2;
}
.cal-event-title {
  font-weight: 600;
  font-size: 11.5px;
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cal-event-time { font-size: 10px; opacity: .75; font-variant-numeric: tabular-nums; }
/* Upcoming reads as live/actionable; past recedes without disappearing. */
.cal-event.upcoming { background: var(--cal-upcoming); color: var(--cal-upcoming-ink); }
.cal-event.past { background: var(--cal-past); color: var(--cal-past-ink); }
.cal-now { position: absolute; left: 44px; right: 0; z-index: 3; display: flex; align-items: center; }
.cal-now-dot { width: 9px; height: 9px; border-radius: 999px; background: var(--nowline); margin-left: -4px; flex-shrink: 0; }
.cal-now-line { flex: 1; height: 2px; background: var(--nowline); }
.cal-upcoming { border-top: 1px solid var(--border); margin-top: 12px; padding-top: 10px; }
.cal-up-list { display: flex; flex-direction: column; margin-top: 4px; }
.cal-up-row {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 5px 8px;
  border-radius: 6px;
}
.cal-up-row[data-rb-stripe="even"] { background: var(--zebra); }
.cal-up-time { font-size: 10.5px; color: var(--timestamp); white-space: nowrap; }
.cal-up-title {
  font-size: 12px;
  font-weight: 500;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Streams: compact connector list */
.streams { list-style: none; margin: 0; padding: 0; }
.streams li { display: flex; align-items: center; gap: 8px; padding: 5px 8px; border-radius: 6px; }
.streams .badge { margin-left: auto; color: var(--fg-dim); font-variant-numeric: tabular-nums; font-size: 12px; }
.streams .kbd { display: inline-block; min-width: 16px; padding: 0 5px; font-size: 11px; color: var(--fg-dim); border: 1px solid var(--border); border-radius: 4px; background: var(--card); text-align: center; }
.auth-log-link a { display: flex; align-items: center; gap: 8px; color: var(--fg-dim); text-decoration: none; font-size: 13px; width: 100%; }
.auth-log-link a:hover { color: var(--ink); }
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
    ("whatsnext", "/whats-next", "What's Next"),
    ("authlog", "/auth-log", "System Log"),
    ("sleuthgraph", "/sleuth-graph", "Reminder Graph"),
)

# Pinned to the bottom of the sidebar rather than appended to _NAV_LINKS: this is
# configuration, not a data surface, so it should not sit in the same scan path as
# Today / Focus 5 / What's Next. `.sidebar-foot` already has `margin-top: auto`, so
# the footer floats to the bottom of the flex column on every page height.
_FOOTER_NAV_LINKS = (
    ("settings", "/settings", "Settings"),
)


def _render_footer_nav(active: str) -> str:
    """Render the bottom-pinned nav (currently just Settings)."""
    return "".join(
        f'<li{" class=\"active\"" if key == active else ""}>'
        f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a></li>'
        for key, href, label in _FOOTER_NAV_LINKS
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
        cal_html       – the calendar module block (day grid + Upcoming), already
                         wrapped in its own container by the caller
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
        footer_nav = _render_footer_nav(active)
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
      <nav class="nav-foot">
        <ul class="nav-list">{footer_nav}</ul>
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
    footer_nav = _render_footer_nav(active)
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
        {cal_html}

        <div class="nav-section-label">Reminders</div>
        <ul class="side-list rb-data-list">{sleuth_html}</ul>
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
            <a href="/whats-next" target="_blank" rel="noopener noreferrer"
               title="Open What's Next — the single ranked list of what to work on next (calendar + GitHub + vault + reminders, team-blended)">
              <span class="auth-log-icon">🧭</span><span>What's Next</span>
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
      <nav class="nav-foot">
        <ul class="nav-list">{footer_nav}</ul>
      </nav>
      <footer class="sidebar-foot subtle">Drift {drift_total} · {semantic_total:,} docs</footer>
    </aside>
    """


RB_THEME_BOOTSTRAP_JS = """<script>
/* GH-154 P4 — theme bootstrap. MUST stay synchronous and inline, and MUST be emitted
   BEFORE the <style> block: any defer/async/external form reintroduces the flash of the
   default theme that decision D2 exists to prevent.

   This is the ONE derivation implementation (D1). Python never derives; it ships the default
   preset pre-derived as literals in RB_TOKENS_CSS and serialises the user's inputs here.
   Persisted record is versioned INPUTS, never derived output (D1/D3) — a formula change must
   be able to re-derive, which a frozen snapshot cannot.

   Any malformed state falls through to the default preset silently: a theme picker that
   white-screens on a bad JSON blob is worse than one that ignores it. */
(function () {
  var KEY = 'pulse-theme-settings-v2';
  var SCHEMA = 1;
  var HEX = /^#[0-9a-fA-F]{6}$/;
  var FIELDS = ['page', 'card', 'ink', 'accent', 'border', 'nowline', 'timestamp'];
  /* Helpers and the reuse seam are defined UNCONDITIONALLY, before any validation.
     The Settings page needs window.__pulseTheme even when nothing is stored yet — which
     is precisely the first-visit case — so an early return must never skip it. */
  {
    var int_ = function (h) { return parseInt(h.slice(1), 16); };
    var isDark = function (h) {
      var v = int_(h);
      return (0.299 * (v >> 16 & 255) + 0.587 * (v >> 8 & 255) + 0.114 * (v & 255)) < 128;
    };
    var mix = function (a, b, w) {
      var pa = int_(a), pb = int_(b);
      var ch = function (s) { return Math.round((pa >> s & 255) * w + (pb >> s & 255) * (1 - w)); };
      return '#' + [16, 8, 0].map(function (s) {
        return ch(s).toString(16).padStart(2, '0');
      }).join('');
    };
    var rgba = function (h, a) {
      var v = int_(h);
      return 'rgba(' + (v >> 16 & 255) + ', ' + (v >> 8 & 255) + ', ' + (v & 255) + ', ' + a + ')';
    };
    /* Tier 2 — derived here and ONLY here. Mirrors the mockup's themeOf().
       Exposed on window so the Settings page (P5) can re-use it for live preview
       instead of shipping a second copy: two derivation implementations is exactly
       the drift D1 exists to prevent. This is the ONLY supported reuse seam. */
    var apply = function (inp, el) {
      var s = (el || document.documentElement).style;
      for (var f = 0; f < FIELDS.length; f++) s.setProperty('--' + FIELDS[f], inp[FIELDS[f]]);
      s.setProperty('--muted', mix(inp.ink, inp.page, 0.45));
      s.setProperty('--fg-dim', mix(inp.ink, inp.page, 0.5));
      s.setProperty('--accent-ink', isDark(inp.accent) ? '#ffffff' : '#111111');
      s.setProperty('--zebra', mix(inp.card, isDark(inp.page) ? '#ffffff' : '#000000', 0.96));
      s.setProperty('--shadow',
        '0 1px 2px ' + rgba(inp.ink, 0.04) + ', 0 8px 24px ' + rgba(inp.ink, 0.04));
      /* Legacy aliases are var()-chained in RB_TOKENS_CSS, so they follow automatically. */
    };
    window.__pulseTheme = {
      KEY: KEY, SCHEMA: SCHEMA, FIELDS: FIELDS, HEX: HEX,
      mix: mix, isDark: isDark, rgba: rgba, apply: apply,
      /* Serialise the ONE persisted shape. Callers must not hand-build the record. */
      record: function (preset, inp) {
        return { schema_version: SCHEMA, derivation_version: 1, preset: preset, inputs: inp };
      },
      /* The one validator. Returns the inputs object, or null for ANY malformed state. */
      parse: function (raw) {
        if (!raw) return null;
        var rec;
        try { rec = JSON.parse(raw); } catch (e) { return null; }
        if (!rec || rec.schema_version !== SCHEMA || !rec.inputs) return null;
        for (var n = 0; n < FIELDS.length; n++) {
          if (!HEX.test(rec.inputs[FIELDS[n]])) return null;   /* partial -> reject wholesale */
        }
        return rec.inputs;
      }
    };
  }
  /* Apply a stored theme, if there is a valid one. Anything else falls through to the
     default preset Python already shipped as literals in RB_TOKENS_CSS. */
  try {
    var stored = window.__pulseTheme.parse(window.localStorage.getItem(KEY));
    if (stored) window.__pulseTheme.apply(stored);
  } catch (e) { /* disabled localStorage / quota / privacy mode -> default preset */ }
})();
</script>"""


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
    theme_bootstrap: str = RB_THEME_BOOTSTRAP_JS,
) -> str:
    """Assemble a complete HTML document around a page ``body``.

    Pure (zero I/O). ``body`` is the inner content of ``<main>`` (its exact
    bytes, including leading/trailing whitespace). The page's ``<style>`` is
    composed as ``<style>\\n{RB_TOKENS_CSS}{RB_CHROME_CSS}{page_css}{RB_BUTTON_CSS}</style>``
    so tokens + chrome are single-sourced and the page-local rules slot in
    between. ``theme_bootstrap`` is emitted inside ``<head>`` **before** the style
    block and must stay synchronous and inline — it sets the theme's custom
    properties on ``<html>`` ahead of first paint, so there is no flash of the
    default theme (GH-154 D2/P4). Both the live routes and the static ``/`` build
    pass through here, so it is single-sourced. ``head_extra`` is emitted inside
    ``<head>`` immediately *after* the style block (e.g. a Chart.js ``<script>``)
    and is therefore NOT suitable for theming; ``body_extra`` is emitted inside
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
  {theme_bootstrap}
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
