#!/usr/bin/env bash
# The production server's one door for CI: a forced ssh command.
#
# deploy/remote/install.sh puts this file at /opt/lava-ci/lava-gate.sh and
# prints the line that ties it to ONE key in root's authorized_keys:
#
#   command="/opt/lava-ci/lava-gate.sh",restrict,no-port-forwarding,
#   no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA... lava-ci
#
# sshd then runs this script whatever the client asked for and leaves what it
# asked for in SSH_ORIGINAL_COMMAND. The key can do exactly what is matched
# below and nothing else -- no shell, no scp, no forwarding:
#
#   assets-hash            the cache key of the test assets: one sha256 line
#   assets                 the test assets as a tar.gz on stdout
#   deploy <sha> <sum>     a tar.gz of the tree on stdin, <sha> the 40-hex
#                          commit it was packed from, <sum> its own sha256
#
# Anything else is refused, logged, and answered with exit status 2.
#
# A second key may be tied to the same script with --assets-only after it
# (command="/opt/lava-ci/lava-gate.sh --assets-only",...): that key gets the
# first two and is refused "deploy". It is for a repository that can keep the
# deploying key apart from the testing one (README «CI/CD», «Два ключа»);
# with one key for both, nothing here changes.
#
# WHY THE TEST ASSETS COME FROM HERE
#
# The suites need two things that may not live in the repository: the slice of
# the player's client that the server reads (res/ -- locations, mobs.xml,
# objects.xml, avatars/list.xml, ~39 MB) and the original string table that
# the data builders' tests compare against (texts.xml, 20 MB). This machine
# already holds the first, read-only, for the game itself, and the second is
# uploaded beside this script once. "assets" streams exactly the files
# deploy.sh --with-data pushes, by the same include list, plus that table,
# plus res-extra/ if it is here: what the suites read beyond the server's
# slice, made by deploy/ci/make_test_extras.sh (1.3 MB of small files, empty
# stand-ins for icons whose existence is all a suite checks, and one .swf as
# "CWS" and zeros at its real size).
# "assets-hash" is a digest of the same files, which CI uses as its cache key
# and checks the unpacked copy against, so a stream cut short is caught there
# and not three jobs later.
#
# WHAT A DEPLOY DOES, IN ORDER
#
#   1. take the lock (one deploy at a time; the next one waits its turn);
#   2. read the tarball off stdin, at most MAX_TGZ_MB, and check its sha256;
#   3. check it before unpacking a byte: gzip intact, unpacked size under
#      MAX_RAW_MB both as a stream and as the sizes its members declare (a
#      sparse member is small in the stream and huge on disk), only plain
#      files and directories with no setuid/setgid/sticky bit, no absolute
#      paths and no "..", only the top-level directories in ALLOWED_DIRS,
#      none of .env, res/ or the database, no compose file but
#      docker-compose.yml (compose would merge an override on its own), and
#      the files the server cannot start without;
#   4. unpack into a staging directory and validate the compose file it
#      carries against the real .env -- and against the policy below;
#   5. back up what is running -- the same three things the manual backup
#      script takes: pg_dump of the shared database to
#      /opt/lava-pg-backup-<id>.dump, cp -a of /opt/lava to
#      /opt/lava.bak-<id>, and a tag lava-server:pre-<id> on the image the
#      game is running now. Nothing has been changed yet, so a failure here
#      changes nothing;
#   6. swap the tree into /opt/lava with rsync --delete under the same filter
#      deploy.sh uses, which keeps .env, res/ and everything else that lives
#      only on the server;
#   7. docker compose up -d --build;
#   8. wait until both containers run, have not restarted, answer the same
#      check their compose healthcheck runs (twice in a row), and have
#      written no traceback; then wait SETTLE seconds more and look again,
#      and count the log lines since step 7 that match ERROR_PATTERN;
#   9. compare the key files in /opt/lava and inside the running image with
#      the tarball's;
#  10. report, record the commit as deployed, prune old backups.
#
# Any failure from step 6 on rolls back: the saved tree goes back with rsync
# --delete, the pre-<id> image is tagged lava-server again, compose brings the
# old containers up, and the script exits non-zero so the job goes red. The
# database is NOT restored by itself: rows written by players since the backup
# would go with it, and an old server reads a schema with extra columns
# without complaint. The dump is named in the report; restoring it is a
# decision for a human (README, "CI/CD").
#
# The rest of a deploy survives the client going away. Once the tarball is in,
# a cancelled job or a dropped connection must not leave the server half
# swapped, so SIGHUP and SIGPIPE are ignored from then on and everything the
# script says goes to the log first and to the client only if it is still
# there.
#
# Exit status: 0 deployed; 1 failed and rolled back (or failed before
# anything changed); 2 refused; 3 failed and the rollback failed too -- the
# server needs a human, and the log says where it stopped.
#
# Logs: one line per request in /opt/lava-ci/log/gate.log, the whole of each
# deploy (docker build output included) in /opt/lava-ci/log/deploy-<id>-<sha>.log.
#
# THE COMPOSE POLICY
#
# Whoever may deploy may change docker-compose.yml, and docker runs what that
# file says as root: a privileged container, the host's / mounted, a volume
# whose driver binds a host path, a build whose context is /etc. Unchecked,
# "deploy" would be a root shell with extra steps. So before anything is
# backed up the compose file is normalised (docker compose config, against
# the real .env, from /opt/lava as the project directory -- exactly what "up"
# will read) and the result has to stay inside what this server needs:
#
#   - services may not ask for privileged, cap_add, devices, gpus,
#     pid/ipc/uts/network_mode/userns_mode/cgroup, security_opt,
#     volumes_from, a runtime, secrets or configs;
#   - a bind mount only of RES_DIR, read-only; named volumes only as declared
#     at the top, and those with no driver or driver_opts; tmpfs;
#   - a build only of /opt/lava itself, its Dockerfile inside it, with none
#     of additional_contexts, secrets, ssh, network, privileged, entitlements
#     or cache_from/cache_to;
#   - networks only bridge, nothing external; no top-level secrets/configs;
#   - and in the file as written: no env_file, extends or include (they read
#     other files of the host, and the first is gone from the normalised
#     form), no backslash and no "!!" tag (the ways to spell a key without
#     writing it).
#
# A deploy outside it is refused before anything changes, and the report
# says which rule. COMPOSE_POLICY=0 in gate.conf turns it off, for the day
# the server needs something it does not allow; the owner's decision, made
# on the server.
#
# The deploy's health checks read the services' logs, and the http service
# writes every request line into its own -- the path included, which anyone
# on the internet chooses. So the access lines ("  HTTP ...") are not read,
# and what counts as an error is what only the server itself writes: a
# traceback, the exception line that ends one, or its "  !!    " marker for a
# failure it caught (ERROR_PATTERN).
#
# MEASURED, NOT ASSUMED (deploy/remote/test_gate.sh: a throwaway /opt with
# its own containers, image and Postgres, installed by install.sh, driven
# through a stand-in for sshd): requests outside the
# list refused; bad tarballs refused before anything was touched -- "..", an
# absolute path, a symlink, a hard link, a fifo, a newline in a name, .env at
# the top and deeper, data/lava.db, res/, an unknown top directory, no
# Dockerfile, over the size limit, a zip bomb, a sparse member, a setuid
# bit, an override compose file, compose files that break the policy, not
# gzip at all, a wrong sha256 and a cut-short stream; a good deploy with .env
# and res/ kept and the new code inside the running image; a crash at start,
# a build that fails and a caught failure in the log each rolled back to the
# image that ran before, tree byte for byte; request lines naming Traceback
# and Error during the watch not taken for errors; a second deploy refused
# while the lock was held; a deploy whose client vanished after the first
# line finished on its own; pruning to KEEP. The launcher's table as read
# here agrees with GetManifestResourceStream on the published exe.
#
# Every build gets a new image id, even when every step comes from cache, so
# compose recreates both containers on every deploy -- as deploy.sh's own
# "docker compose up -d --build" always has. The server saves everyone on the
# way down.

