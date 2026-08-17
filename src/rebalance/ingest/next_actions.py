"""P2 v0.5 "what should we work on next" — the single ranked-output service.

This is the keystone the dashboard route AND the ``ask`` surface both call, so
the two never drift: a flat, ranked "next actions" list assembled from the
operator's own signals (calendar + GitHub + vault + sleuth + email + figma)
blended with a strictly-additive, de-duplicated delta of teammate calendar signal.

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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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
from rebalance.ingest.config import get_pulse_config, get_vault_path
from rebalance.lib.time_ops import parse_date, parse_iso
from rebalance.ingest.db import db_connection, run_migrations
from rebalance.ingest.pulse import _query_day_activity, collect_pulse_snapshot
from rebalance.tz_utils import format_local, local_tz

logger = logging.getLogger(__name__)

# git-pulse is the project's own status repo — its commits are noise for a
# "what should I work on next" view, so they are excluded ONCE at the assembler
# boundary (mirrors temp/ab_team_signal.NOISE_REPOS).
NOISE_REPOS = {"hypercart-dev-tools/rebalance-git-pulse"}

# priority_tier is 1 (highest) .. 5 (lowest). At/above this tier a project is a
# low-cadence/periodic effort (e.g. a weekly devops repo) and is SOFT down-weighted
# in the ranking — tagged for the synthesis and sunk in the deterministic fallback,
# never muted. # ponytail: one threshold constant, no new config surface.
_DEPRIORITIZE_TIER = 4


def _is_low_priority(project: str | None, priority_by_project: dict[str, int]) -> bool:
    """True when *project*'s effective priority_tier marks it low-cadence/periodic.

    Drives both the ``[priority:low]`` prompt tag and the deterministic fallback
    demotion, so the soft down-weight is defined in exactly one place.
    """
    if not project:
        return False
    return priority_by_project.get(project, 0) >= _DEPRIORITIZE_TIER


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
    email_activity: list[dict[str, Any]] = field(default_factory=list)
    figma_activity: list[dict[str, Any]] = field(default_factory=list)


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
        email_activity=list(activity.email_activity),
        figma_activity=list(activity.figma_activity),
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
    # ``automation``: this action looks like a concrete code/repo task that could
    # be filed as a GitHub issue and handed to a coding agent (Codex / Claude
    # Code). For now it only drives an "automation" tag in the UI — no issue is
    # created and no agent is triggered (that hook is future work).
    automation: bool = False

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
    client_by_project: dict[str, str] | None = None,
    client_roster: dict[str, list[str]] | None = None,
    priority_by_project: dict[str, int] | None = None,
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
    clients = client_by_project or {}
    priorities = priority_by_project or {}
    if operator_candidates:
        lines = ["## [OWN] Operator signals"]
        for c in operator_candidates:
            proj = f" {{{c.project}}}" if c.project else ""
            client = clients.get(c.project) if c.project else None
            cli = f" [client:{client}]" if client else ""
            pri = " [priority:low]" if _is_low_priority(c.project, priorities) else ""
            ev = f"  — {'; '.join(c.evidence)}" if c.evidence else ""
            lines.append(f"- ({c.source}){proj}{cli}{pri} {c.title}{ev}")
        sections.append("\n".join(lines))

    # Client roster — the discrete client buckets, so synthesis can group items by
    # client and surface an at-risk client whose projects are individually quiet.
    if client_roster:
        roster = ["## Client roster (group ranked items by client)"]
        for client, projects in sorted(client_roster.items()):
            roster.append(f"- {client}: {', '.join(sorted(projects))}")
        sections.append("\n".join(roster))

    # [TEAMMATE] person-attributed blocks — classified project/duration/blocker
    # PREFERRED over verbatim detail (data minimization). The section header
    # carries each teammate's NAME so the model can echo it verbatim into
    # ``person=<TeammateName>`` (the attribution mapping in the OUTPUT CONTRACT).
    if blended and teammate_delta:
        lines = ["## [TEAMMATE] Cross-person signals (additive, de-duplicated)"]
        lines.append(
            "- These are HIGH-VALUE: a teammate item here has NO matching operator "
            "signal (it is already the de-duplicated additive delta). A high-evidence "
            "teammate item with no operator counterpart is the highest-value class — "
            "surface it at or near the TOP."
        )
        for blk in teammate_delta:
            who = blk.get("person") or "teammate"
            dur = blk.get("duration_minutes") or 0
            proj = f" {{{blk['project']}}}" if blk.get("project") else ""
            # Header carries the teammate name → echo it into person=<name>.
            lines.append(
                f"- [TEAMMATE: {who}]{proj} {blk['summary']} "
                f"({blk.get('time', '')}, {dur}m)"
            )
        sections.append("\n".join(lines))

    # Calibration levers.
    lever_lines = ["## Ranking calibration"]
    lever_lines.append(
        "All weights below are multipliers in [0.0, 1.0] where 1.0 = full effect "
        "and lower = weaker; apply them when ordering items."
    )
    if weights.owner_bias_correction:
        lever_lines.append(
            "- OWNER-BIAS CORRECTION ON: do not rank an item higher merely because "
            "it is the operator's own. Weigh teammate signal on EQUAL evidentiary "
            "footing — a cross-person dropped ball can and should outrank the "
            "operator's own busywork."
        )
    lever_lines.append(
        f"- VAGUENESS, both directions: DOWN-weight vague items (untitled holds, "
        f"'focus time', 'catch up', generic blocks) by vagueness_discount="
        f"{weights.vagueness_discount}; UP-weight items naming a concrete artifact "
        f"(a specific PR/issue number, a named meeting/project) to the same degree. "
        f"A named PR should outrank a vague hold of equal recency."
    )
    lever_lines.append(
        f"- Penalize an item that merely restates one already counted "
        f"(redundancy_penalty={weights.redundancy_penalty})."
    )
    if any(_is_low_priority(c.project, priorities) for c in operator_candidates):
        lever_lines.append(
            "- PRIORITY DOWN-WEIGHT: an item tagged [priority:low] belongs to a "
            "low-cadence/periodic project (e.g. a weekly devops/sync repo). Rank it "
            "BELOW comparable items unless its evidence is unusually strong or "
            "time-critical. Down-weight, do not drop — it stays in the list."
        )
    lever_lines.append(
        f"- A signal that dropped/disappeared moves the ranking "
        f"(drop_sensitivity={weights.drop_sensitivity})."
    )
    lever_lines.append(
        "- DROPPED-BALL CLASS (highest value): a high-evidence teammate item with no "
        "matching operator signal is the most valuable thing to surface — rank it at "
        "or near the top."
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

## OUTPUT CONTRACT
For EACH ranked item, output exactly ONE line in this EXACT pipe grammar — same \
field order and keys every time:

  <rank>. <title> | person=<operator|TeammateName> | source=<source> | project=<project-or-empty> | evidence=<p1; p2> | automation=<yes|no> | why=<one-line reason>

Rules:
- Keys are literal and in this order: person= , source= , project= , evidence= , automation= , why=
- ATTRIBUTION: for an [OWN] item write `person=operator`; for a [TEAMMATE] item \
write `person=<the teammate name shown in its section header>` (the name after \
"TEAMMATE:" in that item's bullet).
- source= is the source token of the item (e.g. github, calendar, sleuth, vault).
- project= is the project/repo name, or EMPTY if none (write nothing after the `=`).
- evidence= is 1-2 concrete pointers separated by '; ' (a PR/issue URL or number, a \
time, a path).
- automation=yes ONLY if this item is a concrete code/repo task that could be filed \
as a GitHub issue and handed to a coding agent (Codex / Claude Code) — a bug fix, a \
named PR/issue/plugin/config change, a refactor, a migration. automation=no for \
meetings, emails, reviews needing human judgement, planning, or vague holds.
- why= is a single short reason.
- Output ONLY the numbered list — no preamble, no trailing commentary, no headers, \
no grouping, no sub-bullets.

<context>
{context_block}
</context>

Ranked next actions:"""


