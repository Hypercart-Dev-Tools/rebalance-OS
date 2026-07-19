# Marathon Phase gh156-p2-detect
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-GH156-P2-DETECT-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

---
title: "GH-156 P2 — non-mutating status: source/manifest/target reconciliation and loss detection"
status: "Brief authored; phase not yet run"
created: 2026-07-19
updated: 2026-07-19
owner: noel
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Make projection loss VISIBLE.
  Reconcile the P1 manifest against the live note on every run, classify every source entry,
  and exit non-zero when history has gone missing — without writing anything.
---

# GH-156 P2 — detection and status

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-19. Depends on P1's `utils/CLIO/prompt-log-to-md.sh`, `test/clio-exporter.sh`, and the manifest receipt. | Execute as marathon phase `gh156-p2-detect` (reviewer: agy), sequenced after `gh156-p1-manifest`. P3's repair consumes this phase's classification. |

## Where the code lives

`utils/CLIO/prompt-log-to-md.sh` (extracted in P1) and `test/clio-exporter.sh`.

This phase is **read-only by construction**. It adds no write paths. Everything here must be
safe to run against the live note at any time.

## Task

### 1. Classify every source entry

For each entry in the raw JSONL, assign exactly one state by cross-referencing the manifest
and the current target:

| State | Meaning |
|---|---|
| `delivered-present` | in manifest, `clio:id` found in target — healthy |
| `delivered-missing` | in manifest, `clio:id` NOT in target — **loss detected** |
| `never-delivered` | not in manifest, not in target — normal backlog, cursor will handle |
| `legacy-unlabelled` | not in manifest, but a matching entry appears to exist in the target without a `clio:id` — pre-ID history |

`legacy-unlabelled` is the live-note majority (~330 entries) and is what makes naive repair
dangerous. Detect it heuristically here — match on timestamp + machine + prompt body — and
report it. **Do not** attempt to fix it; that is P3's backfill, deliberately sequenced after.

### 2. Add a `--status` mode

Non-mutating. Reports:

- source count (JSONL lines), manifest count, target rendered-ID count, cursor value
- a count per classification state above
- the specific missing `clio:id`s (capped, with an honest `… and N more` when truncated —
  never silently truncate)
- **marker displacement**: whether `<!-- CLIO:ENTRIES -->` is at the top of the file, and if not,
  its line number and how many lines sit above it
- **target replacement**: manifest count > 0 but target rendered-ID count is 0 or has dropped
  since the last run

Output must be greppable, one fact per line, in the style of the existing
`reconciled <basename>: merged=<n> quarantined=<path>` log lines.

### 3. Wire detection into the scheduled run

- On a normal (non-`--status`) run, perform the same reconciliation **after** the export step.
- If any entry is `delivered-missing`, or target replacement is detected, **exit non-zero** with
  a clear message naming `--status` as the next step.
- A non-zero exit here must NOT prevent the export itself from having completed, and must not
  roll back the cursor — detection reports, it does not repair.
- The launchd job surfaces this via its existing `StandardErrorPath`, so a loss becomes visible
  in `~/.claude/prompt-log-to-md.err.log` rather than staying silent.

## Constraints

- **No write paths whatsoever** in `--status`. It must be safe against the live note.
- Pure `bash` + `jq`/`grep`/`sed`/`awk`; bash 3.2 compatible.
- Detection must be cheap enough to run every 60s (the live launchd cadence) on a
  ~4300-line note and a ~165-line JSONL. Avoid per-entry subprocess spawning.
- Never treat `PROMPT_LOG_EXCLUDE`-filtered prompts as missing — excluded entries are
  intentionally absent from the target and must classify as excluded, not as loss.

## Acceptance (QA gate — all must hold)

- [ ] `--status` against a healthy fixture reports zero missing and exits 0.
- [ ] Deleting one rendered entry from the target is detected as `delivered-missing` on the next
      run, which exits non-zero.
- [ ] Replacing the target wholesale is detected as target replacement, not as 300 individual losses.
- [ ] A marker-displaced fixture reports the marker's line number and the count of lines above it.
- [ ] A legacy un-ID'd fixture classifies those entries as `legacy-unlabelled`, NOT as
      `never-delivered` — misclassifying them here is what would cause P3 to duplicate them.
- [ ] `PROMPT_LOG_EXCLUDE`-matching prompts are never reported as missing.
- [ ] `--status` writes nothing: fixture note, manifest, and state file are byte-identical before
      and after (assert this explicitly in the harness).
- [ ] Suite green under `/bin/bash` 3.2; `utils/pdda/pdda.sh run` clean.

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-GH156-P2-DETECT-TURN --agent codex --paths "phases/gh-156-clio-projection--gh156-p2-detect/RELAY.md,utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-GH156-P2-DETECT-TURN --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH156-P2-DETECT-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/gh-156-clio-projection--gh156-p2-detect/RELAY.md and utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH156-P2-DETECT-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-GH156-P2-DETECT-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh-156-clio-projection--gh156-p2-detect/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 1 · Builder · codex

Implemented P2 in `utils/CLIO/prompt-log-to-md.sh` and extended `test/clio-exporter.sh`.

- Added a read-only `--status` reconciliation pass before any export setup: source/manifest/target/cursor facts, state counts, capped missing IDs, marker displacement, and target-count baseline/replacement reporting.
- Classifies excluded prompts separately so intentional filtering cannot become a loss signal; legacy detection requires timestamp, machine, and rendered prompt content without an ID.
- Normal export now always runs post-export detection, snapshots the rendered-ID count for the next run, and exits non-zero only after preserving the completed export and cursor when loss/replacement is found.
- Added fixtures for status immutability, legacy/unlabelled and excluded classification, marker displacement, one-entry loss, and wholesale replacement. Verified with `/bin/bash test/clio-exporter.sh` (`bash` and `/bin/bash` PASS).
