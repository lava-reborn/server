"""Two players shooting at each other, and the places where they may not.

The client decides nothing here: ItemActivator.fire refuses a peaceful
location on its own, but a modified one would not, so every rule is the
server's. The ones being held to:

  * a blow or a shot lands on another player wherever the location's own XML
    does not say pvp="0" -- read exactly as the client reads it (LDParser:
    pvpEnabled = attributes.pvp != "0"), so the open wasteland, whose desert
    templates carry no pvp attribute at all, is a place to fight. The server
    used to read the silence as "no" and answered every such blow with res=3,
    "Сервер не отвечает": that was the owner's «нет ПвП между игроками»;
  * except in the Nubian valley, where every character starts: its own
    wasteland tiles and rock said pvp="0" and are lost, so its open desert
    and the pockets of rock its walls lead into are refused by the server,
    with the reason in chat, and "Арена Нубии" is the place for a fight
    there (world.NOOB_VALLEY, travel.newbie_ground) -- while the open ground
    of the rectangle outside the owner's wall is the wasteland's;
  * a duel holds both of its sides, the one who opened it as much as the one
    who was struck, or every exchange would end the moment it went badly --
    and only a blow that could reach opens one: a swing from across the
    room misses and holds nobody;
  * the one attacked is told who by (lch;enemy, the frame a mob's aggro
    sends): the attacker turns red on the victim's screen, once;
  * a player killed by a player falls as to anything else -- lch;dead, the
    death written down, what falls off the body (combat.death_losses, every
    chance at 100 per cent here) left in one bag the killer can open, with
    the trophy the kill leaves a killer of the victim's level in it too;
    the kill itself raises no «Навык бойца» (rep) -- registering that
    trophy does, test_trophies' -- and no skill learns from a player (the
    wiki pays experience for mobs only).

The duel rule is the other half of the one test_combat checks from the
mob's side: what shuts the way out is being fought, not having fired.
"""
import os
import threading
import socket
import subprocess
import tempfile
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

# Свалка Вади-Хальфы: pvp="1" war="1" in its own XML, and the suites already
# use it for fighting. The black market (102) is the peaceful half of the
# comparison -- war="0" there, and nothing may be fired at all.
DUMP = 100
MARKET = 102
# Open desert west of Вади-Хальфа. (gx + gy) & 3 == 0 picks desert/0001.xml,
# whose one spawn is a type the client does not know and is never placed,
# so nothing but the two players is in it.
DESERT = (5992, 1760)
# Open desert inside the Nubian valley, between the settlement (6268,1819)
# and the farm; the same template, the same silence about pvp.
VALLEY = (6268, 1820)
# "Арена Нубии", pvp="1": the valley's one place for a fight.
ARENA = (6270, 1831)
# Valley desert on the western edge, the owner's wall to its west (and
# south and east): its W exit ends in a pocket of rock (travel.dead_end),
# filed under this cell.
WALLED = (6261, 1826)
# Open ground inside NOOB_VALLEY's rectangle but outside the wall, one of
# each of its three stretches: the wasteland's, as any other. The wall as
# the owner redrew it on 2026-09-26 (data/terrain_verified.json): the south
# stretch of the old one (6261,1838..1841) is rock now, the north-west
# corner (6260..6261,1817..1818) open ground outside.
OUTSKIRTS = ((6260, 1830), (6260, 1817), (6274, 1818))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# This suite holds the original's peace in the Nubian valley, which is now a
# switch the owner has turned off (world.NOOB_VALLEY_SAFE): it is turned on
# here, for this process and the server it starts. The valley as it plays
# by default is test_valley_pvp's.
os.environ["LAVA_NOOB_VALLEY_SAFE"] = "1"
PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts   # noqa: E402
import combat     # noqa: E402
import inventory  # noqa: E402
import items      # noqa: E402
import mobs       # noqa: E402
import progression  # noqa: E402
import rooms      # noqa: E402
import travel     # noqa: E402
import world      # noqa: E402
from protocol import decode  # noqa: E402

accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("hunter", "secret")
_store.register("quarry", "secret")
_store.close()
CRED_A = accounts.credential("hunter", "secret")
CRED_B = accounts.credential("quarry", "secret")

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


