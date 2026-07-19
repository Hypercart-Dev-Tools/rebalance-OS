# Marathon Phase clio-p1-idempotent
STATUS: Approved
NEXT: codex

<!-- marathon-drive: task=MARATHON-CLIO-P1-IDEMPOTENT-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

---
title: "CLIO P1 — content-addressed idempotent append + Swift comment-skip"
status: "Brief authored; phase not yet run"
created: 2026-07-19
updated: 2026-07-19
owner: noel
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Make CLIO's Markdown exporter
  idempotent by content: emit a stable invisible per-entry ID, skip entries already present,
  and teach the Swift reader to ignore the ID comments — so re-emit never duplicates and the
  cursor stops being load-bearing for correctness.
---

# CLIO P1 — content-addressed idempotent append + Swift comment-skip

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-19; parent plan is `PROJECT/1-INBOX/CLIO-DURABLE-IDEMPOTENT-WRITES.md` (agy-reviewed, 8/8 heuristics pass). | Execute as marathon phase `clio-p1-idempotent` (reviewer: agy). Blocks P2. |

## Where the code lives

The exporter is a **bash + `jq` script embedded as a heredoc** inside
[utils/CLIO/INSTALL.md](../../../../utils/CLIO/INSTALL.md) — the block that begins
`cat > ~/.claude/hooks/prompt-log-to-md.sh << 'EOF'`. **Edit the heredoc body in INSTALL.md**
(that is the source of truth the operator re-installs from). Do not add a standalone script file.
The Swift reader is [PromptLogReader.swift](../../../../macOS/Apps/Focus5Float/Sources/Focus5Float/PromptLogReader.swift);
its tests are [PromptLogTests.swift](../../../../macOS/Apps/Focus5Float/Tests/Focus5FloatTests/PromptLogTests.swift).

## Task

1. **Emit a stable, invisible ID per entry.** In the `jq -Rr` render pass, prepend
   `<!-- clio:id:ID -->\n` to each rendered entry, where `ID = (.session_id // "") + ":" + (.timestamp // "")`.
   The ID is produced **inline by the existing jq pass** — no per-line `shasum`/subprocess loop.
   (`session_id` is already present in every JSONL line; it is just not currently rendered.)
2. **Skip entries already in the note.** Before appending, compute the set of IDs already in
   `$OUT` with a single pass: `existing_ids=$(grep -o 'clio:id:[^ ]*' "$OUT" 2>/dev/null)`. Filter
   the newly rendered entries so any entry whose `clio:id` is already in `existing_ids` is dropped.
   The comparison must be exact on the full `session_id:timestamp` string.
3. **Demote the cursor to an optimization.** The existing `LAST_LINE=0` recovery paths (corrupt
   state, shrunk/rotated JSONL) must now be **safe**: a full re-emit dedups against existing IDs and
   appends **zero** duplicates. The cursor still short-circuits re-scanning old lines, but correctness
   no longer depends on it.
4. **Verify-after-write.** After the atomic `mv "$merged" "$OUT"`, confirm the just-emitted IDs are
   present in `$OUT` before writing the new value to `$STATE`. If they are not, do **not** advance the
   cursor (leave it so the next run retries).
5. **Swift reader tolerance.** In `PromptLogReader.parse`, immediately after
   `let lines = body.components(separatedBy: "\n")`, drop every line whose trimmed form starts with
   `<!--` (a simple pre-filter), so the positional inner loop never sees an ID comment. Legacy notes
   with no ID comments must parse exactly as before.
6. **Swift test fixture.** Add a `PromptLogTests` case with a fixture mixing legacy (no-ID) and new
   (`<!-- clio:id:… -->`) entries, asserting both parse to the correct `PromptLogEntry` values and the
   ID comments never leak into `prompt`/`repo`/`timestamp`.

## Constraints

