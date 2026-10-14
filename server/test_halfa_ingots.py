"""The gold ingots of Вади-Хальфа's bosses, and Мортимер on the black market.

The owner's order of 2026-10-09: «добавь выпадение слитков золота от боссов
в хальфе: колонисты 3 голды, люшер 5, джанджавиды 6, магриб 10. если нет
слитков подходящего номинала то сделай несколько предметов, типа 3 по 1г
слитку. и добавь в черный рынок мортимера который обменивает слитки
(зачисляя на баланс) и продает их еще. слитки бывают на 1 голду на 5 и на
10». And of 2026-10-11: «у всех лагерей сделай голды в 2 раза меньше и
округли в меньшую сторону» -- 1, 2, 3 and 5 ounces.

Each of the four factions has two bosses who keep the boss hours
(bosses.py): the camp's (Агнес 270, Дитрих 283, Ашрам 299, Ихсан 313) and
the chief's of the «встреча с главарем» (Асмунд 269, Лука 284, Рашад 300,
Кайс 314). Each carries the faction's gold on every kill, in the ingots of 1
(7620) and 5 (4796) ounces, rows of data/loot_manual.json at chance 1.0
(mobs.SURE, outside MAX_DROPS): the colonists one ingot of one; the sect
two of one, a row of count 2 (mobs.count_of, one stack of two); the
Janjaweed three of one, one stack of three; the Maghreb one of five. The
ingot of ten drops from nobody now. Nobody else gains one: Halfa's all-day
bosses (the treasurer 586, 696), and the valley's Ян Дуглас carries his
two of one (test_boss_ingot).

Мортимер (1188) stands on the black market (102, data/placements.json) as
well as in the жилой квартал (36) and the other towns' files. His stall
sells the three ingots for gold at face value (data/npcs.json; the frames'
g_cost, items.GOLD_INGOTS), refuses them for afro (Inventory.buy: that would
turn afro into gold) and refuses a purse without the gold; his 301-303 cash
an ingot on the account less the original's 0.05 an ingot, and both go into
the money ledger. Buying and cashing never makes gold.

In process: the bosses, their tables and seeded rolls, a hundred bags each
through RoomCombat and a real database, nobody else's table; with the rule
off (LAVA_BOSS_HOURS=off) no boss's bag holding an ingot, Кайс killed and
back on the respawn delay included; a boss killed in his window written
down (the boss_kills table) and away through a restart until the next
window, standing again in a window he was not killed in; the frames and
the death rule, the stall, the rooms of 102 and 36, every quest that takes
an ingot against the stall's price. On a socket, the clock at six in the
evening (LAVA_BOSS_CLOCK): Мортимер on the black market with his price list,
Асмунд shot in his place 82 and his bag holding one ingot of an ounce,
then at Мортимер's stall no gold, an afro purchase refused, three purchases
for gold at face value, two cashed in -- one command, one ack, every time,
and the ledger with a row for each.

Written against the code before the change it fails from the bosses' tables
on: no boss of Halfa carries an ingot, no ingot has a gold price, Мортимер
sells nothing and stands nowhere on the black market.

    LAVA_RES=.../lava/res python3 server/test_halfa_ingots.py
"""
import asyncio
import math
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

I1, I5, I10 = 7620, 4796, 4797          # New_Gold_Ingot_1 / _5 / _10
INGOTS = (I1, I5, I10)
OUNCE = progression.GOLD_OUNCE          # gold travels in hundredths
RATE = progression.GOLD_TO_AFRO_RATE
MORTIMER, BLACK_MARKET, QUARTER = 1188, 102, 36
MORTIMER_CELL = (40, 59)
CASH = {I1: 301, I5: 302, I10: 303}     # «Обналичить 1/5/10 унций»
ADMIN_GUN, ROUNDS = 1534, 6092
REFUSED, NO_MONEY = 3, 21               # inventory.RES_REFUSED, RES_NO_MONEY