# --- the rule, in process -------------------------------------------------------
def pvp_of(loc_id):
    loc = world.location(loc_id)
    return loc.file, int(bool(loc.pvp)), getattr(loc, "newbies", None)


check("the dump says pvp=\"1\", and is open to it",
      pvp_of(DUMP), ("static/100.xml", 1, False))
check("a Nubian wasteland tile says pvp=\"0\", and is closed to it",
      pvp_of(1334), ("static/1334.xml", 0, False))
check("a rock tile of the rim says nothing, which the client reads as open",
      pvp_of(10), ("static/10.xml", 1, False))
check("so does the open desert: the template says nothing, and it is open",
      pvp_of(world.pack(*DESERT)), ("desert/0001.xml", 1, False))
check("and the edge of the world beyond it",
      pvp_of(4 << 28)[1:], (1, False))
check("but open desert inside the Nubian valley is the newcomers' ground",
      pvp_of(world.pack(*VALLEY)), ("desert/0001.xml", 0, True))
check("the valley is the wiki's fifteen places and a cell around them",
      getattr(world, "NOOB_VALLEY", None), (6260, 1817, 6274, 1841))
x0, y0, x1, y1 = 6260, 1817, 6274, 1841
# Where the owner's wall runs along the rectangle's edge (row 1822, column
# 6268) the edge is the valley's to its last cell.
check("to its last cell, and not one past it",
      [pvp_of(world.pack(x, 1822))[1] for x in (x0 - 1, x0, x1, x1 + 1)]
      + [pvp_of(world.pack(6268, y))[1] for y in (y0 - 1, y0, y1, y1 + 1)],
      [1, 0, 0, 1, 1, 0, 0, 1])
_rect = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
check("every open cell the owner's wall shuts in is the valley's: 151 of them",
      sum(1 for c in _rect if world.passable(*c) and world.in_noob_valley(*c)),
      151)
check("but the open ground of the rectangle outside the wall is the "
      "wasteland's: open to a fight, and nobody's newcomers",
      [pvp_of(world.pack(*c))[1:] for c in OUTSKIRTS], [(1, False)] * 3)
check("21 such cells in all", len(getattr(world, "valley_outskirts", list)()), 21)
check("the valley's settlements keep what their own files say",
      [pvp_of(i)[1:] for i in (181, 185, 167)],
      [(0, False), (0, False), (1, False)])

# The pockets a valley cell's side exits end in (travel.POCKET) are rim
# files: 4, 7 and 40 say nothing about pvp and 14 says "1". Standing in one
# the map cell is still the valley's, and so is the rule.
ground = getattr(travel, "newbie_ground", None)
check("the pockets of rock say a player may be attacked in them",
      [pvp_of(p)[1] for p in (4, 7, 14, 40)], [1, 1, 1, 1])
check("but a pocket entered from a valley cell is the valley's ground",
      [ground(world.location(p), *WALLED) for p in (4, 7, 14, 40)]
      if ground else None, [True] * 4)
check("and one entered from the wasteland, or from outside the wall, is not",
      [ground(world.location(4), *c) for c in (DESERT,) + OUTSKIRTS]
      if ground else None, [False] * 4)
check("open desert in the valley is its ground; its settlements and interiors "
      "are theirs, the arena too",
      [ground(world.location(i), *c) for i, c in
       ((world.pack(*VALLEY), VALLEY), (181, (6268, 1819)), (167, ARENA))]
      if ground else None, [True, False, False])

rep = getattr(progression, "pvp_rep", None)
check("«Навык бойца» for a kill: a stronger victim pays the price, an equal "
      "half, one level down a quarter, two down nothing",
      [rep(v, 4) for v in (9, 5, 4, 3, 2, 0)] if rep else None,
      [20, 20, 10, 5, 0, 0])
# It is paid when the trophy is registered, and the once-an-hour rule for one
# killer and one victim went with it into the database (test_trophies).
check("the kill itself keeps no count of what it paid any more",
      hasattr(combat, "pvp_rep_due"), False)

# One of the types the wiki marks as falling off a corpse (test_death), and
# still one that may.
DROP_TYPE = [t for t in sorted(items.catalogue())
             if (items.wiki().get(t) or {}).get("drop_on_death")
             and combat.drops_on_death(t) and items.params_of(t) is not None][0]

