---
title: "M1 p5 — __main__.py: the CLI skeleton"
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
# M1 p5 — __main__.py: the CLI skeleton

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m1-p4` is approved; `status` calls its aggregator. |

**Canonical spec:** `HIQS-PROJECT.md` Decision 4 (six subcommands), §10, §11 (~180 LOC).

## Build

`HiQS/hiqs/__main__.py` — argparse (not typer, §11), six subcommands:
`refresh | status | search | ask | serve | auth`.

This phase wires **structure, not behaviour**: `status` is real (it calls p4's aggregator);
the rest parse their arguments, validate them, and raise a clear `NotImplementedError` naming the
phase that fills them in. `status --json` emits machine-readable output for scripts and agents.

`auth` exists from Phase 0 even though Calendar arrives in M4, because Decision 4 records why:
the only runner is an unattended launchd job that **cannot open a browser**, so the interactive
re-authorization path must exist before it is needed, not after.

## Acceptance

- `hiqs --help` lists all six subcommands (this exact check is in the Phase 0 gate).
- `hiqs status` on an empty DB prints valid JSON — the Phase 0 exit criterion.
- `hiqs status --json` output parses and matches §8's shape.
- Unimplemented subcommands fail with a message naming the phase, not a traceback.
- Exit codes: 0 success, non-zero on error. No command exits 0 on a failure it detected.

## Do not

- Do not implement `refresh`, `search`, `ask`, `serve`, or `auth`'s OAuth flow here.
- Do not add subcommands beyond the six. Decision 4 counts them, and §18.3's SMALL invariant means
  a seventh is a recorded decision, not a convenience.
