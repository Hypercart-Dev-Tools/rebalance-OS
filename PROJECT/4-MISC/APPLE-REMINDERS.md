---
title: Apple Reminders Integration
status: Phase 0 blocked by macOS privacy gate - 2026-06-05
created: 2026-06-05
updated: 2026-06-05
owner: noel
tool_surface: refresh_index(scope=["apple_reminders"]) + optional list/query MCP tool later
depends_on:
  - src/rebalance/ingest/index_ops.py collector registry
  - local macOS Reminders SQLite store
  - read-only temp snapshot strategy
phases: 0 spike · 1 collector · 2 query surface · 3 semantic opt-in
phases_done: none
phases_next: Phase 0 - local SQLite spike
decision_gates:
  - Phase 0 must prove path discovery, read-only access, field coverage, and launchd/agent permissions
  - Phase 1 starts only if tags/sections/sub-reminders can be extracted deterministically without writing to the live store
non_goals:
  - writing back to Apple Reminders
  - replacing Sleuth reminders
  - relying on EventKit as the primary ingest path
  - broad personal-data embedding before field quality is proven
---

# Apple Reminders Integration

| Last completed | What's next |
|---|---|
| Phase 0 probe run on 2026-06-05. Confirmed the modern Reminders store root exists on this Mac, but the agent runtime gets `PermissionError` on the `Stores` directory even outside the workspace sandbox. | Grant the host runtime Full Disk Access or run the spike from a terminal/runtime that already has access, then rerun `bash scripts/apple_reminders.sh`. |

> Status: Phase 0 blocked on 2026-06-05 by macOS privacy/TCC. Goal remains the same: determine whether Apple Reminders can become a safe, local, read-only source in rebalance without relying on EventKit and without risking store corruption.
> Architecture in one line: live Apple Reminders SQLite -> read-only temp snapshot -> normalized reminder rows -> rebalance collector/table -> optional MCP/query surface.
> Hard rule: never write to the Apple Reminders store.
>
> **Part of the plugin source roster (2026-06-07):** Apple Reminders is the second
> real source slated to onboard via the `SourceModule` plugin architecture — see
> [PLUGINS.md](./PLUGINS.md). This doc remains the detailed spec; the vector
> opt-in maps to the module's `semantic_docs`, and macOS Full Disk Access is the
> module's `requires` precondition. Phase 0 here is still gated on that TCC grant.

## Table of Contents

