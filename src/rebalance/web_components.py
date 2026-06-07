"""Shared HTML building blocks for the rebalance-OS web surfaces.

Kept dependency-light (stdlib only) so both the FastAPI app (:mod:`rebalance.web`)
and the static pulse mirror (``scripts/pulse_web.py``) can render identical
chrome from one place. Import the helper and include :data:`RB_BUTTON_CSS` once
inside each page's ``<style>``.
"""
from __future__ import annotations

import html

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
