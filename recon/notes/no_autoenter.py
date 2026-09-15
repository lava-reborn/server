import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

old = '''        # Arriving back on the settlement drops the player straight into it,
        # which is what the original did and saves a second keypress.
        if self.at_settlement():
            self.on_map = False
            self.enter_location()'''
new = '''        # Deliberately no automatic entry here. Settlements occupy a whole
        # cell, so any short hop near one landed inside it and the map became
        # impossible to stay on. Going in is the button's job.'''
assert old in s
s = s.replace(old, new)

s = s.replace('''            self.on_map = True
            self.gx, self.gy = GLOBAL_X, GLOBAL_Y
            self.send("gmap", x=self.gx, y=self.gy, v_rad=VIEW_RADIUS)''',
'''            self.on_map = True
            self.gx, self.gy = GLOBAL_X, GLOBAL_Y
            self.cancel_travel()
            self.send("gmap", x=self.gx, y=self.gy, v_rad=VIEW_RADIUS)''')

s = s.replace('''            if self.at_settlement():
                self.on_map = False
                self.enter_location()''',
'''            if self.at_settlement():
                self.on_map = False
                self.cancel_travel()
                self.enter_location()''')

s = s.replace('''    def at_settlement(self):''',
'''    def cancel_travel(self):
        """Drop any leg in flight, so the position stops extrapolating."""
        if self.arrival:
            self.arrival.cancel()
            self.arrival = None
        self.leg = None

    def at_settlement(self):''')

s = s.replace('''    def close(self):
        if self.arrival:
            self.arrival.cancel()
            self.arrival = None
        self.writer.close()''',
'''    def close(self):
        self.cancel_travel()
        self.writer.close()''')
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