# The owner's ounces by faction, and the ingots that make them.
FACTION_OUNCES = {"колонисты": 1, "Люшер": 2, "джанджавиды": 3, "Магриб": 5}
BOSSES = {
    # type: (faction, the place he stands in, the ingots of his bag)
    270: ("колонисты", 80, {I1: 1}), 269: ("колонисты", 82, {I1: 1}),
    283: ("Люшер", 81, {I1: 2}), 284: ("Люшер", 83, {I1: 2}),
    299: ("джанджавиды", 84, {I1: 3}), 300: ("джанджавиды", 86, {I1: 3}),
    313: ("Магриб", 85, {I5: 1}), 314: ("Магриб", 87, {I5: 1}),
}
VALLEY_BOSS = 2103                      # Ян Дуглас: his two of one, test_boss_ingot
ALL_DAY = (586, 696)                    # Halfa's bosses on the respawn timer
ASMUND = 269

# Read through getattr: on the code before this change it does not exist, and
# the suite has to say what is missing rather than stop at it.
count_of = getattr(mobs, "count_of", lambda type_id, t: 1)


def ingots_of(pairs):
    """{ingot: pieces} of [(type, count)] rows."""
    out = {}
    for t, n in pairs:
        if t in INGOTS:
            out[t] = out.get(t, 0) + n
    return out


def ounces(bag):
    return sum(items.GOLD_INGOTS[t] * n for t, n in bag.items()) // OUNCE


# --- the bosses --------------------------------------------------------------------
check("the eight are bosses who keep the boss hours, by names the client has",
      {t: (world.creature_role(t), bosses.keeps_hours(t), names.known(t)) for t in BOSSES},
      {t: ("boss", True, True) for t in BOSSES})
MT = world.mob_types()
standing = {}
for loc_id in sorted({where for _f, where, _b in BOSSES.values()}):
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)
    for npc in room.npcs.values():
        if world.creature_role(npc.type_id) == "boss":
            standing.setdefault(npc.type_id, []).append(loc_id)
check("each stands in his own place of the four factions' camps",
      {t: standing.get(t) for t in BOSSES}, {t: [where] for t, (_f, where, _b) in BOSSES.items()})
check("  ..and the treasurer 586 stands in the colonists' camp all day",
      (standing.get(586), [bosses.keeps_hours(t) for t in ALL_DAY]), ([80], [False, False]))

# --- what each one's bag holds -------------------------------------------------------
_one_kill = {t: ingots_of(mobs.roll_table(t, random.Random(t))) for t in BOSSES}
check("a kill of either of a faction's bosses: the owner's ounces halved, 1, 2, 3 and 5",
      {f: sorted({ounces(_one_kill[t]) for t, (ff, _w, _b) in BOSSES.items() if ff == f})
       for f in FACTION_OUNCES}, {f: [n] for f, n in FACTION_OUNCES.items()})
check("each row of theirs is certain (chance 1.0), outside the cap",
      {t: sorted(i for i, c, _v in mobs.loot_table(t) if c >= mobs.SURE) for t in BOSSES},
      {t: sorted(b) for t, (_f, _w, b) in BOSSES.items()})
check("  ..two and three ounces as one stack of ingots of one, the rest one of each",
      {t: {i: count_of(t, i) for i in b} for t, (_f, _w, b) in BOSSES.items()},
      {t: b for t, (_f, _w, b) in BOSSES.items()})
N = 2000
rng = random.Random(20261009)
seen = {}
most = {}
for t in BOSSES:
    rolls = [mobs.roll_table(t, rng) for _ in range(N)]
    seen[t] = sorted({tuple(sorted(ingots_of(r).items())) for r in rolls})
    most[t] = max(sum(1 for i, _n in r if i not in INGOTS) for r in rolls)
check("seeded, %d kills each: exactly his ingots in every one" % N,
      seen, {t: [tuple(sorted(b.items()))] for t, (_f, _w, b) in BOSSES.items()})
