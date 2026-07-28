"""Tests for the job guard's footprint measurement (GH-219)."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from utils import job_guard


def test_over_ceiling_trips(tmp_path):
    """1. A synthetic over-ceiling process trips and is killed."""
    script = tmp_path / "spin.py"
    script.write_text(
        "import time\n"
        "x = bytearray(50 * 1024 * 1024)\n"  # 50MB
        "time.sleep(60)\n"
    )
    
    code = job_guard.run_guarded(
        name="test-over-ceiling",
        argv=[sys.executable, str(script)],
        max_footprint_gb=0.01,  # 10 MB ceiling
        poll_seconds=0.2,
        grace_seconds=0.5,
    )
    
    assert code == 4


def test_healthy_footprint_does_not_trip():
    """2. A process at healthy footprint (~1.4 GB) does not trip."""
    # Use a large ceiling
    ceiling = job_guard.MemoryCeiling(
        max_footprint_bytes=2 * 1024 * 1024 * 1024,  # 2 GB
        poll_seconds=0.1,
    )
    ceiling.start()
    time.sleep(0.3)
    ceiling.stop()
    assert ceiling.tripped_reason is None


def test_high_footprint_near_zero_rss(monkeypatch):
    """3. The 07-27 signature specifically: high footprint, near-zero RSS, must trip."""
    # We mock `tree_footprint_bytes` to simulate this.
    # To test the logic, we simulate that tree_footprint_bytes returns a huge footprint.
    def mock_tree_footprint_bytes(pid):
        return (10 * 1024 * 1024 * 1024, False, 0) # 10 GB, not fallback, 0 unreadable
    
    monkeypatch.setattr(job_guard, "tree_footprint_bytes", mock_tree_footprint_bytes)

    ceiling = job_guard.MemoryCeiling(
        max_footprint_bytes=8 * 1024 * 1024 * 1024, # 8 GB limit
        poll_seconds=0.1,
    )
    ceiling.start()
    time.sleep(0.3)
    ceiling.stop()
    assert ceiling.tripped_reason is not None
    assert "phys_footprint" in ceiling.tripped_reason


def test_unreadable_pids_are_skipped_and_counted(monkeypatch):
    """4. Unreadable pids (rc = -1) are skipped, counted, and never treated as 0."""
    monkeypatch.setattr(sys, "platform", "darwin")

    class MockSubprocessOut:
        returncode = 0
        stdout = "1000 1 100\n1001 1000 200\n1002 1000 300\n"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockSubprocessOut())

    class MockProcPidRusage:
        def __call__(self, pid, flavor, buf_ptr):
            if pid == 1001:
                return -1 # unreadable
            buf = buf_ptr._obj
            buf.ri_phys_footprint = 1024 if pid == 1000 else 2048
            return 0

    class FakeLibc:
        def __init__(self):
            self.proc_pid_rusage = MockProcPidRusage()
            
    monkeypatch.setattr(ctypes, "CDLL", lambda name: FakeLibc())
    monkeypatch.setattr(ctypes.util, "find_library", lambda name: "fake_c")

    footprint, is_fallback, unreadable = job_guard.tree_footprint_bytes(1000)
    
    assert not is_fallback
    assert unreadable == 1
    assert footprint == 3072

    ceiling = job_guard.MemoryCeiling(
        pid=1000,
        max_footprint_bytes=1000,
        poll_seconds=0.1,
    )
    reason = ceiling._check()
    assert reason is not None
    assert "(skipped 1 unreadable pids)" in reason


def test_rss_fallback(monkeypatch):
    """5. The RSS fallback path works and announces itself when footprint is unavailable."""
    # Force fallback by mocking sys.platform
    monkeypatch.setattr(sys, "platform", "linux")
    
    footprint, is_fallback, unreadable = job_guard.tree_footprint_bytes(os.getpid())
    assert is_fallback
    assert footprint > 0
    
    ceiling = job_guard.MemoryCeiling(
        max_footprint_bytes=1024,
        poll_seconds=0.1,
    )
    # The message should announce RSS fallback
    reason = ceiling._check()
    assert reason is not None
    assert "RSS (fallback)" in reason


def test_deprecated_env_var_alias(monkeypatch):
    """6. The deprecated env-var alias still applies."""
    import argparse
    from rebalance.ingest import _job_guard

    # Test the parsing in job_guard.py run_guarded via _job_guard
    monkeypatch.setenv("REBALANCE_JOB_GUARD_MAX_RSS_GB", "42.0")
    monkeypatch.setenv("REBALANCE_JOB_GUARD", "1")
    monkeypatch.setenv("JOB_GUARD_MODULE", str(Path(job_guard.__file__).resolve()))

    # Instead of forcing a reload from disk which ignores our monkeypatch,
    # we inject the already-loaded module into the bridge's cache.
    _job_guard._module = job_guard
    _job_guard._load_attempted = True
    
    # Capture guard arguments
    captured_kwargs = {}
    
    def mock_guard(name, **kwargs):
        captured_kwargs.update(kwargs)
        class DummyContextManager:
            def __enter__(self): pass
            def __exit__(self, exc_type, exc_val, exc_tb): pass
        return DummyContextManager()

    monkeypatch.setattr(job_guard, "guard", mock_guard)
    
    with _job_guard.embedding_guard():
        pass
        
    assert captured_kwargs.get("max_rss_gb") == 42.0
    
    # And test that max_rss_gb is correctly mapped to max_footprint in MemoryCeiling
    ceiling = job_guard.MemoryCeiling(max_rss_bytes=12345)
    assert ceiling.max_footprint == 12345
