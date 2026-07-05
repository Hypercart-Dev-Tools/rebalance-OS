# RELAY · GH-115 Phase 0 — Zapier payload schema + auth feasibility spike (rebalance-OS#115)
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 1 / 5

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are the agent bound to it (see Setup) **and** the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup (read the real file / the latest `git show <last commit>` diff; cite `file:line`):
   - **Reviewer:** review vs the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete proposed fix → set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the artifact; you only append findings here. **Before you set `Approved`, re-read the artifact file itself** (not this log) and confirm every prior `Implemented` fix is actually present and complete — any that is missing or partial → set `Changes requested` with a `[Blocker] claimed-implemented-but-absent @ file:line` instead.
   - **Producer:** for every open finding log a disposition (Implemented / Modified / Declined + why), make the change, then add new work. **Before you flip `NEXT`, re-read the artifact and confirm each `Implemented → @ file:line` actually landed in the file** — cite the line as it appears in your commit diff. A claim you can't point to in the file is not done.
4. **Append ONE block** at the very bottom, directly **above** the marker line (`<!-- ↓↓↓ NEXT TURN ... -->`). Never edit earlier turns. Header it `### Round N · <Role> · <your-label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Findings & proposals:**` (graded bullets) + `**Commit:**`; a Producer block carries `**Decisions on proposals:**` + `**Did:**` + `**Re-review this:**` + `**Commit:**`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` (`Approved` closes the relay — Reviewer only; else leave `Open`); the Producer bumps `ROUND` when opening a new cycle.
6. **Commit only the files you touched** (artifact + this log): `git commit -m "relay(gh115-phase0-spike): <your-label> r<N>"`, then put the short hash in your block's `Commit:` line.
7. **Stop.** Report your one-line result.

## Setup
- Artifact under review: `PROJECT/2-WORKING/GH-115-ZAPIER-INGEST.md` (the "Spike findings (Phase 0)" section)
- Definition of Done: the Phase 0 checklist items are answered with concrete field-mapping tables (Zapier Gmail trigger fields → `email_messages` columns; Zapier GCal trigger fields → `calendar_events` columns), a webhook-auth-mechanism decision (HMAC-SHA256 vs shared-secret query param vs Basic Auth, given "Webhooks by Zapier" often gates custom headers behind Zapier Premium), and any `calendar_events` schema gaps flagged. **No code changes** — findings only, written into the doc's "Spike findings (Phase 0)" section, replacing its placeholder prose. The Phase 0 QA gate checklist in the doc should flip to `[x]` where satisfied.
- Producer: codex   ·   Reviewer: agy
- Handoff: cli-driven (relay-xyz — codex builds, agy reviews; single-session headless)
- Started: 2026-07-05

## Task brief (for the Producer's first turn)
Part of the 2026-07-05 marathon, Lane A (see [MARATHON-2026-07-05.md](../../PROJECT/2-WORKING/MARATHON-2026-07-05.md)). Implements the Phase 0 spike from [GH-115-ZAPIER-INGEST.md](../../PROJECT/2-WORKING/GH-115-ZAPIER-INGEST.md#phase-0--spike-zapier-payload-schema--auth-feasibility-1-2h):

- Document Zapier's Gmail trigger output fields (message_id, subject, from, to, date, snippet/body, labels) and Google Calendar trigger output fields (event_id, summary, start, end, location, description, attendees) — from Zapier's publicly documented trigger shapes (no live account access available in this environment; ground the mapping in Zapier's documented "New Email Matching Search"/Gmail trigger and "Event Start"/Google Calendar trigger field sets, and say so plainly rather than fabricating a live-inspected payload).
- Map each field to the existing `email_messages` / `calendar_events` columns (read `src/rebalance/ingest/gmail.py` and `src/rebalance/ingest/calendar.py` for the real column names — do not guess).
- Decide the webhook auth mechanism: HMAC-SHA256 via a custom header vs. a shared-secret query param vs. HTTP Basic Auth, given the doc's note that "Webhooks by Zapier" often restricts custom headers to Premium accounts. Recommend one, with the fallback documented.
- Flag any `calendar_events` columns a Zapier payload cannot populate (nullable / drop from push path).
- Write all findings into the doc's "Spike findings (Phase 0)" section (What was investigated / What was found / What it changes), and tick the Phase 0 checklist + QA gate items that are now satisfied.
- **Out of scope:** any code changes. This phase is findings-only, per the doc's own Phase 0 scope note.

## Ground rules
1. This file is the single source of truth. If it isn't written here, assume the other agent doesn't know it. The two agents may be different tools and never share memory.
2. Read the whole file. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns. Then update `NEXT`, `STATUS`, `ROUND` at the top.
4. Stay tight. Requests and findings are bullets, not essays.
5. **The Reviewer never edits the artifact.** It proposes graded findings, each with a concrete suggested fix where possible. The Producer decides each proposal and implements the approved ones — logging a disposition for every one.
6. Grade every finding: `[Blocker]` must fix to ship · `[Should]` strong recommendation · `[Nit]` optional · `[Pass]` checked and sound.
7. The Reviewer posts a Verdict every turn. The relay ends on **Approved**. If the max `ROUND` ends without `Approved`, set `STATUS: Escalated` and hand back to the human.
8. End your turn by committing it: `relay(gh115-phase0-spike): <role> r<N>`, then fill the hash into your `Commit:` line.
9. **One window at a time, clean tree at every handoff.** Never flip `NEXT` with uncommitted changes left in the tree.
10. **Evidence contract — state your proof every turn.** Producer logs `Verification:`; Reviewer logs `Basis:` (`behaviorally proven` or `textual only`). For this findings-only phase, `behaviorally proven` means "verified the mapped column names against the real source file"; `textual only` covers the Zapier-side field names (no live account to test against).
11. **Reconcile claims against the file, not this log**, before flipping `NEXT` (Producer) or setting `Approved` (Reviewer).

## Roles
- **Producer** — the only writer of the artifact: builds it, requests review, decides and implements proposals, updates.
- **Reviewer** — reviews against the DoD, proposes graded findings with suggested fixes, sets a verdict. Never edits the artifact.

---
## Log

### Round 1 · Producer · codex · 2026-07-05 13:26 PDT
**Decisions on proposals:**

- No prior reviewer proposals in Round 1.

**Did:**

- Replaced the Phase 0 placeholder prose in `PROJECT/2-WORKING/GH-115-ZAPIER-INGEST.md` with concrete findings, two field-mapping tables, and a direct auth recommendation.
- Grounded the local-side mapping against the real writer/schema lines in `src/rebalance/ingest/gmail.py:327`, `src/rebalance/ingest/db/schema.py:240`, `src/rebalance/ingest/calendar.py:173`, and `src/rebalance/ingest/db/migrations/0005_calendar_events_composite_pk.sql:27`.
- Reflected the main assumption-kill downstream: Phase 1 now specifies Basic Auth primary + query-param fallback instead of HMAC-first, and Phase 3 now explicitly carries the non-payload `calendar_events` fields (`calendar_id`, `fetched_at`, optional `person`, defaulted `status`).

**Re-review this:**

- Check the completed Phase 0 findings and checklist state at `PROJECT/2-WORKING/GH-115-ZAPIER-INGEST.md`.
- Verify the auth-contract redirect landed in the Phase 1 section and the composite-key / non-payload-column notes landed in Phase 3.

**Verification:** behaviorally proven for local column names and write-path requirements; textual only for Zapier-side trigger/auth capabilities (public docs only, no live Zap payload available).

**Commit:** pending (harness-owned; user instruction forbids agent-run git)

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->
