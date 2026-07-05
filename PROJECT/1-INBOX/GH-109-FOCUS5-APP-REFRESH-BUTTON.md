---
gh_issue: 109
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/109
title: "focus5 app: refresh button does not drop Git Worktrees removed from disk"
status: Proposed (1-INBOX — not yet active)
created: 2026-07-04
doc_type: feedback
---

# focus5 app: refresh button does not drop Git Worktrees removed from disk

Captured via HQ (`/hq park`) for project **rebalance-OS** → repo `rebalance-OS`.
The GitHub issue is the signal stream; this doc is the in-repo capture and back-reference.

## Request

The focus5 Mac app refresh button does not remove Git Worktrees that were deleted from disk. After an agent removes a git worktree, its entry remains in the list even after pressing refresh. Update the refresh logic to detect worktrees whose on-disk path no longer exists (reconcile against the output of git worktree list and/or the filesystem) and drop those stale entries from the display.

## Notes

- Filed under the PDDA issue-first SOP. Promote to `PROJECT/2-WORKING/` when execution starts,
  carrying `gh_issue` forward, and satisfy the full active-doc contract (status table, QA gates).
