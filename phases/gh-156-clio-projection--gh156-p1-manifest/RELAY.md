# Marathon Phase gh156-p1-manifest
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-GH156-P1-MANIFEST-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

---
title: "GH-156 P1 — extract the exporter to a testable script + fixture harness + manifest receipt"
status: "Brief authored; phase not yet run"
created: 2026-07-19
updated: 2026-07-19
owner: noel
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Give the CLIO exporter a real
  test surface by extracting it out of the INSTALL.md heredoc, then add a source-owned manifest
  of rendered clio:ids so a later run can tell what was ALREADY delivered — the receipt the
  current intra-run verify cannot provide.
---

# GH-156 P1 — testable surface + manifest receipt

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-19; parent doc `PROJECT/1-INBOX/GH-156-CRITICAL-CLIO-PROJECTION-RECONCILIATION.md`. Predecessor marathon (`MARATHON-2026-07-19-CLIO-DURABLE`) already shipped `clio:id` + conflict reconciliation. | Execute as marathon phase `gh156-p1-manifest` (reviewer: agy). P2/P3 depend on this phase's script file and harness. |

## Where the code lives

The exporter is currently a **heredoc inside**
[utils/CLIO/INSTALL.md](../../../../utils/CLIO/INSTALL.md) — the block beginning
`cat > ~/.claude/hooks/prompt-log-to-md.sh << 'EOF'`. It has **no test surface at all**.
That is not incidental: the durable marathon gated on `swift build`, which never executed a
line of this script, and a bash-3.2 empty-array defect consequently reached a live machine
(fixed in `d96439b`). This phase removes that structural blocker before P2/P3 add repair logic.

## Task

### 1. Extract the exporter to a real file

- Move the exporter body verbatim to `utils/CLIO/prompt-log-to-md.sh` (executable).
- Rewrite `INSTALL.md` so the install step **copies from that file** rather than re-embedding
  the source (e.g. `install -m 0755 utils/CLIO/prompt-log-to-md.sh ~/.claude/hooks/`).
- `INSTALL.md` must remain a correct, self-contained install doc for someone reading it top to
  bottom. Keep the prose, the run/verify/uninstall sections, and the launchd section working.
- **Behaviour must not change in this step.** Extraction is a move, not a rewrite.
- Leave the `log-prompt.sh` capture hook alone — out of scope (see parent doc).

### 2. Stand up the fixture harness

Create `test/clio-exporter.sh` — pure bash, no new dependencies, self-contained temp fixtures,
exits non-zero on any failure. It must cover at minimum:

- **fresh note** — empty/absent `$OUT` gets header + `<!-- CLIO:ENTRIES -->` marker, entries land
  below the marker, newest first.
- **legacy un-ID'd note** — a note whose entries carry NO `clio:id` (the pre-ID format). This is
  the live production shape; assert current dedup behaviour explicitly so P3 can change it
  deliberately rather than by accident.
- **marker-displaced note** — marker NOT at the top, with content above it (the live shape:
  marker at line 331 of 4291). Assert content above the marker is preserved byte for byte.
- **conflict sibling** — one unique entry absorbed, sibling quarantined to `.clio-reconciled/`.
- **bash 3.2** — run the suite under `/bin/bash` (macOS system bash, 3.2) as well as the default
  shell. The empty-`conflict_siblings` array case must stay green.
- **idempotency** — running twice in a row emits nothing the second time and leaves `$OUT` byte-identical.

### 3. Add the manifest receipt

- After the existing verify-after-write check passes, record each successfully rendered
  `clio:id` into a source-owned manifest (alongside the state file, e.g.
  `~/.claude/prompt-log-manifest.txt` — one ID per line, append-only).
- The manifest is a **delivery receipt, not a second history store**: it holds IDs only, never
  prompt text. The raw JSONL stays the source of truth.
- It must be **cursor-independent**: deleting the state file must NOT lose the manifest. This is
  the property that makes P2's detection possible.
- Writing the manifest must be atomic and must never abort the run — a manifest failure is
  logged, not fatal.
- Re-emitting an ID already in the manifest must not duplicate the manifest line.

## Constraints

- Pure `bash` + `jq`/`grep`/`sed`/`awk`; no new dependencies.
- macOS system bash **3.2** compatible — no `mapfile`, no associative arrays, no `${arr[@]}`
  bare-expansion under `set -u` (use the `${arr[@]+"${arr[@]}"}` guard already in the file).
- Never touch the raw JSONL, the capture hook, or anything above the marker.
- All writes atomic (temp + `mv` in the same directory).

## Acceptance (QA gate — all must hold)

- [ ] `bash test/clio-exporter.sh` passes, and passes under `/bin/bash` 3.2.
- [ ] The extracted `utils/CLIO/prompt-log-to-md.sh` is byte-equivalent in behaviour to the
      previous heredoc — verified by running both against the same fixture and diffing output.
- [ ] Following `INSTALL.md` top to bottom on a clean machine still yields a working install.
- [ ] A run records every emitted `clio:id` to the manifest; a second run adds nothing.
- [ ] Deleting the state file leaves the manifest intact.
- [ ] A manifest write failure does not abort the export.
- [ ] `utils/pdda/pdda.sh run` clean.

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): utils/CLIO/INSTALL.md,utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-GH156-P1-MANIFEST-TURN --agent codex --paths "phases/gh-156-clio-projection--gh156-p1-manifest/RELAY.md,utils/CLIO/INSTALL.md,utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-GH156-P1-MANIFEST-TURN --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH156-P1-MANIFEST-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/gh-156-clio-projection--gh156-p1-manifest/RELAY.md and utils/CLIO/INSTALL.md,utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: utils/CLIO/INSTALL.md,utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH156-P1-MANIFEST-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-GH156-P1-MANIFEST-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh-156-clio-projection--gh156-p1-manifest/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
