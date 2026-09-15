import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_bootstrap.py"
s = io.open(p, encoding="utf-8").read()
old = """    check('texts stub echoes ids', b'id=' + chr(34).encode() + b'12' + chr(34).encode() in body, True)"""
new = """    check('texts stub echoes ids', b"id='12'" in body, True)
    # the client's own XML is UTF-8 with a byte order mark; cp1251 here leaves
    # it with no strings at all and no error
    check('texts stub is utf-8 with BOM', body[:3], b'\xef\xbb\xbf')"""
assert old in s, "anchor missing"
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")
