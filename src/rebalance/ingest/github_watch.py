"""External / watched GitHub repos: whole-repo activity rollups + lifecycle reconcile.

A *watched* repo is a third-party repo the operator monitors for **everyone's**
activity (commits, PRs, issues), not just their own GitHub events. It enters the
watched set via the project registry — a project flagged ``external: true`` (see
:func:`rebalance.ingest.registry.get_external_repos`) — and is artifact-synced by
the *existing* :func:`rebalance.ingest.github_knowledge.sync_github_repo` pipeline.
No second ingest path: this module adds the **one** extra step that makes a watched
repo's whole-repo activity surface in the org-activity dashboards/reports — derive a
``github_activity`` rollup under the sentinel login :data:`WATCHED_LOGIN`. The repo's
issues/PRs/commits already flow into ``github_items`` / ``github_commits`` /
``github_documents`` (and thus the repo-scoped feeds + semantic index) for free.

Lifecycle (de-dupe / pause). A watched repo can become *active work* — cloned and
worked on locally, or driven through a cloud agent — and later go quiet again,
possibly oscillating: ``Claude Code cloud → local → Codex cloud → local``. The org
SUMs would double-count if both the sentinel whole-repo rollup and the operator's
own per-login rows existed for the same repo. :func:`reconcile_watched_repo` is
recomputed on every refresh and is **idempotent + bidirectional**:

  - *active work* → **suppress**: skip derivation and purge any sentinel rows, so the
    operator's own per-login rows (incl. cloud-agent authors) are the sole
    representation — no double count.
  - *passive*     → **derive**: (re)build the sentinel whole-repo rollup.

Because artifact tables dedupe by sha/number, the only layer that can double count is
this rollup, which the reconcile keeps mutually exclusive with the owned per-login
rows. A repo moving the other direction (work goes quiet) self-heals on the next
refresh: the rollup resumes, the stale per-login picture simply ages out of the window.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest.config import normalize_github_repo_name
from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.ingest._http import GITHUB_API
from rebalance.ingest.github_knowledge import (
    JsonFetcher,
    _build_url,
    _cutoff_iso,
    _http_get_json,
)

# Sentinel login under which whole-repo (all-author) rollups are written to
# github_activity. Distinct from any real GitHub login so the operator's own
# "your work" rows (and the watched-set discovery in _activity_repos) never
# collide with — or get inflated by — watched-repo aggregates.
WATCHED_LOGIN = "__watch__"

# How recently a local clone must have been touched to count as "active work".
# A live focus5 row means a clone exists on a tracked device; we still require a
# recent operator commit so a long-dormant checkout reverts to external monitoring.
_LOCAL_RECENCY_DAYS = 45


def _bucket(iso: str | None) -> str | None:
    """YYYY-MM-DD day key from an ISO-8601 timestamp, or None."""
    if not iso:
        return None
    return str(iso)[:10]


# ---------------------------------------------------------------------------
# Derivation — whole-repo activity rollup
# ---------------------------------------------------------------------------

_ROLLUP_UPSERT_SQL = """
INSERT OR REPLACE INTO github_activity
    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _fetch_repo_commit_activity(
    repo_full_name: str,
    token: str,
    *,
    since_days: int,
    api_get_json: JsonFetcher | None = None,
) -> tuple[int, str | None]:
    """Return ``(commit_count, last_commit_iso)`` for the repo's default branch.

    Whole-repo, all-author commit history within the window — the signal the
    operator's events feed cannot provide for a repo they don't push to. One
    paginated ``/repos/{repo}/commits?since=`` call, reusing the shared helpers.
    Tolerant: an empty/disabled repo (409/404) yields ``(0, None)``.
    """
    api_get = api_get_json or (lambda url: _http_get_json(url, token))
    cutoff = _cutoff_iso(since_days)
    base = f"{GITHUB_API}/repos/{repo_full_name}/commits"

    count = 0
    last_iso: str | None = None
    page = 1
    while True:
        try:
            data = api_get(_build_url(base, since=cutoff, per_page=100, page=page))
        except Exception:  # noqa: BLE001 — empty repo, no access, transient error
            break
        if not isinstance(data, list) or not data:
            break
        for row in data:
            count += 1
            commit = row.get("commit") or {}
            stamp = (commit.get("committer") or {}).get("date") or (
                commit.get("author") or {}
            ).get("date")
            if stamp and (last_iso is None or stamp > last_iso):
                last_iso = stamp
        if len(data) < 100:
            break
        page += 1
    return count, last_iso


