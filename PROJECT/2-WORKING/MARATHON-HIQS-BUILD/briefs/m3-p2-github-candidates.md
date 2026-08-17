---
title: "M3 p2 — github candidates(): attested and obligation-bearing"
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
# M3 p2 — github candidates(): attested, obligation-bearing

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m3-p1` is approved; extends the same file. |

**Canonical spec:** `HIQS-PROJECT.md` §5 (`Candidate`), §7 (the Ranker's terms), §7.1 (obligation
coverage gate), §12 Phase 2 gate, L2.

Extends p1's file — `depends_on: p1` is required, not decorative.

## Build

A `candidates()` provider on the same `SOURCE`, emitting `Candidate` rows:
- `source`, `evidence`, `why` — **all three non-empty, always.** A bare candidate is not a signal.
- `ts` ← `activity_at` (never `updated_at`).
- `author` ← the item's author.
- `owed_by` ← assignee or requested reviewer, when the source knows it.
- `due` ← milestone or a stated deadline, when the source states one.

`owed_by` and `due` are `""` when unknown — **never guessed, never imputed**. §7.1's obligation
coverage gate measures how often they are populated, and a fabricated value would defeat the
measurement rather than improve the ranking.

## Acceptance

- **Zero core edits.** Adding GitHub touched only `sources/github.py` and one entry-point line.
  Any change to a file under `HiQS/hiqs/*.py` to make this work is a plugin-contract defect (L2) —
  fix the contract, do not absorb it here.
- A test asserts every emitted `Candidate` has non-empty `source`, `evidence`, `why`.
- A test asserts `ts` traces to `activity_at`: a row whose only change is a label edit does not
  move (L20).
- Obligation fields populated where the API supplies them, `""` where it does not; a test covers
  both, including an item with no assignee.
- `evidence` is specific enough to verify by hand ("PR #42, review requested from you, last commit
  2026-08-01"), not a restatement of the title.

## Do not

- Do not infer `owed_by` from heuristics ("probably the author"). Unknown is `""`.
- Do not rank, score, or order here. The Ranker is M4 p2 and there is exactly one of it (§7).