- [Thesis](#thesis)
- [What we keep from the source notes](#what-we-keep-from-the-source-notes)
- [Architecture decisions](#architecture-decisions)
- [Phase 0 - Technical spike](#phase-0---technical-spike)
- [Phase 1 - Collector integration](#phase-1---collector-integration)
- [Phase 2 - Query surface and product use](#phase-2---query-surface-and-product-use)
- [Phase 3 - Semantic opt-in](#phase-3---semantic-opt-in)
- [Risks and blockers](#risks-and-blockers)
- [Appendix A - Perplexity source notes preserved](#appendix-a---perplexity-source-notes-preserved)

## Thesis

If the requirement is "read my real Apple Reminders, including tags, sections,
and sub-reminders," the likely primary integration path is the local Reminders
SQLite store, not EventKit. The current repo architecture supports this shape:
one collector, one normalized table, one registry entry in
`src/rebalance/ingest/index_ops.py`, then optional query/UI layers later.

The spike is not about shipping a polished source. It is about proving four
things early:

1. The database path is discoverable across current macOS layouts.
2. Read-only access is reliable from the execution contexts that matter here
   (interactive shell, agent-hosted process, and ideally launchd).
3. The schema exposes the fields we actually care about: title, notes, due
   state, list, tags, sections, and parent-child reminder structure.
4. We can normalize those fields without brittle, machine-specific SQL that
   will collapse on the next macOS update.

## What we keep from the source notes

- The authoritative location anchor is `Container_v1/Stores/Data-*.sqlite`;
  the full parent path varies by macOS version, so the collector should
  discover it with a small set of known roots plus globbing, not one
  hardcoded absolute string.
- The store is Core Data-backed with `Z*` tables such as
  `ZREMCDREMINDER` / `ZREMCDOBJECT`; schema drift is expected.
- Tags, sections, and sub-reminders are the core reason to prefer SQLite over
  EventKit or AppleScript. If Phase 0 cannot recover those cleanly, the
  feature likely is not worth shipping.
- The live store uses WAL and is owned by `remindd`. Reads may be acceptable;
  writes are not. The design should prefer a temp snapshot over querying the
  live DB directly on every sync.
- "Works in Terminal" is not enough. rebalance also relies on agent-hosted and
  scheduled contexts, so permissions and TCC behavior are a first-class part
  of the spike.

## Architecture decisions

- Keep Apple Reminders separate from `sleuth_reminders`.
  The sources have different provenance, schemas, and freshness semantics.
  Unify them only at presentation/query time if that becomes useful.
- Treat this as a structured source first.
  Phase 0 and Phase 1 should target normalized SQLite rows, not embeddings.
- Use the existing collector registry in
  `src/rebalance/ingest/index_ops.py`.
  The intended scope name is `apple_reminders`; no custom dispatch chain.
- Use one logical pipeline:
  discover live DB -> create read-only snapshot -> introspect/adapt schema ->
  normalize rows -> upsert into rebalance.
- Prefer defensive normalization over overfitting to one Core Data version.
  If a field's location is unstable, store the stable normalized field plus a
  small raw JSON fragment for audit/debugging.
- Never mutate the live Apple database.
  No `UPDATE`, no `VACUUM`, no checkpointing, no write-back path.

## Phase 0 - Technical spike

Intent: validate the critical assumptions in 1-2 hours with the smallest
possible throwaway code. This is a go/no-go spike, not the start of a
production collector.

### What Phase 0 must prove

- **DB availability:** can we deterministically find the current user's
  Reminders store on this machine?
- **DB connectivity:** can we open it safely in read-only form and run
  reproducible queries?
- **Performance baseline:** is a snapshot + extract fast enough for routine
  local sync?
- **Blocking dependencies:** do TCC, launchd, schema drift, or WAL behavior
  make unattended sync impractical?

### Phase 0 checklist

- [ ] Discover the actual Reminders DB path on the local machine and record
      which root matched:
      `~/Library/Group Containers/group.com.apple.reminders/.../Container_v1/Stores/`
      or the older `~/Library/Reminders/Container_v1/Stores/`.
- [ ] Confirm the execution contexts that can read it:
      interactive shell first, then the same Python/runtime context rebalance
      uses, then a launchd-like context if practical.
- [ ] Pick and validate a safe read strategy.
      Preferred: copy the live `Data-*.sqlite` plus matching `-wal` and `-shm`
      into `temp/` and query the snapshot. Fallback: direct read-only open of
      the live DB if snapshotting proves unnecessary and stable. Reject any
      strategy that writes or checkpoints the live store.
- [ ] Dump schema metadata from `sqlite_master` and the candidate `ZREMCD*`
      tables. Record table names, columns, and obvious join keys in this doc.
- [ ] Identify the minimum viable normalized reminder contract:
      `reminder_id`, `title`, `notes`, `is_completed`, `due_at`,
      `completed_at`, `list_name`, `section_name`, `tags[]`,
      `parent_reminder_id`, `sort_hint`, `created_at`, `updated_at`.
- [ ] Extract at least 20 real reminders into that normalized shape from a
      scratch script and manually compare 5 cases against the Reminders UI:
      plain reminder, reminder with notes, tagged reminder, sectioned reminder,
      and a reminder with sub-reminders.
- [ ] Measure timings:
      path discovery, snapshot creation, schema probe, reminder extract, total
      wall clock.
- [ ] Record whether tags and sections are first-class recoverable fields or
      require fragile heuristics/opaque blob parsing.
- [ ] Decide whether recurring reminders and completed reminders are in scope
      for Phase 1 or should be deferred.

### Suggested spike artifacts

- Scratch extractor: `temp/apple_reminders_spike.py`
- Bash wrapper: `scripts/apple_reminders.sh`
- Schema dump: `temp/apple-reminders/schema.txt`
- Sample normalized output: `temp/apple-reminders/sample.json`
- Timing/log output: `temp/logs/apple-reminders-spike.jsonl`
- Findings written back into `## Phase 0 findings` in this doc before any
  Phase 1 work starts

### Phase 0 findings (2026-06-05)

**Recommendation: NO-GO for collector work in the current runtime until the
privacy gate is resolved.**

What was proven:

- The likely current-machine root is the modern path:
  `/Users/noelsaw/Library/Group Containers/group.com.apple.reminders/Container_v1/Stores`
  The probe could confirm the path exists and is a directory.
- The older fallback root
  `/Users/noelsaw/Library/Reminders/Container_v1/Stores`
  does not exist on this machine.
- The longer Sonoma variant with
  `Library/Application Support/Reminders/Container_v1/Stores`
  also does not exist on this machine.
- The block is not just the workspace sandbox. The same probe was rerun with
  escalated execution and still failed with:
  `PermissionError: [Errno 1] Operation not permitted:
  '/Users/noelsaw/Library/Group Containers/group.com.apple.reminders/Container_v1/Stores'`

What failed:

- The agent runtime can list `~/Library` and `~/Library/Group Containers`.
- It cannot list or read the Reminders `Stores` directory itself.
- Because the directory is unreadable, the spike could not:
  discover `Data-*.sqlite`,
  copy a read-only snapshot,
  inspect `sqlite_master`,
  or validate tags/sections/sub-reminders.

Artifacts produced:

- Scratch probe: [temp/apple_reminders_spike.py](/Users/noelsaw/Documents/rebalance-OS/temp/apple_reminders_spike.py)
- Summary: [temp/apple-reminders/summary.json](/Users/noelsaw/Documents/rebalance-OS/temp/apple-reminders/summary.json)
- Log: [temp/logs/apple-reminders-spike.jsonl](/Users/noelsaw/Documents/rebalance-OS/temp/logs/apple-reminders-spike.jsonl)

Timing:

- End-to-end probe time in the blocked runtime: `0.001s`
- That timing is only a permission result, not an extraction baseline

Interpretation:

- The architectural hypothesis is still plausible.
- The immediate blocker is macOS privacy/TCC, not collector design.
- Until the host process has access to the Reminders container, Phase 0 cannot
  answer the important schema and field-coverage questions.

Required next step:

- Grant Full Disk Access to the runtime that will execute rebalance collectors,
  or run the spike from a user-approved terminal/runtime that already has that
  access.
- After that, rerun:

```bash
bash scripts/apple_reminders.sh
```

Important: the item to grant Full Disk Access to is usually `/bin/bash` or the
host app (`Terminal`, `iTerm`, `VS Code`), not the `.sh` file itself. The
wrapper exists to give that FDA-granted runtime a stable entrypoint.

What the next successful rerun still needs to prove:

- exact `Data-*.sqlite` discovery
- snapshot copy of `.sqlite` + `-wal` + `-shm`
- schema dump and join identification
- sample extraction of tags, sections, and sub-reminders
- real timing baseline for snapshot + extract

### Go / no-go gate

**GO** if all of the following are true:

- Path discovery is deterministic enough to encode in the collector.
- Read-only extraction works without writing to the live DB.
- Tags, sections, and parent-child reminder structure are recoverable with
  acceptable confidence.
- The end-to-end extract is fast enough for a normal refresh run.
- Access from the intended runtime is workable, even if it requires a
  documented macOS permission step.

**NO-GO** if any of the following are true:

- Access only works interactively and fails in the runtimes rebalance actually
  uses.
- Tags/sections depend on opaque fields we cannot decode deterministically.
- The schema is too version-fragile to support with one adapter layer.
- The only reliable path requires touching the live database in write mode.

## Phase 1 - Collector integration

Runs only if Phase 0 is a GO.

- [ ] Add `src/rebalance/ingest/apple_reminders.py` with a module-local
      `ensure_apple_reminders_schema()` and `sync_apple_reminders()` entry
      point.
- [ ] Register `Collector(name="apple_reminders", refresh=...)` in
      `src/rebalance/ingest/index_ops.py`.
- [ ] Create an `apple_reminders` table keyed by the local reminder identifier.
      Preserve `first_seen_at`, refresh `last_seen_at`, and avoid deletes by
      default.
- [ ] Store unstable or multi-valued fields conservatively:
      `tags_json`, `raw_section_json`, or `raw_payload_json` are acceptable if
      that is what keeps the normalized contract stable.
- [ ] Add `index_status()` visibility: count + last synced timestamp for the
      new source.
- [ ] Add integration tests from a fixture snapshot, covering:
      first sync, unchanged sync, updated reminder, completed reminder, and a
      missing-field/schema-drift case.
- [ ] Add structured logging and one smoke test before merging.

## Phase 2 - Query surface and product use

- [ ] Add a small read surface such as `list_apple_reminders(...)` or
      `_gather_apple_reminders_context()` for the existing query layer.
- [ ] Keep Apple reminders and Sleuth reminders separate in storage; combine
      only in downstream views if the product wants a single "reminders" lane.
- [ ] Feed due/overdue Apple reminders into the morning-brief and pulse
      surfaces only after the collector proves freshness and quality.
- [ ] Decide whether completed reminders remain queryable history or should be
      hidden by default with an explicit include flag.

## Phase 3 - Semantic opt-in

Optional, not default.

- [ ] Only consider semantic indexing after the structured source is trusted.
- [ ] If added, index selected text fields only:
      title, notes, list name, maybe tags.
- [ ] Use a distinct `source_type="apple_reminders"` in the unified semantic
      index so retrieval remains explainable.
- [ ] Do not embed broad personal reminder history by default without an
      explicit product reason and a privacy review.

## Risks and blockers

- **macOS permissions / TCC.**
  The path is in a user-library container; access may differ between Terminal,
  VS Code, and launchd.
- **Schema drift across macOS versions.**
  Column names such as `ZTITLE`, `ZTITLE1`, or `ZNAME2` may move; the adapter
  must be defensive.
- **WAL consistency.**
  If reading the live DB directly proves flaky, snapshotting becomes mandatory.
- **Privacy sensitivity.**
  Reminders are personal data. Logs, fixtures, and tests must be redacted.
- **Scope creep.**
  Read-only ingest is the only acceptable first step. Editing, completion
  toggles, and automation against Apple Reminders are separate problems.

## Appendix A - Perplexity source notes preserved

The notes below are the starting assumptions for the spike, not proven facts in
this repo yet. Phase 0 exists to verify or falsify them locally.

### The path

The path quoted is correct for macOS Sonoma (14) and later:

```text
~/Library/Group Containers/group.com.apple.reminders/Library/Application Support/Reminders/Container_v1/Stores/Data-*.sqlite
```

However, the exact path has shifted across macOS versions:

```text
~/Library/Reminders/Container_v1/Stores/
~/Library/Group Containers/group.com.apple.reminders/Container_v1/Stores/
```

The `Library/Application Support/Reminders/` segment may or may not exist on a
given machine; `Container_v1/Stores/` is the stable anchor to validate.

### What appears to work

- The database uses a Core Data-style `Z*` schema, including tables such as
  `ZREMCDREMINDER` and `ZREMCDOBJECT`.
- The database can be queried with `sqlite3` as the local user.
- Community reports say this path exposes sub-reminders and sections that
  AppleScript does not.

### Caveats to validate

- The DB uses WAL and has `-wal` / `-shm` companions.
- `remindd` owns the live store.
- Direct writes are dangerous and out of scope.
- Schema names can shift across macOS versions.
- Tags and sections reportedly are not exposed through EventKit or AppleScript.
- Sandboxed apps may need entitlements; a non-sandboxed local script may not.

### Bottom line from the source notes

For a read-only local sync, direct SQLite access looks plausible and may be the
only path that exposes tags, sections, and sub-reminders. That is exactly what
Phase 0 should now prove on a real machine and in rebalance's actual runtime
contexts.
