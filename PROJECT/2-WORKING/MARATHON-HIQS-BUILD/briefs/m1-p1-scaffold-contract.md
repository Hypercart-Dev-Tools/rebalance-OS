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

## Acceptance

- Every dataclass is frozen; field names/order/defaults match §5 character for character.
- `SyncReport.counts` documents the six keys: inserted, updated, unchanged, skipped, rejected,
  **pruned** (§5 rule 2 — `pruned` is not optional, the reconciliation contract needs it).
- Discovery returns `[]` on a clean environment without raising.
- A test asserts each dataclass rejects mutation.
- `.venv/bin/python -m pytest HiQS/tests -q` passes.

## Do not

- Do not add fields, helpers, or a base class "for later". §11 has a 3,000 LOC budget and §14 is
  where deferred things live.
- Do not import anything from `src/rebalance/**`. The clean-room boundary is the whole design.
- Do not write `db.py`, `events.py`, or any source plugin — those are p2, p4, and M2.
