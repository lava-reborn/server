"""Лекари по ценам оригинала: what a full cure costs at every healer of the
cities, and of the places their quest ways lead to.

A healer's full cure (on_conv;op=1, the window of Healer.as) is the other way
to health beside the medicine the cities' stalls sell by tier (server/
test_med_stalls.py): at the 10 afro of the designed fee (server.MEDIC_PRICE)
it made the peace line pointless wherever it stood. The original's prices, by
the rule of Вади-Хальфа's review (2026-09-28, decision 8): the article's
price, else the town's healer's, the prison the town's and 100 (data/npcs.json
healer_price). One commit lays them and this suite; `git revert` of it puts
every fee but Вади-Хальфа's back to 10 and takes the suite with it.

In process:
  1. every healer of a city's place (data/shop_bands.json) and its fee: the
     valley 10, Вади-Хальфа 150 and its prison yard 250, Абри 150 (Лекарь of
     the oasis by his article, Ведич by the town's), Донгола and Абу-Хамед
     500 (Грегори and Роуз by their articles, the oases' by the town's),
     their prisons 600;
  2. every healer of a place a city's place leads to by a quest's way, a door
     or a side exit (data/passages.json), off the map: the town's fee -- Ведич's
     copy in the Амазонка's waste (1178 at 193, quests 473/474 from Абри's port
     market) and Деда Джоф at the quarry (627, from the pier) -- so no hop
     round the town's price;
  3. every type the file prices is a healer standing at one of those places.
Then on the wire: Ведич at Абри's port market and his copy at 193 show their
150 in the window (a_price) and take it for the cure.

    LAVA_RES=.../res python3 server/test_healer_fees.py
"""
import asyncio
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

DB = os.path.join(tempfile.mkdtemp(), "healer_fees.db")
os.environ["LAVA_DB"] = DB
os.environ["LAVA_CHEATS"] = "1"
for _knob in ("LAVA_LOC", "LAVA_START", "LAVA_PLACEMENTS"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import npcs  # noqa: E402
import rooms  # noqa: E402
import shop_bands  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "лекари по ценам оригинала: Абри 150, Донгола и Абу-Хамед 500, тюрьмы 600"

mt = world.mob_types()
PLACE_CITY = {p: name for name, _lo, _hi, places in shop_bands.CITIES for p in places}


def healers(loc_id):
    """The healer types standing in a place, as its room puts them down."""
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), mt)
    out = []
    for npc in room.npcs.values():
        if npc.root == world.HEALER and npc.type_id not in out:
            out.append(npc.type_id)
    return out


def fee(type_id):
    return npcs.healer_price(type_id, 10)


# --- 1. the cities ---------------------------------------------------------------------------
print("the cities")
FEES = {}
for p, name in sorted(PLACE_CITY.items()):
    for t in healers(p):
        FEES.setdefault(name, {})[t] = fee(t)
check("the healers of the cities' places and their fees: the valley's 10, Вади-Хальфа's 150 and"
      " its prison yard's 250, Абри's 150 (Лекарь of the oasis by his article, Ведич by the"
      " town's), Донгола's and Абу-Хамед's 500 (Грегори and Роуз by their articles, the oases'"
      " by the town's), their prisons' 600",
      FEES,
      {"Нубийская долина": {5140: 10, 5200: 10, 5201: 10, 5202: 10},
       "Вади-Хальфа": {100: 150, 1234: 150, 2111: 250},
       "Абри": {1174: 150, 1266: 150},
       "Донгола": {138: 500, 1268: 500, 2109: 600},
       "Абу-Хамед": {728: 500, 2112: 600, 1270: 500}})

# --- 2. a hop from a city --------------------------------------------------------------------
print()
print("a hop from a city")
with open(travel.passages_path(), encoding="utf-8") as _fh:
    SIDES = json.load(_fh).get("sides") or {}


