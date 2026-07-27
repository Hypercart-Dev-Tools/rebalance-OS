---
name: unlock-suite
description: >
  Cross-repo issue triage across a suite of interdependent repos — by default PDDA, XYZ
  (xyz-3-agents-swarm), and Rebalance (rebalance-OS) — answering ONE question: which open
  issues, if closed first, would most unblock reliable use of the whole suite? Builds a
  blocker/hub graph from open-issue cross-references, clusters issues that share a root cause,
  cross-checks every signal against GitHub ground truth before trusting it, and returns a
  tiered shortlist with evidence. Read-only: it never edits code, never closes issues, never
  pushes. Trigger on "/unlock-suite", "what should I fix first across the repos", "which issues
  unblock the most", "cross-repo triage", "what's blocking the suite".
---

# unlock-suite — what to fix first across a repo suite

Some repos depend on each other, so a defect in shared substrate taxes everything downstream.
"Most open issues" and "most urgent issue" are both the wrong question. The right one is
**which fix unblocks the most other work**.

This skill is read-only. It reports; it never edits, closes, or pushes.

## Repo set

Pass any repos you want compared: `/unlock-suite <owner/repo> <owner/repo> ...`.

With no arguments, defaults to the three interdependent repos on this machine:

| Repo | Role in the suite |
|---|---|
| `Hypercart-Dev-Tools/pdda` | doc-governance lifecycle both other repos follow |
| `Claude-AI-Tools-Ventura-County/xyz-3-agents-swarm` | relay/marathon harness that reviews work in the other two |
| `Hypercart-Dev-Tools/rebalance-OS` | signal layer that decides what to work on |

Nothing below is specific to those three. The only assumptions are that the repos are related,
reachable via `gh`, and use issues. **Step 1 and Step 2 additionally assume the Rebalance MCP
tools are available — skip them without comment if they are not**, and rely on Steps 3–5, which
need only `gh`.

When the caller supplies repos, work out each one's role in the suite from its README and issue
content rather than assuming; the role assignment is what makes Step 4's "is this shared
substrate?" judgement possible. Everything is per-repo except Step 4, which is deliberately
cross-repo.

## Step 0 — Preconditions

`gh` **must run un-sandboxed** (`dangerouslyDisableSandbox: true`) — a sandboxed `gh` fails on the
keyring and reads as broken auth. Confirm with `gh auth status` before concluding anything.

## Step 1 — Read the cached ranking, but do not lead with it

```
mcp__rebalance__get_next_actions
```

This is the persisted HiQS "what's next" verdict. **It answers a different question than this
skill.** It is day-level and person-level (calendar blocks, Sleuth reminders, health issues), and
it is a *cache* — check `computed_at`. If it predates today's activity it cannot know about
recent issues, and issues filed hours ago always score low regardless of importance.

Use it for context and for anything time-boxed (a deadline today outranks any structural fix).
Do not use it as the answer.

## Step 2 — Activity and idleness

```
mcp__rebalance__github_balance(since_days=30)
```

Gives commits / PRs / issues per project and an `is_idle` flag. Read it as *where effort is
going*, not as *what is finishing*.

> **Known defect — see rebalance-OS#214.** `prs_merged` is `0` for every project because the
> event classifier matches an action GitHub does not send. Until that lands, this tool cannot
> see completed work at all. **Do not report merge throughput from it.** Get merges from GitHub
> directly (Step 5).

## Step 3 — Build the blocker/hub graph (the core of the skill)

Semantic search is a poor fit here — the index is dominated by commit and PR text, and
dependency language ("blocked by", "prerequisite") returns closed PRs at low similarity. Go
straight to the open-issue graph and count references.

For each repo, dump open issues with bodies **and comments**, then count how many *other open*
issues reference each one. An issue many others point at is a hub; hubs are blocker candidates.

```bash
gh issue list --repo "$R" --state open --limit 400 \
   --json number,title,body,labels,createdAt,comments > "open-$name.json"
```

```python
import json, re, collections
data = json.load(open(f"open-{name}.json"))
open_nums = {d["number"] for d in data}
ref = collections.Counter()
for d in data:
    text = (d.get("body") or "") + " ".join(c.get("body", "") for c in (d.get("comments") or []))
    for m in re.findall(r"#(\d+)", text):
        n = int(m)
        if n in open_nums and n != d["number"]:
            ref[n] += 1
```

