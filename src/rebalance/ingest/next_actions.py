"""P2 v0.5 "what should we work on next" — the single ranked-output service.

This is the keystone the dashboard route AND the ``ask`` surface both call, so
the two never drift: a flat, ranked "next actions" list assembled from the
operator's own signals (calendar + GitHub + vault + sleuth + email) blended with
a strictly-additive, de-duplicated delta of teammate calendar signal.

Design (SOLID — distinct, testable functions):

  - :func:`assemble_day_bundle` productizes the Phase-0 A/B harness Arm A: it
    reuses ``pulse._query_day_activity`` (the operator activity assembler) and a
    productized operator-calendar block extractor, applying the ``NOISE_REPOS``
    guard ONCE at the assembler boundary.
  - :func:`dedup_teammate_blocks` (with :func:`_norm_title`) lifts the harness's
    de-dup: a teammate calendar block is dropped when it is the SAME meeting the
    operator already has — by shared event id (the live operator∩teammate event-id
    intersection, since the composite PK ``(id, calendar_id)`` means a shared
    invite appears under both) OR by normalized-title equality the same local day.
    What remains is the additive delta.
  - :func:`build_rank_prompt` is a sibling to ``querier._build_prompt``: it
    encodes the calibration levers (owner-bias correction, redundancy/vagueness
    discounts, per-source/per-person weights, drop sensitivity) and asks for a
    single FLAT ranked list. It does NOT call any LLM (Dependency Inversion); the
    caller supplies synthesis via ``querier._synthesize_with_fallback``.
  - :func:`rank_next_actions` orchestrates: assemble the operator bundle, gather
    the additivity-PASSING teammates' blocks, dedup to the additive delta, build
    deterministic candidate objects (so an empty/failed Gemini call still yields a
    degraded-but-ranked view — never blank), build the prompt, synthesize, and
    parse. It NEVER raises.

Privacy: ``person`` / teammate labels are LOCAL-DISPLAY-ONLY. They live on the
in-process candidate/result objects and the local-only cache table created by
migration 0006; they are NEVER part of ``export_calendar_snapshot`` or the
pushed pulse. The teammate reader (``calendar.get_team_upcoming_by_person``) is
the only place that SELECTs ``person`` and stays in-process here.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest.calendar_config import (
    OPERATOR_CALENDAR_ID,
    SignalWeights,
    load_signal_weights,
    team_persons_passing_additivity,
)
from rebalance.ingest.calendar_helpers import (
    event_duration_minutes,
    parse_calendar_dt,
)
from rebalance.ingest.config import get_pulse_config
from rebalance.ingest.db import db_connection, run_migrations
from rebalance.ingest.pulse import _query_day_activity
from rebalance.tz_utils import local_tz

logger = logging.getLogger(__name__)

# git-pulse is the project's own status repo — its commits are noise for a
# "what should I work on next" view, so they are excluded ONCE at the assembler
# boundary (mirrors temp/ab_team_signal.NOISE_REPOS).
NOISE_REPOS = {"hypercart-dev-tools/rebalance-git-pulse"}


# ---------------------------------------------------------------------------
# De-dup — lifted from temp/ab_team_signal.py (they exist nowhere in src/)
# ---------------------------------------------------------------------------


def _norm_title(s: str) -> str:
    """Normalize a block title for content de-dup: lowercase, collapse any
    run of punctuation/separators to a single space so "1:45 - Team Call" ==
    "1:45 Team Call"."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def dedup_teammate_blocks(
    teammate_blocks: list[dict[str, Any]],
    operator_blocks: list[dict[str, Any]],
    *,
    shared_ids: set[str],
) -> tuple[list[dict[str, Any]], int]:
    """Reduce teammate calendar blocks to the strictly-additive delta.

    A teammate block is dropped when it is the SAME meeting the operator already
    has, by either rule:

      - its event ``id`` is in *shared_ids* — the live operator∩teammate event-id
        intersection. Because ``calendar_events`` has a composite PK
        ``(id, calendar_id)``, a shared invite is stored once per calendar, so the
        very same id appears under both the operator's and the teammate's rows.
      - its normalized title (:func:`_norm_title`) equals an operator block's
        normalized title on the SAME local day (teammates hand-log joint meetings
        as their own events, so the ids differ but the meeting is already in the
        operator's arm).

    Returns ``(kept_delta, dropped_count)``. The kept delta is what the teammate
    arm contributes ON TOP of the operator's own signal — never a duplicate.
    """
    # Operator titles bucketed by local day so a same-named meeting on a
    # different day is NOT treated as a duplicate.
    operator_titles_by_day: dict[str, set[str]] = {}
    for blk in operator_blocks:
        operator_titles_by_day.setdefault(blk["local_day"], set()).add(
            _norm_title(blk["summary"])
        )

    kept: list[dict[str, Any]] = []
    dropped = 0
    for blk in teammate_blocks:
        if blk["id"] in shared_ids:
            dropped += 1
            continue
        same_day_titles = operator_titles_by_day.get(blk["local_day"], set())
        if _norm_title(blk["summary"]) in same_day_titles:
            dropped += 1
            continue
        kept.append(blk)
    return kept, dropped


