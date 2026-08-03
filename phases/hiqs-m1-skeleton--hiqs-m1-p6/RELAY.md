# Marathon Phase hiqs-m1-p6
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M1-P6-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

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


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/tests/test_contract.py,HiQS/tests/test_clean_room.py,HiQS/tests/fake_source.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M1-P6-TURN --agent codex --paths "phases/hiqs-m1-skeleton--hiqs-m1-p6/RELAY.md,HiQS/tests/test_contract.py,HiQS/tests/test_clean_room.py,HiQS/tests/fake_source.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M1-P6-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P6-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m1-skeleton--hiqs-m1-p6/RELAY.md and HiQS/tests/test_contract.py,HiQS/tests/test_clean_room.py,HiQS/tests/fake_source.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/tests/test_contract.py,HiQS/tests/test_clean_room.py,HiQS/tests/fake_source.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P6-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M1-P6-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m1-skeleton--hiqs-m1-p6/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

### Round 1 · Builder · codex

- Added `HiQS/tests/fake_source.py`, a third-party-shaped source discoverable only through the
  `hiqs.sources` entry-point seam. Its injected network boundary receives an explicit timeout,
  its watermark advances only after a successful fetch, and raw-record reconciliation is scoped
  to the successfully fetched unit.
- Added `HiQS/tests/test_contract.py` to pin fake-source discovery, documents, status telemetry,
  total candidate attestation, timeout propagation, watermark safety, within-unit reconciliation,
  and `log_event()` as the sole `events` writer. The absent M2 docs projection and M3 ranking
  seam are strict `xfail`s so an unreviewed implementation cannot silently satisfy either.
- Added `HiQS/tests/test_clean_room.py`, an AST-based two-direction import detector. Its temporary
  fixture deliberately injects both `import rebalance` and `from hiqs import ...` to demonstrate
  rejection; the real trees are then required to be clean. The module docstring records that this
  is the extraction precondition rather than a style check.
- Verification: `pytest HiQS/tests/test_contract.py HiQS/tests/test_clean_room.py` → 9 passed,
  2 xfailed (strict, pending M2/M3).
