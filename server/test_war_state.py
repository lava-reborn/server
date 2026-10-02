"""The fight is over when nothing is after anybody, and the door opens then.

The owner's complaint: in a location where nothing was aggroed any more, the
creature that had been attacking was killed -- and the fight still hung over
the location, and there was no way out. It has to hang only while a mob has
actually taken somebody here as its target.

The door is the client's before it is the server's. While the room is at
war (lch;ws=1) LocationInterface.battleMode greys the exit button and
toGlobal sends nothing, whatever the server would say to a chWorld; and the
exit cells' window is shut by the countdown every faHit/caHit of the player's
starts (startExitTimer), which only lch;ws=0 cancels (deleteTimerLeaveLocation).
So "the way out is open" means two things here: the last war state the client
heard is 0, and chWorld is then accepted. The server used to keep the room
at war for leave_combat_timeout (30 s) after anybody's last shot or blow,
and the first of the two was simply not true for half a minute after every
fight. (While a creature is still after the player, the war goes on and the
map button stays grey; the exit window of a zone cell opens by the timer
alone -- test_aggro_hold.)

In process: the rule itself (RoomCombat.kill, calm, after_hostile, _step),
on a room with no sockets. On a socket: location 100, the dump, where a dog
and a bum stand four hexes apart. The player walks into reach of both, lets
them come, kills the dog while the bum is still after him -- the war holds
and the door stays shut -- and then the bum, the last one: peace in the same
breath, and the way out.
"""
import asyncio
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

sys.path.insert(0, HERE)
import accounts      # noqa: E402
import combat        # noqa: E402
import inventory     # noqa: E402
import mobs          # noqa: E402
import progression   # noqa: E402
import rooms         # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

DUMP = 100
DOG_HOME, BUM_HOME = 4551, 4363       # mStarvingDog_lvl1 and m05_bich
DOG, BUM, BOX = 82, 411, 409          # the types
KNIFE = 6229                          # knife_lvl1_A, a stall's first blade

from testkit import check, fails  # noqa: E402


# --- the rule, in process -------------------------------------------------------
class _Room(object):
    """A room with nobody on a socket: what is broadcast is kept."""

    def __init__(self):
        self.loc = world.location(DUMP)
        self.npcs = {}
        self.players = {}
        self.ws = False
        self.sent = []

    def broadcast(self, frame, exclude=None):
        self.sent.append(frame)


class _Seat(object):
    """Just enough of a session for a Fighter standing in the room."""
    char_id = 0
    on_map = False
    inv = type("Inv", (), {"store": None})()

    def __init__(self, room, pos, char_id):
        self.room, self.pos, self.pid = room, pos, rooms.player_id(char_id)
        self.sent = []
        self.char = progression.Character()
        self.combat = combat.Fighter(self)
        self.combat.regen_at = float("inf")
        room.players[self] = None

    def send(self, *cmd, **params):
        self.sent.append((cmd[0], params))

    def character(self):
        return self.char


def _scene():
    room = _Room()
    room.combat = rc = combat.RoomCombat(room, None)
    # Far from both spawns: nothing may pick the player up by itself.
    seat = _Seat(room, room.loc.entry_cell() + 40 * room.loc.width, 1)
    return room, rc, seat


def _mob(rc, eid, type_id, cell):
    rc.mobs[eid] = mobs.Mob(eid, type_id, cell)
    return rc.mobs[eid]


def _ws(room):
    return [p["ws"] for n, p in room.sent if n == "lch" and "ws" in p]