def hops(loc_id):
    """Where a place leads off the map: a quest's way (travel.quest_ways), a door the server
    follows (travel.door, travel.DOOR_CONFIDENCE) or a side exit of data/passages.json."""
    out = [r.get("target_loc_id") for _c, r in travel.quest_ways(world.location(loc_id))]
    for side in "ab":
        rec = travel.door(loc_id, side)
        if rec and rec.get("confidence") in travel.DOOR_CONFIDENCE:
            out.append(rec.get("target_loc_id"))
    own = SIDES.get(str(loc_id)) if isinstance(SIDES, dict) else None
    out += [r.get("target_loc_id") for r in (own or {}).values() if isinstance(r, dict)]
    return sorted({int(t) for t in out if t and not world.is_wilderness(int(t))})


NEXT = {}
for p, name in sorted(PLACE_CITY.items()):
    for q in hops(p):
        if q in PLACE_CITY:
            continue
        for t in healers(q):
            NEXT.setdefault(q, {})[t] = (name, fee(t))
check("the healers of the places a city's place leads to: the town's fee -- Ведич's copy in the"
      " Пустошь of the Амазонка (1178 at 193, by 473 from Абри's port market and 474 back, any"
      " time) 150, not the designed 10; Деда Джоф at the quarry (627, from the pier) 150;"
      " Грегори in Донгола's quarry (632, by Джамшут's 708 from the new market, 2026-10-13) 500;"
      " Роуз in Абу-Хамед's quarry (636, by Ибрахим's 903 from the quarter, 2026-10-14) 500",
      NEXT, {193: {1178: ("Абри", 150)}, 627: {100: ("Вади-Хальфа", 150)},
             632: {138: ("Донгола", 500)}, 636: {728: ("Абу-Хамед", 500)}})

# --- 3. the file -----------------------------------------------------------------------------
print()
print("the file")
SEEN = {t for fees in FEES.values() for t in fees} | {t for got in NEXT.values() for t in got}
check("every type data/npcs.json prices is a healer of mobs.xml standing at a city's place or a"
      " hop from one: no fee for a healer nobody meets",
      (sorted(t for t in npcs.HEALER_PRICE if mt.get(t, (None,))[0] != world.HEALER),
       sorted(set(npcs.HEALER_PRICE) - SEEN)), ([], []))

# --- on the wire -----------------------------------------------------------------------------
print()
print("on the wire")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("healed", "secret")
_store.close()
CRED = accounts.credential("healed", "secret")

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)


class Writer:
    """What Session needs of an asyncio StreamWriter, and a record of it."""

    def __init__(self):
        self.frames = []
        self.read = 0
        self.closed = False

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        self.closed = True

    async def drain(self):
        pass

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, text):
    name, params = decode(text)
    sess.handle(name, params)
    w = sess.writer
    out, w.read = w.frames[w.read:], len(w.frames)
    return out


def acks(frames):
    return [p["res"] for n, p in frames if n == "cmdAck"]


def goto(sess, loc_id):
    run(sess, "userMsg;entry=@/goto %d@;group=0;" % loc_id)
    run(sess, "lenter;accept=1;")
    return {npc.type_id: eid for eid, npc in sess.room.npcs.items()}


def cure(sess, loc_id, type_id):
    """(where, the window's fee, acks, afro taken) of one full cure."""
    here = goto(sess, loc_id)
    npc = here.get(type_id)
    if npc is None:
        return (sess.room.loc.id, None, [], 0)
    shown = [p.get("a_price") for n, p in run(sess, "getInfo;lvl=0;id=%d;type=0;" % npc)
             if n.startswith("userInfo") and "a_price" in p]
    before = sess.char.afro
    got = run(sess, "on_conv;mob=%d;op=1;" % npc)
    return (sess.room.loc.id, shown[0] if shown else None, acks(got), before - sess.char.afro)


async def main():
    sess = server.Session(Writer(), "healed")
    run(sess, "hello;minor=2;major=0;")
    run(sess, "login;hash=@%s@;" % CRED)
    run(sess, "newPers;res=1;sex=0;name=@Healed@;")
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    run(sess, "userMsg;entry=@/money 10000 0@;group=0;")
    check("Ведич at Абри's port market and his copy in the Пустошь: 150 in the window, 150 for the"
          " cure, one ack each",
          (cure(sess, 187, 1174), cure(sess, 193, 1178)),
          ((187, 150, [0], 150), (193, 150, [0], 150)))


try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("healer fees OK")
