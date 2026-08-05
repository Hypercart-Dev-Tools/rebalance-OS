---
title: "M1 p6 — the two seam tests (plugin contract + clean room)"
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
# M1 p6 — The two seam tests

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m1-p5` is approved; closes HiQS Phase 0. |

**Canonical spec:** `HIQS-PROJECT.md` §5 rule 6 (contract test), §11 (clean room), L2, **L23**.

L23 is why this phase exists as its own phase: a shipped fix was reintroduced by a new module
because the lesson lived in a changelog instead of a test. These two tests are where HiQS pins its
invariants at the **seam**, so a source written next year inherits them without anyone remembering.

## Build

1. `HiQS/tests/fake_source.py` — a minimal `Source` registered **only** through an entry point.
2. `HiQS/tests/test_contract.py` — the fake reaches `docs`, `status`, and the ranking with **zero
   edits to any file under `HiQS/hiqs/`**. Beyond reachability, assert the invariants against the
   fake, not just the shipped sources:
   - one writer per table (`events` via `log_event`, `docs` via the projection)
   - attestation non-empty on every emitted `Candidate` (source, evidence, why)
   - a watermark advances only after a fetch that completed (L19)
   - reconciliation is within-unit only, never across units (§5 rule 2)
   - every network call carries an explicit timeout (rule 7)
   Where a seam is not yet built (the projection lands in M2), write the test against the
   contract and mark it `xfail(strict=True)` with the phase that will satisfy it — a strict xfail
   flips to a failure the moment it starts passing silently.
3. `HiQS/tests/test_clean_room.py` — fails if any module under `HiQS/**` imports the incumbent
   tree, or the reverse. Walk the AST; do not grep for strings.

## Acceptance

- Adding the fake source changes no file under `HiQS/hiqs/`. A core edit needed to admit it is a
  contract defect to fix in the contract, not a workaround here.
- The clean-room test fails when a deliberate `import rebalance` is injected, and passes when it is
  removed. **Demonstrate both directions** — a test that has never failed proves nothing.
- §19.1: this test is the extraction precondition, not a style check. Say so in a module docstring.