# ---------------------------------------------------------------------------
# Candidate construction (deterministic — the fallback floor)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Per-source candidate providers (registry-driven — Principle 3).
#
# Each provider owns ONE source's candidate shape and is registered on that
# source's Collector via the ``candidates=`` seam (mirroring ``semantic_docs=``)
# in index_ops.py. ``_operator_candidates`` walks the registry and calls them —
# a new work signal reaches the ranked verdict by REGISTERING a collector, never
# by editing this dispatch. ``rank_key`` sorts higher-signal first:
#   sleuth 0 · email 1 · gh_items 2 · calendar 3 · gh_commits 4 · gh_comments 5
#   · figma 6 · vault 7.
# ATTESTED (D2): every candidate carries source, non-empty evidence, and why.
# ---------------------------------------------------------------------------


def sleuth_candidates(bundle: OperatorBundle) -> list[dict[str, Any]]:
    return [
        {
            "rank_key": (0, s.get("last_seen_at") or ""),
            "title": s.get("message_preview") or "Sleuth reminder",
            "source": "sleuth",
            "evidence": [f"sleuth/{s.get('state', '')}"],
            "why": "open reminder assigned to/by you",
        }
        for s in bundle.sleuth_activity
    ]


def email_candidates(bundle: OperatorBundle) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    dropped = 0
    for m in bundle.email_activity:
        subject = (m.get("subject") or "").strip()
        sender = (m.get("from_name") or m.get("from_address") or "").strip()
        # Signal-quality guard: drop CONTENTLESS rows. The Gmail collector can land
        # a message_id + labels while failing to populate the headers — on the live
        # DB (2026-07-14) 119 of 124 rows are exactly that: no sender, no subject.
        # Such a row has nothing to attest with, and email ranks at tier 1 — ABOVE
        # your open GitHub items — so admitting it would push "(no subject) from
        # unknown sender" to the top of the list. That is the bare verdict the
        # Attested pillar forbids. A row needs a subject OR a sender to earn a rank.
        if not subject and not sender:
            dropped += 1
            continue
        out.append({
            "rank_key": (1, m.get("received_at") or ""),
            "title": subject or "(no subject)",
            "source": "email",
            "evidence": [f"from {sender or 'unknown sender'}", m.get("received_at") or ""],
            "why": "email received in the day window",
        })
    if dropped:
        # NON-SILENT: a dropped row is an INGEST defect, not noise to swallow. Source
        # freshness reports "ok" whenever rows exist, so a collector writing header-less
        # rows would otherwise look healthy while contributing nothing. Say it out loud.
        logger.warning(
            "email_candidates: dropped %d contentless email row(s) (no sender, no subject) "
            "— the Gmail collector is landing rows without headers; ranking is starved, "
            "not empty",
            dropped,
        )
    return out


def github_candidates(bundle: OperatorBundle) -> list[dict[str, Any]]:
    """Three candidate classes from the one GitHub source: items, commits, comments."""
    out: list[dict[str, Any]] = []
    for it in bundle.gh_items:
        out.append({
            "rank_key": (2, it.get("updated_at") or it.get("created_at") or ""),
            "title": f"{it.get('item_type', 'item')} #{it.get('number')}: {it.get('title', '')}",
            "source": "github",
            "project": it.get("repo"),
            "evidence": [it.get("html_url") or it.get("repo") or ""],
            "why": "open GitHub item you authored/own",
        })
    for c in bundle.gh_commits:
        direct_push = c.get("source_kind") == "direct_push"
        paths = [path for path in c.get("paths", []) if path][:5]
        evidence = [c.get("html_url") or (c.get("sha") or "")]
        evidence.extend(paths)
        out.append({
            "rank_key": (4, c.get("committed_at") or ""),
            "title": c.get("subject") or "commit",
            "source": "github",
            "project": c.get("repo"),
            "evidence": evidence,
            "why": (
                "unreviewed direct branch push (inspect or continue?)"
                if direct_push else "recent commit (continue / push?)"
            ),
        })
    for cm in bundle.gh_comments:
        out.append({
            "rank_key": (5, cm.get("created_at") or ""),
            "title": cm.get("preview") or "comment",
            "source": "github",
            "project": cm.get("repo"),
            "evidence": [cm.get("html_url") or ""],
            "why": "thread you engaged on",
        })
    return out