# ---------------------------------------------------------------------------
# Operator bundle (productized harness Arm A)
# ---------------------------------------------------------------------------


def _not_noise(repo: str | None) -> bool:
    """True unless *repo* is a known noise repo (git-pulse status repo)."""
    return (repo or "").lower() not in NOISE_REPOS


def _calendar_block(
    row: dict[str, Any] | Any,
    *,
    tz: Any,
) -> dict[str, Any] | None:
    """Parse one calendar_events row into a localized, bucketed block.

    Reuses :func:`parse_calendar_dt` / :func:`event_duration_minutes` (the
    canonical calendar helpers) to localize the start, bucket it to a local day,
    and compute the duration. Returns ``None`` for an unparseable start (an
    all-day/date-only value has no display instant), so callers can skip it.
    """
    raw_start = row["start_time"]
    try:
        start = parse_calendar_dt(raw_start).astimezone(tz)
    except Exception:  # noqa: BLE001 — unparseable / all-day start: not a timed block
        return None
    return {
        "id": row["id"],
        "summary": row["summary"] or "",
        "time": start.strftime("%H:%M"),
        "local_day": start.date().isoformat(),
        "duration_minutes": event_duration_minutes(raw_start, row["end_time"]),
        "person": row["person"] if "person" in _row_keys(row) else None,
    }


def _row_keys(row: Any) -> Any:
    """Return the column names of a sqlite Row or the keys of a dict."""
    try:
        return row.keys()
    except AttributeError:
        return row


@dataclass
class OperatorBundle:
    """The operator's own day signal — productized harness Arm A.

    Calendar blocks are OPERATOR_CALENDAR_ID-scoped; GitHub activity has the
    NOISE_REPOS guard applied once at this boundary. ``person`` is NULL on every
    operator row by construction (operator rows have ``person IS NULL``).
    """

    local_day: str
    calendar_blocks: list[dict[str, Any]] = field(default_factory=list)
    gh_commits: list[dict[str, Any]] = field(default_factory=list)
    gh_items: list[dict[str, Any]] = field(default_factory=list)
    gh_comments: list[dict[str, Any]] = field(default_factory=list)
    vault_edits: list[dict[str, Any]] = field(default_factory=list)
    sleuth_activity: list[dict[str, Any]] = field(default_factory=list)


