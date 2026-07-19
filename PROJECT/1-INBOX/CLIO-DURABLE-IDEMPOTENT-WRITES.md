---
title: CLIO — Durable, Idempotent Writes to the Shared Obsidian Note
status: proposed
doc_type: project-plan
owner: noel@neochro.me
created: 2026-07-19
updated: 2026-07-19
branch: work/clio-durable-obsidian-writes
goal: >
  Make CLIO's Markdown exporter write to the shared, sync-folder-hosted Obsidian note
  in a way that is idempotent by content and durable across concurrent multi-device
  writes — so a lost/late sync round-trip, a corrupt cursor, or an Obsidian/iCloud
  conflict copy can never silently drop or duplicate prompts in the canonical note.
priority: P2
related:
  - utils/CLIO/INSTALL.md
  - PROJECT/2-WORKING/P2-FOCUS5-CLIO-PROMPT-LOG-TAB.md
  - macOS/Apps/Focus5Float/Sources/Focus5Float/PromptLogReader.swift
non_goals:
  - Changing the hook (`log-prompt.sh`) or the raw JSONL contract
  - Turning the append into a transactional / distributed-consensus system
effort: M
complexity: M
risk: M
phases: 4
---

# CLIO — Durable, Idempotent Writes to the Shared Obsidian Note

**One-liner.** CLIO's exporter renders the append-only prompt JSONL into a shared
Obsidian note whose cross-device merge is currently *best-effort*: correctness rests on
a per-device line-count **cursor** that advances whether or not the write survives sync,
with **no content-level idempotency** and **no conflict-copy reconciliation**. This plan
makes the write **idempotent by content** (invisible per-entry IDs) and **self-healing**
(absorbs orphaned conflict copies), demoting the cursor to a pure optimization.

## Status

| Most recently completed phase | What's next |
|---|---|
| **Phases 1 & 2 built + verified (2026-07-19).** Executed via marathon (`PROJECT/3-COMPLETED/MARATHON-2026-07-19-CLIO-DURABLE/`, builder codex / reviewer agy, both phases approved, `swift build` gate green). Delivered: content-addressed `session_id:timestamp` IDs + dedup + verify-after-write in the exporter; conflict-sibling reconciliation (full-block, quarantine-not-delete, dry-run); Swift reader now skips `<!--` lines (48 swift tests pass, +7). **Independent verification caught a real defect the swift gate could not:** the reconciliation array tripped bash 3.2's empty-array-under-`set -u` "unbound variable" on macOS, breaking every normal run — **fixed** (`${arr[@]+…}` guard) and re-verified: idempotency, state-delete safety, full reconciliation, and dry-run all pass on `/bin/bash` 3.2. Prior: agy plan review (8/8 heuristics, 4 refinements applied). | **Phase 0** (live-sync spike) and **Phase 3** (per-device regions) remain deferred — Phase 0 needs two real syncing devices; Phase 3 is gated on 1–2 proving insufficient. Operator litmus: install the updated exporter on both machines and watch a real conflict get reconciled. |

## Table of contents

