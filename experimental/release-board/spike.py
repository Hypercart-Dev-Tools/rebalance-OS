#!/usr/bin/env python3
"""Release Board spike — per-repo "in flight right now" view.

Reads $REBALANCE_DB and renders for one repo:
- A Mermaid flowchart of milestones → PRs → issues (relationship view)
- HTML cards for open issues and open PRs
- ⭐ stars on items referenced by an active Sleuth reminder
- Footer with the last 3 published releases

Usage:
    python spike.py                                # text summary, default repo
    python spike.py --repo owner/name              # text summary, specific repo
    python spike.py --serve                        # HTTP on :8766
    python spike.py --serve --port N               # custom port

The HTTP page auto-refreshes once per day. URL: /?repo=owner/name
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

REFRESH_SECONDS = 86_400  # 24h

GITHUB_URL_RE = re.compile(
    r"github\.com/([^/]+/[^/]+)/(issues|pull)/(\d+)", re.IGNORECASE
)
# GitHub closes-keyword references in PR bodies (closes/fixes/resolves #N).
PR_CLOSES_RE = re.compile(r"\b(?:closes?|fixes?|resolves?)\s+#(\d+)", re.IGNORECASE)


@dataclass
class Item:
    item_type: str          # 'issue' | 'pull_request'
    number: int
    title: str
    state: str
    is_draft: bool = False
    is_merged: bool = False
    base_ref: str | None = None
    head_ref: str | None = None
    milestone_title: str | None = None
    labels: list[str] = field(default_factory=list)
    review_decision: str | None = None
    check_status: str | None = None
    html_url: str | None = None
    updated_at: str | None = None
    starred: bool = False           # set by Sleuth match
    closes_issues: list[int] = field(default_factory=list)  # PR → issue numbers


@dataclass
class Release:
    tag_name: str
    name: str | None
    published_at: str | None
    html_url: str | None


@dataclass
class Milestone:
    title: str
    due_on: str | None
    open_issues: int
    closed_issues: int
    state: str


@dataclass
class ClosedRef:
    """A closed issue referenced by an open PR. Drawn grayed in topology."""
    number: int
    title: str


@dataclass
class Board:
    repo: str
    milestones: list[Milestone]
    open_issues: list[Item]
    open_prs: list[Item]
    closed_refs: dict[int, ClosedRef]   # issue_number → record
    recent_releases: list[Release]
    starred_count: int
    sleuth_match_count: int
    generated_at: str


# ── DB access ───────────────────────────────────────────────────────────────
def parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def load_starred_targets(conn: sqlite3.Connection, repo: str) -> set[tuple[str, int]]:
    """Return {(item_type, number)} for issues/PRs referenced by active Sleuth reminders."""
    rows = conn.execute(
        "SELECT github_urls_json FROM sleuth_reminders WHERE is_active = 1"
    ).fetchall()
    starred: set[tuple[str, int]] = set()
    for (raw,) in rows:
        for url in parse_json_list(raw):
            m = GITHUB_URL_RE.search(url or "")
            if not m:
                continue
            url_repo, kind, num = m.group(1), m.group(2), int(m.group(3))
            if url_repo.lower() != repo.lower():
                continue
            item_type = "pull_request" if kind == "pull" else "issue"
            starred.add((item_type, num))
    return starred


def load_close_links(conn: sqlite3.Connection, repo: str) -> dict[int, list[int]]:
    """Map pull_request_number → [issue_numbers] from github_links (kind='closes' only).

    The github_links table has both 'closes' and 'mentions' rows; mentions
    aren't release-planning relevant, so we filter to closes here. We
    additionally augment from PR body text via load_body_close_refs() since
    not every "Closes #N" reference makes it into github_links.
    """
    rows = conn.execute(
        """
        SELECT source_number, target_number, source_type, target_type
        FROM github_links
        WHERE repo_full_name = ? AND link_kind = 'closes'
        """,
        (repo,),
    ).fetchall()
    pr_to_issues: dict[int, set[int]] = {}
    for src_num, tgt_num, src_type, tgt_type in rows:
        if src_type == "pull_request" and tgt_type == "issue":
            pr_to_issues.setdefault(src_num, set()).add(tgt_num)
        elif src_type == "issue" and tgt_type == "pull_request":
            pr_to_issues.setdefault(tgt_num, set()).add(src_num)
    return {pr: sorted(issues) for pr, issues in pr_to_issues.items()}


def augment_with_body_refs(
    conn: sqlite3.Connection, repo: str, pr_to_issues: dict[int, list[int]]
) -> dict[int, list[int]]:
    """Parse open-PR bodies for 'closes/fixes/resolves #N' and merge into pr_to_issues."""
    rows = conn.execute(
        """
        SELECT number, body FROM github_items
        WHERE repo_full_name = ? AND item_type = 'pull_request' AND state = 'open'
        """,
        (repo,),
    ).fetchall()
    merged = {pr: set(refs) for pr, refs in pr_to_issues.items()}
    for pr_num, body in rows:
        for m in PR_CLOSES_RE.finditer(body or ""):
            merged.setdefault(pr_num, set()).add(int(m.group(1)))
    return {pr: sorted(refs) for pr, refs in merged.items()}


def fetch_closed_refs(
    conn: sqlite3.Connection, repo: str, issue_numbers: set[int]
) -> dict[int, ClosedRef]:
    """Fetch title/state for any of the given issue numbers that exist in the DB."""
    if not issue_numbers:
        return {}
    placeholders = ",".join("?" * len(issue_numbers))
    rows = conn.execute(
        f"""
        SELECT number, title, state
        FROM github_items
        WHERE repo_full_name = ? AND item_type = 'issue' AND number IN ({placeholders})
        """,
        (repo, *sorted(issue_numbers)),
    ).fetchall()
    return {r[0]: ClosedRef(number=r[0], title=r[1] or "") for r in rows if r[2] == "closed"}


def fetch_active_milestones(conn: sqlite3.Connection, repo: str) -> list[Milestone]:
    """Open milestones, sorted by due_on (NULLs last), then by title."""
    rows = conn.execute(
        """
        SELECT title, due_on, open_issues, closed_issues, state
        FROM github_milestones
        WHERE repo_full_name = ? AND state = 'open'
        """,
        (repo,),
    ).fetchall()
    ms = [Milestone(title=r[0], due_on=r[1], open_issues=r[2], closed_issues=r[3], state=r[4]) for r in rows]
    ms.sort(key=lambda m: (m.due_on is None, m.due_on or "", m.title))
    return ms


def fetch_open_items(
    conn: sqlite3.Connection, repo: str, starred: set[tuple[str, int]],
    pr_to_issues: dict[int, list[int]],
) -> tuple[list[Item], list[Item]]:
    rows = conn.execute(
        """
        SELECT item_type, number, title, state, is_draft, is_merged,
               base_ref, head_ref, milestone_title, labels_json,
               review_decision, check_status, html_url, updated_at
        FROM github_items
        WHERE repo_full_name = ? AND state = 'open'
        ORDER BY updated_at DESC
        """,
        (repo,),
    ).fetchall()
    issues, prs = [], []
    for r in rows:
        labels = [lbl.get("name", "") for lbl in parse_json_list(r[9]) if isinstance(lbl, dict)]
        item = Item(
            item_type=r[0],
            number=r[1],
            title=r[2] or "",
            state=r[3] or "",
            is_draft=bool(r[4]),
            is_merged=bool(r[5]),
            base_ref=r[6],
            head_ref=r[7],
            milestone_title=r[8],
            labels=labels,
            review_decision=r[10],
            check_status=r[11],
            html_url=r[12],
            updated_at=r[13],
            starred=(r[0], r[1]) in starred,
            closes_issues=pr_to_issues.get(r[1], []) if r[0] == "pull_request" else [],
        )
        if item.item_type == "issue":
            issues.append(item)
        else:
            prs.append(item)
    return issues, prs


def fetch_recent_releases(conn: sqlite3.Connection, repo: str, limit: int = 3) -> list[Release]:
    rows = conn.execute(
        """
        SELECT tag_name, name, published_at, html_url
        FROM github_releases
        WHERE repo_full_name = ? AND is_draft = 0 AND published_at IS NOT NULL
        ORDER BY published_at DESC LIMIT ?
        """,
        (repo, limit),
    ).fetchall()
    return [Release(*r) for r in rows]


def list_repos(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    return conn.execute(
        "SELECT repo_full_name, COUNT(*) FROM github_items GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()


def collect(db_path: Path, repo: str) -> Board:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        starred = load_starred_targets(conn, repo)
        pr_to_issues = load_close_links(conn, repo)
        pr_to_issues = augment_with_body_refs(conn, repo, pr_to_issues)
        issues, prs = fetch_open_items(conn, repo, starred, pr_to_issues)
        milestones = fetch_active_milestones(conn, repo)
        releases = fetch_recent_releases(conn, repo)
        # Resolve closed-issue references — scoped to references made by OPEN PRs only.
        # Otherwise the shipped-issues subgraph would include issues closed by
        # already-merged PRs, which are out of scope for "in flight right now."
        open_pr_referenced = {n for pr in prs for n in pr.closes_issues}
        open_numbers = {i.number for i in issues}
        closed_refs = fetch_closed_refs(conn, repo, open_pr_referenced - open_numbers)
    starred_count = sum(1 for i in issues + prs if i.starred)
    return Board(
        repo=repo,
        milestones=milestones,
        open_issues=issues,
        open_prs=prs,
        closed_refs=closed_refs,
        recent_releases=releases,
        starred_count=starred_count,
        sleuth_match_count=len(starred),
        generated_at=now,
    )


# ── Mermaid rendering ───────────────────────────────────────────────────────
def mermaid_id(prefix: str, n: int) -> str:
    return f"{prefix}{n}"


def render_mermaid(board: Board, max_issues_per_milestone: int = 8) -> str:
    """Build a milestone-centric flowchart for release planning.

    Layout strategy:
    - Each open milestone is a subgraph, ordered left-to-right by due date.
    - Open issues with a milestone go inside their milestone's subgraph.
    - Open PRs sit in a separate "Open PRs" subgraph (PRs in this codebase
      typically aren't milestoned themselves).
    - For each PR, draw arrows to the issues it closes — including closed
      issues, drawn as grayed nodes ("✓ shipped"). This is the actual flow
      signal: "this PR ships these tickets."
    - Unmilestoned open issues are NOT in the topology; they're backlog
      and live in the cards section below.
    """
    issues_by_num = {i.number: i for i in board.open_issues}
    issues_by_milestone: dict[str, list[Item]] = {}
    for issue in board.open_issues:
        if issue.milestone_title:
            issues_by_milestone.setdefault(issue.milestone_title, []).append(issue)

    lines = ["flowchart LR"]
    ms_subgraphs: list[tuple[str, str]] = []  # (subgraph_id, milestone_title)

    # Milestone subgraphs (sorted by due date via fetch_active_milestones)
    for idx, ms in enumerate(board.milestones):
        items_in_ms = issues_by_milestone.get(ms.title, [])[:max_issues_per_milestone]
        if not items_in_ms and ms.open_issues == 0:
            continue  # nothing actionable in this milestone
        sgid = f"ms{idx}"
        ms_subgraphs.append((sgid, ms.title))
        total = ms.open_issues + ms.closed_issues
        progress = f"{ms.closed_issues}/{total}"
        due = f"due {ms.due_on[:10]}" if ms.due_on else "no due date"
        label = f"📦 {ms.title}<br/><i>{due} · {progress} closed</i>"
        lines.append(f'    subgraph {sgid} ["{escape_mermaid(label)}"]')
        for issue in items_in_ms:
            nid = mermaid_id("I", issue.number)
            star = "⭐ " if issue.starred else ""
            t = escape_mermaid(truncate(issue.title, 40))
            lines.append(f'        {nid}["{star}#{issue.number}<br/>{t}"]')
            lines.append(f"        class {nid} {'issue_starred' if issue.starred else 'issue'};")
        lines.append("    end")

    # Connect milestones in due-date order so the layout flows left→right
    for (a, _), (b, _) in zip(ms_subgraphs, ms_subgraphs[1:]):
        lines.append(f"    {a} -.-> {b}")

    # Open PRs subgraph (these typically aren't milestoned in BinoidCBD's flow)
    if board.open_prs:
        lines.append(f'    subgraph prs ["⚡ Open PRs &#40;{len(board.open_prs)}&#41;"]')
        for pr in board.open_prs:
            nid = mermaid_id("P", pr.number)
            star = "⭐ " if pr.starred else ""
            draft = " &#40;draft&#41;" if pr.is_draft else ""
            target = f"→{pr.base_ref}" if pr.base_ref else ""
            t = escape_mermaid(truncate(pr.title, 40))
            lines.append(f'        {nid}["{star}PR #{pr.number}{draft}<br/>{t}<br/><i>{escape_mermaid(target)}</i>"]')
            cls = "pr_starred" if pr.starred else ("pr_draft" if pr.is_draft else "pr")
            lines.append(f"        class {nid} {cls};")
        lines.append("    end")

    # Closed-issue ghost nodes (referenced by open PRs but already shipped)
    referenced_closed = sorted(board.closed_refs.keys())
    if referenced_closed:
        lines.append('    subgraph shipped ["✓ Shipped issues referenced by open PRs"]')
        for num in referenced_closed:
            ref = board.closed_refs[num]
            nid = mermaid_id("C", num)
            t = escape_mermaid(truncate(ref.title, 40))
            lines.append(f'        {nid}["#{num} ✓<br/>{t}"]')
            lines.append(f"        class {nid} closed;")
        lines.append("    end")

    # Edges: PR --closes--> issue (open or closed)
    for pr in board.open_prs:
        for issue_num in pr.closes_issues:
            pid = mermaid_id("P", pr.number)
            if issue_num in issues_by_num:
                lines.append(f"    {pid} --> {mermaid_id('I', issue_num)}")
            elif issue_num in board.closed_refs:
                lines.append(f"    {pid} -.-> {mermaid_id('C', issue_num)}")

    # Styling
    lines += [
        "    classDef issue fill:#fff,stroke:#9ca3af,color:#374151;",
        "    classDef issue_starred fill:#fef3c7,stroke:#b45309,stroke-width:3px,color:#78350f;",
        "    classDef pr fill:#dcfce7,stroke:#166534,color:#14532d;",
        "    classDef pr_draft fill:#f3f4f6,stroke:#6b7280,color:#4b5563,stroke-dasharray: 4 2;",
        "    classDef pr_starred fill:#fef3c7,stroke:#b45309,stroke-width:3px,color:#78350f;",
        "    classDef closed fill:#f3f4f6,stroke:#9ca3af,color:#9ca3af,stroke-dasharray: 3 3;",
    ]
    return "\n".join(lines)


def truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def escape_mermaid(s: str) -> str:
    """Sanitize text for inclusion inside a mermaid double-quoted node label.

    Mermaid 10.x has flaky support for &quot; HTML entities inside ["..."]
    labels (the parser breaks the label early), so we substitute single
    quotes outright. Parens, slashes, hyphens, and colons render fine
    inside double-quoted labels in current mermaid versions.
    """
    if not s:
        return ""
    return " ".join(s.replace('"', "'").split())


# ── HTML rendering ──────────────────────────────────────────────────────────
def render_html(board: Board, all_repos: list[tuple[str, int]]) -> str:
    mermaid_src = render_mermaid(board)
    repo_options = "\n".join(
        f'<option value="{escape(r)}" {"selected" if r == board.repo else ""}>{escape(r)} ({n})</option>'
        for r, n in all_repos
    )

    issue_cards = "\n".join(item_card(i, kind="issue") for i in board.open_issues) or _empty("No open issues.")
    pr_cards = "\n".join(item_card(p, kind="pr") for p in board.open_prs) or _empty("No open PRs.")
    release_rows = "\n".join(
        f'<li><a href="{escape(r.html_url or "#")}" target="_blank"><code>{escape(r.tag_name)}</code></a> '
        f'· <span class="muted">{escape(r.published_at or "")[:10]}</span> '
        f'· {escape(r.name or "")}</li>'
        for r in board.recent_releases
    ) or "<li class='muted'>No published releases yet.</li>"

    return f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="{REFRESH_SECONDS}">
<title>Release Board · {escape(board.repo)}</title>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{ startOnLoad: true, theme: 'default', flowchart: {{ htmlLabels: true, curve: 'basis' }} }});
</script>
<style>
  body {{ font: 14px -apple-system, system-ui, sans-serif; padding: 24px; max-width: 1400px; margin: 0 auto; color: #1f2328; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; color: #656d76; margin: 24px 0 12px; }}
  .sub {{ color: #656d76; font-size: 12px; margin-bottom: 16px; }}
  .muted {{ color: #656d76; }}
  select {{ font: inherit; padding: 4px 8px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .col h2 {{ display: flex; align-items: baseline; gap: 8px; }}
  .col h2 .count {{ font-weight: 400; color: #6e7781; font-size: 12px; }}
  .card {{ border: 1px solid #d0d7de; border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; }}
  .card.starred {{ border-color: #b45309; background: #fefce8; }}
  .card .num {{ font-family: ui-monospace, Menlo, monospace; color: #6e7781; font-size: 12px; }}
  .card .title {{ font-weight: 500; margin: 2px 0 4px; }}
  .card .meta {{ font-size: 11px; color: #6e7781; }}
  .card .star {{ color: #b45309; font-weight: 700; }}
  .pill {{ display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 10px; margin-right: 4px; background: #eaeef2; color: #424a53; }}
  .pill.target {{ background: #ddf4ff; color: #0969da; }}
  .pill.draft {{ background: #f3f4f6; color: #6b7280; }}
  .pill.merged {{ background: #ddd5f3; color: #5a32a3; }}
  .pill.review-approved {{ background: #d1f3d1; color: #1a7f37; }}
  .pill.review-changes_requested {{ background: #ffd6cc; color: #cf222e; }}
  .pill.check-success {{ background: #d1f3d1; color: #1a7f37; }}
  .pill.check-failure {{ background: #ffd6cc; color: #cf222e; }}
  .mermaid-wrap {{ border: 1px solid #d0d7de; border-radius: 6px; padding: 16px; overflow: auto; background: #f6f8fa; }}
  ul.releases {{ list-style: none; padding: 0; margin: 0; }}
  ul.releases li {{ padding: 6px 0; border-bottom: 1px solid #eaeef2; }}
  .empty {{ padding: 16px; text-align: center; color: #6e7781; font-style: italic; }}
  form {{ display: inline; }}
</style>
</head><body>
<h1>📦 Release board · {escape(board.repo)}</h1>
<div class="sub">
  Generated {escape(board.generated_at)} · auto-refresh every 24h ·
  <form><label>Repo: <select name="repo" onchange="this.form.submit()">{repo_options}</select></label></form> ·
  ⭐ {board.starred_count} starred (Sleuth-linked)
</div>

<h2>Topology</h2>
<div class="mermaid-wrap">
<pre class="mermaid">
{mermaid_src}
</pre>
</div>

<div class="grid">
  <div class="col">
    <h2>Open issues <span class="count">({len(board.open_issues)})</span></h2>
    {issue_cards}
  </div>
  <div class="col">
    <h2>Open PRs <span class="count">({len(board.open_prs)})</span></h2>
    {pr_cards}
  </div>
</div>

<h2>Recent releases</h2>
<ul class="releases">
{release_rows}
</ul>
</body></html>"""


def item_card(item: Item, kind: str) -> str:
    starred_cls = " starred" if item.starred else ""
    star_marker = '<span class="star">⭐ </span>' if item.starred else ""
    pills = []
    if kind == "pr":
        if item.is_draft:
            pills.append('<span class="pill draft">draft</span>')
        if item.base_ref:
            pills.append(f'<span class="pill target">→ {escape(item.base_ref)}</span>')
        if item.review_decision:
            pills.append(f'<span class="pill review-{escape(item.review_decision.lower())}">{escape(item.review_decision.lower())}</span>')
        if item.check_status:
            pills.append(f'<span class="pill check-{escape(item.check_status.lower())}">CI {escape(item.check_status.lower())}</span>')
        if item.closes_issues:
            pills.append(f'<span class="pill">closes #{", #".join(str(n) for n in item.closes_issues)}</span>')
    if item.milestone_title:
        pills.append(f'<span class="pill">📦 {escape(item.milestone_title)}</span>')
    for lbl in item.labels[:3]:
        pills.append(f'<span class="pill">{escape(lbl)}</span>')
    return f"""<div class="card{starred_cls}">
  <div class="num">#{item.number}</div>
  <div class="title">{star_marker}<a href="{escape(item.html_url or '#')}" target="_blank">{escape(item.title)}</a></div>
  <div class="meta">{''.join(pills)}</div>
</div>"""


def _empty(msg: str) -> str:
    return f'<div class="empty">{escape(msg)}</div>'


# ── Text rendering ──────────────────────────────────────────────────────────
def render_text(board: Board) -> str:
    out = [f"Repo: {board.repo}", f"Generated: {board.generated_at}", ""]
    out.append(f"Open issues: {len(board.open_issues)}  |  Open PRs: {len(board.open_prs)}  |  ⭐ Starred: {board.starred_count}")
    out.append("")
    if board.open_prs:
        out.append("OPEN PRS")
        for p in board.open_prs[:20]:
            star = "⭐ " if p.starred else "  "
            target = f" →{p.base_ref}" if p.base_ref else ""
            draft = " [draft]" if p.is_draft else ""
            closes = f"  closes #{','.join(str(n) for n in p.closes_issues)}" if p.closes_issues else ""
            out.append(f"  {star}#{p.number}{target}{draft}  {truncate(p.title, 70)}{closes}")
        out.append("")
    if board.open_issues:
        out.append("OPEN ISSUES")
        for i in board.open_issues[:20]:
            star = "⭐ " if i.starred else "  "
            ms = f" [{i.milestone_title}]" if i.milestone_title else ""
            out.append(f"  {star}#{i.number}{ms}  {truncate(i.title, 70)}")
        out.append("")
    if board.recent_releases:
        out.append("RECENT RELEASES")
        for r in board.recent_releases:
            out.append(f"  {r.tag_name:<14} {(r.published_at or '')[:10]}  {r.name or ''}")
    return "\n".join(out)


# ── HTTP server ─────────────────────────────────────────────────────────────
def make_handler(db_path: Path, default_repo: str | None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

        def do_GET(self):
            url = urlparse(self.path)
            qs = parse_qs(url.query)
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                repos = list_repos(conn)
            if not repos:
                return self._respond_text(503, "No GitHub data yet. Run rebalance github-sync-artifacts first.")
            requested = (qs.get("repo", [None])[0]) or default_repo or repos[0][0]
            if requested not in {r for r, _ in repos}:
                requested = repos[0][0]
            board = collect(db_path, requested)

            if url.path == "/status.json":
                body = self._json(board).encode()
                ctype = "application/json; charset=utf-8"
            elif url.path in ("/", "/index.html"):
                body = render_html(board, repos).encode()
                ctype = "text/html; charset=utf-8"
            else:
                return self._respond_text(404, "not found")

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _respond_text(self, code: int, msg: str):
            body = msg.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        @staticmethod
        def _json(b: Board) -> str:
            def item(i: Item) -> dict:
                return {k: v for k, v in i.__dict__.items()}
            return json.dumps({
                "repo": b.repo,
                "generated_at": b.generated_at,
                "starred_count": b.starred_count,
                "open_issues": [item(i) for i in b.open_issues],
                "open_prs": [item(i) for i in b.open_prs],
                "recent_releases": [r.__dict__ for r in b.recent_releases],
            }, indent=2, default=str)
    return Handler


def serve(db_path: Path, port: int, default_repo: str | None) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(db_path, default_repo))
    print(f"release board → http://127.0.0.1:{port}/  (Ctrl-C to stop)", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", file=sys.stderr)


def resolve_db() -> Path:
    env = os.environ.get("REBALANCE_DB")
    return Path(env).expanduser() if env else Path.cwd() / "rebalance.db"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="rebalance OS release-board (spike)")
    p.add_argument("--db", type=Path, default=None)
    p.add_argument("--repo", type=str, default=None, help="owner/name; default: most-active repo in DB")
    p.add_argument("--serve", action="store_true")
    p.add_argument("--port", type=int, default=8766)
    args = p.parse_args(argv)

    db_path = args.db or resolve_db()
    if args.serve:
        serve(db_path, args.port, args.repo)
        return 0

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        repos = list_repos(conn)
    if not repos:
        print("No GitHub data yet — run `rebalance github-sync-artifacts` first.")
        return 1
    repo = args.repo or repos[0][0]
    if repo not in {r for r, _ in repos}:
        print(f"Repo '{repo}' has no data. Available:")
        for r, n in repos:
            print(f"  {r}  ({n} items)")
        return 2
    print(render_text(collect(db_path, repo)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
