import io
base = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/"

p = base + "items.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('_CATALOGUE = None',
'''# Creatures and items are numbered in separate spaces that overlap, while the
# strings they point at share one. The real texts.xml gave each its own string
# id; this offset keeps the stub's synthetic ones apart, so item 4380 no longer
# answers with the name of the creature that happens to share the number.
STRING_ID_OFFSET = 1000000

_CATALOGUE = None''')
s = s.replace("        name=type_id,          # a string id; the texts endpoint resolves it",
              "        name=STRING_ID_OFFSET + type_id,   # string id, not the item id")
io.open(p, "w", encoding="utf-8").write(s)

p = base + "bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace("    ITEM_NAMES = {t: n for t, (_root, n) in items.catalogue().items()}",
              "    ITEM_NAMES = {items.STRING_ID_OFFSET + t: n\n"
              "                  for t, (_root, n) in items.catalogue().items()}")
io.open(p, "w", encoding="utf-8").write(s)
import ast
for f in (base + "items.py", base + "bootstrap_http.py"):
    ast.parse(io.open(f, encoding="utf-8").read())
print("ok")