check("  ..and the rolled rows keep no more than their own two",
      {t: n <= mobs.MAX_DROPS for t, n in most.items()}, {t: True for t in BOSSES})
rng = random.Random(9)
full = {t: [ingots_of(mobs.loot_for(mobs.stats(t), rng)) for _ in range(300)] for t in BOSSES}
check("what the body carries adds no ingot (mobs.loot_for)",
      {t: sorted({tuple(sorted(b.items())) for b in v}) for t, v in full.items()},
      {t: [tuple(sorted(b.items()))] for t, (_f, _w, b) in BOSSES.items()})

# --- nobody else ----------------------------------------------------------------------
rollers = sorted(int(t) for t in mobs.TYPES
                 if {r[0] for r in mobs.loot_table(int(t))} & set(INGOTS))
# Абри's four hour-keeping bosses carry theirs since the owner's Абри of
# 2026-10-12 (server/test_abri_ingots.py holds them), Донгола's four since
# the owner's Донгола of 2026-10-13 (server/test_dongola_ingots.py),
# Абу-Хамед's five since the owner's Абу-Хамед of 2026-10-14
# (server/test_abuhamed_ingots.py).
ABRI_BOSSES = [327, 328, 360, 361]
DONGOLA_BOSSES = [374, 375, 407, 408]
ABUHAMED_BOSSES = [777, 778, 1037, 1038, 8620]
check("nobody else's table holds an ingot but the valley's boss, his two of one, Абри's and"
      " Донгола's four bosses each and Абу-Хамед's five",
      (rollers, [(i, c) for i, c, _v in mobs.loot_table(VALLEY_BOSS) if i in INGOTS],
       count_of(VALLEY_BOSS, I1)),
      (sorted(list(BOSSES) + [VALLEY_BOSS] + ABRI_BOSSES + DONGOLA_BOSSES + ABUHAMED_BOSSES),
       [(I1, 1.0)], 2))
check("  ..and the ingot of ten drops from Донгола's four bosses and Абу-Хамед's five alone (no creature"
      " dropped it from 2026-10-11 to 2026-10-13)",
      [t for t in rollers if I10 in {r[0] for r in mobs.loot_table(t)}], DONGOLA_BOSSES + ABUHAMED_BOSSES)
check("  ..Halfa's all-day bosses carry none, ordinary or for a quest",
      [i for t in ALL_DAY for i, *_r in mobs.loot_table(t) + mobs.quest_table(t) if i in INGOTS],
      [])
check("  ..and a row with no count puts one thing in the bag",
      [count_of(836, 2258), count_of(ASMUND, 6935), count_of(586, I1)], [1, 1, 1])


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
KILLS = 100


async def _bags():
    store = accounts.Store(DB0)
    combat.RNG.seed(1009)
    out = {}
    for t, (_f, where, _b) in sorted(BOSSES.items()):
        rc = combat.RoomCombat(_Room(where), store)
        shapes = set()
        for i in range(KILLS):
            mob = mobs.Mob(i + 1, t, 10 + 3 * i)
            rc.corpse_gone(mob, [])
            rows = [store.item(u) for u in rc.loot[mob.cell].uniqs]
            # one row per ingot type: (type, pieces in it, its root)
            shapes.add(tuple(sorted((r["type_id"], r["count"], r["root"]) for r in rows
                                    if r["type_id"] in INGOTS)))
        for bag in rc.loot.values():
            if bag.expiry is not None:
                bag.expiry.cancel()
        out[t] = sorted(shapes)
    store.close()
    return out


check("%d kills each leave a bag with his ingots, a stack per kind" % KILLS,
      asyncio.run(_bags()),
      {t: [tuple(sorted((i, n, items.TRASH) for i, n in b.items()))]
       for t, (_f, _w, b) in sorted(BOSSES.items())})


