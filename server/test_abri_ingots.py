"""Current owner rule: 2 one-ounce ingots per existing gold-carrying boss.
Historical reward decisions follow; assertions use the current regional rule.

The gold ingots of Абри's bosses, and Мортимер in its port market.

The owner's order of 2026-10-12: «Делаем Абри ... Там голду дают 6
(работорговцы) и 8 (живодеры), принимает также Мортимер в портовом рынке».

Each of Абри's two factions has two bosses who keep the boss hours
(bosses.py): the camp's (Папаша Абу 327 in 88, Элфрид 360 in 92) and the
chief's of the «встреча с главарем» (Надзиратель Лаки 328 in 89, Бетти 361
in 90). Each carries the faction's gold on every kill, in the ingots of 1
(7620) and 5 (4796) ounces, rows of data/loot_manual.json at chance 1.0
(mobs.SURE, outside MAX_DROPS): the slave traders one of five and one of
one, 6 ounces; the flayers one of five and a stack of three of one, 8. The
numbers are the owner's as said (the halving of 2026-10-11 was over
before). The camps' treasurers (590, 591) stand all day and carry none, and
nobody else of Абри does. A window of the boss hours holds 52 ounces for
the whole server: Вади-Хальфа's 8, the valley's 2 and Абри's 28; 96 since
Донгола's 4 (the owner's Донгола, 2026-10-13, server/test_dongola_ingots.py),
170 since Абу-Хамед's 5 (the owner's Абу-Хамед, 2026-10-14,
server/test_abuhamed_ingots.py).

Мортимер (1188) stands in the port market 187 (data/placements.json) as
well as in the slums 255: the same stall, the ingots for gold at face
value, and his 301-307, cashing less the original's 0.05 an ingot.

In process: the bosses, their rows, seeded rolls, a hundred bags each
through RoomCombat on a real database; with the rule off (LAVA_BOSS_HOURS=
off) no ingot; a boss killed in his window remembered through a restart;
the budget of a window. On a socket, the clock at six in the evening
(LAVA_BOSS_CLOCK): Мортимер in the port market with his stall, Папаша Абу
shot in his camp 88 with the admin gun and his bag holding 6 ounces, both
ingots cashed at Мортимер's in 187 -- one ack each, the ledger with a row
for each, and no gold out of the air.

    LAVA_RES=.../res python3 server/test_abri_ingots.py

Current owner rule (2026-10-26) supersedes historical sums above: 2
one-ounce ingots per existing carrier. Exchanges and existing ingots are unchanged.
"""
import asyncio
import glob
import json
import os
import random
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
for _k in ("LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ", "LAVA_BOSS_CLOCK",
           "LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_QUESTS"):
    os.environ.pop(_k, None)

sys.path.insert(0, HERE)
import accounts      # noqa: E402
import bosses        # noqa: E402
import combat        # noqa: E402
import inventory     # noqa: E402
import items         # noqa: E402
import mobs          # noqa: E402
import names         # noqa: E402
import progression   # noqa: E402
import quests        # noqa: E402
import rooms         # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

I1, I5, I10 = 7620, 4796, 4797
INGOTS = (I1, I5, I10)
OUNCE = progression.GOLD_OUNCE
MORTIMER, PORT, SLUMS = 1188, 187, 255
MORTIMER_CELL = (40, 72)
CASH = {I1: 301, I5: 302, I10: 303}
ADMIN_GUN, ROUNDS = 1534, 6092
BOSSES = {
    # type: (faction, the place he stands in, the ingots of his bag)
    327: ("работорговцы", 88, {I1: 2}), 328: ("работорговцы", 89, {I1: 2}),
    360: ("живодеры", 92, {I1: 2}), 361: ("живодеры", 90, {I1: 2}),
}
FACTION_OUNCES = {"работорговцы": 2, "живодеры": 2}
TREASURERS = (590, 591)
ABU = 327
WINDOW_OUNCES = 49
MT = world.mob_types()


def ingots_of(pairs):
    out = {}
    for t, n in pairs:
        if t in INGOTS:
            out[t] = out.get(t, 0) + n
    return out


def ounces(bag):
    return sum(items.GOLD_INGOTS[t] * n for t, n in bag.items()) // OUNCE


