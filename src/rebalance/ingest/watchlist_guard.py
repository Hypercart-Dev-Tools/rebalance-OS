"""Watch-list coverage guard — snapshot the watched-repos set and alarm on a
silent reduction.

``get_watched_repos`` (index_ops) is a recomputed union with no persisted
history, so a repo held only by a rolling window (``activity`` 14d / ``pushed``)
drops off the roster with no trace. This module gives the set a memory:

  * :func:`snapshot_and_detect` is the **single writer** — it resolves the
    watched set with a *fixed canonical window*, persists one row per repo (with
    the resolving buckets), diffs against the previous snapshot, and emits a
    ``watched_repos_reduced`` event on a *concerning* drop. It prunes snapshots
    older than :data:`RETENTION_DAYS`.
  * :func:`classify_removal` is a pure helper (no I/O) so the warn-vs-churn
    signal logic is unit-testable in isolation.

Design rationale + QA history: ``PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md``.
"""

from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from rebalance.ingest.db import db_connection, run_migrations

# A repo dropping out of the watched set is only *concerning* when it was held by
# a durable-intent bucket; a repo held only by a rolling window legitimately ages
# out and must not cry wolf (agy relay r1). Keep this vocabulary in ONE place.
_DURABLE_BUCKETS = frozenset({"project", "external"})

# Pin a fixed window so the snapshot baseline is stable. refresh_index defaults
# since_days=30 while the watched-set windows default to 14; if the snapshot
# reflected the *caller's* window, a 30-day sync vs a 14-day sync would diff
# against each other and manufacture phantom reductions (agy relay r1).
CANONICAL_SINCE_DAYS = 14

# Keep ~30 days of diffable history; prune older rows so the table can't grow
# without bound (agy relay r1, resolves Open Q2).
RETENTION_DAYS = 30

_SNAPSHOT_TABLE = "watched_repos_snapshot"
# Map each watched-set bucket list (keys in the get_watched_repos view) to its
# canonical bucket label. Order is the attribution order; a repo can be in many.
_BUCKET_SOURCES = (
    ("project_repos", "project"),
    ("external_repos", "external"),
    ("activity_repos", "activity"),
    ("pushed_repos", "pushed"),
)


def classify_removal(buckets: set[str]) -> str:
    """``warn`` if the repo's last-known buckets include a durable-intent bucket
    (``project``/``external``); ``info`` for rolling-window-only churn."""
    return "warn" if (_DURABLE_BUCKETS & buckets) else "info"


def _bucket_map(view: dict[str, Any]) -> dict[str, set[str]]:
    """Per watched repo, the set of buckets that resolved it (ignored excluded)."""
    watched = set(view.get("watched") or [])
    out: dict[str, set[str]] = defaultdict(set)
    for key, label in _BUCKET_SOURCES:
        for repo in view.get(key) or []:
            if repo in watched:
                out[repo].add(label)
    return out


def _read_latest_snapshot(conn) -> tuple[int | None, dict[str, set[str]]]:
    """The most recent snapshot: ``(snapshot_ts, {repo: buckets})`` or
    ``(None, {})`` when the table is empty (first-ever run).

    Anchored on ``MAX(snapshot_ts)`` over the rows, so an empty watched set
    (which writes zero rows) is invisible here. That only matters if monitoring
    drops to *nothing* — a far bigger alarm than any single reduction — and the
    effect is merely that the next run diffs against the last non-empty snapshot
    and re-alarms. Safe-loud, never silent, so the guard's invariant holds.
    """
    row = conn.execute(
        f"SELECT MAX(snapshot_ts) AS ts FROM {_SNAPSHOT_TABLE}"
    ).fetchone()
    ts = row["ts"] if row else None
    if ts is None:
        return None, {}
    rows = conn.execute(
        f"SELECT repo, buckets FROM {_SNAPSHOT_TABLE} WHERE snapshot_ts = ?",
        (ts,),
    ).fetchall()
    prev = {
        r["repo"]: {b for b in (r["buckets"] or "").split(",") if b}
        for r in rows
    }
    return ts, prev


def snapshot_and_detect(
    database_path: Path,
    *,
    now_ts: int | None = None,
) -> dict[str, Any]:
    """Resolve the watched set, persist a snapshot, diff against the previous one,
    and emit a ``watched_repos_reduced`` event on a concerning reduction.

    The single writer of ``watched_repos_snapshot``. Safe to call directly (runs
    migrations first). ``now_ts`` is injectable for tests; production uses wall
    clock. Returns a summary dict (also folded into the github refresh result).
    """
    # Import here so the module imports cheaply and avoids an index_ops cycle.
    from rebalance.ingest.config import get_github_ignored_repos
    from rebalance.ingest.index_ops import get_watched_repos

    view = get_watched_repos(database_path, since_days=CANONICAL_SINCE_DAYS)
    curr_buckets = _bucket_map(view)
    curr = set(view.get("watched") or [])

    with db_connection(database_path) as conn:
        run_migrations(conn)  # ensure the table exists even on a direct call
        prev_ts, prev_buckets = _read_latest_snapshot(conn)

        # ponytail: INSERT OR REPLACE handles a same-second double-run (PK is
        # (snapshot_ts, repo)); a real github sync takes minutes, so two in one
        # second can't happen in prod — no monotonic-id machinery needed.
        ts = int(now_ts if now_ts is not None else time.time())

        conn.executemany(
            f"INSERT OR REPLACE INTO {_SNAPSHOT_TABLE} "
            "(snapshot_ts, repo, buckets) VALUES (?,?,?)",
            [(ts, repo, ",".join(sorted(curr_buckets.get(repo, set()))))
             for repo in sorted(curr)],
        )

        # Prune old history (keep ~RETENTION_DAYS).
        cutoff = ts - RETENTION_DAYS * 86400
        conn.execute(
            f"DELETE FROM {_SNAPSHOT_TABLE} WHERE snapshot_ts < ?", (cutoff,)
        )
        conn.commit()

    # First-ever run: baseline only, never a reduction event.
    if prev_ts is None:
        return {"baseline": True, "snapshot_ts": ts, "watched": len(curr)}

    prev_set = set(prev_buckets)
    removed = sorted(prev_set - curr)
    added = sorted(curr - prev_set)
    ignored_lower = {r.lower() for r in get_github_ignored_repos()}

    warn_removed: list[dict[str, Any]] = []
    info_churn: list[str] = []
    for repo in removed:
        # An intentional opt-out (just-ignored) is not a coverage loss (agy r1).
        if repo.lower() in ignored_lower:
            continue
        last_buckets = prev_buckets.get(repo, set())
        if classify_removal(last_buckets) == "warn":
            warn_removed.append({"repo": repo, "last_buckets": sorted(last_buckets)})
        else:
            info_churn.append(repo)

    # Only a *concerning* reduction alarms; pure window churn stays quiet.
    if warn_removed:
        from rebalance.ingest import auth_log

        auth_log.log_watched_repos_reduced(warn_removed, info_churn=info_churn)

    return {
        "baseline": False,
        "snapshot_ts": ts,
        "watched": len(curr),
        "added": added,
        "removed": removed,
        "warn_removed": warn_removed,
        "info_churn": info_churn,
    }
