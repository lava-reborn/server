import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace('        self.pos = START_POS',
              '        self.pos = LOCATION.entry_cell()\n'
              '        # entity id -> (cell, type_id, rtype) for everything placed\n'
              '        self.npcs = {}')

s = s.replace('{"name": "polestvr", "sex": 0, "res": 1}',
              '{"name": "polestvr", "sex": 0, "res": START_RES}')
s = s.replace('"res": p.get("res", 1)', '"res": p.get("res", START_RES)')
s = s.replace('{"name": "Noname", "sex": 0, "res": 1}',
              '{"name": "Noname", "sex": 0, "res": START_RES}')

old = '''    def enter_location(self):
        # ie != 1 means the client must confirm with lenter;accept=1 once it
        # has finished loading the location's XML and artwork.
        self.send("lcall", id=START_LOC, ws=0, ie=0, g_id=START_LOC)

    def cmd_lenter(self, p):
        self.send("cmdAck", res=0)
        # aspd is the action-point gain per 600ms tick, amax the ceiling.
        self.send("lenter", pos=self.pos, aspd=1, amax=20)
'''
new = '''    def enter_location(self):
        # ie != 1 means the client must confirm with lenter;accept=1 once it
        # has finished loading the location's XML and artwork.
        self.send("lcall", id=LOCATION.id, ws=LOCATION.war, ie=0,
                  g_id=LOCATION.id)

    def cmd_lenter(self, p):
        self.send("cmdAck", res=0)
        # aspd is the action-point gain per 600ms tick, amax the ceiling.
        self.send("lenter", pos=self.pos, aspd=1, amax=20)
        self.populate()

    def populate(self):
        """Place the location's own inhabitants, one lch frame each.

        The spawn points and their type ids come straight out of the location
        file; only behaviour was stripped. rtype tells the client which class
        to build, and it then asks for each one's details with getInfo type=1.
        """
        self.npcs.clear()
        for i, (cell, type_id) in enumerate(LOCATION.spawns):
            root, _name = MOB_TYPES.get(type_id, (world.MOB, ""))
            npc_id = FIRST_NPC_ID + i
            self.npcs[npc_id] = (cell, type_id, root)
            self.send("lch", newUser=npc_id, pos=cell, rtype=root)
        log.info("  ..    placed %d inhabitants in %s",
                 len(self.npcs), LOCATION.title)
'''
assert old in s
s = s.replace(old, new)

old_gi = '''    def cmd_getInfo(self, p):
        if int(p.get("id", 0)) != 0:
            return
        pers = self.active or {"name": "Noname", "sex": 0, "res": START_RES}'''
new_gi = '''    def cmd_getInfo(self, p):
        who = int(p.get("id", 0))
        if who != 0:
            self.send_npc_info(who)
            return
        pers = self.active or {"name": "Noname", "sex": 0, "res": START_RES}'''
assert old_gi in s
s = s.replace(old_gi, new_gi)

# add the NPC info sender right after cmd_getInfo's usrUp line
anchor = '        self.send("usrUp", id=0, hcur=100, hmax=100, scur=100, smax=100)\n'
addition = anchor + '''
    def send_npc_info(self, npc_id):
        """Answer getInfo for one inhabitant.

        name is a numeric string id, not text: the client resolves it over HTTP
        against database/texts.xml. Passing the type id lets the stub there hand
        back the creature's internal name instead of a placeholder.

        ally must be truthy or every service this NPC offers is refused before
        a single frame is exchanged.
        """
        entry = self.npcs.get(npc_id)
        if not entry:
            return
        cell, type_id, root = entry
        cmd = world.USERINFO.get(root, "userInfo")
        params = dict(id=npc_id, name=type_id, sex=0, res=type_id, ail=0,
                      ally=1, lvl=1, rep=[0], bg_rep=0, bg_pen=0,
                      give_quests=[], take_quests=[], m_hello=[],
                      can_set_home=0, can_banking=0, can_trophy=0,
                      can_repair=0, can_trade=0)
        if root == world.TRADER:
            # An empty stock still opens the trade window; goods come later.
            params.update(can_trade=1, can_repair=1, type_list=[],
                          bg_objects=[], bg_obj_rep_req=[],
                          pmod=1, smod=1, rmod=1)
        elif root == world.UPGRADER:
            params.update(in_types=[], out_types=[], costs=[])
        elif root == world.LESSOR:
            params.update(give_transport=[])
        elif root == world.HEALER:
            params.update(a_price=10)
        elif root == world.COMMONER:
            params.update(can_set_home=1)
        self.send(cmd, **params)
'''
assert anchor in s
s = s.replace(anchor, addition, 1)
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
