"""Deterministic grouping and connection surfacing for Sleuth reminders.

Ports reminder-clustering.js + ExtractReminderTitle from the sleuth-app repo
to Python. No AI, no IO in the core functions — pure data transformation.

Grouping rules (priority order, a reminder joins the first group it matches):
  1. Shared GitHub URL  — transitive union-find across reminders sharing any URL
  2. Same client        — channel/repo-pattern match via the client-channel-mapping
  3. Same channel       — 2+ reminders with the same OriginalChannelName
  4. Other              — everything left; always rendered last
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReminderGroup:
    kind: Literal["github", "client", "channel", "other"]
    label: str
    reminders: tuple[dict[str, Any], ...]


# ---------------------------------------------------------------------------
# Title extraction  (ports ExtractReminderTitle from show-me-projects-command.js)
# ---------------------------------------------------------------------------

_SLACK_USER_RE  = re.compile(r"<@[A-Z0-9]+(?:\|[^>]*)?>")
_SLACK_LINK_RE  = re.compile(r"<([^|>\s]+)\|([^>]+)>")
_SLACK_TOKEN_RE = re.compile(r"<[^>]+>")
_MRKDWN_RE      = re.compile(r"[*_`]")
_KEY_TASK_RE    = re.compile(r"Key task\(s\):\s*\n?\s*[•\-*]?\s*([^\n]+)", re.IGNORECASE)
_FOLLOW_UP_RE   = re.compile(r"^.*?please follow up on <[^>]*>:?\s*", re.IGNORECASE | re.DOTALL)
_QUOTE_LEAD_RE  = re.compile(r"^>\s*", re.MULTILINE)


def _strip_slack_mrkdwn(text: str) -> str:
    text = _SLACK_USER_RE.sub("", text)
    text = _SLACK_LINK_RE.sub(r"\2", text)
    text = _SLACK_TOKEN_RE.sub("", text)
    text = _MRKDWN_RE.sub("", text)
    return text.strip()


def extract_task_text(text: str) -> str:
    """Return a short title for a Sleuth reminder message.

    Prefers the ``Key task(s):`` bullet the pipeline writes; falls back to
    stripping the Sleuth digest prefix and returning the first non-empty line.
    Slack mrkdwn tokens (<@USER>, <url|text>, *bold*, etc.) are removed.
    Truncates at 140 chars with an ellipsis.
    """
    if not isinstance(text, str):
        return ""
    m = _KEY_TASK_RE.search(text)
    if m and m.group(1).strip():
        result = _strip_slack_mrkdwn(m.group(1).strip())
        return result[:140] + "…" if len(result) > 140 else result

    stripped = _FOLLOW_UP_RE.sub("", text)
    stripped = _QUOTE_LEAD_RE.sub("", stripped)
    first_line = next(
        (line.strip() for line in stripped.split("\n") if line.strip()),
        text.strip(),
    )
    result = _strip_slack_mrkdwn(first_line)
    return result[:140] + "…" if len(result) > 140 else result


# ---------------------------------------------------------------------------
# Client mapping  (mirrors client-mapping.js + client-channel-mapping.json)
# ---------------------------------------------------------------------------

def _find_client_mapping_path() -> Path | None:
    """Locate client-channel-mapping.json.

    Checks ``sleuth_client_mapping_path`` in rbos.config first (portable);
    falls back to the canonical sibling sleuth-app checkout heuristic.
    """
    from rebalance.ingest.config import get_sleuth_client_mapping_path
    configured = get_sleuth_client_mapping_path()
    if configured:
        p = Path(configured)
        return p if p.exists() else None
    from rebalance.paths import resolve_project_root
    repo_root = resolve_project_root(Path(__file__))
    candidate = (
        repo_root.parent / "GH Repos" / "sleuth-app"
        / "data" / "static" / "client-channel-mapping.json"
    )
    return candidate if candidate.exists() else None


def load_client_mapping(path: Path | None = None) -> list[dict[str, Any]]:
    """Load client→channel/repo mappings.  Returns [] when file is absent."""
    resolved = path or _find_client_mapping_path()
    if resolved is None or not resolved.exists():
        return []
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data.get("clients", []) if isinstance(data, dict) else []


def _does_reminder_match_client(reminder: dict[str, Any], client: dict[str, Any]) -> bool:
    """True when the reminder is associated with the given client mapping entry.

    Mirrors DoesReminderMatchClient from client-mapping.js.
    """
    channel_ids = client.get("ChannelIDs") or []
    if reminder.get("original_channel_id") and reminder["original_channel_id"] in channel_ids:
        return True

    channel_name = (reminder.get("original_channel_name") or "").lower()
    name_patterns = [
        p.lower()
        for p in (client.get("ChannelNamePatterns") or [])
        if isinstance(p, str) and p
    ]
    if channel_name and any(p in channel_name for p in name_patterns):
        return True

    github_urls = reminder.get("github_urls") or []
    repo_patterns = [
        p.lower()
        for p in (client.get("GitHubRepoPatterns") or [])
        if isinstance(p, str) and p
    ]
    if github_urls and repo_patterns:
        if any(
            p in (url or "").lower()
            for url in github_urls
            for p in repo_patterns
        ):
            return True

    return False


# ---------------------------------------------------------------------------
# GitHub URL label  (mirrors GitHubRefFromUrl from reminder-clustering.js)
# ---------------------------------------------------------------------------

def _github_label_from_url(url: str) -> str:
    m = re.search(r"/(issues|pull)/(\d+)", url or "", re.IGNORECASE)
    if not m:
        return url
    return f"PR #{m.group(2)}" if m.group(1).lower() == "pull" else f"#{m.group(2)}"


# ---------------------------------------------------------------------------
# Union-find helpers (for rule 1)
# ---------------------------------------------------------------------------

def _uf_find(parent: list[int], i: int) -> int:
    root = i
    while parent[root] != root:
        root = parent[root]
    while parent[i] != root:
        parent[i], i = root, parent[i]
    return root


def _uf_union(parent: list[int], a: int, b: int) -> None:
    parent[_uf_find(parent, a)] = _uf_find(parent, b)


# ---------------------------------------------------------------------------
# Core grouping  (ports ClusterRemindersByRelationship)
# ---------------------------------------------------------------------------

def group_reminders(
    reminders: list[dict[str, Any]],
    clients: list[dict[str, Any]] | None = None,
) -> list[ReminderGroup]:
    """Cluster reminders by inferred relationship.

    Groups are ordered by size descending; the ``other`` bucket is always last.
    Reminder order within a group preserves the input order.
    """
    if clients is None:
        clients = load_client_mapping()

    placed: set[int] = set()
    clusters: list[ReminderGroup] = []

    # Rule 1 — shared GitHub URL (transitive union-find) -------------------
    github_idxs = [
        i for i, r in enumerate(reminders)
        if r.get("github_urls")
    ]
    if github_idxs:
        parent = list(range(len(reminders)))
        first_seen: dict[str, int] = {}
        for i in github_idxs:
            for url in (reminders[i].get("github_urls") or []):
                if url in first_seen:
                    _uf_union(parent, i, first_seen[url])
                else:
                    first_seen[url] = i

        by_root: dict[int, list[int]] = {}
        for i in github_idxs:
            root = _uf_find(parent, i)
            by_root.setdefault(root, []).append(i)

        for component in by_root.values():
            url_counts: dict[str, int] = {}
            for i in component:
                for url in (reminders[i].get("github_urls") or []):
                    url_counts[url] = url_counts.get(url, 0) + 1
            best_url = max(url_counts, key=lambda u: (url_counts[u], -list(url_counts).index(u)))
            for i in component:
                placed.add(i)
            clusters.append(ReminderGroup(
                kind="github",
                label=_github_label_from_url(best_url),
                reminders=tuple(reminders[i] for i in sorted(component)),
            ))

    # Rule 2 — same client -------------------------------------------------
    for client in clients:
        members = [i for i, r in enumerate(reminders) if i not in placed and _does_reminder_match_client(r, client)]
        if not members:
            continue
        for i in members:
            placed.add(i)
        clusters.append(ReminderGroup(
            kind="client",
            label=str(client.get("ClientName") or "Client"),
            reminders=tuple(reminders[i] for i in members),
        ))

    # Rule 3 — same channel (2+ members) -----------------------------------
    by_channel: dict[str, list[int]] = {}
    for i, r in enumerate(reminders):
        if i in placed:
            continue
        ch = r.get("original_channel_name")
        if ch:
            by_channel.setdefault(ch, []).append(i)
    for ch, members in by_channel.items():
        if len(members) < 2:
            continue
        for i in members:
            placed.add(i)
        clusters.append(ReminderGroup(
            kind="channel",
            label=f"#{ch}",
            reminders=tuple(reminders[i] for i in members),
        ))

    # Sort non-other clusters by size descending (stable)
    clusters.sort(key=lambda g: -len(g.reminders))

    # Rule 4 — Other -------------------------------------------------------
    leftover = [r for i, r in enumerate(reminders) if i not in placed]
    if leftover:
        clusters.append(ReminderGroup(kind="other", label="Other", reminders=tuple(leftover)))

    return clusters


# ---------------------------------------------------------------------------
# Connection surfacing
# ---------------------------------------------------------------------------

def find_connections(
    reminder: dict[str, Any],
    all_reminders: list[dict[str, Any]],
    clients: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return reminders related to *reminder* by GitHub URL, client, or channel.

    A reminder is never returned as a connection of itself.
    """
    if clients is None:
        clients = load_client_mapping()

    target_id = reminder.get("reminder_id")
    target_urls = set(reminder.get("github_urls") or [])
    target_channel = reminder.get("original_channel_name")

    # Which clients does the target belong to?
    target_clients = {
        client.get("ClientName")
        for client in clients
        if _does_reminder_match_client(reminder, client)
    }

    related: list[dict[str, Any]] = []
    for r in all_reminders:
        if r.get("reminder_id") == target_id:
            continue
        # Shared GitHub URL
        if target_urls and target_urls.intersection(r.get("github_urls") or []):
            related.append(r)
            continue
        # Same client
        if target_clients:
            r_clients = {
                c.get("ClientName")
                for c in clients
                if _does_reminder_match_client(r, c)
            }
            if target_clients & r_clients:
                related.append(r)
                continue
        # Same channel
        if target_channel and r.get("original_channel_name") == target_channel:
            related.append(r)

    return related


