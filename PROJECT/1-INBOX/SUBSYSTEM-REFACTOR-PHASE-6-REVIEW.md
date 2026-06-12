# Phase 6 Review Findings

Here is the review of Phase 6 (Welcome Agent) based on the claims provided.

## Claims Verification

### 1. Hermetic seams actually seal ALL machine-global escapes.
**VERDICT: CONFIRMED / PARTIAL**
*   **Evidence:** `src/rebalance/ingest/config.py` correctly uses `_resolved_config_path` which is fully sandboxed by `CONFIG_PATH` in the test. `get_github_token` is sealed by `REBALANCE_HERMETIC`. `get_calendar_oauth_token_json` and `get_gmail_oauth_token_json` only check `_keyring_get` (which is sealed).
*   **The Catch:** The OAuth getters *do not* check the pickle file fallback (`resolve_oauth_token_path` / `USER_CONFIG_DIR`) at all. If an operator's machine *only* has the pickle file, `evaluate_setup` will declare the auth incomplete. The test passes on a machine with a pickle file because the getter blindly ignores it, not because it's actively sandboxing it.

### 2. Skipped-status semantics are sound.
**VERDICT: REFUTED**
*   **Evidence:** In `src/rebalance/ingest/lifecycle.py` (`evaluate_setup`), the check `if stage.optional and stage.id in skipped_ids:` precedes `elif not deps_done:`.
*   **Impact:** A skipped stage will receive the `status="skipped"` label even if its dependencies are missing (which should make it `blocked`). This bypasses the block guard in consumers. For example, `_offer_optional_stages` correctly skips offering "blocked" stages, but prompts the user for "skipped" ones. Thus, a user is allowed to execute a stage that is structurally impossible.

### 3. Clients consume the contract, never re-declare it.
**VERDICT: REFUTED**
*   **Evidence 1 (Desync):** In `src/rebalance/cli/onboard.py` (`_offer_optional_stages`), if `questionary.confirm(...).ask()` is interrupted via Ctrl+C, it returns `None`. `not run_it` evaluates to `True`, causing the CLI to erroneously persist the stage as "skipped".
*   **Evidence 2 (Executor assumptions):** The executor dispatch hardcodes `cmd = [".venv/bin/python", target]`. If the operator installed via a global method (e.g., `pipx`) and runs this from an arbitrary directory, `find_project_root` will return `None`. `subprocess.run(cmd, cwd=repo_root)` will then run in the arbitrary `cwd` where `.venv/bin/python` does not exist, causing a crash.

### 4. Local discovery is read-only and correctly deduped.
**VERDICT: PARTIAL**
*   **Evidence:** Deduplication works (vault titles vs local candidates via casefolding). Scanning is read-only (`_git` only uses `remote`, `rev-parse`, `rev-list`).
*   **The Catch (Unpushed semantics):** In `src/rebalance/ingest/local_repos.py`, a detached HEAD or a bare repo will cause `@{upstream}` to fail. `ahead` becomes `None`, which `unpushed_work` treats as unpushed work (`(r.unpushed_commits or 0) > 0 or r.unpushed_commits is None`). This causes detached HEADs to be falsely flagged as having unpushed work.

### 5. Reset is safe by construction.
**VERDICT: REFUTED**
*   **Evidence 1 (Half-reset state):** In `src/rebalance/cli/reset.py`, if the config file is deleted but the database remains, `resolve_database_path()` may raise `DatabaseNotFoundError` on a re-run if the DB path was only stored in the user config layer. The DB files are then left orphaned on disk.
*   **Evidence 2 (Missed Secrets):** `KEYRING_KEYS` explicitly enumerates secrets but misses `sleuth_web_api` (`SLEUTH_KEYRING_KEY`).
*   **Evidence 3 (Missed files):** The reset completely ignores the OAuth pickle files (`resolve_oauth_token_path`). Since they are created by the setup process, failing to delete them violates the promise of returning to a pre-onboarding state. Custom plists (e.g., `com.user.git-pulse`) are also missed by the hardcoded `com.rebalance-os.*` glob.

### 6. Graduation stages are honest checks.
**VERDICT: PARTIAL**
*   **Evidence:** `_check_schedulers_installed` only checks if `com.rebalance-os.daily-sync.plist` exists, not if `launchctl list` indicates it's loaded. `_check_first_pulse` only checks if `web/pulse.html` exists.
*   **Requirement:** These checks are too weak. `pulse.html` could be stale/broken from a previous failed run; an `mtime` check (e.g., < 24 hours old) is required to honestly verify a pulse. For schedulers, checking `launchctl list | grep com.rebalance-os` ensures the fleet is actually loaded.

## Also Answer

### 7. Beta-readiness
The agent will likely strand the beta tester at the optional stages prompt. If the beta tester installs the package globally (as most would on a fresh Mac), `repo_root` will be `None`, and the `[".venv/bin/python", target]` command will instantly fail. Additionally, a simple Ctrl+C during the prompts will silently corrupt their skip state.

### 8. Anything hard to reverse later in the contract v2 vocabulary?
The precedence of `skipped` over `blocked` in the vocabulary. If clients bake in the assumption that a `status="skipped"` stage "can be safely executed now if the user changes their mind" (because they assume `blocked` would have overridden it if dependencies were missing), fixing this precedence later will break clients that didn't independently re-verify dependencies before execution.

---
**OVERALL VERDICT:** Issues found in skipped-status logic, executor paths, and reset cleanup. Fixes required before Phase 6 close.