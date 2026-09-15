import io
BS = chr(92)
WINPATH = BS.join(["C:", "Users", "gmkrt", "OneDrive", "Desktop", "LAVA", "res"])
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/world.py"
s = io.open(p, encoding="utf-8").read()
old = 'RES = os.environ.get("LAVA_RES", r"' + WINPATH + '")'
new = "\n".join([
    "# The servers run under WSL while the client lives on the Windows drive, so",
    "# fall back to the mounted path whenever the configured one is unreachable.",
    'RES = os.environ.get("LAVA_RES") or ""',
    "if not os.path.isdir(RES):",
    '    for _candidate in (r"' + WINPATH + '",',
    '                       "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"):',
    "        if os.path.isdir(_candidate):",
    "            RES = _candidate",
    "            break",
])
assert old in s, "anchor missing"
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
