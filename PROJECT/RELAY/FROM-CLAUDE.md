You previously reviewed Phase 5 of the subsystem refactor (rebalance-OS,
branch feat/subsystem-refactor) and your findings drove fixes. Phase 6 — the
Welcome Agent — is now complete: commits 4dfcdc6..8a66f3c (7 commits,
v0.38.0→v0.39.0). Same job as last time: REFUTE the claims below with
file:line evidence. Verdict per claim (CONFIRMED / REFUTED / PARTIAL), then
ranked findings, then an overall verdict. Evidence or it didn't happen.

Known accepted gaps — do NOT re-report these: the pre-existing figma test
failure; the audit_modules doc backlog; "no secrets in transcript" being
prompt-enforced without an automated test (logged for a hardening pass); the
tokenizer dedup declined in Phase 5.

## Claims to verify

1. **Hermetic seams actually seal ALL machine-global escapes.**
   REBALANCE_NO_KEYRING=1 no-ops every keyring helper; REBALANCE_HERMETIC=1
   additionally disables the gh-CLI token fallback (src/rebalance/ingest/
   config.py). The hermetic walkthrough already caught the gh-CLI leak — your
   job is to find the THIRD escape. Audit every config getter the lifecycle
   checks call (get_calendar_oauth_token_json, get_gmail_oauth_token_json,
   get_vault_path, get_github_token): do any read fixed machine paths
   (~/.config files, token file fallbacks, env vars) that hermetic mode does
   not cover? Would tests/test_welcome_walkthrough.py pass on a machine where
   such a fallback exists, or did it pass here only by accident of this
   operator's storage layout?

2. **Skipped-status semantics are sound.** evaluate_setup
   (src/rebalance/ingest/lifecycle.py): only optional stages can be skipped
   (skip_onboarding_stage refuses required ones), a completed stage always
   wins over a stale skip marker, skipped stages never block setup_complete.
   Try edge cases: a skip marker for a stage id that no longer exists; a
   required stage id smuggled into the config list directly (bypassing the
   MCP tool); skip interactions with `blocked`.

3. **Clients consume the contract, never re-declare it.** The /welcome skill
   (.claude/skills/welcome/SKILL.md), `rebalance onboard --status` and the
   optional-stage offers (src/rebalance/cli/onboard.py), the spike, and the
   walkthrough all dispatch on evaluate_setup output + executor hints. Check
   the CLI executor dispatch specifically (_offer_optional_stages): shlex
   handling, cwd assumptions, the `.venv/bin/python` relative path, behavior
   when find_project_root returns None, and whether skip persistence can
   desync from what the user actually answered.

4. **Local discovery is read-only and correctly deduped.**
   src/rebalance/ingest/local_repos.py + the preflight integration: scanning
   never mutates anything; local candidates dedupe against vault titles,
   remote candidates, and registered projects via casefolded names; no roots
   configured = scanning off everywhere (discovery AND doctor). Probe: name
   collision between a local repo's owner/repo and a vault note title;
   git subprocess failure modes (permission-denied dirs, detached HEAD,
   bare repos); unpushed semantics (no upstream counts as unpushed — agree?).

5. **Reset is safe by construction.** src/rebalance/cli/reset.py: dry-run
   default, vault never touched, keyring delete gated behind
   --include-keyring. Probe: does the com.rebalance-os.* glob miss jobs the
   operator actually runs (com.user.git-pulse, stickies)? Is anything deleted
   that isn't re-creatable by /welcome? Does it handle a half-reset state
   (config gone, DB present) gracefully on re-run?

6. **Graduation stages are honest checks.** schedulers_installed verifies
   only the daily-sync plist exists (not the whole fleet, not that launchd
   loaded it) and first_pulse only that web/pulse.html exists (not freshness).
   Are these exit conditions too weak to mean "graduated", or appropriately
   minimal? What would you require instead?

## Also answer

7. Beta-readiness: you are the first external beta tester running /welcome on
   a fresh Mac tomorrow. Walk the journey mentally against the actual code —
   what breaks first, and at which stage does the agent most likely strand
   the user?
8. Anything hard to reverse later in the contract v2 vocabulary (statuses,
   executor kinds, contract_version semantics) before other clients start
   depending on it?
