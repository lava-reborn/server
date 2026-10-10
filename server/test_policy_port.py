"""The socket policy port: a Flash player that hangs up is no error.

Production, 2026-10-09 09:44, in the error log the admin panel shows:

    ERROR asyncio: Unhandled exception in client_connected_cb
    File "server.py", in handle_policy
        await reader.read(64)
    ConnectionResetError

The port (843, mapped to 8430) answers one request with the policy file and
closes. A player that resets the socket before the answer -- a page closed
or reloaded while it asked, a scanner, a dead link -- raised out of
handle_policy, and asyncio logged it at ERROR with its traceback.

Held to here, on server.handle_policy served by asyncio.start_server in
process, the way main() serves it, with asyncio's own handling of what a
client_connected_cb raises and every record at WARNING and above kept (what
errlog writes to the error log):

  * a request gets the policy, null-terminated, and the socket is closed;
  * a client that resets before sending anything, and one that sends the
    request and resets without reading the answer: nothing raised, no
    record at WARNING or above, the hang-up one INFO line at most;
  * a read that times out (TimeoutError, as a socket reports ETIMEDOUT):
    the same, and the socket closed.

Written against the code before the fix, the reset fails on asyncio's ERROR
record and the timeout on the exception raised.
"""
import asyncio
import logging
import os
import socket
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["LAVA_DB"] = os.path.join(tempfile.mkdtemp(), "policy.db")
sys.path.insert(0, HERE)
import server  # noqa: E402
from testkit import check, fails  # noqa: E402


class Records(logging.Handler):
    def __init__(self, level):
        super().__init__(level)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def reset(sock):
    """Close with an RST rather than a FIN: SO_LINGER on, zero seconds."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    sock.close()


async def main():
    loop = asyncio.get_running_loop()
    caught = []

    def handler(_loop, ctx):
        # Kept, and passed on to asyncio's own handler, which logs it at
        # ERROR -- the record production had.
        caught.append(ctx)
        _loop.default_exception_handler(ctx)

    loop.set_exception_handler(handler)
    loud = Records(logging.WARNING)
    info = Records(logging.INFO)
    root = logging.getLogger()
    lava = logging.getLogger("lava")
    root.addHandler(loud)
    lava.addHandler(info)
    level = lava.level
    lava.setLevel(logging.INFO)
    done = asyncio.Queue()

    async def served(reader, writer):
        # handle_policy as main() serves it; what it raises goes on to
        # asyncio as before -- only the end of it is told to the test.
        try:
            await server.handle_policy(reader, writer)
        finally:
            done.put_nowait(writer)

    srv = await asyncio.start_server(served, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]

    async def connect():
        sock = socket.socket()
        sock.setblocking(False)
        await loop.sock_connect(sock, ("127.0.0.1", port))
        return sock

    async def settled():
        writer = await asyncio.wait_for(done.get(), 5)
        await asyncio.sleep(0.05)        # asyncio's done-callback of the handler
        return writer

    def hung_up():
        return [r.getMessage() for r in info.records if "hung up" in r.getMessage()]

    def fresh():
        """Each case on its own: what the last one left is not its."""
        caught.clear()
        loud.records.clear()
        info.records.clear()

    try:
        # --- a request, answered ---------------------------------------------------------
        sock = await connect()
        await loop.sock_sendall(sock, b"<policy-file-request/>\x00")
        got = b""
        while True:
            chunk = await asyncio.wait_for(loop.sock_recv(sock, 4096), 5)
            if not chunk:
                break
            got += chunk
        sock.close()
        await settled()
        check("a request gets the policy, null-terminated, and the socket closed after it",
              (got == server.POLICY, got.endswith(b"\x00")), (True, True))
        check("  ..nothing raised, nothing logged at WARNING or above",
              (caught, [r.getMessage() for r in loud.records]), ([], []))

        # --- a client that resets ---------------------------------------------------------
        fresh()
        sock = await connect()
        await asyncio.sleep(0.1)         # the server is in its read
        reset(sock)
        writer = await settled()
        check("a reset before the request: nothing raised to asyncio",
              [(c.get("message"), repr(c.get("exception"))) for c in caught], [])
        check("  ..no record at WARNING or above (asyncio's ERROR was the production one)",
              [(r.levelname, r.name, r.getMessage()) for r in loud.records], [])
        check("  ..the hang-up one INFO line, and the socket closed",
              (len(hung_up()), writer.is_closing()), (1, True))

        fresh()
        sock = await connect()
        await loop.sock_sendall(sock, b"<policy-file-request/>\x00")
        reset(sock)
        writer = await settled()
        check("a reset right after the request, the answer never read: nothing raised, "
              "nothing at WARNING or above, at most one INFO line",
              (caught, loud.records, len(hung_up()) <= 1, writer.is_closing()),
              ([], [], True, True))

        # --- a read that times out --------------------------------------------------------
        class TimedOut:
            async def read(self, n):
                raise TimeoutError(110, "Connection timed out")

        class Writer:
            closed = False

            def write(self, data):
                raise AssertionError("an answer to a socket that timed out")

            async def drain(self):
                pass

            def close(self):
                self.closed = True

            def get_extra_info(self, name, default=None):
                return ("203.0.113.9", 4242) if name == "peername" else default

        fresh()
        w = Writer()
        try:
            await server.handle_policy(TimedOut(), w)
            raised = None
        except BaseException as exc:
            raised = repr(exc)
        check("a read that times out: nothing raised, the socket closed, one INFO line",
              (raised, w.closed, hung_up()),
              (None, True, ["  policy ('203.0.113.9', 4242) hung up: TimeoutError"]))
        check("  ..and nothing at WARNING or above", loud.records, [])
    finally:
        srv.close()
        await srv.wait_closed()
        root.removeHandler(loud)
        lava.removeHandler(info)
        lava.setLevel(level)


try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("the policy port scene crashed:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("policy port OK")
