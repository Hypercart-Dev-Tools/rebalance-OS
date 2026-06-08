# Writing a Source Plugin (`SourceModule`)

Developer how-to for adding a new data source to rebalance-OS through the plugin
(`SourceModule`) contract. For the *why / when* — roadmap, decisions, deferred
work — see [PROJECT/2-WORKING/PLUGINS.md](PROJECT/2-WORKING/PLUGINS.md). This
guide supersedes the older "Adding a New Source" recipe in
[ARCHITECTURE.md](ARCHITECTURE.md), which predates the registry contract.

## The model

Every source is registered with **one registry** — `COLLECTORS` in
[`src/rebalance/ingest/index_ops.py`](src/rebalance/ingest/index_ops.py). You add
a source by constructing a `Collector` (alias `SourceModule`) and calling
`register_collector(...)`. The `refresh_index(scope=[...])` dispatcher routes
each scope through the registry — **no edits to the dispatch chain are required.**

A source can span up to three planes; you implement only what you need:

| Plane | What | Required? |
|---|---|---|
| **Ingest** | fetch upstream → normalize → upsert into your own table | **yes** (the `refresh` callable) |
| **Vectorize** | yield `SemanticDoc`s into the unified semantic index (FTS5 + vec0) | optional — set `semantic_docs` |
| **Display** | dashboard panels | not a plugin plane yet (Phase 2 in the roadmap) |

**Strangler note.** The four legacy sources (vault / github / email / code) still
vectorize through a hardcoded if-ladder in `backfill_semantic_documents`. **New
sources ride the registry-driven *provider path* (`semantic_docs`).** Do not
touch the if-ladder — flipping the legacy sources onto providers is a separate,
parity-gated PR (see the roadmap doc).

## The descriptor

```python
# src/rebalance/ingest/index_ops.py
@dataclass(frozen=True)
class Collector:                     # alias: SourceModule = Collector
    name: str                        # unique user-facing scope key (reserved: "all")
    refresh: Callable[..., dict]     # (db_path, **opts) -> {"scope": name, ...}; ignore unknown opts
    requires: tuple[str, ...] = ()   # preconditions: "vault_path" | "github_token" | "figma_token"
    included_in_all: bool = True     # False = opt-in (network/secret-gated; runs only on explicit scope)
    semantic_docs: Callable[[Conn], Iterable[SemanticDoc]] | None = None  # vectorize provider
    secrets: tuple[str, ...] = ()    # secret config keys this source consumes (metadata for tooling)
```

A `Collector` that also exposes `semantic_docs` *is* a `SourceModule`.

## Worked example — the Figma source

Figma is the reference `SourceModule`. Files to copy the shape from:
`ingest/figma.py`, `db/migrations/0004_add_figma_comments.sql`, the `figma_*`
config in `ingest/config.py`, the `_refresh_figma` adapter + registration in
`index_ops.py`, and `tests/test_figma_ingest.py` / `tests/test_figma_source_module.py`.

### 1. Ingest layer — client + table + read helper

- `src/rebalance/ingest/<source>.py`: a client + `sync_<source>(database_path, *, ...) -> <Result>`
  that fetches → normalizes → upserts into **your own table**. Keep module-top
  imports limited to `rebalance.ingest.db` (no mlx / embedder).
