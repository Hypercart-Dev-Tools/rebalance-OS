"""Wave 1 launchd-adoption contract (GH-195 P8)."""

from __future__ import annotations

from three_eyes import registry


ADOPTED = {
    "daily-sync": {
        "label": "com.rebalance-os.daily-sync",
        "calendar": {"Hour": 6, "Minute": 30},
    },
    "github-sync": {
        "label": "com.rebalance-os.github-sync",
        "calendar": [{"Hour": hour, "Minute": 45} for hour in range(6, 24)],
    },
    "vault-sync": {
        "label": "com.rebalance-os.vault-sync",
        "calendar": [{"Hour": hour, "Minute": 15} for hour in range(6, 24)],
    },
}


def _jobs():
    return {job.id: job for job in registry.load_jobs(include_local=False)}


def _runs_health_issue_reporter(job, allow):
    command = allow[job.command]
    return "scripts/health_issue_reporter.py" in command["args"]


def test_wave1_adoptions_are_allowlisted_and_replace_incumbents():
    jobs = _jobs()
    allow = registry.load_commands_allow(include_local=False)

    for job_id, expected in ADOPTED.items():
        job = jobs[job_id]
        assert job.command in allow
        assert expected["label"] in job.supersedes


def test_wave1_adoption_schedules_exactly_match_live_plists():
    jobs = _jobs()
    for job_id, expected in ADOPTED.items():
        assert jobs[job_id].launchd_calendar() == expected["calendar"]


def test_health_issue_reporter_has_no_concurrent_enabled_3eyes_owner():
    """#139: the legacy emitters stay superseded, never independently adopted."""
    jobs = _jobs()
    allow = registry.load_commands_allow(include_local=False)
    enabled_reporters = [
        job for job in jobs.values()
        if job.enabled and _runs_health_issue_reporter(job, allow)
    ]

    assert len(enabled_reporters) <= 1
    assert not enabled_reporters
    assert set(jobs["collector-health"].supersedes) == {
        "com.rebalance-os.health-check",
        "com.rebalance-os.health-check-triage",
    }
