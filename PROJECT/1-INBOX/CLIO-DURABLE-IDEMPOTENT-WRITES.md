---
title: CLIO — Durable, Idempotent Writes to the Shared Obsidian Note
status: proposed
doc_type: project-plan
owner: Noel Saw
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

## Status

| What was just completed | What's next |
|---|---|
| **Plan drafted (2026-07-19).** Root-caused the durability gap in the CLIO exporter (`prompt-log-to-md.sh` in [utils/CLIO/INSTALL.md](../../utils/CLIO/INSTALL.md)): correctness depends on a per-device line-count **cursor** that advances whether or not the write survives sync, with **no content-level idempotency and no conflict-copy reconciliation**. Confirmed the Swift [PromptLogReader](../../macOS/Apps/Focus5Float/Sources/Focus5Float/PromptLogReader.swift) parses the note positionally, so any in-note format change is a coupled cross-component concern. | Execute **Phase 0** (spike: reproduce the three failure modes and pin the real conflict-file naming on this sync stack) before writing code, per PDDA discovery rules. |

## Table of contents

- [Context](#context)
- [The durability gap (root cause)](#the-durability-gap-root-cause)
- [Design](#design)
- [Rejected alternatives](#rejected-alternatives)
- [Phase 0 — Spike: reproduce & confirm](#phase-0--spike-reproduce--confirm)
- [Phase 1 — Content-addressed idempotent append](#phase-1--content-addressed-idempotent-append)
- [Phase 2 — Conflict-copy reconciliation](#phase-2--conflict-copy-reconciliation)
- [Phase 3 — (Optional) per-device regions](#phase-3--optional-per-device-regions)
- [Anti-goals](#anti-goals)

## Context

CLIO logs every Claude Code prompt to a centralized append-only JSONL
(`~/.claude/prompt-log.jsonl`), and a **separate** exporter script
(`prompt-log-to-md.sh`) renders that JSONL into a human-readable Markdown note.
When that note lives in a folder synced across machines (an Obsidian vault via
Obsidian Sync / iCloud / Dropbox), the intended behavior is that **each device
appends only its own new local prompts** to the one shared note, and both
devices' history accumulates there. The cross-device merge is *emergent* from
sync + incremental append — no device ever reads another device's JSONL.

INSTALL.md is already honest about the weakness (see its final **Caveat** bullet):
the merge is *best-effort, not transactional*. This plan closes that gap.

## The durability gap (root cause)

The exporter's correctness rests entirely on a **per-device cursor** — a line
count stored in `~/.claude/prompt-log-to-md.state` — that says "I have already
emitted the first N lines of my local JSONL." Three failure modes follow:

1. **Cursor advances even when the write doesn't survive sync.** The local
   `temp + mv` is atomic *on that disk*, so a single reader never sees a
   half-written file. But sync happens **after** `mv`, asynchronously. If two
   devices write near-simultaneously, Obsidian/iCloud resolves it by spawning a
   **conflict copy** (`… (conflicted copy).md`, `*.sync-conflict-*.md`, iCloud
   `… 2.md`). One device's freshly appended entries land in that orphan file
   that nothing reads — and its cursor has already moved past them, so they are
   **permanently absent** from the canonical note.
2. **No content-level idempotency / dedup.** Correctness is positional, not
   content-addressed. The two recovery paths that re-emit from scratch
   (`corrupt state → LAST_LINE=0` and `JSONL shrank/rotated → LAST_LINE=0`) both
   **re-prepend everything**, and because nothing detects "this entry is already
   in the note," they produce **duplicates**.
3. **No reconciliation of conflict copies.** Nothing ever looks for the orphaned
   sibling files, so a batch lost to (1) is never pulled back.

The through-line: **the cursor is load-bearing for correctness when it should
only be an optimization.** Fix that inversion and (1)–(3) all become recoverable.

## Design

**Principle: make the write idempotent by content, and let the cursor be a pure
performance hint.** Two coupled mechanisms, plus a small hardening.

### 1. Content-addressed entry IDs (the core)

Give every rendered entry a **stable, unique, invisible ID** derived from its
source JSONL line — `sha256(raw_line)` (or `session_id + timestamp`, already
unique per prompt) — embedded as an HTML comment so it renders invisibly in
Obsidian:

```markdown
<!-- clio:id:8f3a…c1 -->
## HYPERCART
2026-07-19T18:42:11Z
Noels-MacBook-Pro · main

> "the prompt text"
```

Before appending an entry, the exporter builds a **set of IDs already present in
the target note** (one `grep -o 'clio:id:[0-9a-f]*'` pass) and **skips any entry
whose ID is already there.** Now:

- Re-emitting is harmless → the "start over from line 0" recovery paths stop
  duplicating.
- The cursor is demoted to an optimization: with it, we skip re-scanning old
  JSONL lines; **without it (deleted/corrupt), the run is still correct**, just
  slower. Correctness no longer depends on the cursor surviving anything.
- Because the dedup key lives **in the shared synced note itself**, the
  idempotency is **cross-device**: any device can safely reconcile entries it
  finds, regardless of which device first wrote them.

### 2. Conflict-copy reconciliation (the durability close-out)

At the start of each run, glob the output directory for conflict siblings
(`* (conflicted copy*).md`, `*.sync-conflict-*.md`, and — guardedly — iCloud
`<base> [0-9].md`), extract their `clio:id` set, **merge any IDs missing from
the canonical note** (deduped by the Phase 1 index), then **quarantine** the
conflict copy (move to a `.clio-reconciled/` subfolder rather than delete, so a
bad heuristic is never destructive). This is what actually recovers a batch that
failure mode (1) stranded.

### 3. Verify-after-write (cheap insurance)

After `mv`, read the note back and confirm the just-emitted IDs are present
before advancing the cursor. If they aren't, **don't advance** — the next run
re-attempts them. This makes the cursor advance *follow* a confirmed local
write instead of merely a successful `mv`.

### Cross-component coupling (must not break the Swift reader)

[PromptLogReader.swift](../../macOS/Apps/Focus5Float/Sources/Focus5Float/PromptLogReader.swift)
parses the note **positionally**: the line after `## REPO` is the timestamp, the
next is the machine/branch line. A naïvely placed `<!-- clio:id -->` comment
would either be mis-read as the timestamp or get swept into the previous entry's
prompt text. Therefore Phase 1 **requires** a matching, backward-compatible
change: teach the reader to **skip HTML-comment lines** wherever they appear, so
it tolerates both legacy (no-ID) and new (ID-bearing) entries. Governed by the
existing Focus5Float rollout rule — `swift build` green and `swift test` green
after every change.

## Rejected alternatives

- **Local sidecar ID index** (`~/.claude/prompt-log-to-md.index`): keeps the MD
  format unchanged (no Swift change), but a per-device local file **cannot**
  dedup across devices or absorb conflict copies — the dedup key must be
  readable from the *shared synced artifact* to be cross-device. Rejected as
  not solving the actual problem.
- **File lock during write**: an advisory lock serializes local writers but does
  nothing about sync-layer conflict copies (sync runs async, outside any local
  lock). Necessary-but-insufficient; folded into Phase 3 only if measurements
  justify it.
- **Full per-device regions now (Phase 3) as the primary fix**: the cleanest
  *conflict-avoidance* design (mirrors the Git Pulse per-device-namespacing
  durable fix — see the `pulse-sync-render-only-this-device` note), but it
  changes the note layout *and* the Swift reader's block model, a larger blast
  radius. Kept as an optional deeper phase; Phases 1–2 deliver the durability
  win without a layout change.

## Phase 0 — Spike: reproduce & confirm

Discovery phase — **findings written back into this doc before its QA gate can pass.**

- Reproduce all three failure modes locally: (1) force a conflict copy by having
  two writers append before a sync round-trip; (2) delete/corrupt the state file
  and observe duplicate re-emit; (3) confirm no reconciliation occurs.
- Pin the **exact** conflict-file naming produced by the operator's real sync
  stack (Obsidian Sync vs iCloud vs Dropbox) — the reconciliation glob in
  Phase 2 depends on this, and guessing wrong makes it a no-op.
- Empirically confirm the Swift reader's behavior when an ID comment is injected
  above / inside / below an entry block (validates the "skip comment lines"
  requirement).

**QA gate:** the three failure modes are reproduced and documented here with the
real conflict-file name(s); the reader's mis-parse of an injected comment is
demonstrated (justifying Phase 1's coupled Swift change).

## Phase 1 — Content-addressed idempotent append

- Emit a `<!-- clio:id:HASH -->` comment per entry in `prompt-log-to-md.sh`.
- Build the in-note ID set once per run; skip entries already present.
- Demote the cursor to an optimization; make a missing/corrupt state file a
  correct (if slower) full-reconcile, **not** a duplicating re-emit.
- Add verify-after-write before advancing the cursor.
- Teach `PromptLogReader.swift` to skip HTML-comment lines (backward compatible
  with legacy no-ID entries).

**QA gate (DRY/observability/idempotency):** running the exporter twice in a row
is a no-op (0 new); deleting the state file and re-running produces **0**
duplicates in the note; a new prompt still appends exactly once. `swift build`
green; `swift test` green including a new fixture with ID comments; existing
Focus 5 / Prompt Log tab behavior unchanged.

## Phase 2 — Conflict-copy reconciliation

- Detect conflict siblings by the Phase 0-confirmed naming; merge their missing
  IDs into canonical; quarantine (not delete) the copy under `.clio-reconciled/`.
- Structured, greppable log line of what was reconciled (no silent recovery).

**QA gate:** a manufactured conflict copy holding one unique entry is fully
absorbed into the canonical note on the next run, deduped, with the copy moved
to quarantine and the action logged; a conflict copy with **only** already-known
IDs is quarantined with nothing appended.

## Phase 3 — (Optional) per-device regions

Deferred / opt-in. Give each device its own marker region
(`<!-- clio:device:MACHINE:start/end -->`) or per-device note composed into a
merged view, so devices never edit each other's bytes and sync has nothing to
conflict on — the fuller structural fix that mirrors the Git Pulse
per-device-namespacing pattern. Requires a PromptLogReader block-model change.

**QA gate:** two devices writing concurrently produce **no** conflict copy at
all (not just a recovered one); reader renders the merged view identically to
today. **Gated on** Phases 1–2 proving insufficient in practice — do not build
speculatively.

## Anti-goals

- No changes to the hook (`log-prompt.sh`) or the raw JSONL — the JSONL stays
  the append-only source of truth and per-device local record.
- No cross-device reads of another device's JSONL — the merge stays emergent
  from sync + idempotent append (that property is a feature, not a gap).
- No distributed consensus / locking service — this is a single shared file with
  best-effort sync; the goal is *recoverable* idempotency, not a transaction log.
- No dedup by fuzzy prompt-text matching — dedup is strictly by stable content ID.
