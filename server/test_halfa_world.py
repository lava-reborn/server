"""Вади-Хальфа's map and population, made ready for its quests (the owner's
«займись фулл восстановлением Вади-Хальфы», 2026-09-28): the places, who
stands in them, and the things there that are made to be broken.

  * the quest places and camps the map's tooltips and the wiki's quests put
    on cells of their own (data/settlements_verified.json): each cell leads
    into its file and the file back to its cell, and every one of them is a
    walk from the Причал (5965,1728) -- none of them shut away;
  * the camps' empty slots (type 0) filled with their faction, in the band
    the tooltips give (data/camp_fill.json): 80/81/84/85 stand nine
    fighters and more each, the chiefs' places 82/83/86/87 their chief and
    the fill, «Механик ДСР» (122) its ДСР of levels 7-8; and nothing
    changes where the table says nothing -- the valley's camp 34, the slave
    traders' camp 88;
  * the objects of STANDING_OBJECTS stand where they are listed and nowhere
    else: the «ящик спирта» of 64 takes a shot, dies, counts as a kill, is
    gone and comes back whole; the Tir's targets and the quarry's stones
    stand; the turrets of «Огневые установки» (141) shoot and never walk;
  * the range's targets stand beyond the booth's counter, which a bullet
    flies over there and nowhere else (world.SHOOT_OVER): each of them can
    be shot from the booth, and one of TIR_01 falls, counts and comes back
    (on a socket: test_halfa_tir.py);
  * the town's people a seasonal token used to take are back (662, 711,
    1977, 423, 425) while Савин's presents and the developers' stand-ins
    stay out; Ольсен (431) waits for goods of his own, since the only stall
    he has is a low-confidence guess at Донгола's «Генрих»;
  * the «Главарь бандитов» (696) and the colonists' treasurer (586) stand at
    noon, when the other bosses are gone (bosses.ALL_DAY).

    LAVA_RES=.../lava/res python3 server/test_halfa_world.py
"""
import asyncio
import collections
import json
import os
import re
import sys
from types import SimpleNamespace

# The boss clock at noon, Moscow time, on the owner's hours: outside every
# window, so a boss that keeps the hours is gone and one that does not stands.
os.environ["LAVA_BOSS_HOURS"] = "18,20"
os.environ["LAVA_BOSS_STAY"] = "60"
os.environ["LAVA_BOSS_CLOCK"] = "2026-09-28T12:00:00"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bosses        # noqa: E402
import combat        # noqa: E402
import mobs          # noqa: E402
import names         # noqa: E402
import npcs          # noqa: E402
import progression   # noqa: E402
import rooms         # noqa: E402
import world         # noqa: E402

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


MT = world.mob_types()
START = (5965, 1728)            # the Причал, where the valley's ride arrives

# --- the cells ------------------------------------------------------------------------
NEW_CELLS = {
    (5987, 1699): 62, (6038, 1721): 201, (6008, 1742): 117, (5973, 1727): 47,
    (5986, 1725): 64, (5976, 1720): 137, (5972, 1735): 139, (5963, 1736): 141,
    (5979, 1732): 138, (5970, 1741): 142, (5988, 1714): 122, (5984, 1735): 158,
    (5988, 1735): 160, (5971, 1731): 108, (5967, 1737): 45, (5975, 1733): 46,
    (5971, 1723): 82, (5979, 1728): 83, (5975, 1738): 86, (5992, 1720): 87,
    (5972, 1738): 61, (5957, 1733): 44,
}
CAMPS = {(5970, 1724): 80, (5978, 1727): 81, (5974, 1739): 84, (5993, 1721): 85}

check("every new cell leads into its file",
      {c: world.location_at(*c) for c in NEW_CELLS}, NEW_CELLS)
check("and every file back to its cell (world.cell_of)",
      {c: world.cell_of(i) for c, i in NEW_CELLS.items()}, {c: c for c in NEW_CELLS})
