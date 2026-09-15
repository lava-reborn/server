import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace('''GLOBAL_X = float(os.environ.get("LAVA_GX", "5968"))
GLOBAL_Y = float(os.environ.get("LAVA_GY", "1727"))
VIEW_RADIUS = 8
TRAVEL_SPEED = 0.35   # cells per second''',
'''GLOBAL_X = int(os.environ.get("LAVA_GX", "5968"))
GLOBAL_Y = int(os.environ.get("LAVA_GY", "1727"))
VIEW_RADIUS = 8
TRAVEL_SPEED = 0.35   # cells per second

# lcall carries the map cell packed into g_id, which the client unpacks with
# LocIdToCoordinate: x in bits 13..25, y in bits 0..12, z above bit 26. Sending
# the location's own file number there, as if the two were the same, puts the
# settlement in the wrong place on the map.
GEO_ID = (GLOBAL_X << 13) | GLOBAL_Y''')

s = s.replace('''        self.send("lcall", id=LOCATION.id, ws=LOCATION.war, ie=0,
                  g_id=LOCATION.id)''',
              '''        self.send("lcall", id=LOCATION.id, ws=LOCATION.war, ie=0,
                  g_id=GEO_ID)''')

old = '''        self.send("cmdAck", res=0)
        if p.get("to"):
            self.on_map = False
            self.enter_location()
        else:
            self.on_map = True
            self.send("gmap", x=self.gx, y=self.gy, v_rad=VIEW_RADIUS)'''
new = '''        self.send("cmdAck", res=0)
        if self.on_map:
            # Standing on the settlement's own cell is what lets you in; the
            # client offers no separate command for it.
            if self.at_settlement():
                self.on_map = False
                self.enter_location()
            else:
                self.send("gmap", x=self.gx, y=self.gy, v_rad=VIEW_RADIUS)
        else:
            self.on_map = True
            self.gx, self.gy = GLOBAL_X, GLOBAL_Y
            self.send("gmap", x=self.gx, y=self.gy, v_rad=VIEW_RADIUS)

    def at_settlement(self):
        x, y = self.current_pos()
        return abs(x - GLOBAL_X) < 0.5 and abs(y - GLOBAL_Y) < 0.5'''
assert old in s
s = s.replace(old, new)

s = s.replace('''        if abs(self.gx - GLOBAL_X) < 0.5 and abs(self.gy - GLOBAL_Y) < 0.5:
            self.on_map = False
            self.enter_location()''',
'''        # Arriving back on the settlement drops the player straight into it,
        # which is what the original did and saves a second keypress.
        if self.at_settlement():
            self.on_map = False
            self.enter_location()''')

s = s.replace('''    def cmd_chWorld(self, p):
        """Leave for the global map, or drop back into the location.

        No "to" means the map. The client will not move a step there until the
        server answers, and it treats the frame as authoritative, so the reply
        carries the absolute position rather than a delta.
        """''',
'''    def cmd_chWorld(self, p):
        """One command, both directions: the button is a toggle.

        GlobalMapInterface.toLocation and LocationInterface both call
        changeWorld with no argument, so which way the player goes is decided
        here, from where they currently are.
        """''')
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok, GEO_ID =", (5968 << 13) | 1727)
