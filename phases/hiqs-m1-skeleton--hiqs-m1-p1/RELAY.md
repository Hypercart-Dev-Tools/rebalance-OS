# Marathon Phase hiqs-m1-p1
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M1-P1-TURN builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

---
title: "M1 p1 — subtree scaffold + the frozen plugin contract"
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
# M1 p1 — Subtree scaffold + the plugin contract

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Fire M1 (`--builder codex`). This phase runs first — nothing depends on prior output. |

**Canonical spec:** `PROJECT/2-WORKING/HIQS-PROJECT.md` §5 (the plugin surface), §11 (tree, deps).
Read §5 in full before writing. The dataclasses there are **verbatim contract** — reproduce their
field names, order, and defaults exactly. If you think one is wrong, say so in the relay; do not
"improve" it. Six later phases cite these shapes.

## Build

1. `HiQS/pyproject.toml` — package `hiqs`, own project (not a subpackage of anything in this repo),
   entry-point group `hiqs.sources`, deps exactly the 4 top-level ones from §11
   (`mcp`, `sentence-transformers`, `google-auth-oauthlib`, `keyring`) plus `pytest` as a dev extra.
2. `HiQS/hiqs/__init__.py` — version only.
3. `HiQS/hiqs/plugins.py` — `Source`, `SyncReport`, `Doc`, `Candidate`, all `@dataclass(frozen=True)`,
   exactly as §5 defines them, **including** `Doc.source`, `Doc.author`, and
   `Candidate.author/owed_by/due`. Plus the entry-point discovery walk (~10 lines, stdlib
   `importlib.metadata`).
4. `HiQS/tests/conftest.py` — puts `HiQS/` on `sys.path` so the suite runs before an editable install.
5. `HiQS/tests/test_plugins.py`.
6. `HiQS/.gitignore` — at minimum `.venv/`, `__pycache__/`, `*.egg-info/`. The venv lives **inside**
   the subtree (`HiQS/.venv`), never the repo root's: §19.1 forbids anything HiQS needs living above
   `HiQS/`, and the incumbent's venv carries an mlx/transformers stack that seven live launchd jobs
   depend on. The operator creates the venv as a pre-step; do not create or mutate it in this turn.

## Acceptance

- Every dataclass is frozen; field names/order/defaults match §5 character for character.
- `SyncReport.counts` documents the six keys: inserted, updated, unchanged, skipped, rejected,
  **pruned** (§5 rule 2 — `pruned` is not optional, the reconciliation contract needs it).
- Discovery returns `[]` on a clean environment without raising.
- A test asserts each dataclass rejects mutation.
- `HiQS/.venv/bin/python -m pytest HiQS/tests -q` passes.

## Do not

- Do not add fields, helpers, or a base class "for later". §11 has a 3,000 LOC budget and §14 is
  where deferred things live.
- Do not import anything from `src/rebalance/**`. The clean-room boundary is the whole design.
- Do not write `db.py`, `events.py`, or any source plugin — those are p2, p4, and M2.


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/pyproject.toml,HiQS/hiqs/__init__.py,HiQS/hiqs/plugins.py,HiQS/tests/conftest.py,HiQS/tests/test_plugins.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M1-P1-TURN --agent codex --paths "phases/hiqs-m1-skeleton--hiqs-m1-p1/RELAY.md,HiQS/pyproject.toml,HiQS/hiqs/__init__.py,HiQS/hiqs/plugins.py,HiQS/tests/conftest.py,HiQS/tests/test_plugins.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M1-P1-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P1-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m1-skeleton--hiqs-m1-p1/RELAY.md and HiQS/pyproject.toml,HiQS/hiqs/__init__.py,HiQS/hiqs/plugins.py,HiQS/tests/conftest.py,HiQS/tests/test_plugins.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/pyproject.toml,HiQS/hiqs/__init__.py,HiQS/hiqs/plugins.py,HiQS/tests/conftest.py,HiQS/tests/test_plugins.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P1-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M1-P1-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m1-skeleton--hiqs-m1-p1/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
