# HiQS — Guiding Principles

**What this is.** The tie-breaker. When two reasonable choices both look defensible and the
argument is going in circles, this document decides. It is deliberately opinionated, ordered, and
short enough to actually read during a disagreement.

**Who it is for.** Anyone — human or agent — writing code in this repository, and any reviewer
deciding whether to approve a change. If a reviewer and a builder deadlock, the party who can cite
a principle here wins. If neither can, the disagreement is a real design question and belongs to
the operator, not to another review round.

**Self-contained on purpose.** This repo will be extracted to its own home. Nothing here depends on
the parent repository's documents existing. Where history is cited it is cited as reasoning, not as
a link you must follow.

---

## Part 1 — The four tenets (what HiQS owes the person using it)

These define the product. A change that weakens one of them is not an optimisation, it is a
regression, even when every test passes.

### 01 · ATTESTED
Every signal carries its receipts: **source, author, time, link**. A claim you cannot trace is not
a signal, it is a rumour.

A receipt lives in a **field**, never in prose. Something buried in a free-text `evidence` string
cannot be queried, validated, or asserted non-empty — and a receipt nobody can check is not a
receipt. When a source genuinely does not know a value, the field is `""`. It is never a guess and
never a value invented to fill a column.

### 02 · RANKED
Output is ordered by **what your team owes and is owed**, not by what happened most recently.
Recency is an input to that judgment, never a substitute for it.

Ranking quality is a claim, and every quality claim needs a detector that can fail. A ranker with
no failing test is a ranker nobody has measured.

### 03 · FRESH
Stale signals decay and say so. An old signal presented with the same confidence as a new one is a
lie of omission. Age is surfaced, not silently folded into a score.

### 04 · STRUCTURED
Typed and agent-ready. If the only way to use an answer is to parse prose out of it, it is not
structured — it is a screenshot with extra steps.

---

## Part 2 — The four counterpart invariants (what HiQS owes whoever maintains it)

The tenets above describe the output. They say nothing about how the system fails, what it costs,
or how it grows — and those are exactly where real systems die. These four cover that gap.

### PORTABLE
No hardcoded paths, no machine-specific assumptions, no "works on my laptop." Configuration comes
from a defined place with a defined precedence.

### BOUNDED
Every loop, fetch, and allocation has a ceiling. Every network call has an explicit timeout.
Unbounded means "fine until the day it isn't, and then it takes the machine with it."

### LOUD
**A component that cannot do its job says so.** It does not return an empty result that reads as
success. This is the single most important invariant in this repository, and Part 3 is mostly its
consequences.

### SMALL
The plugin contract stays minimal. Every field a source must populate is a tax on every future
source and on anyone reading the code. Adding to the contract requires showing that the thing
genuinely cannot be expressed outside it.

---

## Part 3 — Precedence, for when principles collide

They do collide. LOUD and SMALL pull against each other constantly. When they do, apply in this
order and stop at the first one that decides it:

1. **Do not destroy data.** No other consideration outranks this.
2. **Do not report success you did not have.** A wrong answer that announces itself beats a wrong
   answer that doesn't.
3. **Make the invariant checkable.** A rule with no test is a wish.
4. **Keep the contract small.** Prefer the change that adds less surface.
5. **Keep it simple to read.** Between two correct designs, take the one a tired person understands
   at 2am.

The order matters. #4 loses to #1 and #2 every time — which is precisely why the attestation
decision below went the way it did, despite adding to the contract.

---

## Part 4 — Standing decisions

Settled. Do not re-litigate these in review; cite them and move on. Each records *why*, because the
reasoning generalises further than the specific rule.

### D1 · Stale beats deleted

When an operation could either leave old data in place or remove data it is not certain about, it
leaves it. Always.

**Why:** the failure modes are not symmetric. Stale data is visible, annoying, and self-corrects on
the next successful run. Deleted data is silent and permanent. A system that occasionally shows you
something out of date is irritating; a system that occasionally eats your notes is unusable.

