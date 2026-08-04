# Marathon Phase hiqs-m3-p2
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M3-P2-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

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


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/sources/github.py,HiQS/tests/test_github_candidates.py,HiQS/pyproject.toml
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M3-P2-TURN --agent codex --paths "phases/hiqs-m3-github--hiqs-m3-p2/RELAY.md,HiQS/hiqs/sources/github.py,HiQS/tests/test_github_candidates.py,HiQS/pyproject.toml"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M3-P2-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M3-P2-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m3-github--hiqs-m3-p2/RELAY.md and HiQS/hiqs/sources/github.py,HiQS/tests/test_github_candidates.py,HiQS/pyproject.toml. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/sources/github.py,HiQS/tests/test_github_candidates.py,HiQS/pyproject.toml. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M3-P2-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M3-P2-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m3-github--hiqs-m3-p2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

### Round 1 · Builder · codex

- Added the `github` candidate provider and wired it into `SOURCE`; every receipt includes source,
  hand-verifiable evidence, why, `activity_at` as `ts`, URL, and author.
- Persisted GitHub-supplied requested-reviewer and milestone/deadline data in the source-owned
  `github_item_obligations` table. Candidates prefer an assignee, otherwise use a requested reviewer;
  unknown obligations remain empty rather than inferred.
- Added focused API-shaped tests covering attestation, label-only timestamp stability, assignee/reviewer
  obligations, milestone due dates, and absent obligations. The existing GitHub entry point in
  `HiQS/pyproject.toml` already registers this source, so it required no change.
- Verified with `python -m pytest HiQS/tests/test_github.py HiQS/tests/test_github_candidates.py` (5 passed).