# --- the gold is the hours' --------------------------------------------------------------
# With the rule off (LAVA_BOSS_HOURS=off) a boss is an ordinary mob, back on
# the respawn delay, and a certain ingot on every one of those kills would be
# gold without a limit: his bag holds the rest of his loot and no ingot.
WHERE = {t: where for t, (_f, where, _b) in BOSSES.items()}
WHERE[VALLEY_BOSS] = 34                 # the valley's camp, test_boss_ingot


def _cancel(*rcs):
    for rc in rcs:
        for bag in rc.loot.values():
            if bag.expiry is not None:
                bag.expiry.cancel()


async def _rule_off():
    store = accounts.Store(DB0)
    real = (bosses.HOURS, combat.CORPSE_DELAY, combat.RESPAWN_DELAY)
    bosses.HOURS = ()
    out = {}
    try:
        for t, where in sorted(WHERE.items()):
            rc = combat.RoomCombat(_Room(where), store)
            mob = mobs.Mob(1, t, 10)
            rc.corpse_gone(mob, [])
            rows = [store.item(u) for u in rc.loot[mob.cell].uniqs] if mob.cell in rc.loot else []
            out[t] = (bosses.keeps_hours(t), len(rows) > 0,
                      sorted(r["type_id"] for r in rows if r["type_id"] in INGOTS))
            _cancel(rc)
        # Раид Кайс in his own room, killed and back on the delay five times
        # (the real five minutes stood in for by a twentieth of one).
        combat.CORPSE_DELAY = 0.05
        combat.RESPAWN_DELAY = 0.05
        room = rooms.Room(world.location(87), rooms.IdAllocator(), MT, 87)
        rc = combat.RoomCombat(room, store)
        kais = [m for m in rc.mobs.values() if m.type_id == 314][0]
        back = 0
        for _ in range(5):
            if kais.alive:
                back += 1
                rc.kill(kais, None)
            await asyncio.sleep(0.3)
        got = [store.item(u)["type_id"] for bag in rc.loot.values() for u in bag.uniqs]
        out["kais"] = (rc.bosses, back, len(got) > 0, [i for i in got if i in INGOTS])
        _cancel(rc)
    finally:
        bosses.HOURS, combat.CORPSE_DELAY, combat.RESPAWN_DELAY = real
        store.close()
    return out


def _run(coro, what):
    """A section run to its end, or what broke it as a failure: the code
    before this change has no boss_spot, and the suite says so rather than
    stopping at it."""
    try:
        return asyncio.run(coro)
    except Exception:
        import traceback
        fails.append(what + ":\n" + traceback.format_exc())
        return None


check("with the rule off, every boss's bag holds his loot and no ingot; Кайс killed and back"
      " on the delay five times leaves none",
      _run(_rule_off(), "the rule off"),
      dict({t: (False, True, []) for t in WHERE}, kais=([], 5, True, [])))


# A boss killed in his window is gone until the next one, and the game server
# writes that down (the boss_kills table): a restart inside the window -- a
# deploy, a crash -- makes the room afresh, and the boss starts away rather
# than standing there with his ingots a second time.
def _msk(h, m=0, s=0):
    return datetime(2026, 10, 9, h, m, s, tzinfo=bosses.ZONE).timestamp()


