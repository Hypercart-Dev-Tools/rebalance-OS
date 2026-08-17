# P1 — catalog hygiene: retire the deleted, classify the unknown

## Context you need

`utils/3-eyes/` is a local job supervisor (GH-195). `registry/catalog-notes.toml` is
**committed human curation**: it annotates every launchd agent on this machine with a
`status` of `managed | to-adopt | observe | server | system`. `CATALOG.md` is generated
from it and is gitignored. `three_eyes catalog --check` fails when a live agent has no
entry; `three_eyes health` reports the same as "unclassified".

Read `utils/3-eyes/registry/jobs.local.d/README.md` and the header of
`catalog-notes.toml` before editing.

## The work

Two corrections, both to `utils/3-eyes/registry/catalog-notes.toml`.

**1. The Cactus sentinels are gone — stop listing them as adoption targets.**

`com.neochro.sentinel-daemon` and `com.neochro.sentinel-daemon.sleuth-app` are still
marked `to-adopt`. They were disabled and deleted by the operator on 2026-07-27; their
plists are parked in `~/Library/LaunchAgents/.disabled-cactus-sentinel-2026-07-27/`.
3-Eyes supersedes them — that was the entire point of removing them.

They must stop appearing as work to be done. Give each a `status` that records the
history rather than deleting the block outright (a deleted block reads as "we never knew
about this"; the point is that we knowingly retired it). Add a short `does`/note line
saying they were retired on 2026-07-27 and superseded by 3-Eyes. Use whichever existing
status value is honest — do **not** invent a new one without checking what
`catalog.py` and `health.py` actually accept, because an unrecognised status will
silently fall through their branching.

Also review `com.neochro.cactus-serve` and `com.neochro.needle-router` (currently
`server`). They are the Cactus SLM server and its routing shim, both `not-loaded`. Decide
and record whether they are retired too, or genuinely still wanted. State the reasoning
in a comment; do not guess silently.

**2. `com.neochro.sys-mem-attribute` is unclassified.**

`three_eyes health` currently reports exactly one unclassified agent. It is a memory
sampler, sibling to `com.neochro.vscode-mem-attribute`, which is already classified
`observe` with the note that it is a continuous KeepAlive logger, NOT a scheduled
findings job. Classify `sys-mem-attribute` consistently with its sibling and say why.

## Definition of done

- `python -m three_eyes health` reports **zero** unclassified agents.
- `python -m three_eyes catalog --check` passes, or the only drift reported is expected
  and explained in your turn.
- The two deleted Cactus sentinels no longer count as `to-adopt`.
- A test in `utils/3-eyes/tests/test_catalog_health.py` asserts that a retired agent is
  not reported as an adoption target, so this cannot silently regress.
- `.venv/bin/python -m pytest utils/3-eyes/tests -q` is green.

## Constraints

- **Do not touch `~/Library/LaunchAgents`.** No `launchctl` invocation of any kind. This
  phase edits committed curation only.
- `CATALOG.md` is generated and gitignored — do not hand-edit it. Regenerate with
  `python -m three_eyes catalog --write` if you need to inspect the result.
- Every status value you use must already be handled by `catalog.py`/`health.py`. Check.
- Explain any judgement call in your turn block. "I classified X as Y because Z" — a
  status set without a stated reason is the thing this file exists to prevent.