check("the four camps keep their first cell, and only it, now that the second is the chief's",
      ({c: world.location_at(*c) for c in CAMPS},
       sorted(c for c, i in world.settlements().items() if i in CAMPS.values())),
      (CAMPS, sorted(CAMPS)))
check("283 (Apoc_Oasis) is off the hermit's oasis and on no other cell",
      [c for c, i in world.settlements().items() if i == 283], [])


def walk_from(start):
    """Every map cell reachable on foot, a side at a time (test_borders)."""
    seen = {start}
    queue = collections.deque([start])
    while queue:
        x, y = queue.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in seen and world.passable(*n):
                seen.add(n)
                queue.append(n)
    return seen


reach = walk_from(START)
check("a walk from the Причал reaches every new cell (none is stranded behind a wall)",
      sorted(c for c in list(NEW_CELLS) + list(CAMPS) if c not in reach), [])

# --- who stands in them -------------------------------------------------------------------


def room(loc_id):
    return rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)


def stood(r):
    return collections.Counter(n.type_id for n in r.npcs.values())


def prefix(t):
    m = re.match(r"^([A-Za-z]+?)_", MT[t][1])
    return m.group(1).lower() if m else None


BANDS = {80: ("nc", 0, 2), 81: ("lu", 2, 4), 84: ("ja", 4, 6), 85: ("mg", 6, 8)}
for loc_id, (fac, lo, hi) in sorted(BANDS.items()):
    r = room(loc_id)
    loc = r.loc
    fighters = [n.type_id for n in r.npcs.values()
                if n.root == world.MOB and prefix(n.type_id) == fac
                and world.creature_role(n.type_id) in ("mob", "boss")]
    check("camp %d stands %d fighters of %s_, every one of levels %d-%d (the tooltip's band)"
          % (loc_id, len(fighters), fac, lo, hi),
          (len(fighters) >= 9, all(lo <= mobs.stats(t).level <= hi for t in fighters)), (True, True))
    check("  ..and every slot of its file stands: the empty ones filled, the chief, the boxes",
          len(r.npcs), len(loc.spawns))
    check("  ..its empty slots are the table's, one for one",
          sum(1 for _c, t in loc.spawns if t == 0), len(world.camp_fill(loc_id)))

check("the colonists' camp has its treasurer, the commissar of «Реклама» (586)",
      stood(room(80))[586], 1)
check("the sect's camp has lu_Looser (336) of «Театр жизни»", stood(room(81))[336], 1)
check("the Janjaweed camp has the level-5 diversants of «Бандитская активность» (291)",
      stood(room(84))[291] >= 3, True)
check("Magrib's camp has its three officers for «Порядок (часть 2)» (303, 307, 311)",
      [stood(room(85))[t] >= 1 for t in (303, 307, 311)], [True, True, True])

CHIEFS = {82: (269, "nc"), 83: (284, "lu"), 86: (300, "ja"), 87: (314, "mg")}
for loc_id, (chief, fac) in sorted(CHIEFS.items()):
    r = room(loc_id)
    got = stood(r)
    empty = sum(1 for _c, t in r.loc.spawns if t == 0)
    check("%d stands its chief %d and %d of his %s_ in its %d empty slots"
          % (loc_id, chief, empty, fac, empty),
          (got[chief], sum(n for t, n in got.items() if prefix(t) == fac)), (1, empty))

r122 = room(122)
check("«Механик ДСР» (122): the mechanic and eight ДСР stand-ins of levels 7-8, two officers"
      " (inv_8_cap) among them",
      (stood(r122)[717], sorted(mobs.stats(n.type_id).level for n in r122.npcs.values()
                                if n.type_id != 717), stood(r122)[1040]),
      (1, [7, 7, 7, 7, 7, 8, 8, 8], 2))
check("the sectarians of 64: six sektant, two of the sect, and the box",
      stood(room(64)), collections.Counter({854: 6, 282: 1, 280: 1, 102: 1}))
check("«Перехват» (46): four shooters over the box", stood(room(46)),
      collections.Counter({21: 4, 50: 1}))