# --- the bosses --------------------------------------------------------------------
check("the four are bosses who keep the boss hours, by names the client has",
      {t: (world.creature_role(t), bosses.keeps_hours(t), names.known(t)) for t in BOSSES},
      {t: ("boss", True, True) for t in BOSSES})
standing = {}
for loc_id in sorted({where for _f, where, _b in BOSSES.values()}):
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)
    for npc in room.npcs.values():
        if world.creature_role(npc.type_id) == "boss":
            standing.setdefault(npc.type_id, []).append(loc_id)
check("each stands in his own place: the camps 88 and 92, the chiefs' places 89 and 90",
      {t: standing.get(t) for t in BOSSES}, {t: [where] for t, (_f, where, _b) in BOSSES.items()})
check("  ..and the treasurers stand in the camps all day, carrying no ingot",
      ([standing.get(t) for t in TREASURERS], [bosses.keeps_hours(t) for t in TREASURERS],
       [i for t in TREASURERS for i, *_r in mobs.loot_table(t) + mobs.quest_table(t) if i in INGOTS]),
      ([[88], [92]], [False, False], []))
_one = {t: ingots_of(mobs.roll_table(t, random.Random(t))) for t in BOSSES}
check("a kill of either of a faction's bosses: 2 ounces per existing gold carrier",
      {f: sorted({ounces(_one[t]) for t, (ff, _w, _b) in BOSSES.items() if ff == f})
       for f in FACTION_OUNCES}, {f: [n] for f, n in FACTION_OUNCES.items()})
check("each row certain (chance 1.0), outside the cap",
      {t: sorted(i for i, c, _v in mobs.loot_table(t) if c >= mobs.SURE) for t in BOSSES},
      {t: sorted(b) for t, (_f, _w, b) in BOSSES.items()})
check("  ..2 one-ounce ingots (mobs.count_of)",
      {t: {i: mobs.count_of(t, i) for i in b} for t, (_f, _w, b) in BOSSES.items()},
      {t: b for t, (_f, _w, b) in BOSSES.items()})
rng = random.Random(20261012)
seen = {t: sorted({tuple(sorted(ingots_of(mobs.roll_table(t, rng)).items())) for _ in range(1000)})
        for t in BOSSES}
check("seeded, a thousand kills each: exactly his ingots in every one",
      seen, {t: [tuple(sorted(b.items()))] for t, (_f, _w, b) in BOSSES.items()})
full = {t: sorted({tuple(sorted(ingots_of(mobs.loot_for(mobs.stats(t), rng)).items()))
                   for _ in range(300)}) for t in BOSSES}
check("what the body carries adds no ingot (mobs.loot_for)",
      full, {t: [tuple(sorted(b.items()))] for t, (_f, _w, b) in BOSSES.items()})
abri_types = set()
for lid in (88, 89, 90, 92, 191, 261, 262, 289, 189, 192, 219, 220, 1038):
    abri_types |= {t for _c, t in world.location(lid).spawns if t} | set(world.camp_fill(lid))
check("nobody else of Абри's camps and quest places carries an ingot",
      sorted(t for t in abri_types - set(BOSSES)
             if {r[0] for r in mobs.loot_table(t)} & set(INGOTS)), [])


# --- the budget of a window ----------------------------------------------------------------
# Every creature with a certain ingot that keeps the hours stands in one place
# and comes once a window: the window's gold is the sum of their bags.
rollers = sorted(int(t) for t in mobs.TYPES if {r[0] for r in mobs.loot_table(int(t))} & set(INGOTS))
places = {t: set() for t in rollers}
# A place out of the game stands nobody (data/retired.json places): Донгола's
# copy 1171 of the Peacekeepers' camp put Шеф Дженсен down a second time.
with open(os.path.join(os.path.dirname(HERE), "data", "retired.json"), encoding="utf-8") as _fh:
    RETIRED_PLACES = {int(k) for k in json.load(_fh)["places"] if not k.startswith("_")}
for p in glob.glob(os.path.join(world.RES, "locations", "static", "*.xml")):
    lid = int(os.path.basename(p)[:-4])
    if lid in RETIRED_PLACES:
        continue
    try:
        loc = world.location(lid)
    except (KeyError, OSError, ValueError, AttributeError):
        continue
    for _c, t in loc.spawns:
        if t in places and world.belongs_here(t, MT[t][1], MT[t][0], loc.war, lid):
            places[t].add(lid)
    for t in world.camp_fill(lid):
        if t in places:
            places[t].add(lid)