# --- the server ------------------------------------------------------------------
# Action points refill at once, so no blow below waits on the bar.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB, LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730",
           LAVA_AP_REGEN="25",
           # Every thing that may fall off the quarry does, so the bag the
           # hunter opens is known (the rates are test_death_drops').
           LAVA_WEAR_DROP="100", LAVA_BAG_DROP="100")
# The lines the server says by itself (Session.say) are off on a served
# server; this suite reads them as the server's reasons, so it asks for
# them by name.
env["LAVA_SERVER_CHAT"] = "1"
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


class Client:
    def __init__(self, sock):
        self.s = sock
        self.s.settimeout(2)
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while True:
            left = deadline - time.time()
            if left <= 0:
                break
            self.s.settimeout(left)
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [f.decode(ENC) for f in parts if f]

    def until(self, name, wait=3.0):
        """Everything up to and including the first frame of that name."""
        got = []
        end = time.time() + wait
        while time.time() < end:
            got += self.frames(0.3)
            if any(f.startswith(name + ";") for f in got):
                break
        return got


def param(frame, key):
    for part in frame.split(";")[1:]:
        if part.startswith(key + "="):
            return part[len(key) + 1:]
    return None


def named(frames, name):
    return [f for f in frames if f.startswith(name + ";")]


def parsed(frames, name):
    """The params of every frame of that name, decoded as the client would."""
    return [decode(f)[1] for f in named(frames, name)]


def said(frames):
    return [p["entry"] for p in parsed(frames, "userMsg")]


def enter(c, cred, nick):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
    c.frames()
    c.send("actPlayer;")
    c.frames()
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return int(param(named(got, "lenter")[0], "pos"))


def come_back(c, cred):
    """Log an existing character in again, into wherever it was left."""
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    c.frames()
    c.send("selPers;num=0;")
    got = c.until("lcall")
    c.send("lenter;accept=1;")
    got += c.frames(wait=2)
    return got


def goto(c, where):
    """/goto a location by number, or the one on a map cell (gx, gy)."""
    if isinstance(where, tuple):
        c.send("userMsg;entry=@/goto %d %d@;group=0;" % where)
    else:
        c.send("userMsg;entry=@/goto %d@;group=0;" % where)
    c.until("lcall")
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return int(param(named(got, "lenter")[0], "pos"))


def entity(eid):
    """An ss_use target: one hex digit of type (1 = entity, 0 = a hex of the
    floor) and the id padded to eight (MDString.createBigUINT)."""
    return "x1%08x" % eid


def meet(where, pid_b):
    """Both into the same place, the hunter first, so the quarry's arrival is
    announced to them rather than listed in a snapshot taken before it
    happened; then the hunter steps off the doorway they share to stand
    beside the quarry. Returns the quarry's cell."""
    goto(a, where)
    a.frames(1.0)
    pos_b = goto(b, where)
    got = a.frames(1.5)
    arrived = [int(param(f, "newUser")) for f in named(got, "lch") if "newUser" in f]
    b.frames(1.0)
    # Location.entry_cell hands every arrival the same doorway, and a cell is
    # not adjacent to itself, so the fist has to step off it first.
    loc = world.location(world.location_at(*where)) if isinstance(where, tuple) \
        else world.location(where)
    pos_a = pos_b
    spot = next(n for n in progression.hex_neighbours(pos_b, loc.width, loc.height)
                if n not in loc.obstacles)
    a.send("moveTo;path=|%d|%d|;" % (pos_a, spot))
    a.frames(0.5 + mobs.HEX_MS / 1000.0)
    b.frames(0.5)
    return arrived, mobs.hex_distance(spot, pos_b, loc.width), pos_b


