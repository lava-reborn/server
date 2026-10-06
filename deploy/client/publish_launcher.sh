#!/usr/bin/env bash
# Publish a launcher build: from the owner's machine, after build.ps1 -SignKey.
#
#   bash deploy/client/publish_launcher.sh dist/LavaReborn.exe dist/<N>.txt [root@159.194.247.90]
#
# Copies the exe and its signed statement to the server, then runs the
# installed publisher there (/opt/lava-ci/client/publish.py launcher), which
# checks the statement against client/keys/launcher.keys as install.sh copied
# it, re-signs the pointer with the launcher in it and puts the exe at
# /download/LavaReborn.exe, the site's link (the one before is kept as
# LavaReborn.exe.prev). Every self-updating launcher replaces itself with it
# on its next start; older ones send their players to the site.
#
# Needs root over ssh: publishing a launcher is the owner's, not CI's.
set -euo pipefail

[ $# -ge 2 ] || { echo "usage: $0 EXE STATEMENT [user@host]" >&2; exit 2; }
EXE=$1
ST=$2
HOST=${3:-root@159.194.247.90}
ROOT=${LAVA_CLIENT_ROOT:-/opt/lava-site/download/client}

[ -f "$EXE" ] || { echo "no exe at $EXE" >&2; exit 1; }
[ -f "$ST" ] || { echo "no statement at $ST" >&2; exit 1; }
tail -n 1 "$ST" | grep -q '^sig ' || { echo "$ST is not signed: build with -SignKey" >&2; exit 1; }
version=$(sed -n 's/^version \([0-9]*\)$/\1/p' "$ST")
want=$(sed -n 's/^sha256 \([0-9a-f]*\)$/\1/p' "$ST")
got=$(sha256sum < "$EXE" | cut -c1-64)
[ -n "$version" ] && [ "$want" = "$got" ] \
  || { echo "$EXE is not the build $ST describes (sha256 $got, statement $want)" >&2; exit 1; }

tmp=/root/lava-launcher-$version
echo "==> launcher $version ($got) to $HOST"
ssh "$HOST" "mkdir -p '$tmp'"
scp -q "$EXE" "$HOST:$tmp/LavaReborn.exe"
scp -q "$ST" "$HOST:$tmp/$version.txt"
ssh "$HOST" "python3 /opt/lava-ci/client/publish.py launcher --root '$ROOT' \
  --key /opt/lava-ci/client/resource.pem --launcher-keys /opt/lava-ci/client/launcher.keys \
  --exe '$tmp/LavaReborn.exe' --statement '$tmp/$version.txt' --download /opt/lava-site/download \
  && rm -rf '$tmp' && python3 /opt/lava-ci/client/publish.py status --root '$ROOT'"
