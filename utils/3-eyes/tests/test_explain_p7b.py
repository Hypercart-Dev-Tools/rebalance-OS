"""P7b failure explainer + known-issues suppression (GH-195).

The load-bearing property here is NOT "the model gives good answers" — it is that
the cheap deterministic stage runs first and correctly, because that is what makes
the `gh-issue` route safe to enable in P8. #139 was closed by *deleting* a
duplicate-issue emitter; a supervisor that files an issue for every recurring,
already-understood failure recreates that defect.

The second property is that suppression fails OPEN. A rule is a decision to stop
looking, so every way a rule can be wrong (unreadable file, broken regex, expired
date) must result in reporting the failure, never in hiding it.
"""

from __future__ import annotations

from datetime import date

import pytest

from three_eyes import breakers, classify, explain, registry, routes, run


KNOWN_LOG = "sleuth has not advanced in 9 days; no new messages"
NOVEL_LOG = "Traceback: ValueError: unexpected column 'widget_id' in projection"


# --------------------------------------------------------------------------- #
# Stage 1 — deterministic suppression
# --------------------------------------------------------------------------- #

def test_a_known_issue_is_suppressed_without_any_model_call(activate, monkeypatch):
    """The cost argument: recurring failures must cost nothing.

    They are the high-volume ones, so suppressing them for free is what keeps the
    daily LLM budget available for genuine novelty.
    """
    activate()
    called = []
    monkeypatch.setattr(classify, "explain_failure", lambda *a, **k: called.append(1) or {})

    job = registry.load_job("selfcheck")
    result = explain.explain(job, code=1, evidence=KNOWN_LOG)

    assert called == [], "a known issue reached the model"
    assert result["verdict"] == explain.KNOWN
    assert result["rule"] == "sleuth-staleness"
    assert result["severity"] == "info"
    assert "152" in result["summary"], "a suppressed issue must still name its tracking issue"


def test_a_suppressed_issue_gets_no_banner_and_no_github_issue():
    """Suppression converts noise into a quiet record — that is the entire point."""
    job = registry.load_job("collector-health")     # routes: pdda-inbox, notify
    assert explain.routes_for(job, explain.KNOWN) == ["log-only"]


def test_a_novel_failure_keeps_the_jobs_real_routes():
    job = registry.load_job("collector-health")
    got = explain.routes_for(job, explain.NEW)
    assert "notify" in got and "log-only" not in got


def test_an_unmatched_failure_reaches_the_model(activate, monkeypatch):
    activate()
    monkeypatch.setattr(classify, "explain_failure", lambda *a, **k: {
        "severity": "error", "headline": "schema drift", "summary": "unexpected column",
        "next_step": "check the projection",
    })

    result = explain.explain(registry.load_job("selfcheck"), code=1, evidence=NOVEL_LOG)

    assert result["verdict"] == explain.NEW
    assert result["model_used"] is True
    assert "schema drift" in result["title"]
    assert result["next_step"] == "check the projection"


# --------------------------------------------------------------------------- #
# Suppression must fail OPEN — every way a rule can be wrong
# --------------------------------------------------------------------------- #

def test_an_unreadable_rules_file_suppresses_nothing(tmp_path):
    """Failing closed here would silence real failures. Worse than a false alarm."""
    missing = tmp_path / "nope.toml"
    assert explain.load_rules(missing) == []
    assert explain.match_known_issue("selfcheck", KNOWN_LOG, rules=[]) is None


def test_malformed_toml_suppresses_nothing(tmp_path):
    bad = tmp_path / "known_issues.toml"
    bad.write_text("[[rule]\nid = broken")
    assert explain.load_rules(bad) == []


def test_a_broken_regex_suppresses_nothing_but_others_still_match():
    rules = [
        {"id": "bad", "pattern": "([unclosed", "reason": "x"},
        {"id": "good", "pattern": "sleuth", "reason": "y"},
    ]
    got = explain.match_known_issue("selfcheck", KNOWN_LOG, rules=rules)
    assert got is not None and got["id"] == "good"


