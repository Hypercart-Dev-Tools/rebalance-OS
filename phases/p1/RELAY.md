# Marathon Phase p1
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-P1-TURN builder=agy reviewer=codex round-cap=5 -->

## Phase Brief

# Phase 1 — GH-101 Phase 1: `recent_row_count_7d` additive field

## Scope lock

Edit ONLY `src/rebalance/ingest/index_ops.py` (the `get_index_status` function, `index_ops.py:224`)
and `tests/test_index_ops.py`. Do not touch ingest logic, gates, or any other file. Do not run the
full test suite as your gate — the pre-advance check runs `pytest tests/test_index_ops.py` for you.

## Task

Add `recent_row_count_7d` to each source dict returned by `get_index_status()`, computed via the
existing `_safe_count_where` helper against the content-timestamp column already used for freshness
per source. This is a pure additive read field:

- No ingest change.
- No gate/threshold logic.
- No new table, no new migration.
- `index_status` stays read-only.

## Acceptance criteria

- `recent_row_count_7d` is present in every source's dict in `get_index_status()`'s return value.
- Value is correct for at least 2 seeded sources in a new/updated unit test, including a zero-volume
  case (a source with no rows in the last 7 days should report `0`, not `None` or a KeyError).
- No existing test in `tests/test_index_ops.py` regresses.

## Provenance

`PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md`, Phase 1 section.

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/ingest/index_ops.py,tests/test_index_ops.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-P1-TURN --agent agy --paths "phases/p1/RELAY.md,src/rebalance/ingest/index_ops.py,tests/test_index_ops.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-P1-TURN --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-P1-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/p1/RELAY.md and src/rebalance/ingest/index_ops.py,tests/test_index_ops.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/ingest/index_ops.py,tests/test_index_ops.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-P1-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-P1-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/p1/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
