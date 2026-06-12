# /welcome — reference transcript (UX baseline)

Abridged reference session for a fresh machine. The exact wording may vary;
the *shape* is the contract: status render first, one stage at a time,
verification after every step, secrets out of band, skips persisted.

---

**You:** /welcome

**Agent:** Welcome to rebalance. Checking where you are…

```
  [x] Operator config        — temp/rbos.config
   -> Obsidian vault path    — not configured        ← you are here
  ( ) GitHub PAT             — no token found
  ( ) Google Calendar        (optional)
  ( ) Gmail                  (optional)
   !! Project registry       — waiting on vault + PAT
   !! projects.yaml          — waiting on registry
   !! SQLite registry        — waiting on registry
  ( ) Scheduled sync fleet   (optional)
  ( ) First pulse            (optional)
```

Where does your Obsidian vault live? I'll configure it for you.

**You:** ~/Documents/Noel Saw

**Agent:** *(runs `rebalance config set-vault-path "~/Documents/Noel Saw"`,
re-checks status)* Done — vault verified. Next: your GitHub PAT. Create one at
https://github.com/settings/tokens — classic token with the `repo` scope, or
a fine-grained token with Repository access changed from the "Public
repositories" default to All/selected repos — then paste it
**as the tool argument when I call setup_github_token** — don't paste it into
the chat.

**You:** *(provides token via the tool prompt)*

**Agent:** Validated — logged in as `noelsaw1`, `repo` scope confirmed
(private repos visible), stored keyring-first. Google Calendar next (optional) — set it up now, or skip? You
can add it any time by running /welcome again.

**You:** skip for now

**Agent:** *(calls `skip_onboarding_stage("calendar_auth")`)* Skipped and
remembered. Gmail? … *(same offer)* … Now the good part: discovery. *(calls
`run_preflight` — read-only, safe to re-run)*

I found **6 candidates**:

| Candidate | Source | Signal |
|---|---|---|
| acme/site-redesign | remote activity | 12 events, band A |
| acme/api-v2 | remote activity | band B |
| acme/forgotten-spike | **local checkout** | 3 unpushed commits on `main` |
| "Side Quest" | vault note | — |
| … | | |

Which should I promote to monitored? (This is the only step that writes —
everything until you confirm is reversible.)

**You:** the two acme remote ones and the local spike

**Agent:** *(calls `confirm_projects` with the curated list, verifies
registry/projection/DB flipped to done)* Promoted 3 projects. Running the
initial refresh… done, no errors. Graduation: install the scheduled fleet
(daily 06:30 sync + hourly jobs per SCHEDULER.md) and render your first
pulse?

**You:** yes

**Agent:** *(runs the installers, then `pulse_web_sync.sh`, opens
web/pulse.html)*

```
  [x] all 8 required+graduation stages — setup complete
  (s) Google Calendar  (skipped — say the word to add it later)
  (s) Gmail            (skipped)
```

Your first pulse is open. Day-to-day: `rebalance` for the dashboard,
SCHEDULER.md for the fleet runbook, `rebalance doctor` if anything looks off.
Run /welcome whenever you want to add Calendar/Gmail.

---

*Re-entry shape:* on a machine where setup is already complete, /welcome
renders the all-done map, names the skipped optional stages, and offers them
— it never re-runs completed steps.