def test_an_expired_rule_stops_suppressing():
    """A suppression with a shelf life that has run out must start reporting again."""
    rules = [{"id": "temp", "pattern": "sleuth", "reason": "x", "expires": "2026-01-01"}]
    assert explain.match_known_issue("s", KNOWN_LOG, rules=rules, today=date(2026, 7, 28)) is None
    assert explain.match_known_issue("s", KNOWN_LOG, rules=rules, today=date(2025, 12, 1)) is not None


def test_an_unparseable_expiry_does_not_silently_disable_the_rule():
    rules = [{"id": "temp", "pattern": "sleuth", "reason": "x", "expires": "not-a-date"}]
    assert explain.match_known_issue("s", KNOWN_LOG, rules=rules) is not None


def test_a_rule_scoped_to_other_jobs_does_not_match():
    rules = [{"id": "scoped", "pattern": "sleuth", "reason": "x", "jobs": ["other-job"]}]
    assert explain.match_known_issue("selfcheck", KNOWN_LOG, rules=rules) is None
    assert explain.match_known_issue("other-job", KNOWN_LOG, rules=rules) is not None


def test_database_is_locked_is_NOT_suppressed():
    """It was on the original GH-146 known-issues list. That was wrong.

    The DB is WAL with a 30s busy timeout, so an abort proves a writer held the lock
    for 30+ continuous seconds — a real defect (#222 / #171). A rule for it would
    have kept a genuine bug invisible for as long as the rule stood.
    """
    got = explain.match_known_issue(
        "vault-sync", "sqlite3.OperationalError: database is locked"
    )
    assert got is None, "a real ingest defect is being suppressed as a known issue"


def test_the_shipped_rules_all_carry_a_tracking_issue_or_an_expiry():
    """A rule with neither is permanent silence, which is how a regression hides."""
    naked = [r["id"] for r in explain.load_rules() if not r.get("issue") and not r.get("expires")]
    assert not naked, f"rules with no issue and no expiry: {naked}"


# --------------------------------------------------------------------------- #
# Budget + availability
# --------------------------------------------------------------------------- #

def test_no_model_call_when_inert(monkeypatch):
    called = []
    monkeypatch.setattr(classify, "explain_failure", lambda *a, **k: called.append(1) or {})
    result = explain.explain(registry.load_job("selfcheck"), code=1, evidence=NOVEL_LOG)
    assert called == []
    assert result["verdict"] == explain.UNJUDGED
    assert result["severity"] == "error", "an unjudged failure must not be downgraded to info"


def test_budget_exhaustion_leaves_the_failure_UNJUDGED_not_benign(activate, monkeypatch):
    """Running out of budget must never be mistaken for "nothing is wrong"."""
    activate()
    monkeypatch.setattr(classify, "explain_failure", lambda *a, **k: {"summary": "should not run"})
    job = registry.load_job("collector-health")
    for _ in range(20):
        explain.relief.budget_for(job, "llm").reserve(1)

    result = explain.explain(job, code=1, evidence=NOVEL_LOG)

    assert result["verdict"] == explain.UNJUDGED
    assert result["model_used"] is False
    assert result["severity"] == "error"


def test_a_throwing_classifier_does_not_take_the_job_down(activate, monkeypatch):
    """An explainer that raises would turn one broken job into two."""
    activate()
    def _boom(*a, **k):
        raise RuntimeError("ollama exploded")
    monkeypatch.setattr(classify, "explain_failure", _boom)

    result = explain.explain(registry.load_job("selfcheck"), code=1, evidence=NOVEL_LOG)
    assert result["verdict"] == explain.UNJUDGED
    assert "ollama exploded" in result["summary"]


# --------------------------------------------------------------------------- #
# The run.py hook
# --------------------------------------------------------------------------- #

