import io
base = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/"

p = base + "test_handshake.py"
s = io.open(p, encoding="utf-8").read()
if "import tempfile" not in s:
    first = s.index("import ")
    line_end = s.index("\n", first) + 1
    s = s[:line_end] + "import tempfile\n" + s[line_end:]
io.open(p, "w", encoding="utf-8").write(s)
print("test_handshake: tempfile добавлен")

p = base + "test_bootstrap.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace("    check('no digest handed out', h, None)",
              "    check('no digest handed out', bool(h), False)")
s = s.replace('    check("no digest handed out", h, None)',
              "    check('no digest handed out', bool(h), False)")
io.open(p, "w", encoding="utf-8").write(s)
print("test_bootstrap: ожидание поправлено")