async def _rule():
    # The last creature after anybody dies: lch;ws=0 in the same breath as
    # its lch;dead, not a tick later.
    room, rc, seat = _scene()
    dog = _mob(rc, 1, DOG, DOG_HOME)
    rc.aggro(dog, seat.combat)
    room.sent = []
    rc.kill(dog, None)
    check("the last hunter down: lch;ws=0 right behind its lch;dead, from kill() itself",
          [p for n, p in room.sent if n == "lch"], [{"dead": 1}, {"ws": 0}])

    # Another is still after somebody: the war goes on, and so does the hold.
    room, rc, seat = _scene()
    dog, bum = _mob(rc, 1, DOG, DOG_HOME), _mob(rc, 2, BUM, BUM_HOME)
    rc.aggro(dog, seat.combat)
    rc.aggro(bum, seat.combat)
    # The blow that fells the dog is a hit, and the exit timer runs from it.
    seat.combat.last_hit = combat.now()
    room.sent = []
    rc.kill(dog, None)
    check("one of two down: no ws=0 while the other is after the player, and the"
          " exit timer still runs",
          (_ws(room), room.ws, seat.combat.in_combat()), ([], True, True))
    rc.kill(bum, None)
    check("the second down: peace, and with it the timer: the player is free to go",
          (_ws(room), room.ws, seat.combat.in_combat()), ([0], False, False))

    # A creature holds on to its target for as long as he is here: nothing
    # it has failed to do about him lets the room go (the owner's rule,
    # 2026-09-25). It used to give up after mobs.GIVE_UP seconds of not
    # getting at him; a tick a minute on keeps the war.
    room, rc, seat = _scene()
    dog = _mob(rc, 1, DOG, DOG_HOME)
    rc.aggro(dog, seat.combat)
    dog.pressed = combat.now() - 60     # the old clock, for the code before the rule
    dog.next_attack = 0.0               # ready to think, not waiting on a swing
    room.sent = []
    rc._step()
    check("a creature that has not got at its target for a minute keeps it, and the war",
          (dog.target is seat.combat, _ws(room), room.ws), (True, [], True))

    # A box cannot fight back, so it takes nobody as its target: shot at, it
    # neither paints itself red nor holds the room. A dog shot at does both.
    room, rc, seat = _scene()
    box = _mob(rc, 3, BOX, DOG_HOME + 2)
    rc.after_hostile(seat.combat, box)
    check("a box shot at turns on nobody and holds nothing",
          (box.target, seat.sent, _ws(room), rc.hostilities(combat.now())),
          (None, [], [], False))
    dog = _mob(rc, 1, DOG, DOG_HOME)
    rc.after_hostile(seat.combat, dog)
    check("a dog shot at turns on its shooter and the room goes to war",
          (dog.target is seat.combat, seat.sent, _ws(room)),
          (True, [("lch", {"enemy": 1})], [1]))


check("a box is an object and cannot fight back", mobs.stats(BOX).can_attack, False)
asyncio.run(_rule())


# --- the server -------------------------------------------------------------------
# The exit timer is the game's own thirty seconds, said out loud so that no
# environment shortens the very tail this suite exists to catch. Nothing
# respawns for the length of the scene, the AP bar never throttles, and the
# dice are seeded.
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "war.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("wanderer", "secret")
_store.close()
CRED = accounts.credential("wanderer", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730",
           LAVA_LEAVE_COMBAT="30", LAVA_RESPAWN="600",
           LAVA_AP_REGEN="25", LAVA_SEED="7")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