def through_wall(c, cell, side):
    """/goto a map cell, walk onto the middle of its exit on that side and
    take it (chWorld;to=1). Returns the lcall's location id and the cell
    the lenter put the player on."""
    goto(c, cell)
    loc = world.location(world.location_at(*cell))
    exits = [x for x, s in travel.exit_sides(loc).items() if s == side]
    mx, my = travel._edge_middle(loc, side)
    ex = min(exits, key=lambda x: (x % loc.width - mx) ** 2 + (x // loc.width - my) ** 2)
    c.send("moveTo;path=|%d|;" % ex)
    c.frames(0.6)
    c.send("chWorld;to=1;")
    got = c.until("lcall")
    c.send("lenter;accept=1;")
    got += c.frames(wait=2)
    lcall = parsed(got, "lcall")
    lenter = named(got, "lenter")
    return (lcall[0]["id"] if lcall else None,
            int(param(lenter[0], "pos")) if lenter else None)


def swing(c, target, wait=3.0):
    """One blow of the fist, and everything up to its landing or refusal."""
    c.send("ss_use;type=16;obj=x0;target=%s;" % entity(target))
    got, end = [], time.time() + wait
    while time.time() < end:
        got += c.frames(0.3)
        if named(got, "caHit") or named(got, "caMiss") or \
                [f for f in named(got, "cmdAck") if param(f, "res") != "0"]:
            break
    return got


def arm(c):
    """The oids of the starter pistol in the hand and its rounds in the bag
    (inventory.STARTER_KIT), off the character's own list of what it has."""
    c.send("ss_get;target=0;slot=11;")
    listed = [str(o) for o in parsed(c.frames(), "ss_ack")[0]["o_list"]]
    by_type = {}
    for o in listed:
        if o != "0":
            by_type.setdefault(inventory.parse_oid(o)[1], o)
    return by_type[inventory.STARTER_PISTOL], by_type[inventory.STARTER_AMMO]


def load(c, gun, rounds):
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
    return c.until("ss_di_firearm")


def shoot(c, gun, target):
    """One burst, up to the magazine report that closes it -- or a refusal."""
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(target)))
    got, end = [], time.time() + 3.0
    while time.time() < end:
        got += c.frames(0.3)
        if named(got, "ss_di_firearm") or \
                [f for f in named(got, "cmdAck") if param(f, "res") != "0"]:
            break
    return got


def enemies(frames):
    return [p["enemy"] for p in parsed(frames, "lch") if "enemy" in p]


