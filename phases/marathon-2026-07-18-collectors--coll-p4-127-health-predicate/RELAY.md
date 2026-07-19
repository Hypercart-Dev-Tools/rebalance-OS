# Marathon Phase coll-p4-127-health-predicate
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-COLL-P4-127-HEALTH-PREDICATE-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

# Phase 4 — registry-driven content/volume health predicate

Part of **GH-127**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/127
Wave 2. **Depends on p3** — shares `src/rebalance/doctor.py`. Do not start until p3 has landed.
**Artifact: `src/rebalance/doctor.py`.**

## The problem

`_check_collector_freshness()` (`doctor.py:330`) reports a source **`ok`** whenever rows exist.
It never asks whether those rows *mean* anything. A collector writing structurally valid but
semantically empty rows looks healthy forever.

This has now fired **twice on the same collector in six weeks**:

| When | Failure | Detected by |
|---|---|---|
| June (#127) | 119 of 124 `email_messages` rows (96%) were husks — `message_id` + `snippet`, no sender, no subject, no `received_at`. Sat 3 weeks. 118 polluted `semantic_documents`. | a human noticing the ranker had nothing to rank |
| July (#141) | email freshness timestamp current, **0 rows in 7d** | `rebalance doctor`, after the monitoring layer was reinstalled |

Two shapes of the same defect: **content** absent with rows present, and **volume** absent with
freshness current. Both report `ok`.

## ⛔ Hard invariants

- **Registry-driven.** Adding a source's predicate must not edit the health module
  (Principle 3). The collector registry already owns `semantic_docs=` and `candidates=`
  providers — a `health_predicate=` is the **third use of the same seam**, not a new
  abstraction. If this phase invents a parallel registry, it has gone wrong.
- **Non-destructive.** Reporting `degraded` must never delete, purge, or rewrite rows
  (Principle 4 — *the store accretes truth*). Detection only.
- **Do not re-fix the June write-boundary bug.** It was fixed and the husk rows purged under
  #125. This phase is about the **detector**, not that bug.
- **Do not touch `scripts/health_issue_reporter.py`** (p1's artifact) or the job-liveness check
  p3 added — extend the freshness path only.
- **`_check_collector_freshness()` is shared and load-bearing** across all eight sources.
  Changing its contract changes every source's reported status. Extend; don't rewrite.

## Task

Teach the freshness contract to assert **content and volume**, not merely presence.

1. Add a `health_predicate=` provider to the collector registry — same seam as `semantic_docs=`
   / `candidates=`. Each source declares what a *meaningful* row looks like (email → has a
   sender or a subject; calendar → has a start time; github → has a title).
2. Report `degraded` (not `ok`) when rows exist but a material share fail the predicate.
3. Report the **volume** case too: freshness current but zero rows landed across the window —
   this is #141's shape and must be caught by the same mechanism, not a parallel one.
4. Sources without a declared predicate keep today's behavior. Absence of a predicate must not
   become a silent failure.

### The open question — decide it first, in the relay

The issue names this explicitly and it is **not pre-decided**: is "healthy but meaningless" a
**doctor warning**, a **freshness status**, or an **auth-log badge**? The row-count metric is
already plumbed; the question is where an operator actually sees it. State the choice and the
reasoning before implementing.

## Watch for

- **What counts as "a material share"?** A threshold pulled from thin air is a magic number.
  Justify it, make it per-source-overridable, or make it structural (any husk is a failure).
- **The predicate is a per-source assertion about schema.** Keep it declarative data, not
  arbitrary callables doing I/O, or health checks acquire their own failure modes.
- **`figma` is currently 37 days stale** (`last refresh advanced 37d ago`, window 7d) — a live
  third case worth checking your design against.
- Doctor's output is already long. A new status must be legible in it, not buried.

## Acceptance

- [ ] A source whose rows exist but are contentless reports something other than `ok`.
- [ ] A source whose freshness is current but landed **0 rows** in the window reports
      something other than `ok` (the #141 case), via the same mechanism.
- [ ] The check is registry-driven — adding a source's predicate does not edit the health
      module. Demonstrated by adding one for a second source.
- [ ] A regression test seeding a table full of husks asserts the source is **not** reported
      healthy.
- [ ] A regression test seeding an empty-but-fresh table asserts the same.
- [ ] Sources with no declared predicate behave exactly as before.
- [ ] Nothing is deleted or rewritten by the detector.
- [ ] The surfacing decision (warning / status / badge) is stated with reasoning.
- [ ] Gate: `.venv/bin/python -m pytest tests/ -k "doctor or health or freshness" -q` green.
- [ ] `rebalance doctor` runs clean and its output remains readable.

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/doctor.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-COLL-P4-127-HEALTH-PREDICATE-TURN --agent codex --paths "phases/marathon-2026-07-18-collectors--coll-p4-127-health-predicate/RELAY.md,src/rebalance/doctor.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-COLL-P4-127-HEALTH-PREDICATE-TURN --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-COLL-P4-127-HEALTH-PREDICATE-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/marathon-2026-07-18-collectors--coll-p4-127-health-predicate/RELAY.md and src/rebalance/doctor.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/doctor.py.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-COLL-P4-127-HEALTH-PREDICATE-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-COLL-P4-127-HEALTH-PREDICATE-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/marathon-2026-07-18-collectors--coll-p4-127-health-predicate/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
