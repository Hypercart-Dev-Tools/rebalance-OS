# Schema migrations

Forward-only SQL migrations for `rebalance.db`. The runner is
[`db/migrate.py`](../migrate.py).

## The model

- **Version 1 is the baseline** — everything the `ensure_*_schema` functions in
  [`db/schema.py`](../schema.py) create. Any database that has run those
  functions is, by definition, at version 1.
- **`schema.py` is frozen at the baseline.** Do **not** add columns or tables to
  the `ensure_*_schema` functions for a schema change. They exist only to build
  the version-1 baseline (and to keep fresh installs working).
- **Every schema change from version 2 onward is a file in this directory.**

This keeps fresh installs and existing databases on the same path: the baseline
is created/assumed, then migrations `0002…N` are applied in order.

### Exception: idempotent, self-healing virtual indexes (FTS5, `vec0`)

The migration rule above is for **base tables, columns, and their indexes** — the
source-of-truth schema. SQLite *virtual tables that are derived indexes* over base
tables are deliberately the exception: the `vec0` embedding indexes
(`semantic_embeddings`, `github_embeddings`) and the `semantic_documents_fts`
FTS5 index are created in `ensure_*_schema`, **not** as numbered migrations.

This is intentional, for two reasons a one-time migration can't satisfy:

1. **Self-heal.** These indexes are rebuildable from their base tables and must
   survive being dropped or left half-built. `ensure_semantic_schema` recreates
   and backfills the FTS index whenever it's missing or stale (guarded by an
   `fts_version` marker that forces a clean drop+rebuild when the definition
   changes). A migration runs once and would never repair a later-dropped index.
2. **Read-path coverage.** Read paths such as `semantic_index.query()` open the
   DB through `ensure_semantic_schema` *without* running migrations, so `ensure`
   is what guarantees the index exists for reads (it degrades to ANN-only if a
   virtual table can't be created — e.g. the `vec0` extension isn't loaded).

So: **changing one of these virtual indexes** = bump its in-code version marker
(`fts_version`, …) to trigger a rebuild on the next `ensure`, not a numbered
migration. **Everything else** (real tables, columns, indexes on base tables)
still follows the migration rule above.

## Adding a migration

1. Create `NNNN_short_description.sql` here, where `NNNN` is the next integer
   after the highest existing file, zero-padded to four digits (`0002`, `0003`, …).
2. Write forward-only SQL. Be defensive — prefer `IF EXISTS` / `IF NOT EXISTS`
   so a partially-applied run can be re-run safely.
3. **Do not add your own `BEGIN` / `COMMIT`.** The runner wraps every migration
   in a single transaction and rolls back on any error, so a multi-statement
   migration that fails mid-script is atomic — the database stays at the prior
   version with the original tables intact, never half-applied. A file that
   opens its own transaction would hit a nested `BEGIN` and be rolled back
   instead of applied. (The rare statement that cannot run inside a transaction —
   `VACUUM`, `PRAGMA foreign_keys` toggles around a table rebuild — is not
   supported by the wrapper; raise it before writing such a migration.)
4. That's it. `run_migrations()` discovers the file, applies it once inside its
   transaction, and records the new version in the `schema_version` table.

Example — `0002_add_repo_topic.sql` (no transaction control — the runner
provides it):

```sql
ALTER TABLE github_repo_meta ADD COLUMN topics_json TEXT;
```

## When migrations run

`run_migrations(conn)` is invoked automatically at the start of every
non-dry-run `refresh_index()` call. Any new code path that opens the database
before a refresh has happened should call it too:

```python
from rebalance.ingest.db import db_connection, run_migrations

with db_connection(db_path) as conn:
    run_migrations(conn)
```

The runner is idempotent — calling it on an already-current database is a cheap
no-op.

## Why forward-only, no down-migrations

`rebalance.db` is a local derived cache that can be rebuilt from source
(`refresh_index(scope=["all"])`). Rollback complexity is not worth it — if a
migration is wrong, fix it forward with the next one.
