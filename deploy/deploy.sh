#!/usr/bin/env bash
# Put the LAVA server on the host that already runs Agile Quest.
#
#   bash deploy/deploy.sh               code only: rsync, rebuild, warn, restart
#   bash deploy/deploy.sh --with-data   also push the tables the server reads
#   bash deploy/deploy.sh --data-only   only those, no rebuild
#   bash deploy/deploy.sh --now         restart without warning the players
#   bash deploy/deploy.sh --warn=300    warn them 300 seconds ahead (default
#                                       LAVA_STOP_WARN_SEC, else 180)
#
# The players are warned before the restart (server/stopwarn.py): the new
# image is built first, with the old containers still running; then the game
# tells everyone logged in that it stops in N seconds and counts it down in
# the client's own alert, and only when that is over -- or nobody is left --
# are the containers recreated. With nobody logged in there is no wait. Ctrl-C
# during the countdown calls it off and restarts nothing; so does a cancel
# from the admin panel. A poll that gets no answer does not cut the wait
# short, and a game that restarted by itself meanwhile is restarted at once.
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
# The game itself reaches players another way: the launcher installs it from
# the client release the CI gate publishes (client/README.md), out of a store
# that holds the original once. This script pushes the server, and the slice
# is all the server reads.
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
# Seconds of warning before the restart; --now makes it none.
warn=${LAVA_STOP_WARN_SEC:-180}
for arg in "$@"; do
  case "$arg" in
    --with-data) with_data=1 ;;
    --data-only) with_data=1; data_only=1 ;;
    --now) warn=0 ;;
    --warn=*) warn=${arg#--warn=} ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done
case "$warn" in
  ''|*[!0-9]*) echo "--warn wants whole seconds, not '$warn'" >&2; exit 2 ;;
esac
# What the game takes (stopwarn.MIN_SECONDS, MAX_SECONDS).
if [ "$warn" != 0 ] && { [ "$warn" -lt 10 ] || [ "$warn" -gt 600 ]; }; then
  echo "--warn: from 10 to 600 seconds (or --now)" >&2
  exit 2
fi

