#!/usr/bin/env bash
# Does the runner's rootless Docker on the production host do what ci.yml
# takes for granted? Once after the runner is set up, and again after any
# change to its Docker or its firewall, with no job running (README «Между
# задачами», «Проверка на сервере»):
#
#   bash deploy/runner/check.sh      as root (it runs itself as ghrunner),
#                                    or as ghrunner
#
# First the host's private addresses (HOST_BLOCKED) from ghrunner on the
# host, and the same kind (BLOCKED) from a container on the rootless default
# bridge: none may connect. An address inside one of the rootless Docker's
# own networks is that network's address for a container (its default
# bridge is 172.17/16 like the system one's, and a job network takes
# 172.18/16 when it is free) -- such a target is named and left to the probe
# from the host.
#
# Then what the runner builds for the Postgres job -- a network of its own,
# postgres:16-alpine on it by the name "postgres" with its data on a tmpfs, a
# python:3.12-slim job container with --init and ~/.ssh on a tmpfs -- and
# from inside the job container:
#   * PID 1 is docker-init (--init works: the daemon finds docker-init);
#   * "postgres" resolves, and a Postgres answers on postgres:5432 (job and
#     service talk inside the rootless network namespace, where the host's
#     REJECT of 172.16/12 for ghrunner does not reach);
#   * the internet answers (GitHub, PyPI, Debian), and so does the gate's
#     sshd on the host's public address;
#   * nothing written to ~/.ssh reaches the folder mounted as HOME.
# Last, whether every runner has the job hooks and its unit the drop-in. Prints
# one line per check and exits 1 if any failed. Leaves nothing behind.
#
#   GATE=host:port            the gate's sshd, must answer (159.194.247.90:22)
#   HOST_BLOCKED="h:p ..."    must not connect from the host
#                             (127.0.0.1:22 172.18.0.1:5432 172.17.0.1:22)
#   BLOCKED="h:p ..."         must not connect from a container
#                             (172.18.0.1:5432 172.17.0.1:22 10.0.2.2:22)
# 172.18.0.1:5432 is production's Postgres on the system Docker's bridge,
# 172.17.0.1 the system docker0, 10.0.2.2 slirp's door to the host's
# loopback (closed by --disable-host-loopback).
set -uo pipefail

U=${LAVA_RUNNER_USER:-ghrunner}
if [ "$(id -u)" = 0 ]; then
  uid=$(id -u "$U") || { echo "no user $U"; exit 1; }
  h=$(getent passwd "$U" | cut -d: -f6)
  # A copy ghrunner can read: the folder this one lies in may be root's.
  t=$(mktemp /tmp/lava-check.XXXXXX.sh)
  cp "$0" "$t" && chmod 644 "$t"
  runuser -u "$U" -- env -i PATH=/usr/local/bin:/usr/bin:/bin HOME="$h" LANG=C.UTF-8 \
    XDG_RUNTIME_DIR="/run/user/$uid" DOCKER_HOST="unix:///run/user/$uid/docker.sock" \
    GATE="${GATE:-}" HOST_BLOCKED="${HOST_BLOCKED:-}" BLOCKED="${BLOCKED:-}" \
    LAVA_RUNNER_DIR="${LAVA_RUNNER_DIR:-}" \
    bash "$t"
  rc=$?
  rm -f "$t"
  exit "$rc"
fi