### D2 · Attestation, never inference

A destructive operation requires a positive statement from the component that did the work, saying
what it actually did. It must never infer that from stored state.

**Why:** stored state is cumulative and has no run identity. A row in a tracking table cannot tell
you whether it was written by the run happening right now or by a run that half-failed last
Tuesday. Treating it as permission to delete means one partial failure authorises the next run to
destroy what it could not read. This is how "successful sync" and "corpus quietly shrinking" become
the same log line.

**Concretely:** `SyncReport.units_ok` carries the units a fetch genuinely completed. The projection
reconciles only within those. Nothing else grants permission to delete.

### D3 · An authorisation may not outlive its run

Attestation is passed in-process, from the operation that earned it to the operation that acts on
it. It is never persisted and read back later.

**Why:** the moment it is stored, it becomes a standing licence to delete, redeemable long after
the conditions that justified it stopped holding.

### D4 · No attestation means no destruction

Every destructive path defaults to doing nothing. A source that does not populate `units_ok` still
works — it inserts and updates, and keeps its stale rows.

**Why:** the alternative default is "absence of an objection authorises deletion," which arms the
destructive path against every un-migrated and third-party source simultaneously. Defaults are what
happens when someone forgets, so the default must be the safe one.

### D5 · Structure is a field, not a parse

If a component needs to know which thing another component's output belongs to, that goes in a
field. Never recover it by splitting a string.

**Why:** id grammars are per-source and change without warning. `Doc.unit` exists because parsing
the unit back out of `<source>:<unit>:<hash>` looked identical and was not — a path may itself
contain a colon, so the parse silently returned the wrong unit, and the wrong rows got pruned. The
parse does not fail. That is what makes it dangerous.

This is STRUCTURED applied inward: the same argument that says don't make callers parse prose says
don't make your own modules parse each other's identifiers.

### D6 · Zero results and failure are different states, and must be distinguishable

"Fetched successfully, found nothing" and "could not fetch" produce identical output unless the
contract keeps them apart. Any interface where they collapse into the same value is broken, however
convenient.

**Why:** everything downstream has to guess, and it will guess wrong in the direction that loses
data. This is the general form of D2 — the attestation channel exists precisely to separate these
two states.

### D7 · A test that scans nothing must fail, not pass

Any check that walks a set and asserts something about it must first assert the set is non-empty.
Scan-nothing and found-nothing are the same green tick otherwise.

**Why:** this class of test rots invisibly. Move the code it inspects, rename a directory, extract
the project to a new repo, and the check keeps passing while covering literally nothing. A gate
that authorises a decision must fail loudly when it can no longer see what it is judging.

### D8 · Verification scans first-party code only

Checks that walk the source tree exclude vendored dependencies, virtualenvs, and caches.

**Why:** third-party code can never satisfy or violate a first-party invariant, so scanning it buys
no coverage — while making the check slow and exposing it to false positives from somebody else's
imports. Measured once: 847 of 862 files scanned were the virtualenv, 78% of total runtime, and
that was before the machine-learning dependencies landed.

### D9 · The contract grows only when the alternative is impossible

Adding a field or a callable to the plugin contract requires demonstrating that the need cannot be
met outside it. "It would be more convenient" is not that demonstration.

**Why:** SMALL is real, and the pressure to add is constant. But note how this resolves against
Part 3: `units_ok` and `Doc.unit` were added because the rule they serve was genuinely
*unimplementable* without them, not merely awkward — the consuming call receives only a database
connection and cannot know what the producing call attempted. A richer design was considered at the
same time (per-unit state enums, run identifiers, a fifth callable) and **rejected**: more rigorous,
but far more machinery than three sources justify. Add the minimum that makes the impossible
possible, and no more.

---

## Part 5 — Inherited anti-patterns