def connect(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return socket.create_connection(("127.0.0.1", PORT), 0.5)
        except OSError:
            time.sleep(0.1)
    raise SystemExit("server did not start")


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""
        self.seen = []            # every frame this client was ever handed

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def _recv(self, timeout):
        self.s.settimeout(max(0.01, timeout))
        try:
            chunk = self.s.recv(65536)
        except socket.timeout:
            return False
        if not chunk:
            return False
        self.buf += chunk
        return True

    def _drain(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        out = [decode(f.decode(ENC)) for f in parts if f]
        self.seen += out
        return out

    def frames(self, wait=0.5):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._drain()

    def until(self, pred, wait=3.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._drain()
            out += new
            if any(pred(f) for f in new):
                break
        return out

    def ws(self):
        """The war-state edges this client has heard, in order; the last one
        is what its exit button shows."""
        return [p["ws"] for n, p in self.seen if n == "lch" and "ws" in p]


def named(frames, name):
    return [p for n, p in frames if n == name]


def entity(eid):
    return "x1%08x" % eid


def login(c, first=False):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@wanderer@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    got = c.frames(2)
    return got, named(got, "lenter")[0]["pos"]


def cell_of(c, mob, home):
    """Where a mob's walks have left it: the end of its last userMove."""
    for n, p in reversed(c.seen):
        if n == "userMove" and p.get("id") == mob:
            return p["path"][-1]
    return home


try:
    # --- a character with a blade and the hand to use it -----------------------------
    # Ближний бой 20 so the blows land and the scene stays short; the kit's
    # gun goes to the bag and a stall's knife into the hand.
    c = Client(connect())
    login(c, first=True)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    store = accounts.Store(DB)
    char_id = store.character_by_name("wanderer")["id"]
    ch = progression.Character.load(store, char_id)
    ch.skill[progression.MELEE] = [20, 0, progression.skill_xp_max(20)]
    ch.recalc()
    ch.hp = ch.sp = None
    ch.save(store)
    for row in store.items_of(char_id):
        if row["slot"] == inventory.PRIMARY:
            store.update_item(row["uniq"], slot=inventory.BAG)
    fields = inventory.new_fields(KNIFE)
    root = fields.pop("root")
    fields["slot"] = inventory.PRIMARY
    knife = inventory.oid_of(store.create_item(char_id, KNIFE, root, **fields))
    store.close()

    c = Client(connect())
    login(c)
    c.send("userMsg;entry=@/goto %d@;group=0;" % DUMP)
    lcall = named(c.until(lambda f: f[0] == "lcall"), "lcall")[0]
    check("the dump is entered at peace", (lcall["id"], lcall["ws"]), (DUMP, 0))
    c.send("lenter;accept=1;")
    arrival = c.frames(2)
    pos = named(arrival, "lenter")[0]["pos"]
    spawns = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    dog, bum = spawns[DOG_HOME], spawns[BUM_HOME]

    # --- into reach of the two, and of nothing else --------------------------------------
    loc = world.location(DUMP)
    W = loc.width
    others = [(cell, mobs.stats(t)) for cell, t in loc.spawns
              if cell not in (DOG_HOME, BUM_HOME) and mobs.stats(t).can_attack]
    spot = lambda cell: (
        mobs.hex_distance(cell, DOG_HOME, W) <= mobs.stats(DOG).aggro - 0.5
        and mobs.hex_distance(cell, BUM_HOME, W) <= mobs.stats(BUM).aggro - 0.5
        and all(mobs.hex_distance(cell, o, W) > st.aggro + 1.5 for o, st in others))
    path = mobs.find_path(loc, pos, spot, {DOG_HOME, BUM_HOME})
    check("there is a cell within reach of the dog and the bum only", path is not None, True)
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    pos = path[-1]
    enemies = lambda: {p["enemy"] for p in named(c.seen, "lch") if "enemy" in p}
    c.until(lambda f: enemies() >= {dog, bum}, 6)
    check("both come for the player: each is painted an enemy, the room goes to war",
          (sorted(enemies()), c.ws()), (sorted([dog, bum]), [1]))
    # The dog is "the attacking mob" of the complaint: it is let bite first.
    bit = lambda: [p for n, p in c.seen if n in ("caHit", "caMiss") and p.get("id") == dog]
    c.until(lambda f: bit() != [], 10)
    check("the dog attacks", bit() != [], True)
    homes = {dog: DOG_HOME, bum: BUM_HOME}

    def fight(target):
        """Knife blows at one creature until it falls; the frames of the
        blow that felled it, or None."""
        for attempt in range(80):
            if mobs.adjacent(pos, cell_of(c, target, homes[target]), loc):
                c.send("ss_use;type=16;obj=x%s;target=%s;" % (knife, entity(target)))
                got = c.until(lambda f: f[0] == "c_ap"
                              or (f[0] == "cmdAck" and f[1]["res"] != 0), 3)
                got += c.frames(0.2)
            else:
                got = c.frames(0.4)
            if [p for n, p in got if n == "lch" and p.get("dead") == target]:
                return got
        return None

    # --- the dog falls; the bum is still after the player ------------------------------
    got = fight(dog)
    check("the dog dies to the knife", got is not None, True)
    c.frames(1.0)                        # more than two of the room's ticks
    check("with the bum still after him the room stays at war", c.ws(), [1])
    # And the blow that felled the dog started the exit timer, thirty
    # seconds of it, which the war keeps running.
    c.send("chWorld;")
    got = c.frames(0.5)
    check("and the way out stays shut: res=39, no gmap",
          [(n, p.get("res")) for n, p in got if n in ("cmdAck", "gmap", "lcall")],
          [("cmdAck", 39)])

    # --- the bum falls: nothing is after anybody, and the fight is over ----------------
    got = fight(bum)
    check("the bum dies to the knife", got is not None, True)
    check("the war ends with the blow that felled the last hunter, not 30 s later",
          [p for n, p in got if n == "lch" and "ws" in p], [{"ws": 0}])
    check("so the client's exit button is lit: the last war state it heard is 0",
          c.ws(), [1, 0])
    c.send("chWorld;")
    got = c.frames(0.5)
    check("and the way out is open at once",
          [(n, p.get("res")) for n, p in got if n in ("cmdAck", "gmap")],
          [("cmdAck", 0), ("gmap", None)])
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=5)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails or os.environ.get("LAVA_TEST_LOG"):
        fails.append("server log tail:\n" + out[-4000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("war state OK")