set -uo pipefail
umask 022
export LC_ALL=C

SELF=$(readlink -f "$0")
CI_DIR=$(dirname "$SELF")

# --- settings ---------------------------------------------------------------
#
# The defaults are production's. gate.conf beside this script -- written once
# by install.sh and the owner's afterwards -- may override any of them. It is
# sourced as root, so it has to be root's and writable by nobody else, which
# is checked before it is read. The test layout is a gate.conf too: the same
# script runs against a throwaway /opt with throwaway container names.

APP_DIR=/opt/lava
RES_DIR=                      # empty: $APP_DIR/res
BACKUP_DIR=/opt               # lava.bak-<id>/ and lava-pg-backup-<id>.dump
KEEP=5                        # CI backups kept; older ones are pruned
PG_CONTAINER=lava-pg-db-1     # empty: no pg_dump (a server on SQLite)
GAME=lava-game
HTTP=lava-http
IMAGE=lava-server             # the image name docker-compose.yml builds
LAUNCHER_EXE=/opt/lava-site/download/LavaReborn.exe
MAX_TGZ_MB=64                 # the tarball as sent (the tree packs to ~2 MB)
MAX_RAW_MB=256                # the tarball unpacked
MAX_FILES=20000
MIN_FREE_MB=2048              # free space a backup may not eat into
HEALTH_TIMEOUT=240            # seconds for both services to come up
SETTLE=20                     # seconds watched after they are up
LOCK_WAIT=900                 # seconds a deploy waits for the one before it
ALLOWED_DIRS="server data tools deploy launcher"
REQUIRED="Dockerfile docker-compose.yml server/server.py server/healthcheck.py"
KEY_FILES="server/server.py server/accounts.py server/storage.py server/names.py server/bootstrap_http.py data/quests.json"
COMPOSE_POLICY=1              # 0: docker-compose.yml is not policed (see above)
# What only the server writes when something goes wrong: a traceback's first
# line, the exception line that ends one, and the marker the server puts on a
# failure it caught (log.exception("  !!    ...")). Read over both services'
# logs since the build, with the http service's request lines left out --
# their paths are anyone's to choose. CRASH_PATTERN is the part that ends the
# wait for health at once.
ERROR_PATTERN='^Traceback \(most recent call last\)|^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception)(: |$)|  !!    '
CRASH_PATTERN='^Traceback \(most recent call last\)'

CONF=$CI_DIR/gate.conf
if [ -e "$CONF" ]; then
  if [ ! -O "$CONF" ] || [ -n "$(find "$CONF" -perm /022 -print)" ]; then
    echo "gate: $CONF must belong to $(id -un) and be writable by nobody else" >&2
    exit 2
  fi
  # shellcheck source=/dev/null
  . "$CONF"
fi
RES_DIR=${RES_DIR:-$APP_DIR/res}
TEXTS=$CI_DIR/texts.xml
FILTER=$CI_DIR/rsync.filter
LOG_DIR=$CI_DIR/log
STATE_DIR=$CI_DIR/state
STAGE=$CI_DIR/stage
mkdir -p "$LOG_DIR" "$STATE_DIR"

# --- the request log --------------------------------------------------------

CLIENT=${SSH_CLIENT:-local}
CLIENT=${CLIENT%% *}
REQ=${SSH_ORIGINAL_COMMAND-}
SHOWN=$(printf '%q' "${REQ:0:200}")
OUTCOME=
TMPD=
# The forced command's own arguments, written in authorized_keys by root --
# not anything the client sends, which arrives in SSH_ORIGINAL_COMMAND.
KEYMODE=full
case "${1:-}/$#" in
  /0)              ;;
  --assets-only/1) KEYMODE=assets; CLIENT="$CLIENT(assets-only)" ;;
  *)               KEYMODE=bad ;;
