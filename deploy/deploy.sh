#!/usr/bin/env bash
# Put the LAVA server on the host that already runs Agile Quest.
#
#   bash deploy/deploy.sh               code only: rsync, rebuild, restart
#   bash deploy/deploy.sh --with-data   also push the tables the server reads
#   bash deploy/deploy.sh --data-only   only those, no rebuild
#
# The database lives in a named docker volume and is never touched here.
# Addresses live in /opt/lava/.env on the server; this script creates it from
# deploy/env.example on the first run and then leaves it alone, so a redeploy
# cannot overwrite the address friends are already using.
#
# WHAT GOES UP, AND WHY SO LITTLE OF IT
#
# The client is 2.1 GB and the server opens six kinds of file out of it:
# locations/{static,deadloc,desert}/*.xml, database/mobs.xml,
# database/objects.xml and avatars/list.xml -- about 35 MB, 1.7 % of the
# whole. Everything else is artwork, sound and animation that the server
# never reads; it belongs to the player's own copy and travels no further
# than their disk. So only that slice is pushed, into a read-only mount.
#
# This is a server, not a game distribution. A player brings their own client
# and the package from tools/make_client_package.py, which is three text
# files and no part of the game.
set -euo pipefail

HOST=${LAVA_DEPLOY_HOST:-root@159.194.247.90}
DEST=${LAVA_DEPLOY_DIR:-/opt/lava}
# Where the client sits on this machine. In WSL the Windows copy is under
# /mnt/c; override for any other layout.
RES_SRC=${LAVA_RES_SRC:-/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res}

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SSH=(ssh -o BatchMode=yes)

with_data=0
data_only=0
for arg in "$@"; do
  case "$arg" in
    --with-data) with_data=1 ;;
    --data-only) with_data=1; data_only=1 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

echo "==> $HOST:$DEST"
"${SSH[@]}" "$HOST" "mkdir -p '$DEST' '$DEST/res'"

if [ "$data_only" = 0 ]; then
  echo "==> code"
  # tools/ holds ~80 MB of downloaded players; only its scripts are ours, and
  # the include has to come before the exclude or rsync never sees them.
  # recon/ is the decompiled client: our reading material, no business on a
  # public host. The image itself takes only server/ and data/ (.dockerignore).
  rsync -a --delete --info=stats1 \
    --exclude '.git/' \
    --exclude '.claude/' \
    --exclude 'res/' \
    --exclude 'dist/' \
    --exclude 'logs/' \
    --exclude 'recon/' \
    --include 'tools/' \
    --include 'tools/*.py' \
    --exclude 'tools/*' \
    --exclude 'data/wiki*' \
    --exclude 'data/lava.db*' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.env' \
    -e "${SSH[*]}" \
    "$HERE/" "$HOST:$DEST/"
fi

if [ "$with_data" = 1 ]; then
  [ -d "$RES_SRC" ] || { echo "no client at $RES_SRC" >&2; exit 1; }
  echo "==> location and item tables"
  # Named file by named file. --prune-empty-dirs keeps the directories that
  # end up with nothing in them from being created at all, and the final
  # --exclude '*' is what makes this a whitelist rather than a filter.
  rsync -a --delete --prune-empty-dirs --info=stats1 \
    --include 'database/' \
    --include 'database/mobs.xml' \
    --include 'database/objects.xml' \
    --include 'avatars/' \
    --include 'avatars/list.xml' \
    --include 'locations/' \
    --include 'locations/static/' \
    --include 'locations/static/*.xml' \
    --include 'locations/deadloc/' \
    --include 'locations/deadloc/*.xml' \
    --include 'locations/desert/' \
    --include 'locations/desert/*.xml' \
    --exclude '*' \
    -e "${SSH[*]}" \
    "$RES_SRC/" "$HOST:$DEST/res/"
fi

if [ "$data_only" = 1 ]; then
  echo "==> done (tables only, nothing restarted)"
  exit 0
fi

echo "==> env"
"${SSH[@]}" "$HOST" "cd '$DEST' && if [ ! -f .env ]; then cp deploy/env.example .env && echo 'created .env from deploy/env.example -- check LAVA_PUBLIC_HOST'; else echo '.env kept as it is'; fi"

echo "==> build and start"
"${SSH[@]}" "$HOST" "cd '$DEST' && docker compose up -d --build"

echo "==> state"
"${SSH[@]}" "$HOST" "cd '$DEST' && docker compose ps && echo && docker compose logs --tail 5 game"
