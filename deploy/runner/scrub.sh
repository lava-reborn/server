#!/usr/bin/env bash
# The self-hosted runner's work folder, swept between jobs (README «Раннер»,
# «Между задачами»). Installed by deploy/runner/install.sh as
# /usr/local/lib/lava-runner/scrub.sh, root's, and run as ghrunner:
#
#   ACTIONS_RUNNER_HOOK_JOB_STARTED=/usr/local/lib/lava-runner/scrub.sh
#   ACTIONS_RUNNER_HOOK_JOB_COMPLETED=/usr/local/lib/lava-runner/scrub.sh
#       in the runner's .env: before the job's containers start, and after
#       they are gone ("Set up runner" and "Complete runner" in the job log)
#   ExecStartPre=-/usr/local/lib/lava-runner/scrub.sh --idle
#       in lava-runner[-N].service.d/scrub.conf: whenever the runner
#       starts, after a crash or a reboot as well
#
# Several runners share the host (~ghrunner/actions-runner, actions-runner-2,
# ...; deploy/runner/register.sh): each sweeps its own _work, and its own
# containers only (below).
#
# A job (a hook): everything in _work goes but _actions and _temp, which the
# runner renews itself (it deletes _actions and downloads the actions again
# at the start of every job, and empties _temp at the start and the end);
# of _temp, _github_home goes too -- a job container's HOME, with the
# assets and whatever a job wrote there. The two folders the runner made for
# this job before the hook (_tool, the default workspace) are made again,
# empty. So the checkout, its .git with it, never reaches the next job, and
# neither does _PipelineMapping, the runner's tracking file, which a job can
# rewrite to move the next job's workspace. ci.yml's first step does the
# same from inside the container; this is the half that does not depend on
# the workflow a branch brings.
#
# --idle (the runner is not running): first whatever the unit's last run
# left in its cgroup -- KillMode=process leaves a worker and its children
# alive when the listener dies -- then the containers and networks this
# runner made in the rootless Docker the runners share: the runner labels
# them with a key of its own ("--label 1d54aa"), which its worker logs name;
# another runner's job keeps running. Then unused volumes, dangling images
# and the build cache (what a running job uses is in use and stays), then
# all of _work. The runner is the unit's WorkingDirectory (systemd starts
# ExecStartPre there), else LAVA_RUNNER_DIR, else ~/actions-runner.
#
# Never follows a link: a job can leave one in _work pointing anywhere, and
# rm -rf on a link removes the link. Always exits 0: a hook that fails fails
# the job, and a deploy that went through should not turn red over a file
# that would not go; what is left is printed (a warning in the job log, the
# journal for --idle), and the next job's first step deletes it from inside
# its container, where every file a job can make is root's.
#
# The runner runs a hook as "bash --noprofile --norc -e -o pipefail": errexit
# goes off again here, so one file that will not go does not stop the rest.
set +e
set -uo pipefail
shopt -s nullglob dotglob

say() {
  if [ -n "${RUNNER_TEMP:-}" ] && [ -z "$IDLE" ]; then
    echo "::warning title=Runner scrub::$*"
  else
    echo "scrub: $*" >&2
  fi
}

IDLE=
[ "${1:-}" = --idle ] && IDLE=1

if [ -n "$IDLE" ]; then
  if [ -n "${LAVA_RUNNER_DIR:-}" ]; then
    RDIR=$LAVA_RUNNER_DIR
  elif [ -f "$PWD/.runner" ]; then
    RDIR=$PWD
  else
    RDIR=$HOME/actions-runner
  fi
  WORK=${LAVA_RUNNER_WORK:-$RDIR/_work}
elif [ -n "${RUNNER_TEMP:-}" ]; then
  WORK=$(dirname "$RUNNER_TEMP")
else
  echo "usage: $0 (as a job hook of the runner) | $0 --idle (the runner stopped)" >&2
  exit 2
fi

