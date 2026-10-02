"""The admin panel, and the queue between it and the game.

The panel runs in the HTTP process and the game in another, with only the
database between them. The point of the queue is the case this suite spends
most of its length on: a character who is online is held in memory by the
session playing it, and Character.save() writes those numbers back at
logout. A panel that wrote to the characters row directly would have every
change to an online player quietly undone the moment they left. So the game
server is what carries the action out, and the check is not "the row changed"
but "the row is still changed after the player logs out".

The other half is the door. It is the game's own account: the same login and
password, checked against the same digest the client sends, so the panel
keeps no passwords of its own. Which logins may open it is configuration --
with none set there is no panel at all.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
ADMIN_LOGIN = "tester"
ADMIN_PASSWORD = "secret"
# hermit_mask_pm, «Маска отшельника (P)»: tradable but for its (P), and the
# answer the game server writes for it (server.PREMIUM_REFUSED).
MASK_P = 6511
REFUSED_P = "предмет %d — (P), выведен из игры, не выдаётся" % MASK_P
# The premium vehicles, «Газ 67 Б (P)» and «Летающая тарелка»
# (transport.premium), and the answer for them (server.PREMIUM_TRANSPORT_REFUSED).
GAZ_P, SAUCER_P = 8, 12
REFUSED_TR = "транспорт %d — (P), выведен из игры, не выдаётся"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = free_port()
HTTP_PORT = free_port()
HTTP_CLOSED_PORT = free_port()

DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts  # noqa: E402
import inventory  # noqa: E402
import storage  # noqa: E402
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
                LAVA_GAME_PORT=str(PORT), LAVA_ADMINS=ADMIN_LOGIN)
http = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE,
                        env=http_env, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True)
_hlog = []
threading.Thread(target=lambda: _hlog.extend(http.stdout), daemon=True).start()

# A second HTTP process with no token at all: the panel must not exist there.
closed_env = dict(os.environ, LAVA_HTTP_PORT=str(HTTP_CLOSED_PORT),
                  LAVA_DB=DB, LAVA_GAME_PORT=str(PORT))
closed = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE,
                          env=closed_env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)
_clog = []
threading.Thread(target=lambda: _clog.extend(closed.stdout), daemon=True).start()

from testkit import check, fails  # noqa: E402


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


def sign_in(login=None, password=None):
    """Sign in the way a browser does and keep the cookie it is given."""
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", HTTP_PORT, timeout=5)
    body = urllib.parse.urlencode(
        {"login": login or ADMIN_LOGIN,
         "password": ADMIN_PASSWORD if password is None else password})
    conn.request("POST", "/admin/login", body,
                 {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    raw = resp.getheader("Set-Cookie") or ""
    conn.close()
    return raw.split(";")[0].split("=", 1)[1] if "=" in raw else ""


def row(char_id):
    # storage, not sqlite3: under LAVA_DB_URL the same suite runs on Postgres.
    db = storage.connect(DB)
    try:
        return dict(db.execute("SELECT * FROM characters WHERE id = ?",
                               (char_id,)).fetchone())
    finally:
        db.close()


def wait_done(n=1, timeout=10):
    """Wait for the game server to drain the queue."""
    db = storage.connect(DB)
    try:
        end = time.time() + timeout
        while time.time() < end:
            left = db.execute("SELECT COUNT(*) c FROM admin_actions"
                              " WHERE done_at IS NULL").fetchone()["c"]
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
    wait_http(HTTP_CLOSED_PORT)

    print("дверь")
    code, _ = get(HTTP_CLOSED_PORT, "/admin")
    check("без списка админов панели нет вовсе", code, 404)

    code, body = get(HTTP_PORT, "/admin")
    check("без входа отдаётся форма", "name=password" in body, True)
    check("и не сама панель", "Сейчас в игре" in body, False)

    code, body = get(HTTP_PORT, "/admin", cookie="forged%7C99999999999%7Cdeadbeef")
    check("подделанная кука не пускает", "name=password" in body, True)

    code, body = post(HTTP_PORT, "/admin/login",
                      {"login": ADMIN_LOGIN, "password": "wrong"})
    check("неверный пароль не пускает", "name=password" in body, True)

    code, body = post(HTTP_PORT, "/admin/login",
                      {"login": "stranger", "password": ADMIN_PASSWORD})
    check("посторонний логин не пускает", "name=password" in body, True)

    COOKIE = sign_in()
    code, body = get(HTTP_PORT, "/admin", cookie=COOKIE)
    check("свой логин с паролем открывает панель",
          "Сейчас в игре" in body, True)
    check("и панель подписана именем администратора",
          ADMIN_LOGIN in body, True)

    print("\nпоиск по нику")
    code, body = get(HTTP_PORT, "/admin", cookie=COOKIE)
    check("без запроса карточек нет", "Начислить" in body, False)
    code, body = get(HTTP_PORT, "/admin?q=tes", cookie=COOKIE)
    check("часть ника находит персонажа", "Начислить" in body, True)
    check("в списке транспорта нет (P): ни Газа 67 Б (P), ни тарелки; ламантин есть",
          ['<option value="%d">' % t in body for t in (GAZ_P, SAUCER_P, 16)],
          [False, False, True])
    check("  ..и сам транспорт помечен премиальным только у этих двух",
          sorted(t for t in transport.TABLE if transport.premium(t)), [GAZ_P, SAUCER_P])
    code, body = get(HTTP_PORT, "/admin?q=TES", cookie=COOKIE)
    check("регистр не важен", "Начислить" in body, True)
    code, body = get(HTTP_PORT, "/admin?q=" + urllib.parse.quote("такогонет"),
                     cookie=COOKIE)
    check("чужой запрос ничего не находит", "Начислить" in body, False)
    check("и об этом сказано", "никого" in body, True)

    print("\nкто в игре")

    def panel_until(pred, timeout=10):
        """The panel once `pred` holds of it, or as it was at the deadline.

        The list travels game server -> database -> panel, once a second
        and in two processes, so one fixed sleep either waits for nothing
        or, on a loaded machine, not long enough: the game server's first
        mark can come after the panel's first answer, and a leaving player
        after the next pass. The panel still has to say the right thing;
        it only gets a deadline to say it by instead of an instant.
        """
        end = time.time() + timeout
        while True:
            code, body = get(HTTP_PORT, "/admin", cookie=COOKIE)
            if pred(body) or time.time() > end:
                return body
            time.sleep(0.25)

    body = panel_until(lambda b: "никого нет в игре" in b)
    check("пока никто не зашёл -- так и написано",
          "никого нет в игре" in body, True)
    watcher = Client()
    watcher.enter()
    body = panel_until(lambda b: "<td><b>tester</b></td>" in b)
    check("вошедший игрок виден в таблице",
          ("никого нет в игре" not in body, "<td><b>tester</b></td>" in body),
          (True, True))
    watcher.close()
    body = panel_until(lambda b: "никого нет в игре" in b)
    check("вышедший из неё пропадает", "никого нет в игре" in body, True)

    print("\nперсонаж не в игре")
    before = row(_char_id)
    post(HTTP_PORT, "/admin/do",
         {"kind": "money", "char_id": str(_char_id), "afro": "500",
          "gold": "0"}, cookie=COOKIE)
    check("очередь разобрана", wait_done(), True)
    check("деньги записаны в базу",
          row(_char_id)["afro"], before["afro"] + 500)
    # Вещь -- такой же, как выдаёт Session.admin_give в игре (new_fields):
    # раньше строка ложилась голой, ствол 0 из 0 -- NaN у клиента, мимо
    # окна ремонта; дробовик -- на выключенном режиме огня, лекарство без
    # зарядов.
    GIFTS = (25636, 7072, 6049)          # Walther, lamantin_shotgun_4, Med_Pacific_Rest
    for t in GIFTS:
        post(HTTP_PORT, "/admin/do",
             {"kind": "item", "char_id": str(_char_id), "type_id": str(t),
              "count": "1"}, cookie=COOKIE)
    check("очередь разобрана", wait_done(), True)
    db = storage.connect(DB)
    got = {r["type_id"]: (r["brk"], r["max_break_cur"], r["cur_mode"], r["use_count"])
           for r in db.execute("SELECT * FROM items WHERE char_id = ?", (_char_id,)).fetchall()
           if r["type_id"] in GIFTS}
    said = [r["result"] for r in db.execute(
        "SELECT result FROM admin_actions WHERE kind = 'item' ORDER BY id").fetchall()]
    db.close()
    check("выдано мимо сессии -- персонажа в игре нет", said,
          ["положено в рюкзак (не в игре)"] * len(GIFTS))
    fresh = {t: inventory.new_fields(t) for t in GIFTS}
    check("вещь в рюкзак -- как новая: прочность заводская, режим огня рабочий, заряды на месте",
          got, {t: (f.get("brk", 0), f.get("max_break_cur", 0), f.get("cur_mode", 0),
                    f.get("use_count", 0)) for t, f in fresh.items()})
    check("  ..это и в самом деле не нули",
          [got[t] for t in GIFTS], [(500, 500, 0, 0), (400, 400, 2, 0), (0, 0, 0, 10)])
    # (P) выведены из игры, и для админа тоже (решение владельца 2026-09-30,
    # «можно ли админу выдавать (P)? Нельзя»): маска отшельника (P) не
    # ложится в рюкзак, а в журнале панели сказано почему.
    post(HTTP_PORT, "/admin/do",
         {"kind": "item", "char_id": str(_char_id), "type_id": str(MASK_P),
          "count": "1"}, cookie=COOKIE)
    check("очередь разобрана", wait_done(), True)
    db = storage.connect(DB)
    said = db.execute("SELECT result FROM admin_actions WHERE kind = 'item'"
                      " ORDER BY id DESC").fetchone()["result"]
    owned = db.execute("SELECT COUNT(*) c FROM items WHERE type_id = ?",
                       (MASK_P,)).fetchone()["c"]
    db.close()
    check("вещь (P) не в игре -- не выдаётся, и сказано почему",
          (said, owned), (REFUSED_P, 0))
    # Так же транспорт (P): панель его не предлагает, а запрос в обход
    # формы game server отклоняет и вне игры.
    post(HTTP_PORT, "/admin/do",
         {"kind": "transport", "char_id": str(_char_id), "type_id": str(GAZ_P),
          "days": "5"}, cookie=COOKIE)
    check("очередь разобрана", wait_done(), True)
    db = storage.connect(DB)
    said = db.execute("SELECT result FROM admin_actions WHERE kind = 'transport'"
                      " ORDER BY id DESC").fetchone()["result"]
    db.close()
    check("транспорт (P) не в игре -- не выдаётся, и сказано почему",
          (said, row(_char_id)["transport_type"]), (REFUSED_TR % GAZ_P, None))

    print("\nперсонаж в игре")
    cl = Client()
    cl.enter()
    was = row(_char_id)["afro"]
    post(HTTP_PORT, "/admin/do",
         {"kind": "money", "char_id": str(_char_id), "afro": "300",
          "gold": "0"}, cookie=COOKIE)
    check("очередь разобрана", wait_done(), True)
    frames = cl.frames(1.0)
    check("игроку пришёл кошелёк, не дожидаясь перезахода",
          any(f.startswith("userInfo_Player") for f in frames), True)
    post(HTTP_PORT, "/admin/do",
         {"kind": "item", "char_id": str(_char_id), "type_id": str(MASK_P),
          "count": "1"}, cookie=COOKIE)
    check("очередь разобрана", wait_done(), True)
    frames = cl.frames(1.0)
    db = storage.connect(DB)
    said = db.execute("SELECT result FROM admin_actions WHERE kind = 'item'"
                      " ORDER BY id DESC").fetchone()["result"]
    db.close()
    check("и в игре вещь (P) не выдаётся: ни строки в рюкзак, ни ss_obj_status",
          (said, [f for f in frames if f.startswith("ss_obj_status")]),
          (REFUSED_P, []))
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
         {"kind": "transport", "char_id": str(_char_id), "type_id": str(SAUCER_P),
          "days": "5"}, cookie=COOKIE)
    check("очередь разобрана", wait_done(), True)
    frames = cl.frames(1.0)
    db = storage.connect(DB)
    said = db.execute("SELECT result FROM admin_actions WHERE kind = 'transport'"
                      " ORDER BY id DESC").fetchone()["result"]
    db.close()
    check("и в игре транспорт (P) не выдаётся: летающей тарелки нет, userInfo_Player не пришёл",
          (said, row(_char_id)["transport_type"],
           [f for f in frames if f.startswith("userInfo_Player")]),
          (REFUSED_TR % SAUCER_P, None, []))
    post(HTTP_PORT, "/admin/do",
         {"kind": "transport", "char_id": str(_char_id), "type_id": "16",
          "days": "5"}, cookie=COOKIE)
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
          "seconds": "60"}, cookie=COOKIE)
    check("очередь разобрана", wait_done(), True)
    frames = cl.frames(2.0)
    kick = [f for f in frames if f.startswith("kickban")]
    check("пришёл kickban", len(kick), 1)
    if kick:
        # Session.as:199 reads exactly these three and writes
        # "Администратор <admin> ведет работу над вашим аккаунтом".
        check("с логином администратора вместо общего имени",
              "admin=@%s@" % ADMIN_LOGIN in kick[0], True)
        check("со сроком", "seconds=60" in kick[0], True)
        check("и с причиной", "reason=@проверка@" in kick[0], True)
    check("и сокет закрыт", cl.eof or not cl.frames(1.0), True)
    cl.close()

    print("\nбан")
    post(HTTP_PORT, "/admin/do",
         {"kind": "ban", "account_id": str(_acc), "reason": "нельзя"},
         cookie=COOKIE)
    check("очередь разобрана", wait_done(), True)
    db = storage.connect(DB)
    banned = db.execute("SELECT banned FROM accounts WHERE id = ?",
                        (_acc,)).fetchone()["banned"]
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
