#!/usr/bin/env bash
# Give a CI job the host alias "lava-gate": the production server, as the one
# key that install.sh tied to deploy/remote/lava-gate.sh.
#
#   DEPLOY_SSH_KEY=... DEPLOY_KNOWN_HOSTS=... DEPLOY_HOST=... \
#       bash deploy/ci/ssh_setup.sh
#   ssh lava-gate assets-hash
#
# Whatever a job asks over this key, sshd runs the gate, and the gate answers
# assets-hash, assets and deploy and refuses everything else. The host key is
# pinned -- DEPLOY_KNOWN_HOSTS is the line install.sh printed on the server --
# and StrictHostKeyChecking is on, so a machine that only claims to be the
# server gets no tarball and no signature from this key: the job stops at the
# handshake.
set -euo pipefail

fail() { echo "::error title=Gate access::$*"; exit 1; }
[ -n "${DEPLOY_SSH_KEY:-}" ] \
  || fail "the DEPLOY_SSH_KEY secret is not set (Settings -> Secrets and variables -> Actions)"
[ -n "${DEPLOY_KNOWN_HOSTS:-}" ] \
  || fail "the DEPLOY_KNOWN_HOSTS secret is not set: the line install.sh printed"
[ -n "${DEPLOY_HOST:-}" ] || fail "DEPLOY_HOST is empty"

install -d -m 700 "$HOME/.ssh"
umask 077
# A secret pasted in a browser on Windows may come back with CRs in it.
printf '%s\n' "$DEPLOY_SSH_KEY" | tr -d '\r' > "$HOME/.ssh/lava_gate"
printf '%s\n' "$DEPLOY_KNOWN_HOSTS" | tr -d '\r' > "$HOME/.ssh/lava_gate_known_hosts"
ssh-keygen -y -f "$HOME/.ssh/lava_gate" > /dev/null 2>&1 \
  || fail "DEPLOY_SSH_KEY is not a private key without a passphrase"

# ssh reads its config from the home the passwd file gives the account, not
# from $HOME, and in a container job the two differ: HOME is /github/home
# (the runner's temp folder), root's home is /root. The key and the host key
# stay under $HOME/.ssh -- where the jobs' "forget the key" step removes the
# key; in CI that folder is a tmpfs of the job's container (ci.yml), so the
# key never reaches the runner's disk -- and the alias, naming them by full
# path, goes where ssh will look for it.
PW_HOME=$(getent passwd "$(id -u)" | cut -d: -f6) || PW_HOME=
CONFIGS=("$HOME/.ssh/config")
if [ -n "$PW_HOME" ] && [ "$PW_HOME" != "$HOME" ]; then
  install -d -m 700 "$PW_HOME/.ssh"
  CONFIGS+=("$PW_HOME/.ssh/config")
fi
for c in "${CONFIGS[@]}"; do
  cat >> "$c" <<EOF
Host lava-gate
  HostName $DEPLOY_HOST
  Port ${DEPLOY_PORT:-22}
  User root
  IdentityFile $HOME/.ssh/lava_gate
  IdentitiesOnly yes
  UserKnownHostsFile $HOME/.ssh/lava_gate_known_hosts
  StrictHostKeyChecking yes
  BatchMode yes
  ConnectTimeout 20
  ServerAliveInterval 30
  ServerAliveCountMax 6
EOF
done
echo "lava-gate -> root@$DEPLOY_HOST:${DEPLOY_PORT:-22}, host key pinned"
