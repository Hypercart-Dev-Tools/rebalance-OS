---
gh_issue: 156
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/156
title: "[CRITICAL] CLIO prompt projection silently loses historical entries"
status: triage
doc_type: pdda-spec
priority: P0
effort: 2
complexity: 3
risk: 3
phases: 3
created: 2026-07-18
updated: 2026-07-19
---

# GH-156 — Critical CLIO prompt-projection loss

## TOC

- Decision and impact
- What already shipped (2026-07-19 rescope)
- Evidence and root cause
- PDDA contract
- Phased delivery
- Swarm Preflight Contract
- Acceptance checklist
- Out of scope

## Decision and impact

Treat this as a P0 historical-integrity defect. The raw Claude prompt log is
not the operator-facing record; the rendered Obsidian target is. A cursor that
claims delivery while that target lacks the source entries breaks the product
promise of a durable, cross-device prompt history.

## What already shipped (2026-07-19 rescope)

This doc was captured **2026-07-18**, one day before the CLIO durable-writes
marathon (`PROJECT/3-COMPLETED/MARATHON-2026-07-19-CLIO-DURABLE/`, status COMPLETE) landed.
Two of its three original phases are now substantially built, so the plan below
is rescoped to the genuine remainder. Verified against `utils/CLIO/INSTALL.md`
at `development@0970d3f`:

| Originally planned | Status | Evidence |
|---|---|---|
| Stable entry IDs on emitted entries | **Shipped** | `<!-- clio:id:<session>:<ts> -->`, dedup via `existing_ids` |
| Idempotent append; never clobber the shared note | **Shipped** | marker-bounded insert, atomic temp+`mv` |
| Conflict-copy reconciliation, quarantine not delete | **Shipped** | sibling globs → `.clio-reconciled/` |
| Non-mutating preview before recovery writes | **Shipped** | `CLIO_RECONCILE_DRY_RUN=1` |
| Verify-after-write before advancing the cursor | **Shipped (intra-run only)** | emitted IDs re-read from `$OUT`; cursor held on mismatch |
| **Source-owned manifest of rendered IDs** | **NOT built** | zero `manifest` references in `INSTALL.md` |
| **Detection of target replacement / historical loss** | **NOT built** | no cross-run reconciliation of delivered IDs vs target |
| **Targeted repair of specific missing IDs** | **NOT built** | only lever is deleting the state file → full replay |
| **Legacy un-ID'd entry backfill** | **NOT built** | new — see below |

The shipped verify-after-write is a genuine improvement but is **intra-run**: it
proves the entries written *this run* landed. It cannot detect an entry that was
delivered last week and has since been deleted, overwritten, or lost to a sync
round-trip.

## Evidence and root cause

The original capture's evidence stands: the raw CLIO JSONL contains the
2026-07-17 19:03–19:07 PT prompts that directed the CLIO import, back-port, and
reinstall, while the configured Obsidian target `0. Claude Prompts.md` does not.
Its cursor equals the raw line count, so scheduled runs consider those entries
permanently complete and will not replay them.

**Reproduced live during the 2026-07-19 reinstall on the Mac Studio**, which
sharpened the root cause and added one finding the original capture missed:

1. **Marker displacement is real and already present.** The target's
   `<!-- CLIO:ENTRIES -->` marker sits at **line 331 of 4291**, not at the top —
   with a duplicated CLIO header block immediately above it (lines 328–331). The
   current exporter only ever writes below the marker, so this is proof of an
   external writer or sync merge rearranging the projection after cursor
   advancement.

2. **~330 legacy entries carry no `clio:id`.** Everything above the marker was
   written by the pre-ID exporter. Dedup is keyed on `clio:id`, so those entries
   are **invisible to it**. This is the load-bearing new finding: it means any
   repair or cursor reset re-emits them as duplicates rather than recognising
   them as already delivered. A repair path built without a legacy backfill
   would actively corrupt the note.

3. **Confirmed by accident, then reverted.** A cursor rewound to 160 against a
   163-line source caused the exporter to re-emit 3 entries that were already
   present in legacy un-ID'd form — producing 3 duplicate blocks. Detected by
   multiset comparison against a backup (net exactly +23 lines, no content lost)
   and reverted to a byte-identical state. This is the failure mode in miniature,
   and it will recur on any state-file loss.

The through-line: **capture acknowledgement is being mistaken for durable
projection acknowledgement**, and the identity scheme that would let us tell the
difference does not cover the historical majority of the note.

## PDDA contract

### Problem

An overwritten or externally changed target silently loses source history, and
the exporter has no way to notice or to repair a specific gap — its only lever
is a full replay that duplicates every legacy entry.

### Decision

Give the exporter a **source-owned manifest** of rendered IDs and reconcile it
against the target on every run. Add a non-mutating status/diff path, then a
targeted repair that re-emits only genuinely missing IDs. Backfill `clio:id`
onto legacy entries first, so repair can distinguish "missing" from
"present but unlabelled". The exporter remains the single writer for its
marker-bounded block; human text and other-device entries stay preserved.