def _trip(job_id: str, monkeypatch, seen: list):
    monkeypatch.setattr(breakers, "run_job_command", lambda job: 1)
    monkeypatch.setattr(routes, "route",
                        lambda finding, rts, **k: seen.append((finding, list(rts))) or [])
    for _ in range(3):
        run.run_job(job_id)


def test_a_trip_from_a_known_issue_is_suppressed_end_to_end(activate, monkeypatch):
    activate()
    monkeypatch.setattr(explain, "gather_evidence", lambda *a, **k: KNOWN_LOG)
    monkeypatch.setattr(classify, "explain_failure",
                        lambda *a, **k: pytest.fail("a known issue reached the model"))
    seen: list = []
    _trip("selfcheck", monkeypatch, seen)

    assert breakers.FailureBreaker().is_open("selfcheck") is True, "the breaker must still trip"
    finding, rts = seen[-1]
    assert rts == ["log-only"], "a suppressed trip raised a banner"
    assert "known issue" in finding["title"]


def test_a_trip_from_a_NOVEL_failure_is_announced_with_the_explanation(activate, monkeypatch):
    activate()
    monkeypatch.setattr(explain, "gather_evidence", lambda *a, **k: NOVEL_LOG)
    monkeypatch.setattr(classify, "explain_failure", lambda *a, **k: {
        "severity": "error", "headline": "schema drift",
        "summary": "unexpected column in projection", "next_step": "check the projection",
    })
    seen: list = []
    _trip("selfcheck", monkeypatch, seen)

    finding, rts = seen[-1]
    assert "breaker opened" in finding["title"]
    assert "unexpected column in projection" in finding["summary"]
    assert "Next: check the projection" in finding["summary"]
    assert rts == ["log-only"], "selfcheck's only route is log-only"


def test_an_explainer_crash_still_announces_the_trip(activate, monkeypatch):
    """The reporter must survive its own analysis failing."""
    activate()
    def _boom(*a, **k):
        raise RuntimeError("explainer died")
    monkeypatch.setattr(explain, "explain", _boom)
    seen: list = []
    _trip("selfcheck", monkeypatch, seen)

    assert any("breaker opened" in f.get("title", "") for f, _ in seen), (
        "the trip went unannounced because the explainer crashed"
    )


# --------------------------------------------------------------------------- #
# Defects found by the agy QA relay (2026-07-28)
# --------------------------------------------------------------------------- #

def test_suppression_rules_are_scoped_to_jobs(monkeypatch):
    """QA finding 5: an unscoped rule silences failures it was never meant to cover.

    "interrupted system call" is a generic EINTR string that can surface in a database
    write or any syscall-heavy collector, and a bare "403 rate limit" can come from an
    API that has nothing to do with GitHub.
    """
    for rule in explain.load_rules():
        if rule["id"] in ("python-bootstrap-errno-4", "github-403-rate-limit"):
            assert rule.get("jobs"), f"{rule['id']} is unscoped and applies fleet-wide"


def test_a_generic_EINTR_elsewhere_is_not_suppressed():
    """The concrete scenario: EINTR during a DB write, not interpreter bootstrap."""
    got = explain.match_known_issue(
        "some-other-job", "sqlite3.OperationalError: interrupted system call during commit"
    )
    assert got is None, "a generic EINTR was suppressed by the bootstrap rule"


def test_a_non_github_403_is_not_suppressed():
    got = explain.match_known_issue("daily-sync", "Figma API returned 403 forbidden")
    assert got is None, "an unrelated 403 was suppressed by the GitHub rate-limit rule"


def test_the_real_github_403_is_still_suppressed():
    """The scoping must not break the suppression it exists to provide."""
    got = explain.match_known_issue(
        "collector-health",
        "GitHub API request failed: 403 https://api.github.com/repos/x/y/issues",
    )
    assert got is not None and got["id"] == "github-403-rate-limit"