async def _restart():
    db = os.path.join(tempfile.mkdtemp(), "restart.db")
    now = [_msk(18, 0, 5)]
    real = (bosses.clock, combat.CORPSE_DELAY)
    bosses.clock = lambda: now[0]
    combat.CORPSE_DELAY = 0.05
    out = {}

    def room_87(store):
        room = rooms.Room(world.location(87), rooms.IdAllocator(), MT, 87)
        rc = combat.RoomCombat(room, store)
        return room, rc, [m for m in rc.mobs.values() if m.type_id == 314][0]

    try:
        store = accounts.Store(db)
        room, rc, kais = room_87(store)
        rc.keep_hours()
        out["stands at six"] = kais.eid in room.npcs
        rc.kill(kais, None)
        await asyncio.sleep(0.3)
        out["his bag"] = sorted(ingots_of(
            (store.item(u)["type_id"], store.item(u)["count"])
            for bag in rc.loot.values() for u in bag.uniqs).items())
        out["written down"] = store.boss_kills([rc.boss_spot(kais)]) == {
            rc.boss_spot(kais): _msk(18)}
        _cancel(rc)
        store.close()

        # The restart at half past six: a new process, the same database.
        now[0] = _msk(18, 30)
        store = accounts.Store(db)
        room, rc, kais = room_87(store)
        rc.keep_hours()
        out["after a restart in the window"] = (kais.eid in room.npcs, kais.away,
                                                rc.actor(kais.eid))
        now[0] = _msk(22, 0, 5)
        rc.keep_hours()
        out["at ten he comes"] = (kais.eid in room.npcs, kais.alive)
        store.close()

        # Another restart in the ten o'clock window, nobody having killed
        # him in it: he stands.
        store = accounts.Store(db)
        room, rc, kais = room_87(store)
        rc.keep_hours()
        out["a restart in a window he was not killed in"] = kais.eid in room.npcs
        store.close()
    finally:
        bosses.clock, combat.CORPSE_DELAY = real
    return out


check("a boss killed in his window stays away through a restart until the next one",
      _run(_restart(), "a restart in the window"),
      {"stands at six": True, "his bag": [(I5, 1)], "written down": True,
       "after a restart in the window": (False, True, None),
       "at ten he comes": (True, True),
       "a restart in a window he was not killed in": True})


# --- the ingots --------------------------------------------------------------------------
check("each ingot: its ounces in gold and at the one rate in afro, the article's weight,"
      " fifty to a stack, changing hands",
      [tuple((items.params_of(t) or {}).get(k) for k in ("cost", "g_cost", "weight", "max_count",
                                                          "exchang", "quest"))
       for t in INGOTS],
      [(n * RATE, n * OUNCE, n, 50, 1, 0) for n in (1, 5, 10)])
check("  ..by the original's names, every id in the launcher's table",
      [(names.ALL.get(items.STRING_ID_OFFSET + t), names.known(items.params_of(t)["name"]),
        names.known(items.params_of(t)["desc"])) for t in INGOTS],
      [("1 унция золота", True, True), ("5 унций золота", True, True),
       ("10 унций золота", True, True)])
check("  ..loot: a corpse may hold it, it is no gold thing, and it falls off a dead player",
      [(mobs.droppable(t), combat.gold_item(t), combat.drops_on_death(t)) for t in INGOTS],
      [(True, False, True)] * 3)

# --- Мортимер --------------------------------------------------------------------------
check("Мортимер sells the three ingots, 1, 5 and 10, and no other stall sells one",
      (items.stock_for(MORTIMER),
       sorted(t for t, (root, _n, _a) in MT.items()
              if root == world.TRADER and set(items.stock_for(t)) & set(INGOTS))),
      ([I1, I5, I10], [MORTIMER]))
check("  ..at face value in gold, as the stall charges (inventory.buy_price)",
      [inventory.buy_price(items.params_of(t), items.root_of(t), 1, True) for t in INGOTS],
      [100, 500, 1000])
check("he stands on the black market by a row of data/placements.json, on his cell",
      [(r["type"], tuple(r["cell"])) for r in world.placed_in(BLACK_MARKET)],
      [(MORTIMER, MORTIMER_CELL)])