# The slice the server reads is the original's. An installed client is the
# launcher's, and the launcher puts the release's own files (client/files)
# into it -- one of them inside the slice: locations/static/262.xml, the
# Тотем titled for the client's window (client/files/README.md). Synced from
# such a client, /opt/lava/res would read ours, the server with it, and CI's
# copy of the slice (README «Ресурсы для тестов»). The locations of ours,
# data/locations/static/<id>.xml, go the same way: the release ships each as
# locations/static/<id>.xml, and the server reads them from the repository
# (server/world.py, static_path), never from /opt/lava/res. So every slice
# path either of the two has must be, in RES_SRC, the original's bytes as
# client/base.txt has them; else nothing goes up, before anything is done.
# A path the original lacks -- a new place of ours, 1381 and up -- is
# never sent at all, whatever the client holds there (slice_excludes).
slice_excludes=()
ours_in_slice() {
  {
    (cd "$HERE/client/files" && find . -type f | sed 's|^\./||')
    if [ -d "$HERE/data/locations/static" ]; then
      (cd "$HERE/data/locations/static" && find . -maxdepth 1 -type f -name '*.xml' \
         | sed 's|^\./|locations/static/|')
    fi
  } | LC_ALL=C sort -u
}
check_slice() {
  local bad=0 rel want have
  while IFS= read -r rel; do
    case "$rel" in
      database/mobs.xml|database/objects.xml|avatars/list.xml) ;;
      locations/static/*.xml|locations/deadloc/*.xml|locations/desert/*.xml) ;;
      *) continue ;;
    esac
    want=$(awk -F'\t' -v p="$rel" 'NF == 3 && $3 == p { print $1 }' "$HERE/client/base.txt")
    if [ -z "$want" ]; then
      slice_excludes+=(--exclude "/$rel")
      continue
    fi
    have=
    if [ -f "$RES_SRC/$rel" ]; then
      have=$(sha256sum "$RES_SRC/$rel" | cut -d' ' -f1)
    fi
    if [ "$have" != "$want" ]; then
      echo "slice: $RES_SRC/$rel is not the original's (client/base.txt: $want);" \
           "client/files or data/locations has its own copy, which the server never" \
           "reads from /opt/lava/res" >&2
      bad=1
    fi
  done < <(ours_in_slice)
  if [ "$bad" = 1 ]; then
    echo "put the original's file back (LAVA.zip, LAVA/res/<path>) or point LAVA_RES_SRC at a res" \
         "that has it; nothing was sent" >&2
    exit 1
  fi
}

if [ "$with_data" = 1 ]; then
  [ -d "$RES_SRC" ] || { echo "no client at $RES_SRC" >&2; exit 1; }
  check_slice
fi

echo "==> $HOST:$DEST"
"${SSH[@]}" "$HOST" "mkdir -p '$DEST' '$DEST/res'"

if [ "$data_only" = 0 ]; then
  echo "==> code"
  # What goes up and what stays behind is deploy/rsync.filter, one list for
  # this script, for CI's tarball (deploy/ci/pack.sh) and for the gate that
  # swaps that tarball in on the server (deploy/remote/lava-gate.sh): tools/
  # scripts but not the downloaded players beside them, no recon/, no wiki
  # dumps, no database, no .env. The reasons are written there, rule by rule.
  #
  # A push to main deploys by itself now (README, "CI/CD"); this script stays
  # for the first install and for a deploy by hand. Not while CI deploys: the
  # gate's lock does not cover it.
  rsync -a --delete --info=stats1 \
    --filter="merge $HERE/deploy/rsync.filter" \
    -e "${SSH[*]}" \
    "$HERE/" "$HOST:$DEST/"
fi

if [ "$with_data" = 1 ]; then
  [ -d "$RES_SRC" ] || { echo "no client at $RES_SRC" >&2; exit 1; }
  echo "==> location and item tables"
  # Named file by named file. --prune-empty-dirs keeps the directories that
  # end up with nothing in them from being created at all, and the final
  # --exclude '*' is what makes this a whitelist rather than a filter. The
  # new places of ours go first (check_slice): the first rule that matches
  # wins, and those files are the repository's to serve.
  rsync -a --delete --prune-empty-dirs --info=stats1 \
    ${slice_excludes[@]+"${slice_excludes[@]}"} \
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

echo "==> build"
# The new image first, while the old containers go on serving: a build that
# fails stops the script here, and the players never notice it.
"${SSH[@]}" "$HOST" "cd '$DEST' && docker compose build"

# The countdown (server/stopwarn.py, run inside the running game). Each call
# prints "LEFT PLAYERS": seconds to the stop, "-" with none announced. The
# wait is on this side: a countdown waited out inside one long ssh would go
# on after a dropped link with nobody left to restart.
stopwarn() {   # its line on stdout; the game's own words on the terminal
  "${SSH[@]}" "$HOST" "docker exec lava-game python3 stopwarn.py $*"
}
STOP_LINE='^(-|0|[1-9][0-9]{0,5}) (0|[1-9][0-9]{0,5})$'
warned=0
call_off() {
  [ "$warned" = 1 ] || return 0
  warned=0
  stopwarn cancel --by deploy.sh > /dev/null \
    && echo "    the countdown is called off" \
    || echo "    could not call the countdown off: it ends by itself, two minutes after its time"
}
trap call_off EXIT
trap 'echo; echo "==> interrupted: nothing restarted"; exit 130' INT TERM

if [ "$warn" = 0 ]; then
  echo "==> no warning (--now)"
else
  echo "==> warning the players: ${warn}s"
  asked=$SECONDS
  out=$(stopwarn start "$warn" --by deploy.sh --skip-empty) || out=
  if [[ ! $out =~ $STOP_LINE ]]; then
    # The first deploy that carries stopwarn.py lands here (the running image
    # has none), and so does a game that is down: restart at once, as before.
    echo "    the running server cannot count down; restarting now"
  elif [ "${BASH_REMATCH[2]}" = 0 ]; then
    echo "    nobody online, no wait"
  elif [ "${BASH_REMATCH[1]}" = - ]; then
    echo "    the game announced no stop; restarting now"
  elif [ "${BASH_REMATCH[1]}" = 0 ]; then
    echo "    a countdown already over; restarting now"
  else
    left=${BASH_REMATCH[1]}
    warned=1
    echo "    ${BASH_REMATCH[2]} player(s) told: the restart in ${left}s (Ctrl-C calls it off)"
    # When the restart is due: as the game last said, and never past the
    # longest countdown it takes (stopwarn.MAX_SECONDS) and half a minute. A
    # poll that gets no answer -- one ssh that failed, a slow docker exec --
    # leaves it where it is: the players were told that time.
    start=$SECONDS
    cap=$(( start + (left < 600 ? left : 600) + 30 ))
    due=$(( start + left < cap ? start + left : cap ))
    while :; do
      sleep $(( due - SECONDS < 1 ? 1 : (due - SECONDS < 10 ? due - SECONDS : 10) ))
      out=$(stopwarn status) || out=
      if [[ ! $out =~ $STOP_LINE ]]; then
        if [ "$SECONDS" -ge "$due" ]; then
          echo "    the countdown does not answer, and its time is up; restarting"
          break
        fi
        echo "    the countdown does not answer; waiting out the $((due - SECONDS))s the players were told"
        continue
      fi
      left=${BASH_REMATCH[1]}
      if [ "$left" = - ]; then
        # Gone with an order that called it off, or gone with the game's
        # process (a crash docker brought back, a stop by hand), whose
        # players are cut off already. No clear answer: the first.
        n=$(stopwarn cancelled $((SECONDS - asked + 2))) || n=
        warned=0
        if [ "$n" != 0 ]; then
          echo "==> the countdown was called off (the admin panel?): nothing restarted"
          echo "    $DEST already holds the new tree and the new image; the next"
          echo "    'docker compose up' there starts them"
          exit 1
        fi
        echo "    the game restarted by itself (a crash?) and dropped the countdown; restarting now"
        break
      fi
      echo "    ${left}s to the restart, ${BASH_REMATCH[2]} online"
      [ "$left" -le 0 ] && break
      if [ "${BASH_REMATCH[2]}" = 0 ]; then
        echo "    nobody online any more"
        break
      fi
      if [ "$SECONDS" -ge "$cap" ]; then
        echo "    waited $((SECONDS - start))s, the most a countdown takes; restarting"
        break
      fi
      due=$(( SECONDS + left < cap ? SECONDS + left : cap ))
    done
  fi
fi

echo "==> start"
"${SSH[@]}" "$HOST" "cd '$DEST' && docker compose up -d --no-build"
# Restarted: the countdown went with the old process.
warned=0
trap - INT TERM

echo "==> state"
"${SSH[@]}" "$HOST" "cd '$DEST' && docker compose ps && echo && docker compose logs --tail 5 game"
