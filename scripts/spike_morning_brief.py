#!/usr/bin/env python3
"""Phase 0 spike — single-shot morning briefing.

Simulates "tomorrow's morning briefing" from data already in the local SQLite DB,
in one shot, in seconds. THROWAWAY-quality on purpose: the goal is to see a real
briefing immediately and decide go/no-go on the productionized version.

Design (mirrors PROJECT/2-WORKING/P1-MORNING-BRIEFING.md):
  - Deterministic collector owns the FACTS: it reads the five signal sources,
    scores each row for salience, and emits a ranked candidate set.
  - The LLM (Haiku) owns JUDGMENT + PROSE: it only ranks/narrates rows the
    collector handed it. It never invents tasks, deadlines, commits, or emails.

If GEMINI_API_KEY + the `google.generativeai` SDK are present, this prints a Gemini
briefing. Otherwise it writes the candidate JSON and prints a deterministic
grouped fallback so you still see a real briefing with zero external deps.

Usage:
    .venv/bin/python scripts/spike_morning_brief.py
    .venv/bin/python scripts/spike_morning_brief.py --since-days 1 --json-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- repo imports (canonical read paths, same as MCP server / querier) --------
from rebalance.ingest.calendar_config import OPERATOR_CALENDAR_ID
from rebalance.ingest.registry import get_projects
from rebalance.ingest.github_scan import get_github_balance
from rebalance.ingest.db import db_connection, ensure_email_schema, ensure_calendar_schema
from rebalance.ingest.sleuth_reminders import ensure_sleuth_schema

CANDIDATES_PATH = Path("temp/morning-brief-candidates.json")
HAIKU_MODEL = "claude-haiku-4-5"


def _resolve_db_path() -> Path:
    env = os.environ.get("REBALANCE_DB")
    if env:
        return Path(env).expanduser()
    return Path.home() / "Library/Application Support/rebalance-os/rebalance.db"


def _now_local() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


# --- collectors: each returns (rows, error_or_None) ---------------------------
# A source that raises is recorded explicitly, never silently treated as empty.


def collect_projects(db: Path, since_days: int) -> tuple[list[dict[str, Any]], str | None]:
    """Active projects scored by priority tier x recent GitHub momentum."""
    try:
        projects = get_projects(db, status="active")
        repos_map = {p["name"]: p.get("repos", []) for p in projects}
        balance = get_github_balance(db, repos_map, since_days=since_days)
        bal_by_name = {b["project_name"]: b for b in balance}

        rows: list[dict[str, Any]] = []
        for p in projects:
            tier = p.get("priority_tier") or 5  # 1 = highest; default low
            b = bal_by_name.get(p["name"], {})
            commits = int(b.get("total_commits", 0) or 0)
            prs = int(b.get("prs_opened", 0) or 0) + int(b.get("prs_merged", 0) or 0)
            issues = int(b.get("issues_opened", 0) or 0)
            momentum = commits + 2 * prs + issues
            last_active = b.get("last_active_at")

            # "Continue working on": priority-weighted, lifted by recent momentum.
            priority_score = max(0, (6 - tier)) * 10           # tier 1 -> 50, tier 5 -> 10
            momentum_score = min(40, momentum * 4)             # cap the bonus
            salience = priority_score + momentum_score

            rows.append({
                "source": "project",
                "id": p["name"],
                "label": p["name"],
                "salience": float(salience),
                "timestamp": last_active,
                "detail": {
                    "priority_tier": tier,
                    "summary": (p.get("summary") or "").strip(),
                    "repos_touched": b.get("repos_touched", []),
                    "commits": commits,
                    "prs": prs,
                    "issues": issues,
                    "momentum": momentum,
                    "idle": bool(b.get("is_idle", momentum == 0)),
                },
            })
        return rows, None
    except Exception as exc:  # noqa: BLE001 - spike: record, don't crash the run
        return [], f"{type(exc).__name__}: {exc}"


def collect_reminders(db: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Open Sleuth/Slack reminders; overdue and due-today score highest."""
    try:
        now = _now_local()
        end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=0)
        rows: list[dict[str, Any]] = []
        with db_connection(db, ensure_sleuth_schema) as conn:
            recs = conn.execute(
                """SELECT reminder_id, reminder_message_text, should_post_on, state,
                          original_channel_name, github_urls_json
                   FROM sleuth_reminders
                   WHERE is_active = 1
                   ORDER BY should_post_on ASC"""
            ).fetchall()
        for r in recs:
            due = _parse_iso(r["should_post_on"])
            if due is None:
                bucket, salience = "scheduled", 40.0
            elif due <= now:
                bucket, salience = "overdue", 95.0
            elif due <= end_of_today:
                bucket, salience = "due_today", 85.0
            else:
                bucket, salience = "upcoming", 45.0
            rows.append({
                "source": "reminder",
                "id": r["reminder_id"],
                "label": (r["reminder_message_text"] or "").strip()[:160],
                "salience": salience,
                "timestamp": r["should_post_on"],
                "detail": {
                    "bucket": bucket,
                    "state": r["state"],
                    "channel": r["original_channel_name"],
                },
            })
        return rows, None
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}"


