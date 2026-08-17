"""Daily fleet digest — the first thing that actually asks Gemma a question (GH-195 P7a).

Until this module, 3-Eyes had a classifier that had never run. `classify()` was
reachable from exactly one place — `run._process_emit`, which fires only when a job
drops a finding file — and no job had ever dropped one. A 10 GB model sat on disk,
never resident, while the operator's stated goal was "a smarter model keeping an eye
on things." The safety machinery was excellent and the centre was empty.

P7a is deliberately the surface with **no dependencies**. It reads state that already
exists on disk — `launchctl` exit codes via :mod:`health`, breaker state, the findings
log, and the tail of any failing job's log — and asks the model one question a day:
*what broke, what matters, what can be ignored?* It does not wait on the
collector-health observer (P7c), which is the larger build.

Egress boundary: this module makes **no** network call. The corpus is assembled here
and handed to :func:`classify.summarize_digest`, which is one of the two modules
allowed to talk to the outside world (enforced by `test_egress_static_guard.py`).

Cost posture: one model call per run, reserved through the job's ``[relief]`` budget
*before* the call, so a digest cannot quietly consume the same daily allowance the
failure explainer (P7b) and findings triage (P7c) draw from.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import breakers, classify, config, health, registry, relief

#: How much of a failing job's log to hand the model. Enough to carry a traceback,
#: bounded so one pathological log cannot blow the context window or the wall clock.
LOG_TAIL_BYTES = 4000

#: Findings newer than this are considered "today's" for digest purposes.
FINDINGS_WINDOW_HOURS = 24

#: Where the rendered report lands. Kept in the state dir (gitignored, machine-local)
#: because it describes THIS machine's jobs and would be meaningless in a clone.
REPORT_NAME = "digest"


def _report_dir() -> Path:
    return config.state_dir() / REPORT_NAME


def _log_dirs() -> list[Path]:
    """Directories whose `*.log` files may be tailed for a failing job."""
    return [config.state_dir() / "logs", config.REPO_ROOT / "temp" / "logs"]


def _tail(path: Path, limit: int = LOG_TAIL_BYTES) -> str:
    """Last ``limit`` bytes of a file, or "" if it cannot be read.

    Seeks rather than reading the whole file: `github_sync_*.log` runs to hundreds
    of KB and only the end is diagnostic.
    """
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > limit:
                fh.seek(size - limit)
            raw = fh.read()
    except OSError:
        return ""
    text = raw.decode("utf-8", errors="replace")
    if size > limit:
        text = text.split("\n", 1)[-1]      # drop the partial first line
    return text.strip()


def _logs_for(label: str) -> str:
    """Best-effort log tail for a launchd label.

    Matches on the label's last segment (`com.rebalance-os.vault-sync` → `vault-sync`)
    against both underscore and hyphen spellings, because the two log trees disagree:
    3-Eyes writes `<job>.err.log`, the rebalance collectors write `vault_sync_*.log`.
    Getting this wrong is how an earlier pass concluded a job "had no telemetry" when
    it was simply spelled differently.
    """
    stem = label.rsplit(".", 1)[-1]
    variants = {stem, stem.replace("-", "_"), stem.replace("_", "-")}
    chunks: list[str] = []
    for directory in _log_dirs():
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.log")):
            if any(path.name.startswith(v) for v in variants):
                tail = _tail(path)
                if tail:
                    chunks.append(f"--- {path.name} ---\n{tail}")
    return "\n\n".join(chunks[:3])          # at most 3 files per job


def _recent_findings(now: datetime) -> list[dict]:
    path = config.state_dir() / "findings.jsonl"
    cutoff = now - timedelta(hours=FINDINGS_WINDOW_HOURS)
    out: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        ts = str(rec.get("ts", ""))
        try:
            when = datetime.fromisoformat(ts)
        except ValueError:
            out.append(rec)                 # undateable: include rather than drop
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when >= cutoff:
            out.append(rec)
    return out


def collect(now: datetime | None = None) -> dict[str, Any]:
    """Gather the day's fleet state. Pure reads — no model call, no egress."""
    now = now or datetime.now(timezone.utc)
    try:
        report = health.scan()
    except Exception as exc:                # health must never take the digest down
        report = {"rows": [], "probe_error": f"health.scan failed: {exc}",
                  "launchctl_available": False, "ok": 0, "failing": 0,
                  "not_loaded": 0, "unknown": 0, "unclassified": [], "removed": []}

    failing = [r for r in report.get("rows", []) if "FAIL" in str(r.get("health", ""))]
    for row in failing:
        row["log_tail"] = _logs_for(row["label"])

    breaker = breakers.FailureBreaker()
    breaker_state = {}
    for job in registry.load_jobs(include_local=True):
        st = breaker.status(job.id)
        if st.get("quarantined") or st.get("consecutive_failures") or st.get("last") == "deferred":
            breaker_state[job.id] = st

    return {
        "generated_at": now.isoformat(),
        "health": report,
        "failing": failing,
        "breakers": breaker_state,
        "findings": _recent_findings(now),
    }


