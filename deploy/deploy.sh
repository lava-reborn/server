#!/usr/bin/env bash
# Put the LAVA server on the host that already runs Agile Quest.
#
#   bash deploy/deploy.sh              code only: rsync, rebuild, restart
#   bash deploy/deploy.sh --with-res   also push the client (2.1 GB, once)
#   bash deploy/deploy.sh --res-only   only the client, no rebuild
#
# The database lives in a named docker volume and is never touched here.
# Secrets and addresses live in /opt/lava/.env on the server; this script
# creates it from deploy/env.example on the first run and then leaves it
# alone, so a redeploy cannot overwrite the address friends are using.
#
# The client's own files are NOT in this repository and never will be. They
# go up as a separate rsync into /opt/lava/res, which docker mounts
# read-only. Keeping them out of the image means a rebuild moves megabytes
# instead of gigabytes, and the server reads that tree without writing to it.
set -euo pipefail

HOST=${LAVA_DEPLOY_HOST:-root@159.194.247.90}
DEST=${LAVA_DEPLOY_DIR:-/opt/lava}
# Where the client sits on this machine. In WSL the Windows copy is under
# /mnt/c; override for any other layout.
RES_SRC=${LAVA_RES_SRC:-/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res}

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SSH=(ssh -o BatchMode=yes)

with_res=0
res_only=0
for arg in "$@"; do
  case "$arg" in
    --with-res) with_res=1 ;;
    --res-only) with_res=1; res_only=1 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

echo "==> $HOST:$DEST"
"${SSH[@]}" "$HOST" "mkdir -p '$DEST' '$DEST/res'"

if [ "$res_only" = 0 ]; then
  echo "==> code"
  # Everything the image needs and nothing else: no client, no database, no
  # wiki dumps, no worktrees. --delete keeps the server from accumulating
  # files that have been deleted here.
  rsync -a --delete --info=stats1 \
    --exclude '.git/' \
    --exclude '.claude/' \
    --exclude 'res/' \
    --exclude 'dist/' \
    --exclude 'logs/' \
    --exclude 'tools/flash/' \
    --exclude 'tools/ruffle/' \
    --exclude 'data/wiki*' \
    --exclude 'data/lava.db*' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.env' \
    -e "${SSH[*]}" \
    "$HERE/" "$HOST:$DEST/"
fi

if [ "$with_res" = 1 ]; then
  [ -d "$RES_SRC" ] || { echo "no client at $RES_SRC" >&2; exit 1; }
  echo "==> client (this is the slow one)"
  rsync -a --partial --info=progress2 \
    -e "${SSH[*]}" \
    "$RES_SRC/" "$HOST:$DEST/res/"
fi

if [ "$res_only" = 1 ]; then
  echo "==> done (client only, nothing restarted)"
  exit 0
fi

echo "==> env"
"${SSH[@]}" "$HOST" "cd '$DEST' && if [ ! -f .env ]; then cp deploy/env.example .env && echo 'created .env from deploy/env.example -- check LAVA_PUBLIC_HOST'; else echo '.env kept as it is'; fi"

echo "==> build and start"
"${SSH[@]}" "$HOST" "cd '$DEST' && docker compose up -d --build"

echo "==> state"
"${SSH[@]}" "$HOST" "cd '$DEST' && docker compose ps && echo && docker compose logs --tail 5 game"
