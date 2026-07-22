"""Fleet health for 3-Eyes (GH-195).

Answers "are my scheduled jobs OK?" across everything in the catalog — managed by
3-Eyes or not. One `launchctl list` call gives every loaded agent's last exit code;
we join that against the curated `catalog-notes.toml` set (so vendor noise is
excluded) and overlay the 3-Eyes failure-breaker state for managed jobs.
"""

from __future__ import annotations

import subprocess

from . import breakers, catalog


def _launchctl_list() -> dict[str, str]:
    """Map label → last-exit-status string from `launchctl list` (one call)."""
    out: dict[str, str] = {}
    try:
        proc = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return out
    for line in proc.stdout.splitlines()[1:]:            # skip PID/Status/Label header
        parts = line.split("\t")
        if len(parts) >= 3:
            out[parts[2].strip()] = parts[1].strip()     # status column
    return out


def scan() -> dict:
    """Return a structured health report over the catalogued automations."""
    notes = catalog.load_notes()
    listed = _launchctl_list()
    breaker = breakers.FailureBreaker()

    rows, ok, failing, not_loaded = [], 0, 0, 0
    for label, note in sorted(notes.get("agent", {}).items()):
        if note.get("status") == "system":
            continue
        loaded = label in listed
        status = listed.get(label, "")
        if not loaded:
            health = "not-loaded"
            not_loaded += 1
        elif status in ("0", "-", ""):
            health = "ok"
            ok += 1
        else:
            health = f"FAIL(exit {status})"
            failing += 1
        row = {"label": label, "system": note.get("system"), "status_note": note.get("status"),
               "loaded": loaded, "last_exit": status or "-", "health": health}
        if note.get("status") == "managed":
            job_id = label.rsplit(".", 1)[-1]
            bst = breaker.status(job_id)
            row["breaker"] = "OPEN" if bst.get("quarantined") else "closed"
        rows.append(row)

    drift = catalog.drift(notes)
    return {
        "ok": ok, "failing": failing, "not_loaded": not_loaded,
        "unclassified": drift["new"], "removed": drift["removed"],
        "rows": rows,
    }


def format_report(report: dict | None = None) -> str:
    r = report or scan()
    lines = [
        f"Fleet health: {r['ok']} ok · {r['failing']} FAILING · {r['not_loaded']} not-loaded"
        + (f" · {len(r['unclassified'])} unclassified" if r["unclassified"] else ""),
        "",
    ]
    for row in r["rows"]:
        mark = "✅" if row["health"] == "ok" else ("❌" if "FAIL" in row["health"] else "◦")
        extra = f"  breaker={row['breaker']}" if "breaker" in row else ""
        lines.append(f"  {mark} {row['label']:<44} {row['health']}{extra}")
    if r["unclassified"]:
        lines += ["", "⚠️  Unclassified (not in catalog-notes.toml):"]
        lines += [f"    - {lbl}" for lbl in r["unclassified"]]
    return "\n".join(lines)
