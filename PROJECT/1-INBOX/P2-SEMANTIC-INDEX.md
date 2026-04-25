# Unified Semantic Index Plan

## TOC
- Current State
- Goals
- Architecture Direction
- Phase 0 Technical Spike
- Phase 1 Build The Index Layer
- Phase 2 Migrate Readers
- Phase 3 Opt-In For Calendar And Sleuth
- Contracts And Ownership
- Risks And Guardrails
- Success Criteria
- Open Questions

## Current State

`rebalance.db` already contains two parallel semantic indexes that don't talk to each other:

- **Vault**: `chunks` (sub-divided note text) → `embeddings` (sqlite-vec virtual table, 1024-dim Qwen3) → `embedding_meta` (key/value: `model_name`, `embedding_dim`, `last_embed_at`). Written by [src/rebalance/ingest/embedder.py](../../src/rebalance/ingest/embedder.py).
- **GitHub artifacts**: `github_documents` (issues, PRs, comments, reviews, commits as embeddable rows) → `github_embeddings` (sqlite-vec) → `github_embedding_meta`. Written by [src/rebalance/ingest/github_knowledge.py](../../src/rebalance/ingest/github_knowledge.py).

Cross-source semantic search today means:
1. Run the vault ANN query → get vault hits.
2. Run the GitHub ANN query → get GitHub hits.
3. Merge in [src/rebalance/ingest/querier.py](../../src/rebalance/ingest/querier.py) (`_gather_vault_context()` and `_gather_github_semantic_context()` are separate functions called from `ask()`).
4. Format two distinct prompt sections so the LLM can tell them apart.

This works but it scales poorly. Adding Calendar event titles or Sleuth reminder bodies as semantic-searchable content means a third embedder, a third meta table, a third gather function, and a third prompt section. The seam multiplies with every source.

## Goals

- [ ] One `semantic_documents` table that holds embeddable text from every source, with provenance back to the source-of-truth row.
- [ ] One `semantic_embeddings` vec table keyed off `semantic_documents.id`.
- [ ] One `query_semantic_context(query, k, source_filter=None)` API that returns ranked hits across sources in a single pass.
- [ ] Source tables (`chunks`, `github_items`, `calendar_events`, `sleuth_reminders`, etc.) stay canonical. The semantic layer is a derived index, not a replacement.
- [ ] One model-version contract: `semantic_embedding_meta` records the embedder + dim used; mismatched rows trigger re-embed, not silent staleness.
- [ ] Onboarding a new source becomes "write rows into `semantic_documents`," not "build another embedding pipeline."

## Architecture Direction

Two layers, not one:

```
SOURCE TABLES (canonical, structured)              SEMANTIC INDEX (derived)
─────────────────────────────────────              ──────────────────────────
vault_files ─▶ chunks ─────────────────┐
                                       │
github_items                           ├──▶ semantic_documents ──▶ semantic_embeddings (vec0)
github_comments ─▶ github_documents ───┤             │                     │
github_commits                         │             ▼                     ▼
github_reviews                         │     semantic_embedding_meta (model + dim + last_embed_at)
                                       │
calendar_events  (opt-in, Phase 3) ────┤
sleuth_reminders (opt-in, Phase 3) ────┘
```

Source tables keep their domain-specific columns (`state`, `start_at`, `due_date`, foreign-key cascades). The index layer holds only what semantic search needs: text, source pointer, content hash, model version.

### Schema

