#!/usr/bin/env python3
"""End-to-end triage CLI for any synced GitHub repo in rebalance.db.

Reads from local SQLite (populated by `rebalance github-sync-artifacts` and
`rebalance sleuth-sync`), bucketizes open issues + PRs into 6 deterministic
action categories, optionally posts the result as a GitHub issue.

Edge cases (fuzzy duplicates, PROJECT-umbrella scope decisions) are routed
through a review queue so a human or VS Code agent can resolve them
without forking the script.

Usage:
    # Print to stdout, no posting, no agent hooks
    spike.py --repo BinoidCBD/universal-child-theme-oct-2024

    # Write markdown + queue files; do nothing else
    spike.py --repo X --out-dir temp/triage

    # Resolve ambiguities by asking the operator interactively
    spike.py --repo X --ambiguity ask-operator

    # Use pre-filled decisions (e.g. produced by a VS Code agent)
    spike.py --repo X --decisions temp/triage/decisions.jsonl --post-issue

Agent-hook contract: see experimental/triage/README.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "temp" / "triage"
DEFAULT_DB = Path(os.environ.get("REBALANCE_DB", REPO_ROOT / "rebalance.db"))


# ── data shapes ─────────────────────────────────────────────────────────────
@dataclass
class Item:
    number: int
    title: str
    url: str
    rationale: str = ""


@dataclass
class ReviewCase:
    """One ambiguous decision the script can't make alone.

    A VS Code agent (or operator) is expected to populate `decision` and
    optionally `decision_reason`, then either (a) re-run with --decisions
    pointing at a JSONL file containing this record, or (b) for ask-operator
    mode, answer the stdin prompt at the moment.
    """
    id: str
    kind: str                           # 'duplicate' | 'project-needs-split'
    items: list[int]                    # issue/PR numbers under review
    suggested: str                      # what the script would do unattended
    rationale: str                      # why the script flagged it
    repo: str
    decision: str | None = None         # populated externally: 'accept'|'reject'|<custom>
    decision_reason: str | None = None


@dataclass
class Bucket:
    key: str
    icon: str
    name: str
    description: str
    items: list[Item] = field(default_factory=list)
    review_markers: list[str] = field(default_factory=list)  # `<!-- agent-review id=... -->`


# ── DB helpers ──────────────────────────────────────────────────────────────
def open_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        sys.exit(f"ERROR: rebalance DB not found at {path}. "
                 f"Run `rebalance github-sync-artifacts --repo X` first.")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def issue_url(repo: str, number: int) -> str:
    return f"https://github.com/{repo}/issues/{number}"


def pr_url(repo: str, number: int) -> str:
    return f"https://github.com/{repo}/pull/{number}"


# ── jaccard for duplicate detection ─────────────────────────────────────────
WORD_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "of", "on", "or", "the", "to", "with",
    # noise common in repo titles:
    "binoid", "bloomz", "binoidcbd", "binoidcbd.com", "com", "dev", "fix",
    "issue", "issues", "perf", "performance", "pr", "project", "site",
    "the", "update", "updates", "with", "wp",
}


def tokenize(text: str) -> set[str]:
    return {w for w in WORD_RE.findall((text or "").lower())
            if w not in STOPWORDS and len(w) > 2}


def jaccard(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# ── ambiguity resolution ────────────────────────────────────────────────────
class AmbiguityResolver:
    """Routes review cases to one of three handlers based on --ambiguity."""

    MODE_AUTO = "auto"           # take suggested action; mark in markdown
    MODE_QUEUE = "queue"         # write to JSONL; mark in markdown; do not act
    MODE_OPERATOR = "ask-operator"  # stdin prompt at decision time

    def __init__(self, mode: str, decisions: dict[str, ReviewCase],
                 queue_path: Path, repo: str):
        self.mode = mode
        self.decisions = decisions
        self.queue_path = queue_path
        self.repo = repo
        self.queued: list[ReviewCase] = []

    def resolve(self, case: ReviewCase) -> tuple[str, str]:
        """Return (decision, source) where source is 'pre-decided'|'auto'|'operator'|'queued'."""
        if case.id in self.decisions:
            d = self.decisions[case.id]
            return (d.decision or "accept", "pre-decided")

        if self.mode == self.MODE_AUTO:
            return ("accept", "auto")

        if self.mode == self.MODE_OPERATOR:
            return self._ask_operator(case)

        # queue mode
        self.queued.append(case)
        return ("pending", "queued")

    def _ask_operator(self, case: ReviewCase) -> tuple[str, str]:
        print("", file=sys.stderr)
        print(f"--- review case [{case.id}] ({case.kind}) ---", file=sys.stderr)
        print(f"  items: {case.items}", file=sys.stderr)
        print(f"  rationale: {case.rationale}", file=sys.stderr)
        print(f"  suggested: {case.suggested}", file=sys.stderr)
        try:
            ans = input("  accept (a) / reject (r) / skip (s)? ").strip().lower()
        except EOFError:
            ans = "s"
        return ({"a": "accept", "r": "reject"}.get(ans, "pending"), "operator")

    def flush_queue(self) -> Path | None:
        if not self.queued:
            return None
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        with self.queue_path.open("w", encoding="utf-8") as fh:
            for case in self.queued:
                fh.write(json.dumps(asdict(case)) + "\n")
        return self.queue_path


def load_decisions(path: Path | None) -> dict[str, ReviewCase]:
    if path is None or not path.exists():
        return {}
    out: dict[str, ReviewCase] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        case = ReviewCase(**{k: data.get(k) for k in ReviewCase.__dataclass_fields__})
        out[case.id] = case
    return out


# ── bucket builders ─────────────────────────────────────────────────────────
def bucket_prs_unblocked(conn: sqlite3.Connection, repo: str, **_) -> Bucket:
    rows = conn.execute("""
        SELECT number, title, base_ref, mergeable_state, review_decision,
               check_status, requested_reviewers_json, is_draft
        FROM github_items
        WHERE repo_full_name = ? AND item_type = 'pull_request' AND state = 'open'
        ORDER BY updated_at DESC LIMIT 6
    """, (repo,)).fetchall()
    b = Bucket("prs_unblocked", "🚀", "Merge now (or unblock)",
               "PRs that are CI-green but stuck on review or mergeability.")
    for r in rows:
        bits = []
        if r["check_status"] == "success":
            bits.append("CI green")
        if r["mergeable_state"] == "dirty":
            bits.append("**rebase needed**")
        elif r["mergeable_state"] == "blocked":
            bits.append("blocked on review")
        reviewers = json.loads(r["requested_reviewers_json"] or "[]")
        if reviewers:
            bits.append(f"requested: {', '.join(str(x) for x in reviewers)}")
        else:
            bits.append("no reviewer requested → assign one")
        if r["is_draft"]:
            bits.append("DRAFT")
        bits.append(f"→`{r['base_ref']}`")
        b.items.append(Item(
            number=r["number"], title=r["title"], url=pr_url(repo, r["number"]),
            rationale=" · ".join(bits),
        ))
    return b


def bucket_release_blockers(conn: sqlite3.Connection, repo: str, **_) -> Bucket:
    rows = conn.execute("""
        SELECT number, title, milestone_title
        FROM github_items
        WHERE repo_full_name = ? AND item_type = 'issue' AND state = 'open'
          AND milestone_title IS NOT NULL AND milestone_title != ''
        ORDER BY milestone_title, number LIMIT 6
    """, (repo,)).fetchall()
    b = Bucket("release_blockers", "🔥", "Release blockers",
               "Open issues attached to active milestones — finish to ship.")
    for r in rows:
        b.items.append(Item(
            number=r["number"], title=r["title"], url=issue_url(repo, r["number"]),
            rationale=f"milestone: **{r['milestone_title']}**",
        ))
    return b


def bucket_client_visible(conn: sqlite3.Connection, repo: str, **_) -> Bucket:
    rows = conn.execute("""
        SELECT github_urls_json FROM sleuth_reminders
        WHERE is_active = 1 AND github_urls_json LIKE ?
    """, (f"%{repo}%",)).fetchall()
    seen: dict[int, list[str]] = {}
    pat = re.compile(rf"github\.com/{re.escape(repo)}/(?:issues|pull)/(\d+)", re.I)
    for r in rows:
        for url in json.loads(r["github_urls_json"] or "[]"):
            m = pat.search(url or "")
            if m:
                seen.setdefault(int(m.group(1)), []).append(url)
    b = Bucket("client_visible", "👀", "Client-visible (Sleuth-linked)",
               "Items referenced from active Sleuth reminders — client is watching.")
    if not seen:
        return b
    placeholders = ",".join("?" * len(seen))
    rows = conn.execute(
        f"""SELECT number, title FROM github_items
            WHERE repo_full_name = ? AND number IN ({placeholders})
            ORDER BY number""",
        (repo, *sorted(seen)),
    ).fetchall()
    for r in rows[:6]:
        b.items.append(Item(
            number=r["number"], title=r["title"], url=issue_url(repo, r["number"]),
            rationale="referenced from active Sleuth reminder",
        ))
    return b


def bucket_perf_concrete(conn: sqlite3.Connection, repo: str, **_) -> Bucket:
    rows = conn.execute("""
        SELECT number, title FROM github_items
        WHERE repo_full_name = ? AND item_type = 'issue' AND state = 'open'
          AND (title LIKE 'perf:%' OR title LIKE 'Perf:%' OR title LIKE 'perf %')
        ORDER BY updated_at DESC LIMIT 6
    """, (repo,)).fetchall()
    b = Bucket("perf_concrete", "⚡", "Performance — concrete data attached",
               "`perf:`-prefixed issues — typically pre-scoped, low decision overhead.")
    for r in rows:
        b.items.append(Item(
            number=r["number"], title=r["title"], url=issue_url(repo, r["number"]),
            rationale="perf-prefixed → concrete metric or fix-shape implied",
        ))
    return b


def bucket_duplicates(conn: sqlite3.Connection, repo: str,
                      resolver: AmbiguityResolver, threshold: float = 0.7,
                      **_) -> Bucket:
    """Fuzzy-duplicate detection. Each candidate pair is a review case."""
    rows = conn.execute("""
        SELECT number, title FROM github_items
        WHERE repo_full_name = ? AND item_type = 'issue' AND state = 'open'
        ORDER BY number
    """, (repo,)).fetchall()
    b = Bucket("duplicates", "🧹", "Probable duplicates",
               "Title-similar pairs flagged for human/agent review.")
    n = len(rows)
    pairs: list[tuple[int, int, float, str, str]] = []
    for i in range(n):
        for j in range(i + 1, n):
            sim = jaccard(rows[i]["title"], rows[j]["title"])
            if sim >= threshold:
                pairs.append((rows[i]["number"], rows[j]["number"], sim,
                              rows[i]["title"], rows[j]["title"]))
    pairs.sort(key=lambda p: -p[2])
    for lo, hi, sim, t1, t2 in pairs[:6]:
        case_id = f"dup-{lo}-{hi}"
        case = ReviewCase(
            id=case_id, kind="duplicate", items=[lo, hi],
            suggested=f"close #{hi} as duplicate of #{lo}",
            rationale=f"jaccard={sim:.2f} between titles",
            repo=repo,
        )
        decision, source = resolver.resolve(case)
        marker = f"<!-- agent-review id={case_id} kind=duplicate items=[{lo},{hi}] decision={decision} source={source} -->"
        b.review_markers.append(marker)
        b.items.append(Item(
            number=lo,
            title=f"#{lo} ⇄ #{hi}  (sim {sim:.2f})",
            url=issue_url(repo, lo),
            rationale=(
                f"#{lo} '{t1[:55]}' vs #{hi} '{t2[:55]}'  ·  "
                f"decision: **{decision}** ({source})"
            ),
        ))
    return b


def bucket_project_umbrellas(conn: sqlite3.Connection, repo: str,
                             resolver: AmbiguityResolver, **_) -> Bucket:
    rows = conn.execute("""
        SELECT number, title, body FROM github_items
        WHERE repo_full_name = ? AND item_type = 'issue' AND state = 'open'
          AND (title LIKE 'PROJECT%' OR title LIKE 'Project:%' OR title LIKE 'project:%')
        ORDER BY updated_at DESC LIMIT 6
    """, (repo,)).fetchall()
    b = Bucket("project_umbrellas", "🤔", "PROJECT umbrellas",
               "Wide-scope items — each likely needs splitting before estimation.")
    for r in rows:
        body_len = len(r["body"] or "")
        case_id = f"split-{r['number']}"
        case = ReviewCase(
            id=case_id, kind="project-needs-split", items=[r["number"]],
            suggested=f"agent should read body of #{r['number']} ({body_len} chars) "
                      f"and propose 2-4 child issues with acceptance criteria",
            rationale=f"PROJECT umbrella with {body_len}-char body",
            repo=repo,
        )
        decision, source = resolver.resolve(case)
        marker = f"<!-- agent-review id={case_id} kind=split items=[{r['number']}] decision={decision} source={source} -->"
        b.review_markers.append(marker)
        b.items.append(Item(
            number=r["number"], title=r["title"], url=issue_url(repo, r["number"]),
            rationale=f"split decision: **{decision}** ({source}) · body {body_len}c",
        ))
    return b


BUCKET_BUILDERS: list[Callable[..., Bucket]] = [
    bucket_prs_unblocked,
    bucket_release_blockers,
    bucket_client_visible,
    bucket_perf_concrete,
    bucket_duplicates,
    bucket_project_umbrellas,
]


# ── markdown rendering ──────────────────────────────────────────────────────
def render_markdown(buckets: list[Bucket], repo: str, generated_at: str,
                    queue_path: Path | None) -> str:
    lines: list[str] = []
    lines.append(
        f"> Generated **{generated_at}** from a cross-source query against "
        f"`rebalance-OS` local SQLite. Re-runnable via "
        f"`experimental/triage/spike.py --repo {repo}`."
    )
    if queue_path:
        rel = queue_path.relative_to(REPO_ROOT) if queue_path.is_absolute() else queue_path
        lines.append("")
        lines.append(
            f"> ⚠ {sum(len(b.review_markers) for b in buckets)} review cases pending — see "
            f"`{rel}`. Resolve with a VS Code agent or operator review, then re-run with "
            f"`--decisions <decisions.jsonl>`."
        )
    lines.append("")
    for idx, b in enumerate(buckets, 1):
        lines.append(f"## {b.icon} {idx}. {b.name}")
        lines.append("")
        lines.append(f"_{b.description}_")
        lines.append("")
        if not b.items:
            lines.append("*(none)*")
            lines.append("")
            continue
        lines.append("| # | Title | Rationale |")
        lines.append("|---|---|---|")
        for it in b.items:
            title = it.title.replace("|", "\\|")
            rat = it.rationale.replace("|", "\\|")
            lines.append(f"| [#{it.number}]({it.url}) | {title} | {rat} |")
        for marker in b.review_markers:
            lines.append(marker)
        lines.append("")
    return "\n".join(lines)


# ── posting ─────────────────────────────────────────────────────────────────
def post_issue(repo: str, title: str, body: str) -> str:
    body_path = Path("/tmp") / f"triage-issue-{os.getpid()}.md"
    body_path.write_text(body, encoding="utf-8")
    try:
        result = subprocess.run(
            ["gh", "issue", "create", "--repo", repo, "--title", title,
             "--body-file", str(body_path)],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        sys.exit("ERROR: `gh` CLI not found. Install gh or use --dry-run.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: gh issue create failed: {e.stderr.strip()}")
    finally:
        body_path.unlink(missing_ok=True)


# ── CLI ─────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Bucket open issues + PRs into action categories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--repo", required=True, help="owner/name (must already be synced)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB,
                   help=f"rebalance.db path (default: {DEFAULT_DB})")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                   help="where queue/markdown artifacts land")
    p.add_argument("--ambiguity", choices=["auto", "queue", "ask-operator"],
                   default="queue",
                   help="how to handle review cases (default: queue)")
    p.add_argument("--decisions", type=Path, default=None,
                   help="JSONL of pre-made decisions (overrides --ambiguity)")
    p.add_argument("--duplicate-threshold", type=float, default=0.7,
                   help="jaccard cutoff for duplicate detection (0..1)")
    p.add_argument("--post-issue", action="store_true",
                   help="post final markdown as a GitHub issue via gh CLI")
    p.add_argument("--issue-title", default=None,
                   help="title for posted issue (default: 'Triage: 6 action buckets ...')")
    p.add_argument("--dry-run", action="store_true",
                   help="print what would happen but don't post")
    args = p.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    decisions = load_decisions(args.decisions)
    queue_path = args.out_dir / f"{args.repo.replace('/', '__')}__queue.jsonl"
    body_path = args.out_dir / f"{args.repo.replace('/', '__')}__triage.md"

    resolver = AmbiguityResolver(args.ambiguity, decisions, queue_path, args.repo)

    with open_db(args.db) as conn:
        buckets = [
            build(conn, args.repo, resolver=resolver,
                  threshold=args.duplicate_threshold)
            for build in BUCKET_BUILDERS
        ]

    queue_emitted = resolver.flush_queue()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = render_markdown(buckets, args.repo, generated_at, queue_emitted)

    body_path.write_text(body, encoding="utf-8")
    print(f"[triage] markdown → {body_path}", file=sys.stderr)
    if queue_emitted:
        print(f"[triage] {len(resolver.queued)} review cases → {queue_emitted}",
              file=sys.stderr)

    if args.post_issue and not args.dry_run:
        title = args.issue_title or f"Triage: 6 action buckets ({generated_at[:10]})"
        url = post_issue(args.repo, title, body)
        print(url)
    elif args.post_issue and args.dry_run:
        print("[triage] --dry-run set; would post to gh issue create", file=sys.stderr)
        print(body)
    else:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
