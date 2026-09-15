import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()
NL = chr(10)
broken = '            self._send("data=%s:%s devhash' + NL + '" % (GAME_HOST, GAME_PORT))'
fixed = '            self._send("data=%s:%s devhash" % (GAME_HOST, GAME_PORT))'
assert broken in s, "anchor not found"
io.open(p, "w", encoding="utf-8").write(s.replace(broken, fixed))
import ast
ast.parse(io.open(p, encoding="utf-8").read())
print("fixed, syntax ok")
