#!/usr/bin/env bash
# Inside a disposable local Docker container only. Reuses CI's check scripts.
# /source and /res are read-only mounts; /reports is the sole host output.
set -uo pipefail
mkdir -p /work /reports/ci
if ! tar -C /source --exclude=./logs --exclude=./dist --exclude=./.env \
  --exclude=./.aws --exclude=./.codex --exclude=./.vscode \
  --exclude='*/__pycache__' --exclude='*/node_modules' \
  --exclude=./.venv --exclude=./.venv-local-checks -cf - . | tar -C /work -xf -; then
  echo 'Cannot copy the complete source tree; refusing a partial CI run'
  exit 2
fi
cd /work || exit 2
# Windows line endings are normalized in this disposable copy, never on the host.
find deploy tools launcher -name '*.sh' -type f -exec sed -i 's/\r$//' {} +
export HOME=/tmp/local-home
mkdir -p "$HOME"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1
export PYTHONWARNINGS=always::ResourceWarning
export LAVA_RES=/res LAVA_ORIG_TEXTS=/res/xml/texts.xml
export GITHUB_ACTIONS=true GITHUB_STEP_SUMMARY=/reports/ci/steps.md
unset LAVA_DB_URL
bad=0
stage() {
  local label=$1; shift
  local begin=$SECONDS
  "$@" > "/reports/ci/$label.log" 2>&1
  local rc=$?
  printf '%s\t%s\t%s\n' "$label" "$rc" "$((SECONDS-begin))" >> /reports/ci/stages.tsv
  echo "CI $label: exit=$rc, $((SECONDS-begin))s"
  if [ "$rc" -ne 0 ]; then tail -n 25 "/reports/ci/$label.log"; bad=1; fi
  return 0
}
# Same tools/base as ci.yml; package installation happens only in this container.
apt-get update -qq && apt-get install -qq -y --no-install-recommends \
  git openssh-client rsync ca-certificates > /reports/ci/setup.log 2>&1 \
  && python3 -m pip install --quiet 'psycopg[binary]==3.2.3' >> /reports/ci/setup.log 2>&1
if [ "$?" -ne 0 ]; then echo 'CI prerequisites failed; see ci/setup.log'; exit 2; fi
git config --global --add safe.directory /work
stage syntax bash deploy/ci/syntax.sh
stage texts python3 tools/export_texts.py -o /reports/ci/texts.xml
# Only the gate's configuration branches, with boolean placeholders. No SSH key.
stage gate-without-key env HAVE_KEY=false HAVE_HOSTS=false bash deploy/ci/preflight.sh
stage gate-configured env HAVE_KEY=true HAVE_HOSTS=true bash deploy/ci/preflight.sh
jobs=${LOCAL_CHECK_JOBS:-1}
for shard in 1 2 3; do
  stage "shard-$shard" bash tools/run_suite.sh --known tools/known_failures.txt \
    --rerun --rerun-jobs "$jobs" --shard "$shard/3" \
    --summary "$GITHUB_STEP_SUMMARY" . "/reports/ci/shards/$shard" "$jobs"
done
stage merge-shards bash deploy/ci/merge_shards.sh /reports/ci/shards /reports/ci/summary.txt
if [ -n "${LAVA_PG:-}" ]; then
  stage postgres bash deploy/ci/pg_suites.sh /reports/ci/postgres "$jobs"
else
  echo 'Postgres not available; CI coverage incomplete'; bad=1
fi
stage package bash deploy/ci/pack.sh /reports/ci/local-package.tgz
echo 'Not executed locally: SSH gate access, remote asset download, GitHub cache/artifact transport, deployment.'
exit "$bad"
