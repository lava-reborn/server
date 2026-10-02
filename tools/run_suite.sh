#!/usr/bin/env bash
# Every suite, N at a time, longest first (README «Запуск»):
#
#   bash tools/run_suite.sh [options] . /tmp/lava_suite 8
#
# $1 the repository, $2 the output directory, $3 how many at once. One output
# file per suite in $2, and summary.txt with a line per suite: exit code,
# seconds, name; a zero in front is a green suite. The suites that wait on
# game time share the clock, so one that depends on it can fail under load:
# run it alone before taking the failure for real.
#
# LAVA_RES names the client's res folder (default: ../lava-online/res beside
# the repository); LAVA_ORIG_TEXTS the original texts.xml for
# data/test_orig_misc (default: res/xml/texts.xml). test_storage_pg is left
# out: it wants Postgres (CI runs it in its own job, deploy/ci/pg_suites.sh).
#
# Longest first: by the durations in the summary.txt a previous run left in
# the same output directory (a suite it does not know goes first), else
# test_halfa_training, then the server suites by size, then the rest. A long
# suite started last would be the whole wait on its own.
#
# OPTIONS -- what CI runs it with (.github/workflows/ci.yml). Without them the
# runner does what it always has, and its exit status says whether anything
# failed.
#
#   --known FILE    suites expected to fail, each with the line its output has
#                   to show and the reason (tools/known_failures.txt). Such a
#                   failure is reported and not counted -- but only when its
#                   output shows that line: a known suite failing some other
#                   way is failing. A known suite that passes is reported too,
#                   so the list does not outlive its reasons.
#   --rerun         a failure that is not known is run again once the crowd
#                   has finished, alone, and counts only if it fails again
#                   (output in <name>.rerun.out). On a 2-vCPU runner a dozen
#                   servers at once can make a suite miss a window it makes
#                   alone; a real failure fails twice.
#   --summary FILE  append the outcome as Markdown to FILE (the job summary).
set -u

KNOWN=
RERUN=0
SUMMARY=
while [ $# -gt 0 ]; do
  case $1 in
    --known)   KNOWN=$2; shift 2 ;;
    --rerun)   RERUN=1; shift ;;
    --summary) SUMMARY=$2; shift 2 ;;
    --)        shift; break ;;
    -*)        echo "run_suite: unknown option $1" >&2; exit 2 ;;
    *)         break ;;
  esac
done
if [ -n "$KNOWN" ]; then
  [ -f "$KNOWN" ] || { echo "run_suite: no $KNOWN" >&2; exit 2; }
  KNOWN=$(cd "$(dirname "$KNOWN")" && pwd)/$(basename "$KNOWN")
fi

ROOT=$(cd "${1:-.}" && pwd)
OUT=${2:-/tmp/lava_suite}
N=${3:-8}
export LAVA_RES=${LAVA_RES:-$ROOT/../lava-online/res}
export LAVA_ORIG_TEXTS=${LAVA_ORIG_TEXTS:-$LAVA_RES/xml/texts.xml}
export PYTHONUTF8=1
# objects.xml, not main.swf: CI carries the slice of res/ the server reads
# (deploy/ci/fetch_assets.sh), and that is enough for every suite but the
# ones its extras stand in for -- the same file launcher/build.ps1 asks for.
[ -f "$LAVA_RES/database/objects.xml" ] \
  || { echo "no client at $LAVA_RES (database/objects.xml missing); set LAVA_RES" >&2; exit 2; }
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
cd "$ROOT"

# The previous run's durations, before this run starts writing its own.
PREV=$OUT/summary.prev.txt
if [ -s "$OUT/summary.txt" ]; then
  mv "$OUT/summary.txt" "$PREV"
fi
{
  echo server/test_halfa_training.py
  ls -S server/test_*.py | grep -v -e test_halfa_training -e test_storage_pg
  ls data/test_*.py tools/test_*.py
} > "$OUT/list.static"
if [ -s "$PREV" ]; then
  # "0 123s test_x" -> 123 for test_x; unknown ones 99999, so they go first,
  # in the static order among themselves (sort -s keeps it).
  while read -r t; do
    d=$(awk -v n="$(basename "$t" .py)" '$3 == n { sub(/s$/, "", $2); print $2; exit }' "$PREV")
    echo "${d:-99999} $t"
  done < "$OUT/list.static" | sort -s -k1,1rn | cut -d' ' -f2 > "$OUT/list.txt"
