"""Tests for the job guard's footprint measurement (GH-219 Lane 4).

These must be deterministic and host-independent. An earlier version passed only
when run from the repo root on the development machine, and failed in an isolated
worktree on three counts: it used the real `~/.cache` lock directory, it depended
on `total_memory_bytes()` probing real hardware, and it relied on host `ps`
visibility. A guard test that only passes on one machine cannot protect anything.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# `from utils import job_guard` resolves only when the repo root is importable.
# pytest puts `tests/` on sys.path (conftest, no __init__.py), not the root, so
# running from any other cwd fails at collection. Bootstrap it explicitly.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from utils import job_guard  # noqa: E402

GIB = 1024 ** 3
FAKE_TOTAL_RAM = 64 * GIB


@pytest.fixture
def isolated_guard(tmp_path, monkeypatch):
    """Detach the guard from host RAM, the real lock dir, and system memory pressure."""
    monkeypatch.setattr(job_guard, "LOCK_DIR", tmp_path / "locks")
    monkeypatch.setattr(job_guard, "total_memory_bytes", lambda: FAKE_TOTAL_RAM)
    # A healthy machine by default, so the preflight never masks what a test means
    # to exercise. Individual tests override this.
    monkeypatch.setattr(job_guard, "available_memory_bytes", lambda: 32 * GIB)
    return tmp_path


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_over_ceiling_trips_and_child_is_reaped(isolated_guard, monkeypatch):
    """1. A synthetic over-ceiling child trips the guard AND is actually killed.

    Asserting only `code == 4` is insufficient: `run_guarded` also returns 4 when
    the available-memory preflight refuses to start, so the assertion can pass
    without the child ever launching. The preflight is pinned healthy here and the
    child's liveness is checked directly.
    """
    script = isolated_guard / "spin.py"
    script.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")

    captured: dict[str, int] = {}
    real_popen = subprocess.Popen

    def capturing_popen(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        captured["pid"] = proc.pid
        return proc

    monkeypatch.setattr(subprocess, "Popen", capturing_popen)
    # Force the ceiling branch specifically, independent of what the child does.
    monkeypatch.setattr(
        job_guard, "tree_footprint_bytes", lambda pid: (10 * GIB, False, 0)
    )

    code = job_guard.run_guarded(
        name="test-over-ceiling",
        argv=[sys.executable, str(script)],
        max_footprint_gb=1.0,
        poll_seconds=0.1,
        grace_seconds=0.5,
    )

    assert code == 4
    assert "pid" in captured, "the child never launched — 4 came from the preflight"

    deadline = time.monotonic() + 5
    while _pid_alive(captured["pid"]) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not _pid_alive(captured["pid"]), "child survived the ceiling trip"


def test_healthy_footprint_does_not_trip(isolated_guard, monkeypatch):
    """2. A process at a healthy footprint does not trip."""
    monkeypatch.setattr(
        job_guard, "tree_footprint_bytes", lambda pid: (1.4 * GIB, False, 0)
    )
    ceiling = job_guard.MemoryCeiling(max_footprint_bytes=8 * GIB, poll_seconds=0.05)
    ceiling.start()
    time.sleep(0.3)
    ceiling.stop()
    assert ceiling.tripped_reason is None


def test_high_footprint_near_zero_rss(isolated_guard, monkeypatch):
    """3. The 07-27 signature: high phys_footprint with negligible RSS must trip.

    This is the case the RSS-based guard structurally could not see — it ran 233
    jobs on 2026-07-27 without tripping while the machine fell to 0.09 GB free.
    """
    monkeypatch.setattr(
        job_guard, "tree_footprint_bytes", lambda pid: (10 * GIB, False, 0)
    )
    ceiling = job_guard.MemoryCeiling(max_footprint_bytes=8 * GIB, poll_seconds=0.05)
    ceiling.start()
    time.sleep(0.3)
    ceiling.stop()

    assert ceiling.tripped_reason is not None
    assert "phys_footprint" in ceiling.tripped_reason


def _fake_libc(unreadable_pid: int):
    """A libc whose proc_pid_rusage reports -1 for one pid and a footprint for others."""

    class _ProcPidRusage:
        argtypes = None
        restype = None

        def __call__(self, pid, flavor, buf_ptr):
            if int(pid) == unreadable_pid:
                return -1
            buf_ptr._obj.ri_phys_footprint = 1024 if int(pid) == 1000 else 2048
            return 0

    class _FakeLibc:
        def __init__(self):
            self.proc_pid_rusage = _ProcPidRusage()

    return _FakeLibc()


def test_unreadable_pids_are_skipped_and_counted(isolated_guard, monkeypatch):
    """4. Unreadable pids (rc = -1) are skipped, counted, and never counted as 0.

    Reading a runaway as zero is precisely the blindness this lane exists to
    remove, so an unreadable process must be surfaced rather than absorbed.
    """
    monkeypatch.setattr(sys, "platform", "darwin")

    class _PsOut:
        returncode = 0
        stdout = "1000 1 100\n1001 1000 200\n1002 1000 300\n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _PsOut())
    monkeypatch.setattr(ctypes.util, "find_library", lambda name: "fake_c")
    monkeypatch.setattr(ctypes, "CDLL", lambda *a, **k: _fake_libc(unreadable_pid=1001))

    footprint, is_fallback, unreadable = job_guard.tree_footprint_bytes(1000)

    assert not is_fallback
    assert unreadable == 1
    assert footprint == 3072, "an unreadable pid must not silently contribute 0"

    ceiling = job_guard.MemoryCeiling(
        pid=1000, max_footprint_bytes=1000, poll_seconds=0.1
    )
    reason = ceiling._check()
    assert reason is not None
    assert "skipped 1 unreadable pids" in reason


def test_rss_fallback_announces_itself(isolated_guard, monkeypatch):
    """5. The RSS fallback works and says so — a degraded metric must never be silent."""
    monkeypatch.setattr(sys, "platform", "linux")

    class _PsOut:
        returncode = 0
        stdout = f"{os.getpid()} 1 2048\n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _PsOut())

    footprint, is_fallback, unreadable = job_guard.tree_footprint_bytes(os.getpid())
    assert is_fallback
    assert footprint > 0

    ceiling = job_guard.MemoryCeiling(max_footprint_bytes=1024, poll_seconds=0.1)
    reason = ceiling._check()
    assert reason is not None
    assert "RSS (fallback)" in reason


def test_footprint_env_var_is_read(monkeypatch):
    """6a. The footprint-named setting actually applies."""
    monkeypatch.delenv(job_guard.ENV_MAX_FOOTPRINT_GB_DEPRECATED, raising=False)
    monkeypatch.setenv(job_guard.ENV_MAX_FOOTPRINT_GB, "6.5")
    assert job_guard.env_max_footprint_gb(warn=lambda _m: None) == 6.5


def test_deprecated_rss_env_var_still_applies(monkeypatch):
    """6b. The old RSS-named variable keeps working, with a deprecation warning."""
    monkeypatch.delenv(job_guard.ENV_MAX_FOOTPRINT_GB, raising=False)
    monkeypatch.setenv(job_guard.ENV_MAX_FOOTPRINT_GB_DEPRECATED, "42.0")

    warnings: list[str] = []
    assert job_guard.env_max_footprint_gb(warn=warnings.append) == 42.0
    assert any("deprecated" in w for w in warnings)


def test_footprint_env_var_wins_over_deprecated_alias(monkeypatch):
    """6c. With both set, the footprint-named variable takes precedence."""
    monkeypatch.setenv(job_guard.ENV_MAX_FOOTPRINT_GB, "3.0")
    monkeypatch.setenv(job_guard.ENV_MAX_FOOTPRINT_GB_DEPRECATED, "42.0")
    assert job_guard.env_max_footprint_gb(warn=lambda _m: None) == 3.0


def test_non_numeric_env_var_is_ignored_not_fatal(monkeypatch):
    """6d. A typo must not crash the job the guard exists to protect."""
    monkeypatch.setenv(job_guard.ENV_MAX_FOOTPRINT_GB, "eight")
    monkeypatch.delenv(job_guard.ENV_MAX_FOOTPRINT_GB_DEPRECATED, raising=False)

    warnings: list[str] = []
    assert job_guard.env_max_footprint_gb(warn=warnings.append) is None
    assert any("non-numeric" in w for w in warnings)


def test_max_rss_bytes_still_maps_to_the_footprint_ceiling():
    """The bridge still passes max_rss_gb; that path must keep working."""
    ceiling = job_guard.MemoryCeiling(max_rss_bytes=12345)
    assert ceiling.max_footprint == 12345


def test_available_memory_counts_reclaimable_pages_not_just_free(monkeypatch):
    """A healthy Mac with little FREE but lots of INACTIVE must not read as starved.

    Regression test for the defect this lane briefly shipped: `available_memory_bytes`
    was narrowed to free-only without re-tuning the floor that consumes it. On a
    healthy machine (free 1.59 GB, inactive 21.46 GB, speculative 0.93 GB) that
    reported 1.58 GB against a 7.68 GB floor, so the preflight refused EVERY guarded
    job. macOS keeps cache in inactive by design, so free alone is not availability.

    Nothing caught it because every other test pins this function to a healthy
    constant for determinism — correct in itself, but it left the real
    implementation with no coverage at all.
    """
    monkeypatch.setattr(sys, "platform", "darwin")

    # Real vm_stat shape, 16 KiB pages: the healthy-machine numbers above.
    class _VmStatOut:
        returncode = 0
        stdout = (
            "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
            "Pages free:                              104000.\n"
            "Pages active:                            874626.\n"
            "Pages inactive:                         1406000.\n"
            "Pages speculative:                        61000.\n"
        )

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _VmStatOut())

    available = job_guard.available_memory_bytes()
    free_only = 104000 * 16384

    assert available > free_only, "inactive/speculative must count as reclaimable"
    assert available == (104000 + 1406000 + 61000) * 16384

    # And the consequence that actually matters: this machine must clear the floor.
    floor = max(
        int(FAKE_TOTAL_RAM * job_guard.DEFAULT_MIN_AVAILABLE_FRACTION),
        job_guard.MIN_AVAILABLE_FLOOR,
    )
    assert available > floor, (
        f"a healthy machine reads as starved: {available / GIB:.2f} GB < "
        f"{floor / GIB:.2f} GB floor — the guard would refuse every job"
    )
