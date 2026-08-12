"""Bounded, durable capture of direct GitHub branch-push signals (GH-155)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from rebalance.ingest._http import GITHUB_API, GitHubClient
from rebalance.ingest.config import normalize_github_repo_name
from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.ingest.db import github as gh
from rebalance.lib.time_ops import _now

MAX_PUSH_COMPARES_PER_REFRESH = 5
MAX_COMMIT_DETAILS_PER_REFRESH = 20
MAX_COMMITS_PER_PUSH = 250
MAX_EVENT_ATTEMPTS = 3
JsonGetter = Callable[[str], tuple[int, Any]]


@dataclass
class DirectCommitCaptureResult:
    events_seen: int = 0
    events_new: int = 0
    events_enriched: int = 0
    events_deferred: int = 0       # genuinely failed, will retry (costs an attempt)
    events_over_budget: int = 0     # ran out of per-run quota (costs nothing)
    commits_captured: int = 0
    head_only: int = 0
    api_calls_used: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _event_id(event: dict[str, Any]) -> str:
    """Use GitHub's event ID, with a deterministic fixture-safe fallback."""
    value = str(event.get("id") or "").strip()
    if value:
        return value
    payload = event.get("payload") or {}
    repo = (event.get("repo") or {}).get("name") or ""
    return ":".join((str(repo), str(event.get("created_at") or ""), str(payload.get("head") or "")))


def _is_deleted(head: str) -> bool:
    return not head or set(head) == {"0"}


def _commit_values(
    *, repo: str, sha: str, event_id: str, ref: str, row: dict[str, Any], coverage: str, now: str
) -> tuple:
    commit = row.get("commit") or {}
    author = row.get("author") or {}
    committer = commit.get("committer") or commit.get("author") or {}
    return (
        repo,
        sha,
        event_id,
        ref,
        author.get("login") or "",
        (commit.get("author") or {}).get("name") or "",
        (commit.get("message") or "").strip(),
        committer.get("date"),
        row.get("html_url") or "",
        coverage,
        now,
        now,
    )


