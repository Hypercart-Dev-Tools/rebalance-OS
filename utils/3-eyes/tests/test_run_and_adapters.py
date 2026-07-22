"""End-to-end run loop (active) + launchd/cron adapters (GH-195)."""

from __future__ import annotations

import json
import plistlib

import pytest

from three_eyes import breakers, config, cron, launchd, registry, routes, run


# ------------------------------ run loop ---------------------------------- #

def test_active_run_executes_guarded_and_succeeds(activate, monkeypatch):
    activate()
    calls = {}

    def _fake(job):
        calls["job"] = job.id
        return 0

    monkeypatch.setattr(breakers, "run_job_command", _fake)
    assert run.run_job("selfcheck") == 0
    assert calls["job"] == "selfcheck"


def test_consecutive_failures_open_the_breaker_and_route(activate, monkeypatch):
    activate()
    monkeypatch.setattr(breakers, "run_job_command", lambda job: 1)   # always fail
    logged = []
    monkeypatch.setattr(routes, "route", lambda finding, rts, **k: logged.append(finding) or [])
    # selfcheck trip_after_failures = 3
    run.run_job("selfcheck")
    run.run_job("selfcheck")
    run.run_job("selfcheck")   # opens here
    assert breakers.FailureBreaker().is_open("selfcheck") is True
    assert any("breaker opened" in f.get("title", "") for f in logged)


def test_quarantined_job_is_skipped(activate, monkeypatch):
    activate()
    breakers.FailureBreaker().quarantine("selfcheck")
    monkeypatch.setattr(breakers, "run_job_command",
                        lambda job: pytest.fail("ran a quarantined job"))
    assert run.run_job("selfcheck") == 0


def test_quarantined_skip_does_not_renotify(activate, monkeypatch):
    """Throttle: a job that is ALREADY quarantined re-routes only to log-only on each
    skipped run — never `notify`. The operator was banner-alerted once when it opened;
    re-notifying every scheduling tick (a 120s job → every 2 min) would be spam."""
    activate()
    breakers.FailureBreaker().quarantine("selfcheck")
    seen = []
    monkeypatch.setattr(routes, "route",
                        lambda finding, rts, **k: seen.append(list(rts)) or [])
    run.run_job("selfcheck")
    assert seen == [["log-only"]]   # exactly one route call, log-only only


def test_emitted_finding_is_routed(activate, monkeypatch):
    activate()
    monkeypatch.setattr(breakers, "run_job_command", lambda job: 0)
    emit = config.state_dir() / "emit"
    emit.mkdir(parents=True, exist_ok=True)
    (emit / "selfcheck.json").write_text(json.dumps(
        {"title": "found something", "severity": "warn", "summary": "s", "text": "t"}))
    routed = []
    monkeypatch.setattr(routes, "route", lambda finding, rts, **k: routed.append(finding) or [])
    run.run_job("selfcheck")
    assert any(f.get("title") == "found something" for f in routed)
    assert not (emit / "selfcheck.json").exists()   # consumed


def test_unknown_job_is_config_error(activate):
    activate()
    assert run.run_job("does-not-exist") == 2


# ----------------------------- launchd ------------------------------------ #

def test_render_plist_is_valid_and_labeled():
    job = registry.load_job("selfcheck")
    data = plistlib.loads(launchd.render_plist(job))
    assert data["Label"] == "com.rebalance-os.3eyes.selfcheck"
    assert data["StartInterval"] == 3600
    assert data["ProgramArguments"][0] == "/bin/bash"
    assert data["RunAtLoad"] is False


def test_observe_existing_reads_and_tags(monkeypatch, tmp_path):
    agents_dir = tmp_path / "LaunchAgents"
    agents_dir.mkdir()
    with open(agents_dir / "com.rebalance-os.3eyes.selfcheck.plist", "wb") as fh:
        plistlib.dump({"Label": "com.rebalance-os.3eyes.selfcheck",
                       "ProgramArguments": ["/bin/echo"], "StartInterval": 3600}, fh)
    with open(agents_dir / "com.other.thing.plist", "wb") as fh:
        plistlib.dump({"Label": "com.other.thing", "ProgramArguments": ["/bin/true"]}, fh)
    monkeypatch.setattr(launchd, "LAUNCH_AGENTS_DIR", agents_dir)

    agents = {a["label"]: a for a in launchd.observe_existing()}
    assert agents["com.rebalance-os.3eyes.selfcheck"]["managed_by_3eyes"] is True
    assert agents["com.other.thing"]["managed_by_3eyes"] is False


# ------------------------------- cron ------------------------------------- #

def test_shim_selects_a_tomllib_capable_python():
    """Regression: launchd's minimal PATH resolves `python3` to system 3.9 (no
    tomllib). The shim must SELECT a >=3.11 interpreter, not bare-exec python3."""
    shim = (config.ROOT / "shims" / "run-job.sh").read_text()
    assert "import tomllib" in shim, "shim must probe for a tomllib-capable python"
    assert ".venv/bin/python" in shim, "shim should prefer the repo venv python"
    assert "exec python3 -m" not in shim, "shim must not bare-exec python3 (may be 3.9)"


def test_cron_line_and_block(tmp_path):
    reg = tmp_path / "registry"
    (reg / "jobs.d").mkdir(parents=True)
    (reg / "commands.allow").write_text('[commands.noop]\nexec="/bin/echo"\nargs=[]\ndescription="n"\n')
    (reg / "routes.toml").write_text('[routes.log-only]\ndescription="l"\n')
    (reg / "jobs.d" / "c.toml").write_text(
        'id="c"\ncommand="noop"\nroutes=["log-only"]\n[schedule.cron]\nexpr="*/30 * * * *"\n')
    jobs = registry.load_jobs(reg)
    line = cron.render_cron_line(jobs[0])
    assert line.startswith("*/30 * * * *") and "run-job.sh c" in line
    block = cron.render_block(jobs)
    assert cron.BEGIN in block and cron.END in block
