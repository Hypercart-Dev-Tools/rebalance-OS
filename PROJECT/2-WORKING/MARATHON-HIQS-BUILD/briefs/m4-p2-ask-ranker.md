---
title: "M4 p2 — ask.py: attested context and the one Ranker"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M4 p2 — ask.py: attested context and the one Ranker

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m4-p1` is approved. |

**Canonical spec:** `HIQS-PROJECT.md` §7 (seams, `RankedAction`, the return shape verbatim), §7.1
(what the ranking is measured against), §3.1 Decision 5, §11 (~180 LOC), L1, L9.

This module carries the plan's namesake invariant. Read §7 in full.

## Build

`HiQS/hiqs/ask.py`:
- Context gather across sources → the §7 JSON shape, verbatim, including `synthesis: null`
  (`null`, not `""` — a host must be able to tell "no synthesizer" from "returned nothing").
- The deterministic `Ranker` (~40 LOC, §3.1 Decision 5). Terms in §7's stated weight order:
  **obligation** (`owed_by` set; `due` proximity when stated) → **activity** (recency of
  `activity_at`, never `updated_at`) → **source weight**.
- `RankedAction` carrying `author`, `owed_by`, `due`, **`source_age_s`**, **`source_status`**.
- **Exactly one ranking**, written by `refresh`, read by everyone.

## Acceptance

- **The namesake invariant, proved (L1):** a test asserts `ask()` and the persisted ranking are
  identical for the same DB state, and that no other module computes an ordering. The incumbent's
  core claim was two-thirds true because nothing enforced this; the test is the enforcement.
- **Determinism:** same candidates in, same order out. No clock-dependent or network-dependent
  tiebreak. **No LLM anywhere in the path** (Decision 5, L9).
- **Freshness rides on the item:** every `RankedAction` carries `source_age_s` and `source_status`
  from the source's last *successful* sync. A source that has not synced in three weeks cannot put
  a three-week-old item at rank 1 looking current — that is the incumbent's 0.57.0 shape. Unmeasured
  is `-1` / `unknown`, never a default that reads healthy.
- **Attestation is total:** every ranked item carries source, author, time, and link **as fields**.
  A receipt reachable only by parsing `evidence` prose fails this.
- Obligation ordering is testable: a due-soon assigned item outranks a newer unassigned one.

## Do not

- Do not call an LLM, add a synthesis step, or populate `synthesis`. The `Synthesizer` seam is
  `None` in v1 with a trigger in §14.
- Do not let any surface re-rank. If a consumer needs a different order, that is a §14 conversation.