def assemble_day_bundle(
    conn: Any,
    *,
    local_day: str,
    start: datetime,
    end: datetime,
    github_login: str,
    slack_user_id: str | None,
    tz: Any,
) -> OperatorBundle:
    """Assemble the operator's own day bundle (Arm A) for [start, end).

    REUSES ``pulse._query_day_activity`` for the operator's activity (vault,
    github, sleuth) rather than re-querying, then layers an OPERATOR_CALENDAR_ID-
    scoped calendar block extractor on top. The ``NOISE_REPOS`` guard is applied
    ONCE here — every downstream consumer can trust the bundle is already clean.
    """
    activity = _query_day_activity(
        conn,
        label=local_day,
        start=start,
        end=end,
        github_login=github_login,
        slack_user_id=slack_user_id,
    )

    # Operator calendar arm — OPERATOR_CALENDAR_ID-scoped (never a teammate id).
    cal_rows = conn.execute(
        "SELECT id, summary, start_time, end_time, person "
        "FROM calendar_events WHERE calendar_id = ?",
        (OPERATOR_CALENDAR_ID,),
    ).fetchall()
    calendar_blocks: list[dict[str, Any]] = []
    for r in cal_rows:
        block = _calendar_block(r, tz=tz)
        if block is None or block["local_day"] != local_day:
            continue
        calendar_blocks.append(block)
    calendar_blocks.sort(key=lambda b: (b["time"], b["summary"]))

    return OperatorBundle(
        local_day=local_day,
        calendar_blocks=calendar_blocks,
        gh_commits=[c for c in activity.gh_commits if _not_noise(c.get("repo"))],
        gh_items=[i for i in activity.gh_items if _not_noise(i.get("repo"))],
        gh_comments=[c for c in activity.gh_comments if _not_noise(c.get("repo"))],
        vault_edits=list(activity.vault_edits),
        sleuth_activity=list(activity.sleuth_activity),
    )


# ---------------------------------------------------------------------------
# Result types — SEPARATE from QueryResult (do not touch it)
# ---------------------------------------------------------------------------


@dataclass
class RankedAction:
    """One ranked next-action.

    ``person`` is LOCAL-DISPLAY-ONLY: the operator's own items carry ``None``;
    teammate-attributed items carry the teammate label. It is never exported.
    """

    rank: int
    title: str
    person: str | None
    source: str
    project: str | None = None
    evidence: list[str] = field(default_factory=list)
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RankedNextActions:
    """The single ranked-output contract the dashboard route and ask() consume.

    ``ranked`` is always populated when there is ANY candidate — the deterministic
    candidate ordering is the fallback floor, so a failed/empty Gemini call yields
    a degraded-but-ranked view, never a blank one. ``person``/labels on the ranked
    items are LOCAL-DISPLAY-ONLY.
    """

    ranked: list[RankedAction] = field(default_factory=list)
    synthesis: str = ""
    model_used: str = ""
    blended: bool = False
    weights_used: dict[str, Any] = field(default_factory=dict)
    note: str = ""
    elapsed_seconds: float = 0.0
    computed_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ranked"] = [a.as_dict() for a in self.ranked]
        return d


# ---------------------------------------------------------------------------
# Prompt assembly — sibling to querier._build_prompt (no LLM call here)
# ---------------------------------------------------------------------------


