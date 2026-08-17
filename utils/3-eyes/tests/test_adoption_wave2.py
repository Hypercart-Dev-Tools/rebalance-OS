"""Wave 2 launchd-adoption contract (GH-195 P8)."""

from __future__ import annotations

from three_eyes import registry


HOURS = range(6, 24)

ADOPTED = {
    "pulse-sync": {
        "label": "com.rebalance-os.pulse-sync",
        "calendar": [{"Hour": hour, "Minute": 0} for hour in HOURS],
    },
    "pulse-web-sync": {
        "label": "com.rebalance-os.pulse-web-sync",
        "calendar": [
            {"Hour": hour, "Minute": minute}
            for hour in HOURS
            for minute in (8, 38)
        ],
    },
    "pulse-warning-watch": {
        "label": "com.rebalance-os.pulse-warning-watch",
        "calendar": [{"Minute": minute} for minute in (7, 22, 37, 52)],
    },
    "obsidian-daily-sync": {
        "label": "com.rebalance-os.obsidian-daily-sync",
        "calendar": {"Hour": 18, "Minute": 20},
    },
    "obsidian-rollover": {
        "label": "com.rebalance-os.obsidian-rollover",
        "calendar": {"Hour": 0, "Minute": 40},
    },
    "stickies2obsidian": {
        "label": "com.user.stickies2obsidian",
        "interval": 300,
    },
}


def _jobs():
    return {job.id: job for job in registry.load_jobs(include_local=False)}


def test_wave2_adoptions_are_allowlisted_and_replace_incumbents():
    jobs = _jobs()
    allow = registry.load_commands_allow(include_local=False)

    for job_id, expected in ADOPTED.items():
        job = jobs[job_id]
        assert job.command in allow
        assert expected["label"] in job.supersedes


def test_wave2_adoption_schedules_exactly_match_live_plists():
    jobs = _jobs()

    for job_id, expected in ADOPTED.items():
        job = jobs[job_id]
        if "calendar" in expected:
            assert job.launchd_calendar() == expected["calendar"]
            assert job.launchd_interval() is None
        else:
            assert job.launchd_interval() == expected["interval"]
            assert job.launchd_calendar() is None