check("  ..which can stand (rooms.placement_problems)", rooms.placement_problems(MT), [])
there = {}
for loc_id in (BLACK_MARKET, QUARTER):
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)
    loc = room.loc
    there[loc_id] = sorted((n.cell % loc.width, n.cell // loc.width)
                           for n in room.npcs.values() if n.type_id == MORTIMER)
check("  ..one Мортимер there, one still in the жилой квартал",
      (there[BLACK_MARKET], len(there[QUARTER])), ([MORTIMER_CELL], 1))
check("  ..a trader by a name the client has, at peace there",
      (MT[MORTIMER][0], names.known(MORTIMER), world.location(BLACK_MARKET).war),
      (world.TRADER, True, 0))
check("his service quests are his wherever he stands: cashing and change",
      quests.given_by(MORTIMER), [301, 302, 303, 304, 305, 306, 307])

# --- buying and cashing never makes gold --------------------------------------------------
price = {t: inventory.buy_price(items.params_of(t), items.root_of(t), 1, True) for t in INGOTS}
worth = dict(items.GOLD_INGOTS)
taking = [q for _t, q in sorted(quests.QUESTS.items())
          if q.wants() and all(o in INGOTS for o, _n in q.wants())]
gains = {}
for q in taking:
    cost = sum(price[o] * n for o, n in q.wants())
    paid = q.rew_gold + sum(worth.get(o, 0) * n for o, n in zip(q.rew_obj, q.num_rew_obj)) \
        + q.rew_afro * OUNCE // RATE
    gains[q.type] = paid - cost
check("every quest that takes ingots: Мортимер's seven and Джеррах's",
      sorted(gains), [10, 301, 302, 303, 304, 305, 306, 307])
check("  ..pays no more than the stall asks for them: cashing 0.05 less, change and"
      " Джеррах's even",
      gains, {10: 0, 301: -5, 302: -5, 303: -5, 304: 0, 305: 0, 306: 0, 307: 0})
check("  ..cashing pays the ounces less 0.05 on the account",
      [quests.get(CASH[t]).rew_gold for t in INGOTS], [95, 495, 995])
check("a trader pays for an ingot less afro than c_ga gives for its ounces",
      [math.floor(items.params_of(t)["cost"] * inventory.SMOD) < worth[t] * RATE // OUNCE
       for t in INGOTS], [True] * 3)


# --- the server ----------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "ingots.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("assayer", "secret")
_store.close()
CRED = accounts.credential("assayer", "secret")
# Five seconds past six on the Moscow clock: the bosses are in for the hour.
CLOCK = datetime(2026, 10, 9, 18, 0, 5)
MARKET_CELL = world.cell_of(BLACK_MARKET)
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX=str(MARKET_CELL[0]), LAVA_GY=str(MARKET_CELL[1]),
           LAVA_AP_REGEN="25", LAVA_RESPAWN="600", LAVA_SEED="9", LAVA_POLICY_PORT="0",
           LAVA_BOSS_CLOCK=CLOCK.isoformat())
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


def connect(timeout=None):
    return testkit.connect(PORT, srv, LOG, timeout)


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
    """Pieces of a type in the character's bag, as the database has them."""
    probe = accounts.Store(DB)
    try:
        return sum(r["count"] for r in probe.items_of(char_id)
                   if r["type_id"] == type_id and r["slot"] == inventory.BAG)
    finally:
        probe.close()


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


def buy(c, index, code):
    c.send("ss_upd;s_status=%d;obj=x%x;param=1;" % (code, index))
    return c.frames(0.8)