# The work folder by its name, a folder of its own, ours -- or nothing.
if [ "${WORK##*/}" != _work ] || [ -L "$WORK" ] || [ ! -d "$WORK" ] || [ ! -O "$WORK" ]; then
  [ -e "$WORK" ] || [ -L "$WORK" ] || exit 0    # a fresh runner: no _work before its first job
  say "'$WORK' is not the runner's own _work folder; nothing swept"
  exit 0
fi

if [ -n "$IDLE" ]; then
  cg=$(sed -n 's/^0:://p' /proc/self/cgroup)
  unit=${LAVA_RUNNER_UNIT:-${cg##*/}}
  if [[ ${cg##*/} == lava-runner*.service ]] && [ "${cg##*/}" = "$unit" ]; then
    # ExecStartPre of the unit: the listener is not started yet, so whatever
    # else is in the unit's cgroup is what its last run left behind.
    procs=()
    [ -r "/sys/fs/cgroup$cg/cgroup.procs" ] && mapfile -t procs < "/sys/fs/cgroup$cg/cgroup.procs"
    left=0
    for p in "${procs[@]}"; do
      [ "$p" = "$$" ] && continue
      kill -KILL "$p" 2> /dev/null && left=$((left + 1))
    done
    [ "$left" = 0 ] || say "killed $left process(es) the runner's last run left in $unit"
  elif pgrep -u "$(id -u)" -f "^$RDIR/bin/Runner\.(Listener|Worker)" > /dev/null; then
    say "the runner in $RDIR is running; stop it first (systemctl --user stop its unit), or let a job hook sweep"
    exit 0
  fi

  export DOCKER_HOST=${DOCKER_HOST:-unix://${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock}
  if docker info > /dev/null 2>&1; then
    # This runner's own label, as its workers passed it to docker create and
    # docker network create. None yet: it never made a container.
    logs=("$RDIR"/_diag/Worker_*.log)
    labels=()
    [ "${#logs[@]}" = 0 ] || mapfile -t labels < <(grep -ohE -- '--label [0-9a-f]{6}( |$)' "${logs[@]}" 2> /dev/null \
                                                     | awk '{ print $2 }' | sort -u)
    for l in "${labels[@]}"; do
      mapfile -t ids < <(docker ps -aq --filter "label=$l")
      [ "${#ids[@]}" = 0 ] || docker rm -f -v "${ids[@]}" > /dev/null || say "docker rm failed"
      docker network prune -f --filter "label=$l" > /dev/null || say "docker network prune failed"
    done
    docker volume prune -af > /dev/null 2>&1 || docker volume prune -f > /dev/null || say "docker volume prune failed"
    docker image prune -f > /dev/null || say "docker image prune failed"
    docker builder prune -af > /dev/null 2>&1 || true
  else
    say "the runner's Docker ($DOCKER_HOST) does not answer; its containers are left as they are"
  fi

  for e in "$WORK"/*; do
    rm -rf -- "$e"
  done
  mapfile -t left < <(find "$WORK" -mindepth 1)
else
  for e in "$WORK"/*; do
    case ${e##*/} in
      _actions | _temp) ;;
      *) rm -rf -- "$e" ;;
    esac
  done
  if [ -d "$WORK/_temp" ] && [ ! -L "$WORK/_temp" ]; then
    rm -rf -- "$WORK/_temp/_github_home"
  fi
  # What the runner prepared for this job before the started hook, empty
  # again (after the job the next one prepares them anyway).
  keep=("$WORK/_tool")
  r=${GITHUB_REPOSITORY:-}
  r=${r#*/}
  if [[ $r =~ ^[A-Za-z0-9._-]+$ ]] && [ "$r" != . ] && [ "$r" != .. ]; then
    keep+=("$WORK/$r" "$WORK/$r/$r")
  fi
  mkdir -p -- "${keep[@]}"
  mapfile -t left < <(find "$WORK" -mindepth 1 \( -path "$WORK/_actions" -o -path "$WORK/_temp" \) -prune -o -print \
                        | grep -vxF -f <(printf '%s\n' "${keep[@]}"))
fi

[ "${#left[@]}" = 0 ] || say "${#left[@]} entries in $WORK would not go, $(id -un) may not delete them: ${left[*]:0:5}"
exit 0
