"""GitHub source plugin: bounded activity scans and issue/PR synchronization."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, MutableMapping
import json
import platform
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

try:  # `resource` is absent on Windows, where HiQS still supports a local DB.
    import resource
except ImportError:  # pragma: no cover - covered by Windows packaging, not CI here.
    resource = None  # type: ignore[assignment]

from hiqs import config as hiqs_config
from hiqs.chunking import split_oversized
from hiqs.events import log_event
from hiqs.plugins import Candidate, Doc, Source, SyncReport


NETWORK_TIMEOUT_SECONDS = 15
API_CALL_LIMIT = 100
RSS_LIMIT_MB = 500
_ACTIVITY_EVENTS = frozenset({"closed", "reopened", "merged", "committed", "commented", "reviewed", "created"})


def _ensure_obligations_table(connection: Any) -> None:
    """Create the GitHub-owned receipts that are not part of the core item schema."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS github_item_obligations(
          repo TEXT NOT NULL,
          type TEXT NOT NULL,
          number INTEGER NOT NULL,
          requested_reviewer TEXT NOT NULL,
          due TEXT NOT NULL,
          PRIMARY KEY (repo, type, number))
        """
    )


def _settings(config: Mapping[str, Any]) -> tuple[str, list[str], str]:
    """Read GitHub settings without embedding an operator-specific default."""
    github = config.get("github", {})
    github = github if isinstance(github, Mapping) else {}
    login = github.get("login", config.get("github_login", ""))
    raw_repos = github.get("repos", config.get("github_repos", ()))
    base_url = github.get("api_url", config.get("github_api_url", "https://api.github.com"))
    repos = [repo.strip() for repo in raw_repos if isinstance(repo, str) and repo.strip()]
    return str(login or ""), repos, str(base_url).rstrip("/")


def _request_json(url: str, token: str | None, api_calls: list[int]) -> Any:
    """Perform one explicitly bounded GitHub request and decode its JSON body."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "hiqs"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    api_calls[0] += 1
    with urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _peak_rss_mb() -> float:
    """Return process peak RSS in MB across the platforms supported by HiQS."""
    if resource is None:
        return 0.0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(rss / (1024 * 1024 if platform.system() == "Darwin" else 1024), 2)


def _upsert_activity(connection: Any, login: str, events: list[Mapping[str, Any]], counts: dict[str, int]) -> None:
    """Aggregate user events by repo/day and upsert only changed activity rows."""
    grouped: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for event in events:
        repo = event.get("repo", {})
        repo_name = repo.get("name") if isinstance(repo, Mapping) else None
        created_at = event.get("created_at")
        event_type = event.get("type")
        if isinstance(repo_name, str) and isinstance(created_at, str) and isinstance(event_type, str):
            grouped[(repo_name, created_at[:10])][event_type] += 1

    for (repo, day), event_counts in grouped.items():
        counts_json = json.dumps(dict(sorted(event_counts.items())), separators=(",", ":"), sort_keys=True)
        existing = connection.execute(
            "SELECT counts_json FROM github_activity WHERE login = ? AND repo = ? AND day = ?",
            (login, repo, day),
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO github_activity(login, repo, day, counts_json) VALUES (?, ?, ?, ?)",
                (login, repo, day, counts_json),
            )
            counts["inserted"] += 1
        elif existing[0] == counts_json:
            counts["unchanged"] += 1
        else:
            connection.execute(
                "UPDATE github_activity SET counts_json = ? WHERE login = ? AND repo = ? AND day = ?",
                (counts_json, login, repo, day),
            )
            counts["updated"] += 1


def _actual_activity_by_number(events: list[Mapping[str, Any]]) -> dict[int, str]:
    """Return the newest non-metadata GitHub event for each issue or pull request."""
    activity: dict[int, str] = {}
    for event in events:
        issue = event.get("issue", {})
        number = issue.get("number") if isinstance(issue, Mapping) else None
        timestamp = event.get("created_at")
        if event.get("event") not in _ACTIVITY_EVENTS or not isinstance(number, int) or not isinstance(timestamp, str):
            continue
        if timestamp > activity.get(number, ""):
            activity[number] = timestamp
    return activity


