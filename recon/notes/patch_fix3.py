import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

# 1. matched avatar pair
s = s.replace('''# The avatar id must exist in avatars/list.xml, which holds only eight, and
# must also have a folder under res/personages or the body silently falls back
# to a different character than the portrait. Ids 0, 3, 131 and 133 satisfy
# both; the rest give a face that does not match the figure on screen.
START_RES = int(os.environ.get("LAVA_RES_ID", "0"))''',
'''# Portrait and body come from two different fields of the same avatars/list.xml
# row and have to be taken together: res selects the portrait, sex selects the
# body, because PersInfo.set sex assigns persType as a side effect. Row 0 is
# the one the creation screen offers first.
AVATARS = world.avatars()
START_AVATAR = int(os.environ.get("LAVA_AVATAR", "0"))''')

s = s.replace('MOB_TYPES = world.mob_types()',
              'MOB_TYPES = world.mob_types()\n\n\n'
              'def default_character():\n'
              '    res, sex = AVATARS[START_AVATAR % len(AVATARS)]\n'
              '    return {"name": "polestvr", "sex": sex, "res": res}')

s = s.replace('        self.characters = [] if NEW_CHAR else [\n'
              '            {"name": "polestvr", "sex": 0, "res": START_RES}]',
              '        self.characters = [] if NEW_CHAR else [default_character()]')
s = s.replace('"res": p.get("res", START_RES)', '"res": p.get("res", AVATARS[0][0])')
s = s.replace('pers = self.active or {"name": "Noname", "sex": 0, "res": START_RES}',
              'pers = self.active or default_character()')
# avatar ids are not always numeric, so they travel as strings
s = s.replace('                      sex=pers["sex"], death=0, res=pers["res"])',
              '                      sex=pers["sex"], death=0,\n'
              '                      res=Str(str(pers["res"])))')
s = s.replace('                  res=pers["res"], ail=0, ally=1, lvl=1,',
              '                  res=Str(str(pers["res"])), ail=0, ally=1, lvl=1,')

# 2. three-pass placement
old = '''        self.npcs.clear()
        for i, (cell, type_id) in enumerate(LOCATION.spawns):
            root = MOB_TYPES.get(type_id, (world.MOB, "", ""))[0]
            npc_id = FIRST_NPC_ID + i
            self.npcs[npc_id] = (cell, type_id, root)
            self.send("lch", newUser=npc_id, pos=cell, rtype=root)'''
new = '''        self.npcs.clear()
        for i, (cell, type_id) in enumerate(LOCATION.spawns):
            root = MOB_TYPES.get(type_id, (world.MOB, "", ""))[0]
            self.npcs[FIRST_NPC_ID + i] = (cell, type_id, root)

        # Three passes, and the order is what makes them visible. A positioned
        # lch builds the figure at once, and the figure resolves its art from
        # persType, which only userInfo supplies. Place first and it asks for
        # mobs/undefined.xml once, never retries, and leaves a placeholder cone
        # standing there. An lch carrying refl registers the entity without a
        # figure, so the details can land before anything is drawn.
        for npc_id, (_cell, _type, root) in self.npcs.items():
            self.send("lch", newUser=npc_id, rtype=root, refl=1)
        for npc_id in self.npcs:
            self.send_npc_info(npc_id)
        for npc_id, (cell, _type, root) in self.npcs.items():
            self.send("lch", newUser=npc_id, pos=cell, rtype=root)'''
assert old in s, "populate anchor missing"
s = s.replace(old, new)

s = s.replace('''        The spawn points and their type ids come straight out of the location
        file; only behaviour was stripped. rtype tells the client which class
        to build, and it then asks for each one's details with getInfo type=1.
        """''',
'''        The spawn points and their type ids come straight out of the location
        file; only behaviour was stripped. rtype tells the client which class
        to build.
        """''')
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
