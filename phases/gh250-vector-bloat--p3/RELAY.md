# Marathon Phase p3
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-P3-TURN builder=agy reviewer=codex round-cap=5 -->

## Phase Brief

# p3 — R2: author the reclaim runbook

## Deliverable

One file: `PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md`. No code in this phase.

It is the procedure a human follows, inside a maintenance window, to reclaim ~10.2 GB from
`rebalance.db`. It must be executable by someone who has not read GH-250 — every number and command
spelled out, every abort condition explicit.

## Measured starting state (2026-08-04 16:26 PDT, noels-Mac-Studio)

| | |
|---|---|
| `rebalance.db` | 13.43 GB |
| vectors total | 2,687,606 |
| orphaned | 2,678,314 (99.65%) |
| live vectors | 9,292 |
| `freelist_count` | 0 |
| expected reclaim | ~10.2 GB → db lands near ~1.2 GB |
| free space on volume | 319 GB |

Treat these as the *reference* run. The runbook must re-measure at execution time and compare,
because the orphan count moves with every sync until p1 lands.

## Required sections

### 1. Preconditions (a checklist that gates everything)
- GH-250 **R1 confirmed**: orphan count flat across >=3 `github_sync` cycles. Reclaiming before the
  writer fix is verified means the next sync re-orphans the work — this ordering error is exactly
  what the GH-248 review caught.
- Writers fenced per `utils/gh250/fence-writers.sh` (p4), with its verification output pasted in.
- Backup taken **and a restore actually rehearsed** — not merely "a copy exists". A backup nobody
  has restored from is a hope, not a rollback.
- Free-space go/no-go: require headroom for `db + backup + vacuum rebuild copy` plus margin. At the
  reference numbers that is ~40 GB against 319 GB available. State the formula, not just the answer,
  so it re-evaluates correctly on another machine.

### 2. Execution
- Prefer `NOT EXISTS` over `NOT IN`. (`EXPLAIN` confirms `vec0` accepts both, and there are
  currently zero NULL `doc_id`s so they are equivalent here — but `NOT EXISTS` stays correct if a
  NULL ever appears, and costs nothing.)
- **Batch the delete.** A single 2.68M-row transaction holds the writer lock for a long time and
  inflates the WAL unboundedly. Specify a batch size, a commit between batches, a WAL checkpoint
  cadence, and a progress line per batch so a human can see it moving.
- State the journal mode the procedure assumes, and how to confirm it before starting.
- `VACUUM` after the deletes. Note that it rebuilds the file and needs exclusive access — no
  concurrent reader, including `doctor`. Consider `VACUUM INTO` + atomic swap as the safer variant
  and say which is recommended and why.

### 3. Abort and resume
- Named abort conditions: unexpected orphan count at start, `integrity_check` not `ok`, disk
  headroom below threshold, any writer still live, batch error.
- What is safe to resume vs. what forces a restore. Batched deletes are resumable (each committed
  batch is durable); an interrupted `VACUUM` is not — say so plainly.
- The exact restore command, and how to verify the restore worked.

### 4. Post-checks (all must pass before unfencing)
- `PRAGMA integrity_check` → `ok`.
- Orphan count → 0.
- Live vector count → **unchanged** from the pre-run measurement. This is the one that proves you
  deleted only garbage; if live vectors dropped, you over-deleted and must restore.
- Database size → near the predicted ~1.2 GB.
- `rebalance doctor` clean (using the p2 checks).
- Only then restore the launchd schedules, and confirm the next sync completes normally.

### 5. Rollback
Explicit, with commands. Assume the reader is under time pressure and something has already gone
wrong.

## Style

Copy-pasteable commands. Every destructive step preceded by the read-only command that verifies its
precondition. Where a number is asserted, give the command that produces it — a runbook whose claims
cannot be re-derived rots silently.

## Definition of done

A reviewer who has not read GH-250 can follow it end to end, knows exactly when to stop, and can
get back to the starting state from any abort point.


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-P3-TURN --agent agy --paths "phases/gh250-vector-bloat--p3/RELAY.md,PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-P3-TURN --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-P3-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/gh250-vector-bloat--p3/RELAY.md and PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-P3-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-P3-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh250-vector-bloat--p3/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
