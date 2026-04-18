"""
Explicit readiness and current-state inference over the local GitHub corpus.

This module does not hide its reasoning. It computes inspectable status,
evidence, blockers, and confidence from local SQLite signals that were synced
from GitHub earlier.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest.db import db_connection, ensure_github_schema

_RELEASE_BRANCH_RE = re.compile(r"\brelease/[A-Za-z0-9._-]+\b")


@dataclass
class IssueReadiness:
    issue_number: int
    title: str
    state: str
    classification: str
    linked_pr_numbers: list[int] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class GitHubReadinessResult:
    repo_full_name: str
    milestone_title: str
    milestone_due_on: str
    status: str
    confidence: float
    summary: str
    blockers: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    release_branch: str = ""
    release_branch_exists: bool = False
    promotion_pr: dict[str, Any] = field(default_factory=dict)
    deployment_issue: dict[str, Any] = field(default_factory=dict)
    recent_release: dict[str, Any] = field(default_factory=dict)
    issue_states: list[IssueReadiness] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence"] = round(self.confidence, 2)
        return data


def _parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_until(iso_date: str) -> int | None:
    if not iso_date:
        return None
    try:
        target = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
    except ValueError:
        return None
    now = datetime.now(timezone.utc)
    return (target.date() - now.date()).days


def _select_milestone(conn: Any, repo_full_name: str, milestone_title: str) -> dict[str, Any] | None:
    if milestone_title.strip():
        row = conn.execute(
            """
            SELECT *
            FROM github_milestones
            WHERE repo_full_name = ? AND title = ?
            LIMIT 1
            """,
            (repo_full_name, milestone_title.strip()),
        ).fetchone()
        return dict(row) if row else None

    rows = conn.execute(
        """
        SELECT *
        FROM github_milestones
        WHERE repo_full_name = ? AND state = 'open'
        ORDER BY
            CASE WHEN open_issues > 0 THEN 0 ELSE 1 END,
            CASE WHEN due_on IS NULL THEN 1 ELSE 0 END,
            due_on ASC,
            updated_at DESC
        """,
        (repo_full_name,),
    ).fetchall()
    return dict(rows[0]) if rows else None


def _classify_issue(issue: dict[str, Any], linked_prs: list[dict[str, Any]], default_branch: str) -> IssueReadiness:
    issue_number = int(issue["number"])
    title = issue["title"]
    issue_state = issue["state"]
    linked_numbers = [int(pr["number"]) for pr in linked_prs]
    evidence: list[str] = []

    if issue_state == "closed":
        evidence.append(f"Issue #{issue_number} is closed.")
        return IssueReadiness(issue_number, title, issue_state, "closed", linked_numbers, evidence)

    merged_prs = [
        pr for pr in linked_prs
        if pr.get("is_merged") and pr.get("base_ref") in {default_branch, "main"}
    ]
    if merged_prs:
        pr_numbers = ", ".join(f"#{pr['number']}" for pr in merged_prs)
        evidence.append(f"Issue #{issue_number} is still open, but linked PR {pr_numbers} is already merged.")
        return IssueReadiness(issue_number, title, issue_state, "done_not_closed", linked_numbers, evidence)

    open_prs = [pr for pr in linked_prs if pr.get("state") == "open"]
    if not open_prs:
        evidence.append(f"Issue #{issue_number} has no linked open PR.")
        return IssueReadiness(issue_number, title, issue_state, "open_without_pr", linked_numbers, evidence)

    if any(pr.get("review_decision") == "CHANGES_REQUESTED" for pr in open_prs):
        pr = next(pr for pr in open_prs if pr.get("review_decision") == "CHANGES_REQUESTED")
        evidence.append(f"PR #{pr['number']} linked to issue #{issue_number} has changes requested.")
        return IssueReadiness(issue_number, title, issue_state, "blocked_review_changes", linked_numbers, evidence)

    if any(pr.get("check_status") == "failing" for pr in open_prs):
        pr = next(pr for pr in open_prs if pr.get("check_status") == "failing")
        evidence.append(f"PR #{pr['number']} linked to issue #{issue_number} has failing checks.")
        return IssueReadiness(issue_number, title, issue_state, "blocked_checks", linked_numbers, evidence)

    if any(pr.get("is_draft") for pr in open_prs):
        pr = next(pr for pr in open_prs if pr.get("is_draft"))
        evidence.append(f"PR #{pr['number']} linked to issue #{issue_number} is still a draft.")
        return IssueReadiness(issue_number, title, issue_state, "draft_pr", linked_numbers, evidence)

    if any(pr.get("review_decision") == "APPROVED" and pr.get("check_status") in {"", "success", "mixed"} for pr in open_prs):
        pr = next(pr for pr in open_prs if pr.get("review_decision") == "APPROVED")
        evidence.append(f"PR #{pr['number']} linked to issue #{issue_number} is approved.")
        return IssueReadiness(issue_number, title, issue_state, "approved_ready_to_merge", linked_numbers, evidence)

    if any(pr.get("review_decision") == "REVIEW_REQUIRED" and pr.get("check_status") == "success" for pr in open_prs):
        pr = next(pr for pr in open_prs if pr.get("review_decision") == "REVIEW_REQUIRED" and pr.get("check_status") == "success")
        evidence.append(f"PR #{pr['number']} linked to issue #{issue_number} is green and awaiting review.")
        return IssueReadiness(issue_number, title, issue_state, "awaiting_review", linked_numbers, evidence)

    if any(pr.get("check_status") in {"pending", "mixed"} for pr in open_prs):
        pr = next(pr for pr in open_prs if pr.get("check_status") in {"pending", "mixed"})
        evidence.append(f"PR #{pr['number']} linked to issue #{issue_number} is still waiting on checks.")
        return IssueReadiness(issue_number, title, issue_state, "awaiting_checks", linked_numbers, evidence)

    evidence.append(f"Issue #{issue_number} has an open linked PR but no decisive signal yet.")
    return IssueReadiness(issue_number, title, issue_state, "active_with_pr", linked_numbers, evidence)


def infer_github_release_readiness(
    database_path: Path,
    repo_full_name: str,
    *,
    milestone_title: str = "",
) -> GitHubReadinessResult:
    with db_connection(database_path, ensure_github_schema) as conn:
        repo_meta_row = conn.execute(
            "SELECT * FROM github_repo_meta WHERE repo_full_name = ?",
            (repo_full_name,),
        ).fetchone()
        if not repo_meta_row:
            return GitHubReadinessResult(
                repo_full_name=repo_full_name,
                milestone_title=milestone_title.strip(),
                milestone_due_on="",
                status="no_local_data",
                confidence=0.0,
                summary="No local GitHub data found for this repo. Sync artifacts first.",
                blockers=["Run `rebalance github-sync-artifacts` for this repo."],
            )

        repo_meta = dict(repo_meta_row)
        default_branch = repo_meta.get("default_branch") or "main"
        milestone = _select_milestone(conn, repo_full_name, milestone_title)
        if not milestone:
            return GitHubReadinessResult(
                repo_full_name=repo_full_name,
                milestone_title=milestone_title.strip(),
                milestone_due_on="",
                status="no_active_milestone",
                confidence=0.4,
                summary="No matching open milestone found in the local GitHub store.",
                blockers=["Create or sync an open milestone, or pass an explicit --milestone."],
                evidence=[f"Default branch is {default_branch}."],
            )

        issues = [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM github_items
                WHERE repo_full_name = ? AND item_type = 'issue' AND milestone_title = ?
                ORDER BY state ASC, number ASC
                """,
                (repo_full_name, milestone["title"]),
            ).fetchall()
        ]
        open_issue_count = sum(1 for issue in issues if issue.get("state") == "open")
        closed_issue_count = sum(1 for issue in issues if issue.get("state") == "closed")

        pr_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM github_items
                WHERE repo_full_name = ? AND item_type = 'pull_request'
                """,
                (repo_full_name,),
            ).fetchall()
        ]
        pr_by_number = {int(pr["number"]): pr for pr in pr_rows}

        link_rows = conn.execute(
            """
            SELECT source_number, target_number
            FROM github_links
            WHERE repo_full_name = ?
              AND source_type = 'pull_request'
              AND target_type = 'issue'
            """,
            (repo_full_name,),
        ).fetchall()
        issue_to_prs: dict[int, list[dict[str, Any]]] = {}
        for row in link_rows:
            pr = pr_by_number.get(int(row["source_number"]))
            if not pr:
                continue
            issue_to_prs.setdefault(int(row["target_number"]), []).append(pr)

        issue_states: list[IssueReadiness] = []
        counts = {
            "issues_total": len(issues),
            "issues_open": open_issue_count,
            "issues_closed": closed_issue_count,
            "closed": 0,
            "done_not_closed": 0,
            "open_without_pr": 0,
            "blocked_review_changes": 0,
            "blocked_checks": 0,
            "draft_pr": 0,
            "approved_ready_to_merge": 0,
            "awaiting_review": 0,
            "awaiting_checks": 0,
            "active_with_pr": 0,
        }

        blockers: list[str] = []
        evidence: list[str] = [
            f"Default branch is `{default_branch}`.",
            f"Milestone `{milestone['title']}` has {open_issue_count} open issues and {closed_issue_count} closed issues in the local store.",
        ]

        for issue in issues:
            readiness = _classify_issue(issue, issue_to_prs.get(int(issue["number"]), []), default_branch)
            issue_states.append(readiness)
            counts[readiness.classification] = counts.get(readiness.classification, 0) + 1
            evidence.extend(readiness.evidence)

        if counts["blocked_review_changes"] > 0:
            blockers.append(f"{counts['blocked_review_changes']} milestone issue(s) have PRs with changes requested.")
        if counts["blocked_checks"] > 0:
            blockers.append(f"{counts['blocked_checks']} milestone issue(s) have failing checks.")
        if counts["open_without_pr"] > 0:
            blockers.append(f"{counts['open_without_pr']} open milestone issue(s) have no linked PR.")

        branches = [
            dict(row)
            for row in conn.execute(
                """
                SELECT name, is_default
                FROM github_branches
                WHERE repo_full_name = ?
                ORDER BY name ASC
                """,
                (repo_full_name,),
            ).fetchall()
        ]
        release_branches = [branch["name"] for branch in branches if str(branch["name"]).startswith("release/")]

        promotion_pr_row = conn.execute(
            """
            SELECT *
            FROM github_items
            WHERE repo_full_name = ?
              AND item_type = 'pull_request'
              AND state = 'open'
              AND base_ref = 'main'
              AND (head_ref = ? OR head_ref LIKE 'release/%')
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (repo_full_name, default_branch),
        ).fetchone()
        promotion_pr = dict(promotion_pr_row) if promotion_pr_row else {}

        deployment_issue_row = conn.execute(
            """
            SELECT *
            FROM github_items
            WHERE repo_full_name = ?
              AND item_type = 'issue'
              AND state = 'open'
              AND LOWER(title) LIKE ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (repo_full_name, f"%deployment:%{milestone['title'].lower()}%"),
        ).fetchone()
        deployment_issue = dict(deployment_issue_row) if deployment_issue_row else {}

        expected_release_branch = ""
        release_branch_exists = False
        if deployment_issue.get("body"):
            matches = _RELEASE_BRANCH_RE.findall(deployment_issue["body"])
            if matches:
                expected_release_branch = matches[0]
                release_branch_exists = expected_release_branch in release_branches
                if release_branch_exists:
                    evidence.append(f"Deployment issue references release branch `{expected_release_branch}`, which exists locally.")
                else:
                    blockers.append(f"Deployment issue expects release branch `{expected_release_branch}`, but that branch is missing.")
            evidence.append(f"Found deployment issue #{deployment_issue['number']} for milestone `{milestone['title']}`.")

        if release_branches:
            evidence.append(f"Known release branches: {', '.join(release_branches[:5])}.")

        recent_release_row = conn.execute(
            """
            SELECT tag_name, published_at, target_commitish
            FROM github_releases
            WHERE repo_full_name = ?
            ORDER BY COALESCE(published_at, created_at) DESC
            LIMIT 1
            """,
            (repo_full_name,),
        ).fetchone()
        recent_release = dict(recent_release_row) if recent_release_row else {}
        if recent_release:
            evidence.append(
                f"Most recent release is `{recent_release.get('tag_name', '')}` targeting `{recent_release.get('target_commitish', '')}`."
            )

        if promotion_pr:
            evidence.append(
                f"Open promotion PR #{promotion_pr['number']} targets `main` from `{promotion_pr.get('head_ref', '')}` "
                f"with review={promotion_pr.get('review_decision', '')} checks={promotion_pr.get('check_status', '')}."
            )

        due_in_days = _days_until(milestone.get("due_on") or "")
        if due_in_days is not None:
            evidence.append(f"Milestone `{milestone['title']}` is due in {due_in_days} day(s).")

        unresolved_count = (
            counts["open_without_pr"]
            + counts["blocked_review_changes"]
            + counts["blocked_checks"]
            + counts["draft_pr"]
            + counts["awaiting_review"]
            + counts["awaiting_checks"]
            + counts["active_with_pr"]
        )

        if counts["issues_total"] == 0:
            status = "planning"
            summary = f"{repo_full_name} has milestone `{milestone['title']}`, but no milestone issues are synced yet."
        elif promotion_pr and unresolved_count == 0 and promotion_pr.get("review_decision") == "APPROVED" and promotion_pr.get("check_status") == "success":
            status = "deploy_ready"
            summary = f"{repo_full_name} milestone `{milestone['title']}` looks deploy-ready: milestone work is resolved and the promotion PR to `main` is approved with green checks."
        elif unresolved_count == 0 and not promotion_pr:
            status = "release_candidate"
            summary = f"{repo_full_name} milestone `{milestone['title']}` looks release-candidate ready: milestone work is resolved, but there is no open promotion PR to `main` yet."
        elif blockers:
            status = "release_blocked" if deployment_issue or (due_in_days is not None and due_in_days <= 7) else "blocked"
            summary = f"{repo_full_name} milestone `{milestone['title']}` is blocked by explicit review/check/branch issues."
        elif counts["approved_ready_to_merge"] > 0 and unresolved_count == counts["approved_ready_to_merge"]:
            status = "merge_queue"
            summary = f"{repo_full_name} milestone `{milestone['title']}` is in merge queue: remaining open issues all have approved PRs."
        elif counts["awaiting_review"] > 0:
            status = "review_queue"
            summary = f"{repo_full_name} milestone `{milestone['title']}` is in review queue: green PRs are waiting on approval."
        else:
            status = "active_development"
            summary = f"{repo_full_name} milestone `{milestone['title']}` is still in active development."

        confidence = 0.35
        confidence += 0.15 if repo_meta.get("default_branch") else 0.0
        confidence += 0.15 if milestone else 0.0
        confidence += 0.15 if branches else 0.0
        confidence += 0.1 if counts["issues_total"] > 0 else 0.0
        confidence += 0.1 if any(issue.linked_pr_numbers for issue in issue_states) else 0.0
        confidence += 0.05 if deployment_issue else 0.0
        confidence += 0.05 if recent_release else 0.0
        confidence = min(confidence, 0.95)

        return GitHubReadinessResult(
            repo_full_name=repo_full_name,
            milestone_title=milestone["title"],
            milestone_due_on=milestone.get("due_on") or "",
            status=status,
            confidence=confidence,
            summary=summary,
            blockers=blockers,
            evidence=evidence,
            counts=counts,
            release_branch=expected_release_branch,
            release_branch_exists=release_branch_exists,
            promotion_pr={
                "number": promotion_pr.get("number"),
                "title": promotion_pr.get("title", ""),
                "head_ref": promotion_pr.get("head_ref", ""),
                "review_decision": promotion_pr.get("review_decision", ""),
                "check_status": promotion_pr.get("check_status", ""),
            } if promotion_pr else {},
            deployment_issue={
                "number": deployment_issue.get("number"),
                "title": deployment_issue.get("title", ""),
            } if deployment_issue else {},
            recent_release=recent_release,
            issue_states=issue_states,
        )
