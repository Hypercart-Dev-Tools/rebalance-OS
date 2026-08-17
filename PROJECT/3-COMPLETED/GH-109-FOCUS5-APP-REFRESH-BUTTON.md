---
title: "focus5 app: refresh button does not drop Git Worktrees removed from disk"
gh_issue: 109
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/109"
status: complete
created: 2026-07-04
updated: 2026-07-04
doc_type: bugfix
---

# focus5 app: refresh button does not drop Git Worktrees removed from disk

Captured via HQ (`/hq park`) for project **rebalance-OS** → repo `rebalance-OS`.

## Status

| What was just completed | What's next |
|---|---|
| **DONE 2026-07-04.** `summarize_focus5` (`src/rebalance/ingest/focus5_scan.py`) gained a `_repo_path_live()` existence check (mirrors `iter_git_repos`'s `.git` predicate) applied on the read path via `drop_missing_paths=True` (default on; the synthetic-path ranking unit tests opt out). A repo whose folder or `.git` no longer exists now drops from the roster/off-roster on the next read-only `GET /focus-5.json` fetch — no full ~30s device rescan needed. 2 new regression tests in `tests/test_focus5_scan.py`; full suite green (153 passed pre-merge). **Visually verified live in the native Focus5Float app**, not just the Python suite: a throwaway git worktree was synced into the running app's roster, deleted from disk, and confirmed to disappear from the panel via the app's own read-only refresh path (no full rescan triggered). Merged via [PR #111](https://github.com/Hypercart-Dev-Tools/rebalance-OS/pull/111); `/Applications/Focus 5 Float.app` rebuilt via `make-app.sh` so the installed copy carries the fix. | Done — closed. |

## Request

The focus5 Mac app refresh button does not remove Git Worktrees that were deleted from disk. After an agent removes a git worktree, its entry remains in the list even after pressing refresh. Update the refresh logic to detect worktrees whose on-disk path no longer exists (reconcile against the output of git worktree list and/or the filesystem) and drop those stale entries from the display.

## Root cause

The Mac app's refresh button hit `summarize_focus5()`, which is strictly read-only (never runs the device git scan) — so a checkout/worktree deleted from disk lingered from its stale cached DB row until the next full sync. The fix filters on the read path instead of requiring a rescan.
