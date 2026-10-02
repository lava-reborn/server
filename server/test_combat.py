"""Shoot a starving dog, get bitten, loot the corpse, die, come back home.

Every exchange is the client's own: ItemActivator.as sends the ss_use, and
Location.as, Loot.as, Resurrector.as and PersEquip.as read the answers in the
order checked here (recon/analysis/combat.md 1-3, invariants in 10). The
fight happens in location 100, the dump behind the black market, where quest
5 sends the player for three dogs; the dog nearest the entrance stands 6.2
hexes away, one more than its aggro radius, so the first shot is the
player's. Quest 5, «Голодные собаки», was one of the black market's
placeholders that left data/quests.json on 2026-09-28 (the plan's gold
taps); the suite keeps it as a fixture of its own table (LAVA_QUESTS).

Randomness is real (hits, misses, damage), so the fight is a loop that
checks the shape of every burst rather than a fixed transcript, and the AP
regeneration and the combat timeouts are shortened through the environment
to keep the whole thing under a minute.
"""
import asyncio
import json
import os
import random
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

# The dogs' errand at Техногик (652), as it stood in data/quests.json until
# 2026-09-28: the real table with it put back, for this process and the
# server alike (quests.quests_path).
DOGS_Q = dict(type=5, kind="kill_mobs", name="Голодные собаки",
              start="Голодные собаки таскают со склада всё, что плохо лежит.",
              notfinish="Собаки всё ещё здесь.", finish="Тише стало.",
              give=[652], take=[652], mobs_kill=[82], num_kill=[3], rew_afro=40,
              repeatable=1)
with open(os.path.join(os.path.dirname(HERE), "data", "quests.json"), encoding="utf-8") as _fh:
    _TABLE = json.load(_fh)
_TABLE["quests"].append(DOGS_Q)
QUESTS_FILE = os.path.join(tempfile.mkdtemp(), "quests.json")
with open(QUESTS_FILE, "w", encoding="utf-8") as _fh:
    json.dump(_TABLE, _fh, ensure_ascii=False)
os.environ["LAVA_QUESTS"] = QUESTS_FILE

sys.path.insert(0, HERE)
import accounts
import storage
import combat
import inventory
import items
import mobs
import progression
import quests
import world
from protocol import decode


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "combat.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("gunner", "secret")
_store.close()
CRED = accounts.credential("gunner", "secret")

from testkit import check, fails  # noqa: E402


# --- the formulas and the geometry, in process --------------------------------
# Wiki "Броня": 100 damage against armour 60 -> 40 HP, 60 SP; 120 -> 0/100;
# 0 -> 100/0. Stamina that is not there spills into HP; a crit skips it all.
check("armour turns damage into stamina loss", combat.split_damage(100, 60, 0, False, 1000), (40, 60))
check("armour above the damage absorbs everything", combat.split_damage(100, 120, 0, False, 1000), (0, 100))
check("no armour, all HP", combat.split_damage(100, 0, 0, False, 1000), (100, 0))
check("missing stamina spills into HP", combat.split_damage(100, 60, 0, False, 20), (80, 20))
check("a crit ignores armour", combat.split_damage(100, 60, 0, True, 1000), (100, 0))
check("piercing eats into the armour", combat.split_damage(100, 60, 10, False, 1000), (50, 50))
check("a blow lands on stamina first", combat.melee_split(10, False, 4), (6, 4))
# Wiki "Расчет углового отклонения": the bracket of МР runs from 2.5 for
# nobody to 1.1 for Стрельба 20 and spec 5; a gun's target_size is its
# scatter at max_range, so the cone is that over the range per hex; the
# target is 0.3 wide, and a shot hits as often as the target fits the cone.
check("spread factor: a novice 2.5, a master 1.1, out of range clamped",
      [round(combat.spread_factor(s, p), 3) for s, p in ((0, 0), (20, 5), (10, 2), (99, 9), (-3, -1))],
      [2.5, 1.1, 1.875, 1.1, 2.5])
WALTHER = combat.cone_of(combat.spread_factor(0, 0), 0.8, 1, 10)      # P99, first mode
check("a Walther's cone in a novice's hands is 0.2 a hex", round(WALTHER, 3), 0.2)
check("  ..a hit every time inside the target's width, then the target over the cone",
      [round(combat.hit_probability(WALTHER, d), 2) for d in (1, 2, 3, 5, 10)],
      [1.0, 0.75, 0.5, 0.3, 0.15])
check("  ..a master at five hexes two times in three, at ten one in three",
      [round(combat.hit_probability(combat.cone_of(1.1, 0.8, 1, 10), d), 2) for d in (5, 10)],
      [0.68, 0.34])
check("  ..and a precise round tightens it",
      combat.hit_probability(combat.cone_of(2.5, 0.8, 0.8, 10), 5) > combat.hit_probability(WALTHER, 5), True)
check("the admin gun never misses across a location",
      combat.hit_probability(combat.cone_of(2.5, 0.01, 1, 64), 64), 1.0)
_rng = random.Random(7)
_offsets = [combat.bullet_offset(WALTHER, 5, _rng) for _ in range(2000)]
check("a bullet lands inside the cone, either side of the line",
      (max(abs(o) for o in _offsets) <= 0.5, min(_offsets) < 0 < max(_offsets)), (True, True))
check("  ..and on target about as often as the probability says (30% at five hexes)",
      abs(sum(combat.on_target(o) for o in _offsets) / 2000.0 - 0.3) < 0.04, True)
# A designed gun stands beside a wiki one: the training pistol (3728, CLASS_SHAPE
# PISTOL, 14/10/6 hexes) shows the class's 8 at a hundred metres, a burst
# mode 1.5 and 2 times that (items.MODE_SPREAD).
_training = items.designed_info(3728)[1]
check("a designed pistol scatters like the wiki's: 8, 12 and 16 at a hundred metres",
      [round(100 * ts / r, 1) for ts, r in zip(_training["target_size"], _training["max_range"])],
      [8.0, 12.0, 16.0])
check("target BigUINT: one type digit then eight of id", combat.parse_target("10000002a"), (1, 42))
check("a hex target has type 0", combat.parse_target("000000f3c"), (0, 3900))
W = 64
even = 4 * W + 5
check("facing east is 8", mobs.direction(even, even + 1, W), 8)
check("facing west is 4", mobs.direction(even, even - 1, W), 4)
check("down-right is 1", mobs.direction(even, even + W, W), 1)
check("straight down keeps the facing", mobs.direction(even, even + 2 * W, W), 0)
check("neighbours are exactly one hex apart",
      sorted(round(mobs.hex_distance(even, n, W), 6)
             for n in progression.hex_neighbours(even, W, 128)), [1.0] * 6)
loc100 = world.location(100)
rock = next(o for o in sorted(loc100.obstacles)
            if 2 <= o % W <= W - 3
            and all(o + d not in loc100.obstacles for d in (-2, -1, 1, 2)))
check("a rock on the straight line is what faWall reports",
      mobs.line_of_fire(loc100, rock - 2, rock + 2), rock)
check("nothing between neighbours", mobs.line_of_fire(loc100, even, even + 1), None)
dog_stats = mobs.stats(82)
check("a level-1 dog has the curve's HP times the animal share",
      (dog_stats.level, dog_stats.hp_max, dog_stats.ranged, dog_stats.can_attack),
      (1, 84, False, True))
check("a box is an object: shot at, never shooting", mobs.stats(409).can_attack, False)
check("an armed bandit carries a pistol of his own",
      mobs.stats(17).weapon_type_id, 4380)