```sql
CREATE TABLE semantic_documents (
    id                      INTEGER PRIMARY KEY,            -- vec0 rowid
    source_type             TEXT NOT NULL,                  -- 'vault' | 'github' | 'calendar' | 'sleuth'
    source_table            TEXT NOT NULL,                  -- 'chunks' | 'github_documents' | ...
    source_pk               TEXT NOT NULL,                  -- stable, source-derived (see mapping below)
    doc_kind                TEXT NOT NULL,                  -- 'chunk' | 'item_body' | 'issue_comment' | 'review' | ...
    title                   TEXT,                           -- short header (file heading, issue title, event summary)
    body                    TEXT NOT NULL,                  -- the embeddable text, stored inline
    content_hash            TEXT NOT NULL,                  -- sha256(body) — invalidates the embedding when changed
    embedded_hash           TEXT,                           -- content_hash at the time the embedding was written; NULL = unembedded
    embedded_model_version  TEXT,                           -- model_name + dim; NULL = unembedded
    embedded_at             TEXT,                           -- ISO8601 of last successful embed
    metadata_json           TEXT,                           -- source-specific extras (repo, label set, attendees)
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    UNIQUE(source_type, source_pk)
);
CREATE INDEX idx_semantic_docs_source ON semantic_documents(source_type, updated_at DESC);
CREATE INDEX idx_semantic_docs_pending ON semantic_documents(source_type)
    WHERE embedded_hash IS NULL OR embedded_hash != content_hash;

CREATE VIRTUAL TABLE semantic_embeddings USING vec0(
    embedding float[1024]
);
-- LOAD-BEARING INVARIANT: every insert into semantic_embeddings sets
--   rowid = semantic_documents.id
-- This is what makes "join semantic_embeddings to semantic_documents" possible
-- (vec0 has no foreign-key syntax). Every writer must respect this; queries
-- assume `JOIN semantic_documents sd ON sd.id = se.rowid` everywhere.

CREATE TABLE semantic_embedding_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- seeded with: model_name, embedding_dim, embedder_version, last_embed_at
```

**`source_pk` mapping per source type** (this contract is load-bearing — get it wrong and a re-ingest collapses distinct rows into one):

| `source_type` | `source_pk` | `doc_kind` values |
|---|---|---|
| `vault` | `chunks.id` cast to TEXT | `chunk` |
| `github` | `github_documents.source_key` (TEXT) — **not `id`**, which is local autoincrement | `item_body`, `issue_comment`, `review_comment`, `review`, `commit_message` |
| `calendar` | `calendar_events.id` (TEXT, Google event ID) | `event` |
| `sleuth` | `sleuth_reminders.reminder_id` (TEXT) | `reminder` |

`chunks` has no domain-stable identifier — its primary key is autoincrement `id`, with the natural compound key being `(file_id, chunk_index)`. Using `chunks.id` (cast to TEXT) is the simplest path because it matches existing FK relationships and the chunk lifecycle (delete + re-insert on file change) already invalidates corresponding `semantic_documents` rows via the source-table → semantic-layer reconciliation hook. If we later want stability across full vault rebuilds, switch to `f"{file_id}:{chunk_index}"`; that's a single-line change in the ingester.

