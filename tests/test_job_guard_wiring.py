"""GH-172: the embedding leaves must actually be guarded.

#174 landed ``utils/job_guard.py`` with ZERO callers, so the crash path stayed
open. These tests exist to make that regression loud: they assert the guard is
wired to the leaves, that two concurrent runs cannot both hold the lock, and
that the escape hatches behave.

The suite-wide autouse fixture in conftest disables the guard; every test here
re-enables it explicitly via monkeypatch.
"""

from __future__ import annotations

import multiprocessing
import os
from pathlib import Path

import pytest

from rebalance.ingest import _job_guard


@pytest.fixture(autouse=True)
def _enable_guard(monkeypatch, tmp_path):
    """Re-enable the guard and isolate the lock dir from the real one."""
    monkeypatch.setenv("REBALANCE_JOB_GUARD", "1")
    monkeypatch.setenv("JOB_GUARD_LOCK_DIR", str(tmp_path / "locks"))
    # GH-231: isolate the memory ceiling too, not just the lock dir.
    #
    # Without this the guard falls back to DEFAULT_MAX_COMPRESSOR_FRACTION (0.25 of physical RAM,
    # utils/job_guard.py:132) and its preflight reads the machine's LIVE compressor usage. On a
    # 32 GB machine that is an 8 GB ceiling; anything above it makes preflight() refuse to start,
    # the child never launches, and the test fails as "child never acquired the lock" — a result
    # about the machine, not about the locking these tests exist to verify.
    #
    # This bites hardest while the memory work in #209/#210/#215 is in flight, because that work
    # is precisely about jobs driving the compressor to tens of GB. Invisible in CI, where the
    # Linux runner is not under pressure.
    #
    # A test that means to exercise the ceiling should set this to a value that trips it, rather
    # than relying on whatever the host happens to be doing.
    monkeypatch.setenv("REBALANCE_JOB_GUARD_MAX_COMPRESSOR_GB", "999")
    # The module caches its load; drop it so LOCK_DIR is re-read per test.
    _job_guard._module = None
    _job_guard._load_attempted = False
    _job_guard._warned = False
    yield
    _job_guard._module = None
    _job_guard._load_attempted = False


def test_job_guard_module_is_locatable():
    """The path bridge resolves to a real file in a normal checkout."""
    assert _job_guard.module_path().is_file(), (
        f"utils/job_guard.py not found at {_job_guard.module_path()}; "
        "the package bridge cannot guard anything"
    )
    assert _job_guard.available() is True


def test_embed_leaves_are_decorated():
    """Both embedding leaves must carry the guard.

    This is the regression test for the #174 gap — a guard with no callers.
    """
    from rebalance.ingest.embedder import embed_chunks
    from rebalance.ingest.semantic_index import embed_pending

    for fn in (embed_chunks, embed_pending):
        assert hasattr(fn, "__wrapped__"), (
            f"{fn.__name__} is not guarded — GH-172 crash path is open again"
        )


def test_facades_delegate_and_are_not_double_guarded():
    """Facades must NOT carry their own guard.

    ``embed_vault_chunks`` delegates to ``embed_chunks``; guarding both would
    take the same ``flock`` twice in one process and self-deadlock.
    """
    from rebalance.ingest.embedder import embed_vault_chunks
    from rebalance.ingest.semantic_index import embed_semantic_pending

    for fn in (embed_vault_chunks, embed_semantic_pending):
        assert not hasattr(fn, "__wrapped__"), (
            f"{fn.__name__} is double-guarded; it delegates to a guarded leaf "
            "and would deadlock on the shared flock"
        )


def test_both_leaves_share_one_lock_name():
    """Cumulative memory means they must serialise against each other."""
    assert _job_guard.EMBEDDING_LOCK == "rebalance-embed"


def test_disabled_by_env_is_a_noop(monkeypatch):
    monkeypatch.setenv("REBALANCE_JOB_GUARD", "0")
    assert _job_guard.enabled() is False
    with _job_guard.embedding_guard():
        pass  # must not raise, must not lock


@pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
def test_falsey_env_values_disable(monkeypatch, value):
    monkeypatch.setenv("REBALANCE_JOB_GUARD", value)
    assert _job_guard.enabled() is False


