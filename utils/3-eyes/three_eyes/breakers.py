"""Circuit breakers for 3-Eyes (GH-195).

Three layers, each catching a different failure:

  1. **Single-instance + memory ceiling** — reused wholesale from the existing
     ``utils/job_guard.py`` (GH-172, kernel-panic-hardened). We do NOT reimplement
     it; we load it by path and wrap ``run_guarded`` so every 3-Eyes job runs its
     command tree under a flock and an RSS/available-memory watchdog.
  2. **Per-job failure breaker** — after N consecutive *failures* a job's breaker
     OPENS and the job is quarantined. It recovers on its own: after a cooldown the
     breaker goes HALF-OPEN and permits exactly one probe run. The probe succeeding
     closes it; the probe failing re-opens it with a doubled cooldown. An explicit
     ``reset`` also closes it, and an operator ``quarantine`` (manual pause) never
     half-opens — a human pause stays paused until a human lifts it.
  3. **Global kill-switch** — a PANIC file or ``THREE_EYES_ENABLE=0`` halts every
     job at once (delegated to ``config.kill_switch_engaged``).

**Not every non-zero exit is a failure (GH-195 P6).** ``job_guard`` returns 3 when
another instance holds the lock and 75 when it refuses to start on a starved
machine. In both the command *never ran* — they mean "come back later", not "this
job is broken". Counting them as failures is what latched ``skill-sync``'s breaker
for a day: three transient memory refusals, caused by an unrelated regression in a
different project, permanently quarantined a perfectly healthy job. Use
:func:`classify_exit` and route ``deferred`` outcomes to :meth:`FailureBreaker.record_deferred`,
which deliberately leaves the failure counter alone.

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
import time
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
# Run outcomes (GH-195 P6)
# --------------------------------------------------------------------------- #

#: Exit codes meaning "the command never ran; retry later is the right response".
#: Mirrors ``job_guard.DEFERRED_EXIT_CODES``; the literals are the fallback for the
#: (defensive) case where job_guard could not be loaded, so a missing guard cannot
#: silently turn deferrals back into failures.
DEFERRED_EXIT_CODES: frozenset[int] = getattr(
    job_guard, "DEFERRED_EXIT_CODES", frozenset({3, 75})
)

#: How long a quarantined job waits before it is allowed one probe run. Doubles on
#: each failed probe, capped at :data:`MAX_COOLDOWN_SECONDS`, so a job that is
#: genuinely broken backs off instead of retrying hourly forever (invariant 6).
DEFAULT_COOLDOWN_SECONDS = 3600
MAX_COOLDOWN_SECONDS = 24 * 3600


def classify_exit(code: int) -> str:
    """Map a guarded command's exit code to ``ok`` / ``deferred`` / ``fail``.

    The whole point of P6: ``deferred`` is a third outcome, not a flavour of
    failure. See the module docstring for why conflating them was harmful.
    """
    if code == 0:
        return "ok"
    if code in DEFERRED_EXIT_CODES:
        return "deferred"
    return "fail"


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

        Callers must pass only genuine ok/fail outcomes here — a *deferred* run
        (guard refusal, instance conflict) belongs in :meth:`record_deferred`.
        Use :func:`classify_exit` rather than deciding with ``code == 0``.
        """
        with _locked("breakers"):
            state = _load_state()
            node = self._job(state, job_id)
            if ok:
                node["consecutive_failures"] = 0
                # An OPERATOR PAUSE outranks a successful run (agy review, P6 QA
                # finding 1b). Without this guard: a job is running, the operator
                # pauses it mid-flight, the run then succeeds, and `record` clears
                # `quarantined` while leaving `paused` set — `is_open` reads only
                # `quarantined`, so the next wake runs a job the operator had
                # explicitly stopped. Only `reset()` may lift a pause.
                if not node.get("paused"):
                    node["quarantined"] = False
                    # A success closes the breaker completely: clear the half-open
                    # bookkeeping too, or the next trip would inherit a stale
                    # (already doubled) cooldown from a previous episode.
                    for key in ("quarantined_at", "cooldown_seconds", "probe_at",
                                "skip_notice_at"):
                        node.pop(key, None)
            else:
                node["consecutive_failures"] = int(node.get("consecutive_failures", 0)) + 1
            node["last"] = "ok" if ok else "fail"

            opened = False
            if not ok and node.get("quarantined") and node.get("probe_at"):
                # A HALF-OPEN PROBE FAILED. The breaker is already open, so the
                # first-trip branch below will not fire — without this the cooldown
                # would never grow and a permanently broken job would probe again
                # every hour forever, which is the backoff invariant 6 promises and
                # the plain trip logic silently skips.
                self._rearm(node, doubled=True)
            elif (
                not ok
                and trip_after > 0
                and node["consecutive_failures"] >= trip_after
                and not node["quarantined"]
            ):
                node["quarantined"] = True
                self._rearm(node, doubled=False)
                opened = True

            _atomic_write(_state_path(), state)
            return opened

    @staticmethod
    def _rearm(node: dict[str, Any], *, doubled: bool) -> None:
        """(Re)start the quarantine clock, optionally with a doubled cooldown.

        Clears ``probe_at`` so the next probe is measured from now, and
        ``skip_notice_at`` so the operator gets one fresh notice per episode.
        """
        previous = int(node.get("cooldown_seconds") or 0)
        if doubled and previous:
            cooldown = min(previous * 2, MAX_COOLDOWN_SECONDS)
        else:
            cooldown = previous or DEFAULT_COOLDOWN_SECONDS
        node["cooldown_seconds"] = cooldown
        node["quarantined_at"] = time.time()
        node.pop("probe_at", None)
        node.pop("skip_notice_at", None)

    def record_deferred(self, job_id: str, code: int) -> None:
        """Record that a run was DEFERRED — it never happened (GH-195 P6).

        Deliberately does not touch ``consecutive_failures``: a machine that was
        too busy to start a job says nothing about whether that job works. Kept
        visible in the state file so ``status`` can show it, rather than being
        silently dropped.
        """
        with _locked("breakers"):
            state = _load_state()
            node = self._job(state, job_id)
            node["last"] = "deferred"
            node["last_deferred_code"] = int(code)
            node["deferred_runs"] = int(node.get("deferred_runs", 0)) + 1
            # RELEASE AN UNUSED PROBE CLAIM (agy review, P6 QA finding 5). If this
            # run was the half-open probe and it never actually executed, the claim
            # must go back — otherwise a deferral silently costs the job a whole
            # cooldown of recovery time. That is the same "a busy machine punished a
            # healthy job" mistake P6 exists to fix, reintroduced one level up.
            node.pop("probe_at", None)
            _atomic_write(_state_path(), state)

    def claim_probe(self, job_id: str, now: float | None = None) -> bool:
        """Half-open: atomically claim the single probe run for this cooldown.

        Returns True at most once per cooldown window, so concurrent wakes cannot
        both decide they are the probe. Returns False for a *manually* paused job:
        an operator pause is not a fault condition and must not self-heal.
        """
        now = time.time() if now is None else now
        with _locked("breakers"):
            state = _load_state()
            node = state.get(job_id)
            if not node or not node.get("quarantined") or node.get("paused"):
                return False
            cooldown = int(node.get("cooldown_seconds") or DEFAULT_COOLDOWN_SECONDS)
            # Anchor on the most recent of "when we tripped" and "when we last
            # probed", so a failed probe restarts the clock instead of letting
            # every subsequent wake qualify.
            since = max(
                float(node.get("quarantined_at") or 0.0),
                float(node.get("probe_at") or 0.0),
            )
            # NO CLOCK AT ALL = a breaker latched by the PRE-P6 code, which never
            # recorded one (agy review, P6 QA finding 6). Refusing here would strand
            # precisely the jobs this phase exists to rescue — skill-sync sat dead
            # for a day in exactly this state. Grant the probe immediately: such a
            # quarantine necessarily predates this deploy, so its cooldown is long
            # since served.
            if since <= 0.0:
                node["probe_at"] = now
                node.setdefault("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS)
                _atomic_write(_state_path(), state)
                return True
            if now - since < cooldown:
                return False
            node["probe_at"] = now
            _atomic_write(_state_path(), state)
            return True

    def should_notice_skip(self, job_id: str, now: float | None = None) -> bool:
        """True when a quarantined-skip is worth recording again.

        Without this, a 120 s job that is quarantined appends a finding 720 times a
        day — 72 of the 73 records in the live ``findings.jsonl`` were exactly that
        one line, which is how the evidence channel became useless. One notice per
        cooldown window is enough to show the job is still parked.
        """
        now = time.time() if now is None else now
        with _locked("breakers"):
            state = _load_state()
            node = state.get(job_id)
            if node is None:
                return False
            cooldown = int(node.get("cooldown_seconds") or DEFAULT_COOLDOWN_SECONDS)
            last = float(node.get("skip_notice_at") or 0.0)
            if last and now - last < cooldown:
                return False
            node["skip_notice_at"] = now
            _atomic_write(_state_path(), state)
            return True

    def reset(self, job_id: str) -> None:
        """Manually close a job's breaker (operator un-quarantine / resume)."""
        with _locked("breakers"):
            state = _load_state()
            node = self._job(state, job_id)
            node["consecutive_failures"] = 0
            node["quarantined"] = False
            node["paused"] = False
            # Clear the half-open bookkeeping: an operator resume is a clean
            # slate, so the next trip starts from the default cooldown.
            for key in ("quarantined_at", "cooldown_seconds", "probe_at", "skip_notice_at"):
                node.pop(key, None)
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
