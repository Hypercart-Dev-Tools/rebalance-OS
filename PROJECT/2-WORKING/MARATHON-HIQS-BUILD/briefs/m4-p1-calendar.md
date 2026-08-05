---
title: "M4 p1 — calendar.py: read-only OAuth client"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M4 p1 — calendar.py: read-only OAuth client

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after M3 is approved. Fire M4 with `--builder agy`. |

**Canonical spec:** `HIQS-PROJECT.md` §5 (rules 3/7/8), §9 (`calendar_events` columns), Decision 6
(read-only everywhere in v1), §11 (~180 LOC).

## Build

`HiQS/hiqs/sources/calendar.py` — Google Calendar, **read-only scope**, window upsert
(§5 rule 2, pattern 2). Project `id, summary, start, end, project, organizer, attendees_json`.

Token handling goes through `config.secret()` and keyring. The **interactive consent flow belongs
to `hiqs auth calendar`** (M4 scope, wired in p1's CLI stub) — this module consumes a token, it
does not obtain one interactively.

## Acceptance

- **Read-only, enforced structurally:** a test asserts no write method is reachable from
  `HiQS/**` (Decision 6). Scope strings are read-only.
- `sync.failed` on an expired token carries a non-empty `error_type` from the closed vocabulary
  (`auth_expired`|`network`|`rate_limit`|`parse`) **and** a non-empty `message`, and leaves
  `status` reporting `error` for that source — never a silent empty result rendered green
  (L6, L8, Phase 3 gate).
- The `auth_expired` path's remediation text names `hiqs auth calendar`. A failure whose only
  remedy is improvisation is not specced.
- Explicit timeout on every call (rule 7); watermark on success only (rule 8).
- Day boundaries pinned to device-local tz at query time; storage UTC ISO-8601 (§9).
- Fully offline tests — OAuth and the API are stubbed.

## Do not

- Do not create, modify, or delete a calendar event. Not behind a flag, not in a test helper.
- Do not attempt an interactive browser flow inside `fetch` — the runner is an unattended launchd
  job that cannot complete one (Decision 4).
