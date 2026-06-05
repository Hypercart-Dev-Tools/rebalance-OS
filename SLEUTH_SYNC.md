# Sleuth reminder sync

`rebalance sleuth-sync` pulls Slack reminders into the local `sleuth_reminders`
SQLite table (consumed by the morning brief, dashboard, and the
`sleuth_sync_reminders` MCP tool).

**Production is read from a published file — no inbound access to the Sleuth
server, no SSH tunnel, no open port.** The Sleuth box pushes its reminders to a
private git repo; rebalance-OS reads the locally-synced copy. (This replaced an
earlier SSH-tunnel approach — if you're looking for `127.0.0.1:12020` or
`install_sleuth_tunnel_scheduler.sh`, they're gone.)

## How it works

```
Sleuth box (systemd timer, every 5 min)
   └─ GET  http://127.0.0.1:2020/.../reminders?format=rebalance   (loopback, on the box)
   └─ PUT  Hypercart-Dev-Tools/rebalance-git-pulse : sync/sleuth/reminders-<ws>.json   (GitHub contents API)
                                                  │
                                        git pull  ▼
rebalance-OS  ──reads──►  ~/git-pulse-sync/sync/sleuth/reminders-<ws>.json   (local clone)
```

- **Publisher** lives in the `sleuth-app` repo under `deploy/reminders-export/`
  (systemd `sleuth-reminders-export.timer`). It only commits when the reminder
  data actually changed.
- **Consumer** points `base_url` at the local file. A `base_url` that is a
  `file://` URL or a plain `/…`/`~/…` path is read directly; an `http(s)://`
  `base_url` still uses the live API (that's how **dev** works — the dev box is
  reachable directly).
- **Freshness:** `refresh_index` / the daily launchd sync does a best-effort
  `git -C <repo> pull --rebase --autostash` before reading, so a read-only device
  self-refreshes. On devices that also push pulses, the pulse sync already pulls.

## Setup on a device

1. **Clone the private export repo** (any path; `~/git-pulse-sync` is the
   convention):
   ```bash
   git clone https://github.com/Hypercart-Dev-Tools/rebalance-git-pulse.git ~/git-pulse-sync
   ```
2. **Point rebalance-OS at the local file** (token is unused for a file source —
   any non-empty placeholder):
   ```bash
   rebalance config set-sleuth \
       --base-url "~/git-pulse-sync/sync/sleuth/reminders-neochrome.json" \
       --token file-source \
       --workspace neochrome
   ```
3. **Verify:**
   ```bash
   rebalance doctor                          # sleuth → configured
   rebalance sleuth-sync --active-only --json | head
   ```

That's it — no SSH key on the prod box, no tunnel, no firewall change. Dev is
unchanged: `--base-url http://<dev-host>:2020 --token <token> --workspace neochrome-dev`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Sleuth reminders file not found: …` | The export repo isn't cloned/pulled on this device | `git clone …/rebalance-git-pulse.git ~/git-pulse-sync` (or `git -C ~/git-pulse-sync pull`) |
| File present but data is stale | The local clone hasn't pulled recently | The daily sync pulls automatically; force with `git -C ~/git-pulse-sync pull`. Confirm the publisher timer is up on the Sleuth box (`systemctl list-timers sleuth-reminders-export.timer`) |
| `Sleuth reminders file is invalid JSON` | Partial write / merge conflict in the clone | `git -C ~/git-pulse-sync status`; resolve, then re-pull |
| Want the live API instead (dev/debug) | — | `rebalance config set-sleuth --base-url http://<host>:2020 --token <token> --workspace <ws>` |

## Related

- `sleuth-app` repo → `deploy/reminders-export/` — the publisher (script + systemd units + README)
- `UPGRADE.md` — full credential migration for a device
