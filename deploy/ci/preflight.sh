#!/usr/bin/env bash
# Can this run reach the production server's gate at all? The answer is the
# job output "gate" (true/false) that every job needing the server waits on.
#
#   HAVE_KEY=true|false HAVE_HOSTS=true|false bash deploy/ci/preflight.sh
#
# The workflow passes whether the two secrets are set -- as the words "true"
# and "false", never the secrets themselves (ci.yml, job preflight):
#
#   neither          the repository has no CI key yet (the owner adds it,
#                    README «CI/CD»), or this is a pull request from a fork,
#                    which GitHub never hands a secret. Not a failure: the
#                    jobs that need the client's files from the server and
#                    the deploy are skipped, grey, and this says why -- as a
#                    notice on the run and a line in its summary;
#   the key alone    half set up: without the server's host key ssh refuses
#                    to connect, and a deploy that silently never happens is
#                    worse than a red run. Red, with what to add;
#   both             go.
set -euo pipefail

out() { echo "$1" >> "${GITHUB_OUTPUT:-/dev/stdout}"; }
summary() { echo "$*" >> "${GITHUB_STEP_SUMMARY:-/dev/stdout}"; }

case "${HAVE_KEY:-false}/${HAVE_HOSTS:-false}" in
  true/true)
    out gate=true
    echo "gate: ASSETS_SSH_KEY and DEPLOY_KNOWN_HOSTS are set; the jobs that need the server run"
    ;;
  true/*)
    echo "::error title=CI half set up::ASSETS_SSH_KEY is set but DEPLOY_KNOWN_HOSTS is not: add the server's host-key line that deploy/remote/install.sh printed (Settings -> Secrets and variables -> Actions)"
    summary "### CI half set up: ASSETS_SSH_KEY without DEPLOY_KNOWN_HOSTS -- nothing that needs the server ran, nothing was deployed"
    out gate=false
    exit 1
    ;;
  *)
    msg="ASSETS_SSH_KEY is not set for this run, so the suites (they need the client's files, fetched from the server) and the deploy are skipped. Only the syntax check ran. To turn CI on, add the secrets as README «CI/CD» says."
    echo "::notice title=CI without the server::$msg"
    summary "### Suites and deploy skipped: no ASSETS_SSH_KEY"
    summary ""
    summary "$msg A pull request from a fork never gets the secret; push the branch to this repository instead."
    out gate=false
    ;;
esac
