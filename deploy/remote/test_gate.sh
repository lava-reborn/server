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
# Everything docker here is named cicdtest-* (containers, compose project,
# volume, image) and removed at the end (KEEP_DOCKER=1 keeps it). The gate is
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
  docker volume rm cicdtest_lava-db > /dev/null 2>&1
  docker network rm cicdtest_default > /dev/null 2>&1
  for t in $(docker images cicdtest-lava-server --format '{{.Repository}}:{{.Tag}}'); do
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
}
new = edits[edit](text)
assert new != text, edit
open(path, "w", encoding="utf-8").write(new)
PY
  bash "$d/deploy/ci/pack.sh" "$T/bad/policy_$1.tgz" "$d" > /dev/null
  rm -rf "$d"
}
POLICY="privileged cap_add pid_host host_root docker_sock res_writable volume_driver build_context build_extra env_file backslash volumes_from secrets"
for p in $POLICY; do policy_tree "$p" "$p"; done

for b in traversal traversal_deep absolute symlink hardlink fifo topdir dotenv dotenv_deep database res \
         newline_name oversize bomb setuid sticky_dir override compose_yaml no_dockerfile garbage \
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

# --- a good deploy through the CI end (pack.sh + send.sh) --------------------------
echo "== v1: good deploy through send.sh; request lines and a player called Terror while it is watched"
check "the Postgres stand-in is still up" "$(pg_up)" up
mk_tree "$T/trees/v1"
mark "$T/trees/v1" v1
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
wait $SP
check "v1 deployed (send.sh exit)" "$?" 0
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
check "errors: 0 in the report" "$(grep -c '^errors:   0 ' "$T/v1.out")" 1
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

echo "== v4: a failure the server caught and logged, no crash -> rollback"
mk_tree "$T/trees/v4"
mark "$T/trees/v4" v1
sed -i '1i import logging, threading; threading.Timer(4, lambda: logging.getLogger("lava").error("  !!    cicd test: failed on purpose")).start()' \
  "$T/trees/v4/server/server.py"
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
