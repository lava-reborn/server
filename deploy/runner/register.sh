#!/usr/bin/env bash
# Register GitHub Actions runners for lvrbrn/server on the production host
# and start them (README «Раннер»). Installed by deploy/runner/install.sh as
# /opt/lava-runner/register.sh. As root:
#
#   ssh -t root@159.194.247.90 bash /opt/lava-runner/register.sh [N ...]
#
# or, the token copied to the clipboard on Windows, in one go:
#
#   powershell -NoProfile -Command Get-Clipboard | ssh -o BatchMode=yes root@159.194.247.90 bash /opt/lava-runner/register.sh 2 3 4
#
# Reads one registration token (GitHub -> lvrbrn/server -> Settings ->
# Actions -> Runners -> New self-hosted runner, the value after --token; it
# lives an hour and registers any number of runners). N is the runner's
# number, 1 when none is given:
#
#   1   ~ghrunner/actions-runner,   name lava-prod,   unit lava-runner.service
#   N   ~ghrunner/actions-runner-N, name lava-prod-N, unit lava-runner-N.service
#       (its program copied from the first runner's folder)
#
# A runner already registered is removed and registered again. All of them
# run as ghrunner under its user systemd, inside one user-1500.slice (4
# cores, 6 GB for all of them together) and with its one rootless Docker,
# labels self-hosted and lava. Afterwards deploy/runner/install.sh puts the
# sweep between jobs (hooks, drop-ins) on each of them.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }
U=$(id -u ghrunner)
H=/home/ghrunner
FIRST=$H/actions-runner
AS=(runuser -u ghrunner -- env "XDG_RUNTIME_DIR=/run/user/$U" "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$U/bus" "HOME=$H")
# Where they register: the repository (the default), or the organisation when
# the token is one from the organisation's settings (LAVA_RUNNER_URL=https://github.com/lvrbrn).
URL=${LAVA_RUNNER_URL:-https://github.com/lvrbrn/server}
[[ $URL =~ ^https://github[.]com/lvrbrn(/server)?$ ]] || { echo "LAVA_RUNNER_URL is not lvrbrn or lvrbrn/server: $URL"; exit 2; }

NS=("$@")
[ "${#NS[@]}" -gt 0 ] || NS=(1)
for n in "${NS[@]}"; do
  [[ $n =~ ^[1-9]$ ]] || { echo "runner numbers are 1 to 9, got '$n'"; exit 2; }
done

read -rs -p "Registration token: " TOKEN || true
echo
# A token piped from a Windows clipboard ends in CR LF; spaces may ride along.
TOKEN=$(printf %s "$TOKEN" | tr -d '\r\n\t ')
[ -n "$TOKEN" ] || { echo "empty token"; exit 1; }

for n in "${NS[@]}"; do
  if [ "$n" = 1 ]; then
    R=$FIRST NAME=lava-prod UNIT=lava-runner.service
  else
    R=$H/actions-runner-$n NAME=lava-prod-$n UNIT=lava-runner-$n.service
  fi
  echo "== runner $n: $NAME in $R ($UNIT)"
  if [ ! -x "$R/config.sh" ]; then
    [ -x "$FIRST/config.sh" ] || { echo "no runner program in $FIRST to copy"; exit 1; }
    install -d -m 755 -o ghrunner -g ghrunner "$R"
    # The program only: not the first runner's registration, credentials,
    # settings, logs or work folder.
    for e in "$FIRST"/* "$FIRST"/.[!.]*; do
      case ${e##*/} in
        _work | _diag | .runner | .runner_migrated | .credentials | .credentials_rsaparams | .env | .path | .service) continue ;;
      esac
      cp -RL --preserve=mode,timestamps "$e" "$R/"
    done
    chown -R ghrunner:ghrunner "$R"
    # The version as ghrunner: the program writes its _diag on any start, and
    # one made by root would stop config.sh below.
    echo "   program copied from $FIRST ($(cd "$R" && "${AS[@]}" ./bin/Runner.Listener --version 2> /dev/null || echo '?'))"
  fi
  if [ -f "$R/.runner" ]; then
    echo "   already configured: stopping and removing the old registration"
    "${AS[@]}" systemctl --user stop "$UNIT" 2> /dev/null || true
    (cd "$R" && "${AS[@]}" ./config.sh remove --token "$TOKEN") || true
  fi
  (cd "$R" && "${AS[@]}" ./config.sh --unattended --url "$URL" --token "$TOKEN" \
     --name "$NAME" --labels lava --work _work --replace)
  printf 'LANG=C.UTF-8\nDOCKER_HOST=unix:///run/user/%s/docker.sock\n' "$U" > "$R/.env"
  chown ghrunner:ghrunner "$R/.env"
  mkdir -p "$H/.config/systemd/user"
  cat > "$H/.config/systemd/user/$UNIT" <<EOT
[Unit]
Description=GitHub Actions runner $NAME for lvrbrn/server (labels self-hosted, lava)
After=docker.service
Wants=docker.service

[Service]
WorkingDirectory=$R
ExecStart=$R/run.sh
Restart=always
RestartSec=10
KillMode=process
KillSignal=SIGTERM
TimeoutStopSec=5min

[Install]
WantedBy=default.target
EOT
done
unset TOKEN
chown -R ghrunner:ghrunner "$H/.config"
"${AS[@]}" systemctl --user daemon-reload
for n in "${NS[@]}"; do
  if [ "$n" = 1 ]; then UNIT=lava-runner.service R=$FIRST; else UNIT=lava-runner-$n.service R=$H/actions-runner-$n; fi
  "${AS[@]}" systemctl --user enable --now "$UNIT"
done
sleep 8
for n in "${NS[@]}"; do
  if [ "$n" = 1 ]; then UNIT=lava-runner.service R=$FIRST; else UNIT=lava-runner-$n.service R=$H/actions-runner-$n; fi
  "${AS[@]}" systemctl --user --no-pager status "$UNIT" | sed -n 1,3p
  grep -h "Listening for Jobs" "$R"/_diag/Runner_*.log 2> /dev/null | tail -1 || true
done
echo "== done: the runners should show as Idle in GitHub -> Settings -> Actions -> Runners."
echo "   Then, for the sweep between jobs: bash /root/lava-ci-src/deploy/runner/install.sh"
