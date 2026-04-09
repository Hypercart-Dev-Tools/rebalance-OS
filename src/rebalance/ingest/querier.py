"""
General-purpose natural language query engine.

Gathers context from all data sources (vault embeddings, GitHub activity,
project registry), assembles a prompt, and optionally synthesizes via a
local LLM (Qwen3 via mlx-lm). Returns both raw context and synthesis so
the host agent can review, adapt, and present.

The local LLM is a first-pass summarizer — not the final answer. The host
agent (Claude, Copilot, etc.) is expected to refine the output.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from rebalance.ingest.db import db_connection, ensure_schema, ensure_calendar_schema
from rebalance.ingest.embedder import query_similar

DEFAULT_CHAT_MODEL = "Qwen/Qwen3-0.6B"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    query: str
    synthesis: str                                     # LLM-generated first-pass answer
    vault_context: list[dict[str, Any]] = field(default_factory=list)    # semantic search hits
    github_context: list[dict[str, Any]] = field(default_factory=list)   # per-project activity
    project_context: list[dict[str, Any]] = field(default_factory=list)  # registry entries
    vault_activity: list[dict[str, Any]] = field(default_factory=list)   # recently modified notes
    calendar_context: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # upcoming + recent events
    temporal_context: dict[str, Any] = field(default_factory=dict)  # today/tomorrow day type
    model_used: str = ""
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------


def _gather_vault_context(
    database_path: Path,
    query: str,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """Semantic search over embedded vault chunks."""
    try:
        return query_similar(database_path=database_path, query_text=query, top_k=top_k)
    except Exception as e:
        print(f"[rebalance] vault context unavailable: {e}", file=sys.stderr)
        return []


def _local_now() -> datetime:
    """Return current time in the user's local timezone (not UTC)."""
    return datetime.now().astimezone()


def _gather_temporal_context(
    database_path: Path,
    target_date: datetime | None = None,
) -> dict[str, Any]:
    """Build temporal context: day of week, work/off/vacation status.

    Uses local timezone for day-of-week calculations.
    Checks calendar_events for vacation-like events on the target date.
    """
    if target_date is None:
        target_date = _local_now()

    day_name = target_date.strftime("%A")  # "Monday", "Tuesday", etc.
    weekday = target_date.weekday()  # 0=Mon, 6=Sun
    date_str = target_date.strftime("%Y-%m-%d")
    is_weekend = weekday >= 5

    # Check for vacation/OOO events on this date
    vacation_keywords = ["vacation", "pto", "ooo", "time off", "holiday", "day off"]
    is_vacation = False
    vacation_event = ""

    try:
        with db_connection(database_path, ensure_calendar_schema) as conn:
            # Check for all-day or spanning events on the target date
            rows = conn.execute(
                """SELECT summary FROM calendar_events
                   WHERE start_time <= ? AND end_time >= ?""",
                (date_str + "T23:59:59", date_str + "T00:00:00"),
            ).fetchall()
        for row in rows:
            title = (row["summary"] or "").lower()
            if any(kw in title for kw in vacation_keywords):
                is_vacation = True
                vacation_event = row["summary"]
                break
    except Exception:
        pass

    if is_vacation:
        day_type = "vacation"
    elif is_weekend:
        day_type = "off"
    else:
        day_type = "workday"

    return {
        "date": date_str,
        "day_name": day_name,
        "day_type": day_type,  # "workday", "off", "vacation"
        "is_weekend": is_weekend,
        "is_vacation": is_vacation,
        "vacation_event": vacation_event,
    }


def _gather_vault_activity(
    database_path: Path,
    since_days: int = 7,
) -> list[dict[str, Any]]:
    """Recently modified vault files as a project activity signal."""
    import json

    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    with db_connection(database_path, ensure_schema) as conn:
        rows = conn.execute(
            """
            SELECT rel_path, title, last_modified, tags_json
            FROM vault_files
            WHERE last_modified >= ?
            ORDER BY last_modified DESC
            LIMIT 20
            """,
            (cutoff,),
        ).fetchall()
    return [
        {
            "file_path": row["rel_path"],
            "title": row["title"],
            "last_modified": row["last_modified"],
            "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
        }
        for row in rows
    ]


