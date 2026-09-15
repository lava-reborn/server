import io, re
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_bootstrap.py"
s = io.open(p, encoding="utf-8", errors="surrogateescape").read()
lines = s.split("\n")
out = []
for ln in lines:
    if "texts stub is utf-8 with BOM" in ln:
        out.append("    # the client's own XML is UTF-8 with a byte order mark; cp1251 here")
        out.append("    # leaves it with no strings at all, and no error either")
        out.append("    check('texts stub is utf-8 with BOM',")
        out.append("          body[:3], bytes([0xEF, 0xBB, 0xBF]))")
        continue
    if ln.strip().startswith("# the client's own XML is UTF-8"):
        continue
    if ln.strip().startswith("# it with no strings at all and no error"):
        continue
    out.append(ln)
io.open(p, "w", encoding="utf-8").write("\n".join(out))
import ast
ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
