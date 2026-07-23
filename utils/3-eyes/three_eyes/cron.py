"""cron adapter for 3-Eyes (GH-195) — a portable alternative to launchd.

Same registry source as ``launchd.py``: a job's ``[schedule.cron] expr`` renders
to a crontab line that execs the same one-line shim. Installing/uninstalling the
crontab block is GATED behind ``three_eyes_active`` — an inert clone never writes
a user's crontab.

The managed block is delimited by sentinel comments so 3-Eyes only ever rewrites
its own lines and leaves the operator's other cron entries untouched.
"""

from __future__ import annotations

import subprocess

from . import config, registry

BEGIN = "# >>> 3-eyes managed (GH-195) >>>"
END = "# <<< 3-eyes managed (GH-195) <<<"
SHIM = config.ROOT / "shims" / "run-job.sh"


def render_cron_line(job) -> str | None:
    """Render one crontab line for a job, or None when it has no cron expr.

    B2: refuses to render an unsafe expr or job id — both are validated so neither
    can smuggle a shell command into the crontab line. Raises RegistryError rather
    than emit a poisoned line.
    """
    expr = job.cron_expr()
    if not expr:
        return None
    problem = registry.cron_expr_problem(expr)
    if problem:
        raise registry.RegistryError(f"{job.id}: {problem}")
    if not registry.JOB_ID_RE.match(job.id):
        raise registry.RegistryError(f"unsafe job id {job.id!r} for cron")
    return f"{expr} /bin/bash {SHIM} {job.id}"


def render_block(jobs) -> str:
    """Render the full managed crontab block from the registry.

    S8: a ``enabled = false`` job is NOT scheduled — it is skipped here, matching
    launchd's refusal, so "disabled" prevents installation, not just runtime skip.
    """
    lines = [BEGIN]
    for job in jobs:
        if not job.enabled:
            continue
        line = render_cron_line(job)
        if line:
            lines.append(line)
    lines.append(END)
    return "\n".join(lines) + "\n"


def _current_crontab() -> str:
    try:
        proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def _strip_managed(crontab: str) -> str:
    """Remove any existing 3-Eyes managed block, preserving everything else."""
    out, skipping = [], False
    for line in crontab.splitlines():
        if line.strip() == BEGIN:
            skipping = True
            continue
        if line.strip() == END:
            skipping = False
            continue
        if not skipping:
            out.append(line)
    return "\n".join(out).strip("\n")


def install(jobs) -> None:
    """Replace the managed crontab block. GATED + validated (GH-195 review B2/S8).

    Refuses when 3-Eyes is inert, and refuses to write anything if the registry
    has ANY validation problem — so a malformed cron expr or unsafe job id can
    never reach the crontab.
    """
    if not config.three_eyes_active():
        raise PermissionError("3-Eyes is inert; refusing to write crontab")
    problems = registry.validate()
    if problems:
        raise registry.RegistryError(
            "refusing to install crontab — registry invalid: " + "; ".join(problems)
        )
    preserved = _strip_managed(_current_crontab())
    new = (preserved + "\n\n" if preserved else "") + render_block(jobs)
    subprocess.run(["crontab", "-"], input=new, text=True, timeout=8)


def uninstall() -> None:
    """Remove the managed crontab block only. GATED."""
    if not config.three_eyes_active():
        raise PermissionError("3-Eyes is inert; refusing to write crontab")
    preserved = _strip_managed(_current_crontab())
    subprocess.run(["crontab", "-"], input=preserved + "\n", text=True, timeout=8)