def test_missing_module_fails_open_with_warning(monkeypatch, tmp_path, capsys):
    """A missing guard must warn loudly but not block ingest."""
    monkeypatch.setenv("JOB_GUARD_MODULE", str(tmp_path / "nope.py"))
    _job_guard._module = None
    _job_guard._load_attempted = False
    _job_guard._warned = False

    assert _job_guard.available() is False
    with _job_guard.embedding_guard():
        pass

    err = capsys.readouterr().err
    assert "UNGUARDED" in err and "GH-172" in err


def _hold_lock(lock_dir: str, ready, release):
    """Child process: take the embedding lock, signal, wait, exit."""
    os.environ["JOB_GUARD_LOCK_DIR"] = lock_dir
    os.environ["REBALANCE_JOB_GUARD"] = "1"
    from rebalance.ingest import _job_guard as jg

    jg._module = None
    jg._load_attempted = False
    with jg.embedding_guard():
        ready.set()
        release.wait(timeout=30)


def test_two_concurrent_runs_cannot_both_acquire(tmp_path):
    """The #172 scenario: a re-run stacking on a resident run must be refused.

    This is the acceptance test named in #175's remediation.
    """
    guard_mod = _job_guard.load_job_guard()
    assert guard_mod is not None

    lock_dir = str(tmp_path / "locks")
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    child = ctx.Process(target=_hold_lock, args=(lock_dir, ready, release))
    child.start()
    try:
        assert ready.wait(timeout=60), "child never acquired the lock"

        # Second run, same lock name, while the first is still held.
        lock = guard_mod.SingleInstanceLock("rebalance-embed", lock_dir=Path(lock_dir))
        with pytest.raises(guard_mod.InstanceConflict):
            lock.acquire(on_conflict="refuse")
    finally:
        release.set()
        child.join(timeout=30)
        if child.is_alive():  # pragma: no cover
            child.terminate()
            child.join(timeout=10)


def test_peak_footprint_is_recorded_to_jsonl(tmp_path, monkeypatch):
    """GH-175 item 4: every guarded run leaves an attributable record.

    GH-172 could not be attributed because jetsam logs only ``Python``. This is
    the fix — a named, per-job peak-RSS row.
    """
    import json

    guard_mod = _job_guard.load_job_guard()
    log_path = tmp_path / "job_rss.jsonl"
    monkeypatch.setenv("JOB_GUARD_LOCK_DIR", str(tmp_path / "locks"))

    with guard_mod.guard("test-embed-job") as ceiling:
        pass
    guard_mod.record_peak_footprint("test-embed-job", ceiling, path=log_path)

    rows = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert rows, "no peak-RSS row written"
    row = rows[-1]
    assert row["job"] == "test-embed-job"
    assert row["peak_footprint_bytes"] >= 0
    assert "peak_footprint_gb" in row and "ts" in row and "pid" in row


def test_footprint_logging_never_breaks_the_job(tmp_path):
    """Observability must not be able to take down the thing it observes."""
    guard_mod = _job_guard.load_job_guard()
    ceiling = guard_mod.MemoryCeiling()
    # Unwritable target: a path under a regular file.
    bad = tmp_path / "afile"
    bad.write_text("x")
    guard_mod.record_peak_footprint("x", ceiling, path=bad / "nested" / "log.jsonl")  # must not raise


def test_guard_writes_a_record_on_its_own(tmp_path, monkeypatch):
    """The contextmanager records without the caller doing anything."""
    import json

    guard_mod = _job_guard.load_job_guard()
    log_path = tmp_path / "auto.jsonl"
    monkeypatch.setenv("JOB_GUARD_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(guard_mod, "RSS_LOG_PATH", log_path)

    with guard_mod.guard("auto-recorded-job"):
        pass

    rows = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert any(r["job"] == "auto-recorded-job" for r in rows)
    assert rows[-1]["duration_s"] is not None


def test_lock_is_released_after_guard_exits(tmp_path):
    """Sequential passes must not block each other (index_ops calls both)."""
    guard_mod = _job_guard.load_job_guard()
    lock_dir = Path(str(tmp_path / "locks"))

    for _ in range(3):
        lock = guard_mod.SingleInstanceLock("rebalance-embed", lock_dir=lock_dir)
        lock.acquire(on_conflict="refuse")
        lock.release()
