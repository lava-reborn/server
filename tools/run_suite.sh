#!/usr/bin/env bash
# Every suite, N at a time, longest first (README «Запуск»):
#
#   bash tools/run_suite.sh [options] . /tmp/lava_suite 8
#   bash tools/run_suite.sh . /tmp/lava_suite 8 --affected
#   bash tools/run_suite.sh . /tmp/lava_suite 8 --only test_combat,test_death
#
# $1 the repository, $2 the output directory, $3 how many at once; options
# may come before or after them. One output file per suite in $2, and
# summary.txt with a line per suite: exit code, seconds, name; a zero in
# front is a green suite. The suites that wait on game time share the clock,
# so one that depends on it can fail under load: run it alone before taking
# the failure for real.
#
# Every check a suite makes through server/testkit.py also goes, one JSON
# line each, to <name>.jsonl (LAVA_TEST_REPORT), and tools/suite_report.py
# makes report.html of the run at its end: mechanic, test, check, status and
# time, failed suites first (README «Запуск»). The report is for reading; it
# never changes the exit status.
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
#                   has finished, in a smaller crowd, and counts only if it
#                   fails again (output in <name>.rerun.out). On a busy
#                   runner (CI's: four shared cores, eight at once) a crowd
#                   of servers can make a suite miss a window it makes with
#                   fewer beside it; a real failure fails twice.
#   --rerun-jobs N  how many reruns at once (4). One at a time they used to
#                   outlast the job: two dozen suites of two to ten minutes.
#   --rerun-max M   more than M failures in the crowd (10) are not rerun: so
#                   many is a break, not a crowd, and the run fails at once
#                   rather than spend half an hour proving it.
#   --summary FILE  append the outcome as Markdown to FILE (the job summary).
#   --shard I/N     only the I-th of N parts of the set, for N runners side by
#                   side (CI ran three such shards while it had three
#                   runners; on one it runs the whole set). The parts are cut by the durations of
#                   the previous run, longest first, each suite to the part
#                   with the least so far (a suite it does not know counts as
#                   two minutes); every part of one run must see the same
#                   summary.txt, or a suite could fall between two of them.
#                   deploy/ci/merge_shards.sh checks afterwards that every
#                   suite ran exactly once.
#
# OPTIONS for a run by hand, never in CI: CI and with it every deploy run
# every suite, so under GitHub Actions (GITHUB_ACTIONS set) the runner
# refuses these two and exits 2 rather than run part of the set.
#
#   --only A,B      only these suites, by name (test_combat).
#   --affected      only the suites the change since --base (origin/main)
#                   touches, by the map --record-map writes (tools/suite.py
#                   picks them and says why; no map runs everything).
#   --base REF      what --affected compares with.
#   --list          say which suites, in which order, and run nothing.
#   --record-map    run, and remember which functions of server/ each suite
#                   runs (tools/impact/sitecustomize.py on the path of every
#                   process): tools/impact_map.json, the map of --affected.
set -u

KNOWN=
RERUN=0
RERUN_JOBS=4
RERUN_MAX=10
SUMMARY=
SHARD=
ONLY=
AFFECTED=0
BASE=origin/main
LIST=0
RECORD=0
POS=()
while [ $# -gt 0 ]; do
  case $1 in
    --known)      KNOWN=$2; shift 2 ;;
    --rerun)      RERUN=1; shift ;;
    --rerun-jobs) RERUN_JOBS=$2; shift 2 ;;
    --rerun-max)  RERUN_MAX=$2; shift 2 ;;
    --summary)    SUMMARY=$2; shift 2 ;;
    --shard)      SHARD=$2; shift 2 ;;
    --only)       ONLY=$2; shift 2 ;;
    --affected)   AFFECTED=1; shift ;;
    --base)       BASE=$2; shift 2 ;;
    --list)       LIST=1; shift ;;
    --record-map) RECORD=1; shift ;;
    --)           shift; POS+=("$@"); break ;;
    -*)           echo "run_suite: unknown option $1" >&2; exit 2 ;;
    *)            POS+=("$1"); shift ;;
  esac
done
SELECT=0
if [ -n "$ONLY" ] || [ "$AFFECTED" = 1 ]; then
  SELECT=1
fi
if [ "$SELECT" = 1 ] && [ -n "${GITHUB_ACTIONS:-}" ]; then
  echo "run_suite: CI runs every suite; --only and --affected are for a run by hand" >&2
  exit 2
