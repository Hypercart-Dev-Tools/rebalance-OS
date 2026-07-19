# Marathon Phase gh156-p3-repair
STATUS: Approved
NEXT: codex

<!-- marathon-drive: task=MARATHON-GH156-P3-REPAIR-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

---
title: "GH-156 P3 — legacy clio:id backfill, then targeted idempotent re-emission"
status: "Brief authored; phase not yet run"
created: 2026-07-19
updated: 2026-07-19
owner: noel
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Close the loop: label the ~330
  legacy un-ID'd entries so dedup can see them, THEN re-emit only the genuinely missing IDs.
  Backfill before repair is the ordering invariant that prevents mass duplication.
---

# GH-156 P3 — legacy backfill + safe repair

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-19. Depends on P1's manifest and P2's classification. | Execute as marathon phase `gh156-p3-repair` (reviewer: agy), sequenced after `gh156-p2-detect`. Final phase of the bundle. |

## Where the code lives

`utils/CLIO/prompt-log-to-md.sh` and `test/clio-exporter.sh`.

## The ordering invariant — read this first

**Backfill MUST precede re-emission.** Dedup is keyed on `clio:id`. The ~330 pre-ID entries in
the live note carry none, so to a repair pass they look absent — and it would re-emit every one
of them as a duplicate.

This is a **demonstrated** failure mode, not a theoretical one. On 2026-07-19 a cursor rewound to
160 against a 163-line source caused 3 entries to be re-emitted that were already present in
legacy un-ID'd form, producing 3 duplicate blocks (detected by multiset comparison against a
backup — net exactly +23 lines — and reverted). At full scale that is ~330 duplicates in the
operator's primary note.

If backfill cannot confidently label an entry, repair must treat it as **present** (skip it),
never as missing. Under-repairing is recoverable; duplicating the note is what this whole issue
exists to prevent.

## Task

### 1. Legacy backfill (`--backfill`)

- Match each un-ID'd target entry against the raw JSONL on **timestamp + machine + prompt body**.
  All three must agree; timestamp alone is not sufficient (two machines can share a second).
- On a confident match, insert the `<!-- clio:id:… -->` comment line immediately above the
  entry's `## REPO` heading. Change **nothing else** about the entry — not whitespace, not the
  quoted body, not the ordering.
- On an ambiguous or absent match, **leave the entry completely untouched** and report it. Never
  guess an ID.
- Dry-run first and by default: `--backfill` reports its plan; `--backfill --apply` writes.
- Idempotent: a second `--backfill` run labels nothing new and changes no bytes.
- Add successfully backfilled IDs to the manifest — they are now delivered and provable.

### 2. Targeted re-emission (`--repair`)

- Operates **only** on P2's `delivered-missing` set. Never a full replay; never touches the cursor.
- Renders the missing entries from the raw JSONL in the existing entry format and inserts them
  below the `<!-- CLIO:ENTRIES -->` marker, newest first, deduped by `clio:id`.
- Dry-run first and by default: `--repair` reports its plan; `--repair --apply` writes.
- **Refuse to run if unlabelled legacy entries remain.** `--repair --apply` must hard-fail with a
  message pointing at `--backfill` when P2 reports any `legacy-unlabelled` entries. This is the
  enforcement of the ordering invariant — do not make it a warning.
- Re-running `--repair --apply` after a successful repair must be a no-op.
- Reuse the existing verify-after-write path: confirm each re-emitted ID is present in the
  written file before reporting success.

### 3. Safety rails (both modes)

- Write a timestamped backup of the target beside it before any `--apply` write, and name the
  backup path in the output.
- All writes atomic (temp + `mv` in the same directory).
- Content above the marker must survive byte for byte, in both modes.

## Constraints

- Pure `bash` + `jq`/`grep`/`sed`/`awk`; bash 3.2 compatible.
- Never touch the raw JSONL — it is the source of truth and is never rewritten by repair.
- Never delete anything; quarantine/backup only.
- Running `--backfill` or `--repair` against the LIVE note is an **operator action**, explicitly
  out of scope for this phase. Ship and test the capability against fixtures only.

## Acceptance (QA gate — all must hold)

- [ ] Backfill labels a legacy fixture's entries correctly; a second run changes zero bytes.
- [ ] An entry with no confident JSONL match is left untouched and reported, not guessed.
- [ ] `--repair --apply` **hard-fails** while any `legacy-unlabelled` entry remains.
- [ ] After backfill, `--repair` re-emits **zero** legacy entries (the headline regression: the
      ~330 live entries must not duplicate).
- [ ] A deliberately deleted rendered entry is restored by `--repair --apply`, once, with the
      correct body — and a second run is a no-op.
- [ ] The three CLIO-import prompts (2026-07-17 19:03–19:07 PT) are recoverable from raw JSONL
      without a full replay — the parent doc's headline acceptance criterion.
- [ ] Content above the marker is byte-identical before and after backfill + repair.
- [ ] A backup is written before every `--apply` and its path is reported.
- [ ] Suite green under `/bin/bash` 3.2; `utils/pdda/pdda.sh run` clean.

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-GH156-P3-REPAIR-TURN --agent codex --paths "phases/gh-156-clio-projection--gh156-p3-repair/RELAY.md,utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-GH156-P3-REPAIR-TURN --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH156-P3-REPAIR-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/gh-156-clio-projection--gh156-p3-repair/RELAY.md and utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH156-P3-REPAIR-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-GH156-P3-REPAIR-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh-156-clio-projection--gh156-p3-repair/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 1 · Builder · codex

Implemented P3 in `utils/CLIO/prompt-log-to-md.sh` and expanded `test/clio-exporter.sh`.

- Added dry-run-by-default `--backfill` and `--repair` modes with explicit `--apply` writes, atomic replacements, timestamped beside-target backups, and output that names each backup.
- Backfill matches timestamp, machine, and rendered prompt body; only unique matches get an immediately preceding `clio:id` comment and a manifest receipt. Unmatched/ambiguous entries are left unchanged and reported.
- Repair consumes only manifest-backed `delivered-missing` IDs, hard-fails on remaining matched `legacy-unlabelled` entries, verifies all written IDs, and does not move the cursor.
- Tightened status legacy detection to compare one rendered entry rather than unrelated strings anywhere in the note.
- Added P3 fixture coverage for dry runs, blocked pre-backfill repair, byte-preserved pre-marker content, backups, manifest updates, idempotency, unmatched legacy safety, and recovery of the three 19:03–19:07 CLIO-import prompts.

Verification: `/bin/bash test/clio-exporter.sh` (PASS for `bash` and `/bin/bash`).

### Round 1 · Reviewer · agy

I have reviewed the `prompt-log-to-md.sh` implementation and the `clio-exporter.sh` tests. The implementation correctly introduces `--backfill` and `--repair` modes. The constraints around legacy labeling are sound and safely skip ambiguous/absent entries without guessing. The ordering invariant (enforcing backfill before repair) is strictly enforced as a hard failure. Test coverage looks comprehensive and correctly validates these scenarios. The test suite passes cleanly under bash and `/bin/bash`. 

**Verdict:** Approved