export DOCKER_HOST=${DOCKER_HOST:-unix://${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock}
GATE=${GATE:-159.194.247.90:22}
HOST_BLOCKED=${HOST_BLOCKED:-127.0.0.1:22 172.18.0.1:5432 172.17.0.1:22}
BLOCKED=${BLOCKED:-172.18.0.1:5432 172.17.0.1:22 10.0.2.2:22}
R=${LAVA_RUNNER_DIR:-$HOME/actions-runner}
fails=0
ok() { echo "ok      $*"; }
bad() { echo "FAIL    $*"; fails=$((fails + 1)); }
# What a python3 probe printed, its FAIL lines counted into fails.
tally() {
  local rc=$1 out=$2 n
  echo "$out"
  n=$(grep -c '^FAIL' <<< "$out")
  [ "$rc" = 0 ] || [ "$n" -gt 0 ] || n=1
  fails=$((fails + n))
}

echo "== the runner's Docker ($DOCKER_HOST)"
if ! info=$(docker info --format '{{.ServerVersion}} {{.Driver}} cgroup {{.CgroupDriver}}/{{.CgroupVersion}} {{.SecurityOptions}}' 2>&1); then
  bad "docker does not answer: $info"
  exit 1
fi
case $info in
  *rootless*) ok "rootless: $info" ;;
  *) bad "not a rootless daemon: $info" ;;
esac
for img in python:3.12-slim postgres:16-alpine; do
  if docker pull -q "$img" > /dev/null 2>&1; then ok "pull $img"; else bad "pull $img"; fi
done

echo "== the host's private addresses"
for hp in $HOST_BLOCKED; do
  if timeout 5 bash -c "exec 3<>/dev/tcp/${hp%:*}/${hp##*:}" 2> /dev/null; then
    bad "$hp connects from the host as $(id -un); it should not"
  else
    ok "$hp does not connect from the host as $(id -un)"
  fi
done
if timeout 8 bash -c "exec 3<>/dev/tcp/${GATE%:*}/${GATE##*:}" 2> /dev/null; then
  ok "gate $GATE connects from the host"
else
  bad "gate $GATE does not connect from the host"
fi
mapfile -t nets < <(docker network ls -q)
shadow=$(docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}} {{end}}' "${nets[@]}" 2> /dev/null | tr '\n' ' ')
out=$(docker run --rm -i -e BLOCKED="$BLOCKED" -e SHADOW="$shadow" python:3.12-slim python3 - 2>&1 << 'EOF'
import ipaddress, os, socket, sys

fails = 0
nets = [ipaddress.ip_network(n, strict=False) for n in os.environ["SHADOW"].split()]
for hp in os.environ["BLOCKED"].split():
    host, port = hp.rsplit(":", 1)
    inside = [str(n) for n in nets if ipaddress.ip_address(host) in n]
    if inside:
        print("skip    %s: inside the rootless network %s, for a container that network's own address"
              % (hp, inside[0]))
        continue
    try:
        socket.create_connection((host, int(port)), timeout=5).close()
        fails += 1
        print("FAIL    %s connects from a container; it should not" % hp)
    except Exception as e:
        print("ok      %s does not connect from a container (%s)" % (hp, type(e).__name__))
sys.exit(1 if fails else 0)
EOF
)
tally $? "$out"

N=lava-check-$$
HOMEDIR=$(mktemp -d)
cleanup() {
  docker rm -f -v "$N-job" "$N-pg" > /dev/null 2>&1
  docker network rm "$N" > /dev/null 2>&1
  rm -rf "$HOMEDIR"
}
trap cleanup EXIT

echo "== a job with a Postgres service, as the runner makes them"
docker network create --label lava-check "$N" > /dev/null || bad "network create"
docker run -d --name "$N-pg" --label lava-check --network "$N" --network-alias postgres \
  -e POSTGRES_USER=lava -e POSTGRES_PASSWORD=lavatest -e POSTGRES_DB=lava_test \
  --tmpfs /var/lib/postgresql/data \
  --health-cmd "pg_isready -U lava -d lava_test" --health-interval 2s --health-timeout 5s --health-retries 30 \
  postgres:16-alpine > /dev/null || bad "service container"
if docker run -d --name "$N-job" --label lava-check --network "$N" \
     -e HOME=/github/home -v "$HOMEDIR":/github/home \
     --init --tmpfs /github/home/.ssh:mode=0700,size=1m \
     --entrypoint tail python:3.12-slim -f /dev/null > /dev/null; then
  ok "job container with --init and a tmpfs on ~/.ssh"
else
  bad "job container with --init and a tmpfs on ~/.ssh (docker-init missing?)"
  exit 1
