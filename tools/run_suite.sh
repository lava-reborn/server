#!/usr/bin/env bash
# The suites, N at a time (README «Запуск»): tools/suite.py does the work.
#
#   bash tools/run_suite.sh . /tmp/lava_suite 8
#   bash tools/run_suite.sh . /tmp/lava_suite 8 --affected
#   bash tools/run_suite.sh . /tmp/lava_suite 8 --only test_combat,test_death
#
# $1 the repository, $2 the output directory, $3 how many at once; anything
# after goes to tools/suite.py as it is (--affected, --only, --record-map,
# --list). One output file per suite in $2, summary.txt with a line per
# suite (exit code, seconds, name; a zero in front is a green suite) and
# report.html, the run as a table: mechanic, test, check, status, time.
#
# LAVA_RES names the client's res folder (default: ../lava-online/res beside
# the repository). test_storage_pg is left out: it wants Postgres.
set -u
ROOT=$(cd "${1:-.}" && pwd)
OUT=${2:-/tmp/lava_suite}
N=${3:-8}
shift $(( $# < 3 ? $# : 3 ))
export LAVA_RES=${LAVA_RES:-$ROOT/../lava-online/res}
exec python3 "$ROOT/tools/suite.py" --out "$OUT" --jobs "$N" --res "$LAVA_RES" "$@"