### Design constraints

- Reconciliation must be idempotent and append/insert only missing entries.
- Never regenerate or clobber the full shared note.
- Keep the raw JSONL as the source of truth; the manifest is a delivery receipt,
  not a second history store.
- Provide a non-mutating status/repair preview before any recovery write.
- Report source, rendered, and missing counts with actionable diagnostics.
- **Backfill before repair.** No targeted re-emission may run against a note that
  still holds un-ID'd legacy entries — that ordering is what prevents duplicates.
- Content above the marker must survive byte for byte.

### Structural blocker

The exporter currently lives as a **heredoc inside `utils/CLIO/INSTALL.md`**.
It has no test surface at all — the durable marathon gated on `swift build`,
which never exercised a line of it, and the bash-3.2 empty-array defect
(commit `d96439b`) reached a live machine as a direct result. Repair logic of
this risk level cannot ship untested, so Phase 1 extracts the exporter to a real
script file that `INSTALL.md` installs from, and stands up a fixture harness.

## Phased delivery

### Phase 1 — testable surface + manifest receipt

- [ ] Extract the exporter heredoc to `utils/CLIO/prompt-log-to-md.sh`; rewrite
      `INSTALL.md` to install from that file rather than re-embedding it.
- [ ] Stand up `test/clio-exporter.sh` with fixtures: fresh note, legacy
      un-ID'd note, marker-displaced note, conflict sibling, bash-3.2 empty array.
- [ ] Add a source-owned manifest of rendered IDs, written only after the
      existing verify-after-write check passes.
- [ ] Manifest must be additive and cursor-independent (a lost state file must
      not lose the receipt).

### Phase 2 — detection and status

- [ ] `--status`: report source count, manifest count, target count, missing IDs.
- [ ] Detect marker displacement and target replacement **without writing**.
- [ ] Classify each source entry: delivered-and-present, delivered-but-missing,
      never-delivered, legacy-unlabelled.
- [ ] Exit non-zero on detected loss so a scheduled run surfaces it.

### Phase 3 — legacy backfill + safe repair

- [ ] One-time backfill stamping `clio:id` onto legacy un-ID'd entries by
      matching timestamp + machine + prompt body against the raw JSONL.
- [ ] Backfill must be dry-run-first, idempotent, and leave unmatched legacy
      entries untouched rather than guessing.
- [ ] Targeted idempotent re-emission of missing IDs, with a dry-run repair plan
      and an explicit apply path.
- [ ] Preserve cross-device entries and human-authored text.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        "if [ -x test/clio-exporter.sh ]; then bash test/clio-exporter.sh; else awk \"/prompt-log-to-md.sh << .EOF.$/{f=1;next} f&&/^EOF$/{exit} f\" utils/CLIO/INSTALL.md > \"${TMPDIR:-/tmp}/clio-gate.sh\" && bash -n \"${TMPDIR:-/tmp}/clio-gate.sh\"; fi",
  "fix_probes": [
    { "type": "grep_absent", "path": "utils/CLIO/INSTALL.md", "pattern": "manifest" },
    { "type": "path_absent", "path": "utils/CLIO/prompt-log-to-md.sh" },
    { "type": "path_absent", "path": "test/clio-exporter.sh" }
  ],
  "artifacts":     [ "utils/CLIO/INSTALL.md", "utils/CLIO/prompt-log-to-md.sh", "test/clio-exporter.sh" ],
  "artifacts_new": [ "utils/CLIO/prompt-log-to-md.sh", "test/clio-exporter.sh" ],
  "remediation": { "source": "self#phases", "criteria": "Phases 1-3 of GH-156 (rescoped 2026-07-19)" },
  "lanes":       { "agy_safe": [ "test/clio-exporter.sh" ], "orchestrator_only": [] }
}
```

## Acceptance checklist

- [ ] The three CLIO-import prompts can be recovered from raw JSONL without a
      full replay.
- [ ] A replaced target is detected on the next scheduled run and exits non-zero.
- [ ] Re-running repair creates no duplicate prompt blocks.
- [ ] Backfill correctly labels the ~330 legacy entries in the live note, and a
      subsequent repair re-emits **zero** of them.
- [ ] Content above the marker is byte-identical before and after backfill+repair.
- [ ] Malformed source rows and configured exclusions retain current semantics.
- [ ] Cross-device append and concurrent-marker fixtures are covered.
- [ ] The exporter runs green on `/bin/bash` 3.2 (macOS system bash).

## Out of scope

- Changing UserPromptSubmit capture semantics.
- An automatic unreviewed full historical replay into the shared Obsidian note.
- Per-device regions (deferred Phase 3 of the durable-writes plan) — revisit only
  if manifest + repair prove insufficient in practice.