def capture_direct_commits(
    database_path: Path,
    *,
    token: str,
    events: list[dict[str, Any]],
    watched_repos: list[str],
    api_get: JsonGetter | None = None,
    compare_cap: int = MAX_PUSH_COMPARES_PER_REFRESH,
    detail_cap: int = MAX_COMMIT_DETAILS_PER_REFRESH,
) -> DirectCommitCaptureResult:
    """Persist watched branch PushEvent receipts and enrich them within hard caps.

    The Events payload is only a discovery signal: compare resolves the range and
    commit-detail resolves exact file paths. A transient failure remains a
    durable deferred receipt, so no work is silently treated as absent.
    """
    result = DirectCommitCaptureResult()
    watched = {normalize_github_repo_name(repo) for repo in watched_repos}
    now = _now()
    with db_connection(database_path, ensure_github_schema) as conn:
        for event in events:
            if event.get("type") != "PushEvent":
                continue
            repo = str((event.get("repo") or {}).get("name") or "")
            normalized = normalize_github_repo_name(repo)
            if normalized not in watched:
                continue
            payload = event.get("payload") or {}
            ref = str(payload.get("ref") or "")
            if not ref.startswith("refs/heads/"):
                continue
            result.events_seen += 1
            if gh.insert_push_event(
                conn,
                (
                    _event_id(event), repo, ref, payload.get("before"), payload.get("head"),
                    event.get("created_at"), now,
                ),
            ):
                result.events_new += 1
        conn.commit()

    fetch = api_get or GitHubClient(token).get
    compare_used = detail_used = 0
    with db_connection(database_path, ensure_github_schema) as conn:
        pending = gh.pending_push_events(
            conn, max(compare_cap + detail_cap, compare_cap), MAX_EVENT_ATTEMPTS,
        )
        for event in pending:
            event_id = event["event_id"]
            repo = event["repo_full_name"]
            ref = event["ref"]
            before = str(event["before_sha"] or "")
            head = str(event["head_sha"] or "")
            attempt_now = _now()
            if _is_deleted(head):
                gh.update_push_event(conn, event_id, state="ignored", now=attempt_now, reason="branch deleted")
                continue

            if not before:
                if detail_used >= detail_cap:
                    gh.update_push_event(conn, event_id, state="deferred", now=attempt_now,
                                         reason="commit detail cap reached", deferral_kind="budget")
                    result.events_over_budget += 1
                    continue
                status, detail = fetch(f"{GITHUB_API}/repos/{quote(repo, safe='/')}/commits/{head}")
                detail_used += 1
                result.api_calls_used += 1
                if status == 200 and isinstance(detail, dict):
                    gh.upsert_direct_commit(conn, _commit_values(
                        repo=repo, sha=head, event_id=event_id, ref=ref, row=detail,
                        coverage="complete", now=attempt_now,
                    ))
                    gh.replace_direct_commit_files(conn, repo, head, detail.get("files") or [])
                    gh.update_push_event(conn, event_id, state="head_only", now=attempt_now, reason="missing push base")
                    result.commits_captured += 1
                    result.head_only += 1
                else:
                    state = "deferred" if status in (429, 500, 502, 503, 504) else "failed"
                    gh.update_push_event(conn, event_id, state=state, now=attempt_now,
                                         reason=f"head fetch HTTP {status}", deferral_kind="failure")
                    result.events_deferred += state == "deferred"
                continue

            if compare_used >= compare_cap:
                gh.update_push_event(conn, event_id, state="deferred", now=attempt_now,
                                     reason="compare cap reached", deferral_kind="budget")
                result.events_over_budget += 1
                continue
            compare_url = f"{GITHUB_API}/repos/{quote(repo, safe='/')}/compare/{before}...{head}"
            status, comparison = fetch(compare_url)
            compare_used += 1
            result.api_calls_used += 1
            if status != 200 or not isinstance(comparison, dict):
                state = "deferred" if status in (429, 500, 502, 503, 504) else "failed"
                gh.update_push_event(conn, event_id, state=state, now=attempt_now,
                                     reason=f"compare HTTP {status}", deferral_kind="failure")
                result.events_deferred += state == "deferred"
                continue
            commits = comparison.get("commits") or []
            if int(comparison.get("ahead_by") or len(commits)) > MAX_COMMITS_PER_PUSH:
                gh.update_push_event(conn, event_id, state="failed", now=attempt_now, reason="compare range exceeds direct-commit cap")
                continue

            complete = True
            terminal_detail_error = False
            deferral_kind = "budget"  # downgraded to "failure" on a real fetch error
            for summary in commits:
                sha = str(summary.get("sha") or "")
                if not sha:
                    continue
                existing = conn.execute(
                    "SELECT path_coverage FROM github_direct_commits WHERE repo_full_name = ? AND sha = ?",
                    (repo, sha),
                ).fetchone()
                if existing and existing["path_coverage"] == "complete":
                    continue
                if detail_used >= detail_cap:
                    gh.upsert_direct_commit(conn, _commit_values(
                        repo=repo, sha=sha, event_id=event_id, ref=ref, row=summary,
                        coverage="unavailable", now=attempt_now,
                    ))
                    complete = False
                    continue
                detail_status, detail = fetch(f"{GITHUB_API}/repos/{quote(repo, safe='/')}/commits/{sha}")
                detail_used += 1
                result.api_calls_used += 1
                if detail_status != 200 or not isinstance(detail, dict):
                    gh.upsert_direct_commit(conn, _commit_values(
                        repo=repo, sha=sha, event_id=event_id, ref=ref, row=summary,
                        coverage="unavailable", now=attempt_now,
                    ))
                    complete = False
                    terminal_detail_error |= detail_status not in (429, 500, 502, 503, 504)
                    deferral_kind = "failure"
                    continue
                gh.upsert_direct_commit(conn, _commit_values(
                    repo=repo, sha=sha, event_id=event_id, ref=ref, row=detail,
                    coverage="complete", now=attempt_now,
                ))
                gh.replace_direct_commit_files(conn, repo, sha, detail.get("files") or [])
                result.commits_captured += 1
            state = "enriched" if complete else ("failed" if terminal_detail_error else "deferred")
            # A partial pass that ran out of DETAIL budget has not failed at
            # anything; charging it an attempt is what evicted live events.
            kind = None if complete else ("failure" if terminal_detail_error else deferral_kind)
            reason = "" if complete else (
                "non-retryable commit detail failure" if terminal_detail_error
                else ("commit detail cap reached" if kind == "budget"
                      else "transient commit detail fetch failure")
            )
            gh.update_push_event(conn, event_id, state=state, now=attempt_now,
                                 reason=reason, deferral_kind=kind)
            result.events_enriched += complete
            if not complete and not terminal_detail_error:
                if kind == "budget":
                    result.events_over_budget += 1
                else:
                    result.events_deferred += 1
        conn.commit()
    return result


