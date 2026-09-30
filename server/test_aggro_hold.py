"""A creature keeps its target until the player walks out, and the exit
timer alone says when he may.

The owner's rule (2026-09-25): «агр не должен сниматься в локации сам по
себе, пока игрок не выйдет после истечения таймера». What production showed
the same day: a creature chased past its leash (mobs.LEASH, 24 hexes from
home) flapped every AI tick -- lch;ws=1 with lch;enemy, lch;ws=0, again --
because the leash reset it, whole, on the spot, and the next tick found the
same player within its aggro radius. A creature that could not reach its
target was also dropped after mobs.GIVE_UP (15 s) and took it again at once.

Both are gone, and what is held to here is what replaces them:

  * a creature pulled far from home keeps the player as its target: no ws
    edge over seconds of it, no heal (in process, on a real RoomCombat);
  * a player it cannot reach stays its target long past the old fifteen
    seconds, and it comes as close as the ground lets it;
  * when the target leaves, the creature walks home and heals there, and
    not a hex before;
  * the timer is the client's own countdown ("Выход возможен через N сек.",
    LocationInterface.startExitTimer): a hit given or taken starts it, every
    hit restarts it, peace cancels it, a new location has none. chWorld is
    refused (res=39) while it runs and allowed once it has run out, with
    the creature still after the player -- in process, and on a socket in
    the dump (100): a starving dog is let come, punched, the exit refused
    and /home with it; punched again, still refused past where the first
    punch alone would have let him go; then left alone to bite at him, and
    the way is open.

The character on the socket has Ближний бой 50: his fist lands every time
and crits, and the dog's teeth never get through his evasion (its 50 hit
against his 59), so the only hits in the scene are the ones he throws and
the timer is his to read. The timer itself is cut to three seconds
(LAVA_LEAVE_COMBAT).

Written against the code before the rule, the in-process part fails on the
leash's flapping (the ws edges and the heal), on the give-up, on the heal
where it let go, and on every check where the creature after him was what
held the player; the socket part fails where the way opens with the dog
still at his heels.
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
import mobs          # noqa: E402
import progression   # noqa: E402
import rooms         # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

DUMP = 100
DOG_HOME, BUM_HOME = 4551, 4363       # mStarvingDog_lvl1 and m05_bich
DOG, BOX = 82, 409                    # the types
HOLD = 3                              # LAVA_LEAVE_COMBAT for the socket part
OLD_LEASH, OLD_GIVE_UP = 24, 15.0     # what the code before the rule let go at

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


# --- in process: a real RoomCombat on a room with nobody on a socket ------------------
class _Room(object):
    """A room whose broadcasts are kept."""

    def __init__(self):
        self.loc = world.location(DUMP)
        self.npcs = {}
        self.players = {}
        self.ws = False
        self.sent = []

    def broadcast(self, frame, exclude=None):
        self.sent.append(frame)


class _Inv(object):
    store = None

    def wear_worn(self, n):
        pass


class _Seat(object):
    """Just enough of a session for a Fighter standing in the room."""
    char_id = 0
    on_map = False

    def __init__(self, room, pos, char_id=1):
        self.room, self.pos, self.pid = room, pos, rooms.player_id(char_id)
        self.inv = _Inv()
        self.sent = []
        self.char = progression.Character()
        self.combat = combat.Fighter(self)
        self.combat.regen_at = float("inf")
        room.players[self] = None

    def send(self, *cmd, **params):
        self.sent.append((cmd[0], params))

    def character(self):
        return self.char


LOC = world.location(DUMP)
W = LOC.width


def _open(cell):
    return 0 <= cell < W * LOC.height and cell not in LOC.obstacles


def _scene(player_cell):
    room = _Room()
    room.combat = rc = combat.RoomCombat(room, None)
    seat = _Seat(room, player_cell)
    return room, rc, seat


def _mob(rc, eid, type_id, home, cell=None):
    mob = rc.mobs[eid] = mobs.Mob(eid, type_id, home)
    if cell is not None:
        mob.cell = cell
    return mob


def _ws(room):
    return [p["ws"] for n, p in room.sent if n == "lch" and "ws" in p]


def _bars(room, eid):
    return [p for n, p in room.sent if n == "usrUp" and p.get("id") == eid]


def _run(rc, mob, t0, seconds, each=None):
    """The room's brain for `seconds` of its own clock, a tick every
    AI_TICK: the mob thinks, the room is asked whether it is still at war.
    Returns the loop time the run ended at."""
    t = t0
    for _ in range(int(seconds / combat.AI_TICK)):
        t += combat.AI_TICK
        mob.think(rc, t)
        rc.calm(t)
        if each is not None:
            each(t)
    return t


# A far cell, well past the old leash, with open ground to a player three
# hexes off -- inside the dog's aggro radius, as in production, so the old
# code took him again on the tick after it let him go.
FAR = next(c for c in range(W * LOC.height)
           if _open(c) and OLD_LEASH + 6 <= mobs.hex_distance(DOG_HOME, c, W) <= OLD_LEASH + 12
           and mobs.find_path(LOC, c, lambda x: x == DOG_HOME) is not None)
NEAR = next(c for c in range(W * LOC.height)
            if _open(c) and 2.5 <= mobs.hex_distance(FAR, c, W) <= 3.5
            and mobs.find_path(LOC, FAR, lambda x: mobs.adjacent(x, c, LOC)) is not None)
check("a spot %.0f hexes from the dog's home, past the old leash of %d, with a player"
      " %.1f hexes off inside its aggro radius"
      % (mobs.hex_distance(DOG_HOME, FAR, W), OLD_LEASH, mobs.hex_distance(FAR, NEAR, W)),
      mobs.hex_distance(FAR, NEAR, W) <= mobs.stats(DOG).aggro, True)


async def _pulled_far():
    room, rc, seat = _scene(NEAR)
    dog = _mob(rc, 1, DOG, DOG_HOME, FAR)
    rc.aggro(dog, seat.combat)
    wounded = dog.hp_max - 20
    dog.hp = wounded
    room.sent = []
    held = []
    _run(rc, dog, combat.now(), 6.0, lambda t: held.append(dog.target is seat.combat))
    check("pulled %.0f hexes from home, the dog keeps the player as its target, every tick"
          " for six seconds" % mobs.hex_distance(DOG_HOME, FAR, W),
          (len(held), all(held)), (int(6.0 / combat.AI_TICK), True))
    check("and the room stays at war all along: not one lch;ws edge", _ws(room), [])
    check("nor is it healed in between: no bar of its own sent, the wound as it was",
          (_bars(room, 1), dog.hp), ([], wounded))
    swung = [n for n, p in room.sent if n in ("caHit", "caMiss") and p.get("id") == 1]
    check("it came for him and went for his throat", swung != [], True)
    return room, rc, seat, dog, wounded


async def _goes_home(room, rc, seat, dog, wounded):
    # He leaves the room: the dog lets go, walks home, and heals there.
    del room.players[seat]
    room.sent = []
    trail = []
    t = _run(rc, dog, combat.now(), 20.0, lambda t: trail.append((dog.cell, dog.hp)))
    check("the player gone, the dog lets go of him", dog.target, None)
    check("and the room goes to peace", _ws(room), [0])
    check("it walks home, however far it was pulled", dog.cell, DOG_HOME)
    check("and is whole there", (dog.hp, dog.sp), (dog.hp_max, dog.sp_max))
    check("healed at home and not a hex before",
          sorted({cell for cell, hp in trail if hp != wounded}), [DOG_HOME])
    check("the room is told of it: its bar, full",
          [(p["hcur"], p["hmax"]) for p in _bars(room, 1)], [(dog.hp_max, dog.hp_max)])
    walked = [p["path"] for n, p in room.sent if n == "userMove" and p.get("id") == 1]
    check("on foot: legs of at most %d hexes, each from where the last ended" % mobs.LEG,
          (all(len(leg) - 1 <= mobs.LEG for leg in walked),
           all(a[-1] == b[0] for a, b in zip(walked, walked[1:])), walked[-1][-1] if walked else None),
          (True, True, DOG_HOME))
    return t


async def _unreachable():
    # A player the dog cannot get next to: every hex around him taken by a
    # box, which stands and fights nobody (role "object").
    spot = next(c for c in range(W * LOC.height)
                if _open(c) and 5 <= mobs.hex_distance(DOG_HOME, c, W) <= 8
                and all(_open(n) for n in progression.hex_neighbours(c, W, LOC.height)))
    room, rc, seat = _scene(spot)
    for i, n in enumerate(progression.hex_neighbours(spot, W, LOC.height)):
        _mob(rc, 100 + i, BOX, n)
    dog = _mob(rc, 1, DOG, DOG_HOME)
    rc.aggro(dog, seat.combat)
    before = mobs.hex_distance(dog.cell, spot, W)
    room.sent = []
    held = []
    _run(rc, dog, combat.now(), OLD_GIVE_UP + 6, lambda t: held.append(dog.target is seat.combat))
    check("a player it cannot get next to stays its target %.0f s on, past the old"
          " give-up of %.0f s" % (OLD_GIVE_UP + 6, OLD_GIVE_UP), all(held), True)
    check("and the room at war all that time", (_ws(room), room.ws), ([], True))
    check("it came as close as the boxes let it, and waits there",
          (mobs.hex_distance(dog.cell, spot, W) < before,
           mobs.hex_distance(dog.cell, spot, W) <= 2.0), (True, True))


async def _timer():
    """The exit timer, on a Fighter in a room where a dog is after him."""
    room, rc, seat = _scene(NEAR)
    me = seat.combat
    dog = _mob(rc, 1, DOG, DOG_HOME)
    rc.aggro(dog, me)
    check("the dog is after him and the room at war", (dog.target is me, room.ws), (True, True))
    check("no hit yet, either way: the timer is not running and the way out is open",
          (me.in_combat(), me.refuse_leave(), seat.sent[-1:]),
          (False, False, [("lch", {"enemy": 1})]))
    me.last_hit = combat.now() - (combat.LEAVE_COMBAT_TIMEOUT - 1)
    seat.sent = []
    check("a hit a second short of the timer: chWorld is refused with res=39",
          (me.in_combat(), me.refuse_leave(), seat.sent), (True, True, [("cmdAck", {"res": 39})]))
    me.last_hit = combat.now() - combat.LEAVE_COMBAT_TIMEOUT - 0.05
    seat.sent = []
    check("the timer run out, the dog still after him: the way out is open",
          (me.in_combat(), me.refuse_leave(), seat.sent, dog.target is me, room.ws),
          (False, False, [], True, True))
    # Every hit given or taken restarts it: the dog's teeth, his fist, a
    # bullet either way -- all through the one place the frames go out from.
    rc.hit_landed(dog, me)
    left = me.exit_timer_left()
    check("a hit taken starts it over, to the full count",
          combat.LEAVE_COMBAT_TIMEOUT - 0.5 < left <= combat.LEAVE_COMBAT_TIMEOUT, True)
    me.last_hit = combat.now() - combat.LEAVE_COMBAT_TIMEOUT - 0.05
    rc.hit_landed(me, dog)
    check("and so does a hit given", me.in_combat(), True)
    other = _Seat(room, NEAR + 1, char_id=2)
    rc.hit_landed(me, other.combat)
    check("a hit on another player runs it for both of them",
          (me.in_combat(), other.combat.in_combat()), (True, True))
    bystander = _Seat(room, NEAR + 2, char_id=3)
    check("and for nobody who was at neither end", bystander.combat.in_combat(), False)
    # Peace cancels the client's countdown (battleMode -> deleteTimerLeaveLocation),
    # and a war that starts again does not bring it back.
    del room.players[other]
    other.combat.last_pvp = -1e9
    me.last_pvp = -1e9
    room.sent = []
    rc.kill(dog, None)
    check("the dog down and nothing else after anybody: peace, and the timer with it",
          (_ws(room), me.in_combat(), me.last_hit), ([0], False, -1e9))
    bum = _mob(rc, 2, 411, BUM_HOME)
    rc.aggro(bum, me)
    check("a new creature after him puts the room at war again, the timer still not running",
          (room.ws, me.in_combat()), (True, False))
    rc.hit_landed(bum, me)
    me.left()
    check("and a new location has none: the one it ran in keeps it", me.last_hit, -1e9)


async def _in_process():
    got = await _pulled_far()
    await _goes_home(*got)
    await _unreachable()
    await _timer()


try:
    asyncio.run(_in_process())
except Exception:
    import traceback
    fails.append("the in-process part broke:\n" + traceback.format_exc())


# --- on a socket: the dump, a dog, a fist -------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "aggro.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("brawler", "secret")
_store.close()
CRED = accounts.credential("brawler", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730",
           LAVA_LEAVE_COMBAT=str(HOLD), LAVA_RESPAWN="600", LAVA_AP_REGEN="25",
           LAVA_SEED="7")
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
        self.seen += [(time.time(), f) for f in out]
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

    def since(self, t):
        return [f for at, f in self.seen if at >= t]


def named(frames, name):
    return [p for n, p in frames if n == name]


def entity(eid):
    return "x1%08x" % eid


def login(c, first=False):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    got = c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@brawler@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    return got + c.until(lambda f: f[0] == "lcall")


try:
    c = Client(connect())
    login(c, first=True)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    store = accounts.Store(DB)
    char_id = store.character_by_name("brawler")["id"]
    ch = progression.Character.load(store, char_id)
    ch.skill[progression.MELEE] = [50, 0, progression.skill_xp_max(50)]
    ch.recalc()
    ch.hp = ch.sp = None
    ch.save(store)
    store.close()
    check("his fist cannot miss the dog, and its teeth cannot find him",
          (combat.melee_hit_chance(ch, combat.SPEC_FIST) - mobs.stats(DOG).dodge >= 100,
           mobs.stats(DOG).hit - progression.melee_evade(ch) < 1), (True, True))

    c = Client(connect())
    got = login(c)
    check("the client counts its exit countdown from the server's timer",
          [p["leave_combat_timeout"] for p in named(got, "constants")], [HOLD])
    c.send("lenter;accept=1;")
    c.frames(1.5)
    c.send("userMsg;entry=@/goto %d@;group=0;" % DUMP)
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    arrival = c.frames(2)
    pos = named(arrival, "lenter")[0]["pos"]
    spawns = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    dog = spawns[DOG_HOME]

    # --- into the dog's reach, and nobody else's -------------------------------------
    others = [(cell, mobs.stats(t)) for cell, t in LOC.spawns
              if cell != DOG_HOME and mobs.stats(t).can_attack]
    wary = {cell for cell in range(W * LOC.height)
            if any(mobs.hex_distance(cell, o, W) <= st.aggro + 1.5 for o, st in others)}
    spot = lambda cell: mobs.hex_distance(cell, DOG_HOME, W) <= mobs.stats(DOG).aggro - 0.5
    path = mobs.find_path(LOC, pos, spot, wary | {DOG_HOME})
    check("there is a cell only the dog will notice", path is not None, True)
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    pos = path[-1]
    enemy = lambda: [p["enemy"] for p in named([f for _, f in c.seen], "lch") if "enemy" in p]
    c.until(lambda f: f[0] == "lch" and f[1].get("enemy") == dog, 6)
    check("the dog takes him as its target, and the room goes to war",
          (enemy(), [p["ws"] for p in named([f for _, f in c.seen], "lch") if "ws" in p]),
          ([dog], [1]))

    def dog_cell():
        for _at, (n, p) in reversed(c.seen):
            if n == "userMove" and p.get("id") == dog:
                return p["path"][-1]
        return DOG_HOME

    c.until(lambda f: f[0] in ("caHit", "caMiss") and f[1].get("id") == dog, 6)
    check("it comes and snaps at him", mobs.adjacent(pos, dog_cell(), LOC), True)

    def punch():
        """Fists at the dog until one lands: (the loop time it landed, as
        this side saw it, or None)."""
        for _ in range(10):
            c.send("ss_use;type=16;obj=x0;target=%s;" % entity(dog))
            got = c.until(lambda f: f[0] in ("caHit", "caMiss") and f[1].get("id", 0) == 0, 2)
            if [p for p in named(got, "caHit") if p.get("id", 0) == 0]:
                return time.time()
            time.sleep(0.3)
        return None

    def leave():
        c.send("chWorld;")
        got = c.frames(0.4)
        return [(n, p.get("res")) for n, p in got if n in ("cmdAck", "gmap", "lcall")]

    def pump_until(t):
        """Read the room until loop time t, so every frame is stamped when
        it came."""
        c.frames(max(0.0, t - time.time()))

    first = punch()
    check("his fist lands", first is not None, True)
    check("a hit given: chWorld is refused with res=39, nobody moves", leave(), [("cmdAck", 39)])
    # /home is held by the same timer; its refusal is a line of chat behind
    # the one ack the userMsg is owed.
    c.send("userMsg;entry=@/home@;group=0;")
    got = c.frames(0.5)
    check("and so is /home: the chat line acknowledged, nobody moves",
          [(n, p.get("res")) for n, p in got if n in ("cmdAck", "lcall", "gmap")],
          [("cmdAck", 0)])
    pump_until(first + 1.5)
    second = punch()
    check("and lands again", second is not None, True)
    pump_until(first + HOLD + 0.5)
    check("past where the first hit alone would have let him go, the second keeps the "
          "timer running: still res=39", leave(), [("cmdAck", 39)])
    # Now nothing more from him, and nothing gets through to him.
    pump_until(second + HOLD + 0.4)
    everything = [f for _, f in c.seen]
    check("the dog is still after him: it goes on snapping at him",
          [n for n, p in c.since(second + 0.2) if n == "caMiss" and p.get("id") == dog] != [],
          True)
    check("and none of it lands, so the only hits were his",
          [p for n, p in everything if n == "caHit" and p.get("id") == dog], [])
    check("the room at war all along: no lch;ws=0 since it came",
          [p["ws"] for p in named(everything, "lch") if "ws" in p], [1])
    bars = [p for p in named(c.since(first), "usrUp") if p.get("id") == dog]
    check("nor was the dog healed: every bar of its own since the first punch short of full",
          (bars != [], all(p["hcur"] < p["hmax"] for p in bars)), (True, True))
    check("the timer run out, the dog still at his heels: chWorld takes him out",
          leave(), [("cmdAck", 0), ("gmap", None)])
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
except Exception:
    import traceback
    fails.append("the socket part broke:\n" + traceback.format_exc())
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
print("aggro hold OK")
