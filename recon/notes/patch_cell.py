import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()
old = '''GLOBAL_X = int(os.environ.get("LAVA_GX", "5968"))
GLOBAL_Y = int(os.environ.get("LAVA_GY", "1727"))'''
new = '''# Cell 5970x1730, which the client's own map data describes as "Чёрный рынок:
# Торговцы оружием, снаряжением и патронами | Банк | Аренда транспорта |
# Покупка чертежей" - the weapon stalls, Аарон's bank and Шихаб's transport,
# which is exactly who stands in location 102.
GLOBAL_X = int(os.environ.get("LAVA_GX", "5970"))
GLOBAL_Y = int(os.environ.get("LAVA_GY", "1730"))'''
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("GEO_ID =", (5970 << 13) | 1730)

t = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(t, encoding="utf-8").read()
s = s.replace('"x=5968;y=1727;"', '"x=5970;y=1730;"')
s = s.replace('"g_id=48891583;"', '"g_id=48908098;"')
s = s.replace('"dx=5967;"', '"dx=5969;"')
io.open(t, "w", encoding="utf-8").write(s)
