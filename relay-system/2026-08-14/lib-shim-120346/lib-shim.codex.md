**NO FIRSTHAND VERIFICATION CITED** — treat conclusions as conditional (codex's answer carries an unsupported [Pass]/verified/confirmed-style claim with no quoted span or file:line citation nearby, despite the consult PREAMBLE asking advisors to cite evidence.)

> **ATTESTATION**
> Model: gpt-5.6-terra
> Provider: openai
> Sandbox: read-only

Reading additional input from stdin...
2026-08-14T19:03:47.556196Z ERROR codex_models_manager::cache: failed to load models cache: missing field `base_instructions` at line 95 column 5
OpenAI Codex v0.144.6
--------
workdir: /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
model: gpt-5.6-terra
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 01a001a8-b1fe-7770-9c9c-e7b7f55a6ed6
--------
user
You are an INDEPENDENT advisor in a one-shot cross-model consult. Another model is answering the SAME question separately and a coordinator will reconcile both answers, so give your own honest, specific read — do not hedge toward a consensus you cannot see. Read any repo files the question references (cite file:line). Respond with: (1) a short direct ANSWER; (2) graded FINDINGS — [Blocker]/[Should]/[Nit]/[Pass] — where applicable; (3) a one-line RECOMMENDATION. You are ADVISORY ONLY: output your analysis as text; do not rely on writing files (you are running in a throwaway copy).

=== CONSULT QUESTION ===
# Question: is this DRY-governance refactor sound, or should it be reworked before commit?

Repo: rebalance-OS (Python). Branch `feature/gh-266-phase3`. There are ~64 files of
**uncommitted** work in the tree right now. I want an independent read on whether it
should be committed as-is, reworked, or abandoned.

## Background — what problem was being solved

GitHub issue #266 was an architectural audit. It found genuine duplication, e.g.
`_parse_iso` defined 3×, `_now_iso` 3×, `_json_dumps` 3×, `_git` 4×, `as_dict` 19×.

The plan (`PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md`) had 3 phases:

- Phase 1: extract the duplicated helpers into `src/rebalance/lib/{time_ops,json_ops,git_ops}.py`
- Phase 2: **governance** — "enforce importing `datetime`, `json` and `subprocess`
  exclusively from `rebalance.lib.*`", and "implement an import linter to physically
  fail the build on restricted imports"
- Phase 3: delete redundant query layers

Phase 2's stated intent (from the plan's "Quad Concepts" section) was:
> "Agents hallucinating duplicate checks via grep_search → Ban raw `datetime`/`subprocess`
> imports outside `lib/` and enforce via CI import-linter."

## What is actually in the working tree now

`utils/pdda/check_banned_imports.py` is an AST linter that walks `src/rebalance/` and
fails the build on any `import datetime` / `import subprocess` / `from datetime import ...`
/ `from subprocess import ...` outside a path containing `lib`. It is now wired into
`.github/workflows/ci.yml`.

To satisfy that linter, ~64 files were rewritten to import through new shim modules.
The **entire** content of `src/rebalance/lib/subprocess_ops.py` is:

```python
from subprocess import run, Popen, PIPE, TimeoutExpired, CalledProcessError, check_output, check_call, DEVNULL, SubprocessError

# Re-exported for use across the project to comply with banned imports.
```

`src/rebalance/lib/time_ops.py` begins:

```python
from datetime import datetime, timezone, timedelta, date, time
```

...and then defines some genuinely shared helpers (`_parse_iso`, `_now_iso`, `_now`).

Call sites were rewritten mechanically, e.g. in `src/rebalance/doctor.py`:

```python
-import subprocess
+import rebalance.lib.subprocess_ops as subprocess
-from datetime import datetime, timezone
+from rebalance.lib.time_ops import datetime, timezone
```

An untracked script `fix_imports.py` at the repo root appears to be what performed this
rewrite. (Please read these files directly — they are all in the worktree you have.)

## The specific worry I want pressure-tested

The original duplication was of **behavior** (four different hand-rolled `_git`
wrappers, three `_parse_iso`s that disagreed on edge cases). Consolidating *those* is
clearly correct and is what Phase 1 did.

But `datetime` and `subprocess` are not duplicated behavior — they are the stdlib. My
concern is that re-exporting stdlib names through a shim and rewriting 64 files to
import `datetime` from `rebalance.lib.time_ops` satisfies the linter **mechanically**
while delivering none of the intent: every call site still gets raw stdlib semantics,
just laundered through a module the linter can't see into. It arguably makes things
worse — `import rebalance.lib.subprocess_ops as subprocess` is actively deceptive to a
reader, since the name `subprocess` now refers to something that is not the stdlib
module (and is missing most of its surface).

## What I want from you

1. **Is my read correct**, or am I missing a real benefit of the shim approach
   (e.g. a genuine future seam for injecting timeouts / freezing time / mocking)?
2. **Should this be committed, reworked, or dropped?** Be decisive.
3. If reworked: **what is the smallest change** that keeps the legitimate Phase 1 win
   (the real deduplicated helpers) and gets a governance rule that is *enforceable
   without being theatre*? Consider specifically:
   - narrowing the ban to the actual duplicated helpers rather than to stdlib modules
   - whether a lint rule can even express "don't hand-roll a fifth `_parse_iso`"
   - whether existing tooling (ruff, flake8-tidy-imports banned-api, pylint) already
     does this, so no bespoke AST linter is needed at all
4. Is there a **cheaper enforcement** that gets the real goal (stop agents re-inventing
   helpers) without a 64-file diff? Note the repo already has a working precedent: a CI
   grep that bans raw `.replace('Z', ...)` outside a canonical `parse_calendar_dt()`
   and requires a `# raw-ok` marker to opt out.

Be blunt. If the whole Phase 2 premise is wrong, say so. If the 64-file diff is
recoverable with a small change, say exactly what. Advisory only — do not edit files.

hook: SessionStart
hook: SessionStart Completed
codex
I’ll inspect the plan, linter, CI wiring, shims, rewrite script, and representative call sites, then give a commit-level recommendation with file/line evidence.
mcp: codebase-memory-mcp/list_projects started
mcp: codebase-memory-mcp/list_projects (failed)
user cancelled MCP tool call
mcp: codebase-memory-mcp/index_repository started
mcp: codebase-memory-mcp/index_repository (failed)
user cancelled MCP tool call
exec
/bin/zsh -lc 'git status --short && git diff --stat && git diff -- .github/workflows/ci.yml utils/pdda/check_banned_imports.py src/rebalance/lib/subprocess_ops.py src/rebalance/lib/time_ops.py fix_imports.py PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md' in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
2026-08-14T19:04:13.275100Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
 succeeded in 8934ms:
2026-08-14 12:04:05.302 xcodebuild[95735:100280267]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:05.794 xcodebuild[95735:100280265] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-01BWa2JV' (errno=Operation not permitted)
2026-08-14 12:04:06.628 xcodebuild[95886:100280550]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:06.858 xcodebuild[95886:100280549] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
?? CONSULT-Q.md
?? PROJECT/1-INBOX/3EYES-2026-08-14-collector-sync-degraded-2-unexplained-error-s.md
?? fix_imports.py
?? relay-system/2026-08-14/
?? src/rebalance/lib/subprocess_ops.py
?? test_hiqs.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-CU84nQOg' (errno=Operation not permitted)
2026-08-14 12:04:08.474 xcodebuild[95912:100280833]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:08.680 xcodebuild[95912:100280651] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-JUSr21my' (errno=Operation not permitted)
2026-08-14 12:04:09.281 xcodebuild[96043:100280871]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:09.470 xcodebuild[96043:100280870] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-56qRcCHR' (errno=Operation not permitted)
2026-08-14 12:04:11.067 xcodebuild[96185:100281238]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:11.283 xcodebuild[96185:100281236] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-Wad39nRW' (errno=Operation not permitted)
2026-08-14 12:04:11.970 xcodebuild[96195:100281302]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:12.210 xcodebuild[96195:100281288] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.

exec
/bin/zsh -lc "git diff --cached --stat; git diff --cached --name-status; rg -n -C 4 \"check_banned_imports|banned-import|banned imports|subprocess_ops\" .github/workflows/ci.yml utils/pdda/check_banned_imports.py src/rebalance/lib/time_ops.py src/rebalance/doctor.py PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md fix_imports.py; nl -ba src/rebalance/lib/subprocess_ops.py; nl -ba utils/pdda/check_banned_imports.py; nl -ba .github/workflows/ci.yml | sed -n '1,240p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
2026-08-14T19:04:24.200076Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
 succeeded in 5189ms:
2026-08-14 12:04:19.239 xcodebuild[96783:100282333]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:19.465 xcodebuild[96783:100282331] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-7pZbgvlK' (errno=Operation not permitted)
2026-08-14 12:04:20.085 xcodebuild[96816:100282457]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:20.288 xcodebuild[96816:100282454] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-T2LCLCwU' (errno=Operation not permitted)
2026-08-14 12:04:21.845 xcodebuild[96959:100282725]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:22.119 xcodebuild[96959:100282708] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-WTMqsOIH' (errno=Operation not permitted)
2026-08-14 12:04:22.803 xcodebuild[96969:100282858]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:23.018 xcodebuild[96969:100282857] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
fix_imports.py-23-        elif stripped.startswith('from datetime import'):
fix_imports.py-24-            new_lines.append(indent + stripped.replace('from datetime', 'from rebalance.lib.time_ops'))
fix_imports.py-25-            modified = True
fix_imports.py-26-        elif stripped.startswith('import subprocess'):
fix_imports.py:27:            new_lines.append(indent + 'import rebalance.lib.subprocess_ops as subprocess')
fix_imports.py-28-            modified = True
fix_imports.py-29-        elif stripped.startswith('from subprocess import'):
fix_imports.py:30:            new_lines.append(indent + stripped.replace('from subprocess', 'from rebalance.lib.subprocess_ops'))
fix_imports.py-31-            modified = True
fix_imports.py-32-        else:
fix_imports.py-33-            new_lines.append(line)
fix_imports.py-34-            
--
.github/workflows/ci.yml-70-            echo "::error::Raw duration calc found — use event_duration_minutes() from calendar_helpers.py"
.github/workflows/ci.yml-71-            exit 1
.github/workflows/ci.yml-72-          fi
.github/workflows/ci.yml-73-
.github/workflows/ci.yml:74:      - name: Check for banned imports
.github/workflows/ci.yml:75:        run: python utils/pdda/check_banned_imports.py
.github/workflows/ci.yml-76-
.github/workflows/ci.yml-77-      - name: Check for duplicate code
.github/workflows/ci.yml-78-        run: |
.github/workflows/ci.yml-79-          python -m pip install pylint
--
src/rebalance/doctor.py-13-
src/rebalance/doctor.py-14-import json
src/rebalance/doctor.py-15-import os
src/rebalance/doctor.py-16-import re
src/rebalance/doctor.py:17:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/doctor.py-18-from dataclasses import dataclass, field
src/rebalance/doctor.py-19-from rebalance.lib.time_ops import datetime, timezone
src/rebalance/doctor.py-20-from pathlib import Path
src/rebalance/doctor.py-21-from typing import Callable, Literal
     1	from subprocess import run, Popen, PIPE, TimeoutExpired, CalledProcessError, check_output, check_call, DEVNULL, SubprocessError
     2	
     3	# Re-exported for use across the project to comply with banned imports.
     1	import os
     2	import ast
     3	import sys
     4	from pathlib import Path
     5	
     6	def check_file(path: Path) -> list[str]:
     7	    errors = []
     8	    try:
     9	        content = path.read_text(encoding="utf-8")
    10	        tree = ast.parse(content, filename=str(path))
    11	    except Exception as e:
    12	        return []
    13	
    14	    is_lib = "lib" in path.parts
    15	
    16	    for node in ast.walk(tree):
    17	        if isinstance(node, ast.Import):
    18	            for alias in node.names:
    19	                if alias.name in ("subprocess", "datetime") and not is_lib:
    20	                    errors.append(f"{path}:{node.lineno}: Banned import '{alias.name}'. Use rebalance.lib instead.")
    21	        elif isinstance(node, ast.ImportFrom):
    22	            if node.module in ("subprocess", "datetime") and not is_lib:
    23	                errors.append(f"{path}:{node.lineno}: Banned import from '{node.module}'. Use rebalance.lib instead.")
    24	    return errors
    25	
    26	def main():
    27	    root_dir = Path("src/rebalance")
    28	    any_errors = False
    29	    for root, _, files in os.walk(root_dir):
    30	        for file in files:
    31	            if file.endswith(".py"):
    32	                path = Path(root) / file
    33	                errors = check_file(path)
    34	                for err in errors:
    35	                    print(err)
    36	                    any_errors = True
    37	    
    38	    sys.exit(1 if any_errors else 0)
    39	
    40	if __name__ == "__main__":
    41	    main()
     1	name: CI
     2	
     3	# `development` is the integration branch and the repo default — every feature
     4	# branch is cut from it and merged back into it. Triggering on `main` alone meant
     5	# the branch that receives all the work had ZERO checks, which is how GH-124
     6	# merged 10 failing tests on 2026-07-11 and went unnoticed for 9 days (GH-178).
     7	# `main` stays listed so release merges are still gated. (GH-177)
     8	on:
     9	  push:
    10	    branches: [main, development]
    11	  pull_request:
    12	    branches: [main, development]
    13	
    14	jobs:
    15	  test:
    16	    runs-on: ubuntu-latest
    17	    timeout-minutes: 10
    18	    strategy:
    19	      matrix:
    20	        python-version: ["3.12", "3.13"]
    21	
    22	    steps:
    23	      - uses: actions/checkout@v4
    24	
    25	      - name: Set up Python ${{ matrix.python-version }}
    26	        uses: actions/setup-python@v5
    27	        with:
    28	          python-version: ${{ matrix.python-version }}
    29	
    30	      - name: Install dependencies
    31	        run: |
    32	          python -m pip install --upgrade pip
    33	          # server extra: rebalance.web imports FastAPI at module level, so
    34	          # the web-surface tests need it. pytest: the suite is pytest-run
    35	          # locally and some modules are pytest-style (unittest discover
    36	          # can't collect them, and one imports pytest at module scope).
    37	          pip install -e ".[calendar,server]" pytest
    38	
    39	      # tests/test_pulse_reconcile.py drives real `git pull --rebase` against a
    40	      # throwaway clone. Without an identity that dies with code 128 on a fresh
    41	      # runner — a CI-environment gap, not a product bug, and one only CI ever
    42	      # hits (developer machines always have a global identity). (GH-177)
    43	      - name: Configure git identity for tests
    44	        run: |
    45	          git config --global user.email "ci@rebalance-os.invalid"
    46	          git config --global user.name "rebalance-OS CI"
    47	          git config --global init.defaultBranch main
    48	
    49	      - name: Run tests
    50	        run: python -m pytest tests/ utils/3-eyes/tests -q
    51	
    52	      - name: 3-Eyes dashboard is in sync with the registry (GH-195)
    53	        run: python -m three_eyes.dashboard --check
    54	        working-directory: utils/3-eyes
    55	        env:
    56	          PYTHONPATH: ${{ github.workspace }}/utils/3-eyes
    57	
    58	      - name: Check for raw datetime parsing (use parse_calendar_dt)
    59	        run: |
    60	          if grep -rn "replace('Z'" src/rebalance/ --include="*.py" \
    61	               | grep -v "# raw-ok" | grep -v calendar_helpers.py | grep -v "src/rebalance/lib/"; then
    62	            echo "::error::Raw Z-replace found — use parse_calendar_dt() from calendar_helpers.py"
    63	            exit 1
    64	          fi
    65	
    66	      - name: Check for raw duration calculation (use event_duration_minutes)
    67	        run: |
    68	          if grep -rn "total_seconds() / 60" src/rebalance/ --include="*.py" \
    69	               | grep -v "# raw-ok" | grep -v calendar_helpers.py | grep -v "src/rebalance/lib/"; then
    70	            echo "::error::Raw duration calc found — use event_duration_minutes() from calendar_helpers.py"
    71	            exit 1
    72	          fi
    73	
    74	      - name: Check for banned imports
    75	        run: python utils/pdda/check_banned_imports.py
    76	
    77	      - name: Check for duplicate code
    78	        run: |
    79	          python -m pip install pylint
    80	          pylint --disable=all --enable=duplicate-code src/rebalance/

exec
/bin/zsh -lc "git branch --show-current; git log --oneline --decorate -8; git merge-base HEAD development; git diff --stat development...HEAD; git diff --name-status development...HEAD; nl -ba src/rebalance/lib/time_ops.py | sed -n '1,240p'; nl -ba fix_imports.py | sed -n '1,180p'; nl -ba PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md | sed -n '1,300p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
2026-08-14T19:04:41.120847Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
2026-08-14T19:04:42.687772Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
 succeeded in 13983ms:
2026-08-14 12:04:31.451 xcodebuild[97607:100284355]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:31.730 xcodebuild[97607:100284354] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-dFJ5Yv0S' (errno=Operation not permitted)
2026-08-14 12:04:32.378 xcodebuild[97742:100284581]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:32.640 xcodebuild[97742:100284580] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-1Ec0ahes' (errno=Operation not permitted)
2026-08-14 12:04:34.332 xcodebuild[97890:100284981]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:34.603 xcodebuild[97890:100284980] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-1jguR1sY' (errno=Operation not permitted)
2026-08-14 12:04:35.349 xcodebuild[97896:100285036]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:35.579 xcodebuild[97896:100285033] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
070c0f4d (HEAD) WIP on feature/gh-266-phase3: 21bc1b5e fix(GH-266): Resolve broken test assertions and dangling imports
4c87381b index on feature/gh-266-phase3: 21bc1b5e fix(GH-266): Resolve broken test assertions and dangling imports
21bc1b5e (origin/feature/gh-266-phase3, feature/gh-266-phase3) fix(GH-266): Resolve broken test assertions and dangling imports
c88fdddc chore: Phase 3 (Technical Debt Eradication) - Remove redundant query methods and refactor TF-IDF batching
8b92ee81 (origin/feature/gh-266-architectural-audit, feature/gh-266-architectural-audit) Phase 2: Add mechanical governance rules and import linter (GH-266)
69c5f917 Phase 1: Extract redundant utilities and refactor existing ingest collectors (GH-266)
cda5a433 (origin/development, origin/HEAD, gh-198-local-qwen-mlx, development) Merge pull request #262 from Hypercart-Dev-Tools/chore/version-sync-0.68.7
61496588 chore: date the 0.68.7 entry to its ship date
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-A3Hdw2Ck' (errno=Operation not permitted)
2026-08-14 12:04:37.210 xcodebuild[98063:100285390]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:37.422 xcodebuild[98063:100285388] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-O45eqVCn' (errno=Operation not permitted)
2026-08-14 12:04:38.006 xcodebuild[98084:100285456]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:38.216 xcodebuild[98084:100285455] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
cda5a4338b5ef96b70252ac0cbbeb943586814ef
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-lZm4cdpj' (errno=Operation not permitted)
2026-08-14 12:04:39.774 xcodebuild[98251:100285869]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:40.040 xcodebuild[98251:100285867] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-v0Xt3DJw' (errno=Operation not permitted)
2026-08-14 12:04:40.763 xcodebuild[98390:100286123]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:40.997 xcodebuild[98390:100286115] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
 .claude/settings.json                              |  19 +-
 .../scratch/refactor.py                            |  80 ++++++
 .github/workflows/ci.yml                           |  14 +-
 .pdda-quad                                         |   4 +
 AGENTS.md                                          |   2 +
 ARCHITECTURE.md                                    |   2 +
 ...ollector-sync-degraded-2-unexplained-error-s.md |  37 +++
 ...ollector-sync-degraded-2-unexplained-error-s.md |  37 +++
 ...ollector-sync-degraded-2-unexplained-error-s.md |  37 +++
 ...ollector-sync-degraded-4-unexplained-error-s.md |  39 +++
 ...ES-2026-08-04-collector-run-wrote-no-outcome.md |  35 +++
 ...ollector-sync-degraded-1-unexplained-error-s.md |  36 +++
 ...ector-sync-complete-1-unexplained-error-s-ou.md |  36 +++
 ...ollector-sync-degraded-2-unexplained-error-s.md |  37 +++
 .../3EYES-2026-08-10-collector-sync-stale-74h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-75h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-76h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-77h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-78h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-79h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-80h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-81h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-85h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-86h.md   |  32 +++
 ...ector-sync-complete-6-unexplained-error-s-ou.md |  41 +++
 PROJECT/1-INBOX/RADAR-REPORT-2026-08-07.md         | 281 +++++++++++++++++++++
 PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md    |  63 +++++
 PROJECT/PDDA.md                                    |  96 ++++++-
 ROADMAP.md                                         |   2 +
 ROUTER.md                                          |   2 +
 phases/gh195-p8-fleet-adoption--p1/RELAY.md        |  96 +++++++
 .../gh195-p8-fleet-adoption--p8-cutover/RELAY.md   | 113 +++++++++
 phases/gh195-p8-fleet-adoption--p8-wave2/RELAY.md  |  90 +++++++
 phases/gh195-p8-fleet-adoption--p8-wave3/RELAY.md  | 109 ++++++++
 .../RELAY.md                                       | 134 ++++++++++
 src/rebalance/chat.py                              |   2 +-
 src/rebalance/cli/__init__.py                      |   2 +-
 src/rebalance/cli/calendar.py                      |   8 +-
 src/rebalance/cli/dashboard.py                     |   2 +-
 src/rebalance/cli/github.py                        |  10 +-
 src/rebalance/cli/onboard.py                       |   2 +-
 src/rebalance/cli/query.py                         |   8 +-
 src/rebalance/cli/raw.py                           |  10 +-
 src/rebalance/cli/reset.py                         |   2 +-
 src/rebalance/doctor.py                            |   6 +-
 src/rebalance/health.py                            |  14 +-
 src/rebalance/ingest/apple_reminders.py            |   2 +-
 src/rebalance/ingest/apple_reminders_write.py      |   9 +-
 src/rebalance/ingest/ask_self_scan.py              |   4 +-
 src/rebalance/ingest/audit.py                      |   2 +-
 src/rebalance/ingest/auth_log.py                   |   2 +-
 src/rebalance/ingest/calendar.py                   |   2 +-
 src/rebalance/ingest/calendar_helpers.py           |   8 +-
 src/rebalance/ingest/calendar_snap.py              |   2 +-
 src/rebalance/ingest/claude_cloud.py               |   5 +-
 src/rebalance/ingest/code_collector.py             |   2 +-
 src/rebalance/ingest/config.py                     |   4 +-
 src/rebalance/ingest/daily_report.py               |   2 +-
 src/rebalance/ingest/db/migrate.py                 |   2 +-
 src/rebalance/ingest/diagnose.py                   |  17 +-
 src/rebalance/ingest/embedder.py                   |  57 +----
 src/rebalance/ingest/figma.py                      |  12 +-
 src/rebalance/ingest/focus5_scan.py                |  19 +-
 src/rebalance/ingest/github_commit_backfill.py     |   9 +-
 src/rebalance/ingest/github_coverage.py            |   9 +-
 src/rebalance/ingest/github_direct_commits.py      |   7 +-
 src/rebalance/ingest/github_knowledge.py           |  45 +---
 src/rebalance/ingest/github_readiness.py           |   7 +-
 src/rebalance/ingest/github_reconciliation.py      |   7 +-
 src/rebalance/ingest/github_scan.py                |   2 +-
 src/rebalance/ingest/github_watch.py               |   2 +-
 src/rebalance/ingest/gmail.py                      |   2 +-
 src/rebalance/ingest/goals_file.py                 |   2 +-
 src/rebalance/ingest/index_ops.py                  |  18 +-
 src/rebalance/ingest/local_repos.py                |  12 +-
 src/rebalance/ingest/next_actions.py               |   2 +-
 src/rebalance/ingest/note_builder.py               |   2 +-
 src/rebalance/ingest/note_ingester.py              |  93 ++++---
 src/rebalance/ingest/preflight.py                  |   2 +-
 src/rebalance/ingest/profile_sync.py               |   8 +-
 src/rebalance/ingest/project_inference.py          |   2 +-
 src/rebalance/ingest/pulse.py                      |  11 +-
 src/rebalance/ingest/pulse_health.py               |   2 +-
 src/rebalance/ingest/querier.py                    |  42 +--
 src/rebalance/ingest/semantic_index.py             |   6 +-
 src/rebalance/ingest/sleuth_reminders.py           |   4 +-
 src/rebalance/ingest/sync_snapshot.py              |   4 +-
 src/rebalance/ingest/token_meta.py                 |   2 +-
 src/rebalance/ingest/weekly_report.py              |   2 +-
 src/rebalance/lib/__init__.py                      |   0
 src/rebalance/lib/git_ops.py                       |  15 ++
 src/rebalance/lib/json_ops.py                      |   6 +
 src/rebalance/lib/time_ops.py                      |  37 +++
 src/rebalance/mcp/tools/calendar.py                |   4 +-
 src/rebalance/mcp/tools/hygiene.py                 |   2 +-
 src/rebalance/mcp/tools/retrieval.py               |  40 ---
 src/rebalance/tz_utils.py                          |  20 +-
 src/rebalance/web.py                               |   4 +-
 tests/test_focus5_scan.py                          |   6 +-
 tests/test_gemini_key_resolution.py                |   8 +-
 tests/test_github_knowledge.py                     |  13 +-
 tests/test_mlx_cache_cap.py                        |   8 +-
 tests/test_mlx_instrumentation.py                  |   1 -
 tests/test_retrieval_contracts.py                  |  19 --
 utils/pdda/PDDA-INSTALL.md                         |  18 +-
 utils/pdda/check_banned_imports.py                 |  41 +++
 utils/pdda/pdda-lib.sh                             |  94 ++++++-
 utils/pdda/pdda.sh                                 | 246 +++++++++++++++++-
 108 files changed, 2380 insertions(+), 485 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-xjfG740O' (errno=Operation not permitted)
