---
title: "Unified Front-Door, Portability, and Auth Hardening Plan"
doc_type: audit-remediation-plan
status: active
owner: Noel Saw
last_updated: 2026-06-21
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
| **Pre-unification groundwork complete (2026-06-21).** Collector taxonomy, default-refresh semantics, source-owned helper extraction, semantic-stage ownership, secret-store rollout, repo-local secret removal, and JSON OAuth fallback all shipped. The front-door audit then exposed the remaining gaps: doc drift, unresolved contract edges, incomplete contract coverage, install-path ambiguity, and an under-explained Gmail/Calendar connector split. | **Phase 1 - Close the remaining runtime contract gaps.** Finish the still-open collector/auth contract items first, then lock verification, then clean up docs and onboarding in dependency order. |

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

## Phase 1 - Runtime Contract Closure

Goal: close the remaining collector/auth contract gaps before expanding doc cleanup or onboarding guidance.

- [ ] Collapse each raw incoming source onto one clearly canonical source-owned write path.
  Observable result: no raw source still has multiple competing user-facing write paths pretending to be equal; the one true source-owned path is explicit for vault, github, calendar, sleuth, email, and figma.
- [ ] Align semantic-maintenance CLI semantics with the live `semantic` stage contract.
  Observable result: maintenance commands such as `--source all` match the same semantic-capable source set the runtime stage actually processes; no stage/CLI drift remains.
- [ ] Finish runtime resolver cleanup in setup scripts and script bootstraps.
  Observable result: the remaining offenders are named and closed one by one — the OAuth setup scripts (`scripts/setup_calendar_oauth.py`, `scripts/setup_gmail_oauth.py`), the scheduler bootstraps (`scripts/*sync.sh`), and any residual `sys.path.insert` / repo-root shim. Each either routes through the shared resolver (`resolve_project_root` / `resolve_oauth_token_path`) or carries a one-line comment stating why it cannot, so "where applicable" is enumerated rather than left open.
- [ ] Route auth-activity and token-metadata writes through the storage contract.
  Observable result: secret-store writes, migrations, OAuth refreshes, and future storage changes all preserve `auth_activity.jsonl` and `token_meta.json` behavior through one contract.
- [ ] Complete doctor posture coverage for active auth integrations.
  Observable result: doctor distinguishes `optional+unconfigured` from `configured+broken/insecure`, and reports the active source/posture for the shipped auth flows without requiring the deferred descriptor registry.
- [ ] Finish the per-machine secret-store migration on the remaining operator Macs (operator action, carried over from the auth-hardening plan).
  Observable result: `rebalance config migrate-secrets` has been run on each remaining Mac (~2 outstanding as of 2026-06-21) so every machine resolves GitHub/Sleuth/Figma and Google OAuth from keyring + secret store, and no machine still reads a live secret from `temp/rbos.config`. This is the single-operator equivalent of the deferred fleet-decommission ceremony, not part of it.

### QA Checklist

- [ ] Each raw source has one documented and testable source-owned write path.
- [ ] Semantic-maintenance commands and the live `semantic` stage produce the same source coverage.
- [ ] No remaining setup/runtime path hardcodes the retired Google token locations or repo-root walk assumptions where a shared resolver exists.
- [ ] Auth-activity and token-metadata logging still survive migration and refresh flows after the contract consolidation.
- [ ] Doctor output is sufficient for an operator to tell whether an integration is absent, healthy, deprecated, or broken.
- [ ] `temp/rbos.config` is confirmed secret-free on every operator Mac, not just the primary machine.

## Phase 2 - Contract Tests, CI, and Observability

Goal: make the unified runtime/storage contract fail fast in CI instead of drifting silently.

- [ ] Add contract tests for secret-storage invariants.
  Observable result: tests cover insecure mode, missing file, corrupt file, idempotent migration, and launchd-safe fallback behavior with keyring disabled.
- [ ] Add a CI regression test that forbids secret-looking keys in `temp/rbos.config`.
  Observable result: a new write path that leaks a live secret back into repo-local config fails CI immediately.
- [ ] Add tests that exercise auth-activity and token-metadata persistence through secret-store writes and token refresh.
  Observable result: fingerprint-only metadata and `first_added_at` retention are asserted, not assumed.
- [ ] Close the remaining collector blind spots in observability/integration coverage.
  Observable result: mocked-only paths such as dashboard refresh/re-ingest are exercised by a real integration-style test path, so a stale call signature cannot pass unnoticed.
