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

## Adding a migration

1. Create `NNNN_short_description.sql` here, where `NNNN` is the next integer
   after the highest existing file, zero-padded to four digits (`0002`, `0003`, …).
2. Write forward-only SQL. Be defensive — prefer `IF EXISTS` / `IF NOT EXISTS`
   so a partially-applied run can be re-run safely.
3. That's it. `run_migrations()` discovers the file, applies it once, and records
   the new version in the `schema_version` table.

Example — `0002_add_repo_topic.sql`:

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
