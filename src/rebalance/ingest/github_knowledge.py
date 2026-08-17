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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
import re

from rebalance.ingest.config import get_github_ignored_repos, normalize_github_repo_name
from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_semantic_schema
from rebalance.ingest.db import github as gh
from rebalance.ingest.db import semantic as sem
from rebalance.ingest._http import GITHUB_API, GitHubClient, GitHubHTTPError
from rebalance.ingest.embedder import (
    DEFAULT_MODEL as DEFAULT_EMBED_MODEL,
    EMBEDDING_DIM,
    _embed_batch,
    _load_model,
    _vec_to_bytes,
)
from rebalance.ingest.semantic_index import sync_github_documents
from rebalance.lib.json_ops import _json_dumps
DEFAULT_SYNC_DAYS = 90
MIN_EMBED_CHARS = 40
# GH-171: release the single SQLite writer periodically during a long persist
# loop instead of holding one write transaction for the whole sync. Mirrors
# the batch size GH-169's commit-history backfill already established
# (see github_commit_backfill.py's _COMMIT_BATCH).
_COMMIT_BATCH = 100
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


@dataclass
class GitHubRepoPurgeResult:
    repo_full_name: str
    dry_run: bool
    row_counts: dict[str, int]
    total_rows: int
    deleted_rows: int


def _github_headers(token: str) -> dict[str, str]:
    """Delegate to the shared GitHub client.

    Retained as a module-level helper because some external callers (tests,
    experimental scripts) imported it before the shared client existed.
    """
    return GitHubClient(token).headers()


def _http_get_json(url: str, token: str) -> Any:
    """GET ``url`` as JSON; raise on non-2xx.

    Thin wrapper over :class:`GitHubClient` so the legacy ``api_get`` callable
    seam in :func:`sync_github_repo` keeps working. New code should construct
    a client once and reuse it.
    """
    try:
        return GitHubClient(token).get_json(url)
    except GitHubHTTPError as exc:
        # Preserve legacy RuntimeError type — tests and callers expect it.
        raise RuntimeError(f"GitHub API request failed: {exc.status} {url}") from exc


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
    return gh.insert_github_document(
        conn,
        repo_full_name=repo_full_name,
        source_type=source_type,
        source_number=source_number,
        doc_type=doc_type,
        source_key=source_key,
        title=title,
        body=body,
        content_hash=_content_hash(body),
        updated_at=updated_at,
        fetched_at=fetched_at,
    )


def purge_github_repo_data(
    database_path: Path,
    repo_full_name: str,
    *,
    dry_run: bool = False,
) -> GitHubRepoPurgeResult:
    """Delete one repo's GitHub ingest footprint and related semantic rows."""
    normalized_repo = normalize_github_repo_name(repo_full_name)
    table_names = [
        "github_activity",
        "github_branches",
        "github_labels",
        "github_milestones",
        "github_releases",
        "github_items",
        "github_comments",
        "github_commits",
        "github_check_runs",
        "github_links",
        "github_documents",
        "github_repo_meta",
    ]

    with db_connection(database_path) as conn:
        ensure_github_schema(conn)
        ensure_semantic_schema(conn)

        row_counts: dict[str, int] = {
            table_name: gh.count_repo_rows(conn, table_name, normalized_repo)
            for table_name in table_names
        }

        github_doc_ids = gh.github_document_ids(conn, normalized_repo)
        row_counts["github_embeddings"] = gh.count_ids_in(
            conn, "github_embeddings", "doc_id", github_doc_ids
        )

        semantic_doc_ids = gh.semantic_doc_ids_for_github_repo(conn, normalized_repo)
        row_counts["semantic_documents"] = len(semantic_doc_ids)
        row_counts["semantic_embeddings"] = gh.count_ids_in(
            conn, "semantic_embeddings", "rowid", semantic_doc_ids
        )

        total_rows = sum(row_counts.values())
        if dry_run:
            return GitHubRepoPurgeResult(
                repo_full_name=normalized_repo,
                dry_run=True,
                row_counts=row_counts,
                total_rows=total_rows,
                deleted_rows=0,
            )

        if semantic_doc_ids:
            sem.delete_semantic_documents(conn, semantic_doc_ids)
        if github_doc_ids:
            gh.delete_github_embeddings_for_docs(conn, github_doc_ids)
        for table_name in table_names:
            gh.delete_repo_rows(conn, table_name, normalized_repo)
        conn.commit()

    return GitHubRepoPurgeResult(
        repo_full_name=normalized_repo,
        dry_run=False,
        row_counts=row_counts,
        total_rows=total_rows,
        deleted_rows=total_rows,
    )


