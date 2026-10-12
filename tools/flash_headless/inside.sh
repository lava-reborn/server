#!/bin/bash
# Inside the container, which run.sh starts with --network none: the film is
# made from the main.swf given, then Xvfb (a screen in memory, nothing on any
# desktop), the stand, the projector under Wine pointed at the film the way
# the launcher points it at main.swf, and check.py over what came back.
#
#   /repo     the repository, read-only (these scripts, tools/swfgen.py)
#   /res      the client's res/, read-only
#   /objects  the objects folder, read-only
#   /fp/flashplayer.exe  the projector, read-only
#   /out      run.sh's output folder: res/ staged there, the rest written here
set -u
OUT=/out
WAIT=${FH_WAIT:-120}
export PYTHONDONTWRITEBYTECODE=1
mkdir -p $OUT/run
own() { [ -n "${HOST_UID:-}" ] && chown -R "$HOST_UID:${HOST_GID:-$HOST_UID}" $OUT; }
trap own EXIT

python3 /repo/tools/flash_headless/mkhost.py /res/main.swf /opt/fh/host_script.swf $OUT/res/fh_host.swf \
  > $OUT/mkhost.log 2>&1 || { cat $OUT/mkhost.log; exit 3; }
Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp > $OUT/xvfb.log 2>&1 &
python3 /repo/tools/flash_headless/stand.py 8099 $OUT/res,/res $OUT/run > $OUT/stand.log 2>&1 &
sleep 2
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
mkdir -p /tmp/xdg && chmod 700 /tmp/xdg
# Run from a bind mount of /mnt/c, the projector's code is mapped as zero
# pages under Wine and it dies at its entry point; a copy in the
# container's own filesystem runs.
cp /fp/flashplayer.exe /root/flashplayer.exe
wine /root/flashplayer.exe "http://127.0.0.1:8099/res/fh_host.swf" > $OUT/wine.log 2>&1 &
t=0
while [ $t -lt "$WAIT" ]; do
  sleep 1
  t=$((t + 1))
  if grep -q "DONE" $OUT/run/log.txt 2>/dev/null; then
    sleep 1
    break
  fi
done
echo "the film ran ${t}s of at most ${WAIT}s" > $OUT/status.txt
import -window root $OUT/screen.png 2>> $OUT/import.log
wineserver -k 2>/dev/null
python3 /repo/tools/flash_headless/check.py $OUT $OUT/res/locations/static/fh.xml /objects /repo/tools
