"""Claude Code Cloud (web) sessions — signal source.

Reads the ad-hoc cloud coding sessions behind the VS Code "Claude Code > Web" tab
(``GET api.anthropic.com/v1/code/sessions``, subscription OAuth bearer token from the
macOS keychain), enriches each with its head-branch PR merge status, and exposes:

  * :func:`sessions_for_day` — normalized session rows for a local day (fail-soft).
  * :func:`grade` — a data-quality grade over those rows (the observation surface;
    written into the Obsidian daily note by ``utils/claude_cloud_daily_grade.py``).
  * :func:`claude_cloud_candidates` — the HiQS ``candidates=`` provider (GH-128).

**Ships DORMANT.** ``claude_cloud_candidates`` yields nothing unless
``claude_cloud_signal_enabled`` is set true in the config (default False) — so the
signal is fully wired into the ranker's registry seam but contributes zero to the
live verdict until the operator promotes it after watching the daily-note grade.
Promotion to first-class (a raw table + ``OperatorBundle`` field, no live read in the
ranking path) is tracked in PROJECT/1-INBOX/GH-128-CC-CLOUD-JOBS-INGEST.md.

Standalone POC twin: ``scripts/cc_cloud_jobs.py`` (stdlib-only, no package import).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from rebalance.lib.time_ops import parse_date, parse_utc_iso

logger = logging.getLogger(__name__)

BASE = "https://api.anthropic.com"
KEYCHAIN_SERVICE = "Claude Code-credentials"
CREDS_FILE = "~/.claude/.credentials.json"

# HiQS rank class for a cloud job awaiting your action — peer with open gh_items
# (see next_actions.py:509-511). Tunable when the signal is promoted to first-class.
_RANK_CLASS = 2


# --------------------------------------------------------------------- auth

def _get_token() -> str | None:
    """Subscription OAuth access token from keychain, then creds file. None if absent."""
    import os

    try:
        raw = subprocess.check_output(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            stderr=subprocess.DEVNULL, text=True, timeout=10).strip()
        tok = json.loads(raw).get("claudeAiOauth", {}).get("accessToken")
        if tok:
            return tok
    except Exception:
        pass
    try:
        with open(os.path.expanduser(CREDS_FILE)) as fh:
            return json.load(fh).get("claudeAiOauth", {}).get("accessToken")
    except Exception:
        return None


# --------------------------------------------------------------------- fetch

def _fetch_raw(token: str, hard_cap: int = 300, timeout: float = 8.0) -> list[dict]:
    """Page through /v1/code/sessions (newest first). Raises on HTTP error."""
    out: list[dict] = []
    cursor: str | None = None
    while len(out) < hard_cap:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        url = f"{BASE}/v1/code/sessions?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("anthropic-version", "2023-06-01")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode())
        out.extend(body.get("data", []))
        cursor = body.get("next_cursor")
        if not cursor:
            break
    return out


def _parse_ts(ts: str | None) -> dt.datetime | None:
    return parse_utc_iso(ts)


def normalize(s: dict) -> dict[str, Any]:
    """Flatten one raw session record to the reporting shape."""
    cfg = s.get("config") or {}
    meta = s.get("external_metadata") or {}
    branches = meta.get("current_branches") or {}
    branch = next((v for v in branches.values() if v), None)
    repo = None
    for oc in cfg.get("outcomes") or []:
        gi = oc.get("git_info") or {}
        if gi.get("repo"):
            repo = gi["repo"]
        if not branch and gi.get("branches"):
            branch = gi["branches"][0]
    if not repo:
        for src in cfg.get("sources") or []:
            url = src.get("url") or ""
            if "github.com/" in url:
                repo = url.split("github.com/", 1)[1]
                if repo.endswith(".git"):
                    repo = repo[:-4]
                break
    pts = meta.get("post_turn_summary") or {}
    if isinstance(pts, str):
        pts = {"status_detail": pts}
    return {
        "id": s.get("id"),
        "title": s.get("title"),
        "status": s.get("status"),
        "status_bucket": s.get("status_bucket"),
        "worker_status": s.get("worker_status"),
        "created_at": s.get("created_at"),
        "last_event_at": s.get("last_event_at"),
        "model": cfg.get("model") or meta.get("last_served_model"),
        "effort_level": cfg.get("effort_level"),
        "origin": cfg.get("origin"),
        "repo": repo,
        "branch": branch,
        "summary": (pts.get("status_detail") or "").strip() or None,
        "needs_action": (pts.get("needs_action") or "").strip() or None,
        "pr_number": None,
        "pr_state": None,   # OPEN|MERGED|CLOSED | None(no PR) | "?"(lookup failed)
        "pr_url": None,
    }


# ----------------------------------------------------------------- PR status

def enrich_pr_status(rows: list[dict]) -> list[dict]:
    """Best-effort: fill pr_* from each head branch's PR via `gh`. Degrades, never raises."""
    if not shutil.which("gh"):
        logger.info("claude_cloud: gh CLI absent — PR merge status omitted")
        return rows
    cache: dict[tuple, Any] = {}
    for r in rows:
        repo, branch = r.get("repo"), r.get("branch")
        if not repo or not branch:
            continue
        key = (repo, branch)
        if key not in cache:
            cache[key] = _gh_pr_for_branch(repo, branch)
        pr = cache[key]
        if pr == "ERROR":
            r["pr_state"] = "?"
        elif pr:
            r["pr_number"], r["pr_state"], r["pr_url"] = pr["number"], pr["state"], pr["url"]
    return rows


