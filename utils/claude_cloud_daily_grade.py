#!/usr/bin/env python3
"""Write a graded Claude Code Cloud signal block into today's Obsidian note (GH-128).

This is the OBSERVATION SURFACE for the cloud-jobs signal: it fetches today's Claude
Code Cloud (web) sessions, grades their data quality, and upserts a block into
``0. Today's Notes.md`` so the operator can watch signal quality daily before the
signal is promoted to influence the HiQS ranked verdict (the ranker provider ships
dormant behind ``claude_cloud_signal_enabled``; this grader is independent of it).

Usage:
  .venv/bin/python utils/claude_cloud_daily_grade.py           # write today's block
  .venv/bin/python utils/claude_cloud_daily_grade.py --dry-run # print, don't write
  .venv/bin/python utils/claude_cloud_daily_grade.py --status  # show vault/block state
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

# Reuse the rollover module's vault config (same pattern as git_pulse_daily_synthesis).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from obsidian_daily_rollover import TODAY_FILE, vault_ready  # noqa: E402

from rebalance.ingest.claude_cloud import grade, sessions_for_day  # noqa: E402

MARKER_START = "<!-- Claude Cloud Signal Start -->"
MARKER_END = "<!-- Claude Cloud Signal End -->"
BLOCK_HEADING = "## 🤖 Claude Code Cloud — Signal Quality"


def log(msg: str) -> None:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


# --- pure block logic -------------------------------------------------------

def _fmt_time(t: dt.datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def _pr_cell(r: dict) -> str:
    st = r.get("pr_state")
    if not st:
        return "no PR" if r.get("repo") else "—"
    if st == "?":
        return "PR ?"
    n = r.get("pr_number")
    label = f"PR #{n} {st}" if n else st
    return f"[{label}]({r['pr_url']})" if r.get("pr_url") else label


def render_summary(rows: list[dict], g: dict) -> str:
    """The markdown body (between the markers)."""
    if g["n"] == 0:
        return "No Claude Code Cloud sessions found today."

    lines: list[str] = []
    dims = g["dimensions"]
    lines.append(f"**Data quality: {g['letter']}** ({g['overall']:.0%}) over {g['n']} session(s).")
    lines.append("")
    lines.append("| Dimension | Coverage |")
    lines.append("|---|---|")
    lines.append(f"| Identified (repo+branch) | {dims['identified']:.0%} |")
    lines.append(f"| Attested (has summary) | {dims['attested']:.0%} |")
    lines.append(f"| Outcome known (status) | {dims['outcome_known']:.0%} |")
    lines.append(f"| PR-linked *(informational)* | {g['pr_linked']:.0%} |")
    lines.append("")
    c = g["counts"]
    lines.append(f"**PR status:** {c['merged']} merged · {c['open']} open · {c['no_pr']} no-PR"
                 + (f" · {c['pr_lookup_failed']} lookup-failed" if c["pr_lookup_failed"] else ""))
    lines.append("")
    lines.append("| Job | Status | PR |")
    lines.append("|---|---|---|")
    for r in sorted(rows, key=lambda x: x["created_at"] or ""):
        title = (r["title"] or "(untitled)").replace("|", "\\|")
        bucket = r["status_bucket"] or "?"
        lines.append(f"| {title} | {bucket} | {_pr_cell(r)} |")
    if g["warnings"]:
        lines.append("")
        lines.append("**Data-quality flags:**")
        for w in g["warnings"]:
            lines.append(f"- ⚠️ {w}")
    return "\n".join(lines)


def build_block(summary: str, generated_at: dt.datetime) -> str:
    stamp = f"*Auto-generated at {_fmt_time(generated_at)}.*"
    return f"{MARKER_START}\n{BLOCK_HEADING}\n{stamp}\n\n{summary.strip()}\n{MARKER_END}\n"


def upsert_block(content: str, summary: str, generated_at: dt.datetime) -> str:
    block = build_block(summary, generated_at)
    if MARKER_START in content and MARKER_END in content:
        before = content.split(MARKER_START, 1)[0]
        tail = content.rsplit(MARKER_END, 1)[1].lstrip("\n")
        return before + block + (f"\n{tail}" if tail else "")
    body = content if content.endswith("\n") else content + "\n"
    if not body.endswith("\n\n"):
        body += "\n"
    return body + block


# --- run --------------------------------------------------------------------

def run(dry_run: bool = False) -> int:
    now = dt.datetime.now()
    rows = sessions_for_day()          # today, PR-enriched, fail-soft ([] on error)
    g = grade(rows)
    summary = render_summary(rows, g)
    log(f"graded {g['n']} session(s): {g['letter']} ({g['overall']})")

    if not vault_ready():
        log("vault not ready — skipping daily-note write (grade computed above).")
        return 0
    if not TODAY_FILE.exists():
        log(f"{TODAY_FILE} does not exist — skipping (rollover creates it).")
        return 0

    content = TODAY_FILE.read_text(encoding="utf-8")
    new_content = upsert_block(content, summary, now)
    if dry_run:
        log("DRY RUN — would write this block:")
        print("-" * 60)
        print(build_block(summary, now), end="")
        print("-" * 60)
        return 0
    if new_content != content:
        TODAY_FILE.write_text(new_content, encoding="utf-8")
        log(f"wrote Claude Cloud signal block to {TODAY_FILE.name}")
    else:
        log("block unchanged — no write needed.")
    return 0


def show_status() -> int:
    log(f"vault ready: {vault_ready()}")
    log(f"Today's Notes exists: {TODAY_FILE.exists()}")
    if TODAY_FILE.exists():
        content = TODAY_FILE.read_text(encoding="utf-8")
        log(f"Claude Cloud block present: {MARKER_START in content and MARKER_END in content}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    return show_status() if args.status else run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