def _gather_calendar_context(
    database_path: Path,
    days_forward: int = 2,
    days_back: int = 7,
) -> dict[str, list[dict[str, Any]]]:
    """Upcoming + recent calendar events."""
    from rebalance.ingest.calendar import get_upcoming_events, get_recent_events
    try:
        return {
            "upcoming": get_upcoming_events(database_path, days_forward),
            "recent": get_recent_events(database_path, days_back),
        }
    except Exception as e:
        print(f"[rebalance] calendar context unavailable: {e}", file=sys.stderr)
        return {"upcoming": [], "recent": []}


def _gather_github_context(
    database_path: Path,
    project_repos: dict[str, list[str]],
    since_days: int = 7,
) -> list[dict[str, Any]]:
    """Per-project GitHub activity summary."""
    from rebalance.ingest.github_scan import get_github_balance
    try:
        return get_github_balance(
            database_path=database_path,
            project_repos=project_repos,
            since_days=since_days,
        )
    except Exception as e:
        print(f"[rebalance] github context unavailable: {e}", file=sys.stderr)
        return []


def _gather_project_context(database_path: Path) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Project registry entries + repos map."""
    from rebalance.ingest.registry import get_projects

    projects = get_projects(database_path)
    repos_map: dict[str, list[str]] = {}
    for p in projects:
        repos_map[p["name"]] = p.get("repos") or []
    return projects, repos_map


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def _build_prompt(
    query: str,
    vault_context: list[dict[str, Any]],
    github_context: list[dict[str, Any]],
    project_context: list[dict[str, Any]],
    vault_activity: list[dict[str, Any]],
    calendar_context: dict[str, list[dict[str, Any]]] | None = None,
    temporal_context: dict[str, Any] | None = None,
) -> str:
    """Assemble a prompt for the local LLM with all gathered context."""
    sections = []

    # Temporal context — always first so the LLM knows what kind of day it is
    if temporal_context:
        today = temporal_context.get("today", {})
        tomorrow = temporal_context.get("tomorrow", {})
        lines = [f"## Schedule Context"]
        lines.append(f"- **Today:** {today.get('day_name', '')} ({today.get('date', '')}) — {today.get('day_type', 'workday')}")
        if today.get("is_vacation"):
            lines.append(f"  Vacation: {today.get('vacation_event', '')}")
        lines.append(f"- **Tomorrow:** {tomorrow.get('day_name', '')} ({tomorrow.get('date', '')}) — {tomorrow.get('day_type', 'workday')}")
        if tomorrow.get("is_vacation"):
            lines.append(f"  Vacation: {tomorrow.get('vacation_event', '')}")
        if tomorrow.get("day_type") == "off":
            lines.append("  (Weekend — no work recommendations unless explicitly asked)")
        sections.append("\n".join(lines))

    # Project registry
    if project_context:
        lines = ["## Projects (by priority tier)"]
        for p in project_context:
            lines.append(f"- **{p['name']}** (Tier {p['priority_tier']}, {p['risk_level']} risk): {p['summary'] or 'No summary'}")
        sections.append("\n".join(lines))

    # GitHub activity
    if github_context:
        lines = ["## GitHub Activity (last 7 days)"]
        for g in github_context:
            if g.get("is_idle"):
                lines.append(f"- {g['project_name']}: IDLE (no activity)")
            else:
                lines.append(
                    f"- {g['project_name']}: {g['total_commits']} commits, "
                    f"{g['prs_opened']} PRs opened, {g['prs_merged']} merged, "
                    f"{g['issues_opened']} issues opened"
                )
        sections.append("\n".join(lines))

    # Vault activity
    if vault_activity:
        lines = ["## Recently Modified Notes (last 7 days)"]
        for v in vault_activity:
            lines.append(f"- {v['title']} ({v['file_path']}) — modified {v['last_modified'][:10]}")
        sections.append("\n".join(lines))

    # Calendar events
    if calendar_context:
        upcoming = calendar_context.get("upcoming", [])
        recent = calendar_context.get("recent", [])
        if upcoming:
            lines = ["## Upcoming Calendar Events"]
            for e in upcoming:
                time_str = e["start_time"][:16].replace("T", " ")
                loc = f" — {e['location']}" if e.get("location") else ""
                lines.append(f"- {time_str}  {e['summary']}{loc}")
            sections.append("\n".join(lines))
        if recent:
            lines = ["## Recent Calendar Events (last 7 days)"]
            for e in recent[:15]:
                time_str = e["start_time"][:16].replace("T", " ")
                lines.append(f"- {time_str}  {e['summary']}")
            sections.append("\n".join(lines))

    # Semantic search results
    if vault_context:
        lines = ["## Relevant Vault Notes"]
        for r in vault_context[:5]:  # top 5 to keep prompt manageable
            heading = f" > {r['heading']}" if r.get("heading") else ""
            lines.append(f"### {r['title']}{heading}")
            lines.append(r.get("body_preview", "")[:300])
            lines.append("")
        sections.append("\n".join(lines))

    context_block = "\n\n".join(sections)

    return f"""You are a workday assistant. Answer the user's question using ONLY the context provided below. Be concise and specific. If the context doesn't contain enough information, say so.

