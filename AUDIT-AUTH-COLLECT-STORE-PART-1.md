---
title: "Ponytail Audit — Auth + Collect→Store (Part 1 of 2)"
doc_type: audit + refactor-plan
status: audit-complete · Phases 1–3 done (2026-06-18) · Phase 4 = deliberate skips
scope:
  slice_1_auth: "GitHub PAT · Google OAuth (calendar + gmail) · Sleuth bearer · token_meta · auth_log"
  slice_2_collect_store: "Collector registry · refresh_index orchestrator · db/ package · per-source collectors"
part: 1 of 2
part_2_covers: "query layer · LLM synthesis · MCP surface · CLI · dashboard/pulse · scheduler"
created: 2026-06-18
owner: noel@neochro.me
intensity: ponytail/full
sources_surveyed:
  - ARCHITECTURE.md
  - ask_self RAG (codebase index)
  - direct read of auth + collect→store source
related:
  - ARCHITECTURE.md
  - PLUGINS.md
  - PROJECT.md
---

# Ponytail Audit — Auth + Collect→Store (Part 1 of 2)

| Most recently completed phase | What's next |
|---|---|
| **Phase 2 — Shared helpers** ✅ (2026-06-18, branch `refactor/phase3-credential-io-dedup`) — adapter factory + parse dedup landed; `_safe_*` consolidation deliberately skipped. All of Phases 1–3 done; 1002 tests green, doctor clean | **Part 2** — query layer · LLM synthesis · MCP surface · CLI · dashboard/pulse · scheduler (Phase 4 here is just recorded skips) |

> **Read me first:** This is two documents in one. The **Audit** (top) is the
> ground-truth read of the two slices as they stand today. The **Ponytail
> Refactor** (bottom) is the *optional* plan to act on it. Headline finding:
> **both slices are solid and conservative — there is no egregious
> over-engineering.** The refactor is small on purpose; most of it is
> deduplication, and the riskiest items touch a trust boundary and may not be
> worth doing at all.

---

## Table of Contents

