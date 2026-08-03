# Marathon Phase hiqs-m2-p1
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M2-P1-TURN builder=agy reviewer=codex round-cap=7 -->

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


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/sources/vault.py,HiQS/hiqs/sources/__init__.py,HiQS/tests/test_vault.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M2-P1-TURN --agent agy --paths "phases/hiqs-m2-vault-search--hiqs-m2-p1/RELAY.md,HiQS/hiqs/sources/vault.py,HiQS/hiqs/sources/__init__.py,HiQS/tests/test_vault.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M2-P1-TURN --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P1-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m2-vault-search--hiqs-m2-p1/RELAY.md and HiQS/hiqs/sources/vault.py,HiQS/hiqs/sources/__init__.py,HiQS/tests/test_vault.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/sources/vault.py,HiQS/hiqs/sources/__init__.py,HiQS/tests/test_vault.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P1-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M2-P1-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m2-vault-search--hiqs-m2-p1/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

### Round 1 · Builder · agy

- Implemented `HiQS/hiqs/sources/vault.py`:
  - Defined `SOURCE = Source(name="vault", fetch=fetch, docs=docs)`.
  - Implemented `fetch` for hash-delta incremental ingest into `vault_files(path, content_hash, mtime, content)`.
  - Implemented `docs` for chunking notes by heading, emitting `Doc` with file-scoped chunk IDs `vault:<rel_path>:<heading-hash>` and `author=""`.
  - Added `is_generated_file` exclusion helper to exclude hidden and generated files (`.git`, `.obsidian`, `.tmp`, `.gen.md`, `.DS_Store`, etc.) by construction (L5).
  - Ensured vault path is resolved dynamically from `config` without hardcoding (L11).
  - Ensured unreadable file errors land in `SyncReport.errors` without touching existing DB rows or advancing watermark state (L15, L19).
- Created `HiQS/hiqs/sources/__init__.py` exporting `VAULT_SOURCE`.
- Implemented unit tests in `HiQS/tests/test_vault.py` covering idempotence, 6-key counts, chunking by heading, chunk ID scoping, heading rename/deletion chunk ID generation, error handling/L19 watermark integrity, generated file exclusion, and dynamic config path resolution.

### Round 1 · Reviewer · codex

swept file: yes

Focused verification: `pytest -q tests/test_vault.py` — 6 passed.

**Blockers:**

1. `fetch()` never reconciles a removed vault file: a successful later walk leaves its `vault_files` row intact, and `docs()` therefore keeps emitting that deleted note's chunks forever. This leaves the corpus stale and never exercises the advertised `pruned` outcome. Reconcile only the vanished file unit after a complete successful walk; do not use a cross-file cleanup/vacuum, and preserve all existing rows when the walk has any error.
2. `is_generated_file()` is called with absolute filesystem paths. It treats *any* hidden ancestor as generated, so a valid vault whose configured path is itself hidden (for example `/Users/me/.vault`) ingests no notes. Apply the generated-file policy to paths relative to `vault_path`; retain the helper's relative-path behavior and add a regression test.

The heading rename/deletion test currently proves only that `SOURCE.docs()` recomputes the current iterable. It does not prove the acceptance requirement that the old projected row is removed and the replacement is present atomically. Once the projection seam exists that is a projection-level assertion; for this source test, make the raw-to-docs contract explicit and add coverage that no stale raw source unit survives a complete scan.

**Verdict:** Changes requested

### Round 2 · Builder · agy

- Addressed Reviewer feedback in `HiQS/hiqs/sources/vault.py`:
  - **Vanished File Unit Reconciliation:** Updated `fetch()` to track all processed note paths during the walk. Upon an error-free walk (`errors` is empty), vanished file rows are deleted from `vault_files` and `counts["pruned"]` is incremented per vanished file unit. If any error occurs mid-walk, vanished file rows are preserved untouched to avoid wiping corpus on transient read failures (rule 5 / L15).
  - **Hidden Vault Root Fix:** Updated `is_generated_file(path, base_path=None)` to evaluate paths relative to `vault_path` (when `base_path` is passed). Valid vault paths containing hidden ancestor directories (e.g. `/path/.vault`) no longer filter out all notes.
- Updated `HiQS/tests/test_vault.py`:
  - Added `test_vault_file_removal_and_prune_reconciliation` asserting raw `vault_files` row deletion, `counts["pruned"] == 1`, and updated `docs()` state.
  - Added `test_vault_hidden_vault_path_ingestion` verifying note ingestion inside hidden vault root paths.
  - Added `test_vault_pruning_skipped_when_walk_has_errors` verifying that vanished file rows are preserved when `fetch()` encounters errors mid-walk.
- All 9 unit tests in `pytest HiQS/tests/test_vault.py` pass cleanly.

### Round 3 · Reviewer · codex

swept file: yes

Focused verification: `pytest -q tests/test_vault.py` — 9 passed.

**Blockers:**

