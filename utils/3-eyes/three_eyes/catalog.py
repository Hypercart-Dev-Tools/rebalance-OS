"""Master automation catalog (GH-195) — CATALOG.md generator.

CATALOG.md is the human master list of EVERY scheduled automation on this machine,
managed by 3-Eyes or not. Unlike DASHBOARD.md (a deterministic mirror of the TOML
registry, committed + CI-checked), CATALOG.md is:

  * **machine-specific** — it reflects this device's `~/Library/LaunchAgents`, so it
    is gitignored (Time Machine covers backup); and
  * **generated** from committed curation (`registry/catalog-notes.toml`) ⋈ this
    device's live `three_eyes observe`. New agents the notes don't cover surface as
    "unclassified — needs triage" so nothing on the machine stays invisible.

`three_eyes catalog --check` reports whether CATALOG.md is stale (agents added or
removed, or the render drifted); `--write` regenerates it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from . import config, launchd

CATALOG = config.ROOT / "CATALOG.md"
NOTES = config.REGISTRY_DIR / "catalog-notes.toml"

#: Prefixes we auto-classify as vendor/OS (ignored, not "unclassified").
VENDOR_PREFIXES = ("com.google.", "com.setapp.", "homebrew.", "com.apple.")

STATUS_EMOJI = {
    "managed": "🟢", "to-adopt": "🎯", "observe": "👁", "server": "⚙️", "system": "⚙️",
}


def load_notes() -> dict:
    try:
        with open(NOTES, "rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _classify(label: str, notes: dict) -> dict | None:
    """Return the note for a label, or None if vendor (ignore) / unclassified."""
    agents = notes.get("agent", {})
    if label in agents:
        return agents[label]
    if any(label.startswith(p) for p in VENDOR_PREFIXES):
        return {"system": "_vendor", "status": "system", "desc": "vendor/OS agent"}
    return None


def drift(notes: dict | None = None) -> dict:
    """Compare live agents vs the curated notes. Returns {new, removed}."""
    notes = notes or load_notes()
    known = set(notes.get("agent", {}))
    live = {a["label"] for a in launchd.observe_existing() if not a.get("unreadable")}
    new = sorted(
        lbl for lbl in live
        if lbl not in known and not any(lbl.startswith(p) for p in VENDOR_PREFIXES)
    )
    removed = sorted(known - live)
    return {"new": new, "removed": removed}


def render(notes: dict | None = None) -> str:
    notes = notes or load_notes()
    order = notes.get("system_order", [])
    names = notes.get("system_names", {})
    agents = launchd.observe_existing()
    by_label = {a["label"]: a for a in agents}

    # Bucket each live agent into a system (or unclassified / vendor).
    buckets: dict[str, list[tuple[str, dict, dict]]] = {s: [] for s in order}
    unclassified: list[str] = []
    vendor = 0
    for label, a in sorted(by_label.items()):
        if a.get("unreadable"):
            continue
        note = _classify(label, notes)
        if note is None:
            unclassified.append(label)
            continue
        sys = note.get("system", "_vendor")
        if sys == "_vendor":
            vendor += 1
            continue
        buckets.setdefault(sys, []).append((label, note, a))

    d = drift(notes)
    managed = sum(1 for _, n, _ in _all(buckets) if n.get("status") == "managed")
    to_adopt = sum(1 for _, n, _ in _all(buckets) if n.get("status") == "to-adopt")

    lines = [
        "# 3-Eyes — Master Automation Catalog",
        "",
        "> **GENERATED — do not hand-edit.** Machine-specific (this device's LaunchAgents), so it is",
        "> **gitignored**; Time Machine covers backup. Rendered from `registry/catalog-notes.toml`",
        "> (committed curation) ⋈ live `three_eyes observe`. Refresh: `python -m three_eyes catalog --write`.",
        ">",
        "> Companion to [`DASHBOARD.md`](DASHBOARD.md) (what 3-Eyes *manages*) and",
        "> `~/bin/servers.md` (ports/long-running servers).",
        "",
        f"**Inventory:** {len([a for a in agents if not a.get('unreadable')])} launchd agents "
        f"({managed} 🟢 managed · {to_adopt} 🎯 to-adopt · {vendor} vendor/OS ignored"
        + (f" · **{len(unclassified)} ⚠️ unclassified**" if unclassified else "") + ").",
        "",
        "Legend: 🟢 managed · 🎯 to-adopt · 👁 observe-only · ⚙️ server/system.",
        "",
    ]

    if d["new"]:
        lines += [
            "## ⚠️ Unclassified — needs triage",
            "",
            "New agents not in `catalog-notes.toml`. Add an `[agent.\"<label>\"]` block to file them:",
            "",
        ]
        lines += [f"- `{lbl}` — {by_label[lbl].get('schedule', '?')}" for lbl in d["new"]]
        lines += [""]

    for sys in order:
        rows = buckets.get(sys, [])
        if not rows:
            continue
        lines += [f"## {names.get(sys, sys)}", "",
                  "| Automation | Does what | Schedule | Status |",
                  "|---|---|---|---|"]
        for label, note, a in rows:
            emoji = STATUS_EMOJI.get(note.get("status", "observe"), "👁")
            lines.append(
                f"| `{label}` | {note.get('desc', '')} | {a.get('schedule', '?')} "
                f"| {emoji} {note.get('status', 'observe')} |"
            )
        lines.append("")

    if d["removed"]:
        lines += ["## Curated but not currently present", "",
                  "In `catalog-notes.toml` but not loaded on this device (uninstalled / renamed?):", ""]
        lines += [f"- `{lbl}`" for lbl in d["removed"]]
        lines += [""]

    # Adoption suggestions, by priority.
    prio = sorted(
        ((n.get("priority"), lbl, n) for lbl, n, _ in _all(buckets) if n.get("priority")),
        key=lambda t: t[0],
    )
    if prio:
        lines += ["## Suggested next adoptions", ""]
        lines += [f"{p}. `{lbl}` — {n.get('desc', '')}" for p, lbl, n in prio]
        lines += [""]
    return "\n".join(lines)


def _all(buckets):
    for rows in buckets.values():
        yield from rows


def write() -> Path:
    CATALOG.write_text(render())
    return CATALOG


def check() -> bool:
    """True when CATALOG.md matches a fresh render (agents unchanged, no drift)."""
    try:
        return CATALOG.read_text() == render()
    except OSError:
        return False
