"""The finding-sink boundary for 3-Eyes (GH-195).

A job observes a signal and produces a *finding*; a route decides where it goes.
This is the ONLY module allowed to reach GitHub (``gh``) or push git — the egress
static-guard enforces it. Four sinks:

  * ``log-only``  — append to a local findings log. Always safe, no egress.
  * ``notify``    — local desktop/log notification (macOS ``osascript``). Gated.
  * ``pdda-inbox``— draft a ``PROJECT/1-INBOX`` capture (PDDA selection rule). A
                    local file write; gated so an inert clone writes nothing.
  * ``gh-issue``  — file a GitHub issue via ``gh``. The one true egress. Gated.

``dry_run=True`` produces the artifact (e.g. the draft text) WITHOUT writing or
calling out, so the CLI ``dry-run`` and tests can exercise the path offline.
Nothing here runs unless 3-Eyes is active (``run.py`` short-circuits earlier when
inert), except ``log-only`` which is inert-safe by construction.
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
from pathlib import Path

from . import config

INBOX = config.REPO_ROOT / "PROJECT" / "1-INBOX"


def _findings_log() -> Path:
    return config.state_dir() / "findings.jsonl"


def _pdda_draft(finding: dict, now: _dt.datetime) -> tuple[str, str]:
    """Return (filename, markdown) for a PDDA 1-INBOX capture.

    Frontmatter carries the keys PDDA requires (title/status/created/updated/
    owner/goal) plus ``ratings_provisional: true`` — a machine-drafted capture is
    always provisional, so the PDDA selection rule routes it to a human.
    """
    date = now.strftime("%Y-%m-%d")
    slug = "".join(c if c.isalnum() else "-" for c in finding.get("title", "finding").lower())
    slug = "-".join(filter(None, slug.split("-")))[:48] or "finding"
    fname = f"3EYES-{date}-{slug}.md"
    severity = finding.get("severity", "info")
    summary = finding.get("summary", finding.get("title", ""))
    body = finding.get("text", "")
    md = f"""---
title: "3-Eyes finding: {finding.get('title', slug)}"
slug: {slug}
status: "DRAFT (machine-authored by 3-Eyes; unverified)"
created: {date}
updated: {date}
owner: 3-Eyes (auto) · Noel (operator)
doc_type: bugfix
goal: "Triage the {severity} signal 3-Eyes surfaced from {finding.get('source', 'a job')}."
ratings_provisional: true
source_job: {finding.get('source', 'unknown')}
severity: {severity}
---

# 3-Eyes finding — {finding.get('title', slug)}

**Severity:** {severity}

## Summary

{summary}

## Raw signal

```
{body[:4000]}
```

> Drafted by 3-Eyes. Provisional — a human owns promotion (PDDA selection rule:
> `eligible = risk<=2 AND not ratings_provisional`).
"""
    return fname, md


def route(finding: dict, routes: list[str] | tuple[str, ...], dry_run: bool = False) -> list[dict]:
    """Dispatch a finding to each configured route. Returns per-route results."""
    now = _dt.datetime.now()
    results: list[dict] = []
    for r in routes:
        if r == "log-only":
            results.append(_route_log(finding, dry_run))
        elif r == "notify":
            results.append(_route_notify(finding, dry_run))
        elif r == "pdda-inbox":
            results.append(_route_pdda(finding, now, dry_run))
        elif r == "gh-issue":
            results.append(_route_gh(finding, dry_run))
        else:
            results.append({"route": r, "status": "unknown-route"})
    return results


def _route_log(finding: dict, dry_run: bool) -> dict:
    """log-only is inert-safe: a local append, no egress, no gate."""
    if dry_run:
        return {"route": "log-only", "status": "dry-run"}
    path = _findings_log()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), **finding}
    with open(path, "a") as fh:
        fh.write(json.dumps(row) + "\n")
    return {"route": "log-only", "status": "logged", "path": str(path)}


def _route_notify(finding: dict, dry_run: bool) -> dict:
    if dry_run:
        return {"route": "notify", "status": "dry-run"}
    if not config.three_eyes_active():
        return {"route": "notify", "status": "refused-inert"}
    title = f"3-Eyes: {finding.get('severity', 'info')}"
    msg = finding.get("summary", finding.get("title", ""))[:200]
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification {json.dumps(msg)} with title {json.dumps(title)}'],
            capture_output=True, timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    return {"route": "notify", "status": "notified"}


def _route_pdda(finding: dict, now: _dt.datetime, dry_run: bool) -> dict:
    fname, md = _pdda_draft(finding, now)
    if dry_run:
        return {"route": "pdda-inbox", "status": "dry-run", "filename": fname, "content": md}
    if not config.three_eyes_active():
        return {"route": "pdda-inbox", "status": "refused-inert"}
    INBOX.mkdir(parents=True, exist_ok=True)
    path = INBOX / fname
    path.write_text(md)
    return {"route": "pdda-inbox", "status": "drafted", "path": str(path)}


def _route_gh(finding: dict, dry_run: bool) -> dict:
    """The one true egress. Files a GitHub issue via ``gh``. Gated hard."""
    if dry_run:
        return {"route": "gh-issue", "status": "dry-run"}
    if not config.three_eyes_active():
        return {"route": "gh-issue", "status": "refused-inert"}
    title = finding.get("title", "3-Eyes finding")
    body = finding.get("summary", "") + "\n\n" + finding.get("text", "")[:4000]
    try:
        proc = subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"route": "gh-issue", "status": "error", "error": str(exc)}
    if proc.returncode != 0:
        return {"route": "gh-issue", "status": "error", "error": proc.stderr.strip()}
    return {"route": "gh-issue", "status": "filed", "url": proc.stdout.strip()}