def _item_row(
    repo: str, item: Mapping[str, Any], activity: Mapping[int, str]
) -> tuple[str, str, int, str, str, str, str, str, str, str, str] | None:
    """Normalize one issue/PR, rejecting shells that cannot provide a useful receipt."""
    number = item.get("number")
    title = item.get("title")
    url = item.get("html_url")
    user = item.get("user", {})
    author = user.get("login") if isinstance(user, Mapping) else None
    updated_at = item.get("updated_at")
    created_at = item.get("created_at")
    if not isinstance(number, int) or not all(isinstance(value, str) and value.strip() for value in (title, url, author, updated_at, created_at)):
        return None
    assignee_data = item.get("assignee", {})
    assignee = assignee_data.get("login", "") if isinstance(assignee_data, Mapping) else ""
    item_type = "pull_request" if isinstance(item.get("pull_request"), Mapping) else "issue"
    # `updated_at` is deliberately never used here: label and assignee edits are metadata.
    activity_at = activity.get(number) or item.get("closed_at") or created_at
    if not isinstance(activity_at, str) or not activity_at:
        return None
    return (repo, item_type, number, title, str(item.get("body") or ""), str(item.get("state") or ""), url, author, str(assignee or ""), updated_at, activity_at)


def _obligation_row(repo: str, item: Mapping[str, Any], item_type: str, number: int) -> tuple[str, str, int, str, str]:
    """Extract only explicitly supplied review and deadline obligations from one item."""
    reviewers = item.get("requested_reviewers")
    requested_reviewer = ""
    if isinstance(reviewers, list):
        for reviewer in reviewers:
            login = reviewer.get("login") if isinstance(reviewer, Mapping) else None
            if isinstance(login, str) and login.strip():
                requested_reviewer = login.strip()
                break

    due = item.get("due_on")
    milestone = item.get("milestone")
    if not isinstance(due, str) or not due.strip():
        due = milestone.get("due_on") if isinstance(milestone, Mapping) else ""
    if not isinstance(due, str) or not due.strip():
        due = milestone.get("title") if isinstance(milestone, Mapping) else ""
    return (repo, item_type, number, requested_reviewer, due.strip() if isinstance(due, str) else "")


