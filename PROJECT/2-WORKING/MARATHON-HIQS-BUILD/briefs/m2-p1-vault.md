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
