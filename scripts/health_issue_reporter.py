#!/usr/bin/env python3
"""Auto-file GitHub issues for failing rebalance health checks.

Runs ``rebalance doctor``, then creates/closes GitHub issues on
``Hypercart-Dev-Tools/rebalance-OS`` so
failures are tracked in the project backlog without manual triage.

Logging
-------
Every run appends a JSON record to ``temp/health-reporter.log.jsonl`` containing
the full check results, every LLM call + response, and every GitHub action taken.

De-duplication
--------------
Issues are matched by a stable check id (``Check.name`` from the doctor
registry — see ``run_doctor_checks()``), not by the GitHub issue *title*.
The id is embedded as a hidden ``<!-- health-check-id: ... -->`` marker in
the issue body at file time, so a human retitling the issue on GitHub (or a
future change to ``ISSUE_TITLE_PREFIX``) can no longer orphan it. Issues
filed before this marker existed are still matched by parsing the check name
out of their title (GH-139 legacy fallback) — see ``dedup_key_for_issue()``.
- Already **open**: refresh the Detail block and bump the occurrence counter.
- Recently **closed** (within --dedup-days, default 30): add a comment noting
  the recurrence instead of opening a new issue.
- Older closed / never filed: file a new issue.

LLM triage (``--llm-triage``)
------------------------------
Before filing, sends each finding to Claude (or a local LLM) and asks whether
it's worth a GitHub issue. Returns file / skip / downgrade + a one-line reason.

Circuit breakers (layered, all must pass to make an LLM call)
--------------------------------------------------------------
  CB-1  HEALTH_LLM_DISABLE=1 env var — hard kill switch, overrides everything.
  CB-2  Daily quota: at most --llm-daily-limit calls/day (default 8, UTC midnight
        reset). Tracked in temp/health-reporter-llm-quota.json.
  CB-3  Per-run cap: at most --llm-max-per-run calls per script invocation (default 5).
        Protects against a burst of new failures eating the daily budget in one run.
  CB-4  No key / package missing: degrades to "file" without crashing.

Usage
-----
    python scripts/health_issue_reporter.py [options]

Options
-------
    --also-pulse            Deprecated compatibility flag; collector checks are in doctor
    --warn                  File issues for WARN findings too (default: FAIL only)
    --close                 Close issues whose checks have recovered
    --llm-triage            Ask an LLM whether each finding is worth filing
    --llm-provider STR      anthropic (default) | openai-compat
    --llm-model MODEL       Model name override (or HEALTH_LLM_MODEL env var)
    --llm-base-url URL      Base URL for openai-compat (or HEALTH_LLM_BASE_URL)
    --llm-daily-limit N     Max LLM API calls per day, UTC reset (default: 8)
    --llm-max-per-run N     Max LLM calls in this single invocation (default: 5)
    --dedup-days N          Look back N days for closed issues (default: 30)
    --dry-run               Print plan; make no GitHub or LLM API calls
    --repo OWNER/REPO       Override target repo (default: Hypercart-Dev-Tools/rebalance-OS)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import _bootstrap  # noqa: F401  — puts src/ on sys.path for rebalance.* imports

DEVICE_NAME: str = socket.gethostname()

REPO = "Hypercart-Dev-Tools/rebalance-OS"
LABEL = "rebalance-health"
ISSUE_TITLE_PREFIX = "health:"

_REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = _REPO_ROOT / "temp" / "health-reporter.log.jsonl"
QUOTA_FILE = _REPO_ROOT / "temp" / "health-reporter-llm-quota.json"


# ---------------------------------------------------------------------------
# Run log — one JSONL record per invocation
# ---------------------------------------------------------------------------

class RunLog:
    """Accumulates data for this run; flushed to JSONL at exit."""

    def __init__(self, run_id: str, args_summary: dict) -> None:
        self.run_id = run_id
        self.args = args_summary
        self.checks: list[dict] = []
        self.llm_calls: list[dict] = []
        self.actions: list[dict] = []
        self.circuit_breakers_triggered: list[str] = []

    def add_check(self, check: dict) -> None:
        self.checks.append({k: check[k] for k in ("name", "status", "detail", "source")})

    def add_llm_call(self, check_name: str, model: str, provider: str,
                     decision: str, reason: str, skipped_reason: str = "") -> None:
        self.llm_calls.append({
            "check": check_name,
            "provider": provider,
            "model": model,
            "decision": decision,
            "reason": reason,
            "skipped_reason": skipped_reason,
        })

    def add_action(self, action: str, check_name: str, issue_number: int | None = None) -> None:
        entry: dict = {"action": action, "check": check_name}
        if issue_number:
            entry["issue"] = issue_number
        self.actions.append(entry)

    def add_cb(self, label: str) -> None:
        self.circuit_breakers_triggered.append(label)

    def flush(self, dry_run: bool = False) -> None:
        record = {
            "run_id": self.run_id,
            "device": DEVICE_NAME,
            "dry_run": dry_run,
            "args": self.args,
            "checks_total": len(self.checks),
            "llm_calls_this_run": len(self.llm_calls),
            "circuit_breakers_triggered": self.circuit_breakers_triggered,
            "checks": self.checks,
            "llm_calls": self.llm_calls,
            "actions": self.actions,
        }
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# LLM daily quota — CB-2
# ---------------------------------------------------------------------------

def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_quota() -> dict:
    today = _today_utc()
    if QUOTA_FILE.exists():
        try:
            data = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
            if data.get("date") == today:
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {"date": today, "calls_today": 0}


def save_quota(quota: dict) -> None:
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUOTA_FILE.write_text(json.dumps(quota, indent=2), encoding="utf-8")


def quota_remaining(daily_limit: int) -> int:
    return max(0, daily_limit - load_quota()["calls_today"])


def increment_quota() -> int:
    """Increment today's call count, return new total."""
    quota = load_quota()
    quota["calls_today"] += 1
    save_quota(quota)
    return quota["calls_today"]


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"


