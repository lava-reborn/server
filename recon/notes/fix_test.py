import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_bootstrap.py"
s = io.open(p, encoding="utf-8").read()
old = '''    check("traversal blocked",
          urllib.request.urlopen(BASE + "/res/../../../windows/win.ini").status
          if False else True, True)
'''
new = '''    # directory traversal must not escape the res root
    traversal_code = None
    try:
        urllib.request.urlopen(BASE + "/res/%2e%2e/%2e%2e/settings.db", timeout=5)
        traversal_code = 200
    except urllib.error.HTTPError as e:
        traversal_code = e.code
    check("traversal blocked", traversal_code, 404)
'''
assert old in s, "anchor not found"
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
print("fixed")
