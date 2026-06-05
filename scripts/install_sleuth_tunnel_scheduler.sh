#!/bin/bash
# Install (or reinstall) the Sleuth Web API SSH tunnel as a launchd agent.
#
# What this does:
#   1. Resolves the prod SSH host and key (from flags / env / your local secrets),
#      then renders com.rebalance-os.sleuth-tunnel.plist.template (substituting
#      {{REBALANCE_DIR}}, {{SLEUTH_PROD_HOST}}, {{SSH_KEY}}) into ~/Library/LaunchAgents/.
#   2. Loads it so macOS keeps a persistent SSH port-forward
#      127.0.0.1:12020 -> prod 127.0.0.1:2020 (the prod API port is firewalled).
#
# WHY: `rebalance sleuth-sync --env production` (and the daily launchd job) talk to
# http://127.0.0.1:12020. Without this tunnel they fail with ECONNREFUSED on
# 127.0.0.1:12020 — that's a missing tunnel, NOT a bad credential.
#
# PREREQUISITE (STEP 0) — key-based SSH (launchd cannot answer a password prompt):
#   The public half of THIS box's SSH key must be in /root/.ssh/authorized_keys on
#   the prod box. A fresh box is NOT authorized until you do this once, and the
#   preflight below will refuse to install until it passes. One-time setup, run on
#   the box you're installing on (substitute your key if not id_ed25519):
#     ssh-copy-id -i ~/.ssh/<key>.pub root@<prod-host>      # prompts for the root password once
#     ssh -i ~/.ssh/<key> root@<prod-host> 'echo ok'        # must print ok with NO prompt
#   No id_ed25519? This installer auto-detects the sole keypair in ~/.ssh (e.g. a
#   box whose only key is google_compute_engine) — just authorize that one.
#
# Key resolution order:  --key  >  ~/.ssh/id_ed25519  >  the only keypair in ~/.ssh
# Host resolution order (first hit wins; never committed to this public repo):
#   1. --host <ip-or-name>
#   2. $SLEUTH_PROD_HOST
#   3. SLEUTH_PROD_HOST in ~/secrets/sleuth/vultr-sleuth-production.env
#
# Usage:
#   bash scripts/install_sleuth_tunnel_scheduler.sh
#   bash scripts/install_sleuth_tunnel_scheduler.sh --host 203.0.113.10 --key ~/.ssh/google_compute_engine
#
# Uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.rebalance-os.sleuth-tunnel.plist
#   rm ~/Library/LaunchAgents/com.rebalance-os.sleuth-tunnel.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REBALANCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_TEMPLATE="$SCRIPT_DIR/com.rebalance-os.sleuth-tunnel.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/com.rebalance-os.sleuth-tunnel.plist"
SECRETS_ENV="$HOME/secrets/sleuth/vultr-sleuth-production.env"

SSH_HOST=""
SSH_KEY_EXPLICIT=""

while [ $# -gt 0 ]; do
    case "$1" in
        --host) SSH_HOST="$2"; shift 2 ;;
        --key)  SSH_KEY_EXPLICIT="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

# Resolve the SSH key: explicit --key wins; else the conventional id_ed25519; else
# auto-detect the sole keypair in ~/.ssh (a private key with a sibling .pub). This
# makes the common single-key box — e.g. one that only has google_compute_engine —
# "just work" without forcing --key. Multiple keys => ask the user to choose.
if [ -n "$SSH_KEY_EXPLICIT" ]; then
    SSH_KEY="$SSH_KEY_EXPLICIT"
elif [ -f "$HOME/.ssh/id_ed25519" ]; then
    SSH_KEY="$HOME/.ssh/id_ed25519"