def calendar_candidates(bundle: OperatorBundle) -> list[dict[str, Any]]:
    return [
        {
            "rank_key": (3, b.get("time") or ""),
            "title": b.get("summary") or "Calendar block",
            "source": "calendar",
            "evidence": [f"{b.get('time', '')} ({b.get('duration_minutes', 0)}m)"],
            "why": "scheduled block on your calendar",
        }
        for b in bundle.calendar_blocks
    ]


def figma_candidates(bundle: OperatorBundle) -> list[dict[str, Any]]:
    # ponytail: this arm ships DORMANT — figma_activity is empty until a
    # configured `figma_file_keys` allow-list turns the opt-in collector on.
    # It is correct-and-idle, not dead: Figma is an explicit product signal.
    out: list[dict[str, Any]] = []
    for fc in bundle.figma_activity:
        handle = fc.get("user_handle") or "someone"
        out.append({
            "rank_key": (6, fc.get("created_at") or ""),
            "title": fc.get("message") or "Figma comment",
            "source": "figma",
            "project": fc.get("file_key"),
            "evidence": [f"{handle} on figma/{fc.get('file_key', '')}"],
            "why": "unresolved Figma comment on a watched file",
        })
    return out


def vault_candidates(bundle: OperatorBundle) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for v in bundle.vault_edits:
        # Skip rebalance's OWN generated next-actions file: it is rewritten every
        # refresh, so it would otherwise always show up as a "recent edit" and
        # rank itself (a self-reference feedback loop).
        if _is_generated_next_actions_file(v.get("rel_path") or "", v.get("title") or ""):
            continue
        out.append({
            "rank_key": (7, v.get("last_modified") or ""),
            "title": v.get("title") or v.get("rel_path") or "vault note",
            "source": "vault",
            "evidence": [v.get("rel_path") or ""],
            "why": "recently edited note",
        })
    return out


def _operator_candidates(bundle: OperatorBundle) -> list[dict[str, Any]]:
    """Deterministic operator candidates — a WALK over the collector registry.

    Each registered :class:`Collector` with a ``candidates=`` provider owns its
    own candidate shape; this walks them all and sorts by ``rank_key`` (higher
    signal class first, most-recent first within a class). There is NO per-source
    dispatch here: a source reaches the ranked verdict by registering a collector,
    not by editing this function (GUIDING-PRINCIPLES Principle 3). The import is
    local so the ranker never hard-depends on the registry module at import time.
    """
    from rebalance.ingest.index_ops import COLLECTORS

    out: list[dict[str, Any]] = []
    for collector in COLLECTORS.values():
        if collector.candidates is None:
            continue
        out.extend(collector.candidates(bundle))

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


def _is_generated_next_actions_file(rel_path: str, title: str) -> bool:
    """True for rebalance's own generated What-To-Do-Next vault file, so it is
    excluded from next-action candidates (it must not rank itself).

    ``VAULT_NEXT_ACTIONS_RELPATH`` is defined later in the module (with the
    render sink); referenced here at call time, which is fine."""
    fname = VAULT_NEXT_ACTIONS_RELPATH.rsplit("/", 1)[-1].lower()  # "what to do next.md"
    stem = fname.rsplit(".", 1)[0]                                  # "what to do next"
    return (rel_path or "").lower().endswith(fname) or (title or "").strip().lower() == stem


def _teammate_candidate(blk: dict[str, Any]) -> dict[str, Any]:
    """Deterministic candidate for one teammate delta block."""
    who = blk.get("person") or "teammate"
    dur = blk.get("duration_minutes") or 0
    return {
        "rank_key": (2, blk.get("time") or ""),  # teammate calendar ~ gh_items tier
        "title": blk.get("summary") or "Teammate block",
        "person": who,
        "source": "calendar",
        "project": blk.get("project"),
        "evidence": [f"{who} {blk.get('time', '')} ({dur}m)"],
        "why": "cross-person signal you are not already tracking",
    }


# Code/repo-task keywords → a task a coding agent (Codex / Claude Code) could pick
# up from a GitHub issue. Used to infer the ``automation`` tag deterministically
# (the fallback floor) and when the model omits ``automation=``.
_AUTOMATION_RE = re.compile(
    r"\b(fix|bug|implement|refactor|migrat\w*|plugin|deploy|endpoint|api|"
    r"webhook|schema|query|test\w*|build|ci|merge|revert|patch|release|"
    r"pr\s*#?\d+|issue\s*#?\d+|gh\s*#?\d+|repo|hotfix|crash|error|regression)\b",
    re.IGNORECASE,
)


def _infer_automation(source: str, title: str, project: str | None) -> bool:
    """Heuristic: could this action become a GitHub issue handed to a coding agent?

    Conservative: GitHub-sourced items (commits/PRs/issues) qualify; anything else
    only qualifies when its title/project names a concrete code/repo task. Meetings,
    emails, and vague calendar holds stay ``False``. This is the deterministic
    counterpart to the model's ``automation=`` field — no issue is created here.
    """
    if (source or "").lower() == "github":
        return True
    haystack = f"{title or ''} {project or ''}"
    return bool(_AUTOMATION_RE.search(haystack))


