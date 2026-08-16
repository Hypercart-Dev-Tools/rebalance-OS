"""Tests for the Claude Code Cloud signal (GH-128).

Covers normalization, data-quality grading, and the dormant/enabled behavior of the
HiQS candidates provider. No network: the session fetch is monkeypatched.
"""


import pytest

from rebalance.ingest import claude_cloud as cc


# --- fixtures ---------------------------------------------------------------

def _raw(title, bucket, repo, branch, summary, origin="web_claude_ai"):
    return {
        "id": f"cse_{title[:4]}",
        "title": title,
        "status": "active",
        "status_bucket": bucket,
        "worker_status": "idle",
        "created_at": "2026-07-14T17:55:54.000000Z",
        "last_event_at": "2026-07-14T18:30:37.000000Z",
        "config": {
            "model": "claude-opus-4-8", "effort_level": "high", "origin": origin,
            "outcomes": [{"git_info": {"repo": repo, "branches": [branch]}}],
        },
        "external_metadata": {"post_turn_summary": {"status_detail": summary, "needs_action": ""}},
    }


@pytest.fixture
def rows():
    r = [
        cc.normalize(_raw("Merged job", "review_ready", "o/r1", "b1", "done")),
        cc.normalize(_raw("Open PR job", "review_ready", "o/r2", "b2", "pr up")),
        cc.normalize(_raw("No-PR job", "review_ready", "o/r3", "b3", "pushed")),
        cc.normalize(_raw("Failed job", "failed", "o/r4", "b4", "broke")),
    ]
    r[0].update(pr_number=126, pr_state="MERGED", pr_url="u126")
    r[1].update(pr_number=54, pr_state="OPEN", pr_url="u54")
    # r[2] no PR (pr_state None); r[3] failed, no PR
    return r


# --- normalize --------------------------------------------------------------

def test_normalize_extracts_repo_branch_summary():
    n = cc.normalize(_raw("T", "review_ready", "owner/repo", "feature/x", "did a thing"))
    assert n["repo"] == "owner/repo"
    assert n["branch"] == "feature/x"
    assert n["summary"] == "did a thing"
    assert n["model"] == "claude-opus-4-8"
    assert n["origin"] == "web_claude_ai"


def test_normalize_repo_falls_back_to_source_url():
    raw = _raw("T", "review_ready", "", "", "s")
    raw["config"]["outcomes"] = []
    raw["config"]["sources"] = [{"url": "https://github.com/owner/repo.git"}]
    raw["external_metadata"]["current_branches"] = {"": "b"}
    n = cc.normalize(raw)
    assert n["repo"] == "owner/repo"  # .git stripped
    assert n["branch"] == "b"


# --- grade ------------------------------------------------------------------

def test_grade_empty():
    g = cc.grade([])
    assert g["n"] == 0 and g["overall"] is None and g["letter"] == "—"


def test_grade_full_coverage_is_A(rows):
    g = cc.grade(rows)
    assert g["n"] == 4
    assert g["dimensions"]["identified"] == 1.0   # all have repo+branch
    assert g["dimensions"]["attested"] == 1.0     # all have summaries
    assert g["dimensions"]["outcome_known"] == 1.0
    assert g["letter"] == "A"
    assert g["counts"] == {"merged": 1, "open": 1, "no_pr": 2, "pr_lookup_failed": 0,
                           "running": 0, "failed": 1}


def test_grade_flags_unattributed_and_summaryless():
    bad = cc.normalize(_raw("bad", "review_ready", "", "", ""))  # no repo/branch/summary
    g = cc.grade([bad])
    assert g["dimensions"]["identified"] == 0.0
    assert g["dimensions"]["attested"] == 0.0
    assert g["letter"] == "F"
    assert any("unattributed" in w for w in g["warnings"])


# --- candidates provider ----------------------------------------------------

def test_candidates_dormant_by_default(rows, monkeypatch):
    monkeypatch.setattr(cc, "_signal_enabled", lambda: False)
    monkeypatch.setattr(cc, "sessions_for_day", lambda *a, **k: rows)

    class B:
        local_day = "2026-07-14"

    assert cc.claude_cloud_candidates(B()) == []


def test_candidates_when_enabled(rows, monkeypatch):
    monkeypatch.setattr(cc, "_signal_enabled", lambda: True)
    monkeypatch.setattr(cc, "sessions_for_day", lambda *a, **k: rows)

    class B:
        local_day = "2026-07-14"

    cands = cc.claude_cloud_candidates(B())
    titles = [c["title"] for c in cands]
    # merged -> dropped; open -> review; no-PR review_ready -> triage; failed -> failed
    assert not any("Merged job" in t for t in titles)
    assert any(t.startswith("Review PR #54") for t in titles)
    assert any(t.startswith("Triage cloud job") for t in titles)
    assert any(t.startswith("Cloud job FAILED") for t in titles)
    assert all(c["source"] == "claude_cloud" for c in cands)
    assert all(c["evidence"] for c in cands)               # Attested: non-empty
    assert all(c["rank_key"][0] == cc._RANK_CLASS for c in cands)


def test_candidates_never_raises_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(cc, "_signal_enabled", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(cc, "sessions_for_day", boom)

    class B:
        local_day = "2026-07-14"

    assert cc.claude_cloud_candidates(B()) == []           # fail-soft, not an exception
