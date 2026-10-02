#!/usr/bin/env bash
# The test assets, from the gate into DIR, checked against the digest the
# gate gave for them.
#
#   bash deploy/ci/fetch_assets.sh DIR HASH     fetch, unpack, check
#   bash deploy/ci/fetch_assets.sh --hash DIR   only print DIR's digest
#
# DIR ends up as res/ (the server's slice of the client plus the extras the
# suites read, see make_test_extras.sh) and texts.xml (the original string
# table). The digest is the gate's own recipe, line for line: one
# "<sha256>  <path>" per file, sorted bytewise, hashed. A stream cut short or
# a file changed on the server between the two requests shows up here as a
# mismatch, before anything is cached under a key it does not match.
set -euo pipefail

digest() {
  (cd "$1" && { find res -type f -print0 | xargs -0 -r sha256sum; sha256sum texts.xml; } \
     | LC_ALL=C sort | sha256sum | cut -c1-64)
}

if [ "${1:-}" = --hash ]; then
  digest "$2"
  exit 0
fi

[ $# -eq 2 ] || { echo "usage: $0 DIR HASH | --hash DIR" >&2; exit 2; }
DIR=$1
WANT=$2
rm -rf "$DIR"
mkdir -p "$DIR"
ssh lava-gate assets | tar -xz -C "$DIR"
GOT=$(digest "$DIR")
if [ "$GOT" != "$WANT" ]; then
  echo "::error title=Assets::the gate said $WANT, what arrived hashes to $GOT"
  exit 1
fi
echo "assets: $(find "$DIR/res" -type f | wc -l) files under res/ and texts.xml, $(du -sh "$DIR" | cut -f1), digest ok"
