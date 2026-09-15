import io, re
base = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/"

for name in ("test_world.py", "test_handshake.py"):
    p = base + name
    s = io.open(p, encoding="utf-8").read()
    # lift the account block above the env dict that uses it
    m = re.search(r"\n# A throwaway database per run.*?CRED = accounts\.credential\([^\n]*\)\n",
                  s, re.S)
    block = m.group(0)
    s = s.replace(block, "\n")
    s = s.replace("\nenv = dict(os.environ", block + "\nenv = dict(os.environ", 1)
    io.open(p, "w", encoding="utf-8").write(s)
    print(name, "ok")

# the landing page is a registration form now, not a Ruffle embed
p = base + "test_bootstrap.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace("""    check('index has ruffle', b"RufflePlayer" in get("/"), True)
    check('index passes logged=1', b'logged: "1"' in get("/"), True)""",
"""    page = get("/")
    check('landing page is the registration form',
          b'action="/register"' in page, True)
    check('landing page is utf-8', b'charset=utf-8' in page, True)""")
s = s.replace('''    check("index has ruffle", b"RufflePlayer" in get("/"), True)
    check("index passes logged=1", b'logged: "1"' in get("/"), True)''',
"""    page = get("/")
    check('landing page is the registration form',
          b'action="/register"' in page, True)
    check('landing page is utf-8', b'charset=utf-8' in page, True)""")
# loaduser no longer carries a digest
s = s.replace("""    check('parsed hash', h, 'devhash')""",
              """    # no digest here any more: the client computes its own from the password
    check('no digest handed out', h, None)""")
s = s.replace('''    check("parsed hash", h, "devhash")''',
              '''    # no digest here any more: the client computes its own from the password
    check("no digest handed out", h, None)''')
io.open(p, "w", encoding="utf-8").write(s)
print("test_bootstrap ok")
