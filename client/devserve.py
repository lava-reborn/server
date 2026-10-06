#!/usr/bin/env python3
"""A developer's own release stand: production's pipeline on one machine.

    python3 client/devserve.py --zip LAVA.zip --prefix LAVA/res/ --res /path/to/res
    python3 client/devserve.py --dir /path/to/original/res --res /path/to/res
    python3 client/devserve.py --serve-only

Everything goes under client/dev/ (not in git):

  keys/resource.pem, launcher.pem   test keys, made on the first run; the
                                    .keys beside them go into a test launcher
  served/download/client/           a ROOT as client/FORMAT.md lays it out
  out/                              what build.py wrote last

1. the original goes into the store (publish.py import-base): from the zip or
   the folder you name. If it is not byte for byte the client base.txt was
   made from, give --own-base: a base list is then made from your copy into
   client/dev/base.txt and used instead (your stand, your original);
2. build.py release runs over this checkout -- the same generators the server
   runs, so a patch to tools/widescreen.py shows up here exactly as it will
   for players;
3. publish.py publish signs it with the test resource key;
4. with --launcher-exe and --launcher-statement, a test launcher signed with
   the test launcher key is published too (build it with launcher\\build.ps1
   -Site http://127.0.0.1:PORT -ResourceKeys client\\dev\\keys\\resource.keys
   -LauncherKeys client\\dev\\keys\\launcher.keys -SignKey client\\dev\\keys\\launcher.pem);
5. the ROOT is served on http://127.0.0.1:PORT/download/client/ until Ctrl+C.

--res is the res/ the string table is generated from: the server's slice in
production, your own full copy here (both hold the same database/*.xml).
"""
import argparse
import functools
import http.server
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
DEV = os.path.join(HERE, "dev")
SERVED = os.path.join(DEV, "served")
ROOT = os.path.join(SERVED, "download", "client")
STATE = os.path.join(DEV, "state")
sys.path.insert(0, HERE)
import build  # noqa: E402
import lavasig  # noqa: E402
import publish  # noqa: E402


def step(name):
    print("==> " + name, flush=True)


def ensure_keys():
    kd = os.path.join(DEV, "keys")
    os.makedirs(kd, exist_ok=True)
    for name in ("resource", "launcher"):
        pem = os.path.join(kd, name + ".pem")
        if not os.path.exists(pem):
            lavasig.main(["genkey", pem])
            with open(os.path.join(kd, name + ".keys"), "w", encoding="ascii", newline="\n") as fh:
                fh.write(lavasig.read_private(pem).keys_line() + "\n")
    return kd


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--zip")
    src.add_argument("--dir")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--own-base", action="store_true")
    ap.add_argument("--res")
    ap.add_argument("--launcher-exe")
    ap.add_argument("--launcher-statement")
    ap.add_argument("--port", type=int, default=8098)
    ap.add_argument("--serve-only", action="store_true")
    ap.add_argument("--no-serve", action="store_true", help="build and publish, then stop")
    a = ap.parse_args()

    kd = ensure_keys()
    if not a.serve_only:
        if not (a.zip or a.dir) or not a.res:
            ap.error("--zip or --dir, and --res, unless --serve-only")
        base = os.path.join(HERE, "base.txt")
        if a.own_base:
            step("base list from your copy")
            base = os.path.join(DEV, "base.txt")
            args = ["base", "-o", base, "--exclude", "database/texts.xml"]
            args += ["--zip", a.zip, "--prefix", a.prefix] if a.zip else ["--dir", a.dir]
            build.main(args)

        step("the original into the store")
        args = ["import-base", "--state", STATE, "--root", ROOT, "--base", base]
        args += ["--zip", a.zip, "--prefix", a.prefix] if a.zip else ["--dir", a.dir]
        if publish.main(args):
            sys.exit("the original is not what %s lists: use --own-base for your own copy" % base)

        step("release")
        out = os.path.join(DEV, "out")
        if os.path.isdir(out):
            import shutil
            shutil.rmtree(out)
        build.Build(TREE, os.path.join(ROOT, "store"), a.res, out, base).run()

        step("publish")
        try:
            sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=TREE, capture_output=True,
                                 text=True).stdout.strip() or "0" * 40
        except OSError:
            sha = "0" * 40
        if publish.main(["publish", "--state", STATE, "--out", out, "--root", ROOT, "--key",
                         os.path.join(kd, "resource.pem"), "--source", sha]):
            sys.exit("publish failed")

    if a.launcher_exe:
        step("test launcher")
        rc = publish.main(["launcher", "--state", STATE, "--root", ROOT, "--key", os.path.join(kd, "resource.pem"),
                           "--launcher-keys", os.path.join(kd, "launcher.keys"),
                           "--exe", a.launcher_exe, "--statement", a.launcher_statement])
        if rc:
            sys.exit("launcher publish failed")

    publish.main(["status", "--state", STATE, "--root", ROOT])
    if a.no_serve:
        return
    step("serving http://127.0.0.1:%d/download/client/ (Ctrl+C to stop)" % a.port)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=SERVED)
    http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler).serve_forever()


if __name__ == "__main__":
    main()