def build_rank_prompt(
    *,
    operator_candidates: list[RankedAction],
    teammate_delta: list[dict[str, Any]],
    weights: SignalWeights,
    temporal_context: dict[str, Any] | None,
    blended: bool,
) -> str:
    """Assemble the ranking prompt — a flat ranked-list request, no analytics.

    Encodes the calibration levers from :class:`SignalWeights`:
      - ``owner_bias_correction`` ON: do NOT rank an item higher merely for being
        the operator's own; weigh teammate signal on equal evidentiary footing so
        a cross-person dropped ball can outrank the operator's own busywork.
      - ``vagueness_discount`` / ``redundancy_penalty`` / ``drop_sensitivity`` /
        ``per_source`` / ``per_person`` are surfaced as weighting instructions.

    Teammate blocks are rendered with person attribution + classified
    project/duration/blocker, PREFERRED over verbatim teammate detail (data
    minimization). The model is told to rank ONLY from provided context and invent
    nothing. This function does NOT call any LLM (Dependency Inversion).
    """
    sections: list[str] = []

    if temporal_context:
        today = temporal_context.get("today", {})
        tomorrow = temporal_context.get("tomorrow", {})
        lines = ["## Schedule Context"]
        lines.append(
            f"- **Today:** {today.get('day_name', '')} ({today.get('date', '')}) "
            f"— {today.get('day_type', 'workday')}"
        )
        lines.append(
            f"- **Tomorrow:** {tomorrow.get('day_name', '')} ({tomorrow.get('date', '')}) "
            f"— {tomorrow.get('day_type', 'workday')}"
        )
        sections.append("\n".join(lines))

    # [OWN] operator candidates — the operator's own signal.
    if operator_candidates:
        lines = ["## [OWN] Operator signals"]
        for c in operator_candidates:
            proj = f" {{{c.project}}}" if c.project else ""
            ev = f"  — {'; '.join(c.evidence)}" if c.evidence else ""
            lines.append(f"- ({c.source}){proj} {c.title}{ev}")
        sections.append("\n".join(lines))

    # [TEAMMATE] person-attributed blocks — classified project/duration/blocker
    # PREFERRED over verbatim detail (data minimization).
    if blended and teammate_delta:
        lines = ["## [TEAMMATE] Cross-person signals (additive, de-duplicated)"]
        for blk in teammate_delta:
            who = blk.get("person") or "teammate"
            dur = blk.get("duration_minutes") or 0
            proj = f" {{{blk['project']}}}" if blk.get("project") else ""
            lines.append(
                f"- [{who}]{proj} {blk['summary']} "
                f"({blk.get('time', '')}, {dur}m)"
            )
        sections.append("\n".join(lines))

    # Calibration levers.
    lever_lines = ["## Ranking calibration"]
    if weights.owner_bias_correction:
        lever_lines.append(
            "- OWNER-BIAS CORRECTION ON: do not rank an item higher merely because "
            "it is the operator's own. Weigh teammate signal on EQUAL evidentiary "
            "footing — a cross-person dropped ball can and should outrank the "
            "operator's own busywork."
        )
    lever_lines.append(
        f"- Discount vague / low-specificity items (vagueness_discount="
        f"{weights.vagueness_discount})."
    )
    lever_lines.append(
        f"- Penalize an item that merely restates one already counted "
        f"(redundancy_penalty={weights.redundancy_penalty})."
    )
    lever_lines.append(
        f"- A signal that dropped/disappeared moves the ranking "
        f"(drop_sensitivity={weights.drop_sensitivity})."
    )
    lever_lines.append(
        f"- Per-source trust: {json.dumps(weights.per_source)}."
    )
    lever_lines.append(
        f"- Per-person trust: {json.dumps(weights.per_person)}."
    )
    sections.append("\n".join(lever_lines))

    context_block = "\n\n".join(sections)

    return f"""You decide what should be worked on NEXT. Produce a SINGLE FLAT ranked list \
of concrete next actions — not analytics, not a report, not grouped sections.

HARD RULE: rank ONLY from the context provided below. Invent nothing. If the \
context is thin, return fewer items rather than padding.

Apply the ranking calibration. For EACH item output exactly:
  <rank>. <one-line title> | person=<operator|name> | source=<source> \
[| project=<project>] — <one-line why> (evidence: <1-2 pointers>)

<context>
{context_block}
</context>

Ranked next actions:"""


# ---------------------------------------------------------------------------
# Candidate construction (deterministic — the fallback floor)
# ---------------------------------------------------------------------------


def _operator_candidates(bundle: OperatorBundle) -> list[dict[str, Any]]:
    """Deterministic operator candidates with a stable ``rank_key`` each.

    The ordering here is the degraded-but-ranked fallback used verbatim when
    synthesis is skipped or fails. ``rank_key`` sorts higher-signal first:
    sleuth/assigned > github items > calendar > commits > comments > vault.
    """
    out: list[dict[str, Any]] = []

    for s in bundle.sleuth_activity:
        out.append({
            "rank_key": (0, s.get("last_seen_at") or ""),
            "title": s.get("message_preview") or "Sleuth reminder",
            "source": "sleuth",
            "evidence": [f"sleuth/{s.get('state', '')}"],
            "why": "open reminder assigned to/by you",
        })
    for it in bundle.gh_items:
        out.append({
            "rank_key": (1, it.get("updated_at") or it.get("created_at") or ""),
            "title": f"{it.get('item_type', 'item')} #{it.get('number')}: {it.get('title', '')}",
            "source": "github",
            "project": it.get("repo"),
            "evidence": [it.get("html_url") or it.get("repo") or ""],
            "why": "open GitHub item you authored/own",
        })
    for b in bundle.calendar_blocks:
        out.append({
            "rank_key": (2, b.get("time") or ""),
            "title": b.get("summary") or "Calendar block",
            "source": "calendar",
            "evidence": [f"{b.get('time', '')} ({b.get('duration_minutes', 0)}m)"],
            "why": "scheduled block on your calendar",
        })
    for c in bundle.gh_commits:
        out.append({
            "rank_key": (3, c.get("committed_at") or ""),
            "title": c.get("subject") or "commit",
            "source": "github",
            "project": c.get("repo"),
            "evidence": [c.get("html_url") or (c.get("sha") or "")],
            "why": "recent commit (continue / push?)",
        })
    for cm in bundle.gh_comments:
        out.append({
            "rank_key": (4, cm.get("created_at") or ""),
            "title": cm.get("preview") or "comment",
            "source": "github",
            "project": cm.get("repo"),
            "evidence": [cm.get("html_url") or ""],
            "why": "thread you engaged on",
        })
    for v in bundle.vault_edits:
        out.append({
            "rank_key": (5, v.get("last_modified") or ""),
            "title": v.get("title") or v.get("rel_path") or "vault note",
            "source": "vault",
            "evidence": [v.get("rel_path") or ""],
            "why": "recently edited note",
        })

    # Higher signal class first; within a class, most-recent first.
    out.sort(key=lambda c: (c["rank_key"][0], _neg_iso(c["rank_key"][1])))
    return out