- Add your table as a **numbered migration** (see [Migrations](#migrations--read-this-theres-a-silent-data-loss-trap)).
- Add a read helper `<source>_for_semantic(conn)` to `db/semantic.py` (all SQL
  lives there) returning the rows your provider will map.

### 2. Refresh adapter — honest envelopes, never silent success

```python
def _refresh_<source>(database_path, *, dry_run):
    keys = get_<source>_file_keys()
    if dry_run:
        return {"scope": "<source>", "dry_run": True, "file_keys": keys, "steps": [...]}
    token = (get_<source>_token() or "").strip()
    if not token:
        return {"scope": "<source>", "error": "<source> token not configured. Set it with ..."}
    if not keys:
        return {"scope": "<source>", "skipped": True, "reason": "No <source> keys configured ..."}
    sync_<source>(database_path, file_keys=keys, token=token)
    backfill_semantic_documents(database_path, source_types=["<source>"], use_registry_providers=True)
    embed_pending(database_path, source_types=["<source>"])
    return {"scope": "<source>", ...}

def _<source>_adapter(db_path, **opts):          # the registry shim
    return _refresh_<source>(db_path, dry_run=opts["dry_run"])
```

A missing token or empty key-list **must** surface as a visible `error` /
`skipped` envelope — never a fake "all good" (the project's no-silent-happy-errors
rule).

### 3. Make it vectorizable — the `semantic_docs` provider

```python
def <source>_semantic_docs(conn) -> Iterator[SemanticDoc]:
    from rebalance.ingest.db import semantic as sem            # function-local imports
    from rebalance.ingest.semantic_index import SemanticDoc    #   keep mlx off the module top
    for row in sem.<source>_for_semantic(conn):
        body = (row["text"] or "").strip()
        if not body:                       # skip empty / no-text rows
            continue
        yield SemanticDoc(
            source_pk=row["stable_key"],   # STABLE per item — the upsert/dedup key
            doc_kind="comment",
            title="...",                   # short human label
            body=body,                     # the embeddable text
            metadata={...},                # source-specific extras (url, author, ids)
            created_at=row["created_at"],
            updated_at=row["synced_at"],
        )
```

Then map your source name to its table in `semantic_index.py`:

```python
_REGISTRY_SOURCE_TABLES: dict[str, str] = {"figma": "figma_comments", "<source>": "<source>_table"}
```

The module **yields**; the index owns hashing, upsert, FTS, and embedding. You
never call `upsert_document` yourself.

### 4. Secrets & config

- **Secrets (API tokens):** OS **keyring**, modeled exactly on
  `get/set/clear_github_token` in `config.py` (keyring primary + a gitignored
  `temp/rbos.config` fallback so launchd jobs that can't reach the keychain still
  work). Never cleartext-only; never logged or committed.
- **Non-secret config** (file keys, scopes): plain `rbos.config` getters/setters.
- Declare `requires=("<source>_token",)` + `secrets=(...)` on the `Collector`,
  and extend the precondition resolver in `refresh_index`
  ([index_ops.py](src/rebalance/ingest/index_ops.py), the `requires` block) to
  resolve your token key — so a missing secret becomes a structured error, not an
  exception.

### 5. Register

```python
register_collector(Collector(
    "<source>", _<source>_adapter,
    requires=("<source>_token",),
    secrets=("<source>_token", "<source>_file_keys"),
    semantic_docs=<source>_semantic_docs,
    included_in_all=False,             # opt-in: network/secret-gated sources stay out of scope=["all"]
))
```

Also: port a `get_index_status` block (additive) so `index_status` surfaces your
source counts, and add your name to the `--source` allow-list in
`cli/semantic.py` if it should be CLI-queryable.

## Migrations — read this, there's a silent-data-loss trap

- New base tables / columns / indexes = a **numbered SQL file**
  `src/rebalance/ingest/db/migrations/NNNN_<desc>.sql`. Use the **next free
  integer** (`ls` the dir first).
- The runner ([`db/migrate.py`](src/rebalance/ingest/db/migrate.py)) applies files
  with `version > current_schema_version` and records each. **A file numbered ≤
  the DB's stamped version is silently skipped and never runs** — your table is
  never created, reads back empty, and *no error is raised*. If you branch from
  someone else's WIP that already used `NNNN`, **renumber** (Figma's table shipped
  `0002`→`0004` for exactly this reason).
- **Exception:** idempotent self-healing virtual indexes (vec0, FTS5) live in
  `ensure_*_schema`, **not** migrations — see
  [db/migrations/README.md](src/rebalance/ingest/db/migrations/README.md).

## Tests — no PAT, no network, no mlx

- Inject a **fake client** into `sync_<source>` via its `client=` param (no token,
  no network).
- Inject **`embed_texts`** into `embed_pending` / `query`. The production embedder
  is `mlx-embeddings` (Apple-Silicon only) and is **not installed in CI**; tests
  must never load it (the F3 finding — see CHANGELOG's embedding entry).
- End-to-end shape (`tests/test_figma_source_module.py`): seed your table →
  `backfill_semantic_documents(source_types=["<source>"], use_registry_providers=True)`
  → assert the `semantic_documents` rows (right `source_type` / `source_table` /
  `source_pk`, empty bodies skipped) → `embed_pending(..., embed_texts=fake)` →
  `query(..., source_filter=["<source>"], embed_texts=fake)` returns your doc.

## The flow at `refresh_index(scope=["<source>"])`

```
refresh_index(scope=["<source>"])
  → registry lookup → precondition check (requires) → _<source>_adapter
    → _refresh_<source>:
        sync_<source>()                                  # ingest → <source>_table
        backfill_semantic_documents(use_registry_providers=True)
          → <source>_semantic_docs(conn) yields SemanticDoc
          → upsert_document(...) into semantic_documents  # FTS-indexed on insert
        embed_pending()                                   # vec0 vectors via mlx-embeddings
  → query() / semantic_query() / ask() now surface your source (FTS + vector, RRF-fused)
```

## Checklist

- [ ] `ingest/<source>.py` — client + `sync_<source>` + `<source>_semantic_docs`
- [ ] `db/migrations/NNNN_<source>.sql` — next free number
- [ ] `db/semantic.py` — `<source>_for_semantic(conn)` read helper
- [ ] `semantic_index.py` — `_REGISTRY_SOURCE_TABLES["<source>"] = "<table>"`
- [ ] `config.py` — keyring token + plain non-secret config getters/setters
- [ ] `index_ops.py` — `_refresh_<source>` + `_<source>_adapter` + `register_collector(...)` + the `requires` precondition + a `get_index_status` block
- [ ] `cli/semantic.py` — add `<source>` to the `--source` allow-list (if CLI-queryable)
- [ ] tests — fake client + injected `embed_texts` (no PAT/network/mlx)
- [ ] `CHANGELOG.md` — an entry under `[Unreleased]`

## See also

- **Roadmap / decisions / deferred work:** [PROJECT/2-WORKING/PLUGINS.md](PROJECT/2-WORKING/PLUGINS.md)
- **Migration discipline:** [db/migrations/README.md](src/rebalance/ingest/db/migrations/README.md)
- **System architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Worked example:** `src/rebalance/ingest/figma.py`, `db/migrations/0004_add_figma_comments.sql`, `tests/test_figma_source_module.py`
