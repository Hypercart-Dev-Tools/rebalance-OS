"""Shared pytest fixtures for the rebalance-OS test suite."""

import os

import pytest


@pytest.fixture(autouse=True)
def _isolate_secret_store(tmp_path_factory):
    """Redirect the out-of-repo secret store to a fresh tmp dir for EACH test.

    The GitHub/Figma dual-store helpers (`config.py`) now write/read the
    permission-enforced secret store at `~/.config/rebalance-os/secrets`. Without
    isolation, suite runs pollute the operator's real secret dir and — because
    secret files are last-write-wins (unlike the append-only auth log) — leak
    values across tests. Per-test scope gives every test a clean store.
    `secret_store.secret_store_root()` honors `REBALANCE_SECRET_STORE_DIR`; tests
    that need a specific path override `secret_store.SECRET_STORE_DIR` (module
    seam), which takes precedence.
    """
    store_dir = tmp_path_factory.mktemp("secret_store")
    previous = os.environ.get("REBALANCE_SECRET_STORE_DIR")
    os.environ["REBALANCE_SECRET_STORE_DIR"] = str(store_dir)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("REBALANCE_SECRET_STORE_DIR", None)
        else:
            os.environ["REBALANCE_SECRET_STORE_DIR"] = previous


@pytest.fixture(autouse=True, scope="session")
def _isolate_auth_log(tmp_path_factory):
    """Redirect the unified auth-activity log to a throwaway tmp dir for the
    whole test session.

    Several code paths (gmail/calendar `_load_credentials`, the 403 scope probe,
    etc.) call `auth_log` helpers that append to `temp/logs/auth_activity.jsonl`.
    Without this, running the suite injects fake `token_missing` /
    `scope_insufficient` events into the *real* log, which then shows up as false
    failures in `rebalance doctor`. `auth_log._log_dir()` honors
    `REBALANCE_AUTH_LOG_DIR`, so pointing it at a tmp dir keeps the suite from
    touching the repo's log.
    """
    log_dir = tmp_path_factory.mktemp("auth_log")
    previous = os.environ.get("REBALANCE_AUTH_LOG_DIR")
    os.environ["REBALANCE_AUTH_LOG_DIR"] = str(log_dir)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("REBALANCE_AUTH_LOG_DIR", None)
        else:
            os.environ["REBALANCE_AUTH_LOG_DIR"] = previous