def _gh_pr_for_branch(repo: str, branch: str) -> Any:
    try:
        out = subprocess.check_output(
            ["gh", "pr", "list", "--repo", repo, "--head", branch, "--state", "all",
             "--json", "number,state,url", "--limit", "5"],
            stderr=subprocess.DEVNULL, text=True, timeout=20).strip()
        prs = json.loads(out) if out else []
        if not prs:
            return None
        merged = [p for p in prs if p.get("state") == "MERGED"]
        return (merged or prs)[0]
    except Exception:
        return "ERROR"


# ----------------------------------------------------------------- high level

def sessions_for_day(day: dt.date | None = None, *, with_pr: bool = True) -> list[dict]:
    """Normalized cloud-session rows created on ``day`` (local). [] on any failure."""
    day = day or dt.date.today()
    token = _get_token()
    if not token:
        logger.info("claude_cloud: no subscription OAuth token; signal unavailable")
        return []
    try:
        raw = _fetch_raw(token)
    except urllib.error.HTTPError as e:
        logger.warning("claude_cloud: sessions fetch failed HTTP %s", e.code)
        return []
    except Exception as e:  # noqa: BLE001 — fail-soft by contract
        logger.warning("claude_cloud: sessions fetch failed: %s", e)
        return []
    rows = []
    for s in raw:
        r = normalize(s)
        d = _parse_ts(r["created_at"])
        if d and d.astimezone().date() == day:
            rows.append(r)
    if with_pr:
        enrich_pr_status(rows)
    return rows


# ------------------------------------------------------------------- grading

_LETTER = [(0.90, "A"), (0.80, "B"), (0.70, "C"), (0.60, "D"), (0.0, "F")]


def _letter(score: float) -> str:
    return next(l for cut, l in _LETTER if score >= cut)


