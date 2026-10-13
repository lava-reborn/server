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
  - a code deploy (no --with-data) does not look at the slice;
  - the locations of ours (data/locations/static, server/world.py) are held
    the same way: our copy of an original location in the client is
    refused, and a new place (an id the original has not) is never sent,
    whatever the client holds there -- the rsync excludes it;
  - database/objects.xml too: the release ships its own, with a row for
    each item type of ours (data/own_items.json), and the launcher puts it
    into the client. Synced up, the server and CI would read our rows as
    the original's; the client holding it is refused like 262.xml.

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


def original_of(rel):
    """The original's bytes of a slice file, from LAVA_RES or the owner's
    client, held to client/base.txt; None when neither has them."""
    for res_dir in (os.environ.get("LAVA_RES") or "", "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"):
        p = os.path.join(res_dir, *rel.split("/"))
        if res_dir and os.path.isfile(p):
            with open(p, "rb") as fh:
                data = fh.read()
            if hashlib.sha256(data).hexdigest() == base_sha(rel):
                return data
    return None


OBJECTS = "database/objects.xml"
ORIGINAL_OBJECTS = original_of(OBJECTS)


def client(data, objects=ORIGINAL_OBJECTS):
    """A client's res holding 262.xml and database/objects.xml as given
    (None: without it); objects.xml the original's unless said."""
    res = tempfile.mkdtemp(dir=WORK)
    os.makedirs(os.path.join(res, "locations", "static"))
    os.makedirs(os.path.join(res, "database"))
    for rel, body in ((REL, data), (OBJECTS, objects)):
        if body is not None:
            with open(os.path.join(res, *rel.split("/")), "wb") as fh:
                fh.write(body)
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
    check("  (the original's database/objects.xml is at hand, from LAVA_RES)",
          ORIGINAL_OBJECTS is not None, True)

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

    # The release's objects.xml: the original's with a row for each item
    # type of ours, as client/build.py writes it (server/own_items.py).
    import own_items  # noqa: E402
    RELEASE_OBJECTS = own_items.release_xml(ORIGINAL_OBJECTS or b"<data></data>")
    check("  (the release's objects.xml is the original's with our rows: 60000 among them)",
          (RELEASE_OBJECTS != ORIGINAL_OBJECTS,
           b'<object type_id="60000" root_type_id= "1" name="helm_Bs_U_LVL_12_G_mod00" />'
           in RELEASE_OBJECTS), (True, True))
    code, err, calls = deploy(client(ORIGINAL, RELEASE_OBJECTS), "--data-only")
    check("the release's objects.xml in the client (the launcher's install since our own item"
          " types): refused, the path named, nothing sent",
          (code, OBJECTS in err, "not the original's" in err, REL in err, calls),
          (1, True, True, False, []))
    code, err, calls = deploy(client(ORIGINAL, RELEASE_OBJECTS), "--with-data", "--now")
    check("  ..and the same with --with-data, before the code goes up",
          (code, OBJECTS in err, calls), (1, True, []))
    code, err, calls = deploy(client(ORIGINAL, None), "--data-only")
    check("  ..and refused when the client has no objects.xml at all",
          (code, OBJECTS in err, calls), (1, True, []))

    with open(os.path.join(ROOT, "deploy", "deploy.sh"), encoding="utf-8") as fh:
        script = fh.read()
    check("a code deploy does not look at the slice: the check runs under --with-data alone",
          'if [ "$with_data" = 1 ]; then\n  [ -d "$RES_SRC" ] || { echo "no client at $RES_SRC" >&2;'
          ' exit 1; }\n  check_slice\nfi' in script, True)

    # The locations of ours (data/locations/static/<id>.xml), which the
    # release ships as locations/static/<id>.xml and the server reads from
    # the repository (server/world.py): held like client/files. A tree of
    # its own, deploy.sh copied into it, so that the repository's
    # data/locations is left as it is.
    TREE = os.path.join(WORK, "tree")
    os.makedirs(os.path.join(TREE, "deploy"))
    shutil.copy(os.path.join(ROOT, "deploy", "deploy.sh"), os.path.join(TREE, "deploy"))
    shutil.copytree(os.path.join(ROOT, "client", "files"), os.path.join(TREE, "client", "files"))
    shutil.copy(os.path.join(ROOT, "client", "base.txt"), os.path.join(TREE, "client"))
    NEW, OLD = "locations/static/1381.xml", "locations/static/102.xml"
    ODIR = os.path.join(TREE, "data", "locations", "static")
    os.makedirs(ODIR)
    PLACE = OURS.replace('title="Тотем"'.encode(), 'title="Новое место"'.encode(), 1)
    for rel in (NEW, OLD):
        with open(os.path.join(ODIR, rel.split("/")[-1]), "wb") as fh:
            fh.write(PLACE)
    check("  (the overlay's 102 is not the original's, its 1381 the original has not)",
          (hashlib.sha256(PLACE).hexdigest() != base_sha(OLD), base_sha(NEW)), (True, None))

    def deploy_tree(res, *args):
        if os.path.exists(LOG):
            os.remove(LOG)
        env = dict(os.environ, PATH=BIN + os.pathsep + os.environ.get("PATH", ""),
                   LAVA_RES_SRC=res, LAVA_DEPLOY_HOST="nobody@nowhere", LAVA_DEPLOY_DIR="/opt/lava")
        p = subprocess.run(["bash", os.path.join(TREE, "deploy", "deploy.sh")] + list(args),
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           timeout=60)
        calls = open(LOG).read().splitlines() if os.path.exists(LOG) else []
        return p.returncode, p.stderr, calls

    def installed(**files):
        """A client's res holding 262.xml as the original and the given files
        (path -> bytes), as the launcher leaves it."""
        res = client(ORIGINAL)
        for rel, data in files.items():
            with open(os.path.join(res, *rel.split("/")), "wb") as fh:
                fh.write(data)
        return res

    original_102 = original_of(OLD)
    check("  (the original's 102.xml is at hand, from LAVA_RES)", original_102 is not None, True)

    code, err, calls = deploy_tree(installed(**{NEW: PLACE, OLD: original_102}), "--data-only")
    rsyncs = [c for c in calls if c.startswith("rsync ")]
    check("a new place of ours in the client and the original's 102: the slice goes up",
          (code, [c.split()[0] for c in calls], err.strip()), (0, ["ssh", "rsync"], ""))
    check("  ..without the new place: the rsync leaves it out, first of its rules",
          [c.split(" --include ")[0].endswith("--exclude /" + NEW) for c in rsyncs], [True])
    check("  ..and leaves the original's own files in, 102 among them",
          ("--exclude /" + OLD) in rsyncs[0], False)

    code, err, calls = deploy_tree(installed(**{OLD: PLACE}), "--data-only")
    check("our copy of an original location in the client: refused, the path named, nothing sent",
          (code, OLD in err, "not the original's" in err, calls), (1, True, True, []))
    code, err, calls = deploy_tree(client(ORIGINAL), "--data-only")
    check("  ..and refused the same way when the client lacks the original's",
          (code, OLD in err, calls), (1, True, []))
finally:
    shutil.rmtree(WORK, ignore_errors=True)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    sys.exit(1)
print("deploy slice OK")
