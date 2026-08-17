"""P7a daily digest — the first surface that actually asks the model a question (GH-195).

Context for anyone changing this: before P7a, `classify()` had never once run in
production. It was reachable only from `run._process_emit`, which fires when a job
drops a finding file, and no job had ever dropped one. That is why the markdown-fence
bug below sat undetected since P5 — an unexercised code path cannot fail.

So these tests care about two things in particular:
  1. The digest still costs nothing and emits nothing when 3-Eyes is inert.
  2. The model's reply is parsed the way the model actually replies, not the way the
     API documentation says it will.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from three_eyes import classify, config, digest, registry, relief


UTC_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# The fence bug — a latent P5 defect the first live run exposed
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "reply",
    [
        '{"severity": "error", "summary": "vault-sync is failing"}',
        '```json\n{"severity": "error", "summary": "vault-sync is failing"}\n```',
        '```\n{"severity": "error", "summary": "vault-sync is failing"}\n```',
        '  ```json\n{"severity": "error", "summary": "vault-sync is failing"}\n```  ',
    ],
    ids=["bare", "fenced-json", "fenced-plain", "fenced-with-whitespace"],
)
def test_model_json_survives_a_markdown_fence(reply):
    """Ollama's `format: "json"` is a request, not a guarantee.

    The very first live digest run came back as ```` ```json … ``` ````, so a
    perfectly good ranked summary was discarded to the `raw` branch and the
    operator's "summary" became the fenced blob verbatim.
    """
    parsed = classify._parse_model_json(reply)
    assert parsed is not None, "a fenced reply was thrown away"
    assert parsed["severity"] == "error"
    assert parsed["summary"] == "vault-sync is failing"


@pytest.mark.parametrize(
    "reply", ["", "   ", "I could not analyse that.", "```\n```", "[1, 2, 3]", None]
)
def test_a_genuinely_non_json_reply_is_reported_as_such(reply):
    """The fence fix must not turn "not JSON" into a silent empty dict.

    A bare list is JSON but not the object shape callers destructure, so it is
    rejected too — otherwise `parsed.setdefault` would explode downstream.
    """
    assert classify._parse_model_json(reply) is None


# --------------------------------------------------------------------------- #
# Inert-by-default still holds with a new spender in the system
# --------------------------------------------------------------------------- #

def test_digest_makes_no_model_call_when_inert(monkeypatch):
    """Invariant 1 must survive P7a. No runtime.env => no model, ever."""
    called = []
    monkeypatch.setattr(classify, "summarize_digest",
                        lambda *a, **k: called.append(1) or {"summary": "x"})
    finding = digest.build(job=None, now=UTC_NOW, force=True)
    assert called == [], "the digest reached the model while 3-Eyes was inert"
    assert finding["model_used"] is False
    assert "unavailable" in finding["summary"]


def test_a_quiet_fleet_does_not_spend_a_model_call(activate, monkeypatch):
    """Pressure relief applied to our own new spender.

    Without this the digest burns one of eight daily LLM units every morning to be
    told everything is fine.
    """
    activate()
    monkeypatch.setenv("THREE_EYES_CLASSIFY_STUB", "1")
    called = []
    monkeypatch.setattr(classify, "summarize_digest",
                        lambda *a, **k: called.append(1) or {"summary": "x"})
    monkeypatch.setattr(digest, "collect", lambda now=None: {
        "generated_at": UTC_NOW.isoformat(),
        "health": {"ok": 24, "failing": 0, "not_loaded": 0, "unknown": 0,
                   "rows": [], "unclassified": [], "launchctl_available": True},
        "failing": [], "breakers": {}, "findings": [],
    })

    finding = digest.build(job=None, now=UTC_NOW)

    assert called == [], "a quiet fleet still paid for a model call"
    assert finding["quiet"] is True
    assert finding["model_used"] is False


def test_a_noisy_fleet_DOES_spend_a_model_call(activate, monkeypatch):
    """The other side: real breakage must reach the model."""
    activate()
    monkeypatch.setattr(classify, "summarize_digest",
                        lambda *a, **k: {"severity": "error", "summary": "vault-sync down"})
    monkeypatch.setattr(digest, "collect", lambda now=None: {
        "generated_at": UTC_NOW.isoformat(),
        "health": {"ok": 20, "failing": 1, "not_loaded": 0, "unknown": 0,
                   "rows": [], "unclassified": [], "launchctl_available": True},
        "failing": [{"label": "com.rebalance-os.vault-sync", "health": "FAIL(exit 1)",
                     "last_exit": "1", "log_tail": "database is locked"}],
        "breakers": {}, "findings": [],
    })

    # A real job, so the call is budgeted. Passing job=None here used to work and
    # was precisely the unbudgeted path the agy review flagged.
    finding = digest.build(job=registry.load_job("daily-digest"), now=UTC_NOW)

    assert finding["model_used"] is True
    assert finding["severity"] == "error"
    assert finding["summary"] == "vault-sync down"


def test_an_unreadable_launchctl_is_noisy_not_quiet(activate, monkeypatch):
    """"We could not look" must never be reported as "nothing is wrong".

    This is health.py's own hard-won rule (a sandboxed shell makes `launchctl list`
    fail, which once made the whole fleet read as dormant). The digest's quiet-path
    optimisation must not quietly reintroduce it.
    """
    activate()
    monkeypatch.setattr(classify, "summarize_digest",
                        lambda *a, **k: {"severity": "warn", "summary": "cannot see the fleet"})
    monkeypatch.setattr(digest, "collect", lambda now=None: {
        "generated_at": UTC_NOW.isoformat(),
        "health": {"ok": 0, "failing": 0, "not_loaded": 0, "unknown": 31, "rows": [],
                   "unclassified": [], "launchctl_available": False,
                   "probe_error": "launchctl list exited 1"},
        "failing": [], "breakers": {}, "findings": [],
    })

    finding = digest.build(job=registry.load_job("daily-digest"), now=UTC_NOW)

    assert finding["quiet"] is False, "an unreadable fleet was treated as a quiet one"
    assert finding["model_used"] is True
    assert "NOT a clean bill of health" in finding["text"]


# --------------------------------------------------------------------------- #
# Budget enforcement
# --------------------------------------------------------------------------- #

def test_the_daily_llm_budget_is_reserved_before_the_call(activate, monkeypatch):
    """Reserve-then-call, not call-then-record.

    `llm_per_run_max = 1` on the digest job means a second build in the same run
    must be refused rather than double-spending.
    """
    activate()
    calls = []
    monkeypatch.setattr(classify, "summarize_digest",
                        lambda *a, **k: calls.append(1) or {"severity": "warn", "summary": "s"})
    monkeypatch.setattr(digest, "collect", lambda now=None: {
        "generated_at": UTC_NOW.isoformat(),
        "health": {"ok": 1, "failing": 1, "not_loaded": 0, "unknown": 0, "rows": [],
                   "unclassified": [], "launchctl_available": True},
        "failing": [{"label": "x", "health": "FAIL(exit 1)", "last_exit": "1"}],
        "breakers": {}, "findings": [],
    })

    job = registry.load_job("daily-digest")
    budget = relief.budget_for(job, "llm")
    assert budget.daily_max == 8 and budget.per_run_max == 1

    first = digest.build(job=job, now=UTC_NOW)
    assert first["model_used"] is True and len(calls) == 1

    # A fresh Budget shares the DAILY counter but not the per-run one; exhaust the day.
    for _ in range(8):
        relief.budget_for(job, "llm").reserve(1)
    blocked = digest.build(job=job, now=UTC_NOW)
    assert blocked["model_used"] is False
    assert "budget" in blocked["summary"].lower()
    assert len(calls) == 1, "the model was called after the budget was exhausted"


# --------------------------------------------------------------------------- #
# Corpus assembly
# --------------------------------------------------------------------------- #

def test_findings_outside_the_window_are_excluded(monkeypatch):
    path = config.state_dir() / "findings.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    old = (UTC_NOW - timedelta(hours=48)).isoformat()
    new = (UTC_NOW - timedelta(hours=1)).isoformat()
    path.write_text(
        json.dumps({"ts": old, "source": "a", "title": "ancient", "severity": "warn"}) + "\n"
        + json.dumps({"ts": new, "source": "b", "title": "recent", "severity": "warn"}) + "\n"
        + "not json at all\n"
    )
    got = digest._recent_findings(UTC_NOW)
    assert [r["title"] for r in got] == ["recent"]


def test_log_tail_matches_both_hyphen_and_underscore_spellings(tmp_path, monkeypatch):
    """The two log trees disagree, and an earlier pass got burned by exactly this.

    3-Eyes writes `<job>.err.log`; the rebalance collectors write `vault_sync_*.log`.
    Grepping only the hyphen spelling is how a working job was once reported as
    having no telemetry at all.
    """
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "vault_sync_2026-07-28.log").write_text("database is locked\n")
    monkeypatch.setattr(digest, "_log_dirs", lambda: [logs])

    tail = digest._logs_for("com.rebalance-os.vault-sync")
    assert "database is locked" in tail


def test_tail_is_bounded(tmp_path, monkeypatch):
    """One pathological log must not blow the model's context window."""
    logs = tmp_path / "logs"
    logs.mkdir()
    big = logs / "vault-sync.log"
    big.write_text("x" * 200_000 + "\nTHE-END\n")
    monkeypatch.setattr(digest, "_log_dirs", lambda: [logs])

    tail = digest._logs_for("com.rebalance-os.vault-sync")
    assert "THE-END" in tail, "the tail did not reach the end of the file"
    assert len(tail) <= digest.LOG_TAIL_BYTES + 200


