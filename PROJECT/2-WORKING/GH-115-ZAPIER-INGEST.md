---
title: "Zapier ingest: alternative email & calendar data streams for the work signal"
owner: Noel
gh_issue: 115
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/115"
status: "Active (2-WORKING) — Phase 1 shipped 2026-07-06 (MARATHON-2026-07-06 Lane B). Phase 2 ‖ Phase 3 next."
created: 2026-07-05
updated: 2026-07-06
branch: marathon/2026-07-06
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
| **Phase 1 shipped 2026-07-06** via `relay-xyz` (Producer=codex, Reviewer=agy, Approved r1; `relay-system/2026-07-06/gh115-phase1.md`), driven in an isolated worktree/branch (`marathon/2026-07-06`). `POST /api/zapier/ingest` + `GET /api/zapier/health` added to `web.py`; `_verify_zapier_auth()` (Basic Auth primary, query-param fallback, constant-time compare); placeholder `zapier_email.py`/`zapier_calendar.py` stubs; `dry_run`, rate-limit guard, DB-lock → 503, structured logging. Independently re-verified: `PYTHONPATH=src pytest tests/test_zapier_webhook.py` → 8 passed; full suite 1322 passed/14 skipped (1 pre-existing unrelated failure in `test_google_oauth_client.py`, reproduces identically on untouched `development`). | Open the Phase 2 ‖ Phase 3 swarm wave (email + calendar ingest) now that the stubbed receiver has landed. |

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

**Security model.** Phase 0 changed the v1 auth decision: inbound Zapier webhooks should use HTTP Basic Auth with the shared secret from `resolve_secret_path("zapier-webhook-secret")` as the password (static username such as `zapier` is fine). Query-param secret fallback remains acceptable for operators who cannot use Basic Auth. HMAC-SHA256 is deferred: Zapier's documented webhook actions can send headers, but true per-request HMAC signing would require extra Zap logic (for example a Code step or private integration) and is not the low-friction default for this project.

---

## Phase 0 — Spike: Zapier payload schema + auth feasibility (1–2h)

**Discuss:**
- Zapier's webhook trigger shape is not public documentation — need to inspect a live zap or Zapier's trigger output docs to know the exact field names for Gmail and GCal triggers.
- The existing `ingest_email_messages()` function in `gmail.py` may or may not accept all the fields Zapier provides — need to verify the schema.
- HMAC auth needs to be chosen before Phase 1: Zapier supports custom header delivery, so we can send a secret alongside or use the Zapier Webhook Signature header (`X-Hook-Signature`) — need to confirm which is simpler to validate without a Zapier Premium plan. **Note:** "Webhooks by Zapier" often restricts custom request headers to Premium accounts. If the spike confirms this, the fallback is a shared-secret query parameter (`?zapier_secret=...`) or HTTP Basic Auth — document the finding and adjust Phase 1 accordingly.
- **Out of scope for this spike:** any code changes. Findings only.

### Checklist