def derive_watched_repo_activity(
    database_path: Path,
    repo_full_name: str,
    token: str,
    *,
    since_days: int,
    api_get_json: JsonFetcher | None = None,
) -> dict[str, Any]:
    """Build a whole-repo ``github_activity`` rollup row under :data:`WATCHED_LOGIN`.

    PR/issue/comment counts come from the already-synced ``github_items`` /
    ``github_comments`` tables (so :func:`sync_github_repo` must have run first);
    commit counts come from a scoped live fetch. Mirrors the existing
    ``upsert_github_activity`` shape: one row per repo with ``scan_date`` = today and
    window-total counts, so the org-activity consumers SUM watched repos on the same
    footing as owned repos.
    """
    repo = normalize_github_repo_name(repo_full_name)
    now = datetime.now(timezone.utc)
    scan_date = now.strftime("%Y-%m-%d")
    cutoff_day = (now.replace(microsecond=0).isoformat())
    cutoff_date = _cutoff_iso(since_days)[:10]

    commits, last_commit = _fetch_repo_commit_activity(
        repo, token, since_days=since_days, api_get_json=api_get_json
    )

    with db_connection(database_path, ensure_github_schema) as conn:
        prs_opened = conn.execute(
            "SELECT COUNT(*) FROM github_items WHERE repo_full_name=? "
            "AND item_type='pull_request' AND substr(created_at,1,10) >= ?",
            (repo, cutoff_date),
        ).fetchone()[0]
        prs_merged = conn.execute(
            "SELECT COUNT(*) FROM github_items WHERE repo_full_name=? "
            "AND item_type='pull_request' AND is_merged=1 "
            "AND substr(merged_at,1,10) >= ?",
            (repo, cutoff_date),
        ).fetchone()[0]
        issues_opened = conn.execute(
            "SELECT COUNT(*) FROM github_items WHERE repo_full_name=? "
            "AND item_type='issue' AND substr(created_at,1,10) >= ?",
            (repo, cutoff_date),
        ).fetchone()[0]
        issue_comments = conn.execute(
            "SELECT COUNT(*) FROM github_comments WHERE repo_full_name=? "
            "AND substr(created_at,1,10) >= ?",
            (repo, cutoff_date),
        ).fetchone()[0]
        last_item = conn.execute(
            "SELECT MAX(updated_at) FROM github_items WHERE repo_full_name=?",
            (repo,),
        ).fetchone()[0]

        last_active = max(x for x in (last_commit, last_item, None) if x) if (
            last_commit or last_item
        ) else None

        conn.execute(
            _ROLLUP_UPSERT_SQL,
            (
                WATCHED_LOGIN,
                repo,
                scan_date,
                int(commits),
                0,  # pushes — not derivable per-repo without events; commits cover it
                int(prs_opened or 0),
                int(prs_merged or 0),
                int(issues_opened or 0),
                int(issue_comments or 0),
                0,  # reviews
                last_active,
                cutoff_day,
            ),
        )
        conn.commit()

    return {
        "commits": int(commits),
        "prs_opened": int(prs_opened or 0),
        "prs_merged": int(prs_merged or 0),
        "issues_opened": int(issues_opened or 0),
        "issue_comments": int(issue_comments or 0),
        "last_active_at": last_active,
    }


def purge_watched_repo_activity(database_path: Path, repo_full_name: str) -> int:
    """Delete the sentinel whole-repo rollup rows for *repo*. Returns rows removed."""
    repo = normalize_github_repo_name(repo_full_name)
    if not database_path.exists():
        return 0
    with db_connection(database_path, ensure_github_schema) as conn:
        cur = conn.execute(
            "DELETE FROM github_activity WHERE login=? AND repo_full_name=?",
            (WATCHED_LOGIN, repo),
        )
        conn.commit()
        return cur.rowcount or 0


# ---------------------------------------------------------------------------
# Lifecycle — is this watched repo now "active work"?
# ---------------------------------------------------------------------------

