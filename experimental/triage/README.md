# Triage Spike

End-to-end triage CLI: reads any synced GitHub repo from local SQLite, groups open issues + PRs into 6 action buckets, optionally posts the result as a GitHub issue. Edge cases are routed through a review queue so a human or VS Code agent can resolve them without forking the script.

## TL;DR

```bash
# Print to stdout, queue ambiguous cases (default mode)
./experimental/triage/spike.py --repo BinoidCBD/universal-child-theme-oct-2024

# Resolve ambiguities interactively at the terminal
./experimental/triage/spike.py --repo X --ambiguity ask-operator

# After an agent fills in decisions, re-run and post
./experimental/triage/spike.py --repo X \
  --decisions temp/triage/BinoidCBD__universal-child-theme-oct-2024__decisions.jsonl \
  --post-issue
```

## The six buckets

| # | Bucket | Source data | Deterministic? |
|---|---|---|---|
| 1 | 🚀 Merge now (or unblock) | `github_items.state='open' AND item_type='pull_request'` | yes |
| 2 | 🔥 Release blockers | open issues with `milestone_title` set | yes |
| 3 | 👀 Client-visible (Sleuth-linked) | `sleuth_reminders.github_urls_json` ↔ `github_items` | yes |
| 4 | ⚡ Performance — concrete data | open issues whose title starts `perf:` | yes |
| 5 | 🧹 Probable duplicates | open-issue title pairs with jaccard ≥ `--duplicate-threshold` | **no — needs review** |
| 6 | 🤔 PROJECT umbrellas | open issues whose title starts `PROJECT` / `Project:` | **no — needs review** |

Buckets 1–4 produce the same output every run. Buckets 5 and 6 generate review cases that route through the agent-hook contract below.

## Agent hook contract

The script splits ambiguous decisions out of the deterministic path. For each one it produces a stable `id` (e.g. `dup-667-746`, `split-770`) and emits an HTML comment marker into the markdown:

```markdown
<!-- agent-review id=dup-667-746 kind=duplicate items=[667,746] decision=pending source=queued -->
```

Three resolution modes, controlled by `--ambiguity`:

### `--ambiguity queue` (default — best for VS Code agent integration)

For each ambiguity, the script writes one JSONL row to `temp/triage/<repo>__queue.jsonl`:

```json
{
  "id": "dup-667-746",
  "kind": "duplicate",
  "items": [667, 746],
  "suggested": "close #746 as duplicate of #667",
  "rationale": "jaccard=0.85 between titles",
  "repo": "BinoidCBD/universal-child-theme-oct-2024",
  "decision": null,
  "decision_reason": null
}
```

A VS Code agent task (or a human) reads the queue, fills in `decision` and optionally `decision_reason`, writes the records to a `decisions.jsonl` file. Re-run the script with `--decisions decisions.jsonl` and the previously-pending markers become resolved.

The `decision` value is freeform: `accept`, `reject`, `not-duplicate`, `defer`, etc. The renderer just echoes the string into the markdown so the issue reader can see how each case was decided and by whom.

### `--ambiguity ask-operator` (interactive)

The script pauses at each review case and prompts on stderr:

```
--- review case [dup-667-746] (duplicate) ---
  items: [667, 746]
  rationale: jaccard=0.85 between titles
  suggested: close #746 as duplicate of #667
  accept (a) / reject (r) / skip (s)?
```

Best for one-off triage at the terminal. Doesn't write a queue file (decisions go straight into the rendered markdown).

### `--ambiguity auto`

Take the suggested action without asking. The marker still appears in the output (with `decision=accept source=auto`) so a downstream reader can tell the script picked it. Use this for fully unattended re-runs once you trust the heuristics — or for a "preview the worst case" first pass.

## Suggested VS Code agent workflow

1. **Generate the queue:**
   ```bash
   ./experimental/triage/spike.py --repo X --ambiguity queue > /dev/null
   ```
2. **Open the queue file** in VS Code: `temp/triage/<repo>__queue.jsonl`. A VS Code agent task can read this and:
   - For each `kind: "duplicate"` case, fetch both issue bodies via `gh issue view` and decide.
   - For each `kind: "project-needs-split"` case, read the PROJECT issue body, propose 2–4 child issues with acceptance criteria.
   - Write decisions to `temp/triage/<repo>__decisions.jsonl`.
3. **Re-run with decisions and post:**
   ```bash
   ./experimental/triage/spike.py --repo X \
     --decisions temp/triage/X__decisions.jsonl --post-issue
   ```

The `decision` field is a free-form string. The agent is encouraged to add `decision_reason` so the published issue carries provenance ("agent reviewed both bodies; #667 is canonical because it has more recent comments").

## Output artifacts

Everything lands under `temp/triage/` (gitignored via `/temp`):

- `<repo>__triage.md` — the rendered markdown body, identical to what `--post-issue` would publish
- `<repo>__queue.jsonl` — pending review cases (only emitted when `--ambiguity queue` and there are open cases)

`<repo>` is the slash-replaced form, e.g. `BinoidCBD__universal-child-theme-oct-2024`.

## What this isn't

- **Not a CI/CD system.** This is read-only triage. The only mutation is `gh issue create`, gated behind `--post-issue`.
- **Not a replacement for `experimental/close-candidates-action`.** That Action runs on PR-merge events. This CLI runs on demand against any synced repo.
- **Not project-management software.** No assignees, labels, or priorities written. The output is a markdown issue body — humans decide what to do with the buckets.

## Limitations / known cuts

- **Bucket 4 (perf)** trusts the `perf:` title prefix. Issues with measurable data but a different title prefix (e.g. "Reduce slow query for X") will not appear here.
- **Bucket 5** uses Jaccard over a small stopword list. False positives on short titles ("Update X" / "Update Y") are possible — that's exactly why they go through the review queue, not auto-applied.
- **No bucket for "stale issues"** — stale-cutoff logic was out of scope for the first pass. If your repo has a long backlog, add a 7th bucket (1 SQL query + 1 builder function, ~15 lines).
- **`gh` must be installed and authenticated** in the org for `--post-issue` to work. The earlier `rebalance config get-github-token` fallback to `gh auth token` covers the auth side.

## Related

- [`src/rebalance/ingest/github_reconciliation.py`](../../src/rebalance/ingest/github_reconciliation.py) — local SQLite issue↔PR matcher (used elsewhere; not invoked by triage)
- [`experimental/close-candidates-action/`](../close-candidates-action/) — per-PR GitHub Action variant
- [`experimental/freshness/spike.py`](../freshness/spike.py) — sibling read-only dashboard pattern
