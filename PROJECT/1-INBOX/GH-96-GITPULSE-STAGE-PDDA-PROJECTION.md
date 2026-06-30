---
title: git-pulse collector stages the PDDA registry projection file
status: In progress
created: 2026-06-30
updated: 2026-06-30
owner: noel
gh_issue: 96
branch: fix/gh-96-gitpulse-stage-pdda-projection
goal: >
  Make the git-pulse collector stage the per-device PDDA projection
  `pdda/registry-<device>.tsv` that PDDA's install.sh now writes into the sync repo, so it rides
  the normal pulse commit/push and propagates across devices instead of sitting as untracked dirt.
non_goals: >
  Not staging the whole `pdda/` dir or arbitrary repo dirt — only the single per-device file.
  No change to PDDA's write side (that was the separate fix, pdda#7). No new commit/push logic.
effort: 1
complexity: 1
risk: 1
phases: 1
---

# GH-96 — git-pulse collector stages the PDDA registry projection

## Status

| What was just completed | What's next |
|---|---|
| Root cause confirmed: `experimental/git-pulse/collect.sh` stages `pulse-<device>.md` and `devices/<device>.yaml` (and `snapshots/`) but never the PDDA projection `pdda/registry-<device>.tsv`, so on a PDDA-installed device it stays `?? pdda/` and never syncs. Verified live on `noels-mac-studio` (the file pdda#7's fix just started writing). Branch cut; one-line guarded `append_stage_path` added before `git add`. | Verify the collector stages + commits the projection (dry-run then real), run `rebalance doctor` + `pytest tests/` + `utils/pdda/pdda.sh run`, record in `CHANGELOG.md`, commit (`Closes #96`), push, land via self-mergeable PR, then archive this doc to `3-COMPLETED/`. |

## Problem

PDDA (`Hypercart-Dev-Tools/pdda` install.sh, `publish_registry_projection()`) writes a
path-normalized `pdda/registry-<device>.tsv` into the git-pulse sync repo. The git-pulse collector is
the **single git writer** for that repo, but its staging list omits `pdda/`, so the projection is
never committed or pushed — it propagates to other devices only via a manual add or a device-local
hotpatch. This is the **sync-side** half of the multi-device PDDA rollup; the **write-side** half was
fixed separately in pdda#7 (path autodetection). pdda#7 actually exposed this on `noels-mac-studio`:
now that the projection is written to `~/git-pulse-sync/pdda/`, it shows as untracked until this lands.

## Fix

In `experimental/git-pulse/collect.sh`, immediately before `git add -A -- "${stage_paths[@]}"`, add a
guarded stage of the single per-device file (mirrors the existing `snapshots/` guard):

```sh
[ -f "$sync_repo_dir/pdda/registry-$device_id.tsv" ] && append_stage_path "pdda/registry-$device_id.tsv"
```

The guard keeps it fail-safe on devices without PDDA (file absent → not staged → `git add` unaffected),
and scoping to the one file avoids broadly committing arbitrary `pdda/` dirt.

## Verification

- `bash -n experimental/git-pulse/collect.sh` clean.
- Collector dry-run, then a real pass on `noels-mac-studio`: `git -C ~/git-pulse-sync status --short`
  shows `pdda/registry-noels-mac-studio.tsv` staged/committed, no longer `??`.
- `rebalance doctor` clean, `pytest tests/` green, `utils/pdda/pdda.sh run` clean for this change.
