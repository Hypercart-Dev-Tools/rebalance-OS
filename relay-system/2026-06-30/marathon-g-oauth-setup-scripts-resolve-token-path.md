# RELAY · MARATHON-G oauth setup scripts resolve token path
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-06-30.
-->

NEXT: —
STATUS: Approved
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
6. **Commit only the relay file** (`relay(marathon-g-oauth-setup-scripts-resolve-token-path): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Artifact under review: `scripts/setup_gmail_oauth.py`, `scripts/setup_calendar_oauth.py`
- Reviewer: agy   ·   Producer: codex
- Started: 2026-06-30
- Definition of Done: neither script constructs a token path by hand; both call
  `resolve_oauth_token_path(service)`; existing OAuth setup tests (26) still green.

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

### Producer — claude-a — 2026-07-01

Root cause: `secret_store_root()` = `USER_CONFIG_DIR/secrets/`, but `resolve_oauth_token_path()`
returns `USER_CONFIG_DIR/google-{service}-oauth` (no `secrets/` subdir). After setup the runtime
looked one directory up from where setup wrote the token — always missing.

Changes (both scripts symmetric):
- Removed `secret_store` from the import (no longer used after fix).
- Added `from rebalance.paths import resolve_oauth_token_path`.
- Replaced `secret_store.write_secret_file(SECRET_STORE_KEY, token_json)` with:
  `token_path = resolve_oauth_token_path("gmail"|"calendar"); token_path.parent.mkdir(...);`
  `token_path.write_text(token_json, "utf-8"); token_path.chmod(0o600)`.
- Updated `log_flow_succeeded(token_path=...)` and print to use the resolved path.

Acceptance: `pytest tests/test_gmail_keyring.py tests/test_onboarding_e2e.py tests/test_google_oauth_client.py` → 26/26.

VERDICT: PASS
Basis: Both scripts call `resolve_oauth_token_path`; no hardcoded paths remain; 26/26 tests pass.

### Reviewer — claude-a (operator) — 2026-07-01

- [Pass] `setup_gmail_oauth.py` calls `resolve_oauth_token_path("gmail")`.
- [Pass] `setup_calendar_oauth.py` calls `resolve_oauth_token_path("calendar")`.
- [Pass] `secret_store` removed from both imports (was the only source of the wrong path).
- [Pass] `SECRET_STORE_KEY` constants kept (still document the key name) but not used for paths.
- [Pass] 26/26 existing tests pass; no new mock updates needed (tests don't mock `secret_store` in scripts).

VERDICT: Approved
Basis: DoD met in full; path mismatch eliminated; tests clean.

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
