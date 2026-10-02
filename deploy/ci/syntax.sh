#!/usr/bin/env bash
# Does every script and module of the tree at least parse? Seconds, and needs
# nothing from the server -- so it runs on every push even before the CI key
# exists, and on pull requests from forks, which never get the key.
#
#   bash deploy/ci/syntax.sh [TREE]
#
# bash -n for the shell scripts, compile() for the Python (no .pyc is
# written), and the JSON tables the server loads at start parsed as JSON. A
# syntax error anywhere is reported with its file and line, all of them, not
# only the first.
set -uo pipefail

TREE=$(cd "${1:-.}" && pwd)
cd "$TREE"
bad=0

while IFS= read -r f; do
  bash -n "$f" || { echo "::error file=$f::bash -n failed"; bad=1; }
done < <(find deploy tools -name '*.sh' -type f | sort)

python3 - <<'EOF' || bad=1
import glob, json, sys
bad = 0
for path in sorted(glob.glob("server/*.py") + glob.glob("data/*.py") + glob.glob("tools/*.py")
                   + glob.glob("tools/impact/*.py")):
    try:
        with open(path, "rb") as fh:
            compile(fh.read(), path, "exec")
    except SyntaxError as e:
        print("::error file=%s,line=%s::%s" % (path, e.lineno, e.msg))
        bad = 1
for path in sorted(glob.glob("data/*.json")):
    try:
        with open(path, encoding="utf-8") as fh:
            json.load(fh)
    except ValueError as e:
        print("::error file=%s::%s" % (path, e))
        bad = 1
sys.exit(bad)
EOF

if [ "$bad" = 0 ]; then
  echo "syntax: every .sh under deploy/ and tools/, every .py under server/, data/, tools/ and tools/impact/, every data/*.json parses"
fi
exit "$bad"
