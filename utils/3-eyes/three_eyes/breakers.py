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
never in the repo.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from . import config

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
# Per-job failure breaker
# --------------------------------------------------------------------------- #

def _state_path() -> Path:
    return config.state_dir() / "breakers.json"


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(_state_path().read_text())
    except (OSError, ValueError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(path)  # atomic swap so a crash never leaves half a file


class FailureBreaker:
    """Consecutive-failure breaker with an on-disk counter per job."""

    def __init__(self) -> None:
        self._state = _load_state()

    def _job(self, job_id: str) -> dict[str, Any]:
        return self._state.setdefault(
            job_id, {"consecutive_failures": 0, "quarantined": False, "last": None}
        )

    def is_open(self, job_id: str) -> bool:
        """True when the job is quarantined and must not run."""
        return bool(self._job(job_id).get("quarantined"))

    def record(self, job_id: str, ok: bool, trip_after: int) -> bool:
        """Record a run outcome. Returns True if this call OPENED the breaker.

        ``trip_after <= 0`` disables the breaker for that job (never trips).
        """
        node = self._job(job_id)
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

        _save_state(self._state)
        return opened

    def reset(self, job_id: str) -> None:
        """Manually close a job's breaker (operator un-quarantine / resume)."""
        node = self._job(job_id)
        node["consecutive_failures"] = 0
        node["quarantined"] = False
        node["paused"] = False
        _save_state(self._state)

    def quarantine(self, job_id: str, reason: str = "manual pause") -> None:
        """Force a job's breaker open (operator pause). Cleared by :meth:`reset`."""
        node = self._job(job_id)
        node["quarantined"] = True
        node["paused"] = True
        node["reason"] = reason
        _save_state(self._state)

    def status(self, job_id: str) -> dict[str, Any]:
        return dict(self._job(job_id))


# --------------------------------------------------------------------------- #
# Guarded command execution (single-instance + memory ceiling)
# --------------------------------------------------------------------------- #

def run_guarded(job_id: str, argv: list[str], max_rss_gb: float | None = None) -> int:
    """Run ``argv`` under the GH-172 single-instance lock + memory ceiling.

    Returns the child's exit code (or the guard's: 3 = instance conflict,
    4 = memory ceiling tripped). If job_guard is somehow unavailable, we fail
    CLOSED — refuse to run rather than run unguarded.
    """
    if job_guard is None:  # pragma: no cover - defensive; guard must be present
        raise RuntimeError("job_guard is unavailable; refusing to run unguarded")
    return int(
        job_guard.run_guarded(
            f"3eyes.{job_id}",
            argv,
            max_rss_gb=max_rss_gb,
            on_conflict="refuse",
        )
    )
