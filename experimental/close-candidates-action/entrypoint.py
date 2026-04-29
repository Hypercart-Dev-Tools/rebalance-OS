#!/usr/bin/env python3
"""Per-PR close-candidates analyzer.

Triggered when a PR merges. Looks at the PR's title and body, finds open
issues that this PR likely closes (explicit closes-keyword refs that GitHub
didn't auto-close, plus high-similarity title matches), and posts an
idempotent comment on the PR.

Self-contained — stdlib + GitHub REST only. No imports from rebalance,
no SQLite, no embeddings. Designed to run inside a GitHub Actions runner
or be vendored directly into another repo.

Usage (CI):
    python entrypoint.py --repo owner/name --pr 123

Usage (local / orchestrated):
    GITHUB_TOKEN=... python entrypoint.py --repo owner/name --pr 123 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

API_BASE = "https://api.github.com"
COMMENT_MARKER = "<!-- close-candidates-bot v1 -->"

# Matchers — kept consistent with experimental/gh_close_candidates_action.py
CLOSE_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.IGNORECASE)
REF_RE = re.compile(r"(?<![/\w])#(\d+)\b")
WORD_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "an", "and", "ajax", "bug", "by", "fix", "for", "from", "hotfix",
    "in", "into", "move", "of", "on", "or", "perf", "performance", "replace",
    "security", "the", "to", "update", "use", "with",
}


@dataclass
class Candidate:
    issue_number: int
    issue_title: str
    issue_url: str
    confidence: float
    band: str                       # 'high' | 'medium'
    evidence: list[str] = field(default_factory=list)
    explicit_close: bool = False
    title_similarity: float = 0.0


# ── HTTP helpers ────────────────────────────────────────────────────────────
def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "close-candidates-bot",
    }


def _request(method: str, url: str, token: str, *, body: dict | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=_headers(token))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read())
        except Exception:
            payload = {}
        raise RuntimeError(f"GitHub {method} {url} → {e.code}: {payload.get('message', 'unknown')}") from e


def _paginate(url: str, token: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    qs = ("?" + urllib.parse.urlencode({**(params or {}), "per_page": 100})) if params else "?per_page=100"
    out: list[dict[str, Any]] = []
    next_url: str | None = url + qs
    while next_url:
        req = urllib.request.Request(next_url, headers=_headers(token))
        with urllib.request.urlopen(req, timeout=30) as resp:
            out.extend(json.loads(resp.read()))
            link = resp.headers.get("Link", "")
        next_url = None
        for piece in link.split(","):
            if 'rel="next"' in piece:
                next_url = piece.split(";")[0].strip().strip("<>")
                break
    return out


# ── Scoring ─────────────────────────────────────────────────────────────────
def _extract_closing_refs(text: str) -> set[int]:
    return {int(m.group(1)) for m in CLOSE_RE.finditer(text or "")}


def _extract_refs(text: str) -> set[int]:
    return {int(m.group(1)) for m in REF_RE.finditer(text or "")}


def _tokenize(text: str) -> set[str]:
    return {w for w in WORD_RE.findall((text or "").lower()) if w not in STOPWORDS and len(w) > 2}


def _title_similarity(a: str, b: str) -> float:
    """Jaccard over normalized tokens, with stopwords removed."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _branch_matches_issue(head_ref: str | None, issue_number: int) -> bool:
    return bool(head_ref) and re.search(rf"\b{issue_number}\b", head_ref) is not None


def score(pr: dict, issue: dict) -> Candidate:
    """Score how likely this PR addresses this issue. 0.0–1.0."""
    pr_title = str(pr.get("title") or "")
    pr_body = str(pr.get("body") or "")
    pr_head = (pr.get("head") or {}).get("ref") if isinstance(pr.get("head"), dict) else pr.get("head_ref")
    issue_num = int(issue["number"])
    issue_title = str(issue.get("title") or "")

    explicit_closes = _extract_closing_refs(pr_title + "\n" + pr_body)
    body_refs = _extract_refs(pr_body)
    sim = _title_similarity(issue_title, pr_title)

    evidence: list[str] = []
    score = 0.0
    explicit = False

    if issue_num in explicit_closes:
        score = 0.99
        explicit = True
        evidence.append(f"PR body uses a closes-keyword for #{issue_num}.")
    else:
        if issue_num in body_refs:
            score += 0.45
            evidence.append(f"PR body references #{issue_num}.")
        if _branch_matches_issue(pr_head, issue_num):
            score += 0.30
            evidence.append(f"PR branch '{pr_head}' contains the issue number.")
        if sim >= 0.6:
            score += 0.30
            evidence.append(f"Issue and PR titles are highly similar ({sim:.2f}).")
        elif sim >= 0.35:
            score += 0.18
            evidence.append(f"Issue and PR titles share several keywords ({sim:.2f}).")

    score = min(score, 0.99)
    band = "high" if explicit or score >= 0.65 else "medium"
    return Candidate(
        issue_number=issue_num,
        issue_title=issue_title,
        issue_url=str(issue.get("html_url") or ""),
        confidence=round(score, 2),
        band=band,
        evidence=evidence,
        explicit_close=explicit,
        title_similarity=round(sim, 2),
    )