def _request(method: str, path: str, token: str, payload: dict | None = None) -> dict | list:
    url = f"{GITHUB_API}{path}"
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise RuntimeError(f"GitHub API {method} {url} → {exc.code}: {body_text}") from exc


def ensure_label(token: str, repo: str, dry_run: bool) -> None:
    try:
        _request("GET", f"/repos/{repo}/labels/{LABEL}", token)
        return
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise
    if dry_run:
        print(f"[dry-run] would create label '{LABEL}' on {repo}")
        return
    _request("POST", f"/repos/{repo}/labels", token,
              {"name": LABEL, "color": "d93f0b",
               "description": "Auto-filed by health_issue_reporter"})
    print(f"  created label '{LABEL}'")


def list_health_issues(token: str, repo: str, state: str = "open",
                       since_days: int = 30) -> dict[str, dict]:
    from datetime import timedelta
    issues: dict[str, dict] = {}
    since_param = ""
    if state == "closed":
        cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        since_param = f"&since={cutoff}"
    page = 1
    while True:
        results = _request(
            "GET",
            f"/repos/{repo}/issues?labels={LABEL}&state={state}&per_page=100&page={page}{since_param}",
            token,
        )
        if not isinstance(results, list) or not results:
            break
        for issue in results:
            issues[dedup_key_for_issue(issue)] = issue
        page += 1
    return issues


def file_issue(token: str, repo: str, title: str, body: str, dry_run: bool) -> int | None:
    if dry_run:
        print(f"  [dry-run] would file: {title!r}")
        return None
    result = _request("POST", f"/repos/{repo}/issues", token,
                      {"title": title, "body": body, "labels": [LABEL]})
    return result["number"]


