# Marathon Phase hiqs-m1-p5
STATUS: Approved
NEXT: none

<!-- marathon-drive: task=MARATHON-HIQS-M1-P5-TURN builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

---
title: "M1 p5 — __main__.py: the CLI skeleton"
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
# M1 p5 — __main__.py: the CLI skeleton

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m1-p4` is approved; `status` calls its aggregator. |

**Canonical spec:** `HIQS-PROJECT.md` Decision 4 (six subcommands), §10, §11 (~180 LOC).

## Build

`HiQS/hiqs/__main__.py` — argparse (not typer, §11), six subcommands:
`refresh | status | search | ask | serve | auth`.

This phase wires **structure, not behaviour**: `status` is real (it calls p4's aggregator);
the rest parse their arguments, validate them, and raise a clear `NotImplementedError` naming the
phase that fills them in. `status --json` emits machine-readable output for scripts and agents.

`auth` exists from Phase 0 even though Calendar arrives in M4, because Decision 4 records why:
the only runner is an unattended launchd job that **cannot open a browser**, so the interactive
re-authorization path must exist before it is needed, not after.

## Acceptance

- `hiqs --help` lists all six subcommands (this exact check is in the Phase 0 gate).
- `hiqs status` on an empty DB prints valid JSON — the Phase 0 exit criterion.
- `hiqs status --json` output parses and matches §8's shape.
- Unimplemented subcommands fail with a message naming the phase, not a traceback.
- Exit codes: 0 success, non-zero on error. No command exits 0 on a failure it detected.

## Do not

- Do not implement `refresh`, `search`, `ask`, `serve`, or `auth`'s OAuth flow here.
- Do not add subcommands beyond the six. Decision 4 counts them, and §18.3's SMALL invariant means
  a seventh is a recorded decision, not a convenience.


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/__main__.py,HiQS/tests/test_cli.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M1-P5-TURN --agent codex --paths "phases/hiqs-m1-skeleton--hiqs-m1-p5/RELAY.md,HiQS/hiqs/__main__.py,HiQS/tests/test_cli.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M1-P5-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P5-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m1-skeleton--hiqs-m1-p5/RELAY.md and HiQS/hiqs/__main__.py,HiQS/tests/test_cli.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/__main__.py,HiQS/tests/test_cli.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P5-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M1-P5-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m1-skeleton--hiqs-m1-p5/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

### Round 1 · Builder · codex

Implemented `HiQS/hiqs/__main__.py` and `HiQS/tests/test_cli.py`.

- Added the stable argparse skeleton for exactly `refresh`, `status`, `search`, `ask`, `serve`, and `auth`.
- Wired `status` to the Phase 0 `events.status()` aggregator; default output is readable valid JSON and `--json` is compact machine JSON.
- Deferred commands validate their arguments, then exit non-zero with a phase-specific message and no traceback.
- Added focused subprocess tests for help, empty-DB status JSON, deferred-command errors, and bounded option validation.
- Verified with `pytest HiQS/tests/test_cli.py -q` — 9 passed.

### Round 1 · Reviewer · agy

swept file: yes

Reviewed `HiQS/hiqs/__main__.py` and `HiQS/tests/test_cli.py`.
- Evaluated whole-file structure and verified zero pre-existing defects.
- All six subcommands (`refresh`, `status`, `search`, `ask`, `serve`, `auth`) are present in `hiqs --help`.
- `hiqs status` and `hiqs status --json` emit valid JSON matching the §8 shape via `events.status()`.
- Unimplemented subcommands cleanly fail with process exit code 2 and a phase-specific message without traceback.
- Verified test suite passes: `pytest HiQS/tests/test_cli.py -q` (9 passed).

**Verdict:** Approved

