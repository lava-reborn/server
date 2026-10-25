"""Mobs: what a creature is, how strong, and how it behaves.

The client draws a mob and animates it, and that is all it knows: mobs.xml
has a type id, a root class, a name and an art folder. Level, hit points,
damage, weapon, speed and temper were on the dead server. data/mob_types.json
recovers the level from the type names and the camps (build_mob_types.py
explains each source) and reads the weapon class off a word in the name;
data/mob_curves.json is ONE designed table by level -- a level-N mob is a fair
match for a level-N player under the wiki's own formulas -- with role and
weapon multipliers. Nothing here invents a second set of numbers: every
figure a mob fights with comes from those two files.

Geometry lives here too, because the mob's brain and the shot resolver in
combat.py share it and neither may import the other: LocationGrid.as puts a
hex at rx = gx + 0.5*(gy % 2), ry = gy * 0.866, measures distance as the
Euclidean one between those points (getHexDistance), and reads the facing
angle off the signs of the difference (getDirection). The client colours the
firing cursor by exactly this distance, so the server has to agree with it
to the decimal, or "green" shots come back refused.
"""
import json
import logging
import math
import os
from collections import deque

import inventory
import items
import progression
import quests
import world

log = logging.getLogger("lava")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    with open(os.path.join(HERE, "data", name), encoding="utf-8") as fh:
        return json.load(fh)


TYPES = _load("mob_types.json")["types"]
CURVES = _load("mob_curves.json")
LEVELS = CURVES["levels"]
ROLES = CURVES["roles"]
WEAPONS = CURVES["weapon_classes"]
MAX_LEVEL = max(int(k) for k in LEVELS)

# The item type a mob holds in its primary hand, by the weapon class its name
# gave it. What the client does with it is pick the animation set
# (Char.changeWeapon: fist/knife/pistol/rifle from the item's weapon_type),
# so a stall's tier-one gun of the right class is enough; the numbers a mob
# shoots with come from the curve, not from the item. The knife is the
# "homemade_knife_mob" entry of the _mob cold-arms series in objects.xml.
# A sub-machine gun is «Кустарный ПП» 25341 (weapon_type 5, the rifle's
# frames: FireArm.weapon_type), not the pistol 4380 it used to share with
# the pistol class, which drew every gunner of the class with a pistol's
# (the owner, 2026-10-09, the Вади-Хальфа mine's miners).
WEAPON_ITEM = {
    "pistol": 4380, "smg": 25341,
    "shotgun": 4392,
    "assault_rifle": 4397,
    "rifle": 4385, "machine_gun": 4385,
    "knife": 195,
}
RANGED = ("pistol", "smg", "shotgun", "assault_rifle", "rifle", "machine_gun")

# Serial numbers of the virtual item instances mobs carry. ItemFactory keys
# its store on the whole oid string and parses the serial as a hex double,
# so anything below 2^53 is fine; 2^30 keeps clear of the items table, whose
# AUTOINCREMENT serials start at 1.
VIRTUAL_BASE = 1 << 30

# The client walks every figure at 200 ms a hex (LocWalker.as:74) whatever
# the server thinks the creature's speed is, so a mob is "busy" for that
# long per hex of the path it was sent, or its next move would start on the
# client before the last one ended. hex_ms in the table only says whether a
# creature moves at all (0 for boxes, ore and targets).
HEX_MS = 200
# Hexes a mob is sent per userMove: short legs, so it re-aims at a moving
# target every second or so instead of finishing a stale path.
LEG = 5
# A target, once taken, is kept for as long as the player is in the room
# and alive -- the owner's rule (2026-09-25): «агр не должен сниматься в
# локации сам по себе, пока игрок не выйдет после истечения таймера». There
# is no leash and no giving up: a creature chases anywhere in the location,
# and one that cannot get at its target waits where it got closest and keeps
# trying. What lets the player go is leaving the room, which the exit timer
# allows (combat.Fighter.in_combat); then the creature walks home and heals
# there (Mob.homing). The leash of 24 hexes it replaces reset the creature
# whole on the spot and let it take the same player again a tick later:
# lch;ws flapped every AI tick, and the creature never went down.
#
# How many hexes one path search looks at. A target further off than it
# reaches is walked towards by the explored hex nearest to it (find_path's
# `toward`), so this bounds the work of a tick, not the chase.
SEARCH_LIMIT = 2500
# Seconds a creature that found no step to take waits before looking again.
STUCK_WAIT = 1.0
# Seconds between two attacks of one mob, on top of its action points: the
# animation of the previous swing or burst has to end on the client first.
ATTACK_PAUSE = 1.5
# The scatter of a creature with no gun of its own to read it from: a
# pistol's, CLASS_SHAPE acc 8 at a hundred metres (combat.cone_of).
DEFAULT_SCATTER = 0.08