HiQS is a clean-room rebuild of a system that ran for 68 releases. Every pattern below is a real
incident from that system, not a hypothetical. They are collected here because of the lesson that
governs all the others:

> **A principle that lives in a changelog protects exactly one code path — the one that was edited.**
>
> A defect was diagnosed and fixed: a health check read a stale status column instead of the live
> process, so a running daemon reported as failed. Months later a *new* health module reproduced the
> identical misread. The principle was known. The fix had shipped. Nothing stopped a second
> implementation from re-committing it.

So the rule for this entire section: **pin the lesson at the seam, not in the module.** A contract
test that asserts a property of *any* source protects a source written next year by someone who
never read this file. A lesson with no seam-level test is decoration.

---

### A · Silent failure — the system breaks and reports itself healthy

**The meta-pattern.** Nearly every severe incident in the old system was this one wearing different
clothes, and it is why HiQS exists.

*How it showed up:* an email ingest defaulted missing fields to empty strings, so 119 of 124 stored
rows had no sender, subject, or timestamp — and freshness checks passed, because they counted rows
instead of reading them. A retired model started returning 404 and every synthesis silently fell
back to a weaker local one, surfacing only as oddly generic titles. The vector-search dependency
was never actually installed, so search quietly degraded to keyword-only for an unknown length of
time. A config loader silently discarded every key it didn't recognise, so a new setting appeared
to be honoured and did nothing.

**The tells:** a default value substituted for missing data. A fallback path that isn't reported. A
health check that counts rather than inspects. Any `except: pass`.

**The rules:**
- Reject unusable records **at the write boundary**. Do not store a placeholder and hope.
- Count stored and rejected separately. A number that mixes them measures nothing.
- **`unknown` is a first-class state**, distinct from `ok`. A probe that cannot run reports
  `unknown`; it never reports healthy.
- No hidden fallbacks. If the system is running in a degraded mode, that mode is queryable.
- Assert **quality**, not volume. "The index has 40,000 rows" is not evidence the index is good.

### B · Trusting the measurement instead of the thing measured

*How it showed up:* months of "the collectors are unstable" turned out to be six investigations, six
health-check misreads, zero real defects. Memory was measured as resident RAM — which excludes
compressed and swapped pages — so two jobs reported ~30 MB while actually consuming ~46 GB, until
the machine died. A field named `updated_at` was used as a progress signal, when it was bumped by
labels and edits that indicated no movement at all.

**The tells:** health inferred from an exit code rather than from what happened. A metric chosen
because it was easy to read. A timestamp used as a proxy for something it doesn't measure.

**The rules:**
- Derive health from a **record of what actually occurred**, never from exit-code archaeology.
- Record the resource number that would have caught the incident, per run, so attribution is a
  query rather than a re-investigation.
- Separate "when this row was touched" from "when something real happened." Only the second one may
  influence ranking.
- A claim with no record behind it reports `unknown`. Including the system's claims about itself.

### C · Drift from duplication

*How it showed up:* two synthesis surfaces shared no code, so each saw a different subset of
sources and the product's central claim was about two-thirds true. A second web server hand-copied a
subset of the first's routes, and the two drifted twice. A ranker hand-dispatched per source, so
every new signal meant editing it. Five separate UTC formatters. Five home directories baked into
config files.

**The tells:** a comment saying "must stay in sync." A `case`/`if` chain over source names. The
same fact expressed in two places.

**The rules:**
- **One writer per table.** The single most valuable invariant carried over from the old system.
- One ranking, computed once, read by every surface. A surface that re-ranks inline is a bug.
- Registry walk, never a dispatch chain. Adding a source touches no core file.
- One server, one port, one page.

### D · Environment and resource assumptions

*How it showed up:* no memory ceiling until the machine OOM'd. No HTTP timeout and no database busy
timeout, so one stalled request took down every scheduled job. A shell script that worked on a
modern shell broke every run on the OS's stock older one. Hardcoded paths that failed silently at 3
a.m. inside OS-protected folders.

