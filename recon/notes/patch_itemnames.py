import io
BS = chr(92)

p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace("import accounts\nimport world", "import accounts\nimport items\nimport world")
old = '''try:
    MOB_NAMES = {t: n for t, (_r, n, _a) in world.mob_types().items()}
except Exception:
    MOB_NAMES = {}'''
new = '''try:
    MOB_NAMES = {t: n for t, (_r, n, _a) in world.mob_types().items()}
except Exception:
    MOB_NAMES = {}

# Items are numbered in the same string space as creatures, and the shop stays
# blank without them: Item.stringUpdate withholds the update event until a name
# arrives, and nothing enters a bag or a price list before that event.
try:
    ITEM_NAMES = {t: n for t, (_root, n) in items.catalogue().items()}
except Exception:
    ITEM_NAMES = {}'''
assert old in s
s = s.replace(old, new)
s = s.replace("% (i, REAL_NAMES.get(int(i)) or MOB_NAMES.get(int(i), \"#\" + i))",
              "% (i, REAL_NAMES.get(int(i)) or MOB_NAMES.get(int(i))\n"
              "               or ITEM_NAMES.get(int(i), \"#\" + i))")
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("имена предметов подключены")

r = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/run.sh"
lines = io.open(r, encoding="utf-8").read().split("\n")
out = []
for ln in lines:
    if ln.strip() == 'local exe="$ROOT/tools/flash/fp32_sa.exe"':
        out.append("  # The debug build reports runtime errors and writes trace output to")
        out.append("  # Logs/flashlog.txt, which is the only way to see a fault on the")
        out.append("  # client's side of the wire.")
        out.append('  local exe="$ROOT/tools/flash/fp32_sa.exe"')
        out.append('  [ "${LAVA_DEBUG:-0}" = "1" ] && exe="$ROOT/tools/flash/fp32_sa_debug.exe"')
        continue
    if 'echo "player      : Flash projector 32.0.0.465"' in ln:
        out.append('  echo "player      : Flash projector 32.0.0.465'
                   '${LAVA_DEBUG:+ (debug)}"')
        continue
    out.append(ln)
io.open(r, "w", encoding="utf-8").write("\n".join(out))
print("run.sh: добавлен отладочный режим")
