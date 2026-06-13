# Review: f0b53be

Audit window: local 2026-06-12 commits through `f0b53be` (`development`).

## Findings

1. **High — direct `calendar-sync --calendar-id ...` now silently ignores the requested calendar.**
   [src/rebalance/ingest/calendar.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/calendar.py:187) resolves the requested calendar ID, then rewrites any non-`primary` value to `"primary"` whenever `person is None`. The CLI path passes the operator-supplied `--calendar-id` to this function without `person` at [src/rebalance/cli/calendar.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/cli/calendar.py:256), so `rebalance calendar-sync --calendar-id team@...` prints that it is syncing `team@...` but actually fetches/stores `primary`. This also contradicts the config comment that `calendar_id` can be changed for direct CLI usage. Fix by canonicalizing only the orchestrated operator path, or add an explicit `canonicalize_operator=True` parameter that the CLI does not set for explicit overrides.

2. **Medium — release/changelog metadata is inconsistent with today's code changes.**
   [CHANGELOG.md](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:9) records `0.39.3`, but package metadata still reports older versions: [pyproject.toml](/Users/noelsaw/Documents/rebalance-OS/pyproject.toml:7) is `0.35.0`, [src/rebalance/__init__.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/__init__.py:31) is `0.39.2`, and generated `PKG-INFO` is also `0.35.0`. Also, the current 2026-06-12 changelog entry only covers sidebar reminders and PAT guidance, while today's committed code includes P2 calendar composite-PK migration, team-calendar config/sync, primary-only export hardening, Gemini synthesis, and migration-runner changes. This violates the repo's stated "every fix or feature gets a version bump at commit/merge time" rule and makes `rebalance --version`/packaging misleading.

3. **Medium — Gemini Secret Manager implementation does not match the locked P2 design.**
   The P2 doc says Gemini keys are fetched from Google Secret Manager via the `gcloud` CLI ([PROJECT/2-WORKING/P2-TEAM-CALENDAR-SIGNAL.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/P2-TEAM-CALENDAR-SIGNAL.md:129)), but [src/rebalance/ingest/config.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/config.py:1164) uses the optional `google-cloud-secret-manager` Python package and requires `GOOGLE_CLOUD_PROJECT`. On an operator machine where the key is available through `gcloud secrets versions access` but the optional package/env is absent, `ask()` will silently fall back to local Qwen instead of using the mandated Gemini path. Either update the implementation to the documented `gcloud` resolver with tests, or update the P2 contract and deployment docs to require the Python GCP dependency/env.

4. **Low — P2 project doc still contains stale privacy-state language.**
   [PROJECT/2-WORKING/P2-TEAM-CALENDAR-SIGNAL.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/P2-TEAM-CALENDAR-SIGNAL.md:127) still says the primary-only export filter is "NOT YET IMPLEMENTED", but [src/rebalance/ingest/sync_snapshot.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/sync_snapshot.py:100) now filters `calendar_id = 'primary'`, and tests cover that. This is not a code bug, but it weakens the audit trail around a privacy-critical invariant.

## What Looked Solid

- Calendar migration `0005` preserves existing rows, adds `person`, and allows the same Google event ID to coexist across calendars.
- `refresh_index()` now skips collectors after migration failure instead of letting them write into an unknown schema state.
- Pulse/export paths are now explicitly primary-calendar-only.
- Team calendar sync failures are isolated per teammate and do not abort the operator calendar sync.
- Gemini response parsing handles valid but textless `MAX_TOKENS`/safety-style responses without raw `KeyError`/`IndexError`.

## Verification

Targeted tests passed:

```bash
.venv/bin/python -m unittest \
  tests.test_calendar_composite_pk_migration \
  tests.test_calendar_config_reject_primary_team \
  tests.test_calendar_config_team_calendars \
  tests.test_calendar_person_attribution \
  tests.test_calendar_read_nonprimary_config \
  tests.test_calendar_reader_scope \
  tests.test_calendar_reports \
  tests.test_calendar_sync_migrates \
  tests.test_calendar_team_loop_isolation \
  tests.test_db_migrations \
  tests.test_index_ops_migration_gate \
  tests.test_pulse_calendar_scope \
  tests.test_querier_gemini_parse \
  tests.test_querier_vacation_scope \
  tests.test_sync_snapshot
```

Result: `Ran 101 tests ... OK`.

## Residual Risk

I did not run the full repository test suite. The main remaining risk is behavior outside the orchestrated `refresh_index()` path, especially direct CLI/MCP calendar operations and runtime environments that do not have the optional GCP Python dependency installed.
