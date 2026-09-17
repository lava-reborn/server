#!/usr/bin/env python3
"""Write the string table to a file, byte for byte as the HTTP stub serves it.

res/database/texts.xml is one of two files missing from the shipped client, and
in LOCAL mode there is no HTTP stub to stand in for it: SSEmulator builds the
string URL as localPath + "database/texts.xml" and the client reads it off the
disk. So the file has to exist on the player's own disk, and it has to be the
same document bootstrap_http answers ?all=1 with -- UTF-8 with a byte order
mark, one <s id='N'>name</s> per row, wrapped in <data>.

The invariant from PROTOCOL.md 9 is what makes this worth a check rather than a
redirect: every id the game server may put on the wire has to already be in the
file. StringCollector is a singleton, SBase stays subscribed to its "update"
event for the life of the session, and any batch fetched after login walks the
player back to the login screen. A row missing here is not a blank label, it is
a lost session.

    LAVA_RES=/path/to/res python3 tools/export_texts.py [-o dist/texts.xml]

Exits non-zero if anything in names.ALL failed to reach the file.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))

import names  # noqa: E402  (needs the path above)

# Exactly what bootstrap_http._send_xml puts on the wire for ?all=1: the byte
# order mark, the client's own single-quoted declaration, then the document.
# Both sides are checked against each other in tools/test_export_texts.py.
PROLOGUE = "﻿<?xml version='1.0'?>"


def document_bytes():
    """The whole table as the bytes the client expects to read."""
    return (PROLOGUE + "<data>" + names.document() + "</data>").encode("utf-8")


def verify(blob):
    """Ids in names.ALL that did not reach the document, and stray ones."""
    have = {int(i) for i in re.findall(rb"<s id='(\d+)'>", blob)}
    return sorted(set(names.ALL) - have), sorted(have - set(names.ALL))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "dist", "texts.xml"),
                    help="where to write (default: dist/texts.xml)")
    args = ap.parse_args(argv)

    blob = document_bytes()
    missing, stray = verify(blob)
    if missing:
        print("строк не хватает: %d, первые %s" % (len(missing), missing[:10]),
              file=sys.stderr)
        return 1
    if stray:
        print("лишние id в документе: %s" % stray[:10], file=sys.stderr)
        return 1

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(blob)
    print("%s: %d строк, %.1f МБ" % (out, len(names.ALL), len(blob) / 1048576.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
