# UPGRADE — bring a device onto the keyring credential model

> **Status note (updated 2026-06-21).** The auth-storage hardening **Phases 0–3 have
> landed**: keyring stays the interactive primary, but every launchd fallback now
> lives in the permission-enforced out-of-repo **secret store**
> (`~/.config/rebalance-os/secrets/`, `0600`) — no plaintext secrets in `temp/rbos.config`,
> no pickle OAuth files. This guide reflects that model. Full audit, rationale, and the
> deferred (multi-operator) work:
> [PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md](PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md).

rebalance-OS now stores its external credentials in the **OS keyring**
(macOS Keychain) as the primary, with a **launchd-reachable fallback** for each
(launchd's stripped environment can't read the keychain). This replaces the old
"loose secret files in `~/secrets/`" approach, which caused silent stalls when a
file was missing or in the wrong place.

> **Keyring is per-machine.** It does **not** sync across devices. Each device
> installs its secrets once. This guide is what you run on a device to catch up.

> **DB migrations auto-apply.** After `git pull`, numbered migration files in
> `src/rebalance/ingest/db/migrations/` are applied automatically the first time
> any ingest or collector runs. No manual schema step required.

## Refresh a running device after `git pull` (code · services · apps)

`git pull` only rewrites files on disk. It does **not** touch anything already
running — the editable install's entry points/metadata, the long-lived launchd
daemon (which holds its imported Python modules in memory from the moment it
started), or the compiled macOS `.app` bundles. A device can therefore have the
new code checked out while every *running* surface still executes the old code.
Run the steps below after every pull to bring the live device fully onto new code.

```bash
cd /path/to/rebalance-OS
git pull

# 1. Re-sync the Python runtime — entry points, dependencies, version metadata.
#    Use the same extras you installed with; the macOS default is embeddings+calendar.
#    (An editable install still needs re-running: deps and console-scripts change
#     with new collectors, and the package version metadata is baked at install time.)
.venv/bin/pip install -e ".[embeddings,calendar]"     # Linux/Intel Mac: drop `embeddings`

# 2. Restart the launchd services so they exec the new code.
#    A running Python process never hot-reloads from disk — it keeps the modules it
#    imported at startup. `kickstart -k` stops and respawns a job on the new code.
#    This loop is safe for every job (see the table below); the one it is REQUIRED
#    for is the pulse server.
launchctl list | awk '/com\.rebalance-os\./ {print $3}' | while read -r label; do
  launchctl kickstart -k "gui/$(id -u)/$label" && echo "restarted $label"
done

# 3. Rebuild + reinstall the macOS apps (release build, ad-hoc sign, copy to /Applications).
#    Each app under macOS/Apps/* ships its own make-app.sh that does the full pass.
macOS/Apps/Focus5Float/make-app.sh

# 4. Verify.
.venv/bin/rebalance --version                                    # matches pyproject.toml
.venv/bin/rebalance doctor                                       # all green
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8767/  # 200 = pulse server up
```

### Which services actually need the restart

Only one `com.rebalance-os.*` job runs **continuously**, and it is the one that
serves stale code indefinitely if you don't restart it:

| Label | Type | After a pull |
|---|---|---|
| `com.rebalance-os.pulse-server` | `KeepAlive` daemon — HTTP server on **:8767** that Focus 5 Float and the web pulse read from | **Must** be restarted — it holds its imported modules in memory and never re-execs on its own |

Every other job (`daily-sync`, `github-sync`, `vault-sync`, `pulse-sync`,
`pulse-web-sync`, `pulse-warning-watch`, `git-pulse-daily-synthesis`, the
`obsidian-*` and `health-check*` jobs) is `KeepAlive=false` + `StartCalendarInterval`:
it re-execs from scratch on its **next scheduled tick** and self-heals onto new code
with no action. The kickstart loop in step 2 just makes that immediate instead of
waiting for the next tick — harmless (each runs one cycle early), never required.

> **Restart only the pulse server** (the common case — you changed a collector or a
> render path and want :8767 on it now):
> ```bash
> launchctl kickstart -k "gui/$(id -u)/com.rebalance-os.pulse-server"
> ```

## Credential model (after upgrade)

> This table reflects the **auth-storage hardening (Phases 0–3, landed 2026-06-21)**:
> every launchd fallback now lives in the permission-enforced out-of-repo **secret
> store** — no plaintext in `temp/rbos.config`, no pickle OAuth files. The only
> remaining work is multi-operator/fleet machinery, deferred in the plan.