- [ ] Verify opt-in source paths under the new contracts or gate them explicitly.
  Observable result: figma and other opt-in flows either have hermetic coverage or an explicit guarded skip with a named reason, rather than silent coverage holes.

### QA Checklist

- [ ] CI fails on secret-location regressions, insecure file modes, and migration regressions.
- [ ] Launchd-safe fallback is proven in tests for PAT-based auth and Google OAuth flows.
- [ ] No runtime code outside the storage module writes secret-bearing files directly.
- [ ] Dashboard/weekly-note re-ingest paths are covered by a non-mocked contract test.
- [ ] Opt-in integrations have explicit coverage posture instead of informal manual confidence.

## Phase 3 - Canonical Doc Truthfulness

Goal: make the canonical docs match the shipped auth/runtime model exactly.

- [ ] Fix the stale Calendar token-location line in `README.md`.
  Observable result: README names the current keyring + JSON secret-store fallback, not the retired pickle path.
- [ ] Remove the stale `migrate-to-keyring` follow-up from README/setup guidance.
  Observable result: newcomer-facing docs reflect the one-pass setup flow that writes keyring + JSON directly.
- [ ] Tighten Gmail fallback wording to name the JSON secret store precisely.
  Observable result: docs no longer use vague "file fallback" language where the concrete store/path matters.
- [ ] Sweep README and linked newcomer/operator docs for retired credential-model wording.
  Observable result: no active newcomer-facing doc still treats pickle fallback or repo-local secret persistence as the live model.
- [ ] Run one operator-doc consistency pass across README, UPGRADE, GMAIL, GOOGLE_CALENDAR, and doctor terminology.
  Observable result: the same storage/source language appears everywhere an operator or newcomer is told where credentials live.

### QA Checklist

- [ ] README, UPGRADE, GMAIL, and GOOGLE_CALENDAR agree on the current credential/storage model.
- [ ] Doctor source labels match the language used in docs.
- [ ] A reader who only follows the README gets a correct mental model of secret storage and OAuth fallback.
- [ ] No active doc still instructs a migration step that the setup flow already performs automatically.

## Phase 4 - Install-Path Clarity and Front-Door Guidance

Goal: make the clone-to-working path readable in one pass for supported, unsupported, and sandboxed environments.

- [ ] Surface the supported platform before the first install command.
  Observable result: the macOS Apple-Silicon MLX requirement is visible before install, not buried later in prerequisites.
- [ ] Document the cross-platform minimal install and feature subset.
  Observable result: readers can tell what works with `pip install -e .` or a narrower extra, and what still requires the embeddings stack.
- [ ] Document first-run network egress where it actually happens.
  Observable result: the HuggingFace model download plus GitHub/Google API calls are named inline with host expectations and approximate impact.
- [ ] Tie egress/platform notes into the agent-facing onboarding path.
  Observable result: `/welcome` and `rebalance onboard` warn sandboxed users about likely allowlist/download blockers and the one-time remedy.

### QA Checklist

- [ ] The supported platform statement appears above the first install command.
- [ ] An unsupported-platform reader can still identify the working subset quickly.
- [ ] The model-download host and other first-run network touches are discoverable before failure.
- [ ] An agent-sandbox user can self-serve the allowlist/remedy path from docs alone.

## Phase 5 - Google Consumption Path Clarity

Goal: explain the local-OAuth path and host-connector path clearly, with the privacy trade-off stated inline.

> Note: Phase 3 and this phase both edit `GMAIL.md` and `GOOGLE_CALENDAR.md` — Phase 3 for credential-storage wording, Phase 5 for the `oauth`/`mcp` consumption modes and the privacy trade-off. Do them as one editing pass per file to avoid a second sweep over the same documents.

- [ ] Promote Gmail `mcp` mode as a first-class option for users already on a host with connected Google connectors.
  Observable result: Gmail docs and README present `oauth` and `mcp` as deliberate choices, not a default plus a buried alternate path.
- [ ] Add inline trade-off language wherever the connector path is offered.
  Observable result: docs explicitly say that the connector path routes Google data through the host cloud, while local OAuth + SQLite keeps it on this machine.
- [ ] Carry the connector precondition everywhere the connector path is recommended.
  Observable result: docs state that the host must actually ship the Google connector and the user must already have connected/consented their account there.
