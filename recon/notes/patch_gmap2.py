import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace('''        self.on_map = False
        self.gx, self.gy = GLOBAL_X, GLOBAL_Y
        self.arrival = None''',
'''        self.on_map = False
        self.gx, self.gy = GLOBAL_X, GLOBAL_Y
        self.arrival = None
        # a leg in flight: (start time, from x, from y, vx, vy)
        self.leg = None''')

old = '''        if "trg" in p:
            return                      # intercepting a player: not implemented
        dx = float(p.get("dx", 0)) / 100.0
        dy = float(p.get("dy", 0)) / 100.0'''
new = '''        if "trg" in p:
            return                      # intercepting a player: not implemented
        # Offsets are measured from where the player is standing right now, and
        # the client has been extrapolating since the last moveAck, so a stale
        # origin here sends them somewhere neither side expects.
        self.gx, self.gy = self.current_pos()
        dx = float(p.get("dx", 0)) / 100.0
        dy = float(p.get("dy", 0)) / 100.0'''
assert old in s
s = s.replace(old, new)

s = s.replace('''        self.send("moveAck", vx=vx, vy=vy, t=0)

        if self.arrival:
            self.arrival.cancel()
        loop = asyncio.get_running_loop()
        self.arrival = loop.call_later(dist / TRAVEL_SPEED, self.arrive, tx, ty)''',
'''        self.send("moveAck", vx=vx, vy=vy, t=0)

        loop = asyncio.get_running_loop()
        self.leg = (loop.time(), self.gx, self.gy, vx, vy)
        if self.arrival:
            self.arrival.cancel()
        self.arrival = loop.call_later(dist / TRAVEL_SPEED, self.arrive, tx, ty)

    def current_pos(self):
        """Where the player is now, matching the client's own extrapolation."""
        if not self.leg:
            return self.gx, self.gy
        started, sx, sy, vx, vy = self.leg
        dt = asyncio.get_running_loop().time() - started
        return sx + vx * dt, sy + vy * dt''')

s = s.replace('''    def arrive(self, tx, ty):
        self.arrival = None''',
'''    def arrive(self, tx, ty):
        self.arrival = None
        self.leg = None''')

s = s.replace('''    def cmd_logout(self, p):
        self.writer.close()''',
'''    def cmd_logout(self, p):
        self.close()

    def close(self):
        if self.arrival:
            self.arrival.cancel()
            self.arrival = None
        self.writer.close()''')

s = s.replace('''    finally:
        log.info("disconnect %s", peer)
        writer.close()''',
'''    finally:
        log.info("disconnect %s", peer)
        sess.close()''')
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