def render_corpus(data: dict[str, Any]) -> str:
    """Flatten the collected state into the text the model is asked to rank.

    Deliberately plain text rather than JSON: the model is being asked to *triage*,
    and a compact human-shaped brief gets better ranking out of a 12B local model
    than a nested object does.
    """
    h = data["health"]
    lines = [f"Fleet digest for {data['generated_at']}", ""]

    if not h.get("launchctl_available", True):
        lines += [
            "LAUNCHCTL COULD NOT BE READ — this is NOT a clean bill of health.",
            f"  {h.get('probe_error', 'unavailable')}", "",
        ]
    else:
        lines += [
            f"Totals: {h.get('ok', 0)} ok · {h.get('failing', 0)} failing · "
            f"{h.get('not_loaded', 0)} not-loaded · {h.get('unknown', 0)} unknown",
            "",
        ]

    if data["failing"]:
        lines.append("FAILING JOBS")
        for row in data["failing"]:
            lines.append(f"- {row['label']}: {row['health']} (last exit {row.get('last_exit')})")
            if row.get("log_tail"):
                lines += ["  log tail:", *(f"    {l}" for l in row["log_tail"].splitlines()[-40:])]
        lines.append("")
    else:
        lines += ["No jobs are currently failing.", ""]

    if data["breakers"]:
        lines.append("BREAKERS NOT CLEAN")
        for job_id, st in sorted(data["breakers"].items()):
            state = "OPEN" if st.get("quarantined") else "closed"
            detail = f"fails={st.get('consecutive_failures', 0)} last={st.get('last')}"
            if st.get("paused"):
                detail += " (operator paused)"
            lines.append(f"- {job_id}: {state} {detail}")
        lines.append("")

    if data["findings"]:
        lines.append(f"FINDINGS (last {FINDINGS_WINDOW_HOURS}h)")
        for rec in data["findings"][-25:]:
            lines.append(
                f"- [{rec.get('severity', '?')}] {rec.get('source', '?')}: "
                f"{rec.get('title', '')} — {rec.get('summary', '')}"
            )
        lines.append("")

    if h.get("unclassified"):
        lines += ["UNCLASSIFIED AGENTS (not in catalog-notes.toml)",
                  *(f"- {lbl}" for lbl in h["unclassified"]), ""]

    return "\n".join(lines).strip()


def _has_anything_to_say(data: dict[str, Any]) -> bool:
    """True when the day contains something worth spending a model call on.

    A quiet fleet should cost nothing. Without this the digest burns one of eight
    daily LLM units every morning to be told everything is fine — the pressure-relief
    posture (invariant 6) applied to our own new spender.
    """
    return bool(
        data["failing"]
        or data["breakers"]
        or data["findings"]
        or data["health"].get("unclassified")
        or not data["health"].get("launchctl_available", True)
    )


