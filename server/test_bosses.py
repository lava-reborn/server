"""Bosses keep hours: only at the owner's hours, 14:00, 18:00 and 22:00 Moscow
time, and not after a kill.

The owner's rule (2026-09-24): «босс постоянно не должен быть в локации, а
только в 18 и 20 часов», 14 added on 2026-10-02, and on 2026-10-11 «давай
14 18 22». The warehouses' «Хозяин склада» comes once a day, at 20:00
(the owner's «на складах хозяин должен прриходить один раз!!!», 2026-10-12).
bosses.py holds the clock and the windows,
combat.RoomCombat.keep_hours applies them to a room. Three layers here:

  * the windows themselves, on the Moscow clock and not the machine's, and
    the settings they are read from: a slip in one costs its default, never
    the server's start nor, but for "off", the rule; and the defaults of
    docker-compose.yml and the env examples, which must name the hours of
    bosses.DEFAULT_HOURS that the client's release and lava-http's string
    table are built on, and the hour of bosses.DEFAULT_WAREHOUSE_HOURS that
    a server started without them keeps; the warehouse masters' list
    against the warehouses' files;
  * a real room and a real RoomCombat on a clock the test turns by hand:
    out of hours nobody meets the boss, at the hour it arrives the way a
    respawn does, at the end of its stay it leaves -- but not in the middle
    of a fight -- and a boss that was killed is not back after the respawn
    delay the rest of the camp keeps, only at the next hour; a warehouse's
    master is not there at 14, 18 or 22, comes at 20:00 and leaves at
    21:00, and killed -- a restart in between or not -- he is back the next
    day at 20:00;
  * a server on a socket whose clock starts a little before six in the
    evening (LAVA_BOSS_CLOCK): the crashed Il-4 (539), where the boss is the
    only inhabitant and stands fifty hexes from the door, is empty on entry;
    the player standing in it sees the boss walk in at six and fade at the
    end of its stay; and the same place under another number (547), entered
    by a second player before, during and after the window while nobody else
    is in it, shows the boss only during it.
"""
import asyncio
import glob
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

# The defaults are part of what is tested: the owner's hours, whatever the
# shell running this happens to carry.
for _k in ("LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ", "LAVA_BOSS_CLOCK",
           "LAVA_WAREHOUSE_HOURS"):
    os.environ.pop(_k, None)

sys.path.insert(0, HERE)
import accounts      # noqa: E402
import bosses        # noqa: E402
import combat        # noqa: E402
import mobs          # noqa: E402
import rooms         # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

IL4, IL4_12 = 539, 547                 # "Сбитый ИЛ-4", level-6 and level-12 copies
BOSS, BOSS_12 = 6897, 6907             # fash_boss_6_1, fash_boss_12_1
DOG = 82

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def at(h, m=0, s=0, day=24):
    """A moment on the Moscow clock, 2026-09-<day>, as seconds since the epoch."""
    return datetime(2026, 9, day, h, m, s, tzinfo=bosses.ZONE).timestamp()


# --- the windows ------------------------------------------------------------------
check("the owner's hours are the default: 14:00, 18:00 and 22:00, for an hour, in Moscow",
      (bosses.HOURS, bosses.STAY, bosses.TZ_NAME),
      ([14 * 60, 18 * 60, 22 * 60], 3600.0, "Europe/Moscow"))
check("  ..as the quests' starts name them, long and short",
      (bosses.say_hours(), bosses.say_hours(short=True)),
      ("в 14:00, 18:00 и 22:00", "в 14, 18 и 22 часа"))
_hours = bosses.HOURS
try:
    bosses.HOURS = [18 * 60, 22 * 60]
    _two = bosses.say_hours(short=True)
    bosses.HOURS = [21 * 60]
    _one = bosses.say_hours(short=True)
    bosses.HOURS = [18 * 60 + 30]
    _half = bosses.say_hours(short=True)
    bosses.HOURS = []
    _off = bosses.say_hours()
finally:
    bosses.HOURS = _hours
check("  ..the hour's word agrees with the last, minutes keep the long form, no hours"
      " is any time", (_two, _one, _half, _off),
      ("в 18 и 22 часа", "в 21 час", "в 18:30", "в любое время"))
check("six in the evening in Moscow is three in the afternoon UTC",
      at(18), datetime(2026, 9, 24, 15, tzinfo=timezone.utc).timestamp())
check("a second before six: no window", bosses.slot(at(17, 59, 59)), None)
check("at six the six o'clock window opens", bosses.slot(at(18)), at(18))
check("and holds to the last second of its hour", bosses.slot(at(18, 59, 59)), at(18))
check("at seven it is shut", bosses.slot(at(19)), None)
check("half past ten is the ten o'clock one", bosses.slot(at(22, 30)), at(22))
check("half past eight: no window any more", bosses.slot(at(20, 30)), None)
check("noon, nine at night: none",
      (bosses.slot(at(12)), bosses.slot(at(21))), (None, None))
