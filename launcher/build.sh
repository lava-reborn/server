#!/usr/bin/env bash
# Build LavaReborn.exe on Linux, the way the CI gate does it (lava-gate.sh,
# "THE LAUNCHER"): Roslyn's csc out of the mono:6.12 image, against Mono's
# .NET Framework 4.5 libraries, which carry the same assembly names as
# Windows' own, so the exe runs on Windows' .NET Framework unchanged.
#
#   bash launcher/build.sh --out DIR --build N --projector fp32_sa.exe \
#       [--site https://lava-reborn.ru] [--host lava-reborn.ru] [--port 9775] \
#       [--commit SHA] [--resource-keys F] [--launcher-keys F]
#
# The same sources and switches as launcher\build.ps1, and -deterministic: the
# same tree, build number, commit and day give the same bytes, so a build can be
# repeated and compared. Writes DIR/LavaReborn.exe and nothing else; the gate
# signs and publishes it (client/README.md).
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(dirname "$HERE")
OUT= BUILD= PROJECTOR= COMMIT=
SITE=https://lava-reborn.ru
FORUM=https://forum.lava-reborn.ru/
NEWS=https://forum.lava-reborn.ru/forum/1-novosti
HOST=lava-reborn.ru
PORT=9775
RES_KEYS=$REPO/client/keys/resource.keys
LN_KEYS=$REPO/client/keys/launcher.keys
while [ $# -gt 0 ]; do
  case $1 in
    --out) OUT=$2; shift 2 ;;
    --build) BUILD=$2; shift 2 ;;
    --projector) PROJECTOR=$2; shift 2 ;;
    --site) SITE=${2%/}; shift 2 ;;
    --forum) FORUM=$2; shift 2 ;;
    --news) NEWS=$2; shift 2 ;;
    --host) HOST=$2; shift 2 ;;
    --port) PORT=$2; shift 2 ;;
    --commit) COMMIT=$2; shift 2 ;;
    --resource-keys) RES_KEYS=$2; shift 2 ;;
    --launcher-keys) LN_KEYS=$2; shift 2 ;;
    *) echo "build.sh: unknown argument $1" >&2; exit 2 ;;
  esac
