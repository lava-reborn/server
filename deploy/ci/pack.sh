#!/usr/bin/env bash
# The tree exactly as deploy.sh would rsync it, as one tar.gz for the gate.
#
#   bash deploy/ci/pack.sh OUT.tgz [TREE]
#
# Not a second list of what goes up: the same rsync with the same filter file
# (deploy/rsync.filter) that deploy.sh sends to the server, only into a local
# staging directory, and that directory tarred. Fixed owner and member order,
# so two packs of one checkout differ at most in mtimes.
set -euo pipefail

[ $# -ge 1 ] || { echo "usage: $0 OUT.tgz [TREE]" >&2; exit 2; }
OUT=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
TREE=$(cd "${2:-.}" && pwd)
# CI's job container gets rsync in its first step (ci.yml); by hand, any
# Linux with rsync. Nothing here installs it: a job runs as root without sudo.
command -v rsync > /dev/null \
  || { echo "::error title=Pack::pack.sh needs rsync, and there is none here"; exit 1; }

W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
rsync -a --filter="merge $TREE/deploy/rsync.filter" "$TREE/" "$W/tree/"
tar -C "$W/tree" --sort=name --owner=0 --group=0 --numeric-owner -czf "$OUT" .
echo "$(basename "$OUT"): $(find "$W/tree" -type f | wc -l) files," \
     "$(stat -c %s "$OUT") bytes, sha256 $(sha256sum "$OUT" | cut -c1-64)"
