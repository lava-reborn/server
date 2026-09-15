import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_protocol.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('print()\nif fails:',
'''# --- regression: a protocol param literally named "name" (ah_search) ---
check("param called name",
      encode("ah_search", name=Str("gun"), page=1),
      "ah_search;name=@gun@;page=1;")
check("param name roundtrip",
      decode(encode("ah_search", name=Str("gun"), page=1)),
      ("ah_search", {"name": "gun", "page": 1}))

print()
if fails:''')
io.open(p, "w", encoding="utf-8").write(s)
print("test patched")
