import io, re
base = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/"

p = base + "test_handshake.py"
lines = io.open(p, encoding="utf-8").read().split("\n")
out = []
for ln in lines:
    if "deadbeefcafe" in ln:
        indent = ln[:len(ln) - len(ln.lstrip())]
        out.append(indent + 's.sendall(("login;hash=@%s@;" % CRED).encode("cp1251")')
        out.append(indent + '          + b"' + chr(92) + 'x00")')
        continue
    out.append(ln)
io.open(p, "w", encoding="utf-8").write("\n".join(out))
print("test_handshake: подставлен настоящий хеш")

p = base + "bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()
m = re.search(r'RES_ROOT = os\.environ\.get\(\s*"LAVA_RES",[^)]*\)', s, re.S)
assert m, "anchor missing"
s = s.replace(m.group(0),
              "# one source of truth for where the client's files are\n"
              "RES_ROOT = world.RES")
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(s)
print("bootstrap_http: путь к ресурсам общий")
