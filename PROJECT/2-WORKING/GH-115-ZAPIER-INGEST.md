---
title: "Zapier ingest: alternative email & calendar data streams for the work signal"
owner: Noel
gh_issue: 115
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/115"
status: "Active (2-WORKING) — Phase 0 spike not yet started"
created: 2026-07-05
updated: 2026-07-05
branch: development
doc_type: project
goal: >
  Let operators bring email and calendar into the work signal via Zapier webhooks instead of
  (or alongside) direct Gmail/GCal OAuth — lowering the setup bar and enabling non-Google
  sources (Outlook, Exchange) without new native connectors.
non_goals: >
  Not replacing OAuth for operators who have it working. Not building a certified Zapier app
  or full integration platform. Not adding Zapier for any source beyond email + calendar in v1.
  Not a new ingest table — Zapier payloads normalize into the existing email_messages and
  calendar_events tables.
related:
  - src/rebalance/ingest/gmail.py
  - src/rebalance/ingest/calendar.py
  - src/rebalance/ingest/index_ops.py
  - src/rebalance/ingest/zapier_email.py
  - src/rebalance/ingest/zapier_calendar.py
effort: 3
complexity: 3
risk: 2
phases: 5
---

## Status

| What was just completed | What's next |
|---|---|
| GH-115 opened 2026-07-05. Project doc created. Agy review applied 2026-07-05 — Phase 3 writer renamed to source-agnostic `push_calendar_events()`; Phase 1 added SQLite 503 handling and rate-limiter ephemerality note; Phase 4 added `index_ops.py` collector early-return requirement; Phase 0 HMAC note expanded for Zapier Premium restriction. `swarm-preflight` run 2026-07-05: original single-module design (Phase 2 + Phase 3 both writing `zapier_ingest.py`) was not swarm-eligible — **forced a file-split** into `zapier_email.py` / `zapier_calendar.py` plus Phase 1 handler-stub ownership of `web.py`, making Phase 2 ‖ Phase 3 a genuine path-disjoint concurrent lane (see [Lane / swarm structure](#lane--swarm-structure)). | **Run Phase 0 spike** — catalog Zapier payload shapes for Gmail + GCal triggers, validate HMAC auth model (confirm free vs Premium header support), confirm schema gap for calendar push. Write findings back here before Phase 0 QA gate passes. Phase 0 and Phase 1 still run sequentially before the Phase 2 ‖ Phase 3 swarm wave opens. |

---

## Table of Contents

- [Lane / swarm structure](#lane--swarm-structure)
- [Phase 0 — Spike: Zapier payload schema + auth feasibility](#phase-0--spike-zapier-payload-schema--auth-feasibility-1-2h)
- [Phase 1 — Webhook receiver](#phase-1--webhook-receiver)
- [Phase 2 — Email ingest (Zapier → email_messages)](#phase-2--email-ingest-zapier--email_messages)
- [Phase 3 — Calendar ingest (Zapier → calendar_events)](#phase-3--calendar-ingest-zapier--calendar_events)
- [Phase 4 — Operator config + doctor integration](#phase-4--operator-config--doctor-integration)

---

## Lane / swarm structure

A `swarm-preflight` pass (2026-07-05) found the original single-module design (Phase 2 and Phase 3 both
writing `zapier_ingest.py`) was **not** swarm-eligible — same-file collision, plus both phases wiring
into Phase 1's route in `web.py`. Forcing the module split above removes both collisions and yields a
real 2-lane concurrent wave:

```
Phase 0 (spike, sequential)
   → Phase 1 (webhook receiver + handler stubs, sequential — the only phase that touches web.py)
       → Phase 2 (email lane)  ‖  Phase 3 (calendar lane)   ← concurrent, path-disjoint
           → Phase 4 (config + doctor integration, sequential — depends on 1–3)
```

**Why Phase 1 stays sequential and exclusive on `web.py`:** Phase 1 creates thin placeholder modules
`zapier_email.py` / `zapier_calendar.py` (each exporting a stub `handle_*_event(payload)` that raises
`NotImplementedError`) and wires the `/api/zapier/ingest` dispatch to call those stubs by name. That is
the **only** phase that ever edits `web.py`'s dispatch — Phase 2 and Phase 3 each fill in their own
module's stub body and never touch `web.py` again.

**Disjointness (tick's literal-prefix rule) — Phase 2 vs. Phase 3:**

| Lane | Paths |
|---|---|
| Phase 2 (email) | `src/rebalance/ingest/zapier_email.py`, `tests/test_zapier_email.py`, `fixtures/zapier_gmail_trigger.json` |
| Phase 3 (calendar) | `src/rebalance/ingest/zapier_calendar.py`, `src/rebalance/ingest/calendar.py`, `tests/test_zapier_calendar.py`, `fixtures/zapier_gcal_trigger.json` |

No shared path prefix — both lanes can run concurrently under `tick` (e.g. two agents, `claude-a` /
`codex-b`) once Phase 1 is committed. Phase 0, Phase 1, and Phase 4 remain single-agent sequential
gates (spike findings, then a foundational webhook-receiver commit, then a downstream
config/doctor/docs pass that depends on all three prior phases existing).

---

## Background

rebalance-OS currently ingests email and calendar via direct OAuth:

- **Email (Gmail):** `gmail.py` → `email_messages` table. Also accepts agent-pushed payloads via `ingest_email_messages()` (the MCP push-ingest path, set via `gmail_ingest_method=mcp` in `temp/rbos.config`).
- **Calendar (GCal):** `calendar.py` → `calendar_events` table. No push path exists.

The Gmail push-ingest pattern (`ingest_email_messages()`) is the right model: normalize an external payload into the existing table schema and call the single established writer. Zapier email ingest follows this path exactly. Zapier calendar ingest requires a new push function in `calendar.py` using the same ownership pattern.

**Module split (swarm-forced, 2026-07-05):** email and calendar normalization live in **two separate modules** — `src/rebalance/ingest/zapier_email.py` and `src/rebalance/ingest/zapier_calendar.py` — instead of one shared `zapier_ingest.py`. A single shared module would force Phase 2 (email) and Phase 3 (calendar) to write the same file, making them sequential by construction; splitting the module makes the two phases path-disjoint so they can run as a concurrent 2-lane swarm. See [Lane / swarm structure](#lane--swarm-structure) below.

**Security model.** Every inbound Zapier webhook must be HMAC-SHA256 verified using a shared secret stored via `resolve_secret_path("zapier-webhook-secret")`. Zapier sends a signature header (`X-Hook-Signature` or configurable) on every request. The endpoint rejects any request that fails verification or lacks the header. This is the same pattern used by GitHub webhooks.

---

## Phase 0 — Spike: Zapier payload schema + auth feasibility (1–2h)

**Discuss:**
- Zapier's webhook trigger shape is not public documentation — need to inspect a live zap or Zapier's trigger output docs to know the exact field names for Gmail and GCal triggers.
- The existing `ingest_email_messages()` function in `gmail.py` may or may not accept all the fields Zapier provides — need to verify the schema.
- HMAC auth needs to be chosen before Phase 1: Zapier supports custom header delivery, so we can send a secret alongside or use the Zapier Webhook Signature header (`X-Hook-Signature`) — need to confirm which is simpler to validate without a Zapier Premium plan. **Note:** "Webhooks by Zapier" often restricts custom request headers to Premium accounts. If the spike confirms this, the fallback is a shared-secret query parameter (`?zapier_secret=...`) or HTTP Basic Auth — document the finding and adjust Phase 1 accordingly.
- **Out of scope for this spike:** any code changes. Findings only.

### Checklist

- [ ] Document Zapier Gmail trigger output fields (message_id, subject, from, to, date, snippet/body, labels)
- [ ] Document Zapier Google Calendar trigger output fields (event_id, summary, start, end, location, description, attendees)
- [ ] Map each Zapier Gmail field → `email_messages` column; flag any gaps or mismatches
- [ ] Map each Zapier GCal field → `calendar_events` column; flag any gaps or mismatches
- [ ] Confirm Zapier webhook auth mechanism (HMAC-SHA256 vs shared-secret header vs IP allowlist)
- [ ] Confirm `ingest_email_messages()` signature is reusable as-is (or document the minimal delta needed)
- [ ] Identify any `calendar_events` schema columns that a Zapier payload cannot populate (flag as nullable or drop from push path)
- [ ] Write all findings into the [Spike findings](#spike-findings-phase-0) section below before closing this phase

### Spike findings (Phase 0)

> _To be filled in during the spike run. This section must be complete before the Phase 0 QA gate passes._

**What was investigated:** _(Zapier Gmail + GCal trigger payload shapes; HMAC auth options)_

**What was found:** _(concrete field mapping, gaps, auth recommendation — with file:line pointers where relevant)_

**What it changes:** _(confirms, redirects, or kills any Phase 1–4 assumptions)_

### Phase 0 QA gate

- [ ] Spike findings section above is filled in (not placeholder prose)
- [ ] At least one field-mapping table exists for each source (Gmail, GCal)
- [ ] Auth mechanism selected and documented
- [ ] Any assumption-kills from the spike are reflected in the Phase 1–4 checklists below
- [ ] No code written in this phase

---

## Phase 1 — Webhook receiver

**Discuss:**
- Endpoint lives in `web.py` (the FastAPI dashboard layer) — same host/port as `/api/refresh`, `/api/apple-reminders/complete`, etc. No new server process.
- Route: `POST /api/zapier/ingest` — receives any Zapier event, routes internally by `source` field in the payload.
- HMAC verification runs before any payload parsing. A failed verify → `403` immediately, no body read.
- Dry-run support: `?dry_run=true` validates the envelope (signature verifies, `source` is a recognized value) and returns `ok: true` **without invoking the source handler** — so Phase 1's own dry-run test is provable against the stub handlers alone and doesn't depend on Phase 2/3 landing first. Per-field/normalization dry-run coverage is each source phase's own QA gate (Phase 2/3), once the real handler body exists.
- Secret stored via `resolve_secret_path("zapier-webhook-secret")` — never in `temp/rbos.config`, never in code.
- **Swarm interface contract:** this phase creates `src/rebalance/ingest/zapier_email.py` and
  `src/rebalance/ingest/zapier_calendar.py` as thin placeholders — each exports a single
  `handle_email_event(payload: dict) -> dict` / `handle_calendar_event(payload: dict) -> dict` stub
  that raises `NotImplementedError("Phase 2/3 not yet implemented")`. `web.py` imports and calls these
  by name. This is the **only** phase that edits `web.py`'s dispatch — Phase 2 and Phase 3 each replace
  their own stub body in their own file and never touch `web.py` again (see
  [Lane / swarm structure](#lane--swarm-structure)).

### Checklist

- [ ] Add `POST /api/zapier/ingest` route to `web.py`
- [ ] Implement `_verify_zapier_signature(request, secret)` helper — HMAC-SHA256, constant-time compare (`hmac.compare_digest`)
- [ ] Load webhook secret via `resolve_secret_path("zapier-webhook-secret")` at startup (fail-open with a clear error log if not set)
- [ ] Create placeholder `src/rebalance/ingest/zapier_email.py` (`handle_email_event()` stub, `NotImplementedError`) and `src/rebalance/ingest/zapier_calendar.py` (`handle_calendar_event()` stub, `NotImplementedError`)
- [ ] Route payload by `source` field: `"email"` → `zapier_email.handle_email_event()`, `"calendar"` → `zapier_calendar.handle_calendar_event()`, unknown → `400`
- [ ] Catch `NotImplementedError` from a stub handler and return `501 Not Implemented` (expected until Phase 2/3 land; not a Phase 1 bug)
- [ ] Return structured JSON response: `{"ok": true, "source": "email", "dry_run": false, "message_id": "..."}` or error shape
- [ ] Add `?dry_run=true` query param — validate envelope (signature + recognized `source`) and return `ok: true` without calling the source handler or writing to the DB
- [ ] Rate-limit guard: reject if > 100 requests/minute from same IP (simple in-memory token bucket — state is ephemeral and resets on worker restart; acceptable for local dashboard spam protection, not a distributed rate limiter)
- [ ] Catch SQLite `database is locked` errors and return `503 Service Unavailable` — Zapier retries on 5xx; a 4xx causes Zapier to drop the payload permanently
- [ ] Structured log line per request: `request_id`, `source`, `dry_run`, `status`, `duration_ms`
- [ ] Add `/api/zapier/health` GET endpoint — returns `{"ok": true, "secret_configured": bool}` (no secret value ever returned)

### Phase 1 QA gate

- [ ] `rebalance doctor` still clean after adding the endpoint
- [ ] `pytest tests/` green (no regressions)
- [ ] `curl -X POST /api/zapier/ingest` with wrong signature → `403`
- [ ] `curl -X POST /api/zapier/ingest` with valid signature + unknown source → `400`
- [ ] `?dry_run=true` with a valid signature + recognized `source` returns `ok: true` and writes nothing to DB (envelope-only — does not call the stub handler)
- [ ] `/api/zapier/health` returns `secret_configured: true` when secret is set
- [ ] New tests: `tests/test_zapier_webhook.py` covering HMAC accept, HMAC reject, routing (dispatch reaches the correct stub and gets its `NotImplementedError`, surfaced as `501`), dry-run, health

**Verification summary:** _(fill in before marking gate passed — doctor: / pytest: / unmet: none)_

---

## Phase 2 — Email ingest (Zapier → email_messages)

**Discuss:**
- `gmail.py::ingest_email_messages()` is the single writer for `email_messages`. Zapier email goes through this function — not a second writer.
- **Swarm lane — path-disjoint from Phase 3.** This phase owns exactly one new module,
  `src/rebalance/ingest/zapier_email.py`, plus its own tests and fixture. It replaces the
  `NotImplementedError` stub body Phase 1 created — it does **not** touch `web.py` again.
- `handle_email_event(payload: dict) -> dict` (replacing the Phase 1 stub) calls a new
  `normalize_zapier_email(payload: dict) -> list[dict]` in the same module to translate the Zapier
  Gmail trigger payload into the `ingest_email_messages()` input shape, then calls
  `gmail.py::ingest_email_messages()`.
- Idempotency: Gmail message_id is available from Zapier — the existing upsert in `ingest_email_messages()` handles dedup automatically.
- Body handling: Zapier's Gmail trigger may surface the full body. Phase 1 email ingest was metadata+snippet only — Zapier email should also stay snippet-only in v1 (full body is a separate future decision, tracked in `PROJECT/1-INBOX/EMAIL-INGEST.md`).

### Checklist

- [ ] Create `src/rebalance/ingest/zapier_email.py`
- [ ] Implement `normalize_zapier_email(payload: dict) -> list[dict]` — maps Zapier Gmail fields to `ingest_email_messages()` input shape
- [ ] Implement `handle_email_event(payload: dict) -> dict` — replaces the Phase 1 `NotImplementedError` stub; calls `normalize_zapier_email()` then `gmail.py::ingest_email_messages()`
- [ ] Truncate body/snippet to match existing `email_messages.snippet` length cap (derive from Phase 0 field mapping)
- [ ] Add `tests/test_zapier_email.py` — happy path, malformed payload (missing message_id, missing from/date), duplicate upsert returns unchanged count
- [ ] Store a fixture in `fixtures/zapier_gmail_trigger.json` for realistic test payloads (derive from Phase 0 findings)
- [ ] Confirm no second writer to `email_messages` is introduced (only `gmail.py::ingest_email_messages()` writes)
- [ ] Confirm this phase touched only `src/rebalance/ingest/zapier_email.py`, `tests/test_zapier_email.py`, `fixtures/zapier_gmail_trigger.json` — no edits to `web.py` or `zapier_calendar.py` (swarm disjointness)

### Phase 2 QA gate

- [ ] `pytest tests/` green including `test_zapier_email.py`
- [ ] `rebalance doctor` clean
- [ ] Live manual test: send a Zapier webhook POST with a real Gmail trigger payload → row appears in `email_messages` with correct `message_id`
- [ ] Duplicate POST with same `message_id` → no new row, upsert counts `unchanged: 1`
- [ ] Malformed payload (missing `message_id`) → `400` response, no DB write
- [ ] `fixtures/zapier_gmail_trigger.json` committed and used by tests

**Verification summary:** _(fill in before marking gate passed)_

---

## Phase 3 — Calendar ingest (Zapier → calendar_events)

**Discuss:**
- **Swarm lane — path-disjoint from Phase 2.** This phase owns one new module,
  `src/rebalance/ingest/zapier_calendar.py`, plus its edit to `calendar.py` (adding the new push
  function) and its own tests + fixture. It replaces the `NotImplementedError` stub body Phase 1
  created for the calendar path — it does **not** touch `web.py` again, and never touches
  `zapier_email.py`.
- `calendar.py` is the single writer for `calendar_events`. The new push function belongs there, mirroring how `gmail.py` owns the push path for `email_messages`.
- The push function in `calendar.py` must be **source-agnostic**: `push_calendar_events(db_path: str, events: list[dict]) -> dict`. It accepts a normalized event list and knows nothing about Zapier. This keeps `calendar.py` consistent with how `gmail.py` exposes its push path and avoids coupling the core writer to an external service name.
- All Zapier-specific field translation belongs in `zapier_calendar.py::normalize_zapier_calendar(payload: dict) -> list[dict]`. The same module's `handle_calendar_event()` (replacing the Phase 1 stub) calls `normalize_zapier_calendar()` then `push_calendar_events()` — same layering as email, in its own file.
- `push_calendar_events()` uses the existing `INSERT OR REPLACE` keyed on Google event ID — same upsert semantics as the OAuth sync path.
- Attendees: GCal trigger may include attendees as a comma-separated string or array — normalize to a consistent format matching the existing `calendar_events.attendees` column.
- Phase 0 findings govern which fields are nullable when Zapier cannot supply them.

### Checklist

- [ ] Create `src/rebalance/ingest/zapier_calendar.py`
- [ ] Add `normalize_zapier_calendar(payload: dict) -> list[dict]` to `src/rebalance/ingest/zapier_calendar.py` — all Zapier-specific field mapping lives here
- [ ] Implement `handle_calendar_event(payload: dict) -> dict` in the same module — replaces the Phase 1 `NotImplementedError` stub; calls `normalize_zapier_calendar()` then `push_calendar_events()`
- [ ] Add `push_calendar_events(db_path: str, events: list[dict]) -> dict` to `calendar.py` (single writer, source-agnostic, uses existing `ensure_calendar_schema`)
- [ ] Handle attendees normalization (string list → consistent stored format)
- [ ] Add `tests/test_zapier_calendar.py` — happy path, missing event_id, duplicate upsert, attendees normalization
- [ ] Store a fixture in `fixtures/zapier_gcal_trigger.json`
- [ ] Confirm `calendar_events` has exactly one writer (`calendar.py`) — verify no second write path was introduced
- [ ] Confirm this phase touched only `src/rebalance/ingest/zapier_calendar.py`, `src/rebalance/ingest/calendar.py`, `tests/test_zapier_calendar.py`, `fixtures/zapier_gcal_trigger.json` — no edits to `web.py` or `zapier_email.py` (swarm disjointness)

### Phase 3 QA gate

- [ ] `pytest tests/` green including `test_zapier_calendar.py`
- [ ] `rebalance doctor` clean
- [ ] Live manual test: Zapier GCal webhook POST → row appears in `calendar_events` with correct `event_id`
- [ ] Duplicate POST → `unchanged: 1`, no duplicate row
- [ ] Missing `event_id` in payload → `400`, no DB write
- [ ] `fixtures/zapier_gcal_trigger.json` committed and used by tests

**Verification summary:** _(fill in before marking gate passed)_

---

## Phase 4 — Operator config + doctor integration

**Discuss:**
- Config keys: `email_source` (`oauth` | `zapier` | `both`) and `calendar_source` (`oauth` | `zapier` | `both`). Default is `oauth` so existing setups are unaffected.
- `rebalance doctor` should: if `email_source` includes `zapier`, check that the webhook secret is set; if `calendar_source` includes `zapier`, same check.
- The existing OAuth onboarding flow is unchanged — Zapier is an alternative, not a replacement.
- ARCHITECTURE.md must be updated in the same PR as any structural change (per ARCHITECTURE.md's own rule).
- Add Zapier as a signal source row in ARCHITECTURE.md's Signal Sources table (push path, `zapier_email.py` + `zapier_calendar.py`, writes to existing `email_messages`/`calendar_events`).

### Checklist

- [ ] Add `email_source` and `calendar_source` config keys to `ingest/config.py` with `oauth` as default
- [ ] Update email and calendar collectors in `src/rebalance/ingest/index_ops.py` — when `email_source=zapier` (or `calendar_source=zapier`), the corresponding adapter must return early and skip the OAuth pull; otherwise `refresh_index(scope=["all"])` will attempt an OAuth pull and throw missing-token errors for Zapier-only operators
- [ ] Update `rebalance doctor` (`doctor.py`) — if Zapier source configured, check `resolve_secret_path("zapier-webhook-secret")` is present; emit a clear remediation hint if missing
- [ ] Update `onboarding_status()` in `lifecycle.py` — if Zapier source configured and secret missing, surface as an incomplete step
- [ ] Add MCP tool `ingest_zapier_event(source, payload, dry_run)` in `src/rebalance/mcp/tools/` — thin wrapper over the Phase 1 handler for agent-driven ingest
- [ ] Update `ARCHITECTURE.md` — add Zapier webhook as a signal source row (push path, `zapier_email.py` + `zapier_calendar.py`, `email_messages` / `calendar_events`)
- [ ] Update `ARCHITECTURE.md` module map — add `zapier_email.py` and `zapier_calendar.py` entries under `ingest/`
- [ ] Add `tests/test_zapier_config.py` — validate that doctor emits warning when Zapier source configured but secret missing, and clean when secret present

### Phase 4 QA gate

- [ ] `rebalance doctor` clean (no false positives on a default `email_source=oauth` setup)
- [ ] `rebalance doctor` emits a clear warning when `email_source=zapier` and secret is missing
- [ ] `pytest tests/` green including `test_zapier_config.py`
- [ ] ARCHITECTURE.md updated — `audit_modules` MCP tool or `scripts/audit_modules.py` returns no undocumented module errors
- [ ] `pdda.sh run` clean
- [ ] End-to-end path documented in this doc (Zapier trigger → webhook → normalize → upsert → `index_status` shows fresh row)

**Verification summary:** _(fill in before marking gate passed)_

---

## Open questions

1. Does Zapier's free tier support custom webhook headers (for HMAC delivery)? If not, a shared-secret URL param is the fallback — Phase 0 spike resolves this.
2. Should the webhook endpoint require the pulse server to be running, or should it also work via the CLI dashboard server (`rebalance serve`)? v1 = pulse server only; revisit if demand exists.
3. Future: should `refresh_index(scope=["zapier"])` be a valid scope to replay buffered Zapier payloads from a local queue? Not in v1.
