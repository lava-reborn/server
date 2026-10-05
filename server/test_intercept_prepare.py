"""Fifteen seconds of interception immunity, then an automatic player duel.

Real Sessions and room combat, with time controlled at the deadline. The
live timer is also exercised by test_two_clients. Location.prepare and
Player.prepare in the original client require time=remaining+2, then zero
to clear the stored preparation flag. No player or mob, including a stray
bullet, may damage either participant during those fifteen seconds.
"""
import asyncio
import os
import random
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["LAVA_DB"] = os.path.join(tempfile.mkdtemp(), "prepare.db")
os.environ["LAVA_ENCOUNTER_CHANCE"] = "0"
sys.path.insert(0, HERE)
import server  # noqa: E402
import combat  # noqa: E402
import mobs  # noqa: E402
from protocol import decode  # noqa: E402
from testkit import check, fails  # noqa: E402


class Writer:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        pass


def frames(sess, name):
    return [p for n, p in sess.writer.frames if n == name]


def make_player(name):
    server.STORE.register(name, "secret")
    sess = server.Session(Writer(), name)
    sess.cmd_login({"hash": server.accounts.credential(name, "secret")})
    sess.cmd_newPers(dict(res=1, sex=0, name=name))
    sess.cmd_actPlayer({})
    return sess


# --- placement, in process ------------------------------------------------
def placement_checks():
    rng = random.Random(731)
    for x in range(5992, 5996):
        loc = server.world.location(server.world.location_at(x, 1760))
        room = server.ROOMS.get(server.travel.room_key(loc, x, 1760))
        reserved = set(combat.interception_positions(room, rng=rng))
        forbidden = set(loc.obstacles) | set(server.travel.exit_sides(loc)) | reserved
        forbidden.update(n.cell for n in room.npcs.values())
        pairs = [combat.interception_positions(room, reserved, rng) for _ in range(12)]
        check(loc.file + ": random starts avoid occupied cells and exits, at 8..15 hexes",
              all(pair is not None and not (set(pair) & forbidden)
                  and 8 <= mobs.hex_distance(*pair, loc.width) <= 15 for pair in pairs), True)
        check(loc.file + ": both starts are connected by a walk of at most fifteen steps",
              all((path := mobs.find_path(loc, a, lambda c, b=b: c == b,
                                         blocked=forbidden, limit=loc.width * loc.height))
                  and len(path) <= 16 for a, b in pairs), True)
    # No suitable pair in disconnected little islands, even though they
    # are at the requested geometric distance across an impassable wall.
    loc = SimpleNamespace(width=20, height=1, obstacles=set(range(20)) - {0, 12})
    room = SimpleNamespace(loc=loc, players={}, npcs={}, combat=None)
    with patch.object(server.travel, "exit_sides", return_value={}), \
            patch.object(server.travel, "walk_ins", return_value=[]):
        check("disconnected spawn islands never become an unreachable duel",
              combat.interception_positions(room, rng=rng), None)
        loc.width, loc.height, loc.obstacles = 40, 40, set()
        class StartAt(random.Random):
            def __init__(self, start):
                super().__init__(731)
                self.start = start

            def shuffle(self, cells):
                cells.remove(self.start)
                cells.insert(0, self.start)
        starts = [5*40+5, 5*40+35, 35*40+5, 35*40+35, 20*40+20]
        check("the center and every side can be the interception's starting area",
              [combat.interception_positions(room, rng=StartAt(c))[0] for c in starts], starts)