check("every type the table fills a slot with is one the client can draw and name",
      sorted({t for i in (80, 81, 82, 83, 84, 85, 86, 87, 122, 64, 46) for t in world.camp_fill(i)
              if t not in MT or not names.known(t)}), [])

# Where the table says nothing, nothing changed.
check("the valley's camp 34 stands what its file says, as before",
      stood(room(34)), collections.Counter({251: 4, 2103: 1, 20: 1, 21: 2}))
check("the slave traders' camp 88 (another city's Bandit_Camp): its chief alone, the"
      " empty slots and the ammunition boxes left out as before",
      (stood(room(88)), world.camp_fill(88)), (collections.Counter({327: 1}), ()))
check("an Up_Camp copy of the colonists' camp keeps its ammunition box out",
      stood(room(1057))[409], 0)
# Each place the table lets an object stand, by where it is: a map cell of
# Вади-Хальфа outside the valley, or an interior of the town's own -- the
# range TIR_01..06 or the quarry's pits -- which have no cell of their own.
HALFA_INSIDE = re.compile(r"^(TIR_0[1-6]|WH_Stone_Mine_)")
check("no object stands by the table in the Nubian valley, nor anywhere but Вади-Хальфа's"
      " cells and its range and quarry",
      sorted(i for i in world.STANDING_OBJECTS
             if (world.in_noob_valley(*world.cell_of(i)) if world.cell_of(i)
                 else not HALFA_INSIDE.match(world.location(i).fn))), [])
check("  ..the interiors among them are the range's six and the quarry's four",
      sorted(world.location(i).fn for i in world.STANDING_OBJECTS if not world.cell_of(i)),
      sorted(["TIR_01", "TIR_02", "TIR_03", "TIR_04", "TIR_05", "TIR_06",
              "WH_Stone_Mine_C", "WH_Stone_Mine_S", "WH_Stone_Mine_W2", "WH_Stone_Mine_E2"]))

# --- the objects ---------------------------------------------------------------------------
tir = [stood(room(i)) for i in (1048, 1233, 1260, 1276, 1280, 1282)]
check("the Tir's targets stand in TIR_01..06, three and one to a lesson",
      [sum(c[t] for t in range(1397, 1403)) for c in tir], [4, 3, 4, 3, 3, 3])
check("  ..but not in the old copy of the range (670)", sum(stood(room(670))[t] for t in range(1397, 1403)), 0)


def booth(r):
    """Every cell of a room a player can walk to from where he comes in."""
    loc = r.loc
    taken = {n.cell for n in r.npcs.values()}
    start = loc.entry_cell()
    seen = {start}
    queue = collections.deque([start])
    while queue:
        cur = queue.popleft()
        for nb in progression.hex_neighbours(cur, loc.width, loc.height):
            if nb not in seen and nb not in loc.obstacles and nb not in taken:
                seen.add(nb)
                queue.append(nb)
    return seen


TIR = (1048, 1233, 1260, 1276, 1280, 1282)      # TIR_01..06
RANGES = {}
for i in TIR:
    r = room(i)
    RANGES[i] = (r, booth(r), [n.cell for n in r.npcs.values() if 1397 <= n.type_id <= 1402])
check("in every range the targets stand beyond the counter: no cell of the booth next to"
      " one, and a bullet as the rest of the world sees it (mobs.line_of_fire) stopped by"
      " the counter from every cell of it",
      [(i, sum(1 for t in ts for c in cells if mobs.adjacent(c, t, r.loc)),
        sum(1 for t in ts for c in cells if mobs.line_of_fire(r.loc, c, t) is None))
       for i, (r, cells, ts) in sorted(RANGES.items())],
      [(i, 0, 0) for i in sorted(RANGES)])
check("  ..and every target of all six has a clear shot from the booth over the counter"
      " (combat.shot_wall)",
      [(i, [t for t in ts if not any(combat.shot_wall(r.loc, c, t) is None for c in cells)])
       for i, (r, cells, ts) in sorted(RANGES.items())],
      [(i, []) for i in sorted(RANGES)])