else
  cp "$OUT/list.static" "$OUT/list.txt"
fi
rm -f "$OUT/list.static"

# Each suite gets a database file and a TMPDIR of its own, empty at its start,
# under a folder named after the output directory: two runs side by side
# (two worktrees, a rerun while another run goes on) do not share a file, and
# a rerun does not start on what the failed attempt left.
RUNTMP=/tmp/lava_suite_tmp.$(printf '%s' "$OUT" | cksum | cut -d' ' -f1)

# SUMMARY_FILE and SUFFIX let the rerun below keep its own record and its own
# output beside the first ones, so both are there to read afterwards.
run_one() {
  t=$1; name=$(basename "$t" .py); dir=$(dirname "$t")
  rm -rf "${RUNTMP:?}/$name"
  mkdir -p "$RUNTMP/$name/tmp"
  export LAVA_DB=$RUNTMP/$name/lava.db TMPDIR=$RUNTMP/$name/tmp
  start=$(date +%s)
  ( cd "$dir" && timeout 1500 python3 "$(basename "$t")" ) > "$OUT/$name${SUFFIX:-}.out" 2>&1
  echo "$? $(( $(date +%s) - start ))s $name" >> "${SUMMARY_FILE:-$OUT/summary.txt}"
}
export -f run_one
export OUT RUNTMP
: > "$OUT/summary.txt"
rm -f "$OUT/summary.rerun.txt"
start=$(date +%s)
xargs -P "$N" -I{} bash -c 'run_one {}' < "$OUT/list.txt"
total=$(( $(date +%s) - start ))
echo DONE >> "$OUT/summary.txt"
nfailed=$(grep -c -v -e '^0 ' -e DONE "$OUT/summary.txt")
echo "$(wc -l < "$OUT/list.txt") suites, $nfailed failed (${total}s, $N at once)"
grep -v -e '^0 ' -e DONE "$OUT/summary.txt"

if [ -z "$KNOWN" ] && [ "$RERUN" = 0 ] && [ -z "$SUMMARY" ]; then
  [ "$nfailed" = 0 ]
  exit
fi

# --- the CI verdict -----------------------------------------------------------
#
# The known list: "suite | pattern | reason", one suite a line, # comments;
# the suite by its path in the repository (server/test_x.py). The pattern is
# grep -E over the suite's output and may not contain a '|'; several joined
# by " && " must each match a line -- which is how an entry says "this
# failure and no other" (the suite's own count of failures, and the one).

