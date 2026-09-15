import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace('FIRST_NPC_ID = 100',
'''FIRST_NPC_ID = 100

# Where this location sits on the global map. Those coordinates are a plain
# grid, 5833..6305 by 1600..2110, and res/database/locations.xml labels 414 of
# its cells, so the client draws the settlement names by itself.
GLOBAL_X = float(os.environ.get("LAVA_GX", "5968"))
GLOBAL_Y = float(os.environ.get("LAVA_GY", "1727"))
VIEW_RADIUS = 8
TRAVEL_SPEED = 0.35   # cells per second''')

s = s.replace('''        self.active = None
        self.pos = LOCATION.entry_cell()''',
'''        self.active = None
        self.pos = LOCATION.entry_cell()
        self.on_map = False
        self.gx, self.gy = GLOBAL_X, GLOBAL_Y
        self.arrival = None''')

old = '''    def cmd_chWorld(self, p):
        self.send("cmdAck", res=0)'''
new = '''    def cmd_chWorld(self, p):
        """Leave for the global map, or drop back into the location.

        No "to" means the map. The client will not move a step there until the
        server answers, and it treats the frame as authoritative, so the reply
        carries the absolute position rather than a delta.
        """
        self.send("cmdAck", res=0)
        if p.get("to"):
            self.on_map = False
            self.enter_location()
        else:
            self.on_map = True
            self.send("gmap", x=self.gx, y=self.gy, v_rad=VIEW_RADIUS)

    def cmd_moveTo(self, p):
        if self.on_map:
            self.move_on_map(p)
        else:
            self.move_in_location(p)

    def move_on_map(self, p):
        """dx and dy are hundredths of a cell, measured from where we stand.

        moveAck only sets a velocity; the client extrapolates from its own
        position and never asks again, so arrival has to be timed here and
        confirmed with a userMove carrying zero speed.
        """
        if "trg" in p:
            return                      # intercepting a player: not implemented
        dx = float(p.get("dx", 0)) / 100.0
        dy = float(p.get("dy", 0)) / 100.0
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 0.01:
            return
        tx, ty = self.gx + dx, self.gy + dy
        vx, vy = dx / dist * TRAVEL_SPEED, dy / dist * TRAVEL_SPEED
        self.send("moveAck", vx=vx, vy=vy, t=0)

        if self.arrival:
            self.arrival.cancel()
        loop = asyncio.get_running_loop()
        self.arrival = loop.call_later(dist / TRAVEL_SPEED, self.arrive, tx, ty)

    def arrive(self, tx, ty):
        self.arrival = None
        self.gx, self.gy = tx, ty
        # zero speed is how the client is told to stop; it has no other signal
        self.send("userMove", id=0, dx=self.gx, dy=self.gy, vx=0, vy=0, t=0)
        if abs(self.gx - GLOBAL_X) < 0.5 and abs(self.gy - GLOBAL_Y) < 0.5:
            self.on_map = False
            self.enter_location()'''
assert old in s
s = s.replace(old, new)

# the old location-movement handler becomes the in-location branch
s = s.replace('''    def cmd_moveTo(self, p):
        """Echo the path back; the client renders no step until we do.''',
'''    def move_in_location(self, p):
        """Echo the path back; the client renders no step until we do.''')
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