def _neg_iso(value: str) -> str:
    """Sort helper: invert an ISO string so a plain ascending sort puts newest
    first. Empty strings sort last (least recent)."""
    # ISO strings compare lexicographically; we want descending within a class.
    # Map to a key that ascends as the timestamp descends by complementing chars.
    if not value:
        return "￿"  # empty → least recent → last
    return "".join(chr(0x10FFFD - ord(ch)) if ord(ch) < 0x10FFFD else ch for ch in value)


def _teammate_candidate(blk: dict[str, Any]) -> dict[str, Any]:
    """Deterministic candidate for one teammate delta block."""
    who = blk.get("person") or "teammate"
    dur = blk.get("duration_minutes") or 0
    return {
        "rank_key": (1, blk.get("time") or ""),  # teammate calendar ~ github tier
        "title": blk.get("summary") or "Teammate block",
        "person": who,
        "source": "calendar",
        "project": blk.get("project"),
        "evidence": [f"{who} {blk.get('time', '')} ({dur}m)"],
        "why": "cross-person signal you are not already tracking",
    }


def _candidate_to_action(c: dict[str, Any], rank: int) -> RankedAction:
    return RankedAction(
        rank=rank,
        title=str(c.get("title") or "").strip()[:200],
        person=c.get("person"),
        source=str(c.get("source") or ""),
        project=c.get("project"),
        evidence=[e for e in (c.get("evidence") or []) if e],
        why=str(c.get("why") or ""),
    )


# ---------------------------------------------------------------------------
# Synthesis parsing
# ---------------------------------------------------------------------------

_RANK_LINE = re.compile(r"^\s*(\d+)[.)]\s*(.+)$")


def _parse_ranked_synthesis(text: str) -> list[RankedAction]:
    """Parse the model's flat ranked list back into :class:`RankedAction`.

    Tolerant: matches numbered lines ``N. <title> | person=.. | source=.. — why``.
    Any line that doesn't match is ignored. Returns ``[]`` if nothing parses, so
    the caller can fall back to the deterministic candidate ordering.
    """
    actions: list[RankedAction] = []
    for line in (text or "").splitlines():
        m = _RANK_LINE.match(line)
        if not m:
            continue
        rank = int(m.group(1))
        rest = m.group(2).strip()

        # Split the title off the first " | " field; pull why off " — ".
        title = rest
        person: str | None = None
        source = ""
        project: str | None = None
        why = ""

        if " — " in rest:
            head, why = rest.split(" — ", 1)
        else:
            head = rest
        why = why.strip()

        fields = [f.strip() for f in head.split("|")]
        title = fields[0].strip()
        for fld in fields[1:]:
            low = fld.lower()
            if low.startswith("person="):
                val = fld.split("=", 1)[1].strip()
                person = None if val.lower() in ("operator", "self", "me", "") else val
            elif low.startswith("source="):
                source = fld.split("=", 1)[1].strip()
            elif low.startswith("project="):
                project = fld.split("=", 1)[1].strip() or None

        if not title:
            continue
        actions.append(RankedAction(
            rank=rank, title=title[:200], person=person,
            source=source, project=project, why=why,
        ))
    return actions


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _local_day_window(now: datetime | None, tz: Any) -> tuple[str, datetime, datetime]:
    """Return (local_day_iso, day_start, day_end) for the local day of *now*."""
    current = now.astimezone(tz) if now is not None else datetime.now(tz)
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.date().isoformat(), start, end