fi
st=
for _ in $(seq 60); do
  st=$(docker inspect -f '{{.State.Health.Status}}' "$N-pg" 2> /dev/null)
  [ "$st" = healthy ] && break
  sleep 2
done
if [ "$st" = healthy ]; then ok "service healthy"; else bad "service: $st"; fi
echo "        job network $(docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}' "$N")"

out=$(docker exec -i -e GATE="$GATE" "$N-job" python3 - 2>&1 << 'EOF'
import os, socket, struct, sys

fails = 0
def ok(m): print("ok      " + m)
def bad(m):
    global fails
    fails += 1
    print("FAIL    " + m)

pid1 = open("/proc/1/cmdline", "rb").read().split(b"\0")[0].decode()
(ok if "docker-init" in pid1 or "tini" in pid1 else bad)("PID 1 is %s" % pid1)

def connect(host, port, timeout=8):
    s = socket.create_connection((host, port), timeout=timeout)
    s.settimeout(timeout)
    return s

try:
    ip = socket.getaddrinfo("postgres", 5432, proto=socket.IPPROTO_TCP)[0][4][0]
    s = connect("postgres", 5432)
    s.sendall(struct.pack("!II", 8, 80877103))   # SSLRequest: a Postgres answers S or N
    a = s.recv(1)
    s.close()
    (ok if a in (b"S", b"N") else bad)("postgres:5432 by name -> %s, a Postgres answers (%r)" % (ip, a))
except Exception as e:
    bad("postgres:5432 by name: %s: %s" % (type(e).__name__, e))

for host, port in (("github.com", 443), ("pypi.org", 443), ("deb.debian.org", 80)):
    try:
        connect(host, port).close()
        ok("internet: %s:%d" % (host, port))
    except Exception as e:
        bad("internet: %s:%d: %s" % (host, port, e))

host, port = os.environ["GATE"].rsplit(":", 1)
try:
    s = connect(host, int(port))
    banner = s.recv(64)
    s.close()
    (ok if banner.startswith(b"SSH-") else bad)("gate %s:%s answers %r" % (host, port, banner.split(b"\r")[0]))
except Exception as e:
    bad("gate %s:%s: %s" % (host, port, e))

os.makedirs("/github/home/.ssh", exist_ok=True)
open("/github/home/.ssh/probe", "w").write("not a key")
sys.exit(1 if fails else 0)
EOF
)
tally $? "$out"

if [ -z "$(ls -A "$HOMEDIR/.ssh" 2> /dev/null)" ]; then
  ok "nothing of ~/.ssh reached the folder mounted as HOME"
else
  bad "the job's .ssh reached the disk: $(ls -A "$HOMEDIR/.ssh")"
fi

echo "== the runners' own setup"
hook=/usr/local/lib/lava-runner/scrub.sh
if [ -x "$hook" ] && [ "$(stat -c %u "$hook")" = 0 ]; then ok "$hook, root's"; else bad "$hook missing or not root's"; fi
if [ -n "${LAVA_RUNNER_DIR:-}" ]; then
  RS=("$R")
else
  RS=()
  for d in "$HOME/actions-runner" "$HOME"/actions-runner-[0-9]*; do
    [ -f "$d/.runner" ] && RS+=("$d")
  done
fi
[ "${#RS[@]}" -gt 0 ] || bad "no registered runner under $HOME"
for r in "${RS[@]}"; do
  for k in ACTIONS_RUNNER_HOOK_JOB_STARTED ACTIONS_RUNNER_HOOK_JOB_COMPLETED; do
    if grep -qx "$k=$hook" "$r/.env" 2> /dev/null; then ok "$k in $r/.env"; else bad "$k=$hook not in $r/.env"; fi
  done
  d=$HOME/.config/systemd/user/lava-runner${r##*/actions-runner}.service.d/scrub.conf
  if grep -q 'scrub.sh --idle' "$d" 2> /dev/null; then ok "drop-in $d"; else bad "drop-in $d missing"; fi
done

echo "== $fails failed"
[ "$fails" = 0 ]
