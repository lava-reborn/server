"""The admin panel, and the queue between it and the game.

The panel runs in the HTTP process and the game in another, with only the
database between them. The point of the queue is the case this suite spends
most of its length on: a character who is online is held in memory by the
session playing it, and Character.save() writes those numbers back at
logout. A panel that wrote to the characters row directly would have every
change to an online player quietly undone the moment they left. So the game
server is what carries the action out, and the check is not "the row changed"
but "the row is still changed after the player logs out".

The other half is the door: with no token configured there is no panel at
all, and with one, nothing answers without it.
"""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
TOKEN = "test-token-42"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = free_port()
HTTP_PORT = free_port()
HTTP_NO_TOKEN_PORT = free_port()

DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts  # noqa: E402
import transport  # noqa: E402

accounts.DB_PATH = DB
_store = accounts.Store(DB)
_acc, _err = _store.register("tester", "secret")
_char_id, _slot = _store.create_character(_acc, "tester", 0, "1")
_store.close()
CRED = accounts.credential("tester", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_GX="5970", LAVA_GY="1730")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

http_env = dict(os.environ, LAVA_HTTP_PORT=str(HTTP_PORT), LAVA_DB=DB,
                LAVA_GAME_PORT=str(PORT), LAVA_ADMIN_TOKEN=TOKEN,
                LAVA_ADMIN_NAME="Тестер")
http = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE,
                        env=http_env, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True)
_hlog = []
threading.Thread(target=lambda: _hlog.extend(http.stdout), daemon=True).start()

# A second HTTP process with no token at all: the panel must not exist there.
closed_env = dict(os.environ, LAVA_HTTP_PORT=str(HTTP_NO_TOKEN_PORT),
                  LAVA_DB=DB, LAVA_GAME_PORT=str(PORT))
closed = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE,
                          env=closed_env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)
_clog = []
threading.Thread(target=lambda: _clog.extend(closed.stdout), daemon=True).start()

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


def wait_http(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/status" % port,
                                   timeout=1).read()
            return
        except Exception:
            time.sleep(0.2)
    raise SystemExit("http did not start:\n" + "".join(_hlog)[-1500:])


def get(port, path, cookie=None):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path))
    if cookie:
        req.add_header("Cookie", "lava_admin=" + cookie)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def post(port, path, fields, cookie=None):
    data = "&".join("%s=%s" % (k, v) for k, v in fields.items()).encode()
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data)
    if cookie:
        req.add_header("Cookie", "lava_admin=" + cookie)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def row(char_id):
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    try:
        return dict(db.execute("SELECT * FROM characters WHERE id = ?",
                               (char_id,)).fetchone())
    finally:
        db.close()


def wait_done(n=1, timeout=10):
    """Wait for the game server to drain the queue."""
    db = sqlite3.connect(DB)
    try:
        end = time.time() + timeout
        while time.time() < end:
            left = db.execute("SELECT COUNT(*) FROM admin_actions"
                              " WHERE done_at IS NULL").fetchone()[0]
            if left == 0:
                return True
            time.sleep(0.2)
        return False
    finally:
        db.close()


class Client:
    def __init__(self):
        end = time.time() + 10
        while True:
            if srv.poll() is not None:
                raise SystemExit("server exited:\n" + "".join(_log)[-1500:])
            try:
                self.s = socket.create_connection(("127.0.0.1", PORT), 0.5)
                break
            except OSError:
                if time.time() > end:
                    raise SystemExit("server did not start")
                time.sleep(0.1)
        self.s.settimeout(2)
        self.buf = b""
        self.eof = False

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                self.eof = True
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [f.decode(ENC) for f in out if f]

    def enter(self):
        self.send("hello;major=0;minor=2;")
        self.frames()
        self.send("login;hash=@%s@;" % CRED)
        self.frames()
        self.send("selPers;num=0;")
        self.frames()
        self.send("actPlayer;")
        self.frames(1.0)

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


