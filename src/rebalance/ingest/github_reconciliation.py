"""
Issue <-> PR reconciliation over the local GitHub corpus.

This module finds open issues that likely have already been fixed by a merged
PR but were not closed on GitHub. It keeps explicit links separate from
inferred links and returns confidence, evidence, and recommended actions.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest.db import db_connection, ensure_github_schema

_REF_RE = re.compile(r"(?<![/\w])#(\d+)\b")
_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "ajax",
    "bug",
    "by",
    "for",
    "from",
    "fix",
    "hotfix",
    "in",
    "into",
    "move",
    "of",
    "on",
    "or",
    "perf",
    "performance",
    "replace",
    "security",
    "the",
    "to",
    "update",
    "use",
    "with",
}


@dataclass
class IssuePRRecommendation:
    issue_number: int
    issue_title: str
    issue_html_url: str
    issue_milestone_title: str
    pr_number: int
    pr_title: str
    pr_html_url: str
    confidence: float
    confidence_band: str
    recommendation: str
    evidence: list[str] = field(default_factory=list)
    explicit_link: bool = False
    explicit_close: bool = False
    issue_state: str = ""
    pr_state: str = ""
    pr_review_decision: str = ""
    pr_check_status: str = ""
    pr_merged_at: str = ""
    title_similarity: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence"] = round(self.confidence, 2)
        data["title_similarity"] = round(self.title_similarity, 2)
        return data


@dataclass
class GitHubIssuePRReport:
    repo_full_name: str
    generated_at: str
    summary: str
    counts: dict[str, int] = field(default_factory=dict)
    high_confidence: list[IssuePRRecommendation] = field(default_factory=list)
    medium_confidence: list[IssuePRRecommendation] = field(default_factory=list)
    unmatched_open_issues: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "repo_full_name": self.repo_full_name,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "counts": self.counts,
            "high_confidence": [item.as_dict() for item in self.high_confidence],
            "medium_confidence": [item.as_dict() for item in self.medium_confidence],
            "unmatched_open_issues": self.unmatched_open_issues,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_refs(text: str) -> set[int]:
    if not text:
        return set()
    return {int(num) for num in _REF_RE.findall(text)}


def _tokenize(text: str) -> set[str]:
    words = {word.lower() for word in _WORD_RE.findall((text or "").lower())}
    return {word for word in words if len(word) >= 3 and word not in _STOPWORDS and not word.isdigit()}


def _title_similarity(issue_title: str, pr_title: str) -> float:
    issue_tokens = _tokenize(issue_title)
    pr_tokens = _tokenize(pr_title)
    if not issue_tokens or not pr_tokens:
        return 0.0
    overlap = len(issue_tokens & pr_tokens)
    return overlap / max(len(issue_tokens), len(pr_tokens))


def _head_ref_matches_issue(head_ref: str, issue_number: int) -> bool:
    if not head_ref:
        return False
    return re.search(rf"(^|[^0-9]){issue_number}([^0-9]|$)", head_ref) is not None


def _group_rows_by_number(rows: list[dict[str, Any]], key: str, value_key: str) -> dict[int, list[str]]:
    grouped: dict[int, list[str]] = {}
    for row in rows:
        number = int(row[key])
        value = str(row.get(value_key) or "").strip()
        if value:
            grouped.setdefault(number, []).append(value)
    return grouped


def infer_issue_pr_close_candidates(
    database_path: Path,
    repo_full_name: str,
    *,
    high_threshold: float = 0.85,
    medium_threshold: float = 0.65,
) -> GitHubIssuePRReport:
    generated_at = _now_iso()
    with db_connection(database_path, ensure_github_schema) as conn:
        repo_meta_row = conn.execute(
            "SELECT default_branch FROM github_repo_meta WHERE repo_full_name = ?",
            (repo_full_name,),
        ).fetchone()
        if not repo_meta_row:
            return GitHubIssuePRReport(
                repo_full_name=repo_full_name,
                generated_at=generated_at,
                summary="No local GitHub data found for this repo. Sync artifacts first.",
                counts={
                    "open_issues_considered": 0,
                    "merged_prs_considered": 0,
                    "high_confidence": 0,
                    "medium_confidence": 0,
                    "explicit_auto_close": 0,
                },
                unmatched_open_issues=0,
            )

        default_branch = repo_meta_row["default_branch"] or "main"
        open_issues = [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM github_items
                WHERE repo_full_name = ?
                  AND item_type = 'issue'
                  AND state = 'open'
                ORDER BY updated_at DESC, number DESC
                """,
                (repo_full_name,),
            ).fetchall()
        ]
        merged_prs = [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM github_items
                WHERE repo_full_name = ?
                  AND item_type = 'pull_request'
                  AND is_merged = 1
                  AND (base_ref = ? OR base_ref = 'main')
                ORDER BY merged_at DESC, updated_at DESC
                """,
                (repo_full_name, default_branch),
            ).fetchall()
        ]
        pr_by_number = {int(pr["number"]): pr for pr in merged_prs}

        explicit_link_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT source_number, target_number, link_kind
                FROM github_links
                WHERE repo_full_name = ?
                  AND source_type = 'pull_request'
                  AND target_type = 'issue'
                """,
                (repo_full_name,),
            ).fetchall()
        ]
        explicit_by_issue: dict[int, list[dict[str, Any]]] = {}
        for row in explicit_link_rows:
            pr = pr_by_number.get(int(row["source_number"]))
            if not pr:
                continue
            explicit_by_issue.setdefault(int(row["target_number"]), []).append(
                {"pr": pr, "link_kind": str(row["link_kind"] or "")}
            )

        issue_comment_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT item_number, body
                FROM github_comments
                WHERE repo_full_name = ?
                  AND item_type = 'issue'
                """,
                (repo_full_name,),
            ).fetchall()
        ]
        issue_comments = _group_rows_by_number(issue_comment_rows, "item_number", "body")

        pr_comment_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT item_number, body
                FROM github_comments
                WHERE repo_full_name = ?
                  AND item_type = 'pull_request'
                """,
                (repo_full_name,),
            ).fetchall()
        ]
        pr_comments = _group_rows_by_number(pr_comment_rows, "item_number", "body")

        pr_commit_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT item_number, message
                FROM github_commits
                WHERE repo_full_name = ?
                  AND item_type = 'pull_request'
                """,
                (repo_full_name,),
            ).fetchall()
        ]
        pr_commits = _group_rows_by_number(pr_commit_rows, "item_number", "message")

        high_confidence: list[IssuePRRecommendation] = []
        medium_confidence: list[IssuePRRecommendation] = []
        matched_issue_numbers: set[int] = set()

        for issue in open_issues:
            issue_number = int(issue["number"])
            issue_text_parts = [str(issue.get("title") or ""), str(issue.get("body") or "")]
            issue_text_parts.extend(issue_comments.get(issue_number, []))
            issue_text = "\n".join(part for part in issue_text_parts if part)
            issue_pr_refs = {ref for ref in _extract_refs(issue_text) if ref in pr_by_number}

            candidates: list[IssuePRRecommendation] = []
            for pr in merged_prs:
                pr_number = int(pr["number"])
                title_similarity = _title_similarity(issue["title"], pr["title"])
                pr_text_parts = [str(pr.get("title") or ""), str(pr.get("body") or "")]
                pr_text_parts.extend(pr_comments.get(pr_number, []))
                pr_text_parts.extend(pr_commits.get(pr_number, []))
                pr_text = "\n".join(part for part in pr_text_parts if part)

                explicit_links = [
                    item for item in explicit_by_issue.get(issue_number, [])
                    if int(item["pr"]["number"]) == pr_number
                ]
                explicit_close = any(link["link_kind"] == "closes" for link in explicit_links)
                explicit_link = bool(explicit_links)
                issue_mentions_pr = pr_number in issue_pr_refs
                branch_issue_match = _head_ref_matches_issue(pr.get("head_ref", ""), issue_number)
                commit_mentions_issue = issue_number in _extract_refs("\n".join(pr_commits.get(pr_number, [])))
                pr_mentions_issue = issue_number in _extract_refs(pr_text)
                same_milestone = bool(
                    issue.get("milestone_title")
                    and issue.get("milestone_title") == pr.get("milestone_title")
                )

                score = 0.0
                evidence: list[str] = []

                if explicit_close:
                    score = 0.99
                    evidence.append(
                        f"PR #{pr_number} explicitly uses a closing keyword for issue #{issue_number}."
                    )
                else:
                    if explicit_link:
                        score += 0.35
                        evidence.append(
                            f"PR #{pr_number} explicitly references issue #{issue_number}."
                        )
                    if issue_mentions_pr:
                        score += 0.3
                        evidence.append(
                            f"Issue #{issue_number} text/comments explicitly mention PR #{pr_number}."
                        )
                    if branch_issue_match:
                        score += 0.35
                        evidence.append(
                            f"PR branch `{pr.get('head_ref', '')}` contains issue number {issue_number}."
                        )
                    if commit_mentions_issue:
                        score += 0.2
                        evidence.append(
                            f"One or more commit messages in PR #{pr_number} mention issue #{issue_number}."
                        )
                    if pr_mentions_issue:
                        score += 0.15
                        evidence.append(
                            f"PR #{pr_number} title/body/comments mention issue #{issue_number}."
                        )
                    if title_similarity >= 0.6:
                        score += 0.35
                        evidence.append(
                            f"Issue and PR titles are highly similar ({title_similarity:.2f})."
                        )
                    elif title_similarity >= 0.35:
                        score += 0.2
                        evidence.append(
                            f"Issue and PR titles have moderate overlap ({title_similarity:.2f})."
                        )
                    elif title_similarity >= 0.2:
                        score += 0.1
                        evidence.append(
                            f"Issue and PR titles have some overlap ({title_similarity:.2f})."
                        )
                    if same_milestone:
                        score += 0.1
                        evidence.append(
                            f"Issue and PR share milestone `{issue.get('milestone_title', '')}`."
                        )
                    if issue_mentions_pr and branch_issue_match:
                        score += 0.2
                        evidence.append(
                            f"Issue #{issue_number} mentions PR #{pr_number} and the PR branch also carries the issue number."
                        )
                    if explicit_link and title_similarity >= 0.2:
                        score += 0.1
                        evidence.append(
                            "The explicit PR reference is reinforced by title overlap."
                        )
                    if branch_issue_match and title_similarity >= 0.2:
                        score += 0.1
                        evidence.append(
                            "Branch naming and title overlap point to the same issue/PR pair."
                        )

                if score < medium_threshold:
                    continue

                confidence_band = "high" if score >= high_threshold else "medium"
                recommendation = "manual_review_recommended"
                if confidence_band == "high":
                    recommendation = (
                        "auto_close_recommended" if explicit_close else "close_recommended"
                    )

                candidates.append(
                    IssuePRRecommendation(
                        issue_number=issue_number,
                        issue_title=str(issue.get("title") or ""),
                        issue_html_url=str(issue.get("html_url") or ""),
                        issue_milestone_title=str(issue.get("milestone_title") or ""),
                        pr_number=pr_number,
                        pr_title=str(pr.get("title") or ""),
                        pr_html_url=str(pr.get("html_url") or ""),
                        confidence=min(score, 0.99),
                        confidence_band=confidence_band,
                        recommendation=recommendation,
                        evidence=evidence,
                        explicit_link=explicit_link,
                        explicit_close=explicit_close,
                        issue_state=str(issue.get("state") or ""),
                        pr_state=str(pr.get("state") or ""),
                        pr_review_decision=str(pr.get("review_decision") or ""),
                        pr_check_status=str(pr.get("check_status") or ""),
                        pr_merged_at=str(pr.get("merged_at") or ""),
                        title_similarity=title_similarity,
                    )
                )

            if not candidates:
                continue

            candidates.sort(
                key=lambda item: (
                    item.confidence,
                    item.explicit_close,
                    item.explicit_link,
                    item.pr_merged_at,
                ),
                reverse=True,
            )
            best = candidates[0]
            matched_issue_numbers.add(issue_number)
            if best.confidence_band == "high":
                high_confidence.append(best)
            else:
                medium_confidence.append(best)

        high_confidence.sort(key=lambda item: (item.recommendation, item.confidence), reverse=True)
        medium_confidence.sort(key=lambda item: item.confidence, reverse=True)

        explicit_auto_close = sum(1 for item in high_confidence if item.recommendation == "auto_close_recommended")
        counts = {
            "open_issues_considered": len(open_issues),
            "merged_prs_considered": len(merged_prs),
            "high_confidence": len(high_confidence),
            "medium_confidence": len(medium_confidence),
            "explicit_auto_close": explicit_auto_close,
        }
        unmatched_open_issues = max(len(open_issues) - len(matched_issue_numbers), 0)
        summary = (
            f"{repo_full_name} has {len(high_confidence)} high-confidence and "
            f"{len(medium_confidence)} medium-confidence open issues that likely map to merged PRs. "
            f"{explicit_auto_close} of the high-confidence matches are explicit auto-close candidates."
        )

        return GitHubIssuePRReport(
            repo_full_name=repo_full_name,
            generated_at=generated_at,
            summary=summary,
            counts=counts,
            high_confidence=high_confidence,
            medium_confidence=medium_confidence,
            unmatched_open_issues=unmatched_open_issues,
        )
