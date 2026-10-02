#!/usr/bin/env bash
# Hand the packed tree to the gate and turn its report into the job summary.
#
#   bash deploy/ci/send.sh TGZ COMMIT
#
# The whole deploy happens on the server (deploy/remote/lava-gate.sh); this
# end sends the bytes with their sha256, shows what the gate says while it
# says it, and exits with the gate's status, so a rollback is a red job:
#
#   0 deployed   1 failed, rolled back   2 refused   3 rollback failed too
#   255 ssh itself failed (the gate never ran, or the line dropped mid-way --
#       then the deploy finishes on the server regardless; read its log there)
set -uo pipefail

[ $# -eq 2 ] || { echo "usage: $0 TGZ COMMIT" >&2; exit 2; }
TGZ=$1
COMMIT=$2
SUM=$(sha256sum "$TGZ" | cut -c1-64)
OUT=$(mktemp)

# What the gate says may quote the server's log, and lines of that log can
# be a visitor's text. The runner takes a line beginning "::" as a workflow
# command, so commands are off while the gate talks (a token nobody else
# knows ends the pause) -- the gate's own lines are prefixed, this is the
# second lock on the same door.
TOKEN=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')
echo "::stop-commands::$TOKEN"
ssh lava-gate "deploy $COMMIT $SUM" < "$TGZ" 2>&1 | tee "$OUT"
rc=${PIPESTATUS[0]}
echo "::$TOKEN::"

case $rc in
  0)   verdict="deployed" ;;
  1)   verdict="FAILED -- the server was rolled back to the version before" ;;
  2)   verdict="REFUSED by the gate -- nothing on the server changed" ;;
  3)   verdict="FAILED AND THE ROLLBACK FAILED -- the server needs a human now" ;;
  255) verdict="ssh failed -- see the log above; a deploy that had begun finishes on the server" ;;
  *)   verdict="exit status $rc" ;;
esac

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  if grep -q '^=== report' "$OUT"; then
    BODY=$(sed -n '/^=== report/,/^=== end/p' "$OUT")
  else
    BODY=$(tail -n 40 "$OUT")
  fi
  # A fence longer than any run of backticks in the text, so no line of it
  # (a log line is anyone's) can close the block and write Markdown.
  n=$(printf '%s\n' "$BODY" | awk '{ s = $0; while (match(s, /`+/)) {
        if (RLENGTH > m) m = RLENGTH; s = substr(s, RSTART + RLENGTH) } }
        END { print m + 0 }')
  FENCE='```'
  while [ "${#FENCE}" -le "$n" ]; do FENCE="$FENCE\`"; done
  {
    echo "### Deploy \`${COMMIT:0:12}\`: $verdict"
    echo
    echo "$FENCE"
    printf '%s\n' "$BODY"
    echo "$FENCE"
  } >> "$GITHUB_STEP_SUMMARY"
fi

if grep -q '^texts: .*CHANGED' "$OUT"; then
  echo "::notice title=String table changed::$(grep -m1 '^texts: ' "$OUT" | sed 's/^texts: *//')"
fi
if grep -q '^launcher: REBUILD DUE' "$OUT"; then
  echo "::warning title=Launcher rebuild due::$(grep -m1 '^launcher: REBUILD DUE' "$OUT" | sed 's/^launcher: //') -- rebuild it with launcher/build.ps1 and publish it, as before"
fi
if grep -qE '^errors: +[0-9]+ in the start-up logs, [1-9][0-9]* after' "$OUT"; then
  echo "::warning title=Errors after start::$(grep -m1 '^errors: ' "$OUT" | sed 's/^errors: *//' | cut -d'(' -f1)-- the deploy stands; the lines are in the summary and the gate's deploy log"
fi
if grep -q 're-run install.sh' "$OUT"; then
  echo "::warning title=Gate outdated::the repository holds a newer gate or filter than the server runs; re-run deploy/remote/install.sh there"
fi
[ "$rc" = 0 ] || echo "::error title=Deploy::$verdict"
exit "$rc"