def test_a_broken_health_scan_does_not_take_the_digest_down(monkeypatch):
    """The reporter of failures must not itself fail on one."""
    def _boom():
        raise RuntimeError("launchctl exploded")
    monkeypatch.setattr(digest.health, "scan", _boom)

    data = digest.collect(UTC_NOW)
    assert data["health"]["launchctl_available"] is False
    assert "launchctl exploded" in data["health"]["probe_error"]
    corpus = digest.render_corpus(data)
    assert "NOT a clean bill of health" in corpus


# --------------------------------------------------------------------------- #
# Registry wiring
# --------------------------------------------------------------------------- #

def test_the_digest_job_is_registered_and_allowlisted():
    job = registry.load_job("daily-digest")
    assert job.enabled is True
    assert job.command in registry.load_commands_allow()
    assert "notify" in job.routes and "log-only" in job.routes


def test_the_digest_does_NOT_file_a_github_issue():
    """365 issues a year is the duplicate-issue flood #139 was closed by deleting.

    gh-issue belongs to the failure explainer (P7b), which fires on real breakage —
    not to a report that runs every morning regardless.
    """
    assert "gh-issue" not in registry.load_job("daily-digest").routes


# --------------------------------------------------------------------------- #
# Two defects the first LIVE runs exposed (stubbed runs could not have)
# --------------------------------------------------------------------------- #