- [Context](#context)
- [The durability gap (root cause)](#the-durability-gap-root-cause)
- [Design summary](#design-summary)
- [Rejected alternatives](#rejected-alternatives)
- [Phase 0 — Spike: reproduce & confirm](#phase-0--spike-reproduce--confirm)
- [Phase 1 — Content-addressed idempotent append](#phase-1--content-addressed-idempotent-append)
- [Phase 2 — Conflict-copy reconciliation](#phase-2--conflict-copy-reconciliation)
- [Phase 3 — (Optional) per-device regions](#phase-3--optional-per-device-regions)
- [Anti-goals](#anti-goals)

## Context

CLIO logs every Claude Code prompt to a centralized append-only JSONL
(`~/.claude/prompt-log.jsonl`), and a **separate** exporter (`prompt-log-to-md.sh`)
renders that JSONL into a human-readable Markdown note. When that note lives in a
sync folder (Obsidian Sync / iCloud / Dropbox), each device is meant to append **only
its own new local prompts** to the one shared note, so both devices' history
accumulates there. The merge is *emergent* from sync + incremental append — no device
ever reads another device's JSONL. INSTALL.md's final **Caveat** already admits this is
best-effort, not transactional. This plan closes that gap. The default auto-sync cadence
was just tightened from 5 min → 1 min, which *raises* concurrent-write odds and makes
this work more valuable.

## The durability gap (root cause)

Correctness rests on a **per-device cursor** — a line count in
`~/.claude/prompt-log-to-md.state` meaning "I already emitted the first N lines of my
local JSONL." Three failure modes follow:

1. **Cursor advances even when the write doesn't survive sync.** The local `temp + mv`
   is atomic *on that disk*, but sync happens **after** `mv`, asynchronously. Two devices
   writing near-simultaneously make Obsidian/iCloud spawn a **conflict copy**
   (`… (conflicted copy).md`, `*.sync-conflict-*.md`, iCloud `… 2.md`); one device's
   appended entries land in that orphan nothing reads — and its cursor has already moved
   past them, so they are **permanently absent** from the canonical note.
2. **No content-level idempotency / dedup.** Correctness is positional, not
   content-addressed. Both re-emit recovery paths (`corrupt state → 0` and
   `JSONL shrank/rotated → 0`) **re-prepend everything**, producing **duplicates**.
3. **No reconciliation of conflict copies.** Nothing looks for the orphaned siblings, so
   a batch lost to (1) is never pulled back.

The through-line: **the cursor is load-bearing for correctness when it should only be an
optimization.** Fix that inversion and (1)–(3) all become recoverable.

## Design summary

- **Content-addressed entry IDs (core):** emit a stable, unique, invisible ID per entry as
  an HTML comment (`<!-- clio:id:ID -->`). The ID is the composite `session_id + ":" +
  timestamp`, which is **already unique per prompt and can be emitted inline by the existing
  `jq` render pass** — no per-line subprocess (adjudicated from agy's efficiency finding; a
  `shasum`-per-line loop would be O(N) subprocess spawns on a full rebuild). Only if the
  Phase 0 spike finds sub-second collisions do we extend the ID with a short hash computed
  in **one bulk pass** (a single `python`/`jq` invocation over the batch, never per-line).
  Before appending, build the set of IDs already in the note (one `grep` pass) and **skip
  any entry already present**. Re-emit becomes harmless; the cursor becomes a mere speed
  hint; a missing/corrupt cursor is still correct, just slower. Because the dedup key lives
  **in the shared synced note itself**, idempotency is cross-device.
- **Conflict-copy reconciliation:** each run globs the output dir for conflict siblings.
  For each ID present in a sibling but **missing** from canonical, it copies the **entire
  rendered entry block** — the `<!-- clio:id -->` comment, the `## REPO` line, timestamp,
  machine/branch line, and blockquote prompt — not just the ID marker (adjudicated from
  agy's block-extraction finding: merging IDs alone would drop the actual prompt content).
  It then **quarantines** (not deletes) the copy under `.clio-reconciled/`.
- **Verify-after-write:** after `mv`, read the note back and confirm the just-emitted IDs
  are present before advancing the cursor.
- **Coupled Swift change:** [PromptLogReader.swift](../../macOS/Apps/Focus5Float/Sources/Focus5Float/PromptLogReader.swift)
  parses positionally, so after splitting the body into lines it must **drop any line
  starting with `<!--`** *before* the positional inner loop runs (agy's nit: a simple
  pre-filter keeps the positional logic untouched and tolerates both legacy no-ID and new
  ID-bearing entries). Governed by the Focus5Float rollout rule: `swift build` + `swift
  test` green after every change.

**Scope classification (Review Heuristic 3):** the CLIO Markdown note is an **export /
read-only projection** of the prompt JSONL — it is *not* a rebalance canonical store and
is **not `--source all` eligible**; nothing here registers a collector or touches
`index_ops.py`. This plan only hardens an existing export path.

## Rejected alternatives

- **Local sidecar ID index** (`~/.claude/prompt-log-to-md.index`): keeps the MD format
  unchanged (no Swift change) but a per-device local file **cannot** dedup across devices
  or absorb conflict copies — the dedup key must be readable from the *shared synced
  artifact* to be cross-device. Rejected as not solving the actual problem.
- **File lock during write:** serializes local writers but does nothing about sync-layer
  conflict copies (sync runs async, outside any lock). Necessary-but-insufficient.
- **Full per-device regions now as the primary fix:** cleanest conflict-*avoidance*
  (mirrors the Git Pulse per-device-namespacing durable fix) but changes note layout *and*
  the Swift reader's block model — larger blast radius. Kept as optional Phase 3.

---

## Phase 0 — Spike: reproduce & confirm

Discovery phase — **findings must be written back into this doc before its QA gate passes.**

**Work items (observable):**
- [ ] Reproduce failure mode (1): drive two writers to append before a sync round-trip and capture the resulting conflict-copy filename verbatim.
- [ ] Reproduce failure mode (2): delete/corrupt `prompt-log-to-md.state`, re-run, and record the exact duplicate output produced.
- [ ] Reproduce failure mode (3): confirm no reconciliation of the conflict copy occurs on subsequent runs.
- [ ] Pin the exact conflict-file naming pattern(s) produced by the operator's real sync stack (Obsidian Sync vs iCloud vs Dropbox) — the Phase 2 glob depends on this.
- [ ] Inject a `<!-- clio:id:… -->` comment above / inside / below a real entry and record how `PromptLogReader.parse` mis-reads each placement.
- [ ] Write all findings (filenames, dup output, reader behavior) back into this doc under a `## Phase 0 findings` heading.

### QA checklist — Phase 0
- [ ] All three failure modes are reproduced and documented here with real, copy-pasted evidence (not described from theory).
- [ ] The real conflict-file name pattern(s) for this sync stack are recorded verbatim.
- [ ] The reader's mis-parse of an injected comment is demonstrated, justifying Phase 1's coupled Swift change.
- [ ] `## Phase 0 findings` section exists and is non-empty (PDDA discovery-phase requirement).

## Phase 1 — Content-addressed idempotent append

**Work items (observable):**
- [ ] Emit a `<!-- clio:id:ID -->` comment per rendered entry in `prompt-log-to-md.sh`, where `ID = session_id + ":" + timestamp`, **emitted inline by the existing `jq` render pass** (no per-line subprocess loop).
- [ ] Build the in-note ID set once per run (single `grep -o 'clio:id:[^ ]*'` pass) and skip entries whose ID is already present.
- [ ] Demote the cursor to an optimization: a missing/corrupt state file triggers a correct full reconcile, **not** a duplicating re-emit — and verify the full-rebuild path stays fast (bulk ID computation, no O(N) subprocess spawns; add a short bulk hash via one `python`/`jq` call only if Phase 0 found sub-second collisions).
- [ ] Add verify-after-write — confirm just-emitted IDs are present in the note before writing the new cursor value.
- [ ] Teach `PromptLogReader.swift` to drop lines starting with `<!--` immediately after the `body.components(separatedBy: "\n")` split, before the positional inner loop (backward compatible with legacy no-ID entries).
- [ ] Add a Swift test fixture containing ID comments (mixed legacy + ID-bearing entries).

### QA checklist — Phase 1
- [ ] Running the exporter twice in a row is a no-op (reports 0 new, appends nothing).
- [ ] Deleting `prompt-log-to-md.state` and re-running produces **0** duplicate entries in the note.
- [ ] A genuinely new prompt still appends exactly once, newest-first, below the marker.
- [ ] `swift build` green; `swift test` green including the new ID-comment fixture.
- [ ] Existing Focus 5 / Prompt Log tab behavior unchanged (no regression in `PromptLogTests`).
- [ ] Rendered IDs are invisible in Obsidian preview (HTML comments, verified live).

## Phase 2 — Conflict-copy reconciliation

**Work items (observable):**
- [ ] Glob the output directory for conflict siblings using the Phase 0-confirmed naming pattern(s).
- [ ] For each ID present in a sibling but missing from canonical, copy the **entire rendered entry block** (ID comment + `## REPO` + timestamp + machine/branch line + blockquote prompt), not just the ID marker — deduped via the Phase 1 index.
- [ ] Quarantine (move, not delete) each processed conflict copy under a `.clio-reconciled/` subfolder.
- [ ] Emit a structured, greppable log line per reconciliation (count merged, source filename, quarantine path) — no silent recovery.

### QA checklist — Phase 2
- [ ] A manufactured conflict copy holding one unique entry is fully absorbed into canonical on the next run, deduped.
- [ ] The processed conflict copy is moved to `.clio-reconciled/` (still on disk, never deleted).
- [ ] A conflict copy containing **only** already-known IDs is quarantined with nothing appended.
- [ ] Each reconciliation writes one structured log line; a dry-run mode reports intended actions without moving files.
- [ ] `rebalance doctor` and `utils/pdda/pdda.sh run` clean.

## Phase 3 — (Optional) per-device regions

Deferred / opt-in — **gated on Phases 1–2 proving insufficient in practice; do not build speculatively.**

**Work items (observable):**
- [ ] Design per-device marker regions (`<!-- clio:device:MACHINE:start/end -->`) or per-device notes composed into a merged view.
- [ ] Update `PromptLogReader.swift`'s block model to render the merged per-device view identically to today.
- [ ] Migrate the exporter to write only within this device's region.

### QA checklist — Phase 3
- [ ] Two devices writing concurrently produce **no** conflict copy at all (not merely a recovered one).
- [ ] The reader renders the merged view byte-identically to the pre-migration note for the same inputs.
- [ ] A documented, reversible migration path exists for notes already in the flat format.

## Anti-goals

- No changes to the hook (`log-prompt.sh`) or the raw JSONL — the JSONL stays the
  append-only source of truth and per-device local record.
- No cross-device reads of another device's JSONL — the merge stays emergent from sync +
  idempotent append (that property is a feature, not a gap).
- No distributed consensus / locking service — this is a single shared file with
  best-effort sync; the goal is *recoverable* idempotency, not a transaction log.
- No dedup by fuzzy prompt-text matching — dedup is strictly by stable content ID.