esac

note() {
  printf '%s %s %s %s\n' "$(date -u +%FT%TZ)" "$CLIENT" "$SHOWN" "$*" \
    >> "$LOG_DIR/gate.log" 2>/dev/null
}
trap 'rc=$?; [ -n "$TMPD" ] && rm -rf -- "$TMPD"; note "rc=$rc${OUTCOME:+ $OUTCOME}"' EXIT

# DLOG is the deploy's own log once a deploy has begun, /dev/null before.
DLOG=/dev/null

refuse() {
  OUTCOME="refused: $*"
  echo "gate: refused: $*" >&2
  echo "gate: refused: $*" >> "$DLOG" 2>/dev/null
  exit 2
}

# --- assets -----------------------------------------------------------------
#
# The include list is deploy.sh --with-data's, file for file: database/mobs.xml,
# database/objects.xml, avatars/list.xml and the *.xml directly inside
# locations/{static,deadloc,desert}. Its rsync patterns match one level, so
# -maxdepth 1 here.

assets_list() {
  (
    cd "$RES_DIR" || exit 1
    for f in database/mobs.xml database/objects.xml avatars/list.xml; do
      [ -f "$f" ] || { echo "gate: $RES_DIR/$f is missing" >&2; exit 1; }
      echo "$f"
    done
    for d in locations/static locations/deadloc locations/desert; do
      [ -d "$d" ] || { echo "gate: $RES_DIR/$d is missing" >&2; exit 1; }
      find "$d" -maxdepth 1 -type f -name '*.xml'
    done
  ) | sort
}

# What the suites read beyond that slice (database/locations.xml, the vehicle
# icons, the figures' .xml, and stand-ins for files whose existence or size
# is all a suite checks) -- built on the owner's machine by
# deploy/ci/make_test_extras.sh and unpacked into res-extra/ beside this
# script. Optional: without it the assets are the slice alone, and the
# suites that need more fail and say what they missed.
extra_list() {
  [ -d "$CI_DIR/res-extra" ] || return 0
  (cd "$CI_DIR" && find res-extra -type f | sort)
}

need_texts() {
  [ -f "$TEXTS" ] && return 0
  echo "gate: no original string table at $TEXTS -- upload texts.xml there (README, CI/CD)" >&2
  OUTCOME="no texts.xml"
  exit 1
}

# One line per file, "<sha256>  res/<path>" and "<sha256>  texts.xml", sorted.
# The CI side builds the same lines from what it unpacked
# (deploy/ci/fetch_assets.sh) and compares the digests of the two.
assets_manifest() {
  local list extra
  list=$(assets_list) || return 1
  extra=$(extra_list) || return 1
  {
    (cd "$RES_DIR" && printf '%s\n' "$list" | xargs -d '\n' sha256sum \
       | sed 's,^\([0-9a-f]*\)  ,\1  res/,')
    if [ -n "$extra" ]; then
      (cd "$CI_DIR" && printf '%s\n' "$extra" | xargs -d '\n' sha256sum \
         | sed 's,^\([0-9a-f]*\)  res-extra/,\1  res/,')
    fi
    (cd "$CI_DIR" && sha256sum texts.xml)
  } | sort
}

cmd_assets_hash() {
  need_texts
  local m
  m=$(assets_manifest) || { OUTCOME="assets unreadable"; exit 1; }
  printf '%s\n' "$m" | sha256sum | cut -c1-64
  OUTCOME="ok"
}

cmd_assets() {
  need_texts
  local list extra
  list=$(assets_list) || { OUTCOME="assets unreadable"; exit 1; }
  extra=$(extra_list) || { OUTCOME="res-extra unreadable"; exit 1; }
  # Three roots in one archive. -C is positional, so each list is read
  # relative to the directory named just before it: the slice from the
  # game's res/, the extras from res-extra/, the table from here. Both
  # transforms land the first two under res/; texts.xml matches neither and
  # keeps its name at the top.
  TMPD=$(mktemp -d "$CI_DIR/.assets.XXXXXX")
  printf '%s\n' "$list" > "$TMPD/slice"
  printf '%s' "${extra:+$extra$'\n'}" > "$TMPD/extra"
  tar -cz --owner=0 --group=0 --numeric-owner \
      --transform='s,^res-extra/,res/,' \
      --transform='s,^\(database\|avatars\|locations\)/,res/\1/,' \
      -C "$RES_DIR" -T "$TMPD/slice" \
      -C "$CI_DIR" -T "$TMPD/extra" texts.xml \
    || { OUTCOME="tar failed"; exit 1; }
  OUTCOME="ok"
}

# --- deploy: talking ------------------------------------------------------
#
# say() goes to the deploy log first and to the client second; the second may
# fail once the client is gone, and that must not stop anything.

say() {
  printf '%s\n' "$*" >> "$DLOG"
  printf '%s\n' "$*" 2>/dev/null || true
}

# Run a command with all of its output in the deploy log only.
quiet() {
  printf '+ %s\n' "$*" >> "$DLOG"
  "$@" >> "$DLOG" 2>&1
}

# The end of the deploy log, for a failure the client should see the reason of.
show_tail() {
  say "---- last lines of $DLOG"
  tail -n "${1:-30}" "$DLOG" | sed 's/^/  | /' | while IFS= read -r l; do
    printf '%s\n' "$l" 2>/dev/null || true
  done
}

# --- deploy: checking the tarball -------------------------------------------