def sync_direct_commit_documents(database_path: Path) -> int:
    """Materialize non-PR-overlapping direct commits into the GitHub document corpus."""
    now = _now()
    with db_connection(database_path, ensure_github_schema) as conn:
        rows = conn.execute(
            """
            SELECT d.repo_full_name, d.sha, d.ref, d.message, d.committed_at, d.html_url,
                   d.path_coverage
            FROM github_direct_commits d
            WHERE NOT EXISTS (
                SELECT 1 FROM github_commits p
                WHERE p.repo_full_name = d.repo_full_name AND p.sha = d.sha
            )
            ORDER BY d.committed_at DESC
            """
        ).fetchall()

        valid_source_keys = set()

        for row in rows:
            source_key = f"{row['repo_full_name']}:direct_commit:{row['sha']}"
            valid_source_keys.add(source_key)
            paths = [
                file_row["path"] for file_row in conn.execute(
                    "SELECT path FROM github_direct_commit_files WHERE repo_full_name = ? AND sha = ? "
                    "ORDER BY path LIMIT 50",
                    (row["repo_full_name"], row["sha"]),
                ).fetchall()
            ]
            path_text = "\n".join(f"- {path}" for path in paths) or "- (paths unavailable)"
            body = (
                f"Direct branch commit {row['sha']}\nRef: {row['ref'] or ''}\n"
                f"Committed: {row['committed_at'] or ''}\nCoverage: {row['path_coverage']}\n"
                f"Message: {row['message'] or ''}\nChanged paths:\n{path_text}"
            )
            gh.upsert_github_document(
                conn,
                repo_full_name=row["repo_full_name"],
                source_type="direct_commit",
                source_number=0,
                doc_type="direct_commit",
                source_key=source_key,
                title=(row["message"] or "direct commit").splitlines()[0][:200],
                body=body,
                content_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
                updated_at=row["committed_at"] or now,
                fetched_at=now,
            )

        # Prune vanished documents (e.g. vanished or PR-overlapping commits).
        existing_docs = conn.execute(
            "SELECT id, source_key FROM github_documents WHERE doc_type = 'direct_commit'"
        ).fetchall()
        stale_doc_ids = [
            doc["id"] for doc in existing_docs if doc["source_key"] not in valid_source_keys
        ]
        if stale_doc_ids:
            gh.delete_github_documents(conn, stale_doc_ids)

        conn.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# GH-169 Phase 2 — recovery of events evicted by budget deferrals
# ---------------------------------------------------------------------------

# Events written before `deferral_kind` existed carry their classification only
# in prose. This is a ONE-TIME migration seed, never a control path: after the
# migration the column is authoritative, so the fragile text match cannot rot
# into a live dependency.
_LEGACY_BUDGET_REASONS = ("compare cap reached", "commit detail cap reached")


def classify_legacy_deferrals(database_path: Path) -> int:
    """Backfill ``deferral_kind`` for rows written before the column existed.

    Returns the number of rows classified. Anything not recognisably a budget
    deferral is marked ``failure`` — the conservative direction, since it costs
    an attempt rather than granting an infinite retry.
    """
    with db_connection(database_path, ensure_github_schema) as conn:
        placeholders = ",".join("?" for _ in _LEGACY_BUDGET_REASONS)
        cursor = conn.execute(
            f"""
            UPDATE github_push_events
            SET deferral_kind = CASE
                WHEN failure_reason IN ({placeholders}) THEN 'budget'
                ELSE 'failure'
            END
            WHERE deferral_kind IS NULL AND state = 'deferred'
            """,
            _LEGACY_BUDGET_REASONS,
        )
        conn.commit()
        return cursor.rowcount


def recover_budget_evicted_events(
    database_path: Path,
    *,
    apply: bool = False,
    max_attempts: int = MAX_EVENT_ATTEMPTS,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    """Return events evicted purely by budget deferrals to the pending queue.

    PREVIEW BY DEFAULT (``apply=False``) — this mutates a live table, so the
    caller must opt in. Rollback is inherent: the migration is additive and the
    reset only lowers ``attempt_count`` and returns ``state`` to ``pending``,
    so re-running collection restores whatever the reset undid. A pre-image of
    every affected ``(event_id, state, attempt_count)`` is written to
    *snapshot_path* when applying.
    """
    classified = classify_legacy_deferrals(database_path)
    with db_connection(database_path, ensure_github_schema) as conn:
        rows = conn.execute(
            """
            SELECT event_id, repo_full_name, state, attempt_count, failure_reason
            FROM github_push_events
            WHERE state IN ('pending', 'deferred')
              AND attempt_count >= ?
              AND deferral_kind = 'budget'
            ORDER BY observed_at ASC
            """,
            (max_attempts,),
        ).fetchall()
        affected = [dict(row) for row in rows]

        result: dict[str, Any] = {
            "legacy_rows_classified": classified,
            "eligible": len(affected),
            "applied": False,
            "event_ids": [r["event_id"] for r in affected],
            "snapshot_path": None,
        }
        if not apply or not affected:
            return result

        if snapshot_path is not None:
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(json.dumps(affected, indent=2))
            result["snapshot_path"] = str(snapshot_path)

        conn.executemany(
            """
            UPDATE github_push_events
            SET state = 'pending', attempt_count = 0,
                failure_reason = NULL, deferral_kind = NULL
            WHERE event_id = ?
            """,
            [(r["event_id"],) for r in affected],
        )
        conn.commit()
        result["applied"] = True
        return result