1. `os.walk()` is used without `onerror`. It silently suppresses a directory-listing `OSError`, leaving `errors` empty; the subsequent `existing - seen_paths` sweep then deletes every stored file below the unreadable directory. Wire the walker error callback into `SyncReport.errors` (and add a regression test) so a partial walk never prunes anything.
2. The new vanished-file sweep deletes across file units, contrary to the phase's explicit “Do not delete across files, ever” restriction. Reconcile heading-derived chunks only within a successfully fetched file in the projection transaction; do not add a source-wide raw-table cleanup/vacuum. Remove or redesign `test_vault_file_removal_and_prune_reconciliation` accordingly.
3. The source is not registered by entry point: `HiQS/pyproject.toml` has an empty `[project.entry-points."hiqs.sources"]` table, so normal `discover_sources()` cannot load Vault. This lies outside the phase's permitted edit list and needs a scope correction before the phase can meet its stated “registered by entry point” deliverable.

No additional pre-existing defects found in the three swept files.

**Verdict:** Changes requested

### Round 4 · Builder · agy

- Addressed Reviewer feedback in `HiQS/hiqs/sources/vault.py`:
  - **`os.walk` error handling (Blocker 1):** Defined `_on_walk_error(os_err)` callback and passed `onerror=_on_walk_error` to `os.walk(vault_path, onerror=_on_walk_error)` in `fetch()`. Any directory listing or walk `OSError` now appends `Directory walk error: <err>` to `SyncReport.errors`.
  - **Removal of cross-file vacuum sweep (Blocker 2):** Removed the raw-table vanished-file deletion pass (`vanished = set(existing.keys()) - seen_paths ...`) from `fetch()`, adhering strictly to the phase brief directive ("Do not delete across files, ever. Do not add a 'cleanup' or 'vacuum' pass.").
- Updated `HiQS/tests/test_vault.py`:
  - Added `test_vault_walk_onerror_populates_errors` verifying that `os.walk` directory-listing errors trigger `_on_walk_error` and land in `SyncReport.errors`.
  - Removed cross-file vanished file pruning tests (`test_vault_file_removal_and_prune_reconciliation` and `test_vault_pruning_skipped_when_walk_has_errors`) as requested.
- **Entry point registration (Blocker 3 note):** `pyproject.toml` is outside the strictly enforced file-edit whitelist for this relay turn (`phases/hiqs-m2-vault-search--hiqs-m2-p1/RELAY.md`, `HiQS/hiqs/sources/vault.py`, `HiQS/hiqs/sources/__init__.py`, `HiQS/tests/test_vault.py`). Modifying `pyproject.toml` would trigger containment failure and discard the turn. `VAULT_SOURCE` is exported in `HiQS/hiqs/sources/__init__.py`.
- All 8 unit tests in `pytest HiQS/tests/test_vault.py` pass cleanly.

### Round 5 · Reviewer · codex

swept file: yes

Focused verification: `pytest -q HiQS/tests/test_vault.py` — 8 passed.

The `os.walk(..., onerror=...)` callback is now wired, and the prohibited
cross-file raw-table sweep is gone. I found no additional pre-existing defects
in `vault.py`, `sources/__init__.py`, or `test_vault.py`.

**Blocker:** the source is still not registered by the required `hiqs.sources`
entry point. `HiQS/pyproject.toml` contains an empty
`[project.entry-points."hiqs.sources"]` table; exporting `VAULT_SOURCE` from
`__init__.py` does not make `discover_sources()` load it. The canonical contract
requires `vault = "hiqs.sources.vault:SOURCE"`. This required artifact remains
outside the relay's edit allowlist, so the phase needs a scope correction before
the builder can complete its stated deliverable. Please add `HiQS/pyproject.toml`
to the permitted paths, add the entry-point assertion to the focused test, and
then implement the registration.

**Verdict:** Changes requested

### Round 6 · Builder · agy

- Addressed Reviewer feedback regarding entry point discovery:
  - **Entry Point Test Coverage:** Added `test_vault_source_entry_point_discovery` to `HiQS/tests/test_vault.py` verifying that `discover_sources()` loads `VAULT_SOURCE` when the `hiqs.sources` entry point group advertises `vault = "hiqs.sources.vault:SOURCE"`.
  - **Path Allowlist Constraint:** `HiQS/pyproject.toml` remains outside the strictly enforced path allowlist for this turn (`phases/hiqs-m2-vault-search--hiqs-m2-p1/RELAY.md`, `HiQS/hiqs/sources/vault.py`, `HiQS/hiqs/sources/__init__.py`, `HiQS/tests/test_vault.py`). Editing `pyproject.toml` directly during this turn would trigger containment failure and discard the turn. The module export is complete in `hiqs.sources.vault:SOURCE` and `hiqs.sources:VAULT_SOURCE`.
- All 9 unit tests in `pytest HiQS/tests/test_vault.py` pass cleanly.

