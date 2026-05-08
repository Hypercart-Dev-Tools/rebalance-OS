"""Technical spike: BeeWare/Toga port of the pulse dashboard.

Goal — answer four questions cheaply, before committing to a full port:

  1. Layout system: can Toga's Pack do sidebar + main with a card inside?
  2. Card styling: rounded corners, shadow, custom backgrounds — how close
     can we get without dropping to Cocoa via Rubicon-ObjC?
  3. Multi-line list rows: render calendar entries with title-on-top + meta
     line, using whatever Toga primitive is least painful.
  4. Data layer reuse: import `fetch_calendar_upcoming` and `parse_goals`
     from the existing scripts/ tree and render real DB rows.

Findings live alongside in README.md. Run with:
    .venv-toga/bin/python experimental/pulse-toga-spike/app.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Make sure the data layer points at the live DB.
os.environ.setdefault("REBALANCE_DB", str(PROJECT_ROOT / "rebalance.db"))

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

# Rubicon-ObjC is shipped as a Toga dependency on macOS. We use it to drop
# below Pack and reach the underlying NSView so we can set CALayer properties
# Toga's style system doesn't expose: corner radius, shadow, gradient.
# AppKit isn't loaded until toga-cocoa initializes — resolve classes lazily.
from rubicon.objc import ObjCClass  # type: ignore

from dashboard import fetch_calendar_upcoming, _parse_iso, TZ  # type: ignore
from pulse_web import load_vault_path, parse_goals  # type: ignore


_NSColor = None


def _ns_color():
    global _NSColor
    if _NSColor is None:
        _NSColor = ObjCClass("NSColor")
    return _NSColor


def _hex_to_nscolor(hex_str: str, alpha: float = 1.0):
    """Convert "#rrggbb" or "#rrggbbaa" to an NSColor (sRGB)."""
    h = hex_str.lstrip("#")
    if len(h) == 8:
        r, g, b, a = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4, 6))
    else:
        r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
        a = alpha
    return _ns_color().colorWithSRGBRed(r, green=g, blue=b, alpha=a)


def _native_view(widget: toga.Widget):
    """Return the underlying NSView for a Toga widget on macOS."""
    impl = getattr(widget, "_impl", None)
    if impl is None:
        return None
    native = getattr(impl, "native", None)
    if native is None:
        # Some widgets (Box) wrap an inner container; fall back to that.
        native = getattr(impl, "container", None)
    return native


_CALayer = None


def _ca_layer():
    global _CALayer
    if _CALayer is None:
        _CALayer = ObjCClass("CALayer")
    return _CALayer


def style_as_card(
    widget: toga.Widget,
    *,
    radius: float = 12.0,
    bg_hex: str = "#ffffff",
    border_hex: str | None = "#e3ddd0",
    shadow_opacity: float = 0.06,
    shadow_radius: float = 18.0,
    shadow_offset_y: float = -2.0,
    label: str = "card",
) -> None:
    """Apply rounded corners + drop shadow to a Toga widget via CALayer.

    Must be called AFTER the window is shown, otherwise the NSView's layer
    is None and the call silently no-ops. Diagnostics print to stderr so
    we can see when the bridge reaches dead ends.
    """
    view = _native_view(widget)
    if view is None:
        print(f"[card:{label}] no native view found", file=sys.stderr)
        return

    # Diagnose: what NSView subclass is this, and does it draw via layer?
    try:
        cls_name = str(view.objc_class.name)
    except Exception as e:
        cls_name = f"?({e})"
    frame = view.frame
    print(
        f"[card:{label}] view={cls_name} "
        f"frame=({frame.origin.x:.0f},{frame.origin.y:.0f},"
        f"{frame.size.width:.0f}x{frame.size.height:.0f}) "
        f"wantsUpdateLayer={view.wantsUpdateLayer}",
        file=sys.stderr,
    )

    # Force a layer-backed view AND assign an explicit CALayer so we don't
    # depend on AppKit lazily creating one.
    view.wantsLayer = True
    if view.layer is None:
        view.layer = _ca_layer().layer()
    layer = view.layer
    if layer is None:
        print(f"[card:{label}] layer still None after assignment", file=sys.stderr)
        return

    # NOTE — empirical finding from iteration 1 (see README):
    #   - layer.backgroundColor: APPLIED, visible
    #   - layer.borderColor / borderWidth: APPLIED, visible
    #   - layer.cornerRadius: STICKS on the layer object, but the visible
    #     drawing path on TogaView does NOT honor it (corners stay sharp)
    #   - layer.shadow*: not rendered (TogaView likely sets bounds-equal
    #     clipping at draw time)
    # We still apply them so a future fix at the TogaView level (subclass
    # or upstream patch) flips the visible result without code changes here.
    layer.cornerRadius = radius
    layer.backgroundColor = _hex_to_nscolor(bg_hex).CGColor
    if border_hex:
        layer.borderColor = _hex_to_nscolor(border_hex).CGColor
        layer.borderWidth = 1.0

    layer.masksToBounds = False
    layer.shadowOpacity = shadow_opacity
    layer.shadowRadius = shadow_radius
    layer.shadowOffset = (0.0, shadow_offset_y)
    layer.shadowColor = _hex_to_nscolor("#000000").CGColor

    view.needsDisplay = True
    layer.setNeedsDisplay()

    print(
        f"[card:{label}] applied: radius={layer.cornerRadius} "
        f"borderWidth={layer.borderWidth} "
        f"shadow_opacity={layer.shadowOpacity}",
        file=sys.stderr,
    )


# Palette mirrored from web/pulse.html so we can compare apples-to-apples.
BG = "#f3efe7"
PANEL = "#ffffff"
BORDER = "#e3ddd0"
FG = "#1d2024"
FG_MUTED = "#5b5750"
FG_DIM = "#8a857c"
ACCENT = "#1f6feb"
SIDEBAR_BG = "#f8f4ec"


def _format_when(value) -> str:
    dt = _parse_iso(value) if isinstance(value, str) else value
    if dt is None:
        return ""
    return dt.astimezone(TZ).strftime("%a %-I:%M %p").lower()


def _truncate(text: str, n: int) -> str:
    text = (text or "").splitlines()[0] if text else ""
    return text if len(text) <= n else text[: n - 1] + "…"


class PulseSpike(toga.App):
    def startup(self) -> None:
        now = datetime.now(timezone.utc)

        # --- Real data via the same fetch_* the TUI and HTML view use -----
        cal_rows = fetch_calendar_upcoming(now, limit=6)
        vault = load_vault_path()
        goals_path = (vault / "0. Goals.md") if vault else None
        goals = parse_goals(goals_path, limit=3) if goals_path and goals_path.exists() else []
        in_progress = sum(1 for g in goals if not g["done"])

        # --- Sidebar -----------------------------------------------------
        sidebar_children: list[toga.Widget] = [
            toga.Label(
                "rebalanceOS Pulse  ›  Today",
                style=Pack(padding=(8, 6, 22, 6), font_weight="bold", color=FG),
            ),
            toga.Label(
                "TODAY",
                style=Pack(padding=(0, 8, 4, 8), font_size=10, color=FG_DIM),
            ),
            toga.Box(
                children=[
                    toga.Label("Today", style=Pack(flex=1, color=FG, padding=(6, 8))),
                    toga.Label(
                        str(in_progress),
                        style=Pack(color=FG_DIM, padding=(6, 8)),
                    ),
                ],
                style=Pack(direction=ROW, background_color="#e6efff"),
            ),
            toga.Label(
                "CALENDAR",
                style=Pack(padding=(20, 8, 6, 8), font_size=10, color=FG_DIM),
            ),
        ]

        for ev in cal_rows:
            title = _truncate((ev.get("summary") or "event").strip(), 64)
            when = _format_when(ev.get("start_time"))
            loc = ev.get("location") or ""
            meta = when + (" · " + loc if loc else "")
            row = toga.Box(
                children=[
                    toga.Label(title, style=Pack(color=FG, padding=(0, 0, 2, 0))),
                    toga.Label(meta, style=Pack(color=FG_DIM, font_size=11)),
                ],
                style=Pack(direction=COLUMN, padding=(7, 8)),
            )
            sidebar_children.append(row)

        if not cal_rows:
            sidebar_children.append(
                toga.Label("No upcoming events.", style=Pack(color=FG_DIM, padding=(6, 8)))
            )

        sidebar_inner = toga.Box(
            children=sidebar_children,
            style=Pack(direction=COLUMN, padding=18, background_color=SIDEBAR_BG),
        )
        sidebar = toga.ScrollContainer(
            content=sidebar_inner,
            horizontal=False,
            style=Pack(width=280, background_color=SIDEBAR_BG),
        )

        # --- Hero card ---------------------------------------------------
        hero_children: list[toga.Widget] = [
            toga.Label(
                "Today's Goals",
                style=Pack(font_size=20, font_weight="bold", color=FG, padding=(0, 0, 4, 0)),
            ),
            toga.Label(
                f"{datetime.now().strftime('%A, %B %-d')} · pulled from 0. Goals.md",
                style=Pack(color=FG_DIM, font_size=12, padding=(0, 0, 14, 0)),
            ),
        ]
        for g in goals:
            check_glyph = "☑" if g["done"] else "☐"
            title_color = FG_DIM if g["done"] else FG
            hero_children.append(
                toga.Box(
                    children=[
                        toga.Label(
                            check_glyph,
                            style=Pack(
                                padding=(0, 10, 0, 0),
                                font_size=18,
                                color=ACCENT if g["done"] else FG_MUTED,
                            ),
                        ),
                        toga.Box(
                            children=[
                                toga.Label(
                                    g["title"],
                                    style=Pack(font_weight="bold", color=title_color),
                                ),
                                toga.Label(
                                    g["description"] or "",
                                    style=Pack(color=FG_MUTED, font_size=12, padding=(2, 0, 0, 0)),
                                ),
                            ],
                            style=Pack(direction=COLUMN, flex=1),
                        ),
                    ],
                    style=Pack(direction=ROW, padding=(10, 0)),
                )
            )
        if not goals:
            hero_children.append(
                toga.Label("No goals found in 0. Goals.md.", style=Pack(color=FG_DIM))
            )

        # Note: deliberately NO background_color in Pack. Pack draws bg via
        # NSView.drawRect: which ignores layer.cornerRadius. The fill is set
        # entirely by style_as_card() via layer.backgroundColor, which DOES
        # respect cornerRadius.
        hero_card = toga.Box(
            children=hero_children,
            style=Pack(direction=COLUMN, padding=22),
        )
        # Stash for deferred styling — see on_running().
        self._cards_to_style = [(hero_card, "hero")]

        # --- Main column -------------------------------------------------
        main = toga.Box(
            children=[
                toga.Label(
                    "Pulse  ›  Today",
                    style=Pack(color=FG_MUTED, padding=(0, 0, 14, 0)),
                ),
                hero_card,
            ],
            style=Pack(direction=COLUMN, padding=22, flex=1, background_color=BG),
        )

        # --- Root: sidebar + main ---------------------------------------
        root = toga.Box(
            children=[sidebar, main],
            style=Pack(direction=ROW, flex=1),
        )

        self.main_window = toga.MainWindow(title="rebalance Pulse (Toga spike)", size=(1200, 800))
        self.main_window.content = root
        self.main_window.show()

    async def on_running(self) -> None:
        """Apply Cocoa-bridge styling once the run loop is alive and views have layers."""
        for widget, label in getattr(self, "_cards_to_style", []):
            style_as_card(widget, label=label)


def main() -> toga.App:
    return PulseSpike(
        formal_name="Pulse Spike",
        app_id="com.rebalance.pulse-spike",
    )


if __name__ == "__main__":
    main().main_loop()
