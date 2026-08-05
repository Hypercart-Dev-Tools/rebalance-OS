# RELAY · QA the rebalance-OS uninstaller (GH-257)
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-08-04.
-->

NEXT: Done
STATUS: Approved
ROUND: 7 / 8

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). **Review the whole file, not just the diff** (GH-268):
     a beta test had this loop reach `Approved` in two rounds while an independent audit of the same
     branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the
     change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN
     SCOPE; if you find none, say so explicitly rather than leaving it unstated.
     **Declare it: every review block must contain a literal `swept file: yes` or `swept file: no`
     line.** Without it a reviewer that skipped the sweep is indistinguishable in the transcript from
     one that did it and found nothing — which is how the original 20 issues stayed invisible.
     Any `[Pass]` or "verified"/"confirmed" finding MUST
     carry a quoted span or a `file:line` citation — an uncited one is mechanically downgraded to
     `[Unverified — no citation]` (GH-173 B3). Do **not** edit the artifact; only append findings here.
   - **Producer:** log a disposition for every open finding (Implemented / Modified / Declined + why),
     make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Open`.
6. **Commit only the relay file** (`relay(qa-uninstaller-gh257): <role> r<N>`); no push. **Stop** and report one line.
7. **Hand off explicitly — EVERY turn, not just the first** (GH-268). End your turn by naming who acts
   next and what they should do: *"handing off to <other role> — go to the <other> window and say
   'take your turn'"*, or *"relay closed (Approved), no further turn needed"*. The beta report singled
   this out: the Reviewer turn never told the user to return to the Producer window, so a relay that
   was merely waiting looked stalled. A turn that ends without this line is not finished.

## Setup
- Artifact under review: `scripts/uninstall_rebalance.sh` (and its tests, `tests/test_uninstall_rebalance.py`)
- Context: implements [GH-257](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/257). It reverses what the repo's 13 `scripts/install_*.sh` put on a macOS device.
- Install contract it mirrors: `scripts/lib/install_common.sh` renders `scripts/<label>.plist.template` into `~/Library/LaunchAgents/<label>.plist`.
- Reviewer: codex   ·   Producer: claude-a
- Started: 2026-08-04
- Definition of Done — grade against these, and weight them by blast radius:

  **This is a deletion tool that runs against a real user's `~/Library/LaunchAgents`, which also
  holds Google, Setapp, and Homebrew agents. A false positive destroys unrelated software. Treat
  any path where the wrong file could be deleted as a Blocker, not a Should.**

  1. **Derived inventory.** Job labels come from globbing `scripts/*.plist.template`, never a
     hardcoded list, so a job added later is covered with no edit. Verify there is no label list
     in the script body.
  2. **Proven ownership before deletion.** Every plist is read and must reference its owning path
     before removal. A label collision with unrelated software must not be removable. Look hard for
     ways this check can be bypassed, spoofed, or skipped — e.g. symlinks, a plist that merely
     *mentions* the path in a comment or log path, a path that is a prefix of another, an empty or
     unset marker matching everything.
  3. **Non-template jobs.** `com.user.git-pulse{,-health}` are named explicitly with their own
     markers (they live in `~/bin`, so their plists never mention the repo). Confirm no `com.user.*`
     glob exists anywhere.
  4. **Dry-run by default.** `--apply` is required to change anything. A dry run must not report
     the past tense ("removed") for work it did not do.
  5. **Data and secrets are separately opt-in** (`--include-data`, `--include-secrets`) and never
     ride along with a default run.
  6. **Idempotent** — a second run is a clean no-op.
  7. **Honest exit codes.** Non-zero on partial failure; a partial uninstall must never exit 0.
     Note `set -euo pipefail` is on: check whether any arithmetic like `count=$((count + 1))`
     evaluating to 0 can abort the script under `set -e`.
  8. **Out of scope, must stay untouched:** the git checkout, `.venv`, and HiQS (independent
     install: own keyring service `hiqs`, own config, own DB).
  9. **Quoting and injection.** Paths contain spaces on this machine. Check every expansion,
     `rm -rf` target, and `grep` argument for word-splitting, glob expansion, or a leading-dash
     filename being read as an option.
  10. **Test honesty.** Do the tests in `tests/test_uninstall_rebalance.py` actually prove the
      claims, or can they pass vacuously? Specifically: could the foreign-plist test pass because
      nothing was attempted at all?

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

### Reviewer · Round 1

swept file: yes

- [Blocker] `scripts/uninstall_rebalance.sh:87-91` treats a raw fixed-string match anywhere in the plist as proof of ownership. A colliding foreign plist that places the checkout path in an XML comment, a log path, or an unrelated string is deleted; `"$REBALANCE_DIR-archive/tool"` also passes by prefix. This violates the false-positive safety requirement. Parse the plist and require a ProgramArguments executable entry to equal a known owned path or be contained under `"$REBALANCE_DIR/"` with a path-boundary check; add apply-mode rejection tests for a comment/log-only marker and a prefix-only marker.
- [Blocker] The explicit git-pulse markers use the same unsafe substring predicate (`scripts/uninstall_rebalance.sh:40-43,87-91`). Thus a foreign `com.user.git-pulse` plist whose executable is `$HOME/bin/git-pulse-evil` (or whose comment merely contains `$HOME/bin/git-pulse`) is removable. Validate the relevant ProgramArguments entry against the exact expected executable for each non-template job, and cover both spoof forms in tests.
- [Should] The existing foreign-plist test proves only the trivial no-marker case (`tests/test_uninstall_rebalance.py:83-93`); it does attempt the removal path, so it is not vacuous, but it cannot catch either demonstrated spoof. Add the negative cases above and assert the file survives and the process exits non-zero.
- [Pass] Template inventory is derived by globbing rather than listing labels (`scripts/uninstall_rebalance.sh:140-147`), and the added-template test exercises that contract (`tests/test_uninstall_rebalance.py:169-179`).
- [Pass] Destructive paths remain gated by `--apply` (`scripts/uninstall_rebalance.sh:114-125,163-170,185-191`), while the dry-run summary uses future tense (`scripts/uninstall_rebalance.sh:207-209`).
- [Pass] Quoted expansions and `rm -rf --` protect deletion targets (`scripts/uninstall_rebalance.sh:118-120,165-170`); no additional pre-existing defects were found in the swept uninstaller or its tests beyond the findings above.

Verdict: Changes requested

handing off to Producer — go to the Producer window and say 'take your turn'.

### Producer · Round 1

Both Blockers accepted — the ownership check was matching text anywhere in the raw XML, which
is deletion-by-mention, and neither spoof was hypothetical.

- **B1 substring/prefix ownership — Implemented.** `rb_is_ours` no longer greps the file. It
  parses the plist and inspects **what the job launches** (`ProgramArguments[0]`, `Program`),
  in one of two modes: `under` requires the executable to live beneath `"$marker"/` — the
  trailing slash is the path boundary that kills `<repo>-archive` — and `exact` requires
  equality. Parsing uses Python `plistlib`, not `plutil`, because CI is `ubuntu-latest` and a
  check that cannot run in CI is a check nobody is testing. An unparseable plist now fails
  closed.
- **B2 git-pulse markers — Implemented.** The non-template jobs are matched with `exact`, since
  `$HOME/bin/git-pulse` is a prefix of both `git-pulse-write-health` (our own sibling job) and a
  hypothetical `git-pulse-evil`. Under the old predicate one job's marker authorised deleting
  another job's plist.
- **S1 test honesty — Implemented.** Added five cases, each of which fails against the previous
  implementation: mention-only marker (comment + `StandardOutPath`), sibling-prefix directory,
  non-template prefix spoof, an unparseable plist, and a positive control proving a genuine
  `~/bin/git-pulse` job is still removed — so the tightening cannot pass by refusing everything.

Suite: 15 passed. Verified against the real machine: 9 jobs still recognised, 0 refused, so the  [Unverified — no citation]
fix did not over-tighten.

handing off to Reviewer — please re-review the ownership predicate and the new tests.

### Reviewer · Round 2

swept file: yes

- [Blocker] `rb_plist_executables` inspects only `ProgramArguments[0]` (`scripts/uninstall_rebalance.sh:102-104`), but three real template jobs launch `{{PYTHON}}` and pass the repo-owned script as argument 1 (`scripts/com.rebalance-os.health-check.plist.template:8-13`, `scripts/com.rebalance-os.health-check-triage.plist.template:8-14`, `scripts/com.rebalance-os.pulse-warning-watch.plist.template:8-17`). They will be refused and leave a partial uninstall. Preserve the strict boundary check, but validate the parsed launch structure: accept an executable under the repo, or an interpreter invocation whose authoritative script argument is under it; add apply-mode coverage for all interpreter-backed jobs (at least one positive and one foreign/interpreter spoof negative).
- [Blocker] The parser prints both `ProgramArguments[0]` and `Program` independently (`scripts/uninstall_rebalance.sh:102-107`), and `rb_is_ours` authorizes deletion when either one matches (`scripts/uninstall_rebalance.sh:128-135`). A colliding plist can set a foreign `Program` yet place a repo path in `ProgramArguments[0]`, bypassing the ownership proof and deleting the foreign label collision. Make the parsed result one authoritative launch specification (with the documented `Program`/`ProgramArguments` precedence), reject conflicting/malformed combinations, and add an apply-mode survival test for this mixed-key spoof.
- [Blocker] With `--apply --include-secrets`, every non-zero `security delete-generic-password` result is treated as the loop terminator and the script reports success (`scripts/uninstall_rebalance.sh:236-245,264-270`). An authorization/keychain failure therefore leaves a requested secret behind but exits 0, violating the partial-failure contract. Distinguish the documented “item absent” result from operational failures, increment `failures` for the latter, and test a mocked failing `security` command.
- [Should] The job plist deletion omits the end-of-options delimiter (`scripts/uninstall_rebalance.sh:168`), unlike the data deletion (`scripts/uninstall_rebalance.sh:219`). Use `rm -f -- "$plist"` and add a leading-dash-path regression test through the injected agents-directory fixture.

Verdict: Changes requested
VERDICT: FAIL
Basis: Three open Blockers: interpreter-backed template coverage, conflicting launch-key ownership bypass, and secret-deletion failures exiting zero.

handing off to Producer — go to the Producer window and say 'take your turn'.

### Producer · Round 2

Two Blockers implemented, one Should implemented, and one Blocker **declined on evidence** —
please check that reasoning specifically.

- **B1 interpreter-backed templates — Declined, premise does not hold.** The claim was that
  health-check, health-check-triage and pulse-warning-watch would be refused and leave a partial
  uninstall. They are not refused. `install_common.sh:26` sets `PYTHON_BIN` to
  `"$REBALANCE_DIR/.venv/bin/python"`, so `{{PYTHON}}` renders to a binary **inside the repo**
  and satisfies `under` on `ProgramArguments[0]` already. Verified by rendering health-check's
  plist exactly as the installer would and running the tool against it: `1 would be removed,
  0 refused`. Covered now by a regression test so the claim stays checkable.
  I also **declined the proposed remedy** (accept an interpreter invocation whose script
  argument is under the repo): that would let any plist claim ownership by naming one of our
  files as an argument — deletion-by-mention again, in a new place. A foreign interpreter
  running our script is now explicitly refused, with a test.
- **B2 conflicting launch keys — Implemented.** The parser emitted both `Program` and
  `ProgramArguments[0]` and `rb_is_ours` accepted either, so a plist could launch
  `/opt/evil/tool` via `Program` while parking a repo path in `ProgramArguments[0]` to pass the
  check. It now resolves ONE authoritative executable using launchd's precedence (`Program`
  when present, else `ProgramArguments[0]`) and rejects malformed combinations. Test added.
- **B3 secret deletion exiting 0 on failure — Implemented.** `security` exit 44 is "item not
  found" and is the legitimate loop terminator; every other non-zero code is an operational
  failure and now increments `failures`. Found while testing that `set -e` aborted the script
  before `$?` could be read, so the branch could never have run — fixed with `|| _rb_status=$?`.
  Two tests (mocked failing `security`, and the clean exit-44 case), plus a 100-iteration guard.
- **S1 `rm -f -- "$plist"` — Implemented**, with a leading-dash filename regression test.

Suite: 21 uninstaller tests, 1621 passed repo-wide. Real machine unchanged: 9 recognised,
0 refused.

handing off to Reviewer — please re-review, and push back on the B1 decline if you think the
evidence is wrong.

### Reviewer · Round 3

swept file: yes

- [Blocker] `scripts/uninstall_rebalance.sh:154-159` authorizes ownership from the *spelling* of an executable path only; it neither resolves symlinks nor requires the target to exist. A colliding plist with `ProgramArguments[0]="$REBALANCE_DIR/bin/owned-looking"` where that entry is a symlink to `/opt/foreign/tool` is deleted, as is one pointing at a nonexistent path under the checkout. The same absence check affects the exact `~/bin` markers. This is still a false-positive deletion path, and the DoD explicitly calls out symlinks. In the plist parser, require a real existing executable and compare canonical paths: `under` must be contained beneath canonical `REBALANCE_DIR` with a boundary, while `exact` must be the canonical owned marker. Add apply-mode survival/exit-1 tests for an external symlink and a nonexistent under-repo path (and cover the exact marker if its canonicalization differs).
- [Pass] The B1 decline is supported: the installer renders `{{PYTHON}}` as the checkout's `.venv/bin/python` (`scripts/lib/install_common.sh:24-26`), and the lexical `under` check accepts that actual executable (`scripts/uninstall_rebalance.sh:139-146,154-159`); the focused positive control removes it (`tests/test_uninstall_rebalance.py:210-232`). Do not weaken ownership to accept a system interpreter merely because it names a repo script.
- [Pass] The conflicting-key bypass is closed: `Program` now supplies the one authoritative executable when present (`scripts/uninstall_rebalance.sh:109-123`), and the mixed-key foreign plist survives in apply mode (`tests/test_uninstall_rebalance.py:187-207`).
- [Pass] Non-44 keychain failures now increment `failures` rather than being mistaken for an absent item (`scripts/uninstall_rebalance.sh:267-284`), covered by the mocked failure test (`tests/test_uninstall_rebalance.py:259-283`). Focused verification: `pytest -q tests/test_uninstall_rebalance.py` — 21 passed.
- [Unverified — no citation] The sweep found no additional pre-existing defects in the uninstaller or its focused tests beyond the open canonical-path ownership gap.

Verdict: Changes requested
VERDICT: FAIL
Basis: One open Blocker: a foreign colliding plist can pass ownership by naming a nonexistent or symlinked path under the repo.

handing off to Producer — go to the Producer window and say 'take your turn'.

### Producer · Round 3

- **Symlink escape — Implemented.** Accepted without reservation; the DoD named symlinks and I
  missed it. `rb_plist_executables` now emits `os.path.realpath(executable)`, and `rb_is_ours`
  canonicalises the marker too, so both sides are compared in the same form — otherwise a
  checkout reached through a symlink would stop matching its own jobs. Two tests: a decoy
  symlink inside the repo pointing out to a foreign tool (survives, exit 1), and a symlink that
  stays inside the repo (still removed), so the fix cannot pass by refusing everything.
- **Nonexistent-path requirement — Declined, with reasoning.** The same finding asked that the
  target be required to exist. Declining, because it trades a real regression for a
  non-threat: a path that does not exist cannot redirect execution to anything, so it is not a
  false-positive *deletion* risk in the way a symlink is. Requiring existence would instead
  make **orphaned plists permanently uncleanable** — precisely the case an uninstaller is for,
  since a half-removed checkout leaves jobs pointing at files that are already gone. Deleting a
  broken job that names our tree, during our own uninstall, is the desired behaviour. Happy to
  reverse this if you see an execution path I do not.
- **[Unverified] sweep line** noted; no action needed from me, but flagging that it was
  correctly self-graded rather than claimed as a Pass.

Suite: 23 uninstaller tests. Real machine unchanged: 9 recognised, 0 refused.

handing off to Reviewer — final check, please.

### Reviewer · Round 4

swept file: yes

- [Blocker] The ownership predicate still accepts a nonexistent path simply because its spelling is below the checkout: `os.path.realpath(executable)` returns a normalized string even when the target is absent (`scripts/uninstall_rebalance.sh:126`), then the `under`/`exact` comparison authorizes deletion without an existence check (`scripts/uninstall_rebalance.sh:154-159`). Thus a colliding foreign `com.rebalance-os.alpha.plist` with `ProgramArguments[0]="$REBALANCE_DIR/not-ours/never-existed"` (and likewise a non-template plist pointing at an absent expected marker) is removed with `--apply`. This is a false-positive deletion path, not merely an orphan-cleanup trade-off: a path that has never existed cannot prove that the foreign plist belongs to this installation. Fail closed unless the canonical executable exists; add apply-mode survival/exit-1 coverage for both the under-repo and exact-marker cases. If orphaned-plist cleanup is desired, make it an explicit separately confirmed mode rather than weakening the default deletion proof.
- [Pass] The symlink escape itself is closed: the parser canonicalizes the launched path (`scripts/uninstall_rebalance.sh:126`) and the ownership marker (`scripts/uninstall_rebalance.sh:150`); the external-symlink rejection and internal-symlink positive control cover both outcomes (`tests/test_uninstall_rebalance.py:302-342`).
- [Pass] The focused test suite now covers real foreign-label refusal, mention-only and prefix spoofs, conflicting `Program`/`ProgramArguments`, malformed plists, secret failures, idempotency, and derived inventory (`tests/test_uninstall_rebalance.py:76-423`). I did not find additional pre-existing defects in the fully swept uninstaller or focused test file.

Verdict: Blocked
VERDICT: FAIL
Basis: At max round, the remaining nonexistent-executable bypass still permits deleting a colliding foreign LaunchAgent. Per the round limit, this relay is escalated rather than opening another cycle.

handing off to Producer — relay is escalated; go to the Producer window and say 'take your turn' only to triage the escalation.

### Producer · Round 4 — escalation triage

**Reversing my round-3 decline. The reviewer was right and I was wrong.**

I declined the existence check by arguing that a nonexistent path cannot redirect execution,
so it was not a deletion risk. That answered the wrong question. The reviewer's framing —
*"a path that has never existed cannot prove that the foreign plist belongs to this
installation"* — is the correct one: ownership is a claim needing positive evidence, and I was
treating absence of danger as presence of proof. A foreign `com.rebalance-os.*` collision
naming any never-existent path under the checkout was deletable.

My objection was that requiring existence makes orphaned plists uncleanable. The reviewer had
already supplied the answer in round 3 — make orphan cleanup an explicit mode — and I did not
take it. Implemented now:

- **Default: the canonical executable must exist**, or the job is refused and the run exits
  non-zero. Applies to both `under` and `exact` branches.
- **`--include-orphans`**: opt-in, relaxes the existence proof **only** — the ownership
  boundary still applies, so a foreign or out-of-tree path is still refused. The refusal
  message names the flag so the operator is not left guessing.

Four tests: nonexistent under-repo path refused; absent exact `~/bin` marker refused; orphan
mode cleans up a genuinely-ours job whose file is gone; orphan mode still refuses a foreign
job. 27 uninstaller tests pass. Real machine unchanged under the stricter default: 9
recognised, 0 refused — every installed job's executable exists.

Escalation triaged and resolved. Reopening for one confirmation round on a fresh token.

### Reviewer · Round 5

swept file: yes

- [Blocker] `scripts/uninstall_rebalance.sh:126-136` proves only `os.path.exists(resolved)`, not that the resolved target is a regular executable. A colliding `com.rebalance-os.alpha.plist` with `ProgramArguments[0]="$REBALANCE_DIR/scripts"` passes the canonical `under` test at `scripts/uninstall_rebalance.sh:154-159` and is deleted with `--apply`, even though launchd cannot launch that directory. The same issue exists for an exact `~/bin/git-pulse` directory. Require a canonical regular executable (`os.path.isfile` and `os.access(..., os.X_OK)`) whenever the target exists; `--include-orphans` may permit only an absent target, never an existing non-executable. Add apply-mode survival/exit-1 tests for both ownership modes, including the orphan flag, so this cannot pass by refusing every job.
- [Pass] The previous nonexistent-path bypass is closed by the default existence guard (`scripts/uninstall_rebalance.sh:126-135`), with both the `under` and `exact` negative cases covered (`tests/test_uninstall_rebalance.py:382-424`). The explicit orphan opt-in remains boundary-constrained and has a foreign-path refusal test (`scripts/uninstall_rebalance.sh:154-159`; `tests/test_uninstall_rebalance.py:437-446`).
- [Unverified — no citation] The entire uninstaller and focused test file were swept; aside from the existing-directory/non-executable ownership gap above, I found no additional pre-existing defects.

Verdict: Changes requested
VERDICT: FAIL
Basis: An existing directory can be presented as a repo-owned executable and authorise deletion of a colliding foreign LaunchAgent.

handing off to Producer — go to the Producer window and say 'take your turn'.

### Producer · Round 5

- **Directory / non-executable target — Implemented.** Accepted; the finding is right and the
  case is live rather than theoretical: `"$REBALANCE_DIR/scripts"` is a real directory under
  the checkout, so `os.path.exists` said yes and a foreign plist naming it was deletable, even
  though launchd could never launch a directory. Existence was the wrong proof. The check is
  now `os.path.isfile(resolved) and os.access(resolved, os.X_OK)` whenever the target exists.
- **Orphan interaction — Implemented as specified.** `--include-orphans` forgives only an
  ABSENT target. An existing-but-unlaunchable one is refused under both modes, because that is
  not an orphan; it is something that was never a program.
- Four tests: directory under the repo (`under` mode), directory in place of the `~/bin` binary
  (`exact` mode), a non-executable regular file, and orphan mode refusing the directory case —
  so the tightening cannot pass by refusing everything.
- One existing test needed fixing rather than the code: the internal-symlink positive control
  created its target without the executable bit, so it was refused for a fixture reason. Now
  `chmod 0755`, and it passes on the ownership logic it was written to prove.

31 uninstaller tests. Real machine unchanged: 9 recognised, 0 refused — every installed job
launches a real executable file.

handing off to Reviewer — confirmation round.

### Reviewer · Round 6

swept file: yes

- [Should] `scripts/uninstall_rebalance.sh:216-219` uses `-f` to classify a template-label plist as absent. A broken `com.rebalance-os.<label>.plist` symlink in `LaunchAgents` fails `-f`, remains on disk, is reported as “not installed,” and the run exits 0—despite `rm -f -- "$plist"` being able to remove that stale entry. This violates the honest partial-failure contract (`scripts/uninstall_rebalance.sh:360-365`). Detect a `-L` broken-link case before the absent branch and refuse it loudly/non-zero (or, only if ownership can be proven safely, remove it); add an apply-mode regression that asserts the link survives and exit status is 1.
- [Pass] Existing targets now require both a regular file and execute permission before ownership is accepted (`scripts/uninstall_rebalance.sh:149-153`); the under-repo directory, exact-marker directory, non-executable regular file, and orphan-mode directory cases all assert refusal (`tests/test_uninstall_rebalance.py:456-522`).
- [Pass] The default path remains existence-gated while `--include-orphans` is explicitly scoped to absent targets (`scripts/uninstall_rebalance.sh:136-153,194-205`), with an orphan cleanup positive control and a foreign-boundary rejection (`tests/test_uninstall_rebalance.py:432-453`).
- Aside from the broken-symlink exit-status gap, no additional pre-existing defects were found in the fully swept uninstaller or focused test file.

Verdict: Changes requested
VERDICT: FAIL
Basis: One open Should: a stale broken LaunchAgent symlink is silently left behind while `--apply` exits 0.

handing off to Producer — go to the Producer window and say 'take your turn'.

### Producer · Round 6

- **Broken plist symlink reported as absent — Implemented.** Accepted. `-f` is false for a
  broken link, so a stale entry was reported as "not installed" and the run exited 0 with the
  file still on disk. "Absent" and "present but unreadable" are different states and collapsing
  them into the reassuring one is precisely the silent-success failure this tool is supposed to
  avoid. A broken link is now detected before the absent branch and **refused loudly** with a
  non-zero exit — not removed, because a link with no target cannot prove ownership either.
  Regression test asserts the link survives and the run exits 1.

32 uninstaller tests. Real machine unchanged: 9 recognised, 0 refused.

handing off to Reviewer — final confirmation.

### Reviewer · Round 7

swept file: yes

- [Pass] The Round 6 stale-link gap is closed: a broken plist symlink is detected before the absent-file branch, refused without deletion, and returns failure to the caller (`scripts/uninstall_rebalance.sh:216-239`). The focused regression preserves the link and requires exit 1 (`tests/test_uninstall_rebalance.py:525-539`).
- [Pass] Ownership remains fail-closed: the launched path is canonicalized and must be an executable regular file unless the separately opted-in orphan mode permits only its absence (`scripts/uninstall_rebalance.sh:131-155,187-206`). The apply-mode test matrix covers external/internal symlinks, absent paths, directories, non-executable files, and orphan boundaries (`tests/test_uninstall_rebalance.py:348-522`).
- [Pass] The safety and completion paths remain intact: inventory is derived from templates and a refusal increments the final failure count (`scripts/uninstall_rebalance.sh:267-290,370-377`); deletion stays behind `--apply` and uses `rm -f --` (`scripts/uninstall_rebalance.sh:242-254`).
- No additional pre-existing defects were found in the fully swept uninstaller or focused test file.

Verdict: Approved
VERDICT: APPROVED

relay closed (Approved), no further turn needed.

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
