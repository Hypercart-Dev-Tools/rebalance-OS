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

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from rebalance.ingest.calendar_config import OPERATOR_CALENDAR_ID
from rebalance.ingest.db import db_connection, ensure_schema, ensure_calendar_schema
from rebalance.ingest.embedder import query_similar

logger = logging.getLogger(__name__)

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
    github_semantic_context: list[dict[str, Any]] = field(default_factory=list)  # semantic GitHub hits
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
        logger.warning("vault context unavailable: %s", e)
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
            # Check for all-day or spanning events on the target date.
            # Operator-only scope (OPERATOR_CALENDAR_ID); unified from a hardcoded
            # 'primary' literal in 0.40.1 (F1, single source of truth).
            # REVERT PATH: inline the literal 'primary' here again.
            rows = conn.execute(
                """SELECT summary FROM calendar_events
                   WHERE calendar_id = ?
                     AND start_time <= ? AND end_time >= ?""",
                (OPERATOR_CALENDAR_ID, date_str + "T23:59:59", date_str + "T00:00:00"),
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
        logger.warning("calendar context unavailable: %s", e)
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
        logger.warning("github context unavailable: %s", e)
        return []


def _gather_github_semantic_context(
    database_path: Path,
    query: str,
    top_k: int = 6,
) -> list[dict[str, Any]]:
    """Semantic search over synced GitHub issues, PRs, comments, and commits."""
    try:
        from rebalance.ingest.github_knowledge import query_github_documents

        return query_github_documents(database_path=database_path, query_text=query, top_k=top_k)
    except Exception as e:
        logger.warning("github semantic context unavailable: %s", e)
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
    github_semantic_context: list[dict[str, Any]],
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

    if github_semantic_context:
        lines = ["## Relevant GitHub Artifacts"]
        for item in github_semantic_context[:5]:
            meta = f"{item['repo_full_name']} {item['source_type']} #{item['source_number']}"
            if item.get("state"):
                meta += f" ({item['state']})"
            if item.get("milestone_title"):
                meta += f" milestone={item['milestone_title']}"
            lines.append(f"### {meta}")
            lines.append(item.get("title", ""))
            lines.append(item.get("body_preview", "")[:320])
            lines.append("")
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
# LLM synthesis — Gemini (preferred) with local Qwen fallback
# ---------------------------------------------------------------------------

_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

_cached_chat_model = None
_cached_chat_tokenizer = None
_cached_chat_model_name = None


def _synthesize_gemini(
    prompt: str,
    api_key: str,
    model: str = DEFAULT_GEMINI_MODEL,
    max_tokens: int = 1024,
) -> str:
    """Synthesize via Gemini REST API.

    The API key is passed in-memory and is never logged or written to disk.
    Uses the same REST pattern as repair.py so we don't pull in extra deps.
    """
    import json as _json
    import urllib.request

    url = _GEMINI_ENDPOINT.format(model=model) + f"?key={api_key}"
    body = _json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = _json.loads(resp.read().decode())

    # Defensive parse: a MAX_TOKENS / SAFETY response is valid JSON but may carry
    # no candidates or no text parts. Bare subscripting raised a KeyError/
    # IndexError that ask() mislabelled as a hard "Gemini synthesis failed";
    # surface a clear, accurate error (with finishReason/blockReason) so the
    # fallback log is meaningful. A truncated response that still produced some
    # text returns that partial text rather than discarding it.
    # Mirrors note_builder._synthesize_gemini's guard.
    candidates = payload.get("candidates") or []
    if not candidates:
        block = (payload.get("promptFeedback") or {}).get("blockReason")
        raise RuntimeError(
            "Gemini response had no candidates"
            + (f" (blockReason={block})" if block else "")
        )
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text = "\n".join(p.get("text", "").strip() for p in parts if p.get("text")).strip()
    if not text:
        finish = candidates[0].get("finishReason")
        raise RuntimeError(
            "Gemini response had no text"
            + (f" (finishReason={finish})" if finish else "")
        )
    return text


def _synthesize_with_fallback(
    prompt: str,
    *,
    chat_model: str = DEFAULT_CHAT_MODEL,
    max_tokens: int = 1024,
) -> tuple[str, str]:
    """Synthesize via the Gemini -> local Qwen ladder.

    Tries Gemini first (key from GSM/env via get_gemini_api_key); on failure
    logs and falls back to the local Qwen model. On a second failure, emits a
    dual-failure warning and returns a sentinel. When no Gemini key is present,
    goes straight to Qwen.

    Returns ``(synthesis_text, model_used)`` where model_used is the Gemini
    model id, the Qwen model id (optionally annotated), or a "(failed)" marker.
    """
    from rebalance.ingest.config import get_gemini_api_key

    gemini_key = get_gemini_api_key()
    if gemini_key:
        try:
            synthesis = _synthesize_gemini(prompt, api_key=gemini_key, max_tokens=max_tokens)
            return synthesis, DEFAULT_GEMINI_MODEL
        except Exception as e:
            logger.warning("Gemini synthesis failed, falling back to local LLM: %s", e)
            try:
                synthesis = _synthesize(prompt, model_name=chat_model)
                return synthesis, f"{chat_model} (gemini-fallback)"
            except Exception as e2:
                logger.warning("Qwen fallback also failed after Gemini failure: %s", e2)
                return f"[LLM synthesis failed: {e2}]", f"{chat_model} (failed)"
    else:
        try:
            synthesis = _synthesize(prompt, model_name=chat_model)
            return synthesis, chat_model
        except Exception as e:
            return f"[Local LLM synthesis failed: {e}]", f"{chat_model} (failed)"


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


# Sidecar attribute name under which a team=True ask() stashes the ranked
# "what should we work on next" output. It is a DYNAMIC attribute on the returned
# QueryResult instance — deliberately NOT a dataclass field — so the pinned
# QueryResult field/dict contract (test_querier EXPECTED_KEYS, retrieval.py's
# flatten) stays byte-identical for the default operator flow. The MCP layer
# reads it via getattr(result, NEXT_ACTIONS_ATTR, None).
NEXT_ACTIONS_ATTR = "_next_actions"


def ask(
    query: str,
    database_path: Path,
    *,
    chat_model: str = DEFAULT_CHAT_MODEL,
    since_days: int = 7,
    top_k: int = 8,
    skip_synthesis: bool = False,
    team: bool = False,
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
        team:           If True, ALSO compute the ranked "what should we work on
                        next" list (next_actions.rank_next_actions with
                        blend_team=True) and stash it on the returned QueryResult
                        under the NEXT_ACTIONS_ATTR sidecar attribute. Default OFF:
                        the operator flow + the pinned QueryResult contract stay
                        byte-identical. Never raises — a degraded rank attaches
                        nothing extra and ask() returns its normal result.
    """
    start = time.monotonic()

    # Gather all context
    project_context, repos_map = _gather_project_context(database_path)
    github_context = _gather_github_context(database_path, repos_map, since_days)
    github_semantic_context = _gather_github_semantic_context(database_path, query, top_k=min(top_k, 6))
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

    # Synthesize — Gemini preferred (key from GSM/env); local Qwen as fallback.
    synthesis = ""
    model_used = ""
    if not skip_synthesis:
        prompt = _build_prompt(
            query,
            vault_context,
            github_context,
            github_semantic_context,
            project_context,
            vault_activity,
            calendar_context,
            temporal_context,
        )
        synthesis, model_used = _synthesize_with_fallback(prompt, chat_model=chat_model)

    elapsed = time.monotonic() - start

    result = QueryResult(
        query=query,
        synthesis=synthesis,
        vault_context=vault_context,
        github_context=github_context,
        github_semantic_context=github_semantic_context,
        project_context=project_context,
        vault_activity=vault_activity,
        calendar_context=calendar_context,
        temporal_context=temporal_context,
        model_used=model_used,
        elapsed_seconds=round(elapsed, 2),
    )

    # team=True sidecar: attach the ranked next-actions WITHOUT mutating the
    # pinned QueryResult fields. PREFER the persisted cache so the interactive
    # ask() path never silently pays for a second Gemini round-trip; only when the
    # cache is absent fall back to a LIVE but DETERMINISTIC rank (synthesize=False
    # — the ranked floor, no LLM call). Never raises out of ask(): a degraded rank
    # just stays unattached. Import is local so the default operator path never
    # pays for it.
    if team:
        try:
            from rebalance.ingest import next_actions as _next_actions

            ranked = _next_actions.load_ranked_next_actions(database_path)
            if ranked is None:
                # No precompute yet — deterministic ranked floor (no LLM call).
                ranked = _next_actions.rank_next_actions(
                    database_path, blend_team=True, synthesize=False
                )
            setattr(result, NEXT_ACTIONS_ATTR, ranked)
        except Exception as e:  # noqa: BLE001 — team blend must never break ask()
            logger.warning("team next-actions rank unavailable: %s", e)

    return result
