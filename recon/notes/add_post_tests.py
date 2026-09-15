import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_bootstrap.py"
s = io.open(p, encoding="utf-8").read()
Q = chr(34)
block = [
    "",
    "    # The client loads every XML resource with LoadVars.sendAndLoad, i.e.",
    "    # over POST, so serving those paths on GET alone leaves it with 404s",
    "    # and no usable settings file.",
    "    def post(path, data=b''):",
    "        rq = urllib.request.Request(BASE + path, data=data, method='POST')",
    "        try:",
    "            r = urllib.request.urlopen(rq, timeout=10)",
    "            return r.status, r.read()",
    "        except urllib.error.HTTPError as e:",
    "            return e.code, b''",
    "",
    "    check('POST csettings', post('/res/xmldocs/csettings_v1.xml')[0], 200)",
    "    check('POST avatar list', post('/res/avatars/list.xml')[0], 200)",
    "    check('POST real file', post('/res/database/objects.xml')[0], 200)",
    "    check('POST missing file 404', post('/res/nope/nope.xml')[0], 404)",
    "",
    "    # base must be absolute and carry no trailing slash: the client builds",
    "    # every resource URL as base + '/avatars/list.xml'.",
    "    base_attr = re.search('base=' + chr(34) + '([^' + chr(34) + ']*)' + chr(34), cs).group(1)",
    "    check('base is absolute', base_attr.startswith('http://'), True)",
    "    check('base has no trailing slash', base_attr.endswith('/'), False)",
    "",
    "    # texts.xml is absent from the client; the stub must answer or items",
    "    # never reach the inventory.",
    "    code, body = post('/res/database/texts.xml', b'<data>12,34</data>')",
    "    check('texts stub answers', code, 200)",
    "    check('texts stub echoes ids', b'id=' + chr(34).encode() + b'12' + chr(34).encode() in body, True)",
    "",
]
s = s.replace("import os, subprocess, sys, time, urllib.request, urllib.error",
              "import os, re, subprocess, sys, time, urllib.request, urllib.error")
s = s.replace("    # 3. real client assets must come through",
              chr(10).join(block) + "    # 3. real client assets must come through")
io.open(p, "w", encoding="utf-8").write(s)
print("tests added")
