---
title: "M1 p3 — config.py: one JSON config and the secret chain"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M1 p3 — config.py: one JSON config and the secret chain

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m1-p1` is approved. |

**Canonical spec:** `HIQS-PROJECT.md` §5 rule 3, §11, L16 (a whitelist that silently drops keys).

## Build

`HiQS/hiqs/config.py`:
- One JSON config at the canonical config path (§13). Read it whole.
- `secret(name)` resolving **keyring → 0600 file outside the repo → env**, in that order, first hit
  wins. Return `None` when nothing resolves — never `""`, which reads as "configured but empty".
- Unknown keys in the config file are **reported through `status`, not discarded** (L16 — a
  whitelist that silently no-ops a setting is a cluster-A failure wearing a config file).

## Acceptance

- Each rung of the chain is tested in isolation and in precedence order.
- A config carrying an unrecognised key surfaces it; a test asserts it is not silently dropped.
- A missing config file yields documented defaults, not a crash.
- A `0600` check on the file rung: a secret file with looser permissions is refused, loudly.
- No absolute user path anywhere in the module (L11).

## Do not

- Do not log, echo, or include a resolved secret in any return value, error message, or event
  payload.
- Do not create the config file or write to keyring — this phase reads. `hiqs auth` (p5, then M4)
  is the only writer.
