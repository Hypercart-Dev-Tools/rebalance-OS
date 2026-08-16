"""Routing + classification behaviour (GH-195).

Exercises the observe -> classify -> route path offline: the classifier stub
(no ollama) and the route sinks (log-only always; pdda-inbox/notify/gh gated).
"""

from __future__ import annotations

import json

import pytest

from three_eyes import classify, routes


# ------------------------- classifier (stubbed) --------------------------- #

@pytest.fixture
def stubbed(monkeypatch):
    monkeypatch.setenv("THREE_EYES_CLASSIFY_STUB", "1")


def test_stub_classifies_severities(stubbed):
    assert classify.classify("kernel panic, machine died")["severity"] == "critical"
    assert classify.classify("Traceback: ValueError")["severity"] == "error"
    assert classify.classify("deprecation warning")["severity"] == "warn"
    assert classify.classify("all good, nothing to see")["severity"] == "info"


def test_stub_makes_no_network_call(stubbed, monkeypatch):
    import urllib.request
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda *a, **k: pytest.fail("stub classify hit the network"),
    )
    assert classify.classify("error")["stub"] is True


def test_active_classifier_sends_editable_system_instructions(activate, monkeypatch):
    """The committed instructions file, not a hidden inline prompt, governs Gemma."""
    activate()
    monkeypatch.setenv("THREE_EYES_MODEL", "gemma-test")
    captured: dict = {}

    class Response:
        def read(self):
            return b'{"response": "{\\"severity\\": \\"warn\\", \\"summary\\": \\"test\\"}"}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, **_kwargs):
        captured.update(json.loads(request.data.decode()))
        return Response()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = classify.classify("collector returned no fresh rows")

    assert result["severity"] == "warn"
    assert captured["model"] == "gemma-test"
    assert captured["system"] == classify.load_system_instructions()
    assert "safety-first observability analyst" in captured["system"]


# ------------------------------- routes ----------------------------------- #

def test_pdda_dry_run_has_required_frontmatter():
    [res] = routes.route(
        {"source": "job", "title": "disk full", "severity": "error",
         "summary": "root at 98%", "text": "df output"},
        ["pdda-inbox"], dry_run=True,
    )
    assert res["status"] == "dry-run"
    md = res["content"]
    for key in ("title:", "status:", "created:", "updated:", "owner:", "goal:"):
        assert key in md, f"PDDA draft missing frontmatter key {key!r}"
    assert "ratings_provisional: true" in md   # machine drafts are always provisional


def test_pdda_writes_when_active(activate, monkeypatch, tmp_path):
    activate()
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(routes, "INBOX", inbox)
    [res] = routes.route(
        {"source": "job", "title": "disk full", "severity": "error", "summary": "s", "text": "t"},
        ["pdda-inbox"],
    )
    assert res["status"] == "drafted"
    written = list(inbox.glob("3EYES-*.md"))
    assert len(written) == 1
    assert written[0].read_text().startswith("---")


def test_log_only_appends_jsonl():
    [res] = routes.route({"source": "job", "title": "x", "text": "y"}, ["log-only"])
    assert res["status"] == "logged"
    import json
    from pathlib import Path
    rows = Path(res["path"]).read_text().strip().splitlines()
    assert json.loads(rows[-1])["title"] == "x"


def test_unknown_route_reported():
    [res] = routes.route({"title": "x"}, ["teleport"])
    assert res["status"] == "unknown-route"
