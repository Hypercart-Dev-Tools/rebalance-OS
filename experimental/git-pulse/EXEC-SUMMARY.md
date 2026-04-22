---
name: git-pulse-exec-recap
description: Fill in the TLDR, FOCUS, and OBSERVATIONS placeholders of a Git Pulse Executive Recap so the narrative reads like something an exec or investor would actually want — not another engineering status report. Use this skill whenever the user is editing a Git Pulse recap, asks for an "exec summary" or "executive recap" of git activity, points at a file with `<!-- TLDR: -->`, `<!-- FOCUS: -->`, or `<!-- OBSERVATIONS: -->` placeholders, or complains that previous passes "stayed too technical," "read like changelog," or "kept listing commits." Also trigger when agents (including Claude Code / VS Code agents) have already produced a draft that reproduces commit subjects, SHAs, filenames, or per-commit bullets instead of a narrative — this skill is the corrective pass.
---

# Git Pulse Executive Recap

The Git Pulse recap is a Markdown file with a rich **Appendix** (tables of commits, machines, repos, daily activity) and three prose holes to fill:

- `<!-- TLDR: ... -->` — 1–2 sentences at the top
- `<!-- FOCUS: ... -->` — 2–3 sentences per repo
- `<!-- OBSERVATIONS: ... -->` — 3–5 bullets of patterns and anomalies

The Appendix is the raw material. The prose is the product. **Do not touch the Appendix.** Only replace the three placeholder types, comment delimiters and all.

## The core problem this skill exists to solve

Agents keep writing these sections like commit logs with extra words. They reproduce commit subjects, paste SHAs, list filenames, and enumerate features shipped. The reader does not want that — the Appendix already has it. The reader wants the *meaning* of the week: where did effort concentrate, what shifted, what's worth a second look.

Treat yourself as a chief of staff briefing a busy principal, not a tech lead writing sprint notes.

## Rules, in order of importance

