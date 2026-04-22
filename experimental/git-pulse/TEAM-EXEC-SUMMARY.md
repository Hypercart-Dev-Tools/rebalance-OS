---
name: git-pulse-team-recap
description: Fill in the TLDR, FOCUS, and OBSERVATIONS placeholders of a Git Pulse Team Recap — an exec-style summary of a remote repo covering everyone's activity, not just the user's. Use this skill whenever editing a team recap file with `<!-- TLDR: -->`, `<!-- FOCUS: -->`, or `<!-- OBSERVATIONS: -->` placeholders, or when asked for a "team exec summary" / "team recap" / "what did the team ship this week" of GitHub activity. Also trigger when agents have already produced a draft that reproduces commit SHAs, PR numbers, or per-commit bullets — this skill is the corrective pass.
---

# Git Pulse Team Executive Recap

This is the team-facing sibling of `EXEC-SUMMARY.md`. The recap lists everyone's commits and PRs on the target repo(s) in a window. You are rewriting the prose so it reads like a chief-of-staff briefing on team output — not a changelog, not a person-by-person CV.

The file has a rich **Appendix** (Contributors Table, Repos Table, Daily Activity, Recent Activity, Exceptions). That's the raw material. The prose is the product. **Do not touch the Appendix.** Only replace the three placeholder types, comment delimiters and all.

## Core rules (shared with the personal recap)

1. **Never name a commit SHA, PR number, branch, file, or function.** If you're typing `` ` `` backticks or `#123`, stop. The only proper nouns allowed are **repo names** and **contributor handles** (`@login`) — and only when they carry signal.
2. **Describe work in terms of outcomes and themes, not deliverables.** "Hardened the deployment pipeline and reviewed two API-surface changes" — not a list of commits and PR titles.
3. **Compress ruthlessly.** TLDR is 1–2 sentences. Each FOCUS is 2–3 sentences, hard stop. OBSERVATIONS is 3–5 bullets, each one line.
4. **Lead with the signal.** Start with what matters (concentration, shifts, anomalies), not a restatement of the window.
5. **Synthesize across events.** Five `feat` commits and a PR on one repo is *a focus*, not six bullets. Name it.
6. **Prefer verbs of shape over verbs of motion.** "Drove," "split between," "reviewed," "paused," "backed up" — not "added," "created," "opened."
7. **Numbers earn their place.** Keep a number only if it supports the point. "Two thirds of the team's PR throughput came from one person" is useful; "15 commits across 2 repos" is Appendix.

## TLDR — 1 to 2 sentences

Answer: *If the reader reads nothing else, what should they know about this team this window?*

Good TLDRs name **where energy went** (which people and/or repos concentrated the work), **the dominant mode** (shipping features, reviewing, hardening, onboarding, drifting), and **any standout signal** (a quiet stretch, a bus-factor risk, a sudden newcomer, a PR-cadence shift).

**Weak:**
> Over 11 active days, the team made 82 commits and opened 12 PRs across 4 repos, with @alice being the most active contributor.

**Strong:**
> A lopsided week anchored on `repo-one`, where @alice and @bob drove most of the feature work while four others made minor, scattered touches. PR cadence stayed unusually low — most shipping went direct to main.

Notice: no numbers, named shape ("lopsided... anchored on... minor, scattered... unusually low"), and a concrete pattern the reader can act on.

## FOCUS — 2 to 3 sentences per contributor

Each FOCUS block sits under a `### @login` header. Answer: *What is this person actually working on, and what's the shape of their contribution?*

The `@login` in the header is the subject of the whole block — you may refer to them by handle inside the FOCUS if it reads naturally, but you don't have to.

**Do:**
- Name 1–2 themes across their repos (e.g., "split between feature work on `repo-one` and defensive fixes on `repo-two`").
- Flag tempo shifts (single burst day, steady daily, back-loaded, one-and-done).
- Note role signals (heavy PR opening = builder, lots of reviews = not visible in this data but infer where possible, direct-to-main pushing = owner/solo).

