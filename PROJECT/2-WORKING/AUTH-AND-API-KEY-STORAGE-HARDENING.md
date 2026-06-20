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
| **Trace + audit complete (2026-06-20).** The original keyring project shipped as a keyring-primary credential model with launchd-safe fallbacks, migration tooling, doctor coverage, hermetic test seams, and reset support. It did **not** finish the harder hardening work: repo-local plaintext fallbacks remain, Google OAuth still uses pickle fallbacks, permissions are not enforced, and API-key handling is still fragmented. | **Phase 0 - durability spike.** Prove a launchd-safe replacement for repo-local plaintext secret fallback, and prove JSON OAuth fallback can replace pickle without breaking refresh or unattended jobs. |

## Table of Contents

1. [Status and Supersession](#status-and-supersession)
2. [Trace of the Original Keyring Project](#trace-of-the-original-keyring-project)
3. [What Actually Shipped](#what-actually-shipped)
4. [What Was Deferred or Re-Scoped](#what-was-deferred-or-re-scoped)
5. [Current Audit Findings](#current-audit-findings)
6. [Target State](#target-state)
7. [Phase 0 - Durability Spike](#phase-0---durability-spike)
8. [Phase 1 - Secret Store Contract and Permission Enforcement](#phase-1---secret-store-contract-and-permission-enforcement)
9. [Phase 2 - Remove Repo-Local Secret Persistence](#phase-2---remove-repo-local-secret-persistence)
10. [Phase 3 - Replace Pickle OAuth Fallback and Stabilize Google OAuth](#phase-3---replace-pickle-oauth-fallback-and-stabilize-google-oauth)
11. [Phase 4 - Unify API Key Resolution and Diagnostics](#phase-4---unify-api-key-resolution-and-diagnostics)
12. [Phase 5 - Migration, Decommissioning, and Docs Cleanup](#phase-5---migration-decommissioning-and-docs-cleanup)
13. [Cross-Phase Risks](#cross-phase-risks)
14. [Definition of Done](#definition-of-done)

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
- Every durable local secret lives outside the repo in one user-level secret root owned by rebalance.
- Every secret file and token file is written atomically with enforced `0600` file mode and `0700` directory mode.
- Google OAuth fallback uses JSON authorized-user blobs, not pickle.
- Every integration exposes one structured resolver contract:
  `source`, `primary_store`, `fallback_store`, `launchd_safe`, `last_validated_at`, `permission_ok`.
- Doctor fails loudly on insecure file modes, deprecated stores, or unresolved migrations.
- Migration is additive first, destructive last: legacy stores remain readable until the new path is proven, then get removed explicitly.

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

- [ ] Introduce one secret-storage module that owns:
  secret root resolution, atomic writes, permission enforcement, safe reads, source labeling, and migration helpers.
  Observable result: GitHub/Figma/Sleuth/OAuth loaders call the same storage primitives instead of hand-rolling file behavior.
- [ ] Add explicit secret descriptors per integration.
  Observable result: each credential declares primary store, fallback store, serialization format, and validation hook in one place.
- [ ] Enforce file and directory mode on every write.
  Observable result: storage writers call one helper that creates dirs with `0700` and files with `0600`.
- [ ] Upgrade doctor to check posture, not just presence.
  Observable result: doctor reports source, path, permissions, deprecated-store usage, and migration-needed state.
- [ ] Add contract tests for storage invariants.
  Observable result: tests fail if a new write path stores secrets in repo-local config or writes insecure modes.

### QA Checklist

- [ ] New tests cover every storage primitive directly.
- [ ] Doctor surfaces an insecure mode as WARN or FAIL, not OK.
- [ ] Launchd-safe fallback still resolves when keyring is unavailable.
- [ ] No runtime code outside the storage module writes secret-bearing files directly.
- [ ] CI includes a contract test that forbids secret keys in `temp/rbos.config`.

## Phase 2 - Remove Repo-Local Secret Persistence

Goal: make `temp/rbos.config` truly non-secret.

- [ ] Remove GitHub PAT writes to `temp/rbos.config`.
  Observable result: `set_github_token()` writes to the new secret store; `rbos.config` no longer receives `github_token`.
- [ ] Remove Figma PAT writes to `temp/rbos.config`.
  Observable result: `figma_token` migrates to the new store; `figma_file_keys` remains plain config.
- [ ] Remove Sleuth credential writes to `temp/rbos.config`.
  Observable result: `sleuth_web_api` leaves repo-local config entirely; file-source mode remains supported without a token.
- [ ] Add explicit migration command(s) for secret-bearing config keys.
  Observable result: one migration command lifts secrets out of `temp/rbos.config`, verifies the new location, then deletes the old keys.
- [ ] Add a repo-local config linter or doctor check.
  Observable result: presence of secret-looking keys in `temp/rbos.config` is surfaced as a failure.

### QA Checklist

- [ ] Existing machines auto-migrate without losing auth.
- [ ] A repo checkout can be copied or archived without carrying credentials.
- [ ] launchd jobs still authenticate after migration.
- [ ] Tests verify `temp/rbos.config` stays secret-free after each setter runs.
- [ ] Figma and Sleuth opt-in paths still work after migration.

## Phase 3 - Replace Pickle OAuth Fallback and Stabilize Google OAuth

Goal: make Google OAuth durable without pickle or ambiguous ownership.

- [ ] Replace pickle fallback files with JSON authorized-user token files.
  Observable result: `setup_calendar_oauth.py`, `setup_gmail_oauth.py`, and `oauth_common.py` no longer use `pickle.dump` / `pickle.load`.
- [ ] Make setup scripts write both durable stores in one pass.
  Observable result: after a successful browser consent, keyring and JSON fallback are both current; no follow-up migrate step is required for the happy path.
- [ ] Add versioned migration from legacy pickle files.
  Observable result: old token files are read once, converted to JSON, validated, and retired.
- [ ] Decide the future of the embedded shared Google client.
  Observable result: one explicit policy:
  keep it as the supported default, or support user-provided client config as the primary path and demote the embedded client to fallback/dev use.
- [ ] Harden Google auth diagnostics.
  Observable result: doctor tells the user whether the active Google token came from keyring, JSON fallback, migrated pickle, or an expired/invalid state.

### QA Checklist

- [ ] Re-auth works without a second manual migration step.
- [ ] Refreshed access tokens persist back to JSON and keyring.
- [ ] Corrupt JSON fallback produces a clean remediation path.
- [ ] Legacy pickle migration is covered by tests.
- [ ] No runtime path still imports `pickle` for OAuth token storage.

## Phase 4 - Unify API Key Resolution and Diagnostics

Goal: give API-key integrations the same durability contract as auth integrations.

- [ ] Decide which API keys should remain env-only and which need durable local storage.
  Observable result: explicit per-provider policy for Anthropic, Gemini, and any future LLM/provider keys.
- [ ] Wrap Gemini resolution behind the same source-reporting contract.
  Observable result: callers receive not just a value but a source label such as `secret-manager-sdk`, `env`, `gcloud`, or `local-secret-store`.
- [ ] Add optional durable local storage for scheduled or unattended API-key use.
  Observable result: launchd-safe use does not depend on an operator shell environment unless policy explicitly says env-only.
- [ ] Expose API-key posture in doctor.
  Observable result: doctor names the source and durability of each provider key, not just whether a value exists.
- [ ] Remove surprising ambient fallbacks where policy says explicit config is required.
  Observable result: hidden dependency on whatever `gcloud` account happens to be active is either surfaced clearly or removed.

### QA Checklist

- [ ] Tests cover env-only, local-store, Secret Manager, and missing-key paths.
- [ ] Doctor output includes source labels for LLM/API keys.
- [ ] A background job can use the intended provider key without an interactive shell.
- [ ] Gemini does not silently switch sources without an observable status signal.
- [ ] Provider-specific docs match the shipped resolver order.

## Phase 5 - Migration, Decommissioning, and Docs Cleanup

Goal: remove legacy paths only after the new contract is proven in the field.

- [ ] Add one migration report command.
  Observable result: operators can see which credentials are still in legacy locations and what will be moved.
- [ ] Decommission secret-bearing config keys from runtime reads.
  Observable result: runtime no longer reads `github_token`, `figma_token`, or `sleuth_web_api` from `temp/rbos.config`.
- [ ] Decommission OAuth pickle fallback reads.
  Observable result: runtime no longer reads `google-calendar-oauth` or `google-gmail-oauth` as pickle files.
- [ ] Update all operator docs.
  Observable result: README, UPGRADE, GMAIL, GOOGLE_CALENDAR, and onboarding docs state one accurate storage model.
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

- additive migration first, removal second
- one integration proven end-to-end before widening rollout
- explicit doctor checks before deleting legacy paths
- contract tests that fail CI on secret regressions

## Definition of Done

- [ ] No live credential is intentionally persisted under the repo root.
- [ ] `temp/rbos.config` is truly non-secret.
- [ ] All durable secret files are outside the repo with enforced `0600` / `0700` permissions.
- [ ] Google OAuth fallback is JSON-based, not pickle-based.
- [ ] Doctor reports source, durability, and posture for every auth and API-key integration.
- [ ] Fresh install and migrated install both work with the documented steps.
- [ ] CI includes contract coverage for storage location, permissions, and migration behavior.
