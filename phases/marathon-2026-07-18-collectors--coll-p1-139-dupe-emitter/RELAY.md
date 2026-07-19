# Marathon Phase coll-p1-139-dupe-emitter
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-COLL-P1-139-DUPE-EMITTER-TURN-3 builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

# Phase 1 — delete the duplicate pulse-collector check emitter

Part of **GH-139**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/139
Wave 1, runs concurrently with p2 and p3. **Artifact: `scripts/health_issue_reporter.py` only.**

## The bug (verified, not assumed)

Two live code paths emit the *same* health check under names differing by one character:

| Emitter | Name | Issues it filed |
|---|---|---|
| `scripts/health_issue_reporter.py:377` | `pulse-collector:{device}` (hyphen) | #46, #47, #48 |
| `src/rebalance/doctor.py:761` | `pulse collector:{device}` (space) | #83, #84, #85 |

The reporter carries its own parallel implementation, `run_pulse_checks()`. It shells out to
git-pulse's health-check script and **screen-scrapes fixed-width columns from its stdout**
(`health_issue_reporter.py:360-382` — `line[:36]`, `line[38:56]`, `line[60:]`), then builds
check dicts with the hyphenated name.

The reporter dedupes open issues by title, so the two names never reconcile. Six issues exist
for three machines. #46/#47/#48 last updated 2026-06-01 and can never close.

This duplication is already tracked: `PROJECT/4-MISC/CLAUDE-REFACTOR.md` ~L255 —
*"repoint `experimental/git-pulse/health-check.py` and `health_issue_reporter.py` at
`pulse_health` to delete the duplicates."*

## ⛔ Hard invariants

- **Do not edit `src/rebalance/doctor.py`.** It holds the canonical emitter and is the
  artifact of phases 3 and 4 running concurrently. Touching it will collide.
- **doctor's name wins.** `pulse collector:` (space) is canonical because doctor consumes the
  real `pulse_health` module. Do not "fix" the drift by changing doctor to match the reporter.
- **Do not close or edit GitHub issues from this phase.** Reconciling #46/#47/#48 is an
  operator decision (the issue's acceptance list flags that a bare close loses history).
  Ship the code; leave the six issues alone.
- **No new abstraction.** This phase is a deletion plus a consumption change. If it grows a
  new module or a name-mapping layer, it has gone wrong — Principle 6, *deleting code counts
  as progress*.
- **Not in this phase:** the registry-level stable check id (option 2, decided on the issue).
  That guards against the *next* drift and edits doctor's check emission — it is sequenced
  after phase 4.

## Task

Delete `run_pulse_checks()`'s parallel implementation and have the reporter consume doctor's
canonical `pulse collector:*` checks instead.

Concretely:

1. Remove the fixed-width stdout parsing at `health_issue_reporter.py:360-382` and the
   `pulse-collector:` name construction at `:377`.
2. Route the reporter's pulse checks through the same path doctor uses (`pulse_health`), so
   there is exactly one producer of these check dicts.
3. Verify the reporter still emits the same check *shape* it did before — `name`, `status`,
   `detail`, `hint`, `source` — since `file_issue()` and the dedupe path consume those keys.
4. Confirm no other caller depended on the hyphenated name. Grep the tree, including
   `src/rebalance/cli/config_cmds.py:518` (check-name substring demotion) and any
   suppression/notice pattern lists — a suppression rule written against `pulse-collector:`
   would silently stop matching.

## Watch for

- **Suppression / demotion patterns.** `config_cmds.py` demotes checks by name substring. If a
  stored pattern targets the hyphenated form, this change silently un-suppresses a check. Check
  the stored config, don't just grep source.
- **`experimental/git-pulse/health-check.py`** is named in the refactor note as a third
  consumer. It is **out of scope** for this phase — but if the reporter's only route to pulse
  data is through that script, say so in the relay rather than expanding scope silently.

## Acceptance

- [ ] Exactly one code path emits `pulse collector:*` checks; the hyphenated form appears
      nowhere in `src/` or `scripts/` (grep proves it).
- [ ] `scripts/health_issue_reporter.py` no longer parses fixed-width columns from another
      script's stdout.
- [ ] The reporter's emitted check dicts keep the same keys and semantics; dedupe and filing
      behavior is unchanged for the checks that remain.
- [ ] No suppression/demotion rule silently changed meaning — verified against stored config,
      and stated explicitly in the relay.
- [ ] `src/rebalance/doctor.py` is **unmodified** (`git diff --stat` proves it).
- [ ] Gate: `.venv/bin/python -m pytest tests/test_health_issue_reporter.py -q` green.
- [ ] A dry-run (`--dry-run`) shows the reporter would file/close the same set of checks it
      does today, minus the duplicates.

## Debug mantra (auto-triggered — 2 prior attempt(s) on this phase did not reach Approved)

Before trying again, read /Users/noelsaw/Documents/rebalance-OS/.xyz/relay-automation/DEBUG-MANTRA.md and follow its four-step discipline: reproduce reliably, know the fail path, question the hypothesis, treat this round as a breadcrumb for the next one.
Last recorded reason (/Users/noelsaw/Documents/rebalance-OS/phases/marathon-2026-07-18-collectors--coll-p1-139-dupe-emitter/ESCALATION.md): `turn-timeout-or-hang`. Read it before re-guessing.
---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): scripts/health_issue_reporter.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-COLL-P1-139-DUPE-EMITTER-TURN-3 --agent codex --paths "phases/marathon-2026-07-18-collectors--coll-p1-139-dupe-emitter/RELAY.md,scripts/health_issue_reporter.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-COLL-P1-139-DUPE-EMITTER-TURN-3 --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-COLL-P1-139-DUPE-EMITTER-TURN-3 --agent codex --to agy
4. Edit ONLY these paths: phases/marathon-2026-07-18-collectors--coll-p1-139-dupe-emitter/RELAY.md and scripts/health_issue_reporter.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: scripts/health_issue_reporter.py.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-COLL-P1-139-DUPE-EMITTER-TURN-3 --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-COLL-P1-139-DUPE-EMITTER-TURN-3 --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/marathon-2026-07-18-collectors--coll-p1-139-dupe-emitter/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 3 · Builder · codex

- Removed `run_pulse_checks()` and its subprocess/fixed-width stdout parser from `scripts/health_issue_reporter.py`. The reporter now consumes the structured `pulse collector:*` checks that `run_doctor_checks()` already obtains from doctor's canonical `pulse_health` path.
- Retained `--also-pulse` only as an explicit deprecated compatibility no-op, so existing scheduled invocations continue to work without adding a second check. All emitted doctor dictionaries retain `name`, `status`, `detail`, `hint`, and `source`.
- Verified: `python3 -m pytest tests/test_health_issue_reporter.py -q` → 47 passed, 10 skipped. A direct structured-check assertion found 27 doctor checks, including 3 canonical pulse checks, with the required shape and `rebalance-doctor` source. `rg` finds no `pulse-collector:` in `src/` or `scripts/`; the stored `temp` configuration has no pulse collector suppression/demotion pattern, while the CLI documentation uses the canonical space form.
- Dry-run breadcrumb: `python3 scripts/health_issue_reporter.py --dry-run --also-pulse` reached doctor, reported the flag redundant, and collected 27 checks; it then failed at the pre-existing GitHub label GET because this sandbox has no DNS/network access. It made no GitHub action and did not reach logging. This confirms the duplicate collection is absent before the network boundary.
