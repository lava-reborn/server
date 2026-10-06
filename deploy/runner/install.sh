#!/usr/bin/env bash
# The sweep between jobs, onto the runners on the production host (README
# «Раннер», «Между задачами»). As root, from a copy of the repository's
# deploy/ folder; a second run updates what the first installed:
#
#   tar -cz deploy | ssh root@159.194.247.90 'rm -rf /root/lava-ci-src && mkdir /root/lava-ci-src && tar -xz -C /root/lava-ci-src'
#   ssh root@159.194.247.90 bash /root/lava-ci-src/deploy/runner/install.sh
#   ssh root@159.194.247.90 bash /root/lava-ci-src/deploy/runner/check.sh
#
#   * scrub.sh -> /usr/local/lib/lava-runner/scrub.sh, root's, 0755: a job
#     runs as ghrunner and cannot rewrite it;
#   * register.sh -> /opt/lava-runner/register.sh, root's, 0700: how the
#     owner registers runners with a token (README «Раннер»);
#   * for every registered runner (~ghrunner/actions-runner, unit
#     lava-runner.service; ~ghrunner/actions-runner-N, lava-runner-N.service):
#     ACTIONS_RUNNER_HOOK_JOB_STARTED and ..._COMPLETED, both that script,
#     into its .env (the lines are replaced, never doubled), and scrub.conf
#     into its unit's drop-in folder;
#   * daemon-reload, and a restart of each runner -- a runner reads .env
#     only when it starts -- unless it is running a job: then it says so,
#     and that restart is yours once the job is over.
#
# LAVA_RUNNER_DIR=<one runner's folder> does that one only.
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
U=${LAVA_RUNNER_USER:-ghrunner}
uid=$(id -u "$U")
H=$(getent passwd "$U" | cut -d: -f6)
LIB=/usr/local/lib/lava-runner
HERE=$(cd "$(dirname "$0")" && pwd)
AS=(runuser -u "$U" -- env "XDG_RUNTIME_DIR=/run/user/$uid" "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus")

# actions-runner -> lava-runner.service, actions-runner-3 -> lava-runner-3.service
unit_of() { echo "lava-runner${1##*/actions-runner}.service"; }

if [ -n "${LAVA_RUNNER_DIR:-}" ]; then
  DIRS=("$LAVA_RUNNER_DIR")
else
  DIRS=()
  for d in "$H/actions-runner" "$H"/actions-runner-[0-9]*; do
    [ -f "$d/.runner" ] && DIRS+=("$d")
  done
fi
[ "${#DIRS[@]}" -gt 0 ] || { echo "no configured runner under $H (no .runner)" >&2; exit 1; }
bash -n "$HERE/scrub.sh"
bash -n "$HERE/register.sh"

install -d -m 755 -o root -g root "$LIB"
install -m 755 -o root -g root "$HERE/scrub.sh" "$LIB/scrub.sh"
echo "== $LIB/scrub.sh"
install -d -m 700 -o root -g root /opt/lava-runner
install -m 700 -o root -g root "$HERE/register.sh" /opt/lava-runner/register.sh
echo "== /opt/lava-runner/register.sh"

for R in "${DIRS[@]}"; do
  [ -f "$R/.runner" ] || { echo "$R is not a configured runner (no .runner)" >&2; exit 1; }
  UNIT=$(unit_of "$R")
  touch "$R/.env"
  for k in ACTIONS_RUNNER_HOOK_JOB_STARTED ACTIONS_RUNNER_HOOK_JOB_COMPLETED; do
    sed -i "/^$k=/d" "$R/.env"
    echo "$k=$LIB/scrub.sh" >> "$R/.env"
  done
  chown "$U:$U" "$R/.env"
  echo "== $R/.env:"
  sed 's/^/   /' "$R/.env"

  [ -f "$H/.config/systemd/user/$UNIT" ] || { echo "no user unit $UNIT for $U" >&2; exit 1; }
  D=$H/.config/systemd/user/$UNIT.d
  install -d -m 755 -o "$U" -g "$U" "$D"
  install -m 644 -o "$U" -g "$U" "$HERE/scrub.conf" "$D/scrub.conf"
  echo "== $D/scrub.conf"
done
"${AS[@]}" systemctl --user daemon-reload
echo "== daemon-reload"

for R in "${DIRS[@]}"; do
  UNIT=$(unit_of "$R")
  if pgrep -u "$U" -f "^$R/bin/Runner\.Worker" > /dev/null; then
    echo "== $UNIT is running a job: the hooks start with its next start."
    echo "   When the job is over:  ${AS[*]} systemctl --user restart $UNIT"
  else
    "${AS[@]}" systemctl --user restart "$UNIT"
    sleep 3
    "${AS[@]}" systemctl --user --no-pager status "$UNIT" | sed -n 1,3p
    echo "== $UNIT restarted; the sweep ran first (journalctl --user -u $UNIT as $U shows what it said)"
  fi
done
