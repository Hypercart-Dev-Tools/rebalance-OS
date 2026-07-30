"""Wave 3 local-overlay adoption contract (GH-195 P8)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from three_eyes import breakers, dashboard, registry


THREE_EYES_DIR = Path(__file__).resolve().parents[1]
REGISTRY_DIR = THREE_EYES_DIR / "registry"
LOCAL_DIR = REGISTRY_DIR / "jobs.local.d"

ADOPTED = {
    "prompt-log-to-md": {
        "label": "com.claude.prompt-log-to-md",
        "interval": 300,
    },
    "ga-pull-binoid": {
        "label": "com.neochro.ga-pull-binoid",
        "calendar": {"Hour": 10, "Minute": 0},
    },
    "ga-pull-bounce": {
        "label": "com.neochro.ga-pull-bounce",
        "calendar": {"Hour": 10, "Minute": 5},
    },
    "ga-pull-bloomz": {
        "label": "com.neochro.ga-pull-bloomz",
        "calendar": {"Hour": 10, "Minute": 10},
    },
    "hq-rollup": {
        "label": "com.neochro.hq-rollup",
        "calendar": {"Hour": 17, "Minute": 50},
    },
    "servers-monitor": {
        "label": "com.neochro.servers-monitor",
        "interval": 1800,
    },
    "git-pulse": {
        "label": "com.user.git-pulse",
        "interval": 3600,
    },
    "hq-marathon-scan": {
        "label": "com.xyz-3-agents-swarm.hq-marathon-scan",
        "interval": 3600,
    },
}


def _jobs(*, include_local: bool):
    return {
        job.id: job
        for job in registry.load_jobs(REGISTRY_DIR, include_local=include_local)
    }


def test_wave3_jobs_are_local_only_and_replace_the_live_agents():
    local_jobs = _jobs(include_local=True)
    committed_jobs = _jobs(include_local=False)

    for job_id, expected in ADOPTED.items():
        job = local_jobs[job_id]
        assert job.source_path == LOCAL_DIR / f"{job_id}.toml"
        assert job_id not in committed_jobs
        assert expected["label"] in job.supersedes


def test_wave3_schedules_exactly_match_live_plists():
    jobs = _jobs(include_local=True)

    for job_id, expected in ADOPTED.items():
        job = jobs[job_id]
        if "calendar" in expected:
            assert job.launchd_calendar() == expected["calendar"]
            assert job.launchd_interval() is None
        else:
            assert job.launchd_interval() == expected["interval"]
            assert job.launchd_calendar() is None


def test_wave3_command_template_has_all_fixed_commands_without_machine_paths():
    example = REGISTRY_DIR / "commands.local.allow.example"
    text = example.read_text()
    with example.open("rb") as fh:
        commands = tomllib.load(fh)["commands"]

    assert set(ADOPTED) <= set(commands)
    assert "/Users/noelsaw" not in text
    assert all("/ABSOLUTE/PATH/" in str(spec["exec"]) or spec["exec"] == "/bin/bash"
               for job_id, spec in commands.items() if job_id in ADOPTED)

    ga = commands["ga-pull-binoid"]
    assert "Documents/GH Repos" in ga["exec"]
    assert breakers._resolve_argv(ga) == [ga["exec"], *ga["args"]]
    assert commands["hq-rollup"]["args"] == [
        "-l",
        "-c",
        '"/ABSOLUTE/PATH/Documents/GH Repos/xyz-3-agents-swarm/utils/hq/rollup.sh"',
    ]


def test_wave3_never_leaks_machine_paths_into_the_committed_registry_or_dashboard():
    committed = [* (REGISTRY_DIR / "jobs.d").glob("*.toml"),
                 REGISTRY_DIR / "commands.allow",
                 REGISTRY_DIR / "commands.local.allow.example"]
    assert all("/Users/noelsaw" not in path.read_text() for path in committed)

    rendered = dashboard.render(REGISTRY_DIR)
    assert rendered == (THREE_EYES_DIR / "DASHBOARD.md").read_text()
    assert all(job_id not in rendered for job_id in ADOPTED)