def build(job=None, now: datetime | None = None, force: bool = False) -> dict[str, Any]:
    """Collect → (optionally) summarise → return a finding dict ready to route.

    The returned dict is the standard finding shape (`source`/`title`/`severity`/
    `summary`/`text`), so it flows through the existing route machinery unchanged.
    """
    data = collect(now)
    corpus = render_corpus(data)
    quiet = not _has_anything_to_say(data)

    summary = ""
    severity = "info"
    model_used = False
    reason = ""
    extras: dict[str, Any] = {}

    if quiet and not force:
        summary = "fleet quiet — no failures, no open breakers, no findings"
    elif not classify.available():
        reason = "3-Eyes inert or classifier unavailable"
        summary = "digest collected but not summarised (classifier unavailable)"
    else:
        # FAIL CLOSED when there is no job to budget against (agy review, P7 QA
        # finding 1). The previous `budget is not None and not reserve(1)` fell
        # through to the model whenever `job` was None — which `main()` produces
        # whenever the registry cannot be read — so a config error silently bought
        # an unbudgeted model call. An unmetered spender is worse than no digest.
        budget = relief.budget_for(job, "llm") if job is not None else None
        if budget is None:
            reason = "no job context, so no budget to reserve against"
            summary = f"digest collected but not summarised ({reason})"
        elif not budget.reserve(1):
            reason = "LLM budget exhausted"
            summary = "digest collected but not summarised (LLM budget exhausted)"
        else:
            result = classify.summarize_digest(corpus)
            if result.get("refused"):
                reason = str(result.get("reason", "classifier refused"))
                summary = f"digest collected but not summarised ({reason})"
            else:
                model_used = True
                summary = str(result.get("summary", "")).strip() or "(model returned no summary)"
                severity = str(result.get("severity", "info"))
                extras = {
                    k: result[k]
                    for k in ("confidence", "evidence", "next_safe_step")
                    if result.get(k)
                }

    h = data["health"]
    headline = (
        f"{h.get('failing', 0)} failing · {h.get('ok', 0)} ok"
        + (f" · {len(data['breakers'])} breaker(s) not clean" if data["breakers"] else "")
    )

    return {
        "source": "daily-digest",
        "title": f"Fleet digest — {headline}",
        "severity": severity,
        "summary": summary,
        "text": corpus,
        "model_used": model_used,
        "skipped_reason": reason,
        "quiet": quiet,
        # gemma volunteers these beyond the two keys asked for; `evidence` in
        # particular is the most operator-useful part of the reply.
        "extras": extras,
    }


def write_report(finding: dict[str, Any], now: datetime | None = None) -> Path:
    """Persist the full digest so the operator can read it after the banner is gone."""
    now = now or datetime.now(timezone.utc)
    directory = _report_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{now.date().isoformat()}.md"
    body = [
        f"# {finding['title']}",
        "",
        f"_generated {now.isoformat()} · "
        f"{'model-summarised' if finding.get('model_used') else 'not summarised'}_",
        "",
        "## Summary",
        finding.get("summary", ""),
        "",
        "## Model notes",
        *(
            [f"- **{k.replace('_', ' ')}:** {v if not isinstance(v, list) else '; '.join(map(str, v))}"
             for k, v in finding.get("extras", {}).items()]
            or ["_(none)_"]
        ),
        "",
        "## Evidence",
        "",
        "```",
        finding.get("text", ""),
        "```",
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """Entry point for the allowlisted ``daily-digest`` command.

    Drops a finding file at the job's emit path so the EXISTING route machinery in
    ``run._process_emit`` dispatches it — the digest does not get its own private
    delivery path. Exit 0 always: a digest that cannot summarise is still a digest,
    and failing here would trip the very breaker this job exists to report on.
    """
    force = bool(argv and "--force" in argv)
    try:
        job = registry.load_job("daily-digest")
    except Exception:
        job = None

    finding = build(job=job, force=force)
    report_path = write_report(finding)

    emit = config.state_dir() / "emit"
    emit.mkdir(parents=True, exist_ok=True)
    payload = {k: finding[k] for k in ("source", "title", "severity", "summary", "text")}
    payload["report"] = str(report_path)
    (emit / "daily-digest.json").write_text(json.dumps(payload), encoding="utf-8")

    print(f"digest: {finding['title']}")
    print(f"digest: {finding['summary']}")
    print(f"digest: report -> {report_path}")
    if finding.get("skipped_reason"):
        print(f"digest: not summarised — {finding['skipped_reason']}")
    return 0


if __name__ == "__main__":                  # pragma: no cover - launchd entry point
    raise SystemExit(main(list(os.sys.argv[1:])))
