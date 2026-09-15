import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/run.sh"
s = io.open(p, encoding="utf-8").read()
old = "    LAVA_HOST=0.0.0.0 LAVA_PORT=$GAME_PORT \\"
new = "    LAVA_RES='$RES_WSL' LAVA_HOST=0.0.0.0 LAVA_PORT=$GAME_PORT \\"
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
print("ok")
