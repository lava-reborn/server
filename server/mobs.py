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
import math
import os
from collections import deque

import inventory
import items
import progression
import world

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
WEAPON_ITEM = {
    "pistol": 4380, "smg": 4380,
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
# How far from its spawn a mob will chase before it gives up and walks home.
LEASH = 24
# Seconds between two attacks of one mob, on top of its action points: the
# animation of the previous swing or burst has to end on the client first.
ATTACK_PAUSE = 1.5

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


def find_path(loc, start, goal, blocked=(), limit=2500):
    """Breadth-first over the hex grid to the nearest cell satisfying goal.

    Obstacles come from the location file, blocked from whoever stands
    where; the limit keeps a mob that cannot reach its target from
    searching the whole 64x128 grid every tick. Returns the cells from
    start inclusive, or None.
    """
    if goal(start):
        return [start]
    prev = {start: None}
    queue = deque([start])
    seen = 0
    while queue and seen < limit:
        cur = queue.popleft()
        seen += 1
        for nb in progression.hex_neighbours(cur, loc.width, loc.height):
            if nb in prev or nb in loc.obstacles or nb in blocked:
                continue
            prev[nb] = cur
            if goal(nb):
                path = [nb]
                while prev[path[-1]] is not None:
                    path.append(prev[path[-1]])
                path.reverse()
                return path
            queue.append(nb)
    return None


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
        self.ap_max = int(row["ap"])
        self.xp_mult = float(role["xp_mult"])
        self.xp_pool = int(row["xp_pool"] * self.xp_mult)
        self.aggro = float(role["aggro"])
        self.range = int(weapon["range"])
        self.shots = max(1, int(weapon["shots"]))
        self.attack_ap = int(weapon["ap"])
        self.ranged = self.weapon_class in RANGED
        self.weapon_type_id = WEAPON_ITEM.get(self.weapon_class)
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


# What a corpse leaves behind (designed; the wiki's loot edges in
# data/loot_wiki.json are not linked to item types yet). An animal always
# has its meat and sometimes its skin or fang -- objects.xml's own DogMeat/
# DogFang/DogSkin, RatTail, AntilopeMeat/Skin, CrocodileMeat, Hyena_Skin;
# an armed man drops a few of the rounds his gun takes; anyone else a
# cigarette (41), so a bag always has something in it and never nothing.
ANIMAL_LOOT = [("dog", [216, 217, 218]), ("rat", [3216]), ("antilope", [224, 225]),
               ("crocodile", [1752]), ("hyena", [3923])]
FALLBACK_LOOT = 41


def loot_for(st, rng):
    """[(type_id, count)] for a corpse of this type."""
    name = st.name.lower()
    if st.role == "animal":
        for word, types in ANIMAL_LOOT:
            if word in name:
                out = [(types[0], 1)]
                out += [(t, 1) for t in types[1:] if rng.random() < 0.5]
                return out
        return [(FALLBACK_LOOT, 1)]
    si = items.params_of(st.weapon_type_id) if st.weapon_type_id else None
    if si and st.ranged and si.get("comp_array"):
        return [(si["comp_array"][0], rng.randint(3, 10))]
    if "ammo" in name:
        return [(items.AMMO_9MM[0], items.AMMO_PACK)]
    return [(FALLBACK_LOOT, 1)]


_STATS = {}


def stats(type_id):
    st = _STATS.get(type_id)
    if st is None:
        st = _STATS[type_id] = MobStats(type_id)
    return st


def virtual_di(uniq, type_id, root):
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
                                 "ammo_type": comp[0], "cur_mode": 0}
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
        self.busy_until = 0.0       # walking: the client is still animating
        self.next_attack = 0.0
        self.aim = None             # TimerHandle of a burst or swing in flight
        self.regen_at = 0.0

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
        return self.stats.dodge

    def dodge_ranged(self):
        return self.stats.dodge

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
        self.busy_until = 0.0
        self.next_attack = 0.0

    # --- behaviour ----------------------------------------------------------
    def think(self, rc, now):
        """One decision: acquire, chase, attack, or go home.

        idle -> a player within the role's aggro radius makes it a target
        (rc.aggro turns the room's war state on and tells the player with
        lch;enemy) -> chase by short legs of userMove until in reach (next to
        the target for a blade or fist, within the weapon's range with a
        clear line for a gun) -> attack while action points last, one
        burst or swing per ATTACK_PAUSE -> the target leaving the room,
        dying, or being chased past LEASH hexes from home drops it, and the
        mob walks back and recovers.
        """
        if not self.alive or self.aim is not None:
            return
        loc = rc.room.loc
        if self.target is not None and not self.target.present(rc):
            rc.mob_reset(self)
        if self.target is None:
            if now < self.busy_until:
                return
            if self.stats.can_attack:
                found = rc.nearest_fighter(self.cell, self.stats.aggro)
                if found is not None:
                    rc.aggro(self, found)
                    return
            if self.cell != self.home and self.stats.moves:
                rc.mob_walk(self, lambda c: c == self.home, now)
            return
        if now < self.busy_until or now < self.next_attack:
            return
        target = self.target
        if hex_distance(self.home, self.cell, loc.width) > LEASH:
            rc.mob_reset(self)
            return
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
