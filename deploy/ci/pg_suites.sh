#!/usr/bin/env bash
# The suites that run against Postgres, each on a database of its own.
#
#   LAVA_PG=postgresql://lava:lavatest@127.0.0.1:5432 \
#       bash deploy/ci/pg_suites.sh [out] [jobs]
#
# LAVA_PG is the server without a database name, as a role that may create
# databases (the CI service's POSTGRES_USER is its superuser). Needs psycopg,
# LAVA_RES, and the tree this script sits in.
#
# Production runs on Postgres and every suite runs on SQLite by default, and
# that gap is where a deploy broke before: rowcount, a schema race, run_once
# keys, a 32-bit ALTER -- all fine on SQLite, all fatal on the shared
# database (README, "База: файл или общая"). So this job takes every suite
# that honours LAVA_DB_URL, not only the storage layer's own:
#
#   test_storage_pg   the Store against both dialects, the schema twice, the
#                     move from the old server's schema; it drops its tables
#   clan and ground   test_clans, test_clan_admin, test_clan_diplomacy,
#                     test_clan_mail, test_clan_treasury, test_ground
#   the rest          accounts, admin, auction, bank, combat, progression,
#                     relogin
#
# Not test_repair, though LAVA_DB_URL appears in it: it takes the variable
# OUT of its server's environment, so that server runs on a SQLite file while
# the suite's own Store, which follows the variable, would look in Postgres
# for what the server wrote. Under LAVA_DB_URL it fails for that reason alone
# (measured: "fixer" not found), so it runs in the SQLite job only. The same
# goes for test_clan_admin_wire and the socket half of test_clan_mail, which
# skip themselves.
#
# Each gets a fresh database, created here and named after it. That is also
# what test_clans needs: it is order-sensitive and has to be the first thing
# to run on its database -- one of its own, it always is. A failure is run
# again once, alone, on a database made fresh again; only a second failure
# counts, as in tools/run_suite.sh --rerun.
set -u

BASE=${LAVA_PG:?set LAVA_PG to postgresql://USER:PASSWORD@HOST:PORT}
OUT=${1:-/tmp/lava_pg}
JOBS=${2:-8}
TREE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
SUITES=(storage_pg clans clan_admin clan_diplomacy clan_mail clan_treasury ground
        accounts admin auction bank combat progression relogin)

mkdir -p "$OUT"
: > "$OUT/results"
rm -f "$OUT/results.rerun"

fresh() {   # suite... -> a new empty database t_<suite> for each
  python3 - "$BASE" "$@" <<'EOF'
import sys
import psycopg
base, suites = sys.argv[1], sys.argv[2:]
with psycopg.connect(base + "/postgres", autocommit=True) as db:
    for s in suites:
        db.execute('DROP DATABASE IF EXISTS "t_%s" WITH (FORCE)' % s)
        db.execute('CREATE DATABASE "t_%s"' % s)
EOF
}

run_pg() {
  s=$1; st=$(date +%s)
  (cd "$TREE/server" && LAVA_DB_URL="$BASE/t_$s" timeout 1500 \
     python3 "test_$s.py" > "$OUT/$s${SUFFIX:-}.log" 2>&1)
  echo "server/test_$s.py rc=$? $(( $(date +%s) - st ))s" >> "${RESULTS:-$OUT/results}"
}
export -f run_pg
export BASE OUT TREE

fresh "${SUITES[@]}" || { echo "pg: could not create the databases" >&2; exit 1; }
start=$(date +%s)
printf '%s\n' "${SUITES[@]}" | xargs -P "$JOBS" -I{} bash -c 'run_pg "$@"' _ {}
total=$(( $(date +%s) - start ))
echo "=== ${#SUITES[@]} suites on Postgres in ${total}s, $JOBS at once"

flaky=()
hard=()
for line in $(grep -v ' rc=0 ' "$OUT/results" | cut -d' ' -f1); do
  s=${line#server/test_}; s=${s%.py}
  echo "=== $line failed among the others; again, alone, on a fresh database"
  fresh "$s"
  RESULTS="$OUT/results.rerun" SUFFIX=.rerun run_pg "$s"
  tail -n 1 "$OUT/results.rerun"
  if grep -q "^$line rc=0 " "$OUT/results.rerun"; then flaky+=("$line"); else hard+=("$line"); fi
done

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### Postgres: ${#SUITES[@]} suites in ${total}s, $JOBS at once"
    echo
    for t in "${hard[@]}"; do echo "- **failed twice**: \`$t\`"; done
    for t in "${flaky[@]}"; do echo "- passed on rerun: \`$t\` (failed among the others, passed alone)"; done
    echo "- passed: $(grep -c ' rc=0 ' "$OUT/results") of ${#SUITES[@]} at the first go"
    echo
    echo '```'
    sed -E 's/^(.*) ([0-9]+)s$/\2 \1/' "$OUT/results" | sort -rn | sed -E 's/^([0-9]+) (.*)$/\2 \1s/'
    echo '```'
  } >> "$GITHUB_STEP_SUMMARY"
fi

for t in "${flaky[@]}"; do echo "=== failed among the others, passed alone: $t"; done
if [ ${#hard[@]} -gt 0 ]; then
  for t in "${hard[@]}"; do echo "=== FAILED twice: $t (logs in $OUT)"; done
  exit 1
fi
echo "=== all green on Postgres"
