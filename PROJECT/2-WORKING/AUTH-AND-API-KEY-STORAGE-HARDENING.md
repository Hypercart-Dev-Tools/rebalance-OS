---
title: "Auth and API Key Storage Hardening Plan"
doc_type: audit + remediation-plan
status: active
owner: Noel Saw
last_updated: 2026-06-20
supersedes:
  - UPGRADE.md  (for future auth-storage design and hardening work; UPGRADE remains the current shipped-operator guide)
  - PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md  (only the config/auth/keyring follow-up slice)
related:
  - UPGRADE.md
  - PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md
  - CHANGELOG.md
  - src/rebalance/ingest/config.py
  - src/rebalance/cli/config_cmds.py
  - src/rebalance/ingest/oauth_common.py
  - src/rebalance/paths.py
---

# Auth and API Key Storage Hardening

| Most recently completed phase | What's next |
|---|---|
| **Phase 1 started (2026-06-20).** The keystone `secret_store` module landed: atomic, permission-enforced (`0600`/`0700`) writes; safe reads that never raise; JSON helpers; a `permission_ok` posture check; and the six-field `ResolverStatus` contract — covered by 11 contract tests ([src/rebalance/ingest/secret_store.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/secret_store.py:1), [tests/test_secret_store.py](/Users/noelsaw/Documents/rebalance-OS/tests/test_secret_store.py:1)). The canonical secret root (a Phase 0 decision) was settled inline: `~/.config/rebalance-os/secrets`. | **Wire integrations to the module.** Route the GitHub/Figma/Sleuth/OAuth loaders through `secret_store` (they still hand-roll file behavior and dual-write to `temp/rbos.config`), add per-integration secret descriptors, and upgrade doctor to report `ResolverStatus` posture. Phase 0's remaining spike items (launchd-safe read proof, JSON-vs-pickle refresh proof) still gate Phase 2's destructive steps. |

## Table of Contents

