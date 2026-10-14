"""Encounters: the open wasteland around a town is not empty.

DESIGNED, on the original's own traces. Every desert template the map falls
back to (res/locations/desert/0001-0011.xml) keeps a <mobs> of two or three
four-hex cells and no creature type -- "nests" the dead server filled, by
region, since nothing in the file says who stood there (hscan: the camps'
tooltips speak of «патрули вокруг»). So walking the map near a town now and
then ends that way: the figure stops, the cell's own wasteland opens, and on
its nests stands a pack of the nearest camp's faction at that camp's level
band, after him from the first moment.

The client has a loader caption for this, «Внимание! На Вас напали в локации
...» (LocGen.loadSources), and never shows it here: Master.playerIntercepted
wants userCallChangeWorld down, the player's own chWorld to the map raised
it, and only the next lcall's loading or lenter lowers it (Master.
enterLocation) -- this server sends gmap only to answer a chWorld -- so the
lcall is captioned «Переход в локацию "Пустошь"» like any other. What tells
him is the room: at war the moment he is in (lch;ws=1 -- the battle track,
the fight's bar, the map button greyed) and every creature of the pack red
on his screen and minimap (lch;enemy; combat.RoomCombat.player_entered reads
Room.ambush).

Written once, for any town; a town is a row of REGIONS -- its camps, whose
faction and band data/camp_fill.json already gives (Вади-Хальфа: Новые
колонисты 0-2, Люшер 2-4, Джанджавиды 4-6, Магриб 6-8), and how far out from
them the wasteland is theirs. Only open desert can hold an encounter: never a
settlement's cell nor a cell beside one (the town and its doorsteps; the
cell of a place taken out of the game still counts, world.retired_cells),
never the rim's rocks, never the Nubian valley, never the first GRACE cells
from where the player stepped onto the map. A cell entered while walking is one
roll of CHANCE -- once a visit to the map, however often it is walked over --
less under a vehicle by its aggro_mod (ts_si: «к агрессии мобов»); a band
whose every creature is grey to the player (progression.
GREY_GAP) leaves him be; after one, COOLDOWN seconds of peace, and no more
than PER_DAY a day.

The pack is the player's own: a room of its own (Encounters.room_key), under
the cell's location, which the client is told is the desert it always was.
Its creatures stand on the nests and come for him; he arrives on the edge he
walked in over, beside its exit cells and twenty-five cells or more from
them, where none of the four bands reaches (ten at most) -- so one step back
over that edge opens the exit window (Location.finishMove on a zone cell,
which ws=1 does not grey) and he is out before the first shot, or he fights.
Nothing of the pack comes back when killed (combat.RoomCombat.corpse_gone
reads Room.ambush), and the room is gone with the last one out. Loot and
experience are a camp's creature's, nothing more.

The day's count and the rest live in this process: a restart forgets them,
and whoever walks the ring again that day may meet up to PER_DAY more.
"""
import asyncio
import json
import logging
import math
import os
import random
import time
import weakref
from collections import namedtuple

import mobs
import names
import progression
import rooms
import transport
import travel
import world

log = logging.getLogger("lava")

# The towns whose wasteland is peopled: the camps whose faction and band an
# encounter takes (data/camp_fill.json), and how far from the nearest of them
# a cell still belongs to them, in cells. DESIGNED: the four camps of
# Вади-Хальфа stand within twenty cells of each other, and twenty-five from
# them is the town's ring -- the gold mine's road, the quarries, the lake
# shore -- and nowhere near Абри (216 cells) or the valley. Абри's two camps
# (the owner's «В Абри добавь мобов в лагеря и в окрестности», 2026-10-12),
# the slave traders 8-10 (88) and the flayers 10-12 (92), fifteen cells
# apart, by the same rule: twenty-five from them is the town's desert, the
# fields, the totem, Зубери's digs, the oasis of Карло Меони and the roads to
# the works; the two towns' rings never meet. Донгола's two (the owner's «и
# потом сделай донголу тоже», 2026-10-13), the ДСР 12-14 (93) and the
# Peacekeepers 14-16 (98), forty-five cells apart, by the same rule: the road to
# the mines and the prison, the oasis «Аль-Захаб», the warehouses, the cells
# the map names «Засада» (5905-5913 by 2001-2006, wasteland since). Its ring
# reaches over the Nile to the west, where nobody walks: south of the
# station the owner's wall stands on the bank, and by the pier it is closed
# (data/terrain_verified.json), so an ambush, met only on a cell a player
# walks onto, is never met across the river (server/test_dongola_world.py
# holds that once, by a walk from the station). It never meets Абри's.
# Абу-Хамед's three (the owner's «сделай потом абу хамед в таком же формате»,
# 2026-10-14), the Somali pirates 16-18 (132, west of the town), the
# Alliance's outpost 16-18 (168, south-east) and its base 19-20 (263, far to
# the east), by the same rule: the oasis «Аль-Кусай», the works' road, the
# prison, the Dark Mine and the mountain paths, the base's eastern desert.
# The rings reach into the Nile's loop and over its far bank, which the
# owner's wall closes (data/terrain_verified.json): only the cells a walk from
# the station reaches are met (server/test_abuhamed_world.py holds that once).
# The town itself and its gates take no ambush (near_town), and it never
# meets Донгола's.
REGIONS = (
    {"town": "Вади-Хальфа", "camps": (80, 81, 84, 85), "reach": 25},
    {"town": "Абри", "camps": (88, 92), "reach": 25},
    {"town": "Донгола", "camps": (93, 98), "reach": 25},
    {"town": "Абу-Хамед", "camps": (132, 168, 263), "reach": 25},
)

