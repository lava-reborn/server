#!/usr/bin/env bash
# The real Flash Player 32 projector the launcher ships draws a location with
# our own objects, through the client's own location classes, inside a
# docker container: a virtual X screen, no window on any desktop, no
# network. Optional, by hand; CI does not run it (README.md beside this file).
#
#   bash tools/flash_headless/run.sh LOCATION.xml [OUTDIR]
#
# LOCATION.xml          the location to draw, e.g. a copy of an original
#                       with an object placed by tools/custom_objects.py place
# OUTDIR                where everything goes (default: a new folder in /tmp)
# LAVA_CLIENT_RES       the client's res/ with main.swf and locations/libs/
#                       (default: LAVA_RES, if that is a whole client)
# LAVA_FLASH_PROJECTOR  the projector (default: tools/flash/fp32_sa.exe of the
#                       repository, the launcher's flashplayer.exe)
# LAVA_OBJECTS          the objects folder (default: client/objects)
# FH_WAIT               seconds the film may take (default 120)
#
# Exit status: 0 every check passed, 1 a check failed (report.txt says
# which), 2 something to run with is missing, 3 the image or the film did
# not build.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
XML=${1:-}
OUT=${2:-}
RES=${LAVA_CLIENT_RES:-${LAVA_RES:-}}
PROJECTOR=${LAVA_FLASH_PROJECTOR:-$ROOT/tools/flash/fp32_sa.exe}
OBJECTS=${LAVA_OBJECTS:-$ROOT/client/objects}

fail() { echo "$*" >&2; exit 2; }
[ -n "$XML" ] && [ -f "$XML" ] || fail "usage: run.sh LOCATION.xml [OUTDIR]"
[ -n "$RES" ] && [ -f "$RES/main.swf" ] && [ -d "$RES/locations/libs" ] \
  || fail "LAVA_CLIENT_RES must name the client's res/ with main.swf and locations/libs/ (the server's slice has neither)"
[ -f "$PROJECTOR" ] || fail "no projector at $PROJECTOR: set LAVA_FLASH_PROJECTOR to the launcher's flashplayer.exe"
[ -d "$OBJECTS" ] || fail "no objects folder $OBJECTS"
command -v docker >/dev/null || fail "docker is needed"
[ -n "$OUT" ] || OUT=$(mktemp -d "${TMPDIR:-/tmp}/lava-flash-headless.XXXXXX")
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)

TAG=lava-flash-headless:$(cat "$HERE/Dockerfile" "$HERE/host.as" "$HERE/skel.py" | sha256sum | cut -c1-12)
if ! docker image inspect "$TAG" >/dev/null 2>&1; then
  echo "building $TAG once (the network is needed for Debian's packages and FFDec)"
  docker build --network host -t "$TAG" "$HERE" > "$OUT/build.log" 2>&1 \
    || { tail -20 "$OUT/build.log" >&2; exit 3; }
fi

rm -rf "$OUT/res" "$OUT/run"
mkdir -p "$OUT/res/locations/static"
cp "$XML" "$OUT/res/locations/static/fh.xml"
python3 -B "$ROOT/tools/custom_objects.py" build "$OUT/res" "$OBJECTS" > "$OUT/objects.log" 2>&1 \
  || { cat "$OUT/objects.log" >&2; exit 3; }
rc=0
docker run --rm --network none \
  -v "$ROOT:/repo:ro" -v "$RES:/res:ro" -v "$OBJECTS:/objects:ro" \
  -v "$PROJECTOR:/fp/flashplayer.exe:ro" -v "$OUT:/out" \
  -e FH_WAIT="${FH_WAIT:-120}" -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
  "$TAG" bash /repo/tools/flash_headless/inside.sh || rc=$?
echo "everything is in $OUT"
exit $rc