done
[ -n "$OUT" ] && [ -n "$PROJECTOR" ] || { echo "build.sh: --out and --projector are required" >&2; exit 2; }
[[ $BUILD =~ ^[1-9][0-9]{0,8}$ ]] || { echo "build.sh: --build must be a positive integer" >&2; exit 2; }
[[ $PORT =~ ^[0-9]{1,5}$ ]] || { echo "build.sh: bad --port" >&2; exit 2; }
[[ $HOST =~ ^[A-Za-z0-9.-]+$ ]] || { echo "build.sh: bad --host" >&2; exit 2; }
[[ $SITE =~ ^https?://[A-Za-z0-9.:-]+$ ]] || { echo "build.sh: bad --site" >&2; exit 2; }
[[ $FORUM =~ ^https?://[A-Za-z0-9./:_-]+$ ]] || { echo "build.sh: bad --forum" >&2; exit 2; }
[[ $NEWS =~ ^https?://[A-Za-z0-9./:_-]+$ ]] || { echo "build.sh: bad --news" >&2; exit 2; }
[[ -z $COMMIT || $COMMIT =~ ^[0-9a-f]{7,40}$ ]] || { echo "build.sh: bad --commit" >&2; exit 2; }

for f in "$PROJECTOR" "$HERE/assets/hero.jpg" "$HERE/assets/logo.png" "$HERE/assets/wrapper.swf" \
         "$HERE/assets/wrapper_plain.swf" "$HERE/assets/lava.ico"; do
  [ -f "$f" ] || { echo "build.sh: missing $f" >&2; exit 1; }
done

# The keys as C# string literals: "<id> <e> <n>", comma-separated.
key_literals() {
  local f=$1 out= line
  [ -f "$f" ] || { echo "build.sh: no keys at $f" >&2; exit 1; }
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    case $line in ''|'#'*) continue ;; esac
    [[ $line =~ ^[0-9a-f]{16}\ [0-9]+\ [0-9a-f]+$ ]] || { echo "build.sh: bad line in $f" >&2; exit 1; }
    out="$out${out:+, }\"$line\""
  done < "$f"
  [ -n "$out" ] || { echo "build.sh: no keys in $f" >&2; exit 1; }
  printf '%s' "$out"
}
RES_LITS=$(key_literals "$RES_KEYS")
LN_LITS=$(key_literals "$LN_KEYS")

STAMP=$(date -u +%d.%m.%Y)
VERSION="v$BUILD $STAMP${COMMIT:+ ${COMMIT:0:7}}"
FILEVERSION="$BUILD.$(date -u +%Y).$((10#$(date -u +%m) * 100 + 10#$(date -u +%d))).0"

W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
# Every value above was checked against a pattern without | or \, so a plain
# sed with | as its separator cannot be broken by them.
sed -e "s|@HOST@|$HOST|g" -e "s|@PORT@|$PORT|g" \
    -e "s|@VERSION@|$VERSION|g" -e "s|@FILEVERSION@|$FILEVERSION|g" \
    -e "s|@REGISTER@|$SITE/register|g" -e "s|@WIKI@|$SITE/wiki|g" -e "s|@CABINET@|$SITE/cabinet|g" \
    -e "s|@FORUM@|$FORUM|g" -e "s|@NEWS@|$NEWS|g" \
    -e "s|@BUILD@|$BUILD|g" -e "s|@SITE@|$SITE|g" \
    -e "s|@RESOURCE_KEYS@|$RES_LITS|g" -e "s|@LAUNCHER_KEYS@|$LN_LITS|g" \
    "$HERE/Launcher.cs" > "$W/Launcher.generated.cs"
if grep -q '@[A-Z_]*@' "$W/Launcher.generated.cs"; then
  echo "build.sh: a placeholder is left in Launcher.cs: $(grep -o '@[A-Z_]*@' "$W/Launcher.generated.cs" | head -n 1)" >&2
  exit 1
fi

# Against the .NET Framework 4.5 REFERENCE assemblies Mono ships, not Mono's
# own libraries: those carry methods Windows' .NET Framework does not have
# (String.TrimEnd(char) is one), the compiler binds to them, and the exe then
# dies on Windows with MissingMethodException. Measured, not supposed.
API=${LAVA_NETFX_API:-/usr/lib/mono/4.5-api}
[ -f "$API/mscorlib.dll" ] || { echo "build.sh: no .NET Framework reference assemblies at $API" >&2; exit 1; }

mkdir -p "$OUT"
# Full paths: csc looks for a bare name in its own folder -- Mono's libraries
# -- before any -lib.
csc -nologo -noconfig -nostdlib -deterministic -target:winexe -platform:anycpu -optimize+ \
  -codepage:65001 -langversion:5 \
  -r:"$API/mscorlib.dll" -r:"$API/System.dll" -r:"$API/System.Core.dll" -r:"$API/System.Numerics.dll" \
  -r:"$API/System.Drawing.dll" -r:"$API/System.Windows.Forms.dll" -r:"$API/System.Security.dll" \
  -win32icon:"$HERE/assets/lava.ico" \
  -resource:"$PROJECTOR",fp32_sa.exe \
  -resource:"$HERE/assets/hero.jpg",hero.jpg \
  -resource:"$HERE/assets/logo.png",logo.png \
  -resource:"$HERE/assets/lava.ico",icon.ico \
  -resource:"$HERE/assets/wrapper.swf",wrapper.swf \
  -resource:"$HERE/assets/wrapper_plain.swf",wrapper_plain.swf \
  -out:"$OUT/LavaReborn.exe" \
  "$HERE/Theme.cs" "$HERE/Icons.cs" "$HERE/Controls.cs" "$HERE/Panels.cs" "$HERE/MainForm.cs" \
  "$HERE/Dialogs.cs" "$HERE/Prefs.cs" "$HERE/Notice.cs" \
  "$HERE/Creds.cs" "$HERE/GameProbe.cs" "$HERE/GameWindow.cs" "$HERE/LocalServer.cs" \
  "$HERE/Release.cs" "$HERE/Sync.cs" "$HERE/TextsCheck.cs" "$W/Launcher.generated.cs"
echo "build.sh: $OUT/LavaReborn.exe, build $BUILD ($VERSION), $(stat -c %s "$OUT/LavaReborn.exe") bytes, sha256 $(sha256sum < "$OUT/LavaReborn.exe" | cut -c1-16)"