A single GitHub PR generates many rows in `github_documents`. The current schema enforces `UNIQUE(source_key) ON CONFLICT REPLACE` ([db.py](../../src/rebalance/ingest/db.py)) — there is no uniqueness on `(repo, item_type, number)` (that's just an index). So one PR produces one `item_body` keyed e.g. `pull_request:<repo>:<num>:body`, plus N `issue_comment` rows (`pull_request:<repo>:<num>:comment:<id>`), N `review_comment`, N `review`, N `commit_message` — each with its own `source_key`. The semantic layer's `UNIQUE(source_type, source_pk)` reuses those same `source_key` values, so the granularity carries over 1:1. Calendar and Sleuth produce one row per source row (no sub-division).

**Per-row embed state.** Three columns make incremental re-embed observable:

- `embedded_hash` matches `content_hash` → up to date.
- `embedded_hash IS NULL` → never embedded (or model changed since last embed).
- `embedded_hash != content_hash` → text changed since last embed, needs re-embed.
- `embedded_model_version != current` → model changed; treated as `embedded_hash IS NULL` and re-embedded.

`semantic_embedding_meta` records the *current* model contract (what `embed_pending()` will use). Per-row `embedded_model_version` records what each row was *last embedded under*. The two together let the system answer "which rows are stale?" without scanning the whole corpus or rebuilding from scratch on every model bump. This mirrors the `content_hash` / `embedded_hash` pair already used by [github_knowledge.py](../../src/rebalance/ingest/github_knowledge.py) — we're lifting that pattern, not inventing one.

**Body storage is inline, not by-reference.** Rationale: bodies are a small fraction of embedding cost (a few KB per row vs. 4KB per 1024-float vector), and inline storage means the semantic layer is self-sufficient for reranking, snippet display, and prompt assembly without joining back to four different source tables.

**`chunks` stays.** Vault notes need sub-division before embedding (long notes → multiple chunks). `chunks` keeps doing that job; the semantic layer ingests one row per chunk with `source_table = 'chunks'`, `source_pk = str(chunks.id)`.

**`github_documents` is absorbed.** It was always a derived "embeddable view" of `github_items` + `github_comments` + etc. — same role the new layer plays. After Phase 2, `github_documents` is dropped; the data lives in `semantic_documents` with `source_type = 'github'`, multiple rows per PR/issue, each keyed by the same `source_key` the existing pipeline already produces.

### Reconciliation

When source data changes, the index layer needs to keep up:

- **Vault**: re-ingest deletes/recreates `chunks` for changed files (existing CASCADE behavior). The semantic ingester re-emits `semantic_documents` rows for any chunk whose `chunks.id` was reissued.
- **GitHub**: existing `github_knowledge.py` maintains `github_documents` with `UNIQUE(source_key) ON CONFLICT REPLACE` — one row per embeddable artifact (item body, comment, review, commit), not one row per issue/PR. The semantic ingester subscribes to that pipeline; its `source_pk = source_key` carries the same granularity through.
- **Calendar / Sleuth (Phase 3)**: opt-in, write-through from their existing collectors.

`embed_pending()` re-embeds a row when:
- `embedded_hash IS NULL` (new or never embedded), OR
- `embedded_hash != content_hash` (text changed), OR
- `embedded_model_version != current_model_version` (model bumped).

After embedding, `embedded_hash`, `embedded_model_version`, and `embedded_at` are written atomically with the vec0 row. A model change does **not** require pre-emptively clearing all rows — the version mismatch alone marks them as pending. This is the same delta strategy `embedder.py` and `github_knowledge.py` already use, generalized.

## Phase 0 Technical Spike

Timebox: half-day. Read-only investigation plus a backfill prototype.

### Checklist

- [ ] Confirm `sqlite-vec` virtual tables coexist with the existing `embeddings` and `github_embeddings` virtual tables in the same DB without conflict.
- [ ] Write a one-shot Python script `experimental/semantic-index/backfill_vault.py` that copies `chunks` rows into a temporary `semantic_documents_spike` table (no embed yet — just the schema and the row mapping).
- [ ] Run an ANN query against the existing vault `embeddings` joined to the new spike table. Confirm hit ranking is identical to the current `embedder.py` query path.
- [ ] Measure storage: how much does inline-body duplication add for the current ~20 chunk rows? Project to 1k and 10k.
- [ ] Repeat for GitHub: prototype copy `github_documents` → `semantic_documents_spike`. Verify the `metadata_json` shape captures everything `_gather_github_semantic_context()` currently surfaces.

### What Phase 0 Must Prove

- The proposed schema can hold every field today's two semantic gathers consume — including the `source_key` granularity for GitHub (one row per item_body, comment, review, commit).
- Inline body storage isn't a meaningful cost increase at projected scale.
- A unified-table ANN query, **scoped by `source_filter` to a single source**, returns hits at parity with the existing per-source queries (top-10 overlap ≥ 80%; see Phase 1 Acceptance #3). Unscoped global top-k will return a different source mix — that's the design intent of unification, not a fidelity regression, and is evaluated separately under Phase 2.
- The per-row embed-state contract (`embedded_hash` + `embedded_model_version`) works for both vault chunks and GitHub artifacts without source-specific branches.

### Spike Deliverables

- [ ] A throwaway `semantic-index_spike.py` that builds `semantic_documents_spike` and runs comparison queries.
- [ ] A short findings block in this doc with timing, storage, and any schema gaps that surfaced.

## Phase 1 Build The Index Layer

Objective: ship `semantic_documents` + `semantic_embeddings` + `semantic_embedding_meta` as live tables that *parallel* the existing pipeline. No reader changes yet.

### Checklist

- [ ] Add the three tables to [src/rebalance/ingest/db.py](../../src/rebalance/ingest/db.py) with an `ensure_semantic_schema(conn)` helper.
- [ ] Add `src/rebalance/ingest/semantic_index.py` with:
  - `upsert_document(conn, source_type, source_pk, title, body, metadata) -> doc_id`
  - `embed_pending(conn, batch_size, model)` — embeds rows whose `content_hash` doesn't match the current model version.
  - `query(conn, query_text, k, source_filter=None) -> list[Hit]`
- [ ] Wire vault re-ingest to write through to `semantic_documents` (additive — keep writing the existing `embeddings` table during the transition).
- [ ] Wire GitHub artifact sync to write through to `semantic_documents`.
- [ ] Add a CLI: `rebalance semantic-backfill --source vault|github|all` to populate from existing data without re-running collectors.
- [ ] Add `rebalance semantic-embed` mirroring `ingest embed` and `github-embed`.
- [ ] Add a freshness signal so the dashboard at [experimental/freshness/spike.py](../../experimental/freshness/spike.py) can show `semantic_embedding_meta.last_embed_at` as a unified vector column (replacing the per-source vector columns it added).

### Phase 1 Acceptance

Three checks, all required:

1. **Row-count parity** (necessary, not sufficient — counts can match while contents drift):
   ```sql
   -- vault parity
   SELECT
     (SELECT COUNT(*) FROM embeddings)                                      AS old_vault,
     (SELECT COUNT(*) FROM semantic_embeddings se
      JOIN semantic_documents sd ON sd.id = se.rowid
      WHERE sd.source_type = 'vault')                                       AS new_vault;
   -- github parity, same shape against github_embeddings + source_type='github'
   ```
   `source_type` lives on `semantic_documents`, not on `semantic_embeddings`, so this is always a join.

2. **Identity parity.** For each source, hash the set of `(source_pk, content_hash)` tuples on both sides and compare. Counts can match while a row points at the wrong content; this catches that.

3. **Top-k overlap on a fixed query set.** Run 5 representative queries through both the old per-source ANN paths and the new unified path with `source_filter=` to scope to a single source. The unfiltered union of the new path's hits should contain ≥80% of the union of the old paths' hits at k=10. This is the real fidelity check; it's the only one that catches "embeddings written under wrong rowid mapping" or "vec0 dimension mismatch."

`rebalance semantic-embed` must re-embed only rows where `embedded_hash != content_hash` OR `embedded_model_version != current` — verified by snapshotting `embedded_at` for unchanged rows and confirming it doesn't move on a re-run.

Daily sync still uses the old paths; nothing in the read layer has moved yet.

## Phase 2 Migrate Readers

Objective: cut over `querier.py` and any MCP tools to the unified API. Drop the old tables.

### Checklist

- [ ] Add `_gather_semantic_context(query, k, sources=None)` in [src/rebalance/ingest/querier.py](../../src/rebalance/ingest/querier.py) that calls `semantic_index.query()`.
- [ ] Remove `_gather_vault_context()` and `_gather_github_semantic_context()`. Replace their call sites in `ask()` with one call to `_gather_semantic_context`.
- [ ] Update `_build_prompt()` so cross-source hits render in one labeled section (with per-hit source badges) instead of two separate sections.
- [ ] Update the `query_notes` and `query_github_context` MCP tools to either (a) delegate to `query_semantic_context` with a `source_filter`, or (b) be deprecated in favor of a new `query_semantic` MCP tool. Pick one; don't ship both long-term.
- [ ] Delete `chunks → embeddings` writeback in `embedder.py` once vault is exclusively going through the semantic layer.
- [ ] Delete `github_documents → github_embeddings` writeback in `github_knowledge.py`.
- [ ] Drop the old tables (`embeddings`, `embedding_meta`, `github_documents`, `github_embeddings`, `github_embedding_meta`) in a single migration. Keep `chunks` — it's still the sub-division unit for vault.

### Phase 2 Acceptance

- All semantic-recall tests pass with one query path.
- The `ask()` prompt has one semantic-context section, not two.
- The DB is smaller (no duplicated embeddings after the dual-write window closes).
- The freshness dashboard shows one "Vector" column, not per-source ones.
- **Source-mix evaluation** (this is an explicit behavior change, not a fidelity check): run 10 real `ask()` prompts through both the old per-source-budget path and the new global top-k path. Capture the source distribution of the returned hits in both. Expect the mix to shift — possibly substantially, depending on query intent. The pass criterion is human-judged relevance: for ≥ 8 of 10 prompts, the new mix is rated equal-or-better than the old mix. If it fails, fall back to the budget-preserving design below before cutover.

### Phase 2 design decision: global top-k vs. per-source budgets

Today's `ask()` runs two separate ANN queries, each with its own `k` (vault vs. GitHub). After unification two designs are possible:

| Design | Behavior | Pros | Cons |
|---|---|---|---|
| **Global top-k** | One ANN query over the whole index, return the absolute top-k regardless of source | Lets the query choose the best across sources; simpler API | Source mix shifts vs. today; risk of one source crowding out another on broad queries |
| **Per-source budgets** | One unified table but the query API takes `{source: k}` and returns top-k per source | Drop-in fidelity for `ask()` today; preserves prompt-section balance | Re-introduces per-source caller knowledge into the query API; partly defeats the unification |

Default: build the API to support both (`query(text, k=10)` for global; `query(text, budgets={'vault': 5, 'github': 5})` for per-source). Call site decides. `ask()` starts on per-source budgets to preserve current behavior, then revisits after evaluating real prompts. This makes the cutover reversible by call-site config rather than schema.

## Phase 3 Opt-In For Calendar And Sleuth

Objective: extend semantic search to structured-but-textual sources where it actually helps.

### Decision criteria — opt in only if

- The text fields are long enough for embeddings to add over keyword search (`event.summary + event.description` for calendar; `reminder.text` for Sleuth).
- The source has queries that are currently hard ("find meetings about OAuth," "show reminders about the calendar bug").
- The user demonstrates real friction with the existing structured queries.

### Checklist (gated on the criteria above)

- [ ] Calendar: write `event.summary + "\n\n" + event.description` into `semantic_documents` with `source_type='calendar'`, `source_pk=event_id`. Metadata captures `start_at`, `end_at`, `attendees_count`.
- [ ] Sleuth: write `reminder.text` with `source_type='sleuth'`, `source_pk=reminder_id`. Metadata captures `should_post_on`, `is_active`.
- [ ] Run an A/B against 10 real prompts comparing structured-only retrieval to structured + semantic. Stop here if semantic doesn't materially help.
- [ ] If the test passes, add Calendar/Sleuth sections to `_build_prompt()` and update the freshness dashboard to remove `NOT_APPLICABLE` from those rows.

### Guardrail

If structured queries already answer Calendar/Sleuth questions well, don't embed them. Embeddings cost storage and re-embed time on every model change; opting in should be a measured win, not a default.

## Contracts And Ownership

Single-writer rule (mirrors P1-SQLITE):

- One module (`semantic_index.py`) owns the schema, `upsert_document`, `embed_pending`, and `query`.
- Source-specific writers (`embedder.py`, `github_knowledge.py`, future Calendar/Sleuth hooks) call into the single owner; they don't touch the semantic tables directly.
- Schema changes go through `ensure_semantic_schema(conn)` migrations and are called out as contract changes.

`semantic_embedding_meta` is the model-version contract:

- `model_name`, `embedding_dim`, `embedder_version`, `last_embed_at`.
- A model change bumps the version and triggers a full re-embed of `semantic_documents` rows. No silent dimension drift.
- During the dual-write window, the old `embedding_meta` and `github_embedding_meta` tables remain authoritative for their own consumers; only the unified meta governs the new layer.

## Risks And Guardrails

- **Dual-write divergence.** During Phase 1 both pipelines write embeddings. If a sync writes to the old tables but fails on the new ones, the layers drift. Mitigation: wrap both writes in a single transaction; on failure, rollback both. Add a daily reconciliation check that compares row counts.
- **Embedder consolidation isn't free.** `embedder.py` (mlx-embeddings, batch ANN over `chunks`) and `github_knowledge.py` (its own embed loop) have diverged in batch sizing, error handling, and rate limiting. Merging into one `embed_pending()` is the single biggest piece of work in Phase 1 — easily a full day on its own.
- **Prompt-assembly rewrites in `querier.py`.** Today's `_build_prompt()` formats two distinct semantic sections. Collapsing to one with per-hit source badges is a behavior change for the local Qwen3 layer; outputs will shift. Plan a manual eval pass against 10 real `ask()` calls before deleting the old gather functions.
- **Source-mix shift on global top-k.** Today's two-query design gives vault and GitHub independent recall budgets — vault always gets some seats at the table, GitHub always gets some seats. A single global ANN query over the union doesn't preserve that; on a heavily-GitHub query, vault hits can drop out entirely (and vice versa). This is the design intent of unification, but it's a real behavior change. Mitigation: ship the query API with optional per-source budgets (see Phase 2 design decision); start `ask()` on budgets, evaluate, only then consider switching to global top-k.
- **Effort honesty.** The original "half a day" estimate was the schema only. Realistic full Phase 1 + Phase 2: 2–3 days of focused work. Phase 3 is open-ended and gated on evidence.
- **Inline body duplication.** `semantic_documents.body` re-stores text that already lives in `chunks.text`, `github_documents.body`, etc. At current scale (20 vault chunks, ~hundreds of GitHub docs) this is negligible. At 100k+ rows it's worth measuring; Phase 0 covers this.
- **Migration window.** Between Phase 1 ship and Phase 2 cutover, the DB carries both old and new embeddings. Disk roughly doubles on the embedded portion. Acceptable for the transition window; not acceptable as a long-term state.

## Success Criteria

- [ ] One ANN query returns ranked hits across vault and GitHub artifacts in a single call (with optional per-source budgets to preserve prompt-section balance).
- [ ] `_gather_vault_context()` and `_gather_github_semantic_context()` are gone, replaced by `_gather_semantic_context()`.
- [ ] Per-row embed state is observable: `embedded_hash`, `embedded_model_version`, and `embedded_at` accurately reflect what's been embedded under what model. A model bump triggers re-embed of stale rows only, not the whole corpus.
- [ ] The freshness dashboard shows one "Vector" column, sourced from `semantic_embedding_meta.last_embed_at`.
- [ ] Adding Calendar or Sleuth to the semantic index is a config decision, not a new pipeline.
- [ ] Old tables (`embeddings`, `embedding_meta`, `github_documents`, `github_embeddings`, `github_embedding_meta`) are dropped.
- [ ] Identity parity holds at cutover: hashed `(source_pk, content_hash)` tuple sets match between old and new indexes per source.
- [ ] No human-judged regression on the 10-prompt eval set after the cutover (≥ 8/10 rated equal-or-better).

## Open Questions

- [ ] Should `semantic_documents.body` be the canonical text, with source tables drop their text columns once cutover completes? Probably no — source tables stay self-contained — but worth confirming after Phase 2.
- [ ] Does the model-version contract need to support multiple concurrent embedders (e.g., a smaller model for low-priority sources)? If yes, `semantic_embedding_meta` needs to become per-source instead of global.
- [ ] If we add the unified `relations` table from [P2-GRAPHQL.md](./P2-GRAPHQL.md) later, does it key off `semantic_documents.id` or off `(source_type, source_pk)`? The latter survives a full re-embed; the former is faster to join. Probably the latter.
- [ ] Phase 3 opt-in test: what's the actual prompt set? Should be drawn from real `ask()` history once we have one, not invented.
