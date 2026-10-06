#!/usr/bin/env bash
# The sweep between jobs, onto the runner on the production host (README
# «Раннер», «Между задачами»). As root, from a copy of the repository's
# deploy/ folder; a second run updates what the first installed:
#
#   tar -cz deploy | ssh root@159.194.247.90 'rm -rf /root/lava-ci-src && mkdir /root/lava-ci-src && tar -xz -C /root/lava-ci-src'
#   ssh root@159.194.247.90 bash /root/lava-ci-src/deploy/runner/install.sh
#   ssh root@159.194.247.90 bash /root/lava-ci-src/deploy/runner/check.sh
#
#   * scrub.sh -> /usr/local/lib/lava-runner/scrub.sh, root's, 0755: a job
#     runs as ghrunner and cannot rewrite it;
#   * ACTIONS_RUNNER_HOOK_JOB_STARTED and ..._COMPLETED, both that script,
#     into the runner's .env (the lines are replaced, never doubled);
#   * scrub.conf -> ~ghrunner/.config/systemd/user/lava-runner.service.d/;
#   * daemon-reload, and a restart of the runner -- the runner reads .env
#     only when it starts -- unless a job is running: then it says so, and
#     the restart is yours once the job is over.
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
U=${LAVA_RUNNER_USER:-ghrunner}
UNIT=${LAVA_RUNNER_UNIT:-lava-runner.service}
uid=$(id -u "$U")
H=$(getent passwd "$U" | cut -d: -f6)
R=${LAVA_RUNNER_DIR:-$H/actions-runner}
LIB=/usr/local/lib/lava-runner
HERE=$(cd "$(dirname "$0")" && pwd)
AS=(runuser -u "$U" -- env "XDG_RUNTIME_DIR=/run/user/$uid" "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus")

[ -f "$R/.runner" ] || { echo "$R is not a configured runner (no .runner)" >&2; exit 1; }
bash -n "$HERE/scrub.sh"

install -d -m 755 -o root -g root "$LIB"
install -m 755 -o root -g root "$HERE/scrub.sh" "$LIB/scrub.sh"
echo "== $LIB/scrub.sh"

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
"${AS[@]}" systemctl --user daemon-reload
echo "== $D/scrub.conf, daemon-reload"

if pgrep -u "$U" -f 'bin/Runner\.Worker' > /dev/null; then
  echo "== a job is running: the hooks start with the next start of the runner."
  echo "   When the job is over:  ${AS[*]} systemctl --user restart $UNIT"
else
  "${AS[@]}" systemctl --user restart "$UNIT"
  sleep 5
  "${AS[@]}" systemctl --user --no-pager status "$UNIT" | sed -n 1,5p
  echo "== restarted; the sweep ran first (journalctl --user -u $UNIT as $U shows what it said)"
fi
