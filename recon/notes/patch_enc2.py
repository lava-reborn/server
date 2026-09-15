import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()
old = '''    def _send(self, body, ctype="text/plain; charset=windows-1251", code=200):
        if isinstance(body, str):
            body = body.encode("cp1251", "replace")'''
new = '''    def _send(self, body, ctype="text/plain; charset=windows-1251", code=200):
        if isinstance(body, str):
            # Encode to whatever the header promises. The game's own replies
            # are cp1251, but the web pages here are utf-8, and declaring one
            # while sending the other is how the labels went blank once.
            enc = "utf-8" if "utf-8" in ctype else "cp1251"
            body = body.encode(enc, "replace")'''
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))

r = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/run.sh"
s = io.open(r, encoding="utf-8").read()
s = s.replace('''  # logged=1 is what sends the client down the loaduser path, where it takes
  # our host, port and login hash, instead of the official domain that is now
  # dead. The projector takes no flashvars on the command line, so they ride
  # in the SWF's query string, which Flash unpacks into _root exactly the same.
  local vars="logged=1&session=dev&vversion=1&var_host=127.0.0.1&var_port=$GAME_PORT&var_login=dev"''',
'''  # No logged=1 here: that flag is what makes the client skip its own login
  # screen and take a session straight from loaduser. With it gone the player
  # types a name and password, the client hashes them, and the game server
  # checks the digest against a registered account.
  # The projector takes no flashvars on the command line, so they ride in the
  # SWF's query string, which Flash unpacks into _root exactly the same.
  local vars="vversion=1&var_host=127.0.0.1&var_port=$GAME_PORT"''')
s = s.replace('''      -Plogged=1 -Psession=dev -Pvversion=1 \
      -Pvar_host=127.0.0.1 -Pvar_port=$GAME_PORT -Pvar_login=dev \''',
'''      -Pvversion=1 -Pvar_host=127.0.0.1 -Pvar_port=$GAME_PORT \''')
io.open(r, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