def collect_emails(db: Path, since_days: int) -> tuple[list[dict[str, Any]], str | None, int]:
    """Recent inbox; IMPORTANT/STARRED labels score highest. Returns dropped count."""
    try:
        rows: list[dict[str, Any]] = []
        dropped = 0
        with db_connection(db, ensure_email_schema) as conn:
            recs = conn.execute(
                """SELECT message_id, from_address, from_name, subject, snippet,
                          received_at, labels_json
                   FROM email_messages
                   WHERE received_at >= datetime('now', ?)
                   ORDER BY received_at DESC
                   LIMIT 100""",
                (f"-{since_days} day",),
            ).fetchall()
        for r in recs:
            labels = set(json.loads(r["labels_json"] or "[]"))
            important = bool(labels & {"IMPORTANT", "STARRED"})
            in_inbox = "INBOX" in labels or not labels
            if not important and not in_inbox:
                dropped += 1
                continue  # promotional/social/archived noise
            rows.append({
                "source": "email",
                "id": r["message_id"],
                "label": (r["subject"] or "(no subject)").strip()[:160],
                "salience": 80.0 if important else 50.0,
                "timestamp": r["received_at"],
                "detail": {
                    "from": r["from_name"] or r["from_address"],
                    "from_address": r["from_address"],
                    "important": important,
                    "snippet": (r["snippet"] or "").strip()[:200],
                },
            })
        return rows, None, dropped
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}", 0


def collect_calendar(db: Path) -> tuple[list[dict[str, Any]], str | None]:
    """The whole of TODAY's calendar (00:00-23:59 local), not now->forward.

    A morning briefing wants the full day ahead, including events earlier than
    the moment the briefing is generated. (`calendar.get_upcoming_events` filters
    from `now`, which drops the morning's events once the day is underway.)
    """
    try:
        today = _now_local().date().isoformat()
        rows: list[dict[str, Any]] = []
        with db_connection(db, ensure_calendar_schema) as conn:
            # Operator-only scope (OPERATOR_CALENDAR_ID); unified from a 'primary'
            # literal in 0.40.1 (F1). REVERT PATH: inline the literal 'primary'.
            recs = conn.execute(
                """SELECT id, summary, start_time, end_time, location, attendees_json
                   FROM calendar_events
                   WHERE calendar_id = ?
                     AND date(start_time) = ?
                   ORDER BY start_time ASC""",
                (OPERATOR_CALENDAR_ID, today),
            ).fetchall()
        for ev in recs:
            attendees = json.loads(ev["attendees_json"] or "[]")
            rows.append({
                "source": "calendar",
                "id": ev["id"] or ev["summary"],
                "label": (ev["summary"] or "(busy)").strip()[:160],
                "salience": 75.0,
                "timestamp": ev["start_time"],
                "detail": {
                    "start": ev["start_time"],
                    "end": ev["end_time"],
                    "location": ev["location"],
                    "attendees": len(attendees),
                },
            })
        return rows, None
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}"


def build_candidate_set(db: Path, since_days: int) -> dict[str, Any]:
    now = _now_local()
    errors: dict[str, str] = {}

    proj_rows, e = collect_projects(db, since_days)
    if e:
        errors["projects"] = e
    rem_rows, e = collect_reminders(db)
    if e:
        errors["reminders"] = e
    mail_rows, e, mail_dropped = collect_emails(db, since_days)
    if e:
        errors["emails"] = e
    cal_rows, e = collect_calendar(db)
    if e:
        errors["calendar"] = e

    candidates = sorted(
        [*proj_rows, *rem_rows, *mail_rows, *cal_rows],
        key=lambda r: r["salience"],
        reverse=True,
    )

    return {
        "generated_at": now.isoformat(),
        "reference_date": now.date().isoformat(),
        "timezone": str(now.tzinfo),
        "since_days": since_days,
        "counts": {
            "projects": len(proj_rows),
            "reminders": len(rem_rows),
            "emails": len(mail_rows),
            "calendar": len(cal_rows),
            "total_candidates": len(candidates),
        },
        "dropped": {"emails_filtered_as_noise": mail_dropped},
        "source_errors": errors,  # explicit; never silently empty
        "candidates": candidates,
    }


