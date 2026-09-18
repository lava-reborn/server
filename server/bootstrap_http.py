"""HTTP side of the LAVA Online bootstrap.

The client needs three things over HTTP before it will open the game socket.
All of them are reproduced here, so neither the SWF nor the hosts file has to
be touched:

  GET  /res/...                        the client's own res/ tree
  GET  /res/xmldocs/csettings_v1.xml   absent from the shipped client; serving it
                                       flips SSEmulator.PATHTYPE to WEB
  POST /exe/lavaclient/loaduser/?ajax  returns "data=<host>:<port> <hash>",
                                       parsed by Session.getHashHostPort()

Entry path (lol/core/Session.as:88): when _root.logged == 1 and PATHTYPE == WEB,
the client POSTs to the relative loaduser URL and takes host, port and login hash
straight from the reply. That bypasses the hardcoded www.lava-online.ru domain
and the game_session.php endpoint entirely.

None of that is wanted when the player runs the client off their own disk.
Serving csettings_v1.xml is exactly what flips PATHTYPE to WEB, so the whole
/res/ tree -- assets, csettings, texts.xml, hints.xml -- sits behind
LAVA_HTTP_RES, which is off by default. With it off this process is the
registration page and the service replies, nothing else: the client stays in
LOCAL mode, reads its own res/ off the disk and only opens the game socket.
Turn it on (LAVA_HTTP_RES=1) for the WEB path, which is what run.sh and the
test suites use.
"""
import json
import os
import signal
import threading
from xml.sax.saxutils import escape
import posixpath
import re
import sys

import hashlib
import hmac
import time
from urllib.parse import quote

import accounts
import names
import items
import transport
import world
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

# one source of truth for where the client's files are
RES_ROOT = world.RES
GAME_HOST = os.environ.get("LAVA_GAME_HOST", "127.0.0.1")
GAME_PORT = os.environ.get("LAVA_GAME_PORT", "9775")
HTTP_PORT = int(os.environ.get("LAVA_HTTP_PORT", "8080"))

# Adobe pulled the browser plugin and left the standalone player up. Same
# address as tools/make_client_package.py hands out; repeated rather than
# imported, because the image carries server/ and data/ and nothing else.
PROJECTOR_URL = ("https://fpdownload.macromedia.com/pub/flashplayer/updaters/"
                 "32/flashplayer_32_sa.exe")
# Inside a container 127.0.0.1 is the container's own loopback and no
# published port reaches it, so the address to listen on is configuration.
HTTP_HOST = os.environ.get("LAVA_HTTP_HOST", "127.0.0.1")


def _flag(name, default="0"):
    return os.environ.get(name, default).strip().lower() not in (
        "", "0", "no", "off", "false")


# Everything under /res/ -- the client's own files and the three documents
# this process synthesises for them -- is one switch, because they are one
# decision. Serving any of them means serving csettings_v1.xml, and that is
# what puts the client in WEB mode.
SERVE_RES = _flag("LAVA_HTTP_RES")

# Which game logins may open the admin panel, comma separated. Empty means
# there is no panel: every /admin path answers 404, the same as any address
# that is not ours, so a server nobody set it up on does not advertise that
# it has one. The password is the account's own -- the panel checks it the
# way the game does -- and the login is the name the kicked player sees.
ADMINS = {s.strip() for s in os.environ.get("LAVA_ADMINS", "").split(",")
          if s.strip()}
# How long a sign-in lasts.
ADMIN_HOURS = int(os.environ.get("LAVA_ADMIN_HOURS", "12"))
# Signs the cookie. Made fresh on every start, deliberately: it is one less
# secret to configure or leak, and the only cost is that restarting the panel
# asks whoever was in it to sign in again.
ADMIN_SECRET = os.urandom(32)