2026-08-14 12:04:42.796 xcodebuild[98538:100286507]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:42.994 xcodebuild[98538:100286506] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-qScRycbl' (errno=Operation not permitted)
2026-08-14 12:04:43.652 xcodebuild[98543:100286538]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:04:43.861 xcodebuild[98543:100286527] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
M	.claude/settings.json
A	.gemini/antigravity/brain/10c0a689-61ad-4401-b5e0-86c1235b0c01/scratch/refactor.py
M	.github/workflows/ci.yml
A	.pdda-quad
M	AGENTS.md
M	ARCHITECTURE.md
A	PROJECT/1-INBOX/3EYES-2026-07-31-collector-sync-degraded-2-unexplained-error-s.md
A	PROJECT/1-INBOX/3EYES-2026-08-01-collector-sync-degraded-2-unexplained-error-s.md
A	PROJECT/1-INBOX/3EYES-2026-08-02-collector-sync-degraded-2-unexplained-error-s.md
A	PROJECT/1-INBOX/3EYES-2026-08-03-collector-sync-degraded-4-unexplained-error-s.md
A	PROJECT/1-INBOX/3EYES-2026-08-04-collector-run-wrote-no-outcome.md
A	PROJECT/1-INBOX/3EYES-2026-08-04-collector-sync-degraded-1-unexplained-error-s.md
A	PROJECT/1-INBOX/3EYES-2026-08-05-collector-sync-complete-1-unexplained-error-s-ou.md
A	PROJECT/1-INBOX/3EYES-2026-08-06-collector-sync-degraded-2-unexplained-error-s.md
A	PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-74h.md
A	PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-75h.md
A	PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-76h.md
A	PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-77h.md
A	PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-78h.md
A	PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-79h.md
A	PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-80h.md
A	PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-81h.md
A	PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-85h.md
A	PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-86h.md
A	PROJECT/1-INBOX/3EYES-2026-08-11-collector-sync-complete-6-unexplained-error-s-ou.md
A	PROJECT/1-INBOX/RADAR-REPORT-2026-08-07.md
A	PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md
M	PROJECT/PDDA.md
M	ROADMAP.md
M	ROUTER.md
A	phases/gh195-p8-fleet-adoption--p1/RELAY.md
A	phases/gh195-p8-fleet-adoption--p8-cutover/RELAY.md
A	phases/gh195-p8-fleet-adoption--p8-wave2/RELAY.md
A	phases/gh195-p8-fleet-adoption--p8-wave3/RELAY.md
A	phases/gh195-p8-fleet-adoption-resume--p8-cutover/RELAY.md
M	src/rebalance/chat.py
M	src/rebalance/cli/__init__.py
M	src/rebalance/cli/calendar.py
M	src/rebalance/cli/dashboard.py
M	src/rebalance/cli/github.py
M	src/rebalance/cli/onboard.py
M	src/rebalance/cli/query.py
M	src/rebalance/cli/raw.py
M	src/rebalance/cli/reset.py
M	src/rebalance/doctor.py
M	src/rebalance/health.py
M	src/rebalance/ingest/apple_reminders.py
M	src/rebalance/ingest/apple_reminders_write.py
M	src/rebalance/ingest/ask_self_scan.py
M	src/rebalance/ingest/audit.py
M	src/rebalance/ingest/auth_log.py
M	src/rebalance/ingest/calendar.py
M	src/rebalance/ingest/calendar_helpers.py
M	src/rebalance/ingest/calendar_snap.py
M	src/rebalance/ingest/claude_cloud.py
M	src/rebalance/ingest/code_collector.py
M	src/rebalance/ingest/config.py
M	src/rebalance/ingest/daily_report.py
M	src/rebalance/ingest/db/migrate.py
M	src/rebalance/ingest/diagnose.py
M	src/rebalance/ingest/embedder.py
M	src/rebalance/ingest/figma.py
M	src/rebalance/ingest/focus5_scan.py
M	src/rebalance/ingest/github_commit_backfill.py
M	src/rebalance/ingest/github_coverage.py
M	src/rebalance/ingest/github_direct_commits.py
M	src/rebalance/ingest/github_knowledge.py
M	src/rebalance/ingest/github_readiness.py
M	src/rebalance/ingest/github_reconciliation.py
M	src/rebalance/ingest/github_scan.py
M	src/rebalance/ingest/github_watch.py
M	src/rebalance/ingest/gmail.py
M	src/rebalance/ingest/goals_file.py
M	src/rebalance/ingest/index_ops.py
M	src/rebalance/ingest/local_repos.py
M	src/rebalance/ingest/next_actions.py
M	src/rebalance/ingest/note_builder.py
M	src/rebalance/ingest/note_ingester.py
M	src/rebalance/ingest/preflight.py
M	src/rebalance/ingest/profile_sync.py
M	src/rebalance/ingest/project_inference.py
M	src/rebalance/ingest/pulse.py
M	src/rebalance/ingest/pulse_health.py
M	src/rebalance/ingest/querier.py
M	src/rebalance/ingest/semantic_index.py
M	src/rebalance/ingest/sleuth_reminders.py
M	src/rebalance/ingest/sync_snapshot.py
M	src/rebalance/ingest/token_meta.py
M	src/rebalance/ingest/weekly_report.py
A	src/rebalance/lib/__init__.py
A	src/rebalance/lib/git_ops.py
A	src/rebalance/lib/json_ops.py
A	src/rebalance/lib/time_ops.py
M	src/rebalance/mcp/tools/calendar.py
M	src/rebalance/mcp/tools/hygiene.py
M	src/rebalance/mcp/tools/retrieval.py
M	src/rebalance/tz_utils.py
M	src/rebalance/web.py
M	tests/test_focus5_scan.py
M	tests/test_gemini_key_resolution.py
M	tests/test_github_knowledge.py
M	tests/test_mlx_cache_cap.py
M	tests/test_mlx_instrumentation.py
M	tests/test_retrieval_contracts.py
M	utils/pdda/PDDA-INSTALL.md
A	utils/pdda/check_banned_imports.py
M	utils/pdda/pdda-lib.sh
M	utils/pdda/pdda.sh
     1	from datetime import datetime, timezone, timedelta, date, time
     2	
     3	from typing import Any
     4	
     5	def _parse_iso(raw: Any, force_utc: bool = True) -> datetime | None:
     6	    if not raw or not isinstance(raw, str):
     7	        return None
     8	    text = raw.strip().replace("Z", "+00:00")
     9	    
    10	    parsed = None
    11	    for candidate in (text, text.replace(" ", "T")):
    12	        try:
    13	            parsed = datetime.fromisoformat(candidate)
    14	            break
    15	        except ValueError:
    16	            continue
    17	            
    18	    if not parsed:
    19	        return None
    20	        
    21	    if force_utc:
    22	        if parsed.tzinfo is None:
    23	            return parsed.replace(tzinfo=timezone.utc)
    24	        return parsed.astimezone(timezone.utc)
    25	    return parsed
    26	
    27	def _now_iso() -> str:
    28	    """Returns the current UTC time as an ISO format string."""
    29	    return datetime.now(timezone.utc).isoformat()
    30	
    31	def _now() -> str:
    32	    """Alias for _now_iso(). Returns current UTC time as an ISO format string."""
    33	    return _now_iso()
    34	
    35	def _now_utc() -> datetime:
    36	    """Returns the current UTC time as a timezone-aware datetime object."""
    37	    return datetime.now(timezone.utc)
     1	import os
     2	from pathlib import Path
     3	import re
     4	
     5	def fix_file(path):
     6	    with open(path, 'r') as f:
     7	        content = f.read()
     8	    
     9	    # Check if we need to modify
    10	    if 'datetime' not in content and 'subprocess' not in content:
    11	        return
    12	        
    13	    lines = content.split('\n')
    14	    new_lines = []
    15	    modified = False
    16	    
    17	    for line in lines:
    18	        stripped = line.lstrip()
    19	        indent = line[:len(line) - len(stripped)]
    20	        if stripped.startswith('import datetime'):
    21	            new_lines.append(indent + 'from rebalance.lib.time_ops import datetime, timedelta, timezone, date, time')
    22	            modified = True
    23	        elif stripped.startswith('from datetime import'):
    24	            new_lines.append(indent + stripped.replace('from datetime', 'from rebalance.lib.time_ops'))
    25	            modified = True
    26	        elif stripped.startswith('import subprocess'):
    27	            new_lines.append(indent + 'import rebalance.lib.subprocess_ops as subprocess')
    28	            modified = True
    29	        elif stripped.startswith('from subprocess import'):
    30	            new_lines.append(indent + stripped.replace('from subprocess', 'from rebalance.lib.subprocess_ops'))
    31	            modified = True
    32	        else:
    33	            new_lines.append(line)
    34	            
    35	    if modified:
    36	        with open(path, 'w') as f:
    37	            f.write('\n'.join(new_lines))
    38	
    39	for root, _, files in os.walk('src/rebalance'):
    40	    if 'lib' in Path(root).parts:
    41	        continue
    42	    for f in files:
    43	        if f.endswith('.py'):
    44	            fix_file(os.path.join(root, f))
     1	---
     2	title: "Architectural Audit: Complexity, DRY, and System Stability"
     3	status: "Active"
     4	created: "2026-08-11"
     5	updated: "2026-08-11"
     6	owner: "agent"
     7	goal: "Consolidate duplicate ingest logic and implement bulletproof governance rules to prevent system over-engineering."
     8	gh_issue: 266
     9	effort: 2
    10	complexity: 2
    11	risk: 2
    12	phases: 3
    13	---
    14	
    15	## Status
    16	
    17	| What was just completed | What's next |
    18	|---|---|
    19	| Completed all 3 phases and addressed PR feedback from Codex | Done |
    20	
    21	## Quad Concepts
    22	- Repeated duplicate ingest logic → Extract into domain-specific shared libraries (`src/rebalance/lib/time_ops.py`, etc.)
    23	- Agents creating god-modules when told to use `utils.py` → Ban `utils.py` and enforce strict domain boundaries.
    24	- Agents hallucinating duplicate checks via `grep_search` → Ban raw `datetime`/`subprocess` imports outside `lib/` and enforce via CI `import-linter`.
    25	- Telling agents "Extend, don't invent" creates bloated god-objects → Change mandate to "Compose, don't mutate" to encourage primitives.
    26	
    27	## Table of contents
    28	- Phase 1 — Quick Wins (DRY Consolidation)
    29	- Phase 2 — Governance System Rules
    30	- Phase 3 — Technical Debt Eradication & Primitives Application
    31	
    32	## Phase 1 — Quick Wins (DRY Consolidation)
    33	
    34	Extract duplicated ingest utility functions into domain-specific shared libraries. 
    35	
    36	- [x] Extract time-related utilities (`_parse_iso`, `_now_iso`, `_now`) into `src/rebalance/lib/time_ops.py`.
    37	- [x] Extract JSON-related utilities (`_json_dumps`) into `src/rebalance/lib/json_ops.py`.
    38	- [x] Extract Git-related utilities (`_git`) into `src/rebalance/lib/git_ops.py`. *(Note: `github_commit_backfill.py` intentionally kept its own `_git` as it has a different return type tuple contract)*
    39	- [~] Extract dictionary utilities (`as_dict`) into `src/rebalance/lib/dict_ops.py`. *(Deliberately skipped: `as_dict` is implemented per-dataclass and not genuinely shared)*
    40	- [x] Refactor all existing collectors to import from these new domain-specific `lib/` modules.
    41	- [x] **QA Gate**: Run `pytest tests/` to ensure no regressions in behavior.
    42	- [x] **QA Gate**: Run `utils/pdda/pdda.sh run` to verify structural compliance.
    43	
    44	## Phase 2 — Governance System Rules
    45	
    46	To prevent Agents (and human developers) from building overlapping systems in the future, enforce mechanical chokepoints across the governance documentation:
    47	
    48	- [x] Update `AGENTS.md` (Agent Behavior) to enforce importing `datetime`, `json`, and `subprocess` exclusively from `rebalance.lib.*`. 
    49	- [x] Update `PROJECT/PDDA.md` (Design Decision & Automation) to require `pylint --enable=duplicate-code` in the CI pipeline and introduce mechanical import bans for `subprocess` and `datetime` outside of `src/rebalance/lib/`.
    50	- [x] Update `ARCHITECTURE.md` (System Constraints) to include the "Compose, Don't Mutate" rule, forcing features to break core functions into primitives rather than adding conditional flags.
    51	- [x] Update `ROUTER.md` (Entry Point Rules) to introduce a strict rule: any new system overlapping >50% with an old system MUST include the deletion of the old system in the same PR.
    52	- [x] Implement `import-linter` or a CI script to physically fail the build on restricted imports.
    53	- [x] **QA Gate**: Run `utils/pdda/pdda.sh run` and verify it passes with 0 errors on governance checks.
    54	
    55	## Phase 3 — Technical Debt Eradication & Primitives Application
    56	
    57	Apply the newly established governance rules retroactively to prune redundant systems and fix architectural stability issues.
    58	
    59	- [x] **Audit Overlapping Systems:** Identify existing read-paths and query layers that violate the >50% overlap rule (e.g., investigating `semantic_query` vs `ask` vs `query_notes`).
    60	- [x] **Execute Deletions:** Deprecate and delete the legacy, redundant systems identified in the audit to force all traffic through a single, well-maintained pipeline.
    61	- [x] **Refactor God Objects (Fixing #222):** Apply the "Compose, Don't Mutate" rule to the `Database is locked` (#222) issue. Refactor the monolithic, unbounded TF-IDF rebuild transactions into smaller, composable, batched transaction primitives. 
    62	- [x] **QA Gate:** Run the test suite (`pytest tests/`) to ensure no downstream dependencies break from the deleted query layers.
    63	- [x] **QA Gate:** Complete final `utils/pdda/pdda.sh run` validation.

exec
/bin/zsh -lc "nl -ba src/rebalance/lib/time_ops.py | sed -n '1,260p'; nl -ba fix_imports.py | sed -n '1,180p'; nl -ba PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md | sed -n '1,300p'; nl -ba src/rebalance/doctor.py | sed -n '1,70p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
 succeeded in 0ms:
     1	from datetime import datetime, timezone, timedelta, date, time
     2	
     3	from typing import Any
     4	
     5	def _parse_iso(raw: Any, force_utc: bool = True) -> datetime | None:
     6	    if not raw or not isinstance(raw, str):
     7	        return None
     8	    text = raw.strip().replace("Z", "+00:00")
     9	    
    10	    parsed = None
    11	    for candidate in (text, text.replace(" ", "T")):
    12	        try:
    13	            parsed = datetime.fromisoformat(candidate)
    14	            break
    15	        except ValueError:
    16	            continue
    17	            
    18	    if not parsed:
    19	        return None
    20	        
    21	    if force_utc:
    22	        if parsed.tzinfo is None:
    23	            return parsed.replace(tzinfo=timezone.utc)
    24	        return parsed.astimezone(timezone.utc)
    25	    return parsed
    26	
    27	def _now_iso() -> str:
    28	    """Returns the current UTC time as an ISO format string."""
    29	    return datetime.now(timezone.utc).isoformat()
    30	
    31	def _now() -> str:
    32	    """Alias for _now_iso(). Returns current UTC time as an ISO format string."""
    33	    return _now_iso()
    34	
    35	def _now_utc() -> datetime:
    36	    """Returns the current UTC time as a timezone-aware datetime object."""
    37	    return datetime.now(timezone.utc)
     1	import os
     2	from pathlib import Path
     3	import re
     4	
     5	def fix_file(path):
     6	    with open(path, 'r') as f:
     7	        content = f.read()
     8	    
     9	    # Check if we need to modify
    10	    if 'datetime' not in content and 'subprocess' not in content:
    11	        return
    12	        
    13	    lines = content.split('\n')
    14	    new_lines = []
    15	    modified = False
    16	    
    17	    for line in lines:
    18	        stripped = line.lstrip()
    19	        indent = line[:len(line) - len(stripped)]
    20	        if stripped.startswith('import datetime'):
    21	            new_lines.append(indent + 'from rebalance.lib.time_ops import datetime, timedelta, timezone, date, time')
    22	            modified = True
    23	        elif stripped.startswith('from datetime import'):
    24	            new_lines.append(indent + stripped.replace('from datetime', 'from rebalance.lib.time_ops'))
    25	            modified = True
    26	        elif stripped.startswith('import subprocess'):
    27	            new_lines.append(indent + 'import rebalance.lib.subprocess_ops as subprocess')
    28	            modified = True
    29	        elif stripped.startswith('from subprocess import'):
    30	            new_lines.append(indent + stripped.replace('from subprocess', 'from rebalance.lib.subprocess_ops'))
    31	            modified = True
    32	        else:
    33	            new_lines.append(line)
    34	            
    35	    if modified:
    36	        with open(path, 'w') as f:
    37	            f.write('\n'.join(new_lines))
    38	
    39	for root, _, files in os.walk('src/rebalance'):
    40	    if 'lib' in Path(root).parts:
    41	        continue
    42	    for f in files:
    43	        if f.endswith('.py'):
    44	            fix_file(os.path.join(root, f))
     1	---
     2	title: "Architectural Audit: Complexity, DRY, and System Stability"
     3	status: "Active"
     4	created: "2026-08-11"
     5	updated: "2026-08-11"
     6	owner: "agent"
     7	goal: "Consolidate duplicate ingest logic and implement bulletproof governance rules to prevent system over-engineering."
     8	gh_issue: 266
     9	effort: 2
    10	complexity: 2
    11	risk: 2
    12	phases: 3
    13	---
    14	
    15	## Status
    16	
    17	| What was just completed | What's next |
    18	|---|---|
    19	| Completed all 3 phases and addressed PR feedback from Codex | Done |
    20	
    21	## Quad Concepts
    22	- Repeated duplicate ingest logic → Extract into domain-specific shared libraries (`src/rebalance/lib/time_ops.py`, etc.)
    23	- Agents creating god-modules when told to use `utils.py` → Ban `utils.py` and enforce strict domain boundaries.
    24	- Agents hallucinating duplicate checks via `grep_search` → Ban raw `datetime`/`subprocess` imports outside `lib/` and enforce via CI `import-linter`.
    25	- Telling agents "Extend, don't invent" creates bloated god-objects → Change mandate to "Compose, don't mutate" to encourage primitives.
    26	
    27	## Table of contents
    28	- Phase 1 — Quick Wins (DRY Consolidation)
    29	- Phase 2 — Governance System Rules
    30	- Phase 3 — Technical Debt Eradication & Primitives Application
    31	
    32	## Phase 1 — Quick Wins (DRY Consolidation)
    33	
    34	Extract duplicated ingest utility functions into domain-specific shared libraries. 
    35	
    36	- [x] Extract time-related utilities (`_parse_iso`, `_now_iso`, `_now`) into `src/rebalance/lib/time_ops.py`.
    37	- [x] Extract JSON-related utilities (`_json_dumps`) into `src/rebalance/lib/json_ops.py`.
    38	- [x] Extract Git-related utilities (`_git`) into `src/rebalance/lib/git_ops.py`. *(Note: `github_commit_backfill.py` intentionally kept its own `_git` as it has a different return type tuple contract)*
    39	- [~] Extract dictionary utilities (`as_dict`) into `src/rebalance/lib/dict_ops.py`. *(Deliberately skipped: `as_dict` is implemented per-dataclass and not genuinely shared)*
    40	- [x] Refactor all existing collectors to import from these new domain-specific `lib/` modules.
    41	- [x] **QA Gate**: Run `pytest tests/` to ensure no regressions in behavior.
    42	- [x] **QA Gate**: Run `utils/pdda/pdda.sh run` to verify structural compliance.
    43	
    44	## Phase 2 — Governance System Rules
    45	
    46	To prevent Agents (and human developers) from building overlapping systems in the future, enforce mechanical chokepoints across the governance documentation:
    47	
    48	- [x] Update `AGENTS.md` (Agent Behavior) to enforce importing `datetime`, `json`, and `subprocess` exclusively from `rebalance.lib.*`. 
    49	- [x] Update `PROJECT/PDDA.md` (Design Decision & Automation) to require `pylint --enable=duplicate-code` in the CI pipeline and introduce mechanical import bans for `subprocess` and `datetime` outside of `src/rebalance/lib/`.
    50	- [x] Update `ARCHITECTURE.md` (System Constraints) to include the "Compose, Don't Mutate" rule, forcing features to break core functions into primitives rather than adding conditional flags.
    51	- [x] Update `ROUTER.md` (Entry Point Rules) to introduce a strict rule: any new system overlapping >50% with an old system MUST include the deletion of the old system in the same PR.
    52	- [x] Implement `import-linter` or a CI script to physically fail the build on restricted imports.
    53	- [x] **QA Gate**: Run `utils/pdda/pdda.sh run` and verify it passes with 0 errors on governance checks.
    54	
    55	## Phase 3 — Technical Debt Eradication & Primitives Application
    56	
    57	Apply the newly established governance rules retroactively to prune redundant systems and fix architectural stability issues.
    58	
    59	- [x] **Audit Overlapping Systems:** Identify existing read-paths and query layers that violate the >50% overlap rule (e.g., investigating `semantic_query` vs `ask` vs `query_notes`).
    60	- [x] **Execute Deletions:** Deprecate and delete the legacy, redundant systems identified in the audit to force all traffic through a single, well-maintained pipeline.
    61	- [x] **Refactor God Objects (Fixing #222):** Apply the "Compose, Don't Mutate" rule to the `Database is locked` (#222) issue. Refactor the monolithic, unbounded TF-IDF rebuild transactions into smaller, composable, batched transaction primitives. 
    62	- [x] **QA Gate:** Run the test suite (`pytest tests/`) to ensure no downstream dependencies break from the deleted query layers.
    63	- [x] **QA Gate:** Complete final `utils/pdda/pdda.sh run` validation.
     1	"""Health check for a rebalance install — backs ``rebalance doctor``.
     2	
     3	Inspects the live configuration and environment for the class of problem a
     4	unit test cannot catch: which database is actually in use, whether the GitHub
     5	token is reachable by background (launchd) jobs, schema version, registered
     6	projects, GitHub data freshness, the credentials for each external integration
     7	(Sleuth/Slack, Gmail, Google Calendar), and scheduled-job exit status.
     8	
     9	``run_doctor()`` returns a structured :class:`DoctorReport`; the CLI renders it.
    10	"""
    11	
    12	from __future__ import annotations
    13	
    14	import json
    15	import os
    16	import re
    17	import rebalance.lib.subprocess_ops as subprocess
    18	from dataclasses import dataclass, field
    19	from rebalance.lib.time_ops import datetime, timezone
    20	from pathlib import Path
    21	from typing import Callable, Literal
    22	
    23	from rebalance.tz_utils import format_timestamp, local_tz
    24	
    25	OK = "ok"
    26	WARN = "warn"
    27	FAIL = "fail"
    28	
    29	NOTICE = "notice"
    30	WARNING = "warning"
    31	ERROR = "error"
    32	Severity = Literal["notice", "warning", "error"]
    33	
    34	
    35	@dataclass
    36	class Check:
    37	    """One health check result."""
    38	
    39	    name: str
    40	    status: str  # OK | WARN | FAIL
    41	    detail: str
    42	    hint: str = ""
    43	    severity: Severity = WARNING
    44	
    45	    def __post_init__(self) -> None:
    46	        """Keep legacy FAIL emitters in the error bucket and reject typos."""
    47	        if self.severity not in {NOTICE, WARNING, ERROR}:
    48	            raise ValueError(f"invalid check severity: {self.severity}")
    49	        if self.status == FAIL and self.severity == WARNING:
    50	            self.severity = ERROR
    51	
    52	
    53	@dataclass
    54	class DoctorReport:
    55	    checks: list[Check] = field(default_factory=list)
    56	
    57	    @property
    58	    def failed(self) -> bool:
    59	        return any(c.status == FAIL for c in self.checks)
    60	
    61	    @property
    62	    def warned(self) -> bool:
    63	        return any(c.status == WARN for c in self.checks)
    64	
    65	
    66	@dataclass(frozen=True)
    67	class _DeviceScope:
    68	    """Ownership and freshness policy for a device-bound health check."""
    69	
    70	    device_ids: frozenset[str]

2026-08-14T19:04:47.942952Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
exec
/bin/zsh -lc "rg -n --glob '*.py' '"'^(import|from) (datetime|subprocess)|''^import rebalance'"\\.lib\\.subprocess_ops as subprocess|"'^from rebalance'"\\.lib\\.time_ops import .*\\b(datetime|timezone|timedelta|date|time)\\b' src/rebalance | sed -n '1,260p'; rg -n --glob '*.py' 'subprocess\\.[A-Za-z_]+|\\b(datetime|timezone|timedelta|date|time)\\.' src/rebalance | sed -n '1,260p'; rg -n 'datetime|subprocess|parse_iso|now_iso|_git|json_dumps|import-linter|banned import' AGENTS.md PROJECT/PDDA.md ARCHITECTURE.md ROUTER.md pyproject.toml requirements*.txt setup.cfg tox.ini 2>/dev/null | sed -n '1,400p'; find src/rebalance -type f -name '*.py' | wc -l" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
 succeeded in 0ms:
src/rebalance/lib/git_ops.py:1:import subprocess
src/rebalance/health.py:27:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/doctor.py:17:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/doctor.py:19:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/note_builder.py:9:from rebalance.lib.time_ops import date, datetime, timedelta, timezone
src/rebalance/tz_utils.py:13:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/web.py:27:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/lib/subprocess_ops.py:1:from subprocess import run, Popen, PIPE, TimeoutExpired, CalledProcessError, check_output, check_call, DEVNULL, SubprocessError
src/rebalance/ingest/github_coverage.py:30:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/github_coverage.py:32:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/github_reconciliation.py:14:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/chat.py:16:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/note_ingester.py:17:from rebalance.lib.time_ops import date, datetime as _dt
src/rebalance/ingest/note_ingester.py:20:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/lib/time_ops.py:1:from datetime import datetime, timezone, timedelta, date, time
src/rebalance/ingest/weekly_report.py:10:from rebalance.lib.time_ops import date, timedelta
src/rebalance/ingest/pulse.py:23:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/pulse.py:29:from rebalance.lib.time_ops import datetime, timedelta, timezone
src/rebalance/ingest/audit.py:7:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/auth_log.py:59:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/sleuth_reminders.py:33:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/pulse_health.py:28:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/preflight.py:5:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/github_direct_commits.py:8:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/next_actions.py:45:from rebalance.lib.time_ops import date, datetime, timedelta, timezone
src/rebalance/ingest/calendar_snap.py:29:from rebalance.lib.time_ops import date, datetime, timedelta
src/rebalance/ingest/apple_reminders.py:50:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/daily_report.py:12:from rebalance.lib.time_ops import date, timedelta
src/rebalance/ingest/token_meta.py:20:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/profile_sync.py:20:from rebalance.lib.time_ops import datetime, timedelta, timezone, date, time
src/rebalance/ingest/code_collector.py:17:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/claude_cloud.py:24:from rebalance.lib.time_ops import datetime, timedelta, timezone, date, time
src/rebalance/ingest/claude_cloud.py:28:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/config.py:19:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/sync_snapshot.py:39:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/sync_snapshot.py:40:from rebalance.lib.time_ops import datetime, timedelta, timezone
src/rebalance/ingest/github_watch.py:34:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/apple_reminders_write.py:41:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/apple_reminders_write.py:45:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/index_ops.py:16:from rebalance.lib.time_ops import date, datetime, timedelta, timezone
src/rebalance/ingest/goals_file.py:6:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/ask_self_scan.py:34:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/github_scan.py:20:from rebalance.lib.time_ops import datetime, timezone, timedelta
src/rebalance/ingest/gmail.py:28:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/querier.py:18:from rebalance.lib.time_ops import datetime, timezone, timedelta
src/rebalance/ingest/github_commit_backfill.py:25:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/github_commit_backfill.py:28:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/focus5_scan.py:36:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/focus5_scan.py:38:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/github_readiness.py:14:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/calendar_helpers.py:24:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/cli/calendar.py:14:from rebalance.lib.time_ops import date as date_cls, datetime, time as time_cls, timedelta
src/rebalance/ingest/figma.py:18:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/calendar.py:20:from rebalance.lib.time_ops import datetime, timezone, timedelta
src/rebalance/ingest/diagnose.py:15:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/local_repos.py:25:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/project_inference.py:7:from rebalance.lib.time_ops import datetime, timedelta, timezone
src/rebalance/ingest/github_knowledge.py:17:from rebalance.lib.time_ops import datetime, timedelta, timezone
src/rebalance/ingest/embedder.py:19:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/ingest/semantic_index.py:10:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/cli/__init__.py:3:from rebalance.lib.time_ops import date as date_cls, datetime, time as time_cls, timedelta
src/rebalance/cli/reset.py:11:import rebalance.lib.subprocess_ops as subprocess
src/rebalance/ingest/db/migrate.py:18:from rebalance.lib.time_ops import datetime, timezone
src/rebalance/doctor.py:485:                datetime.now(timezone.utc).date()
src/rebalance/doctor.py:486:                - datetime.fromisoformat(str(latest)).date()
src/rebalance/doctor.py:506:        out = subprocess.run(
src/rebalance/doctor.py:509:    except (FileNotFoundError, subprocess.SubprocessError):
src/rebalance/doctor.py:665:        modified_at = datetime.fromtimestamp(log_path.stat().st_mtime, timezone.utc)
src/rebalance/doctor.py:796:    now = now or datetime.now(timezone.utc)
src/rebalance/doctor.py:945:            age_h = (datetime.now(timezone.utc) - beat).total_seconds() / 3600
src/rebalance/doctor.py:1397:            datetime.now(local_tz()).date(),
src/rebalance/cli/refresh.py:31:    started = time.monotonic()
src/rebalance/cli/refresh.py:38:            "elapsed_seconds": round(time.monotonic() - started, 2),
src/rebalance/cli/refresh.py:44:        "elapsed_seconds": round(time.monotonic() - started, 2),
src/rebalance/cli/refresh.py:88:    started = time.monotonic()
src/rebalance/cli/refresh.py:147:    summary["total_elapsed_seconds"] = round(time.monotonic() - started, 2)
src/rebalance/web.py:124:    current = time.monotonic() if now is None else now
src/rebalance/web.py:523:    now_ts = int(datetime.now(timezone.utc).timestamp())
src/rebalance/web.py:562:        datetime.fromtimestamp(banner["my_local_commit_ts"], tz=timezone.utc).isoformat()
src/rebalance/web.py:767:        ts = datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
src/rebalance/web.py:770:    return (datetime.now(timezone.utc) - ts).total_seconds() > FOCUS5_ROSTER_TTL_SECONDS
src/rebalance/web.py:887:    now_iso = datetime.now(timezone.utc).isoformat()
src/rebalance/web.py:920:    now = time.monotonic()
src/rebalance/web.py:1272:        proc = subprocess.run(  # noqa: S603 — argv list, allowlisted path, no shell
src/rebalance/web.py:1274:            stdin=subprocess.DEVNULL,
src/rebalance/web.py:1343:    started_at = time.monotonic()
src/rebalance/web.py:1451:            duration_ms=int((time.monotonic() - started_at) * 1000),
src/rebalance/cli/calendar.py:104:        start_dt = datetime.combine(target_date, time_cls.min, tzinfo=tz)
src/rebalance/cli/calendar.py:105:        end_dt = datetime.combine(target_date + timedelta(days=1), time_cls.min, tzinfo=tz)
src/rebalance/cli/calendar.py:114:        start_dt = datetime.fromisoformat(start_time)
src/rebalance/cli/calendar.py:115:        end_dt = datetime.fromisoformat(end_time)
src/rebalance/cli/calendar.py:177:    """Search for an existing event with the same title and same start date."""
src/rebalance/cli/calendar.py:320:        "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
src/rebalance/cli/calendar.py:406:    today = date.today()
src/rebalance/cli/calendar.py:479:        start_date = datetime.now(ZoneInfo(resolved_timezone)).date()
src/rebalance/cli/calendar.py:544:        target_date = date.fromisoformat(date_str)
src/rebalance/cli/calendar.py:546:        target_date = date.today()
src/rebalance/cli/calendar.py:581:        target_date = date.fromisoformat(date_str)
src/rebalance/cli/calendar.py:583:        target_date = date.today()
src/rebalance/lib/time_ops.py:13:            parsed = datetime.fromisoformat(candidate)
src/rebalance/lib/time_ops.py:23:            return parsed.replace(tzinfo=timezone.utc)
src/rebalance/lib/time_ops.py:24:        return parsed.astimezone(timezone.utc)
src/rebalance/lib/time_ops.py:29:    return datetime.now(timezone.utc).isoformat()
src/rebalance/lib/time_ops.py:37:    return datetime.now(timezone.utc)
src/rebalance/tz_utils.py:50:        dt = dt.replace(tzinfo=timezone.utc)
src/rebalance/tz_utils.py:95:        parsed = parsed.replace(tzinfo=timezone.utc)
src/rebalance/tz_utils.py:96:    reference = now or datetime.now(timezone.utc)
src/rebalance/lib/git_ops.py:7:        result = subprocess.run(
src/rebalance/lib/git_ops.py:14:    except subprocess.TimeoutExpired:
src/rebalance/cli/dashboard.py:47:        target_date = date.fromisoformat(date_str)
src/rebalance/cli/dashboard.py:49:        target_date = date.today()
src/rebalance/chat.py:82:        proc = subprocess.run(
src/rebalance/chat.py:90:    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
src/rebalance/chat.py:151:    start = time.monotonic()
src/rebalance/chat.py:192:        "elapsed_ms": int((time.monotonic() - start) * 1000),
src/rebalance/cli/onboard.py:303:        proc = subprocess.run(cmd, cwd=repo_root)
src/rebalance/ingest/next_actions.py:662:    local so the ranker never hard-depends on the registry module at import time.
src/rebalance/ingest/next_actions.py:891:    current = now.astimezone(tz) if now is not None else datetime.now(tz)
src/rebalance/ingest/next_actions.py:909:    current = (now.astimezone(tz) if now is not None else datetime.now(tz))
src/rebalance/ingest/next_actions.py:1004:        return datetime.fromisoformat(raw).astimezone(tz).date()
src/rebalance/ingest/next_actions.py:1006:        return date.fromisoformat(raw)
src/rebalance/ingest/next_actions.py:1224:    started = time.monotonic()
src/rebalance/ingest/next_actions.py:1269:            elapsed_seconds=round(time.monotonic() - started, 2),
src/rebalance/ingest/next_actions.py:1270:            computed_at=datetime.now(timezone.utc).isoformat(),
src/rebalance/ingest/next_actions.py:1370:        elapsed_seconds=round(time.monotonic() - started, 2),
src/rebalance/ingest/next_actions.py:1371:        computed_at=datetime.now(timezone.utc).isoformat(),
src/rebalance/ingest/next_actions.py:1393:        (datetime.fromisoformat(local_day).date() + timedelta(days=i)).isoformat()
src/rebalance/ingest/next_actions.py:1440:    now_iso = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/next_actions.py:1442:        datetime.now(timezone.utc) - timedelta(days=_ADDITIVITY_HISTORY_DAYS)
src/rebalance/ingest/next_actions.py:1531:                result.computed_at or datetime.now(timezone.utc).isoformat(),
src/rebalance/ingest/note_builder.py:49:    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")
src/rebalance/ingest/note_builder.py:306:        generated_at=datetime.now(timezone.utc).isoformat(),
src/rebalance/cli/reset.py:107:        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
src/rebalance/ingest/code_collector.py:95:            mtime_iso = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
src/rebalance/ingest/note_ingester.py:133:    start = time.monotonic()
src/rebalance/ingest/note_ingester.py:176:                disk_mtime_iso = datetime.fromtimestamp(
src/rebalance/ingest/note_ingester.py:177:                    file_path.stat().st_mtime, tz=timezone.utc
src/rebalance/ingest/note_ingester.py:204:            now_iso = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/note_ingester.py:205:            mtime_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
src/rebalance/ingest/note_ingester.py:284:    elapsed = time.monotonic() - start
src/rebalance/cli/raw.py:88:    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
src/rebalance/cli/raw.py:98:                last_active_map[repo] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
src/rebalance/cli/raw.py:108:                event_time = datetime.fromisoformat((event.get("created_at") or "").replace("Z", "+00:00"))
src/rebalance/cli/raw.py:176:    cutoff = datetime.now(timezone.utc) - timedelta(days=fresh_threshold_days)
src/rebalance/cli/raw.py:184:            pushed = datetime.fromisoformat(rec.pushed_at.replace("Z", "+00:00"))
src/rebalance/cli/raw.py:206:    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
src/rebalance/cli/raw.py:214:            t = datetime.fromisoformat((e.get("created_at") or "").replace("Z", "+00:00"))
src/rebalance/cli/raw.py:228:            last_active_map[repo] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
src/rebalance/cli/raw.py:261:        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
src/rebalance/cli/raw.py:308:        local_time = datetime.fromisoformat(ev["time"]).astimezone().strftime("%H:%M:%S")
src/rebalance/cli/raw.py:341:                local_time = datetime.fromisoformat(ev["time"]).astimezone().strftime("%H:%M:%S")
src/rebalance/cli/raw.py:364:        now_utc = datetime.now(timezone.utc)
src/rebalance/cli/raw.py:366:            pushed = datetime.fromisoformat(r["pushed_at"])
src/rebalance/cli/raw.py:456:            time.sleep(watch)
src/rebalance/ingest/preflight.py:110:        now = datetime.now(timezone.utc)
src/rebalance/ingest/preflight.py:112:            activity_dt = activity_dt.replace(tzinfo=timezone.utc)
src/rebalance/ingest/pulse.py:82:    proc = subprocess.run(
src/rebalance/ingest/pulse.py:91:        subprocess.run(
src/rebalance/ingest/pulse.py:122:    now = now or datetime.now(tz)
src/rebalance/ingest/pulse.py:154:    return dt.astimezone(timezone.utc).isoformat()
src/rebalance/ingest/pulse.py:577:            created = created.replace(tzinfo=timezone.utc)
src/rebalance/ingest/pulse.py:676:    now = now or datetime.now(tz)
src/rebalance/ingest/pulse.py:922:                created = created.replace(tzinfo=timezone.utc)
src/rebalance/ingest/pulse.py:1028:    proc = subprocess.run(
src/rebalance/ingest/pulse.py:1190:    started = time.monotonic()
src/rebalance/ingest/pulse.py:1253:        "elapsed_seconds": round(time.monotonic() - started, 2),
src/rebalance/ingest/focus5_scan.py:170:    not a reason to fall through to a foreign author's commit time.
src/rebalance/ingest/focus5_scan.py:706:    now = datetime.now(timezone.utc)
src/rebalance/ingest/focus5_scan.py:797:    now = datetime.now(timezone.utc)
src/rebalance/ingest/focus5_scan.py:874:    probed_at = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/focus5_scan.py:1045:                now_ts = int(datetime.now(timezone.utc).timestamp())
src/rebalance/ingest/apple_reminders.py:163:    aware UTC datetime. Returns None for NULL / non-numeric values."""
src/rebalance/ingest/apple_reminders.py:170:    return datetime.fromtimestamp(seconds + CORE_DATA_EPOCH_OFFSET, tz=timezone.utc)
src/rebalance/ingest/apple_reminders.py:528:    started = time.monotonic()
src/rebalance/ingest/apple_reminders.py:538:    duration = time.monotonic() - started
src/rebalance/ingest/apple_reminders.py:722:    now = now_iso or datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/apple_reminders.py:883:    started = time.monotonic()
src/rebalance/ingest/apple_reminders.py:890:    now_iso = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/apple_reminders.py:914:        duration_seconds=time.monotonic() - started,
src/rebalance/ingest/sync_snapshot.py:100:    generated_at = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/sync_snapshot.py:101:    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
src/rebalance/ingest/sync_snapshot.py:165:    generated_at = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/sync_snapshot.py:239:    proc = subprocess.run(
src/rebalance/ingest/sleuth_reminders.py:196:        return subprocess.run(
src/rebalance/ingest/sleuth_reminders.py:210:    except subprocess.CalledProcessError as exc:
src/rebalance/ingest/sleuth_reminders.py:554:    now_iso = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/github_coverage.py:113:    return (datetime.now(timezone.utc).timestamp() - mtime) / 3600.0
src/rebalance/ingest/github_coverage.py:124:        result = subprocess.run(
src/rebalance/ingest/github_coverage.py:128:    except (subprocess.TimeoutExpired, OSError):
src/rebalance/mcp/tools/hygiene.py:80:            proc = subprocess.run(
src/rebalance/mcp/tools/hygiene.py:87:        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
src/rebalance/ingest/apple_reminders_write.py:98:    """The signed helper failed to launch, verify, or respond in time."""
src/rebalance/ingest/apple_reminders_write.py:531:    verify = subprocess.run(
src/rebalance/ingest/apple_reminders_write.py:539:    info = subprocess.run(
src/rebalance/ingest/apple_reminders_write.py:589:    launch = subprocess.run(
src/rebalance/ingest/apple_reminders_write.py:598:    deadline = time.monotonic() + timeout_seconds
src/rebalance/ingest/apple_reminders_write.py:599:    while time.monotonic() < deadline:
src/rebalance/ingest/apple_reminders_write.py:606:        time.sleep(poll_seconds)
src/rebalance/ingest/goals_file.py:108:            "completed_at": datetime.now(timezone.utc).isoformat(),
src/rebalance/ingest/auth_log.py:116:        "ts": datetime.now(timezone.utc).isoformat(),
src/rebalance/mcp/tools/calendar.py:165:            timezone_name: IANA timezone. Defaults to config timezone.
src/rebalance/mcp/tools/calendar.py:183:            start_date = datetime.now(ZoneInfo(resolved_timezone)).date()
src/rebalance/ingest/calendar.py:198:    start = time.monotonic()
src/rebalance/ingest/calendar.py:201:    now = datetime.now(timezone.utc)
src/rebalance/ingest/calendar.py:286:        elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/calendar.py:448:    now = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/calendar.py:449:    cutoff = (datetime.now(timezone.utc) + timedelta(days=days_forward)).isoformat()
src/rebalance/ingest/calendar.py:485:    now = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/calendar.py:486:    cutoff = (datetime.now(timezone.utc) + timedelta(days=days_forward)).isoformat()
src/rebalance/ingest/calendar.py:516:    now = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/calendar.py:517:    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
src/rebalance/ingest/calendar.py:585:    now = datetime.now(timezone.utc)
src/rebalance/ingest/calendar.py:621:        day_obj = datetime.fromisoformat(date_str).date()  # raw-ok: date-only string, no Z
src/rebalance/ingest/figma.py:237:    start = time.monotonic()
src/rebalance/ingest/figma.py:281:        elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/project_inference.py:239:    today = datetime.now(timezone.utc).date()
src/rebalance/ingest/project_inference.py:316:    return dt.astimezone(timezone.utc)
src/rebalance/ingest/project_inference.py:450:        latest_dt = parse_calendar_dt(latest).astimezone(timezone.utc)
src/rebalance/ingest/project_inference.py:453:    age_days = (datetime.now(timezone.utc) - latest_dt).days
src/rebalance/ingest/project_inference.py:890:                "promoted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
src/rebalance/mcp/tools/index.py:185:        dry_run=False, push=True between 6 AM and 11 PM local time.
src/rebalance/ingest/calendar_snap.py:15:  overlap — i.e. it silently discards real time. Keep it at 0 for accurate
src/rebalance/ingest/calendar_snap.py:221:    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=tz)
src/rebalance/ingest/calendar_snap.py:222:    day_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time(), tzinfo=tz)
src/rebalance/ingest/calendar_snap.py:304:    start = time.monotonic()
src/rebalance/ingest/calendar_snap.py:322:            "time. Set snap_gap_minutes to 0 for accurate time calculations."
src/rebalance/ingest/calendar_snap.py:331:        elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/semantic_index.py:521:    start = time.monotonic()
src/rebalance/ingest/semantic_index.py:606:        elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/semantic_index.py:654:    start = time.monotonic()
src/rebalance/ingest/semantic_index.py:684:                elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/semantic_index.py:692:            now_iso = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/semantic_index.py:702:        now_iso = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/semantic_index.py:718:        elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/semantic_index.py:759:                       updated before this date/time.
src/rebalance/ingest/querier.py:59:    return datetime.now().astimezone()
src/rebalance/ingest/querier.py:69:    Checks calendar_events for vacation-like events on the target date.
src/rebalance/ingest/querier.py:86:            # Check for all-day or spanning events on the target date.
src/rebalance/ingest/querier.py:150:    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
src/rebalance/ingest/querier.py:541:    start = time.monotonic()
src/rebalance/ingest/querier.py:587:    elapsed = time.monotonic() - start
src/rebalance/ingest/sleuth_grouping.py:332:    """Return all active reminders from the DB as plain dicts, ordered by due date."""
src/rebalance/ingest/audit.py:28:        "timestamp": datetime.now(timezone.utc).isoformat(),
src/rebalance/ingest/calendar_helpers.py:7:  - Raw `datetime.fromisoformat(x.replace('Z', ...))` → use parse_calendar_dt()
src/rebalance/ingest/calendar_helpers.py:30:    """Parse a Google Calendar datetime string into a Python datetime.
src/rebalance/ingest/calendar_helpers.py:61:    return parsed.astimezone(timezone.utc)
src/rebalance/ingest/calendar_helpers.py:67:        dt = dt.replace(tzinfo=timezone.utc)
src/rebalance/ingest/calendar_helpers.py:68:    return dt.astimezone(timezone.utc)
src/rebalance/ingest/calendar_helpers.py:79:    """Filter and sort calendar rows by absolute event start time.
src/rebalance/ingest/claude_cloud.py:53:        raw = subprocess.check_output(
src/rebalance/ingest/claude_cloud.py:55:            stderr=subprocess.DEVNULL, text=True, timeout=10).strip()
src/rebalance/ingest/claude_cloud.py:95:        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
src/rebalance/ingest/claude_cloud.py:98:            return dt.datetime.fromisoformat(ts.split(".")[0] + "+00:00")
src/rebalance/ingest/claude_cloud.py:173:        out = subprocess.check_output(
src/rebalance/ingest/claude_cloud.py:176:            stderr=subprocess.DEVNULL, text=True, timeout=20).strip()
src/rebalance/ingest/claude_cloud.py:190:    day = day or dt.date.today()
src/rebalance/ingest/claude_cloud.py:303:                                dt.date.fromisoformat(bundle.local_day))
src/rebalance/ingest/gmail.py:151:                dt = dt.replace(tzinfo=timezone.utc)
src/rebalance/ingest/gmail.py:152:            return dt.astimezone(timezone.utc).isoformat()
src/rebalance/ingest/gmail.py:159:            return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()
src/rebalance/ingest/gmail.py:226:    start = time.monotonic()
src/rebalance/ingest/gmail.py:251:    synced_at = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/gmail.py:316:        elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/gmail.py:363:    start = time.monotonic()
src/rebalance/ingest/gmail.py:364:    synced_at = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/gmail.py:429:        elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/embedder.py:46:    now = time.monotonic()
src/rebalance/ingest/embedder.py:140:    _last_activity_time = time.monotonic()
src/rebalance/ingest/embedder.py:212:    start = time.monotonic()
src/rebalance/ingest/embedder.py:254:                elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/embedder.py:279:        now_iso = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/embedder.py:297:        elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/calendar_config.py:2:Calendar configuration — per-user settings for event filtering, calendar selection, and timezone.
src/rebalance/ingest/github_readiness.py:72:        target = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
src/rebalance/ingest/github_readiness.py:75:    now = datetime.now(timezone.utc)
src/rebalance/ingest/lifecycle.py:151:            "read time. Never persisted back to the registry."
src/rebalance/ingest/github_scan.py:120:    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
src/rebalance/ingest/github_scan.py:470:    now = datetime.now(timezone.utc)
src/rebalance/ingest/github_scan.py:477:        scanned_at=datetime.now(timezone.utc).isoformat(),
src/rebalance/ingest/github_scan.py:616:    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
src/rebalance/ingest/github_scan.py:723:    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")
src/rebalance/ingest/_http.py:55:_PROCESS_RUN_ID = f"pid-{os.getpid()}-{time.time_ns()}"
src/rebalance/ingest/_http.py:238:        sleep=time.sleep,
src/rebalance/ingest/token_meta.py:82:    now = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/token_meta.py:116:    now = now or datetime.now(timezone.utc)
src/rebalance/ingest/github_commit_backfill.py:85:        result = subprocess.run(
src/rebalance/ingest/github_commit_backfill.py:91:    except subprocess.TimeoutExpired:
src/rebalance/ingest/daily_report.py:218:    # Store UTC, compute "the day" in the user's local timezone. SQLite's
src/rebalance/ingest/daily_report.py:304:    """Format an event's start time in the configured local timezone."""
src/rebalance/ingest/github_knowledge.py:145:    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
src/rebalance/ingest/github_knowledge.py:365:    start = time.monotonic()
src/rebalance/ingest/github_knowledge.py:366:    fetched_at = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/github_knowledge.py:887:    elapsed = round(time.monotonic() - start, 2)
src/rebalance/ingest/github_knowledge.py:943:    start = time.monotonic()
src/rebalance/ingest/github_knowledge.py:962:                elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/github_knowledge.py:976:        now_iso = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/github_knowledge.py:991:        elapsed_seconds=round(time.monotonic() - start, 2),
src/rebalance/ingest/config.py:280:        result = subprocess.run(
src/rebalance/ingest/config.py:287:    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
src/rebalance/ingest/config.py:1556:        completed = subprocess.run(
src/rebalance/ingest/index_ops.py:207:# for why 30 minutes is well past a healthy run's expected completion time.
src/rebalance/ingest/index_ops.py:356:    now = datetime.now(timezone.utc)
src/rebalance/ingest/index_ops.py:744:            now = datetime.now(timezone.utc)
src/rebalance/ingest/index_ops.py:921:            datetime.now(timezone.utc) - timedelta(days=int(since_days))
src/rebalance/ingest/index_ops.py:1558:        target_date=date.today(),
src/rebalance/ingest/index_ops.py:1622:    started = time.monotonic()
src/rebalance/ingest/index_ops.py:1814:        "elapsed_seconds": round(time.monotonic() - started, 2),
src/rebalance/ingest/index_ops.py:1869:    sleep = sleep_fn if sleep_fn is not None else time.sleep
src/rebalance/ingest/index_ops.py:1950:    started = time.monotonic()
src/rebalance/ingest/index_ops.py:1967:        "elapsed_seconds": round(time.monotonic() - started, 2),
src/rebalance/ingest/watchlist_guard.py:125:        ts = int(now_ts if now_ts is not None else time.time())
src/rebalance/ingest/db/migrate.py:58:        (version, datetime.now(timezone.utc).isoformat()),
src/rebalance/ingest/pulse_health.py:79:        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
src/rebalance/ingest/pulse_health.py:187:    now = now or datetime.now(timezone.utc)
src/rebalance/ingest/db/semantic.py:404:    """Mark a document fresh: copy ``content_hash`` and stamp model/version/time."""
src/rebalance/ingest/weekly_report.py:153:        target_date = date.today()
src/rebalance/ingest/github_watch.py:140:    now = datetime.now(timezone.utc)
src/rebalance/ingest/github_watch.py:255:        datetime.now(timezone.utc).timestamp() - _LOCAL_RECENCY_DAYS * 86400
src/rebalance/ingest/ask_self_scan.py:8:file/chunk counts, embedding model, and last ingest time.
src/rebalance/ingest/ask_self_scan.py:125:        proc = subprocess.run(
src/rebalance/ingest/ask_self_scan.py:311:    scanned_at = datetime.now(timezone.utc).isoformat()
src/rebalance/ingest/profile_sync.py:170:        mtime = datetime.fromtimestamp(
src/rebalance/ingest/profile_sync.py:171:            log_path.stat().st_mtime, tz=timezone.utc
zsh:1: no matches found: requirements*.txt
     110

2026-08-14T19:04:57.861350Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
codex
The checkout has the Phase 2 work already committed on the feature branch (not as tracked uncommitted changes); I’m therefore reviewing the actual Phase 2 commit plus the current WIP state. The core mechanism matches your description.
exec
/bin/zsh -lc "python utils/pdda/check_banned_imports.py; git show --format=fuller --stat --summary 8b92ee81; git show --format= --name-only 8b92ee81 | sed -n '1,220p'; git show --format= --numstat 8b92ee81 | awk '{a+="'$1; d+=$2} END {print "added="a, "deleted="d}'"'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
2026-08-14T19:05:15.264247Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
 succeeded in 7646ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-gvPUTq8H' (errno=Operation not permitted)
2026-08-14 12:05:08.173 xcodebuild[563:100290731]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:08.441 xcodebuild[563:100290728] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-U9CKj4JS' (errno=Operation not permitted)
2026-08-14 12:05:09.104 xcodebuild[569:100290773]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:09.298 xcodebuild[569:100290771] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
commit 8b92ee81b1eb632864461323490a98955b48e89f
Author:     CI Runner <ci@runner.invalid>
AuthorDate: Tue Aug 11 20:12:16 2026 -0700
Commit:     CI Runner <ci@runner.invalid>
CommitDate: Tue Aug 11 20:12:16 2026 -0700

    Phase 2: Add mechanical governance rules and import linter (GH-266)

 AGENTS.md                          |   2 +
 ARCHITECTURE.md                    |   2 +
 PROJECT/PDDA.md                    |  96 +++++++++++++--
 ROUTER.md                          |   2 +
 utils/pdda/check_banned_imports.py |  35 ++++++
 utils/pdda/pdda.sh                 | 246 +++++++++++++++++++++++++++++++++++--
 6 files changed, 362 insertions(+), 21 deletions(-)
 create mode 100755 utils/pdda/check_banned_imports.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-1M5scwlk' (errno=Operation not permitted)
2026-08-14 12:05:10.746 xcodebuild[827:100290998]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:10.979 xcodebuild[827:100290997] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-ZogYdwrd' (errno=Operation not permitted)
2026-08-14 12:05:11.642 xcodebuild[832:100291017]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:11.842 xcodebuild[832:100291016] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
AGENTS.md
ARCHITECTURE.md
PROJECT/PDDA.md
ROUTER.md
utils/pdda/check_banned_imports.py
utils/pdda/pdda.sh
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-2zD1dJ7w' (errno=Operation not permitted)
2026-08-14 12:05:13.165 xcodebuild[991:100291244]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:13.367 xcodebuild[991:100291243] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-qjuGYUPu' (errno=Operation not permitted)
2026-08-14 12:05:13.944 xcodebuild[994:100291262]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:14.139 xcodebuild[994:100291260] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
added=362 deleted=21

exec
/bin/zsh -lc "git show --format=fuller --stat --summary 69c5f917; git show --format= --name-only 69c5f917 | sed -n '1,260p'; git show --format=fuller --stat --summary c88fdddc; git show --format= --name-only c88fdddc | sed -n '1,260p'; git show --format= --stat 21bc1b5e; git show --format= --name-only 21bc1b5e | sed -n '1,260p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
2026-08-14T19:05:30.744362Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
2026-08-14T19:05:37.833176Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
 succeeded in 17044ms:
2026-08-14 12:05:21.058 xcodebuild[1604:100292536]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:21.369 xcodebuild[1604:100292535] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-gUWvW2iL' (errno=Operation not permitted)
2026-08-14 12:05:22.236 xcodebuild[1612:100292575]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:22.483 xcodebuild[1612:100292574] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
commit 69c5f917c664ed064490ea87703e17c4cd773528
Author:     CI Runner <ci@runner.invalid>
AuthorDate: Tue Aug 11 20:04:41 2026 -0700
Commit:     CI Runner <ci@runner.invalid>
CommitDate: Tue Aug 11 20:04:41 2026 -0700

    Phase 1: Extract redundant utilities and refactor existing ingest collectors (GH-266)

 PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md | 63 +++++++++++++++++++++++++
 ROADMAP.md                                      |  2 +
 src/rebalance/ingest/apple_reminders_write.py   |  5 +-
 src/rebalance/ingest/diagnose.py                | 15 +-----
 src/rebalance/ingest/figma.py                   | 10 +---
 src/rebalance/ingest/focus5_scan.py             | 15 +-----
 src/rebalance/ingest/github_commit_backfill.py  |  5 +-
 src/rebalance/ingest/github_coverage.py         |  5 +-
 src/rebalance/ingest/github_direct_commits.py   |  5 +-
 src/rebalance/ingest/github_knowledge.py        |  5 +-
 src/rebalance/ingest/github_readiness.py        |  5 +-
 src/rebalance/ingest/github_reconciliation.py   |  5 +-
 src/rebalance/ingest/local_repos.py             | 10 +---
 src/rebalance/ingest/pulse.py                   |  5 +-
 src/rebalance/ingest/semantic_index.py          |  4 +-
 src/rebalance/lib/__init__.py                   |  0
 src/rebalance/lib/git_ops.py                    | 11 +++++
 src/rebalance/lib/json_ops.py                   |  6 +++
 src/rebalance/lib/time_ops.py                   | 20 ++++++++
 19 files changed, 116 insertions(+), 80 deletions(-)
 create mode 100644 PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md
 create mode 100644 src/rebalance/lib/__init__.py
 create mode 100644 src/rebalance/lib/git_ops.py
 create mode 100644 src/rebalance/lib/json_ops.py
 create mode 100644 src/rebalance/lib/time_ops.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-DrOXTZAh' (errno=Operation not permitted)
2026-08-14 12:05:23.969 xcodebuild[1751:100292809]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:24.183 xcodebuild[1751:100292806] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-jliHYv36' (errno=Operation not permitted)
2026-08-14 12:05:24.788 xcodebuild[1755:100292822]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:25.008 xcodebuild[1755:100292820] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md
ROADMAP.md
src/rebalance/ingest/apple_reminders_write.py
src/rebalance/ingest/diagnose.py
src/rebalance/ingest/figma.py
src/rebalance/ingest/focus5_scan.py
src/rebalance/ingest/github_commit_backfill.py
src/rebalance/ingest/github_coverage.py
src/rebalance/ingest/github_direct_commits.py
src/rebalance/ingest/github_knowledge.py
src/rebalance/ingest/github_readiness.py
src/rebalance/ingest/github_reconciliation.py
src/rebalance/ingest/local_repos.py
src/rebalance/ingest/pulse.py
src/rebalance/ingest/semantic_index.py
src/rebalance/lib/__init__.py
src/rebalance/lib/git_ops.py
src/rebalance/lib/json_ops.py
src/rebalance/lib/time_ops.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-tx1CfRSe' (errno=Operation not permitted)
2026-08-14 12:05:26.671 xcodebuild[1899:100293066]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:26.898 xcodebuild[1899:100293064] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-U6ZocxnV' (errno=Operation not permitted)
2026-08-14 12:05:27.544 xcodebuild[2048:100293328]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:27.756 xcodebuild[2048:100293325] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
commit c88fdddcb1e79d609b8fadffb6e305921ee644c8
Author:     CI Runner <ci@runner.invalid>
AuthorDate: Tue Aug 11 20:35:03 2026 -0700
Commit:     CI Runner <ci@runner.invalid>
CommitDate: Tue Aug 11 20:35:03 2026 -0700

    chore: Phase 3 (Technical Debt Eradication) - Remove redundant query methods and refactor TF-IDF batching

 .claude/settings.json                              |  19 +-
 .../scratch/refactor.py                            |  80 ++++++
 .pdda-quad                                         |   4 +
 ...ollector-sync-degraded-2-unexplained-error-s.md |  37 +++
 ...ollector-sync-degraded-2-unexplained-error-s.md |  37 +++
 ...ollector-sync-degraded-2-unexplained-error-s.md |  37 +++
 ...ollector-sync-degraded-4-unexplained-error-s.md |  39 +++
 ...ES-2026-08-04-collector-run-wrote-no-outcome.md |  35 +++
 ...ollector-sync-degraded-1-unexplained-error-s.md |  36 +++
 ...ector-sync-complete-1-unexplained-error-s-ou.md |  36 +++
 ...ollector-sync-degraded-2-unexplained-error-s.md |  37 +++
 .../3EYES-2026-08-10-collector-sync-stale-74h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-75h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-76h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-77h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-78h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-79h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-80h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-81h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-85h.md   |  32 +++
 .../3EYES-2026-08-10-collector-sync-stale-86h.md   |  32 +++
 ...ector-sync-complete-6-unexplained-error-s-ou.md |  41 +++
 PROJECT/1-INBOX/RADAR-REPORT-2026-08-07.md         | 281 +++++++++++++++++++++
 phases/gh195-p8-fleet-adoption--p1/RELAY.md        |  96 +++++++
 .../gh195-p8-fleet-adoption--p8-cutover/RELAY.md   | 113 +++++++++
 phases/gh195-p8-fleet-adoption--p8-wave2/RELAY.md  |  90 +++++++
 phases/gh195-p8-fleet-adoption--p8-wave3/RELAY.md  | 109 ++++++++
 .../RELAY.md                                       | 134 ++++++++++
 src/rebalance/cli/github.py                        |  10 +-
 src/rebalance/cli/query.py                         |   8 +-
 src/rebalance/ingest/embedder.py                   |  55 ----
 src/rebalance/ingest/github_knowledge.py           |  38 ---
 src/rebalance/ingest/note_ingester.py              |  89 ++++---
 src/rebalance/ingest/querier.py                    |  39 +--
 src/rebalance/mcp/tools/retrieval.py               |  40 ---
 tests/test_github_knowledge.py                     |   7 +-
 tests/test_mlx_cache_cap.py                        |   8 +-
 tests/test_mlx_instrumentation.py                  |   1 -
 tests/test_retrieval_contracts.py                  |  19 --
 utils/pdda/PDDA-INSTALL.md                         |  18 +-
 utils/pdda/pdda-lib.sh                             |  94 ++++++-
 41 files changed, 1756 insertions(+), 251 deletions(-)
 create mode 100644 .gemini/antigravity/brain/10c0a689-61ad-4401-b5e0-86c1235b0c01/scratch/refactor.py
 create mode 100644 .pdda-quad
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-07-31-collector-sync-degraded-2-unexplained-error-s.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-01-collector-sync-degraded-2-unexplained-error-s.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-02-collector-sync-degraded-2-unexplained-error-s.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-03-collector-sync-degraded-4-unexplained-error-s.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-04-collector-run-wrote-no-outcome.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-04-collector-sync-degraded-1-unexplained-error-s.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-05-collector-sync-complete-1-unexplained-error-s-ou.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-06-collector-sync-degraded-2-unexplained-error-s.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-74h.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-75h.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-76h.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-77h.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-78h.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-79h.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-80h.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-81h.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-85h.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-86h.md
 create mode 100644 PROJECT/1-INBOX/3EYES-2026-08-11-collector-sync-complete-6-unexplained-error-s-ou.md
 create mode 100644 PROJECT/1-INBOX/RADAR-REPORT-2026-08-07.md
 create mode 100644 phases/gh195-p8-fleet-adoption--p1/RELAY.md
 create mode 100644 phases/gh195-p8-fleet-adoption--p8-cutover/RELAY.md
 create mode 100644 phases/gh195-p8-fleet-adoption--p8-wave2/RELAY.md
 create mode 100644 phases/gh195-p8-fleet-adoption--p8-wave3/RELAY.md
 create mode 100644 phases/gh195-p8-fleet-adoption-resume--p8-cutover/RELAY.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-8vmwdDhP' (errno=Operation not permitted)
2026-08-14 12:05:29.209 xcodebuild[2082:100293544]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:29.442 xcodebuild[2082:100293543] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-68Oaa9jQ' (errno=Operation not permitted)
2026-08-14 12:05:30.112 xcodebuild[2221:100293783]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:30.340 xcodebuild[2221:100293780] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
.claude/settings.json
.gemini/antigravity/brain/10c0a689-61ad-4401-b5e0-86c1235b0c01/scratch/refactor.py
.pdda-quad
PROJECT/1-INBOX/3EYES-2026-07-31-collector-sync-degraded-2-unexplained-error-s.md
PROJECT/1-INBOX/3EYES-2026-08-01-collector-sync-degraded-2-unexplained-error-s.md
PROJECT/1-INBOX/3EYES-2026-08-02-collector-sync-degraded-2-unexplained-error-s.md
PROJECT/1-INBOX/3EYES-2026-08-03-collector-sync-degraded-4-unexplained-error-s.md
PROJECT/1-INBOX/3EYES-2026-08-04-collector-run-wrote-no-outcome.md
PROJECT/1-INBOX/3EYES-2026-08-04-collector-sync-degraded-1-unexplained-error-s.md
PROJECT/1-INBOX/3EYES-2026-08-05-collector-sync-complete-1-unexplained-error-s-ou.md
PROJECT/1-INBOX/3EYES-2026-08-06-collector-sync-degraded-2-unexplained-error-s.md
PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-74h.md
PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-75h.md
PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-76h.md
PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-77h.md
PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-78h.md
PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-79h.md
PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-80h.md
PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-81h.md
PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-85h.md
PROJECT/1-INBOX/3EYES-2026-08-10-collector-sync-stale-86h.md
PROJECT/1-INBOX/3EYES-2026-08-11-collector-sync-complete-6-unexplained-error-s-ou.md
PROJECT/1-INBOX/RADAR-REPORT-2026-08-07.md
phases/gh195-p8-fleet-adoption--p1/RELAY.md
phases/gh195-p8-fleet-adoption--p8-cutover/RELAY.md
phases/gh195-p8-fleet-adoption--p8-wave2/RELAY.md
phases/gh195-p8-fleet-adoption--p8-wave3/RELAY.md
phases/gh195-p8-fleet-adoption-resume--p8-cutover/RELAY.md
src/rebalance/cli/github.py
src/rebalance/cli/query.py
src/rebalance/ingest/embedder.py
src/rebalance/ingest/github_knowledge.py
src/rebalance/ingest/note_ingester.py
src/rebalance/ingest/querier.py
src/rebalance/mcp/tools/retrieval.py
tests/test_github_knowledge.py
tests/test_mlx_cache_cap.py
tests/test_mlx_instrumentation.py
tests/test_retrieval_contracts.py
utils/pdda/PDDA-INSTALL.md
utils/pdda/pdda-lib.sh
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-AJjXYnQB' (errno=Operation not permitted)
2026-08-14 12:05:31.985 xcodebuild[2362:100294012]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:32.259 xcodebuild[2362:100294010] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-uq2MPS76' (errno=Operation not permitted)
2026-08-14 12:05:32.952 xcodebuild[2369:100294060]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:33.195 xcodebuild[2369:100294059] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
 src/rebalance/ingest/querier.py | 1 -
 tests/test_github_knowledge.py  | 6 +++---
 2 files changed, 3 insertions(+), 4 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-aLANHNQg' (errno=Operation not permitted)
2026-08-14 12:05:34.691 xcodebuild[2513:100294312]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:34.976 xcodebuild[2513:100294311] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-w5VqGCTQ' (errno=Operation not permitted)
2026-08-14 12:05:35.856 xcodebuild[2545:100294624]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:36.234 xcodebuild[2545:100294452] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
src/rebalance/ingest/querier.py
tests/test_github_knowledge.py

exec
/bin/zsh -lc "git show --format=fuller --stat --summary HEAD; git show --format= --name-only HEAD | sed -n '1,300p'; git show HEAD:src/rebalance/doctor.py | sed -n '10,24p'; git show HEAD:src/rebalance/lib/subprocess_ops.py 2>&1 | sed -n '1,40p'; git diff HEAD -- src/rebalance/doctor.py; git ls-files -v src/rebalance/doctor.py src/rebalance/lib/time_ops.py src/rebalance/lib/subprocess_ops.py" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
2026-08-14T19:05:57.764225Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
2026-08-14T19:06:03.758666Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
 succeeded in 15939ms:
2026-08-14 12:05:48.048 xcodebuild[3429:100296332]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:48.355 xcodebuild[3429:100296331] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-3YOKe88C' (errno=Operation not permitted)
2026-08-14 12:05:48.998 xcodebuild[3575:100296600]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:49.192 xcodebuild[3575:100296599] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
commit 070c0f4d979577b7d1e882e348ea3ae0a514d9d2
Merge: 21bc1b5e 4c87381b
Author:     CI Runner <ci@runner.invalid>
AuthorDate: Fri Aug 14 12:03:46 2026 -0700
Commit:     CI Runner <ci@runner.invalid>
CommitDate: Fri Aug 14 12:03:46 2026 -0700

    WIP on feature/gh-266-phase3: 21bc1b5e fix(GH-266): Resolve broken test assertions and dangling imports

 .github/workflows/ci.yml                        | 14 +++++++--
 PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md | 38 ++++++++++++-------------
 src/rebalance/chat.py                           |  2 +-
 src/rebalance/cli/__init__.py                   |  2 +-
 src/rebalance/cli/calendar.py                   |  8 +++---
 src/rebalance/cli/dashboard.py                  |  2 +-
 src/rebalance/cli/onboard.py                    |  2 +-
 src/rebalance/cli/raw.py                        | 10 +++----
 src/rebalance/cli/reset.py                      |  2 +-
 src/rebalance/doctor.py                         |  6 ++--
 src/rebalance/health.py                         | 14 ++-------
 src/rebalance/ingest/apple_reminders.py         |  2 +-
 src/rebalance/ingest/apple_reminders_write.py   |  4 +--
 src/rebalance/ingest/ask_self_scan.py           |  4 +--
 src/rebalance/ingest/audit.py                   |  2 +-
 src/rebalance/ingest/auth_log.py                |  2 +-
 src/rebalance/ingest/calendar.py                |  2 +-
 src/rebalance/ingest/calendar_helpers.py        |  8 ++++--
 src/rebalance/ingest/calendar_snap.py           |  2 +-
 src/rebalance/ingest/claude_cloud.py            |  5 ++--
 src/rebalance/ingest/code_collector.py          |  2 +-
 src/rebalance/ingest/config.py                  |  4 +--
 src/rebalance/ingest/daily_report.py            |  2 +-
 src/rebalance/ingest/db/migrate.py              |  2 +-
 src/rebalance/ingest/diagnose.py                |  2 +-
 src/rebalance/ingest/embedder.py                |  2 +-
 src/rebalance/ingest/figma.py                   |  2 +-
 src/rebalance/ingest/focus5_scan.py             |  4 +--
 src/rebalance/ingest/github_commit_backfill.py  |  4 +--
 src/rebalance/ingest/github_coverage.py         |  4 +--
 src/rebalance/ingest/github_direct_commits.py   |  2 +-
 src/rebalance/ingest/github_knowledge.py        |  2 +-
 src/rebalance/ingest/github_readiness.py        |  2 +-
 src/rebalance/ingest/github_reconciliation.py   |  2 +-
 src/rebalance/ingest/github_scan.py             |  2 +-
 src/rebalance/ingest/github_watch.py            |  2 +-
 src/rebalance/ingest/gmail.py                   |  2 +-
 src/rebalance/ingest/goals_file.py              |  2 +-
 src/rebalance/ingest/index_ops.py               | 18 +++---------
 src/rebalance/ingest/local_repos.py             |  2 +-
 src/rebalance/ingest/next_actions.py            |  2 +-
 src/rebalance/ingest/note_builder.py            |  2 +-
 src/rebalance/ingest/note_ingester.py           |  4 +--
 src/rebalance/ingest/preflight.py               |  2 +-
 src/rebalance/ingest/profile_sync.py            |  8 +++---
 src/rebalance/ingest/project_inference.py       |  2 +-
 src/rebalance/ingest/pulse.py                   |  6 ++--
 src/rebalance/ingest/pulse_health.py            |  2 +-
 src/rebalance/ingest/querier.py                 |  2 +-
 src/rebalance/ingest/semantic_index.py          |  2 +-
 src/rebalance/ingest/sleuth_reminders.py        |  4 +--
 src/rebalance/ingest/sync_snapshot.py           |  4 +--
 src/rebalance/ingest/token_meta.py              |  2 +-
 src/rebalance/ingest/weekly_report.py           |  2 +-
 src/rebalance/lib/git_ops.py                    | 18 +++++++-----
 src/rebalance/lib/time_ops.py                   | 29 +++++++++++++++----
 src/rebalance/mcp/tools/calendar.py             |  4 +--
 src/rebalance/mcp/tools/hygiene.py              |  2 +-
 src/rebalance/tz_utils.py                       | 20 ++++---------
 src/rebalance/web.py                            |  4 +--
 tests/test_focus5_scan.py                       |  6 ++--
 tests/test_gemini_key_resolution.py             |  8 +++---
 utils/pdda/check_banned_imports.py              | 12 ++++++--
 utils/pdda/pdda.sh                              |  2 +-
 64 files changed, 179 insertions(+), 165 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-f4KJvtk5' (errno=Operation not permitted)
2026-08-14 12:05:50.616 xcodebuild[3609:100296746]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:50.858 xcodebuild[3609:100296681] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-eV7y9bN6' (errno=Operation not permitted)
2026-08-14 12:05:51.502 xcodebuild[3723:100296875]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:52.008 xcodebuild[3723:100296874] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
.github/workflows/ci.yml
PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md
src/rebalance/chat.py
src/rebalance/cli/__init__.py
src/rebalance/cli/calendar.py
src/rebalance/cli/dashboard.py
src/rebalance/cli/onboard.py
src/rebalance/cli/raw.py
src/rebalance/cli/reset.py
src/rebalance/doctor.py
src/rebalance/health.py
src/rebalance/ingest/apple_reminders.py
src/rebalance/ingest/apple_reminders_write.py
src/rebalance/ingest/ask_self_scan.py
src/rebalance/ingest/audit.py
src/rebalance/ingest/auth_log.py
src/rebalance/ingest/calendar.py
src/rebalance/ingest/calendar_helpers.py
src/rebalance/ingest/calendar_snap.py
src/rebalance/ingest/claude_cloud.py
src/rebalance/ingest/code_collector.py
src/rebalance/ingest/config.py
src/rebalance/ingest/daily_report.py
src/rebalance/ingest/db/migrate.py
src/rebalance/ingest/diagnose.py
src/rebalance/ingest/embedder.py
src/rebalance/ingest/figma.py
src/rebalance/ingest/focus5_scan.py
src/rebalance/ingest/github_commit_backfill.py
src/rebalance/ingest/github_coverage.py
src/rebalance/ingest/github_direct_commits.py
src/rebalance/ingest/github_knowledge.py
src/rebalance/ingest/github_readiness.py
src/rebalance/ingest/github_reconciliation.py
src/rebalance/ingest/github_scan.py
src/rebalance/ingest/github_watch.py
src/rebalance/ingest/gmail.py
src/rebalance/ingest/goals_file.py
src/rebalance/ingest/index_ops.py
src/rebalance/ingest/local_repos.py
src/rebalance/ingest/next_actions.py
src/rebalance/ingest/note_builder.py
src/rebalance/ingest/note_ingester.py
src/rebalance/ingest/preflight.py
src/rebalance/ingest/profile_sync.py
src/rebalance/ingest/project_inference.py
src/rebalance/ingest/pulse.py
src/rebalance/ingest/pulse_health.py
src/rebalance/ingest/querier.py
src/rebalance/ingest/semantic_index.py
src/rebalance/ingest/sleuth_reminders.py
src/rebalance/ingest/sync_snapshot.py
src/rebalance/ingest/token_meta.py
src/rebalance/ingest/weekly_report.py
src/rebalance/lib/git_ops.py
src/rebalance/lib/time_ops.py
src/rebalance/mcp/tools/calendar.py
src/rebalance/mcp/tools/hygiene.py
src/rebalance/tz_utils.py
src/rebalance/web.py
tests/test_focus5_scan.py
tests/test_gemini_key_resolution.py
utils/pdda/check_banned_imports.py
utils/pdda/pdda.sh
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-rlfiJwPj' (errno=Operation not permitted)
2026-08-14 12:05:53.566 xcodebuild[3876:100297280]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:53.790 xcodebuild[3876:100297278] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-MAglVUbU' (errno=Operation not permitted)
2026-08-14 12:05:54.438 xcodebuild[3885:100297353]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:54.676 xcodebuild[3885:100297352] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
"""

from __future__ import annotations

import json
import os
import re
import rebalance.lib.subprocess_ops as subprocess
from dataclasses import dataclass, field
from rebalance.lib.time_ops import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from rebalance.tz_utils import format_timestamp, local_tz

git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-YsLa27ok' (errno=Operation not permitted)
2026-08-14 12:05:56.102 xcodebuild[4027:100297611]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:56.343 xcodebuild[4027:100297609] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-wAhoYmhG' (errno=Operation not permitted)
2026-08-14 12:05:57.011 xcodebuild[4054:100297807]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:57.229 xcodebuild[4054:100297667] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
fatal: path 'src/rebalance/lib/subprocess_ops.py' exists on disk, but not in 'HEAD'
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-s13klCRe' (errno=Operation not permitted)
2026-08-14 12:05:58.720 xcodebuild[4216:100298478]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:58.987 xcodebuild[4216:100298476] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-SPHBReSQ' (errno=Operation not permitted)
2026-08-14 12:05:59.600 xcodebuild[4411:100299798]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:05:59.828 xcodebuild[4411:100299735] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-ABZLtmWh' (errno=Operation not permitted)
2026-08-14 12:06:01.389 xcodebuild[4642:100302135]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:06:01.653 xcodebuild[4642:100302082] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-xxyxp23v' (errno=Operation not permitted)
2026-08-14 12:06:02.286 xcodebuild[4698:100303149]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:06:02.493 xcodebuild[4698:100303070] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
H src/rebalance/doctor.py
H src/rebalance/lib/time_ops.py

exec
/bin/zsh -lc "rg -o --glob '*.py' 'subprocess\\.[A-Za-z_]+' src/rebalance | sed 's/.*subprocess\\.//' | sort -u; rg -n --glob '*.py' '"'^(import|from) (datetime|subprocess)'"' src/rebalance/mcp src/rebalance/cli src/rebalance/ingest src/rebalance | sed -n '1,180p'; nl -ba src/rebalance/mcp/tools/hygiene.py | sed -n '1,110p'; nl -ba src/rebalance/web.py | sed -n '1,42p'; nl -ba src/rebalance/cli/onboard.py | sed -n '1,26p'; nl -ba src/rebalance/cli/raw.py | sed -n '1,28p'; nl -ba src/rebalance/ingest/claude_cloud.py | sed -n '1,40p'; nl -ba src/rebalance/lib/git_ops.py | sed -n '1,100p'; nl -ba src/rebalance/lib/json_ops.py | sed -n '1,100p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
 succeeded in 0ms:
CalledProcessError
DEVNULL
SubprocessError
TimeoutExpired
check_output
run
src/rebalance/lib/subprocess_ops.py:1:from subprocess import run, Popen, PIPE, TimeoutExpired, CalledProcessError, check_output, check_call, DEVNULL, SubprocessError
src/rebalance/lib/time_ops.py:1:from datetime import datetime, timezone, timedelta, date, time
src/rebalance/lib/git_ops.py:1:import subprocess
     1	from __future__ import annotations
     2	
     3	from pathlib import Path
     4	from typing import Any
     5	
     6	from mcp.server.fastmcp import FastMCP
     7	
     8	# project root: src/rebalance/mcp/tools/hygiene.py → 5 levels up
     9	_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
    10	
    11	
    12	def register(mcp: FastMCP, database_path: Path) -> None:
    13	    @mcp.tool()
    14	    def audit_modules(
    15	        init: bool = False,
    16	        commits_window: int = 20,
    17	        include_uncommitted: bool = False,
    18	    ) -> dict[str, Any]:
    19	        """
    20	        Audit ingest collectors, render modules, and scheduled-job infrastructure
    21	        against ARCHITECTURE.md and CHANGELOG.md.
    22	
    23	        Three checks run on every invocation:
    24	          1. ARCHITECTURE.md mention check — every Python module in ingest/ and
    25	             scripts/ (minus IGNORED_FILES) is mentioned somewhere in
    26	             ARCHITECTURE.md.
    27	          2. CHANGELOG.md historical-mention check — same, against any past
    28	             version section.
    29	          3. Recent-commit coverage — last `commits_window` commits since the
    30	             latest version's date have their touched .py/.sh/.plist files
    31	             reflected in that version's CHANGELOG section.
    32	
    33	        Pre-existing gaps (#1 and #2) can be silenced via a baseline lockfile
    34	        at scripts/audit_modules.lock; the audit then fails only on NEW drift.
    35	        Re-snapshot the baseline after a doc backfill by calling with init=True.
    36	
    37	        Returns the script's stable JSON schema (audit_version=1):
    38	          {
    39	            "audit_version": 1,
    40	            "passed": bool,
    41	            "exit_code": int,         # 0 pass, 1 new drift, 2 cannot run
    42	            "summary": str,
    43	            "candidate_modules_count": int,
    44	            "checks": {
    45	              "ignored_files_valid": {...},
    46	              "architecture_md":     {"new_misses": [...], "silenced_by_baseline": [...], "resolved_in_lockfile": [...]},
    47	              "changelog_md":        {... same shape ...},
    48	              "recent_commits":      {"commits_examined": int, "version_section_checked": str,
    49	                                      "version_date": str, "missing_from_changelog": [...]}
    50	            },
    51	            "next_steps": [str, ...]  # actionable guidance for an orchestrating agent
    52	          }
    53	
    54	        Args:
    55	            init: Snapshot current ARCHITECTURE.md and CHANGELOG.md misses as
    56	                the baseline lockfile and exit. Use after a deliberate doc
    57	                backfill to re-zero the audit.
    58	            commits_window: How many recent commits to check against the latest
    59	                CHANGELOG version (default: 20). Bounded by the version date —
    60	                older commits already documented under prior versions are
    61	                excluded automatically.
    62	            include_uncommitted: Pre-commit preview. When True, also flag
    63	                working-tree changes (modified or untracked audit-worthy files)
    64	                that aren't in the latest CHANGELOG section. Useful for an agent
    65	                doing a "would this commit pass the audit?" check before staging.
    66	        """
    67	        import json as _json
    68	        import rebalance.lib.subprocess_ops as subprocess
    69	        import sys as _sys
    70	
    71	        script_path = _PROJECT_ROOT / "scripts" / "audit_modules.py"
    72	
    73	        cmd = [_sys.executable, str(script_path), "--json", "--commits", str(commits_window)]
    74	        if init:
    75	            cmd.append("--init")
    76	        if include_uncommitted:
    77	            cmd.append("--include-uncommitted")
    78	
    79	        try:
    80	            proc = subprocess.run(
    81	                cmd,
    82	                cwd=_PROJECT_ROOT,
    83	                capture_output=True,
    84	                text=True,
    85	                timeout=60,
    86	            )
    87	        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
    88	            return {
    89	                "audit_version": 1,
    90	                "passed": False,
    91	                "exit_code": 2,
    92	                "summary": f"audit_modules subprocess failed: {exc}",
    93	                "error": str(exc),
    94	            }
    95	
    96	        if not proc.stdout.strip():
    97	            return {
    98	                "audit_version": 1,
    99	                "passed": False,
   100	                "exit_code": proc.returncode if proc.returncode is not None else 2,
   101	                "summary": "audit_modules produced no output",
   102	                "stderr": proc.stderr,
   103	            }
   104	        try:
   105	            return _json.loads(proc.stdout)
   106	        except _json.JSONDecodeError as exc:
   107	            return {
   108	                "audit_version": 1,
   109	                "passed": False,
   110	                "exit_code": 2,
     1	"""Minimal FastAPI web server for rebalance-OS local dashboards.
     2	
     3	Start with:
     4	    rebalance serve            # default port 8787
     5	    rebalance serve --port 9000
     6	
     7	Routes
     8	------
     9	GET /              — index with links to all pages
    10	GET /focus-5       — top-5 device-local repos: tree health, newest PR, activity
    11	GET /auth-log      — unified auth-activity log across all collectors (HTML table)
    12	GET /auth-log/raw  — raw JSONL file download
    13	"""
    14	
    15	from __future__ import annotations
    16	
    17	import base64
    18	import html
    19	import json
    20	import logging
    21	import secrets
    22	import sqlite3
    23	import threading
    24	import time
    25	import uuid
    26	from contextlib import asynccontextmanager
    27	from rebalance.lib.time_ops import datetime, timezone
    28	from pathlib import Path
    29	from typing import Any, Callable
    30	
    31	from fastapi import FastAPI, Request
    32	from fastapi.responses import (
    33	    HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse,
    34	)
    35	from pydantic import BaseModel
    36	
    37	from rebalance.ingest.auth_log import read_log, _log_path
    38	from rebalance.ingest import zapier_calendar, zapier_email
    39	from rebalance.ingest.sleuth_grouping import grouped_reminders_from_db
    40	from rebalance.paths import resolve_db, resolve_secret_path
    41	from rebalance.tz_utils import format_relative
    42	from rebalance.web_components import badge_html, button_link, render_shell
     1	"""`rebalance onboard` — guided setup: token, project discovery, initial refresh.
     2	
     3	Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.
     4	"""
     5	
     6	from __future__ import annotations
     7	
     8	from pathlib import Path
     9	from typing import Any
    10	
    11	import typer
    12	
    13	from rebalance.cli._core import app
    14	from rebalance.paths import (
    15	    DatabaseNotFoundError,
    16	    DBOption,
    17	    canonical_database_path,
    18	    resolve_database_path,
    19	)
    20	
    21	
    22	# Status glyphs — same vocabulary the /welcome skill renders; the CLI is the
    23	# no-LLM parity client of the lifecycle contract.
    24	_STATUS_GLYPHS = {
    25	    "done": "[x]",
    26	    "now": " ->",
     1	"""`rebalance raw` — calibration probe: recent GitHub events vs local pipeline state.
     2	
     3	Extracted from the cli monolith (Phase 5). Registers the `raw` command on the
     4	shared Typer `app` and keeps its `_raw_*` helpers alongside it.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from pathlib import Path
    10	from typing import Any
    11	
    12	import typer
    13	
    14	from rebalance.cli._core import app
    15	from rebalance.ingest.config import get_github_ignored_repos
    16	from rebalance.paths import DatabaseNotFoundError, DBOption, resolve_database_path
    17	
    18	
    19	# ---------------------------------------------------------------------------
    20	# Raw activity probe (calibration tool)
    21	# ---------------------------------------------------------------------------
    22	
    23	def _raw_summarize_event(event: dict[str, Any]) -> str:
    24	    """One-line summary of a GitHub user-event dict."""
    25	    kind = event.get("type") or ""
    26	    p = event.get("payload") or {}
    27	    if kind == "PushEvent":
    28	        n = len(p.get("commits") or [])
     1	"""Claude Code Cloud (web) sessions — signal source.
     2	
     3	Reads the ad-hoc cloud coding sessions behind the VS Code "Claude Code > Web" tab
     4	(``GET api.anthropic.com/v1/code/sessions``, subscription OAuth bearer token from the
     5	macOS keychain), enriches each with its head-branch PR merge status, and exposes:
     6	
     7	  * :func:`sessions_for_day` — normalized session rows for a local day (fail-soft).
     8	  * :func:`grade` — a data-quality grade over those rows (the observation surface;
     9	    written into the Obsidian daily note by ``utils/claude_cloud_daily_grade.py``).
    10	  * :func:`claude_cloud_candidates` — the HiQS ``candidates=`` provider (GH-128).
    11	
    12	**Ships DORMANT.** ``claude_cloud_candidates`` yields nothing unless
    13	``claude_cloud_signal_enabled`` is set true in the config (default False) — so the
    14	signal is fully wired into the ranker's registry seam but contributes zero to the
    15	live verdict until the operator promotes it after watching the daily-note grade.
    16	Promotion to first-class (a raw table + ``OperatorBundle`` field, no live read in the
    17	ranking path) is tracked in PROJECT/1-INBOX/GH-128-CC-CLOUD-JOBS-INGEST.md.
    18	
    19	Standalone POC twin: ``scripts/cc_cloud_jobs.py`` (stdlib-only, no package import).
    20	"""
    21	
    22	from __future__ import annotations
    23	
    24	from rebalance.lib.time_ops import datetime, timedelta, timezone, date, time
    25	import json
    26	import logging
    27	import shutil
    28	import rebalance.lib.subprocess_ops as subprocess
    29	import urllib.error
    30	import urllib.parse
    31	import urllib.request
    32	from typing import Any
    33	import rebalance.lib.time_ops as dt
    34	
    35	logger = logging.getLogger(__name__)
    36	
    37	BASE = "https://api.anthropic.com"
    38	KEYCHAIN_SERVICE = "Claude Code-credentials"
    39	CREDS_FILE = "~/.claude/.credentials.json"
    40	
     1	import subprocess
     2	from pathlib import Path
     3	
     4	def _git(repo_path: Path, *args: str, timeout: float = 30.0) -> str | None:
     5	    """Run git in *repo_path* and return stdout. Returns None if it fails."""
     6	    try:
     7	        result = subprocess.run(
     8	            ["git", "-C", str(repo_path), *args],
     9	            capture_output=True,
    10	            text=True,
    11	            timeout=timeout
    12	        )
    13	        return result.stdout.strip() if result.returncode == 0 else None
    14	    except subprocess.TimeoutExpired:
    15	        return None
     1	import json
     2	from typing import Any
     3	
     4	def _json_dumps(value: Any) -> str:
     5	    """Returns a deterministic, sorted, ensure_ascii=False JSON string."""
     6	    return json.dumps(value, ensure_ascii=False, sort_keys=True)

2026-08-14T19:06:23.335300Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
exec
/bin/zsh -lc 'git diff HEAD''^1 HEAD -- src/rebalance/lib/time_ops.py src/rebalance/lib/git_ops.py utils/pdda/check_banned_imports.py .github/workflows/ci.yml src/rebalance/doctor.py src/rebalance/health.py src/rebalance/ingest/index_ops.py src/rebalance/tz_utils.py PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md | sed -n '"'1,900p'; nl -ba AGENTS.md | sed -n '150,230p'; nl -ba PROJECT/PDDA.md | sed -n '1,180p'; nl -ba ARCHITECTURE.md | sed -n '1,140p'; nl -ba ROUTER.md | sed -n '1,160p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
2026-08-14T19:06:33.599865Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
 succeeded in 2468ms:
2026-08-14 12:06:31.326 xcodebuild[9284:100333483]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:06:31.608 xcodebuild[9284:100333405] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-UvUlqJ6I' (errno=Operation not permitted)
2026-08-14 12:06:32.293 xcodebuild[9346:100334600]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-08-14 12:06:32.490 xcodebuild[9346:100334542] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index a8203d46..3ca481a0 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -57,8 +57,8 @@ jobs:
 
       - name: Check for raw datetime parsing (use parse_calendar_dt)
         run: |
-          if grep -rn "replace('Z'" src/rebalance/ingest/ --include="*.py" \
-               | grep -v "# raw-ok" | grep -v calendar_helpers.py; then
+          if grep -rn "replace('Z'" src/rebalance/ --include="*.py" \
+               | grep -v "# raw-ok" | grep -v calendar_helpers.py | grep -v "src/rebalance/lib/"; then
             echo "::error::Raw Z-replace found — use parse_calendar_dt() from calendar_helpers.py"
             exit 1
           fi
@@ -66,7 +66,15 @@ jobs:
       - name: Check for raw duration calculation (use event_duration_minutes)
         run: |
           if grep -rn "total_seconds() / 60" src/rebalance/ --include="*.py" \
-               | grep -v "# raw-ok" | grep -v calendar_helpers.py; then
+               | grep -v "# raw-ok" | grep -v calendar_helpers.py | grep -v "src/rebalance/lib/"; then
             echo "::error::Raw duration calc found — use event_duration_minutes() from calendar_helpers.py"
             exit 1
           fi
+
+      - name: Check for banned imports
+        run: python utils/pdda/check_banned_imports.py
+
+      - name: Check for duplicate code
+        run: |
+          python -m pip install pylint
+          pylint --disable=all --enable=duplicate-code src/rebalance/
diff --git a/PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md b/PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md
index 419d6f2e..038e91c0 100644
--- a/PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md
+++ b/PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md
@@ -16,7 +16,7 @@ phases: 3
 
 | What was just completed | What's next |
 |---|---|
-| Cut new branch and created PDDA tracking doc | Execute Phase 1: extract `_parse_iso`, `_now_iso`, `_json_dumps` to `src/rebalance/lib` |
+| Completed all 3 phases and addressed PR feedback from Codex | Done |
 
 ## Quad Concepts
 - Repeated duplicate ingest logic → Extract into domain-specific shared libraries (`src/rebalance/lib/time_ops.py`, etc.)
@@ -33,31 +33,31 @@ phases: 3
 
 Extract duplicated ingest utility functions into domain-specific shared libraries. 
 
-- [ ] Extract time-related utilities (`_parse_iso`, `_now_iso`, `_now`) into `src/rebalance/lib/time_ops.py`.
-- [ ] Extract JSON-related utilities (`_json_dumps`) into `src/rebalance/lib/json_ops.py`.
-- [ ] Extract Git-related utilities (`_git`) into `src/rebalance/lib/git_ops.py`.
-- [ ] Extract dictionary utilities (`as_dict`) into `src/rebalance/lib/dict_ops.py`.
-- [ ] Refactor all existing collectors to import from these new domain-specific `lib/` modules.
-- [ ] **QA Gate**: Run `pytest tests/` to ensure no regressions in behavior.
-- [ ] **QA Gate**: Run `utils/pdda/pdda.sh run` to verify structural compliance.
+- [x] Extract time-related utilities (`_parse_iso`, `_now_iso`, `_now`) into `src/rebalance/lib/time_ops.py`.
+- [x] Extract JSON-related utilities (`_json_dumps`) into `src/rebalance/lib/json_ops.py`.
+- [x] Extract Git-related utilities (`_git`) into `src/rebalance/lib/git_ops.py`. *(Note: `github_commit_backfill.py` intentionally kept its own `_git` as it has a different return type tuple contract)*
+- [~] Extract dictionary utilities (`as_dict`) into `src/rebalance/lib/dict_ops.py`. *(Deliberately skipped: `as_dict` is implemented per-dataclass and not genuinely shared)*
+- [x] Refactor all existing collectors to import from these new domain-specific `lib/` modules.
+- [x] **QA Gate**: Run `pytest tests/` to ensure no regressions in behavior.
+- [x] **QA Gate**: Run `utils/pdda/pdda.sh run` to verify structural compliance.
 
 ## Phase 2 — Governance System Rules
 
 To prevent Agents (and human developers) from building overlapping systems in the future, enforce mechanical chokepoints across the governance documentation:
 
-- [ ] Update `AGENTS.md` (Agent Behavior) to enforce importing `datetime`, `json`, and `subprocess` exclusively from `rebalance.lib.*`. 
-- [ ] Update `PROJECT/PDDA.md` (Design Decision & Automation) to require `pylint --enable=duplicate-code` in the CI pipeline and introduce mechanical import bans for `subprocess` and `datetime` outside of `src/rebalance/lib/`.
-- [ ] Update `ARCHITECTURE.md` (System Constraints) to include the "Compose, Don't Mutate" rule, forcing features to break core functions into primitives rather than adding conditional flags.
-- [ ] Update `ROUTER.md` (Entry Point Rules) to introduce a strict rule: any new system overlapping >50% with an old system MUST include the deletion of the old system in the same PR.
-- [ ] Implement `import-linter` or a CI script to physically fail the build on restricted imports.
-- [ ] **QA Gate**: Run `utils/pdda/pdda.sh run` and verify it passes with 0 errors on governance checks.
+- [x] Update `AGENTS.md` (Agent Behavior) to enforce importing `datetime`, `json`, and `subprocess` exclusively from `rebalance.lib.*`. 
+- [x] Update `PROJECT/PDDA.md` (Design Decision & Automation) to require `pylint --enable=duplicate-code` in the CI pipeline and introduce mechanical import bans for `subprocess` and `datetime` outside of `src/rebalance/lib/`.
+- [x] Update `ARCHITECTURE.md` (System Constraints) to include the "Compose, Don't Mutate" rule, forcing features to break core functions into primitives rather than adding conditional flags.
+- [x] Update `ROUTER.md` (Entry Point Rules) to introduce a strict rule: any new system overlapping >50% with an old system MUST include the deletion of the old system in the same PR.
+- [x] Implement `import-linter` or a CI script to physically fail the build on restricted imports.
+- [x] **QA Gate**: Run `utils/pdda/pdda.sh run` and verify it passes with 0 errors on governance checks.
 
 ## Phase 3 — Technical Debt Eradication & Primitives Application
 
 Apply the newly established governance rules retroactively to prune redundant systems and fix architectural stability issues.
 
-- [ ] **Audit Overlapping Systems:** Identify existing read-paths and query layers that violate the >50% overlap rule (e.g., investigating `semantic_query` vs `ask` vs `query_notes`).
-- [ ] **Execute Deletions:** Deprecate and delete the legacy, redundant systems identified in the audit to force all traffic through a single, well-maintained pipeline.
-- [ ] **Refactor God Objects (Fixing #222):** Apply the "Compose, Don't Mutate" rule to the `Database is locked` (#222) issue. Refactor the monolithic, unbounded TF-IDF rebuild transactions into smaller, composable, batched transaction primitives. 
-- [ ] **QA Gate:** Run the test suite (`pytest tests/`) to ensure no downstream dependencies break from the deleted query layers.
-- [ ] **QA Gate:** Complete final `utils/pdda/pdda.sh run` validation.
+- [x] **Audit Overlapping Systems:** Identify existing read-paths and query layers that violate the >50% overlap rule (e.g., investigating `semantic_query` vs `ask` vs `query_notes`).
+- [x] **Execute Deletions:** Deprecate and delete the legacy, redundant systems identified in the audit to force all traffic through a single, well-maintained pipeline.
+- [x] **Refactor God Objects (Fixing #222):** Apply the "Compose, Don't Mutate" rule to the `Database is locked` (#222) issue. Refactor the monolithic, unbounded TF-IDF rebuild transactions into smaller, composable, batched transaction primitives. 
+- [x] **QA Gate:** Run the test suite (`pytest tests/`) to ensure no downstream dependencies break from the deleted query layers.
+- [x] **QA Gate:** Complete final `utils/pdda/pdda.sh run` validation.
diff --git a/src/rebalance/doctor.py b/src/rebalance/doctor.py
index 4da61d7a..f9ffc1c3 100644
--- a/src/rebalance/doctor.py
+++ b/src/rebalance/doctor.py
@@ -14,9 +14,9 @@ from __future__ import annotations
 import json
 import os
 import re
-import subprocess
+import rebalance.lib.subprocess_ops as subprocess
 from dataclasses import dataclass, field
-from datetime import datetime, timezone
+from rebalance.lib.time_ops import datetime, timezone
 from pathlib import Path
 from typing import Callable, Literal
 
@@ -934,7 +934,7 @@ def _check_sleuth(db_path: Path | None = None) -> Check:
     # reread even when the upstream export is dead — against now.
     if db_path is not None:
         try:
-            from datetime import datetime, timezone
+            from rebalance.lib.time_ops import datetime, timezone
 
             from rebalance.ingest.sleuth_reminders import get_export_generated_at
 
diff --git a/src/rebalance/health.py b/src/rebalance/health.py
index abd60523..40c7fc92 100644
--- a/src/rebalance/health.py
+++ b/src/rebalance/health.py
@@ -24,7 +24,7 @@ update both together.
 from __future__ import annotations
 
 from dataclasses import dataclass, field
-from datetime import datetime, timezone
+from rebalance.lib.time_ops import datetime, timezone
 from typing import Any
 
 from rebalance.doctor import ERROR, FAIL, NOTICE, OK, WARN, WARNING, Check
@@ -47,16 +47,8 @@ AUTH_RECOVERY: dict[str, tuple[str, int]] = {
 
 
 def _parse_iso(raw: Any) -> datetime | None:
-    if not raw or not isinstance(raw, str):
-        return None
-    s = raw.strip()
-    if s.endswith("Z"):
-        s = s[:-1] + "+00:00"
-    try:
-        dt = datetime.fromisoformat(s)
-    except ValueError:
-        return None
-    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
+    from rebalance.lib.time_ops import _parse_iso as common_parse_iso
+    return common_parse_iso(raw, force_utc=True)
 
 
 def status_timestamp(status: dict[str, Any], key: str) -> str | None:
diff --git a/src/rebalance/ingest/index_ops.py b/src/rebalance/ingest/index_ops.py
index 1b680592..fc444c80 100644
--- a/src/rebalance/ingest/index_ops.py
+++ b/src/rebalance/ingest/index_ops.py
@@ -13,7 +13,7 @@ import logging
 import sqlite3
 import time
 from dataclasses import dataclass
-from datetime import date, datetime, timedelta, timezone
+from rebalance.lib.time_ops import date, datetime, timedelta, timezone
 from pathlib import Path
 from typing import Any, Callable, Iterable
 
@@ -292,18 +292,8 @@ _SIGNAL_HEALTH_TOTAL_KEYS: dict[str, tuple[str, ...]] = {
 
 
 def _parse_status_timestamp(raw: Any) -> datetime | None:
-    if not raw or not isinstance(raw, str):
-        return None
-    text = raw.strip().replace("Z", "+00:00")
-    for candidate in (text, text.replace(" ", "T")):
-        try:
-            parsed = datetime.fromisoformat(candidate)
-            if parsed.tzinfo is None:
-                return parsed.replace(tzinfo=timezone.utc)
-            return parsed.astimezone(timezone.utc)
-        except ValueError:
-            continue
-    return None
+    from rebalance.lib.time_ops import _parse_iso as common_parse_iso
+    return common_parse_iso(raw, force_utc=True)
 
 
 def _vault_ingest_lag_minutes(last_modified_in_vault: Any, last_ingested_at: Any) -> float | None:
@@ -923,7 +913,7 @@ def _pushed_repos(database_path: Path, *, since_days: int = 14) -> list[str]:
     force-push edge cases. The events feed and this signal are
     complementary; the union goes into the watched set.
     """
-    from datetime import datetime, timedelta, timezone
+    from rebalance.lib.time_ops import datetime, timedelta, timezone
 
     repos: list[str] = []
     try:
diff --git a/src/rebalance/lib/git_ops.py b/src/rebalance/lib/git_ops.py
index abd31a19..b1b8c9f5 100644
--- a/src/rebalance/lib/git_ops.py
+++ b/src/rebalance/lib/git_ops.py
@@ -1,11 +1,15 @@
 import subprocess
 from pathlib import Path
 
-def _git(repo_path: Path, *args: str) -> str | None:
+def _git(repo_path: Path, *args: str, timeout: float = 30.0) -> str | None:
     """Run git in *repo_path* and return stdout. Returns None if it fails."""
-    result = subprocess.run(
-        ["git", "-C", str(repo_path), *args],
-        capture_output=True,
-        text=True,
-    )
-    return result.stdout.strip() if result.returncode == 0 else None
+    try:
+        result = subprocess.run(
+            ["git", "-C", str(repo_path), *args],
+            capture_output=True,
+            text=True,
+            timeout=timeout
+        )
+        return result.stdout.strip() if result.returncode == 0 else None
+    except subprocess.TimeoutExpired:
+        return None
diff --git a/src/rebalance/lib/time_ops.py b/src/rebalance/lib/time_ops.py
index da43dd50..e648d73a 100644
--- a/src/rebalance/lib/time_ops.py
+++ b/src/rebalance/lib/time_ops.py
@@ -1,11 +1,28 @@
-from datetime import datetime, timezone
+from datetime import datetime, timezone, timedelta, date, time
 
-def _parse_iso(value: str | None) -> datetime | None:
-    if not value: return None
-    try:
-        return datetime.fromisoformat(value.replace('Z', '+00:00'))
-    except ValueError:
+from typing import Any
+
+def _parse_iso(raw: Any, force_utc: bool = True) -> datetime | None:
+    if not raw or not isinstance(raw, str):
+        return None
+    text = raw.strip().replace("Z", "+00:00")
+    
+    parsed = None
+    for candidate in (text, text.replace(" ", "T")):
+        try:
+            parsed = datetime.fromisoformat(candidate)
+            break
+        except ValueError:
+            continue
+            
+    if not parsed:
         return None
+        
+    if force_utc:
+        if parsed.tzinfo is None:
+            return parsed.replace(tzinfo=timezone.utc)
+        return parsed.astimezone(timezone.utc)
+    return parsed
 
 def _now_iso() -> str:
     """Returns the current UTC time as an ISO format string."""
diff --git a/src/rebalance/tz_utils.py b/src/rebalance/tz_utils.py
index 681bb8bf..1b734fef 100644
--- a/src/rebalance/tz_utils.py
+++ b/src/rebalance/tz_utils.py
@@ -10,7 +10,7 @@ for operator-facing display (terminal dashboard, pulse, reports).
 from __future__ import annotations
 
 import os
-from datetime import datetime, timezone
+from rebalance.lib.time_ops import datetime, timezone
 from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
 
 
@@ -52,21 +52,13 @@ def to_local(dt: datetime, tz: ZoneInfo | None = None) -> datetime:
 
 
 def parse_utc_iso(value: str | None) -> datetime | None:
-    """Parse an ISO 8601 string; assumes UTC if tzinfo is absent.
-
-    Handles both trailing-Z (GitHub/Sleuth APIs) and +HH:MM offset forms.
+    """Parse an ISO 8601 string and ensure it is timezone-aware in UTC.
+    
+    If the string specifies no timezone, it is assumed to be UTC.
     Returns None on empty input or parse failure.
     """
-    if not value:
-        return None
-    text = value.strip().replace("Z", "+00:00")
-    try:
-        parsed = datetime.fromisoformat(text)
-    except ValueError:
-        return None
-    if parsed.tzinfo is None:
-        parsed = parsed.replace(tzinfo=timezone.utc)
-    return parsed
+    from rebalance.lib.time_ops import _parse_iso
+    return _parse_iso(value, force_utc=True)
 
 
 def format_local(value: str | datetime | None, fmt: str, *, tz: ZoneInfo | None = None) -> str:
diff --git a/utils/pdda/check_banned_imports.py b/utils/pdda/check_banned_imports.py
index c7b8638d..8462ba74 100755
--- a/utils/pdda/check_banned_imports.py
+++ b/utils/pdda/check_banned_imports.py
@@ -11,18 +11,21 @@ def check_file(path: Path) -> list[str]:
     except Exception as e:
         return []
 
+    is_lib = "lib" in path.parts
+
     for node in ast.walk(tree):
         if isinstance(node, ast.Import):
             for alias in node.names:
-                if alias.name in ("subprocess", "datetime") and "src/rebalance/lib" not in str(path):
+                if alias.name in ("subprocess", "datetime") and not is_lib:
                     errors.append(f"{path}:{node.lineno}: Banned import '{alias.name}'. Use rebalance.lib instead.")
         elif isinstance(node, ast.ImportFrom):
-            if node.module in ("subprocess", "datetime") and "src/rebalance/lib" not in str(path):
+            if node.module in ("subprocess", "datetime") and not is_lib:
                 errors.append(f"{path}:{node.lineno}: Banned import from '{node.module}'. Use rebalance.lib instead.")
     return errors
 
 def main():
-    root_dir = Path("src/rebalance/ingest")
+    root_dir = Path("src/rebalance")
+    any_errors = False
     for root, _, files in os.walk(root_dir):
         for file in files:
             if file.endswith(".py"):
@@ -30,6 +33,9 @@ def main():
                 errors = check_file(path)
                 for err in errors:
                     print(err)
+                    any_errors = True
+    
+    sys.exit(1 if any_errors else 0)
 
 if __name__ == "__main__":
     main()
   150	- Alerts should be actionable. If a threshold fires, the runbook or next step should be obvious. No alert without a documented response.
   151	- For WordPress/WooCommerce: hook into `query_monitor` data, log slow queries (>500ms), and monitor Action Scheduler queue depth from the start.
   152	- Dashboards and log queries are deliverables, not afterthoughts. Include them in the PR or project doc alongside the code.
   153	
   154	## Testing & Mock Harnesses
   155	
   156	- Write tests _before_ integrating with external APIs. Use mock harnesses to simulate responses.
   157	- Mock harnesses should cover: happy path, rate limits (429), timeouts (504), malformed responses, and auth failures (401/403).
   158	- Store mock response fixtures in `/fixtures/` (JSON, YAML, or plaintext). Keep them realistic and versioned.
   159	- Use conditional logic or env vars (`MOCK_MODE=true`) to toggle between real and mock backends without code changes.
   160	- For external integrations (Shopify, WooCommerce, Meta Ads, GA4), create a mock server or HTTP interceptor (e.g., `nock` in Node, `responses` in Python, `http-mock` in Go).
   161	- Test both sync and async paths separately; async errors (timeouts, retries) are common blindspots.
   162	- Assert on side effects (logs, DB writes, queue messages) not just return values. Mock should verify agent behavior, not just response parsing.
   163	
   164	## Versioning & Changelog
   165	
   166	- There is no concept of "Unreleased." Every fix or feature gets a version bump at time of commit/merge.
   167	- Use semver: MAJOR for breaking changes, MINOR for features, PATCH for fixes.
   168	- Documentation-only changes do not increment version unless explicitly instructed.
   169	- Changelog entries describe _what changed and why_ in plain language. Do not include project names, filenames, or folder paths in changelog entries — those belong in `4X4.md` or project docs, not the changelog.
   170	- Format: `## [x.y.z] - YYYY-MM-DD` followed by `### Added`, `### Changed`, `### Fixed`, `### Removed` as applicable.
   171	
   172	## Monitoring & Safety
   173	
   174	- Audit deps weekly (`safety check`, Dependabot).
   175	- Rate limit APIs; exponential backoff on 429s.
   176	
   177	### 3-Eyes — the local job supervisor (read this before touching scheduled jobs)
   178	
   179	**3-Eyes is the sentinel system for this machine's scheduled jobs.** It supersedes the earlier
   180	Cactus-Needle sentinel, which was disabled on 2026-07-27 (its four `com.neochro.*` launchd agents
   181	are parked in `~/Library/LaunchAgents/.disabled-cactus-sentinel-2026-07-27/`). Do not reintroduce a
   182	second supervisor — one machine, one sentinel.
   183	
   184	- **Code:** `utils/3-eyes/` · **Plan:** [PROJECT/2-WORKING/GH-195-UNIFIED-SENTINEL.md](PROJECT/2-WORKING/GH-195-UNIFIED-SENTINEL.md)
   185	- **Status / inventory:** `cd utils/3-eyes && PYTHONPATH=$PWD python3 -m three_eyes status`
   186	- **Skill:** `/3-eyes` for job health; `/launchd-triage` for raw launchd triage beneath it
   187	- **Inert by default.** A clone without a gitignored `config/runtime.env` is a clean no-op —
   188	  "3-Eyes says nothing" on a fresh machine means *not activated*, not *nothing wrong*.
   189	
   190	**Known gap (2026-07-27): the registry does not match reality.** `registry/jobs.d/` lists
   191	`collector-health` and `selfcheck`, but `3eyes.skill-sync` is loaded in launchd and firing every
   192	120 s without a registry entry. A supervisor that doesn't know about one of its own jobs is the
   193	condition 3-Eyes exists to prevent — reconcile before trusting its inventory.
   194	
   195	## Phase 0 Technical Spikes
   196	
   197	- When proposing phased work, include Phase 0 spike (1–2h max) to validate critical assumptions.
   198	- Phase 0 should test: API availability, DB connectivity, performance baseline, and blocking dependencies.
   199	- If Phase 0 surfaces blockers or contradicts assumptions, pause and escalate; do not proceed to Phase 1.
   200	- Document Phase 0 findings in spike report before committing to later phases.
   201	
   202	---
   203	
   204	## Known MCP tool gaps (as of 2026-06-02)
   205	
   206	Observed in a real session where the MCP surface was unavailable and CLI/SQLite fallbacks were used. Record here so future agents know what to work around or fix.
   207	
   208	| # | Gap | Impact | Owner action |
   209	|---|-----|--------|--------------|
   210	| 1 | **Runtime/docs sync** — AGENTS.md says "use MCP tools first" but the MCP server may not be callable at session start | Agent wastes time on MCP calls before falling back to CLI | Add a session-start connectivity check; verify tool list is live before instructing agents to prefer it |
   211	| 2 | **`semantic_query()` has no time filter** — no `since_days`, `updated_after`, or `updated_before` | Date-bounded investigations require raw SQL fallback | Add time filter to `semantic_query` MCP tool and underlying query in `src/rebalance/ingest/db/semantic.py` |
   212	| 3 | **`semantic_query()` weak filtering** — no `repo`, exact/keyword mode, or source metadata filter | Noisy recall for short/ambiguous terms | Add `repo`, `mode` (semantic/keyword), and `source` filter params |
   213	| 4 | **CLI `semantic-query` hides `updated_at`** — returned by query, stripped from output | Slows triage; requires raw SQL to see timestamps | Expose `updated_at` in the CLI table output |
   214	| 5 | ⚠️ **SECURITY: live API key surfaced in semantic results** — a vault note containing a live credential was indexed and returned by `semantic_query` | Key exposure via any agent that can call the tool | Add pre-embed redaction (strip key-shaped patterns) in `note_ingester.py` and/or a vault note exclusion mechanism (frontmatter `index: false` or path exclusion). **Fix before next vault ingest.** |
   215	
   216	---
   217	
   218	## Agent rulebooks (read before editing generated docs)
   219	
   220	Some generated artifacts in this repo ship with placeholder prose that any agent
   221	(Claude Code, Codex, Copilot, Gemini) is expected to fill in. Each has an
   222	authoritative rulebook that should be read first.
   223	
   224	| Artifact | Rulebook | Notes |
   225	|---|---|---|
   226	| Git Pulse Executive Recap (`reports/YYYY-MM-*.md`) | [experimental/git-pulse/EXEC-SUMMARY.md](experimental/git-pulse/EXEC-SUMMARY.md) | Claude Code skill `git-pulse-exec-recap` via `.claude/skills/` |
   227	| Git Pulse Team Recap (`team-reports/YYYY-MM-*.md`) | [experimental/git-pulse/TEAM-EXEC-SUMMARY.md](experimental/git-pulse/TEAM-EXEC-SUMMARY.md) | Claude Code skill `git-pulse-team-recap` via `.claude/skills/` |
   228	
   229	The generated recap itself carries the same pointer in its top-of-file instructions block, so agents that open the file directly will also find the rulebook without needing this index.     1	# Project-Driven Doc Automation (PDDA)
     2	
     3	PDDA is the document operating layer for this repo. Its job is to keep project plans, bug-fix docs,
     4	research notes, and roadmap pointers clean enough that an agent can pick up work with minimal drift
     5	and enough structure that routine hygiene can be automated instead of re-decided every session.
     6	
     7	The core idea is simple:
     8	
     9	- deterministic scripts enforce the parts that should never require judgment
    10	- an LLM reviewer flags structural or planning-quality gaps that are hard to express as regex alone
    11	- `ROADMAP.md` stays a pointer/index, while project detail lives in the individual project docs
    12	
    13	## Goals
    14	
    15	- Keep `PROJECT/2-WORKING` limited to docs that are truly active.
    16	- Ensure every active doc answers two questions at a glance: what was just completed, and what is next.
    17	- Make phased plans automation-ready by requiring explicit QA gates.
    18	- Prevent plan rot: stale files, missing next steps, hardcoded paths, and hidden scope drift.
    19	- Give agents one repeatable contract for project docs, bug-fix docs, and experimental plans.
    20	
    21	## Non-goals
    22	
    23	- PDDA does not replace the project docs themselves.
    24	- PDDA does not decide product strategy.
    25	- PDDA does not auto-rewrite nuanced plan content without review.
    26	- PDDA does not turn `ROADMAP.md` into a second execution plan.
    27	
    28	## Canonical document model
    29	
    30	PDDA assumes four lifecycle buckets:
    31	
    32	- `PROJECT/1-INBOX`: new ideas, rough proposals, untriaged notes
    33	- `PROJECT/2-WORKING`: active docs that should be updated as work progresses
    34	- `PROJECT/3-COMPLETED`: completed docs with an outcome
    35	- `PROJECT/4-MISC`: reference, stale, superseded, or abandoned docs
    36	
    37	Within that model:
    38	
    39	- `ROADMAP.md` is the index of current, completed, attempted, and deferred work
    40	- project detail lives in the individual `PROJECT/**` documents
    41	- a working doc is the canonical source of truth for that effort until it is completed, deferred, or superseded
    42	- `blank.md` placeholders are scaffolding and should be ignored by PDDA checks
    43	
    44	## Required contract for active docs
    45	
    46	Every doc in `PROJECT/2-WORKING` should have:
    47	
    48	1. YAML frontmatter with at least `title`, `status`, `created`, `updated`, `owner`, and `goal`
    49	2. a near-top status table with the exact columns:
    50	
    51	```md
    52	## Status
    53	
    54	| What was just completed | What's next |
    55	|---|---|
    56	| ... | ... |
    57	```
    58	
    59	3. clear phase or work sections if the doc is a plan. Specifically, any `PROJECT/2-WORKING` doc proposing a new tool, service, or query path must include a **Phase 0 - Prior Art Review** section explicitly explaining why existing layers (`semantic_query`, `three-eyes`, etc.) cannot be extended.
    60	4. a table of contents (`## Table of contents`) listing each phase, if the plan is multi-phase — so a
    61	   cold agent can see the full phase span and jump to the live one without scrolling the whole body
    62	5. QA gates or acceptance criteria after each phase if the plan is multi-phase
    63	6. for any discovery or spike phase, its findings written **back into this doc** before its QA gate can
    64	   pass (see [Discovery & spike phases (Memory Injection)](#discovery--spike-phases-memory-injection))
    65	7. repo-relative paths only; no hardcoded absolute local paths
    66	8. before moving to `PROJECT/3-COMPLETED`, a `## Lessons Learned (For Future Agents)` section appended to capture quirks and gotchas
    67	
    68	Recommended fields when relevant:
    69	
    70	- `related`
    71	- `context_tags` (e.g. `[auth, flaky-tests, build]`)
    72	- `reviewed`
    73	- `branch`
    74	- `non_goals`
    75	- `gh_issue`
    76	- `effort`, `complexity`, `risk`, `phases` — triage ratings; **required for medium-large work** (see
    77	  [Triage ratings for medium-large work](#triage-ratings-for-medium-large-work))
    78	
    79	## Quad Concepts (opt-in)
    80	
    81	An **opt-in** glance layer, **off by default**. The `## Status` table says *where* the work is; Quad
    82	Concepts says *what* it is — a 5-second read of the core problems a plan tackles and how, so an operator
    83	can see whether the real pain points are covered. (Distinct from `context_tags`: those are for search;
    84	this is for glance.)
    85	
    86	When enabled system-wide via the `.pdda-quad` lever (or the `PDDA_QUAD` env var — **orthogonal** to the
    87	enforcement mode), tracked plan docs must carry a `## Quad Concepts` section of **1–4 bullets**,
    88	conventionally right after `## Status`:
    89	
    90	```md
    91	## Quad Concepts
    92	- <pain the doc addresses> → <how it addresses it>
    93	```
    94	
    95	- **Shape (deterministic):** 1–4 **top-level, non-empty** `-`/`*` bullets in the first `## Quad Concepts`
    96	  section. `pain → fix` phrasing is the convention (nudged by the LLM readiness rubric), not a hard regex.
    97	- **Scope:** `PROJECT/2-WORKING`, `PROJECT/1-INBOX/GH-*.md`, and `PROJECT/3-COMPLETED` (the last keeps a
    98	  glanceable summary for cold-start recall). `PROJECT/4-MISC` is out.
    99	- **Enable:** set `.pdda-quad` to `on` (or `PDDA_QUAD=1`). The enforcement mode still governs whether a
   100	  missing/malformed section merely reports or blocks. **Opt a doc out** with `quad_exempt: true`.
   101	- Enforced by `pdda.sh quad-concepts` (deterministic, structure-only) plus a warn-only readiness rubric.
   102	- `pdda.sh glance` (read-only, always available) rolls up `title + Quad Concepts` across `2-WORKING` for
   103	  a one-screen view of what the active portfolio is addressing.
   104	
   105	## Triage ratings for medium-large work
   106	
   107	So automation can pick *which* task to pursue without re-reading every plan, every newly recorded
   108	**medium-large** task or project carries four triage fields in its frontmatter:
   109	
   110	| Field | Range | Meaning |
   111	|---|---|---|
   112	| `effort` | integer `1`–`5` | how much work — `1` low, `5` highest |
   113	| `complexity` | integer `1`–`5` | how intricate / how many moving parts — `1` low, `5` highest |
   114	| `risk` | integer `1`–`5` | blast radius + uncertainty — `1` safe/contained, `5` one-way-door or unknown |
   115	| `phases` | positive integer | total number of phases in the plan |
   116	
   117	```yaml
   118	effort: 2
   119	complexity: 3
   120	risk: 1
   121	phases: 4
   122	```
   123	
   124	`risk` should track the repo's existing reversibility scale (`Easy / Costly / One-way door`,
   125	`AGENTS.md` #3): `1`–`2` ≈ Easy, `3` ≈ Costly, `4`–`5` ≈ one-way door / high uncertainty. It is not a
   126	parallel notion of danger — it is that scale expressed as a number.
   127	
   128	**Scope.** Required for medium-large work (project plans, experiments, features, multi-phase efforts).
   129	Genuinely small/trivial docs (a typo, a path repoint, a ≤2–3 line bug-fix — the same floor as the
   130	issue-first SOP) do not need them. "Medium-large" is a judgment, so *presence* is enforced by the LLM
   131	layer, not a regex (below).
   132	
   133	### How to combine them — derive, don't store
   134	
   135	There is deliberately **no stored composite "score" field.** A frozen aggregate would (a) drift from
   136	the three numbers it came from, violating Principle #4 (*one canonical place per fact*), and (b) bake a
   137	weighting choice into every doc that you then cannot re-tune without rewriting them. Compute the
   138	selection signal **live, at selection time**, from the raw fields:
   139	
   140	- **`risk` is a gate, not an addend.** A trivial-but-risky task (`effort 1`, `complexity 1`, `risk 5`)
   141	  is easy to *do* but exactly what automation should not auto-pick — folding risk into a linear sum
   142	  lets it slip through mid-ranked. Gate on it instead.
   143	- **`effort` and `complexity` are correlated** (complex work is usually effortful), so summing them is
   144	  a rough "size" proxy, not two independent signals — treat the sum as one ease axis, not two.
   145	
   146	Reference selection rule (tune the thresholds per repo):
   147	
   148	```text
   149	eligible      = risk <= 2 AND not ratings_provisional   # safety gate; risk >= 4 => route to a human
   150	ease          = effort + complexity       # 2..10, lower = easier
   151	pick          = among eligible, lowest ease, then fewest phases as the tiebreak
   152	```
   153	
   154	`ratings_provisional: true` is an **eligibility gate, not just metadata.** Auto-drafted intake (e.g.
   155	the `/idea` skill) ships best-guess ratings marked provisional; a rough `risk: 2` guess on a large
   156	effort must **not** become auto-selectable on the strength of that guess. So a provisional doc is held
   157	out of auto-selection until a human confirms the ratings and clears the flag — the same "route to a
   158	human" posture as `risk >= 4`.
   159	
   160	This keeps the raw ratings canonical and queryable while letting the "what's the easiest *safe* thing
   161	to grab" logic live in one place that can evolve. (See the resolved `priority` note under
   162	[Proposed extensions](#proposed-extensions-not-yet-locked).)
   163	
   164	### How this is enforced
   165	
   166	- **deterministic (values)** — `pdda.sh frontmatter` validates the fields **only when present**:
   167	  `effort`/`complexity`/`risk` must be integers `1`–`5`, `phases` a positive integer. A present-but-bad
   168	  value is unambiguous, so it `error`s. The script does **not** force presence — it cannot know whether
   169	  a doc is "medium-large."
   170	- **LLM (presence)** — `pdda-doc-ready.sh` flags a medium-large plan that is *missing* the triage
   171	  ratings. Whether a doc is medium-large is a judgment, so it stays advisory/warn-capped like every
   172	  other readiness finding.
   173	
   174	## Why the two-column status header matters
   175	
   176	The status table is the front door for both humans and automation.
   177	
   178	- The left column is the last verified state change.
   179	- The right column is the next action.
   180	- If either is missing, an agent has to reconstruct state from the body, which is slow and error-prone.
     1	# rebalance OS — ARCHITECTURE.md
     2	
     3	> How data flows through the system. For execution decisions see [PROJECT.md](./PROJECT.md), for tool specs see [MCP.md](./MCP.md), for the *why* behind these decisions see [GUIDING-PRINCIPLES.md](./GUIDING-PRINCIPLES.md).
     4	
     5	> **New maintainer? Start with [Maintainer Orientation](#maintainer-orientation-start-here)** — the load-bearing symbols, the two hubs, where to start reading, and one end-to-end trace. **This doc is load-bearing, not decorative:** `audit_modules` (the `audit_modules` MCP tool / [scripts/audit_modules.py](scripts/audit_modules.py)) and the PDDA gate enforce that collectors, render modules, and scheduled jobs stay documented here — update ARCHITECTURE.md in the *same PR* as any structural change.
     6	
     7	---
     8	
     9	## Core Pipeline
    10	
    11	**INVARIANT**: **Compose, don't mutate**. No new query surfaces (like `semantic_query` vs `ask`) or UI renderers (web server vs static HTML) may be introduced without a plan to deprecate and replace the old one. If extending an existing pipeline, build reusable primitives in `src/rebalance/lib/` instead of duplicating logic in the caller.
    12	
    13	```
    14	Signals (data sources)
    15	  │
    16	  ▼
    17	Ingest Layer (source-specific collectors)
    18	  │
    19	  ▼
    20	SQLite + sqlite-vec (unified local store)
    21	  │
    22	  ▼
    23	Query Layer (context gathering + prompt assembly)
    24	  │
    25	  ▼
    26	Two-Layer LLM
    27	  ├── Layer 1: Local Qwen3 (fast first-pass synthesis)
    28	  └── Layer 2: Host Agent (review, adapt, present)
    29	  │
    30	  ▼
    31	User (via MCP host: VS Code, Claude Desktop, etc.)
    32	```
    33	
    34	Every raw incoming source follows the same pattern: **collect → normalize → store → query**. The collector registry in `index_ops.py` currently also includes derived local scans and post-ingest/export jobs (`code`, `semantic`, `sync`, `focus5`, `ask_self`), so not every registered scope is a raw upstream signal. The query layer and LLM layers are source-agnostic once data is in SQLite.
    35	
    36	### Sync model (in plain English)
    37	
    38	Every `refresh_index` run is **incremental** — nothing is re-downloaded from scratch. What "incremental" means depends on what the upstream API lets us ask for cheaply, but three patterns cover every source:
    39	
    40	1. **Hash/ID delta** — only fetch or reprocess what actually changed. Used by: vault notes, GitHub artifacts, embeddings.
    41	2. **Window refetch + upsert** — refetch a bounded time-or-count window every run and upsert by ID; nothing is auto-deleted. Used by: GitHub activity (last 30d events), calendar (30d back / 7d forward), email (newest 100 `in:inbox` messages).
    42	3. **Full refetch + column-diff** — refetch the whole upstream set, compare row-by-row, and keep everything as history. Used by: sleuth reminders.
    43	
    44	A few caps to know about up-front:
    45	
    46	- **Email** is capped at the **newest 100 inbox messages per run** today (Phase 1, shipped 2026-05-12) — default filter `in:inbox`, overridable via `gmail_query_filter` in `temp/rbos.config`. Not "important and starred." See [PROJECT/1-INBOX/EMAIL-INGEST.md](PROJECT/1-INBOX/EMAIL-INGEST.md).
    47	- **Calendar** refetches a **30-day back / 7-day forward window** by default; a 365-day backfill is available on demand via the CLI.
    48	- **GitHub activity** is bounded by the GitHub Events API's own ~30-day retention.
    49	- **Vault, sleuth, embeddings** are unbounded — they cover everything they can see.
    50	
    51	Detailed per-source mechanics live in [Storage Layer → Sync semantics per source](#sync-semantics-per-source).
    52	
    53	---
    54	
    55	## Maintainer Orientation (start here)
    56	
    57	New to the codebase? Read this section first — it is the mental model the rest of the doc assumes.
    58	
    59	### The two hubs (the model that prevents confusion)
    60	
    61	The system has **two** central things with *opposite* roles. Conflating them is the most common newcomer mistake:
    62	
    63	- **Orchestration spine — fan-OUT.** `refresh_index()` plus the `COLLECTORS` registry in
    64	  [src/rebalance/ingest/index_ops.py](src/rebalance/ingest/index_ops.py) reach **out** into every collector. This is the
    65	  one intended write/refresh entry point. New ingestion work registers here (`register_collector(Collector(...))`).
    66	- **Persistence base — fan-IN.** [src/rebalance/paths.py](src/rebalance/paths.py)::`resolve_database_path()` (answers *which* DB file)
    67	  → `db_connection()` in [src/rebalance/ingest/db/](src/rebalance/ingest/db/) (answers *how* to open it). Everything reaches **down** to these.
    68	
    69	They compose in a single hop (`refresh_index() → db_connection()`). Keeping orchestration and persistence in
    70	**separate** nodes is *why the codebase has no god-object* despite `db_connection()` being the single most-connected
    71	symbol: it is a thin, stateless connection factory (a dependency *sink*), not a place where logic lives. **Read from it
    72	freely; think twice before changing it** — its blast radius is the whole system.
    73	
    74	### Load-bearing symbols (you will see these in almost every file)
    75	
    76	| Symbol | Where | What it is / why it's everywhere |
    77	|---|---|---|
    78	| `db_connection()` | `ingest/db/connection.py` | SQLite factory (WAL, foreign keys, 30s busy-timeout, sqlite-vec). Every collector opens its connection here. **High fan-in, zero business logic.** |
    79	| `resolve_database_path()` | `paths.py` | "Which DB file" — layered resolver (`--database` flag → `REBALANCE_DB` → canonical app-data path → user config). Single source of truth for the DB location. |
    80	| `_read_config()` / `_write_config()` | `ingest/config.py` | Layered config + secrets (`temp/rbos.config` + keyring/secret-store). |
    81	| `CalendarConfig` | `ingest/calendar_config.py` | Validated calendar settings (event filters, signal weights). |
    82	| `normalize_github_repo_name()` | `ingest/github_scan.py` | Canonical `owner/repo` string used across every GitHub path. |
    83	| `refresh_index()` | `ingest/index_ops.py` | The orchestrated ingest entry point (see "two hubs" above). |
    84	| `rank_next_actions()` | `ingest/next_actions.py` | Entry point for the "what to do next" engine (see [Query Layer](#the-next-actions-engine-what-to-do-next)). |
    85	| `run_doctor()` | `doctor.py` | Health-check orchestrator; backs `rebalance doctor` (run it before claiming a change works). |
    86	
    87	### Where to start reading when touching X
    88	
    89	| If you're working on… | Start in | Then read |
    90	|---|---|---|
    91	| A data source (add/fix ingest) | `ingest/index_ops.py` (the `COLLECTORS` registry) + that source's `ingest/<source>.py` | [Adding a New Source](#adding-a-new-source) |
    92	| The read / query side | `ingest/semantic_index.py` (retrieval primitive) + `ingest/querier.py` (`ask()` orchestrator) | [Query Layer](#query-layer) |
    93	| Focus 5 roster / ranking | `ingest/focus5_scan.py` | the `web.py` `/focus-5` route |
    94	| Apple Reminders | `ingest/apple_reminders.py` (read) + `ingest/apple_reminders_write.py` (write, via signed helper) | — |
    95	| "What to do next" | `ingest/next_actions.py` | [The Next Actions engine](#the-next-actions-engine-what-to-do-next) |
    96	| Web dashboard surfaces | `web.py` + `web_components.py` | [Invocation Modes](#invocation-modes) |
    97	| Config / secrets | `ingest/config.py` + `paths.py` | [Credentials](#credentials) |
    98	| Scheduling / launchd jobs | [SCHEDULER.md](SCHEDULER.md) + `scripts/*_sync.sh` | [Invocation Modes](#invocation-modes) |
    99	| The database itself (schema/migrations) | `ingest/db/` (connection, schema, migrations) | [Storage Layer](#storage-layer) |
   100	
   101	### One request, end-to-end (worked trace)
   102	
   103	A `rebalance refresh` (or the `refresh_index` MCP tool) flows through real symbols like this:
   104	
   105	1. **`refresh_index()`** [`index_ops.py`] resolves the scope and iterates the `COLLECTORS` registry (each entry added via `register_collector(Collector(...))`).
   106	2. Each collector's **`sync_*()`** runs fetch → normalize → upsert — e.g. `sync_apple_reminders()`, `github_scan()`, `sync_sleuth_reminders()`.
   107	3. The collector opens storage via **`db_connection(path, ensure_<source>_schema)`** and upserts (e.g. `sync_apple_reminders()` → `upsert_apple_reminders()` → `db_connection()`).
   108	4. **Derived stages** follow (`code`, `semantic`, `sync`): the unified semantic index is rebuilt by `backfill_semantic_documents()` and embedded.
   109	5. **Read side:** `semantic_index.query()` (raw retrieval primitive; MCP `semantic_query`) and `querier.ask()` (broad synthesis orchestrator) read the *same* SQLite via `resolve_database_path()` → `db_connection()`.
   110	6. **Surfaces:** the `web.py` routes (`/focus-5`, `/auth-log`, what's-next), the Typer CLI, and the MCP tools all read through that one persistence base.
   111	
   112	---
   113	
   114	## Signal Sources
   115	
   116	Raw incoming sources have a priority, a collector module, and a target table. For detailed field specs and status, see [PROJECT.md — Signals](./PROJECT.md).
   117	
   118	| Priority | Source | Collector | Storage | Vectorized | Status |
   119	|----------|--------|-----------|---------|------------|--------|
   120	| P1 | GitHub | `github_scan.py` + `github_knowledge.py` + `github_readiness.py` + `github_reconciliation.py` | `github_activity`, `github_repo_meta`, `github_branches`, `github_items`, `github_comments`, `github_documents`, `github_embeddings` | Yes — structured repo signals plus semantic corpus for issues, PRs, comments, reviews, commit messages, and issue/PR reconciliation | Active |
   121	| P1 | Obsidian Vault | `note_ingester.py` + `embedder.py` | `vault_files`, `chunks`, `keywords`, `links`, `embeddings` | **Yes** — Qwen3-Embedding-0.6B, 1024-dim, sqlite-vec | Active |
   122	| P2 | Google Calendar | `calendar.py` | `calendar_events` table (default window 30d back / 7d forward; no auto-deletion) | No — structured event data | Active |
   123	| P3 | Sleuth reminders (Slack) | `sleuth_reminders.py` | `sleuth_reminders` table | No — structured reminder rows | Active |
   124	| P4 | Email (Gmail) | `gmail.py` + `semantic_index.py` | `email_messages` | Yes — subject + snippet participate in the unified semantic index | Active (Phase 1, shipped 2026-05-12): newest 100 `in:inbox` messages per run; metadata + snippet only, no body parsing yet |
   125	| P4 | Figma comments | `figma.py` + `semantic_index.py` | `figma_comments` | Yes — registry-provider semantic docs for comments | Active (opt-in): requires a PAT plus explicit `figma_file_keys` allow-list |
   126	
   127	### Other registered collector scopes
   128	
   129	These are registered in `index_ops.py` and dispatch through the same `refresh_index()` orchestrator, but they are not raw upstream data sources:
   130	
   131	| Scope | Kind | Purpose | Included in `all` |
   132	|---|---|---|---|
   133	| `code` | derived local scan | AST/code chunk collection into the unified semantic index | Yes |
   134	| `semantic` | projection stage | Unified semantic backfill + embed maintenance | Yes |
   135	| `sync` | export stage | Export calendar/email snapshots to the pulse sync repo | Yes |
   136	| `focus5` | derived local scan | Build the device-local Focus 5 roster + signal cache | No |
   137	| `ask_self` | derived local scan | Inventory ask_self indexes on this device | No |
   138	
   139	### Source → Table fanout
   140	
     1	# ROUTER.md
     2	
     3	This file is the first entry point for an AI agent working in this repo: it tells you what to read, what to run, and which files are canonical. **This repo is an MCP server** — reach for the MCP tools before scanning code or writing ad-hoc shell pipelines.
     4	
     5	## Role split
     6	
     7	- `ROUTER.md` = startup order and canonical entry points (this file)
     8	- `AGENTS.md` = behavioral rules, the MCP tool surface, the onboarding flow, and decision quality
     9	- `ARCHITECTURE.md` = system orientation (Signal Sources, Source→Table fanout, "Adding a New Source") — read at session start
    10	- `GUIDING-PRINCIPLES.md` = the *why* behind architecture and design decisions; includes the AI doc-review heuristics appendix
    11	- `README.md` = human-facing repo/product overview and install path
    12	- `CLAUDE.md` = the Claude Code entry stub; it defers to `AGENTS.md` for all behavioral rules
    13	- `ROADMAP.md` = pointer ledger of in-progress, completed, attempted, and deferred work
    14	- `CHANGELOG.md` = the end-of-iteration running log
    15	- `RELEASES.md` = forward-looking release-planning ledger (governed by `PROJECT/PDDA.md`)
    16	- `PROJECT/**` docs = canonical execution detail for a specific effort
    17	- `PROJECT/PDDA.md` = document contract and PDDA automation rules
    18	
    19	## Startup sequence
    20	
    21	1. Read `ROUTER.md` to understand the repo's operating order and canonical files. -> expect one clear next file, not a repo-wide scavenger hunt.
    22	2. Read `AGENTS.md` before making recommendations or edits. -> expect the MCP tool surface, the onboarding flow, explicit assumptions, and verified-claims-only discipline.
    23	3. Read `ARCHITECTURE.md` for orientation, then `src/rebalance/ingest/index_ops.py` — the `COLLECTORS` registry is the data-plane spine. -> expect to extend a source with one `register_collector(...)` call, not edits to the dispatch chain.
    24	4. Read `ROADMAP.md` to find the active effort. -> expect links outward to the canonical `PROJECT/**` docs; `ROADMAP.md` is a pointer ledger, not a plan body.
    25	5. Read the linked `PROJECT/**` document that owns the work you are touching. -> expect a near-top `## Status` table telling you what was just completed and what is next.
    26	6. If the task touches project docs, read `PROJECT/PDDA.md` and follow the PDDA contract. -> expect `PROJECT/2-WORKING` docs to have frontmatter, the exact status table, and QA gates when phased.
    27	7. Before reporting success on code or runtime work, run `rebalance doctor` and `pytest tests/`. -> expect doctor clean and the suite green; do not claim completion if either fails or was skipped.
    28	8. Before reporting success on doc-hygiene or roadmap work, run `utils/pdda/pdda.sh run` (or the relevant `utils/pdda/pdda.sh <check>` command). -> expect deterministic findings first, then any LLM review.
    29	
    30	## Canonical rules
    31	
    32	- This repo **is** an MCP server. Use the MCP tools (`index_status`, `refresh_index`, `semantic_query`, …) for data refresh and retrieval, and `rebalance doctor` for setup/health. Do not write ad-hoc `rebalance ...` shell pipelines or grep for setup scripts.
    33	- Do not put phase checklists, build steps, or deep execution notes in `ROADMAP.md`.
    34	- Every active doc in `PROJECT/2-WORKING/` must be reflected by a one-line pointer in `ROADMAP.md` — or opt out with `roadmap_exempt: true` in its frontmatter. Enforced by `utils/pdda/pdda.sh roadmap-coverage`; governance lives in `PROJECT/PDDA.md`.
    35	- Every captured GitHub issue doc in `PROJECT/1-INBOX/GH-*.md` is first-class intake and must also be parked in `ROADMAP.md` as a one-line queue entry immediately at capture, then promoted or removed later. Enforced by `utils/pdda/pdda.sh roadmap-coverage`; governance lives in `PROJECT/PDDA.md`.
    36	- Do not create a second competing plan when a canonical `PROJECT/**` doc already exists.
    37	- Do not build a redundant solution when extending an existing one is viable (enforced by PDDA Phase 0 review). If >50% of the new solution overlaps with an existing one, the plan MUST include deprecating/deleting the old one.
    38	- Do not override deterministic PDDA findings with prose.
    39	- Do not report a win you did not verify with `rebalance doctor`, `pytest tests/`, or the relevant PDDA check.
    40	
    41	## Command rails
    42	
    43	For setup/health:
    44	
    45	```bash
    46	rebalance doctor
    47	```
    48	
    49	For code correctness:
    50	
    51	```bash
    52	pytest tests/
    53	```
    54	
    55	For document hygiene:
    56	
    57	```bash
    58	utils/pdda/pdda.sh run
    59	```
    60	
    61	For local job health (3-Eyes — optional, inert unless activated on the device):
    62	
    63	```bash
    64	cd utils/3-eyes && PYTHONPATH=$PWD python3 -m three_eyes status   # is it active, what is managed
    65	PYTHONPATH=$PWD python3 -m three_eyes health                      # fleet health (run UNSANDBOXED — see below)
    66	PYTHONPATH=$PWD python3 -m three_eyes catalog --check             # catalog drift vs the live machine
    67	PYTHONPATH=$PWD python3 -m three_eyes why <job>                   # why a job did/didn't run
    68	```
    69	
    70	`health` and `catalog` shell out to `launchctl list`; a sandboxed shell blocks it and every job
    71	reads back `not-loaded`. Re-run unsandboxed before believing a health result.
    72	
    73	For targeted PDDA debugging:
    74	
    75	```bash
    76	utils/pdda/pdda.sh frontmatter
    77	utils/pdda/pdda.sh status-table
    78	utils/pdda/pdda.sh hardcoded-paths
    79	utils/pdda/pdda.sh roadmap
    80	utils/pdda/pdda.sh roadmap-coverage
    81	utils/pdda/pdda.sh changelog
    82	utils/pdda/pdda.sh stale
    83	utils/pdda/pdda.sh quad-concepts     # opt-in: a "## Quad Concepts" section of 1-4 bullets (lever: .pdda-quad / PDDA_QUAD)
    84	utils/pdda/pdda.sh glance            # read-only roll-up: title + Quad Concepts for each PROJECT/2-WORKING doc
    85	utils/pdda/pdda.sh issue-doc-sync    # flag 2-WORKING/GH-*.md docs drifted from their GitHub issue state (warn-only)
    86	utils/pdda/pdda.sh gh-refresh        # refresh the cached GitHub issue-state file issue-doc-sync reads offline (needs gh)
    87	utils/pdda/pdda.sh releases    # validate RELEASES.md, the release-planning ledger (warn-only nudge)
    88	utils/pdda/pdda.sh releases-current  # read-only roll-up: RELEASES.md entries whose Status isn't "Shipped"
    89	utils/pdda/pdda.sh governance  # governance-doc cross-reference + doc/code drift (this file, AGENTS.md, CLAUDE.md, ...)
    90	utils/pdda/pdda.sh banned-imports # AST-level import linter flagging banned modules outside rebalance.lib
    91	utils/pdda/pdda.sh doc-ready   # LLM readiness review — set PDDA_LLM_BIN (codex/claude/agy) for recommendations, else it self-skips
    92	utils/pdda/pdda.sh catchup     # LLM repo triage and ROUTER.md recommendations — opt-in like doc-ready
    93	utils/pdda/pdda.sh help
    94	```
    95	
    96	## Routing hints
    97	
    98	- If the task is about current priorities or active work, start in `ROADMAP.md`, then follow the linked `PROJECT/**` doc.
    99	- If the task is about data sources, refresh, or "why is X empty?", start with `rebalance doctor`, then `src/rebalance/ingest/index_ops.py` (the `COLLECTORS` registry).
   100	- If the task is about retrieval or synthesis (the read side), start in `src/rebalance/querier.py`.
   101	- If the task is about the MCP tool surface or operator onboarding, start in `AGENTS.md`.
   102	- If the task is about document quality, active-doc lifecycle, roadmap sprawl, or automation policy, start in `PROJECT/PDDA.md`.
   103	- If the task is about installing PDDA into another repo, read `PDDA-INSTALL.md`.
   104	- If the task originates from a GitHub issue, capture it as `PROJECT/1-INBOX/GH-<number>-SHORT-DESCRIPTION.md`, then follow the normal `1-INBOX` → `2-WORKING` flow.
   105	- If the task is about job health, what is scheduled on this device, or adopting an automation under supervision, use the `/3-eyes` skill (`utils/3-eyes/`, `python -m three_eyes health|catalog|list`). For raw launchd triage below that layer, use `/launchd-triage`. 3-Eyes is **inert by default** — a clone with no gitignored `config/runtime.env` is a clean no-op, so "3-Eyes says nothing" on a fresh machine means *not activated*, not *nothing wrong*.

exec
/bin/zsh -lc "rg -n -C 3 'datetime|subprocess|json|import' AGENTS.md PROJECT/PDDA.md ARCHITECTURE.md ROUTER.md | sed -n '1,420p'; rg -n -C 5 'banned-imports|check_banned_imports|duplicate-code' utils/pdda/pdda.sh PROJECT/PDDA.md; rg -n -C 3 'replace\\('\"'\"'Z'\"'\"'|total_seconds\\(\\) / 60|raw-ok' .github/workflows/ci.yml src/rebalance/ingest/calendar_helpers.py" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
 succeeded in 0ms:
ROUTER.md-87-utils/pdda/pdda.sh releases    # validate RELEASES.md, the release-planning ledger (warn-only nudge)
ROUTER.md-88-utils/pdda/pdda.sh releases-current  # read-only roll-up: RELEASES.md entries whose Status isn't "Shipped"
ROUTER.md-89-utils/pdda/pdda.sh governance  # governance-doc cross-reference + doc/code drift (this file, AGENTS.md, CLAUDE.md, ...)
ROUTER.md:90:utils/pdda/pdda.sh banned-imports # AST-level import linter flagging banned modules outside rebalance.lib
ROUTER.md-91-utils/pdda/pdda.sh doc-ready   # LLM readiness review — set PDDA_LLM_BIN (codex/claude/agy) for recommendations, else it self-skips
ROUTER.md-92-utils/pdda/pdda.sh catchup     # LLM repo triage and ROUTER.md recommendations — opt-in like doc-ready
ROUTER.md-93-utils/pdda/pdda.sh help
--
ARCHITECTURE.md-43-
ARCHITECTURE.md-44-A few caps to know about up-front:
ARCHITECTURE.md-45-
ARCHITECTURE.md:46:- **Email** is capped at the **newest 100 inbox messages per run** today (Phase 1, shipped 2026-05-12) — default filter `in:inbox`, overridable via `gmail_query_filter` in `temp/rbos.config`. Not "important and starred." See [PROJECT/1-INBOX/EMAIL-INGEST.md](PROJECT/1-INBOX/EMAIL-INGEST.md).
ARCHITECTURE.md-47-- **Calendar** refetches a **30-day back / 7-day forward window** by default; a 365-day backfill is available on demand via the CLI.
ARCHITECTURE.md-48-- **GitHub activity** is bounded by the GitHub Events API's own ~30-day retention.
ARCHITECTURE.md-49-- **Vault, sleuth, embeddings** are unbounded — they cover everything they can see.
--
ARCHITECTURE.md-215-
ARCHITECTURE.md-216-> **Sleuth production is read from a published file — no inbound access.** The
ARCHITECTURE.md-217-> Sleuth box pushes its reminders to a private git repo
ARCHITECTURE.md:218:> (`rebalance-git-pulse:sync/sleuth/reminders-<ws>.json`); rebalance-OS reads the
ARCHITECTURE.md-219-> local clone (`base_url` is a `file://`/local path). No SSH tunnel, no open port.
ARCHITECTURE.md-220-> See [SLEUTH_SYNC.md](SLEUTH_SYNC.md). (Dev still hits the API directly.)
ARCHITECTURE.md-221-
--
ARCHITECTURE.md-230-| Figma | OS keyring + secret store for the PAT; `temp/rbos.config` holds only the (non-secret) file-key allow-list | Personal access token + explicit file selection |
ARCHITECTURE.md-231-| Obsidian vault | none | filesystem read only |
ARCHITECTURE.md-232-
ARCHITECTURE.md:233:Env-file paths resolve via [src/rebalance/paths.py](src/rebalance/paths.py)::`resolve_secret_path(name)` — the layered chain is `REBALANCE_SECRETS_DIR` env var → `secrets_dir` field in `~/.config/rebalance-os/config.json` (set via `rebalance config set-secrets-dir`) → `~/secrets/` legacy default. The domain CLI loaders (for example, [src/rebalance/cli/calendar.py](src/rebalance/cli/calendar.py) and [src/rebalance/cli/sleuth.py](src/rebalance/cli/sleuth.py)) use this resolver, so the repo is portable across operator home directories without hardcoded env-file paths. Env files should sit at mode 600. Env files are parsed manually (no `python-dotenv`). Nothing with a secret value is committed.
ARCHITECTURE.md-234-
ARCHITECTURE.md-235-### Adding a New Source
ARCHITECTURE.md-236-
--
ARCHITECTURE.md-261-
ARCHITECTURE.md-262-### Write discipline (one writer per table)
ARCHITECTURE.md-263-
ARCHITECTURE.md:264:The single most important invariant for a new maintainer to preserve:
ARCHITECTURE.md-265-
ARCHITECTURE.md-266-- **Reads are unrestricted.** Anything may open `db_connection()` and `SELECT`. The "Tables by Domain" list below names the *writer* for each table — that ownership is about **writes**, not reads.
ARCHITECTURE.md-267-- **One writer per table.** Each table is written by exactly one module (e.g. `github_activity` ← `github_scan.py`, `sleuth_reminders` ← `sleuth_reminders.py`, `semantic_documents` ← the `semantic` stage only). Do not add a second writer; extend the owning collector instead.
--
ARCHITECTURE.md-474-
ARCHITECTURE.md-475-Four ways the pipeline runs:
ARCHITECTURE.md-476-
ARCHITECTURE.md:477:1. **Interactive CLI** — `rebalance <subcommand>` via the Typer package under `src/rebalance/cli/`. Ad-hoc and one-shot workflows (`calendar-create-event`, `github-release-readiness`, `sleuth-sync --json`, `profile-sync`, `raw`, etc.). `rebalance` invoked with no arguments launches the live dashboard (mode 4). `rebalance raw [--minutes N] [--watch S] [--json]` is a calibration probe: 1 GitHub API request per invocation, classifies recent events as captured / pending / unwatched against the local pipeline state, used to verify that commits/PRs/issues are making it into rebalanceOS.
ARCHITECTURE.md-478-
ARCHITECTURE.md-479-2. **Unattended scheduled syncs** — a launchd fleet of ten jobs. [SCHEDULER.md](SCHEDULER.md) is the policy table (single source of truth for labels, cadences, scopes, prerequisites, and outputs; enforced by `tests/test_scheduler_policy.py`). The six data/render jobs, conceptually:
ARCHITECTURE.md-480-
--
ARCHITECTURE.md-483-   - **Hourly pulse publish** ([scripts/pulse_sync.sh](scripts/pulse_sync.sh) / [scripts/com.rebalance-os.pulse-sync.plist.template](scripts/com.rebalance-os.pulse-sync.plist.template)) on the hour, 06:00 to 23:00. Renders the operator pulse markdown and pushes it to the configured private repo, but only when the rendered content actually changed since the previous run.
ARCHITECTURE.md-484-   - **30-minute pulse-web refresh** ([scripts/pulse_web_sync.sh](scripts/pulse_web_sync.sh) / [scripts/com.rebalance-os.pulse-web-sync.plist.template](scripts/com.rebalance-os.pulse-web-sync.plist.template)) every 30 minutes from 06:00 to 23:30. Calls [scripts/pulse_web.py](scripts/pulse_web.py) to regenerate the local `web/pulse.html` mirror of the dashboard. Atomic via tmp+replace (a crashed run leaves the previous HTML intact). No network, no git push — separate from the markdown→private-repo flow above.
ARCHITECTURE.md-485-   - **Hourly GitHub sync** ([scripts/github_sync.sh](scripts/github_sync.sh) / [scripts/com.rebalance-os.github-sync.plist.template](scripts/com.rebalance-os.github-sync.plist.template)) — a narrower github-only refresh independent of the daily full sync, for environments that want fresher GitHub data without paying the full multi-source cost.
ARCHITECTURE.md:486:   - **Pulse server (long-running, not scheduled)** ([scripts/pulse_server.sh](scripts/pulse_server.sh) / [scripts/com.rebalance-os.pulse-server.plist.template](scripts/com.rebalance-os.pulse-server.plist.template)) — a FastAPI/uvicorn server on `127.0.0.1:8767` with `RunAtLoad` + `KeepAlive` (autostart at login, restart on crash, `ThrottleInterval=30s`). Adds an interactive layer (real Refresh button + filter) on top of the static `web/pulse.html` the pulse-web job regenerates, **and is the always-on JSON backend for the macOS Focus 5 Float app** ([macOS/Apps/Focus5Float](macOS/Apps/Focus5Float)) — it serves `/focus-5.json` (roster), `/focus-5/goals`, and `/focus-5/note` so the app works without a separate `rebalance serve` on `:8787`. Loopback bind is enforced in [scripts/pulse_server.py](scripts/pulse_server.py). Unlike the five scheduled jobs above, it runs continuously rather than firing on a calendar interval.
ARCHITECTURE.md-487-
ARCHITECTURE.md:488:     **Drift gotcha (has bitten the Focus 5 app twice):** [scripts/pulse_server.py](scripts/pulse_server.py) does *not* mount `rebalance.web`'s app — it hand-re-declares a chosen *subset* of its routes by importing the renderers. Two consequences: (1) a route added to `web.py` is invisible on `:8767` until a matching wrapper is added to `pulse_server.py` (this is how `/focus-5.json` was missed); (2) because it's a `KeepAlive` daemon, any route change requires `launchctl kickstart -k gui/$UID/com.rebalance-os.pulse-server` to take effect — a long-running process keeps serving its old route table otherwise (this is how a freshly-added `/focus-5/goals` still 404'd).
ARCHITECTURE.md-489-
ARCHITECTURE.md-490-   The remaining five jobs (health-check hourly, health-check-triage 3×/day, pulse-warning-watch every 15 min, obsidian-rollover at midnight, obsidian-daily-sync at 18:00) are operational/maintenance agents — see [SCHEDULER.md](SCHEDULER.md). The **obsidian-daily-sync** job ([utils/obsidian_daily_sync.sh](utils/obsidian_daily_sync.sh) / [scripts/com.rebalance-os.obsidian-daily-sync.plist.template](scripts/com.rebalance-os.obsidian-daily-sync.plist.template)) synthesizes a Gemini daily-activity summary from the structured `collect_pulse_snapshot()` output and lands it in an idempotent sentinel-bracketed block at the bottom of the vault's `0. Today's Notes.md`. Similarly, the **git-pulse-daily-synthesis** script ([utils/git_pulse_daily_synthesis.py](utils/git_pulse_daily_synthesis.py)) acts as a manual projection/export stage, aggregating multi-device git commit logs and synthesizing them into a separate block in the vault. Both scripts use Gemini-or-skip logic (no Qwen fallback) and feature late-run guards to prevent colliding with the 00:00 rollover.
ARCHITECTURE.md-491-
ARCHITECTURE.md:492:   Wrapper scripts source [scripts/lib/scheduler_common.sh](scripts/lib/scheduler_common.sh) for env bootstrap (repo root, venv python, `PYTHONPATH`), per-day logs under `temp/logs/`, job-lifecycle events into `auth_activity.jsonl`, and log retention. Installers source [scripts/lib/install_common.sh](scripts/lib/install_common.sh) for one normalized flow: always-unload, render the `.plist.template` (`{{REBALANCE_DIR}}`, `{{PYTHON}}`, `{{HOME}}`), `plutil -lint`, load, poll-verify registration. The rendered plists in `~/Library/LaunchAgents/` are gitignored — the templates are the only checked-in form, so a clone on any machine installs cleanly with no per-user editing.
ARCHITECTURE.md-493-
ARCHITECTURE.md-494-3. **MCP tool handlers** — [src/rebalance/mcp/server.py](src/rebalance/mcp/server.py) registers the tools; [src/rebalance/mcp_server.py](src/rebalance/mcp_server.py) remains as the backward-compatibility shim for older launch commands. Host agents (Claude Code / Claude Desktop) call these on demand. `REBALANCE_DB` env var resolves the shared DB path.
ARCHITECTURE.md-495-
--
ARCHITECTURE.md-613-    audit.py               — structured audit logging (append_audit_entry)
ARCHITECTURE.md-614-    querier.py             — multi-source context gathering + local LLM synthesis
ARCHITECTURE.md-615-
ARCHITECTURE.md:616:scripts/                   — Operator entry points (not part of the importable package)
ARCHITECTURE.md-617-  dashboard.py             — Rich Live terminal dashboard (mode 4 above)
ARCHITECTURE.md-618-  pulse_web.py             — render module: regenerates web/pulse.html (the local
ARCHITECTURE.md-619-                              browser mirror of the dashboard) from the same SQLite
--
AGENTS.md-12-> - **Orientation** → [ARCHITECTURE.md](ARCHITECTURE.md) (Signal Sources table, Source→Table fanout, "Adding a New Source"). Read it at session start.
AGENTS.md-13-> - **`querier.py`** is the read-side orchestrator (retrieval + synthesis); `index_ops.py` is the source/refresh orchestrator. Both consume the same source set — the direction to make `doctor`, the morning brief, and `querier` all iterate the one registry is in [PROJECT/2-WORKING/P1-MODULE-REGISTRY.md](PROJECT/2-WORKING/P1-MODULE-REGISTRY.md).
AGENTS.md-14-
AGENTS.md:15:**Connection.** The repo ships two equivalent configs: [.vscode/mcp.json](.vscode/mcp.json) for VS Code agents and [.mcp.json](.mcp.json) at the repo root for tools that look there. Both launch `.venv/bin/python -m rebalance.mcp_server` over stdio with `REBALANCE_DB` set to the repo's `rebalance.db`.
AGENTS.md-16-
AGENTS.md-17-**Single entry points (use these first):**
AGENTS.md-18-
--
AGENTS.md-60-**Key paths:**
AGENTS.md-61-- Registry: `{vault_path}/Projects/00-project-registry.md`
AGENTS.md-62-- Config: `temp/rbos.config` (gitignored, repo root)
AGENTS.md:63:- Database: resolved from `REBALANCE_DB` env var (set in `.vscode/mcp.json`)
AGENTS.md-64-- Architecture docs: `ARCHITECTURE.md`, `MCP.md`, `PROJECT/PDDA.md`
AGENTS.md-65-
AGENTS.md-66-**Background refresh.** A launchd job (`com.rebalance-os.daily-sync`) runs [scripts/daily_sync.sh](scripts/daily_sync.sh) at 6:30 AM daily and on boot. The script invokes the same `refresh_index(scope=["all"])` orchestration, so the cron and the MCP tool share one code path. If the index looks stale, check `temp/logs/daily_sync_YYYY-MM-DD.log` before manually re-running.
--
AGENTS.md-96-> For the *why* behind these rules, see [GUIDING-PRINCIPLES.md](./GUIDING-PRINCIPLES.md).
AGENTS.md-97-
AGENTS.md-98-- Code: DRY, SOLID; balance maintainability, performance, secure. Comply with framework security best practices.
AGENTS.md:99:- **Pre-flight Search Rule**: Before writing any new utility function or system layer, you MUST use `grep_search` or MCP `search_graph` to check if a similar function exists (e.g., date parsing, JSON handling). If it exists, import it. Do not duplicate it.
AGENTS.md:100:- **Centralization Rule**: All standard data formatting and OS-level operations (like datetime parsing, json dumping, git calls) must use `src/rebalance/lib/*` modules instead of creating local helper methods in the collector.
AGENTS.md-101-- **State Management**: Introduce FSM (Finite State Machine) if state transitions exceed 4 distinct states or more than one conditional branch per state. Document the state diagram in code comments, or in the owning `PROJECT/**` doc.
AGENTS.md-102-- **Contracts**: Designate single writer per contract/schema (API response shape, DB record structure, queue message format). Changes require review from contract owner; broadcast breaking changes immediately.
AGENTS.md-103-- **Pipelines**: One logical pipeline per data flow whenever possible. Avoid forking/rejoining; use filters, transforms, and side effects in sequence. If pipeline needs multiple paths, use conditional routing within single pipeline, not separate pipelines.
--
AGENTS.md-108-  - **Use the shared resolvers** for any new runtime path (DB, secrets, auth/token, operator config). No `Path.home()` token paths, no `parents[N]` repo-root walks, no sibling-checkout assumptions.
AGENTS.md-109-  - **Obsidian/vault is optional output, not a control-plane dependency** — a refresh must succeed with no vault present.
AGENTS.md-110-  - **Name settings by what they are**, not the first feature that used them (e.g. `ask_self_scan_roots` → `repo_scan_roots`).
AGENTS.md:111:  - These are the **target contract**: the route-through-orchestrator and stage-owned-semantic rules bind *new* code; the audit owns migrating existing call sites. Enforce mechanically, not by prose — drift slipped past these same principles once already. Ship the contract tests (single-writer on the semantic tables, `all`-expansion, "no user-facing surface imports a leaf ingest fn") so a violation fails CI instead of accreting.
AGENTS.md-112-  - **Current scope taxonomy (Phase 1, 2026-06-10)** — canonical home until `ARCHITECTURE.md` is re-segmented (it's regenerated by ask-self ingest, so not durable yet):
AGENTS.md-113-    - **raw sources** (the `all` token): `vault`, `github`, `calendar`, `sleuth`, `email`. `figma` is a raw source but **opt-in** (needs PAT + file-key allowlist).
AGENTS.md-114-    - **derived scans:** `code`, `focus5`, `ask_self`.  **projection:** `semantic`.  **export:** `sync`.
--
AGENTS.md-134-
AGENTS.md-135-## Destructive Operations
AGENTS.md-136-
AGENTS.md:137:- Log all DELETE/DROP/TRUNCATE operations with timestamp, user, and target to `/logs/agent-audit.json`.
AGENTS.md-138-- Require explicit confirmation flag (e.g., `--confirm` or env var `CONFIRM_DESTRUCTIVE=true`) before executing.
AGENTS.md-139-- Support `--dry-run` mode when applicable; output what _would_ be deleted without executing.
AGENTS.md-140-- If operation affects >1000 rows/records, require additional confirmation or escalation.
--
PROJECT/PDDA.md-711-  GitHub milestone *title*, so a release's scope can be queried rather than hand-maintained here:
PROJECT/PDDA.md-712-
PROJECT/PDDA.md-713-  ```bash
PROJECT/PDDA.md:714:  gh issue list --milestone "Quicksilver" --state open --json number,title,labels
PROJECT/PDDA.md-715-  ```
PROJECT/PDDA.md-716-
PROJECT/PDDA.md-717-  That query *is* release-driven work selection, with no second cache and no issue list copied into
--
PROJECT/PDDA.md-815-  cached gh-state file). See [Suggested Stop doc-health scan](#suggested-stop-doc-health-scan).
PROJECT/PDDA.md-816-
PROJECT/PDDA.md-817-`PDDA_ONLY_FILE=<path>` is the seam that scopes any check to a single file (unset = full scan, the
PROJECT/PDDA.md:818:default everywhere else). Wiring is repo-local in `.claude/settings.json`; installs receive the hook
PROJECT/PDDA.md-819-scripts via the manifest and opt in by adding the hook entries.
PROJECT/PDDA.md-820-
PROJECT/PDDA.md-821-#### Suggested Stop doc-health scan
--
PROJECT/PDDA.md-830-  finding lines (an `all clear` line when there are none);
PROJECT/PDDA.md-831-- it **always exits `0`** (proven by `test/pdda-doc-health-hooks.sh`), so it can never block a stop.
PROJECT/PDDA.md-832-
PROJECT/PDDA.md:833:Wire it as a `Stop` hook in `.claude/settings.json` (no matcher). Because it reads the cache rather
PROJECT/PDDA.md-834-than calling `gh`, keep `pdda.sh gh-refresh` on the hourly cadence so the Stop report stays current.
PROJECT/PDDA.md-835-
PROJECT/PDDA.md-836-## Enforcement modes
--
PROJECT/PDDA.md-960-
PROJECT/PDDA.md-961-PDDA should write an append-only activity log to:
PROJECT/PDDA.md-962-
PROJECT/PDDA.md:963:- `PROJECT/PDDA-ACTIVITY.jsonl`
PROJECT/PDDA.md-964-
PROJECT/PDDA.md-965-Each script run should append:
PROJECT/PDDA.md-966-
--
PROJECT/PDDA.md-1067-
PROJECT/PDDA.md-1068-These need a decision before the automation should be considered stable:
PROJECT/PDDA.md-1069-
PROJECT/PDDA.md:1070:1. Should `PROJECT/PDDA-ACTIVITY.jsonl` remain append-only forever, or rotate by month once the volume grows?
PROJECT/PDDA.md-1071-2. Should `ROADMAP.md` remain root-level canonical only, or do you also want a project-local roadmap index under `PROJECT/`?
PROJECT/PDDA.md-1072-
PROJECT/PDDA.md-1073-Resolved:
--
PROJECT/PDDA.md-1092-- run deterministic checks hourly
PROJECT/PDDA.md-1093-- let the LLM reviewer flag readiness issues
PROJECT/PDDA.md-1094-- keep `ROADMAP.md` pointer-only (deterministic `pdda.sh roadmap` + the LLM rubric guard it)
PROJECT/PDDA.md:1095:- append all script activity to `PROJECT/PDDA-ACTIVITY.jsonl`
utils/pdda/pdda.sh-1008-      ;;
utils/pdda/pdda.sh-1009-  esac
utils/pdda/pdda.sh-1010-  printf '%s\n' "$candidate"
utils/pdda/pdda.sh-1011-}
utils/pdda/pdda.sh-1012-
utils/pdda/pdda.sh:1013:check_banned_imports() {
utils/pdda/pdda.sh-1014-  pdda_reset_counts
utils/pdda/pdda.sh:1015:  local CHECK_NAME="pdda-check-banned-imports" rc=0
utils/pdda/pdda.sh:1016:  local script_path="$PDDA_REPO_ROOT/utils/pdda/check_banned_imports.py"
utils/pdda/pdda.sh-1017-  
utils/pdda/pdda.sh-1018-  if [ ! -f "$script_path" ]; then
utils/pdda/pdda.sh-1019-    return 0
utils/pdda/pdda.sh-1020-  fi
utils/pdda/pdda.sh-1021-
--
utils/pdda/pdda.sh-1266-pdda-check-changelog:check_changelog
utils/pdda/pdda.sh-1267-pdda-stale-working-docs:check_stale
utils/pdda/pdda.sh-1268-pdda-check-issue-doc-sync:check_issue_doc_sync
utils/pdda/pdda.sh-1269-pdda-check-releases:check_releases
utils/pdda/pdda.sh-1270-pdda-check-governance:check_governance
utils/pdda/pdda.sh:1271:pdda-check-banned-imports:check_banned_imports
utils/pdda/pdda.sh-1272-"
utils/pdda/pdda.sh-1273-
utils/pdda/pdda.sh-1274-cmd_run() {
utils/pdda/pdda.sh-1275-  local EXIT_CODE=0 FAILED="" entry label fn MODE_NOTE
utils/pdda/pdda.sh-1276-
--
utils/pdda/pdda.sh-1433-  stale)            check_stale; exit "$?" ;;
utils/pdda/pdda.sh-1434-  issue-doc-sync)   check_issue_doc_sync; exit "$?" ;;
utils/pdda/pdda.sh-1435-  releases)         check_releases; exit "$?" ;;
utils/pdda/pdda.sh-1436-  releases-current) cmd_releases_current; exit "$?" ;;
utils/pdda/pdda.sh-1437-  governance)       check_governance; exit "$?" ;;
utils/pdda/pdda.sh:1438:  banned-imports)   check_banned_imports; exit "$?" ;;
utils/pdda/pdda.sh-1439-  gh-refresh)       exec "$HERE/pdda-gh-refresh.sh" "$@" ;;
utils/pdda/pdda.sh-1440-  doc-ready)        exec "$HERE/pdda-doc-ready.sh" "$@" ;;
utils/pdda/pdda.sh-1441-  catchup)          exec "$HERE/pdda-catchup.sh" "$@" ;;
utils/pdda/pdda.sh-1442-  help|-h|--help)   pdda_usage; exit 0 ;;
utils/pdda/pdda.sh-1443-  *)                printf 'pdda.sh: unknown command %q\n\n' "$cmd" >&2; pdda_usage >&2; exit 2 ;;
src/rebalance/ingest/calendar_helpers.py-4-
src/rebalance/ingest/calendar_helpers.py-5-GUARD RAILS — DO NOT DUPLICATE THESE PATTERNS ELSEWHERE:
src/rebalance/ingest/calendar_helpers.py-6-
src/rebalance/ingest/calendar_helpers.py:7:  - Raw `datetime.fromisoformat(x.replace('Z', ...))` → use parse_calendar_dt()
src/rebalance/ingest/calendar_helpers.py:8:  - Raw `(end - start).total_seconds() / 60` → use event_duration_minutes()
src/rebalance/ingest/calendar_helpers.py-9-  - Raw `get_connection() + ensure_calendar_schema()` → use calendar_connection()
src/rebalance/ingest/calendar_helpers.py-10-  - Raw ISO text comparisons for upcoming events → use upcoming_calendar_rows()
src/rebalance/ingest/calendar_helpers.py-11-    after a julianday() SQL prefilter. Calendar rows preserve source offsets,
--
src/rebalance/ingest/calendar_helpers.py-13-    once the UTC clock reaches afternoon.
src/rebalance/ingest/calendar_helpers.py-14-
src/rebalance/ingest/calendar_helpers.py-15-CI enforces this via grep checks in .github/workflows/ci.yml.
src/rebalance/ingest/calendar_helpers.py:16:If you need an exception, add `# raw-ok` on the same line.
src/rebalance/ingest/calendar_helpers.py-17-"""
src/rebalance/ingest/calendar_helpers.py-18-
src/rebalance/ingest/calendar_helpers.py-19-from __future__ import annotations
--
src/rebalance/ingest/calendar_helpers.py-34-    when possible; date-only strings (all-day events) return naive.
src/rebalance/ingest/calendar_helpers.py-35-    """
src/rebalance/ingest/calendar_helpers.py-36-    from rebalance.lib.time_ops import _parse_iso
src/rebalance/ingest/calendar_helpers.py:37:    parsed = _parse_iso(raw, force_utc=False)  # raw-ok: canonical location
src/rebalance/ingest/calendar_helpers.py-38-    if parsed is None:
src/rebalance/ingest/calendar_helpers.py-39-        raise ValueError(f"Invalid isoformat string: '{raw}'")
src/rebalance/ingest/calendar_helpers.py-40-    return parsed
--
src/rebalance/ingest/calendar_helpers.py-116-        end = parse_calendar_dt(end_str)
src/rebalance/ingest/calendar_helpers.py-117-        if start.tzinfo is None or end.tzinfo is None:
src/rebalance/ingest/calendar_helpers.py-118-            return 0
src/rebalance/ingest/calendar_helpers.py:119:        return max(0, int((end - start).total_seconds() / 60))  # raw-ok: canonical location
src/rebalance/ingest/calendar_helpers.py-120-    except Exception:
src/rebalance/ingest/calendar_helpers.py-121-        return 0
src/rebalance/ingest/calendar_helpers.py-122-
--
src/rebalance/ingest/calendar_helpers.py-134-    """
src/rebalance/ingest/calendar_helpers.py-135-    from rebalance.ingest.db import db_connection, ensure_calendar_schema
src/rebalance/ingest/calendar_helpers.py-136-
src/rebalance/ingest/calendar_helpers.py:137:    with db_connection(database_path, ensure_calendar_schema) as conn:  # raw-ok: canonical location
src/rebalance/ingest/calendar_helpers.py-138-        yield conn
--
.github/workflows/ci.yml-57-
.github/workflows/ci.yml-58-      - name: Check for raw datetime parsing (use parse_calendar_dt)
.github/workflows/ci.yml-59-        run: |
.github/workflows/ci.yml:60:          if grep -rn "replace('Z'" src/rebalance/ --include="*.py" \
.github/workflows/ci.yml:61:               | grep -v "# raw-ok" | grep -v calendar_helpers.py | grep -v "src/rebalance/lib/"; then
.github/workflows/ci.yml-62-            echo "::error::Raw Z-replace found — use parse_calendar_dt() from calendar_helpers.py"
.github/workflows/ci.yml-63-            exit 1
.github/workflows/ci.yml-64-          fi
.github/workflows/ci.yml-65-
.github/workflows/ci.yml-66-      - name: Check for raw duration calculation (use event_duration_minutes)
.github/workflows/ci.yml-67-        run: |
.github/workflows/ci.yml:68:          if grep -rn "total_seconds() / 60" src/rebalance/ --include="*.py" \
.github/workflows/ci.yml:69:               | grep -v "# raw-ok" | grep -v calendar_helpers.py | grep -v "src/rebalance/lib/"; then
.github/workflows/ci.yml-70-            echo "::error::Raw duration calc found — use event_duration_minutes() from calendar_helpers.py"
.github/workflows/ci.yml-71-            exit 1
.github/workflows/ci.yml-72-          fi

2026-08-14T19:06:39.045125Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 95 column 5
codex
I’ve confirmed the key distinction: the current CI guard passes, but it bans module spellings rather than the duplicated behaviors. I’m checking whether off-the-shelf linting can replace the bespoke rule cleanly.
web search: 
web search: Ruff TID251 banned-api documentation banned imports ...
exec
/bin/zsh -lc "rg -n -C 3 '"'^'"\\[tool\\.(ruff|pylint)|pylint|ruff|flake8' pyproject.toml setup.cfg .ruff.toml tox.ini 2>/dev/null; nl -ba pyproject.toml | sed -n '1,260p'; nl -ba utils/pdda/pdda.sh | sed -n '1008,1045p'; nl -ba PROJECT/PDDA.md | sed -n '836,915p'; nl -ba AGENTS.md | sed -n '92,106p'; nl -ba .github/workflows/ci.yml | sed -n '52,86p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
 succeeded in 0ms:
     1	[build-system]
     2	requires = ["setuptools>=69", "wheel"]
     3	build-backend = "setuptools.build_meta"
     4	
     5	[project]
     6	name = "rebalance-os"
     7	version = "0.68.7"
     8	description = "Local-first workday operating system with MCP tools and Obsidian ingest"
     9	readme = "README.md"
    10	requires-python = ">=3.12"
    11	dependencies = [
    12	  "typer>=0.12.0",
    13	  "rich>=13.7.0",
    14	  "pydantic>=2.8.0",
    15	  "PyYAML>=6.0.1",
    16	  "questionary>=2.0.1",
    17	  # Capped at <2: mcp 2.0.0 removed mcp.server.fastmcp, which src/rebalance/mcp/
    18	  # imports in 8 modules. See GH-225.
    19	  "mcp>=1.0.0,<2",
    20	  "sqlite-vec>=0.1.6",
    21	  "keyring>=25.0.0",
    22	]
    23	
    24	[project.optional-dependencies]
    25	calendar = [
    26	  "google-api-python-client>=2.0.0",
    27	  "google-auth-oauthlib>=1.0.0",
    28	  "google-auth-httplib2>=0.2.0",
    29	]
    30	embeddings = [
    31	  "mlx-embeddings>=0.1.0",
    32	]
    33	server = [
    34	  "fastapi>=0.110.0",
    35	  "uvicorn[standard]>=0.29.0",
    36	]
    37	gcp = [
    38	  "google-cloud-secret-manager>=2.0.0",
    39	]
    40	dev = [
    41	  "pytest>=8.0.0",
    42	]
    43	
    44	[project.scripts]
    45	rebalance = "rebalance.cli:app"
    46	
    47	[tool.setuptools]
    48	package-dir = {"" = "src"}
    49	
    50	[tool.setuptools.packages.find]
    51	where = ["src"]
    52	
    53	[tool.setuptools.package-data]
    54	# Ship SQL migration files inside the wheel so run_migrations() can find them.
    55	"rebalance.ingest.db" = ["migrations/*.sql"]
  1008	      ;;
  1009	  esac
  1010	  printf '%s\n' "$candidate"
  1011	}
  1012	
  1013	check_banned_imports() {
  1014	  pdda_reset_counts
  1015	  local CHECK_NAME="pdda-check-banned-imports" rc=0
  1016	  local script_path="$PDDA_REPO_ROOT/utils/pdda/check_banned_imports.py"
  1017	  
  1018	  if [ ! -f "$script_path" ]; then
  1019	    return 0
  1020	  fi
  1021	
  1022	  local output
  1023	  output=$("$PDDA_REPO_ROOT/.venv/bin/python" "$script_path" 2>/dev/null)
  1024	  
  1025	  if [ -n "$output" ]; then
  1026	    while IFS= read -r line; do
  1027	      local file="${line%%:*}"
  1028	      local rest="${line#*:}"
  1029	      local lineno="${rest%%:*}"
  1030	      local msg="${rest#*: }"
  1031	      pdda_record_finding error "$CHECK_NAME" "$file" "$lineno" "$msg" "replace-import"
  1032	      rc=1
  1033	    done <<< "$output"
  1034	  fi
  1035	
  1036	  pdda_emit_summary "$CHECK_NAME" 0
  1037	  return "$(pdda_gated_exit 0)"
  1038	}
  1039	
  1040	check_governance() {
  1041	  pdda_reset_counts
  1042	  local CHECK_NAME="pdda-check-governance" rc=0
  1043	  local docs="${PDDA_GOVERNANCE_DOCS:-$PDDA_GOVERNANCE_DOCS_DEFAULT}"
  1044	  local index_doc="${PDDA_GOVERNANCE_INDEX:-$PDDA_GOVERNANCE_INDEX_DEFAULT}"
  1045	  local shipped_docs="${PDDA_GOV_SHIPPED_DOCS:-$PDDA_GOV_SHIPPED_DOCS_DEFAULT}"
   836	## Enforcement modes
   837	
   838	PDDA runs in one of three modes. The mode is resolved in this order: **the `PDDA_MODE` env var wins if
   839	set; otherwise the first non-comment line of a repo-root `.pdda-mode` file; otherwise the built-in
   840	default `observe`.** (So an env var overrides a committed `.pdda-mode` — convenient for a one-off
   841	`PDDA_MODE=observe` pass against a repo otherwise committed to `full`.) The point is an **adoption
   842	ramp**: a freshly-installed PDDA should never break a build on day one, and a project should graduate
   843	onto the rails deliberately.
   844	
   845	| Mode | When | Findings reported | Exit on `error` |
   846	|---|---|---|---|
   847	| `observe` | just installed | yes | always `0` |
   848	| `light` | transitioning | yes | `0` (warn, don't block) |
   849	| `full` | fully on rails | yes | non-zero (blocks) |
   850	
   851	- The default is `observe` so a brand-new install is non-blocking — it shows the team what PDDA
   852	  *would* flag without failing anything.
   853	- `light` is the transition phase: loud reports, but still never fails a build, while the backlog of
   854	  doc debt is cleared.
   855	- `full` is the strict end state: `error` findings block with a non-zero exit. A repo declares it by
   856	  committing `.pdda-mode` with `full`.
   857	- **No mode mutates the tree.** Stale docs are *flagged, never auto-moved* — the only destructive
   858	  mechanic was removed (see the stale-doc check above). Mode controls one thing only: whether an
   859	  `error` blocks. Every check ends with `exit "$(pdda_gated_exit "$EXIT_CODE")"`, which returns the
   860	  real code only in `full`.
   861	
   862	## ROADMAP.md contract
   863	
   864	`ROADMAP.md` is a pointer file, not a plan body.
   865	
   866	It should contain:
   867	
   868	- queued / parked intake pointers for newly captured `GH-*.md` docs
   869	- projects in progress
   870	- completed work
   871	- attempted work
   872	- deferred work
   873	- links to the canonical project docs
   874	
   875	It should usually not contain:
   876	
   877	- detailed phase checklists
   878	- step-by-step build instructions
   879	- deep execution notes already owned by a project file
   880	
   881	Strict exemption:
   882	- a short exception note is allowed when omitting the note would hide an operationally critical fact
   883	
   884	Maintainer rule:
   885	- when a roadmap entry needs more than a one-line status + a link, that is the signal to put the
   886	  detail in the entry's `PROJECT/**` doc and leave only the pointer here — do not grow the roadmap
   887	
   888	Coverage rule:
   889	- every active doc in `PROJECT/2-WORKING` must be reflected here by a pointer (a one-line ledger entry
   890	  that links it), so the ledger never falls behind the working set. A working doc that legitimately
   891	  should not appear opts out with `roadmap_exempt: true` in its frontmatter. This is the inverse of the
   892	  "no detail leaks in" rule above: nothing active goes *missing from* the roadmap either.
   893	- every captured GitHub issue doc in `PROJECT/1-INBOX/GH-*.md` must also be reflected here as a
   894	  one-line **queued / parked** pointer until it is promoted, deferred out, or closed, so intake cannot
   895	  quietly disappear and later be duplicated.
   896	
   897	How this is enforced (so it cannot quietly rot in either direction):
   898	- **deterministic (no leak in)** — `pdda.sh roadmap` errors on task checklists / `### Checklist` /
   899	  `### QA checklist` headings and warns on size sprawl (runs hourly, free, no model needed)
   900	- **deterministic (no gap missing)** — `pdda.sh roadmap-coverage` errors when either an
   901	  active `PROJECT/2-WORKING` doc has no pointer here, or a captured `PROJECT/1-INBOX/GH-*.md` doc is
   902	  not parked here as a queue entry (honors `roadmap_exempt: true`)
   903	- **LLM** — `utils/pdda/pdda-doc-ready.sh` reviews `ROADMAP.md` against the full pointer contract for the
   904	  fuzzier "this paragraph is really execution detail" cases (honors the carve-out)
   905	- the file itself carries a top banner restating the contract, so a human editing it sees the rule
   906	
   907	## CHANGELOG.md — end-of-iteration record (first-class)
   908	
   909	`CHANGELOG.md` is a first-class PDDA artifact: the canonical, newest-first running log of what changed,
   910	updated **at the end of each iteration**. It is the one narrative/provenance log this contract
   911	prescribes — if an adopting repo kept its own ad hoc recap or run-observation notes before adopting
   912	PDDA, `CHANGELOG.md` supersedes them; PDDA does not require or name any such file itself (Principle #4 —
   913	one canonical place per fact). Durable Costly / one-way-door bets still earn a `decisions/` record.
   914	updated **at the end of each iteration**. It supersedes the retired RECAP convention as the running
   915	provenance/narrative log, and it also absorbs the run-specific compliance findings the retired
    92	- Default to the most common action. If 80% of users will pick the same option, pre-select it — don't make the majority click what the system already knows.
    93	
    94	## Code & Architecture
    95	
    96	> For the *why* behind these rules, see [GUIDING-PRINCIPLES.md](./GUIDING-PRINCIPLES.md).
    97	
    98	- Code: DRY, SOLID; balance maintainability, performance, secure. Comply with framework security best practices.
    99	- **Pre-flight Search Rule**: Before writing any new utility function or system layer, you MUST use `grep_search` or MCP `search_graph` to check if a similar function exists (e.g., date parsing, JSON handling). If it exists, import it. Do not duplicate it.
   100	- **Centralization Rule**: All standard data formatting and OS-level operations (like datetime parsing, json dumping, git calls) must use `src/rebalance/lib/*` modules instead of creating local helper methods in the collector.
   101	- **State Management**: Introduce FSM (Finite State Machine) if state transitions exceed 4 distinct states or more than one conditional branch per state. Document the state diagram in code comments, or in the owning `PROJECT/**` doc.
   102	- **Contracts**: Designate single writer per contract/schema (API response shape, DB record structure, queue message format). Changes require review from contract owner; broadcast breaking changes immediately.
   103	- **Pipelines**: One logical pipeline per data flow whenever possible. Avoid forking/rejoining; use filters, transforms, and side effects in sequence. If pipeline needs multiple paths, use conditional routing within single pipeline, not separate pipelines.
   104	- **Collectors, sources & write paths** (see `PROJECT/2-WORKING/COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md`):
   105	  - **Classify before you register.** Every scope is exactly one of: raw source / derived scan / projection / export. Only raw sources are `all`-eligible; derived/projection/export attach as named stages, never as peers in the registry.
   106	  - **One writer per table.** Only the `semantic` stage writes `semantic_documents`/`semantic_embeddings`; a source writes only its own raw tables. (This is the Contracts rule above, applied to the semantic tables.)
    52	      - name: 3-Eyes dashboard is in sync with the registry (GH-195)
    53	        run: python -m three_eyes.dashboard --check
    54	        working-directory: utils/3-eyes
    55	        env:
    56	          PYTHONPATH: ${{ github.workspace }}/utils/3-eyes
    57	
    58	      - name: Check for raw datetime parsing (use parse_calendar_dt)
    59	        run: |
    60	          if grep -rn "replace('Z'" src/rebalance/ --include="*.py" \
    61	               | grep -v "# raw-ok" | grep -v calendar_helpers.py | grep -v "src/rebalance/lib/"; then
    62	            echo "::error::Raw Z-replace found — use parse_calendar_dt() from calendar_helpers.py"
    63	            exit 1
    64	          fi
    65	
    66	      - name: Check for raw duration calculation (use event_duration_minutes)
    67	        run: |
    68	          if grep -rn "total_seconds() / 60" src/rebalance/ --include="*.py" \
    69	               | grep -v "# raw-ok" | grep -v calendar_helpers.py | grep -v "src/rebalance/lib/"; then
    70	            echo "::error::Raw duration calc found — use event_duration_minutes() from calendar_helpers.py"
    71	            exit 1
    72	          fi
    73	
    74	      - name: Check for banned imports
    75	        run: python utils/pdda/check_banned_imports.py
    76	
    77	      - name: Check for duplicate code
    78	        run: |
    79	          python -m pip install pylint
    80	          pylint --disable=all --enable=duplicate-code src/rebalance/

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_focus5_scan.py tests/test_gemini_key_resolution.py -q' in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk
 exited 1 in 283ms:
Traceback (most recent call last):
  File "<frozen runpy>", line 203, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pytest/__main__.py", line 9, in <module>
    raise SystemExit(pytest.console_main())
                     ~~~~~~~~~~~~~~~~~~~^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/config/__init__.py", line 223, in console_main
    code = main()
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/config/__init__.py", line 193, in main
    config = _prepareconfig(new_args, plugins)
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/config/__init__.py", line 361, in _prepareconfig
    config: Config = pluginmanager.hook.pytest_cmdline_parse(
                     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        pluginmanager=pluginmanager, args=args
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
    ~~~~~~~~~~~~~~^^^^^^^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/helpconfig.py", line 124, in pytest_cmdline_parse
    config = yield
             ^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/config/__init__.py", line 1192, in pytest_cmdline_parse
    self.parse(args)
    ~~~~~~~~~~^^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/config/__init__.py", line 1562, in parse
    self.hook.pytest_load_initial_conftests(
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        early_config=self, args=args, parser=self._parser
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
    ~~~~~~~~~~~~~~^^^^^^^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/warnings.py", line 128, in pytest_load_initial_conftests
    return (yield)
            ^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/pluggy/_callers.py", line 116, in _multicall
    next(function_gen)  # first yield
    ~~~~^^^^^^^^^^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/capture.py", line 170, in pytest_load_initial_conftests
    capman.start_global_capturing()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/capture.py", line 773, in start_global_capturing
    self._global_capturing = _get_multicapture(self._method)
                             ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/capture.py", line 714, in _get_multicapture
    return MultiCapture(in_=FDCapture(0), out=FDCapture(1), err=FDCapture(2))
                                              ~~~~~~~~~^^^
  File "/Users/noelsaw/Documents/rebalance-OS/.venv-py314-backup/lib/python3.14/site-packages/_pytest/capture.py", line 493, in __init__
    TemporaryFile(buffering=0),
    ~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/tempfile.py", line 652, in TemporaryFile
    prefix, suffix, dir, output_type = _sanitize_params(prefix, suffix, dir)
                                       ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/tempfile.py", line 127, in _sanitize_params
    dir = gettempdir()
  File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/tempfile.py", line 312, in gettempdir
    return _os.fsdecode(_gettempdir())
                        ~~~~~~~~~~~^^
  File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/tempfile.py", line 305, in _gettempdir
    tempdir = _get_default_tempdir()
  File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/tempfile.py", line 222, in _get_default_tempdir
    raise FileNotFoundError(_errno.ENOENT,
                            "No usable temporary directory found in %s" %
                            dirlist)
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk']

codex
ANSWER

Rework before commit. Your read is correct: this Phase 2 turns ordinary stdlib imports into a cosmetic chokepoint, not a behavioral one. Keep the real Phase 1 helper consolidation; discard the 64-file import-laundering migration and its shim policy.

FINDINGS

- [Blocker] The shim has no governance value. [`subprocess_ops.py`](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/lib/subprocess_ops.py:1) merely re-exports selected stdlib names, while callers misleadingly bind it as `subprocess` ([`doctor.py`](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/doctor.py:17)). It sets no timeout, error, logging, or testability policy. `datetime` is even less of a seam: callers import the raw class directly from [`time_ops.py`](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/lib/time_ops.py:1).

- [Blocker] The current WIP is not self-contained until the untracked shim is committed: dozens of rewritten imports require it, but it is absent from `HEAD`. Even if staged, its deliberately partial API makes future ordinary stdlib use a needless source of breakage.

- [Should] The policy and enforcement disagree. The plan says `datetime`, `json`, and `subprocess` must come through `lib` ([plan](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md:48)), but the linter bans only `datetime` and `subprocess` ([linter](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/utils/pdda/check_banned_imports.py:17)). It also silently ignores AST parse failures ([line 11](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/utils/pdda/check_banned_imports.py:11)).

- [Should] Enforce operations, not modules. Retain the genuine canonical implementations—e.g. ISO parsing in [`time_ops.py`](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/lib/time_ops.py:5) and Git execution in [`git_ops.py`](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/lib/git_ops.py:4). Add contract tests for their intended edge cases. A linter can ban exact duplicate helper definitions (`_parse_iso`, `_now_iso`, `_json_dumps`, `_git`) outside their owning modules, but cannot reliably detect a semantically equivalent “fifth parser” with a different name.

- [Pass] The existing targeted CI precedent is the right model: it bans a known duplicate parsing/duration idiom, names the canonical API, and allows a documented `# raw-ok` exception ([CI](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/.github/workflows/ci.yml:58); [canonical helper](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/ingest/calendar_helpers.py:5)). That delivers the real goal with no global import rewrite.

- [Nit] If a genuine import ban is ever needed, use Ruff’s built-in `TID251`/`banned-api`, rather than bespoke AST code; it is designed for project-wide banned imports/APIs. It still cannot enforce behavioral non-duplication. Pylint’s `duplicate-code` is useful as a broad clone detector, not a correctness rule. [Ruff docs](https://docs.astral.sh/ruff/rules/banned-api/), [Pylint R0801 docs](https://pylint.pycqa.org/en/v2.13.9/messages/refactor/duplicate-code.html).

RECOMMENDATION

Commit Phase 1’s real helpers and focused call-site refactors; revert the shim/import rewrite, delete `fix_imports.py`, and use the existing behavior-specific CI pattern plus a tiny exact-helper-definition check if further enforcement is warranted.
tokens used
105,828
ANSWER

Rework before commit. Your read is correct: this Phase 2 turns ordinary stdlib imports into a cosmetic chokepoint, not a behavioral one. Keep the real Phase 1 helper consolidation; discard the 64-file import-laundering migration and its shim policy.

FINDINGS

- [Blocker] The shim has no governance value. [`subprocess_ops.py`](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/lib/subprocess_ops.py:1) merely re-exports selected stdlib names, while callers misleadingly bind it as `subprocess` ([`doctor.py`](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/doctor.py:17)). It sets no timeout, error, logging, or testability policy. `datetime` is even less of a seam: callers import the raw class directly from [`time_ops.py`](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/lib/time_ops.py:1).

- [Blocker] The current WIP is not self-contained until the untracked shim is committed: dozens of rewritten imports require it, but it is absent from `HEAD`. Even if staged, its deliberately partial API makes future ordinary stdlib use a needless source of breakage.

- [Should] The policy and enforcement disagree. The plan says `datetime`, `json`, and `subprocess` must come through `lib` ([plan](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/PROJECT/2-WORKING/GH-266-ARCHITECTURAL-AUDIT.md:48)), but the linter bans only `datetime` and `subprocess` ([linter](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/utils/pdda/check_banned_imports.py:17)). It also silently ignores AST parse failures ([line 11](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/utils/pdda/check_banned_imports.py:11)).

- [Should] Enforce operations, not modules. Retain the genuine canonical implementations—e.g. ISO parsing in [`time_ops.py`](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/lib/time_ops.py:5) and Git execution in [`git_ops.py`](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/lib/git_ops.py:4). Add contract tests for their intended edge cases. A linter can ban exact duplicate helper definitions (`_parse_iso`, `_now_iso`, `_json_dumps`, `_git`) outside their owning modules, but cannot reliably detect a semantically equivalent “fifth parser” with a different name.

- [Pass] The existing targeted CI precedent is the right model: it bans a known duplicate parsing/duration idiom, names the canonical API, and allows a documented `# raw-ok` exception ([CI](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/.github/workflows/ci.yml:58); [canonical helper](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-93808-9khlqdtk/src/rebalance/ingest/calendar_helpers.py:5)). That delivers the real goal with no global import rewrite.

- [Nit] If a genuine import ban is ever needed, use Ruff’s built-in `TID251`/`banned-api`, rather than bespoke AST code; it is designed for project-wide banned imports/APIs. It still cannot enforce behavioral non-duplication. Pylint’s `duplicate-code` is useful as a broad clone detector, not a correctness rule. [Ruff docs](https://docs.astral.sh/ruff/rules/banned-api/), [Pylint R0801 docs](https://pylint.pycqa.org/en/v2.13.9/messages/refactor/duplicate-code.html).

RECOMMENDATION

Commit Phase 1’s real helpers and focused call-site refactors; revert the shim/import rewrite, delete `fix_imports.py`, and use the existing behavior-specific CI pattern plus a tiny exact-helper-definition check if further enforcement is warranted.
