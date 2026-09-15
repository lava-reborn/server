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
"""
import os
import posixpath
import re
import sys

import accounts
import world
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# one source of truth for where the client's files are
RES_ROOT = world.RES
GAME_HOST = os.environ.get("LAVA_GAME_HOST", "127.0.0.1")
GAME_PORT = os.environ.get("LAVA_GAME_PORT", "9775")
HTTP_PORT = int(os.environ.get("LAVA_HTTP_PORT", "8080"))

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

# The server hands out a creature's type id where a string id belongs, so the
# stub below can answer with a real name. Preference order: the names recovered
# from the community wiki, then the internal name from the client's own table,
# then the bare id.
try:
    MOB_NAMES = {t: n for t, (_r, n, _a) in world.mob_types().items()}
except Exception:
    MOB_NAMES = {}

try:
    import json
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(_here, "data", "npc_names.json"), encoding="utf-8") as _f:
        REAL_NAMES = {int(k): v for k, v in json.load(_f)["names"].items()}
except Exception:
    REAL_NAMES = {}

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
<p class=note>Учётных записей: {count}. Вход выполняется из самой игры:
запустите клиент и введите те же логин и пароль. Сервер отвечает на
<code>{host}:{port}</code>.</p>
</div></html>"""


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
        if not full.startswith(os.path.normpath(RES_ROOT)):
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
        recovered, echo every requested id back as its own placeholder: an item
        whose name never arrives is never added to the inventory at all.
        """
        if "all=1" in (query or ""):
            self._send_xml("<data></data>")
            return
        ids = [m.decode() for m in re.findall(rb"\d+", body or b"")]
        rows = "".join(
            "<s id='%s'>%s</s>"
            % (i, REAL_NAMES.get(int(i)) or MOB_NAMES.get(int(i), "#" + i))
            for i in ids)
        self._send_xml("<data>%s</data>" % rows)

    def _page(self, message=""):
        store = accounts.Store()
        try:
            count = store.account_count()
        finally:
            store.close()
        self._send(PAGE.format(message=message, count=count,
                               host=GAME_HOST, port=GAME_PORT),
                   "text/html; charset=utf-8")

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
        path = posixpath.normpath(parts.path)
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
        if path in ("/", "/index.html"):
            self._page()
        elif path.endswith("/crossdomain.xml"):
            self._send(CROSSDOMAIN, "text/x-cross-domain-policy")
        elif path == "/res/xmldocs/csettings_v1.xml":
            self._send(CSETTINGS.format(host=GAME_HOST, port=GAME_PORT,
                                        http_port=HTTP_PORT), "text/xml")
        elif path == "/res/database/texts.xml":
            self._texts(parts.query, body)
        elif path == "/res/hints/hints.xml":
            # never shipped with the client; an empty document satisfies it
            self._send("<data></data>", "text/xml")
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
    print("http     : http://127.0.0.1:%d/" % HTTP_PORT)
    ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler).serve_forever()
