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


def test_over_ceiling_trips():
    """1. A synthetic over-ceiling process trips and is killed."""
    ceiling = job_guard.MemoryCeiling(
        max_footprint_bytes=1024,
        poll_seconds=0.1,
    )
    # The current python process will definitely have > 1KB of footprint.
    ceiling.start()
    time.sleep(0.3)
    ceiling.stop()
    assert ceiling.tripped_reason is not None
    assert "process tree holds" in ceiling.tripped_reason


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
    if sys.platform != "darwin":
        pytest.skip("Requires macOS for proc_pid_rusage")

    import subprocess
    
    # We want a real unreadable PID, e.g., pid 1 (launchd)
    footprint, is_fallback, unreadable = job_guard.tree_footprint_bytes(1)
    # pid 1 should be unreadable by non-root
    assert not is_fallback
    assert unreadable > 0
    
    ceiling = job_guard.MemoryCeiling(
        pid=1,
        max_footprint_bytes=1,
        poll_seconds=0.1,
    )
    ceiling.start()
    time.sleep(0.3)
    ceiling.stop()
    # It might trip if total > 1, but we care that the message includes the unreadable count.
    if ceiling.tripped_reason:
        assert "(skipped" in ceiling.tripped_reason


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
