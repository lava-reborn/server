#!/usr/bin/env bash
# Should this run's commit still go out? "go=true" or "go=false" into
# GITHUB_OUTPUT, and why on stdout.
#
#   GITHUB_SHA=<the run's commit> bash deploy/ci/still_head.sh [workflow.yml]
#
# Runs on main queue up behind each other (ci.yml, concurrency), so by the
# time this run's deploy starts main may have moved on. Two ways that goes:
#
#   main moved by code     a newer run is testing it, or will; it deploys the
#                          newer code and this run must not put the older code
#                          over it afterwards (nor must a re-run of an old
#                          run, days later). go=false.
#   main moved by prose    a push that only touched the files in paths-ignore
#                          starts no run at all. Were "not the head" enough to
#                          stand down, this run's code would never go out:
#                          the run that would deploy it does not exist. So
#                          what counts is the TREE: if the head differs from
#                          this commit only in those files, this commit's
#                          code IS the head's code, and go=true.
#
# The list of prose files is read out of the workflow's own push trigger, so
# there is one list and not two to keep equal. Only the head's commit and tree
# are fetched (depth 1): comparing two trees needs no history.
set -euo pipefail

WF=${1:-.github/workflows/ci.yml}
: "${GITHUB_SHA:?}"
out() { echo "$1" >> "${GITHUB_OUTPUT:-/dev/stdout}"; }

# The "- item" lines of the first paths-ignore: block, which is push's.
mapfile -t IGNORE < <(awk '
  /^[[:space:]]*paths-ignore:/ { if (seen) exit; seen = 1; on = 1; next }
  on && /^[[:space:]]*-[[:space:]]/ { sub(/^[[:space:]]*-[[:space:]]*/, ""); gsub(/["\047]/, ""); print; next }
  on && /^[[:space:]]*#/ { next }
  on { exit }' "$WF")
[ ${#IGNORE[@]} -gt 0 ] || { echo "still_head: no paths-ignore list in $WF" >&2; exit 1; }

# GitHub's globs as used there: "dir/**" is everything under dir/, anything
# else a file name at the top.
prose() {
  local f=$1 p
  for p in "${IGNORE[@]}"; do
    case $p in
      */\*\*) [[ $f == "${p%\*\*}"* ]] && return 0 ;;
      *)      [ "$f" = "$p" ] && return 0 ;;
    esac
  done
  return 1
}

git fetch --quiet --no-tags --depth=1 origin +refs/heads/main:refs/remotes/origin/main
HEAD_SHA=$(git rev-parse refs/remotes/origin/main)

if [ "$HEAD_SHA" = "$GITHUB_SHA" ]; then
  echo "main is still at ${GITHUB_SHA:0:12}: deploying it"
  out go=true
  exit 0
fi

# --no-renames: a code file renamed into a prose name would otherwise be
# listed under its new name alone, and pass for prose.
code=()
while IFS= read -r f; do
  prose "$f" || code+=("$f")
done < <(git diff --no-renames --name-only "$GITHUB_SHA" "$HEAD_SHA")

if [ ${#code[@]} -eq 0 ]; then
  echo "main is at ${HEAD_SHA:0:12} now, which differs from ${GITHUB_SHA:0:12} only in prose (${IGNORE[*]}); that push started no run, so this one deploys the code they share"
  out go=true
else
  echo "::notice title=Deploy skipped::main is at ${HEAD_SHA:0:12} now and its code differs from ${GITHUB_SHA:0:12} (${code[0]}$([ ${#code[@]} -gt 1 ] && echo " and $(( ${#code[@]} - 1 )) more")); the run for that commit deploys it"
  out go=false
fi
