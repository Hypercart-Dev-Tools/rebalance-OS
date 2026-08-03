# Marathon Phase hiqs-m2-p2
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M2-P2-TURN-3 builder=agy reviewer=codex round-cap=11 -->

## Phase Brief

---
title: "M2 p2 — docs_index.py: projection and delta embedding"
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
# M2 p2 — docs_index.py: projection and delta embedding

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m2-p1` is approved. |

**Canonical spec:** `HIQS-PROJECT.md` §6.1, §9 (`docs_vec` PK), §5 rule 2, §3.1 (Decision 1 —
`sentence-transformers`, torch backend), §11 (~130 LOC).

## Build

`HiQS/hiqs/docs_index.py`:
- raw → `docs` projection. **The sole writer to `docs`** (§5 rule 1).
- Delta-only embedding keyed by content hash, writing `docs_vec(doc_id, model, dim, vec)`.
  The **model name is part of the key**, so a model swap re-embeds lazily and two models' vectors
  coexist — that is what makes the Phase 1 comparison free of migration machinery.
- Within-unit reconciliation applied to **both** `docs` and `docs_vec` (§5 rule 2).

### The attestation contract — decided, do not re-derive it

This phase previously stalled twice at the round cap because the contract could not express which
units a run fetched, and the builder tried four workarounds in `docs_index.py` alone: a
`successful_units=` parameter no production caller supplies, duck-typed `source.units()` (impossible
— `Source` is a frozen dataclass), a `sync_successful_units` table probe, and inference from raw
`vault_files` rows. All four are wrong, all four are still in the file, and **all four must be
deleted**. A cross-model consult (codex + agy, `.xyz/relay-system/2026-08-03/hiqs-unit-attestation-150913/`)
independently reached the same conclusion: no fix exists inside `docs_index.py`, because `docs()`
takes only a connection and cannot know what `fetch()` attempted.

§5 rule 2 now specifies the mechanism. Implement exactly it:

1. `SyncReport.units_ok: tuple[str, ...] = ()` — the units this run genuinely fetched.
2. `Doc.unit: str = ""` — unit membership is a **field**. Delete `get_doc_unit()` and every
   id-splitting path with it; a vault path may contain a colon and each source picks its own id
   grammar, so the parse silently returns the wrong unit and prunes the wrong rows.
3. `project_docs(..., reports: Mapping[str, SyncReport] | None = None)` — reconcile **only** within
   `reports[source.name].units_ok`. No attestation ⇒ prune nothing. Never persist and re-read an
   attestation; a stored one outlives the run that earned it.
4. `vault.fetch()` populates `units_ok`, and resolves vanished paths at the raw layer so
   `vault.docs()` stops raising `Tracked file missing from vault` and taking down the whole source.
   A path absent from a **clean** walk is a deletion (attest it; it prunes). A path absent from an
   **errored** walk is unknown (do not attest; nothing prunes).

`HiQS/hiqs/plugins.py` and `HiQS/hiqs/sources/vault.py` are on this phase's allowlist for exactly
this reason. Keep the contract change to those two fields — a `UnitBatch`/`run_id`/four-state design
was considered in the consult and **rejected** as too much machinery for three sources (§18.3 SMALL).

Embedding goes through `SentenceTransformer(...).encode()` and nothing else. Decision 1 is explicit
that hand-rolled pooling is rejected: wrong pooling or a missing L2 norm produces fast,
valid-looking, quietly degraded vectors and nothing throws (L8, twice in the incumbent).

## Acceptance

- A test asserts `docs` has exactly one writer.
- Delta behaviour: unchanged content re-runs with zero embed calls (assert the encoder is not
  called, don't time it).
- Both models resident: embed a fixture under two model names, assert both rows persist with
  correct `dim`, and that reading one does not return the other's vector.
- Reconciliation removes `docs_vec` rows for pruned chunks too — an orphaned vector is as
  corrupting as an orphaned doc row, and easier to miss.
- `embed_ms` and `peak_rss_mb` recorded in `SyncReport.meta` (§8, L7).
- Runs offline in tests: the encoder is stubbed. No network, no model download in the suite.
- **A unit fetched successfully that now yields zero chunks reconciles to zero** — start from a
  multi-chunk unit, attest it with no docs, assert its `docs` *and* `docs_vec` rows are gone.
- **A unit absent from `units_ok` keeps every row**, even while a sibling unit in the same run
  prunes. This is the partial-fetch case and it is the one that matters (GH-169 RC5).
- **Deleting a vault note removes it from search**: delete the file, run a clean fetch, assert the
  rows are gone — via the real `vault.SOURCE`, not a mock. Then delete a note and make the walk
  error, and assert the rows survive.
- **A source with no attestation prunes nothing** — a fake source returning the default
  `units_ok=()` leaves its existing rows intact.
- `get_doc_unit()` and all four attestation workarounds are gone; a test asserts unit membership
  comes from `Doc.unit`, including for an id containing a colon.

## Do not

- Do not implement pooling, normalization, or tokenization yourself (Decision 1, L8).
- Do not embed on every run "to be safe" — the delta is the design, and L7 is what unbounded
  embedding cost this machine.


## Debug mantra (auto-triggered — 1 prior attempt(s) on this phase did not reach Approved)

Before trying again, read /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/relay-automation/DEBUG-MANTRA.md and follow its four-step discipline: reproduce reliably, know the fail path, question the hypothesis, treat this round as a breadcrumb for the next one.
Last recorded reason (/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/phases/hiqs-m2-cont-p2p4--hiqs-m2-p2/ESCALATION.md): `cap-or-close-mismatch`. Read it before re-guessing.

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_contract.py,HiQS/hiqs/plugins.py,HiQS/hiqs/sources/vault.py,HiQS/tests/test_vault.py,HiQS/tests/test_plugins.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M2-P2-TURN-3 --agent agy --paths "phases/hiqs-m2-cont-p2p4--hiqs-m2-p2/RELAY.md,HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_contract.py,HiQS/hiqs/plugins.py,HiQS/hiqs/sources/vault.py,HiQS/tests/test_vault.py,HiQS/tests/test_plugins.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M2-P2-TURN-3 --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P2-TURN-3 --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m2-cont-p2p4--hiqs-m2-p2/RELAY.md and HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_contract.py,HiQS/hiqs/plugins.py,HiQS/hiqs/sources/vault.py,HiQS/tests/test_vault.py,HiQS/tests/test_plugins.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_contract.py,HiQS/hiqs/plugins.py,HiQS/hiqs/sources/vault.py,HiQS/tests/test_vault.py,HiQS/tests/test_plugins.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P2-TURN-3 --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M2-P2-TURN-3 --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m2-cont-p2p4--hiqs-m2-p2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

---

### Round 1 · Builder · agy

Implemented M2 p2 per brief:
- **plugins.py**: Added `units_ok: tuple[str, ...] = ()` to `SyncReport` and `unit: str = ""` to `Doc`.
- **vault.py**: `fetch()` populates `units_ok` and deletes vanished paths on clean walk. On errored walk, unknown paths are retained and not attested. `docs()` skips missing files instead of throwing. `Doc` objects set `unit=rel_path`.
- **docs_index.py**: Deleted `get_doc_unit()` and all 4 legacy attestation workarounds (`successful_units` kwarg, duck-typed `units()`, `sync_successful_units` table probe, raw table probe). Updated `project_docs` signature to accept `reports: Mapping[str, SyncReport] | None = None` and reconcile strictly within `reports[source.name].units_ok` (no attestation ⇒ prune nothing).
- **tests**: Updated `test_plugins.py`, `test_vault.py`, `test_docs_index.py` to cover all acceptance criteria (unit attestation, colon handling, partial fetch retention, zero chunk reconciliation, deleted vault note clean vs errored fetch). All 54 tests passing.