def _shared_event_ids(
    conn: Any,
    *,
    operator_blocks: list[dict[str, Any]],
    persons: list[str],
) -> set[str]:
    """Live operator∩teammate event-id intersection (NO frozen JSON).

    The composite PK ``(id, calendar_id)`` means a shared invite is stored once
    per calendar, so the same ``id`` appears under both the operator's row and a
    teammate's row. The intersection is exactly the set of operator event ids that
    also exist as a teammate (person-labelled) row.
    """
    operator_ids = {b["id"] for b in operator_blocks if b.get("id")}
    if not operator_ids or not persons:
        return set()
    placeholders = ",".join("?" for _ in persons)
    rows = conn.execute(
        f"SELECT DISTINCT id FROM calendar_events WHERE person IN ({placeholders})",
        tuple(persons),
    ).fetchall()
    teammate_ids = {r["id"] for r in rows if r["id"]}
    return operator_ids & teammate_ids


def rank_next_actions(
    database_path: Path,
    *,
    blend_team: bool = True,
    since_days: int = 7,
    weights: SignalWeights | None = None,
    now: datetime | None = None,
    synthesize: bool = True,
) -> RankedNextActions:
    """Produce the ranked "what should we work on next" list. NEVER raises.

    1. Assemble the operator bundle (Arm A) for the local day.
    2. If ``blend_team``: gather teammate blocks via
       ``calendar.get_team_upcoming_by_person`` for the additivity-PASSING persons
       only (per-person event counts in window vs ``weights.min_team_events``;
       Matt passes, sparse Jose/Jinhui are gated), dedup to the additive delta.
    3. Build deterministic candidates (the fallback floor), then ``build_rank_prompt``.
    4. When ``synthesize``: call ``querier._synthesize_with_fallback`` and parse;
       ALWAYS keep the deterministic candidate ordering as the fallback so an
       empty/failed call still yields a ranked (degraded) view, never blank.

    On any internal failure the result is a valid empty-but-noted
    :class:`RankedNextActions` (never an exception). Logs a warning when the ranked
    output is empty.
    """
    started = time.monotonic()
    tz = local_tz()
    weights = weights or load_signal_weights()
    local_day, day_start, day_end = _local_day_window(now, tz)

    note = ""
    blended = False
    teammate_delta: list[dict[str, Any]] = []
    operator_candidates_raw: list[dict[str, Any]] = []

    cfg = get_pulse_config()
    github_login = cfg.get("github_login") or ""
    slack_user_id = cfg.get("slack_user_id")

    try:
        with db_connection(database_path) as conn:
            run_migrations(conn)
            bundle = assemble_day_bundle(
                conn,
                local_day=local_day,
                start=day_start,
                end=day_end,
                github_login=github_login,
                slack_user_id=slack_user_id,
                tz=tz,
            )
            operator_candidates_raw = _operator_candidates(bundle)

            if blend_team:
                teammate_delta, blended, note = _gather_teammate_delta(
                    conn,
                    database_path=database_path,
                    operator_blocks=bundle.calendar_blocks,
                    weights=weights,
                    since_days=since_days,
                    tz=tz,
                )
    except Exception as exc:  # noqa: BLE001 — never raise out of the keystone
        logger.warning("rank_next_actions: assembly failed: %s", exc)
        return RankedNextActions(
            ranked=[],
            blended=False,
            weights_used=_weights_summary(weights),
            note=f"assembly failed: {exc}",
            elapsed_seconds=round(time.monotonic() - started, 2),
            computed_at=datetime.now(timezone.utc).isoformat(),
        )

    # Deterministic candidate objects (operator + additive teammate delta).
    operator_actions = [
        _candidate_to_action(c, i)
        for i, c in enumerate(operator_candidates_raw, 1)
    ]
    teammate_actions = [
        _candidate_to_action(_teammate_candidate(b), 0) for b in teammate_delta
    ]
    # The fallback floor: operator candidates, then the additive teammate delta.
    fallback = operator_actions + teammate_actions
    for i, a in enumerate(fallback, 1):
        a.rank = i

    synthesis = ""
    model_used = ""
    ranked = fallback
    if synthesize:
        prompt = build_rank_prompt(
            operator_candidates=operator_actions,
            teammate_delta=teammate_delta,
            weights=weights,
            temporal_context=None,
            blended=blended,
        )
        try:
            from rebalance.ingest.querier import _synthesize_with_fallback

            synthesis, model_used = _synthesize_with_fallback(prompt)
            parsed = _parse_ranked_synthesis(synthesis)
            if parsed:
                ranked = parsed
            else:
                note = (note + "; " if note else "") + "synthesis parsed to nothing; using deterministic order"
        except Exception as exc:  # noqa: BLE001 — degrade, don't blow up
            logger.warning("rank_next_actions: synthesis failed: %s", exc)
            note = (note + "; " if note else "") + f"synthesis failed: {exc}"

    if not ranked:
        logger.warning(
            "rank_next_actions: empty ranked output (blended=%s, local_day=%s)",
            blended, local_day,
        )

    return RankedNextActions(
        ranked=ranked,
        synthesis=synthesis,
        model_used=model_used,
        blended=blended,
        weights_used=_weights_summary(weights),
        note=note,
        elapsed_seconds=round(time.monotonic() - started, 2),
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


def _gather_teammate_delta(
    conn: Any,
    *,
    database_path: Path,
    operator_blocks: list[dict[str, Any]],
    weights: SignalWeights,
    since_days: int,
    tz: Any,
) -> tuple[list[dict[str, Any]], bool, str]:
    """Gather the additivity-PASSING teammates' blocks, deduped to the delta.

    Returns ``(teammate_delta, blended, note)``. ``blended`` is True whenever the
    team arm was actually consulted (even if the delta is empty). Persons are
    gated by ``team_persons_passing_additivity`` on their in-window event counts.
    """
    from rebalance.ingest.calendar import get_team_upcoming_by_person
    from rebalance.ingest.calendar_config import CalendarConfig

    roster = [tc.person for tc in CalendarConfig.load().team_calendars]
    if not roster:
        return [], True, "no team_calendars configured (operator-only)"

    # Per-person event counts in the recent window — the additivity input.
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    placeholders = ",".join("?" for _ in roster)
    rows = conn.execute(
        f"SELECT person, COUNT(*) AS n FROM calendar_events "
        f"WHERE person IN ({placeholders}) AND start_time >= ? "
        f"GROUP BY person",
        (*roster, since),
    ).fetchall()
    counts = {r["person"]: r["n"] for r in rows}
    # Preserve roster order so the additivity filter is deterministic.
    event_counts = {p: counts.get(p, 0) for p in roster}
    passing = team_persons_passing_additivity(event_counts, weights.min_team_events)

    if not passing:
        return [], True, "no teammate passed the additivity threshold (operator-only)"

    # get_team_upcoming_by_person is the ONLY reader that SELECTs `person`.
    raw = get_team_upcoming_by_person(database_path, passing, days_forward=2)
    teammate_blocks: list[dict[str, Any]] = []
    for ev in raw:
        block = _calendar_block(ev, tz=tz)
        if block is None:
            continue
        block["person"] = ev.get("person")
        teammate_blocks.append(block)

    shared_ids = _shared_event_ids(conn, operator_blocks=operator_blocks, persons=passing)
    delta, dropped = dedup_teammate_blocks(
        teammate_blocks, operator_blocks, shared_ids=shared_ids
    )
    note = (
        f"team blended: {len(passing)} person(s) passed additivity, "
        f"{len(delta)} additive block(s), {dropped} deduped"
    )
    return delta, True, note


def _weights_summary(weights: SignalWeights) -> dict[str, Any]:
    """A JSON-safe summary of the weights that produced a ranking (for the cache)."""
    return {
        "per_person": weights.per_person,
        "per_source": weights.per_source,
        "redundancy_penalty": weights.redundancy_penalty,
        "vagueness_discount": weights.vagueness_discount,
        "owner_bias_correction": weights.owner_bias_correction,
        "drop_sensitivity": weights.drop_sensitivity,
        "min_team_events": weights.min_team_events,
    }


# ---------------------------------------------------------------------------
# Persistence — precompute -> SQLite cache (migration 0006)
#
# LOCAL-ONLY: the ranked_next_actions cache table carries teammate `person`
# labels in its payload_json and is NEVER part of export_calendar_snapshot or the
# pushed pulse. It is a device-local precompute, mirroring focus5_scan's roster
# cache. Do not add it to any export/sync path.
# ---------------------------------------------------------------------------


def persist_ranked_next_actions(database_path: Path, result: RankedNextActions) -> None:
    """Persist *result* to the local ``ranked_next_actions`` cache table.

    Mirrors ``focus5_scan`` persistence: ensures migrations, then inserts one
    cache row. The latest row (by ``computed_at``) is what ``load_*`` returns.
    """
    with db_connection(database_path) as conn:
        run_migrations(conn)
        conn.execute(
            "INSERT INTO ranked_next_actions "
            "(computed_at, blended, model_used, payload_json, weights_json) "
            "VALUES (?,?,?,?,?)",
            (
                result.computed_at or datetime.now(timezone.utc).isoformat(),
                1 if result.blended else 0,
                result.model_used,
                json.dumps(result.as_dict(), ensure_ascii=False),
                json.dumps(result.weights_used, ensure_ascii=False),
            ),
        )
        conn.commit()


def load_ranked_next_actions(database_path: Path) -> RankedNextActions | None:
    """Return the latest persisted :class:`RankedNextActions`, or ``None``.

    Reads the freshest cache row (highest ``computed_at``) and rebuilds the
    dataclass from ``payload_json``. Returns ``None`` when the table is absent or
    empty (a brand-new DB).
    """
    try:
        with db_connection(database_path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM ranked_next_actions "
                "ORDER BY computed_at DESC LIMIT 1"
            ).fetchone()
    except Exception:  # noqa: BLE001 — table absent on a brand-new DB
        return None
    if row is None:
        return None
    try:
        payload = json.loads(row["payload_json"])
    except (json.JSONDecodeError, TypeError):
        return None
    ranked = [
        RankedAction(
            rank=a.get("rank", 0),
            title=a.get("title", ""),
            person=a.get("person"),
            source=a.get("source", ""),
            project=a.get("project"),
            evidence=list(a.get("evidence") or []),
            why=a.get("why", ""),
        )
        for a in payload.get("ranked", [])
    ]
    return RankedNextActions(
        ranked=ranked,
        synthesis=payload.get("synthesis", ""),
        model_used=payload.get("model_used", ""),
        blended=bool(payload.get("blended", False)),
        weights_used=payload.get("weights_used", {}),
        note=payload.get("note", ""),
        elapsed_seconds=payload.get("elapsed_seconds", 0.0),
        computed_at=payload.get("computed_at", ""),
    )


def get_ranked_meta(database_path: Path) -> dict[str, Any]:
    """Cheap freshness check for the ranked cache (no payload parse): when + how many.

    Lets the web route decide whether to lazily recompute on a stale TTL without
    deserializing the full payload first. Mirrors ``focus5_scan.get_roster_meta``.
    """
    try:
        with db_connection(database_path) as conn:
            row = conn.execute(
                "SELECT computed_at, blended, model_used FROM ranked_next_actions "
                "ORDER BY computed_at DESC LIMIT 1"
            ).fetchone()
            n = conn.execute(
                "SELECT COUNT(*) FROM ranked_next_actions"
            ).fetchone()[0]
    except Exception:  # noqa: BLE001 — table absent on a brand-new DB
        return {"computed_at": None, "blended": None, "model_used": None, "row_count": 0}
    return {
        "computed_at": row["computed_at"] if row else None,
        "blended": bool(row["blended"]) if row else None,
        "model_used": row["model_used"] if row else None,
        "row_count": n,
    }