check("six in the evening UTC is nine in Moscow: none",
      bosses.slot(datetime(2026, 9, 24, 18, tzinfo=timezone.utc).timestamp()), None)
check("a boss is a boss, a dog is not",
      (bosses.keeps_hours(BOSS), bosses.keeps_hours(DOG)), (True, False))

_hours, _stay = bosses.HOURS, bosses.STAY
try:
    bosses.HOURS, bosses.STAY = [23 * 60], 2 * 3600.0
    check("a window opened yesterday is still open past midnight",
          bosses.slot(at(0, 30, day=25)), at(23, day=24))
    bosses.HOURS, bosses.STAY = [18 * 60, 20 * 60], 3 * 3600.0
    check("where two overlap the later one counts", bosses.slot(at(20, 30)), at(20))
    bosses.HOURS = []
    check("no hours: the rule is off and a boss is an ordinary mob",
          (bosses.slot(at(18)), bosses.keeps_hours(BOSS)), (None, False))
finally:
    bosses.HOURS, bosses.STAY = _hours, _stay

# --- the warehouses' master: once a day ------------------------------------------------
# The owner's «на складах хозяин должен прриходить один раз!!!» (2026-10-12):
# the «Хозяин склада» keeps one hour of his own, 20:00 by default -- the
# original's «Хозяин присутствует с 20:00 до 21:00» -- and the stay of every
# boss; every other boss keeps 14, 18 and 22.
WH_SEVER = 7448                        # boss_WH_sever, the Северный склад 111
check("the warehouse masters' hour is the default too: 20:00, for the bosses' stay of an hour",
      (bosses.WAREHOUSE_HOURS, bosses.DEFAULT_WAREHOUSE_HOURS, bosses.STAY),
      ([20 * 60], "20", 3600.0))
check("a warehouse master keeps hours like every boss", bosses.keeps_hours(WH_SEVER), True)
check("  ..his own, 20:00 alone, while a camp boss keeps 14, 18 and 22",
      (bosses.hours_of(WH_SEVER), bosses.hours_of(BOSS)),
      ([20 * 60], [14 * 60, 18 * 60, 22 * 60]))
check("  ..all eight masters the one hour",
      sorted({tuple(bosses.hours_of(t)) for t in bosses.WAREHOUSE_MASTERS}), [(20 * 60,)])
check("at eight in the evening his window opens and holds to the last second of the hour",
      (bosses.slot_of(WH_SEVER, at(19, 59, 59)), bosses.slot_of(WH_SEVER, at(20)),
       bosses.slot_of(WH_SEVER, at(20, 59, 59)), bosses.slot_of(WH_SEVER, at(21))),
      (None, at(20), at(20), None))
check("  ..at 14:00, 18:00 and 22:00, the bosses' windows, he has none",
      [bosses.slot_of(WH_SEVER, at(h, m)) for h in (14, 18, 22) for m in (0, 30)], [None] * 6)
check("  ..the camp boss has those, and not his",
      ([bosses.slot_of(BOSS, at(h, 30)) for h in (14, 18, 22)], bosses.slot_of(BOSS, at(20, 30)),
       bosses.slot(at(18, 30)), bosses.slot(at(20, 30))),
      ([at(14), at(18), at(22)], None, at(18), None))
check("  ..the next day's eight o'clock is a new window",
      bosses.slot_of(WH_SEVER, at(20, 10, day=25)), at(20, day=25))

_wh, _hours = bosses.WAREHOUSE_HOURS, bosses.HOURS
try:
    bosses.WAREHOUSE_HOURS = []
    _back = (bosses.hours_of(WH_SEVER), bosses.slot_of(WH_SEVER, at(18, 30)),
             bosses.slot_of(WH_SEVER, at(20, 30)))
    bosses.WAREHOUSE_HOURS = [21 * 60 + 30]
    _moved = (bosses.slot_of(WH_SEVER, at(20, 30)), bosses.slot_of(WH_SEVER, at(21, 45)),
              bosses.hours_of(BOSS))
    bosses.WAREHOUSE_HOURS, bosses.HOURS = _wh, []
    _off = (bosses.keeps_hours(WH_SEVER), bosses.slot(at(18, 30)))
finally:
    bosses.WAREHOUSE_HOURS, bosses.HOURS = _wh, _hours
check("LAVA_WAREHOUSE_HOURS=off: no hours of his own, he keeps the bosses' 14, 18 and 22",
      _back, ([14 * 60, 18 * 60, 22 * 60], at(18), None))
check("  ..another hour moves him alone", _moved,
      (None, at(21, 30), [14 * 60, 18 * 60, 22 * 60]))
check("  ..LAVA_BOSS_HOURS=off turns the rule off for him too: an ordinary mob", _off,
      (False, None))

