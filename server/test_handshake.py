"""End-to-end: replay exactly what lol.core.Session.as sends, against server.py."""
import socket, subprocess, sys, time, os
import threading
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
def free_port():
    """A port nobody holds right now.

    Fixed ports made the verdict depend on who else was testing: with two
    checkouts running the suites at once, the second server failed to bind
    and the test talked to the first one's, passing or failing on code it
    was not built from.
    """
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
# A throwaway database per run, with one account registered in it: the server
# now refuses any digest it does not know, so the test has to own a real one.
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")

# The start cell is a server default and has moved since; these
# assertions name the market by number, so the suite says which
# world it wants.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB, LAVA_GX="5970", LAVA_GY="1730")

srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


# The log outgrows a pipe that nobody drains: at 64 KB the write blocks and
# the server stops answering in the middle of the test, which showed up as
# frames going missing at whatever step happened to cross the threshold.
# Drain it as it comes, the way test_combat and test_quests already do.
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

def wait_port(port, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            s = socket.create_connection(("127.0.0.1", port), 0.5)
            return s
        except OSError:
            time.sleep(0.1)
    raise SystemExit("server did not start")

ok = True
try:
    s = wait_port(PORT)
    s.settimeout(5)

    def recv_frame():
        buf = b""
        while not buf.endswith(b"\x00"):
            chunk = s.recv(4096)
            if not chunk:
                raise SystemExit("connection closed")
            buf += chunk
        return buf[:-1].decode("utf-8")

    # Step 3: Session.sendHello() -> CSM_Hello
    s.sendall(b"hello;minor=2;major=0;\x00")
    r = recv_frame()
    print("  S->C", r)
    ok &= r.split(";")[0] == "hello"
    print("  %s server answered hello (clears the 20s helloTimeout)" % ("OK " if ok else "FAIL"))

    # Step 5: Session.login() -> CSM_Login(hash)
    s.sendall(("login;hash=@%s@;" % CRED).encode("utf-8")
              + b"\x00")
    r = recv_frame()
    print("  S->C", r)
    good = r.split(";")[0] == "cmdAck" and "res=0;" in r
    ok &= good
    print("  %s server answered cmdAck res=0 (client proceeds to loadDescription)"
          % ("OK " if good else "FAIL"))

    # An unimplemented command must not kill the connection
    s.sendall(b"q_list;\x00")
    time.sleep(0.3)
    s.sendall(b"logout;\x00")
    time.sleep(0.3)
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    print("\n--- server log ---")
    print(out.strip())

print("\nHANDSHAKE OK" if ok else "\nHANDSHAKE FAILED")
sys.exit(0 if ok else 1)
