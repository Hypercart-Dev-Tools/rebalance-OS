---
description: Query the ask-self RAG index for this repo
argument-hint: "<your question>"
---

Answer a question by querying this repository's ask-self RAG index.

The user's question is:

$ARGUMENTS

If the question above is empty, ask the user what they would like to know and stop.

Run the detection-and-query script below in a single Bash call. Before running it,
replace `PUT_QUESTION_HERE` on the first line with the user's question as a single
shell-quoted string — quote it correctly for the shell (questions routinely contain
apostrophes, `$`, and quotes; escape as needed). Do not change anything else.

The script resolves the query entry point — stopping at the first matching layout —
and prints the answer:

```bash
Q='PUT_QUESTION_HERE'

set -e

if [ -f scripts/ask-self-query.sh ]; then
  # 1. Integrated target repo: use the wrapper (invoked via bash so a
  #    missing executable bit on the wrapper does not break the command).
  bash scripts/ask-self-query.sh "$Q"
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
  "$PY" "$ASK_SELF_PATH/ask_self_query.py" "$Q" --harness-config "$HARNESS"
elif [ -f ask_self/ask_self_query.py ]; then
  # 3. Portable-mode or vendored copy inside the target repo.
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
  "$PY" ask_self/ask_self_query.py "$Q" --harness-config ask_self/ask_self_harness.json
elif [ -f ask_self_query.py ]; then
  # 4. The ask-self repo itself.
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
  "$PY" ask_self_query.py "$Q" --harness-config ask_self_harness.json
else
  echo "ask-self does not appear to be set up in this repo. See ASK_SELF_INTEGRATION.md for setup." >&2
  exit 1
fi
```

The query prints a human-readable, citation-grounded answer to stdout. Relay that
answer to the user; do not paraphrase away the cited file references.

**Default scope (v0.5+):** queries filter to the current revision of each doc.
If the user's question is historical or comparative ("what did the architecture
plan say last month", "when did we change the auth model"), append `--doc-history`
to widen the candidate pool to additive doc revisions, or `--as-of YYYY-MM-DD`
to time-travel. Inspect what's available with `ask-self history <path>` first if
you're unsure whether the repo has accumulated history for the relevant doc.

If it fails with a `GOOGLE_API_KEY` error: synthesis (and Gemini retrieval) needs a
Gemini API key. Tell the user to make one resolvable (env var, key file, or Secret
Manager), or — if this repo's harness uses a local embedding provider — that the
query can be re-run with `--retrieval-only` for a local, synthesis-free result.

Do not modify any source files. Only run the query command.
