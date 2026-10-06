#!/usr/bin/env bash
# The gate (lava-gate.sh) against a throwaway layout, end to end, with real
# containers -- on a development machine with docker, never on the server:
#
#   bash deploy/remote/test_gate.sh WORK SLICE TEXTS RES_EXTRA_TGZ [LAUNCHER_EXE]
#
#   WORK            an empty directory on a Linux filesystem; WORK/opt stands
#                   in for /opt
#   SLICE           the server's slice of res/ (deploy.sh --with-data's list)
#   TEXTS           the original texts.xml
#   RES_EXTRA_TGZ   what deploy/ci/make_test_extras.sh made
#   LAUNCHER_EXE    a published LavaReborn.exe, for the string-table line
#
# CLIENT_ORIG=DIR in the environment: a folder holding the original main.swf
# and database/locations.xml; with it the client release is tested too. With
# CLIENT_PROJECTOR=fp32_sa.exe as well (and the mono image of LAUNCHER_IMAGE
# pulled), so is the launcher the gate builds and publishes.
#
# Everything docker here is named cicdtest-* (containers, compose project,
# volume, image), or cicdvictim* for the stand-ins of another stack's volume,
# network and image, and removed at the end (KEEP_DOCKER=1 keeps it). The gate is
# installed by install.sh into WORK/opt/lava-ci; a stand-in "ssh" on PATH runs
# it the way sshd runs a forced command, so deploy/ci/fetch_assets.sh and
# send.sh are exercised as CI runs them. The trees deployed are this
# repository as deploy/rsync.filter passes it, with the compose file renamed
# onto the throwaway names. Prints PASS/FAIL per check and exits non-zero if
# any failed.
set -u