def sync_github_artifacts(
    database_path: Path,
    repos: list[str],
    *,
    token: str,
    since_days: int = DEFAULT_SYNC_DAYS,
    on_repo_start: Callable[[str], None] | None = None,
    on_repo_result: Callable[[str, GitHubKnowledgeSyncResult], None] | None = None,
) -> None:
    """Source-owned entry point for the GitHub artifact sync across repos.

    Streaming + fail-fast: ``on_repo_start`` fires before each repo's sync and
    ``on_repo_result`` after, so the caller controls per-repo progress output;
    exceptions propagate (no per-repo swallowing — the loop aborts on first
    failure, preserving today's behavior). CLI `github-sync-artifacts` uses this
    so it no longer imports the leaf sync_github_repo
    (COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2).
    """
    for repo in repos:
        if on_repo_start is not None:
            on_repo_start(repo)
        result = sync_github_repo(
            database_path=database_path,
            repo_full_name=repo,
            token=token,
            since_days=since_days,
        )
        if on_repo_result is not None:
            on_repo_result(repo, result)


def sync_github_repo(
    database_path: Path,
    repo_full_name: str,
    token: str,
    *,
    since_days: int = DEFAULT_SYNC_DAYS,
    api_get_json: JsonFetcher | None = None,
) -> GitHubKnowledgeSyncResult:
    normalized_repo = normalize_github_repo_name(repo_full_name)
    if normalized_repo in set(get_github_ignored_repos()):
        raise ValueError(f"GitHub repo is ignored: {normalized_repo}")

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

    # --- Fetch phase (GH-171) ---
    # Pull every per-issue and per-PR payload (comments, reviews, review
    # comments, commits, check-runs) from the GitHub API here, before any
    # write transaction opens. Previously all of this fetching happened
    # *inside* the `with db_connection(...)` block below, so the write
    # transaction spanned the full network walk — worst case ~49 minutes per
    # GH-146 — holding the single SQLite writer for the entire run and giving
    # every other writer a bare "database is locked". What is fetched and how
    # is unchanged; only the transaction boundary moves.
    issue_payloads: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for issue in issues:
        item_number = int(issue["number"])
        issue_comments = _paginate_list(f"{repo_base}/issues/{item_number}/comments", api_get)
        issue_payloads.append((issue, issue_comments))

    pr_payloads: list[
        tuple[
            dict[str, Any],
            list[dict[str, Any]],
            list[dict[str, Any]],
            list[dict[str, Any]],
            list[dict[str, Any]],
            list[dict[str, Any]],
        ]
    ] = []
    for pull_summary in pull_summaries:
        item_number = int(pull_summary["number"])
        pr = api_get(f"{repo_base}/pulls/{item_number}")
        if not isinstance(pr, dict):
            continue

        pr_issue_comments = _paginate_list(f"{repo_base}/issues/{item_number}/comments", api_get)
        pr_reviews = _paginate_list(f"{repo_base}/pulls/{item_number}/reviews", api_get)
        pr_review_comments = _paginate_list(f"{repo_base}/pulls/{item_number}/comments", api_get)
        pr_commits = _paginate_list(f"{repo_base}/pulls/{item_number}/commits", api_get)
        check_runs_resp = api_get(_build_url(f"{repo_base}/commits/{pr.get('head', {}).get('sha', '')}/check-runs", per_page=100))
        pr_check_runs = (
            check_runs_resp.get("check_runs", [])
            if isinstance(check_runs_resp, dict)
            else []
        )
        pr_payloads.append(
            (pr, pr_issue_comments, pr_reviews, pr_review_comments, pr_commits, pr_check_runs)
        )

    comments_synced = 0
    commits_synced = 0
    checks_synced = 0
    docs_built = 0
    persisted_records = 0

    # --- Persist phase (GH-171) ---
    # Everything below is a local DB write against already-fetched data. The
    # write transaction is batch-committed every _COMMIT_BATCH records
    # (mirrors GH-169's commit-history backfill pattern in
    # github_commit_backfill.py) so a long sync releases the SQLite writer
    # periodically instead of holding it for the whole run.
    with db_connection(database_path, ensure_github_schema) as conn:
        gh.delete_repo_table(conn, "github_branches", repo_full_name)
        gh.delete_repo_table(conn, "github_labels", repo_full_name)
        gh.delete_repo_table(conn, "github_milestones", repo_full_name)
        gh.delete_repo_table(conn, "github_releases", repo_full_name)

        gh.upsert_repo_meta(
            conn,
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
            gh.upsert_branch(
                conn,
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
            gh.upsert_label(
                conn,
                (
                    repo_full_name,
                    label.get("name", ""),
                    label.get("color", ""),
                    label.get("description", ""),
                    1 if label.get("default") else 0,
                ),
            )

        for milestone in milestones:
            gh.upsert_milestone(
                conn,
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
            gh.upsert_release(
                conn,
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

        for issue, issue_comments in issue_payloads:
            item_type = "issue"
            item_number = int(issue["number"])
            milestone = issue.get("milestone") or {}
            gh.delete_item_children(conn, repo_full_name, item_type, item_number)

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

            gh.upsert_item(conn, item_record)

            for comment in issue_comments:
                body = comment.get("body", "") or ""
                gh.upsert_comment(
                    conn,
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

            # GH-171: release the writer periodically instead of holding one
            # transaction across the entire issue+PR persist loop.
            persisted_records += 1
            if persisted_records % _COMMIT_BATCH == 0:
                conn.commit()

        for pr, issue_comments, reviews, review_comments, commits, check_runs in pr_payloads:
            item_type = "pull_request"
            item_number = int(pr["number"])
            milestone = pr.get("milestone") or {}
            gh.delete_item_children(conn, repo_full_name, item_type, item_number)

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

            gh.upsert_item(conn, item_record)

            combined_text = "\n".join(filter(None, [item_record["title"], item_record["body"]]))
            for link_kind, issue_number in _parse_links(combined_text):
                gh.upsert_link(
                    conn,
                    (repo_full_name, item_type, item_number, "issue", issue_number, link_kind),
                )

            for comment in issue_comments:
                body = comment.get("body", "") or ""
                gh.upsert_comment(
                    conn,
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
                gh.upsert_comment(
                    conn,
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
                gh.upsert_comment(
                    conn,
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
                gh.upsert_commit(
                    conn,
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
                gh.upsert_check_run(
                    conn,
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

            # GH-171: same periodic-release batching as the issue loop above.
            persisted_records += 1
            if persisted_records % _COMMIT_BATCH == 0:
                conn.commit()

        ensure_semantic_schema(conn)
        sync_github_documents(conn, repo_full_name=repo_full_name)
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
    from rebalance.ingest.embedder import instrument_embedding_pass
    instrument_embedding_pass("_default_embed_texts")
    model, tokenizer = _load_model(model_name)
    return _embed_batch(model, tokenizer, texts)


def refresh_github_embeddings(
    database_path: Path,
    *,
    model_name: str = DEFAULT_EMBED_MODEL,
    batch_size: int = 32,
    min_chars: int = MIN_EMBED_CHARS,
    force_reembed: bool = False,
    embed_texts: EmbedTexts | None = None,
) -> GitHubEmbedResult:
    """Source-owned 1:1 facade over :func:`embed_github_documents` so CLI
    `github-embed` doesn't import the leaf directly (forwards all flags + the
    embed_texts test seam). COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2.
    """
    return embed_github_documents(
        database_path=database_path,
        model_name=model_name,
        batch_size=batch_size,
        min_chars=min_chars,
        force_reembed=force_reembed,
        embed_texts=embed_texts,
    )


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
            gh.clear_github_embeddings(conn)
            gh.reset_github_embedded_hashes(conn)
            conn.commit()

        rows = gh.github_documents_pending_embed(conn, min_chars)
        total_docs = gh.count_embeddable_github_documents(conn, min_chars)

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
                gh.upsert_github_embedding(conn, row["id"], _vec_to_bytes(vec))
                gh.mark_github_document_embedded(conn, row["id"])
                embedded += 1
            conn.commit()

        now_iso = datetime.now(timezone.utc).isoformat()
        for key, value in [
            ("model_name", model_name),
            ("embedding_dim", str(EMBEDDING_DIM)),
            ("last_embed_at", now_iso),
        ]:
            gh.set_github_embedding_meta(conn, key, value)
        conn.commit()

    return GitHubEmbedResult(
        total_docs=total_docs,
        embedded_docs=embedded,
        skipped_unchanged=total_docs - embedded,
        model_name=model_name,
        embedding_dim=EMBEDDING_DIM,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )
