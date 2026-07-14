---
gh_issue: 125
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/125
title: "HiQS: unify all six signals into one ranked pipeline"
status: "Active (2-WORKING)"
owner: Noel
created: 2026-07-14
updated: 2026-07-14
doc_type: project
goal: >
  One bundle, all six sources (GitHub, vault, Calendar, Sleuth/Slack, Gmail, Figma),
  one ranked verdict, read by every synthesis surface. Wiring and deletion, not new
  machinery. Supersedes the remaining scope of #101/#115/#116/#119.
supersedes: [101, 115, 116, 119]
related:
  - GUIDING-PRINCIPLES.md
  - ARCHITECTURE.md
  - PROJECT/2-WORKING/GH-116-VELOCITY-SIGNAL.md
  - PROJECT/2-WORKING/GH-115-ZAPIER-INGEST.md
  - PROJECT/2-WORKING/GH-119-HIQS-LABEL.md
effort: 3
complexity: 3
risk: 2
phases: 3
---

# GH-125 — HiQS: one unified ranked pipeline

## Status

| What was just completed | What's next |
|---|---|
| Phases 1–3 implemented in a sandbox with NO real signal data / credentials. Verified with `pytest` against seeded temporary SQLite DBs. | Operator local verification (see PENDING LOCAL VERIFICATION). |

## North star (LOCKED — do not relitigate)

Decision-order (GUIDING-PRINCIPLES appendix): **local-first > signal quality >
architectural cleanliness > implementation speed**. When "smaller diff" conflicts
with signal quality or cleanliness, the smaller diff loses.

- **D1 — `hiqs` is a FIRST-CLASS `QueryResult` field, not a sidecar.** The dynamic
  `NEXT_ACTIONS_ATTR` sidecar attribute is REJECTED. The QueryResult contract that
  was pinned "byte-identical" is DELIBERATELY BUMPED to carry `hiqs`; its test is
  updated to assert the new shape (not deleted, not routed around).
- **D2 — ATTESTED is non-negotiable.** Every candidate any arm emits carries
  `source`, non-empty `evidence`, and `why`. A bare title is a failed signal.
- **D3 — one ranked verdict, read via the persisted cache.** `ask()` reads the
  PERSISTED ranking (`load_ranked_next_actions`) — a cheap cached read. It never
  calls `rank_next_actions()` (which can hit Gemini). The dashboard route writes
  the cache; `ask()` reads it; the two are structurally incapable of drifting.

## Problem

Six signals are ingested but no single pipeline combines them. Two synthesis
surfaces disagreed: `querier.ask()` saw no Sleuth/Gmail/Figma;
`next_actions.rank_next_actions()` (the `/whats-next` engine) saw no Gmail/Figma.
Gmail and Figma reached NO synthesis at all.

## Phase 1 — Complete the bundle (all six sources reach the ranker)

- `pulse.DayActivity` gains `email_activity` + `figma_activity`; `_query_day_activity`
  adds two windowed SELECTs mirroring the sleuth block (email on `received_at`; figma
  on `created_at WHERE resolved_at IS NULL`). Both gate on table-existence so a
  partial-schema DB degrades to "no rows" instead of raising.
- `next_actions.OperatorBundle` gains the same two fields, passed through in
  `assemble_day_bundle`.
- `_operator_candidates` gains an email arm (tier 1) and a DORMANT figma arm (tier 6);
  rank tiers renumbered: sleuth 0 · email 1 · gh_items 2 · calendar 3 · gh_commits 4 ·
  gh_comments 5 · figma 6 · vault 7. Every arm is Attested (source/evidence/why).
- Figma arm is marked `# ponytail:` naming its trigger (a configured `figma_file_keys`
  allow-list). It ships correct-and-idle; it is NOT deleted (explicit product signal).
- Module docstring at `next_actions.py:5` corrected — it no longer lies about email,
  and now names figma.

### QA gate — Phase 1

- [x] `email_messages` row in the window → a `source == "email"` candidate (pytest)
- [x] EMPTY `figma_comments` table → zero figma candidates, no raise (pytest)
- [x] Present UNRESOLVED figma comment surfaces; a RESOLVED one is excluded (pytest)
- [x] Every ranked action carries `source` + non-empty `evidence` — Attested (pytest)
- [ ] Real Gmail rows actually surface in the live ranked list — PENDING LOCAL (no creds)