# How much less a creature dodges a blade or a fist than its curve says,
# DESIGNED (2026-10-04). The wiki's blow (combat.melee_hit_chance) is
# 49 + 1.25 * Ближний бой + 5 * spec less the target's dodge, and the curve
# gives a creature the dodge of a player of its level (mob_curves.json
# formulas.dodge). Between two players that is the wiki's duel; against a
# creature of one's own level it left a fighter trained level by level
# hitting 39-44% at every level (a player counted 46% of his knife's blows),
# while a gun, since the scatter cone, hits most of its rounds. 30 less
# puts parity at about 70% at every level and keeps every point of the
# skill and the spec worth what the wiki says. Bullets meet no dodge at all.
MELEE_DODGE_CUT = 30

ROW_H = 0.8660254037844386

# getDirection's table (LocationGrid.as:15-22): the sign pair of (dx, dy)
# picks k, angles[k] is what faAim carries. dx == 0 leaves k undefined and
# the figure keeps its facing, which 0 tells the client as well
# (DisplayLocScene.as:306).
ANGLES = {1: 1, 2: 8, 3: 7, -1: 3, -2: 4, -3: 5}


# --- geometry, as LocationGrid.as does it -------------------------------

def real(cell, width):
    """(rx, ry) of a hex: the coordinates the client measures with."""
    gx, gy = cell % width, cell // width
    return gx + 0.5 * (gy % 2), gy * ROW_H


def hex_distance(a, b, width):
    ax, ay = real(a, width)
    bx, by = real(b, width)
    return math.hypot(ax - bx, ay - by)


def direction(a, b, width):
    """The faAim angle from cell a towards cell b, 1..8, or 0 to keep facing."""
    ax, ay = real(a, width)
    bx, by = real(b, width)
    dx, dy = bx - ax, by - ay
    if dx == 0:
        return 0
    if dy > 0:
        k = 1
    elif dy == 0:
        k = 2
    else:
        k = 3
    if dx < 0:
        k = -k
    return ANGLES[k]


def cell_at(rx, ry, width, height):
    """The hex under a real point, the inverse of real()."""
    gy = int(round(ry / ROW_H))
    gy = max(0, min(height - 1, gy))
    gx = int(round(rx - 0.5 * (gy % 2)))
    gx = max(0, min(width - 1, gx))
    return gy * width + gx


def line_of_fire(loc, a, b):
    """The first obstacle strictly between two hexes, or None if clear.

    The wiki's "Основа ПвП" says rocks are not shot through and the design
    document simulates the bullet hex by hex; this is the plain version of
    that: sample the straight line between the two centres and stop at the
    first obstacle. A blocked line is what faWall reports.
    """
    w = loc.width
    ax, ay = real(a, w)
    bx, by = real(b, w)
    steps = max(1, int(math.ceil(hex_distance(a, b, w) * 2)))
    for i in range(1, steps):
        t = i / float(steps)
        c = cell_at(ax + (bx - ax) * t, ay + (by - ay) * t, w, loc.height)
        if c != a and c != b and c in loc.obstacles:
            return c
    return None


def adjacent(a, b, loc):
    """Neighbouring hexes, not the same one: what a strike needs."""
    return a != b and progression.within_reach(a, b, loc.width, loc.height)


def find_path(loc, start, goal, blocked=(), limit=SEARCH_LIMIT, toward=None):
    """Breadth-first over the hex grid to the nearest cell satisfying goal.

    Obstacles come from the location file, blocked from whoever stands
    where; the limit keeps a mob that cannot reach its target from
    searching the whole 64x128 grid every tick. Returns the cells from
    start inclusive, or None.

    With `toward`, a search that finds no goal within the limit -- the
    target is further off than it looks, or cannot be reached at all --
    returns the way to the hex it did explore that is nearest to that cell,
    if that one is nearer than the start: a creature chasing across the
    whole location gets there leg by leg, and one that cannot reach its
    target at all comes as close as the ground lets it. None when no hex
    is nearer.
    """
    if goal(start):
        return [start]
    prev = {start: None}
    queue = deque([start])
    seen = 0
    best = start
    best_d = hex_distance(start, toward, loc.width) if toward is not None else None

    def way(cell):
        path = [cell]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])
        path.reverse()
        return path

    while queue and seen < limit:
        cur = queue.popleft()
        seen += 1
        for nb in progression.hex_neighbours(cur, loc.width, loc.height):
            if nb in prev or nb in loc.obstacles or nb in blocked:
                continue
            prev[nb] = cur
            if goal(nb):
                return way(nb)
            if toward is not None:
                d = hex_distance(nb, toward, loc.width)
                if d < best_d:
                    best, best_d = nb, d
            queue.append(nb)
    return way(best) if best != start else None


# --- what a type is ------------------------------------------------------