def comment_on_issue(token: str, repo: str, number: int, comment: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would comment on issue #{number}")
        return
    _request("POST", f"/repos/{repo}/issues/{number}/comments", token, {"body": comment})


def close_issue(token: str, repo: str, number: int, comment: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would close issue #{number}")
        return
    _request("POST", f"/repos/{repo}/issues/{number}/comments", token, {"body": comment})
    _request("PATCH", f"/repos/{repo}/issues/{number}", token,
              {"state": "closed", "state_reason": "completed"})


# ---------------------------------------------------------------------------
# Issue body — occurrence counter
#
# The first line of every issue body is a blockquote counter:
#   > **Seen:** 1× · Last: 2026-05-30T20:02:43Z
#
# parse_occurrence_count() reads it; set_occurrence_count() rewrites it.
# The body text below the counter line is never touched.
# ---------------------------------------------------------------------------

_OCCURRENCE_RE = re.compile(
    r"^> \*\*Seen:\*\* (\d+)× · Last: [^\n]*\n?", re.MULTILINE
)


def parse_occurrence_count(body: str) -> int:
    m = _OCCURRENCE_RE.search(body or "")
    return int(m.group(1)) if m else 0


def set_occurrence_count(body: str, count: int, last_seen: str,
                         device: str = "") -> str:
    device_part = f" · Device: {device}" if device else ""
    new_line = f"> **Seen:** {count}× · Last: {last_seen}{device_part}\n"
    if _OCCURRENCE_RE.search(body or ""):
        return _OCCURRENCE_RE.sub(new_line, body, count=1)
    return new_line + (body or "")


# ---------------------------------------------------------------------------
# Issue body — Detail block refresh
#
# _issue_body() writes the finding's Detail as a fenced code block:
#   **Detail:**
#   ```
#   <detail text>
#   ```
#
# Previously only set_occurrence_count() ran on a repeat sighting, so a
# changed root-cause message on re-fire never reached the issue (GH-139).
# set_detail() rewrites that block in place; everything else in the body
# (title, status line, hint, footer, occurrence counter, check-id marker)
# is left untouched.
# ---------------------------------------------------------------------------

_DETAIL_RE = re.compile(r"\*\*Detail:\*\*\n```\n.*?\n```", re.DOTALL)


def set_detail(body: str, detail: str) -> str:
    if not _DETAIL_RE.search(body or ""):
        return body
    replacement = f"**Detail:**\n```\n{detail}\n```"
    return _DETAIL_RE.sub(lambda _m: replacement, body, count=1)


# ---------------------------------------------------------------------------
# Issue body — stable check-id marker (GH-139)
#
# Dedup used to key off the rendered GitHub issue *title*
# (``f"{ISSUE_TITLE_PREFIX} {check['name']}"``), matched via exact string
# equality against ``issue["title"]``. That title is mutable — a human can
# retitle the issue on GitHub, or a future edit to ISSUE_TITLE_PREFIX (or to
# a check's own registry name) changes the computed string — and either one
# silently orphans the existing issue and files a duplicate under the new
# title.
#
# Instead, every issue this script files carries a hidden marker line
# embedding the check's stable registry id (``Check.name`` — see
# ``run_doctor_checks()``, already the identifier used throughout the doctor
# check registry, independent of any GitHub-side display text):
#   <!-- health-check-id: <check-name> -->
#
# dedup_key_for_issue() reads that marker first. Issues filed before this
# marker existed (e.g. the pre-GH-139 pulse-collector duplicates, #46-48 and
# #83-85) have no marker, so it falls back to parsing the check name out of
# the title — preserving today's matching behavior for those legacy issues
# rather than re-duplicating or auto-touching them.
# ---------------------------------------------------------------------------

_CHECK_ID_RE = re.compile(r"^<!-- health-check-id: (.+?) -->\n?", re.MULTILINE)


def check_id_marker(check_id: str) -> str:
    return f"<!-- health-check-id: {check_id} -->\n"


def parse_check_id(body: str) -> str | None:
    m = _CHECK_ID_RE.search(body or "")
    return m.group(1).strip() if m else None


def dedup_key_for_issue(issue: dict) -> str:
    """Stable dedup key for an existing GitHub issue — see module docstring."""
    check_id = parse_check_id(issue.get("body") or "")
    if check_id:
        return check_id
    title = issue.get("title") or ""
    prefix = f"{ISSUE_TITLE_PREFIX} "
    return title[len(prefix):] if title.startswith(prefix) else title


def update_issue_body(
    token: str, repo: str, number: int, new_body: str, dry_run: bool
) -> None:
    if dry_run:
        print(f"  [dry-run] would update body of issue #{number}")
        return
    _request("PATCH", f"/repos/{repo}/issues/{number}", token, {"body": new_body})


# ---------------------------------------------------------------------------
# Issue body builder
# ---------------------------------------------------------------------------

def _issue_body(check_name: str, status: str, detail: str, hint: str, source: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [
        f"> **Seen:** 1× · Last: {now} · Device: {DEVICE_NAME}\n",
        check_id_marker(check_name),
        f"## Rebalance health: `{check_name}`\n",
        f"**Status:** `{status.upper()}`  ",
        f"**Detected:** {now}  ",
        f"**Source:** {source}  ",
        f"**Device:** `{DEVICE_NAME}`\n",
        f"**Detail:**\n```\n{detail}\n```",
    ]
    if hint:
        parts.append(f"\n**Hint:** {hint}")
    parts.append(
        "\n---\n*Auto-filed by `scripts/health_issue_reporter.py`. "
        "Close this issue once the underlying problem is resolved — "
        "the script will re-open it if the check fails again.*"
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Collector checks
# ---------------------------------------------------------------------------

def run_doctor_checks() -> list[dict]:
    from rebalance.doctor import run_doctor  # noqa: PLC0415
    report = run_doctor()
    return [
        {"name": c.name, "status": c.status, "detail": c.detail,
         "hint": c.hint, "source": "rebalance-doctor"}
        for c in report.checks
    ]


# ---------------------------------------------------------------------------
# LLM triage — generic provider interface
#
# Providers:
#   anthropic      — Anthropic SDK (pip install anthropic). Default.
#   openai-compat  — Any OpenAI-compatible endpoint: Ollama, LM Studio,
#                    Codex Desktop, or any local runner.
#                    Env: HEALTH_LLM_BASE_URL, HEALTH_LLM_MODEL, HEALTH_LLM_API_KEY
# ---------------------------------------------------------------------------

_TRIAGE_SYSTEM = """\
You are a pragmatic DevOps engineer triaging automated health-check alerts for
rebalance-OS, a developer tool that runs continuously on a configured machine.
This is NOT a first-run setup environment — it is a machine that was already
set up and is expected to remain operational.

Given a single health check finding, decide whether it warrants a GitHub issue.

Status meanings in this context:
  fail — something that was working is now broken or missing. Even if there is
         a remediation step, a regression on a configured machine is worth tracking.
  warn — degraded or stale state; may be transient or optional-integration related.

Reply with EXACTLY one JSON object and nothing else:
{
  "decision": "file" | "skip" | "downgrade",
  "reason": "<one sentence>"
}

"file"      — actionable, persistent, a regression, or a real failure that blocks
              sync. FAIL checks should almost always be "file".
"skip"      — noise, a known non-issue, or an optional integration the operator
              has deliberately not configured (e.g. calendar, Sleuth on a machine
              that does not use those features). Reserve "skip" for WARN checks only.
"downgrade" — worth tracking but lower urgency than its raw status suggests.
"""

_TRIAGE_USER = """\
Check name:  {name}
Status:      {status}
Detail:      {detail}
Hint:        {hint}
"""

_FALLBACK = ("file", "triage unavailable — filing by default")


def _strip_code_fence(text: str) -> str:
    """Remove leading ```json / ``` fences that some models wrap around JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the opening fence line and the closing ``` (if present).
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return text


def _triage_gemini(user_msg: str, model: str, api_key: str | None) -> dict:
    import json as _json
    import urllib.request
    
    if not api_key:
        print("  [llm-triage] GEMINI_API_KEY is not set", file=sys.stderr)
        return {}
        
    model = model or "gemini-3.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    body = _json.dumps({
        "systemInstruction": {"parts": [{"text": _TRIAGE_SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
        "generationConfig": {"maxOutputTokens": 256, "responseMimeType": "application/json"}
    }).encode()
    
    req = urllib.request.Request(
        url, data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = _json.loads(resp.read().decode())
    except Exception as exc:
        print(f"  [llm-triage] gemini api error: {exc}", file=sys.stderr)
        return {}
        
    candidates = payload.get("candidates") or []
    if not candidates:
        return {}
        
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        return {}
        
    raw = parts[0].get("text", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"{exc.msg} — raw model response: {raw!r}", exc.doc, exc.pos
        ) from exc


def _triage_openai_compat(user_msg: str, base_url: str, model: str, api_key: str) -> dict:
    try:
        import openai  # noqa: PLC0415
    except ImportError:
        print("  [llm-triage] openai not installed; try: pip install openai", file=sys.stderr)
        return {}
    client = openai.OpenAI(base_url=base_url, api_key=api_key or "local")
    resp = client.chat.completions.create(
        model=model, max_tokens=256,
        messages=[
            {"role": "system", "content": _TRIAGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    return json.loads(resp.choices[0].message.content.strip())


def llm_triage(
    check: dict,
    provider: str = "gemini",
    model: str = "",
    base_url: str = "",
    api_key: str | None = None,
) -> tuple[str, str]:
    """Call the LLM and return (decision, reason). Fail-open on any error (CB-4)."""
    user_msg = _TRIAGE_USER.format(
        name=check["name"], status=check["status"].upper(),
        detail=check["detail"], hint=check["hint"],
    )
    try:
        if provider == "openai-compat":
            resolved_url = base_url or os.environ.get("HEALTH_LLM_BASE_URL", "")
            resolved_model = model or os.environ.get("HEALTH_LLM_MODEL", "")
            resolved_key = api_key or os.environ.get("HEALTH_LLM_API_KEY", "local")
            if not resolved_url or not resolved_model:
                print("  [llm-triage] openai-compat requires HEALTH_LLM_BASE_URL + HEALTH_LLM_MODEL",
                      file=sys.stderr)
                return _FALLBACK
            result = _triage_openai_compat(user_msg, resolved_url, resolved_model, resolved_key)
        else:
            from rebalance.ingest.config import get_gemini_api_key
            resolved_model = model or os.environ.get("HEALTH_LLM_MODEL", "")
            resolved_key = api_key or get_gemini_api_key()
            result = _triage_gemini(user_msg, resolved_model, resolved_key)

        if isinstance(result, dict) and result:
            return result.get("decision", "file"), result.get("reason", "")
        return _FALLBACK
    except Exception as exc:  # noqa: BLE001 — CB-4: never crash the reporter
        print(f"  [llm-triage] error: {exc} — filing by default", file=sys.stderr)
        return "file", f"triage error: {exc}"


# ---------------------------------------------------------------------------
# GitHub token resolver
# ---------------------------------------------------------------------------

def _resolve_token() -> str:
    from rebalance.ingest.config import get_github_token_with_source  # noqa: PLC0415
    token, source = get_github_token_with_source()
    if not token:
        sys.exit("No GitHub token found. Run `rebalance config set-github-token` first.")
    if source != "config":
        print(f"  Warning: GitHub token via '{source}' (not config — launchd jobs may fail)",
              file=sys.stderr)
    return token


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--also-pulse", action="store_true",
        help="Deprecated; rebalance doctor already includes collector checks.",
    )
    parser.add_argument("--warn", action="store_true",
                        help="File issues for WARN findings too (default: FAIL only)")
    parser.add_argument("--close", action="store_true",
                        help="Close issues whose checks have recovered")
    parser.add_argument("--llm-triage", action="store_true",
                        help="Ask an LLM whether each finding is worth filing")
    parser.add_argument("--llm-provider", default="gemini",
                        choices=["gemini", "openai-compat"])
    parser.add_argument("--llm-model", default="", metavar="MODEL")
    parser.add_argument("--llm-base-url", default="", metavar="URL")
    parser.add_argument("--llm-daily-limit", type=int, default=8, metavar="N",
                        help="Max LLM API calls per UTC day (default: 8). CB-2.")
    parser.add_argument("--llm-max-per-run", type=int, default=5, metavar="N",
                        help="Max LLM calls in this invocation (default: 5). CB-3.")
    parser.add_argument("--dedup-days", type=int, default=30, metavar="N")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", default=REPO, metavar="OWNER/REPO")
    args = parser.parse_args()

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_log = RunLog(now_str, {
        "repo": args.repo, "warn": args.warn, "close": args.close,
        "llm_triage": args.llm_triage, "llm_provider": args.llm_provider,
        "llm_model": args.llm_model or os.environ.get("HEALTH_LLM_MODEL", ""),
        "llm_daily_limit": args.llm_daily_limit,
        "llm_max_per_run": args.llm_max_per_run,
        "dry_run": args.dry_run,
    })

    print(f"rebalance health issue reporter — {now_str}")
    print(f"  repo:             {args.repo}")
    print(f"  file:             {'FAIL+WARN' if args.warn else 'FAIL only'}")
    print(f"  llm-triage:       {'yes' if args.llm_triage else 'no'}")
    if args.llm_triage:
        remaining = quota_remaining(args.llm_daily_limit)
        disabled = bool(os.environ.get("HEALTH_LLM_DISABLE"))
        print(f"  llm quota today:  {remaining}/{args.llm_daily_limit} remaining"
              + (" [CB-1: DISABLED via env]" if disabled else ""))
        print(f"  llm max/run:      {args.llm_max_per_run}  [CB-3]")
        # CB-1 check: hard kill switch
        if disabled:
            run_log.add_cb("CB-1: HEALTH_LLM_DISABLE")
            print("  [CB-1] HEALTH_LLM_DISABLE=1 — LLM triage will be skipped")
        # Gemini key check (fail early with a clear message)
        from rebalance.ingest.config import get_gemini_api_key
        if args.llm_provider == "gemini" and not get_gemini_api_key():
            print("\n  Warning: GEMINI_API_KEY is not set.")
            print("  Set it with:  export GEMINI_API_KEY=<your-key>")
            print("  LLM triage will degrade gracefully to 'file' for all checks.\n")
    print(f"  dry-run:          {'yes' if args.dry_run else 'no'}")
    print(f"  log:              {LOG_FILE.relative_to(_REPO_ROOT)}")
    print()

    # --- Collect checks ---
    print("Running rebalance doctor...")
    checks = run_doctor_checks()
    if args.also_pulse:
        print("  --also-pulse is redundant; collector checks come from rebalance doctor")
    print(f"  {len(checks)} check(s) collected")
    for c in checks:
        run_log.add_check(c)
    print()

    # --- GitHub state ---
    token = _resolve_token()
    ensure_label(token, args.repo, args.dry_run)
    print("Fetching health issues from GitHub...")
    if args.dry_run:
        open_issues: dict[str, dict] = {}
        recently_closed: dict[str, dict] = {}
    else:
        open_issues = list_health_issues(token, args.repo, state="open")
        recently_closed = list_health_issues(token, args.repo, state="closed",
                                             since_days=args.dedup_days)
    print(f"  {len(open_issues)} open, {len(recently_closed)} recently closed")
    print()

    min_level = {"fail", "warn"} if args.warn else {"fail"}
    filed = closed = skipped = triaged_skip = 0
    llm_calls_this_run = 0

    for check in checks:
        check_id = check["name"]  # stable, registry-level id — see run_doctor_checks()
        title = f"{ISSUE_TITLE_PREFIX} {check_id}"
        already_open = open_issues.get(check_id)
        recently_was_closed = recently_closed.get(check_id)

        if check["status"] in min_level:
            if already_open:
                # Refresh the Detail block, then increment the occurrence
                # counter in the issue body (GH-139: Detail used to go stale
                # forever after the first sighting).
                current_body = already_open.get("body") or ""
                refreshed_body = set_detail(current_body, check["detail"])
                new_count = parse_occurrence_count(refreshed_body) + 1
                new_body = set_occurrence_count(refreshed_body, new_count, now_str,
                                                device=DEVICE_NAME)
                update_issue_body(token, args.repo, already_open["number"], new_body, args.dry_run)
                print(f"  SEEN×{new_count:<3} {check['status'].upper():4}  {check['name']}  "
                      f"(#{already_open['number']} open, counter updated)")
                run_log.add_action("seen-increment", check["name"], already_open["number"])
                skipped += 1
                continue

            # --- LLM triage gate ---
            triage_decision = "file"
            triage_reason = "triage not enabled"

            if args.llm_triage and not args.dry_run:
                cb1 = bool(os.environ.get("HEALTH_LLM_DISABLE"))  # CB-1
                cb2 = quota_remaining(args.llm_daily_limit) <= 0   # CB-2
                cb3 = llm_calls_this_run >= args.llm_max_per_run   # CB-3

                if cb1:
                    triage_reason = "CB-1: HEALTH_LLM_DISABLE set"
                    run_log.add_cb("CB-1")
                elif cb2:
                    triage_reason = f"CB-2: daily quota exhausted ({args.llm_daily_limit}/day)"
                    run_log.add_cb("CB-2: daily quota")
                    print(f"  [CB-2] daily LLM quota exhausted ({args.llm_daily_limit}/day) "
                          "— filing remaining checks without triage")
                elif cb3:
                    triage_reason = f"CB-3: per-run cap reached ({args.llm_max_per_run}/run)"
                    run_log.add_cb("CB-3: per-run cap")
                    print(f"  [CB-3] per-run LLM cap reached ({args.llm_max_per_run}) "
                          "— filing remaining checks without triage")
                else:
                    triage_decision, triage_reason = llm_triage(
                        check,
                        provider=args.llm_provider,
                        model=args.llm_model,
                        base_url=args.llm_base_url,
                    )
                    llm_calls_this_run += 1
                    if not args.dry_run:
                        increment_quota()

                run_log.add_llm_call(
                    check["name"],
                    model=args.llm_model or os.environ.get("HEALTH_LLM_MODEL", "claude-haiku-4-5-20251001"),
                    provider=args.llm_provider,
                    decision=triage_decision,
                    reason=triage_reason,
                )
                icon = {"file": "→", "skip": "✗", "downgrade": "↓"}.get(triage_decision, "→")
                print(f"  TRIAGE {check['status'].upper():4}  {check['name']}  "
                      f"{icon} {triage_decision}: {triage_reason}")
                if triage_decision == "skip":
                    run_log.add_action("triage-skip", check["name"])
                    triaged_skip += 1
                    continue

            # --- File or note recurrence ---
            if recently_was_closed:
                number = recently_was_closed["number"]
                recur_comment = (
                    f"**Recurrence detected** ({now_str}) · Device: `{DEVICE_NAME}`\n\n"
                    f"This check is failing again after being closed.\n\n"
                    f"**Detail:** {check['detail']}\n"
                    + (f"**Hint:** {check['hint']}" if check["hint"] else "")
                )
                comment_on_issue(token, args.repo, number, recur_comment, args.dry_run)
                action_str = "[dry-run] would comment" if args.dry_run else f"commented on #{number}"
                print(f"  RECUR  {check['status'].upper():4}  {check['name']}  "
                      f"(closed #{number}, {action_str})")
                run_log.add_action("recurrence-comment", check["name"], number)
                filed += 1
            else:
                body = _issue_body(check["name"], check["status"],
                                   check["detail"], check["hint"], check["source"])
                number = file_issue(token, args.repo, title, body, args.dry_run)
                num_str = f"#{number}" if number else "(dry-run)"
                print(f"  FILED  {check['status'].upper():4}  {check['name']}  → {num_str}")
                run_log.add_action("filed", check["name"], number)
                filed += 1

        elif check["status"] == "ok" and already_open and args.close:
            comment = (f"This check now reports **OK** as of {now_str}. Auto-closing.\n\n"
                       f"Detail: {check['detail']}")
            close_issue(token, args.repo, already_open["number"], comment, args.dry_run)
            print(f"  CLOSED ok    {check['name']}  (was #{already_open['number']})")
            run_log.add_action("closed", check["name"], already_open["number"])
            closed += 1

    print()
    triage_note = f", {triaged_skip} triage-skipped" if args.llm_triage else ""
    print(f"Done — {filed} filed/actioned, {closed} closed, "
          f"{skipped} counter-incremented{triage_note}")
    if args.llm_triage and not args.dry_run:
        remaining = quota_remaining(args.llm_daily_limit)
        print(f"LLM quota remaining today: {remaining}/{args.llm_daily_limit}")

    run_log.flush(dry_run=args.dry_run)
    print(f"Run logged → {LOG_FILE.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