def _candidate_to_action(c: dict[str, Any], rank: int) -> RankedAction:
    title = str(c.get("title") or "").strip()[:200]
    source = str(c.get("source") or "")
    project = c.get("project")
    automation = c.get("automation")
    if automation is None:
        automation = _infer_automation(source, title, project)
    return RankedAction(
        rank=rank,
        title=title,
        person=c.get("person"),
        source=source,
        project=project,
        evidence=[e for e in (c.get("evidence") or []) if e],
        why=str(c.get("why") or ""),
        automation=bool(automation),
    )


# ---------------------------------------------------------------------------
# Synthesis parsing
# ---------------------------------------------------------------------------

# A list-item line: a leading number (``N.``/``N)``, optionally signed so a
# stray ``-3.`` still parses) OR a bullet marker (``-``/``*``/``•``), then the
# payload. The number branch is tried FIRST so ``-3.`` reads as a (bad) rank, not
# a ``-`` bullet. Ranks are re-sequenced by emit ORDER regardless (model rank
# integers are NOT trusted — they can be negative/zero/duplicate).
_LIST_LINE = re.compile(r"^\s*(?:-?\d+\s*[.)]|[-*•])\s+(.+)$")


def _strip_markdown(s: str) -> str:
    """Strip leading/trailing ``**``/``*``/backticks/whitespace from a fragment."""
    return s.strip().strip("*`").strip()


# An unfilled ``<...>`` template token. A small/weak model sometimes echoes the
# OUTPUT CONTRACT format spec (``<rank>. <title> | person=<operator|Name> ...``)
# verbatim instead of substituting real values. Such a line is junk, not a real
# action — reject it so the deterministic fallback survives (this was the live
# Qwen-0.6B failure mode: placeholder titles persisted because the OTHER fields
# were also echoed and passed the structured-field gate).
_PLACEHOLDER_VALUE_RE = re.compile(r"^<[^<>]+>$")
_TITLE_PLACEHOLDER_RE = re.compile(r"<\s*(?:rank|title)\s*>", re.IGNORECASE)


def _value_is_placeholder(val: str) -> bool:
    """True when *val* is wholly an unfilled ``<...>`` template token."""
    return bool(_PLACEHOLDER_VALUE_RE.match((val or "").strip()))


def _title_is_placeholder(title: str) -> bool:
    """True when the model echoed the literal ``<rank>``/``<title>`` format spec
    (or a bare ``<...>`` token) instead of producing a real title."""
    t = (title or "").strip()
    return bool(_TITLE_PLACEHOLDER_RE.search(t) or _PLACEHOLDER_VALUE_RE.match(t))


def _parse_ranked_synthesis(text: str) -> list[RankedAction]:
    """Parse the model's flat ranked list back into :class:`RankedAction`.

    Parses the uniform pipe grammar emitted by :func:`build_rank_prompt`::

        <rank>. <title> | person=<operator|name> | source=<source>
                | project=<p-or-empty> | evidence=<p1; p2> | why=<reason>

    ``title`` is the text BEFORE the first ` | `; each ` | key=value` field is
    parsed into person/source/project/evidence(split on '; ' into a list)/why.
    Ranks are re-sequenced 1..N by emitted ORDER (model rank integers are not
    trusted). Tolerant of bullet markers (``-``/``*``/``•``) — a bulleted line
    gets a position-assigned rank. Markdown (``**``) is stripped from the title.
    Returns ``[]`` when nothing list-shaped parses, so the caller can fall back
    to the deterministic candidate ordering.
    """
    actions: list[RankedAction] = []
    for line in (text or "").splitlines():
        m = _LIST_LINE.match(line)
        if not m:
            continue
        rest = m.group(1).strip()

        # title = everything before the first ` | `; fields follow.
        # Tolerate stray dash variants of the separator (e.g. "|-", " — ").
        parts = re.split(r"\s*\|\s*", rest)
        title = _strip_markdown(parts[0])

        # Reject a line whose title is an unfilled template token (e.g. the model
        # echoed `<rank>. <title>`). When the model echoes the WHOLE spec, every
        # line is dropped here → parsed == [] → caller keeps the deterministic
        # fallback instead of surfacing placeholder junk.
        if _title_is_placeholder(title):
            continue

        person: str | None = None
        source = ""
        project: str | None = None
        evidence: list[str] = []
        why = ""
        automation: bool | None = None

        for fld in parts[1:]:
            if "=" not in fld:
                continue
            key, _, val = fld.partition("=")
            key = key.strip().lower()
            val = val.strip()
            # An unfilled `<...>` field value (e.g. `source=<source>`) is the
            # echoed spec — treat it as omitted rather than literal junk.
            if _value_is_placeholder(val):
                continue
            if key == "person":
                person = None if val.lower() in ("operator", "self", "me", "") else val
            elif key == "source":
                source = val
            elif key == "project":
                project = val or None
            elif key == "evidence":
                evidence = [e.strip() for e in val.split(";") if e.strip()]
            elif key == "automation":
                automation = val.lower() in ("yes", "true", "1", "y")
            elif key == "why":
                why = _strip_markdown(val)

        if not title:
            continue
        # Model omitted automation= → fall back to the deterministic heuristic.
        if automation is None:
            automation = _infer_automation(source, title, project)
        actions.append(RankedAction(
            rank=0,  # re-sequenced below by emit order
            title=title[:200], person=person, source=source,
            project=project, evidence=evidence, why=why,
            automation=automation,
        ))

    # Re-sequence ranks 1..N by emit order — never trust model rank integers.
    for i, a in enumerate(actions, 1):
        a.rank = i
    return actions