check_tarball() {
  local tgz=$1 raw max_raw declared names listing n name path top isdir req f
  gzip -t "$tgz" 2>/dev/null || refuse "not an intact gzip stream"

  max_raw=$((MAX_RAW_MB * 1024 * 1024))
  raw=$(gzip -dc "$tgz" | head -c $((max_raw + 1)) | wc -c)
  [ "$raw" -le "$max_raw" ] || refuse "unpacks to more than $MAX_RAW_MB MB"

  # Names, and the long listing of the same archive, line for line. The
  # escape quoting keeps one member per line whatever its name holds: a
  # newline or any byte outside printable ASCII comes out as a backslash
  # sequence, and a backslash is refused below. --numeric-owner keeps the
  # owner one field wide, so the size is always the third.
  names=$STAGE/names
  listing=$STAGE/listing
  tar -tzf "$tgz" --quoting-style=escape > "$names" 2>/dev/null \
    || refuse "not a readable tar"
  tar -tvzf "$tgz" --numeric-owner --quoting-style=escape > "$listing" 2>/dev/null \
    || refuse "not a readable tar"
  n=$(wc -l < "$names")
  [ "$n" -gt 0 ] || refuse "empty archive"
  [ "$n" -le "$MAX_FILES" ] || refuse "more than $MAX_FILES members"
  [ "$n" -eq "$(wc -l < "$listing")" ] || refuse "listing mismatch"
  # '-' a file, 'd' a directory. Links of either kind, devices and fifos have
  # no place in a source tree, and a symlink is how an archive reaches
  # outside the directory it is unpacked into.
  if cut -c1 "$listing" | grep -qv '^[-d]$'; then
    refuse "links or special files in the archive"
  fi
  # Nor setuid, setgid or sticky bits: the tree is copied into the image, and
  # a setuid-root file there is root inside the container.
  if cut -c2-10 "$listing" | grep -q '[sStT]'; then
    refuse "a setuid, setgid or sticky bit in the archive"
  fi
  # The stream's length is not what lands on disk: a sparse member is a few
  # bytes in the stream and as large as it likes once unpacked. The sizes the
  # members declare are.
  declared=$(awk '{ s += $3 } END { printf "%.0f", s }' "$listing")
  [ "$declared" -le "$max_raw" ] \
    || refuse "its members declare $((declared / 1048576)) MB, more than $MAX_RAW_MB MB"

  : > "$STAGE/members"
  while IFS= read -r name; do
    path=${name#./}
    [ -z "$path" ] && continue           # the "./" of the root itself
    isdir=0
    case $path in */) isdir=1; path=${path%/} ;; esac
    case $path in
      /*)                       refuse "absolute path: $name" ;;
      *\\*)                     refuse "unprintable or escaped name: $name" ;;
      ..|../*|*/..|*/../*)      refuse "path climbs out: $name" ;;
      .|./*|*/.|*/./*|*//*)     refuse "odd path: $name" ;;
    esac
    case /$path/ in
      */.env/*)                 refuse "an .env in the archive: $name" ;;
      /res/*)                   refuse "res/ is the server's own: $name" ;;
      /data/lava.db*)           refuse "a database in the archive: $name" ;;
      */.git/*)                 refuse "git metadata in the archive: $name" ;;
    esac
    top=${path%%/*}
    if [ "$top" = "$path" ] && [ "$isdir" = 0 ]; then
      # A file at the top: Dockerfile, docker-compose.yml, the docs.
      [[ $path =~ ^[A-Za-z0-9._-]+$ ]] || refuse "odd top-level name: $name"
      # docker compose reads compose.yaml before docker-compose.yml, and
      # merges an override file beside either without being asked: one more
      # compose file here would be read by "up" and never by the checks.
      case $path in
        docker-compose.yml) ;;
        compose.y*ml|compose.*.y*ml|docker-compose.*.y*ml|docker-compose.yaml)
          refuse "a compose file besides docker-compose.yml: $name" ;;
      esac
    else
      case " $ALLOWED_DIRS " in
        *" $top "*) ;;
        *) refuse "top-level directory not in ALLOWED_DIRS: $top" ;;
      esac
    fi
    printf '%s\n' "$path" >> "$STAGE/members"
  done < "$names"

  for req in $REQUIRED; do
    grep -qxF "$req" "$STAGE/members" || refuse "missing $req"
  done
  f=$(sort "$STAGE/members" | uniq -d | head -n 1)
  [ -z "$f" ] || refuse "member twice: $f"
}

# --- deploy: the compose policy ---------------------------------------------
#
# The rules are in the header ("THE COMPOSE POLICY"). Two halves: words in the
# file as written, which the normalised form no longer shows, and the
# normalised form itself, which is what "up" acts on.

POLICY_WHY=

# The structural half, in Python: the host's python3 if it has one, else the
# image the game runs now (python:3.12-slim underneath), with no network. The
# normalised config arrives on stdin, so the container needs no mount.
policy_python() {
  if command -v python3 > /dev/null 2>&1; then
    python3 "$@"
  else
    local img
    img=$(docker inspect --format '{{.Image}}' "$GAME" 2>/dev/null) || return 2
    docker run --rm -i --network none --entrypoint python3 "$img" "$@"
  fi
}

COMPOSE_POLICY_PY='
import json, os, sys

cfg = json.load(sys.stdin)
app, res = os.path.normpath(sys.argv[1]), os.path.normpath(sys.argv[2])
why = []

for k, v in cfg.items():
    if k not in ("name", "services", "networks", "volumes") and v:
        why.append("top-level %s" % k)

volumes = cfg.get("volumes") or {}
for name, v in volumes.items():
    extra = sorted(set(v or {}) - {"name"})
    if extra:
        why.append("volume %s has %s" % (name, ", ".join(extra)))

for name, n in (cfg.get("networks") or {}).items():
    n = n or {}
    extra = sorted(set(n) - {"name", "ipam", "driver", "labels"})
    if extra:
        why.append("network %s has %s" % (name, ", ".join(extra)))
    if n.get("driver", "bridge") != "bridge":
        why.append("network %s uses driver %s" % (name, n.get("driver")))

DENY = ("privileged", "cap_add", "devices", "device_cgroup_rules", "gpus",
        "pid", "ipc", "uts", "network_mode", "userns_mode", "cgroup",
        "cgroup_parent", "security_opt", "volumes_from", "runtime",
        "isolation", "secrets", "configs", "credential_spec",
        "use_api_socket", "post_start", "pre_stop", "provider")
BUILD = {"context", "dockerfile", "args", "target", "labels", "pull",
         "no_cache", "tags", "platforms", "shm_size"}

for name, s in (cfg.get("services") or {}).items():
    for k in DENY:
        if s.get(k) not in (None, False, "", [], {}):
            why.append("%s: %s" % (name, k))
    b = s.get("build")
    if b is not None:
        extra = sorted(set(b) - BUILD)
        if extra:
            why.append("%s: build has %s" % (name, ", ".join(extra)))
        ctx = os.path.normpath(str(b.get("context", "")))
        if ctx != app:
            why.append("%s: builds from %s, not %s" % (name, ctx, app))
        df = os.path.normpath(os.path.join(ctx, str(b.get("dockerfile", "Dockerfile"))))
        if not df.startswith(app + os.sep):
            why.append("%s: Dockerfile %s outside %s" % (name, df, app))
    for v in s.get("volumes") or []:
        t = v.get("type")
        src = v.get("source")
        if t == "bind":
            if os.path.normpath(str(src)) != res:
                why.append("%s: bind mount of %s (only %s may be)" % (name, src, res))
            elif not v.get("read_only"):
                why.append("%s: %s mounted writable" % (name, src))
        elif t == "volume":
            if src and src not in volumes:
                why.append("%s: volume %s not declared at the top" % (name, src))
        elif t != "tmpfs":
            why.append("%s: a %s mount" % (name, t))

print("; ".join(why))
sys.exit(1 if why else 0)
'

compose_policy() {  # the staged docker-compose.yml -> 0 within, else POLICY_WHY
  local file=$1 w out rc
  if grep -q '\\' "$file"; then
    POLICY_WHY="a backslash in it (escapes can spell any key)"; return 1
  fi
  if grep -q '!!' "$file"; then
    POLICY_WHY="a !! tag in it"; return 1
  fi
  for w in env_file label_file extends include; do
    if grep -Eq "(^|[^A-Za-z0-9_])$w([^A-Za-z0-9_]|\$)" "$file"; then
      POLICY_WHY="the word $w in it (it reads other files of this host)"; return 1
    fi
  done
  # Normalised as "up" will read it: the real .env, /opt/lava as the project
  # directory, so "." is /opt/lava and LAVA_RES_DIR is what the game mounts.
  local json=${POLICY_TMP:-$STAGE}/compose.json
  if ! docker compose --project-directory "$APP_DIR" --env-file "$APP_DIR/.env" \
         -f "$file" config --format json > "$json" 2>> "$DLOG"; then
    POLICY_WHY="docker compose config failed"; return 1
  fi
  out=$(policy_python -c "$COMPOSE_POLICY_PY" "$APP_DIR" "$RES_DIR" < "$json" 2>> "$DLOG")
  rc=$?
  case $rc in
    0) return 0 ;;
    1) POLICY_WHY=$out; return 1 ;;
    *) POLICY_WHY="the policy check could not run (no python3 here and no running $GAME image)"; return 1 ;;
  esac
}

# --- deploy: the containers -------------------------------------------------

cstate() {   # container -> "status restarts"
  docker inspect -f '{{.State.Status}} {{.RestartCount}}' "$1" 2>/dev/null \
    || echo "missing -"
}

dhealth() {  # container -> docker's own health verdict, if it has one yet
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
    "$1" 2>/dev/null || echo missing
}

# The very check compose's healthcheck runs, without waiting for its 60 s
# interval: docker runs the first probe only one interval after start.
probe() {    # container kind
  timeout 20 docker exec "$1" python3 healthcheck.py "$2" > /dev/null 2>&1
}

# Both services' logs since T0, without the http service's request lines:
# "  HTTP <request line> <code>", whose path is whatever a visitor asked for
# (bootstrap_http.Handler.log_message). A request for /Traceback is not the
# server failing.
fresh_logs() {
  local c
  for c in "$GAME" "$HTTP"; do
    docker logs --since "$T0" "$c" 2>&1 | grep -v '^  HTTP '
  done
}

fresh_count() {  # pattern -> matching lines in fresh_logs
  local k
  k=$(fresh_logs | grep -cE "$1")
  echo "${k:-0}"
}

# Up means: both running, neither restarted since we started watching, both
# answer their probe twice in a row, and no traceback since the deploy began.
WHY=
wait_up() {
  local limit=$1 start=$SECONDS streak=0 c st rc
  local -A base=()
  for c in "$GAME" "$HTTP"; do
    read -r st rc <<< "$(cstate "$c")"
    base[$c]=$rc
  done
  while :; do
    for c in "$GAME" "$HTTP"; do
      read -r st rc <<< "$(cstate "$c")"
      [ "$st" = running ] || { WHY="$c is $st"; return 1; }
      [ "$rc" = "${base[$c]}" ] || { WHY="$c restarted (restart count $rc)"; return 1; }
    done
    if [ "$(fresh_count "$CRASH_PATTERN")" != 0 ]; then
      WHY="a traceback in the log"
      return 1
    fi
    if probe "$GAME" game && probe "$HTTP" http; then
      streak=$((streak + 1))
    else
      streak=0
    fi
    [ "$streak" -ge 2 ] && return 0
    if [ $((SECONDS - start)) -ge "$limit" ]; then
      WHY="not answering after ${limit}s"
      return 1
    fi
    sleep 3
  done
}

# What the update channel serves now: the sha256 the launcher compares with.
served_texts() {
  timeout 120 docker exec "$HTTP" python3 -c '
import json, os, urllib.request
port = os.environ.get("LAVA_HTTP_PORT", "8080")
url = "http://127.0.0.1:%s/exe/lavaclient/manifest" % port
doc = json.load(urllib.request.urlopen(url, timeout=110))
print(doc["resources"][0]["sha256"])' 2>/dev/null
}

# The string table compiled into the published launcher. csc /resource stores
# a managed resource as a 4-byte little-endian length and then the bytes, and
# the table starts with names.PROLOGUE, so the blob is found by its first
# bytes and measured by the length in front of them. Read inside the http
# container because that is where a Python is sure to be; the exe goes in on
# stdin.
exe_texts() {
  [ -f "$LAUNCHER_EXE" ] || return 1
  timeout 60 docker exec -i "$HTTP" python3 -c '
import hashlib, struct, sys
data = sys.stdin.buffer.read()
head = "﻿<?xml version=\x271.0\x27?>".encode("utf-8")
i = data.find(head)
while i != -1:
    if i >= 4:
        n = struct.unpack_from("<I", data, i - 4)[0]
        blob = data[i:i + n]
        if len(blob) == n > len(head) and blob.rstrip().endswith(b"</data>"):
            print(hashlib.sha256(blob).hexdigest())
            sys.exit(0)
    i = data.find(head, i + 1)
sys.exit(1)' < "$LAUNCHER_EXE" 2>/dev/null
}

# --- deploy: backups ----------------------------------------------------------

backup_ids() {   # every CI backup id that still has any part left, oldest first
  {
    (cd "$BACKUP_DIR" && ls -1d lava.bak-*-ci 2>/dev/null | sed 's/^lava\.bak-//')
    (cd "$BACKUP_DIR" && ls -1 lava-pg-backup-*-ci.dump 2>/dev/null \
       | sed 's/^lava-pg-backup-//; s/\.dump$//')
    docker images "$IMAGE" --format '{{.Tag}}' 2>/dev/null | sed -n 's/^pre-//p'
  } | grep -E '^[0-9]{8}-[0-9]{6}-ci$' | sort -u
}

PRUNED=
prune() {
  local ids n id
  mapfile -t ids < <(backup_ids)
  n=${#ids[@]}
  [ "$n" -gt "$KEEP" ] || return 0
  for id in "${ids[@]:0:n-KEEP}"; do
    [[ $id =~ ^[0-9]{8}-[0-9]{6}-ci$ ]] || continue
    rm -rf -- "$BACKUP_DIR/lava.bak-$id"
    rm -f -- "$BACKUP_DIR/lava-pg-backup-$id.dump"
    quiet docker rmi "$IMAGE:pre-$id"
    PRUNED="$PRUNED $id"
  done
  # Deploy logs: the last fifty.
  ls -1 "$LOG_DIR"/deploy-*.log 2>/dev/null | sort | head -n -50 \
    | while IFS= read -r f; do rm -f -- "$f"; done
}

# --- deploy -------------------------------------------------------------------

PHASE=start
SWAPPED=0
ID=
SHA=
REPORT=()
add() { REPORT+=("$*"); }

report() {
  local line
  say "=== report"
  for line in "${REPORT[@]}"; do say "$line"; done
  say "log:      $DLOG"
  say "=== end"
}

rollback() {
  local had_image=$1
  PHASE=rollback
  say "-- rolling back to $ID"
  if ! quiet rsync -a --delete "$BACKUP_DIR/lava.bak-$ID/" "$APP_DIR/"; then
    add "rollback: FAILED to restore the tree from $BACKUP_DIR/lava.bak-$ID"
    return 1
  fi
  if [ "$had_image" = 1 ]; then
    quiet docker tag "$IMAGE:pre-$ID" "$IMAGE:latest" \
      || { add "rollback: FAILED to retag $IMAGE:pre-$ID"; return 1; }
    (cd "$APP_DIR" && quiet timeout 600 docker compose up -d --no-build) \
      || { add "rollback: FAILED: docker compose up"; return 1; }
  else
    # No container ran before this deploy, so there is no image to go back
    # to: build the restored tree instead.
    (cd "$APP_DIR" && quiet timeout 1200 docker compose up -d --build) \
      || { add "rollback: FAILED: docker compose up --build"; return 1; }
  fi
  T0=$(date -u +%FT%TZ)
  if ! wait_up "$HEALTH_TIMEOUT"; then
    add "rollback: the old version did not come up either: $WHY"
    return 1
  fi
  add "rollback: done, $GAME and $HTTP are up on the previous version"
  return 0
}

# Every failure after the request was accepted ends here.
fail() {
  local why=$1
  OUTCOME="failed ($PHASE): $why"
  say "!! $PHASE failed: $why"
  case $PHASE in
    build)
      show_tail 40 ;;
    up)
      # The game's own words since the deploy began say more than the build.
      say "---- $GAME since $T0"
      docker logs --since "$T0" "$GAME" 2>&1 | tail -n 30 | while IFS= read -r l; do say "  | $l"; done ;;
  esac
  add "result:   FAILED at $PHASE: $why"
  if [ "$SWAPPED" = 1 ]; then
    if rollback "$HAD_IMAGE"; then
      add "state:    rolled back; the database is as the new code left it (dump: $DUMP_NOTE)"
      report
      exit 1
    fi
    add "state:    UNKNOWN -- rollback failed, see the log; backup id $ID"
    OUTCOME="$OUTCOME; rollback failed"
    report
    exit 3
  fi
  add "state:    nothing on the server was changed"
  report
  exit 1
}

cmd_deploy() {
  SHA=$1
  local sum=$2 got size max prev_sha prev_texts new_texts exe_sha img_before img_after
  local f want host inside errs h st rc free

  exec 9> "$CI_DIR/deploy.lock"
  if ! flock -w "$LOCK_WAIT" 9; then
    refuse "another deploy still holds the lock after ${LOCK_WAIT}s"
  fi

  ID=$(date +%Y%m%d-%H%M%S)-ci
  while [ -e "$BACKUP_DIR/lava.bak-$ID" ]; do
    sleep 1
    ID=$(date +%Y%m%d-%H%M%S)-ci
  done
  DLOG=$LOG_DIR/deploy-$ID-${SHA:0:12}.log
  : > "$DLOG"
  say "gate: deploy $SHA as $ID"
  add "commit:   $SHA"
  add "backup:   $ID"

  # 2. receive
  PHASE=receive
  rm -rf -- "$STAGE"
  mkdir -p "$STAGE/tree"
  max=$((MAX_TGZ_MB * 1024 * 1024))
  head -c $((max + 1)) > "$STAGE/in.tgz"
  size=$(stat -c %s "$STAGE/in.tgz")
  [ "$size" -le "$max" ] || refuse "tarball larger than $MAX_TGZ_MB MB"
  got=$(sha256sum < "$STAGE/in.tgz" | cut -c1-64)
  [ "$got" = "$sum" ] || refuse "sha256 mismatch: got $got ($size bytes), expected $sum"

  # From here on the deploy finishes whatever happens to the client.
  trap '' HUP PIPE
  say "gate: received $size bytes, sha256 ok"

  # 3-4. check, unpack, check again
  PHASE=validate
  check_tarball "$STAGE/in.tgz"
  # Owned by root and under umask 022 whatever the archive says.
  tar -xzf "$STAGE/in.tgz" -C "$STAGE/tree" --no-same-owner --no-same-permissions 2>> "$DLOG" \
    || refuse "unpacking failed"
  # The listing was checked; this is the disk agreeing with it.
  f=$(find "$STAGE/tree" -mindepth 1 ! -type f ! -type d -print -quit)
  [ -z "$f" ] || refuse "not a file or a directory after unpacking: $f"
  [ -f "$APP_DIR/.env" ] || refuse "$APP_DIR/.env is missing; the first install is by hand"
  [ -f "$FILTER" ] || refuse "$FILTER is missing; re-run install.sh"
  if ! (cd "$STAGE/tree" && quiet docker compose --env-file "$APP_DIR/.env" \
          -f docker-compose.yml config -q); then
    refuse "docker-compose.yml does not validate against $APP_DIR/.env"
  fi
  if [ "$COMPOSE_POLICY" != 0 ]; then
    compose_policy "$STAGE/tree/docker-compose.yml" \
      || refuse "docker-compose.yml is outside the compose policy: $POLICY_WHY"
    say "gate: docker-compose.yml within the compose policy"
  else
    add "policy:   COMPOSE_POLICY=0 in gate.conf -- docker-compose.yml not policed"
  fi
  say "gate: archive ok ($(wc -l < "$STAGE/members") members)"

  # Notes for the owner, not reasons to stop: this script and the filter it
  # swaps with are the installed copies, and a newer pair in the repository
  # takes effect only when install.sh is run again.
  if ! cmp -s "$STAGE/tree/deploy/remote/lava-gate.sh" "$SELF"; then
    add "gate:     the repository holds a different lava-gate.sh -- re-run install.sh to use it"
  fi
  if ! cmp -s "$STAGE/tree/deploy/rsync.filter" "$FILTER"; then
    add "filter:   the repository holds a different rsync.filter -- re-run install.sh to use it"
  fi

  prev_sha=$(cat "$STATE_DIR/deployed" 2>/dev/null | cut -d' ' -f1)
  add "previous: ${prev_sha:-unknown (no CI deploy recorded)}"
  prev_texts=$(served_texts) || prev_texts=

  # 5. backup
  PHASE=backup
  free=$(df -Pm "$BACKUP_DIR" | awk 'NR == 2 { print $4 }')
  [ "${free:-0}" -ge "$MIN_FREE_MB" ] \
    || fail "only ${free} MB free on $BACKUP_DIR, need $MIN_FREE_MB"
  DUMP_NOTE="none"
  if [ -n "$PG_CONTAINER" ]; then
    local dump=$BACKUP_DIR/lava-pg-backup-$ID.dump
    # shellcheck disable=SC2016  # expanded inside the container, on purpose
    # The braces put a failure to open the dump file in the log too, not
    # only pg_dump's own complaints.
    if ! { docker exec "$PG_CONTAINER" sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' \
             > "$dump.part"; } 2>> "$DLOG"; then
      rm -f -- "$dump.part"
      fail "pg_dump in $PG_CONTAINER into $dump"
    fi
    [ -s "$dump.part" ] || { rm -f -- "$dump.part"; fail "pg_dump wrote nothing"; }
    mv -- "$dump.part" "$dump"
    DUMP_NOTE=$dump
    say "gate: database dumped to $dump ($(stat -c %s "$dump") bytes)"
  fi
  quiet cp -a "$APP_DIR" "$BACKUP_DIR/lava.bak-$ID" || fail "cp -a $APP_DIR"
  HAD_IMAGE=0
  img_before=$(docker inspect --format '{{.Image}}' "$GAME" 2>/dev/null) || img_before=
  if [ -n "$img_before" ]; then
    quiet docker tag "$img_before" "$IMAGE:pre-$ID" || fail "docker tag $IMAGE:pre-$ID"
    HAD_IMAGE=1
  fi
  say "gate: backup $ID taken (tree, ${img_before:+image, }dump: $DUMP_NOTE)"
  add "saved:    $BACKUP_DIR/lava.bak-$ID, $DUMP_NOTE${img_before:+, $IMAGE:pre-$ID}"

  # 6. swap. The fixed excludes come first, and the first matching rule wins:
  # whatever the installed filter says, .env and res/ are not touched.
  PHASE=swap
  SWAPPED=1
  quiet rsync -a --delete --exclude=/.env --exclude=/res/ \
      --filter="merge $FILTER" "$STAGE/tree/" "$APP_DIR/" \
    || fail "rsync into $APP_DIR"

  # 7. build and start
  PHASE=build
  T0=$(date -u +%FT%TZ)
  (cd "$APP_DIR" && quiet timeout 1200 docker compose up -d --build) \
    || fail "docker compose up -d --build"
  img_after=$(docker inspect --format '{{.Image}}' "$GAME" 2>/dev/null) || img_after=
  if [ "$img_after" = "$img_before" ]; then
    add "image:    ${img_after:0:19} (unchanged: nothing the image takes changed)"
  else
    add "image:    ${img_after:0:19} (was ${img_before:0:19})"
  fi

  # 8. up, settled, and quiet
  PHASE=up
  say "gate: waiting for $GAME and $HTTP"
  wait_up "$HEALTH_TIMEOUT" || fail "$WHY"
  say "gate: both answer; watching ${SETTLE}s more"
  sleep "$SETTLE"
  for c in "$GAME" "$HTTP"; do
    read -r st rc <<< "$(cstate "$c")"
    [ "$st" = running ] || fail "$c is $st after settling"
  done
  probe "$GAME" game || fail "$GAME stopped answering after settling"
  probe "$HTTP" http || fail "$HTTP stopped answering after settling"
  errs=$(fresh_count "$ERROR_PATTERN")
  add "health:   $GAME up (docker: $(dhealth "$GAME")), $HTTP up (docker: $(dhealth "$HTTP"))"
  add "errors:   $errs log lines matching /$ERROR_PATTERN/ since $T0"
  if [ "$errs" != 0 ]; then
    docker logs --since "$T0" "$GAME" 2>&1 | grep -E "$ERROR_PATTERN" | head -n 5 \
      | while IFS= read -r l; do say "  | $l"; done
    fail "$errs error line(s) in the fresh logs"
  fi

  # 9. the key files: in /opt/lava, and inside the image that is running
  PHASE=verify
  for f in $KEY_FILES; do
    [ -f "$STAGE/tree/$f" ] || continue
    want=$(sha256sum < "$STAGE/tree/$f" | cut -c1-64)
    host=$(sha256sum < "$APP_DIR/$f" | cut -c1-64)
    [ "$host" = "$want" ] || fail "$APP_DIR/$f differs from the tarball"
    case $f in
      server/*|data/*)
        inside=$(timeout 30 docker exec "$GAME" sha256sum "/app/$f" 2>/dev/null | cut -c1-64)
        [ "$inside" = "$want" ] || fail "/app/$f in $GAME differs from the tarball"
        add "file:     ${want:0:16}  $f (tree and image)" ;;
      *)
        add "file:     ${want:0:16}  $f" ;;
    esac
  done

  PHASE=done
  SWAPPED=0
  OUTCOME="deployed"
  printf '%s %s %s\n' "$SHA" "$ID" "$(date -u +%FT%TZ)" > "$STATE_DIR/deployed"

  # 10. the string table, and whether the published launcher still carries it
  new_texts=$(served_texts) || new_texts=
  if [ -z "$new_texts" ]; then
    add "texts:    the manifest did not answer; not compared"
  else
    if [ -z "$prev_texts" ]; then
      add "texts:    served ${new_texts:0:16} (before: unknown)"
    elif [ "$prev_texts" = "$new_texts" ]; then
      add "texts:    served ${new_texts:0:16}, unchanged by this deploy"
    else
      add "texts:    served ${new_texts:0:16}, CHANGED by this deploy (was ${prev_texts:0:16})"
    fi
    if exe_sha=$(exe_texts); then
      if [ "$exe_sha" = "$new_texts" ]; then
        add "launcher: up to date -- $(basename "$LAUNCHER_EXE") carries the served table"
      else
        add "launcher: REBUILD DUE -- $(basename "$LAUNCHER_EXE") carries ${exe_sha:0:16}, the server serves ${new_texts:0:16}"
      fi
    else
      add "launcher: $LAUNCHER_EXE not found or unreadable; not compared"
    fi
  fi

  prune
  add "kept:     $(backup_ids | wc -l) CI backup(s)${PRUNED:+, pruned:$PRUNED}"
  add "result:   deployed"
  report
  rm -rf -- "$STAGE"
  exit 0
}

# --- dispatch -----------------------------------------------------------------

[ "$KEYMODE" != bad ] \
  || refuse "the forced command in authorized_keys has arguments the gate does not know (only --assets-only)"

# install.sh asks whether the compose file that runs now is within the
# policy -- the same function a deploy calls, on a file named in the
# environment. Only for root at this machine's own prompt: never over ssh
# (sshd sets SSH_CONNECTION, and no client can set this variable -- sshd
# passes a client only LANG and LC_*), never with a request in hand.
if [ -n "${LAVA_GATE_POLICY_ONLY:-}" ] && [ -z "${SSH_CONNECTION:-}" ] \
     && [ -z "${SSH_ORIGINAL_COMMAND+x}" ]; then
  TMPD=$(mktemp -d "$CI_DIR/.policy.XXXXXX")
  POLICY_TMP=$TMPD
  DLOG=$TMPD/log
  if compose_policy "$LAVA_GATE_POLICY_ONLY"; then
    OUTCOME="policy check: within"
    exit 0
  fi
  echo "$POLICY_WHY"
  OUTCOME="policy check: outside: $POLICY_WHY"
  exit 1
fi

case $REQ in
  assets-hash)
    cmd_assets_hash ;;
  assets)
    cmd_assets ;;
  deploy\ *)
    [ "$KEYMODE" = full ] \
      || refuse "this key may only fetch the test assets (--assets-only); the deploy needs the deploying key"
    if [[ $REQ =~ ^deploy\ ([0-9a-f]{40})\ ([0-9a-f]{64})$ ]]; then
      cmd_deploy "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    else
      refuse "usage: deploy <40-hex commit> <64-hex sha256 of the tarball>"
    fi ;;
  *)
    refuse "not a gate command (assets-hash | assets | deploy <commit> <sha256>)" ;;
esac