- [x] Document Zapier Gmail trigger output fields (message_id, subject, from, to, date, snippet/body, labels)
- [x] Document Zapier Google Calendar trigger output fields (event_id, summary, start, end, location, description, attendees)
- [x] Map each Zapier Gmail field → `email_messages` column; flag any gaps or mismatches
- [x] Map each Zapier GCal field → `calendar_events` column; flag any gaps or mismatches
- [x] Confirm Zapier webhook auth mechanism (HTTP Basic Auth vs HMAC-SHA256 custom header vs shared-secret query param)
- [x] Confirm `ingest_email_messages()` signature is reusable as-is (or document the minimal delta needed)
- [x] Identify any `calendar_events` schema columns that a Zapier payload cannot populate (flag as nullable or drop from push path)
- [x] Write all findings into the [Spike findings](#spike-findings-phase-0) section below before closing this phase

### Spike findings (Phase 0)

**What was investigated:**

- Zapier's public Gmail app docs for `New Email Matching Search` and Google Calendar app docs for `Event Start`, plus the `Webhooks by Zapier` action docs for plan availability and auth capabilities. Public Zapier docs list the trigger/action inventory and configuration fields, but they do **not** publish one canonical sample webhook payload for either trigger.
- The local single-writer contracts for `email_messages` and `calendar_events`, using the actual source files instead of guessing: `src/rebalance/ingest/gmail.py:327`, `src/rebalance/ingest/db/schema.py:240`, `src/rebalance/ingest/calendar.py:173`, and `src/rebalance/ingest/db/migrations/0005_calendar_events_composite_pk.sql:27`.
- The underlying Gmail Message and Google Calendar Event resource fields Zapier is surfacing from those triggers, to anchor the normalized mapping where Zapier's public docs stop short of showing raw JSON payloads.

**What was found:**

**Gmail trigger mapping (`New Email Matching Search`)**

Public Zapier docs confirm the trigger exists and is polling-based, but do not publish a canonical output JSON sample. The table below therefore uses the documented trigger plus Gmail's Message resource fields and the existing `ingest_email_messages()` contract (`message_id`, `thread_id`, `from_address`, `from_name`, `subject`, `snippet`, `received_at`, `labels`) as the normalization target.

| Zapier/Gmail field | Normalize to | Evidence / note |
|---|---|---|
| `message_id` | `email_messages.message_id` | Required. `ingest_email_messages()` skips rows with no `message_id` and upserts by that key. See `src/rebalance/ingest/gmail.py:338` and `src/rebalance/ingest/gmail.py:351`. |
| `thread_id` | `email_messages.thread_id` | Optional if Zapier exposes Gmail `threadId`; otherwise leave empty string. Local writer already treats it as optional. See `src/rebalance/ingest/gmail.py:338` and `src/rebalance/ingest/db/schema.py:248`. |
| `from` | `email_messages.from_address` + `email_messages.from_name` | Split sender into address + display name to match the existing table. The Gmail API exposes `From` in message headers; the current OAuth path already parses it this way. See `src/rebalance/ingest/gmail.py:266` and `src/rebalance/ingest/gmail.py:365`. |
| `subject` | `email_messages.subject` | Direct map. See `src/rebalance/ingest/gmail.py:339` and `src/rebalance/ingest/db/schema.py:253`. |
| `date` | `email_messages.received_at` | Normalize to ISO text. Current OAuth path prefers headers, then falls back to Gmail `internalDate`. See `src/rebalance/ingest/gmail.py:268`, `src/rebalance/ingest/gmail.py:339`, and Gmail Message resource docs. |
| `snippet` / body excerpt | `email_messages.snippet` | v1 should stay snippet-only. There is no full-body column in `email_messages`; long body fields must be truncated or reduced to excerpt text. See `src/rebalance/ingest/db/schema.py:254`. |
| `labels` | `email_messages.labels_json` | Store as JSON array of label strings, exactly as `ingest_email_messages()` already does. See `src/rebalance/ingest/gmail.py:370` and `src/rebalance/ingest/db/schema.py:256`. |
| `to` | dropped in v1 | There is no `to_*` column in `email_messages`, and `ingest_email_messages()` has no input slot for it. If later needed, that is a schema change, not a Phase 2 workaround. |

**Result:** `ingest_email_messages()` is reusable as-is. No writer-signature change is needed for the Phase 2 path; the only deliberate drops are `to` and any full-body field that exceeds the existing snippet-only contract.

**Google Calendar trigger mapping (`Event Start`)**

Zapier's public docs confirm `Event Start` exists, is polling-based, and is configured with `Calendar`, `Time Before`, `Time Before (Unit)`, and optional search input. As with Gmail, the public docs do not publish a canonical raw webhook sample, so the mapping below is grounded in the standard Google Calendar Event resource fields and the actual `calendar_events` writer shape in `src/rebalance/ingest/calendar.py`.

| Zapier/GCal field | Normalize to | Evidence / note |
|---|---|---|
| `event_id` | `calendar_events.id` | Required. This is the event identity field from Google Calendar. The existing writer uses `id` in every upsert row. See `src/rebalance/ingest/calendar.py:240` and `src/rebalance/ingest/db/migrations/0005_calendar_events_composite_pk.sql:28`. |
| `summary` | `calendar_events.summary` | Direct map. See `src/rebalance/ingest/calendar.py:241` and `src/rebalance/ingest/db/migrations/0005_calendar_events_composite_pk.sql:29`. |
| `start` | `calendar_events.start_time` | Required for the push path because `start_time` is `NOT NULL`. Normalize from event `start.dateTime` or `start.date`. See `src/rebalance/ingest/calendar.py:242` and `src/rebalance/ingest/db/migrations/0005_calendar_events_composite_pk.sql:30`. |
| `end` | `calendar_events.end_time` | Optional. Normalize from `end.dateTime` or `end.date`. See `src/rebalance/ingest/calendar.py:243` and `src/rebalance/ingest/db/migrations/0005_calendar_events_composite_pk.sql:31`. |
| `location` | `calendar_events.location` | Direct map. See `src/rebalance/ingest/calendar.py:246`. |
| `description` | `calendar_events.description` | Direct map. See `src/rebalance/ingest/calendar.py:247`. |
| `attendees` | `calendar_events.attendees_json` | Must normalize to JSON objects shaped like `{email, name, response}` to match the existing writer's attendee structure. See `src/rebalance/ingest/calendar.py:250`. |
| trigger-selected calendar | `calendar_events.calendar_id` | Not reliably present as a payload field in the public docs. Phase 3 should treat this as a locally supplied value from the Zap step/config, not as something guaranteed to arrive in the request body. |
| event status | `calendar_events.status` | Google's Event resource has a `status` field, but Zapier's public `Event Start` docs do not promise it in the raw output shape. Treat as optional; default if absent. See `src/rebalance/ingest/calendar.py:248`. |
| ingest timestamp | `calendar_events.fetched_at` | Not from Zapier. Must be synthesized locally at ingest time. See `src/rebalance/ingest/calendar.py:204` and `src/rebalance/ingest/db/migrations/0005_calendar_events_composite_pk.sql:37`. |
| operator/team attribution | `calendar_events.person` | Not from Zapier. Nullable column added by migration 0005; must come from config or remain `NULL`. See `src/rebalance/ingest/calendar.py:180` and `src/rebalance/ingest/db/migrations/0005_calendar_events_composite_pk.sql:38`. |

**Calendar schema gaps / required local defaults**

- `calendar_events.start_time`, `calendar_events.calendar_id`, and `calendar_events.fetched_at` are non-null local requirements. A Zapier push path cannot rely on the raw payload alone for all three.
- `calendar_events.person` is nullable and should stay config-driven, not payload-driven.
- Upsert identity is no longer just `event_id`; the live schema uses composite identity `(id, calendar_id)`. Any Phase 3 duplicate test must keep `calendar_id` stable when proving idempotency.

**Webhook auth decision**

- `Webhooks by Zapier` webhook **actions** are not available on the Free plan; Zapier's own help doc marks them available on `Professional`, `Team`, and `Enterprise` only.
- The documented webhook actions expose both a `Headers` section and a dedicated `Basic Auth` field.
- Zapier also notes that `Custom Request` is the path for "Extremely customized headers", which is a signal that true HMAC-by-header is possible only with a more advanced setup, not the low-friction baseline.

**Decision:** Phase 1 should use **HTTP Basic Auth as the v1 default**, with the shared secret from `resolve_secret_path("zapier-webhook-secret")` used as the password. Query-param secret fallback is acceptable only for operators who cannot use Basic Auth. Do **not** make HMAC-SHA256 the default Phase 1 contract.

**Why Basic Auth wins over HMAC and query-param secret**

- It is a first-class documented field in Zapier's webhook actions, so the setup is simpler than asking operators to build a Code step or custom integration to compute a signature.
- It keeps the secret out of the URL, which is better than a query param for logs, browser history, and reverse-proxy access logs.
- It still uses a header transport, so the receiver can reject unauthorized requests before parsing the payload body.

**What it changes:**

- Kills the current Phase 1 assumption that Zapier will send a per-request HMAC signature header by default. Phase 1 should verify HTTP Basic Auth first, with optional query-param fallback, not `_verify_zapier_signature(...)`.
- Confirms the Phase 2 single-writer plan unchanged: `ingest_email_messages()` is already the right writer contract, and the only deliberate v1 drops are `to` and full-body storage.
- Tightens Phase 3 requirements: the push writer must synthesize `calendar_id`, `fetched_at`, and optional `person` locally, and it must treat duplicate identity as `(event_id, calendar_id)`, not just `event_id`.

### Phase 0 QA gate

- [x] Spike findings section above is filled in (not placeholder prose)
- [x] At least one field-mapping table exists for each source (Gmail, GCal)
- [x] Auth mechanism selected and documented
- [x] Any assumption-kills from the spike are reflected in the Phase 1–4 checklists below
- [x] No code written in this phase

---

## Phase 1 — Webhook receiver

**Discuss:**
- Endpoint lives in `web.py` (the FastAPI dashboard layer) — same host/port as `/api/refresh`, `/api/apple-reminders/complete`, etc. No new server process.
- Route: `POST /api/zapier/ingest` — receives any Zapier event, routes internally by `source` field in the payload.
- HTTP Basic Auth verification runs before any payload parsing. A failed verify → `403` immediately, no body read. Query-param fallback (`?zapier_secret=...`) is acceptable only as a compatibility path, not the default contract.
- Dry-run support: `?dry_run=true` validates the envelope (auth verifies, `source` is a recognized value) and returns `ok: true` **without invoking the source handler** — so Phase 1's own dry-run test is provable against the stub handlers alone and doesn't depend on Phase 2/3 landing first. Per-field/normalization dry-run coverage is each source phase's own QA gate (Phase 2/3), once the real handler body exists.
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
- [ ] Implement `_verify_zapier_auth(request, secret)` helper — HTTP Basic Auth primary, optional `?zapier_secret=` fallback, constant-time compare (`hmac.compare_digest` or `secrets.compare_digest`)
- [ ] Load webhook secret via `resolve_secret_path("zapier-webhook-secret")` at startup (fail-open with a clear error log if not set)
- [ ] Create placeholder `src/rebalance/ingest/zapier_email.py` (`handle_email_event()` stub, `NotImplementedError`) and `src/rebalance/ingest/zapier_calendar.py` (`handle_calendar_event()` stub, `NotImplementedError`)
- [ ] Route payload by `source` field: `"email"` → `zapier_email.handle_email_event()`, `"calendar"` → `zapier_calendar.handle_calendar_event()`, unknown → `400`
- [ ] Catch `NotImplementedError` from a stub handler and return `501 Not Implemented` (expected until Phase 2/3 land; not a Phase 1 bug)
- [ ] Return structured JSON response: `{"ok": true, "source": "email", "dry_run": false, "message_id": "..."}` or error shape
- [ ] Add `?dry_run=true` query param — validate envelope (auth + recognized `source`) and return `ok: true` without calling the source handler or writing to the DB
- [ ] Rate-limit guard: reject if > 100 requests/minute from same IP (simple in-memory token bucket — state is ephemeral and resets on worker restart; acceptable for local dashboard spam protection, not a distributed rate limiter)
- [ ] Catch SQLite `database is locked` errors and return `503 Service Unavailable` — Zapier retries on 5xx; a 4xx causes Zapier to drop the payload permanently
- [ ] Structured log line per request: `request_id`, `source`, `dry_run`, `status`, `duration_ms`
- [ ] Add `/api/zapier/health` GET endpoint — returns `{"ok": true, "secret_configured": bool}` (no secret value ever returned)

### Phase 1 QA gate

- [ ] `rebalance doctor` still clean after adding the endpoint
- [ ] `pytest tests/` green (no regressions)
- [ ] `curl -X POST /api/zapier/ingest` with wrong or missing auth → `403`
- [ ] `curl -X POST /api/zapier/ingest` with valid auth + unknown source → `400`
- [ ] `?dry_run=true` with valid auth + recognized `source` returns `ok: true` and writes nothing to DB (envelope-only — does not call the stub handler)
- [ ] `/api/zapier/health` returns `secret_configured: true` when secret is set
- [ ] New tests: `tests/test_zapier_webhook.py` covering Basic Auth accept, Basic Auth reject, optional query-param fallback, routing (dispatch reaches the correct stub and gets its `NotImplementedError`, surfaced as `501`), dry-run, health

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
- Phase 0 confirmed two deliberate v1 drops: there is no destination column for `to`, and there is no full-body storage column. `normalize_zapier_email()` should keep snippet/excerpt text only and ignore `to` unless a later schema change adds a home for it.
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
- `push_calendar_events()` uses the existing `INSERT OR REPLACE` semantics keyed by `(id, calendar_id)` — same logical upsert behavior as the OAuth sync path, but with the migrated composite key.
- Attendees: GCal trigger may include attendees as a comma-separated string or array — normalize to a consistent format matching the existing `calendar_events.attendees` column.
- Phase 0 findings govern which fields are nullable when Zapier cannot supply them.
- The normalized payload will not satisfy every `calendar_events` column by itself. Phase 3 must synthesize `calendar_id` and `fetched_at` locally, and either source `person` from config or leave it `NULL`; `status` should default when the trigger payload omits it.

### Checklist

- [ ] Create `src/rebalance/ingest/zapier_calendar.py`
- [ ] Add `normalize_zapier_calendar(payload: dict) -> list[dict]` to `src/rebalance/ingest/zapier_calendar.py` — all Zapier-specific field mapping lives here
- [ ] Implement `handle_calendar_event(payload: dict) -> dict` in the same module — replaces the Phase 1 `NotImplementedError` stub; calls `normalize_zapier_calendar()` then `push_calendar_events()`
- [ ] Add `push_calendar_events(db_path: str, events: list[dict]) -> dict` to `calendar.py` (single writer, source-agnostic, uses existing `ensure_calendar_schema`)
- [ ] Synthesize non-payload columns in Phase 3: `calendar_id`, `fetched_at`, and optional `person` / default `status`
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

1. If v1 Basic Auth later proves too weak for this threat model, do we want a Code-step/private-Zapier-app HMAC upgrade path, or is transport-level auth sufficient for local/self-hosted deployments?
2. Should the webhook endpoint require the pulse server to be running, or should it also work via the CLI dashboard server (`rebalance serve`)? v1 = pulse server only; revisit if demand exists.
3. Future: should `refresh_index(scope=["zapier"])` be a valid scope to replay buffered Zapier payloads from a local queue? Not in v1.
