import io, re
base = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/"

p = base + "server/protocol.py"
s = io.open(p, encoding="utf-8").read()
old = 'ENCODING = "cp1251"'
new = ('# Flash decodes XMLSocket traffic as UTF-8 unless System.useCodepage is on,\n'
       '# and this client only sets that inside one rarely taken branch of its login\n'
       '# screen. The convertToCP1251 helper it carries belongs to MD5rus and is\n'
       '# only about what gets hashed, not what travels. Sending cp1251 here left\n'
       '# the client parsing a Cyrillic name into rubbish: the parser advances its\n'
       '# cursor by the character length of each string it reads, so a value that\n'
       '# decodes to a different length than it was written slides every field\n'
       '# after it out of place.\n'
       'ENCODING = "utf-8"')
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("protocol: сокет переведён на utf-8")

# tests and helpers that hardcoded the socket encoding
for name in ("server/test_protocol.py", "server/test_handshake.py",
             "server/test_world.py"):
    q = base + name
    s = io.open(q, encoding="utf-8").read()
    s = s.replace('ENC = "cp1251"', 'ENC = "utf-8"')
    s = s.replace('.encode("cp1251")', '.encode("utf-8")')
    s = s.replace('.decode("cp1251")', '.decode("utf-8")')
    s = s.replace('check("cp1251 frame"', 'check("utf-8 frame"')
    s = s.replace('check("cp1251 roundtrip"', 'check("utf-8 roundtrip"')
    io.open(q, "w", encoding="utf-8").write(s)
print("тесты обновлены")

p = base + "server/server.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('data[:-1].decode("cp1251", "replace")',
              'data[:-1].decode("utf-8", "replace")')
io.open(p, "w", encoding="utf-8").write(s)
print("лог сервера тоже")