def watched_repo_is_active_work(
    database_path: Path,
    repo_full_name: str,
    *,
    since_days: int = 14,
) -> bool:
    """True when *repo* is being worked through any **owned** channel.

    Any of these means the operator (or a cloud agent acting for them) is actively
    working the repo, so the whole-repo rollup must step aside to avoid double
    counting against the real per-login rows:

      - a live local clone exists (``focus5_repo_signals`` with a recent
        ``my_last_commit_ts``) — covers the "downloaded and worked on locally" case;
      - the operator has push/collab access (``github_pushed_repos``) — covers cloud
        agents that push (Claude Code cloud / Codex cloud);
      - real per-login activity rows exist in the window (``github_activity`` under a
        non-sentinel login);
      - cloud-agent authored commits exist in the window (``github_commits``).

    Recomputed every refresh, so when these signals age out the repo reverts to
    external monitoring on its own.
    """
    repo = normalize_github_repo_name(repo_full_name)
    if not database_path.exists():
        return False

    recent_local_ts = int(
        datetime.now(timezone.utc).timestamp() - _LOCAL_RECENCY_DAYS * 86400
    )

    with db_connection(database_path, ensure_github_schema) as conn:
        # 1) Live local clone with a recent operator commit.
        try:
            row = conn.execute(
                "SELECT 1 FROM focus5_repo_signals "
                "WHERE LOWER(repo_full_name)=? "
                "AND (my_last_commit_ts IS NOT NULL AND my_last_commit_ts >= ?) "
                "LIMIT 1",
                (repo, recent_local_ts),
            ).fetchone()
            if row:
                return True
        except Exception:  # noqa: BLE001 — focus5 tables may not exist yet
            pass

        # 2) Operator/collab push access.
        try:
            row = conn.execute(
                "SELECT 1 FROM github_pushed_repos WHERE LOWER(repo_full_name)=? LIMIT 1",
                (repo,),
            ).fetchone()
            if row:
                return True
        except Exception:  # noqa: BLE001
            pass

        # 3) Real per-login activity in the window (anything but the sentinel).
        try:
            row = conn.execute(
                "SELECT 1 FROM github_activity WHERE LOWER(repo_full_name)=? "
                "AND login != ? AND scan_date >= date('now', ?) "
                "AND (commits+pushes+prs_opened+prs_merged+issues_opened"
                "     +issue_comments+reviews) > 0 LIMIT 1",
                (repo, WATCHED_LOGIN, f"-{int(since_days)} days"),
            ).fetchone()
            if row:
                return True
        except Exception:  # noqa: BLE001
            pass

        # 4) Cloud-agent authored commits in the window.
        try:
            from rebalance.ingest.pulse import CLOUD_AGENT_AUTHORS  # noqa: PLC0415

            placeholders = ",".join("?" * len(CLOUD_AGENT_AUTHORS))
            row = conn.execute(
                f"SELECT 1 FROM github_commits WHERE LOWER(repo_full_name)=? "
                f"AND author_login IN ({placeholders}) "
                f"AND substr(committed_at,1,10) >= ? LIMIT 1",
                (repo, *CLOUD_AGENT_AUTHORS, _cutoff_iso(since_days)[:10]),
            ).fetchone()
            if row:
                return True
        except Exception:  # noqa: BLE001
            pass

    return False


def reconcile_watched_repo(
    database_path: Path,
    repo_full_name: str,
    token: str,
    *,
    since_days: int,
    api_get_json: JsonFetcher | None = None,
) -> dict[str, Any]:
    """Idempotently bring one watched repo's rollup into the correct mode.

    ``active`` → purge the sentinel rollup (let the owned per-login rows stand);
    ``external`` → (re)derive the whole-repo rollup. Safe to call every refresh.
    """
    repo = normalize_github_repo_name(repo_full_name)
    if watched_repo_is_active_work(database_path, repo, since_days=since_days):
        purged = purge_watched_repo_activity(database_path, repo)
        return {"repo": repo, "mode": "active", "purged": purged}
    summary = derive_watched_repo_activity(
        database_path, repo, token, since_days=since_days, api_get_json=api_get_json
    )
    return {"repo": repo, "mode": "external", **summary}
