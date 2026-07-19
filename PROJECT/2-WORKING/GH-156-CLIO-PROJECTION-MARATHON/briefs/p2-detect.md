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