# The list against the data: the bosses of the warehouses' own files (fn
# stok_*, the Хальфа's WH, Донгола's DN and Абу-Хамед's AH), each its file's
# one boss, by the names data/mob_types.json gives them; no master stands
# anywhere else; and every capturable site's boss is one of them.
_stok = {}
for _p in sorted(glob.glob(os.path.join(world.RES, "locations", "static", "*.xml"))):
    with open(_p, "rb") as _fh:
        _head = re.search(rb'<location[^>]*\bfn="(stok_[^"]*)"', _fh.read(4096))
    if _head:
        _lid = int(os.path.basename(_p)[:-4])
        _stok[_lid] = sorted({t for _c, t in world.location(_lid).spawns
                              if world.creature_role(t) == "boss"})
check("the warehouses' files are eleven -- 109-114, 128, 288 and the copies 982-984 -- each"
      " with one boss",
      (sorted(_stok), sorted({len(b) for b in _stok.values()})),
      ([109, 110, 111, 112, 113, 114, 128, 288, 982, 983, 984], [1]))
check("  ..and their bosses are bosses.WAREHOUSE_MASTERS, all eight",
      sorted({b[0] for b in _stok.values()}), sorted(bosses.WAREHOUSE_MASTERS))
with open(os.path.join(os.path.dirname(HERE), "data", "mob_types.json"), encoding=ENC) as _fh:
    _mt = json.load(_fh)["types"]
check("  ..named boss_WH_, boss_DN_ and boss_AH_ in data/mob_types.json, and nothing else is",
      sorted(int(k) for k, v in _mt.items() if re.match(r"boss_(WH|DN|AH)_", v.get("name", ""))),
      sorted(bosses.WAREHOUSE_MASTERS))
_elsewhere = []
for _p in sorted(glob.glob(os.path.join(world.RES, "locations", "static", "*.xml"))):
    _lid = int(os.path.basename(_p)[:-4])
    if _lid not in _stok and bosses.WAREHOUSE_MASTERS & {t for _c, t in
                                                         world.location(_lid).spawns}:
        _elsewhere.append(_lid)
check("  ..no other location's file has one of them", _elsewhere, [])
with open(os.path.join(os.path.dirname(HERE), "data", "holdings.json"), encoding=ENC) as _fh:
    _sites = json.load(_fh)["sites"]
check("  ..and the capturable sites' bosses (data/holdings.json) are masters: Вади-Хальфа's"
      " three and, since 2026-10-13, Донгола's",
      sorted((s["boss"], s["boss"] in bosses.WAREHOUSE_MASTERS)
             for k, s in _sites.items() if not k.startswith("_")),
      [(7448, True), (7449, True), (7450, True), (7451, True), (7452, True), (7453, True)])

check("hours parse as minutes, sorted and once each",
      bosses.parse_hours(" 20, 18 ,18"), [18 * 60, 20 * 60])
check("H:MM is an hour too", bosses.parse_hours("18:30"), [18 * 60 + 30])
check("what is not an hour is left out, the rest kept",
      bosses.parse_hours("25,x,18,7:75"), [18 * 60])
check("\"off\" is none at all", bosses.parse_hours("off"), [])


