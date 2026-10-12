"""deploy/deploy.sh sends up the original's slice of the client, never ours.

The server reads a slice of the client (locations/{static,deadloc,desert},
database/mobs.xml and objects.xml, avatars/list.xml), which --with-data and
--data-only rsync into /opt/lava/res from the owner's installed client. The
launcher puts the release's own files (client/files) into that client, and
one of them falls inside the slice since 2026-10-12: locations/static/262.xml,
the Тотем of Абри titled «Тотем» for the client's window. Synced up, it would
change what the server reads and what CI tests against. So deploy.sh holds
every slice path client/files has to the original's bytes (client/base.txt)
and refuses, before it touches the host, when the client holds ours.

Here ssh and rsync are stand-ins that only write down their arguments:

  - the original's file in the client: the slice goes up, as before;
  - the release's copy in the client: exit 1, the path named, no ssh and no
    rsync at all;
  - the file missing from the client: refused the same way;
  - a code deploy (no --with-data) does not look at the slice.

    python3 tools/test_deploy_slice.py
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
from testkit import check, fails  # noqa: E402

REL = "locations/static/262.xml"
WORK = tempfile.mkdtemp(prefix="deploy-slice-")
BIN = os.path.join(WORK, "bin")
LOG = os.path.join(WORK, "calls.log")
os.makedirs(BIN)
for tool in ("ssh", "rsync"):
    path = os.path.join(BIN, tool)
    with open(path, "w") as fh:
        fh.write('#!/bin/bash\necho "%s $*" >> "%s"\nexit 0\n' % (tool, LOG))
    os.chmod(path, 0o755)


def base_sha(rel):
    with open(os.path.join(ROOT, "client", "base.txt"), encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 3 and parts[2] == rel:
                return parts[0]
    return None


with open(os.path.join(ROOT, "client", "files", *REL.split("/")), "rb") as fh:
    OURS = fh.read()
ORIGINAL = OURS.replace('title="Тотем"'.encode(), 'title="Пустошь"'.encode(), 1)


def client(data):
    """A client's res holding 262.xml as given (None: without it)."""
    res = tempfile.mkdtemp(dir=WORK)
    os.makedirs(os.path.join(res, "locations", "static"))
    if data is not None:
        with open(os.path.join(res, *REL.split("/")), "wb") as fh:
            fh.write(data)
    return res


def deploy(res, *args):
    """(exit code, stderr, the stand-ins' calls)."""
    if os.path.exists(LOG):
        os.remove(LOG)
    env = dict(os.environ, PATH=BIN + os.pathsep + os.environ.get("PATH", ""),
               LAVA_RES_SRC=res, LAVA_DEPLOY_HOST="nobody@nowhere", LAVA_DEPLOY_DIR="/opt/lava")
    p = subprocess.run(["bash", os.path.join(ROOT, "deploy", "deploy.sh")] + list(args),
                       env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                       timeout=60)
    calls = open(LOG).read().splitlines() if os.path.exists(LOG) else []
    return p.returncode, p.stderr, calls


try:
    check("the copy here is the original's but for its title (client/base.txt)",
          hashlib.sha256(ORIGINAL).hexdigest() == base_sha(REL) != hashlib.sha256(OURS).hexdigest(),
          True)

    code, err, calls = deploy(client(ORIGINAL), "--data-only")
    check("the original's file in the client: the slice goes up, nothing refused",
          (code, [c.split()[0] for c in calls], err.strip()), (0, ["ssh", "rsync"], ""))
    check("  ..by the one whitelist rsync, from the client's res into /opt/lava/res",
          any("--include locations/static/*.xml" in c and c.endswith(":/opt/lava/res/")
              for c in calls), True)

    code, err, calls = deploy(client(OURS), "--data-only")
    check("the release's copy in the client (the launcher's install): refused, the path named,"
          " nothing sent, not even the ssh that makes the folders",
          (code, REL in err, "not the original's" in err, calls), (1, True, True, []))
    code, err, calls = deploy(client(OURS), "--with-data", "--now")
    check("  ..and the same with --with-data, before the code goes up",
          (code, REL in err, calls), (1, True, []))

    code, err, calls = deploy(client(None), "--data-only")
    check("the file missing from the client: refused the same way",
          (code, REL in err, calls), (1, True, []))

    with open(os.path.join(ROOT, "deploy", "deploy.sh"), encoding="utf-8") as fh:
        script = fh.read()
    check("a code deploy does not look at the slice: the check runs under --with-data alone",
          'if [ "$with_data" = 1 ]; then\n  [ -d "$RES_SRC" ] || { echo "no client at $RES_SRC" >&2;'
          ' exit 1; }\n  check_slice\nfi' in script, True)
finally:
    shutil.rmtree(WORK, ignore_errors=True)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    sys.exit(1)
print("deploy slice OK")