for lid, recs in world.placements().items():
    for r in recs:
        if int(r["type"]) in places:
            places[int(r["type"])].add(int(lid))
window = {t: sum(items.GOLD_INGOTS[i] * mobs.count_of(t, i) for i, c, _v in mobs.loot_table(t)
                 if i in INGOTS and c >= mobs.SURE) // OUNCE for t in rollers}
check("every carrier of a certain ingot keeps the hours and stands in one place",
      {t: (bosses.keeps_hours(t), len(places[t])) for t in rollers},
      {t: (True, 1) for t in rollers})
check("a window of the boss hours holds %d ounces for the whole server: Вади-Хальфа's 8, the"
      " valley's 1, Абри's 8, Донгола's 12, Абу-Хамед's 20" % WINDOW_OUNCES,
      (sum(window.values()), sum(window[t] for t in BOSSES), window.get(2103)),
      (WINDOW_OUNCES, 8, 1))
check("  ..twelve windows a day: %d ounces" % (12 * WINDOW_OUNCES),
      len(bosses.parse_hours(bosses.DEFAULT_HOURS)) * sum(window.values()), 12 * WINDOW_OUNCES)


# --- a hundred bags each, through RoomCombat and a real database -----------------------
class _Room(object):
    def __init__(self, loc_id):
        self.loc = world.location(loc_id)
        self.npcs = {}
        self.players = {}
        self.ws = False

    def broadcast(self, frame, exclude=None):
        pass


DB0 = os.path.join(tempfile.mkdtemp(), "bags.db")
accounts.DB_PATH = DB0


def _cancel(*rcs):
    for rc in rcs:
        for bag in rc.loot.values():
            if bag.expiry is not None:
                bag.expiry.cancel()


async def _bags():
    store = accounts.Store(DB0)
    combat.RNG.seed(1012)
    out = {}
    for t, (_f, where, _b) in sorted(BOSSES.items()):
        rc = combat.RoomCombat(_Room(where), store)
        shapes = set()
        for i in range(100):
            mob = mobs.Mob(i + 1, t, 10 + 3 * i)
            rc.corpse_gone(mob, [])
            rows = [store.item(u) for u in rc.loot[mob.cell].uniqs]
            shapes.add(tuple(sorted((r["type_id"], r["count"], r["root"]) for r in rows
                                    if r["type_id"] in INGOTS)))
        _cancel(rc)
        out[t] = sorted(shapes)
    store.close()
    return out


async def _rule_off():
    store = accounts.Store(DB0)
    real = bosses.HOURS
    bosses.HOURS = ()
    out = {}
    try:
        for t, (_f, where, _b) in sorted(BOSSES.items()):
            rc = combat.RoomCombat(_Room(where), store)
            mob = mobs.Mob(1, t, 10)
            rc.corpse_gone(mob, [])
            rows = [store.item(u) for u in rc.loot[mob.cell].uniqs] if mob.cell in rc.loot else []
            out[t] = (bosses.keeps_hours(t), len(rows) > 0,
                      sorted(r["type_id"] for r in rows if r["type_id"] in INGOTS))
            _cancel(rc)
    finally:
        bosses.HOURS = real
        store.close()
    return out


def _msk(h, m=0, s=0):
    return datetime(2026, 10, 12, h, m, s, tzinfo=bosses.ZONE).timestamp()


async def _restart():
    db = os.path.join(tempfile.mkdtemp(), "restart.db")
    now = [_msk(18, 0, 5)]
    real = (bosses.clock, combat.CORPSE_DELAY)
    bosses.clock = lambda: now[0]
    combat.CORPSE_DELAY = 0.05
    out = {}

    def room_90(store):
        room = rooms.Room(world.location(90), rooms.IdAllocator(), MT, 90)
        rc = combat.RoomCombat(room, store)
        return room, rc, [m for m in rc.mobs.values() if m.type_id == 361][0]

    try:
        store = accounts.Store(db)
        room, rc, betty = room_90(store)
        rc.keep_hours()
        out["stands at six"] = betty.eid in room.npcs
        rc.kill(betty, None)
        await asyncio.sleep(0.3)
        out["her bag"] = sorted(ingots_of(
            (store.item(u)["type_id"], store.item(u)["count"])
            for bag in rc.loot.values() for u in bag.uniqs).items())
        out["written down"] = store.boss_kills([rc.boss_spot(betty)]) == {rc.boss_spot(betty): _msk(18)}
        _cancel(rc)
        store.close()
        now[0] = _msk(18, 30)
        store = accounts.Store(db)
        room, rc, betty = room_90(store)
        rc.keep_hours()
        out["after a restart in the window"] = (betty.eid in room.npcs, betty.away)
        now[0] = _msk(20, 0, 5)
        rc.keep_hours()
        out["at eight she comes"] = (betty.eid in room.npcs, betty.alive)
        store.close()
    finally:
        bosses.clock, combat.CORPSE_DELAY = real
    return out


def _run(coro, what):
    try:
        return asyncio.run(coro)
    except Exception:
        import traceback
        fails.append(what + ":\n" + traceback.format_exc())
        return None


check("100 kills each leave a bag with his ingots, a stack per kind",
      _run(_bags(), "the bags"),
      {t: [tuple(sorted((i, n, items.TRASH) for i, n in b.items()))]
       for t, (_f, _w, b) in sorted(BOSSES.items())})
check("with the rule off, every boss's bag holds his loot and no ingot",
      _run(_rule_off(), "the rule off"), {t: (False, True, []) for t in BOSSES})
check("Бетти killed in her window stays away through a restart until the next one",
      _run(_restart(), "a restart in the window"),
      {"stands at six": True, "her bag": [(I1, 2)], "written down": True,
       "after a restart in the window": (False, True), "at eight she comes": (True, True)})


# --- Мортимер in the port market -------------------------------------------------------------
check("Мортимер stands in the port market by a row of data/placements.json, on his cell",
      [(int(r["type"]), tuple(r["cell"])) for r in world.placed_in(PORT)], [(MORTIMER, MORTIMER_CELL)])
check("  ..which can stand (rooms.placement_problems), at peace there",
      (rooms.placement_problems(MT), world.location(PORT).war), ([], 0))
there = {}
for loc_id in (PORT, SLUMS):
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)
    there[loc_id] = [n.type_id for n in room.npcs.values()].count(MORTIMER)