CSETTINGS = """<?xml version="1.0" encoding="windows-1251"?>
<settings>
  <gamesrv host="{host}" port="{port}"/>
  <debug value="1"/>
  <resource base="http://{host}:{http_port}/res">
    <item_icon format="swf">classes/</item_icon>
    <item_anim format="swf">classes/</item_anim>
    <avatar_list format="xml">avatars/list.xml</avatar_list>
    <avatar format="swf">avatars/</avatar>
    <sprite format="swf">locations/libs/</sprite>
    <globalmap format="swf">globalmap/</globalmap>
    <location_info format="xml">locations/</location_info>
    <location_lib format="swf">locations/libs/</location_lib>
    <mob_anim format="swf">mobs/</mob_anim>
    <mob_info format="xml">mobs/</mob_info>
    <char_anim format="swf">personages/</char_anim>
    <char_info format="xml">personages/</char_info>
    <text format="xml">xmldocs/</text>
    <sound format="swf">sounds/</sound>
  </resource>
</settings>
"""

CTYPES = {
    ".swf": "application/x-shockwave-flash",
    ".xml": "text/xml",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".mp3": "audio/mpeg", ".txt": "text/plain",
}

CROSSDOMAIN = (
    '<?xml version="1.0"?>'
    '<cross-domain-policy><allow-access-from domain="*" to-ports="*"/>'
    "</cross-domain-policy>"
)

PAGE = """<!doctype html><html lang=ru><meta charset=utf-8>
<title>LAVA Online</title>
<style>
 body{{background:#15130f;color:#cfc6b0;font:15px/1.5 system-ui,sans-serif;
      margin:0;padding:40px 20px}}
 .w{{max-width:440px;margin:0 auto}}
 h1{{font-size:20px;letter-spacing:.14em;text-transform:uppercase;
     color:#b9a678;margin:0 0 4px}}
 p.sub{{margin:0 0 28px;color:#7d7566}}
 form{{background:#1e1b15;border:1px solid #332d22;padding:22px;border-radius:4px}}
 label{{display:block;margin:0 0 6px;color:#9c9280;font-size:13px}}
 input{{width:100%;box-sizing:border-box;background:#100e0a;color:#e8dfc8;
        border:1px solid #3d362a;border-radius:3px;padding:9px 10px;
        font-size:15px;margin:0 0 16px}}
 button{{width:100%;background:#6b5a34;color:#f2e9d2;border:0;border-radius:3px;
         padding:11px;font-size:15px;cursor:pointer}}
 button:hover{{background:#7d6a3e}}
 .msg{{padding:11px 13px;border-radius:3px;margin:0 0 20px;font-size:14px}}
 .ok{{background:#243a20;border:1px solid #3d5c33;color:#bfe0ae}}
 .err{{background:#3a2020;border:1px solid #5c3333;color:#e0aeae}}
 .note{{margin-top:26px;color:#7d7566;font-size:13px}}
 code{{background:#100e0a;padding:2px 6px;border-radius:3px;color:#c4b48a}}
</style>
<div class=w>
<h1>LAVA Online</h1>
<p class=sub>Регистрация в игре</p>
{message}
<form method=post action="/register">
 <label for=login>Логин</label>
 <input id=login name=login autocomplete=username autofocus>
 <label for=password>Пароль</label>
 <input id=password name=password type=password autocomplete=new-password>
 <button type=submit>Создать аккаунт</button>
</form>
{howto}
<p class=note>Учётных записей: {count}. Сервер отвечает на
<code>{host}:{port}</code>.</p>
</div></html>"""

# Shown when this server hands out the client as well: then a newcomer needs
# nothing but the projector, because csettings_v1.xml goes out with the rest
# and puts the client in WEB mode, pointed back here for every file.
HOWTO_WEB = """<div class=note>
<p><b>Как играть</b></p>
<p>1. Скачайте проигрыватель Flash — отдельную программу, не браузер:<br>
<a href="{projector}">flashplayer_32_sa.exe</a></p>
<p>2. Запустите игру через него. Перетащите ссылку на скачанный файл или
выполните в командной строке:</p>
<p><code>flashplayer_32_sa.exe {base}/res/main.swf</code></p>
<p>3. В окне входа введите логин и пароль отсюда. Персонаж создаётся при
первом входе. Всё остальное игра возьмёт с этого сервера сама.</p>
</div>"""

