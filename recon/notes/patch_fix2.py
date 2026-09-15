import io

# --- world.py: expose the avatar table -------------------------------------
w = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/world.py"
s = io.open(w, encoding="utf-8").read()
s += '''

def avatars():
    """The eight entries of avatars/list.xml as (id, sex) pairs.

    The two fields are not interchangeable and both have to come from the same
    entry. id picks the portrait, avatars/<id>_1.png. sex picks the body,
    because PersInfo.set sex assigns persType as a side effect and the walker
    resolves art as personages/<persType>. Mixing an id from one row with a sex
    from another puts a different person in the corner than the one standing in
    the location.
    """
    txt = _read(os.path.join(RES, "avatars", "list.xml"))
    return [(m.group(1), int(m.group(2)))
            for m in re.finditer(r"<a\s+id='([^']*)'\s+sex='(\d+)'", txt)]
'''
io.open(w, "w", encoding="utf-8").write(s)

# --- server.py -------------------------------------------------------------
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

old_res = '''# The avatar id must exist in avatars/list.xml, which holds only eight, and
# must also have a folder under res/personages or the body silently falls back
# to a different character than the portrait. Ids 0, 3, 131 and 133 satisfy
# both; the rest give a face that does not match the figure on screen.
START_RES = int(os.environ.get("LAVA_RES_ID", "0"))'''
new_res = '''# Portrait and body come from two different fields of the same avatars/list.xml
# row, and they must be taken together: res selects the portrait, sex selects
# the body. Row 0 is the one the creation screen offers first.
AVATARS = world.avatars()
START_AVATAR = int(os.environ.get("LAVA_AVATAR", "0"))'''
assert old_res in s
s = s.replace(old_res, new_res)

s = s.replace('MOB_TYPES = world.mob_types()',
              'MOB_TYPES = world.mob_types()\n\n\ndef default_character():\n'
              '    res, sex = AVATARS[START_AVATAR % len(AVATARS)]\n'
              '    return {"name": "polestvr", "sex": sex, "res": res}')

s = s.replace('        self.characters = [] if NEW_CHAR else [\n'
              '            {"name": "polestvr", "sex": 0, "res": START_RES}]',
              '        self.characters = [] if NEW_CHAR else [default_character()]')
s = s.replace('"res": p.get("res", START_RES)', '"res": p.get("res", AVATARS[0][0])')
s = s.replace('{"name": "Noname", "sex": 0, "res": START_RES}', 'default_character()')

# res is an avatar id, which may be non-numeric, so send it as a string
s = s.replace('                  res=pers["res"], ail=0, ally=1, lvl=1,',
              '                  res=Str(str(pers["res"])), ail=0, ally=1, lvl=1,')
s = s.replace('            self.send("persInfo", num=i, name=Str(pers["name"]),\n'
              '                      sex=pers["sex"], death=0, res=pers["res"])',
              '            self.send("persInfo", num=i, name=Str(pers["name"]),\n'
              '                      sex=pers["sex"], death=0,\n'
              '                      res=Str(str(pers["res"])))')

old_pop = '''        self.npcs.clear()
        for i, (cell, type_id) in enumerate(LOCATION.spawns):
            root, _name = MOB_TYPES.get(type_id, (world.MOB, ""))
            npc_id = FIRST_NPC_ID + i
            self.npcs[npc_id] = (cell, type_id, root)
            self.send("lch", newUser=npc_id, pos=cell, rtype=root)'''
new_pop = '''        self.npcs.clear()
        for i, (cell, type_id) in enumerate(LOCATION.spawns):
            root = MOB_TYPES.get(type_id, (world.MOB, "", ""))[0]
            self.npcs[FIRST_NPC_ID + i] = (cell, type_id, root)

        # Three passes, and the order is what makes them visible. A positioned
        # lch builds the figure immediately, and the figure resolves its art
        # from persType, which only userInfo supplies; place first and it asks
        # for mobs/undefined.xml once and never retries, leaving a placeholder.
        # An lch carrying refl registers the entity without a figure, so the
        # details can land before anything is drawn.
        for npc_id, (_cell, _type_id, root) in self.npcs.items():
            self.send("lch", newUser=npc_id, rtype=root, refl=1)
        for npc_id in self.npcs:
            self.send_npc_info(npc_id)
        for npc_id, (cell, _type_id, root) in self.npcs.items():
            self.send("lch", newUser=npc_id, pos=cell, rtype=root)'''
assert old_pop in s
s = s.replace(old_pop, new_pop)
io.open(p, "w", encoding="utf-8").write(s)

import ast
for f in (w, p):
    ast.parse(io.open(f, encoding="utf-8").read())
print("ok")