path_of() {   # name -> its path as list.txt has it
  grep -m1 -E "(^|/)$1\.py$" "$OUT/list.txt"
}
known_entry() {   # path -> "pattern<TAB>reason", nothing if not listed
  [ -n "$KNOWN" ] || return 0
  awk -F'|' -v t="$1" '
    /^[[:space:]]*(#|$)/ { next }
    {
      p = $1; gsub(/^[ \t]+|[ \t]+$/, "", p)
      if (p != t) next
      sig = $2; gsub(/^[ \t]+|[ \t]+$/, "", sig)
      why = $0; sub(/^[^|]*\|[^|]*\|/, "", why); gsub(/^[ \t]+|[ \t]+$/, "", why)
      print sig "\t" why; exit
    }' "$KNOWN"
}

matches_all() {   # "p1 && p2 ..." file -> every pattern has a line in file
  local rest=$1 p
  while :; do
    p=${rest%% && *}
    grep -qE -- "$p" "$2" || return 1
    [ "$p" = "$rest" ] && return 0
    rest=${rest#* && }
  done
}

allowed=() ; allowed_why=() ; real=() ; flaky=() ; hard=() ; stale=()
while read -r rc secs name; do
  [ "$rc" = DONE ] && continue
  [ "$rc" = 0 ] && continue
  t=$(path_of "$name")
  entry=$(known_entry "$t")
  if [ -n "$entry" ] && matches_all "${entry%%$'\t'*}" "$OUT/$name.out"; then
    allowed+=("$t"); allowed_why+=("${entry#*$'\t'}")
  else
    real+=("$t")
  fi
done < "$OUT/summary.txt"
# A suite that is listed and passed, and a listed suite that is not in the
# tree any more: both mean the list has outlived a reason.
if [ -n "$KNOWN" ]; then
  while IFS='|' read -r t _; do
    t=$(echo "$t" | sed 's/^[ \t]*//; s/[ \t]*$//')
    case $t in ''|'#'*) continue ;; esac
    grep -qxF "$t" "$OUT/list.txt" || { stale+=("$t (no such suite)"); continue; }
    grep -q "^0 [0-9]*s $(basename "$t" .py)$" "$OUT/summary.txt" && stale+=("$t")
  done < "$KNOWN"
fi

if [ "$RERUN" = 1 ] && [ ${#real[@]} -gt 0 ]; then
  echo "=== ${#real[@]} failed in the crowd; running each again, alone"
  for t in "${real[@]}"; do
    SUMMARY_FILE="$OUT/summary.rerun.txt" SUFFIX=.rerun run_one "$t"
    tail -n 1 "$OUT/summary.rerun.txt"
    if grep -q "^0 [0-9]*s $(basename "$t" .py)$" "$OUT/summary.rerun.txt"; then
      flaky+=("$t")
    else
      hard+=("$t")
    fi
  done
else
  hard=("${real[@]}")
fi

out_of() { echo "$OUT/$(basename "$1" .py)${2:-}.out"; }
passed=$(grep -c '^0 ' "$OUT/summary.txt")
echo "=== passed: $passed"
for i in "${!allowed[@]}"; do echo "=== known failure (allowed): ${allowed[$i]} -- ${allowed_why[$i]}"; done
for t in "${stale[@]}"; do echo "=== on the known list but PASSED or GONE: $t -- take it off $KNOWN"; done
for t in "${flaky[@]}"; do echo "=== failed in the crowd, passed alone: $t ($(out_of "$t"), $(out_of "$t" .rerun))"; done
for t in "${hard[@]}"; do
  if [ "$RERUN" = 1 ]; then
    echo "=== FAILED twice: $t ($(out_of "$t"), $(out_of "$t" .rerun))"
  else
    echo "=== FAILED: $t ($(out_of "$t"))"
  fi
done

if [ -n "$SUMMARY" ]; then
  {
    echo "### Suites: $(wc -l < "$OUT/list.txt") in ${total}s, $N at once"
    echo
    echo "| outcome | suite | note |"
    echo "|---|---|---|"
    for t in "${hard[@]}"; do echo "| **failed** | \`$t\` | $( [ "$RERUN" = 1 ] && echo "failed again alone" ) |"; done
    for t in "${flaky[@]}"; do echo "| passed on rerun | \`$t\` | failed among the others, passed alone |"; done
    for i in "${!allowed[@]}"; do echo "| known failure | \`${allowed[$i]}\` | ${allowed_why[$i]} |"; done
    for t in "${stale[@]}"; do echo "| known, but passed or gone | \`$t\` | take it off the list |"; done
    echo "| passed | $passed suites | |"
    echo
    echo "<details><summary>durations</summary>"
    echo
    echo '```'
    grep -v DONE "$OUT/summary.txt" | sort -k2,2rn
    [ -f "$OUT/summary.rerun.txt" ] && { echo "-- rerun alone:"; cat "$OUT/summary.rerun.txt"; }
    echo '```'
    echo "</details>"
  } >> "$SUMMARY"
fi

if [ ${#hard[@]} -gt 0 ]; then
  echo "=== ${#hard[@]} suite(s) failed (output in $OUT)"
  exit 1
fi
if [ ${#allowed[@]} -gt 0 ]; then
  echo "=== green, with ${#allowed[@]} known failure(s)"
else
  echo "=== all green"
fi
exit 0