else
    CANDIDATES=()
    for PUB in "$HOME"/.ssh/*.pub; do
        [ -e "$PUB" ] || continue            # no .pub files -> glob stays literal
        PRIV="${PUB%.pub}"
        [ -f "$PRIV" ] || continue           # only count keys that have a private half
        CANDIDATES+=("$PRIV")
    done
    if [ "${#CANDIDATES[@]}" -eq 1 ]; then
        SSH_KEY="${CANDIDATES[0]}"
        echo "  Auto-detected SSH key: $SSH_KEY"
    elif [ "${#CANDIDATES[@]}" -eq 0 ]; then
        echo "ERROR: no SSH keypair found in ~/.ssh. Generate one (ssh-keygen -t ed25519)" >&2
        echo "       and authorize it on the prod box, or pass --key <path>." >&2
        exit 1
    else
        echo "ERROR: multiple SSH keys found — pass --key to choose one:" >&2
        printf '         %s\n' "${CANDIDATES[@]}" >&2
        exit 1
    fi
fi

# Resolve host: flag > env > local secrets file.
if [ -z "$SSH_HOST" ]; then SSH_HOST="${SLEUTH_PROD_HOST:-}"; fi
if [ -z "$SSH_HOST" ] && [ -f "$SECRETS_ENV" ]; then
    SSH_HOST="$(grep -E '^SLEUTH_PROD_HOST=' "$SECRETS_ENV" | head -1 | cut -d= -f2- | tr -d '"' )"
fi
if [ -z "$SSH_HOST" ]; then
    echo "ERROR: prod host not found. Pass --host, set \$SLEUTH_PROD_HOST, or add" >&2
    echo "       SLEUTH_PROD_HOST=... to $SECRETS_ENV" >&2
    exit 1
fi
if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: SSH key not found at $SSH_KEY (pass --key)." >&2
    exit 1
fi

echo "Installing Sleuth API tunnel launchd agent..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"
echo "  host=$SSH_HOST  key=$SSH_KEY"

# Preflight: keyless SSH must work, or launchd can never bring the tunnel up.
echo "  Verifying keyless SSH..."
if ! ssh -i "$SSH_KEY" -o BatchMode=yes -o ConnectTimeout=10 \
        -o StrictHostKeyChecking=accept-new "root@$SSH_HOST" 'echo ok' 2>/dev/null | grep -q '^ok$'; then
    echo "ERROR: keyless SSH to root@$SSH_HOST failed." >&2
    echo "       Add the public half of $SSH_KEY to the server's authorized_keys first:" >&2
    echo "         ssh-copy-id -i ${SSH_KEY}.pub root@$SSH_HOST" >&2
    exit 1
fi

if launchctl list | grep -q "com.rebalance-os.sleuth-tunnel"; then
    echo "  Unloading existing tunnel agent..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

mkdir -p "$REBALANCE_DIR/temp/logs"

ESCAPED_DIR=$(printf '%s\n' "$REBALANCE_DIR" | sed 's/[\/&]/\\&/g')
ESCAPED_KEY=$(printf '%s\n' "$SSH_KEY"       | sed 's/[\/&]/\\&/g')
ESCAPED_HOST=$(printf '%s\n' "$SSH_HOST"     | sed 's/[\/&]/\\&/g')
sed -e "s/{{REBALANCE_DIR}}/$ESCAPED_DIR/g" \
    -e "s/{{SSH_KEY}}/$ESCAPED_KEY/g" \
    -e "s/{{SLEUTH_PROD_HOST}}/$ESCAPED_HOST/g" \
    "$PLIST_TEMPLATE" > "$PLIST_DEST"
echo "  Rendered plist to $PLIST_DEST"

launchctl load "$PLIST_DEST"
echo "  Loaded tunnel agent"

# Give the forward a moment to come up, then confirm the local port answers.
sleep 3
if nc -z 127.0.0.1 12020 2>/dev/null; then
    echo "  ✓ 127.0.0.1:12020 is now listening — tunnel is up."
else
    echo "  ⚠ 127.0.0.1:12020 not answering yet; check logs (it may still be connecting)." >&2
fi

echo
echo "Done! The tunnel will reconnect automatically and persist across logins."
echo
echo "Commands:"
echo "  Check status:  launchctl list | grep sleuth-tunnel"
echo "  Probe port:    nc -z 127.0.0.1 12020 && echo up || echo down"
echo "  View logs:     cat $REBALANCE_DIR/temp/logs/sleuth_tunnel_stderr.log"
echo "  Sync now:      rebalance sleuth-sync --env production --json | head -20"
echo "  Uninstall:     launchctl unload $PLIST_DEST && rm $PLIST_DEST"