Rank by `ref`, and also list the oldest open issues (carrying cost).

**Two traps that will bite you:**

- `--json comments` returns an **array of comment objects**, not a count. `sort_by(-.comments)`
  fails with `cannot negate: array`. Use `(.comments | length)` in jq, or do the work in Python
  as above.
- Reference count finds **discussed** issues, which correlates with but is not identical to
  **blocking**. Say so in the output.

### Discard standing reference documents

The highest-scoring issues are often long-lived results/efficacy/tracker reports that everything
cites for context — they are not work. Read the title and body of every top hub before ranking
it; drop the ones that are reference material and say why you dropped them.

## Step 4 — Cluster by root cause, across repos

This is where the leverage is. Several open issues frequently describe **one** underlying defect.
Closing the cause closes the cluster.

Look for shared vocabulary in titles and bodies — a common file, a common subsystem, a common
failure mode. Give the cluster one name and count it as one unit of work, not N.

Then ask the cross-repo question explicitly: **does this cluster sit in shared substrate?** A
harness or governance defect that both other repos route through outranks a bigger defect that
is contained inside one repo.

## Step 5 — Verify before you rank (do not skip)

Every candidate gets checked against ground truth before it reaches the output. Three checks that
have each caught a wrong conclusion:

1. **Is the "fixed" issue actually fixed?** A ROADMAP or comment may record a fix as landed on a
   branch while the issue is still open and the branch never merged. Check
   `gh issue view <n> --json state` and `git branch -a | rg <n>` before counting it as work.
2. **Does the signal match GitHub?** When a metric looks impossible (all zeros, everything idle),
   test it directly rather than reporting it:
   ```bash
   gh pr list --repo "$R" --state merged --limit 300 --json mergedAt \
     -q '[.[] | select(.mergedAt > "<cutoff>")] | length'
   ```
   This is exactly how #214 was found — `github_balance` said 0 merged PRs while GitHub had 139.
   A signal that disagrees with reality is itself a finding worth reporting.
3. **Is a red default branch involved?** If the branch that receives all work has failing tests
   or no CI, that outranks most feature work, because it makes every other green result
   meaningless. Check for open issues about failing tests on `development`/`main`.

## Step 6 — Report

Tier the shortlist by *what it unblocks*, not by severity:

- **Tier 1 — shared machinery.** Fixes that unblock work in more than one repo. Usually a
  root-cause cluster in whichever repo the others route their tooling or process through.
- **Tier 2 — signal trust.** Defects that make the data lie. Anything here poisons the ranking
  that decides what to work on next, so it compounds.
- **Tier 3 — cheap, disproportionate friction.** One-line fixes for "works in one session, not
  another" bugs. Low effort, high daily tax.

For each item give: repo + issue number, hub score / cluster size, one sentence on **what it
unblocks**, and the evidence (a quoted line, a count, a file:line). No item ships without evidence.

Close with an **"if you do one thing"** pick and state your limits plainly — what the method
cannot see, and which conclusions rest on a small sample.

## Guardrails

- **Read-only.** Never edit code, close or relabel issues, comment, or push. If the run surfaces
  a new defect worth filing, say so and let the operator decide.
- **Never invent a dependency.** Only claim A blocks B when a body or comment says so, or the
  code makes it structurally true. A plausible-sounding dependency graph is worse than a shorter
  honest one.
- **Report cache staleness.** Always print `computed_at` from Step 1 next to any claim derived
  from it.
- **Say what you dropped.** Filtered hubs, capped lists, and repos you skipped get one line each.
  A silent cap reads as full coverage.

## Environment notes (macOS, this machine)

- There is **no `timeout` binary** — `/usr/bin/timeout` does not exist and a command using it
  fails with "command not found" and *empty output*, which reads exactly like a clean result.
  Use `gtimeout` if present, or bound work another way. This produced a false "no references
  found" conclusion once.
- Prefer `rg` over `grep -r` for repo-wide searches; a `grep -r` over the dev tree can exceed a
  two-minute tool timeout.
- The `rtk` shell hook can rewrite/summarise `ps` and `grep` output. For anything parsed, call
  `/bin/ps` directly or do the parsing in Python.
