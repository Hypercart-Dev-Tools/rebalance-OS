---
title: "CLIO P2 — conflict-copy reconciliation (full-block, quarantine-not-delete)"
status: "Complete — phase ran and was approved; marathon completed 2026-07-19."
created: 2026-07-19
updated: 2026-07-19
owner: noel
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Make the exporter self-healing:
  absorb the entries a sync conflict copy stranded back into the canonical note (deduped by
  clio:id, copying the FULL entry block), then quarantine the copy rather than deleting it.
---

# CLIO P2 — conflict-copy reconciliation

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-19; parent plan is `PROJECT/1-INBOX/CLIO-DURABLE-IDEMPOTENT-WRITES.md`. Depends on P1's `clio:id` infrastructure. | Execute as marathon phase `clio-p2-reconcile` (reviewer: agy), sequenced after `clio-p1-idempotent`. |

## Where the code lives

Same exporter heredoc in [utils/CLIO/INSTALL.md](../../../../utils/CLIO/INSTALL.md)
(`prompt-log-to-md.sh`). This phase adds a reconciliation step; it depends on P1's `clio:id`
comments and the in-note ID set already existing.

## Task

Add a reconciliation step near the **start** of a run (after `$OUT` is known, before the normal
append):

1. **Find conflict siblings** in `$(dirname "$OUT")` matching the sync-stack conflict patterns:
   - Obsidian Sync: `*.sync-conflict-*.md`
   - iCloud / generic "conflicted copy": `* (conflicted copy*).md`
   - iCloud numeric dupes of the base name: `<base> [0-9]*.md`
   Skip `$OUT` itself and anything already under `.clio-reconciled/`.
2. **Merge missing entries as FULL blocks.** For each sibling, for every `clio:id` present in the
   sibling but **missing** from canonical `$OUT`, copy the **entire rendered entry block** — the
   `<!-- clio:id:… -->` comment line, the `## REPO` line, the timestamp line, the machine/branch
   line, and the `>`-quoted prompt (through the blank line before the next `## `). Insert merged
   blocks below the `<!-- CLIO:ENTRIES -->` marker, deduped by `clio:id` (never merge an ID already
   in canonical). **Do not** merge IDs alone — the prompt content must come with them.
3. **Quarantine, never delete.** Move each processed sibling into a `.clio-reconciled/` subfolder
   of the output dir (create it if needed). The file must remain on disk.
4. **Structured log.** Emit one greppable line per reconciled sibling:
   `reconciled <basename>: merged=<n> quarantined=<path>`.
5. **Dry-run mode.** Honor an env flag (e.g. `CLIO_RECONCILE_DRY_RUN=1`) that reports intended
   merges/moves without changing any file.

## Constraints

- Pure `bash` + `jq`/`grep`/`sed`; no new dependencies.
- Non-destructive: quarantine, never `rm`. Never touch the raw JSONL or the hook.
- Reconciliation must itself be idempotent — re-running with the same siblings merges nothing new.

## Acceptance (QA gate — all must hold)

- [ ] A manufactured conflict copy holding **one unique** entry is fully absorbed into `$OUT` on the
      next run — the whole block (repo/timestamp/prompt), deduped by `clio:id`.
- [ ] The processed conflict copy is moved to `.clio-reconciled/` (still on disk, never deleted).
- [ ] A conflict copy containing **only already-known** IDs is quarantined with nothing appended.
- [ ] `CLIO_RECONCILE_DRY_RUN=1` reports intended actions and changes no file.
- [ ] `utils/pdda/pdda.sh run` clean; `swift build` still green (no Swift change expected this phase).
