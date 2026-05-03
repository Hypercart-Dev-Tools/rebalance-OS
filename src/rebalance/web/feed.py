"""
Build the unified activity feed shown on the dashboard.

A feed row is the smallest unit the page renders — a single commit, PR
event, workflow run, or local-device session. Each row carries enough
context for a human to understand what happened and to deep-link into
GitHub if they want more.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rebalance.ingest.agent_tags import classify
from rebalance.web import sources


@dataclass
class CIBadge:
    status: str | None = None
    conclusion: str | None = None
    url: str | None = None
    name: str | None = None

    @property
    def color(self) -> str:
        c = (self.conclusion or "").lower()
        s = (self.status or "").lower()
        if c == "success":
            return "green"
        if c in {"failure", "timed_out", "cancelled", "startup_failure",
                 "action_required", "stale"}:
            return "red"
        if s in {"in_progress", "queued", "pending", "waiting"}:
            return "yellow"
        if not c and not s:
            return "grey"
        return "grey"


@dataclass
class FeedRow:
    when: str
    repo: str
    branch: str | None
    kind: str
    title: str
    actor: str | None
    source_tag: str
    links: dict[str, str | None] = field(default_factory=dict)
    ci: CIBadge | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.ci is not None:
            d["ci"]["color"] = self.ci.color
        return d


def _commit_title(message: str | None) -> str:
    if not message:
        return ""
    return message.split("\n", 1)[0].strip()[:200]


def build_feed(database_path: Path, mirror_path: Path | None, since: str | None) -> list[dict[str, Any]]:
    cutoff = sources._parse_since(since)

    rows: list[FeedRow] = []

    for c in sources.read_github_commits(database_path, cutoff):
        title = _commit_title(c.get("message"))
        branch = c.get("run_branch")
        ci = None
        if c.get("run_url") or c.get("run_status") or c.get("run_conclusion"):
            ci = CIBadge(
                status=c.get("run_status"),
                conclusion=c.get("run_conclusion"),
                url=c.get("run_url"),
                name=c.get("run_name"),
            )
        rows.append(
            FeedRow(
                when=c.get("committed_at") or "",
                repo=c["repo"],
                branch=branch,
                kind="commit",
                title=title or c.get("sha", "")[:7],
                actor=c.get("author"),
                source_tag=classify(
                    branch=branch,
                    author_login=c.get("author"),
                    commit_message=c.get("message"),
                ),
                links={
                    "commit": c.get("commit_url"),
                    "pr": None,
                    "run": ci.url if ci else None,
                },
                ci=ci,
            )
        )

    for p in sources.read_pull_requests(database_path, cutoff):
        if p.get("merged_at"):
            kind = "pr_merged"
            when = p["merged_at"]
        elif p.get("state") == "closed":
            kind = "pr_closed"
            when = p.get("updated_at") or p.get("created_at") or ""
        else:
            kind = "pr_opened"
            when = p.get("created_at") or p.get("updated_at") or ""
        rows.append(
            FeedRow(
                when=when or "",
                repo=p["repo"],
                branch=p.get("branch"),
                kind=kind,
                title=f"#{p['number']} {p.get('title') or ''}".strip(),
                actor=p.get("author"),
                source_tag=classify(
                    branch=p.get("branch"),
                    author_login=p.get("author"),
                ),
                links={
                    "commit": None,
                    "pr": p.get("html_url"),
                    "run": None,
                },
            )
        )

    for w in sources.read_workflow_runs(database_path, cutoff):
        ci = CIBadge(
            status=w.get("status"),
            conclusion=w.get("conclusion"),
            url=w.get("run_url"),
            name=w.get("workflow_name"),
        )
        rows.append(
            FeedRow(
                when=w.get("created_at") or "",
                repo=w["repo"],
                branch=w.get("head_branch"),
                kind="workflow_run",
                title=f"{w.get('workflow_name') or 'workflow'} · {w.get('event') or ''}".strip(" ·"),
                actor=w.get("actor_login"),
                source_tag=classify(
                    branch=w.get("head_branch"),
                    author_login=w.get("actor_login"),
                ),
                links={"commit": None, "pr": None, "run": w.get("run_url")},
                ci=ci,
            )
        )

    for d in sources.read_device_pulses(mirror_path or Path("/nonexistent"), cutoff):
        rows.append(
            FeedRow(
                when=d.when,
                repo=d.repo,
                branch=d.branch,
                kind="local_session",
                title=d.subject,
                actor=d.device,
                source_tag="local-vscode",
                links={"commit": None, "pr": None, "run": None},
            )
        )

    rows.sort(key=lambda r: r.when, reverse=True)
    return [r.to_dict() for r in rows[:300]]


__all__ = ["build_feed", "CIBadge", "FeedRow"]