# --- a target is let go of only when it is gone ---------------------------------
# The owner's rule (2026-09-25): the aggro does not drop by itself while the
# player is in the location. There used to be two ways it did: a leash of 24
# hexes from home, and fifteen seconds of not getting at the target. Neither
# is left: only the target leaving the room or dying frees the creature
# (test_aggro_hold has the rest, on a real room and on a socket).
class _Release(object):
    """Just enough of a RoomCombat for Mob.think to talk to."""
    def __init__(self, loc):
        self.room = type("R", (), {"loc": loc})()
        self.released = 0

    def mob_release(self, mob):
        self.released += 1
        mob.target = None
    mob_reset = mob_release           # its name before the rule

    def nearest_fighter(self, cell, aggro):
        return None

    def mob_walk(self, mob, goal, t):
        pass


class _Target(object):
    here = True

    def present(self, rc):
        return self.here
    cell = 0


def _let_go(far=0, idle=0.0, here=True):
    """How often a mob chasing a player across loc100 lets go of him on one
    tick: `far` rows from its home, `idle` seconds since it was
    provoked, with nothing it could do about him in between."""
    rc = _Release(loc100)
    m = mobs.Mob(1, 82, 10)
    m.cell = 10 + far * loc100.width
    m.target = _Target()
    m.target.here = here
    m.target.cell = m.cell + 40 * loc100.width   # far away and never approached
    t = 1000.0
    m.pressed = t - idle              # the old clock, for the code before the rule
    m.busy_until = 0.0
    m.next_attack = 0.0
    m.think(rc, t)
    return rc.released


check("a mob thirty rows from home, past the old leash of 24 hexes, keeps its target",
      _let_go(far=30), 0)
check("so does one that has not got at it for a minute", _let_go(idle=60.0), 0)
check("it lets go when the target is gone", _let_go(here=False), 1)

# The kill counter, on a scratch character in a scratch database.
_scratch = accounts.Store(os.path.join(tempfile.mkdtemp(), "scratch.db"))
_acc, _ = _scratch.register("scratch", "secret")
_cid, _ = _scratch.create_character(_acc, "scratch", 0, "1")
_q5 = quests.get(5)
_scratch_q = _scratch.take_quest(_cid, 5, _q5.fresh_progress(), 0)
check("a kill of the wrong type moves nothing", quests.kill_progress(_scratch, _cid, 999), [])
check("a dog counts", quests.kill_progress(_scratch, _cid, 82),
      [("q_di_kill_mobs", dict(q_id=_scratch_q, q_type=5, complete=0, kill_num=[1]))])
quests.kill_progress(_scratch, _cid, 82)
check("the third completes the quest", quests.kill_progress(_scratch, _cid, 82),
      [("q_di_kill_mobs", dict(q_id=_scratch_q, q_type=5, complete=1, kill_num=[3]))])
# The server's first quest: 1 in its own file, the next id when LAVA_DB_URL
# puts the scratch character in the same database.
FIRST_Q = _scratch_q + 1 if storage.using_postgres() else 1
check("a fourth is not counted", quests.kill_progress(_scratch, _cid, 82), [])


# --- medicines that are for peace only, and a refusal for want of AP ------------
# The Med_Pacific_ series says "Нельзя использовать в бою" and costs 0 AP, so
# only the server can keep it out of a fight; a refusal for AP brings the
# client's bar down to the pool, so it does not let the next one through too.
class _Medic(combat.Fighter):
    rc = None           # the room's combat, set by hand: only its ws is read


class _MedicSession(object):
    def __init__(self, store, cid):
        self.char_id, self.pos, self.room, self.loc = cid, 0, None, None
        self.sent = []
        self.char = progression.Character.load(store, cid)
        self.inv = inventory.Inventory(self, store)

    def send(self, *cmd, **params):
        self.sent.append((cmd[0], params))

    def character(self):
        return self.char

    def send_player_info(self):
        self.send("userInfo_Player", afro=self.char.afro)


def _at_war(ws):
    return type("RC", (), {"room": type("R", (), {"ws": ws})()})()


pacific = sorted(t for t, (r, n) in items.catalogue().items()
                 if r == items.HEAL and items.no_combat(t))
check("peace-only medicines: the 24 of the Med_Pacific_ series and nothing else",
      (len(pacific), all(items.catalogue()[t][1].startswith("Med_Pacific_") for t in pacific),
       items.no_combat(7100), items.no_combat(6055)), (24, True, False, False))


async def _heals():
    ms = _MedicSession(_scratch, _cid)
    medic = _Medic(ms)
    peace_only = inventory.oid_of(_scratch.create_item(
        _cid, 6904, items.HEAL, slot=inventory.BAG, use_count=1))
    for_war = inventory.oid_of(_scratch.create_item(
        _cid, 7100, items.HEAL, slot=inventory.BAG, use_count=1))
    medic.rc, medic.ap = _at_war(True), 100
    medic.use_heal({"obj": peace_only}, inventory.USE_IDLE)
    check("a peace-only medicine in a fight: one refusal, nothing started",
          (ms.sent, medic.healing, medic.ap), ([("cmdAck", {"res": inventory.RES_REFUSED})], None, 100))
    ms.sent, medic.ap = [], 2
    medic.use_heal({"obj": for_war}, inventory.USE_IDLE)
    check("a battle medicine without the AP: res=11, then the pool as it stands",
          ms.sent, [("cmdAck", {"res": inventory.RES_NO_AP}), ("c_ap", {"ap": 2})])
    ms.sent, medic.rc = [], _at_war(False)
    medic.use_heal({"obj": peace_only}, inventory.USE_IDLE)
    check("the peace-only one out of a fight: accepted",
          (ms.sent, medic.healing is not None), ([("cmdAck", {"res": 0})], True))
    medic.cancel_timers()
    # A medicine made when its type held more uses than it does now sells
    # for one of itself, not twenty: 6071 was twenty uses, is one today.
    old = _scratch.create_item(_cid, 6071, items.HEAL, slot=inventory.BAG, use_count=20)
    si = items.params_of(6071)
    ms.sent, before = [], ms.char.afro
    ms.inv.sell({"obj": inventory.oid_of(old)})
    check("a medicine with more uses than its type sells at the whole price, never above",
          (ms.char.afro - before, [p["res"] for n, p in ms.sent if n == "cmdAck"]),
          (max(1, int(si["cost"] / float(si.get("sell_num", 1)) * inventory.SMOD
                      * si.get("sell_mod", 1))), [0]))


asyncio.run(_heals())
_scratch.close()


# --- which level a mob's experience is measured against -------------------------
# By the skill that is being trained, not by the character's best one. A
# character who has shot his way to Стрельба 6 and picks up a knife is a
# beginner with the blade: the level-1 dog is five levels beneath his gun and
# one above his knife, and it has to pay the knife as a mob one level up pays
# a beginner. Measured against the best skill it paid nothing at all -- every
# creature a melee novice can actually hit sits four and more levels under his
# gun -- and the knife never trained.
class _XpSession(object):
    def __init__(self, ch):
        self.char, self.pushed = ch, []

    def character(self):
        return self.char

    def push_stats(self, **groups):
        self.pushed.append(groups)

    def push_vitals(self):
        pass


_shooter = progression.Character()
_shooter.skill[progression.SHOOTING] = [6, 0, progression.skill_xp_max(6)]
_shooter.recalc()
_blade = combat.Fighter(_XpSession(_shooter))
_dog = mobs.Mob(1, 82, 10)
# Harm worth a whole kill: health and stamina together are what a blow is
# measured against (Fighter.award_xp).
_whole = dog_stats.hp_max + dog_stats.sp_max
_blade.award_xp(progression.MELEE, combat.SPEC_BLADE, _whole, _dog)
check("a knife at Ближний бой 0 against the level-1 dog: a mob one level up, 20, times its 0.7",
      _shooter.skill[progression.MELEE][:2], [0, round(20 * dog_stats.xp_mult)])
