# PDDA Install / Extraction Manifest

This file is the portable install manifest for PDDA.

Use it when an LLM agent needs to extract the PDDA files from this repo and install them into a
different repo without guessing which files are canonical.

## Fastest path: `install.sh`

For a normal install, the repo-root `install.sh` automates this entire manifest — copy the runtime,
create the lifecycle tree, synthesize the blank seed files, `chmod`, and run a verification pass:

```bash
./install.sh /path/to/target-repo          # observe mode, idempotent
./install.sh --with-startup-docs --mode light /path/to/target-repo
```

The rest of this document is the canonical spec `install.sh` implements — read on when you need to
install by hand, adapt to a non-standard layout, or keep the script honest. Keep the two in lockstep:
a change to the install surface updates both.

## Purpose

PDDA installs two things:

- the canonical document contract in `PROJECT/PDDA.md`
- the runnable shell checks in `utils/pdda-*.sh`

This standalone repo also carries repo-local startup docs (`ROUTER.md`, `AGENTS.md`, `README.md`) and
the `/pdda` re-orient skill (`.claude/skills/pdda/SKILL.md`) so the installer source stays
self-consistent, but those files are not part of the target-repo install surface unless the target
explicitly wants them. `install.sh --with-startup-docs` ships `ROUTER.md`, `AGENTS.md`, and the
`/pdda` skill together as the agent read-order scaffold.

Do not install deprecated PDDA companion docs from `PROJECT/4-MISC/`.

## Prerequisites

- `bash`
- `node`
- standard POSIX tools used by the scripts: `awk`, `grep`, `sed`, `find`, `wc`, `mv`, `date`

## Canonical install set

Extract these files verbatim from this repo into the target repo at the same relative paths:

```text
PROJECT/PDDA.md
utils/pdda/pdda-lib.sh
utils/pdda/pdda.sh
utils/pdda/pdda-doc-ready.sh
utils/pdda/pdda-catchup.sh
```

The shipped runtime lives in its own `utils/pdda/` subfolder so it never mixes with a target repo's
existing `utils/` files. `utils/pdda/pdda.sh` is the unified entry point — it carries every
deterministic check plus the aggregate `run` as subcommands (`pdda.sh run`, `pdda.sh frontmatter`,
`pdda.sh roadmap`, ...). `utils/pdda/pdda-lib.sh` holds the shared helpers it sources;
`utils/pdda/pdda-doc-ready.sh` is the opt-in LLM readiness layer and `utils/pdda/pdda-catchup.sh` is
the opt-in ROUTER.md triage layer.

## Files to create in the target repo

Create these paths if they do not already exist:

```text
PROJECT/
PROJECT/1-INBOX/
PROJECT/2-WORKING/
PROJECT/3-COMPLETED/
PROJECT/4-MISC/
utils/pdda/
ROADMAP.md
CHANGELOG.md
PROJECT/PDDA-ACTIVITY.jsonl
```

If the target repo already has its own `PROJECT/**` tree, reuse it rather than replacing it.

## Do not copy

These are not part of the live install surface:

```text
PROJECT/4-MISC/PDDA-AGENT.md
PROJECT/4-MISC/AGENTS-DOCS.md
```

Also do not copy this repo's existing `PROJECT/PDDA-ACTIVITY.jsonl` contents into another repo.
Create a fresh empty file instead.

## Install sequence

1. Create the target directories listed above. -> expect `PROJECT/` and `utils/` to exist.
2. Copy the canonical install-set files verbatim to the same relative paths in the target repo. -> expect `PROJECT/PDDA.md` and all shipped `utils/pdda-*.sh` files to exist.
3. Create baseline `ROADMAP.md` and `CHANGELOG.md` files if the target repo does not already have them. -> expect the roadmap contract to have a file to guard and the changelog check to warn less.
4. Create an empty `PROJECT/PDDA-ACTIVITY.jsonl` if it does not exist. -> expect a zero- or low-byte log file, not this repo's historical log.
5. Make the shell scripts executable. -> expect `chmod +x utils/pdda/pdda.sh utils/pdda/pdda-doc-ready.sh utils/pdda/pdda-lib.sh utils/pdda/pdda-catchup.sh` to succeed.
6. Optionally create a repo-root `.pdda-mode` file with `observe` for first install. -> expect a non-destructive first run.
7. If the target repo uses a different doc layout, set environment overrides instead of editing the scripts first. -> expect the checks to honor the env vars below.
8. Run `utils/pdda/pdda.sh run` in the target repo. -> expect report-only behavior in `observe` mode and an append to `PROJECT/PDDA-ACTIVITY.jsonl`.

## Environment overrides

PDDA is portable because the scripts can be redirected by env vars.

Use these when the target repo does not exactly match this repo's layout:

```text
PDDA_MODE
PDDA_WORKING_DIR
PDDA_MISC_DIR
PDDA_ACTIVITY_LOG
PDDA_ROADMAP
PDDA_STALE_DAYS
PDDA_DRY_RUN
PDDA_FORMAT
PDDA_ACTIVITY_MAX_LINES
PDDA_ROADMAP_MAX_LINES
PDDA_ROADMAP_MAX_HEADINGS
PDDA_LLM_BIN
PDDA_LLM_ARGS
PDDA_LLM_MODEL
```

## Minimal target-repo expectations

PDDA assumes these repo concepts exist, either literally or through overrides:

- an active-doc folder
- an archive/misc folder
- a repo roadmap file
- an end-of-iteration changelog file
- Markdown project docs under source control

The default install expects:

```text
PROJECT/2-WORKING
PROJECT/4-MISC
ROADMAP.md
```

## Extraction instructions for an LLM agent

If you are an install agent extracting PDDA into another repo, follow this exact rule:

1. Copy only the files in `Canonical install set`.
2. Create only the paths in `Files to create in the target repo`.
3. Do not copy anything listed under `Do not copy`.
4. Do not infer extra files from historical companions in `PROJECT/4-MISC/`.
5. Do not copy old activity logs from this repo into the target repo.
6. Prefer `.pdda-mode = observe` on first install unless the user explicitly asks for blocking enforcement.

## Post-install verification

Run these commands in the target repo:

```bash
chmod +x utils/pdda/pdda.sh utils/pdda/pdda-doc-ready.sh utils/pdda/pdda-lib.sh utils/pdda/pdda-catchup.sh
printf 'observe\n' > .pdda-mode
utils/pdda/pdda.sh run
```

Expected result:

- the run prints PDDA summaries
- `observe` mode prevents stale-doc moves
- `PROJECT/PDDA-ACTIVITY.jsonl` receives new entries
- the suite exits `0` even if it reports findings

## Notes for adaptation

- `PROJECT/PDDA.md` is the canonical policy doc; if the target repo needs wording changes, edit that file there after install.
- `pdda-doc-ready.sh` is opt-in for model use; if no model CLI is configured, it self-skips and the deterministic suite still works.
- `pdda-lib.sh` uses `node` for JSON escaping/parsing helpers, so Node is required even though the checks are shell scripts.