class MobStats:
    """One type's numbers, from mob_types.json through mob_curves.json."""

    def __init__(self, type_id):
        info = TYPES.get(str(type_id), {})
        self.type_id = type_id
        self.name = info.get("name", "")
        self.level = int(info.get("level", 1))
        self.role = info.get("role", "mob")
        self.weapon_class = info.get("weapon_class", "fist")
        self.hex_ms = int(info.get("hex_ms", HEX_MS))
        row = LEVELS[str(max(0, min(MAX_LEVEL, self.level)))]
        role = ROLES.get(self.role, ROLES["mob"])
        weapon = WEAPONS.get(self.weapon_class, WEAPONS["fist"])
        self.hp_max = max(1, int(round(row["hp"] * role["hp_mult"])))
        self.sp_max = max(0, int(round(row["sp"] * role["hp_mult"])))
        self.dmg_min = int(round(row["dmg_min"] * weapon["dmg_mult"] * role["dmg_mult"]))
        self.dmg_max = max(self.dmg_min,
                           int(round(row["dmg_max"] * weapon["dmg_mult"] * role["dmg_mult"])))
        self.hit = float(row["hit"])
        self.dodge = float(row["dodge"])
        self.armor = float(row["armor"])
        self.ap_max = int(info.get("ap_max", row["ap"]))
        self.xp_mult = float(role["xp_mult"])
        # The curve's 4 * hp, kept for its record only: what a kill pays is
        # progression.mob_xp, priced by level (the owner's rule, 2026-09-24).
        self.xp_pool = int(row["xp_pool"] * self.xp_mult)
        self.aggro = float(role["aggro"])
        self.range = int(weapon["range"])
        self.shots = max(1, int(weapon["shots"]))
        self.attack_ap = int(weapon["ap"])
        self.ranged = self.weapon_class in RANGED
        self.weapon_type_id = info.get("weapon_type_id", WEAPON_ITEM.get(self.weapon_class))
        self.loot_ammo_type = info.get("loot_ammo_type")
        self.loot_ammo_count = tuple(info.get("loot_ammo_count", (3, 10)))
        self.can_attack = (self.role != "object" and self.weapon_class != "none"
                           and self.dmg_max > 0 and self.aggro > 0)
        self.moves = self.hex_ms > 0 and self.role != "object"
        # The curve gives no crit figures; these are the wiki's ranged crit
        # and crit-evade formulas with the attributes the curve's dodge
        # already implies (5 + spec each, spec = min(5, level // 4)).
        s = min(5, self.level // 4)
        self.crit = (5 + s) + self.level / 4.0 + 2 * s
        self.crit_evade = (5 + s) + self.level / 8.0 + s
        # Pacing from the item the client is shown in its hand: the aim bar
        # of a firearm, the swing of a knife; a bare-handed creature has
        # neither and strikes at once.
        si = items.params_of(self.weapon_type_id) if self.weapon_type_id else None
        if si and self.ranged:
            self.attack_time = si.get("fire_times", [700])[0] / 1000.0
        elif si:
            self.attack_time = si.get("strike_time", 0) / 1000.0
        else:
            self.attack_time = 0.0
        # What its bullets scatter by (combat.spread_factor, cone_of): the
        # level for Стрельба, the spec the curve's dodge already implies, and
        # the gun in its hand read as the client reads it, target_size over
        # max_range of the first mode -- a pistol's 0.08 where it has none.
        self.spec = s
        self.scatter = DEFAULT_SCATTER
        if si and self.ranged:
            ts, rng = si.get("target_size", [0])[0], si.get("max_range", [0])[0]
            if ts > 0 and rng > 0:
                self.scatter = ts / float(rng)

    def weapon_oid(self, entity_id):
        """The oid of the weapon in this mob's primary hand, or None. Virtual:
        every mob of the type shares the item type, each its own serial, and
        none of it is in the database."""
        if self.weapon_type_id is None:
            return None
        root = items.root_of(self.weapon_type_id)
        if root is None:
            return None
        return inventory.oid(VIRTUAL_BASE + entity_id, self.weapon_type_id, root)


# --- what a corpse leaves behind -----------------------------------------
#
# Two parts. Until the owner's complaint (2026-09-24: "от мобов падают только
# патроны") there was only the first, and in it a man with a gun had nothing
# on him but his rounds; the table beside it was never read.
#
# What the body certainly had on it, designed. An animal its meat, and on a
# coin toss each its skin or fang -- objects.xml's own DogMeat/DogFang/
# DogSkin, RatTail, AntilopeMeat/Skin, CrocodileMeat, Hyena_Skin. An armed
# man a few of the rounds his gun takes. And every man, armed or not, a
# piece of the original's junk of about his level: objects.xml numbers the
# series itself, TrashLoot_LvL_0 to _24 (Консервная банка, Алюминиевая
# ложка ... Лунный сахар, 20 to 500 afro at a trader), and it is what the
# wiki's loot lists of the camps are made of. That piece took the place of
# the cigarette (41) the unarmed used to carry so that a bag was never empty;
# the cigarette is left to a creature that is neither.
#
# Then what the kind drops by the wiki, rolled row by row: loot_table.
ANIMAL_LOOT = [("dog", [216, 217, 218]), ("rat", [3216]), ("antilope", [224, 225]),
               ("crocodile", [1752]), ("hyena", [3923])]
FALLBACK_LOOT = 41
# Who carries the junk: the fighting kinds of data/mob_types.json, not the
# animals, and not the "object" boxes and ore, which never stand in a room.
HUMAN_ROLES = ("mob", "boss")
TRASH_SERIES = "TrashLoot_LvL_%d"
VALUABLE_SERIES = "ValuableLoot_LvL_%d"
# A man's piece of junk is of his own level or up to this many below, so a
# camp of one level does not leave the same spoon in every bag.
JUNK_SPREAD = 2

# The table (data/loot_wiki.json, built by data/build_loot_wiki.py): the
# wiki's edges from a group of creatures to an item page, with a chance per
# tier that the file itself calls designed. Rows are item page titles; their
# type ids are resolved here through items.resolve_title, the same linker
# (data/wiki_links.json) the stalls' wiki lists go through -- the file's own
# item_type_ids column was never filled, its builder reading an older layout
# of wiki_links.json.
#
# Only the tiers a mob page's own "Лут" section gives, valuable or not. An
# "unknown" row comes off an item page's "Мобы-хранители", which names the
# townsman who hands a quest item over as readily as a creature that drops
# something -- a 100 000-afro Алмаз at 15 % from level-1 raiders came that
# way. The wiki's "Квестовый" rows are left out too: loot only while a quest
# is open, and the wiki's say who holds a quest thing no better than its
# "unknown" ones. The same tier in data/loot_manual.json is the owner's, and
# rolls only for a quest that asks for the thing (QUEST_TIER, quest_roll).
#
# Beside it, data/loot_manual.json: rows the owner decided for creatures the
# wiki is silent about -- the Nubian mine's marauders (836, 837) and their
# gold sand and emeralds, and the Nubian valley's boss (2103) and its two
# ingots of 1 ounce of gold (one of 5 from 2026-09-25, halved on
# 2026-10-11); the gold ingots of Вади-Хальфа's bosses, 2026-10-09, halved
# on 2026-10-11. Same tiers, same roll, same cap; a row
# names its item by type id, the linker tying the emerald and the ingot to
# no type. Hand-made rather than written into the generated file, which
# its builder would take them out of on the next run.
LOOT_TIERS = {"Ценный": True, "Обычный": False}      # tier -> valuable
# The design the file states (its "design" block, which test_loot holds this
# to): one roll per row, valuables first, at most this many that came up kept.
MAX_DROPS = 2
# A row at this chance is no roll but a certainty: the valley boss's two
# ingots of an ounce (data/loot_manual.json, 2103), which the owner wants
# on every kill, and the ingots of Вади-Хальфа's eight hour-keeping bosses
# (269/270 one of an ounce, 283/284 two, 299/300 three, 313/314 one of
# five; the owner's of 2026-10-09, halved on 2026-10-11). It goes into the bag
# whatever else came up and takes none of the MAX_DROPS places, so no table
# the wiki may give the boss one day, and no order of the rows, can push it
# out; the rows that are rolled keep their two. An ingot lands in the bag
# only off a boss that keeps the hours (combat.RoomCombat.drop_loot): with
# the rule off a boss is back every respawn delay, and a certain ingot on
# each kill would be gold without a limit.
SURE = 1.0
# Every man's valuable of his level: objects.xml's ValuableLoot_LvL_0 to _24,
# as a row of the table at the "Ценный" chance.
VALUABLE_CHANCE = 0.06
# A quest's thing, the wiki's own word for the tier: a row of data/
# loot_manual.json under it rolls only while somebody who brought the
# creature down has a quest open that asks for the thing and does not yet
# have as many as it asks (quests.wanted_things, RoomCombat.kill) -- the
# courier's letter for «Пути информации», the medicaments of the colonists
# for «Одолжить аптечку». The original's rule, «loot only while the quest
# is open», and the least surprising one: nobody else finds a quest's
# litter in a bag, and a thing with no price or with the quest flag, which
# droppable() keeps out of every other row, is let in here -- it belongs to
# the quest that asked for it. Such a row is rolled on its own, outside
# MAX_DROPS, so it neither pushes the ordinary loot out nor is pushed out
# by it; at SURE it is certain.
QUEST_TIER = "Квестовый"


def _series(fmt):
    """Type ids of a level series, index = level, off objects.xml's names."""
    by_name = {}
    for t, (_root, name) in sorted(items.catalogue().items()):
        by_name.setdefault(name, t)
    out = []
    while fmt % len(out) in by_name:
        out.append(by_name[fmt % len(out)])
    return out


_SERIES = {}


def series(fmt):
    got = _SERIES.get(fmt)
    if got is None:
        got = _SERIES[fmt] = _series(fmt)
    return got


def level_piece(fmt, level):
    """The piece of a series that is a creature's own level, the top of the
    series standing in for anything above it. None without the series."""
    s = series(fmt)
    return s[max(0, min(len(s) - 1, level))] if s else None


def junk(level, rng):
    """A piece of TrashLoot_LvL_* for a man of this level: his own level or
    up to JUNK_SPREAD below it."""
    s = series(TRASH_SERIES)
    if not s:
        return None
    top = max(0, min(len(s) - 1, level))
    return s[rng.randint(max(0, top - JUNK_SPREAD), top)]


def droppable(type_id):
    """Whether a type may lie in a corpse's bag. Nothing out of the game
    (items.out_of_game: premium, or taken out by name in data/retired.json
    items); not a quest item, which belongs to its quest;
    and something a trader pays for -- a thing that can be neither used nor
    sold would be litter the player cannot even get rid of (the blueprints
    in the table have no price: the upgrader they are for does not exist)."""
    si = items.params_of(type_id)
    return bool(si) and not items.out_of_game(type_id) and not si.get("quest") \
        and si.get("cost", 0) > 0


_LOOT_WIKI = None


def _loot_wiki():
    """type id (str) -> the file's rows for it. A table that cannot be read
    leaves every corpse with what it carried, and says so once."""
    global _LOOT_WIKI
    if _LOOT_WIKI is None:
        try:
            _LOOT_WIKI = _load("loot_wiki.json").get("by_type") or {}
        except (OSError, ValueError) as exc:
            log.warning("  !!    loot table unreadable, corpses keep what they carry: %s", exc)
            _LOOT_WIKI = {}
    return _LOOT_WIKI


_LOOT_MANUAL = None


def _loot_manual():
    """type id (str) -> the hand-made rows of data/loot_manual.json. Read
    like the wiki's table: unreadable, it leaves those corpses with what
    they carried, and says so once."""
    global _LOOT_MANUAL
    if _LOOT_MANUAL is None:
        try:
            _LOOT_MANUAL = _load("loot_manual.json").get("by_type") or {}
        except (OSError, ValueError) as exc:
            log.warning("  !!    hand-made loot unreadable, left out: %s", exc)
            _LOOT_MANUAL = {}
    return _LOOT_MANUAL


def animal_parts(st):
    """An animal's line of ANIMAL_LOOT, meat first, or () for anything else
    or an animal it has no line for."""
    if st.role != "animal":
        return ()
    name = st.name.lower()
    for word, types in ANIMAL_LOOT:
        if word in name:
            return tuple(types)
    return ()


_TABLES = {}


def loot_table(type_id):
    """[(item type, chance, valuable)] a corpse of this type rolls for, in
    the order it rolls: valuables first, then by type id.

    The wiki's rows that resolve to something droppable and the hand-made
    ones of data/loot_manual.json, the higher chance kept where an item is
    listed twice, unless a manual row has exact_chance=true; and for a man,
    the valuable of his level. Built once per type. An exact manual chance
    also takes precedence over that generic level drop.
    """
    rows = _TABLES.get(type_id)
    if rows is not None:
        return rows
    st = stats(type_id)
    got = {}
    exact = set()

    def add(t, chance, valuable, exact_chance=False):
        if t is None or chance <= 0 or not droppable(t):
            return
        if t in exact and not exact_chance:
            return
        # Listed twice, an item keeps the better chance and the tier of the
        # row that gave it. The one case in the data is on purpose: twelve
        # colonist kinds (258..268, 586) whose wiki list names their own
        # level's ValuableLoot among its "Обычный" rows at 0.30 -- the camp's
        # own page is better evidence than the rule that every man has one
        # at 0.06, and an ordinary row rolls in its place by type id, behind
        # the valuables. Kept valuable, it would roll first and get past the
        # cap of two nearly every time: +21 % afro a kill of a level-2
        # colonist, the kind that already pays the most (UNDONE,
        # лут-баланс).
        if exact_chance or t not in got or chance > got[t][0]:
            got[t] = (chance, valuable)
        if exact_chance:
            exact.add(t)

    for rec in _loot_wiki().get(str(type_id), []):
        valuable = LOOT_TIERS.get(rec.get("tier"))
        if valuable is None or rec.get("quest_only"):
            continue
        # The standard (A) variant: a page that lists several is one item
        # in several qualities, and the first is the ordinary one.
        for t in items.resolve_title(rec.get("item", ""))[:1]:
            add(t, float(rec.get("chance", 0)), valuable)
    for rec in _loot_manual().get(str(type_id), []):
        if rec.get(ONE_OF):
            continue
        valuable = LOOT_TIERS.get(rec.get("tier"))
        if valuable is not None and rec.get("type"):
            add(int(rec["type"]), float(rec.get("chance", 0)), valuable,
                exact_chance=rec.get("exact_chance") is True)
    if st.role in HUMAN_ROLES:
        add(level_piece(VALUABLE_SERIES, st.level), VALUABLE_CHANCE, True)
    # What the body has anyway is not rolled for a second time: the dog's
    # page lists its fang and skin, which carried() already tosses for.
    for t in animal_parts(st):
        got.pop(t, None)
    rows = _TABLES[type_id] = sorted(
        ((t, c, v) for t, (c, v) in got.items()), key=lambda r: (not r[2], r[0]))
    return rows


_COUNTS = {}
_INDEPENDENT = {}


def independent_loot(type_id):
    """Explicit per-kind rolls whose stated chances are outside MAX_DROPS."""
    if type_id not in _INDEPENDENT:
        _INDEPENDENT[type_id] = frozenset(
            int(r['type']) for r in _loot_manual().get(str(type_id), [])
            if r.get('independent') is True and r.get('type')
            and r.get('tier') in LOOT_TIERS and not r.get(ONE_OF))
    return _INDEPENDENT[type_id]


def count_of(type_id, t):
    """How many of thing t a row of data/loot_manual.json puts in the bag of
    a corpse of this type when the row lies there: the row's "count", 1
    without one. Ounces no ingot holds go as ingots of one (the owner's of
    2026-10-09: «если нет слитков подходящего номинала то сделай несколько
    предметов, типа 3 по 1г слитку»): since the halving of 2026-10-11 the
    sect of Люшер's bosses and the valley's Лидер carry two, the
    Janjaweed's three, which a table keyed by the thing (loot_table)
    cannot hold as two or three rows. combat.drop_loot makes one stack of
    them, the bag the player opens shows two or three. Built once per
    type; a count that is no whole number above nought counts as 1."""
    counts = _COUNTS.get(type_id)
    if counts is None:
        counts = {}
        for rec in _loot_manual().get(str(type_id), []):
            if rec.get(ONE_OF) or not rec.get("type") or rec.get("tier") not in LOOT_TIERS:
                continue
            n = rec.get("count", 1)
            if isinstance(n, int) and not isinstance(n, bool) and n > 1:
                counts[int(rec["type"])] = n
        _COUNTS[type_id] = counts
    return counts.get(t, 1)


def roll_table(type_id, rng):
    """[(type_id, count)] off loot_table: every row rolled, so the dice
    spent do not depend on what came up, and the first MAX_DROPS successes
    kept. A row at SURE is certain: in the bag every time, without a die and
    outside the cap. Explicit independent rows also do not consume or
    compete for the cap; their individual chances remain literal.
    The count is the row's own (count_of), 1 but where the
    owner's file says more. Then one thing of each ONE_OF group
    (one_of_groups)."""
    out = []
    kept = 0
    independent = independent_loot(type_id)
    for t, chance, _valuable in loot_table(type_id):
        if chance >= SURE:
            out.append((t, count_of(type_id, t)))
        elif rng.random() < chance and (t in independent or kept < MAX_DROPS):
            out.append((t, count_of(type_id, t)))
            if t not in independent:
                kept += 1
    for group in one_of_groups(type_id):
        pick = rng.random() * sum(w for _t, w in group)
        for t, w in group:
            pick -= w
            if pick < 0:
                break
        out.append((t, 1))
    return out


# A group of data/loot_manual.json rows of which exactly one lies in the bag
# on every kill, picked by their weights: Большой Мвамба's two gold belts
# (1406, the owner's of 2026-10-02: «какой-то один точно выпадает»). Outside
# the cap and the ordinary table, like a SURE row; one die a kill.
ONE_OF = "one_of"
_ONE_OF_GROUPS = {}


def one_of_droppable(type_id):
    """A thing a ONE_OF row may put in a bag: one the game has, not out of
    the game (items.out_of_game) and not a quest's. Unlike droppable(), a
    thing priced in gold alone is welcome: the gold belts are worn, not
    litter, though no trader pays afro for them."""
    si = items.params_of(type_id)
    return bool(si) and not items.out_of_game(type_id) and not si.get("quest")


def one_of_groups(type_id):
    """[[(item type, weight)]]: the ONE_OF groups of a creature, each in
    the file's order, built once per type."""
    groups = _ONE_OF_GROUPS.get(type_id)
    if groups is None:
        by_name = {}
        for rec in _loot_manual().get(str(type_id), []):
            name = rec.get(ONE_OF)
            if not name or not rec.get("type"):
                continue
            t, w = int(rec["type"]), float(rec.get("weight", 1))
            if w > 0 and one_of_droppable(t):
                by_name.setdefault(name, []).append((t, w))
        groups = _ONE_OF_GROUPS[type_id] = list(by_name.values())
    return groups


_QUEST_TABLES = {}


def quest_droppable(type_id):
    """Whether a quest row may put a type in a bag: a thing the game has
    and not one out of the game (items.out_of_game). Price and the quest
    flag do not count here (QUEST_TIER): the thing belongs to the quest
    that asks for it."""
    return bool(items.params_of(type_id)) and not items.out_of_game(type_id)


def quest_table(type_id):
    """[(item type, chance)] of the QUEST_TIER rows of data/loot_manual.json
    for a creature, by type id, and of the quest rows' own drops -- a slot
    of data/quests.json that names this creature with a "drop" chance
    (quests.quest_drops) -- the higher chance where both name a thing;
    built once per type. The ordinary table (loot_table) never holds them."""
    rows = _QUEST_TABLES.get(type_id)
    if rows is None:
        got = {}
        for rec in _loot_manual().get(str(type_id), []):
            if rec.get("tier") != QUEST_TIER or not rec.get("type"):
                continue
            t, chance = int(rec["type"]), float(rec.get("chance", 0))
            if chance > 0 and quest_droppable(t):
                got[t] = max(chance, got.get(t, 0.0))
        for t, chance in quests.quest_drops(type_id):
            if quest_droppable(t):
                got[t] = max(chance, got.get(t, 0.0))
        rows = _QUEST_TABLES[type_id] = sorted(got.items())
    return rows


def quest_roll(type_id, wanted, rng, excluded_groups=()):
    """[(type_id, 1)] of the quest rows that came up for a corpse, given the
    things a quest of those who brought it down still asks for (wanted, as
    RoomCombat.kill works it out). A row for a thing nobody wants is not
    rolled at all, so the dice spent on the ordinary table do not depend on
    who has which quest; at SURE a wanted thing is certain. The wanted
    things of a group (quests.drop_group, a slot's "one_of") come one at
    most: the group rolled once at its highest chance, one of them drawn."""
    out, groups = [], {}
    for t, chance in quest_table(type_id):
        if t not in wanted:
            continue
        group = quests.drop_group(t)
        if group in excluded_groups:
            continue
        if group is not None:
            best, members = groups.get(group, (0.0, []))
            groups[group] = (max(best, chance), members + [t])
        elif chance >= SURE or rng.random() < chance:
            out.append((t, 1))
    for group, (chance, members) in sorted(groups.items()):
        if chance >= SURE or rng.random() < chance:
            out.append((rng.choice(members), 1))
    return out


def carried(st, rng):
    """[(type_id, count)]: what the body certainly had on it."""
    if st.role == "animal":
        parts = animal_parts(st)
        if not parts:
            return [(FALLBACK_LOOT, 1)]
        return [(parts[0], 1)] + [(t, 1) for t in parts[1:] if rng.random() < 0.5]
    out = []
    si = items.params_of(st.weapon_type_id) if st.weapon_type_id else None
    if si and st.ranged and si.get("comp_array"):
        out.append((getattr(st, "loot_ammo_type", None) or si["comp_array"][0],
                    rng.randint(*getattr(st, "loot_ammo_count", (3, 10)))))
    elif "ammo" in st.name.lower():
        out.append((items.AMMO_9MM[0], items.AMMO_PACK))
    if st.role in HUMAN_ROLES:
        piece = junk(st.level, rng)
        if piece is not None:
            out.append((piece, 1))
    return out or [(FALLBACK_LOOT, 1)]


def loot_for(st, rng, wanted=(), *, loc_id=None, killer_level=None):
    """[(type_id, count)] for a corpse of this type: what it carried, then
    what its kind's table rolled, then the quest rows for what those who
    brought it down still need (quest_roll; wanted, the types). combat.
    drop_loot still turns away anything out of the game (items.out_of_game),
    whatever a list says."""
    import bosses                  # late: keep module initialization separate
    blueprint = bosses.blueprint_for(loc_id, st.type_id)
    excluded = ("craft_codified",) if blueprint is not None else ()
    out = carried(st, rng) + roll_table(st.type_id, rng) + \
        quest_roll(st.type_id, wanted, rng, excluded_groups=excluded)
    if blueprint is not None and killer_level is not None:
        # Compare with the dropped blueprint, not the boss's combat level.
        blueprint_level = int(items.catalogue()[blueprint][1].rsplit("_", 1)[1])
        chance = bosses.blueprint_drop_chance(killer_level, blueprint_level)
        if rng.random() < chance:
            out.append((blueprint, 1))
    return out


_STATS = {}


def stats(type_id):
    st = _STATS.get(type_id)
    if st is None:
        st = _STATS[type_id] = MobStats(type_id)
    return st


def virtual_di(uniq, type_id, root, ammo_type=None):
    """ss_di_* fields for a virtual instance (uniq >= VIRTUAL_BASE): a clean,
    loaded weapon, so the client shows nothing odd about it. None for a
    serial that is not virtual."""
    if uniq < VIRTUAL_BASE:
        return None
    si = items.params_of(type_id) or {}
    brk = si.get("max_break_abs", 100)
    if root == items.FIRE_ARM:
        comp = si.get("comp_array") or [0]
        return "ss_di_firearm", {"break": brk, "max_break_cur": brk,
                                 "ammo_count": si.get("clip_size", 1),
                                 "ammo_type": ammo_type if ammo_type in comp else comp[0], "cur_mode": 0}
    if root == items.COLD_ARM:
        return "ss_di_coldarm", {"break": brk, "max_break_cur": brk}
    return "ss_di_wear", {"break": brk, "max_break_cur": brk}


# --- one creature in a room ---------------------------------------------

class Mob:
    """A spawned creature: its state, and the decisions it makes each tick.

    Everything that reaches the wire goes through the RoomCombat handed to
    think(): this class never sends a frame, it only says what to do.
    """
    is_player = False

    def __init__(self, entity_id, type_id, cell):
        self.eid = entity_id
        self.type_id = type_id
        self.stats = stats(type_id)
        self.home = cell
        self.cell = cell
        self.hp = self.stats.hp_max
        self.sp = self.stats.sp_max
        self.ap = self.stats.ap_max
        self.alive = True
        self.target = None          # a combat.Fighter, once provoked
        # Let go of a target (RoomCombat.mob_release) and not yet back home:
        # it heals when it gets there, and not before.
        self.homing = False
        self.busy_until = 0.0       # walking: the client is still animating
        self.next_attack = 0.0
        self.aim = None             # TimerHandle of a burst or swing in flight
        self.regen_at = 0.0
        # combat.Fighter -> [harm done, share of the kill already paid,
        # skill, spec]: what a kill is settled from (RoomCombat.settle_xp)
        self.xp_ledger = {}
        # Character id -> harm done since it was last whole: what a
        # warehouse's boss is taken by (holdings.py). Apart from the xp
        # ledger, which keeps every blow until the kill: this one forgets
        # them whenever the creature is whole again (RoomCombat.mob_recover
        # and its regeneration, reset), so harm cannot be banked through
        # heals; and by character, so a reconnect keeps it.
        self.capture_harm = {}
        # Who brought a warehouse's boss down, for which clan, as they stood
        # at the kill (holdings.snapshot): settled when the corpse fades.
        self.capture = None
        # The things a quest of those who brought it down still asks for,
        # set at the kill (RoomCombat.kill): the quest rows of its loot that
        # may come up in its bag (quest_roll).
        self.quest_wants = frozenset()
        # A boss's hours (bosses.py, RoomCombat.keep_hours): the window it
        # last came for, whether it is gone until the next one, and whether
        # its stay is over and it is only finishing the fight it is in.
        self.slot = None
        self.away = False
        self.leaving = False
        # A boss's escort whose boss arrived while its corpse was still
        # fading (RoomCombat.escort_back): back as soon as the corpse is
        # gone, not at the arrival after (corpse_gone).
        self.recalled = False

    # --- the numbers the resolver asks a target for ------------------------
    @property
    def level(self):
        return self.stats.level

    @property
    def hp_max(self):
        return self.stats.hp_max

    @property
    def sp_max(self):
        return self.stats.sp_max

    @property
    def ap_max(self):
        return self.stats.ap_max

    def vitals(self):
        """usrUp payload, hmax first: Entity.userUpdate assigns hmax before
        hcur, and without hmax the bar is drawn against 1200."""
        return dict(hcur=max(0, self.hp), hmax=self.hp_max,
                    scur=max(0, self.sp), smax=self.sp_max)

    def sp_now(self):
        return self.sp

    def apply_damage(self, hdmg, sdmg):
        self.hp = max(0, self.hp - hdmg)
        self.sp = max(0, self.sp - sdmg)
        return self.hp <= 0

    def dodge_melee(self):
        return self.stats.dodge - MELEE_DODGE_CUT

    def crit_evade_melee(self):
        return self.stats.crit_evade

    def crit_evade_ranged(self):
        return self.stats.crit_evade

    def armor(self):
        return self.stats.armor

    def present(self, rc):
        return self.alive and rc.mobs.get(self.eid) is self

    def weapon_oid(self):
        return self.stats.weapon_oid(self.eid)

    def reset(self):
        """Back to the spawn point, whole, and with no grudge."""
        self.hp = self.stats.hp_max
        self.sp = self.stats.sp_max
        self.ap = self.stats.ap_max
        self.alive = True
        self.target = None
        self.homing = False
        self.xp_ledger = {}
        self.capture_harm = {}
        self.capture = None
        self.quest_wants = frozenset()
        self.busy_until = 0.0
        self.next_attack = 0.0
        self.leaving = False

    # --- behaviour ----------------------------------------------------------
    def think(self, rc, now):
        """One decision: acquire, chase, attack, or go home.

        idle -> a player within the role's aggro radius makes it a target
        (rc.aggro turns the room's war state on and tells the player with
        lch;enemy) -> chase by short legs of userMove until in reach (next to
        the target for a blade or fist, within the weapon's range with a
        clear line for a gun) -> attack while action points last, one
        burst or swing per ATTACK_PAUSE -> and so on, anywhere in the
        location, for as long as the target is here and alive (the owner's
        rule, see SEARCH_LIMIT above). Only the target leaving the room or
        dying drops it; then the mob walks back and recovers at home.
        """
        if not self.alive or self.aim is not None:
            return
        loc = rc.room.loc
        if self.target is not None and not self.target.present(rc):
            rc.mob_release(self)
        if self.target is None:
            if now < self.busy_until:
                return
            # A boss past its stay picks no new fight: the one it was in is
            # what kept it here (RoomCombat.keep_hours).
            if self.stats.can_attack and not self.leaving:
                found = rc.nearest_fighter(self.cell, self.stats.aggro)
                if found is not None:
                    rc.aggro(self, found)
                    return
            if self.cell != self.home and self.stats.moves:
                rc.mob_walk(self, lambda c: c == self.home, now)
            elif self.homing:
                rc.mob_recover(self)
            return
        if now < self.busy_until or now < self.next_attack:
            return
        target = self.target
        if self.stats.ranged:
            in_reach = (hex_distance(self.cell, target.cell, loc.width) <= self.stats.range
                        and line_of_fire(loc, self.cell, target.cell) is None)
        else:
            in_reach = adjacent(self.cell, target.cell, loc)
        if in_reach:
            if self.ap >= self.stats.attack_ap:
                rc.mob_attack(self, target, now)
            return
        if not self.stats.moves:
            return
        if self.stats.ranged:
            goal = (lambda c: hex_distance(c, target.cell, loc.width) <= self.stats.range
                    and line_of_fire(loc, c, target.cell) is None)
        else:
            goal = lambda c: adjacent(c, target.cell, loc)
        rc.mob_walk(self, goal, now)
