import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()
old = '''        for npc_id, (cell, _type, root) in self.npcs.items():
            self.send("lch", newUser=npc_id, pos=cell, rtype=root, refl=1)
        for npc_id in self.npcs:
            self.send_npc_info(npc_id)
        for npc_id, (cell, _type, root) in self.npcs.items():
            self.send("lch", newUser=npc_id, pos=cell, rtype=root)'''
new = '''        for npc_id, (cell, _type, root) in self.npcs.items():
            self.send("lch", newUser=npc_id, pos=cell, rtype=root)
            self.send_npc_info(npc_id)'''
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")