1. **Never name a commit, SHA, file, branch, or function.** If you find yourself typing `` ` `` backticks, stop. Proper nouns are limited to **repo names** and **machine names** (and only when they carry signal).
2. **Describe work in terms of outcomes and themes, not deliverables.** "Hardened the RAG query path and tightened the analyst UI" — not "added smoke-query health check, full-width search input, and Docker setup."
3. **Compress ruthlessly.** TLDR is 1–2 sentences. Each FOCUS is 2–3 sentences, hard stop. OBSERVATIONS is 3–5 bullets, each one line.
4. **Lead with the signal, not the recap.** Start with what matters (concentration, shifts, anomalies), not with a restatement of the window.
5. **Synthesize across commits.** Eight `feat` commits in one repo is a theme, not eight bullets. Name the theme.
6. **Prefer verbs of shape over verbs of motion.** "Consolidated," "shifted focus to," "hardened," "paused" — not "added," "updated," "created."
7. **Numbers earn their place.** Keep a number only if it supports the point. "Two-thirds of the week's commits landed in one repo" is useful; "40 commits, 3 machines, 7 active days" is Appendix.

## TLDR — 1 to 2 sentences

Answer: *If the reader reads nothing else, what should they know?*

Good TLDRs name **where the energy went**, **the dominant mode of work** (building vs. hardening vs. planning vs. drifting), and **any standout signal** (a quiet stretch, a cross-machine push, a repo going dark).

**Weak (what agents keep writing):**
> Over 11 active days, 82 commits were made across 4 repos from 3 machines, with the most active repo being rebalance-OS at 40 commits and the busiest day being April 7 with 20 commits.

That's the Summary block rephrased. Useless.

**Strong:**
> A two-front fortnight: a heavy early-window push on the WordPress RAG pipeline gave way to sustained, multi-machine iteration on rebalance-OS, while the two smaller repos effectively went quiet.

Notice: no numbers, no SHAs, a clear shape ("two-front … gave way to … went quiet").

## FOCUS — 2 to 3 sentences per repo

For each repo, answer: *What was this repo actually about this window, and is anything notable about how the work happened?*

**Do:**
- Name 1–2 themes the commits cluster into. "Deployment hardening and analyst-facing UI polish," not a list of features.
- Flag cross-machine coordination *only if it's signal* — e.g., a spike branch opened on a second machine while main work continued on the primary.
- Note tempo shifts (front-loaded, back-loaded, single-day burst, one-commit-then-silence).

**Don't:**
- List commit subjects, even paraphrased.
- Mention branch names unless a branch itself is the story (e.g., an experimental spike on a separate machine).
- Describe every commit type bucket. If `docs` is 6 of 40, it's probably not the story.

**Weak:**
> rebalance-OS saw 40 commits including 8 feat commits, 7 fix commits, and 6 docs commits. Work included adding an --output flag, canonicalizing git-pulse view output, and addressing DRY audit findings. Three machines contributed.

**Strong:**
> rebalance-OS was the center of gravity, with a front-loaded burst of classifier and aggregator work giving way to a late-window focus on git-pulse itself — output canonicalization, device-id normalization, and an experimental history-collector spike opened on a separate machine. The work pattern suggests tooling-on-tooling: the recap system maturing into something Noel uses on his own workflow.

For a small repo (1–3 commits), the honest answer is usually "this repo was effectively idle" — say that, briefly. Don't pad.

**Strong, for a 1-commit repo:**
> Effectively dormant — a single CI/CD guardrail fix mid-window, no feature work.

## OBSERVATIONS — 3 to 5 bullets

Answer: *What should a reader notice that the Summary stats don't already say?*

Mine the Appendix tables for signal: the Coverage, Machines, Cross-Machine Repos, Daily Activity, and Exceptions sections are where interesting gaps live. Good observations often sound mildly uncomfortable — they point at something slightly off.

**Candidate signal types:**
- **Concentration / gaps:** most work on one repo or machine; multi-day silences; a repo with one commit then nothing.
- **Cross-machine patterns:** spike branches opened on a second machine while main work continues elsewhere (is this intentional? a context-switch cost?).
- **Metadata hygiene:** devices listed in metadata with no commits, missing pulse files, detached-HEAD commits, non-default branches with meaningful work.
- **Commit hygiene:** high ratio of uncategorized "other" commits (conventional-commits discipline slipping); docs-heavy stretches (possibly pre-release polish or possibly avoidance).
- **Tempo:** a single 20-commit day followed by a quiet stretch; weekend vs. weekday pattern; a machine that only shows up for a few hours.

**Weak:**
- There were 82 commits across 4 repos.
- rebalance-OS had the most activity.
- Three machines were used.

**Strong:**
- Two devices appear in the coverage metadata with zero commits and no pulse file — either retired machines or a sync gap worth confirming.
- A third of the cross-machine activity sits on a detached / spike branch, suggesting exploratory work that hasn't yet been triaged back to main.
- The WordPress RAG repo went silent after April 12 despite heavy activity the prior week — natural pause, or blocked?
- "Other" (unprefixed) commits outnumber any single conventional type in the WP repo, pointing at drift in commit-message discipline on that codebase specifically.

Each bullet names a pattern *and* hints at the question a principal would want to ask about it. That's the difference between reporting and briefing.

## Worked example: before and after

**Before (what the VS Code agents produce):**

> ## TLDR
> In the 11-day window from April 7 to April 20, 2026, 82 commits were made across 4 repos from 3 machines, with rebalance-OS being the most active repo at 40 commits.
>
> ### rebalance-OS FOCUS
> rebalance-OS had 40 commits across 3 machines. Key work included feat commits (8) such as saving combined git-pulse reports and canonicalizing git-pulse view output, fix commits (7) including using human-friendly device ids and normalizing device config, and 6 docs commits updating GOOGLE_CALENDAR.md.

**After (what this skill should produce):**

> ## TLDR
> A two-front fortnight: a heavy early-window push on the WordPress RAG pipeline gave way to sustained, multi-machine iteration on rebalance-OS, while the two smaller repos effectively went quiet.
>
> ### rebalance-OS FOCUS
> rebalance-OS was the center of gravity, opening with a burst of classifier and aggregator work and closing on tooling-on-tooling polish of the git-pulse system itself — device-id normalization, output canonicalization, and an experimental history-collector spike opened on a separate machine. The dev-calendar integration also got a sustained documentation pass mid-window, pointing at a feature moving from "working" to "shareable."

## Final check before you hand back

Before returning the filled-in recap, read your own prose once and ask:

- Could this have been written without looking at the Appendix? → If yes, it's too generic. Go back and mine specifics.
- Does any sentence name a file, SHA, branch, or commit subject? → Cut it.
- Is any FOCUS section longer than 3 sentences? → Cut it.
- Does the OBSERVATIONS list just restate the Summary stats? → Replace with actual patterns.
- Would a non-engineer (Noel's partner, an investor, an ops lead) follow this? → If not, de-jargon.

Keep the rest of the file byte-identical. Replace only the three placeholder types, including their `<!-- ... -->` delimiters.