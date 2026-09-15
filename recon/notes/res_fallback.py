import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/world.py"
s = io.open(p, encoding="utf-8").read()
old = 'RES = os.environ.get("LAVA_RES", r"C:\Users\gmkrt\OneDrive\Desktop\LAVA\res")'
new = ('# The servers run under WSL while the client lives on the Windows drive, so\n'
       '# fall back to the mounted path when the Windows one is not reachable.\n'
       'RES = os.environ.get("LAVA_RES") or ""\n'
       'if not os.path.isdir(RES):\n'
       '    for _candidate in (r"C:\Users\gmkrt\OneDrive\Desktop\LAVA\res",\n'
       '                       "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"):\n'
       '        if os.path.isdir(_candidate):\n'
       '            RES = _candidate\n'
       '            break')
assert old in s, "anchor missing"
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
