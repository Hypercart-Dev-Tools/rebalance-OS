---
title: "Unified Front-Door, Portability, and Auth Hardening Plan"
doc_type: audit-remediation-plan
status: active
owner: Noel Saw
created: 2026-06-21
updated: 2026-06-21
goal: >
  Close the remaining front-door, portability, and auth-hardening contract gaps in
  dependency order — runtime contract first, then verification, then doc truthfulness
  and onboarding — leaving one canonical active plan for this area.
supersedes:
  - PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md
  - PROJECT/4-MISC/COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md
  - PROJECT/4-MISC/AUTH-AND-API-KEY-STORAGE-HARDENING.md
related:
  - README.md
  - UPGRADE.md
  - GMAIL.md
  - GOOGLE_CALENDAR.md
  - ARCHITECTURE.md
  - ROADMAP.md
  - src/rebalance/ingest/index_ops.py
  - src/rebalance/ingest/secret_store.py
  - src/rebalance/paths.py
  - src/rebalance/doctor.py
---

# Unified Front-Door, Portability, and Auth Hardening

| Most recently completed phase | What's next |
|---|---|
| **Phase 6 complete — all six phases shipped (2026-06-21).** ROADMAP now points only to this unified plan as the single active ledger entry, reflecting Phases 1–6 done; the three source plans are retained with verified supersession breadcrumbs. Per the ponytail-lite, the doc-reorg (inventory/relocate/re-hub) was cut — it risked breaking path-based loaders to tidy sprawl no newcomer hits. **The plan is code- and doc-complete.** | **Operator-only follow-up:** run `rebalance config migrate-secrets` on the ~2 remaining Macs (Phase 1 item 6), under the verify-then-cutover gate. Everything else is the deferred multi-operator / fleet scope, revived on its named triggers. |

## Table of Contents