_blade.award_xp(progression.SHOOTING, 2, _whole, mobs.Mob(2, 82, 10))
check("the same dog is worth nothing to Стрельба 6",
      _shooter.skill[progression.SHOOTING][:2], [6, 0])

# A bullet takes little stamina: the blows of a gun pay short of the price,
# and the kill settles the rest (RoomCombat.settle_xp). Health alone is half
# of the dog's health and stamina, so the pistol is paid half as it shoots
# and half at the death -- the same 14 the knife gets.
_gunner = progression.Character()
_gun = combat.Fighter(_XpSession(_gunner))
_gdog = mobs.Mob(3, 82, 10)
_gun.award_xp(progression.SHOOTING, 2, dog_stats.hp_max, _gdog)
_by_blows = _gunner.skill[progression.SHOOTING][1]
_grc = combat.RoomCombat.__new__(combat.RoomCombat)
_grc.room = type("R", (), {})()
_grc.room.players = {_gun.sess: None}
_grc.settle_xp(_gdog)
check("a gun's shots pay half the dog, its death the other half: 14, as for a knife",
      (_by_blows, _gunner.skill[progression.SHOOTING][:2]), (7, [0, 14]))
check("and the ledger is closed with the kill", _gdog.xp_ledger, {})


# --- what keeps a room at war -----------------------------------------------------
# The client greys its exit button for as long as the room is at war
# (LocationInterface.battleMode), whatever the server would answer to chWorld.
# So the war state is the rule itself: a creature after somebody here, a duel
# inside leave_combat_timeout, or a shot or swing still in the air -- and not
# the mere memory of having fired.
class _Seat(object):
    def __init__(self):
        self.combat = combat.Fighter(self)


_room = type("R", (), {})()
_room.players = {_Seat(): None, _Seat(): None}
_rc = combat.RoomCombat.__new__(combat.RoomCombat)
_rc.room = _room
_rc.mobs = {1: mobs.Mob(1, 82, 10)}
_first, _second = [s.combat for s in _room.players]
_T = 1000.0
check("nobody hunted, aiming or duelling: peace", _rc.hostilities(_T), False)
_rc.mobs[1].target = _second
check("a creature after one player holds the whole room", _rc.hostilities(_T), True)
_rc.mobs[1].target = None
_first.aim = object()
check("so does a burst still being aimed", _rc.hostilities(_T), True)
_first.aim = None
_first.last_pvp = _second.last_pvp = _T - combat.LEAVE_COMBAT_TIMEOUT + 1
check("and a duel inside leave_combat_timeout", _rc.hostilities(_T), True)
check("but not one past it", _rc.hostilities(_T + 2), False)

# --- the server -----------------------------------------------------------------
# AP regeneration is raised so the bar never throttles the fight, the respawn
# is shortened, and the dice are seeded. The exit timer is left at the game's
# own thirty seconds: a chWorld inside it has to be refused, and a room
# still at war half a minute after its last creature fell is exactly what
# the checks below have to be able to see. The wait a
# free resurrection costs goes to zero: that it is charged at all is
# test_death's business, and here it would only add fifteen seconds.
# The start cell is a server default and has moved since; these
# assertions name the market by number, so the suite says which
# world it wants.
# /goto, /give and /money are off on a served server and belong to
# the admin panel; this suite uses them to set a scene, so it asks
# for them by name.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB, LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730",
           LAVA_AP_REGEN="25", LAVA_LEAVE_COMBAT="30", LAVA_RESPAWN="4",
           LAVA_SEED="7", LAVA_START_AFRO="20000")
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
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.5):
        """Everything within an exact window, decoded to (name, params)."""
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._drain()

    def until(self, pred, wait=3.0):
        """Everything up to and including the first frame pred accepts, or
        everything that came before the window closed."""
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._drain()
            out += new
            if any(pred(f) for f in new):
                break
        return out

    def names(self, wait=0.5):
        return [n for n, _ in self.frames(wait)]


def named(frames, name):
    return [p for n, p in frames if n == name]


def only(frames, *names):
    """The frames of these names, in order: what a check is about, with the
    room's own traffic (a respawn, a war-state edge) left out."""
    return [(n, p) for n, p in frames if n in names]


def oids(p):
    return [str(x) for x in p["o_list"]]


def entity(target_id):
    """ss_use target for an entity: type digit 1 and the id in eight hex."""
    return "x1%08x" % target_id


def hexcell(cell):
    return "x0%08x" % cell


# The gun this suite shoots with is bought from the stall, not taken from
# the starting kit. The kit's Самострел eats "9мм даренные" and nothing else,
# and this stall does not sell them -- coupling the two only ever worked by
# accident, while the kit happened to carry an ordinary 9mm gun.
# The scenario shoots a dog from outside its aggro of five and inside the
# gun's own reach, so the gun has to reach further than six and a half cells.
# Of everything the stall sells, only the last two do; this is the cheaper.
PISTOL = 25646                       # СПС, eleven cells, a clip of eighteen
ROUNDS = 6103                        # СП-10 КС, which is what it takes
PISTOL_SI = items.params_of(PISTOL)
CLIP = PISTOL_SI["clip_size"]
COST = PISTOL_SI["fire_costs"][0]
# What holding it asks (inventory.item_level): the character's level below.
LEVEL = inventory.item_level(PISTOL)
# The blade: the first rung of the knives the stalls sell (knife_lvl1_A).
KNIFE = 6229
check("the knife is a cold arm", items.root_of(KNIFE), items.COLD_ARM)


def login(c, first=False):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@gunner@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    got = c.until(lambda f: f[0] == "lcall")
    return named(got, "lcall")[0]


def enter(c):
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return got, named(got, "lenter")[0]["pos"]


class FireTracker:
    """combat.md 10: hits only inside a faShot pair, pairs never nested, as
    many pairs per shooter as its faAim announced, usrUp never inside."""

    def __init__(self):
        self.expected = {}
        self.seen = {}
        self.open = None
        self.errors = []

    def feed(self, frames):
        for name, p in frames:
            sid = p.get("id", 0)
            if name == "faAim":
                if sid in self.expected and self.seen[sid] != self.expected[sid]:
                    self.errors.append("shooter %s: %d pairs for num_shots %d"
                                       % (sid, self.seen[sid], self.expected[sid]))
                self.expected[sid] = p.get("num_shots", 1)
                self.seen[sid] = 0
            elif name == "faShot":
                if p["status"] == 1:
                    if self.open is not None:
                        self.errors.append("pair opened inside a pair")
                    self.open = sid
                else:
                    if self.open != sid:
                        self.errors.append("pair closed by %s while %s open" % (sid, self.open))
                    self.open = None
                    self.seen[sid] = self.seen.get(sid, 0) + 1
            elif name in ("faHit", "faMiss", "faWall"):
                if self.open is None:
                    self.errors.append("%s outside a pair" % name)
            elif name == "usrUp" and self.open is not None:
                self.errors.append("usrUp inside a pair")

    def finish(self):
        for sid, n in self.expected.items():
            if self.seen.get(sid) != n:
                self.errors.append("shooter %s ended with %s pairs for %d"
                                   % (sid, self.seen.get(sid), n))
        return self.errors


def last_cell(frames, mob_id, default):
    """Where a mob's walks left it: the end of its last userMove path."""
    for n, p in reversed(frames):
        if n == "userMove" and p.get("id") == mob_id:
            return p["path"][-1]
    return default