fi
if [ -n "$SHARD" ]; then
  case $SHARD in
    *[!0-9/]*|*/*/*|/*|*/) echo "run_suite: --shard wants I/N, got $SHARD" >&2; exit 2 ;;
  esac
  SHARD_I=${SHARD%/*}; SHARD_N=${SHARD#*/}
  if [ "$SHARD_N" -lt 1 ] || [ "$SHARD_I" -lt 1 ] || [ "$SHARD_I" -gt "$SHARD_N" ]; then
    echo "run_suite: --shard wants I/N with 1 <= I <= N, got $SHARD" >&2; exit 2
  fi
fi
if [ -n "$KNOWN" ]; then
  [ -f "$KNOWN" ] || { echo "run_suite: no $KNOWN" >&2; exit 2; }
  KNOWN=$(cd "$(dirname "$KNOWN")" && pwd)/$(basename "$KNOWN")
fi

ROOT=$(cd "${POS[0]:-.}" && pwd)
OUT=${POS[1]:-/tmp/lava_suite}
N=${POS[2]:-8}

# Which suites --only and --affected ask for: tools/suite.py picks them (the
# map, git diff against --base) and prints the paths, after its reasons.
pick_args=(--list --base "$BASE")
[ -n "$ONLY" ] && pick_args+=(--only "$ONLY")
[ "$AFFECTED" = 1 ] && pick_args+=(--affected)
if [ "$LIST" = 1 ]; then
  exec python3 "$ROOT/tools/suite.py" "${pick_args[@]}"
fi
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

PICKED=
if [ "$SELECT" = 1 ]; then
  picked=$(python3 tools/suite.py "${pick_args[@]}") || { echo "$picked" >&2; exit 2; }
  printf '%s\n' "$picked" | grep -vE '^(server|data|tools)/test_[^/]*\.py$'
  PICKED=$(printf '%s\n' "$picked" | grep -E '^(server|data|tools)/test_[^/]*\.py$')
  if [ -z "$PICKED" ]; then
    echo "nothing to run"
    exit 0
  fi
fi

# The previous run's durations, before this run starts writing its own.
PREV=$OUT/summary.prev.txt
if [ -s "$OUT/summary.txt" ]; then
  mv "$OUT/summary.txt" "$PREV"