# One roll per cell entered on the map: about one encounter in thirty cells
# walked in the ring, a couple on the way to the gold mine and back. DESIGNED.
CHANCE = float(os.environ.get("LAVA_ENCOUNTER_CHANCE", "0.03"))
# Nobody is waylaid on the doorstep: the cells this near to where the player
# stepped onto the map are the approaches of the place he left. DESIGNED.
GRACE = 3
# Seconds of peace after an encounter is left, and how many a day (the day of
# the daily limit, UTC). DESIGNED.
COOLDOWN = float(os.environ.get("LAVA_ENCOUNTER_COOLDOWN", "120"))
PER_DAY = int(os.environ.get("LAVA_ENCOUNTERS_PER_DAY", "12"))
# How far into the cell, in cells, the figure is stopped: inside the square
# the client draws, not on its border.
INSIDE = 0.3
# The sampling step along a leg when looking for the cells it enters.
STEP = 0.02

RNG = (random.Random(int(os.environ["LAVA_SEED"])) if os.environ.get("LAVA_SEED")
       else random.Random())

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A camp's share of the wasteland: the camp, its cell, its level band and the
# creatures of its faction in that band.
Band = namedtuple("Band", "camp cell lo hi types")
# An encounter a session is in: its room's key, the location and map cell.
Meeting = namedtuple("Meeting", "key loc_id cell")

_BANDS = None


def bands():
    """[Band] of every region's camps: the fill's own fighters (role mob,
    level inside the band, a creature the client can draw and name) -- no
    chief, treasurer or box."""
    global _BANDS
    if _BANDS is None:
        try:
            with open(os.path.join(HERE, "data", "camp_fill.json"), encoding="utf-8") as fh:
                fill = json.load(fh)["fill"]
        except (OSError, ValueError, KeyError):
            fill = {}
        known = world.mob_types()
        out = []
        for region in REGIONS:
            for camp in region["camps"]:
                rec, cell = fill.get(str(camp)), world.cell_of(camp)
                if not rec or cell is None:
                    continue
                lo, hi = (int(v) for v in rec["band"])
                types = sorted({t for t in (int(v) for v in rec["types"])
                                if t in known and known[t][0] == world.MOB
                                and names.known(t) and mobs.stats(t).role == "mob"
                                and lo <= mobs.stats(t).level <= hi})
                if types:
                    out.append((Band(camp, cell, lo, hi, tuple(types)), region["reach"]))
        _BANDS = out
    return _BANDS


