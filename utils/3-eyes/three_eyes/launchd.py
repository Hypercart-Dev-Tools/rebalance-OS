"""launchd adapter for 3-Eyes (GH-195).

Scheduling is *rendered from the registry*, never authored by hand — that is what
makes "the dashboard mirrors the jobs" and "the jobs mirror the registry" the same
statement. This module:

  * renders a launchd plist for a job (``plistlib``, so the XML is always valid),
  * OBSERVES every agent already in ``~/Library/LaunchAgents`` read-only (the
    observe-first posture: P0/P1 look but do not touch the existing 14 agents),
  * installs/uninstalls 3-Eyes-managed plists — GATED behind ``three_eyes_active``
    so an inert clone can never load anything.

Every 3-Eyes-managed label is prefixed ``com.rebalance-os.3eyes.`` so observation
can always tell "ours" from the pre-existing ``com.rebalance-os.*`` /
``com.neochro.*`` agents.
"""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

from . import config, registry

LABEL_PREFIX = "com.rebalance-os.3eyes."
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
SHIM = config.ROOT / "shims" / "run-job.sh"


def plist_label(job_id: str) -> str:
    return f"{LABEL_PREFIX}{job_id}"


def render_plist(job) -> bytes:
    """Render a job's launchd plist as bytes (valid XML via plistlib)."""
    program = ["/bin/bash", str(SHIM), job.id]
    spec: dict = {
        "Label": plist_label(job.id),
        "ProgramArguments": program,
        "WorkingDirectory": str(config.REPO_ROOT),
        "RunAtLoad": False,
        "ProcessType": "Background",
        "StandardOutPath": str(config.state_dir() / "logs" / f"{job.id}.out.log"),
        "StandardErrorPath": str(config.state_dir() / "logs" / f"{job.id}.err.log"),
    }
    interval = job.launchd_interval()
    calendar = job.launchd_calendar()
    if interval is not None:
        spec["StartInterval"] = interval
    elif calendar:
        spec["StartCalendarInterval"] = calendar
    return plistlib.dumps(spec)


def plist_path(job_id: str) -> Path:
    return LAUNCH_AGENTS_DIR / f"{plist_label(job_id)}.plist"


def _fmt_interval(n: int) -> str:
    if n and n % 3600 == 0:
        return f"every {n // 3600}h"
    if n and n % 60 == 0:
        return f"every {n // 60}m"
    return f"every {n}s"


def _fmt_calendar(cal) -> str:
    """Compact a launchd StartCalendarInterval into a readable schedule string."""
    def one(entry: dict) -> str:
        h, m = entry.get("Hour"), entry.get("Minute", 0)
        return f"daily {h:02d}:{m:02d}" if h is not None else f"hourly :{m:02d}"

    if isinstance(cal, dict):
        return one(cal)
    if isinstance(cal, list):
        if len(cal) == 1:
            return one(cal[0])
        has_hour = any("Hour" in e for e in cal)
        return f"{len(cal)}×/day" if has_hour else f"{len(cal)}×/hour"
    return "calendar"


def _read_plist(path: Path) -> dict | None:
    try:
        with open(path, "rb") as fh:
            return plistlib.load(fh)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None


def observe_existing() -> list[dict]:
    """Read-only inventory of EVERY user LaunchAgent, ours and pre-existing.

    This is the observe-first data source for the launchd-triage skill and the
    dashboard's "observed (unmanaged)" section. It never loads, unloads, or
    modifies anything.
    """
    out: list[dict] = []
    if not LAUNCH_AGENTS_DIR.exists():
        return out
    for path in sorted(LAUNCH_AGENTS_DIR.glob("*.plist")):
        data = _read_plist(path)
        if data is None:
            out.append({"label": path.stem, "path": str(path), "unreadable": True})
            continue
        label = data.get("Label", path.stem)
        program = data.get("ProgramArguments", [])
        schedule = "on-demand"
        if "StartInterval" in data:
            schedule = _fmt_interval(int(data["StartInterval"]))
        elif "StartCalendarInterval" in data:
            schedule = _fmt_calendar(data["StartCalendarInterval"])
        out.append(
            {
                "label": label,
                "path": str(path),
                "program": program,
                "schedule": schedule,
                "managed_by_3eyes": str(label).startswith(LABEL_PREFIX),
                "run_at_load": bool(data.get("RunAtLoad", False)),
            }
        )
    return out


def launchctl_state(label: str) -> str:
    """Best-effort live run-state for a label via ``launchctl print``.

    Read-only. Returns 'loaded', 'not-loaded', or 'unknown'. This is the volatile
    overlay shown by the CLI/MCP — it is deliberately NOT baked into the committed
    DASHBOARD.md (which mirrors the static registry, not live state).
    """
    try:
        uid = subprocess.run(["id", "-u"], capture_output=True, text=True, timeout=5)
        gui = f"gui/{uid.stdout.strip()}/{label}"
        proc = subprocess.run(
            ["launchctl", "print", gui], capture_output=True, text=True, timeout=8
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return "loaded" if proc.returncode == 0 else "not-loaded"


def install(job) -> Path:
    """Write + load a 3-Eyes-managed plist. GATED: inert clones cannot install.

    Raises PermissionError when 3-Eyes is not active, so activation is the only
    path by which anything is ever loaded.
    """
    if not config.three_eyes_active():
        raise PermissionError(
            "3-Eyes is inert (no runtime.env / THREE_EYES_ENABLE!=1); refusing to install a launchd agent"
        )
    problems = registry.validate()
    if problems:  # S8: never install from an invalid registry
        raise registry.RegistryError(
            "refusing to install launchd agent — registry invalid: " + "; ".join(problems)
        )
    if not job.enabled:  # S8: don't schedule a disabled job
        raise registry.RegistryError(f"job {job.id!r} is disabled; refusing to install")
    # Adoption REPLACES an emitter; it never adds a second one. Installing while the
    # incumbent is live is how #139's duplicate-issue defect comes back. Fail closed:
    # only a positive "not-loaded" clears the gate, so an unreadable probe blocks too.
    blocking = [(lbl, st) for lbl in job.supersedes
                if (st := launchctl_state(lbl)) != "not-loaded"]
    if blocking:
        raise registry.RegistryError(
            f"refusing to install {job.id!r}: it supersedes "
            + ", ".join(f"{lbl!r} ({st})" for lbl, st in blocking)
            + ". Retire the incumbent first (launchctl bootout gui/$UID/<label>), "
            + "then install."
        )
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.state_dir() / "logs").mkdir(parents=True, exist_ok=True)
    path = plist_path(job.id)
    path.write_bytes(render_plist(job))
    label = plist_label(job.id)
    uid = subprocess.run(["id", "-u"], capture_output=True, text=True, timeout=5).stdout.strip()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{label}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(path)], capture_output=True)
    return path


def uninstall(job_id: str) -> None:
    """Unload + remove a 3-Eyes-managed plist. GATED (unload also requires active)."""
    if not config.three_eyes_active():
        raise PermissionError("3-Eyes is inert; refusing to touch launchd")
    label = plist_label(job_id)
    uid = subprocess.run(["id", "-u"], capture_output=True, text=True, timeout=5).stdout.strip()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{label}"], capture_output=True)
    plist_path(job_id).unlink(missing_ok=True)
