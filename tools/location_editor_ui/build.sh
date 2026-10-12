#!/bin/bash
# Build the location editor's page into static/ (tools/location_editor.py serves it).
#
#     bash tools/location_editor_ui/build.sh
#
# Needs Node 18+ (WSL has it). node_modules lives outside the checkout, in a
# copy under ~/.cache (npm over /mnt/c is slow); the repository keeps only
# the source and the built page. The art cache of the editor is another
# folder (~/.cache/lava-location-editor): this one is the build's alone.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${LOCATION_EDITOR_BUILD:-$HOME/.cache/lava-location-editor-ui-build}"
mkdir -p "$WORK"
rsync -a --delete --exclude node_modules --exclude static "$HERE/" "$WORK/"
cd "$WORK"
if [ ! -d node_modules ] || [ package.json -nt node_modules/.stamp ]; then
  npm install --no-audit --no-fund --loglevel=error
  touch node_modules/.stamp
fi
npm run build
rsync -a --delete "$WORK/static/" "$HERE/static/"
echo "built: $HERE/static"
