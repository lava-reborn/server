import io

w = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/world.py"
s = io.open(w, encoding="utf-8").read()
old = '''    def entry_cell(self):
        """First entry cell that is not also an obstacle."""
        for c in self.entries:
            if c not in self.obstacles:
                return c
        return self.entries[0] if self.entries else 0'''
new = '''    def entry_cell(self):
        """A free entry cell, preferring one near whoever lives here.

        inzones usually rings the whole map, and its first cell tends to sit in
        a far corner with nothing around it. Spawning beside the inhabitants
        makes the location look inhabited the moment it opens.
        """
        free = [c for c in self.entries if c not in self.obstacles]
        if not free:
            return self.entries[0] if self.entries else 0
        if not self.spawns:
            return free[0]
        cx = sum(c % self.width for c, _t in self.spawns) / len(self.spawns)
        cy = sum(c // self.width for c, _t in self.spawns) / len(self.spawns)
        return min(free, key=lambda c: (c % self.width - cx) ** 2
                                       + (c // self.width - cy) ** 2)'''
assert old in s
io.open(w, "w", encoding="utf-8").write(s.replace(old, new))

p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()
old2 = '''        # figure, so the details can land before anything is drawn.
        for npc_id, (_cell, _type, root) in self.npcs.items():
            self.send("lch", newUser=npc_id, rtype=root, refl=1)'''
new2 = '''        # figure, so the details can land before anything is drawn. The refl
        # frame still has to carry pos: Location.lch ignores the whole frame
        # unless newUser, pos and rtype are all present, refl or not.
        for npc_id, (cell, _type, root) in self.npcs.items():
            self.send("lch", newUser=npc_id, pos=cell, rtype=root, refl=1)'''
assert old2 in s
io.open(p, "w", encoding="utf-8").write(s.replace(old2, new2))

import ast
for f in (w, p):
    ast.parse(io.open(f, encoding="utf-8").read())
print("ok")
