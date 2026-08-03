# Marathon Phase hiqs-m4-p1
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M4-P1-TURN builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

---
title: "M4 p1 — calendar.py: read-only OAuth client"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M4 p1 — calendar.py: read-only OAuth client

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after M3 is approved. Fire M4 with `--builder agy`. |

**Canonical spec:** `HIQS-PROJECT.md` §5 (rules 3/7/8), §9 (`calendar_events` columns), Decision 6
(read-only everywhere in v1), §11 (~180 LOC).

## Build

`HiQS/hiqs/sources/calendar.py` — Google Calendar, **read-only scope**, window upsert
(§5 rule 2, pattern 2). Project `id, summary, start, end, project, organizer, attendees_json`.

Token handling goes through `config.secret()` and keyring. The **interactive consent flow belongs
to `hiqs auth calendar`** (M4 scope, wired in p1's CLI stub) — this module consumes a token, it
does not obtain one interactively.

## Acceptance

- **Read-only, enforced structurally:** a test asserts no write method is reachable from
  `HiQS/**` (Decision 6). Scope strings are read-only.
- `sync.failed` on an expired token carries a non-empty `error_type` from the closed vocabulary
  (`auth_expired`|`network`|`rate_limit`|`parse`) **and** a non-empty `message`, and leaves
  `status` reporting `error` for that source — never a silent empty result rendered green
  (L6, L8, Phase 3 gate).
- The `auth_expired` path's remediation text names `hiqs auth calendar`. A failure whose only
  remedy is improvisation is not specced.
- Explicit timeout on every call (rule 7); watermark on success only (rule 8).
- Day boundaries pinned to device-local tz at query time; storage UTC ISO-8601 (§9).
- Fully offline tests — OAuth and the API are stubbed.

## Do not

- Do not create, modify, or delete a calendar event. Not behind a flag, not in a test helper.
- Do not attempt an interactive browser flow inside `fetch` — the runner is an unattended launchd
  job that cannot complete one (Decision 4).


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/sources/calendar.py,HiQS/tests/test_calendar.py,HiQS/pyproject.toml
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M4-P1-TURN --agent agy --paths "phases/hiqs-m4-ask-mcp--hiqs-m4-p1/RELAY.md,HiQS/hiqs/sources/calendar.py,HiQS/tests/test_calendar.py,HiQS/pyproject.toml"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M4-P1-TURN --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M4-P1-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m4-ask-mcp--hiqs-m4-p1/RELAY.md and HiQS/hiqs/sources/calendar.py,HiQS/tests/test_calendar.py,HiQS/pyproject.toml. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/sources/calendar.py,HiQS/tests/test_calendar.py,HiQS/pyproject.toml. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M4-P1-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M4-P1-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m4-ask-mcp--hiqs-m4-p1/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