check("the counter is shot over in the six ranges and nowhere else: not in the old ranges"
      " (670, 1037, 1002), nor where the turrets stand, nor in a camp",
      ([i for i in TIR if not world.location(i).shoot_over],
       [i for i in (670, 1037, 1002, 141, 80, 64) if world.location(i).shoot_over]),
      ([], []))
_l141 = world.location(141)
_pairs = [(a, b) for a in range(0, _l141.width * _l141.height, 97)
          for b in range(13, _l141.width * _l141.height, 389)]
check("  ..and elsewhere a shot's wall is line_of_fire's, pair for pair (%d pairs in 141)"
      % len(_pairs),
      [p for p in _pairs if combat.shot_wall(_l141, *p) != mobs.line_of_fire(_l141, *p)], [])
q626 = stood(room(626))
check("the quarry's stones stand in its pits, the control panel does not",
      (q626[977], q626[2022]), (18, 0))
check("a target, a stone, a box: immobile, harmless, with hit points and a level",
      [(mobs.stats(t).moves, mobs.stats(t).can_attack, mobs.stats(t).hp_max > 0)
       for t in (1397, 977, 102, 409)], [(False, False, True)] * 4)
check("the camp boxes are of their camp's band now, not level 14",
      [mobs.stats(t).level for t in (409, 641, 642, 2162)], [1, 3, 5, 7])


class _Store(object):
    """What a corpse's bag is made through: rows with serials, remembered."""

    def __init__(self):
        self.made = []

    def create_item(self, owner, type_id, root, **fields):
        self.made.append(type_id)
        return dict(uniq=len(self.made), type_id=type_id)

    def delete_item(self, uniq):
        pass

    def forget_trophy(self, uniq):
        pass

    def lay_down(self, things, place, cell):
        pass

    def sweep_ground(self, uniqs, loot_owner):
        pass


class _Killer(object):
    """Whoever struck the last blow, as RoomCombat.kill reads him."""
    is_player = True
    eid = rooms.player_id(7)

    def __init__(self):
        self.sess = SimpleNamespace(char_id=0)
        self.kills = []

    def count_kill(self, type_id):
        self.kills.append(type_id)

    def release_stats(self):
        """The kill pushes the killer's held rp_info (Fighter.hold_stats);
        nothing is held here."""


class _Shooter(object):
    is_player = False

    def __init__(self, cell):
        self.cell, self.eid = cell, 999999


async def _the_box():
    combat.CORPSE_DELAY, combat.RESPAWN_DELAY = 0.05, 0.2
    r = room(64)
    store = _Store()
    rc = r.combat = combat.RoomCombat(r, store)
    box = next(m for m in rc.mobs.values() if m.type_id == 102)
    loc = r.loc
    near = next(c for c in progression.hex_neighbours(box.cell, loc.width, loc.height)
                if c not in loc.obstacles)
    gun = combat.Weapon(num_shots=1, dmin=10, dmax=10, opt_lo=0, opt_hi=0, max_range=10,
                        piercing=100, cone=0, crit=0, skill=None, spec=None)
    h, _s, hits, killed = rc.burst(_Shooter(near), box, box.cell, gun, 1)
    check("the «ящик спирта» of 64 takes a shot: 10 off its %d hit points" % box.hp_max,
          (hits, h, box.hp, killed), (1, 10, box.hp_max - 10, False))
    killer = _Killer()
    rc.after_hostile(killer, box)
    check("  ..and does not turn on whoever shot it, nor put the room at war",
          (box.target, r.ws), (None, False))
    box.hp = 0
    rc.kill(box, killer)
    check("killed, it is out of the room's inhabitants and counts as a kill for a quest",
          (box.alive, box.eid in r.npcs, killer.kills), (False, False, [102]))
    await asyncio.sleep(0.12)
    check("its bag holds no stand-in cigarette (an object's bag is its table and its quests)",
          mobs.FALLBACK_LOOT in store.made, False)
    await asyncio.sleep(0.3)
    check("and it comes back whole where it stood",
          (box.alive, box.eid in r.npcs, box.hp == box.hp_max, box.cell == box.home),
          (True, True, True, True))