def grade(rows: list[dict]) -> dict[str, Any]:
    """Score data quality of the cloud-jobs signal — the observation surface.

    Dimensions (each a 0..1 coverage ratio over the day's sessions):
      identified    — repo AND branch resolved (can we attribute the work?)
      attested      — a non-empty post-turn summary (is the outcome legible?)
      outcome_known — a recognized status_bucket (do we know if it finished?)
      pr_linked     — branch maps to a real PR (informational: direct-push work is
                      valid, so this is reported, not penalized in the overall).
    """
    n = len(rows)
    if n == 0:
        return {"n": 0, "overall": None, "letter": "—", "dimensions": {},
                "counts": {}, "warnings": ["no cloud sessions today"]}

    def ratio(pred) -> float:
        return round(sum(1 for r in rows if pred(r)) / n, 3)

    known_buckets = {"review_ready", "working", "running", "failed", "error", "blocked"}
    dims = {
        "identified": ratio(lambda r: r["repo"] and r["branch"]),
        "attested": ratio(lambda r: bool(r["summary"])),
        "outcome_known": ratio(lambda r: r["status_bucket"] in known_buckets),
    }
    pr_linked = ratio(lambda r: r["pr_state"] in ("OPEN", "MERGED", "CLOSED"))
    # Overall excludes pr_linked (no-PR is a legitimate outcome, not a data defect).
    overall = round(sum(dims.values()) / len(dims), 3)

    counts = {
        "merged": sum(1 for r in rows if r["pr_state"] == "MERGED"),
        "open": sum(1 for r in rows if r["pr_state"] == "OPEN"),
        "no_pr": sum(1 for r in rows if r["pr_state"] is None and r["repo"]),
        "pr_lookup_failed": sum(1 for r in rows if r["pr_state"] == "?"),
        "running": sum(1 for r in rows if r["worker_status"] not in ("idle", None)),
        "failed": sum(1 for r in rows if (r["status_bucket"] or "") in ("failed", "error")),
    }

    warnings = []
    for r in rows:
        if not (r["repo"] and r["branch"]):
            warnings.append(f"unattributed session: {r['title'] or r['id']} (no repo/branch)")
        if not r["summary"]:
            warnings.append(f"no summary: {r['title'] or r['id']}")
    if counts["pr_lookup_failed"]:
        warnings.append(f"{counts['pr_lookup_failed']} PR lookup(s) failed (gh error)")

    return {
        "n": n,
        "overall": overall,
        "letter": _letter(overall),
        "dimensions": dims,
        "pr_linked": pr_linked,
        "counts": counts,
        "warnings": warnings,
    }


# ---------------------------------------------------- HiQS candidates provider

def _signal_enabled() -> bool:
    try:
        from rebalance.ingest.config import get_claude_cloud_config
        return bool(get_claude_cloud_config().get("claude_cloud_signal_enabled", False))
    except Exception:
        return False


def claude_cloud_candidates(bundle: Any) -> list[dict[str, Any]]:
    """HiQS ``candidates=`` provider (GH-128). DORMANT unless the config flag is on.

    Emits one candidate per cloud job that still WANTS operator action — an open PR
    to review, a failed run to fix, or a finished run with no PR to triage. A merged
    PR is done work and yields nothing. ``bundle`` is unused: this observation-phase
    provider reads live (fail-soft) rather than from an OperatorBundle field; that
    field is the first-class promotion step (GH-128 Phase 1).
    """
    if not _signal_enabled():
        return []
    try:
        day = parse_date(bundle.local_day) if getattr(bundle, "local_day", None) else None
        rows = sessions_for_day(day)
    except Exception as e:  # noqa: BLE001 — provider must never break the ranker
        logger.warning("claude_cloud_candidates: %s", e)
        return []

    out: list[dict[str, Any]] = []
    for r in rows:
        ts = r["last_event_at"] or r["created_at"] or ""
        title = r["title"] or "cloud job"
        ev = [e for e in (r["pr_url"] or r["branch"], r["summary"]) if e]
        if r["pr_state"] == "MERGED":
            continue  # done
        if r["pr_state"] == "OPEN":
            cand = {"title": f"Review PR #{r['pr_number']}: {title}",
                    "why": "cloud job finished; PR open for your review"}
        elif (r["status_bucket"] or "") in ("failed", "error"):
            cand = {"title": f"Cloud job FAILED: {title}",
                    "why": "cloud coding job did not finish cleanly"}
        elif r["status_bucket"] == "review_ready":
            cand = {"title": f"Triage cloud job: {title}",
                    "why": "cloud job finished with no PR — review the branch"}
        else:
            continue
        out.append({
            "rank_key": (_RANK_CLASS, ts),
            "source": "claude_cloud",
            "project": r["repo"],
            "evidence": ev or [r["id"] or "claude-cloud session"],
            **cand,
        })
    return out
