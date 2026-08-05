# Marathon Phase hiqs-m1-p3
STATUS: Approved
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M1-P3-TURN builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

---
title: "M1 p3 — config.py: one JSON config and the secret chain"
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
# M1 p3 — config.py: one JSON config and the secret chain

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m1-p1` is approved. |

**Canonical spec:** `HIQS-PROJECT.md` §5 rule 3, §11, L16 (a whitelist that silently drops keys).

## Build

`HiQS/hiqs/config.py`:
- One JSON config at the canonical config path (§13). Read it whole.
- `secret(name)` resolving **keyring → 0600 file outside the repo → env**, in that order, first hit
  wins. Return `None` when nothing resolves — never `""`, which reads as "configured but empty".
- Unknown keys in the config file are **reported through `status`, not discarded** (L16 — a
  whitelist that silently no-ops a setting is a cluster-A failure wearing a config file).

## Acceptance

- Each rung of the chain is tested in isolation and in precedence order.
- A config carrying an unrecognised key surfaces it; a test asserts it is not silently dropped.
- A missing config file yields documented defaults, not a crash.
- A `0600` check on the file rung: a secret file with looser permissions is refused, loudly.
- No absolute user path anywhere in the module (L11).

## Do not

- Do not log, echo, or include a resolved secret in any return value, error message, or event
  payload.
- Do not create the config file or write to keyring — this phase reads. `hiqs auth` (p5, then M4)
  is the only writer.


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/config.py,HiQS/tests/test_config.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M1-P3-TURN --agent codex --paths "phases/hiqs-m1-skeleton--hiqs-m1-p3/RELAY.md,HiQS/hiqs/config.py,HiQS/tests/test_config.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M1-P3-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P3-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m1-skeleton--hiqs-m1-p3/RELAY.md and HiQS/hiqs/config.py,HiQS/tests/test_config.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/config.py,HiQS/tests/test_config.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P3-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M1-P3-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m1-skeleton--hiqs-m1-p3/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

### Round 1 · Builder · codex

Implemented `HiQS/hiqs/config.py` and `HiQS/tests/test_config.py`. The read-only API loads the complete JSON config from the canonical path (missing file returns explicit defaults), preserves and reports unknown keys through safe status metadata, and resolves secrets keyring → exact-`0600` JSON secret file → environment. Secret values are never included in errors or status. Focused tests cover defaults, unknown-key visibility, each resolution rung and their precedence, empty values, and unsafe file permissions.

### Round 1 · Reviewer · agy

swept file: yes

Reviewed `HiQS/hiqs/config.py` and `HiQS/tests/test_config.py` in full.
- Canonical path resolution (`~/.config/hiqs/config.json`) with safe missing-file defaults and explicit malformed JSON errors.
- Unknown top-level keys preserved in config dictionary and surfaced via `status` with state `"warn"`.
- Secret resolution chain (`keyring` → `0600` file → environment) correctly enforced in precedence order with empty string / missing value handling returning `None`.
- 0600 file mode check properly enforced and raises `SecretFilePermissionError`.
- No secret values exposed in status outputs, return structures, or error messages.
- Full test suite in `HiQS/tests/test_config.py` verified and passing cleanly.

**Verdict:** Approved

relay closed, no further turn needed

