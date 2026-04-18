"""
GitHub artifact sync, local document corpus construction, and semantic query.

This is the Phase 1 local-first GitHub knowledge layer:
- sync structured artifacts into SQLite
- build a local GitHub document corpus from issues, PRs, comments, reviews, and commits
- embed that corpus with the same local embedding runtime used for vault notes
- query it semantically without re-scanning GitHub live at answer time
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
import re

from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.ingest.embedder import (
    DEFAULT_MODEL as DEFAULT_EMBED_MODEL,
    EMBEDDING_DIM,
    _embed_batch,
    _load_model,
    _vec_to_bytes,
)

GITHUB_API = "https://api.github.com"
DEFAULT_SYNC_DAYS = 90
MIN_EMBED_CHARS = 40
_CLOSES_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.IGNORECASE)
_ISSUE_REF_RE = re.compile(r"(?<![/\w])#(\d+)\b")

JsonFetcher = Callable[[str], Any]
EmbedTexts = Callable[[list[str], str], list[list[float]]]


@dataclass
class GitHubKnowledgeSyncResult:
    repo_full_name: str
    branches_synced: int
    issues_synced: int
    prs_synced: int
    comments_synced: int
    commits_synced: int
    checks_synced: int
    docs_built: int
    milestones_synced: int
    labels_synced: int
    releases_synced: int
    elapsed_seconds: float


@dataclass
class GitHubEmbedResult:
    total_docs: int
    embedded_docs: int
    skipped_unchanged: int
    model_name: str
    embedding_dim: int
    elapsed_seconds: float


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "rebalance-os/phase1",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _http_get_json(url: str, token: str) -> Any:
    req = urllib.request.Request(url, headers=_github_headers(token))
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        raise RuntimeError(f"GitHub API request failed: {exc.code} {url} {body}") from exc


def _build_url(base_url: str, **params: Any) -> str:
    cleaned = {key: value for key, value in params.items() if value not in ("", None)}
    if not cleaned:
        return base_url
    return f"{base_url}?{urlencode(cleaned, doseq=True)}"


def _paginate_list(
    base_url: str,
    api_get: JsonFetcher,
    *,
    stop_updated_before: str = "",
    **params: Any,
) -> list[dict[str, Any]]:
    page = 1
    results: list[dict[str, Any]] = []
    while True:
        data = api_get(_build_url(base_url, per_page=100, page=page, **params))
        if not isinstance(data, list) or not data:
            break

        stop = False
        for row in data:
            updated_at = str(row.get("updated_at") or "")
            if stop_updated_before and updated_at and updated_at < stop_updated_before:
                stop = True
                break
            results.append(row)

        if stop or len(data) < 100:
            break
        page += 1
    return results


def _cutoff_iso(since_days: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _review_decision(reviews: list[dict[str, Any]]) -> str:
    meaningful = [
        (review.get("submitted_at") or "", review.get("state") or "")
        for review in reviews
        if (review.get("state") or "") in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
    ]
    if not meaningful:
        return "REVIEW_REQUIRED"
    meaningful.sort(key=lambda item: item[0])
    last_state = meaningful[-1][1]
    return "REVIEW_REQUIRED" if last_state == "DISMISSED" else last_state


def _check_rollup(check_runs: list[dict[str, Any]]) -> str:
    if not check_runs:
        return ""
    if any((run.get("status") or "") != "completed" for run in check_runs):
        return "pending"
    conclusions = [(run.get("conclusion") or "").lower() for run in check_runs]
    if any(
        conclusion in {"failure", "timed_out", "cancelled", "startup_failure", "action_required", "stale"}
        for conclusion in conclusions
    ):
        return "failing"
    if all(conclusion in {"success", "neutral", "skipped"} for conclusion in conclusions):
        return "success"
    return "mixed"


def _parse_links(text: str) -> list[tuple[str, int]]:
    if not text:
        return []
    closing = {(kind, int(num)) for num in _CLOSES_RE.findall(text) for kind in ["closes"]}
    mentions = {
        ("mentions", int(num))
        for num in _ISSUE_REF_RE.findall(text)
        if ("closes", int(num)) not in closing
    }
    return sorted(closing | mentions, key=lambda item: (item[0], item[1]))


def _item_doc_text(item: dict[str, Any]) -> str:
    lines = [f"{item['item_type']} #{item['number']}: {item['title']}"]
    if item.get("milestone_title"):
        lines.append(f"Milestone: {item['milestone_title']}")
    labels = json.loads(item.get("labels_json") or "[]")
    if labels:
        lines.append(f"Labels: {', '.join(labels)}")
    if item.get("state"):
        lines.append(f"State: {item['state']}")
    if item.get("review_decision"):
        lines.append(f"Review: {item['review_decision']}")
    if item.get("check_status"):
        lines.append(f"Checks: {item['check_status']}")
    if item.get("body"):
        lines.extend(["", item["body"]])
    return "\n".join(lines).strip()


def _comment_doc_text(item_type: str, item_number: int, comment_type: str, body: str, *, review_state: str = "") -> str:
    prefix = f"{comment_type.replace('_', ' ')} on {item_type} #{item_number}"
    if review_state:
        prefix += f" ({review_state})"
    return f"{prefix}\n\n{body}".strip()


def _commit_doc_text(item_type: str, item_number: int, sha: str, message: str) -> str:
    first_line = (message or "").splitlines()[0].strip()
    return f"Commit {sha[:7]} on {item_type} #{item_number}\n\n{first_line}".strip()


def _delete_item_children(conn: Any, repo_full_name: str, item_type: str, item_number: int) -> None:
    doc_ids = [
        row["id"]
        for row in conn.execute(
            """
            SELECT id
            FROM github_documents
            WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
            """,
            (repo_full_name, item_type, item_number),
        ).fetchall()
    ]
    if doc_ids:
        conn.executemany("DELETE FROM github_embeddings WHERE doc_id = ?", [(doc_id,) for doc_id in doc_ids])
    conn.execute(
        """
        DELETE FROM github_documents
        WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
        """,
        (repo_full_name, item_type, item_number),
    )
    conn.execute(
        """
        DELETE FROM github_comments
        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
        """,
        (repo_full_name, item_type, item_number),
    )
    conn.execute(
        """
        DELETE FROM github_commits
        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
        """,
        (repo_full_name, item_type, item_number),
    )
    conn.execute(
        """
        DELETE FROM github_check_runs
        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
        """,
        (repo_full_name, item_type, item_number),
    )
    conn.execute(
        """
        DELETE FROM github_links
        WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
        """,
        (repo_full_name, item_type, item_number),
    )


def _insert_document(
    conn: Any,
    *,
    repo_full_name: str,
    source_type: str,
    source_number: int,
    doc_type: str,
    source_key: str,
    title: str,
    body: str,
    updated_at: str,
    fetched_at: str,
) -> int:
    conn.execute(
        """
        INSERT INTO github_documents
            (repo_full_name, source_type, source_number, doc_type, source_key,
             title, body, content_hash, embedded_hash, updated_at, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (
            repo_full_name,
            source_type,
            source_number,
            doc_type,
            source_key,
            title,
            body,
            _content_hash(body),
            updated_at,
            fetched_at,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def sync_github_repo(
    database_path: Path,
    repo_full_name: str,
    token: str,
    *,
    since_days: int = DEFAULT_SYNC_DAYS,
    api_get_json: JsonFetcher | None = None,
) -> GitHubKnowledgeSyncResult:
    start = time.monotonic()
    fetched_at = datetime.now(timezone.utc).isoformat()
    cutoff = _cutoff_iso(since_days)
    api_get = api_get_json or (lambda url: _http_get_json(url, token))
    repo_base = f"{GITHUB_API}/repos/{repo_full_name}"
    repo_meta = api_get(repo_base)

    branches = _paginate_list(f"{repo_base}/branches", api_get)
    labels = _paginate_list(f"{repo_base}/labels", api_get)
    milestones = _paginate_list(f"{repo_base}/milestones", api_get, state="all", sort="due_on", direction="asc")
    releases = _paginate_list(f"{repo_base}/releases", api_get)
    issues = [
        row
        for row in _paginate_list(
            f"{repo_base}/issues",
            api_get,
            state="all",
            sort="updated",
            direction="desc",
            since=cutoff,
        )
        if "pull_request" not in row
    ]
    pull_summaries = _paginate_list(
        f"{repo_base}/pulls",
        api_get,
        stop_updated_before=cutoff,
        state="all",
        sort="updated",
        direction="desc",
    )

    comments_synced = 0
    commits_synced = 0
    checks_synced = 0
    docs_built = 0

    with db_connection(database_path, ensure_github_schema) as conn:
        conn.execute("DELETE FROM github_branches WHERE repo_full_name = ?", (repo_full_name,))
        conn.execute("DELETE FROM github_labels WHERE repo_full_name = ?", (repo_full_name,))
        conn.execute("DELETE FROM github_milestones WHERE repo_full_name = ?", (repo_full_name,))
        conn.execute("DELETE FROM github_releases WHERE repo_full_name = ?", (repo_full_name,))

        conn.execute(
            """
            INSERT OR REPLACE INTO github_repo_meta
                (repo_full_name, default_branch, pushed_at, updated_at, open_issues_count,
                 has_issues, has_projects, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo_full_name,
                repo_meta.get("default_branch", "") if isinstance(repo_meta, dict) else "",
                repo_meta.get("pushed_at") if isinstance(repo_meta, dict) else None,
                repo_meta.get("updated_at") if isinstance(repo_meta, dict) else None,
                repo_meta.get("open_issues_count") or 0 if isinstance(repo_meta, dict) else 0,
                1 if isinstance(repo_meta, dict) and repo_meta.get("has_issues") else 0,
                1 if isinstance(repo_meta, dict) and repo_meta.get("has_projects") else 0,
                fetched_at,
            ),
        )

        default_branch = repo_meta.get("default_branch", "") if isinstance(repo_meta, dict) else ""
        for branch in branches:
            conn.execute(
                """
                INSERT OR REPLACE INTO github_branches
                    (repo_full_name, name, head_sha, is_protected, is_default, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_full_name,
                    branch.get("name", ""),
                    ((branch.get("commit") or {}).get("sha") or ""),
                    1 if branch.get("protected") else 0,
                    1 if branch.get("name", "") == default_branch else 0,
                    fetched_at,
                ),
            )

        for label in labels:
            conn.execute(
                """
                INSERT OR REPLACE INTO github_labels
                    (repo_full_name, name, color, description, is_default)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    repo_full_name,
                    label.get("name", ""),
                    label.get("color", ""),
                    label.get("description", ""),
                    1 if label.get("default") else 0,
                ),
            )

        for milestone in milestones:
            conn.execute(
                """
                INSERT OR REPLACE INTO github_milestones
                    (repo_full_name, number, title, description, state, open_issues,
                     closed_issues, due_on, created_at, updated_at, closed_at, html_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_full_name,
                    milestone.get("number"),
                    milestone.get("title", ""),
                    milestone.get("description", ""),
                    milestone.get("state", ""),
                    milestone.get("open_issues") or 0,
                    milestone.get("closed_issues") or 0,
                    milestone.get("due_on"),
                    milestone.get("created_at"),
                    milestone.get("updated_at"),
                    milestone.get("closed_at"),
                    milestone.get("html_url", ""),
                ),
            )

        for release in releases:
            conn.execute(
                """
                INSERT OR REPLACE INTO github_releases
                    (repo_full_name, github_id, tag_name, name, target_commitish, is_draft,
                     is_prerelease, body, created_at, published_at, html_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_full_name,
                    release.get("id"),
                    release.get("tag_name", ""),
                    release.get("name", ""),
                    release.get("target_commitish", ""),
                    1 if release.get("draft") else 0,
                    1 if release.get("prerelease") else 0,
                    release.get("body", "") or "",
                    release.get("created_at"),
                    release.get("published_at"),
                    release.get("html_url", ""),
                ),
            )

        for issue in issues:
            item_type = "issue"
            item_number = int(issue["number"])
            milestone = issue.get("milestone") or {}
            _delete_item_children(conn, repo_full_name, item_type, item_number)

            item_record = {
                "repo_full_name": repo_full_name,
                "item_type": item_type,
                "number": item_number,
                "node_id": issue.get("node_id", ""),
                "github_id": issue.get("id"),
                "title": issue.get("title", ""),
                "body": issue.get("body", "") or "",
                "state": issue.get("state", ""),
                "state_reason": issue.get("state_reason", ""),
                "author_login": (issue.get("user") or {}).get("login", ""),
                "assignees_json": _json_dumps([a.get("login", "") for a in issue.get("assignees") or []]),
                "labels_json": _json_dumps([l.get("name", "") for l in issue.get("labels") or []]),
                "milestone_number": milestone.get("number"),
                "milestone_title": milestone.get("title", ""),
                "is_draft": 0,
                "is_merged": 0,
                "base_ref": "",
                "head_ref": "",
                "head_sha": "",
                "mergeable_state": "",
                "review_decision": "",
                "check_status": "",
                "requested_reviewers_json": "[]",
                "comments_count": issue.get("comments") or 0,
                "review_comments_count": 0,
                "commits_count": 0,
                "additions": 0,
                "deletions": 0,
                "changed_files": 0,
                "html_url": issue.get("html_url", ""),
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
                "closed_at": issue.get("closed_at"),
                "merged_at": None,
                "fetched_at": fetched_at,
            }

            conn.execute(
                """
                INSERT OR REPLACE INTO github_items
                    (repo_full_name, item_type, number, node_id, github_id, title, body, state,
                     state_reason, author_login, assignees_json, labels_json, milestone_number,
                     milestone_title, is_draft, is_merged, base_ref, head_ref, head_sha,
                     mergeable_state, review_decision, check_status, requested_reviewers_json,
                     comments_count, review_comments_count, commits_count, additions, deletions,
                     changed_files, html_url, created_at, updated_at, closed_at, merged_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(item_record.values()),
            )

            issue_comments = _paginate_list(f"{repo_base}/issues/{item_number}/comments", api_get)
            for comment in issue_comments:
                body = comment.get("body", "") or ""
                conn.execute(
                    """
                    INSERT OR REPLACE INTO github_comments
                        (repo_full_name, item_type, item_number, comment_type, github_comment_id,
                         author_login, author_association, body, review_state, in_reply_to_id,
                         html_url, created_at, updated_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repo_full_name,
                        item_type,
                        item_number,
                        "issue_comment",
                        comment.get("id"),
                        (comment.get("user") or {}).get("login", ""),
                        comment.get("author_association", ""),
                        body,
                        "",
                        None,
                        comment.get("html_url", ""),
                        comment.get("created_at"),
                        comment.get("updated_at"),
                        fetched_at,
                    ),
                )
                comments_synced += 1
                if body.strip():
                    _insert_document(
                        conn,
                        repo_full_name=repo_full_name,
                        source_type=item_type,
                        source_number=item_number,
                        doc_type="issue_comment",
                        source_key=f"{repo_full_name}:{item_type}:{item_number}:issue_comment:{comment.get('id')}",
                        title=item_record["title"],
                        body=_comment_doc_text(item_type, item_number, "issue_comment", body),
                        updated_at=comment.get("updated_at") or fetched_at,
                        fetched_at=fetched_at,
                    )
                    docs_built += 1

            if item_record["body"].strip():
                _insert_document(
                    conn,
                    repo_full_name=repo_full_name,
                    source_type=item_type,
                    source_number=item_number,
                    doc_type="item_body",
                    source_key=f"{repo_full_name}:{item_type}:{item_number}:item",
                    title=item_record["title"],
                    body=_item_doc_text(item_record),
                    updated_at=item_record["updated_at"] or fetched_at,
                    fetched_at=fetched_at,
                )
                docs_built += 1

        for pull_summary in pull_summaries:
            item_type = "pull_request"
            item_number = int(pull_summary["number"])
            pr = api_get(f"{repo_base}/pulls/{item_number}")
            if not isinstance(pr, dict):
                continue

            issue_comments = _paginate_list(f"{repo_base}/issues/{item_number}/comments", api_get)
            reviews = _paginate_list(f"{repo_base}/pulls/{item_number}/reviews", api_get)
            review_comments = _paginate_list(f"{repo_base}/pulls/{item_number}/comments", api_get)
            commits = _paginate_list(f"{repo_base}/pulls/{item_number}/commits", api_get)
            check_runs_resp = api_get(_build_url(f"{repo_base}/commits/{pr.get('head', {}).get('sha', '')}/check-runs", per_page=100))
            check_runs = (
                check_runs_resp.get("check_runs", [])
                if isinstance(check_runs_resp, dict)
                else []
            )
            milestone = pr.get("milestone") or {}
            _delete_item_children(conn, repo_full_name, item_type, item_number)

            item_record = {
                "repo_full_name": repo_full_name,
                "item_type": item_type,
                "number": item_number,
                "node_id": pr.get("node_id", ""),
                "github_id": pr.get("id"),
                "title": pr.get("title", ""),
                "body": pr.get("body", "") or "",
                "state": pr.get("state", ""),
                "state_reason": "",
                "author_login": (pr.get("user") or {}).get("login", ""),
                "assignees_json": _json_dumps([a.get("login", "") for a in pr.get("assignees") or []]),
                "labels_json": _json_dumps([l.get("name", "") for l in pr.get("labels") or []]),
                "milestone_number": milestone.get("number"),
                "milestone_title": milestone.get("title", ""),
                "is_draft": 1 if pr.get("draft") else 0,
                "is_merged": 1 if pr.get("merged_at") else 0,
                "base_ref": (pr.get("base") or {}).get("ref", ""),
                "head_ref": (pr.get("head") or {}).get("ref", ""),
                "head_sha": (pr.get("head") or {}).get("sha", ""),
                "mergeable_state": pr.get("mergeable_state", ""),
                "review_decision": _review_decision(reviews),
                "check_status": _check_rollup(check_runs),
                "requested_reviewers_json": _json_dumps([r.get("login", "") for r in pr.get("requested_reviewers") or []]),
                "comments_count": pr.get("comments") or 0,
                "review_comments_count": pr.get("review_comments") or 0,
                "commits_count": pr.get("commits") or 0,
                "additions": pr.get("additions") or 0,
                "deletions": pr.get("deletions") or 0,
                "changed_files": pr.get("changed_files") or 0,
                "html_url": pr.get("html_url", ""),
                "created_at": pr.get("created_at"),
                "updated_at": pr.get("updated_at"),
                "closed_at": pr.get("closed_at"),
                "merged_at": pr.get("merged_at"),
                "fetched_at": fetched_at,
            }

            conn.execute(
                """
                INSERT OR REPLACE INTO github_items
                    (repo_full_name, item_type, number, node_id, github_id, title, body, state,
                     state_reason, author_login, assignees_json, labels_json, milestone_number,
                     milestone_title, is_draft, is_merged, base_ref, head_ref, head_sha,
                     mergeable_state, review_decision, check_status, requested_reviewers_json,
                     comments_count, review_comments_count, commits_count, additions, deletions,
                     changed_files, html_url, created_at, updated_at, closed_at, merged_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(item_record.values()),
            )

            combined_text = "\n".join(filter(None, [item_record["title"], item_record["body"]]))
            for link_kind, issue_number in _parse_links(combined_text):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO github_links
                        (repo_full_name, source_type, source_number, target_type, target_number, link_kind)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (repo_full_name, item_type, item_number, "issue", issue_number, link_kind),
                )

            for comment in issue_comments:
                body = comment.get("body", "") or ""
                conn.execute(
                    """
                    INSERT OR REPLACE INTO github_comments
                        (repo_full_name, item_type, item_number, comment_type, github_comment_id,
                         author_login, author_association, body, review_state, in_reply_to_id,
                         html_url, created_at, updated_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repo_full_name,
                        item_type,
                        item_number,
                        "issue_comment",
                        comment.get("id"),
                        (comment.get("user") or {}).get("login", ""),
                        comment.get("author_association", ""),
                        body,
                        "",
                        None,
                        comment.get("html_url", ""),
                        comment.get("created_at"),
                        comment.get("updated_at"),
                        fetched_at,
                    ),
                )
                comments_synced += 1
                if body.strip():
                    _insert_document(
                        conn,
                        repo_full_name=repo_full_name,
                        source_type=item_type,
                        source_number=item_number,
                        doc_type="issue_comment",
                        source_key=f"{repo_full_name}:{item_type}:{item_number}:issue_comment:{comment.get('id')}",
                        title=item_record["title"],
                        body=_comment_doc_text(item_type, item_number, "issue_comment", body),
                        updated_at=comment.get("updated_at") or fetched_at,
                        fetched_at=fetched_at,
                    )
                    docs_built += 1

            for review in reviews:
                body = review.get("body", "") or ""
                conn.execute(
                    """
                    INSERT OR REPLACE INTO github_comments
                        (repo_full_name, item_type, item_number, comment_type, github_comment_id,
                         author_login, author_association, body, review_state, in_reply_to_id,
                         html_url, created_at, updated_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repo_full_name,
                        item_type,
                        item_number,
                        "review",
                        review.get("id"),
                        (review.get("user") or {}).get("login", ""),
                        review.get("author_association", ""),
                        body,
                        review.get("state", ""),
                        None,
                        review.get("html_url", ""),
                        review.get("submitted_at"),
                        review.get("submitted_at"),
                        fetched_at,
                    ),
                )
                comments_synced += 1
                if body.strip():
                    _insert_document(
                        conn,
                        repo_full_name=repo_full_name,
                        source_type=item_type,
                        source_number=item_number,
                        doc_type="review",
                        source_key=f"{repo_full_name}:{item_type}:{item_number}:review:{review.get('id')}",
                        title=item_record["title"],
                        body=_comment_doc_text(
                            item_type,
                            item_number,
                            "review",
                            body,
                            review_state=review.get("state", ""),
                        ),
                        updated_at=review.get("submitted_at") or fetched_at,
                        fetched_at=fetched_at,
                    )
                    docs_built += 1

            for comment in review_comments:
                body = comment.get("body", "") or ""
                conn.execute(
                    """
                    INSERT OR REPLACE INTO github_comments
                        (repo_full_name, item_type, item_number, comment_type, github_comment_id,
                         author_login, author_association, body, review_state, in_reply_to_id,
                         html_url, created_at, updated_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repo_full_name,
                        item_type,
                        item_number,
                        "review_comment",
                        comment.get("id"),
                        (comment.get("user") or {}).get("login", ""),
                        comment.get("author_association", ""),
                        body,
                        "",
                        comment.get("in_reply_to_id"),
                        comment.get("html_url", ""),
                        comment.get("created_at"),
                        comment.get("updated_at"),
                        fetched_at,
                    ),
                )
                comments_synced += 1
                if body.strip():
                    _insert_document(
                        conn,
                        repo_full_name=repo_full_name,
                        source_type=item_type,
                        source_number=item_number,
                        doc_type="review_comment",
                        source_key=f"{repo_full_name}:{item_type}:{item_number}:review_comment:{comment.get('id')}",
                        title=item_record["title"],
                        body=_comment_doc_text(item_type, item_number, "review_comment", body),
                        updated_at=comment.get("updated_at") or fetched_at,
                        fetched_at=fetched_at,
                    )
                    docs_built += 1

            for commit in commits:
                sha = commit.get("sha", "")
                message = ((commit.get("commit") or {}).get("message") or "").strip()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO github_commits
                        (repo_full_name, item_type, item_number, sha, author_login,
                         message, committed_at, html_url, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repo_full_name,
                        item_type,
                        item_number,
                        sha,
                        ((commit.get("author") or {}).get("login") or ""),
                        message,
                        ((commit.get("commit") or {}).get("author") or {}).get("date"),
                        commit.get("html_url", ""),
                        fetched_at,
                    ),
                )
                commits_synced += 1
                if message:
                    _insert_document(
                        conn,
                        repo_full_name=repo_full_name,
                        source_type=item_type,
                        source_number=item_number,
                        doc_type="commit_message",
                        source_key=f"{repo_full_name}:{item_type}:{item_number}:commit:{sha}",
                        title=item_record["title"],
                        body=_commit_doc_text(item_type, item_number, sha, message),
                        updated_at=((commit.get("commit") or {}).get("author") or {}).get("date") or fetched_at,
                        fetched_at=fetched_at,
                    )
                    docs_built += 1

            for run in check_runs:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO github_check_runs
                        (repo_full_name, item_type, item_number, head_sha, name, status,
                         conclusion, details_url, started_at, completed_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repo_full_name,
                        item_type,
                        item_number,
                        item_record["head_sha"],
                        run.get("name", ""),
                        run.get("status", ""),
                        run.get("conclusion", ""),
                        run.get("details_url", "") or run.get("html_url", ""),
                        run.get("started_at"),
                        run.get("completed_at"),
                        fetched_at,
                    ),
                )
                checks_synced += 1

            if item_record["body"].strip():
                _insert_document(
                    conn,
                    repo_full_name=repo_full_name,
                    source_type=item_type,
                    source_number=item_number,
                    doc_type="item_body",
                    source_key=f"{repo_full_name}:{item_type}:{item_number}:item",
                    title=item_record["title"],
                    body=_item_doc_text(item_record),
                    updated_at=item_record["updated_at"] or fetched_at,
                    fetched_at=fetched_at,
                )
                docs_built += 1

        conn.commit()

    elapsed = round(time.monotonic() - start, 2)
    return GitHubKnowledgeSyncResult(
        repo_full_name=repo_full_name,
        branches_synced=len(branches),
        issues_synced=len(issues),
        prs_synced=len(pull_summaries),
        comments_synced=comments_synced,
        commits_synced=commits_synced,
        checks_synced=checks_synced,
        docs_built=docs_built,
        milestones_synced=len(milestones),
        labels_synced=len(labels),
        releases_synced=len(releases),
        elapsed_seconds=elapsed,
    )


def _default_embed_texts(texts: list[str], model_name: str) -> list[list[float]]:
    model, tokenizer = _load_model(model_name)
    return _embed_batch(model, tokenizer, texts)


def embed_github_documents(
    database_path: Path,
    *,
    model_name: str = DEFAULT_EMBED_MODEL,
    batch_size: int = 32,
    min_chars: int = MIN_EMBED_CHARS,
    force_reembed: bool = False,
    embed_texts: EmbedTexts | None = None,
) -> GitHubEmbedResult:
    start = time.monotonic()
    embed_fn = embed_texts or _default_embed_texts

    with db_connection(database_path, ensure_github_schema) as conn:
        if force_reembed:
            conn.execute("DELETE FROM github_embeddings")
            conn.execute("UPDATE github_documents SET embedded_hash = NULL")
            conn.commit()

        rows = conn.execute(
            """
            SELECT id, body, content_hash
            FROM github_documents
            WHERE LENGTH(body) >= ?
              AND (embedded_hash IS NULL OR embedded_hash != content_hash)
            ORDER BY id
            """,
            (min_chars,),
        ).fetchall()
        total_docs = conn.execute(
            "SELECT COUNT(*) FROM github_documents WHERE LENGTH(body) >= ?",
            (min_chars,),
        ).fetchone()[0]

        if not rows:
            return GitHubEmbedResult(
                total_docs=total_docs,
                embedded_docs=0,
                skipped_unchanged=total_docs,
                model_name=model_name,
                embedding_dim=EMBEDDING_DIM,
                elapsed_seconds=round(time.monotonic() - start, 2),
            )

        embedded = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            texts = [row["body"][:4000] for row in batch]
            vectors = embed_fn(texts, model_name)
            for row, vec in zip(batch, vectors):
                conn.execute(
                    "INSERT OR REPLACE INTO github_embeddings (doc_id, embedding) VALUES (?, ?)",
                    (row["id"], _vec_to_bytes(vec)),
                )
                conn.execute(
                    "UPDATE github_documents SET embedded_hash = content_hash WHERE id = ?",
                    (row["id"],),
                )
                embedded += 1
            conn.commit()

        now_iso = datetime.now(timezone.utc).isoformat()
        for key, value in [
            ("model_name", model_name),
            ("embedding_dim", str(EMBEDDING_DIM)),
            ("last_embed_at", now_iso),
        ]:
            conn.execute(
                "INSERT OR REPLACE INTO github_embedding_meta (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()

    return GitHubEmbedResult(
        total_docs=total_docs,
        embedded_docs=embedded,
        skipped_unchanged=total_docs - embedded,
        model_name=model_name,
        embedding_dim=EMBEDDING_DIM,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


def query_github_documents(
    database_path: Path,
    query_text: str,
    *,
    repo_full_name: str = "",
    top_k: int = 8,
    model_name: str = DEFAULT_EMBED_MODEL,
    embed_texts: EmbedTexts | None = None,
) -> list[dict[str, Any]]:
    embed_fn = embed_texts or _default_embed_texts
    query_vec = _vec_to_bytes(embed_fn([query_text], model_name)[0])

    with db_connection(database_path, ensure_github_schema) as conn:
        if repo_full_name.strip():
            rows = conn.execute(
                """
                SELECT
                    ge.doc_id,
                    ge.distance,
                    gd.repo_full_name,
                    gd.source_type,
                    gd.source_number,
                    gd.doc_type,
                    gd.title,
                    SUBSTR(gd.body, 1, 400) AS body_preview,
                    gi.state,
                    gi.milestone_title,
                    gi.labels_json,
                    gi.review_decision,
                    gi.check_status,
                    gi.html_url
                FROM github_embeddings ge
                JOIN github_documents gd ON gd.id = ge.doc_id
                LEFT JOIN github_items gi
                  ON gi.repo_full_name = gd.repo_full_name
                 AND gi.item_type = gd.source_type
                 AND gi.number = gd.source_number
                WHERE ge.embedding MATCH ? AND ge.k = ? AND gd.repo_full_name = ?
                ORDER BY ge.distance
                """,
                (query_vec, top_k, repo_full_name.strip()),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    ge.doc_id,
                    ge.distance,
                    gd.repo_full_name,
                    gd.source_type,
                    gd.source_number,
                    gd.doc_type,
                    gd.title,
                    SUBSTR(gd.body, 1, 400) AS body_preview,
                    gi.state,
                    gi.milestone_title,
                    gi.labels_json,
                    gi.review_decision,
                    gi.check_status,
                    gi.html_url
                FROM github_embeddings ge
                JOIN github_documents gd ON gd.id = ge.doc_id
                LEFT JOIN github_items gi
                  ON gi.repo_full_name = gd.repo_full_name
                 AND gi.item_type = gd.source_type
                 AND gi.number = gd.source_number
                WHERE ge.embedding MATCH ? AND ge.k = ?
                ORDER BY ge.distance
                """,
                (query_vec, top_k),
            ).fetchall()

    return [
        {
            "doc_id": row["doc_id"],
            "repo_full_name": row["repo_full_name"],
            "source_type": row["source_type"],
            "source_number": row["source_number"],
            "doc_type": row["doc_type"],
            "title": row["title"],
            "body_preview": row["body_preview"],
            "similarity_score": round(1.0 - row["distance"], 4),
            "state": row["state"] or "",
            "milestone_title": row["milestone_title"] or "",
            "labels": json.loads(row["labels_json"]) if row["labels_json"] else [],
            "review_decision": row["review_decision"] or "",
            "check_status": row["check_status"] or "",
            "html_url": row["html_url"] or "",
        }
        for row in rows
    ]
