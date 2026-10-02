#!/usr/bin/env bash
# Put the CI gate on the production server, or bring an installed one up to
# date. Run as root ON THE SERVER, from a copy of the repository's deploy/:
#
#   bash deploy/remote/install.sh [--pubkey "ssh-ed25519 AAAA... lava-ci"] [--host 159.194.247.90]
#
# Every step is safe to repeat, and repeating it is how the gate is updated
# after deploy/remote/lava-gate.sh or deploy/rsync.filter changes in the
# repository (a deploy report says so when they differ):
#
#   - checks that the tools the gate runs are here: docker compose, rsync,
#     flock, GNU tar, gzip, sha256sum, timeout;
#   - creates /opt/lava-ci, root's only (0700), with log/ and state/;
#   - installs lava-gate.sh and rsync.filter into it -- always, overwriting;
#   - writes gate.conf from the defaults the first time, with RES_DIR read
#     from LAVA_RES_DIR in /opt/lava/.env; an existing gate.conf is the
#     owner's and is left alone;
#   - says whether texts.xml and res-extra/ are in place and, if they are,
#     runs the gate's own assets-hash to prove that side works;
#   - runs the gate with a request it must refuse, and the compose policy
#     over the docker-compose.yml that runs now (it must pass, or the first
#     CI deploy would be refused);
#   - prints the line for the DEPLOY_KNOWN_HOSTS secret (this server's host
#     key) and the line for root's authorized_keys -- and, with
#     --assets-pubkey, the line for a second key that may only fetch the test
#     assets (README «CI/CD», «Два ключа»).
#
# It does not touch authorized_keys, /opt/lava or any container: adding the
# key is a separate, deliberate step, printed at the end.
set -euo pipefail

# The two directories move only for a test run against a throwaway layout.
CI_DIR=${LAVA_CI_DIR:-/opt/lava-ci}
APP_DIR=${LAVA_APP_DIR:-/opt/lava}
HOST=159.194.247.90
PUBKEY=
ASSETS_PUBKEY=
while [ $# -gt 0 ]; do
  case $1 in
    --pubkey)        PUBKEY=$2; shift 2 ;;
    --assets-pubkey) ASSETS_PUBKEY=$2; shift 2 ;;
    --host)          HOST=$2; shift 2 ;;
    *) echo "usage: $0 [--pubkey 'ssh-ed25519 AAAA... lava-ci'] [--assets-pubkey 'ssh-ed25519 AAAA... lava-ci-assets'] [--host ADDRESS]" >&2; exit 2 ;;
  esac
done
for k in "$PUBKEY" "$ASSETS_PUBKEY"; do
  # One line, a key type and its base64, and a comment without quotes: it is
  # pasted after command="..." on the same line of authorized_keys.
  if [ -n "$k" ] && ! [[ $k =~ ^ssh-ed25519\ [A-Za-z0-9+/=]+(\ [A-Za-z0-9@._-]+)?$ ]]; then
    echo "install.sh: '$k' is not one ssh-ed25519 public key line" >&2
    exit 2
  fi
done

HERE=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
GATE=$HERE/lava-gate.sh
FILTER=$HERE/../rsync.filter

[ "$(id -u)" = 0 ] || [ -n "${LAVA_CI_DIR:-}" ] || { echo "install.sh: run me as root" >&2; exit 1; }
[ -f "$GATE" ] && [ -f "$FILTER" ] \
  || { echo "install.sh: lava-gate.sh and ../rsync.filter must sit beside me (a copy of deploy/)" >&2; exit 1; }

echo "==> tools"
missing=
for t in docker rsync flock tar gzip sha256sum timeout stat df find xargs readlink; do
  command -v "$t" > /dev/null || missing="$missing $t"
done
docker compose version > /dev/null 2>&1 || missing="$missing docker-compose-plugin"
tar --version 2>/dev/null | grep -q 'GNU tar' || missing="$missing GNU-tar"
[ -z "$missing" ] || { echo "install.sh: missing:$missing" >&2; exit 1; }
echo "    all there ($(docker compose version --short 2>/dev/null), $(rsync --version | head -n 1))"

echo "==> $CI_DIR"
install -d -m 0700 "$CI_DIR"
install -d -m 0700 "$CI_DIR/log" "$CI_DIR/state"
install -m 0755 "$GATE" "$CI_DIR/lava-gate.sh"
install -m 0644 "$FILTER" "$CI_DIR/rsync.filter"
echo "    lava-gate.sh $(sha256sum < "$CI_DIR/lava-gate.sh" | cut -c1-16), rsync.filter $(sha256sum < "$CI_DIR/rsync.filter" | cut -c1-16)"

if [ -f "$CI_DIR/gate.conf" ]; then
  echo "    gate.conf kept as it is"