**Don't:**
- List commit SHAs, PR numbers, or individual titles.
- Describe each repo separately if the person touched many — synthesize into themes.
- Pad if they're a minor contributor. Two sentences is the ceiling, not the floor.

**Weak:**
> @alice made 15 commits and opened 2 PRs in `repo-one`. Her commits included 5 feat, 4 fix, and 6 docs. She also had 3 commits in `repo-two`.

**Strong:**
> @alice drove the widget work on `repo-one` — a sustained daily cadence ending in two merged PRs — and spent the tail of the window hardening error paths in `repo-two`. The docs-heavy mid-week reads as pre-release polish rather than fresh ground.

**Strong, for a minor contributor (1–3 events, no PRs):**
> @carol: a single CI fix in `repo-one` mid-window. No feature work.

## OBSERVATIONS — 3 to 5 bullets

Answer: *What should a reader notice about the team that the Summary stats don't already say?*

Mine the Appendix. Good team observations often sound slightly uncomfortable — they flag risks, gaps, or process smells.

**Candidate signal types:**

- **Bus factor:** one person driving disproportionate activity on a critical repo. "@alice authored 60% of `repo-one`'s activity — intentional ownership or concentration risk?"
- **Handoff / pair patterns:** two contributors' commits interleaving in the same repo on the same days — possible pair work, review relay, or stepped-on-toes.
- **Direct-push vs. PR ratio:** lots of commits land on main without PRs — is that policy or drift?
- **PR cadence:** PRs piled up early or late, or arriving without matching commit follow-through.
- **Silent repos:** a repo in scope with near-zero activity — intentional freeze, blocked, or nobody remembered to push.
- **New contributors:** logins appearing only in the tail of the window — likely onboarding, worth confirming mentorship.
- **Commit hygiene:** high share of uncategorized (non-conventional-commit) messages in one repo only — discipline slipping in that repo specifically.

**Weak:**
- @alice was the most active contributor.
- 4 contributors opened PRs.
- Most work happened in `repo-one`.

**Strong:**
- @alice owns ~60% of `repo-one`'s activity — worth confirming whether this is intentional lead or concentration risk.
- `repo-three` saw two commits from a previously-unseen contributor in the tail of the window — likely onboarding; confirm review coverage.
- PR cadence is 1:8 against commits — most work lands direct to main; if that isn't policy, worth a process review.
- Mid-week zero-activity days (Apr 13, 14) break an otherwise steady cadence — holiday, team offsite, or blocked?

Each bullet names a pattern *and* hints at the question a principal would want asked about it. That's the difference between reporting and briefing.

## Worked example: before and after

**Before (what agents keep producing):**

> ## TLDR
> In the 11-day window from April 7 to April 20, the team made 82 commits and opened 12 PRs across 4 repos, with @alice being the most active with 42 commits.
>
> ### @alice FOCUS
> @alice made 42 commits across `repo-one` and `repo-two`. Her commits included 15 feat, 12 fix, 8 docs, and 7 other. She also opened 2 PRs including #123 Add widget and #124 Fix bug.

**After (what this skill should produce):**

> ## TLDR
> A lopsided fortnight anchored on `repo-one`: @alice and @bob split the feature load while four others made minor, scattered touches across the other repos. PR cadence trailed commit cadence by 8:1 — most work shipped direct to main.
>
> ### @alice FOCUS
> @alice drove the widget work on `repo-one` through a sustained daily cadence, closing the window with two merged PRs and a docs pass that reads as pre-release polish. Her `repo-two` touches were narrower — a pair of defensive fixes, likely shared ownership rather than focus.

## Final check before you hand back

- Could this have been written without looking at the Appendix? → If yes, mine harder.
- Does any sentence name a SHA, PR number, branch, file, or commit title? → Cut it.
- Is any FOCUS section longer than 3 sentences? → Cut it.
- Does OBSERVATIONS just restate contributor counts or the most-active-person bullet? → Replace with real patterns.
- Would a non-engineer (a VP, an investor, an ops lead) follow this? → If not, de-jargon.

Keep the Appendix byte-identical. Replace only the three placeholder types, including their `<!-- ... -->` delimiters.