- [Audit](#audit)
  - [A1. Scope & method](#a1-scope--method)
  - [A2. Slice 1 — Auth / credentials](#a2-slice-1--auth--credentials)
  - [A3. Slice 2 — Collect→Store](#a3-slice-2--collectstore)
  - [A4. Keep-as-is (do not touch)](#a4-keep-as-is-do-not-touch)
  - [A5. Findings table (all, ranked)](#a5-findings-table-all-ranked)
  - [A6. LOC inventory](#a6-loc-inventory)
- [Ponytail Refactor](#ponytail-refactor)
  - [R0. Ladder verdict](#r0-ladder-verdict)
  - [Phase 1 — Dead code & trivial wins](#phase-1--dead-code--trivial-wins)
  - [Phase 2 — Shared helpers (collect→store)](#phase-2--shared-helpers-collectstore)
  - [Phase 3 — Credential I/O dedup (trust boundary)](#phase-3--credential-io-dedup-trust-boundary)
  - [Phase 4 — Deliberately skipped (YAGNI)](#phase-4--deliberately-skipped-yagni)

---

# Audit

## A1. Scope & method

Two **sequential** slices of the core pipeline (`Signals → Ingest → SQLite → …`):

1. **Auth** — the credential *gate* that must hold before any source collects.
2. **Collect→Store** — the ingest layer: registry dispatch → per-source
   collectors → normalize → upsert into SQLite.

`auth` and `collect→store` are a genuine dependency chain (auth precedes
collect). "Collection" and "ingest" are **not** separate stages here — in this
repo `ingest/` is the umbrella directory that *contains* collection plus
normalize+store, so we audit them as one slice to avoid double-counting.

Method: ARCHITECTURE.md + ask_self RAG for the conceptual map, then a full read
of the source in each slice with file:line citations.

## A2. Slice 1 — Auth / credentials

**What it does.** Five integrations (GitHub PAT, Google Calendar OAuth, Gmail
OAuth, Sleuth bearer, Figma PAT) share one discipline: **keyring-primary,
config-fallback**.

- **Keyring** (macOS Keychain / Win Credential Locker / Linux Secret Service) —
  primary store; reads/writes are best-effort and degrade to `None` instead of
  raising (`config.py:54–74`).
- **`temp/rbos.config`** (gitignored JSON) — duplicate copy so **launchd** jobs
  (stripped env, no Keychain) can still authenticate. Every secret is
  dual-written.
- **GitHub** — three-tier read: keyring → config → `gh auth token`; validated
  against `/user` with token-type classification.
- **Google OAuth (calendar + gmail)** — token in keyring (JSON) + pickle-file
  fallback (`~/.config/rebalance-os/google-{svc}-oauth`); auto-refresh on
  expiry writes the rotated access token back to **both** stores.
- **Sleuth** — bearer creds (base_url/token/workspace) in keyring + config, with
  a legacy env-file fallback parsed manually.
- **`token_meta.py`** (112 LOC) — sidecar `temp/logs/token_meta.json`: SHA-256
  **fingerprint** of the token value (never the raw secret), `first_added_at`,
  re-set counts. Distinguishes *rotation* (new key) from *refresh* (same key,
  new expiry) — this is how "PAT dies every 3 days" gets diagnosed.
- **`auth_log.py`** (372 LOC) — append-only JSONL (`temp/logs/auth_activity.jsonl`)
  unified across collectors + launchd; readers `latest_failure_by_source()` /
  `latest_event_by_source()` back the dashboard `/auth-log` and `rebalance doctor`.
- **`google_oauth_client.py`** (34 LOC) — one base64'd Desktop client shared by
  calendar + gmail; single rotation point.

**Headline:** conservative and correct. The duplication problem is **two
near-identical OAuth loaders** (`calendar.py:83–149` ≈ `gmail.py:79–147`, ~85%
overlap) and a repeated **get/set/clear dual-store dance** per secret type.

## A3. Slice 2 — Collect→Store

**What it does.** A `Collector` frozen dataclass (`index_ops.py:33–85`) +
registry dispatcher is the whole contract:

- Fields: `name`, `refresh` callable `(db_path, **opts)→dict`, `requires`
  (preconditions), `included_in_all`, `kind`
  (`raw_source`/`derived_scan`/`projection`/`export`), `semantic_docs`
  (optional provider), `secrets` (informational).
- `register_collector()` (`index_ops.py:100–122`) validates name/kind, forbids
  dupes.
- `refresh_index()` (`index_ops.py:1040–1251`) is the single entry point:
  normalize scope → `run_migrations()` once → per-scope loop validates
  preconditions, calls `collector.refresh()`, catches exceptions into a
  structured error envelope. `None`/`all` → default recipe.
- **DB layer** (`db/connection.py:20–72`): `db_connection(path, ensure_fn)`
  opens WAL SQLite, FK on, sqlite-vec loaded, row_factory set. Migrations are
  forward-only, version-stamped, atomic (`db/migrate.py`).
- **Shared collect idiom** (exemplars `sleuth_reminders.py`, `github_scan.py`):
  fetch → normalize to dataclass → upsert by PK (SELECT → INSERT new / UPDATE
  changed / bump `last_seen_at` if unchanged) → optional reconciliation sweep →
  return counts.

**Headline:** the registry/migration/upsert core is genuinely good. The fat is
**boilerplate**: 10 near-identical adapter wrappers, three `_safe_*` query
helpers that could be one, hand-rolled ISO-8601 parsing duplicated across 4+
collectors, and one dead field on the contract.

## A4. Keep-as-is (do not touch)

These are correct and/or trust-boundary — **out of scope for the refactor**:

- **Keyring graceful-degrade** never raises (`config.py:54–74`).
- **Token never logged whole** — SHA-256 fingerprint only (`token_meta.py:31–33`).
- **Dual-write keyring+config** in lockstep (launchd safety) — every setter.
- **Best-effort `try/except` around logging** so a log failure never breaks a
  credential write.
- **OAuth refresh isolation** — only rotated access tokens written back; refresh
  token used for fingerprinting (`calendar.py:123–140`, `gmail.py:119–138`).
- **Registry pattern + `register_collector` validation** (`index_ops.py:33–154`).
- **Migration safety** — forward-only, atomic, version-stamped (`db/migrate.py`).
- **Upsert + diff + reconciliation correctness** — field-by-field, unchanged
  tracking, absent-row retirement only on full fetch
  (`sleuth_reminders.py:420–443, 573–708`).
- **Incremental sync semantics** — multi-source repo discovery, A/B/C banding,
  cutoff stopping (`index_ops.py:429–567`, `github_scan.py:177–218`).

## A5. Findings table (all, ranked)

| # | Slice | Finding | File:line | Value | Risk | Phase |
|---|---|---|---|---|---|---|
| 1 | collect | `Collector.secrets` field declared, never read | `index_ops.py:85` | High | None (dead) | 1 |
| 2 | collect | 10 adapter wrappers repeat the same passthrough | `index_ops.py:1264–1434` | Med | None | 2 |
| 3 | collect | `_safe_count`/`_safe_max`/`_safe_meta` → one `_safe_query` | `index_ops.py:163–184` | Med | Low (error paths only) | 2 |
| 4 | collect | hand-rolled ISO-8601 parsing duplicated | `sleuth_reminders.py:113–128`, `github_scan.py:123–125`, calendar/gmail/figma | Med | None | 2 |
| 5 | auth | get/set/clear dual-store dance repeated per secret | `config.py:191–391` (scattered) | High | **High (trust boundary)** | 3 |
| 6 | auth | Calendar/Gmail `_load_credentials()` ~85% identical | `calendar.py:83–149`, `gmail.py:79–147` | High | **High (refresh path)** | 3 |
| 7 | auth | GitHub get-with-source mutates on read (auto-migrate) | `config.py:191–213` | Med | Low | 4 (opt) |
| 8 | auth | Sleuth env parse → `python-dotenv` | `config.py:1314–1347` | Low | Low + **new dep** | 4 (reject) |
| 9 | auth | consolidate `_normalize_*` helpers | `config.py` (~100 LOC) | Low | Low | 4 (defer) |
| 10 | auth | log swallowed exceptions at debug level | `config.py` (9 sites) | Med | Low (additive) | 4 (opt) |
| 11 | both | `kind` metadata is near-cosmetic; repo doc it cites is missing | `index_ops.py:60–65,83,134` | Low | Low | 4 (defer) |
| 12 | auth | GitHub repo regex strictness | `config.py:103–152` | V.Low | Low | skip |

## A6. LOC inventory

**Auth slice ≈ 4,000 LOC** — bulk is `config.py` **1,364** (monolith),
`config_cmds.py` 745, `calendar.py`/`gmail.py` 421 each (842, with ~58 dup
lines), `paths.py` 458, `auth_log.py` 372, `token_meta.py` 112,
`google_oauth_client.py` 34.

**Collect→store core ≈ 8,300 LOC** (full `ingest/` is ~23,102) — `index_ops.py`
**1,464**, `db/semantic.py` ~1,100, `github_scan.py` 809, `sleuth_reminders.py`
736, `calendar.py` 663, `db/schema.py` ~500, `gmail.py` 421, `registry.py` 351,
`figma.py` 328, `db/migrate.py` 100, `db/connection.py` 73, `db/__init__.py` 55.

---

# Ponytail Refactor

## R0. Ladder verdict

Rung 1 of the ladder — *does this need to exist at all?* — applied to the
refactor itself: **mostly no.** Nothing here is broken; this is pure
maintenance-cost reduction. So the plan is deliberately small and **front-loads
the free wins**:

- **Phases 1–2 are worth doing** — zero/low risk, delete real boilerplate
  (~50–60 LOC), no behavior change.
- **Phase 3 is committed (2026-06-18) — do it with tests.** Real duplication on
  the credential trust boundary; the trade chosen is to pay for it with mandatory
  test coverage rather than leave the dup.
- **Phase 4 is mostly "don't"** — including rejecting the `python-dotenv`
  suggestion: adding a dependency to replace 8 lines of parsing is the opposite
  of lazy, and ARCHITECTURE.md already records "parsed manually (no
  python-dotenv)" as a deliberate choice.

Estimated total payoff if Phases 1–3 land: **~110–130 LOC deleted**, one fewer
place to update OAuth refresh, no new dependencies.

---

## Phase 1 — Dead code & trivial wins

*Zero risk. ~1 line. Do this first; it can ship alone.*

- [x] Delete `secrets` field from the `Collector` dataclass
- [x] Remove `secrets` from the `Collector` docstring
- [x] Grep confirms zero `.secrets` references remain (also removed the one
      write-only assignment at the figma registration)
- [x] Registry still builds — 11 collectors enumerated

**QA checklist — Phase 1**
- [x] DRY: no remaining `secrets` reference anywhere in src/tests
- [x] Behavior unchanged: registry registers the same 11 collectors
- [x] Tests: full suite **1002 passed, 10 skipped**
- [x] `rebalance doctor` clean (credential/schema/projects/auth-log all OK)
- [x] Anti-goal check: did **not** touch adjacent fields (`kind`,
      `included_in_all`) — those stay (see Phase 4)

---

## Phase 2 — Shared helpers (collect→store)

*Low risk, mechanical. Pure dedup; same options pass through unchanged.*

- [x] Add `_dry_run_adapter(refresh_fn)` factory; replaced the **8**
      dry_run-only adapters (sleuth, email, code, figma, semantic, sync,
      ask_self, focus5) with one-line assignments. vault/github/calendar keep
      their bespoke option-mapping adapters (not boilerplate).
- [x] **Parse dedup — reused the *existing* `tz_utils.parse_utc_iso`** instead
      of writing a new util (it already does the `Z`→`+00:00` dance, None on
      bad/empty, naive→UTC). Migrated the two in-slice hand-rolled copies:
      `sleuth_reminders._parse_datetime` (kept its non-str guard) and
      `token_meta.age_text`.
- [~] **SKIPPED `_safe_count`/`_safe_max`/`_safe_meta` → `_safe_query`.** On
      inspection this is net-negative: the three return *different shapes*
      (int / scalar / dict) with different defaults (0 / None / {}); a single
      raw-row helper would push shaping into ~17 call sites — more code, not
      less. The three tiny named helpers are already the minimal readable form.
- [x] Factory carries a docstring documenting the dry_run-only passthrough
      contract (bespoke sources keep their own adapter).

> **Scope note:** the other hand-rolled `Z`-dance copies (`diagnose.py`,
> `github_readiness.py`, `note_builder.py`, `pulse_health.py`) are Part-2
> modules (query/diagnostics/render) — intentionally left for Part 2 to avoid
> reaching outside this slice.

**QA checklist — Phase 2**
- [x] DRY: 8 adapters → 1 factory; 2 in-slice date parsers → existing
      `parse_utc_iso`. (`_safe_*` consolidation deliberately not done — see above.)
- [x] SOLID: each `refresh_fn` signature untouched; factory adds no new coupling
- [x] Observability: `index_status` counts/timestamps unchanged (the `_safe_*`
      helpers it depends on were left as-is)
- [x] Correctness: parse behavior verified — Z-parse, non-str→None, bad/empty→
      None/"", naive→UTC, age `6.0h` all preserved
- [x] Tests: full suite **1002 passed, 10 skipped**; sleuth/calendar/gmail/
      auth-log tests unchanged
- [x] Anti-goal: did **not** touch upsert/diff/migration logic, and did **not**
      reach into Part-2 modules for the remaining parse copies

---

## Phase 3 — Credential I/O dedup (trust boundary)

*Higher risk — touches credential persistence + OAuth refresh. **Decision
(2026-06-18): committed — do it WITH tests.** The QA checklist's test items are
mandatory, not optional, for this phase.*

- [x] Add `_set_secret_dual_store(key, value)` + `_clear_secret_dual_store(key)`
      + `_get_secret_dual_store(key)` to `config.py` (keyring + config in
      lockstep; callers layer their own auth_log/token_meta side effects)
- [x] Refactor `set_/get_/clear_` for github, figma, sleuth (clear) to the
      dual-store helpers; collapse calendar+gmail OAuth setters into shared
      `_set_google_oauth_token_json(service, key, …)`
- [x] Extract `oauth_common.load_credentials(OAuthService, scopes)`; point
      `calendar._load_credentials()` and `gmail._load_credentials()` at it
      (per-service error messages + scope rule stay local); dropped now-unused
      `import pickle` from both collectors
- [x] Preserve exact `creds.expired and creds.refresh_token` guard and
      dual-write atomicity (control flow moved verbatim into oauth_common)

**QA checklist — Phase 3**
- [x] Security: token never logged whole — fingerprint path unchanged
      (`_set_google_oauth_token_json` keys sidecar on `refresh_token`)
- [x] Trust boundary: dual-write still lockstep; config-only path verified by
      `test_config_only_path_when_keyring_unavailable` (keyring write fails →
      persists to rbos.config → resolves back with source `config`)
- [x] Refresh: `test_refresh_persists_to_both_stores` asserts rotated token
      written to keyring (`record=False`, `source=refresh`) **and** pickle;
      shared loader covers calendar **and** gmail
- [x] Failure isolation: `test_set_github_token_survives_logging_failure` +
      `test_google_oauth_set_survives_logging_failure` (raising callback does
      not abort the write)
- [x] launchd: config fallback path is the launchd safety net — exercised by the
      config-only test (stripped env has no keychain → same code path)
- [x] Tests: full suite **1002 passed, 10 skipped**; `test_calendar_helpers`
      patch target moved to `oauth_common.pickle.load`; new
      `tests/test_credential_dedup.py` added
- [x] Anti-goal: did **not** touch validation, the GitHub repo regex, or
      `_normalize_*` helpers (those remain in Phase 4)

---

## Phase 4 — Deliberately skipped (YAGNI)

*Recorded so the next pass doesn't re-litigate them.*

- [ ] **REJECT** finding #8 — do **not** add `python-dotenv` for Sleuth env
      parsing. New dependency to replace ~8 lines; ARCHITECTURE.md already pins
      "parsed manually (no python-dotenv)" as intentional. Hand-rolled stays.
- [ ] **DEFER** #9 `_normalize_*` consolidation — current helpers are clear and
      tested; revisit only if the suite grows past ~5.
- [ ] **DEFER** #11 `kind` field — near-cosmetic but fails-safe; the doc it cites
      (`COLLECTOR-PATH-AND-PORTABILITY-AUDIT`) is missing — fix the dangling
      reference, don't remove the field.
- [ ] **SKIP** #12 GitHub repo regex — explicit whitelist is defensible; the API
      rejects bad names anyway.
- [ ] **OPTIONAL** #7 split GitHub get-with-source read-vs-migrate — clarity only,
      no LOC win; do only if touched for another reason.
- [ ] **OPTIONAL** #10 log swallowed exceptions at debug level — additive
      observability; nice-to-have, not now.

**QA checklist — Phase 4**
- [ ] Each skipped item has a one-line rationale recorded above (done)
- [ ] Dangling doc reference (`COLLECTOR-PATH-AND-PORTABILITY-AUDIT`) either
      created or the citation removed from `index_ops.py:62`
- [ ] No silent scope creep: nothing from this phase got "snuck in" during 1–3

---

> **Part 2 (later)** — same treatment for the rest of the app: query layer
> (`querier.py`, `semantic_index.py`, `chat.py`), LLM synthesis, MCP tool
> surface, CLI, dashboard/pulse renderers, and the launchd scheduler fleet.
