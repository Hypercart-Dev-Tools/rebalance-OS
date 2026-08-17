"""Regression tests for the GH-195 Codex review fixes (B1–B4, S6–S8)."""

from __future__ import annotations

import json

import pytest

from three_eyes import breakers, classify, config, cron, registry, relief, routes, run


# ----------------------- B1: no free-form execution ----------------------- #

def test_run_job_command_refuses_when_inert():
    job = registry.load_job("selfcheck")
    with pytest.raises(PermissionError):
        breakers.run_job_command(job)


def test_run_job_command_refuses_command_not_in_allowlist(activate):
    activate()
    job = registry.Job(id="evil", command="rm-rf-slash")
    with pytest.raises(registry.RegistryError):
        breakers.run_job_command(job)


# ------------------- B4: resolve against REPO_ROOT ------------------------ #

def test_resolve_argv_makes_relative_exec_absolute_against_repo_root():
    argv = breakers._resolve_argv({"exec": ".venv/bin/python", "args": ["README.md", "--flag"]})
    assert argv[0] == str(config.REPO_ROOT / ".venv/bin/python")   # not caller CWD
    assert argv[1] == str(config.REPO_ROOT / "README.md")          # existing rel path resolved
    assert argv[2] == "--flag"                                     # non-path arg untouched


def test_resolve_argv_leaves_absolute_exec_alone():
    argv = breakers._resolve_argv({"exec": "/bin/echo", "args": ["hi"]})
    assert argv == ["/bin/echo", "hi"]


# --------------------- B2: cron injection blocked ------------------------- #

def test_cron_expr_problem_accepts_valid_and_rejects_injection():
    assert registry.cron_expr_problem("*/30 * * * *") is None
    assert registry.cron_expr_problem("* * * * * ; rm -rf ~") is not None   # extra fields/chars
    assert registry.cron_expr_problem("*/5 * * * *\nMAILTO=x") is not None  # newline
    assert registry.cron_expr_problem("* * * *") is not None                # too few fields


def test_validate_rejects_unsafe_job_id(tmp_path):
    reg = tmp_path / "registry"
    (reg / "jobs.d").mkdir(parents=True)
    (reg / "commands.allow").write_text('[commands.noop]\nexec="/bin/echo"\nargs=[]\ndescription="n"\n')
    (reg / "routes.toml").write_text('[routes.log-only]\ndescription="l"\n')
    (reg / "jobs.d" / "b.toml").write_text(
        'id = "bad; rm -rf"\ncommand="noop"\nroutes=["log-only"]\n[schedule.launchd]\nStartInterval=60\n')
    problems = registry.validate(reg)
    assert any("unsafe job id" in p for p in problems)


def test_render_cron_line_raises_on_bad_expr():
    job = registry.Job(id="x", command="noop", schedule={"cron": {"expr": "* * * * * ; evil"}})
    with pytest.raises(registry.RegistryError):
        cron.render_cron_line(job)


# --------------------- B3: LLM budget is enforced ------------------------- #

def test_budget_reserve_enforces_daily_cap():
    b = relief.Budget("llm", daily_max=2, per_run_max=None)
    assert b.reserve() is True
    assert b.reserve() is True
    assert b.reserve() is False           # daily cap hit
    # A fresh run this same day still sees it exhausted (persisted).
    assert relief.Budget("llm", daily_max=2, per_run_max=None).reserve() is False


def test_classify_skipped_when_budget_exhausted(activate, monkeypatch):
    activate()   # active, NOT stubbed
    monkeypatch.setattr(classify, "classify",
                        lambda *a, **k: pytest.fail("classify called despite exhausted budget"))
    job = registry.Job(id="j", command="noop", relief={"llm_per_run_max": 0, "llm_daily_max": 0})
    finding = {"text": "boom"}
    run._classify_within_budget(job, finding)
    assert finding["severity"] == "info"
    assert "budget" in finding["summary"].lower()


# ------------------- S7: emit dead-letter on failure ---------------------- #

def test_emit_moved_to_deadletter_when_route_fails(activate, monkeypatch):
    activate()
    job = registry.load_job("selfcheck")
    emit = config.state_dir() / "emit"
    emit.mkdir(parents=True, exist_ok=True)
    (emit / "selfcheck.json").write_text(json.dumps({"title": "x", "severity": "warn", "text": "t"}))
    monkeypatch.setattr(routes, "route", lambda f, r, **k: [{"route": "gh-issue", "status": "error"}])
    run._process_emit(job)
    assert not (emit / "selfcheck.json").exists()          # not left in place
    failed = list((emit / "failed").glob("selfcheck.*.json"))
    assert len(failed) == 1                                 # preserved as evidence


def test_zero_route_finding_is_deadlettered_not_deleted(activate):
    """S7 round-2: a route-less job's finding is preserved, not silently dropped."""
    activate()
    job = registry.Job(id="noroute", command="noop", routes=(),
                       schedule={"launchd": {"StartInterval": 60}})
    emit = config.state_dir() / "emit"
    emit.mkdir(parents=True, exist_ok=True)
    (emit / "noroute.json").write_text(json.dumps({"title": "x", "severity": "warn", "text": "t"}))
    run._process_emit(job)
    assert not (emit / "noroute.json").exists()
    assert list((emit / "failed").glob("noroute.*.json"))     # preserved


def test_cron_render_block_skips_disabled_jobs():
    """S8 round-2: cron does not schedule enabled=false jobs (parity with launchd)."""
    from three_eyes import cron
    on = registry.Job(id="on", command="noop", enabled=True, schedule={"cron": {"expr": "*/5 * * * *"}})
    off = registry.Job(id="off", command="noop", enabled=False, schedule={"cron": {"expr": "*/5 * * * *"}})
    block = cron.render_block([on, off])
    assert "run-job.sh on" in block
    assert "run-job.sh off" not in block


def test_emit_deleted_when_all_routes_ok(activate, monkeypatch):
    activate()
    job = registry.load_job("selfcheck")
    emit = config.state_dir() / "emit"
    emit.mkdir(parents=True, exist_ok=True)
    (emit / "selfcheck.json").write_text(json.dumps({"title": "x", "severity": "warn", "text": "t"}))
    monkeypatch.setattr(routes, "route", lambda f, r, **k: [{"route": "log-only", "status": "logged"}])
    run._process_emit(job)
    assert not (emit / "selfcheck.json").exists()
    assert not (emit / "failed").exists() or not list((emit / "failed").glob("*"))


# --------------------- S8: enabled=false is honored ----------------------- #

def test_disabled_job_is_skipped(activate, monkeypatch):
    activate()
    disabled = registry.Job(id="off", command="noop", enabled=False,
                            schedule={"launchd": {"StartInterval": 60}})
    monkeypatch.setattr(registry, "load_job", lambda job_id, **k: disabled)
    monkeypatch.setattr(breakers, "run_job_command",
                        lambda job: pytest.fail("ran a disabled job"))
    assert run.run_job("off") == 0
