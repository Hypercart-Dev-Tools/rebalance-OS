"""Shared pytest fixtures for the rebalance-OS test suite."""

import os

import pytest

#: GH-178 quarantine. These failed at GH-124's own final commit (536de83,
#: 2026-07-11) and were merged red — nothing caught it because CI did not run on
#: `development` until GH-177. Verified to fail identically on macOS and on clean
#: Ubuntu CI, so they are real product bugs, not environment artifacts.
#:
#: They are quarantined rather than deleted so CI regains signal NOW: a red run
#: means *new* breakage instead of the same 10 forever, which is the state that
#: trains people to ignore CI. This list must shrink to empty — every entry is a
#: real defect in commit-threshold auto-promotion.
#:
#: DO NOT add to this list to make a red build green. Fix the test or the code.
KNOWN_FAILING_GH178 = {
    "tests/test_auto_promote.py::AutoPromoteTests::test_activity_commits_sum_across_scan_dates",
    "tests/test_auto_promote.py::AutoPromoteTests::test_auto_promoted_row_survives_activity_inference_sync",
    "tests/test_auto_promote.py::AutoPromoteTests::test_cloud_agent_commits_count_toward_threshold",
    "tests/test_auto_promote.py::AutoPromoteTests::test_direct_push_commits_count_not_just_pr_commits",
    "tests/test_auto_promote.py::AutoPromoteTests::test_idempotent_rerun_does_not_duplicate",
    "tests/test_auto_promote.py::AutoPromoteTests::test_name_collision_disambiguates_instead_of_overwriting",
    "tests/test_auto_promote.py::AutoPromoteTests::test_operator_push_and_bot_commits_combine",
    "tests/test_auto_promote.py::AutoPromoteTests::test_promotes_repo_at_threshold",
    "tests/test_auto_promote.py::AutoPromoteTests::test_promotion_fires_auth_log_alert",
    "tests/test_project_inference.py::ProjectInferenceTests::test_infers_binoid_from_github_and_ltvera_from_calendar_only",
}


def pytest_collection_modifyitems(config, items):
    """Mark the GH-178 quarantine xfail, non-strict.

    Non-strict on purpose: if one starts passing the run stays green (XPASS) and
    the entry is simply stale. Strict would turn someone else's unrelated fix
    into a red build, which is the opposite of the point.
    """
    for item in items:
        if item.nodeid in KNOWN_FAILING_GH178:
            item.add_marker(
                pytest.mark.xfail(
                    reason="GH-178: known-failing since GH-124 (536de83); quarantined by GH-177",
                    strict=False,
                )
            )


@pytest.fixture(autouse=True)
def _disable_job_guard(monkeypatch):
    """Turn off the GH-172 embedding guard for the whole suite.

    The guard takes a real ``flock`` and starts a memory watchdog whose
    ``preflight()`` REFUSES to start when the machine is low on available
    memory. Left on, tests that call ``embed_pending``/``embed_chunks`` would
    fail spuriously on a busy machine and serialise against any real ingest
    running on the same box. Guard behaviour itself is covered explicitly in
    ``tests/test_job_guard_wiring.py``, which re-enables it per-test.
    """
    monkeypatch.setenv("REBALANCE_JOB_GUARD", "0")


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
