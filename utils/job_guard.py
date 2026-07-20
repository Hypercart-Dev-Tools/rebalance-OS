#!/usr/bin/env python3
"""Single-instance + memory-ceiling guard for long-running local jobs (GH-172).

Context — on 2026-07-19 the Mac Studio hard kernel-panicked (AppleARMWatchdogTimer,
90s watchdogd starvation) because three unbounded Python embedding runs stacked to
~90 GB resident on a 68.7 GB machine. Nothing in either embedding stack prevented
concurrent invocation, and nothing aborted before the VM compressor saturated.

This module supplies the two missing primitives, independent of any one job:

  1. SingleInstanceLock — an advisory ``flock`` on a named lockfile. A second run
     either REFUSES (default) or REPLACES the incumbent. Stale locks left by a
     killed process are reclaimed automatically.
  2. MemoryCeiling — a watchdog thread that samples the guarded process tree's
     RSS *and* system-available memory, and aborts the job CLEANLY (SIGTERM, then
     SIGKILL after a grace period) before the machine starts thrashing.

Deliberately stdlib-only (no psutil): this has to run under the system python3,
inside launchd jobs, and inside the rebalance venv without an install step.

Two usage modes.

In-process — wrap the body of a Python job::

    from job_guard import guard

    with guard("ask-self-ingest", max_rss_gb=24):
        run_the_ingest()

Wrapper — guard any command, including non-Python ones. The ceiling then covers
the whole child process tree::

    python3 utils/job_guard.py --name ask-self-ingest --max-rss-gb 24 -- \
        python3 ask_self/ask_self_ingest.py --repo .

Exit codes in wrapper mode:
    0    child exited 0
    3    another instance holds the lock (``--on-conflict refuse``)
    4    memory ceiling tripped; the job was terminated
    143  evicted by a later ``--on-conflict replace`` run (child tree reaped)
    else the child's own exit status

Installed on the embedding path as of GH-172. #174 landed this module with zero
callers; the wiring followed once attribution was resolved. The 45 GB belonged to
the **HiQS signal / activity RAG** (``src/rebalance/ingest/embedder.py``,
Qwen3-Embedding-0.6B via MLX) — NOT the ask_self codebase index, which is Gemini
and was ruled out. ``rebalance.ingest._job_guard`` loads this module by path and
applies :func:`guard` to ``embed_chunks`` and ``embed_pending``.

Guard the *leaves*, never the facades: ``embed_vault_chunks`` and
``embed_semantic_pending`` delegate to those leaves, and guarding both layers
would take the same ``flock`` twice in one process and self-deadlock.

Operator reference: UPGRADE.md § "Embedding job guard (GH-172)".
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

GIB = 1024 ** 3

#: Where lockfiles live. Kept out of the repo so worktrees share one namespace —
#: two clones of rebalance-OS running the same job must still collide.
LOCK_DIR = Path(
    os.environ.get("JOB_GUARD_LOCK_DIR", Path.home() / ".cache" / "rebalance-os" / "locks")
)

#: Fraction of physical RAM a single guarded job may hold before it is aborted.
DEFAULT_MAX_RSS_FRACTION = 0.35

#: Abort if system-available memory falls below this fraction of physical RAM,
#: regardless of how well-behaved *this* job is. This is the defence against
#: stacked runs: the newcomer notices the machine is already starved and bails.
DEFAULT_MIN_AVAILABLE_FRACTION = 0.12

#: Never let the available-memory floor drop below this absolute value.
MIN_AVAILABLE_FLOOR = 4 * GIB

DEFAULT_POLL_SECONDS = 5.0
DEFAULT_GRACE_SECONDS = 20.0


class GuardError(RuntimeError):
    """Base class for guard failures."""


class InstanceConflict(GuardError):
    """Another instance of this job already holds the lock."""


class MemoryCeilingExceeded(GuardError):
    """The job tripped the RSS ceiling or the system-available floor."""


class _Evicted(BaseException):
    """Raised in the wrapper's main thread when a replacing run SIGTERMs it.

    BaseException, not Exception: it must not be swallowed by a broad
    ``except Exception`` between the handler and the teardown.
    """


# --------------------------------------------------------------------------- #
# Memory probing
# --------------------------------------------------------------------------- #

def _sysctl(name: str) -> str | None:
    try:
        out = subprocess.run(
            ["sysctl", "-n", name], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def total_memory_bytes() -> int:
    """Physical RAM. Returns 0 when it cannot be determined."""
    if sys.platform == "darwin":
        raw = _sysctl("hw.memsize")
        return int(raw) if raw and raw.isdigit() else 0

    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    return 0


def available_memory_bytes() -> int:
    """Memory the OS could hand out without swapping. 0 when undeterminable.

    On macOS this is free + inactive + speculative pages. Inactive pages are
    reclaimable, so counting only ``free`` would report starvation on a healthy
    machine and abort every job. Purgeable/compressed pages are excluded because
    by the time they dominate, the compressor is already the problem.
    """
    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=5
            )
        except (OSError, subprocess.SubprocessError):
            return 0
        if out.returncode != 0:
            return 0

        page_size = 4096
        header = re.search(r"page size of (\d+) bytes", out.stdout)
        if header:
            page_size = int(header.group(1))

        pages = 0
        wanted = ("Pages free:", "Pages inactive:", "Pages speculative:")
        for line in out.stdout.splitlines():
            for key in wanted:
                if line.startswith(key):
                    pages += int(line.split(":")[1].strip().rstrip("."))
        return pages * page_size

    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    return 0


def tree_rss_bytes(pid: int) -> int:
    """Resident memory of ``pid`` plus every descendant, in bytes.

    Uses ``ps`` rather than /proc so one implementation covers macOS and Linux.
    A worker pool's memory lives in its children, so summing the tree is the
    only measurement that would have caught the GH-172 blowup.
    """
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,rss="], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    if out.returncode != 0:
        return 0

    children: dict[int, list[int]] = {}
    rss: dict[int, int] = {}
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            this_pid, ppid, kb = (int(p) for p in parts)
        except ValueError:
            continue
        rss[this_pid] = kb * 1024
        children.setdefault(ppid, []).append(this_pid)

    total = 0
    stack = [pid]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        total += rss.get(current, 0)
        stack.extend(children.get(current, ()))
    return total


def _fmt_gb(value: int) -> str:
    return f"{value / GIB:.1f} GB"


# --------------------------------------------------------------------------- #
# Single-instance lock
# --------------------------------------------------------------------------- #

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


class SingleInstanceLock:
    """Advisory whole-file ``flock`` keyed by job name.

    ``flock`` is released by the kernel when the holder dies, so a killed job
    never leaves a lock that blocks the next run — the failure mode a bare PID
    file has. The PID written into the file is advisory, for diagnostics and for
    ``on_conflict="replace"``.
    """

    def __init__(self, name: str, lock_dir: Path | None = None) -> None:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("_") or "job"
        self.name = name
        self.path = (lock_dir or LOCK_DIR) / f"{safe}.lock"
        self._fh = None

    def _read_state(self) -> dict:
        """Lockfile contents as a dict. Tolerates a bare-PID legacy file."""
        try:
            raw = self.path.read_text().strip()
        except OSError:
            return {}
        if not raw:
            return {}
        try:
            state = json.loads(raw)
        except ValueError:
            return {"pid": int(raw)} if raw.isdigit() else {}
        return state if isinstance(state, dict) else {}

    def holder_pid(self) -> int | None:
        """PID recorded in the lockfile, if it names a live process."""
        pid = self._read_state().get("pid")
        if not isinstance(pid, int):
            return None
        return pid if _pid_alive(pid) else None

    def acquire(self, on_conflict: str = "refuse", replace_grace: float = 15.0) -> None:
        """Take the lock, or raise :class:`InstanceConflict`.

        on_conflict="refuse"  — raise, leaving the incumbent untouched (default;
                                the safe choice for anything that writes).
        on_conflict="replace" — SIGTERM the incumbent, wait ``replace_grace``
                                seconds, SIGKILL it, then take the lock. This is
                                the "re-running the embeddings" ergonomic the
                                operator expected and did not get.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+")

        if self._try_flock():
            self._write_state()
            return

        if on_conflict == "replace":
            if self._evict(replace_grace):
                self._write_state()
                return

        pid = self.holder_pid()
        self.release()
        raise InstanceConflict(
            f"job {self.name!r} is already running"
            + (f" (pid {pid})" if pid else "")
            + f"; lock: {self.path}"
        )

    def _try_flock(self) -> bool:
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _write_state(self, **extra) -> None:
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(json.dumps({"pid": os.getpid(), **extra}))
        self._fh.flush()

    def record_child_group(self, pgid: int) -> None:
        """Record the guarded child's process group in the lockfile.

        Load-bearing for ``--on-conflict replace``: the child runs in its OWN
        session, so it is unreachable via the wrapper's process group. Without
        this, an evictor that has to SIGKILL an unresponsive wrapper leaves the
        grandchildren resident — the exact stacking GH-172 is about.
        """
        if self._fh is None:
            return
        self._write_state(child_pgid=pgid)

    def _evict(self, grace: float) -> bool:
        """Displace the incumbent and take the lock. True if we now hold it.

        Success is measured by ACQUIRING THE FLOCK, not by the incumbent's PID
        disappearing. PID liveness is the wrong signal: ``kill(pid, 0)`` succeeds
        against a zombie, so a reaped-but-unwaited incumbent reads as alive
        forever, and a bare "SIGKILL then retry once" races the kernel's lock
        release. The flock is the only ground truth about who owns the job.
        """
        state = self._read_state()
        pid = state.get("pid")
        child_pgid = state.get("child_pgid")
        if not isinstance(pid, int) or pid == os.getpid():
            return self._try_flock()

        def _signal_all(sig: int) -> None:
            try:
                os.kill(pid, sig)
            except OSError:
                pass
            # The incumbent's child runs in its OWN session, so it is not
            # reachable via the wrapper's group. A cooperative wrapper reaps it
            # on SIGTERM; a SIGKILLed one never gets the chance. Signal it
            # directly so eviction is total either way.
            if isinstance(child_pgid, int) and child_pgid > 0:
                try:
                    os.killpg(child_pgid, sig)
                except OSError:
                    pass

        for sig in (signal.SIGTERM, signal.SIGKILL):
            _signal_all(sig)
            deadline = time.monotonic() + (grace if sig == signal.SIGTERM else 5.0)
            while time.monotonic() < deadline:
                if self._try_flock():
                    return True
                time.sleep(0.1)
        return self._try_flock()

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            self._fh.close()
        finally:
            self._fh = None

    def __enter__(self) -> "SingleInstanceLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