def _has_structured_field(a: RankedAction) -> bool:
    """True when a parsed action carries a real structured field (not bare prose)."""
    return bool(a.person or a.source or a.project or a.evidence)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _local_day_window(now: datetime | None, tz: Any) -> tuple[str, datetime, datetime]:
    """Return (local_day_iso, day_start, day_end) for the local day of *now*."""
    current = now.astimezone(tz) if now is not None else datetime.now(tz)
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.date().isoformat(), start, end


def _operator_temporal_context(
    database_path: Path, now: datetime | None, tz: Any
) -> dict[str, Any]:
    """A minimal OPERATOR-scoped temporal context for the rank prompt.

    Wires the previously-dead Schedule Context branch in :func:`build_rank_prompt`
    and keeps it on parity with ``querier._build_prompt``. Reuses
    ``querier._gather_temporal_context`` — which is OPERATOR_CALENDAR_ID-scoped for
    its vacation inference — so team calendars are NEVER blended into day-type
    inference. Falls back to a pure day_name + weekday/weekend computation (no DB)
    if that helper is unavailable, so this NEVER raises.
    """
    current = (now.astimezone(tz) if now is not None else datetime.now(tz))
    tomorrow = current + timedelta(days=1)
    try:
        from rebalance.ingest.querier import _gather_temporal_context

        return {
            "today": _gather_temporal_context(database_path, current),
            "tomorrow": _gather_temporal_context(database_path, tomorrow),
        }
    except Exception:  # noqa: BLE001 — degrade to a DB-free day-type, never raise
        def _basic(d: datetime) -> dict[str, Any]:
            weekday = d.weekday()
            return {
                "date": d.strftime("%Y-%m-%d"),
                "day_name": d.strftime("%A"),
                "day_type": "off" if weekday >= 5 else "workday",
                "is_weekend": weekday >= 5,
            }

        return {"today": _basic(current), "tomorrow": _basic(tomorrow)}


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


def _signal_views(
    database_path: Path,
) -> tuple[dict[str, str], dict[str, int], dict[str, list[str]]]:
    """Build the per-candidate client + priority lookups and the client roster.

    Both lookups map a project's name AND each of its repos to a value, so an
    operator candidate keyed by ``owner/repo`` resolves. ``client_by_project`` ->
    effective client; ``priority_by_project`` -> effective ``priority_tier``
    (operator-local priority rules overlaid via ``apply_project_priorities``, so a
    configured tier for e.g. git-pulse is honored). ``roster`` is the client
    buckets. Best-effort: any failure returns empties so ranking is never blocked
    by this metadata.
    """
    try:
        from rebalance.ingest.project_priority import apply_project_priorities
        from rebalance.ingest.registry import (
            effective_client,
            get_clients,
            get_projects,
        )

        client_by_project: dict[str, str] = {}
        priority_by_project: dict[str, int] = {}
        for project in apply_project_priorities(get_projects(database_path)):
            keys = [project["name"], *(project.get("repos") or [])]
            client = effective_client(project.get("custom_fields"))
            tier = project.get("priority_tier")
            for key in keys:
                if client:
                    client_by_project[key] = client
                if tier is not None:
                    priority_by_project[key] = int(tier)
        return client_by_project, priority_by_project, get_clients(database_path)
    except Exception as exc:  # noqa: BLE001 — this metadata is never load-bearing
        logger.warning("_signal_views: %s", exc)
        return {}, {}, {}


def _resolve_signal_day(today: date | datetime | str, *, tz: Any) -> date:
    """Normalize *today* to a local date for deep-work signal windows."""
    if isinstance(today, datetime):
        return today.astimezone(tz).date()
    if isinstance(today, date):
        return today
    raw = (today or "").strip()
    if not raw:
        raise ValueError("today must not be empty")
    parsed = parse_iso(raw, force_utc=False)
    if parsed is not None:
        if parsed.tzinfo is not None:
            return parsed.astimezone(tz).date()
        return parsed.date()
    d = parse_date(raw)
    if d is not None:
        return d
    raise ValueError(f"Invalid date string: {raw}")


def _project_activity_rows_for_day(
    snapshot: Any,
    *,
    repos: set[str],
) -> list[str]:
    """Return concrete GitHub-backed activity rows for one project's day."""
    rows: list[str] = []

    def in_project(repo: str | None) -> bool:
        return (repo or "").lower() in repos

    for commit in snapshot.today.gh_commits:
        if not in_project(commit.get("repo")):
            continue
        sha = commit.get("sha") or "commit"
        subject = (commit.get("subject") or "").strip()
        rows.append(f"{commit.get('repo')} commit {sha} {subject}".strip())

    for item in snapshot.today.gh_items:
        if not in_project(item.get("repo")):
            continue
        kind = "pr" if item.get("item_type") == "pull_request" else (item.get("item_type") or "item")
        rows.append(
            f"{item.get('repo')} {kind} #{item.get('number')} {(item.get('title') or '').strip()}".strip()
        )

    for comment in snapshot.today.gh_comments:
        if not in_project(comment.get("repo")):
            continue
        preview = (comment.get("preview") or "").strip()
        rows.append(
            f"{comment.get('repo')} comment #{comment.get('item_number')} {preview}".strip()
        )

    for watched in getattr(snapshot, "watched_repos", []) or []:
        if not in_project(watched.get("repo")):
            continue
        counts: list[str] = []
        commits = int(watched.get("commits") or 0)
        items = len(watched.get("items") or [])
        comments = int(watched.get("comments") or 0)
        if commits:
            counts.append(f"{commits} commit{'s' if commits != 1 else ''}")
        if items:
            counts.append(f"{items} item{'s' if items != 1 else ''}")
        if comments:
            counts.append(f"{comments} comment{'s' if comments != 1 else ''}")
        if counts:
            rows.append(f"{watched.get('repo')} watched activity ({', '.join(counts)})")

    return rows


