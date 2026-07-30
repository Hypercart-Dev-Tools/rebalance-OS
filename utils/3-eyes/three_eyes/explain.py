"""Failure explainer — is this failure known-benign, or new? (GH-195 P7b)

Fires when a job's breaker OPENS, which is the rare, meaningful moment: three
consecutive real failures, the job is now quarantined, and the operator is about to
be told. Explaining every individual failure would spend the daily LLM budget on
noise; explaining the trip spends it on the one event that already warrants a banner.

**Two-stage triage, cheapest first.**

1. A failure matching a rule in ``registry/known_issues.toml`` is suppressed
   deterministically — no model call, no issue, one log-only record. Free, auditable,
   and incapable of hallucinating.
2. Only a failure matching nothing reaches Gemma, which judges whether it is new.

That ordering is the whole cost argument: recurring failures are the high-volume ones,
so suppressing them for free is what keeps budget available for novelty.

This is also the gate that makes the ``gh-issue`` route safe to turn on in P8. #139 was
closed by *deleting* a duplicate-issue emitter — a supervisor that files an issue for
every recurring, already-understood failure recreates exactly the defect 3-Eyes exists
to prevent.

Egress boundary: no network call here. The prompt is assembled and handed to
:func:`classify.explain_failure`, one of the two modules permitted to talk out.
"""

from __future__ import annotations

import re
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

from . import classify, config, digest, relief

#: Verdicts an explanation can carry.
KNOWN = "known"          # matched a suppression rule — do not escalate
NEW = "new"              # nothing matched and the model thinks it is real
UNJUDGED = "unjudged"    # nothing matched but no model was available/affordable


def _rules_path() -> Path:
    return config.ROOT / "registry" / "known_issues.toml"


def load_rules(path: Path | None = None) -> list[dict[str, Any]]:
    """Load the suppression rules. A malformed file suppresses NOTHING.

    Failing open is deliberate: the risk of a broken rules file is that it silences a
    real failure, which is strictly worse than escalating one that turns out to be
    known. An unreadable list means "we cannot prove this is benign".
    """
    try:
        data = tomllib.loads((path or _rules_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rules = data.get("rule", [])
    return [r for r in rules if isinstance(r, dict) and r.get("id") and r.get("pattern")]


def match_known_issue(
    job_id: str, text: str, rules: list[dict] | None = None, today: date | None = None
) -> dict | None:
    """Return the first rule that suppresses this failure, or None.

    An EXPIRED rule deliberately does not match: a suppression with a shelf life that
    has run out should start reporting again, not silently keep hiding the failure.
    """
    today = today or date.today()
    for rule in rules if rules is not None else load_rules():
        jobs = rule.get("jobs")
        if jobs and not any(job_id == j or job_id.endswith(f".{j}") for j in jobs):
            continue
        expires = rule.get("expires")
        if expires:
            try:
                if today > date.fromisoformat(str(expires)):
                    continue
            except ValueError:
                pass                       # unparseable date => treat as non-expiring
        try:
            if re.search(str(rule["pattern"]), text, re.IGNORECASE | re.DOTALL):
                return rule
        except re.error:
            continue                       # a broken regex suppresses nothing
    return None


def gather_evidence(job_id: str, code: int, label: str | None = None) -> str:
    """Assemble the failure's evidence: exit code + whatever logs we can find."""
    tail = digest._logs_for(label or f"com.rebalance-os.3eyes.{job_id}")
    if not tail:
        tail = digest._logs_for(job_id)
    parts = [f"job: {job_id}", f"exit code: {code}"]
    if tail:
        parts += ["", "log tail:", tail]
    else:
        parts += ["", "(no log output found for this job)"]
    return "\n".join(parts)


def explain(job, code: int, evidence: str | None = None, today: date | None = None) -> dict:
    """Judge one job failure. Returns a finding-shaped dict plus a ``verdict``.

    Never raises: this runs on the failure path, and an explainer that throws would
    turn one broken job into two.
    """
    job_id = getattr(job, "id", str(job))
    text = evidence if evidence is not None else gather_evidence(job_id, code)

    rule = match_known_issue(job_id, text, today=today)
    if rule:
        issue = f" (tracking #{rule['issue']})" if rule.get("issue") else ""
        return {
            "source": job_id,
            "title": f"{job_id} failed — known issue: {rule['id']}",
            "severity": "info",
            "summary": f"suppressed by rule {rule['id']}{issue}: {rule.get('reason', '')}",
            "text": text,
            "verdict": KNOWN,
            "rule": rule["id"],
            "model_used": False,
        }

    if not classify.available():
        return {
            "source": job_id,
            "title": f"{job_id} failed — unrecognised",
            "severity": "error",
            "summary": "no suppression rule matched and no classifier was available",
            "text": text,
            "verdict": UNJUDGED,
            "model_used": False,
        }

    budget = relief.budget_for(job, "llm")
    if not budget.reserve(1):
        return {
            "source": job_id,
            "title": f"{job_id} failed — unrecognised",
            "severity": "error",
            "summary": "no suppression rule matched; LLM budget exhausted, not judged",
            "text": text,
            "verdict": UNJUDGED,
            "model_used": False,
        }

    try:
        result = classify.explain_failure(text)
    except Exception as exc:                        # never take the job down
        result = {"refused": True, "reason": f"explainer error: {exc}"}

    if result.get("refused"):
        return {
            "source": job_id,
            "title": f"{job_id} failed — unrecognised",
            "severity": "error",
            "summary": f"not judged ({result.get('reason', 'classifier refused')})",
            "text": text,
            "verdict": UNJUDGED,
            "model_used": False,
        }

    return {
        "source": job_id,
        "title": f"{job_id} failed — {str(result.get('headline', 'unrecognised failure'))[:120]}",
        "severity": str(result.get("severity", "error")),
        "summary": str(result.get("summary", "")).strip() or "(model returned no summary)",
        "text": text,
        "verdict": NEW,
        "model_used": True,
        "next_step": result.get("next_step", ""),
    }


def routes_for(job, verdict: str) -> list[str]:
    """Which of the job's routes an explanation of this verdict may use.

    A KNOWN issue is recorded and nothing more — no banner, no issue. That is the
    entire point of the suppression list: it converts recurring noise into a quiet
    log line instead of a notification the operator learns to ignore.
    """
    if verdict == KNOWN:
        return ["log-only"]
    allowed = [r for r in getattr(job, "routes", []) if r in ("notify", "gh-issue", "log-only")]
    return allowed or ["log-only"]