ADMIN_STYLE = '''
 :root{{--bg:#15130f;--card:#1e1b15;--line:#332d22;--ink:#cfc6b0;
        --dim:#8a8172;--gold:#b9a678;--brass:#6b5a34;--field:#100e0a}}
 *{{box-sizing:border-box}}
 body{{background:var(--bg);color:var(--ink);margin:0;
       font:14px/1.55 -apple-system,Segoe UI,Roboto,system-ui,sans-serif}}
 a{{color:var(--gold)}}
 .bar{{border-bottom:1px solid var(--line);background:#1a1712;
       padding:14px 20px;display:flex;align-items:baseline;gap:12px;
       flex-wrap:wrap}}
 .bar h1{{font-size:15px;letter-spacing:.16em;text-transform:uppercase;
          color:var(--gold);margin:0;font-weight:600}}
 .w{{max-width:920px;margin:0 auto;padding:22px 20px 60px}}
 h2{{font-size:13px;letter-spacing:.12em;text-transform:uppercase;
     color:var(--dim);font-weight:600;margin:30px 0 10px;
     padding-bottom:7px;border-bottom:1px solid var(--line)}}
 h2:first-of-type{{margin-top:6px}}
 .dim{{color:var(--dim)}}
 .card{{background:var(--card);border:1px solid var(--line);border-radius:5px;
        padding:14px 16px;margin:0 0 12px}}
 .card h3{{margin:0 0 2px;font-size:15px;color:#e8dfc8;font-weight:600}}
 .row{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:9px 0 0}}
 .row > label{{color:var(--dim);font-size:12px;letter-spacing:.06em;
               text-transform:uppercase;min-width:82px}}
 input,select{{background:var(--field);color:#e8dfc8;
      border:1px solid #3d362a;border-radius:4px;padding:7px 9px;
      font:inherit;min-width:0}}
 input:focus,select:focus{{outline:none;border-color:var(--gold);
      box-shadow:0 0 0 2px rgba(185,166,120,.18)}}
 input[type=number]{{width:92px}}
 input[type=text]{{width:160px}}
 select{{max-width:270px}}
 button{{background:var(--brass);color:#f6efdd;border:1px solid #7d6a3e;
         border-radius:4px;padding:7px 14px;font:inherit;cursor:pointer}}
 button:hover{{background:#7d6a3e}}
 button.ghost{{background:transparent;color:var(--ink);border-color:var(--line)}}
 button.ghost:hover{{background:#262119;border-color:#4a4132}}
 button.warn{{background:#5c3333;border-color:#7a4444;color:#f0d9d9}}
 button.warn:hover{{background:#6e3d3d}}
 /* The five action forms share one card: without this each would draw its
    own box. Scoped to them by class on purpose -- the sign-in form IS a
    card, and display:contents would dissolve it. */
 form.act{{display:contents}}
 table{{width:100%;border-collapse:collapse;background:var(--card);
        border:1px solid var(--line);border-radius:5px;overflow:hidden}}
 th{{text-align:left;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
     color:var(--dim);font-weight:600;padding:9px 12px;
     border-bottom:1px solid var(--line);background:#1a1712}}
 td{{padding:9px 12px;border-top:1px solid #262119}}
 tr:first-child td{{border-top:0}}
 .num{{font-family:ui-monospace,Consolas,monospace;color:var(--gold)}}
 .msg{{padding:11px 14px;border-radius:4px;margin:0 0 16px;border:1px solid}}
 .ok{{background:#243a20;border-color:#3d5c33;color:#bfe0ae}}
 .err{{background:#3a2020;border-color:#5c3333;color:#e0aeae}}
 .gate{{min-height:100vh;display:flex;align-items:center;justify-content:center;
        padding:24px}}
 .gate .card{{width:100%;max-width:330px;margin:0;padding:26px 24px}}
 .gate .brand{{font-size:12px;letter-spacing:.24em;text-transform:uppercase;
               color:var(--gold);text-align:center;margin:0 0 4px}}
 .gate .sub{{text-align:center;color:var(--dim);font-size:13px;margin:0 0 22px}}
 .gate label{{display:block;color:var(--dim);font-size:12px;
              letter-spacing:.06em;text-transform:uppercase;margin:0 0 6px}}
 .gate input{{width:100%;margin:0 0 16px}}
 .gate button{{width:100%;padding:10px}}
 .gate .foot{{color:var(--dim);font-size:12px;text-align:center;margin:18px 0 0}}
'''