CHAR = None
try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@assayer@;")
    c.frames()
    probe = accounts.Store(DB)
    CHAR = probe.db.execute("SELECT id FROM characters WHERE name = ?",
                            ("assayer",)).fetchone()["id"]
    probe.close()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    arrival, pos = enter(c)

    # --- Мортимер on the black market ------------------------------------------------------
    check("the black market: the room the player stands in",
          [p["id"] for p in named(c.seen, "lcall")][-1:], [BLACK_MARKET])
    mort = npc(arrival, MORTIMER)
    check("Мортимер is there: a stall of the three ingots, his cashing and change on offer",
          (mort.get("can_trade"), mort.get("type_list"), mort.get("give_quests")),
          (1, [I1, I5, I10], [301, 302, 303, 304, 305, 306, 307]))
    check("  ..every inhabitant by a name the client has (an unknown one is the login screen)",
          [p["name"] for n, p in arrival if n.startswith("userInfo_") and n != "userInfo_Player"
           and not names.known(p["name"])], [])
    c.send("ss_get_si;type=%d;" % I10)
    told = named(c.frames(), "ss_si_simple_obj")
    check("the client is told the ingot of ten: 10 G and its afro, 10 g",
          [(p["cost"], p["g_cost"], p["weight"]) for p in told if p.get("type") == I10],
          [(10 * RATE, 10 * OUNCE, 10)])

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

    # --- Асмунд, in his place at six ---------------------------------------------------------
    where_82 = BOSSES[ASMUND][1]
    arrival, pos = goto(c, where_82)
    place = world.location(where_82)
    infos = {p["id"]: p["name"] for p in named(arrival, "userInfo")}
    placed = {p["newUser"]: p["pos"] for p in named(arrival, "lch")
              if "newUser" in p and p["newUser"] in infos}
    boss_ids = [i for i, t in infos.items() if t == ASMUND]
    check("at six Асмунд is in his place", len(boss_ids), 1)
    dead = None
    if boss_ids:
        boss = boss_ids[0]
        home = placed[boss]
        others = [cell for i, cell in placed.items() if i != boss]
        reach = mobs.stats(ASMUND).aggro
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
        for attempt in range(40):
            c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(boss)))
            got = c.until(lambda f: f[0] == "ss_di_firearm"
                          or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.3)
            if [p for p in named(got, "lch") if p.get("dead") == boss]:
                dead = got
                break
            time.sleep(0.5)
    check("Асмунд falls", dead is not None, True)
    got = list(dead or [])
    if not named(got, "ss_loot"):
        got += c.until(lambda f: f[0] == "ss_loot", 5)
    where = [p["hex"][0] for p in named(got, "ss_loot") if p.get("s_status") == 1]
    check("his bag lies where he fell", len(where), 1)
    if where and boss_ids:
        placed_now = dict(placed)
        for n, p in c.seen:
            if n == "userMove" and p.get("id") in placed_now:
                placed_now[p["id"]] = p["path"][-1]
        wary_cells = {cell for cell in range(place.width * place.height)
                      if any(mobs.hex_distance(cell, o, place.width) <= wary
                             for i, o in placed_now.items() if i != boss_ids[0])}
        path = mobs.find_path(place, pos, lambda cell: cell == where[0]
                              or progression.within_reach(cell, where[0], place.width,
                                                          place.height), wary_cells)
        check("the bag is a walk away", path is not None, True)
        c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path or [pos]))
        c.frames(0.2 * len(path or [pos]) + 1.0)
        c.send("ss_create;s_type=0;target=%d;" % where[0])
        check("the bag opens", acks(c.frames()), [0])
        c.send("ss_get;slot=24;")
        lst = [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]
        oids = [inventory.parse_oid(o) for o in lst[lst.index("0") + 1:]]
        probe = accounts.Store(DB)
        stacks = sorted((t, probe.item(u)["count"]) for u, t, _r in oids if t in INGOTS)
        probe.close()
        print("  ..  Асмунд left %s" % sorted(t for _u, t, _r in oids))
        check("in it: one ingot of an ounce", stacks, [(I1, 1)])
        c.send("ss_upd;s_status=3;obj=x0;param=1;")
        check("taken whole, one ack", acks(c.frames(0.8))[:1], [0])
        c.send("ss_upd;s_status=0;obj=x0;param=1;")
        c.frames(0.3)
    check("one ounce in the bag", bag_of(CHAR, I1), 1)

    # --- at Мортимер's stall -----------------------------------------------------------------
    arrival, pos = goto(c, BLACK_MARKET)
    mid = npc(arrival, MORTIMER).get("id", 0)
    c.send("ss_create;s_type=1;target=%d;" % mid)
    check("his stall opens", acks(c.frames()), [0])
    purse0 = money(CHAR)
    check("a newcomer has no gold", purse0[1], 0)
    got = buy(c, 2, inventory.UPD_BUY_GOLD)
    check("no gold: the ingot of ten refused, one ack, nothing moves",
          (acks(got), money(CHAR), bag_of(CHAR, I10)), ([NO_MONEY], purse0, 0))
    chat(c, "/money %d 0" % (20 * RATE))
    purse1 = money(CHAR)
    got = buy(c, 1, inventory.UPD_BUY)
    check("for afro, with afro enough: refused, one ack, nothing moves -- afro buys no gold",
          (acks(got), money(CHAR), bag_of(CHAR, I5)), ([REFUSED], purse1, 0))
    chat(c, "/money 0 %d" % (16 * OUNCE + 50))
    afro2, gold2 = money(CHAR)
    paid = []
    for index, t in enumerate(INGOTS):
        before = money(CHAR)[1]
        got = buy(c, index, inventory.UPD_BUY_GOLD)
        paid.append((t, acks(got), before - money(CHAR)[1], bag_of(CHAR, t),
                     [n for n, _p in got if n in ("cmdAck", "ss_obj_status", "userInfo_Player")]))
    check("for gold: each ingot at its face value, one ack, then the thing and the purse",
          paid, [(I1, [0], 100, 2, ["cmdAck", "ss_obj_status", "userInfo_Player"]),
                 (I5, [0], 500, 1, ["cmdAck", "ss_obj_status", "userInfo_Player"]),
                 (I10, [0], 1000, 1, ["cmdAck", "ss_obj_status", "userInfo_Player"])])
    check("  ..and the afro is untouched, 0.50 ounces left", money(CHAR), (afro2, 50))
    c.send("ss_upd;s_status=0;obj=x0;")
    c.frames(0.3)

    # --- cashed at Мортимер's, on the black market ----------------------------------------------
    cashed = []
    for t in (I1, I10):
        before = money(CHAR)
        c.send("q_st;mob=%d;q_idx=%d;" % (mid, quests.given_by(MORTIMER).index(CASH[t])))
        got = c.frames(0.8)
        q_id = [p["q_id"] for n, p in got if n.startswith("q_di_")][:1]
        c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (mid, (q_id or [0])[0]))
        got = c.frames(0.8)
        after = money(CHAR)
        cashed.append((t, acks(got), after[1] - before[1], after[0] - before[0]))
    check("cashing an ounce and ten: one ack each, 0.95 and 9.95 on the account, no afro",
          cashed, [(I1, [0], 95, 0), (I10, [0], 995, 0)])
    check("  ..the ingots gone from the bag: an ounce and the five left",
          [bag_of(CHAR, t) for t in INGOTS], [1, 1, 0])
    # The five is still in the bag, bought for 500: the ounce and the ten,
    # bought and cashed, are the rest of the change of the purse.
    check("bought and cashed, the ounce and the ten gave 0.10 less than they cost",
          money(CHAR)[1] - gold2 + 500, -10)

    # --- the ledger ---------------------------------------------------------------------
    rows = [(r["source"], r["ref"], r["afro"], r["gold"]) for r in ledger(CHAR)]
    check("the ledger: each purchase under shop_buy and its type, each cashing under quest"
          " and its type, the gold signed",
          [r for r in rows if r[0] in ("shop_buy", "quest")],
          [("shop_buy", I1, 0, -100), ("shop_buy", I5, 0, -500), ("shop_buy", I10, 0, -1000),
           ("quest", 301, 0, 95), ("quest", 303, 0, 995)])
    check("  ..and no row for the refusals: the ledger holds what the purse holds",
          (sum(r[2] for r in rows), sum(r[3] for r in rows)), money(CHAR))

    # --- the жилой квартал ---------------------------------------------------------------
    arrival, pos = goto(c, QUARTER)
    check("Мортимер still in the жилой квартал, with the same stall",
          npc(arrival, MORTIMER).get("type_list"), [I1, I5, I10])
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
        story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-50:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa ingots OK")
