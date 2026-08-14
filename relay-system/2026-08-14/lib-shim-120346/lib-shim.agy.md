### 1. ANSWER
Yes, your read is 100% correct. The Phase 2 premise of banning entire stdlib modules is fundamentally flawed because `datetime` and `subprocess` types are legitimately needed across the codebase for signatures and data structures. Re-exporting them through a shim to evade the linter is pure governance theatre—it breaks standard Python idioms, confuses readers, and completely fails to prevent agents from writing duplicate custom logic using the re-exported primitives. 

### 2. FINDINGS
- **[Blocker]** The 64-file stdlib import laundering and `src/rebalance/lib/subprocess_ops.py`. Re-exporting stdlib primitives does not consolidate behavior. This rewrite must be dropped.
- **[Blocker]** The bespoke AST linter (`utils/pdda/check_banned_imports.py`). Banning entire stdlib modules is the wrong semantic level for this governance rule.
- **[Should]** Keep the genuinely deduplicated helpers (Phase 1's `time_ops.py`, `json_ops.py`, `git_ops.py`) and only the specific call site changes that swapped hand-rolled logic for calls to functions like `_parse_iso` or `_now`.
- **[Should]** Replace the module-level ban with a behavior-level ban using standard tooling. For example, configure Ruff's `flake8-tidy-imports.banned-api` (`TID251`) to ban specific function calls like `datetime.now` or `subprocess.run`, and configure the warning to point developers to the shared `lib/` helpers instead.
- **[Pass]** The CI grep precedent you mentioned for banning specific string manipulations (like `\.replace\('Z', ...\)` with `# raw-ok` escapes) is a cheap, highly effective enforcement mechanism for patterns that AST linters struggle to catch.

### 3. RECOMMENDATION
**Rework**: Revert the 64-file import rewrite and custom AST linter, keep the genuine Phase 1 helpers, and enforce their usage via Ruff `banned-api` rules (or targeted CI `grep`) against the specific hallucinated function calls rather than blanket stdlib module bans.