ADMIN_GATE = '''<!doctype html><html lang=ru><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>LAVA Online — панель</title><style>%s</style>
<div class=gate>
 <form method=post action="/admin/login" class=card>
  <p class=brand>LAVA Online</p>
  <p class=sub>Панель администратора</p>
  {message}
  <label for=l>Логин</label>
  <input id=l name=login autocomplete=username autofocus>
  <label for=p>Пароль</label>
  <input id=p name=password type=password autocomplete=current-password>
  <button type=submit>Войти</button>
  <p class=foot>Те же логин и пароль, что и в игре</p>
 </form>
</div></html>''' % ADMIN_STYLE

ADMIN_ONLINE_ROW = '''<tr>
 <td><b>{nick}</b></td><td class=dim>{login}</td>
 <td>{where} <span class=num>{cell}</span></td>
 <td class=dim>{mins} мин</td>
 <td><a href="/admin?q={query}">открыть</a></td>
</tr>'''

# One card per character found: everything that can be done to it, each its
# own form, because a single form with one button per action would send every
# field of every action every time. q rides along so the page comes back with
# the same search still on it. The class on each form is what lets five of
# them share one card without five boxes appearing round them.
ADMIN_CHAR = '''<div class=card>
<h3>{name} <span class=dim>· {login}{banned}</span></h3>
<div class=dim>#{char_id} · <span class=num>{afro}</span> афро ·
<span class=num>{gold}</span> голды · локация <span class=num>{loc}</span></div>
<form class=act method=post action="/admin/do"><div class=row>
 <input type=hidden name=kind value=money><input type=hidden name=char_id value={char_id}>
 <input type=hidden name=q value="{name}">
 <label>Деньги</label>
 <input type=number name=afro value=0 title="афро"> афро
 <input type=number name=gold value=0 title="голда, целыми унциями"> голды
 <button type=submit>Начислить</button>
</div></form>
<form class=act method=post action="/admin/do"><div class=row>
 <input type=hidden name=kind value=item><input type=hidden name=char_id value={char_id}>
 <input type=hidden name=q value="{name}">
 <label>Предмет</label>
 <input type=number name=type_id placeholder="тип" title="номер типа">
 <input type=number name=count value=1 title="сколько">
 <button type=submit>Выдать</button>
</div></form>
<form class=act method=post action="/admin/do"><div class=row>
 <input type=hidden name=kind value=transport><input type=hidden name=char_id value={char_id}>
 <input type=hidden name=q value="{name}">
 <label>Транспорт</label>
 <select name=type_id>{cars}</select>
 <input type=number name=days placeholder="дней" title="по умолчанию 365">
 <button type=submit>Выдать</button>
</div></form>
<form class=act method=post action="/admin/do"><div class=row>
 <input type=hidden name=kind value=goto><input type=hidden name=char_id value={char_id}>
 <input type=hidden name=q value="{name}">
 <label>Перенести</label>
 <input type=number name=loc placeholder="локация">
 <span class=dim>или</span>
 <input type=number name=gx placeholder="x"> <input type=number name=gy placeholder="y">
 <button type=submit class=ghost>Перенести</button>
</div></form>
<form class=act method=post action="/admin/do"><div class=row>
 <input type=hidden name=account_id value={account_id}>
 <input type=hidden name=q value="{name}">
 <label>Учётка</label>
 <input type=text name=reason placeholder="причина, видна игроку">
 <input type=number name=seconds placeholder="секунд" title="0 — не указывать">
 <button type=submit name=kind value=kick class=ghost>Выкинуть</button>
 <button type=submit name=kind value=ban class=warn>Забанить</button>
 <button type=submit name=kind value=unban class=ghost>Разбанить</button>
</div></form>
</div>'''

ADMIN_PAGE = '''<!doctype html><html lang=ru><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>LAVA Online — панель</title><style>%s</style>
<div class=bar>
 <h1>LAVA Online</h1>
 <span class=dim>панель администратора · {who}</span>
</div>
<div class=w>
{note}
<h2>Сейчас в игре</h2>
{online}
<h2>Найти игрока</h2>
<div class=card><form method=get action="/admin"><div class=row>
 <input type=text name=q value="{query}" placeholder="ник или логин"
        style="width:280px" autofocus>
 <button type=submit>Искать</button>
</div></form></div>
{results}
<h2>Последние действия</h2>
<table><tr><th>кто</th><th>что</th><th>итог</th></tr>{log}</table>
<p class=dim style="margin-top:26px">Действия выполняет игровой сервер: он
разбирает очередь раз в секунду. Игроку в игре изменения приходят сразу,
остальным — при следующем входе.</p>
</div></html>''' % ADMIN_STYLE

