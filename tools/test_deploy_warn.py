"""deploy/deploy.sh warns the players before it restarts the server.

The script talks to the production host over ssh, so here ssh is a stand-in
that runs the remote command on this machine: stopwarn.py against a real
game server and its database, and docker compose as lines in a log. What is
checked is the order of things and the waiting:

  - the image is built first, and a build that fails tells nobody anything
    and restarts nothing;
  - with nobody logged in there is no wait; with --now no countdown at all;
  - with a player in, the countdown goes out (20, 10) and "up" comes only
    once its time is up;
  - a poll that gets no answer (one ssh that failed) does not bring "up"
    forward: it still comes once the time the players were told is over;
  - called off from the panel while the script waits: exit 1, no "up";
  - Ctrl-C while it waits: the countdown is called off, no "up";
  - the game restarted by itself while the script waits (a crash, its new
    process with no countdown, no order calling it off): "up" at once;
  - --warn outside what the game takes is refused before anything is done.

    LAVA_RES=.../lava/res python3 tools/test_deploy_warn.py
"""
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SERVER = os.path.join(ROOT, "server")
sys.path.insert(0, SERVER)
import accounts  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
WORK = tempfile.mkdtemp()
DB = os.path.join(WORK, "deploy_warn.db")
accounts.DB_PATH = DB
_st = accounts.Store(DB)
_st.register("alice", "secret")
_st.close()
CRED = accounts.credential("alice", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_ADMIN_POLL="0.2", LAVA_POLICY_PORT="0")
_log = []