def _open_items_for_projects(
    database_path: Path,
    *,
    project_repos: dict[str, list[str]],
) -> dict[str, list[dict[str, Any]]]:
    """Read open GitHub items per project from the existing collector tables."""
    out = {project: [] for project in project_repos}
    repo_to_projects: dict[str, set[str]] = {}
    for project, repos in project_repos.items():
        for repo in repos:
            repo_to_projects.setdefault(repo.lower(), set()).add(project)

    if not repo_to_projects:
        return out

    placeholders = ",".join("?" for _ in repo_to_projects)
    from rebalance.ingest.db import ensure_github_schema

    with db_connection(database_path, ensure_github_schema) as conn:
        rows = conn.execute(
            f"""
            SELECT repo_full_name, item_type, number, title, html_url,
                   created_at, updated_at
            FROM github_items
            WHERE LOWER(repo_full_name) IN ({placeholders})
              AND LOWER(COALESCE(state, '')) = 'open'
            ORDER BY COALESCE(updated_at, created_at) DESC, number DESC
            """,
            tuple(repo_to_projects),
        ).fetchall()

    for row in rows:
        repo = (row["repo_full_name"] or "").lower()
        for project in repo_to_projects.get(repo, set()):
            out[project].append(
                {
                    "repo": row["repo_full_name"],
                    "item_type": row["item_type"],
                    "number": row["number"],
                    "title": row["title"] or "",
                    "html_url": row["html_url"] or "",
                    "updated_at": row["updated_at"] or row["created_at"] or "",
                }
            )
    return out