def imported(**settings):
    """bosses as a server imports it under these settings: "HOURS STAY
    WAREHOUSE_HOURS", or how the import ended when it did not."""
    env = dict(os.environ, **settings)
    run = subprocess.run([sys.executable, "-c",
                          "import bosses; print(bosses.HOURS, bosses.STAY,"
                          " bosses.WAREHOUSE_HOURS)"],
                         cwd=HERE, env=env, capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else "exit %d" % run.returncode


# The settings are read at import, and an import that raises is a server
# that does not start; a setting that turns the rule off is every boss
# standing all day. Only "off" may do that.
OWNERS = "[840, 1080, 1320] 3600.0 [1200]"
check("a stay that is not a number is the default stay, not a server that "
      "will not start", imported(LAVA_BOSS_STAY="час"), OWNERS)
check("nor is a stay of nothing, which would be bosses that never come",
      (imported(LAVA_BOSS_STAY="0"), imported(LAVA_BOSS_STAY="-5")), (OWNERS, OWNERS))
check("blank hours are the owner's hours, not the rule turned off",
      (imported(LAVA_BOSS_HOURS=""), imported(LAVA_BOSS_HOURS="  ")), (OWNERS, OWNERS))
check("and so are hours in which not one hour could be read",
      imported(LAVA_BOSS_HOURS="18-20"), OWNERS)
check("\"off\" is still off", imported(LAVA_BOSS_HOURS="off"), "[] 3600.0 [1200]")
check("a test clock that is no time is ignored, not fatal",
      imported(LAVA_BOSS_CLOCK="в шесть"), OWNERS)
check("and good settings are read as given",
      imported(LAVA_BOSS_HOURS="18", LAVA_BOSS_STAY="0.25"), "[1080] 15.0 [1200]")
check("the warehouse hours the same way: blank, a word or no hour in them are 20:00",
      [imported(LAVA_WAREHOUSE_HOURS=v) for v in ("", "  ", "восемь", "20-21")], [OWNERS] * 4)
check("  ..\"off\" is none of his own (he keeps the bosses' hours), good ones are read as"
      " given, and neither touches the bosses'",
      (imported(LAVA_WAREHOUSE_HOURS="off"), imported(LAVA_WAREHOUSE_HOURS="19:30, 21")),
      ("[840, 1080, 1320] 3600.0 []", "[840, 1080, 1320] 3600.0 [1170, 1260]"))


# The client's release (deploy/remote/lava-gate.sh, a docker run with no
# LAVA_BOSS_*) and lava-http's string table name the hours in the quests'
# starts from bosses.DEFAULT_HOURS, while lava-game reads its own from
# docker-compose.yml's default. One that differs is bosses coming at hours
# no quest and no map label names: the hours change in DEFAULT_HOURS and in
# these defaults together. The warehouse masters' hour is named by no quest:
# DEFAULT_WAREHOUSE_HOURS is what a server started without compose keeps,
# LAVA_WAREHOUSE_HOURS's defaults what lava-game reads, and the warehouses'
# map labels name it as the original's fixed text (test_map_labels); the
# three change together all the same.
ROOT = os.path.dirname(HERE)


def _default(path, pattern, flags=0):
    """The setting a file of the repo gives, or None without one."""
    with open(os.path.join(ROOT, path), encoding=ENC) as fh:
        found = re.search(pattern, fh.read(), flags)
    return found.group(1).strip() if found else None


check("docker-compose.yml, .env.example and deploy/env.example default to "
      "bosses.DEFAULT_HOURS",
      [_default("docker-compose.yml", r"LAVA_BOSS_HOURS:\s*\$\{LAVA_BOSS_HOURS:-([^}]*)\}"),
       _default(".env.example", r"^LAVA_BOSS_HOURS=(.*)$", re.M),
       _default(os.path.join("deploy", "env.example"), r"^LAVA_BOSS_HOURS=(.*)$", re.M)],
      [bosses.DEFAULT_HOURS] * 3)
check("  ..and to bosses.DEFAULT_WAREHOUSE_HOURS for the warehouse masters",
      [_default("docker-compose.yml",
                r"LAVA_WAREHOUSE_HOURS:\s*\$\{LAVA_WAREHOUSE_HOURS:-([^}]*)\}"),
       _default(".env.example", r"^LAVA_WAREHOUSE_HOURS=(.*)$", re.M),
       _default(os.path.join("deploy", "env.example"), r"^LAVA_WAREHOUSE_HOURS=(.*)$", re.M)],
      [bosses.DEFAULT_WAREHOUSE_HOURS] * 3)


# --- a real room on a clock turned by hand ------------------------------------------
class _Seat(object):
    """A session standing in the room: whatever reaches it is kept."""
    pid = rooms.player_id(1)

    def __init__(self):
        self.sent = []
        self.combat = type("F", (), {"aim": None, "strike": None, "duels": {},
                                     "dead": False})()

    def send(self, cmd, **params):
        self.sent.append((cmd, params))

    def send_npc_info(self, npc_id):
        self.sent.append(("npc_info", dict(id=npc_id)))

    def take(self):
        out, self.sent = self.sent, []
        return out


class _Brain(object):
    """Just enough of a RoomCombat for Mob.think: a player in reach of it."""

    def __init__(self, loc):
        self.room = type("R", (), {"loc": loc})()
        self.aggroed = 0

    def nearest_fighter(self, cell, radius):
        return object()

    def aggro(self, mob, fighter):
        self.aggroed += 1

    def mob_walk(self, mob, goal, t):
        pass


NOW = [0.0]


async def _hours():
    loc = world.location(IL4)
    home = [c for c, t in loc.spawns if t == BOSS][0]
    store = accounts.Store(os.path.join(tempfile.mkdtemp(), "bosses.db"))
    combat.CORPSE_DELAY, combat.RESPAWN_DELAY = 0.05, 0.05
    real_clock = bosses.clock
    bosses.clock = lambda: NOW[0]
    try:
        NOW[0] = at(17)
        room = rooms.Room(loc, rooms.IdAllocator(), world.mob_types())
        check("the Il-4's file puts its boss in the room", [n.type_id for n in room.npcs.values()], [BOSS])
        eid = list(room.npcs)[0]
        rc = combat.RoomCombat(room, store)
        boss = rc.mobs[eid]
        check("the room knows its boss keeps hours", rc.bosses, [boss])
        rc.keep_hours()
        check("at five it is not there: out of the room, not an actor",
              (eid in room.npcs, rc.actor(eid)), (False, None))

        seat = _Seat()
        room.players[seat] = True
        NOW[0] = at(17, 59, 59)
        rc.keep_hours()
        check("a second before six nothing happens", seat.take(), [])

        NOW[0] = at(18)
        rc.keep_hours()
        check("at six it arrives as a respawn does: newUser on its cell, then its details",
              seat.take(), [("lch", dict(newUser=eid, pos=home, rtype=world.MOB)),
                            ("npc_info", dict(id=eid))])
        check("and stands in the room, whole",
              (room.npcs[eid].cell, rc.actor(eid) is boss, boss.hp == boss.hp_max),
              (home, True, True))

        NOW[0] = at(18, 59, 59)
        rc.keep_hours()
        check("it stays through its hour", (seat.take(), eid in room.npcs), ([], True))

        NOW[0] = at(19)
        boss.target = object()
        rc.keep_hours()
        check("at seven, in a fight, it stays to finish it",
              (seat.take(), eid in room.npcs, boss.leaving), ([], True, True))
        brain = _Brain(loc)
        boss.target, boss.busy_until = None, 0.0
        boss.think(brain, 0.0)
        check("but starts no new fight meanwhile", brain.aggroed, 0)
        boss.leaving = False
        boss.think(brain, 0.0)
        check("(a boss in its hours would have)", brain.aggroed, 1)
        boss.target = None
        rc.keep_hours()
        check("the fight over, it leaves: the fade a corpse gets",
              seat.take(), [("lch", dict(lostUser=eid))])
        check("and is out of the room", (eid in room.npcs, rc.actor(eid)), (False, None))

        NOW[0] = at(19, 30)
        rc.keep_hours()
        check("between the hours it is not back", (seat.take(), eid in room.npcs), ([], False))

        NOW[0] = at(22)
        rc.keep_hours()
        check("at ten it comes again", [f[0] for f in seat.take()], ["lch", "npc_info"])

        NOW[0] = at(22, 5)
        rc.kill(boss, None)
        await asyncio.sleep(0.4)          # the corpse fades, the respawn delay passes
        got = seat.take()
        check("killed: it falls, fades and leaves its bag -- and nothing more",
              [(n, sorted(p)) for n, p in got],
              [("lch", ["dead"]), ("lch", ["lostUser"]), ("ss_loot", ["hex", "s_status"])])
        check("not back after the respawn delay", (eid in room.npcs, boss.away), (False, True))
        for t in (at(22, 10), at(22, 59, 59), at(23), at(12, day=25)):
            NOW[0] = t
            rc.keep_hours()
        check("nor for the rest of its hour, nor overnight", (seat.take(), eid in room.npcs), ([], False))
        NOW[0] = at(18, day=25)
        rc.keep_hours()
        check("it is back at the next hour, whole",
              ([f[0] for f in seat.take()], eid in room.npcs, boss.hp == boss.hp_max),
              (["lch", "npc_info"], True, True))

        # The rest of the camp keeps the respawn delay: the same kill of a dog.
        dog = mobs.Mob(10 ** 6 - 1, DOG, home + 3)
        rc.mobs[dog.eid] = dog
        room.npcs[dog.eid] = rooms.NPC(dog.cell, DOG, world.MOB)
        rc.kill(dog, None)
        await asyncio.sleep(0.4)
        check("a dog killed at the same moment is back after the delay",
              [p.get("newUser") for n, p in seat.take() if n == "lch" and "newUser" in p],
              [dog.eid])
        for bag in rc.loot.values():
            if bag.expiry is not None:
                bag.expiry.cancel()
    finally:
        bosses.clock = real_clock
        store.close()


try:
    asyncio.run(_hours())
except Exception:
    fails.append("the room on a hand-turned clock:\n" + traceback.format_exc())


# --- a boss's escort comes with the boss --------------------------------------------
# Большой Мвамба's three thugs in his camp (data/placements.json "escort", the
# owner's of 2026-10-03: «рес только в момент появления босса»): killed, a thug
# is not back on the respawn delay but with Мвамба's next arrival; the living
# stay where they are when he leaves.
MVAMBA_CAMP, MVAMBA, THUG = 31, 1406, 566


async def _escort():
    loc = world.location(MVAMBA_CAMP)
    store = accounts.Store(os.path.join(tempfile.mkdtemp(), "escort.db"))
    combat.CORPSE_DELAY, combat.RESPAWN_DELAY = 0.05, 0.05
    real_clock, real_hours = bosses.clock, bosses.HOURS
    bosses.clock = lambda: NOW[0]
    try:
        NOW[0] = at(14, 10)
        room = rooms.Room(loc, rooms.IdAllocator(), world.mob_types())
        rc = combat.RoomCombat(room, store)
        boss = [m for m in rc.mobs.values() if m.type_id == MVAMBA][0]
        thugs = sorted((m for m in rc.mobs.values() if m.type_id == THUG), key=lambda m: m.eid)
        check("the camp's three thugs are its boss's escort",
              (len(thugs), sorted(m.eid for m in rc.escorts)), (3, [m.eid for m in thugs]))
        check("  ..standing apart from him, not at his elbow",
              all(mobs.hex_distance(m.home, boss.home, loc.width) >= 4 for m in thugs), True)
        rc.keep_hours()
        seat = _Seat()
        room.players[seat] = True

        first, second = thugs[0], thugs[1]
        rc.kill(first, None)
        await asyncio.sleep(0.4)          # the corpse fades, the respawn delay passes
        seat.take()
        check("a thug killed is not back after the respawn delay",
              (first.eid in room.npcs, first.away), (False, True))

        NOW[0] = at(15)
        rc.keep_hours()
        check("Мвамба's stay over, he leaves; the living thugs stay put",
              ([p.get("lostUser") for n, p in seat.take() if n == "lch"],
               second.eid in room.npcs, first.eid in room.npcs),
              ([boss.eid], True, False))

        NOW[0] = at(17, 59, 59)
        rc.keep_hours()
        check("between his hours nobody comes back", seat.take(), [])

        NOW[0] = at(18)
        rc.keep_hours()
        back = [p.get("newUser") for n, p in seat.take() if n == "lch" and "newUser" in p]
        check("at his next hour he arrives, and the killed thug with him, whole",
              (back, first.hp == first.hp_max, second.eid in back),
              ([boss.eid, first.eid], True, False))

        # The room empties in his hour with a thug dead and Мвамба worn down
        # and off his cell: no tick sends him away at seven, so whoever walks
        # in at ten past ten (Session.enter_room asks keep_hours first)
        # finds him standing. He has come for this hour all the same.
        NOW[0] = at(18, 10)
        rc.kill(first, None)
        await asyncio.sleep(0.4)
        boss.hp = 1
        boss.cell = boss.home + 1
        room.npcs[boss.eid] = room.npcs[boss.eid]._replace(cell=boss.cell)
        del room.players[seat]
        seat.take()
        NOW[0] = at(22, 10)
        rc.keep_hours()
        check("a thug killed before the room emptied is back for Мвамба's next hour, "
              "though nothing sent Мвамба away in between",
              (first.eid in room.npcs, first.away), (True, False))
        check("  ..and Мвамба is whole, on his own cell, as an arrival leaves him",
              (boss.hp == boss.hp_max, room.npcs[boss.eid].cell, boss.slot),
              (True, boss.home, at(22)))

        # A thug killed a moment before Мвамба arrives is still a fading
        # corpse at the arrival (CORPSE_DELAY): he is back as soon as it is
        # gone, not at the hour after.
        room.players[seat] = True
        NOW[0] = at(23)
        rc.keep_hours()
        NOW[0] = at(13, 59, 59, day=25)
        rc.kill(second, None)
        NOW[0] = at(14, day=25)
        rc.keep_hours()
        await asyncio.sleep(0.4)
        got = [(n, p) for n, p in seat.take() if n == "lch" and ("newUser" in p or "lostUser" in p)]
        check("a thug whose corpse was fading when Мвамба arrived is back once it fades",
              ([sorted(p.items())[0] for n, p in got], second.eid in room.npcs, second.away),
              ([("lostUser", boss.eid), ("newUser", boss.eid), ("lostUser", second.eid),
                ("newUser", second.eid)], True, False))

        # Watched, in a fight that outlasts the gap, he is not made whole by
        # the clock at the next hour; his escort comes all the same.
        boss.target, boss.hp = object(), 7
        NOW[0] = at(15, day=25)
        rc.keep_hours()
        rc.kill(first, None)
        await asyncio.sleep(0.4)
        seat.take()
        NOW[0] = at(18, day=25)
        rc.keep_hours()
        check("still fighting when his next hour opens: he stays as he is, the thug comes",
              ([p.get("newUser") for n, p in seat.take() if n == "lch" and "newUser" in p],
               boss.hp, boss.leaving, boss.slot),
              ([first.eid], 7, False, at(18, day=25)))
        boss.target = None

        # The rule off (LAVA_BOSS_HOURS=off): no boss keeps hours, and the
        # escort is ordinary again, back on the respawn delay.
        bosses.HOURS = ()
        room2 = rooms.Room(loc, rooms.IdAllocator(), world.mob_types())
        rc2 = combat.RoomCombat(room2, store)
        thug2 = [m for m in rc2.mobs.values() if m.type_id == THUG][0]
        rc2.kill(thug2, None)
        await asyncio.sleep(0.4)
        check("with the hours off, a thug comes back on the respawn delay",
              (thug2.eid in room2.npcs, thug2.away), (True, False))
        for bag in list(rc.loot.values()) + list(rc2.loot.values()):
            if bag.expiry is not None:
                bag.expiry.cancel()
    finally:
        bosses.clock, bosses.HOURS = real_clock, real_hours
        store.close()


try:
    asyncio.run(_escort())
except Exception:
    fails.append("the boss's escort:\n" + traceback.format_exc())

check("a row marked escort in a location with no boss is refused before the server starts",
      [p.split(": ", 1)[1] for p in rooms.placement_problems(
          world.mob_types(), {100: [dict(type=THUG, cell=[30, 30], escort=True, why="x")]})
       if "escort" in p],
      ["566 on 30,30: an escort in a location with no boss to come with"])


# --- a warehouse's master: once a day -------------------------------------------------
# The «Хозяин склада» of Донгола's Северный склад (113, boss_DN_sever 7451),
# a warehouse nobody can take yet (holdings.py has no business with his kill),
# on a clock turned by hand: not there at the bosses' hours, in at 20:00, out
# at 21:00; killed, not back that night nor at the next day's 14 and 18, back
# at its 20:00 -- and a server restarted after the kill, inside his window,
# keeps him away (boss_kills), on the window of his own hour.
DN_SEVER, MASTER = 113, 7451


async def _master():
    loc = world.location(DN_SEVER)
    store = accounts.Store(os.path.join(tempfile.mkdtemp(), "master.db"))
    combat.CORPSE_DELAY, combat.RESPAWN_DELAY = 0.05, 0.05
    real_clock = bosses.clock
    bosses.clock = lambda: NOW[0]
    try:
        NOW[0] = at(13)
        room = rooms.Room(loc, rooms.IdAllocator(), world.mob_types())
        rc = combat.RoomCombat(room, store)
        check("Донгола's Северный склад has one boss keeping hours, its «Хозяин склада»",
              [m.type_id for m in rc.bosses], [MASTER])
        master = rc.bosses[0]
        eid = master.eid
        seat = _Seat()
        room.players[seat] = True
        rc.keep_hours()
        seat.take()
        check("at one in the afternoon he is not there", (eid in room.npcs, rc.actor(eid)),
              (False, None))

        def tick(*when):
            """The clock to each moment, a tick there: (the frames about him,
            whether he stands in the room) after each."""
            out = []
            for t in when:
                NOW[0] = t
                rc.keep_hours()
                out.append(([(n, sorted(p)) for n, p in seat.take()
                             if p.get("newUser") == eid or p.get("lostUser") == eid
                             or p.get("id") == eid], eid in room.npcs))
            return out

        check("at 14:00 and 18:00, the bosses' hours, he does not come, nor a second before 20:00",
              tick(at(14), at(14, 30), at(18), at(18, 30), at(19, 59, 59)), [([], False)] * 5)
        check("at 20:00 he arrives as a respawn does: newUser on his cell, then his details",
              tick(at(20)), [([("lch", ["newUser", "pos", "rtype"]), ("npc_info", ["id"])], True)])
        check("  ..whole, for the window of his hour",
              (master.hp == master.hp_max, master.slot), (True, at(20)))
        check("  ..stays through it and leaves at 21:00",
              tick(at(20, 59, 59), at(21)), [([], True), ([("lch", ["lostUser"])], False)])
        check("at 22:00, the bosses' hour, he does not come again",
              tick(at(22), at(22, 30)), [([], False)] * 2)

        check("the next day: not at 14:00 nor 18:00, in at 20:00",
              [got[1] for got in tick(at(14, day=25), at(18, day=25), at(20, day=25))],
              [False, False, True])
        NOW[0] = at(20, 10, day=25)
        rc.kill(master, None)
        await asyncio.sleep(0.4)          # the corpse fades, the respawn delay passes
        seat.take()
        check("killed at 20:10: not back after the respawn delay",
              (eid in room.npcs, master.away), (False, True))
        check("  ..the kill written down with his window, 20:00",
              store.boss_kills([rc.boss_spot(master)]), {rc.boss_spot(master): at(20, day=25)})

        # The server restarts at half past eight: the room is made afresh
        # from the database, inside his window.
        NOW[0] = at(20, 30, day=25)
        room2 = rooms.Room(loc, rooms.IdAllocator(), world.mob_types())
        rc2 = combat.RoomCombat(room2, store)
        master2 = rc2.bosses[0]
        rc2.keep_hours()
        check("a restart inside his window: he starts away, killed in it",
              (master2.eid in room2.npcs, master2.away, master2.slot),
              (False, True, at(20, day=25)))
        seen = []
        for t in (at(20, 59, day=25), at(22, day=25), at(14, day=26), at(18, day=26),
                  at(19, 59, 59, day=26), at(20, day=26)):
            NOW[0] = t
            rc2.keep_hours()
            seen.append(master2.eid in room2.npcs)
        check("  ..not back that night nor at the next day's 14:00 and 18:00, back at its 20:00",
              seen, [False, False, False, False, False, True])
        check("  ..whole, for the new window", (master2.hp == master2.hp_max, master2.slot),
              (True, at(20, day=26)))

        # A camp boss in a room made at the same moments keeps 14, 18 and 22.
        NOW[0] = at(13, day=26)
        il4 = combat.RoomCombat(rooms.Room(world.location(IL4), rooms.IdAllocator(),
                                           world.mob_types()), store)
        camp = il4.bosses[0]
        seen = []
        for t in (at(14, day=26), at(15, day=26), at(20, day=26), at(22, day=26)):
            NOW[0] = t
            il4.keep_hours()
            seen.append(camp.eid in il4.room.npcs)
        check("the Il-4's boss, on the same clock: in at 14:00, gone at 15:00, none at 20:00,"
              " in at 22:00", seen, [True, False, False, True])
        for bag in list(rc.loot.values()) + list(rc2.loot.values()):
            if bag.expiry is not None:
                bag.expiry.cancel()
    finally:
        bosses.clock = real_clock
        store.close()


try:
    asyncio.run(_master())
except Exception:
    fails.append("the warehouse's master on a hand-turned clock:\n" + traceback.format_exc())


# --- the server -------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "bosses_srv.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("waiter", "secret")
_store.register("visitor", "secret")
_store.close()
CRED_A = accounts.credential("waiter", "secret")
CRED_B = accounts.credential("visitor", "secret")

# The server's clock starts LEAD seconds before six on the Moscow clock and
# runs on; the boss stays STAY_MIN minutes. est() is where that clock is by
# now, or a moment ahead of it: its offset was taken when bosses.py was
# imported, a little after the process started.
LEAD = 30.0
STAY_MIN = 0.25
SIX = at(18)
START = SIX - LEAD
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730",
           LAVA_BOSS_CLOCK=datetime.fromtimestamp(START, bosses.ZONE)
           .replace(tzinfo=None).isoformat(),
           LAVA_BOSS_HOURS="18", LAVA_BOSS_STAY=str(STAY_MIN))