try:
    a = Client(connect())
    b = Client(connect())
    enter(a, CRED_A, "hunter")
    enter(b, CRED_B, "quarry")

    # A player's entity id is their character id plus the register's base
    # (rooms.player_id), and the two characters were created in this order,
    # so there is nothing to discover by listening.
    pid_a, pid_b = rooms.player_id(1), rooms.player_id(2)

    # --- the peaceful half: the market refuses a blow at all ----------------
    # The hunter settles first, so the quarry's arrival is announced to them
    # rather than being listed in a snapshot taken before it happened.
    goto(a, MARKET)
    a.frames(1.0)
    goto(b, MARKET)
    got = a.frames(1.5)
    check("they stand in the market together",
          [int(param(f, "newUser")) for f in named(got, "lch") if "newUser" in f],
          [pid_b])
    b.frames(1.0)

    a.send("ss_use;type=16;obj=x0;target=%s;" % entity(pid_b))
    got = a.frames(1.0)
    check("a blow in a peaceful location is refused",
          [param(f, "res") for f in named(got, "cmdAck")], ["3"])
    check("and nothing is thrown", named(got, "faAim") + named(got, "caHit"), [])

    # --- the valley's walls: a pocket of rock is the valley too -------------
    # Done before any fight: a duel holds both sides, and chWorld is how one
    # walks into the wall. A valley cell's side exit into the owner's wall
    # ends in a pocket (travel.dead_end), a rim file with nothing to say about
    # pvp that the client reads as open; both are filed under the valley cell
    # they left, so they meet. That was a way around the valley's rule: in
    # the original the valley's rock was NoPvP_*, pvp="0".
    pocket_id = travel.POCKET[travel.W]
    into_a = through_wall(a, WALLED, travel.W)
    a.frames(1.0)
    into_b = through_wall(b, WALLED, travel.W)
    got = a.frames(1.5)
    b.frames(0.5)
    check("both walk into the wall west of the valley and meet in one pocket",
          (into_a[0], into_b[0],
           [int(param(f, "newUser")) for f in named(got, "lch") if "newUser" in f]),
          (pocket_id, pocket_id, [pid_b]))
    pocket = world.location(pocket_id)
    spot = next(n for n in progression.hex_neighbours(into_b[1], pocket.width, pocket.height)
                if n not in pocket.obstacles)
    a.send("moveTo;path=|%d|%d|;" % (into_a[1], spot))
    a.frames(0.5 + mobs.HEX_MS / 1000.0)
    b.frames(0.5)
    check("the hunter stands beside the quarry among the rocks",
          mobs.hex_distance(spot, into_b[1], pocket.width), 1)
    got = swing(a, pid_b)
    got_b = b.frames(0.6)
    check("a blow in the valley's pocket of rock is refused, as in its desert",
          [param(f, "res") for f in named(got, "cmdAck")],
          [str(getattr(combat, "RES_NO_PVP", "no such code"))])
    check("with the valley's reason in chat",
          [t for t in said(got) if "Нубийская долина" in t] != [], True)
    check("nothing is swung, and the quarry is nobody's enemy",
          (named(got, "caHit") + named(got, "caMiss"), enemies(got_b)), ([], []))
    b.send("chWorld;to=1;")
    got = b.until("lcall")
    check("nor held: the way it came in is open",
          [param(f, "res") for f in named(got, "cmdAck")], ["0"])
    b.send("lenter;accept=1;")
    b.frames(1.0)
    a.frames(0.5)

    # --- the dump: pvp="1", and the blow lands -------------------------------
    # The hunter goes first and is already standing there when the quarry
    # walks in, so the arrival is announced to the hunter rather than listed
    # in a snapshot taken before it happened.
    pos_a = goto(a, DUMP)
    a.frames(1.0)
    pos_b = goto(b, DUMP)
    got = a.frames(1.5)
    check("the hunter is told the quarry walked into the dump",
          [int(param(f, "newUser")) for f in named(got, "lch") if "newUser" in f],
          [pid_b])
    b.frames(1.0)

    # A fist reaches one hex and no further, and a cell is not adjacent to
    # itself -- which is where the two of them are, because Location.
    # entry_cell hands every arrival the same doorway. So the hunter steps
    # off it, and from beside the quarry the blow can actually land.
    loc = world.location(DUMP)
    check("both arrivals land on the same entry cell", pos_a, pos_b)
    spot = next(n for n in progression.hex_neighbours(pos_b, loc.width, loc.height)
                if n not in loc.obstacles)
    a.send("moveTo;path=|%d|%d|;" % (pos_a, spot))
    a.frames(0.5 + mobs.HEX_MS / 1000.0)
    b.frames(0.5)
    check("the hunter is standing next to the quarry",
          mobs.hex_distance(spot, pos_b, loc.width), 1)

    # A bare fist can miss, and does: melee_hit against the other's dodge is
    # a roll like any other, 40 against 100 between two newcomers. So the
    # claim under test is that a blow between players *can* land, and it is
    # swung until one does or the attempts run out -- twenty-five misses in a
    # row would be a run of luck of about three in a million (ten, as it
    # was, lost one run in a hundred and fifty).
    # Each swing has to be let finish before the next is thrown: the strike
    # bar runs strike_time from the command to the caHit, and a second ss_use
    # in the meantime cancels the first (Fighter.strike is one timer).
    acks, hits, seen = [], [], []
    for _ in range(25):
        got = swing(a, pid_b)
        acks += [param(f, "res") for f in named(got, "cmdAck")]
        hits += named(got, "caHit")
        seen += b.frames(0.3)
        if hits:
            break
    check("a blow between players is accepted where pvp is declared",
          acks[:1], ["0"])
    # A strike is one frame, hit or miss -- no faAim, that is for a firearm.
    check("it lands on the other player",
          [param(f, "target") for f in hits][:1], [str(pid_b)])
    check("with damage on it",
          [int(param(f, "dmg")) + int(param(f, "sdmg")) > 0 for f in hits][:1],
          [True])

    seen += b.frames(0.6)
    check("the struck player sees the war state",
          [f for f in named(seen, "lch") if "ws=1" in f] != [], True)
    check("and their own bar drops",
          [f for f in named(seen, "usrUp") if param(f, "id") == "0"] != [], True)

    # --- neither of them may simply walk out ---------------------------------
    b.send("chWorld;")
    got = b.frames(0.8)
    seen += got
    check("the one who was struck is held",
          [(f.split(";")[0], param(f, "res")) for f in got
           if f.split(";")[0] in ("cmdAck", "gmap", "lcall")],
          [("cmdAck", "39")])
    a.send("chWorld;")
    got = a.frames(0.8)
    check("and so is the one who struck",
          [(f.split(";")[0], param(f, "res")) for f in got
           if f.split(";")[0] in ("cmdAck", "gmap", "lcall")],
          [("cmdAck", "39")])
    # And the room with them. A fight with a creature ends the war state the
    # moment nothing is after anybody, but a duel is held for
    # leave_combat_timeout, and ws=0 would light the client's exit button
    # (LocationInterface.battleMode) over a door the server keeps shut.
    seen += b.frames(0.6)
    check("the room stays at war through the duel",
          [f for f in named(seen, "lch") if "ws=0" in f], [])

    # --- the open desert: where the owner found no fighting at all ----------
    arrived, apart, _cell = meet(DESERT, pid_b)
    check("the two of them meet in the open desert", arrived, [pid_b])
    check("side by side", apart, 1)
    got = swing(a, pid_b)
    got_b = b.frames(0.6)
    check("a blow in the open desert is accepted, not \"Сервер не отвечает\"",
          [param(f, "res") for f in named(got, "cmdAck")], ["0"])
    check("the struck one is told who attacks: the hunter turns red for them",
          enemies(got_b), [pid_a])
    check("the one who struck is marked by nobody yet", enemies(got), [])
    hits, seen_a, seen_b = named(got, "caHit"), got, got_b
    for _ in range(25):
        if hits:
            break
        got = swing(a, pid_b)
        hits += named(got, "caHit")
        seen_a += got
        seen_b += b.frames(0.3)
    check("and out in the wasteland a blow lands on a player",
          [param(f, "target") for f in hits][:1], [str(pid_b)])
    seen_b += b.frames(0.4)
    check("the mark is sent once, not with every blow", enemies(seen_b), [pid_a])

    # The quarry answers with a gun: the starter pistol every character is
    # born holding, loaded with the rounds it is born carrying. A shot is a
    # burst -- faAim, the faShot pair around what the bullet did, the
    # victim's usrUp -- and a bullet misses more than half the time between
    # two newcomers, so it is fired until one lands, reloading as it runs dry.
    gun, rounds = arm(b)
    shots, landed, got_a = [], [], []
    for _ in range(20):
        got = shoot(b, gun, pid_a)
        if [f for f in named(got, "cmdAck") if param(f, "res") == "13"]:
            load(b, gun, rounds)
            continue
        shots += got
        got_a += a.frames(0.3)
        landed = [p for p in parsed(got, "faHit") if p.get("target") == pid_a]
        if landed:
            break
    got_a += a.frames(0.5)
    seen_a += got_a
    check("the quarry answers with a shot, and may",
          [param(f, "res") for f in named(shots, "cmdAck")][:1], ["0"])
    check("the gun is raised at the hunter: faAim, then the pair",
          [f.split(";")[0] for f in shots if f.split(";")[0] in ("faAim", "faShot")][:3],
          ["faAim", "faShot", "faShot"])
    check("and a bullet finds the hunter", [p["target"] for p in landed][:1], [pid_a])
    check("who sees it land on himself, and his bar drop",
          ([p for p in parsed(got_a, "faHit") if p.get("target", 0) == 0] != [],
           [p for p in parsed(got_a, "usrUp") if p["id"] == 0] != []), (True, True))
    check("and now the hunter sees the quarry as the enemy",
          enemies(got_a), [pid_b])
    # Skills learn from creatures only; beating a player trains none of them,
    # and rp_info is how a skill's rise would have reached the client.
    check("hitting a player teaches no skill",
          (named(seen_a, "rp_info"), named(shots, "rp_info")), ([], []))

    # --- the Nubian valley: the newcomers' ground ---------------------------
    arrived, apart, _cell = meet(VALLEY, pid_b)
    check("in the valley's open desert, side by side again",
          (arrived, apart), ([pid_b], 1))
    a.send("ss_use;type=16;obj=x0;target=%s;" % entity(pid_b))
    got = a.frames(1.0)
    got_b = b.frames(0.5)
    check("a blow there is refused -- with a code the client shows nothing for",
          [param(f, "res") for f in named(got, "cmdAck")],
          [str(getattr(combat, "RES_NO_PVP", "no such code"))])
    check("and the reason in chat, not a \"Сервер не отвечает\"",
          [t for t in said(got) if "Нубийская долина" in t and "Арена" in t] != [],
          True)
    check("nothing is thrown", named(got, "faAim") + named(got, "caHit")
          + named(got, "caMiss"), [])
    check("the other hears nothing of it: no war, no enemy",
          ([f for f in named(got_b, "lch") if "ws=1" in f], enemies(got_b)),
          ([], []))

    # The arena is the valley's place for it, and the refusal says so.
    goto(a, ARENA)
    a.frames(1.0)
    goto(b, ARENA)
    a.frames(1.0)
    b.frames(0.5)
    a.send("ss_use;type=16;obj=x0;target=%s;" % entity(pid_b))
    got = a.frames(1.0)
    check("in «Арена Нубии» a blow at another player is accepted",
          [param(f, "res") for f in named(got, "cmdAck")], ["0"])
    # The client never aims at its own figure (targetActionMap[Gamer] is
    # null); a modified one that does is not told "Сервер не отвечает".
    a.send("ss_use;type=16;obj=x0;target=%s;" % entity(pid_a))
    got = a.frames(1.0)
    check("a blow at oneself: refused with the code that only lowers the weapon",
          ([param(f, "res") for f in named(got, "cmdAck")],
           named(got, "caHit") + named(got, "caMiss")),
          ([str(getattr(combat, "RES_NO_PVP", "no such code"))], []))

    # --- a kill in the open desert -------------------------------------------
    # The quarry takes a thing the wiki says falls off a corpse, and comes
    # back with one hit point: the first blow that lands finishes it.
    b.send("userMsg;entry=@/give %d@;group=0;" % DROP_TYPE)
    got = b.frames(1.0)
    dropping = [str(p["obj"]) for p in parsed(got, "ss_obj_status")
                if p["status"] == 1]
    check("the quarry carries something that can fall", len(dropping), 1)
    b.send("logout;")
    b.frames(0.3)
    b.s.close()
    time.sleep(0.3)
    st = accounts.Store(DB)
    st.save_character_state(2, hp=1, sp=0)
    # The rounds it fired at the hunter are gone from the stack; what is
    # left of it loses a third, or goes whole when that is under one piece.
    left = [r for r in st.items_of(2) if r["slot"] == inventory.BAG
            and r["type_id"] == inventory.STARTER_AMMO]
    st.close()
    rounds_left = left[0]["count"] if left else 0
    rounds_part = int(round(rounds_left / 3.0)) if rounds_left >= 3 else 0
    if 0 < rounds_left < 3:
        dropping.append(inventory.oid_of(left[0]))
    b = Client(connect())
    come_back(b, CRED_B)
    a.frames(0.5)

    # --- a swing that cannot reach opens no fight ----------------------------
    # The quarry is a new session, held by nothing. The two of them share the
    # doorway, and a cell is not next to itself: the client would not strike
    # from there (Gamer.strike: isSiblings), a modified one might, and the
    # blow that misses for want of reach must not hold its mark in the room
    # nor paint anybody red.
    goto(a, DESERT)
    a.frames(1.0)
    pos_b = goto(b, DESERT)
    a.frames(1.5)
    b.frames(1.0)
    desert = world.location(world.location_at(*DESERT))
    check("the quarry's doorway is no exit of the desert",
          travel.side_at(desert, pos_b), None)
    got = swing(a, pid_b)
    got_b = b.frames(0.6)
    check("a swing from out of reach is let go, and misses",
          ([param(f, "res") for f in named(got, "cmdAck")],
           [param(f, "hex") for f in named(got, "caMiss")], named(got, "caHit")),
          (["0"], [str(pos_b)], []))
    check("and makes the hunter nobody's enemy", enemies(got_b), [])
    b.send("chWorld;to=1;")
    got = b.frames(0.8)
    check("nor holds the quarry: chWorld is answered as by anyone free to "
          "leave -- no exit here, rather than res=39",
          ([param(f, "res") for f in named(got, "cmdAck")] != ["39"],
           [t for t in said(got) if "нет выхода" in t] != []),
          (True, True))

    arrived, apart, where = meet(DESERT, pid_b)
    check("back in the desert, side by side", (arrived, apart), ([pid_b], 1))
    seen_a, seen_b, dead = [], [], []
    for _ in range(25):
        seen_a += swing(a, pid_b)
        seen_b += b.frames(0.3)
        dead = [p for p in parsed(seen_b, "lch") if p.get("dead") == 0]
        if dead:
            break
    seen_a += a.frames(1.0)
    seen_b += b.frames(0.5)
    check("the quarry falls: lch;dead about itself, once", dead, [{"dead": 0}])
    check("and the hunter sees it fall",
          [p for p in parsed(seen_a, "lch") if "dead" in p], [{"dead": pid_b}])
    st = accounts.Store(DB)
    rows = {r["id"]: dict(r) for r in st.db.execute(
        "SELECT id, death, rep FROM characters").fetchall()}
    st.close()
    check("the death is written down", rows[2]["death"], 1)
    check("the hunter's «Навык бойца» does not rise at the kill: it is the"
          " trophy's, when it is registered",
          ([p["rep"] for p in parsed(seen_a, "userInfo_Player") if p["id"] == 0],
           rows[1]["rep"]), ([], 0))
    check("and still no skill from it", named(seen_a, "rp_info"), [])
    check("what fell lies in a bag where the quarry did",
          [(p["s_status"], p["hex"]) for p in parsed(seen_a, "ss_loot")],
          [(1, [where])])
    check("gone from the quarry's own bag",
          sorted(str(p["obj"]) for p in parsed(seen_b, "ss_obj_status")
                 if p["status"] == 0), sorted(dropping))
    check("and a stack of rounds keeps two thirds of itself",
          [(str(p["obj"]), p["size"]) for p in parsed(seen_b, "ss_di_heap")],
          [(inventory.oid_of(left[0]), rounds_left - rounds_part)] if rounds_part else [])

    a.send("ss_create;s_type=0;target=%d;" % where)
    check("the hunter opens it",
          [param(f, "res") for f in named(a.frames(), "cmdAck")], ["0"])
    a.send("ss_get;slot=24;")
    listed = [str(o) for o in parsed(a.frames(), "ss_ack")[0]["o_list"]]
    inside = listed[listed.index("0") + 1:]
    # Two newcomers, level 0 both: the kill left the hunter a trophy.
    won = [o for o in inside if inventory.parse_oid(o)[2] == items.TROPHY]
    split = [o for o in inside if o not in dropping and o not in won]
    st = accounts.Store(DB)
    split_rows = [st.item(inventory.parse_oid(o)[0]) for o in split]
    won_words = [st.trophy(inventory.parse_oid(o)[0]) for o in won]
    st.close()
    check("with the trophy of the kill: an ear, the hunter's off the quarry",
          [(inventory.parse_oid(o)[1], w["killer_id"], w["victim_id"])
           for o, w in zip(won, won_words)], [(1495, 1, 2)])
    check("and finds the quarry's things in it, and a third of its rounds as"
          " a row of their own",
          (sorted(o for o in inside if o in dropping),
           [(r["type_id"], r["count"]) for r in split_rows]),
          (sorted(dropping),
           [(inventory.STARTER_AMMO, rounds_part)] if rounds_part else []))
    a.send("ss_upd;s_status=3;obj=x0;param=1;")
    got = a.frames()
    check("takes it, and the empty bag is gone",
          [(n, p.get("res", p.get("s_status"))) for n, p in
           (decode(f) for f in got) if n in ("cmdAck", "ss_loot")],
          [("cmdAck", 0), ("ss_loot", 0)])
    st = accounts.Store(DB)
    owner = st.item(inventory.parse_oid(dropping[0])[0])["char_id"]
    st.close()
    check("it is the hunter's now", owner, 1)

    a.send("logout;")
    b.send("logout;")
    a.frames(0.3)
    b.frames(0.3)
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("pvp OK")
