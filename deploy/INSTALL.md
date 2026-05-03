# Deploying the rebalance-os activity dashboard on Vultr

The dashboard runs alongside Production Sleuth on the same Vultr host:

| Service                | Port | Stack         |
|------------------------|------|---------------|
| sleuth-app             | 2020 | Node / Bolt   |
| **rebalance-web** (new)| 2030 | Python / FastAPI |

The two are independent systemd units. Sleuth is not touched.

---

## 1. One-time host setup

```bash
ssh root@<vultr-host>

# Code checkout
git clone https://github.com/hypercart-dev-tools/rebalance-os.git /root/rebalance-os
cd /root/rebalance-os

# Python venv with the web extra
python3.12 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[web]"

# DB + pulse-mirror dirs (matches systemd ReadWritePaths)
mkdir -p /var/lib/rbos-web

# Pulse mirror — the same private repo each Mac pushes into.
# Replace <pulse-repo-ssh> with the SSH URL of the rebalance-git-pulse repo.
git clone <pulse-repo-ssh> /root/rebalance-pulse-mirror
```

## 2. Runtime env file

```bash
cp deploy/rebalance-web.env.example /root/rebalance-os/.env.runtime
chmod 600 /root/rebalance-os/.env.runtime
$EDITOR /root/rebalance-os/.env.runtime   # paste GITHUB_TOKEN, optional BASIC_AUTH_*
```

## 3. Install systemd units

```bash
install -m 0644 deploy/rebalance-web.service          /etc/systemd/system/
install -m 0644 deploy/rebalance-web-pull.service     /etc/systemd/system/
install -m 0644 deploy/rebalance-web-pull.timer       /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now rebalance-web.service
systemctl enable --now rebalance-web-pull.timer
```

## 4. Smoke test

```bash
systemctl status rebalance-web                   # should be active (running)
systemctl status rebalance-web-pull.timer        # should be active (waiting)
curl -s http://127.0.0.1:2030/api/health | jq

# After ~10 min (or POST /api/refresh), verify activity rows:
curl -s "http://127.0.0.1:2030/api/activity?since=24h" | jq '.count, .rows[0]'
```

## 5. Expose to your browser

Pick **one** of:

- **Tailscale** (simplest): `tailscale serve https / http://127.0.0.1:2030`
- **nginx**: reverse-proxy `dashboard.<your-domain>` to `127.0.0.1:2030` with
  Let's Encrypt + HTTP basic auth (set `BASIC_AUTH_USER`/`PASS` in
  `.env.runtime` so FastAPI also requires creds).

Sleuth on `:2020` is not affected — it keeps its own bearer-token API.

## 6. Updating

```bash
ssh root@<vultr-host>
cd /root/rebalance-os
git pull
.venv/bin/pip install -e ".[web]"
systemctl restart rebalance-web
```

## 7. Logs

```bash
journalctl -u rebalance-web -f
journalctl -u rebalance-web-pull -n 50
```

## 8. Rolling back

```bash
systemctl disable --now rebalance-web rebalance-web-pull.timer
rm /etc/systemd/system/rebalance-web*.service /etc/systemd/system/rebalance-web*.timer
systemctl daemon-reload
```
