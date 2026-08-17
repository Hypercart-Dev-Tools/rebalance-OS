"""P7c collector-health observer (GH-195).

This is the producer that had been missing: `classify()` is reachable only from
`run._process_emit`, which fires when a job drops a finding file, and no job had ever
dropped one. Everything here exists to make that finding trustworthy.

Every test below corresponds to a way the FIRST version of this module was wrong when
run against the real logs in `temp/logs/`, or to a misread GH-146 records. Log parsing
looks trivial and is not — the failure mode is silence, which nobody notices.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from three_eyes import config, observe


NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

COMPLETE = """[2026-07-28 06:30:05] === rebalance daily sync starting ===
{
  "results": [{"scope": "vault"}, {"scope": "github"}],
  "errors": [],
  "sync_outcome": "complete"
}
[2026-07-28 07:28:54] === rebalance daily sync complete ===
"""

# The exact banner that broke the first implementation.
DEGRADED = """[2026-07-27 19:30:05] === rebalance daily sync starting ===
{
  "errors": [{"scope": "vault", "error": "database is locked"}],
  "sync_outcome": "degraded"
}
[2026-07-27 20:17:05] === rebalance daily sync degraded; partial errors recorded (see JSON above) ===
"""

IN_FLIGHT = """[2026-07-26 06:30:05] === rebalance daily sync starting ===
Fetching 10 files:  40%|####      | 4/10
"""

# A resolved failure followed by a good run — reading the FIRST outcome reports a
# problem that is already over.
DEGRADED_THEN_COMPLETE = DEGRADED + COMPLETE


def _write(tmp_path, name: str, body: str, age_hours: float = 0.0) -> Path:
    logs = tmp_path / "temp" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / name
    path.write_text(body)
    if age_hours:
        old = time.time() - age_hours * 3600
        os.utime(path, (old, old))
    return path


@pytest.fixture
def logdir(tmp_path, monkeypatch):
    monkeypatch.setattr(observe, "_log_dir", lambda: tmp_path / "temp" / "logs")
    return tmp_path


# --------------------------------------------------------------------------- #
# Rule 1 — a log holds many runs; only the last one is current
# --------------------------------------------------------------------------- #

def test_only_the_LAST_run_in_a_multi_run_log_counts(logdir):
    """`daily_sync_2026-07-19.log` really does hold a degraded run then a complete one.

    Reading the first match reports a failure that was already resolved.
    """
    path = _write(logdir, "daily_sync_2026-07-28.log", DEGRADED_THEN_COMPLETE)
    assert observe.parse_sync_log(path)["state"] == "complete"


def test_a_complete_run_followed_by_a_degraded_one_reports_degraded(logdir):
    path = _write(logdir, "daily_sync_2026-07-28.log", COMPLETE + DEGRADED)
    assert observe.parse_sync_log(path)["state"] == "degraded"


def test_the_last_outcome_wins_even_with_NO_start_markers(logdir):
    """Covers the case where splitting on the start banner cannot help.

    `last_run_block` normally isolates a single run, which makes the "take the last
    outcome" index look redundant — a mutation to `outcomes[0]` survived the two tests
    above for exactly that reason. It stops being redundant when a log has no start
    banner at all (truncated, rotated mid-run, or a future format change): then the
    whole file is one block and the index is the only thing choosing the current run.
    """
    body = (
        '{"errors": [{"error": "x"}], "sync_outcome": "degraded"}\n'
        "[t] === rebalance daily sync degraded; partial errors recorded ===\n"
        '{"errors": [], "sync_outcome": "complete"}\n'
        "[t] === rebalance daily sync complete ===\n"
    )
    path = _write(logdir, "daily_sync_2026-07-28.log", body)
    assert "starting" not in body, "this test is meaningless if a start banner exists"
    assert observe.parse_sync_log(path)["state"] == "complete"


# --------------------------------------------------------------------------- #
# Rule 2 — terminal-by-elimination, and the ceiling on "still running"
# --------------------------------------------------------------------------- #

def test_a_DEGRADED_banner_counts_as_terminal(logdir):
    """The bug that would have made this whole module useless.

    The first implementation matched `complete` and `finished…` and therefore missed
    `=== rebalance daily sync degraded; partial errors recorded ===`. Every degraded
    run read as "still running" and was silently reported as fine — exactly the GH-146
    failure the observer exists to prevent, reintroduced by the observer.
    """
    path = _write(logdir, "daily_sync_2026-07-27.log", DEGRADED)
    assert observe.parse_sync_log(path)["state"] == "degraded"


@pytest.mark.parametrize("banner", [
    "=== rebalance daily sync complete ===",
    "=== rebalance daily sync finished with errors (see JSON above) ===",
    "=== rebalance hourly github sync finished with errors ===",
    "=== rebalance daily sync degraded; partial errors recorded (see JSON above) ===",
    "=== rebalance daily sync some-future-outcome-word ===",
])
def test_every_non_starting_banner_is_terminal(banner):
    """Terminality is decided by elimination, so a NEW outcome word still terminates.

    The last case matters most: an outcome nobody has written yet must fail toward
    "evaluate this run", not toward silence.
    """
    text = observe.MARKER_RE.findall(banner)
    assert text, f"marker regex did not match: {banner}"
    assert observe._is_terminal(text[0]) is True


def test_the_starting_banner_is_not_terminal():
    text = observe.MARKER_RE.findall("=== rebalance daily sync starting ===")
    assert text and observe._is_terminal(text[0]) is False


def test_a_fresh_in_flight_run_says_nothing(logdir):
    _write(logdir, "daily_sync_2026-07-28.log", IN_FLIGHT, age_hours=1)
    assert observe.observe(now=datetime.now(timezone.utc)) is None


def test_a_STALE_in_flight_run_is_a_dead_run(logdir):
    """`daily_sync_2026-07-26.log` opens with a start banner and simply stops.

    The run was killed mid-flight during the memory crisis. Without a ceiling it reads
    as "running" forever and a dead nightly sync stays invisible permanently.
    """
    _write(logdir, "daily_sync_2026-07-26.log", IN_FLIGHT,
           age_hours=observe.IN_FLIGHT_MAX_HOURS + 2)
    finding = observe.observe(now=datetime.now(timezone.utc))
    assert finding is not None, "a run dead for hours was reported as still running"
    assert "never finished" in finding["title"]
    assert finding["severity"] == "error"


# --------------------------------------------------------------------------- #
# Rule 3 — missing telemetry is UNKNOWN, never healthy
# --------------------------------------------------------------------------- #

def test_no_log_at_all_is_a_warning_not_a_clean_bill(logdir):
    (logdir / "temp" / "logs").mkdir(parents=True, exist_ok=True)
    finding = observe.observe(now=NOW)
    assert finding is not None
    assert finding["severity"] == "warn"
    assert "NOT a clean bill of health" in finding["summary"]


def test_an_unreadable_log_is_reported(logdir, monkeypatch):
    path = _write(logdir, "daily_sync_2026-07-28.log", COMPLETE)
    monkeypatch.setattr(Path, "read_text",
                        lambda self, **k: (_ for _ in ()).throw(OSError("permission denied")))
    parsed = observe.parse_sync_log(path)
    assert parsed["state"] == "unreadable"


def test_a_finished_run_with_no_outcome_is_reported(logdir):
    _write(logdir, "daily_sync_2026-07-28.log",
           "[x] === rebalance daily sync starting ===\n[y] === rebalance daily sync complete ===\n")
    finding = observe.observe(now=datetime.now(timezone.utc))
    assert finding is not None and "no outcome" in finding["title"]


# --------------------------------------------------------------------------- #
# Suppression reuse, and "complete" that is not actually clean
# --------------------------------------------------------------------------- #

def test_complete_with_only_KNOWN_errors_stays_silent(logdir):
    """2026-07-25: outcome `complete`, 16 GitHub 403s — all rate-limit noise (#144).

    Reporting that daily would train the operator to ignore this job.
    """
    body = COMPLETE.replace(
        '"errors": [],',
        '"errors": [{"error": "GitHub API request failed: 403 secondary rate limit"}],',
    )
    _write(logdir, "daily_sync_2026-07-28.log", body)
    assert observe.observe(now=datetime.now(timezone.utc)) is None


def test_complete_with_an_UNKNOWN_error_is_surfaced(logdir):
    """"outcome said complete" can lie too — the GH-146 lesson one level up."""
    body = COMPLETE.replace(
        '"errors": [],',
        '"errors": [{"error": "ValueError: unexpected column widget_id"}],',
    )
    _write(logdir, "daily_sync_2026-07-28.log", body)
    finding = observe.observe(now=datetime.now(timezone.utc))
    assert finding is not None
    assert "outcome said complete" in finding["title"]
    assert "widget_id" in finding["text"]


def test_a_degraded_finding_carries_NO_severity_so_it_gets_classified(logdir):
    """Leaving severity out is the documented signal for run._process_emit to classify.

    This is the finding Gemma was always meant to triage, and the precise reason that
    path had never once executed.
    """
    _write(logdir, "daily_sync_2026-07-27.log", DEGRADED)
    finding = observe.observe(now=datetime.now(timezone.utc))
    assert finding is not None
    assert "severity" not in finding, "a pre-set severity would bypass the classifier"


def test_a_degraded_finding_reports_how_many_errors_were_suppressed(logdir):
    body = DEGRADED.replace(
        '{"scope": "vault", "error": "database is locked"}',
        '{"error": "GitHub API request failed: 403 rate limit"}, '
        '{"error": "ValueError: brand new problem"}',
    )
    _write(logdir, "daily_sync_2026-07-27.log", body)
    finding = observe.observe(now=datetime.now(timezone.utc))
    assert "1 matched a known-issue rule" in finding["text"]
    assert "brand new problem" in finding["text"]


def test_database_is_locked_still_reaches_the_operator(logdir):
    """It is NOT on the suppression list, and must not be quietly absorbed here either."""
    _write(logdir, "daily_sync_2026-07-27.log", DEGRADED)
    finding = observe.observe(now=datetime.now(timezone.utc))
    assert finding is not None
    assert "database is locked" in finding["text"]


# --------------------------------------------------------------------------- #
# Freshness + the emit contract
# --------------------------------------------------------------------------- #

def test_a_stale_completed_run_is_reported(logdir):
    _write(logdir, "daily_sync_2026-07-20.log", COMPLETE, age_hours=observe.STALE_HOURS + 5)
    finding = observe.observe(now=datetime.now(timezone.utc))
    assert finding is not None and "stale" in finding["title"]


def test_a_healthy_run_emits_nothing_and_CLEARS_a_stale_finding(logdir):
    """A finding file left from a previous bad run would be re-routed forever."""
    _write(logdir, "daily_sync_2026-07-28.log", COMPLETE)
    emit = config.state_dir() / "emit"
    emit.mkdir(parents=True, exist_ok=True)
    stale = emit / "collector-health.json"
    stale.write_text('{"title": "old problem"}')

    assert observe.main([]) == 0
    assert not stale.exists(), "a resolved finding kept being re-routed"


def test_a_problem_writes_an_emit_file_main_still_exits_zero(logdir):
    """Exit 0 even on a finding: a non-zero exit would trip this job's own breaker
    for correctly doing its job. The FINDING is the output, not the exit code."""
    _write(logdir, "daily_sync_2026-07-27.log", DEGRADED)
    assert observe.main([]) == 0
    payload = json.loads((config.state_dir() / "emit" / "collector-health.json").read_text())
    assert payload["source"] == "collector-health"
    assert "severity" not in payload


# --------------------------------------------------------------------------- #
# Defects found by the agy QA relay (2026-07-28)
# --------------------------------------------------------------------------- #

def test_a_LONG_error_is_not_silently_invisible(logdir):
    """QA finding 4: `[^"]{0,200}` does not truncate a long error — it MISSES it.

    After 200 non-quote characters the next character must be a quote and is not, so a
    300-character traceback produced ZERO matches. `errs` came back empty and a
    `complete` run carrying a catastrophic error was reported as clean.
    """
    long_err = "ValueError: " + "z" * 400
    body = COMPLETE.replace('"errors": [],', f'"errors": [{{"error": "{long_err}"}}],')
    path = _write(logdir, "daily_sync_2026-07-28.log", body)

    parsed = observe.parse_sync_log(path)
    assert parsed["errors"], "a 400-character error was invisible to the parser"
    assert parsed["errors"][0].startswith("ValueError: zzz")

    finding = observe.observe(now=datetime.now(timezone.utc))
    assert finding is not None, "a complete run with a long unknown error looked clean"


def test_staleness_is_checked_BEFORE_the_known_errors_early_return(logdir):
    """QA finding 3: the "complete + only-known errors" branch returned None directly.

    That skipped the staleness check entirely, so a job that died after one such run
    was reported healthy forever. Freshness is a property of the job still running at
    all and must not be gated on what its last run happened to say.
    """
    body = COMPLETE.replace(
        '"errors": [],',
        '"errors": [{"error": "GitHub API request failed: 403 secondary rate limit"}],',
    )
    _write(logdir, "daily_sync_2026-07-20.log", body, age_hours=observe.STALE_HOURS + 10)

    finding = observe.observe(now=datetime.now(timezone.utc))
    assert finding is not None, "a long-dead job with only known errors read as healthy"
    assert "stale" in finding["title"]
