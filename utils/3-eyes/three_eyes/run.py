"""Single-job entrypoint — what launchd/cron actually exec (GH-195).

The one-line ``shims/run-job.sh`` execs ``python3 -m three_eyes.run <job-id>``.
This module is the gate stack every scheduled run passes through, in order:

  1. **Global halt** — PANIC file / ``THREE_EYES_ENABLE=0`` → do nothing, exit 0.
  2. **Inert** — not active (no runtime.env) → do nothing, exit 0. This is the
     observe-first / inert-by-default guarantee at the point of execution.
  3. **Breaker open** — job quarantined → skip, exit 0. Unless the cooldown has
     elapsed, in which case this run is the HALF-OPEN probe and proceeds (P6).
  4. **Quiet hours** — inside the window → skip, exit 0.
  5. **Run** — execute the allowlisted command under the GH-172 single-instance
     lock + memory ceiling; record the outcome against the failure breaker —
     but only if it *was* an outcome. See below.
  6. **Route** — if the command dropped a finding (``<state>/emit/<job>.json``),
     classify any missing severity and dispatch it to the job's routes.

Exit codes: 0 skipped/ok, 2 config error (unknown job/command), else the guarded
command's own code (3 instance-conflict, 4 memory-ceiling mid-run, 75 refused to
start — all from job_guard).

**A deferred run is not a failed run (GH-195 P6).** Exit 3 and exit 75 both mean
the command never executed, so step 5 records them via ``record_deferred`` and
leaves the failure counter untouched. Before P6 this module used ``ok = code == 0``,
which meant three "the machine is busy" refusals could — and did — permanently
quarantine a healthy job.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import breakers, classify, config, explain, registry, relief, routes


#: Route results that count as a successful dispatch. Anything else (error,
#: refused, unknown) means the finding is NOT safely delivered.
_OK_STATUSES = {"logged", "drafted", "notified", "filed", "dry-run"}


def _emit_path(job_id: str) -> Path:
    return config.state_dir() / "emit" / f"{job_id}.json"


def _classify_within_budget(job, finding: dict) -> None:
    """Fill severity via the classifier, but only within the job's LLM budget (B3).

    The stub classifier is free (offline); the real one must reserve budget BEFORE
    the call, so a job's ``[relief] llm_daily_max / llm_per_run_max`` caps are
    actually enforced instead of merely declared.
    """
    text = finding.get("text", finding.get("summary", ""))
    if config.classify_stubbed():
        classified = classify.classify(text)
    elif relief.budget_for(job, "llm").reserve(1):
        classified = classify.classify(text)
    else:
        finding["severity"] = "info"
        finding.setdefault("summary", "(classify skipped: LLM budget exhausted)")
        return
    finding["severity"] = classified.get("severity", "info")
    finding.setdefault("summary", classified.get("summary", ""))


def _process_emit(job) -> list[dict]:
    """If the job dropped a finding file, classify + route it.

    S7: the emit file is deleted ONLY when every route acknowledged. If any route
    failed (e.g. ``gh-issue`` errored), the finding is moved to a dead-letter
    directory instead of being discarded — verified-success-only, no lost evidence.
    """
    path = _emit_path(job.id)
    try:
        finding = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    finding.setdefault("source", job.id)
    if "severity" not in finding:
        _classify_within_budget(job, finding)
    results = routes.route(finding, job.routes)

    # S7: empty results means NO route consumed the finding (e.g. a route-less job)
    # — that is not success. Only delete when at least one route ran and all acked.
    all_ok = bool(results) and all(r.get("status") in _OK_STATUSES for r in results)
    if all_ok:
        path.unlink(missing_ok=True)
    else:
        dead = config.state_dir() / "emit" / "failed"
        dead.mkdir(parents=True, exist_ok=True)
        try:
            path.replace(dead / f"{job.id}.{os.getpid()}.json")
        except OSError:
            pass
    return results


def run_job(job_id: str, *, log=print) -> int:
    # 1 + 2: halt / inert — the inert-by-default guarantee at exec time.
    if breakers.global_halt():
        log(f"[3eyes] halted (kill-switch); {job_id} not run")
        return 0
    if not config.three_eyes_active():
        log(f"[3eyes] inert (no runtime.env / disabled); {job_id} not run")
        return 0

    try:
        job = registry.load_job(job_id)
    except registry.RegistryError as exc:
        log(f"[3eyes] {exc}")
        return 2

    # 2b: disabled jobs never run (S8) — enabled=false is an off switch, not decor.
    if not job.enabled:
        log(f"[3eyes] {job.id} is disabled (enabled=false); skipping")
        return 0

    breaker = breakers.FailureBreaker()
    # 3: breaker open → quarantined, unless the cooldown has elapsed and this run
    #    gets to be the half-open probe (P6). claim_probe is atomic and returns
    #    True at most once per cooldown, so concurrent wakes cannot both probe.
    if breaker.is_open(job.id):
        if breaker.claim_probe(job.id):
            log(f"[3eyes] {job.id} breaker half-open; taking the probe run")
        else:
            log(f"[3eyes] {job.id} is quarantined (breaker open); skipping")
            # Throttle (relief posture): the operator was already notified ONCE at
            # the moment the breaker opened (step 6 below). Re-notifying on every
            # subsequent skipped run would fire a banner every scheduling tick — a
            # 120s job would spam one every 2 minutes. Even the local findings log
            # cannot absorb that: 72 of 73 live records were this single line.
            # One notice per cooldown window is enough to show it is still parked.
            if breaker.should_notice_skip(job.id):
                routes.route(
                    {"source": job.id, "title": f"{job.id} quarantined",
                     "severity": "warn",
                     "summary": "breaker open — skipped run (throttled: at most "
                                "one notice per cooldown window)",
                     "text": ""},
                    ["log-only"],
                )
            return 0

    # 4: quiet hours
    if relief.in_quiet_hours(job.quiet_hours):
        log(f"[3eyes] {job.id} inside quiet hours {job.quiet_hours!r}; skipping")
        return 0

    # 5: run the allowlisted command under the guard. run_job_command resolves the
    # command from commands.allow itself (B1) against REPO_ROOT (B4) — run.py never
    # constructs a free-form argv.
    try:
        code = breakers.run_job_command(job)
    except registry.RegistryError as exc:
        log(f"[3eyes] {exc}")
        return 2
    # P6: three outcomes, not two. A guard refusal (75) or instance conflict (3)
    # means the command never ran — recording it as a failure is what latched
    # skill-sync's breaker for a day off the back of an unrelated regression.
    outcome = breakers.classify_exit(code)
    opened = False
    if outcome == "deferred":
        breaker.record_deferred(job.id, code)
        log(f"[3eyes] {job.id} deferred exit={code} (did not run; failure count unchanged)")
    else:
        opened = breaker.record(job.id, outcome == "ok", job.trip_after_failures)
        log(f"[3eyes] {job.id} finished exit={code} ok={outcome == 'ok'}"
            + (" — BREAKER OPENED (quarantined)" if opened else ""))

    # 6: route any finding the command emitted
    _process_emit(job)

    if opened:
        cooldown_min = breaker.status(job.id).get("cooldown_seconds", 0) // 60
        # P7b: explain the trip before announcing it. A breaker opening is the rare,
        # meaningful moment — three consecutive real failures — so it is worth one
        # judgement, where explaining every individual failure would spend the daily
        # budget on noise. `explain` suppresses known issues deterministically and
        # only reaches the model for genuine novelty.
        try:
            explanation = explain.explain(job, code)
        except Exception as exc:            # an explainer must not break the reporter
            log(f"[3eyes] explainer failed for {job.id}: {exc}")
            explanation = None

        if explanation and explanation["verdict"] == explain.KNOWN:
            # Suppressed: recorded, but no banner and no issue. This is the whole
            # point of the known-issues list — recurring noise becomes a quiet line
            # instead of a notification the operator learns to ignore.
            log(f"[3eyes] {job.id} trip suppressed by rule {explanation['rule']}")
            routes.route(explanation, explain.routes_for(job, explanation["verdict"]))
            return code

        finding = {
            "source": job.id, "title": f"{job.id} breaker opened", "severity": "error",
            "summary": f"{job.trip_after_failures} consecutive failures; "
                       f"will self-retry once in {cooldown_min}m",
            "text": "",
        }
        if explanation:
            finding["summary"] += f" — {explanation['summary']}"
            finding["text"] = explanation["text"]
            if explanation.get("next_step"):
                finding["summary"] += f" Next: {explanation['next_step']}"
        routes.route(
            finding,
            [r for r in job.routes if r in ("notify", "log-only", "gh-issue")] or ["log-only"],
        )
    return code


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m three_eyes.run <job-id>", file=sys.stderr)
        return 2
    return run_job(argv[0])


if __name__ == "__main__":
    raise SystemExit(main())
