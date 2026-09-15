import io
t = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(t, encoding="utf-8").read()
s = s.replace('"g_id=48908098;"', '"g_id=48907970;"')
io.open(t, "w", encoding="utf-8").write(s)
print("правильный g_id:", (5970 << 13) | 1730)