_launched = time.time()
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


def est():
    return START + (time.time() - _launched)


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


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


def named(frames, name):
    return [p for n, p in frames if n == name]


def login(c, cred, nick):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    c.frames(wait=1.5)


def goto(c, loc):
    """Into a location; everything the arrival brought."""
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc)
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    return c.frames(wait=1.5)


def types_in(arrival):
    """The creature types the snapshot showed, by their userInfo."""
    return sorted(p["name"] for p in named(arrival, "userInfo"))


try:
    a = Client(connect())
    b = Client(connect())
    login(a, CRED_A, "waiter")
    login(b, CRED_B, "visitor")

    seen = goto(a, IL4)
    check("before six the Il-4 is empty", (types_in(seen), named(seen, "lch")), ([], []))
    seen = goto(b, IL4_12)
    check("so is its twin, entered by nobody before", types_in(seen), [])
    # A slow start eats into LEAD; this says by how much.
    print("  ..  %.1f s to spare before six" % (SIX - est()))
    check("(and that was before six on the server's clock)", est() < SIX, True)
    goto(b, 102)

    # Six o'clock, with the waiter standing there.
    got = a.until(lambda f: f[0] == "lch" and "newUser" in f[1],
                  wait=max(0.0, SIX - est()) + 5)
    got += a.frames(0.5)
    news = [p for p in named(got, "lch") if "newUser" in p]
    home = [c for c, t in world.location(IL4).spawns if t == BOSS][0]
    check("at six the boss walks in on its own cell, as a mob",
          [(p["pos"], p["rtype"]) for p in news], [(home, world.MOB)])
    boss_id = news[0]["newUser"] if news else None
    check("and is introduced: its userInfo, then its bars",
          [(n, p["name"] if n == "userInfo" else p["id"]) for n, p in got
           if n == "userInfo" or (n == "usrUp" and p.get("id") == boss_id)],
          [("userInfo", BOSS), ("usrUp", boss_id)])
    check("not a second early", est() >= SIX - 1.5, True)

    # The twin was empty and nobody has been in it since six: the boss has
    # come all the same, and is there for the visitor to find.
    seen = goto(b, IL4_12)
    check("the twin's boss came while nobody was there, and is found in it",
          types_in(seen), [BOSS_12])
    goto(b, 102)

    end = SIX + STAY_MIN * 60
    got = a.until(lambda f: f[0] == "lch" and "lostUser" in f[1],
                  wait=max(0.0, end - est()) + 5)
    check("at the end of its stay it leaves",
          [p["lostUser"] for p in named(got, "lch") if "lostUser" in p], [boss_id])
    check("not a second early", est() >= end - 1.5, True)

    seen = goto(a, IL4)
    check("walking back in after it: nobody", types_in(seen), [])
    seen = goto(b, IL4_12)
    check("and the twin's boss is gone too, with nobody there to see it go",
          types_in(seen), [])

    for c in (a, b):
        c.send("logout;")
        c.frames(0.3)
finally:
    srv.terminate()
    srv.wait(timeout=10)
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
print("bosses OK")
