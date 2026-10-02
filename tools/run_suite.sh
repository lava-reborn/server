#!/usr/bin/env bash
# Every suite, N at a time, longest first (README «Запуск»):
#
#   bash tools/run_suite.sh . /tmp/lava_suite 8
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
# out: it wants Postgres.
set -u
ROOT=$(cd "${1:-.}" && pwd)
OUT=${2:-/tmp/lava_suite}
N=${3:-8}
export LAVA_RES=${LAVA_RES:-$ROOT/../lava-online/res}
export LAVA_ORIG_TEXTS=${LAVA_ORIG_TEXTS:-$LAVA_RES/xml/texts.xml}
export PYTHONUTF8=1
[ -f "$LAVA_RES/main.swf" ] || { echo "no client at $LAVA_RES (main.swf missing); set LAVA_RES" >&2; exit 2; }
mkdir -p "$OUT"
cd "$ROOT"
{
  echo server/test_halfa_training.py
  ls -S server/test_*.py | grep -v -e test_halfa_training -e test_storage_pg
  ls data/test_*.py tools/test_*.py
} > "$OUT/list.txt"

run_one() {
  t=$1; name=$(basename "$t" .py); dir=$(dirname "$t")
  export LAVA_DB=/tmp/lava_$name.db TMPDIR=/tmp/lava_$name
  mkdir -p "$TMPDIR"
  start=$(date +%s)
  ( cd "$dir" && timeout 1500 python3 "$(basename "$t")" ) > "$OUT/$name.out" 2>&1
  echo "$? $(( $(date +%s) - start ))s $name" >> "$OUT/summary.txt"
}
export -f run_one
export OUT
: > "$OUT/summary.txt"
xargs -P "$N" -I{} bash -c 'run_one {}' < "$OUT/list.txt"
echo DONE >> "$OUT/summary.txt"
echo "$(wc -l < "$OUT/list.txt") suites, $(grep -c -v -e '^0 ' -e DONE "$OUT/summary.txt") failed"
grep -v -e '^0 ' -e DONE "$OUT/summary.txt"