1. [Background](#background)
2. [Why One Unified Plan](#why-one-unified-plan)
3. [Scope and Sequencing Rules](#scope-and-sequencing-rules)
4. [Phase 1 - Runtime Contract Closure](#phase-1---runtime-contract-closure)
5. [Phase 2 - Contract Tests, CI, and Observability](#phase-2---contract-tests-ci-and-observability)
6. [Phase 3 - Canonical Doc Truthfulness](#phase-3---canonical-doc-truthfulness)
7. [Phase 4 - Install-Path Clarity and Front-Door Guidance](#phase-4---install-path-clarity-and-front-door-guidance)
8. [Phase 5 - Google Consumption Path Clarity](#phase-5---google-consumption-path-clarity)
9. [Phase 6 - Documentation Surface Cleanup and Canonicalization](#phase-6---documentation-surface-cleanup-and-canonicalization)
10. [Cross-Phase Risks](#cross-phase-risks)
11. [Definition of Done](#definition-of-done)

## Background

These three plans were written for different slices of the same operator journey:

- the collector/portability audit established the write-side architecture and exposed the remaining runtime-contract gaps
- the auth hardening plan changed where secrets live and how OAuth fallback works
- the front-door audit found that the onboarding/docs surface drifted behind those code changes

Taken separately, they now create more coordination cost than clarity. The remaining work is no longer three independent efforts. It is one sequence:

1. finish the runtime and storage contract edges
2. prove the contract with tests and CI
3. make the docs and onboarding path tell the truth about the shipped behavior
4. clean up the remaining documentation surface so there is one canonical active plan

## Why One Unified Plan

- The three docs now share the same failure modes: launchd breakage, stale credential docs, resolver drift, and onboarding ambiguity.
- The front-door fixes depend on the auth/runtime contract being stable first; otherwise README cleanup just chases moving behavior.
- QA is duplicated across the old docs. One merged plan lets each check happen once, in the phase where it is actually decisive.
- ROADMAP should point at one active project doc for this area, not three partially overlapping ones.

## Scope and Sequencing Rules

This unified plan carries forward only the remaining work that is still open or partial.

Already complete and therefore not re-opened here:

- collector taxonomy split, `all` semantics, and source/job classification
- source-owned helper extraction across MCP/CLI/scheduler surfaces
- semantic stage as the single writer on the collector path
- secret-store introduction, repo-local secret removal, and JSON OAuth fallback

Still deferred and therefore not promoted into active phases here. Each carries the revive-when signal from its source plan so a deferral can be reopened without re-deriving it:

- full multi-operator / fleet migration ceremony (migration-report command + staged decommission gate) — **revive when** more than a handful of machines need a coordinated, auditable migration.
- per-integration six-field resolver registry wiring (the `source` / `primary_store` / `fallback_store` / `launchd_safe` / `last_validated_at` / `permission_ok` descriptor layer) — **revive when** a second operator, or a CI/fleet audit, needs a uniform machine-readable credential-posture report.
- broad API-key contract unification beyond the current auth integrations (the deferred Phase 4 Gemini/Anthropic resolver work; Anthropic is already env-only, the correct contract) — **revive when** a provider key must be rotated centrally across machines, or a third LLM provider arrives with its own resolution chain.
- building Calendar host-connector ingestion; only the spec/doc position is active here — **revive when** a user asks for Claude-Desktop Calendar consumption, or Gmail `mcp` mode proves the pattern in the field.

Sequencing rule:

- runtime contract first
- verification second
- docs and onboarding only after the runtime story is stable
- repo-surface cleanup last

On the `ponytail (lite)` callouts in Phases 3–6: each names a lazier scope the implementer should weigh — **a recommended default, not a cut already applied**. The phase checklists deliberately still carry full scope; the decision to trim or keep each item is made at build time, in the phase where the work happens. The callout is therefore guidance sitting alongside the bullets, not a contradiction with them.

## Phase 1 - Runtime Contract Closure

Goal: close the remaining collector/auth contract gaps before expanding doc cleanup or onboarding guidance.

- [x] Collapse each raw incoming source onto one clearly canonical source-owned write path.
  Observable result: no raw source still has multiple competing user-facing write paths pretending to be equal; the one true source-owned path is explicit for vault, github, calendar, sleuth, email, and figma.
  Done (2026-06-21, verify): each source is registered as one `Collector` via `register_collector` and dispatched through the single `refresh_index` entry point (`src/rebalance/ingest/index_ops.py:92-116,1428-1451`); no competing write path remains.
- [x] Align semantic-maintenance CLI semantics with the live `semantic` stage contract.
  Observable result: maintenance commands such as `--source all` match the same semantic-capable source set the runtime stage actually processes; no stage/CLI drift remains.
  Done (2026-06-21): `normalize_sources` now derives its legal set from `_all_semantic_sources()` (the single runtime source-of-truth) instead of a hand-maintained literal that wrongly accepted non-semantic `calendar`/`sleuth` (`src/rebalance/ingest/semantic_index.py:130-143`). Guarded by `tests/test_semantic_source_contract.py`.
- [x] Finish runtime resolver cleanup in setup scripts and script bootstraps.
  Observable result: the remaining offenders are named and closed one by one — the OAuth setup scripts (`scripts/setup_calendar_oauth.py`, `scripts/setup_gmail_oauth.py`), the scheduler bootstraps (`scripts/*sync.sh`), and any residual `sys.path.insert` / repo-root shim. Each either routes through the shared resolver (`resolve_project_root` / `resolve_oauth_token_path`) or carries a one-line comment stating why it cannot, so "where applicable" is enumerated rather than left open.
  Done (2026-06-21, verify): the only `sys.path.insert` is the documented single exception in `scripts/_bootstrap.py:18`; no `parents[N]` repo-root walks remain; all five `*sync.sh` route through `scripts/lib/scheduler_common.sh`, which derives `REBALANCE_DIR` from its own file location (no hardcoded path); setup scripts import from `rebalance.ingest` and write via `secret_store` with no hardcoded `/Users/` or retired pickle/credentials paths.
- [x] Route auth-activity and token-metadata writes through the storage contract.
  Observable result: secret-store writes, migrations, OAuth refreshes, and future storage changes all preserve `auth_activity.jsonl` and `token_meta.json` behavior through one contract.
  Done (2026-06-21, verify): `auth_activity.jsonl` is written only by `src/rebalance/ingest/auth_log.py`; `token_meta.json` only by `src/rebalance/ingest/token_meta.py`. All callers (config OAuth/PAT writes, doctor reads) route through those module APIs — every other repo reference is a docstring or user-facing echo.
- [x] Complete doctor posture coverage for active auth integrations.
  Observable result: doctor distinguishes `optional+unconfigured` from `configured+broken/insecure`, and reports the active source/posture for the shipped auth flows without requiring the deferred descriptor registry.
  Done (2026-06-21): added `_check_figma` (`src/rebalance/doctor.py`) — the last uncovered active source. Unconfigured = clean skip (OK), half-configured (token without files, or files without token) = WARN, configured = OK with resolved source + file count. Already surfaced a real prior-silent failure on the primary Mac (file key set, no token). GitHub/Sleuth/Gmail/Calendar posture was already covered. Tested in `tests/test_doctor.py`.
- [ ] Finish the per-machine secret-store migration on the remaining operator Macs (operator action, carried over from the auth-hardening plan), under the source plan's hard verify-then-cutover gate.
  **Remaining (operator-only):** cannot be driven from a dev session — needs interactive runs on the ~2 outstanding Macs.
  Observable result: on each remaining Mac (~2 outstanding as of 2026-06-21) `rebalance config migrate-secrets` (a) writes GitHub/Sleuth/Figma and Google OAuth to keyring + secret store, (b) proves both interactive *and* unattended (launchd) reads resolve from the new store on that machine, and only then (c) stops reading the live secret from `temp/rbos.config`. A release-wide cutover before per-machine verification is rejected — legacy `rbos.config` reads stay available on every un-migrated Mac so launchd is never locked out. This is the single-operator equivalent of the deferred fleet-decommission ceremony, not part of it.

### QA Checklist

- [x] Each raw source has one documented and testable source-owned write path.
- [x] Semantic-maintenance commands and the live `semantic` stage produce the same source coverage. (`tests/test_semantic_source_contract.py`)
- [x] No remaining setup/runtime path hardcodes the retired Google token locations or repo-root walk assumptions where a shared resolver exists.
- [x] Auth-activity and token-metadata logging still survive migration and refresh flows after the contract consolidation. (existing `tests/test_auth_log.py` + verified single-writer routing)
- [x] Doctor output is sufficient for an operator to tell whether an integration is absent, healthy, deprecated, or broken.
- [ ] On every operator Mac, interactive *and* unattended (launchd) reads are proven to resolve from the new store before old-key cutover, and `temp/rbos.config` is confirmed secret-free — not just on the primary machine. (tied to the operator-only migration above)

## Phase 2 - Contract Tests, CI, and Observability

Goal: make the unified runtime/storage contract fail fast in CI instead of drifting silently.

> **CI precondition (2026-06-21):** `pytest tests/` (what `.github/workflows/ci.yml` runs) was red — `test_pulse_warning_watch.py` imported `scripts.*` as a package, interrupting whole-suite collection. Fixed with the established sys.path pattern, so CI now collects and the contract tests below actually run.

- [x] Add contract tests for secret-storage invariants.
  Observable result: tests cover insecure mode, missing file, corrupt file, idempotent migration, and launchd-safe fallback behavior with keyring disabled.
  Done (2026-06-21): insecure mode / missing dir / corrupt file are covered by `tests/test_secret_store.py`; idempotency + launchd-safe read by `tests/test_phase2_migration.py`. Added the genuinely-uncovered **verify-then-cutover gate** there: migration never deletes a secret from rbos.config unless the store provably retained it (store-write-raises and store-doesn't-retain branches).
- [x] Add a CI regression test that forbids secret-looking keys in `temp/rbos.config`.
  Observable result: a new write path that leaks a live secret back into repo-local config fails CI immediately.
  Done (2026-06-21): `tests/test_repo_local_secret_leak.py` drives the real setters (github/figma/sleuth) with keyring off and asserts `repo_local_secret_keys_present() == []`, plus a detector test proving a planted leak is flagged.
- [x] Add tests that exercise auth-activity and token-metadata persistence through secret-store writes and token refresh.
  Observable result: fingerprint-only metadata and `first_added_at` retention are asserted, not assumed.
  Done (2026-06-21): `tests/test_auth_sidecar_persistence.py` drives the real setter path — asserts a `token_set` auth event + fingerprint-only token_meta, `first_added_at` retained across re-set and reset for a new token, and that a google refresh (`record=False`) does not restamp it. Also gave `token_meta._meta_path()` the shared `REBALANCE_AUTH_LOG_DIR` seam so conftest isolation covers it (fixing latent pollution of the real token_meta.json).
- [x] Close the remaining collector blind spots in observability/integration coverage.
  Observable result: mocked-only paths such as dashboard refresh/re-ingest are exercised by a real integration-style test path, so a stale call signature cannot pass unnoticed.
  Done (2026-06-21): `tests/test_dashboard_refresh_integration.py` drives the real `_refresh_dashboard_note` chain (build note → write → re-ingest vault → embed_chunks) against an on-disk vault + SQLite DB, faking only the embedding *model* at the lowest seam so the real `embed_chunks` body still runs.
- [x] Verify opt-in source paths under the new contracts or gate them explicitly.
  Observable result: figma and other opt-in flows either have hermetic coverage or an explicit guarded skip with a named reason, rather than silent coverage holes.
  Done (2026-06-21): figma happy path is already hermetic (fake client). Added `tests/test_figma_gating.py` for the unconfigured gate — missing token → clean error envelope, token-without-files → skip-with-reason, dry-run → plan; no network, no DB. Fixed the figma "not configured" error string, which pointed at a non-existent `set-figma-token` CLI command.

### QA Checklist

- [x] CI fails on secret-location regressions, insecure file modes, and migration regressions.
- [x] Launchd-safe fallback is proven in tests for PAT-based auth and Google OAuth flows.
- [x] No runtime code outside the storage module writes secret-bearing files directly. (verified in Phase 1; re-asserted by the leak test)
- [x] Dashboard/weekly-note re-ingest paths are covered by a non-mocked contract test.
- [x] Opt-in integrations have explicit coverage posture instead of informal manual confidence.

## Phase 3 - Canonical Doc Truthfulness

Goal: make the canonical docs match the shipped auth/runtime model exactly.

> **ponytail (lite):** Bullets 1–3 fix lines that are actively wrong — a newcomer following the stale pickle / `migrate-to-keyring` text fails, so that's correctness, keep them. The cut is bullets 4–5: `grep -ri 'pickle\|migrate-to-keyring' *.md` and fix the hits, then stop. Skip the full 5-doc terminology-unification pass until a reader actually reports drift — the audience is ~2 operators.

- [x] Fix the stale Calendar token-location line in `README.md`.
  Observable result: README names the current keyring + JSON secret-store fallback, not the retired pickle path.
  Done (2026-06-21): README.md step 4b now says "saved in your OS keyring, with a launchd-reachable JSON fallback in the out-of-repo secret store at `~/.config/rebalance-os/secrets/google-calendar-oauth`".
- [x] Remove the stale `migrate-to-keyring` follow-up from README/setup guidance.
  Observable result: newcomer-facing docs reflect the one-pass setup flow that writes keyring + JSON directly.
  Done (2026-06-21): dropped the redundant `migrate-to-keyring` step from the Gmail setup block (README), the Gmail "re-mint" + Claude-Code + troubleshooting flows (GMAIL.md), and the Calendar re-auth + Internal-remint flows (GOOGLE_CALENDAR.md). Verified against the setup scripts, which write keyring + JSON in one pass. UPGRADE.md keeps `migrate-to-keyring` because there it legitimately covers the **sleuth env-file / legacy → keyring** path that `migrate-secrets` does not.
- [x] Tighten Gmail fallback wording to name the JSON secret store precisely.
  Observable result: docs no longer use vague "file fallback" language where the concrete store/path matters.
  Done (2026-06-21): README's "file fallback" → "JSON fallback in the out-of-repo secret store (`~/.config/rebalance-os/secrets/`)"; GMAIL.md already named the JSON secret store.
- [x] Sweep README and linked newcomer/operator docs for retired credential-model wording.
  Observable result: no active newcomer-facing doc still treats pickle fallback or repo-local secret persistence as the live model.
  Done (2026-06-21): grep-driven pass over `*.md`. Also corrected the ARCHITECTURE.md credential table, which still claimed GitHub/Figma secrets live in `temp/rbos.config` and Calendar/Gmail use pickle paths — directly contradicting the Phase 2 model (and the new leak guard). Internal `PROJECT/` / `AUDIT-*` / `relay-system/` records left as historical context.
- [x] Run one operator-doc consistency pass across README, UPGRADE, GMAIL, GOOGLE_CALENDAR, and doctor terminology.
  Observable result: the same storage/source language appears everywhere an operator or newcomer is told where credentials live.
  Done (2026-06-21): one model everywhere — keyring (primary) + JSON secret-store fallback; `migrate-secrets` for upgrades; `migrate-to-keyring` scoped to UPGRADE.md's sleuth-env/legacy path. Fixed the stale `migrate-to-keyring` follow-up in doctor's gmail auth-fail hint too.

### QA Checklist

- [x] README, UPGRADE, GMAIL, and GOOGLE_CALENDAR agree on the current credential/storage model.
- [x] Doctor source labels match the language used in docs.
- [x] A reader who only follows the README gets a correct mental model of secret storage and OAuth fallback.
- [x] No active doc still instructs a migration step that the setup flow already performs automatically.

## Phase 4 - Install-Path Clarity and Front-Door Guidance

Goal: make the clone-to-working path readable in one pass for supported, unsupported, and sandboxed environments.

> **ponytail (lite):** A user on the wrong platform genuinely fails, so bullets 1–3 earn their place — but collapse them into one "Supported platform & first-run network" block at the top of README, not four tracked tasks. Bullet 4 (wire warnings into `/welcome` + `rebalance onboard`) is the cut: that's touching onboarding code for a sandbox blocker no one has reported yet. Add it when a sandboxed user actually hits one.

Per the ponytail-lite, bullets 1–3 shipped as **one** consolidated "Supported platform & first-run network" block in README, placed immediately before Step 1; bullet 4 is deliberately cut (see below).

- [x] Surface the supported platform before the first install command.
  Observable result: the macOS Apple-Silicon MLX requirement is visible before install, not buried later in prerequisites.
  Done (2026-06-21): new README block before Step 1 leads with "Full experience: macOS with Apple Silicon (M1+)"; the Prerequisites bullet now points to it and clarifies the core is cross-platform.
- [x] Document the cross-platform minimal install and feature subset.
  Observable result: readers can tell what works with `pip install -e .` or a narrower extra, and what still requires the embeddings stack.
  Done (2026-06-21): an install matrix shows `pip install -e .` (CLI/MCP/SQLite/vault-ingest/GitHub — any platform), `+[calendar]`, `+[server]` (any), and `+[embeddings]` (**Apple Silicon only**). Step 1 gained a one-line "drop the embeddings extra on Linux/Windows/Intel" note. Corrected the overstated "macOS Apple Silicon required" framing — only embeddings are platform-gated.
- [x] Document first-run network egress where it actually happens.
  Observable result: the HuggingFace model download plus GitHub/Google API calls are named inline with host expectations and approximate impact.
  Done (2026-06-21): the block names huggingface.co (one-time Qwen3-Embedding-0.6B download, several hundred MB, cached), api.github.com (PAT), and accounts.google.com / *.googleapis.com (OAuth+sync), framed for egress-allowlist / agent-sandbox readers.
- [ ] Tie egress/platform notes into the agent-facing onboarding path. **Cut (ponytail-lite):** touching `/welcome` + `rebalance onboard` code for a sandbox blocker no one has reported yet. The README block already lets a sandboxed user self-serve the allowlist; revive when a sandboxed user actually hits a blocker.

### QA Checklist

- [x] The supported platform statement appears above the first install command.
- [x] An unsupported-platform reader can still identify the working subset quickly. (install matrix)
- [x] The model-download host and other first-run network touches are discoverable before failure.
- [x] An agent-sandbox user can self-serve the allowlist/remedy path from docs alone. (the README block lists the hosts; the onboarding-code wiring is the cut bullet above)

## Phase 5 - Google Consumption Path Clarity

Goal: explain the local-OAuth path and host-connector path clearly, with the privacy trade-off stated inline.

> Note: Phase 3 and this phase both edit `GMAIL.md` and `GOOGLE_CALENDAR.md` — Phase 3 for credential-storage wording, Phase 5 for the `oauth`/`mcp` consumption modes and the privacy trade-off. Do them as one editing pass per file to avoid a second sweep over the same documents.

> **ponytail (lite):** The privacy trade-off and connector precondition are correctness — keep them inline, don't simplify away. The cut is bullet 1 ("promote `mcp` to first-class co-equal"): you run `oauth`. Keep `oauth` the documented default and add one pointer line to `mcp` mode; don't restructure the docs to present both as equal choices until someone actually uses `mcp`.

Per the ponytail-lite, bullet 1's full "co-equal restructure" is cut — `oauth` stays the documented default; `mcp` keeps its existing decision-table row + pointer. Bullets 2–5 (the correctness pieces) are done.

- [x] Promote Gmail `mcp` mode as a first-class option for users already on a host with connected Google connectors. *(ponytail-lite scope: kept `oauth` default, did not restructure to co-equal.)*
  Observable result: Gmail docs and README present `oauth` and `mcp` as deliberate choices, not a default plus a buried alternate path.
  Done (2026-06-21): GMAIL.md's "Two ingest methods" table already frames both as a deliberate `set-gmail-method` choice (oauth default); README Step 5 keeps Option A/B. No restructure beyond the trade-off/precondition callouts below.
- [x] Add inline trade-off language wherever the connector path is offered.
  Observable result: docs explicitly say that the connector path routes Google data through the host cloud, while local OAuth + SQLite keeps it on this machine.
  Done (2026-06-21): added a "Data boundary" callout after the GMAIL.md methods table, a "Before you switch" note in Method B, and a "Trade-off" note in README Option B — each says `mcp` routes email through the host cloud (e.g. claude.ai) while `oauth` keeps it on this machine.
- [x] Carry the connector precondition everywhere the connector path is recommended.
  Observable result: docs state that the host must actually ship the Google connector and the user must already have connected/consented their account there.
  Done (2026-06-21): the same three callouts state `mcp` requires a host that ships a Gmail connector with your account already connected/consented there, else stay on `oauth`.
- [x] Keep Calendar host-connector ingestion documented as planned, not shipped.
  Observable result: no doc implies Calendar connector ingestion exists today; local OAuth remains the current path.
  Done (2026-06-21): GOOGLE_CALENDAR.md gained an explicit "Calendar has no host-connector (`mcp`) ingest mode … planned, not shipped" note; it had no connector claims to begin with.
- [x] Preserve and carry forward the deferred Calendar `mcp` consumption spec.
  Observable result: the spec below stays embedded in this doc (not just referenced), without promoting it into an active build.
  Done (2026-06-21): verified the spec block below is intact and unpromoted.

  **Deferred Calendar `mcp` spec (build not in scope):**
  - **Setting:** `calendar_ingest_method = oauth | mcp` (mirrors Gmail's existing `oauth | mcp` switch).
  - **Tool:** a new `ingest_calendar_events` MCP tool fed by the host's Google Calendar connector, parallel to today's `ingest_gmail_messages` push path.
  - **Row shape:** writes the same `calendar_events` rows the local OAuth sync already produces, so downstream reads/exports are unchanged.
  - **Data boundary:** the connector path routes Calendar data through the host cloud (claude.ai); local OAuth + SQLite keeps it on this machine. State this trade-off inline wherever the mode is offered.
  - **Revisit trigger:** a user asks for Claude-Desktop Calendar consumption, or Gmail `mcp` mode proves the pattern in the field. Until both the setting and the tool ship, no doc presents Calendar host-connector consumption as available.

### QA Checklist

- [x] Gmail clearly presents both local OAuth and host-connector modes.
- [x] Calendar clearly presents local OAuth now and host-connector ingestion as planned only.
- [x] The privacy trade-off and connector precondition are stated inline everywhere the connector option appears.
- [x] A README-only reader can tell, separately for Gmail and Calendar, what is available now and where data flows.

## Phase 6 - Documentation Surface Cleanup and Canonicalization

Goal: leave one canonical active plan and a cleaner newcomer-facing documentation surface.

> **ponytail (lite):** Keep only bullet 1 — one ROADMAP pointer line is the genuinely useful bit. Bullets 2–5 are a doc-reorg project for an audience of one: inventory / relocate / re-hub risks breaking path-based loaders (your own Cross-Phase Risk #4) to tidy sprawl that bothers no one but you, and the source plans already carry supersession breadcrumbs. Drop the relocation; revisit only if root clutter ever actually impedes a newcomer.

Per the ponytail-lite, only bullet 1 (the ROADMAP pointer) and bullet 5 (keep source plans + breadcrumbs) are kept; bullets 2–4 (the inventory/relocate/re-hub doc-reorg) are cut — they risk breaking path-based loaders (Cross-Phase Risk #4) to tidy sprawl no newcomer hits.

- [x] Add this unified plan to every canonical index that should point to active work.
  Observable result: ROADMAP, README doc hubs where appropriate, and any active project index point to this unified doc instead of fragmenting the follow-up across three separate active plans.
  Done (2026-06-21): ROADMAP status table + ledger now point only to this doc and reflect Phases 1–6 complete (operator-only `migrate-secrets` + deferred fleet scope remaining). The ROADMAP "In progress" ledger already listed only this unified plan, not the three source docs — no fragmentation to fix.
- [ ] ~~Inventory root `.md` files into newcomer-facing vs internal docs.~~ **Cut (ponytail-lite).**
- [ ] ~~Relocate internal docs that do not need to stay at root.~~ **Cut (ponytail-lite)** — relocation risks breaking path-based loaders / tool references for no newcomer benefit.
- [ ] ~~Keep one newcomer index.~~ **Cut (ponytail-lite)** — README is already the newcomer hub; no reorg attempted.
- [x] Keep the three source plans in-tree as linked appendices and leave explicit supersession breadcrumbs on each.
  Observable result: the three source docs are retained (not deleted) as the detailed record behind this plan — they hold the load-bearing detail this doc references but does not fully transcribe (audit tables, source manifest, line-level README references, the runtime credential-flow descriptions, the locked Decisions A/B). Each keeps its "active sequencing moved to this unified doc; kept as source context" breadcrumb, so a future reader can tell sequencing moved here and does not need to reconcile three overlapping plans manually. If any source doc is ever removed, its load-bearing detail must first be folded into this doc.
  Verified (2026-06-21): breadcrumbs confirmed present on all three — COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md, AUTH-AND-API-KEY-STORAGE-HARDENING.md, and FRONT-DOOR-ONBOARDING-REMEDIATION.md.

### QA Checklist

- [x] ROADMAP points to this unified plan as the active ledger entry for this area.
- [ ] ~~The repo root shows only newcomer-relevant docs plus required agent/tool files.~~ **Cut with the relocation bullets** — root sprawl left as-is (no newcomer is impeded; revisit only if that changes).
- [x] No moved doc breaks README links, tool loaders, or skill references. (nothing moved — the relocation was cut)
- [x] A reader can identify this file as the single active sequencing document for front-door/portability/auth follow-up work.

## Cross-Phase Risks

- The main availability risk is breaking unattended launchd behavior while tightening auth/storage contracts.
- The main correctness risk is cleaning up docs before the runtime story is fully stable, which would reintroduce drift.
- The main UX risk is steering privacy-first users toward the host-connector path without stating the cloud trade-off inline.
- The main regression risk is treating doc cleanup as harmless and accidentally breaking path-based loaders or hubs.

Mitigation rules:

- finish runtime contract work before front-door doc cleanup
- land contract tests before broad documentation claims
- keep connector-path trade-offs inline wherever the option is presented
- verify every doc move against README links and tool-loader expectations

## Definition of Done

- [x] Every raw incoming source has one clear source-owned write contract. *(Phase 1 — single `COLLECTORS` registry dispatched via `refresh_index`.)*
- [x] Semantic-maintenance CLI behavior matches the live `semantic` stage coverage. *(Phase 1 — `normalize_sources` derives from `_all_semantic_sources()`; `tests/test_semantic_source_contract.py`.)*
- [x] Remaining runtime path assumptions are reduced behind shared resolvers where applicable. *(Phase 1 — only the documented `_bootstrap.py` shim remains; sync scripts route through `scheduler_common.sh`.)*
- [x] Secret-storage, migration, permissions, and launchd-safe fallback are enforced by CI-backed contract tests. *(Phase 2 — CI unblocked; secret-store/migration/leak/verify-then-cutover tests run in `pytest tests/`.)*
- [x] Auth-activity and token-metadata behavior survive storage migration and OAuth refresh unchanged. *(Phase 1 routing + Phase 2 `tests/test_auth_sidecar_persistence.py`; fingerprint-only, `first_added_at` retained.)*
- [x] Doctor reports source, permissions, and posture for every active auth integration, and distinguishes `optional+unconfigured` (clean skip) from `configured+broken/insecure` (warn/fail). *(Phase 1 — added `_check_figma`; github/sleuth/gmail/calendar already covered.)*
- [x] README and operator docs agree exactly with the shipped credential/storage model. *(Phase 3 — README/UPGRADE/GMAIL/GOOGLE_CALENDAR/ARCHITECTURE + doctor unified on keyring + JSON secret store.)*
- [x] Supported-platform limits, cross-platform subset, and first-run network egress are clear at the front door. *(Phase 4 — "Supported platform & first-run network" README block before Step 1.)*
- [x] Gmail connector mode is first-class, and Calendar connector ingestion is clearly marked as planned-only. *(Phase 5 — `mcp` documented as a deliberate choice with privacy trade-off + precondition; Calendar marked planned-only. Per ponytail-lite, `oauth` stays the default rather than a co-equal restructure.)*
- [x] ROADMAP and the newcomer-facing doc surface point to one canonical active plan for this work. *(Phase 6 — ROADMAP status table + ledger point only to this doc.)*
