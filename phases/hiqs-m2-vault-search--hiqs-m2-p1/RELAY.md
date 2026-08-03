# Marathon Phase hiqs-m2-p1
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M2-P1-TURN-2 builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

---
title: "M2 p1 — vault.py: walk, hash delta, chunk by heading"
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
# M2 p1 — vault.py: walk, hash delta, chunk by heading

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after M1 is fully approved. Fire M2 with `--builder agy`. |

**Canonical spec:** `HIQS-PROJECT.md` §5 (Source contract, rules 2/7/8), §6.1 (chunking + scoped
ids), §11 (~150 LOC), L5, L15, L19.

## Build

`HiQS/hiqs/sources/vault.py` — a `SOURCE` object registered by entry point, with:
- `fetch` — walk `.md`, hash delta into `vault_files(path, content_hash, mtime)`. Idempotent and
  incremental (§5 rule 2, pattern 1).
- `docs` — chunk by heading, emitting `Doc` with **file-scoped chunk ids**:
  `vault:<rel_path>:<heading-hash>` (§6.1). This id shape is what makes within-unit reconciliation
  a query rather than a guess — it is load-bearing, not cosmetic.

## Acceptance

- Two consecutive runs over an unchanged tree: zero inserts, zero updates. Counts distinguish
  inserted/updated/unchanged/skipped/rejected/pruned.
- **Reconciliation, the M2 headline (§5 rule 2):** rename a heading in a fixture note, re-run, and
  assert the old chunk's row is gone and the new one present — in the same transaction. Then delete
  a heading and assert the same. Orphans that survive here are the corpus-corrupting bug the plan
  was reviewed for; this test is the detector.
- **Never across units, never on failure:** make one file unreadable mid-walk and assert its
  existing rows are untouched, the error lands in `SyncReport.errors`, and the walk continues
  (rule 5). A source returning nothing transiently must not be able to empty the corpus (L15).
- Watermark/mtime state does not advance for a file whose read failed (L19).
- Generated files are excluded from ingest by construction (L5) — v1 writes nothing to the vault,
  so assert the exclusion helper exists and is applied, not that it currently matches anything.
- `Doc.author` is `""` for vault notes (they are the operator's own) — `""`, never a guess.

## Do not

- Do not delete across files, ever. Do not add a "cleanup" or "vacuum" pass.
- Do not resolve the vault path from a hardcoded location — it comes from `config` (L11).


## Debug mantra (auto-triggered — 1 prior attempt(s) on this phase did not reach Approved)

Before trying again, read /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/relay-automation/DEBUG-MANTRA.md and follow its four-step discipline: reproduce reliably, know the fail path, question the hypothesis, treat this round as a breadcrumb for the next one.
Last recorded reason (/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/phases/hiqs-m2-vault-search--hiqs-m2-p1/ESCALATION.md): `cap-or-close-mismatch`. Read it before re-guessing.

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/sources/vault.py,HiQS/hiqs/sources/__init__.py,HiQS/tests/test_vault.py,HiQS/pyproject.toml
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M2-P1-TURN-2 --agent agy --paths "phases/hiqs-m2-vault-search--hiqs-m2-p1/RELAY.md,HiQS/hiqs/sources/vault.py,HiQS/hiqs/sources/__init__.py,HiQS/tests/test_vault.py,HiQS/pyproject.toml"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M2-P1-TURN-2 --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P1-TURN-2 --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m2-vault-search--hiqs-m2-p1/RELAY.md and HiQS/hiqs/sources/vault.py,HiQS/hiqs/sources/__init__.py,HiQS/tests/test_vault.py,HiQS/pyproject.toml. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/sources/vault.py,HiQS/hiqs/sources/__init__.py,HiQS/tests/test_vault.py,HiQS/pyproject.toml. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P1-TURN-2 --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M2-P1-TURN-2 --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m2-vault-search--hiqs-m2-p1/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