**The tells:** a network call with no timeout. A loop with no ceiling. An absolute path. Assuming
the interpreter, shell, or directory layout of the machine you happen to be on.

**The rules:**
- **Every network call carries an explicit timeout.** No exceptions.
- Bound every loop and allocation.
- No shell in the runtime path. A scheduled job invokes the interpreter directly.
- Verify a write path is usable before depending on it, and fail loudly when it isn't.

### E · Scope and complexity accretion — the machinery becomes the project

*How it showed up:* a release that was meant to remove code added a net 519 lines. Whole releases
disappeared into documentation-hygiene sweeps and status-field corrections that themselves needed
correcting. A fleet of ten scheduled jobs became its own maintenance project, requiring tooling to
manage the tooling.

**The tells:** work whose output is more machinery. A doc that must be updated by hand whenever code
changes. Anything justified as "we'll need it eventually."

**The rules:**
- Keep a **named line-of-code budget** for the core and check it.
- Deleting something is a decision worth recording, with a numeric trigger for re-adding it.
- One scheduled job. A second one is a conversation, not a commit.
- Prefer a test that enforces a property over a document that describes it.

### F · Self-reference and feedback loops

*How it showed up:* the system's own generated output file was ingested as a recent edit and ranked
into its own list. A watermark advanced even when the scan that should have moved it had failed —
so the window that broke repaired itself out of existence, and everything authored during it became
permanently invisible.

**The tells:** output written back into a location the system also reads. Progress state updated
outside the success path.

**The rules:**
- **A watermark advances only after the fetch it describes completed.** On error it stays put and
  the error is recorded. See D2 — this is the same principle as the prune warrant.
- Generated artifacts are excluded from ingest **by construction**, not by a filename filter someone
  has to remember.

---

## Part 6 — Working rules

### R1 · A unit of work must be allowed to write everything its definition requires

If a task's stated deliverable depends on changing a file, that file is in its scope. A task scoped
below its own deliverable cannot be completed by anyone, and the attempt produces confident
workarounds instead of an error.

**Earned the hard way.** Three separate build phases deadlocked on exactly this. Each time the
reviewer correctly refused to approve an unmet deliverable, the builder correctly refused to write
outside its scope, and neither could yield — because both were right. The output was not failure but
something worse: four increasingly elaborate workarounds, each plausible, none correct, all of them
shipped into the file while the tests stayed green.

**The tell:** when a competent implementer keeps producing near-misses for the same requirement,
suspect the scope before you suspect the implementer.

### R2 · A forward-declared contract is strict, and retiring it is someone's job

A test for a not-yet-built capability is marked strictly, so that the day it starts passing, it
fails loudly and forces acknowledgement. Whoever builds the capability retires the marker.

**Why:** a lenient marker would let a live contract sit forever labelled "not yet implemented,"
which is a lie that compounds. The cost is that the marker's retirement must be in scope for the
phase that satisfies it — see R1, which is the same lesson.

### R3 · Read the failure before proposing the fix

Where a review comment cites a file and line, open it. Where it makes a claim about behaviour,
reproduce the behaviour. Do not respond to a summary of a defect with a summary of a fix.

### R4 · Prefer the disagreement you can settle with evidence

When two reviewers disagree, the resolvable version is almost always narrower than the argument
being had. Find the claim that a test could decide, and write that test.

---

## Part 7 — Changing this document

These principles are load-bearing and stable, not immutable. To change one:

1. Say which principle, and what specifically is wrong with it.
2. Give the case that broke it — a real one, with evidence, not a hypothetical.
3. Record the change here with its reasoning, so the next person inherits the argument rather than
   just the conclusion.

A principle overridden once by an explicit, recorded decision is fine. A principle quietly worked
around is a bug in this document — either it is wrong and should be fixed, or it is right and the
workaround is the defect.