try:
    wait_http(HTTP_PORT)
    wait_http(HTTP_NO_TOKEN_PORT)

    print("дверь")
    code, _ = get(HTTP_NO_TOKEN_PORT, "/admin")
    check("без ключа в настройках панели нет вовсе", code, 404)

    code, body = get(HTTP_PORT, "/admin")
    check("без куки отдаётся форма входа", "name=token" in body, True)
    check("и не сама панель", "Последние действия" in body, False)

    code, body = get(HTTP_PORT, "/admin", cookie="wrong-token")
    check("с неверной кукой тоже форма", "name=token" in body, True)

    code, body = get(HTTP_PORT, "/admin", cookie=TOKEN)
    check("с ключом открывается панель", "Последние действия" in body, True)

    print("\nперсонаж не в игре")
    before = row(_char_id)
    post(HTTP_PORT, "/admin/do",
         {"kind": "money", "char_id": str(_char_id), "afro": "500",
          "gold": "0"}, cookie=TOKEN)
    check("очередь разобрана", wait_done(), True)
    check("деньги записаны в базу",
          row(_char_id)["afro"], before["afro"] + 500)

    print("\nперсонаж в игре")
    cl = Client()
    cl.enter()
    was = row(_char_id)["afro"]
    post(HTTP_PORT, "/admin/do",
         {"kind": "money", "char_id": str(_char_id), "afro": "300",
          "gold": "0"}, cookie=TOKEN)
    check("очередь разобрана", wait_done(), True)
    frames = cl.frames(1.0)
    check("игроку пришёл кошелёк, не дожидаясь перезахода",
          any(f.startswith("userInfo_Player") for f in frames), True)
    # The point of the whole queue: the session holds this character, and its
    # save() at logout must not write the pre-change number back over it.
    cl.close()
    time.sleep(1.5)
    check("после выхода игрока деньги на месте",
          row(_char_id)["afro"], was + 300)

    print("\nтранспорт")
    cl = Client()
    cl.enter()
    post(HTTP_PORT, "/admin/do",
         {"kind": "transport", "char_id": str(_char_id), "type_id": "16",
          "days": "5"}, cookie=TOKEN)
    check("очередь разобрана", wait_done(), True)
    cl.frames(1.0)
    cl.close()
    time.sleep(1.5)
    after = row(_char_id)
    check("выдан крылатый ламантин", after["transport_type"], 16)
    check("и он действительно стократный",
          transport.speed_mod(16) > 50, True)

    print("\nвыкинуть из игры")
    cl = Client()
    cl.enter()
    post(HTTP_PORT, "/admin/do",
         {"kind": "kick", "account_id": str(_acc), "reason": "проверка",
          "seconds": "60"}, cookie=TOKEN)
    check("очередь разобрана", wait_done(), True)
    frames = cl.frames(2.0)
    kick = [f for f in frames if f.startswith("kickban")]
    check("пришёл kickban", len(kick), 1)
    if kick:
        # Session.as:199 reads exactly these three and writes
        # "Администратор <admin> ведет работу над вашим аккаунтом".
        check("с именем администратора", "admin=@Тестер@" in kick[0], True)
        check("со сроком", "seconds=60" in kick[0], True)
        check("и с причиной", "reason=@проверка@" in kick[0], True)
    check("и сокет закрыт", cl.eof or not cl.frames(1.0), True)
    cl.close()

    print("\nбан")
    post(HTTP_PORT, "/admin/do",
         {"kind": "ban", "account_id": str(_acc), "reason": "нельзя"},
         cookie=TOKEN)
    check("очередь разобрана", wait_done(), True)
    db = sqlite3.connect(DB)
    banned = db.execute("SELECT banned FROM accounts WHERE id = ?",
                        (_acc,)).fetchone()[0]
    db.close()
    check("аккаунт помечен", banned, 1)
    cl = Client()
    cl.send("hello;major=0;minor=2;")
    cl.frames()
    cl.send("login;hash=@%s@;" % CRED)
    check("забаненного не пускают",
          any("res=2" in f for f in cl.frames()), True)
    cl.close()

finally:
    for proc in (srv, http, closed):
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

if fails:
    print("\nПАДАЕТ:")
    for f in fails:
        print(" -", f)
    print("\nлог игрового сервера:\n" + "".join(_log)[-2500:])
    sys.exit(1)
print("\nadmin OK")
