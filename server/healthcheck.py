#!/usr/bin/env python3
"""What docker asks the two services to prove they are still working.

    python3 healthcheck.py game   -- the game socket accepts and answers
    python3 healthcheck.py http   -- /status answers and the account store opens

The game check is the socket policy handshake (server.py:1737), which is the
only exchange the server will hold with a caller that has not logged in: it
reaches accept, the read loop and the writer, and leaves no session behind.
"""
import os
import socket
import sys
import urllib.request

POLICY_REQUEST = b"<policy-file-request/>\x00"


def game():
    port = int(os.environ.get("LAVA_PORT", "9775"))
    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
        s.sendall(POLICY_REQUEST)
        reply = s.recv(512)
    return b"cross-domain-policy" in reply


def http():
    port = int(os.environ.get("LAVA_HTTP_PORT", "8080"))
    with urllib.request.urlopen(
            "http://127.0.0.1:%d/status" % port, timeout=5) as r:
        return b'"ok": true' in r.read()


def main(argv):
    which = (argv[1] if len(argv) > 1 else "").lower()
    if which not in ("game", "http"):
        print("usage: healthcheck.py game|http", file=sys.stderr)
        return 2
    try:
        ok = game() if which == "game" else http()
    except Exception as exc:          # a healthcheck reports, it does not raise
        print("%s: %s" % (which, exc), file=sys.stderr)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