# ── Pipeline ────────────────────────────────────────────────────────────────
def gather_candidates(repo: str, pr_number: int, token: str, min_confidence: float) -> tuple[dict, list[Candidate]]:
    pr = _request("GET", f"{API_BASE}/repos/{repo}/pulls/{pr_number}", token)
    if not pr.get("merged_at"):
        # Don't fail — just emit empty result. The workflow filter should handle this,
        # but a manual run on a non-merged PR shouldn't crash.
        return pr, []

    pr_body_refs = _extract_refs(str(pr.get("body") or ""))
    pr_close_refs = _extract_closing_refs(str(pr.get("body") or "") + "\n" + str(pr.get("title") or ""))

    open_issues = _paginate(
        f"{API_BASE}/repos/{repo}/issues",
        token,
        params={"state": "open", "sort": "updated", "direction": "desc"},
    )
    # GitHub's /issues endpoint mixes issues and PRs. Drop PRs.
    open_issues = [i for i in open_issues if "pull_request" not in i]

    # Only score issues we actually care about: explicit refs in PR body, OR a meaningful similarity.
    candidates: list[Candidate] = []
    for issue in open_issues:
        num = int(issue["number"])
        title_sim = _title_similarity(str(issue.get("title") or ""), str(pr.get("title") or ""))
        if num in pr_close_refs or num in pr_body_refs or title_sim >= 0.35:
            c = score(pr, issue)
            if c.confidence >= min_confidence:
                candidates.append(c)
    candidates.sort(key=lambda c: (-c.confidence, c.issue_number))
    return pr, candidates


def render_comment(repo: str, pr_number: int, candidates: list[Candidate], pr_base: str | None) -> str:
    if not candidates:
        return ""
    high = [c for c in candidates if c.band == "high"]
    medium = [c for c in candidates if c.band == "medium"]

    lines = [COMMENT_MARKER, "", "## 🎯 Close Candidates"]
    lines.append("")
    if pr_base and pr_base not in {"main", "master", "trunk"}:
        lines.append(
            f"_PR merged into `{pr_base}` (not the default branch), so GitHub did not "
            "auto-close any referenced issues. Suggestions:_"
        )
        lines.append("")

    if high:
        lines.append(f"### High confidence ({len(high)})")
        for c in high:
            lines.append(f"- **#{c.issue_number}** — {c.issue_title}  _(confidence {c.confidence:.2f})_")
            for ev in c.evidence:
                lines.append(f"  - {ev}")
        lines.append("")

    if medium:
        lines.append(f"### Medium confidence ({len(medium)})")
        for c in medium:
            lines.append(f"- #{c.issue_number} — {c.issue_title}  _(confidence {c.confidence:.2f})_")
            for ev in c.evidence:
                lines.append(f"  - {ev}")
        lines.append("")

    lines.append("---")
    lines.append(
        "_Posted by [close-candidates-bot]"
        "(https://github.com/Hypercart-Dev-Tools/rebalance-OS/tree/main/experimental/close-candidates-action). "
        "This is a suggestion only — review before closing._"
    )
    return "\n".join(lines)


def find_existing_bot_comment(repo: str, pr_number: int, token: str) -> int | None:
    """Look for our prior comment by marker. Returns comment id or None."""
    comments = _paginate(f"{API_BASE}/repos/{repo}/issues/{pr_number}/comments", token)
    for c in comments:
        if COMMENT_MARKER in (c.get("body") or ""):
            return int(c["id"])
    return None


def upsert_comment(repo: str, pr_number: int, body: str, token: str) -> dict:
    existing_id = find_existing_bot_comment(repo, pr_number, token)
    if existing_id is not None:
        return _request("PATCH", f"{API_BASE}/repos/{repo}/issues/comments/{existing_id}", token, body={"body": body})
    return _request("POST", f"{API_BASE}/repos/{repo}/issues/{pr_number}/comments", token, body={"body": body})


# ── CLI ─────────────────────────────────────────────────────────────────────
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Per-PR close-candidates analyzer")
    p.add_argument("--repo", required=False, default=os.environ.get("GITHUB_REPOSITORY"),
                   help="owner/name (defaults to $GITHUB_REPOSITORY)")
    p.add_argument("--pr", required=True, type=int, help="PR number to analyze")
    p.add_argument("--min-confidence", type=float, default=0.5, help="Skip candidates below this score (0.0–1.0)")
    p.add_argument("--dry-run", action="store_true", help="Print the comment instead of posting it")
    p.add_argument("--json", action="store_true", help="Emit JSON to stdout in addition to/instead of comment")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.repo:
        print("ERROR: --repo not provided and $GITHUB_REPOSITORY not set", file=sys.stderr)
        return 2
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: $GITHUB_TOKEN not set", file=sys.stderr)
        return 2

    pr, candidates = gather_candidates(args.repo, args.pr, token, args.min_confidence)
    pr_base = (pr.get("base") or {}).get("ref")
    comment = render_comment(args.repo, args.pr, candidates, pr_base)

    summary = {
        "repo": args.repo,
        "pr_number": args.pr,
        "merged": bool(pr.get("merged_at")),
        "base_ref": pr_base,
        "candidates": [c.__dict__ for c in candidates],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if args.json:
        print(json.dumps(summary, indent=2))

    if not candidates:
        if not args.json:
            print(f"No close candidates ≥ {args.min_confidence} for PR #{args.pr}.")
        return 0

    if args.dry_run:
        print("=== comment that would be posted ===", file=sys.stderr)
        print(comment)
        return 0

    result = upsert_comment(args.repo, args.pr, comment, token)
    print(f"Posted/updated comment #{result.get('id')} on PR #{args.pr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
