"""The server's own lines of chat, and the switch that keeps them out.

The owner took the lines the server says by itself -- signed «Сервер», with
from=0: a refusal's reason, what fell on death, how a barter ended -- out of
the game's chat (Session.say). LAVA_SERVER_CHAT=1 brings them back, and the
suites that read those lines as the server's reasons ask for it by name.
What a player typed himself is still answered (Session.answer): /where is a
question, and its answer is not a service line.

So the same scene is played twice, on two servers: once with the variable
unset, as a served server has it, and once with it set. The scene is a
refusal whose only words are a line of chat -- chWorld;to=1 where no exit
is -- and a typed /where after it.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
sys.path.insert(0, HERE)
import accounts
import travel
import world

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Client:
    def __init__(self, sock):
        self.s = sock
        self.s.settimeout(2)
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.5):
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


def names(frames):
    return [f.split(";")[0] for f in frames]


def param(frame_text, key):
    return frame_text.split(";%s=" % key)[1].split(";")[0]


def scene(chat):
    """One server, one character in the black market: a refused exit, then
    /where. chat is the value of LAVA_SERVER_CHAT, None for unset."""
    tag = "LAVA_SERVER_CHAT=%s" % chat if chat is not None else "unset"
    port = free_port()
    db = os.path.join(tempfile.mkdtemp(), "test.db")
    store = accounts.Store(db)
    store.register("tester", "secret")
    store.close()
    cred = accounts.credential("tester", "secret")
    # The market by number, as the other suites name it; no cheats, since
    # nothing here needs a scene set.
    env = dict(os.environ, LAVA_PORT=str(port), LAVA_HOST="127.0.0.1",
               LAVA_DB=db, LAVA_GX="5970", LAVA_GY="1730", LAVA_POLICY_PORT="0")
    # Unset means unset: a shell that exported the variable must not decide
    # what "by default" is here.
    env.pop("LAVA_SERVER_CHAT", None)
    env.pop("LAVA_CHEATS", None)
    if chat is not None:
        env["LAVA_SERVER_CHAT"] = chat
    log_path = os.path.join(os.path.dirname(db), "server.log")
    srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                           stdout=open(log_path, "w"), stderr=subprocess.STDOUT,
                           text=True)
    try:
        end = time.time() + 10
        while True:
            try:
                sock = socket.create_connection(("127.0.0.1", port), 0.5)
                break
            except OSError:
                if time.time() > end:
                    raise SystemExit("server did not start")
                time.sleep(0.1)
        c = Client(sock)
        c.send("hello;minor=2;major=0;")
        c.send("login;hash=@%s@;" % cred)
        c.frames()
        c.send("newPers;res=1;sex=0;name=@wanderer@;")
        c.frames()
        c.send("actPlayer;")
        got = c.frames()
        check("%s: called into the market" % tag,
              any(f.startswith("lcall;") and ";id=102;" in f for f in got), True)
        c.send("lenter;accept=1;")
        got = c.frames(wait=2)
        check("%s: positioned" % tag, names(got)[:1], ["lenter"])
        pos = int(param(got[0], "pos"))
        check("%s: the entry cell is no exit" % tag,
              travel.side_at(world.location(102), pos), None)

        # Refused: nothing moves, one acknowledgement -- and its reason is
        # chat, the one thing the switch decides.
        c.send("chWorld;to=1;")
        got = c.frames(wait=1.0)
        check("%s: to=1 off any exit is refused" % tag,
              names(got)[:1] == ["cmdAck"] and got[0] != "cmdAck;res=0;", True)
        server_lines = [f for f in got if f.startswith("userMsg;")]
        if chat == "1":
            check("%s: the reason comes back into the chat" % tag,
                  len(server_lines) == 1 and "nick=@Сервер@;" in server_lines[0]
                  and "from=0" in server_lines[0], True)
        else:
            check("%s: and no line of the server's follows it" % tag,
                  server_lines, [])
        # One acknowledgement and no more: the queue is still in step.
        c.send("chkml;mode=0;")
        check("%s: the queue is still in step" % tag,
              names(c.frames()), ["cmdAck", "lsml"])

        # Typed, so answered, switch or no switch.
        c.send("userMsg;entry=@/where@;group=0;")
        got = c.frames()
        check("%s: /where is answered" % tag, names(got), ["cmdAck", "userMsg"])
        check("%s: by the server, in the channel it was asked in" % tag,
              len(got) == 2 and "nick=@Сервер@;" in got[1]
              and "group=0;" in got[1] and "static/102.xml" in got[1], True)
        c.send("logout;")
        c.frames(0.3)
    except Exception:
        import traceback
        fails.append("%s: the test itself broke:\n%s" % (tag, traceback.format_exc()))
    finally:
        srv.terminate()
        srv.wait(timeout=5)
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        out = fh.read()
    if "Traceback" in out:
        fails.append("%s: server logged a traceback:\n%s" % (tag, out[-2500:]))
    return out


# As a served server has it: the variable is not set anywhere.
log_off = scene(None)
# What was not said is still in the log, with whom it was for, for whoever
# is looking into it.
check("unset: the unsaid reason is in the server's log",
      "not said to wanderer: Здесь нет выхода" in log_off, True)
# Set to 1: the lines are back, as the suites that read them expect.
log_on = scene("1")
check("LAVA_SERVER_CHAT=1: and nothing is held back",
      "not said to" in log_on, False)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("server chat OK")