def _upsert_items(connection: Any, repo: str, items: list[Mapping[str, Any]], activity: Mapping[int, str], counts: dict[str, int]) -> list[str]:
    """Upsert item rows by their stable GitHub identity; never delete absent rows."""
    watermarks: list[str] = []
    for item in items:
        row = _item_row(repo, item, activity)
        if row is None:
            counts["rejected"] += 1
            continue
        obligation = _obligation_row(row[0], item, row[1], row[2])
        watermarks.append(row[-2])
        existing = connection.execute(
            "SELECT title, body, state, url, author, assignee, updated_at, activity_at "
            "FROM github_items WHERE repo = ? AND type = ? AND number = ?",
            (row[0], row[1], row[2]),
        ).fetchone()
        payload = row[3:]
        if existing is None:
            connection.execute(
                "INSERT INTO github_items(repo, type, number, title, body, state, url, author, assignee, updated_at, activity_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
            counts["inserted"] += 1
        elif tuple(existing) == payload:
            counts["unchanged"] += 1
        else:
            connection.execute(
                "UPDATE github_items SET title = ?, body = ?, state = ?, url = ?, author = ?, assignee = ?, "
                "updated_at = ?, activity_at = ? WHERE repo = ? AND type = ? AND number = ?",
                (*payload, row[0], row[1], row[2]),
            )
            counts["updated"] += 1
        connection.execute(
            "INSERT INTO github_item_obligations(repo, type, number, requested_reviewer, due) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(repo, type, number) DO UPDATE SET requested_reviewer = excluded.requested_reviewer, due = excluded.due",
            obligation,
        )
    return watermarks


def candidates(connection: Any, _config: Mapping[str, Any]) -> Iterable[Candidate]:
    """Expose GitHub work as attested candidates without assigning a rank or score."""
    rows = connection.execute(
        """
        SELECT item.type, item.number, item.title, item.url, item.author, item.assignee,
               item.activity_at, COALESCE(obligation.requested_reviewer, ''), COALESCE(obligation.due, '')
        FROM github_items AS item
        LEFT JOIN github_item_obligations AS obligation
          ON obligation.repo = item.repo AND obligation.type = item.type AND obligation.number = item.number
        """
    ).fetchall()
    return [_candidate_from_row(row) for row in rows]


def docs(connection: Any) -> Iterable[Doc]:
    """Expose each persisted GitHub issue or pull request as searchable documents.

    An issue body is unbounded, and this provider used to emit each one whole: only 11.7% of
    GitHub documents fit MiniLM's 256-token window, so the overwhelming majority were indexed
    from their first paragraph and the discussion below it — where decisions actually get made
    — was never embedded. Long bodies are split under the shared cap (§6.3).
    """
    rows = connection.execute(
        """
        SELECT repo, number, title, body, url, activity_at, author
        FROM github_items
        ORDER BY repo, number
        """
    ).fetchall()
    documents: list[Doc] = []
    for repo, number, title, body, url, activity_at, author in rows:
        parts = split_oversized(body)
        for index, part in enumerate(parts, start=1):
            # An item that fits keeps its bare id, so the common case is unchanged and the
            # §6.1 id contract still holds for it. Only a split item takes a part suffix.
            doc_id = f"github:{repo}#{number}"
            if len(parts) > 1:
                doc_id = f"{doc_id}:{index}"
            documents.append(
                Doc(
                    source="github",
                    id=doc_id,
                    title=title,
                    body=part,
                    url=url,
                    ts=activity_at,
                    project=repo,
                    author=author,
                    unit=repo,
                )
            )
    return documents


def _candidate_from_row(row: tuple[str, int, str, str, str, str, str, str, str]) -> Candidate:
    """Build a hand-verifiable candidate receipt from one persisted GitHub item."""
    item_type, number, title, url, author, assignee, activity_at, requested_reviewer, due = row
    owed_by = assignee or requested_reviewer
    item_label = "PR" if item_type == "pull_request" else "Issue"
    if assignee:
        obligation = f"assigned to {assignee}"
    elif requested_reviewer:
        obligation = f"review requested from {requested_reviewer}"
    else:
        obligation = "no assignee or requested reviewer recorded"
    due_receipt = f", due {due}" if due else ""
    return Candidate(
        title=title,
        source="github",
        evidence=f"{item_label} #{number}, {obligation}, last activity {activity_at}{due_receipt}",
        why="This GitHub item has recent recorded activity and may require follow-up.",
        ts=activity_at,
        url=url,
        author=author,
        owed_by=owed_by,
        due=due,
    )


def _record(status: str, payload: Mapping[str, Any]) -> None:
    """Keep event writes at the core-owned observability seam."""
    log_event("sync.github", "github", status, payload)


def fetch(connection: Any, config: Mapping[str, Any]) -> SyncReport:
    """Refetch a bounded GitHub window, upsert it, and advance watermark on total success only."""
    counts = {"inserted": 0, "updated": 0, "unchanged": 0, "skipped": 0, "rejected": 0, "pruned": 0}
    errors: list[str] = []
    units_ok: list[str] = []
    api_calls = [0]
    login, repos, api_base = _settings(config)
    token = hiqs_config.secret("GITHUB_TOKEN")
    watermarks: list[str] = []

    _ensure_obligations_table(connection)

    if login:
        try:
            events = _request_json(f"{api_base}/users/{quote(login, safe='')}/events?per_page=100", token, api_calls)
            if not isinstance(events, list):
                raise ValueError("unexpected activity response")
            with connection:
                _upsert_activity(connection, login, events, counts)
            units_ok.append("activity")
        except Exception:
            errors.append("GitHub activity request failed")

    for repo in repos:
        encoded_repo = quote(repo, safe="/")
        try:
            items = _request_json(f"{api_base}/repos/{encoded_repo}/issues?state=all&sort=updated&direction=desc&per_page=100", token, api_calls)
            events = _request_json(f"{api_base}/repos/{encoded_repo}/issues/events?per_page=100", token, api_calls)
            if not isinstance(items, list) or not isinstance(events, list):
                raise ValueError("unexpected item response")
            with connection:
                watermarks.extend(_upsert_items(connection, repo, items, _actual_activity_by_number(events), counts))
            units_ok.append(repo)
        except Exception:
            errors.append("GitHub item request failed")

    peak_rss_mb = _peak_rss_mb()
    meta = {"api_calls": api_calls[0], "peak_rss_mb": peak_rss_mb}
    if api_calls[0] > API_CALL_LIMIT or peak_rss_mb > RSS_LIMIT_MB:
        _record("warn", meta)
    elif errors:
        _record("error", {"failed_units": len(errors)})
    else:
        _record("ok", meta)

    # The mutable watermark is an optional host-owned cursor.  It is untouched
    # after any failed request so the next run refetches the whole window.
    watermark = config.get("watermark")
    if not errors and isinstance(watermark, MutableMapping) and watermarks:
        watermark["github"] = max(watermarks)

    return SyncReport(counts=counts, errors=errors, meta=meta, units_ok=tuple(units_ok))


SOURCE = Source(name="github", fetch=fetch, docs=docs, candidates=candidates)
