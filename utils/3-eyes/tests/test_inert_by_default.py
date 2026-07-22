"""The flagship guarantee: inert by default (GH-195).

With no runtime.env, 3-Eyes must be a clean no-op — zero network / ollama / gh /
launchd mutation. These tests PROVE it rather than assert it: egress primitives are
monkeypatched to blow up if ever called, and the entrypoints are driven anyway.
"""

from __future__ import annotations

import pytest

from three_eyes import classify, config, launchd, registry, routes, run


def test_gate_is_closed_without_runtime_env():
    assert config.three_eyes_active() is False


def test_run_job_is_a_noop_when_inert(monkeypatch):
    # Any attempt to actually execute a command would go through run_job_command.
    import three_eyes.breakers as breakers
    monkeypatch.setattr(
        breakers, "run_job_command",
        lambda *a, **k: pytest.fail("run_job_command called while inert"),
    )
    assert run.run_job("selfcheck") == 0


def test_classify_makes_no_network_call_when_inert(monkeypatch):
    import urllib.request
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda *a, **k: pytest.fail("classify hit the network while inert"),
    )
    result = classify.classify("fatal error: kernel panic")
    assert result.get("refused") is True


def test_gh_route_refuses_and_never_shells_out_when_inert(monkeypatch):
    import three_eyes.routes as routes_mod
    monkeypatch.setattr(
        routes_mod.subprocess, "run",
        lambda *a, **k: pytest.fail("gh route shelled out while inert"),
    )
    [res] = routes.route({"title": "x", "text": "y"}, ["gh-issue"])
    assert res["status"] == "refused-inert"


def test_pdda_and_notify_routes_refuse_when_inert(monkeypatch):
    import three_eyes.routes as routes_mod
    monkeypatch.setattr(
        routes_mod.subprocess, "run",
        lambda *a, **k: pytest.fail("a route shelled out while inert"),
    )
    results = routes.route({"title": "x", "text": "y", "summary": "s"}, ["pdda-inbox", "notify"])
    assert all(r["status"] == "refused-inert" for r in results)


def test_log_only_route_is_inert_safe():
    # log-only is the one route that works inert (local append, no egress).
    [res] = routes.route({"title": "x", "text": "y"}, ["log-only"])
    assert res["status"] == "logged"


def test_launchd_install_refuses_when_inert():
    job = registry.load_job("selfcheck")
    with pytest.raises(PermissionError):
        launchd.install(job)


def test_kill_switch_forces_inert_even_when_enabled(monkeypatch, tmp_path):
    # Activate, then engage the hard kill-switch: gate must still be closed.
    env = tmp_path / "runtime.env"
    env.write_text("THREE_EYES_ENABLE=1\n")
    monkeypatch.setenv("THREE_EYES_RUNTIME_ENV", str(env))
    assert config.three_eyes_active() is True
    monkeypatch.setenv("THREE_EYES_ENABLE", "0")   # explicit off beats the file
    assert config.three_eyes_active() is False


def test_panic_file_forces_inert(monkeypatch, tmp_path, activate):
    activate()
    assert config.three_eyes_active() is True
    config.panic_file().parent.mkdir(parents=True, exist_ok=True)
    config.panic_file().write_text("halt")
    assert config.three_eyes_active() is False
