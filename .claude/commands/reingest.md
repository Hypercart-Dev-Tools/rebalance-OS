---
description: Refresh the ask-self RAG index for this repo
argument-hint: "[--mode all|docs|code] [--no-prs] [...ingest flags]"
---

Run an ask-self (re)ingest of the current codebase to refresh the RAG index.

As of v0.5, the index is **revision-aware**: doc files ingest additively
(history is preserved across runs) and code files ingest in overwrite mode
(working tree wins). Re-ingesting an unchanged repo is a near-instant no-op —
the planner dedupes against the existing DB before calling the embedding API,
so unchanged chunks are never re-embedded. No flags are required to opt in;
the behavior is the default.

**First run after upgrading to v0.5:** the ingester will detect a pre-v2
index, print `[ask-self] Detected pre-v2 index at <path>; rebuilding...` to
stderr, and rebuild from scratch (one-time cost, matches today's behaviour).
Subsequent ingests run on the new schema and dedupe automatically.

**After a successful ingest, you can:**
- Inspect doc revision history: `ask-self history <path>` (e.g. `ask-self history README.md`).
- Query historical doc content: `ask-self ask "..." --doc-history` or `--as-of YYYY-MM-DD`.
- Prune accumulated history: `ask-self prune-history --older-than 90d` or `--keep-last K --per-path` (add `--dry-run` to preview).

Run the following detection-and-ingest script in a single Bash call. It resolves
the ingest path (stopping at the first matching layout) and runs the ingest with
`--json` so the result is machine-parseable:

```bash
set -e

# Default to --mode all unless the caller already passed --mode.
# An array, not a string: zsh does not word-split unquoted variables, so a
# "--mode all" string would reach the CLI as a single bogus argument.
MODE_ARGS=(--mode all)
case " $ARGUMENTS " in *" --mode "*) MODE_ARGS=() ;; esac

if [ -f scripts/ask-self-ingest.sh ]; then
  # 1. Integrated target repo: use the wrapper (invoked via bash so a
  #    missing executable bit on the wrapper does not break the command).
  bash scripts/ask-self-ingest.sh "${MODE_ARGS[@]}" --json $ARGUMENTS
elif [ -n "$ASK_SELF_PATH" ]; then
  # 2. External install located via ASK_SELF_PATH.
  if [ -f "$ASK_SELF_PATH/ask_self/ask_self_harness.json" ]; then
    HARNESS="$ASK_SELF_PATH/ask_self/ask_self_harness.json"
  else
    HARNESS="$ASK_SELF_PATH/ask_self_harness.json"
  fi
  if [ -n "$ASK_SELF_PYTHON" ]; then
    PY="$ASK_SELF_PYTHON"
  elif [ -x "$ASK_SELF_PATH/.venv/bin/python" ]; then
    PY="$ASK_SELF_PATH/.venv/bin/python"
  else
    PY="python3"
  fi
  "$PY" "$ASK_SELF_PATH/ask_self_ingest.py" --harness-config "$HARNESS" "${MODE_ARGS[@]}" --json $ARGUMENTS
elif [ -f ask_self/ask_self_ingest.py ]; then
  # 3. Portable-mode or vendored copy inside the target repo.
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
  "$PY" ask_self/ask_self_ingest.py --harness-config ask_self/ask_self_harness.json "${MODE_ARGS[@]}" --json $ARGUMENTS
elif [ -f ask_self_ingest.py ]; then
  # 4. The ask-self repo itself.
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
  "$PY" ask_self_ingest.py --harness-config ask_self_harness.json "${MODE_ARGS[@]}" --json $ARGUMENTS
else
  echo "ask-self does not appear to be set up in this repo. See ASK_SELF_INTEGRATION.md for setup." >&2
  exit 1
fi
```

The ingest prints a JSON object to stdout. After the script exits, parse it and summarise:

- On success (`"ok": true`): report `total_chunks`, `db_path`, and `elapsed_seconds`.
  Also report the revision-aware counters from the `revisions` block when present:
  - `new` — new file revisions written (additive doc edits or new files)
  - `refreshed` — unchanged files whose `last_seen_at` was bumped
  - `chunks_embedded` vs `chunks_reused` — embedding cost vs cache reuse
  - `deleted_paths_swept` — overwrite paths removed from disk and pruned
  A second consecutive run on an unchanged repo should show `new: 0`, `chunks_embedded: 0`, and a large `refreshed` count. If those numbers don't match expectation, flag it (it usually means a noisy auto-generated doc is churning).
- On failure (`"ok": false`, or a non-zero exit): report the `error` field plus any warnings.

Do not modify any source files. Only run the ingest command.
