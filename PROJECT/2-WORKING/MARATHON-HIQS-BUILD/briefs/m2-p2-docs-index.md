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