else
  res=
  if [ -f "$APP_DIR/.env" ]; then
    res=$(sed -n 's/^LAVA_RES_DIR=//p' "$APP_DIR/.env" | tail -n 1 | tr -d '"'"'"'\r')
  fi
  res=${res:-$APP_DIR/res}
  # compose reads a relative LAVA_RES_DIR from the project directory.
  case $res in /*) ;; *) res=$APP_DIR/${res#./} ;; esac
  umask 077
  cat > "$CI_DIR/gate.conf" <<EOF
# Settings of $CI_DIR/lava-gate.sh, sourced by it as root. Written once by
# install.sh; yours from now on (install.sh never overwrites it). Every name
# here is a default in the gate itself -- delete a line to get the default.
APP_DIR=$APP_DIR
RES_DIR=$res
BACKUP_DIR=/opt
KEEP=5
PG_CONTAINER=lava-pg-db-1
GAME=lava-game
HTTP=lava-http
IMAGE=lava-server
LAUNCHER_EXE=/opt/lava-site/download/LavaReborn.exe
MAX_TGZ_MB=64
MAX_RAW_MB=256
MIN_FREE_MB=2048
HEALTH_TIMEOUT=240
SETTLE=20
ALLOWED_DIRS="server data tools deploy launcher"
# 0 lets any docker-compose.yml through -- and with it root on this host to
# whoever can deploy (lava-gate.sh, "THE COMPOSE POLICY").
COMPOSE_POLICY=1
EOF
  echo "    gate.conf written (RES_DIR=$res)"
fi

echo "==> checks"
[ -f "$APP_DIR/.env" ] && echo "    $APP_DIR/.env present" \
  || echo "    WARNING: no $APP_DIR/.env -- the gate refuses to deploy without one"
if [ -f "$CI_DIR/texts.xml" ]; then
  echo "    texts.xml present ($(stat -c %s "$CI_DIR/texts.xml") bytes)"
else
  echo "    MISSING: $CI_DIR/texts.xml -- upload the original string table:"
  echo "        scp texts.xml root@$HOST:$CI_DIR/texts.xml"
fi
if [ -d "$CI_DIR/res-extra" ]; then
  echo "    res-extra/ present ($(find "$CI_DIR/res-extra" -type f | wc -l) files)"
else
  echo "    MISSING: $CI_DIR/res-extra/ -- the suites that read more than the slice need it; build it with"
  echo "        deploy/ci/make_test_extras.sh on the machine that has the client"
fi
if [ -f "$CI_DIR/texts.xml" ]; then
  if h=$(SSH_ORIGINAL_COMMAND=assets-hash SSH_CLIENT="install.sh 0 0" "$CI_DIR/lava-gate.sh"); then
    echo "    assets-hash answers: $h"
  else
    echo "    WARNING: assets-hash failed; see the message above"
  fi
fi
rc=0
SSH_ORIGINAL_COMMAND="echo hello" SSH_CLIENT="install.sh 0 0" "$CI_DIR/lava-gate.sh" > /dev/null 2>&1 || rc=$?
if [ "$rc" = 2 ]; then
  echo "    a request outside the list is refused (status 2)"
else
  echo "    WARNING: the gate answered 'echo hello' with status $rc, not 2" >&2
fi
rc=0
SSH_ORIGINAL_COMMAND="deploy $(printf '0%.0s' $(seq 40)) $(printf '0%.0s' $(seq 64))" SSH_CLIENT="install.sh 0 0" \
  "$CI_DIR/lava-gate.sh" --assets-only < /dev/null > /dev/null 2>&1 || rc=$?
if [ "$rc" = 2 ]; then
  echo "    an --assets-only key asking to deploy is refused (status 2)"
else
  echo "    WARNING: an --assets-only deploy got status $rc, not 2" >&2
fi
if command -v python3 > /dev/null 2>&1; then
  echo "    the compose policy runs on this host's $(python3 --version 2>&1)"
else
  echo "    no python3 on this host: the compose policy runs in the game's image"
fi
# The compose policy against what runs now: the gate's own check, by itself
# (sourced functions would drag the dispatcher along, so the gate is asked
# through a mode that does nothing else). This script is usually run over
# ssh, and the gate keeps that mode from anything that came in over ssh --
# hence the env -u: it is root at the server running this, on purpose.
if [ -f "$APP_DIR/docker-compose.yml" ] && [ -f "$APP_DIR/.env" ]; then
  if out=$(env -u SSH_CONNECTION -u SSH_ORIGINAL_COMMAND LAVA_GATE_POLICY_ONLY="$APP_DIR/docker-compose.yml" \
             SSH_CLIENT="install.sh 0 0" "$CI_DIR/lava-gate.sh" 2>&1); then
    echo "    the running $APP_DIR/docker-compose.yml is within the compose policy"
  else
    echo "    WARNING: the running $APP_DIR/docker-compose.yml is OUTSIDE the compose policy: $out" >&2
    echo "    the first CI deploy of the same file would be refused; see lava-gate.sh, THE COMPOSE POLICY" >&2
  fi
fi

echo
echo "==> for GitHub: the secret DEPLOY_KNOWN_HOSTS is this one line"
for f in /etc/ssh/ssh_host_ed25519_key.pub /etc/ssh/ssh_host_ecdsa_key.pub; do
  if [ -f "$f" ]; then
    echo "$HOST $(cut -d' ' -f1,2 "$f")"
    break
  fi
done

echo
echo "==> for /root/.ssh/authorized_keys: one line, the CI key and nothing else on it"
echo "command=\"$CI_DIR/lava-gate.sh\",restrict,no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ${PUBKEY:-ssh-ed25519 AAAA...the-public-key... lava-ci}"
if [ -n "$ASSETS_PUBKEY" ]; then
  echo
  echo "==> and, for the two-key setup, a second line: the key that may only fetch the test assets"
  echo "command=\"$CI_DIR/lava-gate.sh --assets-only\",restrict,no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty $ASSETS_PUBKEY"
fi