def test_every_classifier_entry_point_allows_for_a_COLD_model():
    """The bug that would have made all three Gemma surfaces useless in production.

    `classify()` defaulted to a 30 s ceiling. gemma4:12b-mlx is ~10 GB, takes ~70 s to
    load cold, and ollama evicts it after ~5 minutes idle — while the jobs calling it
    run every 30 minutes and once a day. So essentially every scheduled call pays the
    cold load, and every one would have timed out at 30 s and returned a refusal.
    Nothing crashes and nothing logs an error; the classifier just declines forever.
    """
    import inspect
    for fn in (classify.classify, classify.explain_failure, classify.summarize_digest):
        default = inspect.signature(fn).parameters["timeout"].default
        assert default == classify.DEFAULT_TIMEOUT_S, f"{fn.__name__} has its own timeout"
    assert classify.DEFAULT_TIMEOUT_S >= 90, (
        "the ceiling must exceed the ~70s cold load, or it reads as a broken model"
    )


def test_explicit_json_nulls_do_not_survive_as_None():
    """`setdefault` fills a MISSING key, not a present-but-null one.

    A reply of {"severity": null} left severity as None, and `str(None)` renders as the
    literal string "None" in the operator's summary.
    """
    parsed = classify._parse_model_json('{"severity": null, "summary": "s", "extra": null}')
    assert "severity" not in parsed
    assert parsed["summary"] == "s"
    assert "extra" not in parsed


def test_no_job_context_means_NO_model_call(monkeypatch, activate):
    """QA finding 1: `budget is not None and not reserve(1)` fell through to the model.

    `main()` sets job=None whenever the registry cannot be read, so a config error
    silently bought an unbudgeted model call. An unmetered spender is worse than no
    digest — fail closed.
    """
    activate()
    called = []
    monkeypatch.setattr(classify, "summarize_digest",
                        lambda *a, **k: called.append(1) or {"severity": "warn", "summary": "s"})
    monkeypatch.setattr(digest, "collect", lambda now=None: {
        "generated_at": UTC_NOW.isoformat(),
        "health": {"ok": 1, "failing": 1, "not_loaded": 0, "unknown": 0, "rows": [],
                   "unclassified": [], "launchctl_available": True},
        "failing": [{"label": "x", "health": "FAIL(exit 1)", "last_exit": "1"}],
        "breakers": {}, "findings": [],
    })

    finding = digest.build(job=None, now=UTC_NOW)

    assert called == [], "an unbudgeted model call was made with no job context"
    assert finding["model_used"] is False
    assert "no budget" in finding["summary"]


@pytest.mark.parametrize("reply", [
    '{"severity": "error", "summary": "s"}\nHere is why that matters...',
    'Thinking...\n{"severity": "error", "summary": "s"}\ntrailing prose',
    '{"severity": "error", "summary": "s"} {"second": "object"}',
])
def test_valid_json_followed_by_prose_is_not_discarded(reply):
    """QA finding 6: `Extra data` threw away an otherwise perfect answer."""
    parsed = classify._parse_model_json(reply)
    assert parsed is not None, "a good JSON answer was discarded because of trailing prose"
    assert parsed["severity"] == "error"


def test_a_brace_inside_a_string_does_not_break_extraction():
    """raw_decode is used precisely so hand-rolled brace counting cannot mis-split."""
    parsed = classify._parse_model_json('{"summary": "contains } a brace"} trailing')
    assert parsed["summary"] == "contains } a brace"