| Credential | Primary | launchd fallback | Logged on (re)auth |
|---|---|---|---|
| GitHub PAT | keyring | secret store (`~/.config/rebalance-os/secrets/github_token`, `0600`) | `auth_log` `token_set` + `token_meta` |
| Sleuth sync source | keyring | secret store (`~/.config/rebalance-os/secrets/sleuth_web_api`, `0600`) | same |
| Google Calendar OAuth | keyring | secret store JSON (`~/.config/rebalance-os/secrets/google-calendar-oauth`, `0600`) | same |
| Gmail OAuth (oauth mode) | keyring | secret store JSON (`~/.config/rebalance-os/secrets/google-gmail-oauth`, `0600`) | same |
| Figma PAT (opt-in) | keyring | secret store (`~/.config/rebalance-os/secrets/figma_token`, `0600`) | — (not auth-logged; set manually) |

### What changed (auth-storage hardening, 2026-06-21)

- **Secrets left the repo.** GitHub / Figma / Sleuth fallbacks no longer write to
  repo-local `temp/rbos.config`; they live in the secret store. A repo checkout now
  carries **no live credentials** — it can be copied or archived safely.
- **Google OAuth fallback is JSON, not pickle**, in the same secret store. (Pickle is
  code-executing on load; JSON is data-only and inspectable.)
- **Permissions are enforced** — every secret file is `0600`, its directory `0700`;
  `doctor` warns if anything drifts broader.

**What to do on each device (after `git pull`):**

```bash
rebalance config migrate-secrets   # lifts existing secrets out of rbos.config AND
                                   # retires legacy OAuth pickle files → JSON
rebalance doctor                   # expect "repo-local secrets — … no live secrets"
```

`migrate-secrets` is **idempotent** (safe to re-run) and **per-machine** — until a
device runs it, it keeps working via the legacy read fallback, so there is no flag
day and no rush. There is nothing to copy between machines; each device migrates its
own local secrets in place.