def start_game():
    """The game server on PORT and DB; its output into _log."""
    p = subprocess.Popen([sys.executable, "server.py"], cwd=SERVER, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    threading.Thread(target=lambda: _log.extend(p.stdout), daemon=True).start()
    return p


srv = start_game()

# The stand-ins: ssh runs the remote command here, rsync does nothing.
BIN = os.path.join(WORK, "bin")
os.makedirs(BIN)
LOG = os.path.join(WORK, "remote.log")
with open(os.path.join(BIN, "ssh"), "w") as f:
    f.write(r'''#!/bin/bash
# ssh [-o X] HOST CMD -> CMD, here
while [ $# -gt 0 ]; do case $1 in -o) shift 2 ;; -*) shift ;; *) break ;; esac; done
shift
cmd="$*"
case $cmd in
  *"docker exec lava-game python3 stopwarn.py"*)
    echo "stopwarn ${cmd#*stopwarn.py }" >> "$STUB_LOG"
    # The status polls listed in STUB_FAIL_STATUS (1,3: the first and the
    # third) fail as an ssh that could not connect does.
    if [ "${cmd#*stopwarn.py }" = status ]; then
      n=$(grep -c '^stopwarn status$' "$STUB_LOG")
      case ",$STUB_FAIL_STATUS," in
        *",$n,"*) echo "ssh: connect to host stand-in port 22: Connection timed out" >&2; exit 255 ;;
      esac
    fi
    cd "$STUB_SERVER" && exec "$STUB_PYTHON" stopwarn.py ${cmd#*stopwarn.py } ;;
  *"docker compose build"*)
    echo build >> "$STUB_LOG"
    [ -z "$STUB_FAIL_BUILD" ] ;;
  *"docker compose up"*)
    echo up >> "$STUB_LOG" ;;
  *) exit 0 ;;
esac
''')
with open(os.path.join(BIN, "rsync"), "w") as f:
    f.write("#!/bin/sh\nexit 0\n")
for name in ("ssh", "rsync"):
    os.chmod(os.path.join(BIN, name), 0o755)

DEPLOY = os.path.join(ROOT, "deploy", "deploy.sh")


def deploy(*args, fail_build=False, fail_status="", during=None):
    """deploy.sh with the stand-ins: (exit status, its output, the remote
    log as a list, seconds it took). during(proc, out) runs while it does."""
    open(LOG, "w").close()
    denv = dict(env, PATH=BIN + os.pathsep + os.environ["PATH"], STUB_LOG=LOG,
                STUB_SERVER=SERVER, STUB_PYTHON=sys.executable,
                STUB_FAIL_BUILD="1" if fail_build else "", STUB_FAIL_STATUS=fail_status,
                LAVA_DEPLOY_HOST="stand-in", LAVA_DEPLOY_DIR=os.path.join(WORK, "opt"))
    denv.pop("LAVA_STOP_WARN_SEC", None)
    out_path = os.path.join(WORK, "deploy.out")
    t0 = time.time()
    # Through a Python that gives SIGINT back its default first: a suite run
    # in the background of a script inherits it ignored, and a shell that
    # starts with a signal ignored cannot trap it -- Ctrl-C below would test
    # nothing.
    launch = [sys.executable, "-c",
              "import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL);"
              " os.execvp('bash', ['bash'] + sys.argv[1:])", DEPLOY]
    with open(out_path, "w") as out:
        p = subprocess.Popen(launch + list(args), env=denv, stdout=out,
                             stderr=subprocess.STDOUT, start_new_session=True)
        if during:
            during(p, out_path)
        p.wait(timeout=200)
    took = time.time() - t0
    with open(LOG) as f:
        remote = [l.strip() for l in f if l.strip()]
    with open(out_path) as f:
        text = f.read()
    return p.returncode, text, remote, took


def wait_for(path, text, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        with open(path) as f:
            if text in f.read():
                return True
        time.sleep(0.2)
    return False


class Player:
    def __init__(self):
        self.s = testkit.connect(PORT, srv, _log)
        self.s.settimeout(None)
        self.got = []
        self.eof = False
        threading.Thread(target=self._read, daemon=True).start()
        self.s.sendall(b"hello;minor=2;major=0;\x00" + ("login;hash=@%s@;\x00" % CRED).encode())
        end = time.time() + 10
        while time.time() < end and not any(f.startswith("accountInfo;") for f in self.got):
            time.sleep(0.05)

    def _read(self):
        buf = b""
        while True:
            try:
                chunk = self.s.recv(65536)
            except OSError:
                self.eof = True
                return
            if not chunk:
                self.eof = True
                return
            buf += chunk
            *done, buf = buf.split(b"\x00")
            self.got += [f.decode("utf-8") for f in done if f]

    def stops(self):
        return [f for f in self.got if f.startswith("shutdown;")]

    def wait_eof(self, timeout=10):
        end = time.time() + timeout
        while time.time() < end and not self.eof:
            time.sleep(0.1)
        return self.eof

    def close(self):
        self.s.close()


def status():
    p = subprocess.run([sys.executable, "stopwarn.py", "status"], cwd=SERVER, env=env,
                       capture_output=True, text=True, timeout=30)
    return p.stdout.strip()


player = None
try:
    # The game up, and writing its stop row.
    testkit.connect(PORT, srv, _log).close()
    end = time.time() + testkit.START_WAIT
    while time.time() < end and status() != "- 0":
        time.sleep(0.3)
    check("the game answers: nobody in", status(), "- 0")

    # --- the arguments ------------------------------------------------------------
    for bad in ("--warn=5", "--warn=601", "--warn=soon"):
        rc, out, remote, _t = deploy(bad)
        check("%s refused before anything is done" % bad, (rc, remote), (2, []))

    # --- nobody logged in: no wait ---------------------------------------------------
    rc, out, remote, took = deploy("--warn=20")
    check("nobody in: build, ask, up -- no wait",
          (rc, remote, took < 15), (0, ["build", "stopwarn start 20 --by deploy.sh --skip-empty", "up"], True))
    check("and says so", "nobody online, no wait" in out, True)

    # --- a build that fails ------------------------------------------------------------
    player = Player()
    rc, out, remote, took = deploy("--warn=20", fail_build=True)
    check("the build fails: the script stops there", (rc != 0, remote), (True, ["build"]))
    check("the player was told nothing", player.stops(), [])

    # --- --now -------------------------------------------------------------------------
    rc, out, remote, took = deploy("--now")
    check("--now: build and up, no countdown", (rc, remote), (0, ["build", "up"]))
    check("the player was told nothing", player.stops(), [])

    # --- a player in: the countdown, then up --------------------------------------------
    rc, out, remote, took = deploy("--warn=20")
    check("a player in: build, then the countdown, then up",
          (rc, remote[:2], remote[-1]), (0, ["build", "stopwarn start 20 --by deploy.sh --skip-empty"], "up"))
    check("it asked how things stand while it waited",
          remote[2:-1] and all(r == "stopwarn status" for r in remote[2:-1]), True)
    check("up came once the 20 seconds were over", took >= 20, True)
    check("the player was told 20, then 10", player.stops(), ["shutdown;seconds=20;", "shutdown;seconds=10;"])
    check("the script said it waited", ("1 player(s) told: the restart in 2" in out,
                                        "0s to the restart, 1 online" in out), (True, True))
    # The stand-in restarts nothing; the game's countdown is over and stays so.
    subprocess.run([sys.executable, "stopwarn.py", "cancel", "--by", "test"], cwd=SERVER,
                   env=env, capture_output=True, timeout=30)
    check("cleared for the next one", status(), "- 1")

    # --- a poll that gets no answer -----------------------------------------------------
    n = len(player.stops())
    rc, out, remote, took = deploy("--warn=20", fail_status="1")
    check("the first poll's ssh failed: the wait goes on, up once the 20 seconds are over",
          (rc, remote[-1], took >= 20), (0, "up", True))
    check("and says so", "the countdown does not answer; waiting out the" in out, True)
    check("the player was told 20, then 10", player.stops()[n:],
          ["shutdown;seconds=20;", "shutdown;seconds=10;"])
    subprocess.run([sys.executable, "stopwarn.py", "cancel", "--by", "test"], cwd=SERVER,
                   env=env, capture_output=True, timeout=30)
    check("cleared again", status(), "- 1")

    # --- called off from the panel while it waits ---------------------------------------
    def call_off(p, out_path):
        wait_for(out_path, "player(s) told")
        time.sleep(1)
        subprocess.run([sys.executable, "stopwarn.py", "cancel", "--by", "panel"], cwd=SERVER,
                       env=env, capture_output=True, timeout=30)

    n = len(player.stops())
    rc, out, remote, took = deploy("--warn=20", during=call_off)
    check("called off from the panel: exit 1, no up", (rc, "up" in remote), (1, False))
    check("and says nothing was restarted", "the countdown was called off" in out, True)
    check("it asked the game whether an order called it off",
          any(r.startswith("stopwarn cancelled ") for r in remote), True)
    check("the player was told 20 only", player.stops()[n:], ["shutdown;seconds=20;"])

    # --- Ctrl-C while it waits -----------------------------------------------------------
    def ctrl_c(p, out_path):
        wait_for(out_path, "player(s) told")
        time.sleep(1)
        os.killpg(p.pid, signal.SIGINT)

    n = len(player.stops())
    rc, out, remote, took = deploy("--warn=20", during=ctrl_c)
    check("Ctrl-C: exit 130, no up", (rc, "up" in remote), (130, False))
    check("the countdown called off on the way out",
          (remote[-1], "the countdown is called off" in out), ("stopwarn cancel --by deploy.sh", True))
    check("no countdown left", status(), "- 1")
    time.sleep(1)
    check("the player was told 20 only", player.stops()[n:], ["shutdown;seconds=20;"])

    # --- the game restarted by itself while it waits -------------------------------------
    # Past the window the next one asks about (`cancelled`), so the cancel
    # just above is not taken for one of its own.
    time.sleep(3)

    def crash(p, out_path):
        global srv
        wait_for(out_path, "player(s) told")
        time.sleep(1)
        # Killed outright -- no shutdown(), no cancel -- and a new process on
        # the same database, as docker's restart policy brings one back.
        srv.kill()
        srv.wait(timeout=10)
        srv = start_game()

    n = len(player.stops())
    rc, out, remote, took = deploy("--warn=120", during=crash)
    check("restarted by itself: no order called it off, so up at once",
          (rc, remote[-1], took < 110), (0, "up", True))
    check("and says so", "the game restarted by itself" in out, True)
    check("not taken for a cancel", "called off" in out, False)
    check("it asked the game whether an order called it off",
          any(r.startswith("stopwarn cancelled ") for r in remote), True)
    check("the player was told 120, then the crash cut him off",
          (player.stops()[n:], player.wait_eof()), (["shutdown;seconds=120;"], True))
finally:
    if player is not None:
        player.close()
    if srv.poll() is None:
        srv.terminate()
        srv.wait(timeout=10)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("the game logged a traceback:\n" + out[-1500:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("deploy warn OK")