# --- rendering ----------------------------------------------------------------


def render_fallback(data: dict[str, Any]) -> str:
    """Deterministic grouped briefing — no LLM. Always available."""
    by_source: dict[str, list[dict[str, Any]]] = {}
    for c in data["candidates"]:
        by_source.setdefault(c["source"], []).append(c)

    out: list[str] = []
    out.append(f"# Morning Briefing (deterministic) — {data['reference_date']}")
    out.append(f"_generated {data['generated_at']}_\n")

    projects = sorted(by_source.get("project", []), key=lambda r: r["salience"], reverse=True)
    active = [p for p in projects if not p["detail"]["idle"]] or projects
    if active:
        out.append("## Pick back up")
        for p in active[:5]:
            d = p["detail"]
            mo = f"{d['commits']}c/{d['prs']}pr" if d["momentum"] else "no recent activity"
            out.append(f"- **{p['label']}** (tier {d['priority_tier']}, {mo}) — {d['summary'][:100]}")
        out.append("")

    rem = by_source.get("reminder", [])
    due = [r for r in rem if r["detail"]["bucket"] in ("overdue", "due_today")]
    if due:
        out.append("## Due today / overdue")
        for r in sorted(due, key=lambda r: r["salience"], reverse=True):
            out.append(f"- [{r['detail']['bucket']}] {r['label']}  ({r['detail'].get('channel') or '—'})")
        out.append("")

    cal = sorted(by_source.get("calendar", []), key=lambda r: r["timestamp"] or "")
    if cal:
        out.append("## On your calendar")
        for c in cal:
            start = _parse_iso(c["timestamp"])
            hhmm = start.astimezone().strftime("%H:%M") if start else "??:??"
            out.append(f"- {hhmm}  {c['label']}")
        out.append("")

    mail = by_source.get("email", [])
    important = [m for m in mail if m["detail"]["important"]] or mail[:5]
    if important:
        out.append("## Worth a look (inbox)")
        for m in important[:6]:
            star = "★ " if m["detail"]["important"] else ""
            out.append(f"- {star}{m['label']}  — {m['detail']['from']}")
        out.append("")

    if data["source_errors"]:
        out.append("## ⚠ Source errors (not silently hidden)")
        for src, err in data["source_errors"].items():
            out.append(f"- {src}: {err}")
        out.append("")

    return "\n".join(out)


def render_haiku(data: dict[str, Any]) -> str | None:
    """If anthropic SDK + key are available, synthesize with Haiku. Else None."""
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None

    system = (
        "You write a concise morning briefing for one engineer. You are given a JSON "
        "candidate set already ranked by a deterministic collector. Rules: only reference "
        "items present in the JSON; never invent tasks, deadlines, commits, or emails. "
        "Group into: Pick back up, Due today / overdue, On your calendar, Worth a look. "
        "End with a one-line suggested focus order. Cite the source of each line "
        "(project name / reminder / email subject / event). Keep it short and act-on-it-now."
    )
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": json.dumps(data["candidates"], indent=2)}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 0 morning-briefing spike")
    ap.add_argument("--since-days", type=int, default=1, help="lookback window for activity/email")
    ap.add_argument("--json-only", action="store_true", help="only write candidates JSON, no render")
    args = ap.parse_args()

    db = _resolve_db_path()
    if not db.exists():
        print(f"ERROR: DB not found at {db} (set REBALANCE_DB)", file=sys.stderr)
        return 1

    t0 = time.monotonic()
    data = build_candidate_set(db, args.since_days)
    elapsed = time.monotonic() - t0
    data["elapsed_seconds"] = round(elapsed, 3)

    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    c = data["counts"]
    print(
        f"[collector] {c['total_candidates']} candidates "
        f"(projects={c['projects']} reminders={c['reminders']} "
        f"emails={c['emails']} calendar={c['calendar']}) in {elapsed:.2f}s "
        f"-> {CANDIDATES_PATH}",
        file=sys.stderr,
    )
    if data["source_errors"]:
        print(f"[collector] source errors: {data['source_errors']}", file=sys.stderr)

    if args.json_only:
        return 0

    briefing = render_haiku(data)
    if briefing is not None:
        print(f"\n--- Haiku ({HAIKU_MODEL}) ---\n")
        print(briefing)
    else:
        print(
            "\n[synthesis] GEMINI_API_KEY/gemini SDK not available — "
            "showing deterministic fallback. (Haiku is the Phase 2 productization step.)\n",
            file=sys.stderr,
        )
        print(render_fallback(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
