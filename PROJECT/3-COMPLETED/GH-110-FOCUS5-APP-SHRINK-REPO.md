---
title: "focus5 app: shrink repo-name font size by 20%"
gh_issue: 110
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/110"
status: complete
created: 2026-07-04
updated: 2026-07-04
doc_type: bugfix
---

# focus5 app: shrink repo-name font size by 20%

Captured via HQ (`/hq park`) for project **rebalance-OS** → repo `rebalance-OS`.

## Status

| What was just completed | What's next |
|---|---|
| **DONE 2026-07-04.** Mac app's `Theme.display` (`macOS/Apps/Focus5Float/Sources/Focus5Float/Theme.swift`) reduced 17pt → 14pt; HTML `/focus-5` page's `.f5-name` (`src/rebalance/web.py`) reduced 15px → 12px (~20% smaller, matching the sibling web surface). Verified visually in a `swift build`/`swift run` of the native app — repo names render clearly legible at the smaller size with no clipping. Merged via [PR #111](https://github.com/Hypercart-Dev-Tools/rebalance-OS/pull/111); `/Applications/Focus 5 Float.app` rebuilt via `make-app.sh` so the installed copy carries the fix. | Done — closed. |

## Request

In the focus5 Mac app, the repo names in the list render too large. Reduce the repo-name font size by approximately 20 percent.
