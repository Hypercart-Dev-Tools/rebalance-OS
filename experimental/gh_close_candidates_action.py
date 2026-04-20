#!/usr/bin/env python3
"""Deterministic GitHub Action helper for issue <-> PR close candidates.

This script is intentionally conservative and Action-friendly:
- reads open issues and merged PRs directly from GitHub REST API
- avoids local SQLite and embeddings
- produces JSON + Markdown outputs
- does not mutate GitHub state
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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_BASE = "https://api.github.com"
REF_RE = re.compile(r"(?<![/\w])#(\d+)\b")
CLOSE_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.IGNORECASE)
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
    pr_number: int
    pr_title: str
    pr_url: str
    confidence: float
    confidence_band: str
    recommendation: str
    evidence: list[str] = field(default_factory=list)
    explicit_close: bool = False
    title_similarity: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence"] = round(self.confidence, 2)
        data["title_similarity"] = round(self.title_similarity, 2)
        return data


@dataclass
class Report:
    repo_full_name: str
    generated_at: str
    counts: dict[str, int]
    high_confidence: list[Candidate]
    medium_confidence: list[Candidate]
    unmatched_open_issues: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "repo_full_name": self.repo_full_name,
            "generated_at": self.generated_at,
            "counts": self.counts,
            "high_confidence": [item.as_dict() for item in self.high_confidence],
            "medium_confidence": [item.as_dict() for item in self.medium_confidence],
            "unmatched_open_issues": self.unmatched_open_issues,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "rebalance-experimental/gh-close-candidates",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _http_get(url: str, token: str) -> Any:
    request = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(f"GitHub API request failed: {exc.code} {url} {body}") from exc


def _paginate(url: str, token: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    page = 1
    results: list[dict[str, Any]] = []
    while True:
        query = dict(params or {})
        query["per_page"] = 100
        query["page"] = page
        full_url = f"{url}?{urllib.parse.urlencode(query)}"
        data = _http_get(full_url, token)
        if not isinstance(data, list) or not data:
            break
        results.extend(data)
        if len(data) < 100:
            break
        page += 1
    return results


def _extract_refs(text: str) -> set[int]:
    return {int(num) for num in REF_RE.findall(text or "")}


def _extract_closing_refs(text: str) -> set[int]:
    return {int(num) for num in CLOSE_RE.findall(text or "")}


def _tokenize(text: str) -> set[str]:
    words = {word.lower() for word in WORD_RE.findall((text or "").lower())}
    return {word for word in words if len(word) >= 3 and word not in STOPWORDS and not word.isdigit()}


def _title_similarity(issue_title: str, pr_title: str) -> float:
    issue_tokens = _tokenize(issue_title)
    pr_tokens = _tokenize(pr_title)
    if not issue_tokens or not pr_tokens:
        return 0.0
    overlap = len(issue_tokens & pr_tokens)
    return overlap / max(len(issue_tokens), len(pr_tokens))


def _branch_matches_issue(head_ref: str, issue_number: int) -> bool:
    return re.search(rf"(^|[^0-9]){issue_number}([^0-9]|$)", head_ref or "") is not None


def build_close_candidates_report(
    repo_full_name: str,
    default_branch: str,
    open_issues: list[dict[str, Any]],
    merged_prs: list[dict[str, Any]],
    *,
    high_threshold: float = 0.85,
    medium_threshold: float = 0.65,
) -> Report:
    high: list[Candidate] = []
    medium: list[Candidate] = []
    matched_issue_numbers: set[int] = set()

    for issue in open_issues:
        issue_number = int(issue["number"])
        issue_body = str(issue.get("body") or "")
        issue_text = "\n".join([str(issue.get("title") or ""), issue_body])
        issue_pr_refs = _extract_refs(issue_text)
        candidates: list[Candidate] = []

        for pr in merged_prs:
            pr_number = int(pr["number"])
            pr_body = str(pr.get("body") or "")
            pr_text = "\n".join([str(pr.get("title") or ""), pr_body])
            explicit_close = issue_number in _extract_closing_refs(pr_text)
            explicit_ref = issue_number in _extract_refs(pr_text)
            issue_mentions_pr = pr_number in issue_pr_refs
            branch_match = _branch_matches_issue(str(pr.get("headRefName") or ""), issue_number)
            title_similarity = _title_similarity(str(issue.get("title") or ""), str(pr.get("title") or ""))

            score = 0.0
            evidence: list[str] = []

            if explicit_close:
                score = 0.99
                evidence.append(f"PR #{pr_number} explicitly uses a closing keyword for issue #{issue_number}.")
            else:
                if explicit_ref:
                    score += 0.45
                    evidence.append(f"PR #{pr_number} explicitly references issue #{issue_number}.")
                if issue_mentions_pr:
                    score += 0.30
                    evidence.append(f"Issue #{issue_number} text explicitly mentions PR #{pr_number}.")
                if branch_match:
                    score += 0.35
                    evidence.append(f"PR branch `{pr.get('headRefName', '')}` contains issue number {issue_number}.")
                if title_similarity >= 0.6:
                    score += 0.30
                    evidence.append(f"Issue and PR titles are highly similar ({title_similarity:.2f}).")
                elif title_similarity >= 0.35:
                    score += 0.18
                    evidence.append(f"Issue and PR titles have moderate overlap ({title_similarity:.2f}).")
                elif title_similarity >= 0.2:
                    score += 0.10
                    evidence.append(f"Issue and PR titles have some overlap ({title_similarity:.2f}).")
                if issue_mentions_pr and branch_match:
                    score += 0.20
                    evidence.append("Issue text and PR branch naming reinforce the same issue/PR pair.")
                if explicit_ref and title_similarity >= 0.2:
                    score += 0.10
                    evidence.append("The explicit PR reference is reinforced by title overlap.")

            if score < medium_threshold:
                continue

            confidence_band = "high" if score >= high_threshold else "medium"
            recommendation = "auto_close_recommended" if explicit_close else (
                "close_recommended" if confidence_band == "high" else "manual_review_recommended"
            )
            candidates.append(
                Candidate(
                    issue_number=issue_number,
                    issue_title=str(issue.get("title") or ""),
                    issue_url=str(issue.get("html_url") or issue.get("url") or ""),
                    pr_number=pr_number,
                    pr_title=str(pr.get("title") or ""),
                    pr_url=str(pr.get("html_url") or pr.get("url") or ""),
                    confidence=min(score, 0.99),
                    confidence_band=confidence_band,
                    recommendation=recommendation,
                    evidence=evidence,
                    explicit_close=explicit_close,
                    title_similarity=title_similarity,
                )
            )

        if not candidates:
            continue

        candidates.sort(
            key=lambda item: (item.confidence, item.explicit_close, item.title_similarity),
            reverse=True,
        )
        best = candidates[0]
        matched_issue_numbers.add(issue_number)
        if best.confidence_band == "high":
            high.append(best)
        else:
            medium.append(best)

    high.sort(key=lambda item: (item.recommendation, item.confidence), reverse=True)
    medium.sort(key=lambda item: item.confidence, reverse=True)
    counts = {
        "open_issues_considered": len(open_issues),
        "merged_prs_considered": len(merged_prs),
        "high_confidence": len(high),
        "medium_confidence": len(medium),
        "explicit_auto_close": sum(1 for item in high if item.recommendation == "auto_close_recommended"),
    }
    return Report(
        repo_full_name=repo_full_name,
        generated_at=_now_iso(),
        counts=counts,
        high_confidence=high,
        medium_confidence=medium,
        unmatched_open_issues=max(len(open_issues) - len(matched_issue_numbers), 0),
    )


def render_markdown(report: Report) -> str:
    lines = [
        f"# Close Candidates Report — {report.repo_full_name}",
        "",
        f"Generated at: `{report.generated_at}`",
        "",
        "## Summary",
        "",
        f"- Open issues considered: {report.counts['open_issues_considered']}",
        f"- Merged PRs considered: {report.counts['merged_prs_considered']}",
        f"- High confidence: {report.counts['high_confidence']}",
        f"- Medium confidence: {report.counts['medium_confidence']}",
        f"- Explicit auto-close candidates: {report.counts['explicit_auto_close']}",
        f"- Unmatched open issues: {report.unmatched_open_issues}",
        "",
    ]
    if report.high_confidence:
        lines.extend(["## High Confidence", ""])
        for item in report.high_confidence:
            lines.append(
                f"- Issue #{item.issue_number} -> PR #{item.pr_number} "
                f"({item.recommendation}, confidence {item.confidence:.2f})"
            )
            lines.append(f"  - Issue: {item.issue_title}")
            lines.append(f"  - PR: {item.pr_title}")
            for evidence in item.evidence[:3]:
                lines.append(f"  - Evidence: {evidence}")
        lines.append("")
    if report.medium_confidence:
        lines.extend(["## Medium Confidence", ""])
        for item in report.medium_confidence:
            lines.append(
                f"- Issue #{item.issue_number} -> PR #{item.pr_number} "
                f"({item.recommendation}, confidence {item.confidence:.2f})"
            )
            lines.append(f"  - Issue: {item.issue_title}")
            lines.append(f"  - PR: {item.pr_title}")
            for evidence in item.evidence[:3]:
                lines.append(f"  - Evidence: {evidence}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _write_text(path: Path | None, text: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic GitHub close-candidate report.")
    parser.add_argument("--repo", required=True, help="Repo in owner/name form.")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""), help="GitHub token.")
    parser.add_argument("--json-output", default="", help="Write machine-readable report JSON to this file.")
    parser.add_argument("--markdown-output", default="", help="Write Markdown summary to this file.")
    parser.add_argument("--high-threshold", type=float, default=0.85)
    parser.add_argument("--medium-threshold", type=float, default=0.65)
    args = parser.parse_args(argv)

    if not args.token.strip():
        print("GITHUB_TOKEN or --token is required.", file=sys.stderr)
        return 2

    repo_meta = _http_get(f"{API_BASE}/repos/{args.repo}", args.token.strip())
    default_branch = str(repo_meta.get("default_branch") or "main")

    raw_issues = _paginate(
        f"{API_BASE}/repos/{args.repo}/issues",
        args.token.strip(),
        params={"state": "open", "sort": "updated", "direction": "desc"},
    )
    open_issues = [item for item in raw_issues if "pull_request" not in item]

    raw_pulls = _paginate(
        f"{API_BASE}/repos/{args.repo}/pulls",
        args.token.strip(),
        params={"state": "closed", "sort": "updated", "direction": "desc"},
    )
    merged_prs = [
        {
            "number": pr["number"],
            "title": pr.get("title", ""),
            "body": pr.get("body", ""),
            "headRefName": (pr.get("head") or {}).get("ref", ""),
            "baseRefName": (pr.get("base") or {}).get("ref", ""),
            "mergedAt": pr.get("merged_at"),
            "html_url": pr.get("html_url", ""),
            "url": pr.get("url", ""),
        }
        for pr in raw_pulls
        if pr.get("merged_at") and ((pr.get("base") or {}).get("ref") in {default_branch, "main"})
    ]

    report = build_close_candidates_report(
        args.repo,
        default_branch,
        open_issues,
        merged_prs,
        high_threshold=args.high_threshold,
        medium_threshold=args.medium_threshold,
    )
    json_text = json.dumps(report.as_dict(), ensure_ascii=False, indent=2) + "\n"
    markdown_text = render_markdown(report)

    _write_text(Path(args.json_output).expanduser(), json_text) if args.json_output else None
    _write_text(Path(args.markdown_output).expanduser(), markdown_text) if args.markdown_output else None

    print(json_text, end="")
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown_text)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
