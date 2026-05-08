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

from dashboard import fetch_calendar_upcoming, _parse_iso, TZ  # type: ignore
from pulse_web import load_vault_path, parse_goals  # type: ignore


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

        hero_card = toga.Box(
            children=hero_children,
            style=Pack(
                direction=COLUMN,
                padding=22,
                background_color=PANEL,
            ),
        )

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


def main() -> toga.App:
    return PulseSpike(
        formal_name="Pulse Spike",
        app_id="com.rebalance.pulse-spike",
    )


if __name__ == "__main__":
    main().main_loop()