# Built once: the table is loaded at import and never changes.
TRANSPORT_OPTIONS = "".join(
    '<option value="%d">%d · %s (x%s)</option>'
    % (int(v["type"]), int(v["type"]), v["name"], v["speed_mod"])
    for v in sorted(transport.TABLE.values(), key=lambda v: int(v["type"]))
) + '<option value="0">0 · снять транспорт</option>'


# And when it does not: the client is the player's own copy, so the launcher
# and the string table come from the package instead.
HOWTO_LOCAL = """<div class=note>
<p>Вход выполняется из самой игры: запустите клиент и введите те же логин и
пароль.</p>
</div>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "lava-bootstrap"

    def _send(self, body, ctype="text/plain; charset=windows-1251", code=200):
        if isinstance(body, str):
            # Encode to whatever the header promises. The game replies
            # are cp1251, the web pages here are utf-8, and declaring
            # one while sending the other is how labels went blank once.
            enc = "utf-8" if "utf-8" in ctype else "cp1251"
            body = body.encode(enc, "replace")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("  HTTP %s" % (fmt % args), flush=True)

    # --- routing ---------------------------------------------------------
    def _resource(self, path):
        """Serve a file straight out of the client's own res/ tree."""
        rel = path[len("/res/"):].replace("/", os.sep)
        full = os.path.normpath(os.path.join(RES_ROOT, rel))
        # Compare with a separator on the end, or a sibling directory whose
        # name merely starts with the root's would pass for being inside it.
        root = os.path.normpath(RES_ROOT) + os.sep
        if not (full + os.sep).startswith(root):
            self._send("forbidden", code=403)
            return
        if not os.path.isfile(full):
            self._send("not found", code=404)
            return
        ctype = CTYPES.get(os.path.splitext(full)[1].lower(),
                           "application/octet-stream")
        with open(full, "rb") as fh:
            self._send(fh.read(), ctype)

    def _texts(self, query, body):
        """Stand in for the missing res/database/texts.xml.

        Item names, quest text and NPC lines all travel as numeric string ids
        resolved through this endpoint, and the 20 MB file behind it is one of
        only two files absent from the shipped client. Until those strings are
        recovered, answer with the names the client's own tables and the wiki
        can supply: an item whose name never arrives is never added to the
        inventory at all.

        The ?all=1 request must answer with every id the server will ever use,
        and an empty reply here is not a harmless stub. StringCollector is a
        singleton that keeps SBase subscribed to its "update" event for the
        life of the session, and SBase answers that event by reloading the
        location names and dispatching its own "onLoad" — which Session
        handles with SceneShifter.enterScene(), the login screen. So any batch
        of strings fetched after login throws the player back to the login
        window. Filling the cache up front is what stops a second batch from
        ever being asked for; that is also why logging in twice used to work.
        """
        if "all=1" in (query or ""):
            self._send_xml("<data>%s</data>" % names.document())
            return
        # Reaching this at all means an id escaped the preload, which is the
        # fault worth knowing about: answering keeps the client moving, but
        # the request itself has already brought the login screen back.
        ids = [int(m) for m in re.findall(b"[0-9]+", body or b"")]
        unknown = [i for i in ids if not names.known(i)]
        if unknown:
            print("  HTTP строки мимо предзагрузки: %s" % unknown[:10],
                  flush=True)
        rows = "".join("<s id='%d'>%s</s>" % (i, names.text(i)) for i in ids)
        self._send_xml("<data>%s</data>" % rows)

    def _page(self, message=""):
        store = accounts.Store()
        try:
            count = store.account_count()
        finally:
            store.close()
        if SERVE_RES:
            # The address the browser reached us by, not one from the
            # environment: it is right whether that was an IP and a port or
            # a name in front of a proxy, and the proxy says which scheme.
            host = self.headers.get("Host") or ("%s:%s" % (GAME_HOST, HTTP_PORT))
            scheme = self.headers.get("X-Forwarded-Proto") or "http"
            howto = HOWTO_WEB.format(base="%s://%s" % (scheme, host),
                                     projector=PROJECTOR_URL)
        else:
            howto = HOWTO_LOCAL
        self._send(PAGE.format(message=message, count=count, howto=howto,
                               host=GAME_HOST, port=GAME_PORT),
                   "text/html; charset=utf-8")

    # --- admin panel -----------------------------------------------------
    #
    # The door is the game's own account: the same login and password the
    # player types into the client, checked the same way, because the client
    # sends md5(cp1251(password + login)) and that digest is what the
    # accounts table already holds. So the panel needs no password store of
    # its own and no second thing to forget. Which logins may open it is
    # configuration, not data: LAVA_ADMINS.

    def _admin_cookie(self, login):
        """A cookie that says who, signed so it cannot say someone else."""
        until = int(time.time()) + ADMIN_HOURS * 3600
        raw = "%s|%d" % (login, until)
        sig = hmac.new(ADMIN_SECRET, raw.encode("utf-8"),
                       hashlib.sha256).hexdigest()
        return quote("%s|%s" % (raw, sig), safe="")

    def _admin_login_of(self, cookie_value):
        """The login a cookie proves, or None."""
        try:
            raw = unquote(cookie_value)
            login, until, sig = raw.rsplit("|", 2)
        except ValueError:
            return None
        want = hmac.new(ADMIN_SECRET, ("%s|%s" % (login, until)).encode("utf-8"),
                        hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, want):
            return None
        if int(until) < time.time():
            return None
        return login if login in ADMINS else None

    def _admin_who(self):
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "lava_admin":
                return self._admin_login_of(value)
        return None

    def _admin_signin(self, body):
        form = parse_qs(body.decode("utf-8", "replace"))
        login = (form.get("login") or [""])[0].strip()
        password = (form.get("password") or [""])[0]
        store = accounts.Store()
        try:
            row = store.account_by_login(login)
        finally:
            store.close()
        # Every failure says the same thing: which of the three went wrong is
        # not the visitor's business.
        ok = (row is not None and login in ADMINS and not row["banned"]
              and hmac.compare_digest(str(row["hash"]),
                                      accounts.credential(login, password)))
        if not ok:
            print("  ADMIN refused %r" % login, flush=True)
            self._admin_gate("Не подошло")
            return
        print("  ADMIN %r signed in" % login, flush=True)
        payload = b"ok"
        self.send_response(303)
        self.send_header("Location", "/admin")
        self.send_header("Set-Cookie",
                         "lava_admin=%s; Path=/; HttpOnly; SameSite=Strict"
                         % self._admin_cookie(login))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _admin_gate(self, message=""):
        msg = '<p class="msg err">%s</p>' % escape(message) if message else ""
        self._send(ADMIN_GATE.format(message=msg), "text/html; charset=utf-8")

    def _admin_panel(self, who, note="", query=""):
        store = accounts.Store()
        try:
            found = [dict(r) for r in store.find_characters(query)] if query else []
            online, beat = store.online()
            online = [dict(r) for r in online]
            recent = [dict(r) for r in store.admin_recent(25)]
        finally:
            store.close()

        now = int(time.time())
        if beat is None:
            live = ('<p class="msg err">Игровой сервер ни разу не отмечался — '
                    'похоже, он не запущен.</p>')
        elif now - beat > 15:
            live = ('<p class="msg err">Последняя отметка игрового сервера '
                    '%d с назад: список ниже устарел.</p>' % (now - beat))
        elif not online:
            live = '<p class=dim>Сейчас никого нет в игре.</p>'
        else:
            live = "<table><tr><th>ник</th><th>учётка</th><th>где</th>"\
                   "<th>в игре</th><th></th></tr>" + "".join(
                ADMIN_ONLINE_ROW.format(
                    nick=escape(r["nick"]), login=escape(r["login"]),
                    where=escape(r["title"] or "-"),
                    cell="%s,%s" % (r["gx"], r["gy"]),
                    mins=max(0, (now - r["since"]) // 60),
                    char_id=r["char_id"], query=escape(r["nick"]))
                for r in online) + "</table>"

        if query and not found:
            results = '<p class=dim>По запросу «%s» никого.</p>' % escape(query)
        else:
            results = "".join(
                ADMIN_CHAR.format(
                    char_id=ch["id"], name=escape(ch["name"]),
                    login=escape(ch["login"]),
                    account_id=ch["account_id"],
                    banned=" · <b>забанен</b>" if ch["banned"] else "",
                    afro=ch["afro"], gold=ch["gold"] // 100,
                    loc=ch["loc"] if ch["loc"] is not None else "-",
                    cars=TRANSPORT_OPTIONS)
                for ch in found)

        log_rows = "".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (escape(r["admin"]), escape(r["kind"]),
               escape(r["result"] or "ждёт очереди"))
            for r in recent) or "<tr><td colspan=3 class=dim>пусто</td></tr>"

        note_html = '<p class="msg ok">%s</p>' % escape(note) if note else ""
        self._send(ADMIN_PAGE.format(who=escape(who), note=note_html,
                                     online=live, query=escape(query),
                                     results=results, log=log_rows),
                   "text/html; charset=utf-8")

    def _admin_do(self, who, body):
        """Queue one action. The game server is what carries it out."""
        form = parse_qs(body.decode("utf-8", "replace"))

        def one(key, default=""):
            return (form.get(key) or [default])[0].strip()

        def num(key, default=0):
            try:
                return int(one(key) or default)
            except ValueError:
                return default

        kind = one("kind")
        char_id = num("char_id") or None
        account_id = num("account_id") or None
        # Whatever was searched for stays searched for, so the page comes
        # back with the same player on it rather than empty.
        query = one("q")
        store = accounts.Store()
        try:
            if kind == "money":
                store.admin_push(who, "money", char_id=char_id,
                                 afro=num("afro"), gold=num("gold") * 100)
                note = "Деньги поставлены в очередь"
            elif kind == "item":
                store.admin_push(who, "item", char_id=char_id,
                                 type_id=num("type_id"),
                                 count=num("count", 1) or 1)
                note = "Предмет поставлен в очередь"
            elif kind == "transport":
                store.admin_push(who, "transport", char_id=char_id,
                                 type_id=num("type_id"),
                                 days=num("days") or None)
                note = "Транспорт поставлен в очередь"
            elif kind == "goto":
                loc = one("loc")
                if loc:
                    store.admin_push(who, "goto", char_id=char_id,
                                     loc_id=int(loc))
                else:
                    store.admin_push(who, "goto", char_id=char_id,
                                     gx=num("gx"), gy=num("gy"))
                note = "Перенос поставлен в очередь"
            elif kind in ("kick", "ban", "unban"):
                store.admin_push(
                    who, "kick" if kind == "kick" else "ban",
                    account_id=account_id, seconds=num("seconds"),
                    reason=one("reason"), banned=(kind == "ban"))
                note = {"kick": "Игрок будет выкинут",
                        "ban": "Бан поставлен в очередь",
                        "unban": "Разбан поставлен в очередь"}[kind]
            else:
                note = "Неизвестное действие"
        finally:
            store.close()
        self._admin_panel(who, note, query)

    def _status(self):
        """What a healthcheck can ask without a game client.

        Touching the account store is the point: the page cannot register
        anyone if the database is unreachable, and a process that answers
        while its only job is broken is worse than one that is down.
        """
        store = accounts.Store()
        try:
            count = store.account_count()
        finally:
            store.close()
        self._send(json.dumps({
            "ok": True,
            "accounts": count,
            "strings": len(names.ALL),
            "game": "%s:%s" % (GAME_HOST, GAME_PORT),
            "res": SERVE_RES,
        }), "application/json; charset=utf-8")

    def _register(self, body):
        form = parse_qs(body.decode("utf-8", "replace"))
        login = (form.get("login") or [""])[0]
        password = (form.get("password") or [""])[0]
        store = accounts.Store()
        try:
            _id, err = store.register(login, password)
        finally:
            store.close()
        if err:
            self._page('<p class="msg err">%s</p>' % err)
        else:
            self._page('<p class="msg ok">Аккаунт <b>%s</b> создан. '
                       'Запустите клиент и войдите этим логином.</p>'
                       % login.replace("<", "&lt;"))

    def _send_xml(self, body):
        """Answer the way the client's own XML files are written.

        Every file under res/ is UTF-8, most of them with a byte order mark,
        whatever their declaration claims. Sending cp1251 here, as the game
        socket uses, leaves the parser with bytes it cannot read, and the
        client quietly ends up with no strings at all rather than an error.
        """
        payload = ("﻿<?xml version='1.0'?>" + body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _dispatch(self, body=b""):
        parts = urlparse(self.path)
        # Percent-decode before touching the filesystem. Fifteen files under
        # res/ have a space in the name -- "Vadihalfa port.swf" is the art
        # library of the Wadi Halfa docks -- and the client asks for them
        # correctly escaped. Without this the location loads with no artwork
        # at all and shows as a black field, with only a 404 in the log to
        # say so.
        path = posixpath.normpath(unquote(parts.path))
        if path.rstrip("/") == "/exe/lavaclient/loaduser":
            # Fills the host and port fields on the client's own login screen,
            # which parses the reply with getHashHostPort. No digest belongs
            # here any more: the client computes its own from the password.
            # Real Flash asks with GET, since LoadVars.sendAndLoad downgrades
            # to one when the outgoing object carries no variables, while
            # Ruffle issues the POST that was actually requested.
            self._send("data=%s:%s" % (GAME_HOST, GAME_PORT))
            return
        if path == "/register":
            self._register(body)
            return
        if path == "/admin" or path.startswith("/admin/"):
            if not ADMINS:
                self._send("not found", code=404)
                return
            if path == "/admin/login":
                self._admin_signin(body)
                return
            who = self._admin_who()
            if not who:
                self._admin_gate()
            elif path == "/admin/do":
                self._admin_do(who, body)
            else:
                self._admin_panel(who, query=parse_qs(parts.query)
                                  .get("q", [""])[0])
            return
        if path in ("/", "/index.html"):
            self._page()
        elif path == "/status":
            self._status()
        elif path.endswith("/crossdomain.xml"):
            self._send(CROSSDOMAIN, "text/x-cross-domain-policy")
        elif path.startswith("/res/") and not SERVE_RES:
            # Assets are the player's own copy of the game; we never hand them
            # out. Answering 404 rather than 403 is also the answer the client
            # needs: a csettings_v1.xml that is not there is what leaves it in
            # LOCAL mode, reading its own res/ off the disk.
            self._send("not found", code=404)
        elif path == "/res/xmldocs/csettings_v1.xml":
            self._send(CSETTINGS.format(host=GAME_HOST, port=GAME_PORT,
                                        http_port=HTTP_PORT), "text/xml")
        elif path == "/res/database/texts.xml":
            self._texts(parts.query, body)
        elif path == "/res/hints/hints.xml":
            # The other of the two files missing from the shipped client
            # (texts.xml is the first). An empty document satisfies it, but
            # written the way the client's own XML is, UTF-8 with a byte
            # order mark, which is what _send_xml does; the cp1251 that
            # _send produces is the same silent failure texts.xml had.
            self._send_xml("<data/>")
        elif path.startswith("/res/"):
            self._resource(path)
        else:
            self._send("not found", code=404)

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        # The client fetches every XML resource with LoadVars.sendAndLoad,
        # which issues a POST. Only the login handshake is a POST by intent;
        # everything else must be served exactly as it would be over GET.
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self._dispatch(body)


if __name__ == "__main__":
    print("res root : %s" % RES_ROOT)
    print("game srv : %s:%s" % (GAME_HOST, GAME_PORT))
    print("http     : http://%s:%d/" % (HTTP_HOST, HTTP_PORT))
    print("res serve: %s" % ("on" if SERVE_RES else "off (registration only)"))
    # Build the 1.9 MB string table before the client can ask for it.
    names.document()
    httpd = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler)
    # docker stop sends SIGTERM, whose default action kills the process where
    # it stands. Nothing here is worth saving, but the listener should close
    # and the log should say so rather than the container reporting 143.
    for _sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(_sig, lambda *_a: threading.Thread(
            target=httpd.shutdown, daemon=True).start())
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        print("http stopped", flush=True)