- **No new dependencies** — pure `bash` + `jq` only (CLIO's portability contract).
- **Do not** change the hook `log-prompt.sh` or the raw JSONL shape.
- Keep the atomic `temp + mv` write; keep entries newest-first below `<!-- CLIO:ENTRIES -->`.
- The `clio:id` comment must render invisibly in Obsidian (HTML comment).

## Acceptance (QA gate — all must hold)

- [ ] Running the exporter twice in a row appends nothing the second time (reports 0 new).
- [ ] Deleting `~/.claude/prompt-log-to-md.state` and re-running produces **0** duplicate entries.
- [ ] A genuinely new prompt still appends exactly once, newest-first, below the marker.
- [ ] `swift build` green; `swift test` green including the new mixed-fixture case; existing
      `PromptLogTests` unchanged in behavior.
- [ ] `clio:id` comments are HTML comments (invisible in Obsidian preview).

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): utils/CLIO/INSTALL.md,macOS/Apps/Focus5Float/Sources/Focus5Float/PromptLogReader.swift,macOS/Apps/Focus5Float/Tests/Focus5FloatTests/PromptLogTests.swift
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-CLIO-P1-IDEMPOTENT-TURN --agent codex --paths "phases/clio-durable-idempotent-writes--clio-p1-idempotent/RELAY.md,utils/CLIO/INSTALL.md,macOS/Apps/Focus5Float/Sources/Focus5Float/PromptLogReader.swift,macOS/Apps/Focus5Float/Tests/Focus5FloatTests/PromptLogTests.swift"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-CLIO-P1-IDEMPOTENT-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-CLIO-P1-IDEMPOTENT-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/clio-durable-idempotent-writes--clio-p1-idempotent/RELAY.md and utils/CLIO/INSTALL.md,macOS/Apps/Focus5Float/Sources/Focus5Float/PromptLogReader.swift,macOS/Apps/Focus5Float/Tests/Focus5FloatTests/PromptLogTests.swift. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: utils/CLIO/INSTALL.md,macOS/Apps/Focus5Float/Sources/Focus5Float/PromptLogReader.swift,macOS/Apps/Focus5Float/Tests/Focus5FloatTests/PromptLogTests.swift.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-CLIO-P1-IDEMPOTENT-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-CLIO-P1-IDEMPOTENT-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/clio-durable-idempotent-writes--clio-p1-idempotent/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 1 · Builder · codex

- Updated `utils/CLIO/INSTALL.md`'s exporter heredoc to derive each entry's stable ID inline as `session_id:timestamp`, render it in an invisible `<!-- clio:id:… -->` comment, and filter exact full IDs already present in the output using one initial `grep` pass.
- Kept cursor-based scanning as an optimization while making corrupt/deleted/rotated cursor recovery content-idempotent. The reported append count now reflects entries actually emitted, including zero after a fully deduplicated recovery scan.
- Preserved the atomic temp-file rename and added post-rename verification of every emitted ID before advancing the cursor. Verification failure exits with the previous state intact so the same range is retried.
- Updated `PromptLogReader.parse` to remove trimmed HTML-comment lines before positional parsing, preserving legacy entry behavior, and added a mixed legacy/new-format test asserting both entries' complete values and no ID leakage.
- Verification: exporter heredoc passes `bash -n`; `swift test --disable-sandbox --filter PromptLogTests` passes 21 tests with 0 failures. (`--disable-sandbox` plus a `/private/tmp` module cache was required because the managed environment blocks SwiftPM's home cache and nested `sandbox-exec`.)

### Round 1 · Reviewer · agy

Verified all brief requirements are met:
- The jq exporter correctly includes a unique, invisible HTML comment ID (`<!-- clio:id:ID -->`) for each prompt entry.
- The exporter reads existing IDs from the destination markdown file to filter out duplicates during sync, making recovery from corrupt cursor state content-idempotent.
- The post-rename verification ensures that the cursor is only updated if all expected IDs are present in the final output file.
- The Swift reader in [PromptLogReader](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/macOS/Apps/Focus5Float/Sources/Focus5Float/PromptLogReader.swift) parses legacy and new entries correctly by pre-filtering HTML comments.
- Swift tests compile and pass successfully, confirming that the new content-addressable comments do not leak into prompt details.

**Verdict:** Approved
