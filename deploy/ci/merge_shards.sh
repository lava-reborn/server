#!/usr/bin/env bash
# The shards' records as one run: did every suite run, and exactly once?
#
#   bash deploy/ci/merge_shards.sh DIR OUT
#
# DIR holds one folder per shard, each with the summary.txt that
# tools/run_suite.sh --shard I/N left there. OUT becomes the summary.txt of
# the whole set, the durations the next run cuts its shards by. The shards
# cut the set each on its own, from the same list and the same durations; a
# shard that saw other durations (or a list that differs) would leave a suite
# out or run it twice, and this is where that shows: a missing suite fails the
# job, since a green run without it would deploy what nothing tested.
#
# CI has one runner now and runs the whole set in one job, as a single folder
# under DIR (ci.yml, job suite); the check is the same: every suite of the
# tree ran, and once.
set -uo pipefail

DIR=$1
OUT=$2

# What run_suite.sh runs: test_storage_pg is Postgres's, in its own job.
expected=$( { ls server/test_*.py | grep -v -e test_storage_pg; ls data/test_*.py tools/test_*.py; } \
            | xargs -n1 basename | sed 's/[.]py$//' | sort)

cat "$DIR"/*/summary.txt 2>/dev/null | grep -v '^DONE$' > "$OUT.all"
ran=$(awk '{ print $3 }' "$OUT.all" | sort)

missing=$(comm -23 <(echo "$expected") <(echo "$ran" | sort -u))
twice=$(echo "$ran" | uniq -d)
bad=0
for s in $missing; do echo "::error title=Shards::$s ran in no shard"; bad=1; done
for s in $twice; do echo "::error title=Shards::$s ran in more than one shard"; bad=1; done

mv "$OUT.all" "$OUT"
echo "$(echo "$ran" | grep -c .) suites over $(ls -d "$DIR"/*/ | wc -l) shards"
exit $bad