# ---------------------------------------------------------------------------
# DB readers
# ---------------------------------------------------------------------------

def load_active_reminders(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all active reminders from the DB as plain dicts, ordered by due date."""
    rows = conn.execute(
        """
        SELECT reminder_id, original_channel_name, original_channel_id,
               reminder_message_text, github_urls_json, state,
               should_post_on, created_on
        FROM   sleuth_reminders
        WHERE  is_active = 1
        ORDER  BY should_post_on ASC NULLS LAST, created_on ASC
        """
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        try:
            github_urls = json.loads(row[4] or "[]")
        except (json.JSONDecodeError, TypeError):
            github_urls = []
        result.append({
            "reminder_id":          row[0],
            "original_channel_name": row[1],
            "original_channel_id":  row[2],
            "reminder_message_text": row[3],
            "github_urls":          github_urls,
            "state":                row[5],
            "should_post_on":       row[6],
            "created_on":           row[7],
            "task_text":            extract_task_text(row[3]),
        })
    return result


def grouped_reminders_from_db(
    db_path: Path,
    clients: list[dict[str, Any]] | None = None,
) -> list[ReminderGroup]:
    """Convenience wrapper: open DB, load active reminders, group them."""
    conn = sqlite3.connect(db_path)
    try:
        reminders = load_active_reminders(conn)
    finally:
        conn.close()
    return group_reminders(reminders, clients=clients)