def walk(c, loc, start, goal, avoid=()):
    """A real path (adjacent, off the obstacles) to the nearest goal cell,
    sent as the client would; returns the cell reached."""
    path = mobs.find_path(loc, start, goal, set(avoid))
    if path is None:
        raise RuntimeError("no path from %d" % start)
    if len(path) == 1:
        return start, []
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    got = c.until(lambda f: f[0] == "userMove" and f[1].get("id") == 0)
    check("walk accepted", [n for n, _ in got if n in ("cmdAck", "breakMv")][:1], ["cmdAck"])
    return path[-1], got


try:
    c = Client(connect())
    lcall = login(c, first=True)
    check("a peaceful location is called with ws=0", lcall["ws"], 0)
    arrival, pos = enter(c)
    npc = {p["name"]: p["id"] for n, p in arrival if n.startswith("userInfo")}
    TECHNOGEEK = npc[652]
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.frames()
    check("own bars on entry", [n for n, _ in got], ["userInfo_Player", "usrUp"])
    check("full at birth", (got[1][1]["hcur"], got[1][1]["hmax"]), (120, 120))

    # --- the level the pistol asks -----------------------------------------------
    # СПС asks Стрельба 5 of whoever holds it (inventory.py, "the level") and
    # a newborn is level 0. The level is the best skill, whichever it is, so
    # the character is made a level-5 industrialist between two sessions --
    # not a shooter: what a shot at the dog teaches is weighed below, and a
    # Стрельба five levels above the dog would be taught nothing.
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    store = accounts.Store(DB)
    char_id = store.db.execute("SELECT id FROM characters WHERE name = 'gunner'").fetchone()["id"]
    ch = progression.Character.load(store, char_id)
    ch.skill[progression.INDUSTRY] = [LEVEL, 0, progression.skill_xp_max(LEVEL)]
    ch.recalc()
    ch.save(store)
    store.close()
    c = Client(connect())
    login(c)
    arrival, pos = enter(c)
    npc = {p["name"]: p["id"] for n, p in arrival if n.startswith("userInfo")}
    TECHNOGEEK = npc[652]

    # --- the kit: rounds from the stall, the pistol worn and loaded ------------
    # The stall's own head, which is not the kit's pistol: it sells the models
    # the wiki named, starting at the cheapest.
    head = items.stock_for(1200)[0]
    stall = [p for p in named(arrival, "userInfo_Trader") if p["type_list"][:1] == [head]][0]
    c.send("ss_create;s_type=1;target=%d;" % stall["id"])
    c.frames()
    # The gun first, then its rounds, both from the stall.
    c.send("ss_upd;param=1;obj=x%x;s_status=1;" % stall["type_list"].index(PISTOL))
    got = c.frames()
    check("a pistol bought", [n for n, _ in got],
          ["cmdAck", "ss_obj_status", "ss_di_firearm", "userInfo_Player"])
    ammo_idx = stall["type_list"].index(ROUNDS)
    c.send("ss_upd;param=200;obj=x%x;s_status=1;" % ammo_idx)
    got = c.frames()
    check("200 rounds bought", [n for n, _ in got],
          ["cmdAck", "ss_obj_status", "ss_di_heap", "userInfo_Player"])
    rounds = str(got[1][1]["obj"])
    c.send("ss_upd;obj=x0;s_status=0;")
    c.frames(0.2)
    c.send("ss_get;target=0;slot=11;")
    lst = oids(c.frames()[0][1])
    # The kit's own pistol is in the hand already, so the bought one goes to
    # the other hand first and is swapped in.
    pistol = [o for o in lst[8:] if inventory.parse_oid(o)[1] == PISTOL][0]
    c.send("ss_move;obj=x%s;to=513;from=2048;" % pistol)
    c.frames()
    kit_gun = lst[6]
    if kit_gun != "0":
        c.send("ss_move;obj=x%s;to=2048;from=512;" % kit_gun)
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=513;" % pistol)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, pistol))
    got = c.frames()
    check("loading acknowledged", got[0], ("cmdAck", {"res": 0}))
    got = c.until(lambda f: f[0] == "ss_di_firearm")
    check("a full magazine", named(got, "ss_di_firearm")[0]["ammo_count"], CLIP)
    ammo = CLIP
    # A gun that has not been fired is as new as it will ever be, and the
    # client draws the bar from these two numbers.
    fresh = named(got, "ss_di_firearm")[0]
    check("and a whole gun to go with it", fresh["break"], fresh["max_break_cur"])
    brk = int(fresh["break"])

    # --- the errand, and a home to come back to ----------------------------------
    c.send("q_st;mob=%d;q_idx=%d;" % (TECHNOGEEK, quests.given_by(652).index(5)))
    got = c.frames()
    check("the dog quest is taken", got,
          [("cmdAck", {"res": 0}),
           ("q_di_kill_mobs", dict(q_id=FIRST_Q, q_type=5, complete=0, kill_num=[0]))])
    # With the technogeek, who offers "Прописка"; Aaron's safe is a bank.
    c.send("on_conv;mob=%d;op=0;" % TECHNOGEEK)
    check("home registered on the market", c.frames(), [("cmdAck", {"res": 0})])

    # --- no fighting on the market: one refusal, nothing else --------------------
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, hexcell(pos + 1)))
    got = c.frames()
    check("a shot in a peaceful location is refused with one ack",
          ([n for n, _ in got], got[0][1]["res"] != 0), (["cmdAck"], True))
    c.send("ss_use;type=16;obj=x0;target=%s;" % hexcell(pos + 1))
    got = c.frames()
    check("so is a punch", ([n for n, _ in got], got[0][1]["res"] != 0), (["cmdAck"], True))

    # --- effects: the window of five must be answered ------------------------------
    c.send("e_get_si;type=3;")
    got = c.frames()
    check("e_si comes back for the type asked", (got[0][0], got[0][1]["type"]), ("e_si", 3))
    check("with a preloaded string id for its name",
          got[0][1]["name"] == quests.EMPTY_STRING_ID, True)
    check("and the immob/stun flags", (got[0][1]["immob"], got[0][1]["stun"]), (0, 0))
    c.send("e_get_di;type=3;mobi_id=0;")
    got = c.frames()
    check("e_di answered", (got[0][0], got[0][1]["type"], got[0][1]["mobi_id"]), ("e_di", 3, 0))

    # --- the dump: mobs with levels, bars and weapons -----------------------------
    c.send("userMsg;entry=@/goto 100@;group=0;")
    got = c.until(lambda f: f[0] == "lcall")
    lcall = named(got, "lcall")[0]
    check("the dump is called with ws=0 although war=1", (lcall["id"], lcall["ws"]), (100, 0))
    arrival, pos = enter(c)
    loc = world.location(100)
    check("the player stands on the entry cell", pos, loc.entry_cell())
    seq = [(n, p) for n, p in arrival]
    mob_infos = [(i, p) for i, (n, p) in enumerate(seq) if n == "userInfo"]
    check("the dump has mobs", len(mob_infos) > 5, True)
    check("every mob's userInfo is followed at once by its usrUp",
          all(seq[i + 1][0] == "usrUp" and seq[i + 1][1]["id"] == p["id"]
              and seq[i + 1][1]["hcur"] == seq[i + 1][1]["hmax"] > 0
              for i, p in mob_infos), True)
    check("the dog is level 1, the bum level 3",
          sorted({(p["name"], p["lvl"]) for _, p in mob_infos if p["name"] in (82, 411)}),
          [(82, 1), (411, 3)])
    check("an empty effect list is pushed for the player",
          named(arrival, "e_list"), [dict(mobi_id=0, effects=[])])
    spawns = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    DOG_HOME = 4551
    dog = spawns[DOG_HOME]
    bum = [p["id"] for _, p in mob_infos if p["name"] == 411][0]
    dog_hp = [p for p in named(arrival, "usrUp") if p["id"] == dog][0]["hmax"]
    check("the dog's bar is the curve's", dog_hp, dog_stats.hp_max)

    c.send("ss_get;target=%d;slot=3;" % dog)
    check("a dog has bare paws: eight empty slots", oids(c.frames()[0][1]), ["0"] * 8)
    c.send("ss_get;target=%d;slot=3;" % bum)
    hands = oids(c.frames()[0][1])
    knife = inventory.parse_oid(hands[6])
    check("the bum holds a knife in the primary hand",
          (len(hands), hands[:6], hands[7], knife[1:]), (8, ["0"] * 6, "0", (195, items.COLD_ARM)))
    check("a virtual serial, far above the items table", knife[0] >= mobs.VIRTUAL_BASE, True)
    c.send("ss_get_di;obj=x%s;" % hands[6])
    got = c.frames()
    check("the knife's dynamic info is answered",
          (got[0][0], str(got[0][1]["obj"]), got[0][1]["break"] > 0), ("ss_di_coldarm", hands[6], True))
    c.send("ss_get_si;type=195;")
    check("and its static info", c.frames()[0][0], "ss_si_coldarm")

    # --- the first shot: ack, war state, aim, then the burst -----------------------
    check("the dog is out of its aggro radius but in pistol range",
          dog_stats.aggro < mobs.hex_distance(pos, DOG_HOME, loc.width) <= PISTOL_SI["max_range"][0],
          True)
    tracker = FireTracker()
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, entity(dog)))
    got = c.frames(0.3)
    check("ack, then the room goes to war, then the aim",
          got, [("cmdAck", {"res": 0}), ("lch", {"ws": 1}),
                ("faAim", dict(id=0, ang=mobs.direction(pos, DOG_HOME, loc.width), num_shots=1))])
    tracker.feed(got)
    # The magazine report closes the burst; the experience and the dog's
    # reaction follow it in the same breath, so the window is held open a
    # moment longer to catch them.
    got = c.until(lambda f: f[0] == "ss_di_firearm") + c.frames(0.4)
    tracker.feed(got)
    names_ = [n for n, _ in got]
    first = names_.index("faShot")
    burst = names_[first:first + 3]
    check("one pair around the bullet's fate",
          (burst[0], burst[1] in ("faHit", "faMiss", "faWall"), burst[2]), ("faShot", True, "faShot"))
    check("the pair is the player's, open then closed",
          [p for n, p in got if n == "faShot"], [{"id": 0, "status": 1}, {"id": 0, "status": 0}])
    hit = named(got, "faHit")
    tail = names_[first + 3:]
    if hit:
        check("a hit names the dog and its damage",
              (hit[0]["target"], hit[0]["dmg"] + hit[0]["sdmg"] > 0), (dog, True))
        check("after the pair: the dog's bars, then c_ap, then the magazine",
              tail[:3], ["usrUp", "c_ap", "ss_di_firearm"])
        check("the dog's bar dropped",
              [p["hcur"] < dog_hp for n, p in got if n == "usrUp" and p["id"] == dog], [True])
        check("experience pushed for shooting",
              [bool(p["xp_skills_mask"] & 2) for p in named(got, "rp_info")][:1], [True])
    else:
        check("after the pair: c_ap, then the magazine", tail[:2], ["c_ap", "ss_di_firearm"])
    check("the burst cost one shot's action points", named(got, "c_ap")[0]["ap"], 50 + 5 * LEVEL - COST)
    ammo -= 1
    check("the magazine lost a round", named(got, "ss_di_firearm")[0]["ammo_count"], ammo)
    # And the gun lost a point with it. A whole point: Store writes these
    # fields through int(), so anything fractional would round to nothing and
    # the durability bar would sit full for ever, which is the fault this
    # check exists to catch.
    brk -= 1
    check("and the gun a point of durability",
          int(named(got, "ss_di_firearm")[0]["break"]), brk)
    check("the dog turns on the shooter, and the room stays at war",
          [p for n, p in got if n == "lch"], [{"enemy": dog}])
    dog_cell = last_cell(got, dog, DOG_HOME)

    # --- leaving is refused while the exit timer runs -----------------------------------
    # The dog took the shooter as its target above and keeps him, but that is
    # not what shuts the exit: the exit timer is, which every hit given or
    # taken starts (the client's own countdown, LocationInterface.
    # startExitTimer), and which runs thirty seconds here. A bullet that found
    # the dog has started it; one that missed has not, and then the way out
    # is still open -- so the door is tried at the first hit of the fight,
    # the player's or the dog's, whichever comes first (try_exit).
    # /home goes through the same gate and is refused too, in a line of
    # chat rather than a second cmdAck. Not checked inside this scene: the
    # fight below is scripted frame by frame, and one more command in the
    # middle gives the dog half a second it does not have in the script.
    exit_tried = []

    def try_exit(frames):
        """chWorld once a hit has gone either way: res=39 and no gmap. Only
        the player and the dog fight here, and the dog has no gun, so any
        faHit or caHit is one the player gave or took. The frames it brings
        back, for the tracker and the dog's whereabouts."""
        if exit_tried or not [n for n, _ in frames if n in ("faHit", "caHit")]:
            return []
        exit_tried.append(True)
        c.send("chWorld;")
        got = c.frames(0.4)
        check("chWorld while the exit timer runs: res=39 and no gmap",
              [(n, p) for n, p in got if n in ("cmdAck", "gmap", "lcall")],
              [("cmdAck", {"res": 39})])
        return got

    got = try_exit(got)
    tracker.feed(got)
    dog_cell = last_cell(got, dog, dog_cell)

    # --- moving cancels the aim, at no cost --------------------------------------------
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, entity(dog)))
    got = c.until(lambda f: f[0] == "faAim" and f[1].get("id") == 0, 1)
    # This aim is about to be cancelled by a walk and owes no pairs.
    tracker.feed([f for f in got if not (f[0] == "faAim" and f[1].get("id") == 0)])
    dog_cell = last_cell(got, dog, dog_cell)
    check("second aim taken", [p for n, p in got if n == "faAim" and p["id"] == 0] != [], True)
    step = [n for n in progression.hex_neighbours(pos, loc.width, loc.height)
            if n not in loc.obstacles and n != dog_cell]
    step = max(step, key=lambda n: mobs.hex_distance(n, DOG_HOME, loc.width))
    c.send("moveTo;path=|%d|%d|;" % (pos, step))
    old_pos, pos = pos, step
    got = c.frames(1.5)
    tracker.feed(got)
    dog_cell = last_cell(got, dog, dog_cell)
    check("the walk is acknowledged and echoed",
          [(n, p) for n, p in got if n in ("cmdAck", "userMove") and p.get("id", 0) == 0][:2],
          [("cmdAck", {"res": 0}), ("userMove", {"id": 0, "path": [old_pos, pos]})])
    check("no bullet leaves after the walk",
          [p for n, p in got if n == "faShot" and p.get("id", 0) == 0], [])
    check("and nothing is charged or reported",
          [n for n, _ in got if n in ("c_ap", "ss_di_firearm")], [])
    c.send("ss_get_di;obj=x%s;" % pistol)
    got = c.until(lambda f: f[0] == "ss_di_firearm")
    tracker.feed([f for f in got if f[0] != "ss_di_firearm"])
    dog_cell = last_cell(got, dog, dog_cell)
    check("the magazine is untouched", named(got, "ss_di_firearm")[0]["ammo_count"], ammo)

    # --- the fight to the death ----------------------------------------------------------
    bites = hits_on_me = punched = 0
    ap_max = 50 + 5 * LEVEL
    dead_frames = None
    for attempt in range(60):
        if ammo == 0:
            c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, pistol))
            got = c.until(lambda f: f[0] == "ss_di_firearm" and str(f[1]["obj"]) == pistol, 3)
            tracker.feed(got)
            ammo = named(got, "ss_di_firearm")[-1]["ammo_count"]
            check("reloaded mid-fight", ammo, CLIP)
        c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, entity(dog)))
        got = c.until(lambda f: f[0] == "ss_di_firearm" or (f[0] == "cmdAck" and f[1]["res"] != 0), 3)
        got += c.frames(0.2)
        if not [p for n, p in got if n == "lch" and p.get("dead") == dog]:
            got += try_exit(got)
        tracker.feed(got)
        for i, (n, p) in enumerate(got):
            if n == "userMove" and p.get("id") == dog:
                dog_cell = p["path"][-1]
            elif n == "rp_info" and p.get("ap_max"):
                ap_max = p["ap_max"]          # a level-up widens the pool
            elif n == "caHit" and p.get("id") == dog:
                bites += 1
                check("a bite lands on the player as target 0", p["target"], 0)
                check("and the player's own bars follow it at once",
                      (got[i + 1][0], got[i + 1][1].get("id")), ("usrUp", 0))
                hits_on_me += 1
            elif n == "caMiss" and p.get("id") == dog:
                bites += 1
        if [p for n, p in got if n == "lch" and p.get("dead") == dog]:
            dead_frames = got
            break
        acks = named(got, "cmdAck")
        if acks and acks[0]["res"] != 0:
            check("only 'not enough AP' may refuse a shot mid-fight", acks[0]["res"], 11)
            time.sleep(0.7)
            continue
        if named(got, "ss_di_firearm"):
            ammo = named(got, "ss_di_firearm")[-1]["ammo_count"]
        if not punched and mobs.adjacent(pos, dog_cell, loc):
            # The dog is at the player's side: a bare-handed strike, which
            # lands at once (strike_time 0) and costs 5 AP.
            c.send("ss_use;type=16;obj=x0;target=%s;" % entity(dog))
            got = c.until(lambda f: f[0] == "c_ap", 2) + c.frames(0.2)
            tracker.feed(got)
            dog_cell = last_cell(got, dog, dog_cell)
            names_ = [n for n, _ in got]
            swing = [(n, p) for n, p in got if n in ("caHit", "caMiss") and p.get("id", 0) == 0]
            check("a punch: ack, then one caHit or caMiss of the player's",
                  (names_[0], len(swing)), ("cmdAck", 1))
            if swing[0][0] == "caHit":
                check("the punch names the dog", swing[0][1]["target"], dog)
                check("the dog's bars follow the punch",
                      [p["id"] for n, p in got if n == "usrUp" and p["id"] == dog] != [], True)
            else:
                check("a miss names the dog's hex", swing[0][1]["hex"], dog_cell)
            # The pool refills to the maximum between actions at the test's
            # regeneration, so the punch leaves at most max - 5.
            check("the fist costs 5 AP", named(got, "c_ap")[-1]["ap"] <= ap_max - combat.FIST_AP, True)
            punched = 1
            if [p for n, p in got if n == "lch" and p.get("dead") == dog]:
                dead_frames = got
                break
    check("the dog died within sixty shots", dead_frames is not None, True)
    check("and the door was tried while the timer ran", exit_tried, [True])
    check("the dog came and bit", bites > 0, True)
    # Whether one of its bites landed is the dog's luck: with the scatter
    # (combat.cone_of) the pistol hits every time this close, and the dog is
    # dead within three shots, one or two bites in. A bite that did land was
    # checked above for the usrUp behind it; the one that kills, below.
    check("every burst kept its shape", tracker.finish(), [])
    names_ = [n for n, _ in dead_frames]
    i_dead = [i for i, (n, p) in enumerate(dead_frames) if n == "lch" and p.get("dead") == dog][0]
    check("the kill is reported to the journal right after lch;dead",
          dead_frames[i_dead + 1], ("q_di_kill_mobs", dict(q_id=FIRST_Q, q_type=5, complete=0,
                                                         kill_num=[1])))
    dog_cell = last_cell(dead_frames, dog, dog_cell)
    # The dog was the only creature after the player, so the room is at
    # peace the moment it falls: lch;ws=0 right behind its lch;dead, not
    # leave_combat_timeout after the last shot. Held any longer, the client
    # keeps its exit button greyed (LocationInterface.battleMode) over a
    # fight that is over.
    ws_off = lambda f: f[0] == "lch" and f[1].get("ws") == 0
    tail = list(dead_frames)
    if not any(ws_off(f) for f in tail):
        tail += c.until(ws_off, 1.5)
    check("the room leaves the war state as its last hunter falls",
          [p for n, p in tail if n == "lch" and "ws" in p], [{"ws": 0}])
    got = c.until(lambda f: f[0] == "ss_loot", 4)
    check("the corpse fades and a bag appears where it fell",
          only(got, "lch", "ss_loot"),
          [("lch", {"lostUser": dog}), ("ss_loot", {"s_status": 1, "hex": [dog_cell]})])
    # From here the room's own life goes on around the checks: the dog
    # respawns whenever that falls, and the peace has to hold meanwhile;
    # both are gathered and judged at the end.
    after = list(got)

    # --- the bag -------------------------------------------------------------------------------
    if not progression.within_reach(pos, dog_cell, loc.width, loc.height):
        pos, got = walk(c, loc, pos, lambda cell: mobs.adjacent(cell, dog_cell, loc), avoid={dog_cell})
        after += got
    c.send("ss_create;s_type=0;target=%d;" % dog_cell)
    got = c.frames()
    after += got
    check("the bag opens", only(got, "cmdAck"), [("cmdAck", {"res": 0})])
    c.send("ss_get;slot=24;")
    got = c.frames()
    after += got
    lst = oids(named(got, "ss_ack")[0])
    divider = lst.index("0")
    bag, loot = lst[:divider], lst[divider + 1:]
    check("the bag lists the player's things, a 0, then the loot",
          (pistol not in bag, rounds in bag, len(loot) >= 1), (True, True, True))
    # What a dog leaves is meat for certain and the fang and the skin on a
    # coin toss each (mobs.ANIMAL_LOOT), and the checks below need a second
    # piece: a bag closes with its last one and code 2 has no bag to put it
    # back into. LAVA_SEED decides the toss, so the dependency is stated here
    # rather than surfacing as a puzzling frame mismatch further down.
    check("the corpse holds more than one piece", len(loot) >= 2, True)
    kinds = sorted({inventory.parse_oid(o)[1] for o in loot})
    check("a dog leaves meat, and maybe a fang or a skin",
          all(k in (216, 217, 218) for k in kinds) and 216 in kinds, True)
    c.send("ss_get_di;obj=x%s;" % loot[0])
    got = c.frames()
    after += got
    check("loot has dynamic info like anything else",
          [(n, p["size"]) for n, p in got if n == "ss_di_heap"], [("ss_di_heap", 1)])
    c.send("ss_upd;s_status=1;obj=x%s;param=1;" % loot[0])
    got = c.frames()
    after += got
    check("one piece taken", only(got, "cmdAck", "ss_loot", "ss_obj_status"), [("cmdAck", {"res": 0})])
    c.send("ss_get;slot=8;")
    got = c.frames()
    after += got
    check("it is in the bag under the same id", loot[0] in oids(named(got, "ss_ack")[0]), True)
    c.send("ss_upd;s_status=2;obj=x%s;param=1;" % loot[0])
    got = c.frames()
    after += got
    check("and put back", only(got, "cmdAck", "ss_loot", "ss_obj_status"), [("cmdAck", {"res": 0})])
    c.send("ss_get;slot=24;")
    got = c.frames()
    after += got
    lst = oids(named(got, "ss_ack")[0])
    check("back on the ground", loot[0] in lst[lst.index("0") + 1:], True)
    c.send("ss_upd;s_status=3;obj=x0;param=1;")
    got = c.frames()
    after += got
    check("take all: ack, then the empty bag vanishes",
          only(got, "cmdAck", "ss_loot", "ss_obj_status"),
          [("cmdAck", {"res": 0}), ("ss_loot", {"s_status": 0, "hex": [dog_cell]})])
    c.send("ss_get;slot=8;")
    got = c.frames()
    after += got
    check("everything is in the bag", all(o in oids(named(got, "ss_ack")[0]) for o in loot), True)
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    got = c.frames(0.3)
    after += got
    check("closing the bag is answered with nothing", only(got, "cmdAck", "ss_ack", "ss_loot"), [])
    # Out of the way of the dog that is about to come back, so peace can hold.
    pos, got = walk(c, loc, pos,
                    lambda cell: mobs.hex_distance(cell, DOG_HOME, loc.width) >= dog_stats.aggro + 1.5
                    and mobs.hex_distance(cell, DOG_HOME, loc.width) <= PISTOL_SI["max_range"][0] - 2)
    after += got

    # --- peace returns, the dog too ---------------------------------------------------------------
    after += c.frames(8)
    got = after
    tracker2 = FireTracker()
    tracker2.feed(got)
    check("nothing shoots while nobody fights", tracker2.finish(), [])
    check("and peace holds while the bag is emptied and the dog comes back",
          [p for n, p in got if n == "lch" and "ws" in p], [])
    back = [i for i, (n, p) in enumerate(got) if n == "lch" and p.get("newUser") == dog]
    check("the dog respawns under its old id on its spawn cell",
          [got[i][1] for i in back], [dict(newUser=dog, pos=DOG_HOME, rtype=0)])
    i = back[0]
    check("with its details and full bars right behind",
          (got[i + 1][0], got[i + 1][1]["id"], got[i + 1][1]["lvl"],
           got[i + 2][0], got[i + 2][1]["id"], got[i + 2][1]["hcur"]),
          ("userInfo", dog, 1, "usrUp", dog, dog_hp))
    # A blow that nothing answers must not hold the player: the exit is shut
    # by the timer a hit starts, not by having swung. The dog has respawned
    # and is minding its own business, so a swing at bare ground wakes nobody,
    # hits nothing, and leaves the way out open.
    ground = [n for n in progression.hex_neighbours(pos, loc.width, loc.height)
              if n not in loc.obstacles and n != DOG_HOME]
    c.send("ss_use;type=16;obj=x0;target=%s;" % hexcell(ground[0]))
    got = c.frames(1.5)
    check("the swing at empty ground was accepted",
          [p["res"] for n, p in got if n == "cmdAck"][:1], [0])
    # The swing opens the war state -- the bar has to be charged -- and with
    # nothing woken by it the room closes it again on its next tick.
    check("and the room is at peace again as soon as it has landed",
          [p for n, p in got if n == "lch" and "ws" in p], [{"ws": 1}, {"ws": 0}])
    c.send("chWorld;")
    got = c.frames()
    check("a blow nothing answered leaves the way out open",
          [n for n, _ in got], ["cmdAck", "gmap", "marks"])
    # Back into the dump before logging out: a character that logs out on
    # the map is restored with on_map set, and the next sessions fight here.
    c.send("userMsg;entry=@/goto 100@;group=0;")
    c.until(lambda f: f[0] == "lcall")
    arrival, pos = enter(c)
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.until(lambda f: f[0] == "usrUp")
    check("the fight left the player alive", named(got, "usrUp")[0]["hcur"] > 0, True)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()

    # --- a heal, on a wounded character with a bandage slipped into the bag -----------------
    store = accounts.Store(DB)
    char_id = store.db.execute("SELECT id FROM characters WHERE name = 'gunner'"
                               ).fetchone()["id"]
    heal_type = next(t for t, (root, name) in sorted(items.catalogue().items())
                     if root == items.HEAL and items.params_of(t) is not None)
    heal_row = store.create_item(char_id, heal_type, items.HEAL, slot=inventory.BAG, use_count=1)
    store.save_character_state(char_id, hp=60, sp=0)
    store.close()
    heal_oid = inventory.oid_of(heal_row)
    HEAL_SI = items.params_of(heal_type)

    c = Client(connect())
    lcall = login(c)
    check("the character is back in the dump", lcall["id"], 100)
    arrival, pos = enter(c)
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.until(lambda f: f[0] == "usrUp")
    check("wounded as written", (named(got, "usrUp")[0]["hcur"], named(got, "usrUp")[0]["scur"]), (60, 0))
    c.send("ss_use;type=2;obj=x%s;" % heal_oid)
    got = c.frames(0.3)
    check("a bandage: one ack at once", got, [("cmdAck", {"res": 0})])
    got = c.until(lambda f: f[0] == "ss_obj_status", HEAL_SI["heal_time"] / 1000.0 + 1.5)
    got += c.frames(0.3)         # the experience follows the item's removal
    heal = named(got, "heal")
    check("then, after heal_time, an absolute heal frame for oneself",
          (len(heal), heal and heal[0]["id"], heal and heal[0]["target"]), (1, 0, 0))
    check("healed by the item's range, stamina too",
          (HEAL_SI["min_h_rest"] <= heal[0]["hp"] - 60 <= HEAL_SI["max_h_rest"],
           heal[0]["sp"] >= 0), (True, True))
    check("a single-use bandage is removed",
          [(str(p["obj"]), p["status"]) for p in named(got, "ss_obj_status")], [(heal_oid, 0)])
    check("medicine gained experience",
          [bool(p["xp_skills_mask"] & 4) for p in named(got, "rp_info")], [True])
    c.send("logout;")
    c.frames(0.3)
    c.s.close()

    # --- a knife, in the hand of a character who has only ever shot -----------------------------
    # Стрельба 6 and Ближний бой 0, written into the database the way a
    # character who shot his way up would have them; the pistol goes to the
    # bag and a stall's knife into the hand. A blow that does not crit lands
    # on the dog's stamina first (wiki "Ближний бой"), and the dog has as
    # much of it as of health, so the first blows take no health at all:
    # they must train the blade all the same, and the kill must bring the
    # whole to the dog's price.
    store = accounts.Store(DB)
    ch = progression.Character.load(store, char_id)
    ch.skill[progression.MELEE] = [0, 0, progression.skill_xp_max(0)]
    ch.skill[progression.SHOOTING] = [6, 0, progression.skill_xp_max(6)]
    ch.recalc()
    ch.hp = ch.sp = None
    ch.save(store)
    pistol_uniq = inventory.parse_oid(pistol)[0]
    store.update_item(pistol_uniq, slot=inventory.BAG)
    fields = inventory.new_fields(KNIFE)
    knife_root = fields.pop("root")
    fields["slot"] = inventory.PRIMARY
    knife_row = store.create_item(char_id, KNIFE, knife_root, **fields)
    store.close()
    knife = inventory.oid_of(knife_row)

    c = Client(connect())
    login(c)
    arrival, pos = enter(c)
    spawns = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    check("the dog is home again for the knife", spawns.get(DOG_HOME), dog)
    c.send("rp_get_info;")
    rp = named(c.until(lambda f: f[0] == "rp_info"), "rp_info")[0]
    check("a shooter's hands: Стрельба 6, Ближний бой 0 of 100",
          (rp["a_skills"][:2], rp["xp_skills"][:2], rp["xp_max_skills"][0]), ([0, 6], [0, 0], 100))
    # Into the dog's aggro radius; it comes the rest of the way itself.
    pos, got = walk(c, loc, pos,
                    lambda cell: mobs.hex_distance(cell, DOG_HOME, loc.width) <= dog_stats.aggro - 0.5,
                    avoid={DOG_HOME})
    dog_cell = last_cell(got, dog, DOG_HOME)
    # What the server must have paid, worked out from what the blows did:
    # each the part of the dog's health and stamina it took, of the price of
    # a mob one level above the blade (20, times the dog's 0.7), and the kill
    # whatever those parts left of a whole (progression.mob_xp,
    # Fighter.award_xp, RoomCombat.settle_xp).
    mirror = progression.Character()
    whole, paid = float(dog_stats.hp_max + dog_stats.sp_max), [0.0]

    def pay(share):
        paid[0] += share
        mirror.gain_xp(progression.MELEE, mirror.carry_xp(progression.MELEE, progression.mob_xp(
            dog_stats.level, mirror.skill_level(progression.MELEE), share, dog_stats.xp_mult)),
            spec_on_top=True)

    dog_hp = dog_stats.hp_max
    stamina_trained, stamina_only, shooting_pushed, dead_frames = [], 0, 0, None
    for attempt in range(80):
        if mobs.adjacent(pos, dog_cell, loc):
            c.send("ss_use;type=16;obj=x%s;target=%s;" % (knife, entity(dog)))
            got = c.until(lambda f: f[0] == "c_ap" or (f[0] == "cmdAck" and f[1]["res"] != 0), 2)
            got += c.frames(0.2)
        else:
            got = c.frames(0.4)
        dog_cell = last_cell(got, dog, dog_cell)
        for i, (n, p) in enumerate(got):
            if n == "rp_info" and p["xp_skills_mask"] & 2:
                shooting_pushed += 1
            if not (n == "caHit" and p.get("id", 0) == 0 and p["target"] == dog):
                continue
            to_hp = min(p["dmg"], dog_hp)
            dog_hp -= to_hp
            harm = to_hp + p["sdmg"]
            if harm <= 0:
                continue
            stamina_only += p["dmg"] == 0
            pay(min(harm / whole, 1.0 - paid[0]))
            if p["dmg"] == 0:
                stamina_trained.append(any(m == "rp_info" and q["xp_skills_mask"] & 1
                                           for m, q in got[i + 1:]))
        if [p for n, p in got if n == "lch" and p.get("dead") == dog]:
            dead_frames = got
            break
    pay(1.0 - paid[0])             # the kill settles the rest
    check("the dog died to the knife", dead_frames is not None, True)
    check("some blows took stamina only", stamina_only > 0, True)
    check("the blows that took stamina only trained Ближний бой as well",
          any(stamina_trained), True)
    check("and not one of them Стрельба", shooting_pushed, 0)
    c.send("rp_get_info;")
    rp = named(c.until(lambda f: f[0] == "rp_info"), "rp_info")[0]
    check("the kill paid Ближний бой the dog's whole price, 20 times its 0.7",
          (rp["a_skills"][0], rp["xp_skills"][0]), (0, round(20 * dog_stats.xp_mult)))
    check("to exactly what the owner's rule makes of those blows",
          [rp["a_skills"][0], rp["xp_skills"][0]], mirror.skill[progression.MELEE][:2])
    check("while Стрельба is where it was", (rp["a_skills"][1], rp["xp_skills"][1]), (6, 0))
    # The dog was all that was after him: peace at once, and the way out.
    tail = list(dead_frames)
    if not any(ws_off(f) for f in tail):
        tail += c.until(ws_off, 1.5)
    check("a knife kill ends the war state as a shot does",
          [p for n, p in tail if n == "lch" and "ws" in p], [{"ws": 0}])
    c.send("chWorld;")
    got = c.frames()
    check("and the way out is open at once",
          [(n, p.get("res")) for n, p in got if n in ("cmdAck", "gmap")], [("cmdAck", 0), ("gmap", None)])
    c.send("userMsg;entry=@/goto 100@;group=0;")
    c.until(lambda f: f[0] == "lcall")
    arrival, pos = enter(c)
    if dog not in [p["newUser"] for p in named(arrival, "lch") if "newUser" in p]:
        c.until(lambda f: f[0] == "lch" and f[1].get("newUser") == dog, 10)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    # The pistol back into the hand for what follows.
    store = accounts.Store(DB)
    store.update_item(knife_row["uniq"], slot=inventory.BAG)
    store.update_item(pistol_uniq, slot=inventory.PRIMARY)
    store.close()

    # --- death and resurrection ------------------------------------------------------------------
    store = accounts.Store(DB)
    store.save_character_state(char_id, hp=2, sp=0)
    store.close()
    c = Client(connect())
    login(c)
    arrival, pos = enter(c)
    spawns = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    check("the dog is back on its cell for the newcomer", spawns.get(DOG_HOME), dog)
    c.send("ss_get;target=0;slot=2;")
    check("the pistol is still in hand", oids(c.frames()[0][1])[0], pistol)
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, entity(dog)))
    got = c.until(lambda f: f[0] == "lch" and f[1].get("dead") == 0, 30)
    check("the dog kills the wounded player: lch;dead=0",
          [p for n, p in got if n == "lch" and "dead" in p], [{"dead": 0}])
    bitten = [i for i, (n, p) in enumerate(got) if n == "caHit" and p.get("id") == dog]
    check("with a bite", len(bitten) >= 1, True)
    check("and the player's own bars followed the bite at once",
          [(got[i + 1][0], got[i + 1][1].get("id")) for i in bitten[-1:]], [("usrUp", 0)])
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, entity(dog)))
    got = c.frames(0.5)
    check("dead: a shot is refused with an ack and nothing follows",
          [(n, p) for n, p in got if n in ("cmdAck", "faAim")], [("cmdAck", {"res": 3})])
    c.send("moveTo;path=|%d|%d|;" % (pos, pos + 1))
    # The dog's own walk home after the kill (userMove;id=<dog>) is not the
    # dead player's; only his would be the fault.
    check("dead: a walk is dropped",
          [n for n, p in c.frames(0.4)
           if n in ("cmdAck", "breakMv") or (n == "userMove" and p.get("id") == 0)], [])
    # "Частичное восстановление", pressed the moment the body falls: the
    # window's countdown is only there to press it for whoever does not.
    c.send("resurrect;res_type=0;")
    got = c.until(lambda f: f[0] == "lcall", 2)
    check("resurrection is acknowledged and the character is called home",
          [(n, p.get("res", p.get("id"))) for n, p in got if n in ("cmdAck", "lcall")],
          [("cmdAck", 0), ("lcall", 102)])
    arrival, pos = enter(c)
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.until(lambda f: f[0] == "usrUp")
    v = named(got, "usrUp")[0]
    # A free resurrection is the penalised one: the 10% of health and of
    # stamina its window prints (combat.Fighter.resurrect). The prices and
    # the rest of what dying costs are test_death's.
    check("alive at home, on a free resurrection's tenth of HP and stamina",
          (v["hcur"], v["hcur"] < v["hmax"], v["scur"]),
          (max(1, v["hmax"] * 10 // 100), True, v["smax"] * 10 // 100))
    c.send("logout;")
    c.frames(0.3)
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
print("combat OK")
