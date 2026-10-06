"""Online counter: entered characters across rooms, logout and reconnect.

The patched XMLConnection opts in through hello;online=1 and consumes a
standalone online;count=N push, without registering a cmdAck handler.
hello;online=2 asks for the names too, for the list under the counter:
the same frame with names=|@...@|. Unpatched clients count too, but keep
their original frame sequence.
"""
import asyncio
import logging
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "online.db")
os.environ["LAVA_DB"] = DB
os.environ["LAVA_POLICY_PORT"] = "0"
sys.path.insert(0, HERE)
import accounts  # noqa: E402
from protocol import decode  # noqa: E402
from testkit import check, connect, fails  # noqa: E402
import server  # noqa: E402

for login in ("alice", "bob", "legacy", "carol"):
    server.STORE.register(login, "secret")


def command(login):
    return "login;hash=@%s@;" % accounts.credential(login, "secret")


def counts(frames):
    return [p["count"] for n, p in frames if n == "online"]


def names(frames):
    return [p.get("names") for n, p in frames if n == "online"]


class Writer:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        pass

    def get_extra_info(self, name, default=None):
        return default


def run(sess, text):
    sess.handle(*decode(text))


# --- lifecycle, in process -------------------------------------------------
async def lifecycle():
    alice = server.Session(Writer(), "alice")
    run(alice, "hello;minor=2;major=0;online=1;")
    run(alice, command("alice"))
    run(alice, "newPers;res=1;sex=0;name=@Alice@;")
    check("creation and authentication alone do not count as playing",
          (len(server.ONLINE.by_char), counts(alice.writer.frames)), (0, []))
    alice.writer.frames.clear()
    run(alice, "actPlayer;")
    check("activation sends one ack, one count and the location",
          [n for n, _ in alice.writer.frames], ["cmdAck", "online", "lcall"])
    check("the first player includes herself", counts(alice.writer.frames), [1])
    alice.writer.frames.clear()
    alice.enter_location()
    check("re-entering a location cannot add another player or another push",
          (len(server.ONLINE.by_char), counts(alice.writer.frames)), (1, []))
    alice.close()
    alice.close()
    check("repeated cleanup leaves no ghost", len(server.ONLINE.by_char), 0)


logging.getLogger("lava").disabled = True
try:
    asyncio.run(lifecycle())
except Exception:
    import traceback
    fails.append("in-process crash:\n" + traceback.format_exc())
finally:
    server.STORE.close()


# --- real sockets ---------------------------------------------------------
with socket.socket() as port_socket:
    port_socket.bind(("127.0.0.1", 0))
    PORT = port_socket.getsockname()[1]
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, encoding="utf-8")
log = []
drain = threading.Thread(target=lambda: log.extend(srv.stdout), daemon=True)
drain.start()
clients = []


class Client:
    def __init__(self, login, feature=True, level=1):
        self.sock = connect(PORT, srv, log)
        clients.append(self)
        self.buf = b""
        self.send("hello;minor=2;major=0;" + ("online=%d;" % level if feature else ""))
        self.send(command(login))
        self.frames()

    def send(self, text):
        self.sock.sendall(text.encode("utf-8") + b"\0")

    def frames(self, seconds=0.25):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.sock.settimeout(max(0.001, end - time.monotonic()))
            try:
                data = self.sock.recv(65536)
            except socket.timeout:
                break
            if not data:
                break
            self.buf += data
        parts = self.buf.split(b"\0")
        self.buf = parts.pop()
        return [decode(p.decode("utf-8")) for p in parts if p]

    def enter(self, name=None):
        if name:
            self.send("newPers;res=1;sex=0;name=@%s@;" % name)
            self.frames()
            self.send("actPlayer;")
        else:
            self.send("selPers;num=0;")
        result = self.frames()
        self.send("lenter;accept=1;")
        self.frames()
        return result


try:
    alice = Client("alice")
    check("first socket gets the current count on entering", counts(alice.enter()), [1])
    bob = Client("bob")
    check("an account on the character screen does not raise the count", counts(alice.frames()), [])
    check("a second entrant sees both players", counts(bob.enter("Bob")), [2])
    check("the first player hears about the newcomer", counts(alice.frames()), [2])

    alice.send("chWorld;to=0;")
    changed = alice.frames()
    check("the test player really enters the global map",
          "gmap" in [n for n, _ in changed], True)
    check("map travel leaves the online count alone", (counts(changed), counts(bob.frames())), ([], []))

    legacy = Client("legacy", feature=False)
    check("an old client's activation sequence stays unchanged",
          [n for n, _ in legacy.enter("Legacy")], ["cmdAck", "lcall"])
    check("old clients count even when they have no counter",
          (counts(alice.frames()), counts(bob.frames())), ([3], [3]))

    bob.sock.close()
    check("a lost socket updates a player on the map", counts(alice.frames()), [2])
    check("legacy clients receive no counter frames", counts(legacy.frames()), [])
    bob2 = Client("bob")
    check("reconnecting starts with a fresh count", counts(bob2.enter()), [3])
    alice.frames()
    bob3 = Client("bob")
    check("the same character on another socket is counted once", counts(bob3.enter()), [3])
    replaced = counts(alice.frames())
    check("replacing the socket ends at three, never four",
          (bool(replaced), replaced[-1:] == [3], max(replaced, default=0) <= 3),
          (True, True, True))
    check("the replaced connection was closed", bob2.sock.recv(1), b"")
    bob3.send("logout;")
    check("logout updates the remaining player", counts(alice.frames()), [2])

    # --- the names behind the count, for hello;online=2 -------------------
    carol = Client("carol", level=2)
    entered = carol.enter("carol")
    check("names change no ack: activation is still ack, count, location",
          [n for n, _ in entered], ["cmdAck", "online", "lcall"])
    check("a names client gets the count with every name, case aside",
          (counts(entered), names(entered)), ([3], [["Alice", "carol", "Legacy"]]))
    check("an online=1 client keeps the frame without names",
          names(alice.frames()), [None])
    legacy.sock.close()
    left = carol.frames()
    check("a player leaving updates the names", (counts(left), names(left)),
          ([2], [["Alice", "carol"]]))
except Exception:
    import traceback
    fails.append("socket crash:\n" + traceback.format_exc())
finally:
    for c in clients:
        c.sock.close()
    srv.terminate()
    srv.wait(timeout=8)
    drain.join(timeout=2)
    if any("Traceback" in line for line in log):
        fails.append("server traceback:\n" + "".join(log[-60:]))
    elif fails:
        print("".join(log[-30:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("online OK")
