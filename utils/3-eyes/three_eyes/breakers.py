"""Circuit breakers for 3-Eyes (GH-195).

Three layers, each catching a different failure:

  1. **Single-instance + memory ceiling** — reused wholesale from the existing
     ``utils/job_guard.py`` (GH-172, kernel-panic-hardened). We do NOT reimplement
     it; we load it by path and wrap ``run_guarded`` so every 3-Eyes job runs its
     command tree under a flock and an RSS/available-memory watchdog.
  2. **Per-job failure breaker** — after N consecutive failures a job's breaker
     OPENS: it is quarantined, stops being scheduled, and the operator is notified.
     A success (or an explicit reset) closes it again.
  3. **Global kill-switch** — a PANIC file or ``THREE_EYES_ENABLE=0`` halts every
     job at once (delegated to ``config.kill_switch_engaged``).

State (per-job failure counters, quarantine flags) lives as JSON in the state dir,
never in the repo. All read-modify-write of that state happens under an
interprocess ``flock`` (GH-195 review S6) so two jobs racing on the shared file
cannot lose a counter or crash on a competing ``replace()``.
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import config, registry

# --------------------------------------------------------------------------- #
# Load the existing job_guard (GH-172) by path — do not reinvent it
# --------------------------------------------------------------------------- #

_JOB_GUARD_PATH = config.ROOT.parent / "job_guard.py"   # utils/job_guard.py


def _load_job_guard():
    spec = importlib.util.spec_from_file_location("three_eyes._job_guard", _JOB_GUARD_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load job_guard from {_JOB_GUARD_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    job_guard = _load_job_guard()
except (OSError, ImportError):  # pragma: no cover - job_guard should always be present
    job_guard = None


# --------------------------------------------------------------------------- #
# Global kill-switch
# --------------------------------------------------------------------------- #

def global_halt() -> bool:
    """True when every job must halt (PANIC file or explicit disable)."""
    return config.kill_switch_engaged()


# --------------------------------------------------------------------------- #
# Interprocess-locked state (GH-195 review S6)
# --------------------------------------------------------------------------- #

@contextmanager
def _locked(name: str):
    """Hold an exclusive flock on ``<state>/<name>.lock`` for a read-modify-write."""
    lock_path = config.state_dir() / f"{name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


def _atomic_write(path: Path, data: dict) -> None:
    """Write ``data`` as JSON via a unique temp file + fsync + atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


def _state_path() -> Path:
    return config.state_dir() / "breakers.json"


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(_state_path().read_text())
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------------------------- #
# Per-job failure breaker
# --------------------------------------------------------------------------- #

class FailureBreaker:
    """Consecutive-failure breaker with a flock-guarded on-disk counter per job."""

    @staticmethod
    def _job(state: dict[str, Any], job_id: str) -> dict[str, Any]:
        return state.setdefault(
            job_id, {"consecutive_failures": 0, "quarantined": False, "last": None}
        )

    def is_open(self, job_id: str) -> bool:
        """True when the job is quarantined and must not run (lock-free read)."""
        return bool(_load_state().get(job_id, {}).get("quarantined"))

    def record(self, job_id: str, ok: bool, trip_after: int) -> bool:
        """Record a run outcome under lock. Returns True if this OPENED the breaker.

        ``trip_after <= 0`` disables the breaker for that job (never trips).
        """
        with _locked("breakers"):
            state = _load_state()
            node = self._job(state, job_id)
            if ok:
                node["consecutive_failures"] = 0
                node["quarantined"] = False
            else:
                node["consecutive_failures"] = int(node.get("consecutive_failures", 0)) + 1
            node["last"] = "ok" if ok else "fail"

            opened = False
            if (
                not ok
                and trip_after > 0
                and node["consecutive_failures"] >= trip_after
                and not node["quarantined"]
            ):
                node["quarantined"] = True
                opened = True

            _atomic_write(_state_path(), state)
            return opened

    def reset(self, job_id: str) -> None:
        """Manually close a job's breaker (operator un-quarantine / resume)."""
        with _locked("breakers"):
            state = _load_state()
            node = self._job(state, job_id)
            node["consecutive_failures"] = 0
            node["quarantined"] = False
            node["paused"] = False
            _atomic_write(_state_path(), state)

    def quarantine(self, job_id: str, reason: str = "manual pause") -> None:
        """Force a job's breaker open (operator pause). Cleared by :meth:`reset`."""
        with _locked("breakers"):
            state = _load_state()
            node = self._job(state, job_id)
            node["quarantined"] = True
            node["paused"] = True
            node["reason"] = reason
            _atomic_write(_state_path(), state)

    def status(self, job_id: str) -> dict[str, Any]:
        return dict(_load_state().get(job_id, {"consecutive_failures": 0, "quarantined": False, "last": None}))


# --------------------------------------------------------------------------- #
# Guarded command execution — allowlist-resolved, gated (GH-195 review B1/B4)
# --------------------------------------------------------------------------- #

def _resolve_argv(spec: dict) -> list[str]:
    """Resolve a command spec to an absolute argv against the repo root.

    B4: a relative ``exec`` (e.g. ``.venv/bin/python``) or a relative path arg
    (e.g. ``scripts/x.py``) must resolve against ``config.REPO_ROOT`` — NEVER the
    caller's CWD, or ``python -m three_eyes run <job>`` from another checkout would
    execute that checkout's binary. Non-path args (flags like ``--warn``) pass
    through unchanged.
    """
    exe = spec["exec"]
    if not Path(exe).is_absolute():
        exe = str(config.REPO_ROOT / exe)
    argv = [exe]
    for arg in spec.get("args", []):
        arg = str(arg)
        candidate = config.REPO_ROOT / arg
        if not Path(arg).is_absolute() and candidate.exists():
            argv.append(str(candidate))
        else:
            argv.append(arg)
    return argv


def run_job_command(job) -> int:
    """Run a job's ALLOWLISTED command under the GH-172 guard. The only exec path.

    B1: this is the sole way 3-Eyes ever spawns a process. It refuses to accept a
    free-form argv — the command is resolved from ``commands.allow`` by the job's
    ``command`` key, so an unlisted command cannot run. Gated: refuses when 3-Eyes
    is inert. Fails CLOSED if job_guard is unavailable (never runs unguarded).

    Returns the child's exit code (3 = instance conflict, 4 = memory ceiling).
    """
    if not config.three_eyes_active():
        raise PermissionError("3-Eyes is inert; refusing to run a job command")
    if job_guard is None:  # pragma: no cover - defensive; guard must be present
        raise RuntimeError("job_guard is unavailable; refusing to run unguarded")
    allow = registry.load_commands_allow()
    if job.command not in allow:
        raise registry.RegistryError(
            f"command {job.command!r} is not in commands.allow; refusing to run"
        )
    argv = _resolve_argv(allow[job.command])
    return int(
        job_guard.run_guarded(
            f"3eyes.{job.id}", argv, max_rss_gb=job.max_rss_gb, on_conflict="refuse"
        )
    )