async def _the_target():
    """A target of TIR_01 shot from the booth, over the counter, until it
    falls; the socket side of it is test_halfa_tir.py."""
    combat.CORPSE_DELAY, combat.RESPAWN_DELAY = 0.05, 0.2
    r = room(1048)
    store = _Store()
    rc = r.combat = combat.RoomCombat(r, store)
    sent = []
    r.broadcast = lambda frame, exclude=None: sent.append(frame)
    cells = booth(r)
    loc = r.loc
    target = min((m for m in rc.mobs.values() if m.type_id == 1397),
                 key=lambda m: mobs.hex_distance(loc.entry_cell(), m.cell, loc.width))
    spot = min((c for c in cells if combat.shot_wall(loc, c, target.cell) is None),
               key=lambda c: mobs.hex_distance(c, target.cell, loc.width), default=None)
    if spot is None:
        check("TIR_01: a cell of the booth to shoot the target from", spot is not None, True)
        return
    gun = combat.Weapon(num_shots=1, dmin=10, dmax=10, opt_lo=0, opt_hi=0, max_range=10,
                        piercing=100, cone=0, crit=0, skill=None, spec=None)
    killer = _Killer()
    outcomes = []
    killed = False
    for _ in range(target.hp_max // 10 + 2):
        _h, _s, hits, killed = rc.burst(_Shooter(spot), target, target.cell, gun, 1)
        outcomes.append(hits)
        rc.after_hostile(killer, target)
        if killed:
            break
    walls = [p for n, p in sent if n == "faWall"]
    check("TIR_01: from the booth %d hexes off, every shot over the counter lands on the"
          " target until it falls" % round(mobs.hex_distance(spot, target.cell, loc.width)),
          (set(outcomes), killed, walls), ({1}, True, []))
    check("  ..and it never took its shooter for a target", target.target, None)
    rc.kill(target, killer)
    check("  ..its kill counts for a quest", killer.kills, [1397])
    await asyncio.sleep(0.12)
    check("  ..its bag holds no stand-in cigarette", mobs.FALLBACK_LOOT in store.made, False)
    await asyncio.sleep(0.3)
    check("  ..and it stands again, whole, where it stood",
          (target.alive, target.eid in r.npcs, target.hp == target.hp_max,
           target.cell == target.home), (True, True, True, True))


class _Inv(object):
    store = None

    def wear_worn(self, n):
        pass


class _Seat(object):
    """Just enough of a session for a Fighter standing in the room."""
    char_id = 0
    on_map = False

    def __init__(self, r, pos, char_id=1):
        self.room, self.pos, self.pid = r, pos, rooms.player_id(char_id)
        self.inv = _Inv()
        self.sent = []
        self.char = progression.Character()
        self.combat = combat.Fighter(self)
        self.combat.regen_at = float("inf")
        r.players[self] = None

    def send(self, *cmd, **params):
        self.sent.append((cmd[0], params))

    def character(self):
        return self.char


async def _the_turrets():
    r = room(141)
    rc = r.combat = combat.RoomCombat(r, None)
    guns = [m for m in rc.mobs.values() if m.type_id == 832]
    st = mobs.stats(832)
    check("141 stands its twelve turrets: guns that never walk",
          (len(guns), st.moves, st.can_attack, st.ranged, st.weapon_class),
          (12, False, True, True, "machine_gun"))
    loc = r.loc
    w = loc.width
    turret = guns[0]
    taken = {m.cell for m in guns}
    spot = next(c for c in range(w * loc.height)
                if c not in loc.obstacles and c not in taken
                and 3 <= mobs.hex_distance(turret.cell, c, w) <= 5
                and mobs.line_of_fire(loc, turret.cell, c) is None)
    seat = _Seat(r, spot)
    home = turret.cell
    t = combat.now()
    for _ in range(12):
        t += combat.AI_TICK
        turret.think(rc, t)
    aimed = [p for n, p in seat.sent if n == "faAim" and p.get("id") == turret.eid]
    check("a player in its range: it takes him and opens fire (faAim), from where it stands",
          (turret.target is seat.combat, aimed != [], turret.cell), (True, True, home))
    if turret.aim is not None:
        turret.aim.cancel()
        turret.aim = None
    far = next(c for c in range(w * loc.height)
               if c not in loc.obstacles and c not in taken
               and mobs.hex_distance(turret.cell, c, w) > st.range + 4)
    seat.pos = far
    seat.sent = []
    for _ in range(12):
        t += combat.AI_TICK
        turret.think(rc, t)
    check("the player out of its range: it holds him and does not take a step after him",
          (turret.cell, [p for n, p in seat.sent if n == "userMove" and p.get("id") == turret.eid]),
          (home, []))


asyncio.run(_the_box())
asyncio.run(_the_target())
asyncio.run(_the_turrets())

# --- the town's people back from the season ---------------------------------------------
check("the lottery seller stands in both markets (35, 104); Ольсен waits there for goods"
      " of his own",
      [(stood(room(i))[662], stood(room(i))[431]) for i in (35, 104)], [(1, 0), (1, 0)])
with open(os.path.join(os.path.dirname(HERE), "data", "trader_stock_wiki.json"),
          encoding="utf-8") as _fh:
    _WIKI_STOCK = json.load(_fh)["by_type"]


def goods_from(type_id):
    """Where a trader's goods come from: the owner's own list, a wiki row, or
    nothing at all."""
    if npcs.stock(type_id) is not None:
        return "npcs.json"
    row = _WIKI_STOCK.get(str(type_id))
    if row is None:
        return None
    return "%s/%s" % (row.get("city"), row.get("confidence"))


kept_traders = sorted({n.type_id for i in world.SEASON_KEPT for n in room(i).npcs.values()
                       if n.type_id in world.SEASON_KEPT[i] and n.root == world.TRADER})
check("every trader the season list brings back sells the owner's list or the wiki's stall"
      " of this town -- no low-confidence stall of another city's trader (Ольсен's was"
      " Донгола's «Генрих»: Анестетик and Салюс МК V-VII)",
      [(t, goods_from(t)) for t in kept_traders
       if not (goods_from(t) in (None, "npcs.json")
               or goods_from(t).startswith("Вади-Хальфа/") and not goods_from(t).endswith("/low"))],
      [])
black = stood(room(102))
check("the gold lottery stands in the black market (102), Савин's presents and the"
      " developers' stand-ins do not",
      (black[711], black[636], sum(black[t] for t in (7234, 7235, 7236))), (1, 0, 0))
check("the Добрый беженец and the child in the жилой квартал (36), the other child at the Причал (41)",
      (stood(room(36))[1977], stood(room(36))[423], stood(room(41))[425]), (1, 1, 1))
check("Ольсен stays out of Донгола's market (197) as well",
      stood(room(197))[431], 0)

# --- the boss hours ------------------------------------------------------------------------
check("the boss clock reads noon, outside the owner's windows",
      bosses.slot(bosses.clock()), None)
r120 = room(120)
rc120 = r120.combat = combat.RoomCombat(r120, None)
rc120.keep_hours()
glav = [m for m in rc120.mobs.values() if m.type_id == 696]
check("the «Главарь бандитов» (696) of the plundered caravan stands at noon: «Фрэнк"
      " (часть 2)» needs him at any hour",
      (bosses.keeps_hours(696), [m.alive for m in glav], [m.eid in r120.npcs for m in glav]),
      (False, [True], [True]))
r80 = room(80)
rc80 = r80.combat = combat.RoomCombat(r80, None)
rc80.keep_hours()
by_type = collections.defaultdict(list)
for m in rc80.mobs.values():
    by_type[m.type_id].append(m)
check("in the colonists' camp at noon the chief Агнес (270) is away, the treasurer (586) is not",
      ([m.alive for m in by_type[270]], [m.alive for m in by_type[586]],
       bosses.keeps_hours(270), bosses.keeps_hours(586)),
      ([False], [True], True, False))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa world OK")