[ $# -ge 4 ] || { echo "usage: $0 WORK SLICE TEXTS RES_EXTRA_TGZ [LAUNCHER_EXE]" >&2; exit 2; }
T=$(mkdir -p "$1" && cd "$1" && pwd)
SLICE=$(cd "$2" && pwd)
TEXTS=$3
EXTRA=$4
EXE=${5:-}
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
GATE=$T/opt/lava-ci/lava-gate.sh
HTTP_PORT=18080
PASS=0
FAILS=0
ok()  { PASS=$((PASS + 1)); echo "  PASS  $*"; }
bad() { FAILS=$((FAILS + 1)); echo "  FAIL  $*"; }
check() { if [ "$2" = "$3" ]; then ok "$1 ($2)"; else bad "$1: got '$2', want '$3'"; fi; }

cleanup_docker() {
  docker rm -f cicdtest-game cicdtest-http cicdtest-pg > /dev/null 2>&1
  docker volume rm cicdtest_lava-db cicdvictim_data > /dev/null 2>&1
  docker network rm cicdtest_default cicdvictim_net > /dev/null 2>&1
  for t in $(docker images cicdtest-lava-server --format '{{.Repository}}:{{.Tag}}') cicdvictim-img:1; do
    docker rmi "$t" > /dev/null 2>&1
  done
}

tree_sum() {  # everything under /opt/lava but res/
  (cd "$T/opt/lava" && find . -path ./res -prune -o -type f -print0 | sort -z \
     | xargs -0 sha256sum | sha256sum | cut -c1-16)
}
nbackups() { ls -d "$T"/opt/lava.bak-*-ci 2>/dev/null | wc -l; }
ndumps()   { ls "$T"/opt/lava-pg-backup-*-ci.dump 2>/dev/null | wc -l; }
ntags()    { docker images cicdtest-lava-server --format '{{.Tag}}' | grep -c '^pre-'; }
game_img() { docker inspect -f '{{.Image}}' cicdtest-game 2>/dev/null; }
probes()   { docker exec cicdtest-game python3 healthcheck.py game > /dev/null 2>&1 \
               && docker exec cicdtest-http python3 healthcheck.py http > /dev/null 2>&1 \
               && echo up || echo down; }
fake_sha() { echo "$1" | sha1sum | cut -c1-40; }
sum_of()   { sha256sum < "$1" | cut -c1-64; }
gate()     { SSH_CLIENT="198.51.100.7 1 22" "$GATE" "$@"; }

# The repository as the filter passes it, the compose file on throwaway names.
mk_tree() {
  local d=$1
  rm -rf "$d"; mkdir -p "$d"
  rsync -a --filter="merge $REPO/deploy/rsync.filter" "$REPO/" "$d/"
  sed -i -e 's/container_name: lava-game/container_name: cicdtest-game/' \
         -e 's/container_name: lava-http/container_name: cicdtest-http/' \
         -e 's/^\(\s*image:\) lava-server$/\1 cicdtest-lava-server/' "$d/docker-compose.yml"
}
mark() {  # tree text -> the tree's server.py ends with that line
  echo "# cicd test: $2" >> "$1/server/server.py"
}

# --- the layout ---------------------------------------------------------------
echo "== layout in $T"
cleanup_docker
rm -rf "${T:?}/opt" "$T/bin" "$T/trees" "$T/bad" "$T"/*.tgz "$T"/*.out "$T"/*.md
mkdir -p "$T/opt/lava/res" "$T/opt/lava-ci" "$T/opt/lava-site/download" "$T/bin" "$T/trees" "$T/bad"
cp -a "$SLICE/." "$T/opt/lava/res/"
[ -n "$EXE" ] && cp "$EXE" "$T/opt/lava-site/download/LavaReborn.exe"
cat > "$T/opt/lava/.env" <<EOF
COMPOSE_PROJECT_NAME=cicdtest
LAVA_RES_DIR=$T/opt/lava/res
LAVA_PUBLIC_HOST=127.0.0.1
LAVA_BIND=127.0.0.1
LAVA_GAME_PORT=19775
LAVA_POLICY_PUBLIC_PORT=18430
LAVA_HTTP_PORT=$HTTP_PORT
EOF

umask 022
cat > "$T/bin/ssh" <<EOF
#!/bin/bash
# "ssh [opts] HOST CMD..." -> the gate, as sshd runs a forced command.
while [ \$# -gt 0 ]; do case \$1 in -*) shift ;; *) break ;; esac; done
shift
SSH_ORIGINAL_COMMAND="\$*" SSH_CLIENT="198.51.100.7 50000 22" SSH_CONNECTION="198.51.100.7 50000 10.0.0.1 22" exec "$GATE"
EOF
chmod +x "$T/bin/ssh"

echo "== install.sh into the layout"
LAVA_CI_DIR=$T/opt/lava-ci LAVA_APP_DIR=$T/opt/lava bash "$REPO/deploy/remote/install.sh" \
  --pubkey "ssh-ed25519 AAAATEST lava-ci" --assets-pubkey "ssh-ed25519 AAAATESTB lava-ci-assets" \
  > "$T/install1.out" 2>&1
check "install.sh" "$?" 0
sed 's/^/    /' "$T/install1.out" | tail -n 8
[ -x "$GATE" ] && ok "gate installed" || bad "gate not installed"
cmp -s "$GATE" "$REPO/deploy/remote/lava-gate.sh" && ok "installed gate == repo gate" || bad "installed gate differs"
check "gate.conf RES_DIR from .env" "$(sed -n 's/^RES_DIR=//p' "$T/opt/lava-ci/gate.conf")" "$T/opt/lava/res"
check "the --assets-only line printed" "$(grep -c 'lava-gate.sh --assets-only",restrict' "$T/install1.out")" 1
LAVA_CI_DIR=$T/opt/lava-ci LAVA_APP_DIR=$T/opt/lava bash "$REPO/deploy/remote/install.sh" \
  --pubkey 'ssh-ed25519 AAAA" evil' > /dev/null 2>&1
check "install.sh refuses a key line with a quote in it" "$?" 2
cp "$TEXTS" "$T/opt/lava-ci/texts.xml"
mkdir -p "$T/opt/lava-ci/res-extra" && tar -xzf "$EXTRA" --no-same-owner -C "$T/opt/lava-ci/res-extra"
# The test's own settings over the production defaults install.sh wrote.
cat >> "$T/opt/lava-ci/gate.conf" <<EOF
BACKUP_DIR=$T/opt
KEEP=2
PG_CONTAINER=cicdtest-pg
GAME=cicdtest-game
HTTP=cicdtest-http
IMAGE=cicdtest-lava-server
PROJECT=
LAUNCHER_EXE=$T/opt/lava-site/download/LavaReborn.exe
MAX_TGZ_MB=8
MAX_RAW_MB=64
MIN_FREE_MB=1024
HEALTH_TIMEOUT=180
SETTLE=12
LOCK_WAIT=5
EOF

# The shared database's stand-in, with one row the dumps must carry.
docker run -d --name cicdtest-pg -e POSTGRES_USER=lava -e POSTGRES_PASSWORD=t -e POSTGRES_DB=lava postgres:16-alpine > /dev/null
check "Postgres stand-in started" "$?" 0
for _ in $(seq 1 60); do docker exec cicdtest-pg pg_isready -U lava > /dev/null 2>&1 && break; sleep 1; done
sleep 2
docker exec cicdtest-pg psql -qU lava -d lava -c "CREATE TABLE marker (v text); INSERT INTO marker VALUES ('before');" > /dev/null
check "Postgres stand-in holds the marker row" "$?" 0
pg_up() { docker exec cicdtest-pg pg_isready -U lava > /dev/null 2>&1 && echo up || echo down; }

# --- assets -------------------------------------------------------------------
echo "== assets"
H=$(PATH=$T/bin:$PATH ssh lava-gate assets-hash)
check "assets-hash is a sha256" "$(echo "$H" | grep -cE '^[0-9a-f]{64}$')" 1
check "assets-hash is stable" "$(PATH=$T/bin:$PATH ssh lava-gate assets-hash)" "$H"
PATH=$T/bin:$PATH bash "$REPO/deploy/ci/fetch_assets.sh" "$T/ci-assets" "$H" > "$T/fetch.out" 2>&1
check "fetch_assets.sh: digest of what arrived == gate's" "$?" 0
sed 's/^/    /' "$T/fetch.out"
check "the slice arrived as it is on the server" \
  "$(cd "$T/ci-assets/res" && find database/mobs.xml database/objects.xml avatars locations -path locations/libs -prune -o -type f -print | sort | xargs -d '\n' sha256sum | sha256sum | cut -c1-16)" \
  "$(cd "$SLICE" && find database/mobs.xml database/objects.xml avatars locations -type f | sort | xargs -d '\n' sha256sum | sha256sum | cut -c1-16)"
check "texts.xml arrived equal" "$(cmp -s "$T/ci-assets/texts.xml" "$TEXTS" && echo same || echo differs)" same
check "the extras arrived under res/" "$(cmp -s "$T/ci-assets/res/locations/libs/Vadihalfa port.swf" "$T/opt/lava-ci/res-extra/locations/libs/Vadihalfa port.swf" && echo same || echo differs)" same
echo "x" >> "$T/opt/lava-ci/texts.xml"
PATH=$T/bin:$PATH bash "$REPO/deploy/ci/fetch_assets.sh" "$T/ci-assets2" "$H" > "$T/fetch2.out" 2>&1
check "an asset changed between hash and fetch is caught" "$?" 1
grep -q '::error title=Assets::' "$T/fetch2.out" && ok "and reported as a workflow error" || bad "no ::error line"
cp "$TEXTS" "$T/opt/lava-ci/texts.xml"
mv "$T/opt/lava-ci/texts.xml" "$T/opt/lava-ci/texts.xml.away"
SSH_ORIGINAL_COMMAND=assets-hash gate > /dev/null 2> "$T/notexts.err"
check "no texts.xml -> assets-hash fails" "$?" 1
mv "$T/opt/lava-ci/texts.xml.away" "$T/opt/lava-ci/texts.xml"

# --- refused requests ------------------------------------------------------------
echo "== refused requests"
nref=0
for req in "" "whoami" "assets; id" "assets-hash --x" "assets-hash"$'\n'"id" "assets"$'\n' \
           "deploy" "deploy abc" "deploy $(fake_sha a)" "deploy $(fake_sha a) $(fake_sha b)" \
           "deploy $(fake_sha a) $(printf '%064d' 0) extra" "deploy $(fake_sha a) $(printf '%064d' 0) " \
           " deploy $(fake_sha a) $(printf '%064d' 0)" "deploy $(fake_sha a)"$'\t'"$(printf '%064d' 0)" \
           "scp -t /tmp" "bash -i" "ASSETS" "deploy $(fake_sha a | tr a-f A-F) $(printf '%064d' 0)" '$(id)'; do
  SSH_ORIGINAL_COMMAND="$req" gate < /dev/null > /dev/null 2>&1
  rc=$?   # before the label's own $(...) resets $?
  check "refused: $(printf '%q' "$req" | cut -c1-60)" "$rc" 2
  nref=$((nref + 1))
done
(unset SSH_ORIGINAL_COMMAND; gate < /dev/null > /dev/null 2>&1); check "refused: no command at all" "$?" 2
nref=$((nref + 1))
SSH_ORIGINAL_COMMAND=assets-hash gate --assets-only > /dev/null 2>&1
check "--assets-only key: assets-hash answers" "$?" 0
SSH_ORIGINAL_COMMAND="deploy $(fake_sha a) $(printf '%064d' 0)" gate --assets-only < /dev/null > /dev/null 2>&1
check "--assets-only key: deploy refused" "$?" 2
SSH_ORIGINAL_COMMAND=assets-hash gate --shell > /dev/null 2>&1
check "unknown forced-command argument: even assets-hash refused" "$?" 2
SSH_ORIGINAL_COMMAND=assets-hash gate --assets-only extra > /dev/null 2>&1
check "two forced-command arguments refused" "$?" 2
# the policy-only mode is root's at the prompt, never a client's
(unset SSH_ORIGINAL_COMMAND; LAVA_GATE_POLICY_ONLY=/etc/hostname SSH_CONNECTION="198.51.100.7 1 10.0.0.1 22" gate < /dev/null > /dev/null 2>&1)
check "policy-only mode over ssh is just a refused request" "$?" 2
nref=$((nref + 4))
# install.sh's own: "echo hello" and an --assets-only deploy
check "every refusal is in gate.log" "$(grep -c 'rc=2 refused' "$T/opt/lava-ci/log/gate.log")" "$((nref + 2))"

# --- the starting point: production as deploy.sh left it -----------------------
echo "== v0 by hand, as deploy.sh would"
mk_tree "$T/trees/v0"
rsync -a --delete --filter="merge $T/trees/v0/deploy/rsync.filter" "$T/trees/v0/" "$T/opt/lava/"
(cd "$T/opt/lava" && docker compose up -d --build > "$T/v0.build.log" 2>&1)
check "v0 compose up" "$?" 0
for _ in $(seq 1 60); do [ "$(probes)" = up ] && break; sleep 2; done
check "v0 answers" "$(probes)" up
V0_IMG=$(game_img)
SUM0=$(tree_sum)

echo "== install.sh again: the running compose file against the policy"
LAVA_CI_DIR=$T/opt/lava-ci LAVA_APP_DIR=$T/opt/lava bash "$REPO/deploy/remote/install.sh" > "$T/install2.out" 2>&1
grep -E 'policy|gate.conf' "$T/install2.out" | sed 's/^/    /'
check "the running docker-compose.yml is within the policy" \
  "$(grep -c 'is within the compose policy' "$T/install2.out")" 1
check "a second install keeps gate.conf" "$(grep -c '^KEEP=2$' "$T/opt/lava-ci/gate.conf")" 1

echo "== the compose project is held to the one that runs"
# The test's .env names the project (COMPOSE_PROJECT_NAME), which outranks a
# "name:" in the file; production's may not. So a second app directory, with
# an .env that does not: there the file's own "name:" decides, as it would
# on a server whose .env leaves it out.
policy_only() {  # compose-file -> the gate's policy-only verdict, "rc first-reason"
  local out rc
  out=$(env -u SSH_CONNECTION -u SSH_ORIGINAL_COMMAND LAVA_GATE_POLICY_ONLY="$1" \
          SSH_CLIENT="test 0 0" "$GATE" 2>&1)
  rc=$?
  echo "$rc ${out%%;*}"
}
mkdir -p "$T/opt/lava2"
printf 'LAVA_RES_DIR=%s\nLAVA_BIND=127.0.0.1\n' "$T/opt/lava/res" > "$T/opt/lava2/.env"
cp "$T/opt/lava/docker-compose.yml" "$T/opt/lava2/plain.yml"
{ echo "name: cicdtest"; cat "$T/opt/lava/docker-compose.yml"; } > "$T/opt/lava2/same.yml"
{ echo "name: cicdvictim"; cat "$T/opt/lava/docker-compose.yml"; } > "$T/opt/lava2/other.yml"
echo "APP_DIR=$T/opt/lava2" >> "$T/opt/lava-ci/gate.conf"
check "no name, so the directory's: refused" "$(policy_only "$T/opt/lava2/plain.yml")" "1 project lava2, not cicdtest"
check "name: the running project -> within" "$(policy_only "$T/opt/lava2/same.yml")" "0 "
check "name: another project -> refused" "$(policy_only "$T/opt/lava2/other.yml")" "1 project cicdvictim, not cicdtest"
sed -i '$d' "$T/opt/lava-ci/gate.conf"
echo "PROJECT=cicdother" >> "$T/opt/lava-ci/gate.conf"
check "PROJECT in gate.conf outranks the container" "$(policy_only "$T/opt/lava/docker-compose.yml")" "1 project cicdtest, not cicdother"
sed -i '$d' "$T/opt/lava-ci/gate.conf"
check "and without it the running file is within again" "$(policy_only "$T/opt/lava/docker-compose.yml")" "0 "

# --- bad tarballs -----------------------------------------------------------------
echo "== bad tarballs"
rsync -a --filter="merge $T/trees/v0/deploy/rsync.filter" "$T/trees/v0/" "$T/trees/v0.packed/"
python3 "$REPO/deploy/remote/craft_tarballs.py" "$T/trees/v0.packed" "$T/bad" > /dev/null
# Sparse members, by GNU tar in both its formats: 1 GiB declared, bytes sent.
cp -a "$T/trees/v0.packed" "$T/trees/sparse"
truncate -s 1G "$T/trees/sparse/data/sparse.bin"
for fmt in gnu pax; do
  tar -C "$T/trees/sparse" --sparse --format=$fmt --owner=0 --group=0 -czf "$T/bad/sparse_$fmt.tgz" .
done
rm -rf "$T/trees/sparse"
# Compose files outside the policy, each packed by pack.sh as CI would.
policy_tree() {  # name python-edit -> $T/bad/policy_<name>.tgz
  local d=$T/trees/policy_$1
  rm -rf "$d"; cp -a "$T/trees/v0" "$d"
  python3 - "$d/docker-compose.yml" "$2" <<'PY'
import sys
path, edit = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
game = "    container_name: cicdtest-game\n"
assert game in text
edits = {
    "privileged": lambda t: t.replace(game, game + "    privileged: true\n", 1),
    "cap_add": lambda t: t.replace(game, game + "    cap_add: [SYS_ADMIN]\n", 1),
    "pid_host": lambda t: t.replace(game, game + "    pid: host\n", 1),
    "host_root": lambda t: t.replace("      - lava-db:/var/lib/lava\n",
                                     "      - lava-db:/var/lib/lava\n      - /:/host\n", 1),
    "docker_sock": lambda t: t.replace("      - lava-db:/var/lib/lava\n",
                                       "      - lava-db:/var/lib/lava\n      - /var/run/docker.sock:/var/run/docker.sock\n", 1),
    "res_writable": lambda t: t.replace(":/res:ro", ":/res", 1),
    "volume_driver": lambda t: t.replace("\n  lava-db:\n",
                                         "\n  lava-db:\n    driver: local\n    driver_opts: {type: none, o: bind, device: /}\n", 1),
    "build_context": lambda t: t.replace("    build: .\n", "    build:\n      context: /etc\n", 1),
    "build_extra": lambda t: t.replace("    build: .\n", "    build:\n      context: .\n      additional_contexts:\n        root: /root\n", 1),
    "env_file": lambda t: t.replace(game, game + "    env_file: /dev/null\n", 1),
    "backslash": lambda t: t.replace(game, game + "    labels: {\"x\": \"a\\tb\"}\n", 1),
    "volumes_from": lambda t: t.replace(game, game + "    volumes_from: [\"container:cicdtest-pg\"]\n", 1),
    "secrets": lambda t: t.replace(game, game + "    secrets: [s]\n", 1) + "secrets:\n  s:\n    file: /etc/hostname\n",
    # Another stack's things by their names: its volume, its network, its
    # image (a build tag, or the build's own image name), a pull over a
    # local name.
    "volume_alias": lambda t: t.replace("\n  lava-db:\n", "\n  lava-db:\n    name: cicdvictim_data\n", 1),
    "network_alias": lambda t: t + "networks:\n  default:\n    name: cicdvictim_net\n",
    "build_tags": lambda t: t.replace("    build: .\n", "    build:\n      context: .\n      tags: [\"cicdvictim-img:1\"]\n", 1),
    "image_retag": lambda t: t.replace("    image: cicdtest-lava-server\n", "    image: cicdvictim-img:1\n", 1),
    "pull_always": lambda t: t.replace("    pull_policy: never\n", "    pull_policy: always\n", 1),
    "gpu": lambda t: t.replace(game, game + "    deploy:\n      resources:\n        reservations:\n          devices:\n            - capabilities: [gpu]\n", 1),
    "external_links": lambda t: t.replace(game, game + "    external_links: [\"cicdtest-pg\"]\n", 1),
}
new = edits[edit](text)
assert new != text, edit
open(path, "w", encoding="utf-8").write(new)
PY
  bash "$d/deploy/ci/pack.sh" "$T/bad/policy_$1.tgz" "$d" > /dev/null
  rm -rf "$d"
}
POLICY="privileged cap_add pid_host host_root docker_sock res_writable volume_driver build_context build_extra env_file backslash volumes_from secrets
        volume_alias network_alias build_tags image_retag pull_always gpu external_links"
for p in $POLICY; do policy_tree "$p" "$p"; done
# What the aliases would reach: a volume, a network and an image of a stack
# that is not this one. None of it may change.
docker volume create cicdvictim_data > /dev/null
docker network create cicdvictim_net > /dev/null
docker tag postgres:16-alpine cicdvictim-img:1
VICTIM_IMG=$(docker image inspect -f '{{.Id}}' cicdvictim-img:1)

for b in traversal traversal_deep absolute symlink hardlink fifo topdir dotenv dotenv_deep database res \
         newline_name backslash_name backslash_octal control_name \
         oversize bomb setuid sticky_dir override compose_yaml no_dockerfile garbage \
         sparse_gnu sparse_pax $(for p in $POLICY; do echo "policy_$p"; done); do
  out=$(SSH_ORIGINAL_COMMAND="deploy $(fake_sha "$b") $(sum_of "$T/bad/$b.tgz")" gate < "$T/bad/$b.tgz" 2>&1)
  check "bad tarball '$b' refused" "$?" 2
  echo "        $(echo "$out" | grep refused | head -n 1 | cut -c1-150)"
done
bash "$T/trees/v0/deploy/ci/pack.sh" "$T/v0.tgz" "$T/trees/v0" > /dev/null
SSH_ORIGINAL_COMMAND="deploy $(fake_sha v0) $(echo wrong | sha256sum | cut -c1-64)" gate < "$T/v0.tgz" > /dev/null 2>&1
check "good tarball with a wrong sha256 refused" "$?" 2
head -c 1000 "$T/v0.tgz" | SSH_ORIGINAL_COMMAND="deploy $(fake_sha v0) $(sum_of "$T/v0.tgz")" gate > /dev/null 2>&1
check "truncated tarball refused" "$?" 2
check "after all of that /opt/lava is untouched" "$(tree_sum)" "$SUM0"
check "and no backup was taken" "$(nbackups)" 0
check "and the game still runs v0" "$(game_img)" "$V0_IMG"
check "and no .bak, no dump" "$(ndumps)" 0
[ ! -e /tmp/cicdtest-evil.txt ] && [ ! -e "$T/opt/lava-ci/evil.txt" ] && [ ! -e "$T/opt/evil.txt" ] \
  && ok "nothing written outside the stage" || bad "something escaped"
check "the other stack's image still is what it was" "$(docker image inspect -f '{{.Id}}' cicdvictim-img:1)" "$VICTIM_IMG"
check "and no container mounts its volume" "$(docker ps -aq --filter volume=cicdvictim_data | wc -l)" 0
check "or sits on its network" "$(docker ps -aq --filter network=cicdvictim_net | wc -l)" 0

# --- a good deploy through the CI end (pack.sh + send.sh) --------------------------
echo "== v1: good deploy through send.sh; while it is watched: request lines, a player called Terror,"
echo "   a frame the game cannot read, a frame carrying the marker, launchers hanging up mid-download"
check "the Postgres stand-in is still up" "$(pg_up)" up
mk_tree "$T/trees/v1"
mark "$T/trees/v1" v1
# A file named in Cyrillic: the gate lets UTF-8 names through below the top.
echo "заметка" > "$T/trees/v1/data/заметки-cicd.txt"
# A line a player's name could put in the log: not an error.
sed -i '1i import logging, threading; threading.Timer(4, lambda: logging.getLogger("lava").info("cicd test: Terror connects, ErrorBoy too")).start()' \
  "$T/trees/v1/server/server.py"
bash "$T/trees/v1/deploy/ci/pack.sh" "$T/v1.tgz" "$T/trees/v1" | sed 's/^/    /'
mkdir -p "$T/v1.unpacked" && tar -xzf "$T/v1.tgz" -C "$T/v1.unpacked"
rsync -a --filter="merge $T/trees/v1/deploy/rsync.filter" "$T/trees/v1/" "$T/v1.rsynced/"
check "tarball == deploy.sh's rsync of the tree" "$(diff -rq "$T/v1.unpacked" "$T/v1.rsynced" > /dev/null && echo same || echo differs)" same
SHA1=$(fake_sha v1)
s=$(date +%s)
PATH=$T/bin:$PATH GITHUB_STEP_SUMMARY=$T/summary1.md bash "$T/trees/v1/deploy/ci/send.sh" "$T/v1.tgz" "$SHA1" > "$T/v1.out" 2>&1 &
SP=$!
# While the gate watches the fresh logs, anyone on the internet may ask the
# http service for /Traceback: those request lines are not the server failing.
for _ in $(seq 1 240); do
  grep -q 'watching' "$T/v1.out" 2>/dev/null && break
  sleep 1
done
for p in /Traceback "/x?Error=1" "/%0ATraceback%20(most%20recent%20call%20last):" "/ValueError:%20x" "/%20%20!!%20%20%20%20boom"; do
  curl -s -o /dev/null "http://127.0.0.1:$HTTP_PORT$p"
done
check "the injected request lines reached the http log" \
  "$(docker logs cicdtest-http 2>&1 | grep -c '^  HTTP .*Traceback')" 2
# And what an anonymous client can make the services write about themselves:
# a frame the game cannot decode is a full traceback in its log, a frame may
# carry the marker's characters, and a launcher closing in the middle of the
# string table was a traceback in the http log. None of it is the new
# version failing.
python3 - 19775 "$HTTP_PORT" <<'PY'
import socket, struct, sys, time
game, http = int(sys.argv[1]), int(sys.argv[2])
for frame in (b"x;a=@oops\0", b"hello;a=@  !!    @;\0"):
    s = socket.create_connection(("127.0.0.1", game), 5)
    s.sendall(frame)
    time.sleep(0.5)
    s.close()
for _ in range(3):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    s.connect(("127.0.0.1", http))
    s.sendall(b"GET /exe/lavaclient/texts.xml HTTP/1.1\r\nHost: x\r\n\r\n")
    s.recv(1024)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    s.close()
    time.sleep(0.5)
PY
wait $SP
check "v1 deployed (send.sh exit)" "$?" 0
check "the game wrote a traceback for the bad frame" \
  "$(docker logs cicdtest-game 2>&1 | grep -c '^Traceback (most recent call last)' | sed 's/^[1-9][0-9]*$/some/')" some
check "and logged the frame with the marker in it" \
  "$(docker logs cicdtest-game 2>&1 | grep -c "C->S  hello {'a': '  !!    '}")" 1
check "the http service wrote the hang-ups as access lines" \
  "$(docker logs cicdtest-http 2>&1 | grep -c 'dropped the connection' | sed 's/^[1-9][0-9]*$/some/')" some
check "and no traceback at all" "$(docker logs cicdtest-http 2>&1 | grep -c '^Traceback')" 0
check "the report counts them after start, none in start-up" \
  "$(grep -cE '^errors:   0 in the start-up logs, [1-9][0-9]* after' "$T/v1.out")" 1
check "send.sh warns of them" "$(grep -c '^::warning title=Errors after start::' "$T/v1.out")" 1
check "the gate's words came with workflow commands off" \
  "$(sed -n 's/^::stop-commands::\([0-9a-f]\{32\}\)$/\1/p' "$T/v1.out" | head -n 1 | xargs -I{} grep -c '^::{}::$' "$T/v1.out")" 1
check "the Cyrillic file is in /opt/lava" "$(cat "$T/opt/lava/data/заметки-cicd.txt")" "заметка"
echo "    took $(( $(date +%s) - s ))s; report:"
sed -n '/^=== report/,/^=== end/p' "$T/v1.out" | sed 's/^/    /'
check "v1 server.py in /opt/lava" "$(tail -n 1 "$T/opt/lava/server/server.py")" "# cicd test: v1"
check "v1 server.py inside the running image" "$(docker exec cicdtest-game tail -n 1 /app/server/server.py)" "# cicd test: v1"
check "the Terror line is in the game's log" "$(docker logs cicdtest-game 2>&1 | grep -c 'Terror connects')" 1
check ".env kept" "$(grep -c COMPOSE_PROJECT_NAME=cicdtest "$T/opt/lava/.env")" 1
check "res/ kept" "$(find "$T/opt/lava/res" -type f | wc -l)" "$(find "$SLICE" -type f | wc -l)"
check "the game runs a new image" "$( [ "$(game_img)" != "$V0_IMG" ] && echo new || echo same)" new
check "it answers" "$(probes)" up
check "one backup dir" "$(nbackups)" 1
check "one dump" "$(ndumps)" 1
check "one pre- tag" "$(ntags)" 1
check "the pre- tag is the v0 image" "$(docker inspect -f '{{.Id}}' "cicdtest-lava-server:pre-$(ls "$T/opt" | sed -n 's/^lava\.bak-//p' | head -n 1)")" "$V0_IMG"
check "dump restores (has the marker row)" "$(docker exec -i cicdtest-pg pg_restore -f - < "$(ls "$T"/opt/lava-pg-backup-*-ci.dump | head -n 1)" | grep -c '^before$')" 1
check "deployed state records v1" "$(cut -d' ' -f1 "$T/opt/lava-ci/state/deployed")" "$SHA1"
check "summary written" "$(grep -c '^### Deploy' "$T/summary1.md")" 1
grep -q '^launcher: ' "$T/v1.out" && ok "launcher line: $(grep '^launcher: ' "$T/v1.out" | cut -c1-110)" || bad "no launcher line"
grep -q '^texts: ' "$T/v1.out" && ok "texts line: $(grep '^texts: ' "$T/v1.out")" || bad "no texts line"
V1_IMG=$(game_img)
SUM1=$(tree_sum)

# --- deploys that break the game -> rollback ----------------------------------------
echo "== v2: the server crashes at start -> rollback"
mk_tree "$T/trees/v2"
mark "$T/trees/v2" v1
sed -i '1i raise RuntimeError("cicd test: broken on purpose")' "$T/trees/v2/server/server.py"
bash "$T/trees/v2/deploy/ci/pack.sh" "$T/v2.tgz" "$T/trees/v2" > /dev/null
PATH=$T/bin:$PATH GITHUB_STEP_SUMMARY=$T/summary2.md bash "$T/trees/v2/deploy/ci/send.sh" "$T/v2.tgz" "$(fake_sha v2)" > "$T/v2.out" 2>&1
check "v2 fails with status 1 (rolled back)" "$?" 1
grep -E '^(result|state|rollback):' "$T/v2.out" | sed 's/^/    /'
grep -q '::error title=Deploy::FAILED -- the server was rolled back' "$T/v2.out" && ok "send.sh says so as a workflow error" || bad "no ::error"
check "tree back to v1" "$(tree_sum)" "$SUM1"
check "game back on the v1 image" "$(game_img)" "$V1_IMG"
check "and answering" "$(probes)" up
check "deployed state still v1" "$(cut -d' ' -f1 "$T/opt/lava-ci/state/deployed")" "$SHA1"

echo "== v3: the image does not build -> rollback"
mk_tree "$T/trees/v3"
mark "$T/trees/v3" v1
echo 'RUN false' >> "$T/trees/v3/Dockerfile"
bash "$T/trees/v3/deploy/ci/pack.sh" "$T/v3.tgz" "$T/trees/v3" > /dev/null
SSH_ORIGINAL_COMMAND="deploy $(fake_sha v3) $(sum_of "$T/v3.tgz")" gate < "$T/v3.tgz" > "$T/v3.out" 2>&1
check "v3 fails with status 1" "$?" 1
grep -E '^(result|state|rollback):' "$T/v3.out" | sed 's/^/    /'
check "tree back to v1" "$(tree_sum)" "$SUM1"
check "game still on the v1 image" "$(game_img)" "$V1_IMG"
check "and answering" "$(probes)" up

echo "== v4: a failure the server caught and logged while starting, no crash -> rollback"
mk_tree "$T/trees/v4"
mark "$T/trees/v4" v1
sed -i 's/^    game = await asyncio.start_server(handle_client, HOST, PORT)$/    log.error("  !!    cicd test: failed on purpose")\n&/' \
  "$T/trees/v4/server/server.py"
check "v4 logs the marker before it listens" \
  "$(grep -B1 '^    game = await asyncio.start_server' "$T/trees/v4/server/server.py" | grep -c 'cicd test: failed on purpose')" 1
bash "$T/trees/v4/deploy/ci/pack.sh" "$T/v4.tgz" "$T/trees/v4" > /dev/null
SSH_ORIGINAL_COMMAND="deploy $(fake_sha v4) $(sum_of "$T/v4.tgz")" gate < "$T/v4.tgz" > "$T/v4.out" 2>&1
check "v4 fails with status 1" "$?" 1
grep -E '^(errors|result|state|rollback):|^  \| ' "$T/v4.out" | sed 's/^/    /'
check "tree back to v1" "$(tree_sum)" "$SUM1"
check "game back on the v1 image" "$(game_img)" "$V1_IMG"

echo "== lock: a second deploy while one holds the lock"
flock "$T/opt/lava-ci/deploy.lock" -c 'sleep 12' &
LP=$!
sleep 1
SSH_ORIGINAL_COMMAND="deploy $SHA1 $(sum_of "$T/v1.tgz")" gate < "$T/v1.tgz" > "$T/lock.out" 2>&1
check "refused while locked" "$?" 2
grep refused "$T/lock.out" | sed 's/^/    /'
wait $LP

echo "== v5: good deploy, the client goes away mid-way; pruning to KEEP=2"
mk_tree "$T/trees/v5"
mark "$T/trees/v5" v5
bash "$T/trees/v5/deploy/ci/pack.sh" "$T/v5.tgz" "$T/trees/v5" > /dev/null
SHA5=$(fake_sha v5)
before=$(nbackups)
SSH_ORIGINAL_COMMAND="deploy $SHA5 $(sum_of "$T/v5.tgz")" gate < "$T/v5.tgz" 2>&1 | head -n 1
for _ in $(seq 1 150); do
  [ "$(cut -d' ' -f1 "$T/opt/lava-ci/state/deployed")" = "$SHA5" ] && break
  pgrep -f "$GATE" > /dev/null || break
  sleep 2
done
check "the deploy finished without its client" "$(cut -d' ' -f1 "$T/opt/lava-ci/state/deployed")" "$SHA5"
check "v5 running" "$(docker exec cicdtest-game tail -n 1 /app/server/server.py)" "# cicd test: v5"
echo "    backups before v5: $before; after: $(nbackups) dirs, $(ndumps) dumps, $(ntags) tags"
check "pruned to KEEP=2 dirs" "$(nbackups)" 2
check "pruned to KEEP=2 dumps" "$(ndumps)" 2
check "pruned to KEEP=2 tags" "$(ntags)" 2

# --- the client release (CLIENT_ORIG: a folder with the original main.swf and
# database/locations.xml; without it this part is skipped) -----------------------
if [ -n "${CLIENT_ORIG:-}" ]; then
  echo "== client release"
  CROOT=$T/opt/lava-site/download/client
  CPY=$T/opt/lava-ci/client/publish.py
  check "install.sh put the publisher in" "$( [ -f "$CPY" ] && echo yes || echo no)" yes
  check "and made the resource key" "$( [ -f "$T/opt/lava-ci/client/resource.pem" ] && echo yes || echo no)" yes
  grep -E 'resource key|resource.keys|CLIENT_RELEASE' "$T/install1.out" | sed 's/^/    /'
  python3 "$T/opt/lava-ci/client/lavasig.py" pubkey "$T/opt/lava-ci/client/resource.pem" > "$T/resource.keys"
  # A small original: the two files the generators start from and one more.
  rm -rf "$T/orig"; mkdir -p "$T/orig/database" "$T/orig/locations/libs"
  cp "$CLIENT_ORIG/main.swf" "$T/orig/main.swf"
  cp "$CLIENT_ORIG/database/locations.xml" "$T/orig/database/locations.xml"
  echo "a file of the original" > "$T/orig/locations/libs/Abu Hamad.swf"
  client_tree() {  # name -> $T/trees/<name> with the small original as its base
    mk_tree "$T/trees/$1"
    mark "$T/trees/$1" v5
    python3 "$REPO/client/build.py" base --dir "$T/orig" -o "$T/trees/$1/client/base.txt" > /dev/null
  }
  client_deploy() {  # name -> the gate's status; output in $T/<name>.out
    bash "$T/trees/$1/deploy/ci/pack.sh" "$T/$1.tgz" "$T/trees/$1" > /dev/null
    SSH_ORIGINAL_COMMAND="deploy $(fake_sha "$1") $(sum_of "$T/$1.tgz")" gate < "$T/$1.tgz" > "$T/$1.out" 2>&1
  }
  pointer() { cat "$CROOT/current.txt" 2>/dev/null | sha256sum | cut -c1-16; }

  client_tree c0
  python3 "$CPY" import-base --root "$CROOT" --base "$T/trees/c0/client/base.txt" --dir "$T/orig" > "$T/import.out" 2>&1
  check "import-base: the original is in the store" "$?" 0
  printf 'CLIENT_RELEASE=1\nCLIENT_ROOT=%s\n' "$CROOT" >> "$T/opt/lava-ci/gate.conf"

  client_deploy c0
  check "c0: a deploy with the client release" "$?" 0
  grep -E '^client:' "$T/c0.out" | sed 's/^/    /'
  check "c0: the pointer is signed by the server's resource key" \
    "$(python3 "$REPO/client/lavasig.py" verify "$T/resource.keys" "$CROOT/current.txt" 2>&1)" "verify: ok"
  M=$(sed -n 's/^manifest [0-9a-f]* [0-9]* //p' "$CROOT/current.txt")
  check "c0: the manifest it names is there" "$( [ -f "$CROOT/$M" ] && echo yes || echo no)" yes
  check "c0: main.swf in it is the patched one, not the original" \
    "$(awk -F '\t' '$3 == "main.swf" { print $1 }' "$CROOT/$M" | grep -vc "$(sha256sum < "$T/orig/main.swf" | cut -c1-64)")" 1
  check "c0: its string table is the one the server serves" \
    "$(awk -F '\t' '$3 == "database/texts.xml" { print $1 }' "$CROOT/$M")" \
    "$(docker exec cicdtest-http python3 -c 'import json,os,urllib.request; print(json.load(urllib.request.urlopen("http://127.0.0.1:%s/exe/lavaclient/manifest" % os.environ.get("LAVA_HTTP_PORT","8080")))["resources"][0]["sha256"])')"
  check "c0: every file it lists is in the store" \
    "$(awk -F '\t' 'NF == 3 { print $1 }' "$CROOT/$M" | while read -r s; do [ -f "$CROOT/store/${s:0:2}/$s" ] || echo missing; done | wc -l)" 0
  P0=$(pointer)
  SUMC0=$(tree_sum)
  IMGC0=$(game_img)

  client_tree c1
  # At the top: the patcher's own last line is sys.exit(main()), so anything
  # appended after it never runs.
  sed -i '1a raise SystemExit("cicd test: the release does not build")' "$T/trees/c1/tools/widescreen.py"
  client_deploy c1
  check "c1: a release that does not build -> deploy fails" "$?" 1
  grep -E '^(result|state):' "$T/c1.out" | sed 's/^/    /'
  check "c1: nothing on the server changed" "$(tree_sum)" "$SUMC0"
  check "c1: no backup was taken for it" "$(grep -c 'saved:' "$T/c1.out")" 0
  check "c1: the pointer is the one before" "$(pointer)" "$P0"

  client_tree c2
  # The builder is the repository's own code: it may write whatever it likes
  # into its output. A string table that is not the server's is caught.
  sed -i 's/^    def gen_texts(self):$/    def gen_texts(self):\n        return b"not the table the server serves"\n\n    def gen_texts_unused(self):/' \
    "$T/trees/c2/client/build.py"
  client_deploy c2
  check "c2: a string table the server does not serve -> rolled back" "$?" 1
  grep -E '^(result|state|rollback):' "$T/c2.out" | sed 's/^/    /'
  check "c2: the tree is back" "$(tree_sum)" "$SUMC0"
  check "c2: the game is back on its image" "$(game_img)" "$IMGC0"
  check "c2: the pointer is the one before" "$(pointer)" "$P0"

  client_tree c3
  # And it may not write anything else: the store and the tree are read-only
  # to it, and there is no network.
  sed -i 's/^    def run(self):$/    def run(self):\n        open("\/store\/evil", "w").write("x")/' "$T/trees/c3/client/build.py"
  client_deploy c3
  check "c3: a builder writing into the store -> deploy fails" "$?" 1
  check "c3: and the store holds nothing it wrote" "$(find "$CROOT/store" -name evil | wc -l)" 0
  check "c3: the pointer is the one before" "$(pointer)" "$P0"

  # --- the launcher, built by the gate (CLIENT_PROJECTOR: the Flash projector;
  # the mono image of LAUNCHER_IMAGE must be in docker already) -------------------
  if [ -n "${CLIENT_PROJECTOR:-}" ]; then
    echo "== launcher built and published by the gate"
    cp "$CLIENT_PROJECTOR" "$T/opt/lava-ci/client/fp32_sa.exe"
    python3 "$T/opt/lava-ci/client/lavasig.py" pubkey "$T/opt/lava-ci/client/launcher.pem" > "$T/launcher.keys"
    check "install.sh made the launcher key and listed it" \
      "$(grep -c "^$(cut -d' ' -f1 "$T/launcher.keys") " "$T/opt/lava-ci/client/launcher.keys")" 1
    printf 'CLIENT_LAUNCHER=1\nLAUNCHER_DOWNLOAD=%s\n' "$T/opt/lava-site/download" >> "$T/opt/lava-ci/gate.conf"
    keyed_tree() {  # name -> a client tree whose client/keys are this test server's
      client_tree "$1"
      cp "$T/resource.keys" "$T/trees/$1/client/keys/resource.keys"
      cp "$T/launcher.keys" "$T/trees/$1/client/keys/launcher.keys"
    }
    lversion() { sed -n 's/^launcher \([0-9]*\) .*/\1/p' "$CROOT/current.txt"; }

    keyed_tree l1
    client_deploy l1
    check "l1: the first launcher is built and published" "$?" 0
    grep -E '^(launcher|client):' "$T/l1.out" | sed 's/^/    /'
    check "l1: the pointer names launcher 1" "$(lversion)" 1
    check "l1: its statement is signed by this server's launcher key" \
      "$(python3 "$REPO/client/lavasig.py" verify "$T/launcher.keys" "$CROOT/launcher/1.txt" 2>&1)" "verify: ok"
    check "l1: the site's link is the same exe" \
      "$(cmp -s "$CROOT/launcher/1.exe" "$T/opt/lava-site/download/LavaReborn.exe" && echo same || echo differs)" same
    check "l1: it is an exe" "$(head -c 2 "$CROOT/launcher/1.exe")" MZ

    client_deploy l1
    check "l1 again: the same sources build no new launcher" "$(lversion)" 1
    check "l1 again: and the report says so" "$(grep -c '^launcher: unchanged, version 1' "$T/l1.out")" 1

    keyed_tree l2
    echo "// cicd test: a change to the launcher" >> "$T/trees/l2/launcher/Notice.cs"
    client_deploy l2
    check "l2: a changed launcher deploys" "$?" 0
    check "l2: as version 2" "$(lversion)" 2
    P2=$(pointer)
    SUML2=$(tree_sum)

    keyed_tree l3
    echo "this is not C#" >> "$T/trees/l3/launcher/Notice.cs"
    client_deploy l3
    check "l3: a launcher that does not compile -> deploy fails" "$?" 1
    grep -E '^(result|state):' "$T/l3.out" | sed 's/^/    /'
    check "l3: nothing on the server changed" "$(tree_sum)" "$SUML2"
    check "l3: the pointer is the one before" "$(pointer)" "$P2"

    client_tree l4
    echo "// cicd test: l4" >> "$T/trees/l4/launcher/Notice.cs"
    client_deploy l4
    check "l4: a tree whose keys are not this server's -> deploy fails" "$?" 1
    check "l4: and says which key" "$(grep -c "^result: .*does not list this server's launcher key" "$T/l4.out")" 1
    check "l4: the pointer is the one before" "$(pointer)" "$P2"

    keyed_tree l5
    cp "$T/launcher.keys" "$T/trees/l5/client/keys/resource.keys"
    client_deploy l5
    check "l5: resource keys that are not this server's -> deploy fails" "$?" 1
    check "l5: and says which key" "$(grep -c "^result: .*does not list this server's resource key" "$T/l5.out")" 1
    check "l5: the pointer is the one before" "$(pointer)" "$P2"

    # The launcher cannot be published (its served folder is a link): the
    # server and the release stay out, the report says so, and the next
    # deploy of the same sources publishes it after all.
    keyed_tree l6
    echo "// cicd test: l6" >> "$T/trees/l6/launcher/Notice.cs"
    mv "$CROOT/launcher" "$CROOT/launcher.real"
    ln -s launcher.real "$CROOT/launcher"
    client_deploy l6
    check "l6: launcher not publishable -> the deploy still goes out" "$?" 0
    check "l6: and the report says so" "$(grep -c '^launcher: NOT PUBLISHED' "$T/l6.out")" 1
    check "l6: players keep launcher 2" "$(lversion)" 2
    rm "$CROOT/launcher"
    mv "$CROOT/launcher.real" "$CROOT/launcher"
    client_deploy l6
    check "l6 again: the same sources now publish it" "$?" 0
    check "l6 again: as version 3" "$(lversion)" 3
    P2=$(pointer)

    sed -i -e '/^CLIENT_LAUNCHER=1$/d' -e '/^LAUNCHER_DOWNLOAD=/d' "$T/opt/lava-ci/gate.conf"
    P0=$P2
  fi

  sed -i '/^CLIENT_RELEASE=1$/d' "$T/opt/lava-ci/gate.conf"
  client_deploy c0
  check "client release off again: deploys as before" "$?" 0
  check "and says so" "$(grep -c '^client:   no release' "$T/c0.out")" 1
  check "and the pointer stays" "$(pointer)" "$P0"
fi

echo "== COMPOSE_POLICY=0 lets a policed file through (the owner's switch)"
echo "COMPOSE_POLICY=0" >> "$T/opt/lava-ci/gate.conf"
out=$(SSH_ORIGINAL_COMMAND="deploy $(fake_sha p0) $(sum_of "$T/bad/policy_cap_add.tgz")" gate < "$T/bad/policy_cap_add.tgz" 2>&1)
rc=$?
check "with the policy off, a cap_add compose file deploys" "$rc" 0
echo "$out" | grep -E '^(policy|result):' | sed 's/^/    /'
sed -i '/^COMPOSE_POLICY=0$/d' "$T/opt/lava-ci/gate.conf"

echo "== gate.log (last lines)"
tail -n 6 "$T/opt/lava-ci/log/gate.log" | cut -c1-200 | sed 's/^/    /'
echo "== gate.conf writable by others is refused"
chmod 666 "$T/opt/lava-ci/gate.conf"
SSH_ORIGINAL_COMMAND="assets-hash" gate > /dev/null 2>&1
check "group/world-writable gate.conf -> refused" "$?" 2
chmod 600 "$T/opt/lava-ci/gate.conf"

echo
echo "== $PASS passed, $FAILS failed"
if [ "${KEEP_DOCKER:-0}" != 1 ]; then
  (cd "$T/opt/lava" && docker compose down -v > /dev/null 2>&1)
  cleanup_docker
  echo "== throwaway containers, volume and images removed"
fi
[ "$FAILS" = 0 ]
