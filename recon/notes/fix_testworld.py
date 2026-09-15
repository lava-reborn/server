import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(p, encoding="utf-8").read()
old = 'env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1")'
new = ('# This test walks the character-creation path, so it needs the empty\n'
       '# roster; the server otherwise ships a ready character and auto-enters.\n'
       'env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",\n'
       '           LAVA_NEWCHAR="1")')
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("patched")