check("  ..one Мортимер there, one still in the slums", there, {PORT: 1, SLUMS: 1})
check("  ..his stall, the three ingots, and his cashing and change wherever he stands",
      (items.stock_for(MORTIMER), quests.given_by(MORTIMER)),
      ([I1, I5, I10], [301, 302, 303, 304, 305, 306, 307]))
check("  ..cashing pays the ounces less 0.05: 0.95 and 4.95",
      [quests.get(CASH[t]).rew_gold for t in (I1, I5)], [95, 495])


# --- the server ----------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT_NO = free_port()
DB = os.path.join(tempfile.mkdtemp(), "ingots.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("assayer", "secret")
_store.close()
CRED = accounts.credential("assayer", "secret")
CLOCK = datetime(2026, 10, 12, 18, 0, 5)
PORT_CELL = world.cell_of(PORT)
env = dict(os.environ, LAVA_PORT=str(PORT_NO), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX=str(PORT_CELL[0]), LAVA_GY=str(PORT_CELL[1]),
           LAVA_AP_REGEN="25", LAVA_RESPAWN="600", LAVA_SEED="9", LAVA_POLICY_PORT="0",
           LAVA_BOSS_CLOCK=CLOCK.isoformat())
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""
        self.seen = []

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

    def frames(self, wait=0.6):
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


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def entity(target_id):
    return "x1%08x" % target_id


def enter(c):
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return got, named(got, "lenter")[0]["pos"]


def goto(c, loc):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc)
    c.until(lambda f: f[0] == "lcall")
    return enter(c)


def npc(frames, type_id, frame="userInfo_Trader"):
    return next((p for p in named(frames, frame) if p["name"] == type_id), {})


def chat(c, line):
    c.send("userMsg;entry=@%s@;group=0;" % line)
    return c.until(lambda f: f[0] == "userMsg") + c.frames(0.3)


def bag_of(char_id, type_id):
    probe = accounts.Store(DB)
    try:
        return sum(r["count"] for r in probe.items_of(char_id)
                   if r["type_id"] == type_id and r["slot"] == inventory.BAG)
    finally:
        probe.close()


