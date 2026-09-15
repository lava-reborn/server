"""Replay the client's real path from login to standing in a location.

The sequence and the frame shapes come from lol/core/Session.as,
lol/core/player/PersGenerator.as and lol/core/Master.as.
"""
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 19776
ENC = "cp1251"

# This test walks the character-creation path, so it needs the empty
# roster; the server otherwise ships a ready character and auto-enters.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_NEWCHAR="1")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


def connect(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return socket.create_connection(("127.0.0.1", PORT), 0.5)
        except OSError:
            time.sleep(0.1)
    raise SystemExit("server did not start")


class Client:
    def __init__(self, sock):
        self.s = sock
        self.s.settimeout(2)
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.5):
        """Collect whatever arrives within the window, as decoded strings."""
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [f.decode(ENC) for f in out if f]

    def names(self, wait=0.5):
        return [f.split(";")[0] for f in self.frames(wait)]


try:
    c = Client(connect())

    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@abc@;")
    check("login sequence", c.names(),
          ["hello", "cmdAck", "constants", "accountInfo"])

    # A character is created, then the client plays its intro and sends
    # actPlayer of its own accord.
    c.send("newPers;res=1;sex=0;name=@polestvr@;")
    check("newPers acked", c.names(), ["cmdAck"])

    c.send("actPlayer;")
    check("actPlayer opens a location", c.names(), ["cmdAck", "lcall"])

    # ie=0 in lcall means the client confirms once its assets have loaded.
    c.send("lenter;accept=1;")
    got = c.frames()
    check("lenter acked then positioned", [f.split(";")[0] for f in got],
          ["cmdAck", "lenter"])
    check("spawn cell sent", "pos=490;" in got[1], True)

    # userInfo_Player carries a parameter literally called "name"; an earlier
    # version of send() collided with it and dropped the connection.
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.frames()
    check("getInfo answered", [f.split(";")[0] for f in got],
          ["userInfo_Player", "usrUp"])
    check("name survives the collision", "name=@polestvr@;" in got[0], True)

    c.send("rp_get_info;")
    got = c.frames()
    check("rp_info answered", got[0].split(";")[0], "rp_info")
    check("attribute mask is dense", "a_attribs_mask=31;" in got[0], True)
    check("15 specialisation slots", "a_specs_mask=32767;" in got[0], True)

    # These two are pipelined by the client and wedge it if left unanswered,
    # so an empty reply still has to arrive.
    c.send("ss_get;target=0;slot=11;")
    c.send("q_list;")
    check("empty inventory and quest log", c.names(), ["ss_ack", "q_list"])

    # Nothing moves until the server echoes the path back.
    c.send("moveTo;path=|490|491|492|;")
    got = c.frames()
    check("movement echoed", got[0], "userMove;id=0;path=|490|491|492|;")

    # An unknown command must be logged, not fatal.
    c.send("no_such_command;x=1;")
    c.send("q_list;")
    check("unknown command is survivable", c.names(), ["q_list"])

    c.send("logout;")
finally:
    srv.terminate()
    out = srv.communicate(timeout=5)[0]
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-1500:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("world entry OK")