def _terminate_group(pgid: int, grace: float) -> None:
    """SIGTERM a process GROUP, escalating to SIGKILL after ``grace`` seconds."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        return

    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if not _group_alive(pgid):
            return
        time.sleep(0.25)

    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Memory ceiling
# --------------------------------------------------------------------------- #

class MemoryCeiling:
    """Background watchdog that aborts a process tree before the machine dies.

    Two independent trip conditions, because they catch different failures:

      * RSS ceiling — this job leaked or accumulated (GH-172 defects 2 and 3,
        the ``out = [None] * len(texts)`` accumulation).
      * Available-memory floor — the *machine* is starved, whoever is at fault
        (GH-172 defect 1, stacked concurrent runs).
    """

    def __init__(
        self,
        pid: int | None = None,
        max_rss_bytes: int | None = None,
        min_available_bytes: int | None = None,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        on_trip=None,
        log=None,
    ) -> None:
        total = total_memory_bytes()
        self.pid = pid or os.getpid()
        self.total = total
        self.max_rss = max_rss_bytes or int(total * DEFAULT_MAX_RSS_FRACTION) or None
        self.min_available = min_available_bytes or max(
            int(total * DEFAULT_MIN_AVAILABLE_FRACTION), MIN_AVAILABLE_FLOOR if total else 0
        ) or None
        self.poll_seconds = poll_seconds
        self.on_trip = on_trip
        self.log = log or (lambda msg: print(f"[job-guard] {msg}", file=sys.stderr))
        self.tripped_reason: str | None = None
        self.peak_rss = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def preflight(self) -> None:
        """Refuse to even start when the machine is already starved.

        Cheaper than starting a 40-minute job that will be killed at minute two,
        and it is the check that turns a stacked run into a clean error instead
        of a kernel panic.
        """
        if not self.min_available:
            return
        available = available_memory_bytes()
        if available and available < self.min_available:
            raise MemoryCeilingExceeded(
                f"refusing to start: only {_fmt_gb(available)} available, "
                f"floor is {_fmt_gb(self.min_available)}"
            )

    def start(self) -> None:
        if self.total == 0:
            self.log("could not determine physical RAM; memory ceiling disabled")
            return
        self._thread = threading.Thread(target=self._run, name="job-guard", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.poll_seconds):
            reason = self._check()
            if reason:
                self.tripped_reason = reason
                self.log(f"MEMORY CEILING TRIPPED: {reason}")
                if self.on_trip:
                    self.on_trip(reason)
                return

    def _check(self) -> str | None:
        rss = tree_rss_bytes(self.pid)
        self.peak_rss = max(self.peak_rss, rss)
        if self.max_rss and rss > self.max_rss:
            return (
                f"process tree holds {_fmt_gb(rss)}, ceiling is {_fmt_gb(self.max_rss)}"
            )

        available = available_memory_bytes()
        if self.min_available and available and available < self.min_available:
            return (
                f"system available memory {_fmt_gb(available)} fell below "
                f"floor {_fmt_gb(self.min_available)} (this job: {_fmt_gb(rss)})"
            )
        return None

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_seconds + 1)
            self._thread = None


# --------------------------------------------------------------------------- #
# In-process entry point
# --------------------------------------------------------------------------- #

@contextmanager
def guard(
    name: str,
    max_rss_gb: float | None = None,
    min_available_gb: float | None = None,
    on_conflict: str = "refuse",
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    log=None,
):
    """Guard the calling process: single-instance lock + memory ceiling.

    On trip the watchdog raises :class:`MemoryCeilingExceeded` in the MAIN
    thread via ``signal.SIGTERM`` -> handler, so ``finally`` blocks still run and
    partial work is flushed. If the main thread is wedged inside a C extension
    and ignores it, the process is SIGKILLed after the grace period.
    """
    lock = SingleInstanceLock(name)
    lock.acquire(on_conflict=on_conflict)

    ceiling = MemoryCeiling(
        max_rss_bytes=int(max_rss_gb * GIB) if max_rss_gb else None,
        min_available_bytes=int(min_available_gb * GIB) if min_available_gb else None,
        poll_seconds=poll_seconds,
        log=log,
    )

    def _on_trip(reason: str) -> None:
        os.kill(os.getpid(), signal.SIGTERM)
        # Backstop: if SIGTERM is swallowed (native extension mid-allocation),
        # take the process down rather than let it reach the compressor cliff.
        time.sleep(DEFAULT_GRACE_SECONDS)
        os.kill(os.getpid(), signal.SIGKILL)

    ceiling.on_trip = _on_trip

    previous = signal.getsignal(signal.SIGTERM)

    def _handler(signum, frame):
        raise MemoryCeilingExceeded(ceiling.tripped_reason or "terminated by job guard")

    try:
        ceiling.preflight()
        signal.signal(signal.SIGTERM, _handler)
        ceiling.start()
        yield ceiling
    finally:
        ceiling.stop()
        try:
            signal.signal(signal.SIGTERM, previous)
        except (ValueError, TypeError):
            pass
        lock.release()


# --------------------------------------------------------------------------- #
# Wrapper CLI
# --------------------------------------------------------------------------- #

def run_guarded(
    name: str,
    argv: list[str],
    max_rss_gb: float | None = None,
    min_available_gb: float | None = None,
    on_conflict: str = "refuse",
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    grace_seconds: float = DEFAULT_GRACE_SECONDS,
) -> int:
    """Run ``argv`` as a guarded child process. Returns the exit code."""
    log = lambda msg: print(f"[job-guard] {msg}", file=sys.stderr)  # noqa: E731

    lock = SingleInstanceLock(name)
    try:
        lock.acquire(on_conflict=on_conflict, replace_grace=grace_seconds)
    except InstanceConflict as exc:
        log(str(exc))
        return 3

    try:
        ceiling = MemoryCeiling(
            max_rss_bytes=int(max_rss_gb * GIB) if max_rss_gb else None,
            min_available_bytes=int(min_available_gb * GIB) if min_available_gb else None,
            poll_seconds=poll_seconds,
            log=log,
        )
        try:
            ceiling.preflight()
        except MemoryCeilingExceeded as exc:
            log(str(exc))
            return 4

        log(
            f"starting {name!r}: rss ceiling {_fmt_gb(ceiling.max_rss or 0)}, "
            f"available floor {_fmt_gb(ceiling.min_available or 0)}"
        )

        # Own process group, so the whole tree dies together — a pool's workers
        # outliving their parent is how 90 GB stayed resident in GH-172.
        child = subprocess.Popen(argv, start_new_session=True)
        lock.record_child_group(child.pid)  # new session => pgid == pid
        ceiling.pid = child.pid
        ceiling.on_trip = lambda reason: _reap_child_tree(child, grace_seconds, log)
        ceiling.start()

        # A replacing run SIGTERMs THIS wrapper. Without a handler the wrapper
        # dies instantly and the child — in its own session — is orphaned, so
        # "replace" would stack processes instead of replacing them.
        def _on_term(signum, frame):
            raise _Evicted()

        previous_term = signal.signal(signal.SIGTERM, _on_term)

        try:
            code = child.wait()
        except _Evicted:
            log("evicted by a replacing run; tearing down child tree")
            _reap_child_tree(child, grace_seconds, log)
            return 143
        except KeyboardInterrupt:
            _reap_child_tree(child, grace_seconds, log)
            return 130
        finally:
            ceiling.stop()
            try:
                signal.signal(signal.SIGTERM, previous_term)
            except (ValueError, TypeError):
                pass

        log(f"{name!r} finished with exit {code}; peak tree RSS {_fmt_gb(ceiling.peak_rss)}")
        return 4 if ceiling.tripped_reason else code
    finally:
        lock.release()


def _reap_child_tree(child: subprocess.Popen, grace: float, log) -> None:
    """Terminate the guarded child's process group and REAP the child.

    The parent must ``waitpid`` rather than poll ``killpg(pgid, 0)``: a zombie
    still answers signal 0, so polling alone would block for the entire grace
    period on a child that has already exited.
    """
    try:
        pgid = os.getpgid(child.pid)
    except OSError:
        pgid = None

    log(f"terminating child tree {child.pid}")
    if pgid is not None:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            pass

    try:
        child.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        log(f"child {child.pid} ignored SIGTERM; sending SIGKILL")
        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log(f"child {child.pid} survived SIGKILL")

    # Sweep grandchildren that outlived the direct child (the reaped child no
    # longer confuses the liveness probe, so this poll is now meaningful).
    if pgid is not None and _group_alive(pgid):
        _terminate_group(pgid, min(grace, 5.0))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="job_guard",
        description="Run a long-running local job under a single-instance lock "
                    "and a memory ceiling (GH-172).",
    )
    parser.add_argument("--name", required=True, help="lock identity; same name = same lock")
    parser.add_argument(
        "--max-rss-gb", type=float, default=None,
        help=f"abort above this tree RSS "
             f"(default: {DEFAULT_MAX_RSS_FRACTION:.0%} of RAM)".replace("%", "%%"),
    )
    parser.add_argument(
        "--min-available-gb", type=float, default=None,
        help=f"abort below this system-available memory "
             f"(default: max({DEFAULT_MIN_AVAILABLE_FRACTION:.0%} of RAM, 4 GB))"
             .replace("%", "%%"),
    )
    parser.add_argument(
        "--on-conflict", choices=("refuse", "replace"), default="refuse",
        help="what to do when another instance holds the lock (default: refuse)",
    )
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--grace-seconds", type=float, default=DEFAULT_GRACE_SECONDS)
    parser.add_argument(
        "--status", action="store_true",
        help="report memory and lock state for --name, then exit",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- command to run")
    args = parser.parse_args(argv)

    if args.status:
        total = total_memory_bytes()
        lock = SingleInstanceLock(args.name)
        holder = lock.holder_pid()
        print(f"job:       {args.name}")
        print(f"lockfile:  {lock.path}")
        print(f"holder:    {holder if holder else 'none'}")
        print(f"total RAM: {_fmt_gb(total)}")
        print(f"available: {_fmt_gb(available_memory_bytes())}")
        if holder:
            print(f"tree RSS:  {_fmt_gb(tree_rss_bytes(holder))}")
        return 0

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("no command given; pass it after --")

    return run_guarded(
        args.name,
        command,
        max_rss_gb=args.max_rss_gb,
        min_available_gb=args.min_available_gb,
        on_conflict=args.on_conflict,
        poll_seconds=args.poll_seconds,
        grace_seconds=args.grace_seconds,
    )


if __name__ == "__main__":
    sys.exit(main())
