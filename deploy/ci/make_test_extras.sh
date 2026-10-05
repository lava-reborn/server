#!/usr/bin/env bash
# What the suites read out of the client beyond the server's own slice, as one
# tarball to put on the server once, beside the gate:
#
#   bash deploy/ci/make_test_extras.sh ~/Desktop/lava/res /tmp/res-extra.tgz
#   ssh root@SERVER 'rm -rf /opt/lava-ci/res-extra && mkdir -p /opt/lava-ci/res-extra \
#       && tar -xz --no-same-owner -C /opt/lava-ci/res-extra' < /tmp/res-extra.tgz
#
# The gate's "assets" streams it to CI under res/, on top of the slice the
# game itself reads (/opt/lava/res), and its digest is part of the cache key.
#
# Measured on the slice alone, these suites stop for want of something the
# server never opens:
#
#   database/locations.xml       test_settlements, test_terrain, test_map_labels
#                                read the client's own list of locations;
#   transport/*.swf              test_transport_data compares the vehicle icons
#                                on disk with data/transport.json;
#   personages/*.xml and the     test_sets: every set's figure has a folder and
#   figure folders               its .xml;
#   classes/*/*/ico.swf          test_shops and test_halfa_services: a thing is
#                                for sale only if the client can draw its icon;
#   locations/libs/Vadihalfa     test_bootstrap serves it over HTTP with the
#   port.swf                     res serving on: a name with a space decoded,
#                                the file whole.
#
# The small ones (1.3 MB together) are read, so they go as they are:
# locations.xml, the vehicle icons, the figures' .xml. The icons and
# animations (497 MB and 204 MB) are only looked for -- whether the file is
# there -- so they go as empty files under the real names: the client's
# listing, not its art. "Vadihalfa port.swf" goes as a stand-in of the real
# one's exact size, "CWS" (the compressed-SWF signature the suite checks
# first) and then zeros: 1.9 MB that gzip makes a few kilobytes of, and no
# part of the game. A suite that starts reading the content of a stand-in
# fails on it, loudly, and that is the moment to move the file to the first
# list.
#
# Not main.swf: it is the client's code, and tools/test_wrapper.py does read
# it when it is there (every opcode the wrapper emits must be one main.swf
# uses). Without it test_wrapper skips that comparison and test_bootstrap its
# two main.swf checks, each saying so.
# test_widescreen always checks a small SWF fixture and its bytecode; it
# additionally checks the real client when main.swf is installed locally.
set -euo pipefail

[ $# -eq 2 ] || { echo "usage: $0 <client res/> <out.tgz>" >&2; exit 2; }
RES=$(cd "$1" && pwd)
OUT=$(cd "$(dirname "$2")" && pwd)/$(basename "$2")
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
mkdir -p "$W/x"

cd "$RES"
{
  echo database/locations.xml
  find transport -maxdepth 1 -type f -name '*.swf'
  find personages -maxdepth 1 -type f -name '*.xml'
} | sort > "$W/real"
{
  find classes -mindepth 3 -maxdepth 3 -type f -name ico.swf
  find personages -mindepth 2 -maxdepth 2 -type f
} | sort > "$W/empty"
printf '%s\n' "locations/libs/Vadihalfa port.swf" > "$W/standin"

tar -c -T "$W/real" | tar -x -C "$W/x"
sed 's,/[^/]*$,,' "$W/empty" | sort -u | (cd "$W/x" && xargs -d '\n' mkdir -p)
(cd "$W/x" && xargs -d '\n' touch < "$W/empty")
while IFS= read -r f; do
  size=$(stat -c %s "$f")
  mkdir -p "$W/x/$(dirname "$f")"
  { printf 'CWS'; head -c $((size - 3)) /dev/zero; } > "$W/x/$f"
done < "$W/standin"

tar -C "$W/x" -czf "$OUT" --owner=0 --group=0 --numeric-owner --sort=name .
echo "$OUT: $(wc -l < "$W/real") files as they are, $(wc -l < "$W/empty") empty stand-ins," \
     "$(wc -l < "$W/standin") sized stand-ins, $(stat -c %s "$OUT") bytes"
