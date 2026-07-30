"""Collector-health observer — the thing that finally gives the classifier input (GH-195 P7c).

`classify()` sat unexercised for weeks because it is reachable only from
``run._process_emit``, which fires when a job drops a finding file — and no job had
ever dropped one. This module is that missing producer.

**Exit codes lie here (GH-146).** ``daily_sync.sh`` degrades gracefully and exits ``0``
even when collectors fail, so a naive "run command, check exit status" observer reports
a healthy fleet while sources are silently broken. The signal is the trailing JSON in
``temp/logs/daily_sync_*.log`` — ``sync_outcome: "complete" | "degraded"`` — and it is
only meaningful once the run has finished.

Three rules this module exists to encode, each learned from a real misread:

1. **A log holds MANY runs.** `daily_sync_2026-07-19.log` contains a `degraded` run
   followed by a `complete` one. Reading the first match reports a failure that was
   already resolved; reading any match reports whichever the regex happened to hit.
   Only the LAST run block is current.
2. **No terminal marker means STILL RUNNING, not crashed.** A log ending mid-`Fetching…`
   is a run in flight. Calling that a failure is how a working system gets reported
   broken, and it is the single most likely way this observer creates noise.
3. **Missing telemetry is UNKNOWN, not healthy.** If the log cannot be found or read,
   say so. An earlier pass in this project concluded a job "had no telemetry" purely
   because it grepped `vault-sync_` against files named `vault_sync_`.

Egress boundary: no network call. A finding is written to the job's emit path and the
existing route machinery in ``run._process_emit`` takes it from there — including the
Gemma classification, which needs no new wiring because that path already existed and
was merely starving.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

#: Every banner daily_sync writes, of any kind.
#:
#: Terminality is decided by ELIMINATION — a marker is terminal unless it says
#: "starting" — rather than by listing the outcomes. Listing them is what broke the
#: first version of this module: it matched `complete` and `finished…` and therefore
#: missed `=== rebalance daily sync degraded; partial errors recorded ===`, so every
#: DEGRADED run read as "still running" and was silently reported as fine. That is
#: precisely the GH-146 failure this observer exists to prevent, reintroduced by the
#: observer itself.
#:
#: Eliminating also fails in the safe direction. A new outcome word is treated as
#: terminal, so the run gets evaluated (and at worst emits a visible "no outcome"
#: warning); the old scheme treated anything unrecognised as in-flight, which is
#: silence. Visible noise beats invisible breakage.
MARKER_RE = re.compile(r"=== rebalance ([\w \-;,.()']*?) ===")

#: Start-of-run marker, used to split a multi-run log into blocks.
START_RE = re.compile(r"=== rebalance [\w \-]*starting ===")


def _is_terminal(marker_text: str) -> bool:
    """True when a banner means "this run ended", whatever the outcome word is."""
    return not marker_text.strip().endswith("starting")

#: A run's trailing JSON summary. Non-greedy, anchored on the outcome key so we do not
#: match the many nested objects inside the per-scope results.
OUTCOME_RE = re.compile(r'"sync_outcome":\s*"(\w+)"')

#: How stale a completed run may be before freshness itself is the finding.
STALE_HOURS = 26          # daily job + a 2h grace, so a normal late run is not an alert

#: How long a run may plausibly still be "in flight" before we call it dead.
#:
#: Rule 2 says a missing terminal marker means still-running, not crashed — but only
#: for so long. `daily_sync_2026-07-26.log` opens with a start banner and simply stops:
#: the run was killed mid-flight during the memory crisis and never wrote a terminal
#: marker. Without this ceiling that log reads as "running" forever and a dead nightly
#: sync stays invisible permanently. A real run takes ~10-60 minutes; 6h is generous.
IN_FLIGHT_MAX_HOURS = 6


def _log_dir() -> Path:
    return config.REPO_ROOT / "temp" / "logs"


def latest_log(prefix: str = "daily_sync_") -> Path | None:
    """Most recent log file for a sync job, or None when there is no telemetry."""
    directory = _log_dir()
    if not directory.is_dir():
        return None
    candidates = sorted(directory.glob(f"{prefix}*.log"))
    return candidates[-1] if candidates else None


def last_run_block(text: str) -> str:
    """Return only the final run in a log that may contain several.

    Rule 1. Splitting on the start marker and taking the tail is what keeps a
    resolved `degraded` run from being reported as current.
    """
    starts = list(START_RE.finditer(text))
    return text[starts[-1].start():] if starts else text


def parse_sync_log(path: Path) -> dict[str, Any]:
    """Parse one sync log into a verdict. Never raises.

    Returns ``state`` ∈ {complete, degraded, running, unreadable, no-outcome}.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"state": "unreadable", "detail": str(exc), "errors": [], "path": str(path)}

    block = last_run_block(text)
    finished = any(_is_terminal(m) for m in MARKER_RE.findall(block))
    outcomes = OUTCOME_RE.findall(block)

    if not finished:
        # Rule 2 — in flight, not broken.
        return {"state": "running", "detail": "no terminal marker; run still in flight",
                "errors": [], "path": str(path), "outcome": outcomes[-1] if outcomes else None}

    if not outcomes:
        return {"state": "no-outcome", "detail": "run finished but wrote no sync_outcome",
                "errors": [], "path": str(path)}

    # NO LENGTH CAP on the captured error (agy review, P7 QA finding 4). This was
    # `[^"]{0,200}`, which does not truncate a long error — it fails to match it at
    # all, because after 200 non-quote characters the next character must be a quote
    # and is not. A 300-character traceback therefore produced ZERO matches, `errs`
    # came back empty, and a `complete` run carrying a catastrophic error was
    # reported as clean. Capture in full; truncate only for display.
    errors = [e[:400] for e in re.findall(r'"error":\s*"([^"]*)"', block)]
    scopes = re.findall(r'"scope":\s*"(\w+)"', block)
    return {
        "state": outcomes[-1],              # the LAST run's outcome, not the first
        "detail": "",
        "errors": errors,
        "scopes": sorted(set(scopes)),
        "path": str(path),
        "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
    }