def compute_deep_work_signals(
    database_path: Path,
    today: date | datetime | str,
    lookback_days: int = 7,
) -> dict[str, dict[str, Any]]:
    """Compute read-only cross-day streak/stall signals per active project.

    Reuses ``collect_pulse_snapshot()`` once per day across the lookback window,
    with ``github_token=None`` so the signal stays hermetic and never triggers a
    live GitHub assigned-issues fetch.
    """
    if lookback_days <= 0 or not database_path.exists():
        return {}

    from rebalance.ingest.registry import get_projects

    pulse_cfg = get_pulse_config()
    tz_name = pulse_cfg.get("pulse_timezone") or local_tz().key
    tz = ZoneInfo(tz_name)
    github_login = pulse_cfg.get("github_login") or ""
    slack_user_id = pulse_cfg.get("slack_user_id")
    anchor_day = _resolve_signal_day(today, tz=tz)

    active_projects = get_projects(database_path, status="active")
    project_repos = {
        project["name"]: [repo for repo in (project.get("repos") or []) if repo]
        for project in active_projects
    }
    daily_rows: dict[str, dict[str, list[str]]] = {
        project["name"]: {} for project in active_projects
    }

    for offset in range(lookback_days):
        day = anchor_day - timedelta(days=offset)
        snapshot = collect_pulse_snapshot(
            database_path,
            github_login=github_login,
            slack_user_id=slack_user_id,
            timezone_name=tz_name,
            github_token=None,
            now=datetime(day.year, day.month, day.day, 12, tzinfo=tz),
        )
        for project_name, repos in project_repos.items():
            daily_rows[project_name][day.isoformat()] = _project_activity_rows_for_day(
                snapshot,
                repos={repo.lower() for repo in repos},
            )

    open_items = _open_items_for_projects(database_path, project_repos=project_repos)
    today_key = anchor_day.isoformat()
    yesterday_key = (anchor_day - timedelta(days=1)).isoformat()

    signals: dict[str, dict[str, Any]] = {}
    for project in active_projects:
        project_name = project["name"]
        streak_days = 0
        streak_dates: list[str] = []
        recent_activity: list[dict[str, Any]] = []
        streak_open = True
        for offset in range(lookback_days):
            day_key = (anchor_day - timedelta(days=offset)).isoformat()
            day_rows = list(daily_rows.get(project_name, {}).get(day_key, []))
            if day_rows:
                recent_activity.append({"date": day_key, "rows": day_rows})
            if streak_open and day_rows:
                streak_days += 1
                streak_dates.append(day_key)
            else:
                streak_open = False
        today_rows = list(daily_rows.get(project_name, {}).get(today_key, []))
        yesterday_rows = list(daily_rows.get(project_name, {}).get(yesterday_key, []))
        project_open_items = list(open_items.get(project_name, []))
        signals[project_name] = {
            "project": project_name,
            "repos": list(project_repos.get(project_name, [])),
            "streak_days": streak_days,
            "possible_stall": bool(yesterday_rows and not today_rows and project_open_items),
            "evidence": {
                "streak_dates": streak_dates,
                "recent_activity": recent_activity,
                "today_date": today_key,
                "today_rows": today_rows,
                "yesterday_date": yesterday_key,
                "yesterday_rows": yesterday_rows,
                "open_items": project_open_items,
            },
        }
    return signals


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
                    local_day=local_day,
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

    # Client + priority lookups (computed once; used for both the deterministic
    # demotion below and the synthesis prompt).
    client_by_project, priority_by_project, client_roster = _signal_views(database_path)

    # Deterministic candidate objects (operator + additive teammate delta).
    operator_actions = [
        _candidate_to_action(c, i)
        for i, c in enumerate(operator_candidates_raw, 1)
    ]
    # Soft down-weight in the fallback floor: low-priority (periodic) projects sink
    # to the bottom of the operator arm via a STABLE sort (original recency order
    # preserved within each group), so the down-weight holds even when synthesis is
    # skipped or fails. Not a drop — they remain in the list.
    operator_actions.sort(
        key=lambda a: 1 if _is_low_priority(a.project, priority_by_project) else 0
    )
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
            temporal_context=_operator_temporal_context(database_path, now, tz),
            blended=blended,
            client_by_project=client_by_project,
            client_roster=client_roster,
            priority_by_project=priority_by_project,
        )
        try:
            from rebalance.ingest.querier import _synthesize_with_fallback

            # thinking_budget=0 DISABLES the model's hidden reasoning: gemini-2.5
            # is a reasoning model that otherwise spent ~1900 of 2048 tokens
            # "thinking" and truncated the ranked list to ~2 items at MAX_TOKENS.
            # With thinking off the whole budget goes to the answer (the full
            # ranked list). 2048 caps the answer length.
            synthesis, model_used = _synthesize_with_fallback(
                prompt, max_tokens=2048, thinking_budget=0
            )
            parsed = _parse_ranked_synthesis(synthesis)
            # STRUCTURED acceptance gate: only trust the parse over the
            # deterministic fallback when it is non-empty AND at least half its
            # items carry a real structured field (person/source/project/evidence).
            # A degenerate prose/markdown numbered list parses to title-only junk
            # and is REJECTED here so the good deterministic fallback survives.
            structured = sum(1 for a in parsed if _has_structured_field(a))
            if parsed and structured * 2 >= len(parsed):
                ranked = parsed
            else:
                note = (
                    (note + "; " if note else "")
                    + "synthesis parsed to nothing useful; using deterministic order"
                )
                # Synthesis returned text but parsed-to-nothing-useful WHILE
                # candidates existed → the interesting failure.
                if (synthesis or "").strip() and fallback:
                    logger.warning(
                        "rank_next_actions: synthesis text did not parse to "
                        "structured items (parsed=%d, structured=%d, candidates=%d)",
                        len(parsed), structured, len(fallback),
                    )
        except Exception as exc:  # noqa: BLE001 — degrade, don't blow up
            logger.warning("rank_next_actions: synthesis failed: %s", exc)
            note = (note + "; " if note else "") + f"synthesis failed: {exc}"

    if not ranked:
        if operator_candidates_raw or teammate_delta:
            # Candidates existed but the ranked list is empty — the interesting case.
            logger.warning(
                "rank_next_actions: empty ranked output despite candidates "
                "(blended=%s, local_day=%s)",
                blended, local_day,
            )
        else:
            # Zero candidates to begin with — expected (a quiet day / empty DB).
            logger.info(
                "rank_next_actions: no candidates to rank (blended=%s, local_day=%s)",
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


# The teammate arm reads a multi-day horizon; the additivity gate counts a
# trailing-history window so it reflects logging DENSITY, not future scheduling.
_TEAMMATE_HORIZON_DAYS = 2
_ADDITIVITY_HISTORY_DAYS = 30


def _operator_blocks_over_horizon(
    conn: Any, *, local_day: str, days_forward: int, tz: Any
) -> list[dict[str, Any]]:
    """Operator OPERATOR_CALENDAR_ID blocks for [local_day .. local_day+days_forward].

    The teammate arm reads a multi-day upcoming horizon, so normalized-title dedup
    needs the operator's titles across the SAME horizon — otherwise a hand-logged
    duplicate teammate meeting on tomorrow/day-after double-counts against the
    operator's own future block. Same-local-day comparison is preserved (each block
    keeps its ``local_day``); this only widens which operator days are visible.
    """
    start_d = parse_date(local_day)
    if start_d is None:
        start_d = datetime.now(tz).date() if hasattr(tz, "utcoffset") else datetime.now(timezone.utc).date()
    horizon_days = {
        (start_d + timedelta(days=i)).isoformat()
        for i in range(days_forward + 1)
    }
    rows = conn.execute(
        "SELECT id, summary, start_time, end_time, person "
        "FROM calendar_events WHERE calendar_id = ?",
        (OPERATOR_CALENDAR_ID,),
    ).fetchall()
    blocks: list[dict[str, Any]] = []
    for r in rows:
        block = _calendar_block(r, tz=tz)
        if block is None or block["local_day"] not in horizon_days:
            continue
        blocks.append(block)
    return blocks


def _gather_teammate_delta(
    conn: Any,
    *,
    database_path: Path,
    operator_blocks: list[dict[str, Any]],
    weights: SignalWeights,
    since_days: int,
    tz: Any,
    local_day: str,
) -> tuple[list[dict[str, Any]], bool, str]:
    """Gather the additivity-PASSING teammates' blocks, deduped to the delta.

    Returns ``(teammate_delta, blended, note)``. ``blended`` means TEAM SIGNAL
    ACTUALLY CONTRIBUTED: it is ``False`` when there is no roster, no
    additivity-passing person, OR the dedup delta is empty (the explanatory note
    still records why). Persons are gated by ``team_persons_passing_additivity`` on
    their trailing-history event counts (logging density, not future scheduling).
    """
    from rebalance.ingest.calendar import get_team_upcoming_by_person
    from rebalance.ingest.calendar_config import CalendarConfig

    roster = [tc.person for tc in CalendarConfig.load().team_calendars]
    if not roster:
        return [], False, "no team_calendars configured (operator-only)"

    # Per-person event counts over a bounded TRAILING-HISTORY window
    # [now-30d, now] — the additivity gate reflects how densely a teammate logs
    # their calendar, NOT how much future scheduling they happen to have. (An
    # unbounded future bound would let a single heavily-scheduled week pass a
    # teammate who never logs history.)
    now_iso = datetime.now(timezone.utc).isoformat()
    history_floor = (
        datetime.now(timezone.utc) - timedelta(days=_ADDITIVITY_HISTORY_DAYS)
    ).isoformat()
    placeholders = ",".join("?" for _ in roster)
    rows = conn.execute(
        f"SELECT person, COUNT(*) AS n FROM calendar_events "
        f"WHERE person IN ({placeholders}) "
        f"AND start_time >= ? AND start_time <= ? "
        f"GROUP BY person",
        (*roster, history_floor, now_iso),
    ).fetchall()
    counts = {r["person"]: r["n"] for r in rows}
    # Preserve roster order so the additivity filter is deterministic.
    event_counts = {p: counts.get(p, 0) for p in roster}
    passing = team_persons_passing_additivity(event_counts, weights.min_team_events)

    if not passing:
        return [], False, "no teammate passed the additivity threshold (operator-only)"

    # get_team_upcoming_by_person is the ONLY reader that SELECTs `person`.
    raw = get_team_upcoming_by_person(
        database_path, passing, days_forward=_TEAMMATE_HORIZON_DAYS
    )
    teammate_blocks: list[dict[str, Any]] = []
    for ev in raw:
        block = _calendar_block(ev, tz=tz)
        if block is None:
            continue
        block["person"] = ev.get("person")
        teammate_blocks.append(block)

    # Dedup against the operator's titles over the SAME multi-day horizon the
    # teammate read covers (FIX 2 / DSP-05) — comparison stays same-local-day.
    operator_horizon_blocks = _operator_blocks_over_horizon(
        conn, local_day=local_day, days_forward=_TEAMMATE_HORIZON_DAYS, tz=tz
    )
    shared_ids = _shared_event_ids(conn, operator_blocks=operator_blocks, persons=passing)
    delta, dropped = dedup_teammate_blocks(
        teammate_blocks, operator_horizon_blocks, shared_ids=shared_ids
    )
    # blended is True only when the team arm CONTRIBUTED an additive block.
    contributed = bool(delta)
    note = (
        f"team blended: {len(passing)} person(s) passed additivity, "
        f"{len(delta)} additive block(s), {dropped} deduped"
        if contributed
        else (
            f"team consulted: {len(passing)} person(s) passed additivity but "
            f"0 additive block(s) after dedup ({dropped} deduped) — operator-only"
        )
    )
    return delta, contributed, note


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


# ---------------------------------------------------------------------------
# Vault render sink — the fixed Obsidian dashboard file (Task, 2026-06-29)
#
# Writes the SAME ranked output as the route/cache to one fixed vault file so
# the vault is the calm daily operator surface (P1-SIGNAL). This is a render
# sink, NOT a second ranker — it serializes a RankedNextActions produced by
# rank_next_actions(); it never re-ranks. LOCAL-ONLY: the vault is on-device and
# is not the pushed git-pulse repo, so teammate `person` labels here do not
# cross the export boundary (mirrors the ranked_next_actions cache invariant).
# ---------------------------------------------------------------------------

# Fixed, overwrite-in-place dashboard file inside the Obsidian vault.
VAULT_NEXT_ACTIONS_RELPATH = "Dashboards/What To Do Next.md"


def _fmt_local_stamp(iso_utc: str, tz: Any) -> str:
    """Format an ISO-8601 (UTC) timestamp as a local human stamp for the banner."""
    return format_local(iso_utc, "%Y-%m-%d %H:%M %Z", tz=tz) or (iso_utc or "unknown")


def render_next_actions_markdown(
    result: RankedNextActions, *, now: datetime | None = None
) -> str:
    """Render *result* to the fixed-vault-file markdown (single-writer, generated).

    Pure string-from-dataclass; no I/O. The banner carries the generated-file
    contract + provenance (when, which model, item count, blended vs operator-only)
    so a reader can trust freshness at a glance.
    """
    tz = local_tz()
    stamp = _fmt_local_stamp(result.computed_at, tz)
    model = result.model_used or "deterministic (no model)"
    n = len(result.ranked)
    blend = "team-blended" if result.blended else "operator-only"

    lines: list[str] = [
        "# What To Do Next",
        "",
        "> [!note] Generated by rebalance-OS — do not edit by hand.",
        (
            f"> Overwritten on each refresh. Last updated **{stamp}** · "
            f"model `{model}` · {n} item{'' if n == 1 else 's'} · {blend}."
        ),
    ]
    if result.note:
        # The note carries provenance (team-blend stats) AND any degradation
        # ("synthesis failed…"); render it neutrally rather than as an alarm.
        lines.append(">")
        lines.append(f"> _{result.note}_")
    lines.append("")

    if not result.ranked:
        lines.append("_Nothing surfaced to rank right now._")
        lines.append("")
        return "\n".join(lines)

    for a in result.ranked:
        meta: list[str] = []
        if a.source:
            meta.append(a.source)
        if a.project:
            meta.append(a.project)
        if a.person:
            meta.append(f"👤 {a.person}")
        if a.automation:
            meta.append("⚙️ automatable")
        meta_str = f" _({' · '.join(meta)})_" if meta else ""
        lines.append(f"{a.rank}. **{a.title}**{meta_str}")
        if a.why:
            lines.append(f"   {a.why}")
        if a.evidence:
            lines.append(f"   ↳ evidence: {'; '.join(a.evidence)}")
    lines.append("")
    return "\n".join(lines)


def write_next_actions_to_vault(
    result: RankedNextActions,
    *,
    vault_path: str | Path | None = None,
    now: datetime | None = None,
) -> Path | None:
    """Write the ranked markdown to the fixed vault file. Returns the path, or None.

    Resolves the vault root from *vault_path* (override) or ``get_vault_path()``
    (config). Returns None when no vault is configured — a no-op, not an error.
    Creates the ``Dashboards/`` parent if missing and overwrites the file in
    place (single-writer). Raises only on a genuine filesystem error so the
    caller (precompute hook) can record it; the hook wraps this in try/except so
    a vault-write failure never breaks a refresh.
    """
    vp = vault_path if vault_path is not None else get_vault_path()
    if not vp:
        logger.info("next_actions: no vault_path configured; skipping vault write")
        return None
    target = Path(vp).expanduser() / VAULT_NEXT_ACTIONS_RELPATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_next_actions_markdown(result, now=now), encoding="utf-8")
    logger.info("next_actions: wrote vault dashboard %s", target)
    return target
