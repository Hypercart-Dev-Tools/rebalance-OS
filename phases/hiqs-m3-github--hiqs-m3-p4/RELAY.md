# Marathon Phase hiqs-m3-p4
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M3-P4-TURN builder=codex reviewer=agy round-cap=9 -->

## Phase Brief

---
title: "M3 p4 — reference linking: note text to GitHub item"
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
# M3 p4 — reference linking (note → GitHub item)

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 from §6.4, added after the operator's seed questions exposed the gap. **Not yet run.** | Runs last in M3. Needs `github_items` populated by p1. |

**Canonical spec:** `HIQS-PROJECT.md` §6.4 (Q2), §5 rule 1 (one writer per table).
Tie-breakers: `HiQS/GUIDING-PRINCIPLES.md`, especially **D5** (structure is a field, not a parse).

## Why this exists

The operator asked: *"What did we decide on with XYZ to phase out the Bash scripts on which GH
issue?"*

That is two joined asks — find the decision (which lives in a note), then name the artifact
carrying it (which lives in GitHub). Retrieval can already surface the note. **Nothing today
carries the edge from that note to the issue**, so the second half of the question is
unanswerable no matter how good retrieval gets.

## Build

In the projection, record GitHub references that appear **literally** in a document's text:

- Bare issue/PR references — `#123` — resolved against the repo the document is associated with.
- Full GitHub URLs — `https://github.com/<owner>/<repo>/issues/123` and the `/pull/` form.
- `owner/repo#123` shorthand.

Store the edge as a **field**, at projection time. Do not re-derive it at query time by scanning
body text — that is D5's exact prohibition, and it is the defect this build already paid for once
when unit membership was recovered by splitting ids on `:`.

A reference is a link, a link is one of the four ATTESTED receipts, and receipts live in fields.

## Acceptance

- A note containing `#123` yields an edge to the corresponding `github_items` row, and a query
  matching that note can return the linked item alongside it.
- **Unresolvable references are dropped, not guessed.** `#123` with no repo context, or pointing
  at an item not in `github_items`, produces **no edge** — never a fabricated one, never a
  placeholder row. An unresolved reference is `unknown`, and `unknown` is a real state (§8).
- **False-positive resistance, tested explicitly.** `#123` inside a fenced code block, inside a
  URL fragment, or in prose like "issue #1 of the newsletter" must not create an edge. Test the
  code-fence case specifically — it is the common one in an engineering vault.
- Idempotent: re-projecting an unchanged note produces zero edge inserts and zero updates.
- Edges are reconciled **within the unit** that produced them, under the same attestation rule as
  every other projected row (§5 rule 2, `SyncReport.units_ok`). A note whose fetch failed keeps
  its existing edges.
- One writer. Whatever table or column holds these edges has exactly one writing function, pinned
  by the same AST sole-writer test that guards `docs` — and that test must see `async def`, which
  it did not until it was fixed in M2.

## Do not

- **No entity extraction, no inference, no LLM.** If the note does not literally name the issue,
  there is no edge. Inferring an unstated link is not v1 work; it is a quality claim with no
  detector, which §2 forbids.
- Do not create a new top-level module for this. It belongs in the projection that already writes
  `docs`.
- Do not let a reference edge influence ranking. It changes what can be **returned together**,
  not what ranks **higher**.
- Do not scan GitHub bodies for vault references in this phase. One direction only — note → item.
  The reverse has a different false-positive profile and no seed question asking for it.


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/docs_index.py,HiQS/hiqs/db.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_db.py,HiQS/tests/test_contract.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M3-P4-TURN --agent codex --paths "phases/hiqs-m3-github--hiqs-m3-p4/RELAY.md,HiQS/hiqs/docs_index.py,HiQS/hiqs/db.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_db.py,HiQS/tests/test_contract.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M3-P4-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M3-P4-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m3-github--hiqs-m3-p4/RELAY.md and HiQS/hiqs/docs_index.py,HiQS/hiqs/db.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_db.py,HiQS/tests/test_contract.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/docs_index.py,HiQS/hiqs/db.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_db.py,HiQS/tests/test_contract.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M3-P4-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M3-P4-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m3-github--hiqs-m3-p4/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

### Round 1 · Builder · codex

Implemented literal note-to-GitHub reference projection in `HiQS/hiqs/docs_index.py` with the new
`doc_github_refs` receipt table in `HiQS/hiqs/db.py`. Bare references use the document's explicit
`project` repo context; URLs and `owner/repo#number` carry their own context. Only existing
`github_items` rows are linked; fenced code, URL fragments, newsletter prose, and unresolved
references are dropped. Edge writes are delta-reconciled and are retained when document loading
fails. Added retrieval helper (without changing ranking), schema/sole-writer checks, and focused
coverage for resolution, false positives, idempotence, and failed fetches.

Verified: `pytest -q tests/test_docs_index.py tests/test_db.py tests/test_contract.py` — 42 passed,
1 xfailed.