**Verification summary:** ran `pytest tests/test_hiqs_pipeline.py tests/test_next_actions.py`
→ green (Phase 1 arms + the two updated fakes). Full-suite parity checked at end.

## Phase 2 — One ranked verdict (kill the drift)

- `querier._gather_hiqs_context(database_path)` reads the persisted ranking via
  `next_actions.load_ranked_next_actions()` (D3 — cheap cached read; never
  `rank_next_actions()`), degrading to an empty ranking on a never-ranked/empty DB.
- `QueryResult` gains a first-class `hiqs` field (D1). The `NEXT_ACTIONS_ATTR` sidecar
  is deleted. `ask()` always populates `hiqs` on the default path.
- `_build_prompt` gains one labelled `## HiQS — ranked next actions` section carrying
  each action's receipts (source/evidence/why), not bare titles.
- `test_querier` byte-identical pin UPDATED to assert the new `hiqs` shape;
  `test_next_actions_parity` updated to the structural (shared-cache) parity.

### QA gate — Phase 2

- [x] `ask()` does NOT recompute the ranking on the default path (pytest)
- [x] `ask()` on a never-ranked / empty DB degrades to an empty ranking, no raise (pytest)
- [x] `QueryResult.hiqs` carries the persisted ranked verdict (pytest)
- [ ] Live `ask()` renders the HiQS section with real Gemini synthesis — PENDING LOCAL

**Verification summary:** ran `pytest tests/test_querier.py tests/test_next_actions_parity.py
tests/test_retrieval_contracts.py tests/test_mcp_probe.py` → 52 passed. The querier
byte-identical pin was updated (EXPECTED_KEYS now includes `hiqs`); the sidecar test class
was rewritten to the first-class-field contract; the parity test was rewritten to the
structural shared-cache parity (route writes, ask reads). `NEXT_ACTIONS_ATTR` deleted from
querier + retrieval. Live Gemini render is PENDING LOCAL (no key).

## Phase 3 — Collapse the dispatch chain (the Principle 3 fix — headline)

- `Collector` gains a `candidates=` provider, mirroring the existing `semantic_docs=`
  provider. Each source owns its candidate shape, registered at `register_collector()`
  time. `_operator_candidates` becomes a walk over the registry; the eight hand-written
  loops are deleted.
- `ARCHITECTURE.md` updated — stale "future: `_gather_sleuth_context()`" note removed,
  HiQS described as the one unified pipeline; `python scripts/audit_modules.py` passes.
- `compute_deep_work_signals()` disposition recorded (see Decisions below).
- Zapier stubs disposition recorded (see Decisions below).

### QA gate — Phase 3

- [ ] A FAKE collector with a `candidates=` provider reaches the ranked output with
  ZERO edits to next_actions.py / querier.py (pytest — the keystone proof)
- [ ] `python scripts/audit_modules.py` passes
- [ ] `rebalance doctor` clean — PENDING LOCAL (needs real DB + creds)
- [ ] Live `refresh_index()` end-to-end — PENDING LOCAL (needs real sources)

**Verification summary:** _to be filled when Phase 3 lands._

## Decisions recorded during build

- **Zapier stubs — KEPT (kill rejected, with reason).** The task allowed deleting
  `zapier_email.py` / `zapier_calendar.py` IF they carry no real logic. They are pure
  `NotImplementedError` placeholders, BUT they are the live dispatch targets of the
  shipped `POST /api/zapier/ingest` receiver (`web._zapier_handler_for`), and
  `tests/test_zapier_webhook.py` pins the `NotImplementedError → 501` contract by
  patching those exact module functions. Deleting them breaks a shipped, tested
  endpoint the task also said to keep. Per honesty + "keep the receiver", they stay.
- **`compute_deep_work_signals()` — _(recorded in Phase 3 section)._**

## PENDING LOCAL VERIFICATION (gates the sandbox cannot run)

The sandbox has NO populated DB, NO OAuth/PAT/Gemini/Sleuth/Figma credentials, and
cannot run Apple-Silicon `mlx`. The following remain UNVERIFIED and their gate boxes
above stay UNCHECKED:

- `rebalance doctor`
- live `refresh_index()` against real sources
- the live `/whats-next` render
- any real Gemini ranking call
- whether real Gmail rows actually surface in the ranked list

## Net LOC

Reported in the PR body via `git diff --stat` against the branch point.