def _age_hours(path: Path, now: datetime) -> float:
    try:
        return (now - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)).total_seconds() / 3600
    except OSError:
        return float("inf")


def observe(now: datetime | None = None, prefix: str = "daily_sync_") -> dict[str, Any] | None:
    """Look at the collectors. Returns a finding dict, or None when all is well.

    Returning None on a healthy run is what keeps this from becoming the next source
    of daily noise — the finding file is only written when there is something to say.
    """
    now = now or datetime.now(timezone.utc)
    path = latest_log(prefix)

    if path is None:
        # Rule 3 — no telemetry is UNKNOWN, and unknown is worth saying out loud.
        return {
            "source": "collector-health",
            "title": "collector telemetry missing",
            "severity": "warn",
            "summary": f"no {prefix}*.log found in {_log_dir()} — cannot tell whether "
                       "collectors ran. This is NOT a clean bill of health.",
            "text": f"searched: {_log_dir()}/{prefix}*.log",
        }

    parsed = parse_sync_log(path)
    state = parsed["state"]
    age = _age_hours(path, now)

    if state == "running":
        if age <= IN_FLIGHT_MAX_HOURS:
            return None                      # genuinely in flight; say nothing
        return {
            "source": "collector-health",
            "title": f"collector sync never finished ({age:.0f}h)",
            "severity": "error",
            "summary": f"{path.name} started but wrote no terminal marker and has not "
                       f"been touched for {age:.0f}h — the run died mid-flight.",
            "text": f"log: {path}\nage_hours: {age:.1f}\n"
                    f"in-flight ceiling: {IN_FLIGHT_MAX_HOURS}h",
        }

    if state == "unreadable":
        return {
            "source": "collector-health", "title": "collector log unreadable",
            "severity": "warn",
            "summary": f"{path.name} could not be read: {parsed['detail']}",
            "text": json.dumps(parsed, indent=2),
        }

    if state == "no-outcome":
        return {
            "source": "collector-health", "title": "collector run wrote no outcome",
            "severity": "warn",
            "summary": f"{path.name} finished but recorded no sync_outcome",
            "text": json.dumps(parsed, indent=2),
        }

    # Freshness is checked FIRST, before any content-based early return (agy review,
    # P7 QA finding 3). Previously the "complete plus only-known errors" branch
    # returned None directly and skipped the staleness check below — so a job that
    # died after one such run was reported healthy forever. Staleness is a property of
    # the job still running at all, and must not be gated on what its last run said.
    stale = age > STALE_HOURS
    if stale:
        return {
            "source": "collector-health",
            "title": f"collector sync stale ({age:.0f}h)",
            "severity": "warn",
            "summary": f"last completed sync was {age:.0f}h ago (threshold {STALE_HOURS}h)",
            "text": f"log: {path}\nstate: {state}\nage_hours: {age:.1f}",
        }

    errs = parsed.get("errors") or []
    if state == "degraded" or (state == "complete" and errs):
        # Reuse P7b's suppression list rather than growing a second one. Imported
        # locally because `explain` imports `digest`, and a module-level import here
        # would make the observer depend on the whole classification stack just to
        # parse a log file.
        from . import explain as _explain

        unknown = [e for e in errs if _explain.match_known_issue("collector-health", e) is None]
        suppressed = len(errs) - len(unknown)

        if state == "complete" and not unknown:
            # "complete" plus only-known errors is the normal, boring case (16 GitHub
            # 403s on 2026-07-25, all rate-limit noise per #144). Reporting it daily
            # would train the operator to ignore this job.
            return None

        head = (unknown or errs or ["no error detail recorded"])[0]
        qualifier = "" if state == "degraded" else " (outcome said complete)"
        body = "\n".join([
            f"log: {path}",
            f"sync_outcome: {state}",
            f"scopes: {', '.join(parsed.get('scopes', [])) or 'unknown'}",
            f"errors: {len(errs)} recorded, {suppressed} matched a known-issue rule",
            "",
            "unsuppressed errors:",
            *([f"  - {e}" for e in unknown] or ["  (none — all matched known issues)"]),
        ])
        finding = {
            "source": "collector-health",
            "title": f"collector sync {state} ({len(unknown)} unexplained error(s)){qualifier}",
            "summary": f"{path.name}: sync_outcome={state} — {head}",
            "text": body,
        }
        # Severity is deliberately LEFT OUT so run._process_emit hands this to the
        # classifier. This is the finding Gemma was always meant to triage, and the
        # reason that path had never once executed.
        return finding

    return None                              # complete, fresh, nothing unexplained


def main(argv: list[str] | None = None) -> int:
    """Entry point for the allowlisted ``collector-observe`` command.

    Drops a finding file for ``run._process_emit`` to classify and route. Exit 0 even
    when it finds a problem: the *finding* is the output, and a non-zero exit would
    trip this job's own breaker for correctly doing its job.
    """
    finding = observe()
    emit = config.state_dir() / "emit"
    emit.mkdir(parents=True, exist_ok=True)
    path = emit / "collector-health.json"

    if finding is None:
        path.unlink(missing_ok=True)         # stale finding must not be re-routed
        print("collector-observe: collectors healthy — no finding emitted")
        return 0

    # Deliberately no "severity" in the emitted payload when we want triage: leaving it
    # absent is the documented signal that run._process_emit should classify it.
    payload = {k: finding[k] for k in ("source", "title", "summary", "text")}
    if finding.get("severity") in ("warn",):
        payload["severity"] = finding["severity"]   # low-stakes states need no model
    path.write_text(json.dumps(payload), encoding="utf-8")
    print(f"collector-observe: {finding['title']}")
    print(f"collector-observe: {finding['summary']}")
    return 0


if __name__ == "__main__":                   # pragma: no cover - launchd entry point
    raise SystemExit(main(sys.argv[1:]))