# --- preparation and immunity, real Sessions in process --------------------
async def main():
    a, b, c = [make_player(n) for n in ("PrepA", "PrepB", "PrepC")]
    clock = [100.0]
    try:
        with patch.object(combat, "now", lambda: clock[0]):
            for s in (a, b):
                s.on_map = True
                s.gx, s.gy = 5992, 1760
            a.caught(b, 5992, 1760)
            check("a real map catch assigns distinct positions 8..15 hexes apart",
                  8 <= mobs.hex_distance(a.pos, b.pos, a.loc.width) <= 15, True)
            grace = a.combat.interception
            check("both participants share one preparation at interception",
                  grace is not None and b.combat.interception is grace, True)
            a.cmd_lenter({})
            check("the assigned position is sent in the load handshake",
                  frames(a, "lenter")[-1]["pos"], a.pos)
            check("15 visible seconds compensate the client's subtraction of two",
                  frames(a, "prepare")[-1], {"id": 0, "time": 17})
            clock[0] += 3
            b.cmd_lenter({})
            check("a client loading three seconds later gets twelve seconds, not fifteen",
                  frames(b, "prepare")[-1], {"id": 0, "time": 14})
            c.gx, c.gy = a.gx, a.gy
            c.go_to(a.loc.id)
            c.cmd_lenter({})
            check("a third arrival sees both protected figures with the remaining time",
                  {(p["id"], p["time"]) for p in frames(c, "prepare")},
                  {(a.pid, 14), (b.pid, 14)})
            rc = a.combat.rc
            # Three adjacent cells on an unobstructed row for deterministic shots.
            base = next(i for i in range(a.loc.width * 3, a.loc.width * 4 - 3)
                        if not any(j in a.loc.obstacles for j in (i, i+1, i+2)))
            c.pos, a.pos, b.pos = base, base + 1, base + 2
            before = [s.character().vitals().copy() for s in (a, b)]
            for attacker, target in ((a, b), (b, a), (c, a), (c, b)):
                attacker.writer.frames.clear()
                attacker.combat.use_fire(dict(obj="0", target="1%08x" % target.pid))
                check("preparation refuses attacks exactly once (%s to %s)" %
                      (attacker.nick, target.nick),
                      frames(attacker, "cmdAck"), [{"res": server.inventory.RES_NOT_READY}])
            a.writer.frames.clear()
            a.cmd_chWorld({})
            check("preparation cannot be escaped through the map button",
                  (a.on_map, frames(a, "cmdAck")),
                  (False, [{"res": combat.RES_NO_LEAVE}]))
            check("mob acquisition ignores both protected players",
                  rc.nearest_fighter(a.pos, 1000) is c.combat, True)
            mob = mobs.Mob(999, 82, base)
            rc.aggro(mob, a.combat)
            check("direct mob aggro cannot bypass preparation", mob.target, None)
            rc.mob_strike(mob, a.combat)
            gun = combat.Weapon(num_shots=1, dmin=10, dmax=10,
                                opt_lo=0, opt_hi=10, max_range=10,
                                piercing=1, cone=0, crit=0, skill=None, spec=None)
            with patch.object(combat, "bullet_offset", return_value=0):
                for shooter in (c.combat, mob):
                    rc.burst(shooter, a.combat, a.pos, gun, 1)
                    rc.burst(shooter, None, b.pos, gun, 1)
            check("melee, aimed bullets and stray bullets from players and mobs do no harm",
                  [s.character().vitals() for s in (a, b)], before)
            check("protected players are not incidental bullet bodies",
                  list(rc.bodies(c.combat, None, gun)), [])
            clock[0] = 114.999
            grace.finish()  # Even an early callback must not remove protection.
            check("both remain protected until all fifteen seconds pass",
                  (a.combat.preparing(), b.combat.preparing(), rc.room.ws),
                  (True, True, False))
            clock[0] = 115
            for s in (a, b):
                s.writer.frames.clear()
            grace.finish()
            check("at fifteen seconds the duel starts without a hit",
                  (rc.room.ws, a.combat.foes, b.combat.foes, rc.hostilities(clock[0])),
                  (True, {b.pid}, {a.pid}, True))
            check("the client preparation flag is cleared on both sides",
                  [frames(s, "prepare") for s in (a, b)],
                  [[{"id": 0, "time": 0}, {"id": b.pid, "time": 0}],
                   [{"id": a.pid, "time": 0}, {"id": 0, "time": 0}]])
            with patch.object(combat, "bullet_offset", return_value=0):
                rc.burst(c.combat, a.combat, a.pos, gun, 1)
            check("after preparation an ordinary shot can damage a participant",
                  a.character().vitals()["hcur"] < before[0]["hcur"], True)

            # A slow loader does not restart the deadline or receive an
            # enemy id before its room snapshot has introduced that player.
            for s in (a, b):
                s.leave_room()
            clock[0] = 200
            combat.prepare_interception(a.combat, b.combat)
            grace = a.combat.interception
            a.cmd_lenter({})
            clock[0] = 215
            grace.finish()
            b.cmd_lenter({})
            check("a loader arriving after the deadline joins the duel immediately",
                  (a.combat.interception, b.combat.interception,
                   a.combat.foes, b.combat.foes), (None, None, {b.pid}, {a.pid}))

            clock[0] = 300
            combat.prepare_interception(a.combat, b.combat)
            grace = a.combat.interception
            b.close()
            check("disconnect cancels the shared callback and leaves no stale immunity",
                  (grace.timer, a.combat.interception, b.combat.interception),
                  (None, None, None))
            a.go_to(102)
            combat.prepare_interception(a.combat, c.combat)
            check("peaceful locations never arm preparation or an automatic duel",
                  a.combat.interception, None)
    finally:
        for sess in (a, b, c):
            sess.close()


try:
    placement_checks()
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("interception preparation crashed:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("intercept preparation OK")
