import io
BS = chr(92)

p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()
old = ('    def _send(self, body, ctype="text/plain; charset=windows-1251", code=200):\n'
       '        if isinstance(body, str):\n'
       '            body = body.encode("cp1251", "replace")')
new = ('    def _send(self, body, ctype="text/plain; charset=windows-1251", code=200):\n'
       '        if isinstance(body, str):\n'
       '            # Encode to whatever the header promises. The game replies\n'
       '            # are cp1251, the web pages here are utf-8, and declaring\n'
       '            # one while sending the other is how labels went blank once.\n'
       '            enc = "utf-8" if "utf-8" in ctype else "cp1251"\n'
       '            body = body.encode(enc, "replace")')
if old in s:
    s = s.replace(old, new)
    io.open(p, "w", encoding="utf-8").write(s)
    print("bootstrap_http: кодировка исправлена")
else:
    print("bootstrap_http: уже исправлено")

r = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/run.sh"
lines = io.open(r, encoding="utf-8").read().split("\n")
out = []
for ln in lines:
    if "logged=1 is what sends the client" in ln:
        out.append("  # No logged=1 here: that flag makes the client skip its own login")
        out.append("  # screen and take a session straight from loaduser. Without it the")
        out.append("  # player types a name and password, the client hashes them, and the")
        out.append("  # game server checks the digest against a registered account.")
        continue
    if "our host, port and login hash, instead of the official domain" in ln:
        continue
    if ln.strip().startswith("# dead. The projector takes no flashvars"):
        out.append("  # The projector takes no flashvars on the command line, so they ride")
        continue
    if ln.strip().startswith("# in the SWF's query string, which Flash unpacks"):
        out.append("  # in the SWF query string, which Flash unpacks into _root the same.")
        continue
    if 'local vars="logged=1' in ln:
        out.append('  local vars="vversion=1&var_host=127.0.0.1&var_port=$GAME_PORT"')
        continue
    if "-Plogged=1 -Psession=dev -Pvversion=1" in ln:
        out.append("      -Pvversion=1 -Pvar_host=127.0.0.1 -Pvar_port=$GAME_PORT " + BS)
        continue
    if "-Pvar_host=127.0.0.1 -Pvar_port=$GAME_PORT -Pvar_login=dev" in ln:
        continue
    out.append(ln)
io.open(r, "w", encoding="utf-8").write("\n".join(out))
print("run.sh: автовход убран")