fi
{
  echo server/test_halfa_training.py
  ls -S server/test_*.py | grep -v -e test_halfa_training -e test_storage_pg
  ls data/test_*.py tools/test_*.py client/test_*.py
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
if [ -n "$SHARD" ]; then
  # Longest first, each to the part with the least so far: the parts end
  # close together. Every shard computes the same cut from the same list and
  # the same durations, and keeps its own.
  while read -r t; do
    d=
    [ -s "$PREV" ] && d=$(awk -v n="$(basename "$t" .py)" '$3 == n { sub(/s$/, "", $2); print $2; exit }' "$PREV")
    echo "${d:-120} $t"
  done < "$OUT/list.txt" | awk -v i="$SHARD_I" -v n="$SHARD_N" '
    { best = 0
      for (k = 1; k < n; k++) if (load[k] < load[best]) best = k
      load[best] += $1
      if (best == i - 1) print $2 }' > "$OUT/list.shard"
  mv "$OUT/list.shard" "$OUT/list.txt"
  if [ ! -s "$OUT/list.txt" ]; then
    echo "shard $SHARD: nothing to run"
    : > "$OUT/summary.txt"
    exit 0
  fi
fi
if [ -n "$PICKED" ]; then
  # In the order above, only what was picked.
  printf '%s\n' "$PICKED" | grep -xF -f - "$OUT/list.txt" > "$OUT/list.picked"
  mv "$OUT/list.picked" "$OUT/list.txt"
fi

# --record-map: every Python process of the run loads the hook, which writes
# what it runs of server/ to a file of its own in IMPACT; tools/suite.py
# --save-map makes the map of them once the run is over.
IMPACT=
if [ "$RECORD" = 1 ]; then
  IMPACT=$(mktemp -d /tmp/lava_impact.XXXXXX)
  export LAVA_IMPACT_OUT=$IMPACT LAVA_IMPACT_ROOT=$ROOT
  export PYTHONPATH=$ROOT/tools/impact${PYTHONPATH:+:$PYTHONPATH}
fi

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
  # Its checks, one JSON line each (server/testkit.py), for report.html.
  export LAVA_TEST_REPORT=$OUT/$name${SUFFIX:-}.jsonl LAVA_IMPACT_SUITE=$name
  rm -f "$LAVA_TEST_REPORT"
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

# Once the run is over, reruns and all: the map --record-map was asked for,
# and report.html (tools/suite_report.py). The report is for reading, so
# whatever becomes of it, the exit status is the runner's own.
finish() {
  if [ -n "$IMPACT" ]; then
    if python3 tools/suite.py --save-map "$IMPACT" \
        --only "$(xargs -n1 basename < "$OUT/list.txt" | sed 's/[.]py$//' | paste -sd,)"; then
      rm -rf "$IMPACT"
    else
      # A whole run's records are not thrown away with a map that failed.
      echo "run_suite: no map written; the records are kept in $IMPACT"
    fi
  fi
  rm -f "$OUT/report.html"
  python3 tools/suite_report.py "$OUT" > "$OUT/report.txt" 2>&1
  if [ -s "$OUT/report.html" ]; then
    echo "report: $OUT/report.html"
  else
    echo "run_suite: no report.html (see $OUT/report.txt)"
  fi
}

if [ -z "$KNOWN" ] && [ "$RERUN" = 0 ] && [ -z "$SUMMARY" ]; then
  finish
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
    if ! grep -qxF "$t" "$OUT/list.txt"; then
      # Not run: gone from the tree -- or left out of a run by hand (--only,
      # --affected) or to another shard, which says nothing about it.
      { [ -n "$PICKED" ] || [ -n "$SHARD" ]; } && [ -f "$t" ] || stale+=("$t (no such suite)")
      continue
    fi
    grep -q "^0 [0-9]*s $(basename "$t" .py)$" "$OUT/summary.txt" && stale+=("$t")
  done < "$KNOWN"
fi

norerun=
if [ "$RERUN" = 1 ] && [ ${#real[@]} -gt "$RERUN_MAX" ]; then
  norerun="${#real[@]} failed in the crowd, more than --rerun-max $RERUN_MAX: not rerun"
  echo "=== $norerun"
  hard=("${real[@]}")
elif [ "$RERUN" = 1 ] && [ ${#real[@]} -gt 0 ]; then
  echo "=== ${#real[@]} failed in the crowd; running each again, $RERUN_JOBS at once"
  : > "$OUT/summary.rerun.txt"
  printf '%s\n' "${real[@]}" \
    | SUMMARY_FILE="$OUT/summary.rerun.txt" SUFFIX=.rerun xargs -P "$RERUN_JOBS" -I{} bash -c 'run_one {}'
  cat "$OUT/summary.rerun.txt"
  for t in "${real[@]}"; do
    if grep -q "^0 [0-9]*s $(basename "$t" .py)$" "$OUT/summary.rerun.txt"; then
      flaky+=("$t")
    else
      hard+=("$t")
    fi
  done
else
  hard=("${real[@]}")
fi

finish
out_of() { echo "$OUT/$(basename "$1" .py)${2:-}.out"; }
passed=$(grep -c '^0 ' "$OUT/summary.txt")
echo "=== passed: $passed"
for i in "${!allowed[@]}"; do echo "=== known failure (allowed): ${allowed[$i]} -- ${allowed_why[$i]}"; done
for t in "${stale[@]}"; do echo "=== on the known list but PASSED or GONE: $t -- take it off $KNOWN"; done
for t in "${flaky[@]}"; do echo "=== failed in the crowd, passed on rerun: $t ($(out_of "$t"), $(out_of "$t" .rerun))"; done
for t in "${hard[@]}"; do
  if [ "$RERUN" = 1 ] && [ -z "$norerun" ]; then
    echo "=== FAILED twice: $t ($(out_of "$t"), $(out_of "$t" .rerun))"
  else
    echo "=== FAILED: $t ($(out_of "$t"))"
  fi
done

if [ -n "$SUMMARY" ]; then
  {
    echo "### Suites${SHARD:+, shard $SHARD}: $(wc -l < "$OUT/list.txt") in ${total}s, $N at once"
    echo
    [ -n "$norerun" ] && { echo "$norerun."; echo; }
    echo "| outcome | suite | note |"
    echo "|---|---|---|"
    for t in "${hard[@]}"; do echo "| **failed** | \`$t\` | $( [ "$RERUN" = 1 ] && [ -z "$norerun" ] && echo "failed again on rerun" ) |"; done
    for t in "${flaky[@]}"; do echo "| passed on rerun | \`$t\` | failed among the others, passed on rerun |"; done
    for i in "${!allowed[@]}"; do echo "| known failure | \`${allowed[$i]}\` | ${allowed_why[$i]} |"; done
    for t in "${stale[@]}"; do echo "| known, but passed or gone | \`$t\` | take it off the list |"; done
    echo "| passed | $passed suites | |"
    echo
    echo "<details><summary>durations</summary>"
    echo
    echo '```'
    grep -v DONE "$OUT/summary.txt" | sort -k2,2rn
    [ -s "$OUT/summary.rerun.txt" ] && { echo "-- rerun, $RERUN_JOBS at once:"; cat "$OUT/summary.rerun.txt"; }
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
