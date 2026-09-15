"""End-to-end: replay exactly what lol.core.Session.as sends, against server.py."""
import socket, subprocess, sys, time, os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 19775
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

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB)

srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

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
    out = srv.communicate(timeout=5)[0]
    print("\n--- server log ---")
    print(out.strip())

print("\nHANDSHAKE OK" if ok else "\nHANDSHAKE FAILED")
sys.exit(0 if ok else 1)