1. [Status and Supersession](#status-and-supersession)
2. [Trace of the Original Keyring Project](#trace-of-the-original-keyring-project)
3. [What Actually Shipped](#what-actually-shipped)
4. [What Was Deferred or Re-Scoped](#what-was-deferred-or-re-scoped)
5. [How It Currently Works](#how-it-currently-works)
6. [Current Audit Findings](#current-audit-findings)
7. [Target State](#target-state)
8. [Phase 0 - Durability Spike](#phase-0---durability-spike)
9. [Phase 1 - Secret Store Contract and Permission Enforcement](#phase-1---secret-store-contract-and-permission-enforcement)
10. [Phase 2 - Remove Repo-Local Secret Persistence](#phase-2---remove-repo-local-secret-persistence)
11. [Phase 3 - Replace Pickle OAuth Fallback and Stabilize Google OAuth](#phase-3---replace-pickle-oauth-fallback-and-stabilize-google-oauth)
12. [Phase 4 - Unify API Key Resolution and Diagnostics](#phase-4---unify-api-key-resolution-and-diagnostics)
13. [Phase 5 - Migration, Decommissioning, and Docs Cleanup](#phase-5---migration-decommissioning-and-docs-cleanup)
14. [Cross-Phase Risks](#cross-phase-risks)
15. [Definition of Done](#definition-of-done)

## Status and Supersession

Use this document as the source of truth for **future** auth-storage and API-key hardening work.

Pointers back to the older documents:

- [UPGRADE.md](/Users/noelsaw/Documents/rebalance-OS/UPGRADE.md:1) documents the **current shipped operator workflow** for the existing keyring-plus-fallback model.
- [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:229) documents the broader subsystem refactor that absorbed the keyring work and the onboarding/runtime seams around it.
- [CHANGELOG.md](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:641) records the first shipped keyring milestone as `0.31.6`.

This doc supersedes those older docs only for the unresolved follow-up question:
how to move from the currently shipped credential model to a cleaner, more durable, less brittle secret-storage contract.

## Trace of the Original Keyring Project

The original "keyring project" did not vanish. It split into three layers:

1. **Initial ship vehicle: Issue #39 Phase 0**
   Observable result: keyring support landed in `0.31.6`, with GitHub PAT and Calendar OAuth support called out in [CHANGELOG.md](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:645).

2. **Operator adoption vehicle: the upgrade guide**
   Observable result: [UPGRADE.md](/Users/noelsaw/Documents/rebalance-OS/UPGRADE.md:1) reframed the model as "OS keyring primary, launchd fallback secondary" and introduced `rebalance config migrate-to-keyring`.

3. **Stabilization vehicle: subsystem/onboarding refactor**
   Observable result: the config/auth/path work and later `/welcome` onboarding work absorbed the remaining rough edges: resolver centralization, hermetic seams, OAuth status checks, reset enumeration, and launchd/onboarding behavior. See [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:229) and [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:478).

The practical outcome is that the project was **re-scoped**, not abandoned: it became a runtime credential model with migration and onboarding support, but stopped short of fully removing legacy/plaintext fallbacks.

## What Actually Shipped

### Phase-0 / initial keyring ship

- [x] OS keyring integration landed for rebalance secrets.
  Observable result: keyring became the preferred store and was explicitly called out in [CHANGELOG.md](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:645).
- [x] GitHub token resolution became keyring-aware.
  Observable result: runtime order became keyring → config → `gh` CLI, documented in [CHANGELOG.md](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:647) and implemented in [src/rebalance/ingest/config.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/config.py:263).
- [x] Calendar OAuth gained keyring support.
  Observable result: keyring token helpers landed while the existing fallback file was preserved, per [CHANGELOG.md](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:651).
- [x] Doctor started surfacing keyring state.
  Observable result: keyring backend and token source were exposed, per [CHANGELOG.md](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:657).

### Adoption and migration layer

- [x] `rebalance config migrate-to-keyring` shipped.
  Observable result: Calendar pickle, Gmail pickle, and Sleuth env-file migration are handled by [src/rebalance/cli/config_cmds.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/cli/config_cmds.py:626).
- [x] UPGRADE guide was written around the new model.
  Observable result: [UPGRADE.md](/Users/noelsaw/Documents/rebalance-OS/UPGRADE.md:16) documents the current credential table and per-device adoption flow.
- [x] OAuth token-path ownership was centralized.
  Observable result: token-file paths now route through [src/rebalance/paths.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/paths.py:344) instead of ad hoc home-dir strings.

### Refactor and onboarding stabilization

- [x] Config/auth/path resolution was consolidated as a subsystem concern.
  Observable result: the old subsystem plan marks Phase 1 substantially complete in [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:229).
- [x] Hermetic seams were added because keyring and `gh` are machine-global.
  Observable result: the sandbox escape and `gh` fallback findings were closed in [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:515) and [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:533).
- [x] OAuth status checks were fixed to include token files, not just keyring.
  Observable result: this was explicitly called out as a fixed review finding in [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:539).
- [x] Reset learned how to enumerate keyring and OAuth fallback artifacts.
  Observable result: `rebalance reset` covers keyring enumeration plus OAuth token files, per [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:513) and [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:540).

## What Was Deferred or Re-Scoped

- [ ] Plaintext launchd fallbacks were not removed.
  Current state: GitHub, Figma, and Sleuth still intentionally dual-write into `temp/rbos.config` for unattended jobs.
- [ ] Google OAuth pickle fallbacks were not replaced.
  Current state: keyring support shipped, but the existing fallback file remained and is still pickle-based.
- [ ] Permissions were not turned into an enforced contract.
  Current state: presence and source are surfaced more than file mode hygiene.
- [ ] API-key integrations were not brought under the same contract.
  Current state: Anthropic is env-only; Gemini still has its own Secret Manager/env/`gcloud` chain.
- [ ] The UPGRADE guide became the practical source of truth for the shipped model.
  Re-scope consequence: the "keyring project" became "how operators adopt the current model," not "finish hardening the storage contract."

## How It Currently Works

These are the current runtime flows the hardening work is talking about today, before any future cleanup.

### GitHub

GitHub auth resolves keyring first, then `temp/rbos.config`, then `gh auth token` as the last fallback. On a `refresh_index(scope=["github"])` run, rebalance first refreshes `github_pushed_repos`, then scans the authenticated user's GitHub Events feed for recent activity, currently capped by GitHub's own Events API shape: up to 3 pages and roughly 30 days of history. That activity rollup is written to `github_activity`, while a second per-repo artifact pass syncs issues, PRs, comments, commits, checks, and documents for the watched repo set. Those artifact documents are then embedded into the GitHub semantic corpus, so GitHub currently has both a lightweight activity layer and a deeper artifact layer.

### Gmail

Gmail runs in one of two modes: `oauth` or `mcp`. In `oauth` mode, rebalance loads a desktop OAuth token from keyring with a launchd-safe fallback token file, fetches the newest 100 messages matching `gmail_query_filter` (default `in:inbox`), and stores metadata plus Gmail's snippet into `email_messages`; the collector does not parse MIME bodies yet. In `mcp` mode, the scheduled job does nothing and an agent is expected to ingest messages through the Gmail MCP connector instead. Email also participates in the unified semantic index, but only through the stored metadata/snippet layer today.

### Google Calendar

Google Calendar uses desktop OAuth with keyring as the interactive primary and a fallback token file for launchd. A refresh syncs the operator's own calendar plus any configured teammate calendars, usually over a 30-day-back and 7-day-forward window, and upserts rows into `calendar_events`. The operator's own calendar is normalized under the canonical operator calendar id so downstream reads/export paths stay consistent. Events are kept as historical records; rebalance does not auto-delete old calendar rows during sync.

### Figma

Figma is opt-in and file-scoped rather than account-feed scoped. Rebalance reads a Figma PAT from keyring or `temp/rbos.config`, reads an explicit `figma_file_keys` allow-list from config, then fetches comments for each listed file via the Figma comments endpoint. Comments are upserted into `figma_comments` by `file_key:comment_id`, so history is preserved and changed or resolved comments become updates instead of duplicates. Figma comments also feed the unified semantic index through the registry-driven semantic-docs path.

### Sleuth Tasks

Sleuth sync resolves credentials from keyring, then `temp/rbos.config`, then the legacy env-file path; in practice the preferred production mode is now a local published-file source in the git-pulse repo rather than a live API call. A refresh reads the reminders payload, normalizes it into structured reminder rows, and upserts into `sleuth_reminders` by `reminder_id`. When the full sync path runs with `active_only=False`, reminders that disappear from the upstream active set are not deleted; they are retired to a stale/inactive state so the history remains auditable. That means Sleuth currently behaves more like a structured task mirror with preserved lifecycle history than a destructive replace-everything sync.

## Current Audit Findings

### High-severity findings

1. `temp/rbos.config` is still a secret-bearing store, not just non-secret operator config.
   Observable evidence:
   [src/rebalance/ingest/config.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/config.py:4) describes `temp/rbos.config` as non-secret config, while [src/rebalance/ingest/config.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/config.py:111), [src/rebalance/ingest/config.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/config.py:304), [src/rebalance/ingest/config.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/config.py:419), and [src/rebalance/ingest/config.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/config.py:1342) still persist live secrets there.

2. Current on-disk permissions are too broad on Noel's machine.
   Observed on 2026-06-20:
   `temp/rbos.config` = `0644`
   `~/.config/rebalance-os/config.json` = `0644`
   `~/.config/rebalance-os/google-calendar-oauth` = `0644`
   `~/.config/rebalance-os/google-gmail-oauth` = `0644`
   `~/secrets/google-calendar.env` = `0644`
   `~/.config/rebalance-os/` = `0755`
   `~/secrets/` = `0755`

3. GitHub PAT storage is durable for launchd but brittle for secret hygiene.
   It is deliberately stored in both keyring and repo-local config, so a live PAT can persist in plaintext inside a repo checkout.

4. Sleuth and Figma inherit the same plaintext fallback problem.
   Sleuth stores a full credential bundle in config; Figma PAT uses the same dual-store pattern as GitHub.

### Medium-severity findings

1. Gmail and Calendar fallback tokens use pickle, not a data-only format.
   That is durable enough for local unattended use, but it is a poor long-term contract because deserialization is code-executing, opaque, and hard to inspect safely.

2. Google OAuth setup is still "file first, keyring second."
   The setup scripts write the fallback token file first; keyring adoption happens later through `migrate-to-keyring`.

3. Google OAuth client ownership is centralized but operationally brittle.
   Gmail and Calendar share one embedded installed-app client. That is acceptable from a secrecy perspective, but it creates one shared dependency for onboarding and re-auth.

4. LLM provider keys are fragmented.
   Anthropic is env-only. Gemini resolves through Secret Manager, env vars, then `gcloud`. There is no single durable per-machine contract equivalent to the other integrations.

5. Permission checks are mostly advisory, not enforced.
   The code writes files but does not harden mode to `0600` or directories to `0700`, and doctor reports presence more than posture.

## Target State

The target storage contract is:

- `temp/rbos.config` contains no secrets, tokens, OAuth blobs, or API keys.
- Keyring remains the interactive primary store. Every durable local *fallback* secret lives outside the repo in one user-level secret root owned by rebalance — this root replaces the repo-local plaintext and pickle fallbacks, **not** keyring itself.
- Every secret file and token file is written atomically with enforced `0600` file mode and `0700` directory mode.
- Google OAuth fallback uses JSON authorized-user blobs, not pickle.
- Every integration exposes one structured resolver contract, delivered as a concrete status object by a phase (Phase 1 for auth, Phase 4 for API keys):
  `source`, `primary_store`, `fallback_store`, `launchd_safe`, `last_validated_at`, `permission_ok`.
- Auth-activity logging and per-token metadata are preserved: every new write, migration, and refresh still records to `temp/logs/auth_activity.jsonl` and `temp/logs/token_meta.json` (fingerprint-only, `first_added_at` retained), matching the shipped contract in [UPGRADE.md](/Users/noelsaw/Documents/rebalance-OS/UPGRADE.md:36).
- Every secret-store migration is idempotent — safe to re-run with no duplicate side effects, matching today's `migrate-to-keyring` ([UPGRADE.md](/Users/noelsaw/Documents/rebalance-OS/UPGRADE.md:132)).
- Doctor fails loudly on insecure file modes, deprecated stores, or unresolved migrations — and distinguishes `optional+unconfigured` (clean skip, no warning) from `configured+broken/insecure` (warn/fail).
- Migration is additive first, destructive last — a **hard gate, not a guideline**: no phase removes a fallback before its replacement is proven for both interactive and unattended (launchd) reads.

## Phase 0 - Durability Spike

Goal: prove the replacement contract before broad refactoring.

- [ ] Prove a launchd-safe GitHub auth path that does not persist the PAT in `temp/rbos.config`.
  Observable result: one working prototype store under a user-level non-repo path; interactive + unattended reads both succeed.
- [ ] Prove Gmail and Calendar collectors can read a JSON fallback token file instead of pickle.
  Observable result: one local prototype loader that reads JSON, refreshes access tokens, and persists refreshed JSON.
- [ ] Prove permission hardening is reliable on write.
  Observable result: files created by the prototype land at `0600`; directories land at `0700`; tests verify mode correction.
- [ ] Decide the canonical secret root.
  Observable result: one documented path contract, either under `~/.config/rebalance-os/` or app-data, with explicit reasoning about portability and launchd.

### QA Checklist

- [ ] Happy-path prototype works for one PAT-based integration and one Google OAuth integration.
- [ ] Prototype survives process restart and system reboot.
- [ ] Prototype works with keyring available and with keyring unavailable.
- [ ] Tests cover bad file mode, missing file, corrupt file, and token refresh.
- [ ] Spike report names the exact migration path and the exact blockers, if any.

## Phase 1 - Secret Store Contract and Permission Enforcement

Goal: create the single runtime contract before moving data.

**Status (2026-06-20):** keystone module landed and tested; integration wiring + doctor posture still pending. The file primitive (root resolution, atomic writes, `0600`/`0700` enforcement, safe reads, `ResolverStatus`) is done — what remains is making the existing loaders *call* it and surfacing posture in doctor.

- [~] Introduce one secret-storage module that owns:
  secret root resolution, atomic writes, permission enforcement, safe reads, source labeling, and migration helpers.
  Observable result: GitHub/Figma/Sleuth/OAuth loaders call the same storage primitives instead of hand-rolling file behavior.
  Progress: module + primitives shipped in [src/rebalance/ingest/secret_store.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/secret_store.py:1) (migration helpers + loader wiring still to come; loaders do not yet call it).
- [ ] Route auth-activity and token-metadata writes through the storage module.
  Observable result: every secret write still appends to `temp/logs/auth_activity.jsonl` and updates `temp/logs/token_meta.json` (fingerprint-only, `first_added_at` preserved), so the observability shipped in [UPGRADE.md](/Users/noelsaw/Documents/rebalance-OS/UPGRADE.md:36) survives the storage migration.
- [ ] Add explicit secret descriptors per integration.
  Observable result: each credential declares primary store, fallback store, serialization format, and validation hook in one place.
- [ ] Emit one structured resolver-status object per integration with the full field set.
  Observable result: each resolver returns `source`, `primary_store`, `fallback_store`, `launchd_safe`, `last_validated_at`, and `permission_ok` — the complete Target State contract, not a subset. (Phase 4 extends the same shape to API keys.)
- [ ] Enforce file and directory mode on every write.
  Observable result: storage writers call one helper that creates dirs with `0700` and files with `0600`.
- [ ] Upgrade doctor to check posture, not just presence.
  Observable result: doctor reports source, path, permissions, deprecated-store usage, and migration-needed state — and distinguishes `optional+unconfigured` (clean skip) from `configured+broken/insecure` (warn/fail).
- [ ] Add contract tests for storage invariants.
  Observable result: tests fail if a new write path stores secrets in repo-local config or writes insecure modes.

### QA Checklist

- [ ] New tests cover every storage primitive directly.
- [ ] Doctor surfaces an insecure mode as WARN or FAIL, not OK.
- [ ] Launchd-safe fallback still resolves when keyring is unavailable.
- [ ] No runtime code outside the storage module writes secret-bearing files directly.
- [ ] CI includes a contract test that forbids secret keys in `temp/rbos.config`.
- [ ] Storage module, resolver-status, and doctor checks are testable under hermetic seams — no test reads machine-global keyring/`gh`/file tokens unless it opts in (preserves the seams closed in [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:524)).
- [ ] The resolver-status object returns all six fields for every integration.
- [ ] Auth-activity / token-meta writes are exercised by tests (fingerprint-only, `first_added_at` retained on re-write).

## Phase 2 - Remove Repo-Local Secret Persistence

Goal: make `temp/rbos.config` truly non-secret.

**Gate (hard):** this phase may stop repo-local secret writes only after Phase 0/1 have proven the new store resolves on both interactive and unattended (launchd) reads. Additive first — the new store is written and proven before any old key is deleted.

- [ ] Remove GitHub PAT writes to `temp/rbos.config`.
  Observable result: `set_github_token()` writes to the new secret store; `rbos.config` no longer receives `github_token`.
- [ ] Remove Figma PAT writes to `temp/rbos.config`.
  Observable result: `figma_token` migrates to the new store; `figma_file_keys` remains plain config.
- [ ] Remove Sleuth credential writes to `temp/rbos.config`.
  Observable result: `sleuth_web_api` leaves repo-local config entirely; file-source mode remains supported without a token.
- [ ] Add explicit migration command(s) for secret-bearing config keys.
  Observable result: one migration command lifts secrets out of `temp/rbos.config`, verifies the new location, then deletes the old keys. The command is idempotent — safe to re-run, reporting "already migrated ✓" with no duplicate side effects.
- [ ] Add a repo-local config linter or doctor check.
  Observable result: presence of secret-looking keys in `temp/rbos.config` is surfaced as a failure.
- [ ] Update operator docs in this same phase.
  Observable result: UPGRADE and README credential tables reflect the new GitHub/Figma/Sleuth storage location the moment the behavior changes — not deferred to Phase 5 (per the same-phase doc rule in [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:181)).

### QA Checklist

- [ ] Existing machines auto-migrate without losing auth.
- [ ] A repo checkout can be copied or archived without carrying credentials.
- [ ] launchd jobs still authenticate after migration.
- [ ] Tests verify `temp/rbos.config` stays secret-free after each setter runs.
- [ ] Figma and Sleuth opt-in paths still work after migration.
- [ ] Re-running the migration command is a no-op (idempotency test).
- [ ] UPGRADE/README credential tables are updated in this phase, not Phase 5.

## Phase 3 - Replace Pickle OAuth Fallback and Stabilize Google OAuth

Goal: make Google OAuth durable without pickle or ambiguous ownership.

- [ ] Replace pickle fallback files with JSON authorized-user token files.
  Observable result: `setup_calendar_oauth.py`, `setup_gmail_oauth.py`, and `oauth_common.py` no longer use `pickle.dump` / `pickle.load`.
- [ ] Make setup scripts write both durable stores in one pass.
  Observable result: after a successful browser consent, keyring and JSON fallback are both current; no follow-up migrate step is required for the happy path.
- [ ] Add versioned migration from legacy pickle files.
  Observable result: old token files are read once, converted to JSON, validated, and retired. The conversion is idempotent — re-running finds JSON already present and does not re-import or duplicate.
- [ ] Preserve auth-activity logging across OAuth conversion and refresh.
  Observable result: pickle→JSON migration and every token refresh still record to `auth_activity.jsonl` / `token_meta.json`, so Google-token lifetime stays measurable.
- [ ] Decide the future of the embedded shared Google client.
  Observable result: one explicit policy:
  keep it as the supported default, or support user-provided client config as the primary path and demote the embedded client to fallback/dev use.
- [ ] Harden Google auth diagnostics.
  Observable result: doctor tells the user whether the active Google token came from keyring, JSON fallback, migrated pickle, or an expired/invalid state.
- [ ] Update Google OAuth docs in this same phase.
  Observable result: GMAIL and GOOGLE_CALENDAR docs describe the JSON fallback (not pickle) when the behavior changes, not in Phase 5.

### QA Checklist

- [ ] Re-auth works without a second manual migration step.
- [ ] Refreshed access tokens persist back to JSON and keyring.
- [ ] Corrupt JSON fallback produces a clean remediation path.
- [ ] Legacy pickle migration is covered by tests.
- [ ] Legacy pickle migration is idempotent (re-run is a no-op).
- [ ] A token refresh still appends to `auth_activity.jsonl` / `token_meta.json`.
- [ ] No runtime path still imports `pickle` for OAuth token storage.

## Phase 4 - Unify API Key Resolution and Diagnostics

Goal: give API-key integrations the same durability contract as auth integrations.

- [ ] Decide which API keys should remain env-only and which need durable local storage.
  Observable result: explicit per-provider policy for Anthropic, Gemini, and any future LLM/provider keys.
- [ ] Wrap Gemini resolution behind the same source-reporting contract.
  Observable result: callers receive the full resolver-status shape from Phase 1 (`source`, `primary_store`, `fallback_store`, `launchd_safe`, `last_validated_at`, `permission_ok`) with a source label such as `secret-manager-sdk`, `env`, `gcloud`, or `local-secret-store` — not just a value.
- [ ] Add optional durable local storage for scheduled or unattended API-key use.
  Observable result: launchd-safe use does not depend on an operator shell environment unless policy explicitly says env-only.
- [ ] Define an explicit per-provider doctor policy.
  Observable result: doctor distinguishes `optional+unconfigured` (e.g. Figma, or an env-only provider with no key set — clean skip, no warning, per [UPGRADE.md](/Users/noelsaw/Documents/rebalance-OS/UPGRADE.md:94)) from `configured+broken/insecure` (warn/fail), so posture checks do not turn opt-in integrations into noise.
- [ ] Expose API-key posture in doctor.
  Observable result: doctor names the source and durability of each provider key, not just whether a value exists.
- [ ] Remove surprising ambient fallbacks where policy says explicit config is required.
  Observable result: hidden dependency on whatever `gcloud` account happens to be active is either surfaced clearly or removed.
- [ ] Update provider docs in this same phase.
  Observable result: per-provider key docs match the shipped resolver order when Phase 4 lands, not in Phase 5.

### QA Checklist

- [ ] Tests cover env-only, local-store, Secret Manager, and missing-key paths.
- [ ] Doctor output includes source labels for LLM/API keys.
- [ ] A background job can use the intended provider key without an interactive shell.
- [ ] Gemini does not silently switch sources without an observable status signal.
- [ ] Provider-specific docs match the shipped resolver order.

## Phase 5 - Migration, Decommissioning, and Docs Cleanup

Goal: remove legacy paths only after the new contract is proven in the field.

**Gate (hard):** legacy reads may be removed only after the migration report is clean, doctor is green, and both fresh and migrated launchd paths are proven end-to-end.

- [ ] Add one migration report command.
  Observable result: operators can see which credentials are still in legacy locations and what will be moved.
- [ ] Decommission secret-bearing config keys from runtime reads.
  Observable result: runtime no longer reads `github_token`, `figma_token`, or `sleuth_web_api` from `temp/rbos.config`.
- [ ] Decommission OAuth pickle fallback reads.
  Observable result: runtime no longer reads `google-calendar-oauth` or `google-gmail-oauth` as pickle files.
- [ ] Final operator-doc consistency sweep (removal-only).
  Observable result: the per-phase doc updates (Phases 2–4) are already landed; this phase only confirms README, UPGRADE, GMAIL, GOOGLE_CALENDAR, and onboarding docs are mutually consistent and adds the "legacy store removed" notes.
- [ ] Add regression tests for "no secrets in repo-local config."
  Observable result: CI fails if a future change reintroduces secret persistence into the repo tree.

### QA Checklist

- [ ] A fresh machine can complete onboarding with only the documented steps.
- [ ] An upgraded machine can migrate without manual file surgery.
- [ ] Docs, doctor, and runtime report the same storage contract.
- [ ] `rebalance reset` enumerates and removes the new secret locations correctly.
- [ ] Legacy stores are readable during migration and unread after decommissioning.

## Cross-Phase Risks

- The main availability risk is breaking unattended launchd jobs while improving secret hygiene.
- The main migration risk is losing a refresh token during Google OAuth conversion.
- The main UX risk is forcing users through more steps than the current setup flow.
- The main contract risk is fixing GitHub/Figma/Sleuth but leaving API-key sources fragmented.

Mitigation rules:

- additive migration first, removal second — a **hard gate**: no fallback is removed before its replacement is proven for both interactive and unattended (launchd) reads
- one integration proven end-to-end before widening rollout
- explicit doctor checks before deleting legacy paths
- docs updated in the same phase that changes operator behavior (per [PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:181))
- contract tests that fail CI on secret regressions

## Definition of Done

- [ ] No live credential is intentionally persisted under the repo root.
- [ ] `temp/rbos.config` is truly non-secret.
- [ ] All durable secret files are outside the repo with enforced `0600` / `0700` permissions.
- [ ] Google OAuth fallback is JSON-based, not pickle-based.
- [ ] Doctor reports source, durability, and posture for every auth and API-key integration.
- [ ] Each integration's resolver exposes the full six-field status contract; doctor distinguishes `optional+unconfigured` from `configured+broken/insecure`.
- [ ] Auth-activity logging and per-token metadata survive every migration, JSON conversion, and refresh.
- [ ] Every secret-store migration is idempotent (safe to re-run).
- [ ] Fresh install and migrated install both work with the documented steps.
- [ ] CI includes contract coverage for storage location, permissions, and migration behavior.
