# RELAY · QA the rebalance-OS uninstaller (GH-257)
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-08-04.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 3 / 4

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
   set `STATUS: Escalated`.
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

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
