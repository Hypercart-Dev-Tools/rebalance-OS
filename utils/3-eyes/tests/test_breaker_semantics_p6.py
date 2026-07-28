"""P6 breaker semantics: deferred runs, half-open recovery, quiet quarantine (GH-195).

The bug these lock down, concretely: on 2026-07-27 an unrelated regression in
another project made ``job_guard``'s availability preflight refuse to start jobs on
a healthy machine. ``run.py`` computed ``ok = code == 0``, so three "the machine is
busy" refusals were counted as three job failures and permanently quarantined
``skill-sync``. It then stayed quarantined — no cooldown, no probe — while launchd
kept waking it every 120 s, and every wake appended a finding. 72 of the 73 records
in the live ``findings.jsonl`` were that one line.

So three properties are tested here, each of which independently would have
prevented that outcome:

  1. A deferred exit never increments the failure counter.
  2. A quarantined breaker recovers on its own after a cooldown.
  3. A quarantined job records at most one skip notice per cooldown window.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from three_eyes import breakers, config, routes, run


# --------------------------------------------------------------------------- #
# 1. Deferred is not failed
# --------------------------------------------------------------------------- #

def test_job_guard_separates_refusal_from_ceiling_trip():
    """The two causes must have DIFFERENT exit codes.

    Before P6 both returned 4, which is precisely why a caller could not tell "the
    machine was busy" from "this job blew its memory budget". If this collapses back
    to one code, every downstream distinction here becomes unenforceable.
    """
    guard = breakers.job_guard
    assert guard is not None, "job_guard must load; 3-Eyes never runs unguarded"
    assert guard.EXIT_REFUSED_TO_START != guard.EXIT_CEILING_TRIPPED
    assert guard.EXIT_REFUSED_TO_START in guard.DEFERRED_EXIT_CODES
    assert guard.EXIT_INSTANCE_CONFLICT in guard.DEFERRED_EXIT_CODES
    # The mid-run trip is a REAL failure and must never be excused as deferred.
    assert guard.EXIT_CEILING_TRIPPED not in guard.DEFERRED_EXIT_CODES


@pytest.mark.parametrize(
    "code, expected",
    [
        (0, "ok"),
        (3, "deferred"),    # another instance holds the lock
        (75, "deferred"),   # refused to start; machine starved
        (4, "fail"),        # ceiling tripped MID-RUN — the job misbehaved
        (1, "fail"),
        (2, "fail"),
    ],
)
def test_classify_exit(code, expected):
    assert breakers.classify_exit(code) == expected


def test_guard_refusals_never_open_the_breaker(activate, monkeypatch):
    """The exact 2026-07-27 sequence: three preflight refusals in a row.

    selfcheck has trip_after_failures = 3, so pre-P6 this quarantined the job. It
    must now leave the breaker closed and the failure count at zero.
    """
    activate()
    monkeypatch.setattr(breakers, "run_job_command",
                        lambda job: breakers.job_guard.EXIT_REFUSED_TO_START)
    monkeypatch.setattr(routes, "route", lambda finding, rts, **k: [])

    for _ in range(5):
        run.run_job("selfcheck")

    breaker = breakers.FailureBreaker()
    assert breaker.is_open("selfcheck") is False
    status = breaker.status("selfcheck")
    assert status["consecutive_failures"] == 0
    # Deferrals stay visible — not counted, but not silently dropped either.
    assert status["deferred_runs"] == 5
    assert status["last"] == "deferred"


def test_instance_conflicts_never_open_the_breaker(activate, monkeypatch):
    """A job that overlaps its own previous run is contention, not breakage."""
    activate()
    monkeypatch.setattr(breakers, "run_job_command",
                        lambda job: breakers.job_guard.EXIT_INSTANCE_CONFLICT)
    monkeypatch.setattr(routes, "route", lambda finding, rts, **k: [])

    for _ in range(5):
        run.run_job("selfcheck")

    assert breakers.FailureBreaker().is_open("selfcheck") is False


def test_mid_run_ceiling_trip_DOES_open_the_breaker(activate, monkeypatch):
    """The other side of the coin — and the way to get this fix wrong.

    Excusing every memory-related exit would mean a job that repeatedly blows its
    footprint ceiling is never quarantined. Exit 4 is a real failure.
    """
    activate()
    monkeypatch.setattr(breakers, "run_job_command",
                        lambda job: breakers.job_guard.EXIT_CEILING_TRIPPED)
    monkeypatch.setattr(routes, "route", lambda finding, rts, **k: [])

    for _ in range(3):        # selfcheck trips after 3
        run.run_job("selfcheck")

    assert breakers.FailureBreaker().is_open("selfcheck") is True


def test_deferred_run_does_not_reset_an_existing_failure_count(activate, monkeypatch):
    """A deferral must be inert in BOTH directions.

    If it cleared the counter, a job failing intermittently between busy periods
    would never accumulate enough consecutive failures to trip.
    """
    activate()
    monkeypatch.setattr(routes, "route", lambda finding, rts, **k: [])

    monkeypatch.setattr(breakers, "run_job_command", lambda job: 1)
    run.run_job("selfcheck")
    run.run_job("selfcheck")
    assert breakers.FailureBreaker().status("selfcheck")["consecutive_failures"] == 2

    monkeypatch.setattr(breakers, "run_job_command",
                        lambda job: breakers.job_guard.EXIT_REFUSED_TO_START)
    run.run_job("selfcheck")
    assert breakers.FailureBreaker().status("selfcheck")["consecutive_failures"] == 2

    monkeypatch.setattr(breakers, "run_job_command", lambda job: 1)
    run.run_job("selfcheck")                        # third real failure -> opens
    assert breakers.FailureBreaker().is_open("selfcheck") is True


# --------------------------------------------------------------------------- #
# 2. Half-open recovery
# --------------------------------------------------------------------------- #

def _open_breaker(job_id: str = "selfcheck") -> breakers.FailureBreaker:
    breaker = breakers.FailureBreaker()
    for _ in range(3):
        breaker.record(job_id, ok=False, trip_after=3)
    assert breaker.is_open(job_id)
    return breaker


def test_no_probe_before_the_cooldown_elapses():
    breaker = _open_breaker()
    assert breaker.claim_probe("selfcheck") is False


def test_exactly_one_probe_is_granted_per_cooldown():
    """Atomicity matters: two wakes must not both believe they are the probe."""
    breaker = _open_breaker()
    status = breaker.status("selfcheck")
    future = status["quarantined_at"] + status["cooldown_seconds"] + 1

    assert breaker.claim_probe("selfcheck", now=future) is True
    assert breaker.claim_probe("selfcheck", now=future) is False
    assert breaker.claim_probe("selfcheck", now=future + 60) is False


def test_a_successful_probe_closes_the_breaker_and_clears_the_clock():
    breaker = _open_breaker()
    status = breaker.status("selfcheck")
    future = status["quarantined_at"] + status["cooldown_seconds"] + 1
    assert breaker.claim_probe("selfcheck", now=future) is True

    breaker.record("selfcheck", ok=True, trip_after=3)

    assert breaker.is_open("selfcheck") is False
    after = breaker.status("selfcheck")
    assert after["consecutive_failures"] == 0
    # Stale half-open bookkeeping must not survive: a later, unrelated trip has to
    # start from the DEFAULT cooldown, not an inherited doubled one.
    for key in ("quarantined_at", "cooldown_seconds", "probe_at"):
        assert key not in after


def test_a_failed_probe_reopens_with_a_doubled_cooldown():
    breaker = _open_breaker()
    first = breaker.status("selfcheck")["cooldown_seconds"]
    assert first == breakers.DEFAULT_COOLDOWN_SECONDS

    future = breaker.status("selfcheck")["quarantined_at"] + first + 1
    assert breaker.claim_probe("selfcheck", now=future) is True

    # The probe run fails: three more failures re-trip it (the counter kept
    # climbing while quarantined, so in practice one is enough — assert the
    # cooldown, which is the P6 behaviour).
    breaker.record("selfcheck", ok=False, trip_after=3)
    assert breaker.status("selfcheck")["cooldown_seconds"] == first * 2


def _fail_a_probe(breaker: breakers.FailureBreaker, job_id: str = "selfcheck") -> int:
    """Drive one full half-open cycle whose probe fails. Returns the new cooldown."""
    status = breaker.status(job_id)
    future = status["quarantined_at"] + status["cooldown_seconds"] + 1
    assert breaker.claim_probe(job_id, now=future) is True
    breaker.record(job_id, ok=False, trip_after=3)
    return breaker.status(job_id)["cooldown_seconds"]


def test_cooldown_doubles_on_each_failed_probe_then_saturates():
    """Backoff must grow, and must stop growing.

    Unbounded doubling would eventually park a job for years; no doubling at all
    would hammer a broken job hourly forever. Both are failures of invariant 6.
    """
    breaker = _open_breaker()
    assert breaker.status("selfcheck")["cooldown_seconds"] == breakers.DEFAULT_COOLDOWN_SECONDS

    seen = [_fail_a_probe(breaker) for _ in range(3)]
    assert seen == [
        breakers.DEFAULT_COOLDOWN_SECONDS * 2,
        breakers.DEFAULT_COOLDOWN_SECONDS * 4,
        breakers.DEFAULT_COOLDOWN_SECONDS * 8,
    ]

    for _ in range(20):       # far more doublings than the cap allows
        cooldown = _fail_a_probe(breaker)
    assert cooldown == breakers.MAX_COOLDOWN_SECONDS


def test_a_failed_probe_restarts_the_clock():
    """After a failed probe the next one must wait the NEW cooldown, not fire at once.

    ``claim_probe`` anchors on the later of ``quarantined_at`` / ``probe_at``; if the
    re-arm forgot to move that anchor, every subsequent wake would qualify as a probe
    and the backoff would be cosmetic.
    """
    breaker = _open_breaker()
    _fail_a_probe(breaker)
    assert breaker.claim_probe("selfcheck") is False


def test_an_operator_pause_on_a_fresh_job_never_self_heals():
    """`quarantine()` is a human decision. Auto-recovery must not undo it."""
    breaker = breakers.FailureBreaker()
    breaker.quarantine("selfcheck", reason="operator paused")
    far_future = 9_999_999_999.0
    assert breaker.claim_probe("selfcheck", now=far_future) is False
    assert breaker.is_open("selfcheck") is True


def test_pausing_an_ALREADY_TRIPPED_job_stops_its_probe():
    """The ordering that actually exercises the `paused` guard.

    Pausing a fresh job leaves no retry clock, so ``claim_probe`` refuses on the
    "no clock" branch and the paused check is never reached — a test that only
    covers that path passes even with the paused guard deleted. Here the job is
    auto-quarantined first (so it HAS a live clock and a due probe) and only then
    paused, which makes the paused check the single thing standing between an
    operator's pause and the job restarting itself.
    """
    breaker = _open_breaker()
    status = breaker.status("selfcheck")
    due = status["quarantined_at"] + status["cooldown_seconds"] + 1
    assert breaker.claim_probe("selfcheck", now=due) is True, "precondition: probe was due"

    breaker.reset("selfcheck")
    breaker = _open_breaker()
    breaker.quarantine("selfcheck", reason="operator paused mid-quarantine")

    status = breaker.status("selfcheck")
    assert status["quarantined_at"] > 0, "precondition: the retry clock is live"
    due = status["quarantined_at"] + status["cooldown_seconds"] + 1
    assert breaker.claim_probe("selfcheck", now=due) is False, (
        "a paused job resumed itself despite a due probe"
    )


def test_half_open_probe_actually_runs_the_job(activate, monkeypatch):
    """End-to-end: the probe reaches run_job_command, not just the state file."""
    activate()
    breaker = _open_breaker()
    status = breaker.status("selfcheck")

    ran = []
    monkeypatch.setattr(breakers, "run_job_command", lambda job: ran.append(job.id) or 0)
    monkeypatch.setattr(routes, "route", lambda finding, rts, **k: [])

    # Before the cooldown: skipped.
    run.run_job("selfcheck")
    assert ran == []

    # Rewind the trip time so the cooldown has "elapsed" without sleeping.
    import json
    path = breakers._state_path()
    state = json.loads(path.read_text())
    state["selfcheck"]["quarantined_at"] = (
        status["quarantined_at"] - status["cooldown_seconds"] - 1
    )
    path.write_text(json.dumps(state))

    run.run_job("selfcheck")
    assert ran == ["selfcheck"], "the half-open probe never reached the command"
    assert breakers.FailureBreaker().is_open("selfcheck") is False, "probe success must close it"


# --------------------------------------------------------------------------- #
# 3. Quiet quarantine
# --------------------------------------------------------------------------- #

def test_quarantined_skips_are_throttled_to_one_notice_per_window(activate, monkeypatch):
    """The findings-log spam fix.

    A 120 s job quarantined for a day wrote 720 identical records. Notice once per
    cooldown window instead, so the evidence channel stays readable.
    """
    activate()
    breakers.FailureBreaker().quarantine("selfcheck")
    monkeypatch.setattr(breakers, "run_job_command",
                        lambda job: pytest.fail("ran a quarantined job"))
    seen = []
    monkeypatch.setattr(routes, "route", lambda finding, rts, **k: seen.append(finding) or [])

    for _ in range(50):
        assert run.run_job("selfcheck") == 0

    assert len(seen) == 1, f"expected one throttled notice, got {len(seen)}"
    assert seen[0]["title"] == "selfcheck quarantined"


def test_the_first_skip_still_records_once(activate, monkeypatch):
    """Throttling must not silence the evidence entirely — one record is required."""
    activate()
    breakers.FailureBreaker().quarantine("selfcheck")
    monkeypatch.setattr(breakers, "run_job_command", lambda job: 0)
    seen = []
    monkeypatch.setattr(routes, "route",
                        lambda finding, rts, **k: seen.append(list(rts)) or [])
    run.run_job("selfcheck")
    assert seen == [["log-only"]], "a quarantined skip must stay log-only, and must appear"


# --------------------------------------------------------------------------- #
# 4. The shim's Python probe: transient vs. permanent
# --------------------------------------------------------------------------- #

def _run_shim(tmp_path, probe_exit: int) -> int:
    """Run the shim with a fake `python3.13` whose tomllib probe exits `probe_exit`.

    The real venv python is stripped from the candidate list so the fake is what
    gets probed.
    """
    # Unique per call: the same tmp_path is reused across probe codes within a test.
    work = tmp_path / f"probe{probe_exit}"
    work.mkdir()

    shim_src = (config.ROOT / "shims" / "run-job.sh").read_text()
    shim = work / "shim.sh"
    shim.write_text(shim_src.replace('"$repo_root/.venv/bin/python" ', ""))

    fakebin = work / "bin"
    fakebin.mkdir()
    fake = fakebin / "python3.13"
    fake.write_text(f"#!/bin/bash\nexit {probe_exit}\n")
    fake.chmod(0o755)

    env = dict(os.environ, PATH=f"{fakebin}:/usr/bin:/bin")
    return subprocess.run(
        ["/bin/bash", str(shim), "selfcheck"],
        env=env, capture_output=True, text=True,
    ).returncode


def test_shim_defers_when_python_cannot_be_EXECUTED(tmp_path):
    """126/127 and signal deaths mean the probe never ran — retry later.

    This is the live failure: 12 times the shim announced "no Python with tomllib
    (>=3.11) found on this host" — a permanent-sounding verdict — while bash logged
    "Interrupted system call" two lines earlier and the venv python was fine the
    whole time.
    """
    assert _run_shim(tmp_path, probe_exit=126) == 75
    assert _run_shim(tmp_path, probe_exit=127) == 75
    assert _run_shim(tmp_path, probe_exit=137) == 75    # SIGKILL


def test_shim_still_reports_a_GENUINELY_too_old_python(tmp_path):
    """Exit 1 means the interpreter RAN and raised ImportError — that is permanent.

    The guard against over-correcting: /usr/bin/python3 on macOS really is 3.9 and
    really has no tomllib. Deferring on that would retry a misconfigured host
    forever instead of surfacing it.
    """
    assert _run_shim(tmp_path, probe_exit=1) == 3


def test_shim_selects_the_repo_venv_when_it_works():
    """Unmodified shim, real interpreter: selfcheck runs and exits clean."""
    proc = subprocess.run(
        ["/bin/bash", str(config.ROOT / "shims" / "run-job.sh"), "selfcheck"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


# --------------------------------------------------------------------------- #
# 5. Defects found by the agy QA relay (2026-07-28) — regression locks
# --------------------------------------------------------------------------- #

def test_a_successful_run_does_not_lift_an_OPERATOR_pause():
    """QA finding 1b: a pause must outrank a success.

    Sequence: the job is already running when the operator pauses it, then the run
    succeeds. `record(ok=True)` cleared `quarantined` while leaving `paused` set,
    and `is_open()` reads only `quarantined` — so the next wake ran a job the
    operator had explicitly stopped. Only `reset()` may lift a pause.
    """
    breaker = breakers.FailureBreaker()
    breaker.quarantine("selfcheck", reason="operator paused")

    breaker.record("selfcheck", ok=True, trip_after=3)

    assert breaker.is_open("selfcheck") is True, "a successful run lifted an operator pause"
    assert breaker.status("selfcheck")["paused"] is True

    breaker.reset("selfcheck")                    # the ONLY sanctioned way out
    assert breaker.is_open("selfcheck") is False


def test_a_deferred_probe_does_not_burn_the_probe_slot():
    """QA finding 5: a probe that never ran must not cost a full cooldown.

    The job claims its half-open probe, then the guard refuses to start it — so
    nothing executed. Leaving `probe_at` set meant the next wake measured against
    it and waited another full cooldown. That is P6's own thesis ("a busy machine
    must not punish a healthy job") violated one level up.
    """
    breaker = _open_breaker()
    status = breaker.status("selfcheck")
    due = status["quarantined_at"] + status["cooldown_seconds"] + 1
    assert breaker.claim_probe("selfcheck", now=due) is True

    breaker.record_deferred("selfcheck", breakers.job_guard.EXIT_REFUSED_TO_START)

    assert "probe_at" not in breaker.status("selfcheck"), "the unused probe claim was not released"
    assert breaker.claim_probe("selfcheck", now=due + 1) is True, (
        "a deferral cost the job a whole cooldown of recovery time"
    )


def test_a_pre_P6_quarantine_is_rescued_not_stranded():
    """QA finding 6: state latched by the old code has no retry clock.

    Pre-P6 `breakers.json` records `quarantined: true` with no `quarantined_at` and
    no `cooldown_seconds`. Refusing the probe when `since <= 0` would strand exactly
    the jobs P6 was written to rescue — skill-sync sat dead for a day in this state.
    """
    import json
    path = breakers._state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "selfcheck": {"consecutive_failures": 3, "last": "fail", "quarantined": True}
    }))

    breaker = breakers.FailureBreaker()
    assert breaker.is_open("selfcheck") is True
    assert breaker.claim_probe("selfcheck") is True, "a pre-P6 quarantine was stranded forever"
    # And it must now carry a clock, so it behaves like any other episode afterwards.
    after = breaker.status("selfcheck")
    assert after["probe_at"] > 0
    assert after["cooldown_seconds"] == breakers.DEFAULT_COOLDOWN_SECONDS
    assert breaker.claim_probe("selfcheck") is False, "the rescue granted more than one probe"


def test_a_pre_P6_state_that_is_PAUSED_is_still_not_rescued():
    """The rescue must not resurrect an operator pause that predates P6 either."""
    import json
    path = breakers._state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "selfcheck": {"consecutive_failures": 0, "quarantined": True, "paused": True}
    }))
    assert breakers.FailureBreaker().claim_probe("selfcheck") is False


def test_shim_defers_on_an_out_of_range_exit_status(tmp_path):
    """QA finding 2: 255 is not "the interpreter lacks tomllib".

    The old `126|127|1??` glob matched exactly three characters starting with 1, so
    it covered signal deaths (128-159) but let 255 — what bash reports for an
    out-of-range exit — fall through to the permanent branch.
    """
    assert _run_shim(tmp_path, probe_exit=255) == 75


def test_deferred_exit_codes_cannot_silently_diverge_from_job_guard():
    """QA finding 4: the literal fallback in breakers.py is unreachable today.

    `run_job_command` raises if job_guard is missing, so the `frozenset({3, 75})`
    default never faces a real exit code. Keeping a hand-copied mirror of another
    module's constants is still a divergence risk, so pin them equal here — if the
    guard's codes change and the fallback does not, this fails instead of rotting.
    """
    assert breakers.DEFERRED_EXIT_CODES == breakers.job_guard.DEFERRED_EXIT_CODES
    assert breakers.DEFERRED_EXIT_CODES == frozenset({3, 75})
