"""Fleet health for 3-Eyes (GH-195).

Answers "are my scheduled jobs OK?" across everything in the catalog — managed by
3-Eyes or not. One `launchctl list` call gives every loaded agent's PID and last
exit code; we join that against the curated `catalog-notes.toml` set (so vendor
noise is excluded) and overlay the 3-Eyes failure-breaker state for managed jobs.

Two rules keep this honest, both learned from GH-146's misreads of the same
`launchctl list` output:

* **A live PID means RUNNING.** The status column holds the *previous* instance's
  exit code, so a `KeepAlive` server that was restarted (SIGTERM → `-15`) is
  healthy right now, not failing. Liveness comes from the PID column; the exit
  status is only meaningful for a job that is not currently running.
* **A probe that could not run reports `unknown`, never a verdict.** Inside a
  sandboxed shell `launchctl list` exits non-zero with no output; treating that
  as "nothing is loaded" made every job read `not-loaded` and the fleet look
  dormant instead of unreadable.
"""

from __future__ import annotations

import subprocess

from . import breakers, catalog


class LaunchctlUnavailable(RuntimeError):
    """`launchctl list` could not be consulted — the answer is unknown, not empty."""


def _launchctl_list() -> dict[str, tuple[str, str]]:
    """Map label → (pid, last-exit-status) from `launchctl list` (one call).

    Raises :class:`LaunchctlUnavailable` when launchctl cannot be reached, so the
    caller can tell "nothing is loaded" apart from "we were not able to look".
    """
    try:
        proc = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        raise LaunchctlUnavailable(f"could not run launchctl: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        why = detail[0][:160] if detail else "no output (a sandboxed shell blocks launchctl)"
        raise LaunchctlUnavailable(f"launchctl list exited {proc.returncode}: {why}")
    out: dict[str, tuple[str, str]] = {}
    for line in proc.stdout.splitlines()[1:]:            # skip PID/Status/Label header
        parts = line.split("\t")
        if len(parts) >= 3:
            out[parts[2].strip()] = (parts[0].strip(), parts[1].strip())
    return out


def scan() -> dict:
    """Return a structured health report over the catalogued automations."""
    notes = catalog.load_notes()
    breaker = breakers.FailureBreaker()

    listed: dict[str, tuple[str, str]] = {}
    probe_error = ""
    try:
        listed = _launchctl_list()
    except LaunchctlUnavailable as exc:
        probe_error = str(exc)
    available = not probe_error

    rows, ok, failing, not_loaded, unknown = [], 0, 0, 0, 0
    for label, note in sorted(notes.get("agent", {}).items()):
        if note.get("status") == "system":
            continue
        pid, status = listed.get(label, ("", ""))
        loaded = label in listed
        running = bool(pid) and pid.isdigit()
        if not available:
            health = "unknown"                  # could not look — say so, do not guess
            unknown += 1
        elif not loaded:
            health = "not-loaded"
            not_loaded += 1
        elif running:
            health = "ok"                       # live PID; `status` is the prior instance's
            ok += 1
        elif status in ("0", "-", ""):
            health = "ok"
            ok += 1
        else:
            health = f"FAIL(exit {status})"
            failing += 1
        row = {"label": label, "system": note.get("system"), "status_note": note.get("status"),
               "loaded": loaded if available else None,
               "pid": pid or "-",
               "running": running if available else None,
               "last_exit": status or "-", "health": health}
        if note.get("status") == "managed":
            job_id = label.rsplit(".", 1)[-1]
            bst = breaker.status(job_id)
            row["breaker"] = "OPEN" if bst.get("quarantined") else "closed"
        rows.append(row)

    drift = catalog.drift(notes)
    return {
        "ok": ok, "failing": failing, "not_loaded": not_loaded, "unknown": unknown,
        "launchctl_available": available, "probe_error": probe_error,
        "unclassified": drift["new"], "removed": drift["removed"],
        "rows": rows,
    }


def format_report(report: dict | None = None) -> str:
    r = report or scan()
    if not r.get("launchctl_available", True):
        return "\n".join([
            f"Fleet health: UNKNOWN — {r.get('unknown', 0)} jobs could not be read.",
            f"  launchctl could not be consulted: {r.get('probe_error', 'unavailable')}",
            "  This is NOT a clean bill of health. Re-run outside a sandboxed shell.",
        ])
    lines = [
        f"Fleet health: {r['ok']} ok · {r['failing']} FAILING · {r['not_loaded']} not-loaded"
        + (f" · {len(r['unclassified'])} unclassified" if r["unclassified"] else ""),
        "",
    ]
    for row in r["rows"]:
        mark = "✅" if row["health"] == "ok" else ("❌" if "FAIL" in row["health"] else "◦")
        extra = f"  breaker={row['breaker']}" if "breaker" in row else ""
        if row["health"] == "ok" and row.get("running") and row["last_exit"] not in ("0", "-", ""):
            extra += f"  (running; prior exit {row['last_exit']})"
        lines.append(f"  {mark} {row['label']:<44} {row['health']}{extra}")
    if r["unclassified"]:
        lines += ["", "⚠️  Unclassified (not in catalog-notes.toml):"]
        lines += [f"    - {lbl}" for lbl in r["unclassified"]]
    return "\n".join(lines)