<context>
{context_block}
</context>

Question: {query}

Answer:"""


# ---------------------------------------------------------------------------
# Local LLM synthesis
# ---------------------------------------------------------------------------


_cached_chat_model = None
_cached_chat_tokenizer = None
_cached_chat_model_name = None


def _synthesize(prompt: str, model_name: str = DEFAULT_CHAT_MODEL, max_tokens: int = 512) -> str:
    """Generate a response using a local Qwen chat model via mlx-lm."""
    global _cached_chat_model, _cached_chat_tokenizer, _cached_chat_model_name

    from mlx_lm import load, generate

    if _cached_chat_model is None or _cached_chat_model_name != model_name:
        _cached_chat_model, _cached_chat_tokenizer = load(model_name)
        _cached_chat_model_name = model_name

    response = generate(
        _cached_chat_model,
        _cached_chat_tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
    )
    # Clean up repetitive stop tokens from small models
    text = response.strip()
    for stop in ["</answer>", "</s>", "<|endoftext|>", "<|im_end|>"]:
        if stop in text:
            text = text[:text.index(stop)].strip()
            break
    return text


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def ask(
    query: str,
    database_path: Path,
    *,
    chat_model: str = DEFAULT_CHAT_MODEL,
    since_days: int = 7,
    top_k: int = 8,
    skip_synthesis: bool = False,
) -> QueryResult:
    """
    Answer a natural language question using all available data sources.

    Gathers context from vault embeddings, GitHub activity, project registry,
    and recent vault file modifications. Optionally synthesizes via local LLM.

    Args:
        query:          Natural language question.
        database_path:  Path to SQLite database.
        chat_model:     HuggingFace model ID for local LLM synthesis.
        since_days:     Window for GitHub and vault activity context.
        top_k:          Number of semantic search results.
        skip_synthesis: If True, skip local LLM and return raw context only.
    """
    start = time.monotonic()

    # Gather all context
    project_context, repos_map = _gather_project_context(database_path)
    github_context = _gather_github_context(database_path, repos_map, since_days)
    vault_context = _gather_vault_context(database_path, query, top_k)
    vault_activity = _gather_vault_activity(database_path, since_days)
    calendar_context = _gather_calendar_context(database_path, days_forward=2, days_back=since_days)

    # Temporal context — today + tomorrow (local timezone)
    now = _local_now()
    tomorrow = now + timedelta(days=1)
    temporal_context = {
        "today": _gather_temporal_context(database_path, now),
        "tomorrow": _gather_temporal_context(database_path, tomorrow),
    }

    # Synthesize
    synthesis = ""
    model_used = ""
    if not skip_synthesis:
        prompt = _build_prompt(query, vault_context, github_context, project_context, vault_activity, calendar_context, temporal_context)
        try:
            synthesis = _synthesize(prompt, model_name=chat_model)
            model_used = chat_model
        except Exception as e:
            synthesis = f"[Local LLM synthesis failed: {e}]"
            model_used = f"{chat_model} (failed)"

    elapsed = time.monotonic() - start

    return QueryResult(
        query=query,
        synthesis=synthesis,
        vault_context=vault_context,
        github_context=github_context,
        project_context=project_context,
        vault_activity=vault_activity,
        calendar_context=calendar_context,
        temporal_context=temporal_context,
        model_used=model_used,
        elapsed_seconds=round(elapsed, 2),
    )
