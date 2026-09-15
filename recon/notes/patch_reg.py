import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace("import world", "import accounts\nimport world")
s = s.replace("from urllib.parse import urlparse",
              "from urllib.parse import parse_qs, urlparse")

# replace the Ruffle embed page with a registration page
start = s.index("INDEX = ")
end = s.index("class Handler(")
new_index = '''PAGE = """<!doctype html><html lang=ru><meta charset=utf-8>
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


'''
s = s[:start] + new_index + s[end:]

# routing: registration page and its POST, and a plain host:port for the login screen
s = s.replace('''        if path.rstrip("/") == "/exe/lavaclient/loaduser":
            # Session.getHashHostPort() splits the reply on ":" then " ".
            # Real Flash asks for this with GET, because LoadVars.sendAndLoad
            # downgrades to GET when the outgoing object carries no variables,
            # while Ruffle issues the POST the call actually requested. Accept
            # both.
            self._send("data=%s:%s devhash" % (GAME_HOST, GAME_PORT))
            return
        if path in ("/", "/index.html"):
            self._send(INDEX.format(host=GAME_HOST, port=GAME_PORT),
                       "text/html; charset=utf-8")''',
'''        if path.rstrip("/") == "/exe/lavaclient/loaduser":
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
            self._page()''')

s = s.replace('''    def _send_xml(self, body):''',
'''    def _page(self, message=""):
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

    def _send_xml(self, body):''')
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
