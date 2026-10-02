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

ssh lava-gate "deploy $COMMIT $SUM" < "$TGZ" 2>&1 | tee "$OUT"
rc=${PIPESTATUS[0]}

case $rc in
  0)   verdict="deployed" ;;
  1)   verdict="FAILED -- the server was rolled back to the version before" ;;
  2)   verdict="REFUSED by the gate -- nothing on the server changed" ;;
  3)   verdict="FAILED AND THE ROLLBACK FAILED -- the server needs a human now" ;;
  255) verdict="ssh failed -- see the log above; a deploy that had begun finishes on the server" ;;
  *)   verdict="exit status $rc" ;;
esac

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### Deploy \`${COMMIT:0:12}\`: $verdict"
    echo
    echo '```'
    if grep -q '^=== report' "$OUT"; then
      sed -n '/^=== report/,/^=== end/p' "$OUT"
    else
      tail -n 40 "$OUT"
    fi
    echo '```'
  } >> "$GITHUB_STEP_SUMMARY"
fi

if grep -q '^texts: .*CHANGED' "$OUT"; then
  echo "::notice title=String table changed::$(grep -m1 '^texts: ' "$OUT" | sed 's/^texts: *//')"
fi
if grep -q '^launcher: REBUILD DUE' "$OUT"; then
  echo "::warning title=Launcher rebuild due::$(grep -m1 '^launcher: REBUILD DUE' "$OUT" | sed 's/^launcher: //') -- rebuild it with launcher/build.ps1 and publish it, as before"
fi
if grep -q 're-run install.sh' "$OUT"; then
  echo "::warning title=Gate outdated::the repository holds a newer gate or filter than the server runs; re-run deploy/remote/install.sh there"
fi
[ "$rc" = 0 ] || echo "::error title=Deploy::$verdict"
exit "$rc"
