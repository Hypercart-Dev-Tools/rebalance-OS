---
title: "MARATHON — CLIO durable idempotent writes (2026-07-19)"
status: "COMPLETE 2026-07-19 — both phases approved, gates green; one bash-3.2 runtime defect caught in post-run verification and fixed"
created: 2026-07-19
updated: 2026-07-19
owner: noel@neochro.me
branch: work/clio-durable-obsidian-writes
roadmap_exempt: true
goal: >
  Execute the buildable phases of the agy-reviewed CLIO durability plan
  (PROJECT/1-INBOX/CLIO-DURABLE-IDEMPOTENT-WRITES.md) via the marathon harness:
  P1 content-addressed idempotent append + Swift comment-skip, then P2 conflict-copy
  reconciliation. Phase 0 (live-sync spike) and Phase 3 (per-device regions) are out of scope.
---

# MARATHON — CLIO durable idempotent writes

## Status

| What was just completed | What's next |
|---|---|
| **Fired and completed.** Both phases approved (agy), both `swift build` gates green. Post-run verification ran the exporter on `/bin/bash` 3.2 and found the reconciliation array aborted with "unbound variable" (empty-array under `set -u`) — fixed with the `${arr[@]+…}` guard and re-verified (idempotency, state-delete, reconciliation, dry-run all pass). 48 swift tests pass. | Archive to `3-COMPLETED` after the operator litmus (install on both machines, watch a real conflict reconcile). |

## Plan

- **Parent plan:** [CLIO-DURABLE-IDEMPOTENT-WRITES.md](../../1-INBOX/CLIO-DURABLE-IDEMPOTENT-WRITES.md)
- **Phases:** [P1](briefs/p1-idempotent-append.md) (idempotent append + Swift reader) → [P2](briefs/p2-conflict-reconciliation.md) (reconciliation, `depends_on` P1)
- **Gate:** `bash -c "cd macOS/Apps/Focus5Float && swift build"` (no root `validate.sh`; pytest carries pre-existing failures so it is not the gate)
- **Out of scope:** Phase 0 spike (needs two live syncing devices), Phase 3 per-device regions (deferred).

## Firing

```bash
eval "$("$HOME/.claude/skills/relay-xyz/find-harness.sh" --env)"
.xyz/relay-automation/marathon.sh \
  --plan PROJECT/2-WORKING/CLIO-DURABLE-MARATHON/MARATHON.yaml \
  --pre-advance-cmd 'bash -c "cd macOS/Apps/Focus5Float && swift build"'
```