- [ ] Keep Calendar host-connector ingestion documented as planned, not shipped.
  Observable result: no doc implies Calendar connector ingestion exists today; local OAuth remains the current path.
- [ ] Preserve and carry forward the deferred Calendar `mcp` consumption spec.
  Observable result: the spec below stays embedded in this doc (not just referenced), without promoting it into an active build.

  **Deferred Calendar `mcp` spec (build not in scope):**
  - **Setting:** `calendar_ingest_method = oauth | mcp` (mirrors Gmail's existing `oauth | mcp` switch).
  - **Tool:** a new `ingest_calendar_events` MCP tool fed by the host's Google Calendar connector, parallel to today's `ingest_gmail_messages` push path.
  - **Row shape:** writes the same `calendar_events` rows the local OAuth sync already produces, so downstream reads/exports are unchanged.
  - **Data boundary:** the connector path routes Calendar data through the host cloud (claude.ai); local OAuth + SQLite keeps it on this machine. State this trade-off inline wherever the mode is offered.
  - **Revisit trigger:** a user asks for Claude-Desktop Calendar consumption, or Gmail `mcp` mode proves the pattern in the field. Until both the setting and the tool ship, no doc presents Calendar host-connector consumption as available.

### QA Checklist

- [ ] Gmail clearly presents both local OAuth and host-connector modes.
- [ ] Calendar clearly presents local OAuth now and host-connector ingestion as planned only.
- [ ] The privacy trade-off and connector precondition are stated inline everywhere the connector option appears.
- [ ] A README-only reader can tell, separately for Gmail and Calendar, what is available now and where data flows.

## Phase 6 - Documentation Surface Cleanup and Canonicalization

Goal: leave one canonical active plan and a cleaner newcomer-facing documentation surface.

- [ ] Add this unified plan to every canonical index that should point to active work.
  Observable result: ROADMAP, README doc hubs where appropriate, and any active project index point to this unified doc instead of fragmenting the follow-up across three separate active plans.
- [ ] Inventory root `.md` files into newcomer-facing vs internal docs.
  Observable result: repo-root doc sprawl is classified before any move or hub cleanup.
- [ ] Relocate internal docs that do not need to stay at root.
  Observable result: internal docs move under an internal/docs home, while tool-loaded files such as `AGENTS.md` and `CLAUDE.md` stay where loaders expect them.
- [ ] Keep one newcomer index.
  Observable result: README remains the primary newcomer hub, and any kept root doc is either in that hub or linked from one that is.
- [ ] Keep the three source plans in-tree as linked appendices and leave explicit supersession breadcrumbs on each.
  Observable result: the three source docs are retained (not deleted) as the detailed record behind this plan — they hold the load-bearing detail this doc references but does not fully transcribe (audit tables, source manifest, line-level README references, the runtime credential-flow descriptions, the locked Decisions A/B). Each keeps its "active sequencing moved to this unified doc; kept as source context" breadcrumb (already in place as of 2026-06-21), so a future reader can tell sequencing moved here and does not need to reconcile three overlapping plans manually. If any source doc is ever removed, its load-bearing detail must first be folded into this doc.

### QA Checklist

- [ ] ROADMAP points to this unified plan as the active ledger entry for this area.
- [ ] The repo root shows only newcomer-relevant docs plus required agent/tool files.
- [ ] No moved doc breaks README links, tool loaders, or skill references.
- [ ] A reader can identify this file as the single active sequencing document for front-door/portability/auth follow-up work.

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

- [ ] Every raw incoming source has one clear source-owned write contract.
- [ ] Semantic-maintenance CLI behavior matches the live `semantic` stage coverage.
- [ ] Remaining runtime path assumptions are reduced behind shared resolvers where applicable.
- [ ] Secret-storage, migration, permissions, and launchd-safe fallback are enforced by CI-backed contract tests.
- [ ] Auth-activity and token-metadata behavior survive storage migration and OAuth refresh unchanged.
- [ ] Doctor reports source, permissions, and posture for every active auth integration, and distinguishes `optional+unconfigured` (clean skip) from `configured+broken/insecure` (warn/fail).
- [ ] README and operator docs agree exactly with the shipped credential/storage model.
- [ ] Supported-platform limits, cross-platform subset, and first-run network egress are clear at the front door.
- [ ] Gmail connector mode is first-class, and Calendar connector ingestion is clearly marked as planned-only.
- [ ] ROADMAP and the newcomer-facing doc surface point to one canonical active plan for this work.