def near_town(gx, gy):
    """Whether a cell is a settlement's or touches one: the town and its
    doorsteps, where nobody is waylaid. A place the owner took out of the
    game counts as it stood (world.retired_cells): its cell is wasteland
    now, and still the town's -- the cut of Вади-Хальфа (2026-10-09) took
    the market and the craftsmen's quarters off the map, and their doorsteps
    5968,1730, 5968,1731 and 5971,1733, on the walks from Причал to «Генри
    Мл.» 43, the crates 108 and the prison yard 176, stay as safe as they
    were."""
    placed, former = world.settlements(), world.retired_cells()
    return any((gx + dx, gy + dy) in placed or (gx + dx, gy + dy) in former
               for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def band_at(gx, gy):
    """The Band whose wasteland a map cell is, or None: open desert only (no
    settlement, no rock of the rim, not beside a settlement), outside the
    Nubian valley, within a region's reach of its nearest camp."""
    x, y = int(math.floor(gx)), int(math.floor(gy))
    if not world.in_map(x, y) or not world.passable(x, y) or world.in_noob_valley(x, y):
        return None
    if world.location_at(x, y) != world.pack(x, y) or near_town(x, y):
        return None
    best, best_d = None, None
    for band, reach in bands():
        d = math.hypot(band.cell[0] - x, band.cell[1] - y)
        if d <= reach and (best_d is None or d < best_d):
            best, best_d = band, d
    return best


_NESTS = {}


def nests(loc):
    """The nest cells of a desert template: its <mobs> read four hex digits
    at a time, as cells of its grid (world.Location reads eight, a cell and a
    type, and so finds nobody there). A cell off the grid or on an obstacle
    is left out."""
    found = _NESTS.get(loc.file)
    if found is None:
        found = []
        path = world.path_for(loc.id)
        for chunk in (world._chunks(world._read(path), "mobs", 4) if path else ()):
            try:
                x, y = int(chunk[0:2], 16), int(chunk[2:4], 16)
            except ValueError:
                continue
            cell = y * loc.width + x
            if x < loc.width and y < loc.height and cell not in loc.obstacles:
                found.append(cell)
        _NESTS[loc.file] = found
    return list(found)


def crossings(sx, sy, tx, ty, speed):
    """[(seconds from the start, (gx, gy))] of every map cell a straight leg
    enters, in order; the one it starts in is not entered."""
    dist = math.hypot(tx - sx, ty - sy)
    if dist <= 0 or speed <= 0:
        return []
    steps = max(1, int(math.ceil(dist / STEP)))
    out, prev = [], (int(math.floor(sx)), int(math.floor(sy)))
    for i in range(1, steps + 1):
        f = float(i) / steps
        cell = (int(math.floor(sx + (tx - sx) * f)), int(math.floor(sy + (ty - sy) * f)))
        if cell != prev:
            out.append((f * dist / speed, cell))
            prev = cell
    return out


def entered_over(vx, vy):
    """The edge of a cell a walker going (vx, vy) comes in over: the one
    behind him."""
    if abs(vx) >= abs(vy):
        return travel.W if vx > 0 else travel.E
    return travel.N if vy > 0 else travel.S


def day(now=None):
    """The UTC day (the daily limit's, DAILY_RESET_TIME 0)."""
    return int((time.time() if now is None else now) // 86400)


class Encounters:
    """The encounters of one server: the legs armed, the packs met, who is
    resting from one. Holds rooms.Rooms to make a pack's room in."""

    def __init__(self, rooms_):
        self.rooms = rooms_
        self.armed = weakref.WeakKeyDictionary()     # session -> TimerHandle
        self.met = weakref.WeakKeyDictionary()       # session -> Meeting
        self.origin = weakref.WeakKeyDictionary()    # session -> cell stepped onto the map on
        self.rolled = weakref.WeakKeyDictionary()    # session -> {cell: hit} of this visit
        self.rest_until = {}                         # char id -> time
        self.today = {}                              # char id -> (day, encounters)
        self.serial = 0

    # --- who may be waylaid ------------------------------------------------
    def allowed(self, sess):
        cid = sess.char_id
        if not cid or sess.closed:
            return False
        if time.time() < self.rest_until.get(cid, 0):
            return False
        when, n = self.today.get(cid, (None, 0))
        return not (when == day() and n >= PER_DAY)

    @staticmethod
    def grey(sess, band):
        """Every creature of the band grey to this player: no encounter."""
        return sess.skill_level() - band.hi >= progression.GREY_GAP

    @staticmethod
    def aggro(sess):
        """The vehicle's share of the mobs' aggression (ts_si aggro_mod), 1 on
        foot."""
        type_id = sess.transport_now()
        rec = transport.get(type_id) if type_id is not None else None
        return float(rec["aggro_mod"]) if rec else 1.0

    # --- the legs ------------------------------------------------------------
    def arm(self, sess, sx, sy, tx, ty, speed):
        """A leg has been laid on the map (server.py Session.step_on_map): roll
        for every cell it enters, and time the first hit."""
        self.disarm(sess)
        if CHANCE <= 0 or not self.allowed(sess):
            return
        origin = self.origin.get(sess)
        if origin is None:
            origin = self.origin[sess] = (int(math.floor(sx)), int(math.floor(sy)))
        chance = CHANCE * self.aggro(sess)
        leg = sess.leg
        total = math.hypot(tx - sx, ty - sy) / speed if speed > 0 else 0
        # One roll a cell a visit to the map, however many legs are laid over
        # it: a player who clicks ahead every second, or a pursuit re-aiming,
        # does not roll the cells in front of him again and again.
        rolled = self.rolled.setdefault(sess, {})
        for seconds, cell in crossings(sx, sy, tx, ty, speed):
            if max(abs(cell[0] - origin[0]), abs(cell[1] - origin[1])) < GRACE:
                continue
            band = band_at(*cell)
            if band is None or self.grey(sess, band):
                continue
            if cell not in rolled:
                rolled[cell] = RNG.random() < chance
            if not rolled[cell]:
                continue
            delay = min(total, seconds + INSIDE / speed)
            self.armed[sess] = asyncio.get_running_loop().call_later(
                delay, self.spring, sess, leg, cell, band)
            return

    def disarm(self, sess):
        """The leg is over or given up (server.py Session.cancel_travel)."""
        handle = self.armed.pop(sess, None)
        if handle is not None:
            handle.cancel()

    def spring(self, sess, leg, cell, band):
        """The timer of an armed leg: the player is on the cell now."""
        self.armed.pop(sess, None)
        try:
            if sess.closed or not sess.on_map or sess.leg is not leg or not self.allowed(sess):
                return
            self.start(sess, cell, band, leg)
        except Exception:
            log.exception("  !!    encounter on %s failed", cell)

    # --- the pack ------------------------------------------------------------
    def start(self, sess, cell, band, leg=None):
        """Waylay the player on a map cell: the pack's room, the pack on its
        nests, and the player into it over the edge he came in by."""
        loc_id = world.pack(*cell)
        loc = world.location(loc_id)
        self.serial += 1
        key = (loc_id, "encounter", self.serial)
        room = self.rooms.get(key)
        # What combat.RoomCombat.corpse_gone reads: none of this comes back.
        room.ambush = band.camp
        for nest in nests(loc):
            room.npcs[self.rooms.ids.npc()] = rooms.NPC(nest, RNG.choice(band.types),
                                                         world.MOB)
        side = entered_over(leg[3], leg[4]) if leg else travel.W
        pos = travel.arrival_cell(loc, side)
        self.met[sess] = Meeting(key, loc_id, cell)
        when, n = self.today.get(sess.char_id, (None, 0))
        self.today[sess.char_id] = (day(), (n if when == day() else 0) + 1)
        log.info("  ..    %s waylaid on %d,%d: %d of camp %d's (%d-%d) in %s",
                 sess.nick, cell[0], cell[1], len(room.npcs), band.camp, band.lo,
                 band.hi, loc.file)
        sess.meet(loc_id, pos, cell[0], cell[1])
        return room

    def room_key(self, sess):
        """The pack's room while the player is in it -- its location, on its
        cell, off the map -- or None (server.py Session.room_key)."""
        met = self.met.get(sess)
        if met is None or sess.on_map or sess.loc is None or sess.loc.id != met.loc_id:
            return None
        if (int(math.floor(sess.gx)), int(math.floor(sess.gy))) != met.cell:
            return None
        return met.key

    def left(self, sess):
        """The player left a room (server.py Session.leave_room): stepping onto
        the map marks where the grace is counted from; out of the pack's room
        for good -- the map, a side, home, the socket -- rests him, and takes
        the room away with the last one out."""
        if sess.on_map:
            self.origin[sess] = (int(math.floor(sess.gx)), int(math.floor(sess.gy)))
            self.rolled[sess] = {}
        met = self.met.get(sess)
        if met is None or (not sess.closed and self.room_key(sess) is not None):
            return
        del self.met[sess]
        if sess.char_id:
            self.rest_until[sess.char_id] = time.time() + COOLDOWN
        room = self.rooms.rooms.get(met.key)
        if room is not None and not room.players \
                and not any(m.key == met.key for m in self.met.values()):
            del self.rooms.rooms[met.key]
            log.info("  ..    the pack of %d,%d is gone", met.cell[0], met.cell[1])
            # What lies on its ground -- the pack's loot, the gear of one who
            # died to it -- lies on for the rest of its time on the cell's
            # own wasteland, the room whoever walks in there next enters
            # (combat.LOOT_LIFETIME, RoomCombat.hand_over).
            if room.combat is not None:
                room.combat.hand_over(self.rooms.get(met.loc_id))
