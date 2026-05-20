"""Typed query helpers for the ``github_*`` tables.

These keep raw SQL out of the CLI and ingest modules — callers work with
plain Python values and let this module own the column layout.
"""

from __future__ import annotations

import sqlite3


def top_active_repos(
    conn: sqlite3.Connection, top_n: int, since_days: int = 7
) -> list[str]:
    """Repo full-names ranked by recent activity score, highest first.

    Score sums ``commits + prs_opened + prs_merged + issues_opened +
    issue_comments + reviews`` over the trailing *since_days* window
    (``github_activity.scan_date``). Repos with a zero score are excluded.
    """
    rows = conn.execute(
        """
        SELECT repo_full_name,
               SUM(commits) + SUM(prs_opened) + SUM(prs_merged) +
               SUM(issues_opened) + SUM(issue_comments) + SUM(reviews) AS score
        FROM github_activity
        WHERE scan_date >= date('now', ?)
        GROUP BY repo_full_name
        HAVING score > 0
        ORDER BY score DESC
        LIMIT ?
        """,
        (f"-{since_days} days", top_n),
    ).fetchall()
    return [r[0] for r in rows]


def repo_last_active(
    conn: sqlite3.Connection, repos: list[str] | None = None
) -> dict[str, str]:
    """Map of ``repo_full_name`` -> latest ``last_active_at`` (raw ISO string).

    Pass *repos* to restrict to a subset; omit it for every repo. Repos with
    no non-null ``last_active_at`` are omitted. Timestamp parsing is left to
    the caller — this helper only touches the database.
    """
    if repos is not None:
        if not repos:
            return {}
        placeholders = ",".join("?" * len(repos))
        rows = conn.execute(
            f"SELECT repo_full_name, MAX(last_active_at) FROM github_activity "
            f"WHERE repo_full_name IN ({placeholders}) "
            f"AND last_active_at IS NOT NULL "
            f"GROUP BY repo_full_name",
            list(repos),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT repo_full_name, MAX(last_active_at) FROM github_activity "
            "WHERE last_active_at IS NOT NULL GROUP BY repo_full_name"
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def repo_meta_names(conn: sqlite3.Connection) -> set[str]:
    """Set of ``repo_full_name`` values present in ``github_repo_meta``.

    This is the canonical "fully synced" watched set — a repo only gets a
    ``github_repo_meta`` row after a complete artifact sync.
    """
    return {r[0] for r in conn.execute("SELECT repo_full_name FROM github_repo_meta")}
