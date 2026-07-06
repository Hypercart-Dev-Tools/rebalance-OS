# RELAY · GH-115 Phase 1 — Zapier webhook receiver
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-07-05.
-->

NEXT: Producer
STATUS: Open
ROUND: 1 / 4

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). Do **not** edit the artifact; only append findings here.
   - **Producer:** log a disposition for every open finding (Implemented / Modified / Declined + why),
     make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Escalated`.
6. **Commit only the relay file** (`relay(gh115-phase1): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Paths this lane may touch: `src/rebalance/web.py`, `src/rebalance/ingest/zapier_email.py` (new), `src/rebalance/ingest/zapier_calendar.py` (new), `tests/test_zapier_webhook.py` (new)
- Producer: codex   ·   Reviewer: agy
- Handoff: cli-driven (relay-xyz — codex builds, agy reviews; single-session headless), running against an isolated worktree/branch `marathon/2026-07-06`
- Started: 2026-07-05
- Definition of Done: per [GH-115-ZAPIER-INGEST.md](../../PROJECT/2-WORKING/GH-115-ZAPIER-INGEST.md#phase-1--webhook-receiver) Phase 1 checklist + QA gate — `POST /api/zapier/ingest` route, `_verify_zapier_auth()` (HTTP Basic Auth primary, `?zapier_secret=` fallback, constant-time compare), secret via `resolve_secret_path("zapier-webhook-secret")`, placeholder `zapier_email.py`/`zapier_calendar.py` (`NotImplementedError` stubs, this is the ONLY phase that edits `web.py`'s zapier dispatch), `source`-field routing (unknown → 400), catch `NotImplementedError` → 501, structured JSON response, `?dry_run=true` (validates envelope, writes nothing, never calls the handler), simple in-memory rate-limit guard, catch `database is locked` → 503, structured log line per request, `GET /api/zapier/health`.

## Task brief (for the Producer's first turn)
Part of the 2026-07-06 marathon, Lane B (see [MARATHON-2026-07-06.md](../../PROJECT/2-WORKING/MARATHON-2026-07-06.md#lane-b--gh-115-phase-1-webhook-receiver)). Implements Phase 1 of [GH-115-ZAPIER-INGEST.md](../../PROJECT/2-WORKING/GH-115-ZAPIER-INGEST.md#phase-1--webhook-receiver) — follow its Checklist and Phase 1 QA gate sections exactly (read them in full before starting):

- Add `POST /api/zapier/ingest` to `src/rebalance/web.py`. Auth verification (`_verify_zapier_auth`) runs BEFORE any payload parsing; a failed verify is `403` with no body read.
- Create placeholder `src/rebalance/ingest/zapier_email.py` (`handle_email_event(payload: dict) -> dict`, raises `NotImplementedError("Phase 2 not yet implemented")`) and `src/rebalance/ingest/zapier_calendar.py` (`handle_calendar_event(payload: dict) -> dict`, raises `NotImplementedError("Phase 3 not yet implemented")`). This is the ONLY phase that edits `web.py`'s zapier dispatch — later phases replace their own stub body only.
- Route by `source` field: `"email"` → `zapier_email.handle_email_event()`, `"calendar"` → `zapier_calendar.handle_calendar_event()`, unknown → `400`. Catch `NotImplementedError` from a stub → `501` (expected until Phase 2/3 land, not a bug here).
- `?dry_run=true`: validate the envelope (auth + recognized `source`) and return `ok: true` WITHOUT calling the source handler or writing to the DB.
- Rate-limit guard (simple in-memory token bucket, ~100 req/min/IP — ephemeral state, not a distributed limiter). Catch SQLite `database is locked` → `503` (Zapier retries on 5xx, drops on 4xx). Structured log line per request (`request_id`, `source`, `dry_run`, `status`, `duration_ms`). `GET /api/zapier/health` → `{"ok": true, "secret_configured": bool}` (never return the secret value).
- New tests in `tests/test_zapier_webhook.py`: Basic Auth accept/reject, query-param fallback, routing to the correct stub (surfaced as 501), dry-run, health.
- **Out of scope:** any real email/calendar ingest logic (that's Phase 2/3) — stubs only here.

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