Each (re)authorization is recorded in `temp/logs/auth_activity.jsonl` (event
stream) and `temp/logs/token_meta.json` (per-token sidecar with `first_added_at`,
so a credential's lifetime is measurable). The raw token value is never stored in
the sidecar — only a SHA-256 fingerprint.

## Steps (run on each device)

```bash
cd /path/to/rebalance-OS
git pull
.venv/bin/pip install -e ".[embeddings,calendar]"   # run after every pull — deps/entry points change with new collectors
                                                    # (see "Refresh a running device after git pull" above for the full
                                                    #  code + services + apps refresh; the credential steps below are separate)

# 1. Adopt keyring + move secrets out of the repo (both idempotent, safe to re-run):
.venv/bin/rebalance config migrate-to-keyring   # sleuth env file / any legacy → keyring
.venv/bin/rebalance config migrate-secrets       # rbos.config secrets + OAuth pickle → secret store

# 2. GitHub PAT — cannot be auto-migrated (it's a value only you hold).
#    Use the dedicated, NO-EXPIRATION classic PAT (scopes: repo, read:org).
.venv/bin/rebalance config set-github-token ghp_XXXXXXXX

# 3. Sleuth — all devices should use the git-pulse-sync file-source method.
#    If this machine was previously pointed at the Web API, override it now.
git clone https://github.com/Hypercart-Dev-Tools/rebalance-git-pulse.git ~/git-pulse-sync
.venv/bin/rebalance config set-sleuth \
    --base-url "~/git-pulse-sync/sync/sleuth/reminders-neochrome.json" \
    --token file-source \
    --workspace neochrome
#    This reads the published Sleuth export directly from the companion repo —
#    no API auth, tunnel, or public :2020 endpoint. A file:// or local-path
#    base_url is read directly (token unused). Full setup + troubleshooting:
#    SLEUTH_SYNC.md

# 4. Calendar — only if doctor reports "no Calendar OAuth credentials" (no prior OAuth here):
.venv/bin/python scripts/setup_calendar_oauth.py     # opens a browser; writes keyring + JSON fallback in one pass

# 5. Gmail — only if you use oauth mode (autonomous/launchd sync) and doctor
#    reports "no Gmail OAuth credentials". If you drive rebalance from an MCP host
#    instead, skip this and run: rebalance config set-gmail-method mcp
.venv/bin/python scripts/setup_gmail_oauth.py        # opens a browser (gmail.readonly); writes keyring + JSON fallback

# 6. Verify everything is green:
.venv/bin/rebalance doctor
```

A healthy `rebalance doctor` shows, among the checks:

```
 OK  github token       — stored in keyring + secret store (reachable by launchd) · first added Nd ago (classic PAT)
 OK  secret permissions — N secret file(s)/dir(s) at 0600/0700
 OK  repo-local secrets — temp/rbos.config holds no live secrets
 OK  sleuth             — configured (via file source)
 OK  calendar           — OAuth token present (via keyring) · authorized Nd ago
 OK  gmail              — OAuth token present (via keyring)   # or: MCP mode — N messages ingested
```

## Opt-in integrations (per-device, as needed)

### Figma comments (`figma` scope)

Figma ingestion is PAT-gated and disabled by default. The collector skips cleanly
when unconfigured — no doctor warning, no error. To enable it on a device:

```bash
# figma_file_keys is plain (non-secret) config; the PAT goes to the keyring +
# secret store, never the repo. First set the file keys you want to monitor
# (the alphanumeric ID from figma.com/file/<FILE_KEY>/...):
python3 -c "
import json, pathlib
cfg = pathlib.Path('temp/rbos.config')
d = json.loads(cfg.read_text()) if cfg.exists() else {}
d['figma_file_keys'] = ['FILEKEY1', 'FILEKEY2']
cfg.write_text(json.dumps(d, indent=2))
print('file keys written')
"
# Then store the PAT securely — keyring primary + secret-store fallback, never the
# repo (no CLI wrapper yet, so call the setter directly):
.venv/bin/python -c "from rebalance.ingest import config; config.set_figma_token('figd_XXXXXXXXXXXXXXXX')"
```

The Figma collector is `included_in_all=False` — it runs only when explicitly
scoped (`rebalance refresh --scope figma` or the registry scope list includes
`"figma"`). Comments are ingested into `figma_comments` and vectorized into the
unified semantic index.

### External GitHub repo watching

External repos are declared in the project registry (not via a credential). Add
`external: true` to a project block and list its repos under `repos:`. No new
token is required — the existing GitHub PAT covers public repos and any private
repos the PAT can read. External repos enter the canonical watched set and appear
in the pulse "Watched repos" section automatically on the next refresh.

## Embedding job guard (GH-172) — verify on every device

> **Why this matters.** On 2026-07-19 this Mac hard kernel-panicked. Three
> unbounded Python embedding runs stacked to ~90 GB resident on a 68.7 GB
> machine, saturated the VM compressor (74 swapfiles, 100% of segment limit),
> starved `watchdogd` for 90s, and the kernel shot itself. Nothing prevented
> concurrent invocation and nothing aborted before the cliff.

Since GH-172 the two embedding leaves — `embed_chunks` (vault) and
`embed_pending` (semantic) — hold a **single-instance lock** and run under a
**memory ceiling**. The guard sits at the library level, so it applies to *every*
caller: launchd, CLI, MCP tools, and agent- or shell-spawned runs alike. That
last category matters — the run that caused GH-172 was agent-spawned, so
guarding only the launchd wrappers would not have caught it.

**Nothing to install.** The guard ships with the code and is on by default. This
section is verification, not setup.

### Verify it is active on this device

```bash
.venv/bin/python -c "
from rebalance.ingest import _job_guard as g
print('guard module:', g.module_path())
print('locatable   :', g.available())
print('enabled     :', g.enabled())
"
```

Expect `locatable: True` and `enabled: True`. If `locatable` is `False` the
device is embedding **unguarded** — see "Non-editable installs" below.

Confirm both leaves are actually wrapped (this is the regression that GH-174
shipped and GH-172 had to fix — a guard with zero callers):

```bash
.venv/bin/python -m pytest tests/test_job_guard_wiring.py -q
```

### What happens when it trips

| Condition | Behaviour |
|---|---|
| Another embedding run holds the lock | `InstanceConflict` — the second run refuses and exits. **This is the GH-172 fix.** |
| Job exceeds 35% of physical RAM | `MemoryCeilingExceeded` — SIGTERM, then SIGKILL after grace |
| Machine available memory below floor | Refuses to *start* (`preflight`), rather than dying at minute two |
| Guard module missing | Warns loudly on stderr, runs **unguarded** — see below |

A scheduled job that refuses because another run holds the lock is **correct
behaviour**, not a failure: it skips that cycle instead of stacking. Expect to
see this occasionally in `daily-sync`/`github-sync`/`vault-sync` logs.

### Tuning (per device, optional)

| Variable | Default | Purpose |
|---|---|---|
| `REBALANCE_JOB_GUARD` | `1` | Set `0` to disable entirely. **Do not** disable on a machine that runs scheduled embeds. |
| `REBALANCE_JOB_GUARD_MAX_RSS_GB` | 35% of physical RAM | Absolute RSS ceiling for one embedding pass |
| `REBALANCE_JOB_GUARD_ON_CONFLICT` | `refuse` | `replace` SIGTERMs the incumbent and takes over — the "re-run the embeddings" ergonomic |
| `JOB_GUARD_LOCK_DIR` | `~/.cache/rebalance-os/locks` | Lock namespace. Shared across clones **on purpose**: two worktrees running the same job must still collide. |
| `JOB_GUARD_MODULE` | `<repo>/utils/job_guard.py` | Point at a vendored copy on non-editable installs |

On a machine with substantially less RAM than 68 GB, consider setting
`REBALANCE_JOB_GUARD_MAX_RSS_GB` explicitly rather than relying on the fraction.

### Non-editable installs

`utils/job_guard.py` deliberately lives **outside** the Python package, because
it must also run under the system `python3` inside launchd wrappers with no
install step. A normal editable checkout resolves it automatically. If the
package was installed without the repo tree beside it, `locatable` will be
`False` — vendor the file and point at it:

```bash
export JOB_GUARD_MODULE=/path/to/job_guard.py
```

Failing to do so does not break ingest — the guard fails **open** with a warning
so `daily-sync` keeps working — but the device is unprotected against GH-172.

### Peak-memory logging (GH-175) — how the next incident stays attributable

Every guarded run now appends one row to `temp/logs/job_rss.jsonl`, on **every**
exit path — clean, raised, or ceiling-tripped:

```json
{"ts": "2026-07-19T21:34:37-0700", "job": "rebalance-embed", "pid": 57379,
 "peak_rss_gb": 12.4, "total_memory_gb": 64.0, "max_rss_gb": 22.4,
 "tripped_reason": null, "exit_code": 0, "duration_s": 812.3}
```

This exists because GH-172 could not be attributed from the panic log: jetsam
records only the process name `Python`, so three processes at 45.9 / 35.8 /
9.2 GB gave no indication of *which* code path held them. Attribution took
several rounds of artifact forensics and still needed a correction. With this
log, the next incident reads `rebalance-embed peaked at 45.8 GB at 15:38`.

Inspect the heaviest recent runs:

```bash
tail -50 temp/logs/job_rss.jsonl | python3 -c "
import sys, json
rows = [json.loads(l) for l in sys.stdin if l.strip()]
for r in sorted(rows, key=lambda r: -r['peak_rss_gb'])[:10]:
    print(f\"{r['peak_rss_gb']:6.2f} GB  {r['job']:24s} {r['ts']}  trip={r['tripped_reason']}\")
"
```

Override the location with `JOB_GUARD_RSS_LOG`. Writing is best-effort: a
logging failure is swallowed rather than allowed to take down the job it was
only observing.

### Re-render your launchd plists (GH-175) — REQUIRED on existing devices

> **This is the one step in this section that is not automatic.** `git pull`
> updates the plist *templates* in `scripts/`; it does **not** touch the rendered
> plists already installed in `~/Library/LaunchAgents`. Until you re-run the
> installers, your device keeps the old schedule and no `Nice` value.

Two changes landed in the templates:

**1. `Nice=5` on the batch jobs** — `daily-sync`, `github-sync`, `vault-sync`,
`pulse-sync`, `pulse-web-sync`. This is interactive-responsiveness hygiene, **not**
a GH-172 mitigation: that panic came from `kernel_task` compression starving
`watchdogd`, which `Nice` does not affect. The memory protection is the job guard.

**2. A de-collided schedule.** Four jobs previously fired at `:00`. The
`pulse-web-sync` collision in particular was a **correctness** problem, not just
contention — it is a derived read-only stage over what `pulse-sync` writes at
`:00`, so firing in the same minute risked reading half-written state.

| Job | Was | Now |
|---|---|---|
| `pulse-sync` | :00 | :00 (unchanged — hourly anchor) |
| `pulse-warning-watch` | :00 / :15 / :30 / :45 | :07 / :22 / :37 / :52 |
| `pulse-web-sync` | :00 / :30 | :08 / :38 |
| `health-check` | :00 | :10 |
| `health-check-triage` | 8/14/20:00 | 8/14/20:**25** |
| `obsidian-rollover` | 00:00 | 00:**40** |
| `obsidian-daily-sync` | 18:00 | 18:**20** |
| `git-pulse-daily-synthesis` | 18:05 | 18:**30** |

Unchanged: `vault-sync` :15, `github-sync` :45, `daily-sync` 6:30.

> **`obsidian-daily-sync` and `git-pulse-daily-synthesis` must be re-rendered
> together.** They carry an **ordering dependency**: when both destinations are
> configured, the Git Pulse block must land *after* the GH-112 AI Daily Summary
> block. Re-rendering only the first leaves synthesis at 18:05 — 15 minutes
> *before* the job it has to follow — and the Git Pulse block silently lands above
> the AI summary in Obsidian. Nothing errors; the order is just wrong.

Re-render and reload:

Each job has its own installer — there is no single "install everything" script,
so run the one per changed template:

```bash
./scripts/install_scheduler.sh                      # daily-sync           (Nice)
./scripts/install_github_scheduler.sh               # github-sync          (Nice)
./scripts/install_vault_scheduler.sh                # vault-sync           (Nice)
./scripts/install_pulse_scheduler.sh                # pulse-sync           (Nice)
./scripts/install_pulse_web_scheduler.sh            # pulse-web-sync       (Nice + :08/:38)
./scripts/install_pulse_warning_watch_scheduler.sh  # pulse-warning-watch  (:07/:22/:37/:52)
./scripts/install_health_check_scheduler.sh         # health-check         (:10)
./scripts/install_health_check_triage_scheduler.sh  # health-check-triage  (:25)
./scripts/install_obsidian_rollover_scheduler.sh    # obsidian-rollover    (00:40)
./scripts/install_obsidian_daily_sync_scheduler.sh  # obsidian-daily-sync  (18:20)
./scripts/install_git_pulse_daily_synthesis_scheduler.sh  # git-pulse-daily-synthesis (18:30)
```

`pulse-server` is unchanged — no need to re-render it.

> **Two of these fire immediately.** `daily-sync` and `pulse-warning-watch` set
> `RunAtLoad=true`, so re-rendering them kicks off one real run on the spot — a
> full ingest in `daily-sync`'s case. Expected, not a fault, but pick your moment.

> **If `git-pulse-daily-synthesis` was never installed on this device**, that last
> line installs it for the first time rather than re-rendering. It needs a Gemini
> API key and Full Disk Access; skip it if you do not use the Git Pulse summary,
> but then also skip moving `obsidian-daily-sync` — the pair only matters together.

Verify the new schedule and `Nice` took effect:

```bash
/usr/libexec/PlistBuddy -c "Print :Nice" ~/Library/LaunchAgents/com.rebalance-os.daily-sync.plist
/usr/libexec/PlistBuddy -c "Print :StartCalendarInterval" ~/Library/LaunchAgents/com.rebalance-os.health-check.plist
```

Expect `5`, and a `StartCalendarInterval` **array containing** `Minute = 10`:

```
Array {
    Dict {
        Minute = 10
    }
}
```

If `Print :Nice` errors with "Does Not Exist", the plist has not been
re-rendered.

> **Note on scope.** This de-conflicts jobs firing in the same *minute*. It does
> not address run-window *overlap* — `daily-sync` runs ~25–30 minutes from 06:30
> and still spans `github-sync` at :45. That overlap was handled separately by
> GH-131's bounded SQLite retry and is deliberately unchanged.

### Guarding non-Python jobs

`utils/job_guard.py` also works as a wrapper for any command, which is the route
for shell-based jobs:

```bash
python3 utils/job_guard.py --name ask-self-ingest --max-rss-gb 24 -- \
    ./scripts/ask-self-ingest.sh
```

Exit codes: `3` lock conflict, `4` memory ceiling tripped, `143` evicted by a
later `--on-conflict replace` run.

## Notes for agents

- **Never echo a token/secret value** to chat, logs, or commits. This is a
  **public** repo. Print only fingerprints, lengths, statuses.
- `migrate-to-keyring` is **idempotent** — safe to re-run; it reports
  "already in keyring ✓" for anything done.
- The GitHub PAT dying "every few days" is almost always **expiry** or
  **regeneration elsewhere** (a shared PAT regenerated on another device
  invalidates the old value everywhere). Prefer a **no-expiration** PAT, or a
  **separate PAT per machine**. The sidecar `first_added_at` lets you measure the
  exact lifetime if it recurs.
- launchd jobs read the **config/file fallback**, not the keychain — so the set
  commands above intentionally write both. Don't delete the fallbacks.