def shoot(c, gun, target, tries=40):
    """Fire the admin gun at an entity until it falls: the frames of its
    death, or None."""
    for _ in range(tries):
        c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(target)))
        got = c.until(lambda f: f[0] == "ss_di_firearm"
                      or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.3)
        if [p for p in named(got, "lch") if p.get("dead") == target]:
            return got
        time.sleep(0.5)
    return None


def money(char_id):
    probe = accounts.Store(DB)
    try:
        return tuple(probe.money(char_id))
    finally:
        probe.close()


def ledger(char_id):
    probe = accounts.Store(DB)
    try:
        return probe.ledger(char_id)
    finally:
        probe.close()


CHAR = None
try:
    c = Client(testkit.connect(PORT_NO, srv, LOG, None))
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@assayer@;")
    c.frames()
    probe = accounts.Store(DB)
    CHAR = probe.db.execute("SELECT id FROM characters WHERE name = ?", ("assayer",)).fetchone()["id"]
    probe.close()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    arrival, pos = enter(c)

    # --- Мортимер in the port market --------------------------------------------------------
    check("the port market of Абри: the room the player stands in",
          [p["id"] for p in named(c.seen, "lcall")][-1:], [PORT])
    mort = npc(arrival, MORTIMER)
    check("Мортимер is there: a stall of the three ingots, his cashing and change on offer",
          (mort.get("can_trade"), mort.get("type_list"), mort.get("give_quests")),
          (1, [I1, I5, I10], [301, 302, 303, 304, 305, 306, 307]))
    check("  ..every inhabitant by a name the client has",
          [p["name"] for n, p in arrival if n.startswith("userInfo_") and n != "userInfo_Player"
           and not names.known(p["name"])], [])

    # --- the admin gun, loaded --------------------------------------------------------------
    gun = str(named(chat(c, "/give %d" % ADMIN_GUN), "ss_obj_status")[0]["obj"])
    rounds = str(named(chat(c, "/give %d 50" % ROUNDS), "ss_obj_status")[0]["obj"])
    c.send("ss_get;target=0;slot=11;")
    held = [str(x) for x in c.frames()[0][1]["o_list"]]
    if held[6] != "0":
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % gun)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
    c.until(lambda f: f[0] == "ss_di_firearm")

    # --- Папаша Абу, in his camp at six --------------------------------------------------------
    where = BOSSES[ABU][1]
    arrival, pos = goto(c, where)
    place = world.location(where)
    infos = {p["id"]: p["name"] for p in named(arrival, "userInfo")}
    placed = {p["newUser"]: p["pos"] for p in named(arrival, "lch")
              if "newUser" in p and p["newUser"] in infos}
    boss_ids = [i for i, t in infos.items() if t == ABU]
    check("at six Папаша Абу is in his camp", len(boss_ids), 1)
    dead = None
    if boss_ids:
        boss = boss_ids[0]
        home = placed[boss]
        others = [cell for i, cell in placed.items() if i != boss and mobs.stats(infos[i]).aggro]
        reach = mobs.stats(ABU).aggro
        wary = max(mobs.stats(infos[i]).aggro for i in placed if i != boss) + 0.5
        spots = sorted((mobs.hex_distance(cell, home, place.width), cell)
                       for cell in range(place.width * place.height)
                       if cell not in place.obstacles and cell not in placed.values()
                       and reach + 0.5 < mobs.hex_distance(cell, home, place.width) <= 12
                       and mobs.line_of_fire(place, cell, home) is None
                       and all(mobs.hex_distance(cell, o, place.width) > wary for o in others))
        check("there is a place to shoot him from", bool(spots), True)
        pos = spots[0][1] if spots else pos
        c.send("moveTo;path=|%d|;" % pos)
        c.frames(0.5)
        dead = shoot(c, gun, boss)
    check("Папаша Абу falls", dead is not None, True)
    got = list(dead or [])
    if not named(got, "ss_loot"):
        got += c.until(lambda f: f[0] == "ss_loot", 5)
    bag_at = [p["hex"][0] for p in named(got, "ss_loot") if p.get("s_status") == 1]
    check("his bag lies where he fell", len(bag_at), 1)
    if bag_at and boss_ids:
        placed_now = dict(placed)
        for n, p in c.seen:
            if n == "userMove" and p.get("id") in placed_now:
                placed_now[p["id"]] = p["path"][-1]
        # The camp's men stand closer to their boss than the chief's place's
        # to theirs: whoever would see the player at the bag is shot first,
        # from where he stands, and lies there until the respawn (600 s).
        near = [i for i, cell in placed_now.items() if i != boss_ids[0]
                and mobs.stats(infos[i]).aggro
                and mobs.hex_distance(cell, bag_at[0], place.width) <= wary + 1]
        downed = [i for i in near if shoot(c, gun, i, 10) is not None]
        check("  ..the fighters beside the bag shot first", sorted(downed), sorted(near))
        placed_now = {i: cell for i, cell in placed_now.items() if i not in downed}
        for n, p in c.seen:
            if n == "userMove" and p.get("id") in placed_now:
                placed_now[p["id"]] = p["path"][-1]
        wary_cells = {cell for cell in range(place.width * place.height)
                      if any(mobs.hex_distance(cell, o, place.width) <= wary
                             for i, o in placed_now.items() if i != boss_ids[0]
                             and mobs.stats(infos[i]).aggro)}
        path = mobs.find_path(place, pos, lambda cell: cell == bag_at[0]
                              or progression.within_reach(cell, bag_at[0], place.width,
                                                          place.height), wary_cells)
        check("the bag is a walk away", path is not None, True)
        c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path or [pos]))
        c.frames(0.2 * len(path or [pos]) + 1.0)
        c.send("ss_create;s_type=0;target=%d;" % bag_at[0])
        check("the bag opens", acks(c.frames()), [0])
        c.send("ss_get;slot=24;")
        lst = [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]
        oids = [inventory.parse_oid(o) for o in lst[lst.index("0") + 1:]]
        probe = accounts.Store(DB)
        stacks = sorted((t, probe.item(u)["count"]) for u, t, _r in oids if t in INGOTS)
        probe.close()
        print("  ..  Папаша Абу left %s" % sorted(t for _u, t, _r in oids))
        check("in it: 2 one-ounce ingots", stacks, [(I1, 2)])
        c.send("ss_upd;s_status=3;obj=x0;param=1;")
        check("taken whole, one ack", acks(c.frames(0.8))[:1], [0])
        c.send("ss_upd;s_status=0;obj=x0;param=1;")
        c.frames(0.3)
    check("2 ounces in the bag", (bag_of(CHAR, I5), bag_of(CHAR, I1)), (0, 2))

    # --- cashed at Мортимер's, in the port market ---------------------------------------------
    arrival, pos = goto(c, PORT)
    mid = npc(arrival, MORTIMER).get("id", 0)
    purse0 = money(CHAR)
    cashed = []
    for t in (I1,) * 2:
        before = money(CHAR)
        c.send("q_st;mob=%d;q_idx=%d;" % (mid, quests.given_by(MORTIMER).index(CASH[t])))
        got = c.frames(0.8)
        q_id = [p["q_id"] for n, p in got if n.startswith("q_di_")][:1]
        c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (mid, (q_id or [0])[0]))
        got = c.frames(0.8)
        after = money(CHAR)
        cashed.append((t, acks(got), after[1] - before[1], after[0] - before[0]))
    check("cashing the one-ounce ingot: one ack, 0.95 on the account, no afro",
          cashed, [(I1, [0], 95, 0)] * 2)
    check("  ..the ingots gone from the bag", [bag_of(CHAR, t) for t in INGOTS], [0, 0, 0])
    check("  ..2 ounces of loot made 1.90 on the account: no gold out of the air",
          money(CHAR)[1] - purse0[1], 190)
    rows = [(r["source"], r["ref"], r["afro"], r["gold"]) for r in ledger(CHAR)]
    check("the ledger: each cashing under quest and its type",
          [r for r in rows if r[0] == "quest"], [("quest", 301, 0, 95)] * 2)
    check("  ..and the ledger holds what the purse holds",
          (sum(r[2] for r in rows), sum(r[3] for r in rows)), money(CHAR))
    c.send("logout;")
    c.frames(0.5)
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        out = fh.read()
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [ln for ln in out.splitlines() if "C->S" in ln or "  ..  " in ln]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-50:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("abri ingots OK")
