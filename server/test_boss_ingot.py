"""The Nubian valley boss's gold ingot, and Джеррах's «Обмен слитка».

The owner's decisions of 2026-09-25: «давай чтобы у босса в нубийке выпадал
слиток золото и сделай квест, чтобы его можно было сдать и получить на
баланс», the ingot «и слиток в 5 голд», the giver «давай чтобы квест был у
Джерраха».

The boss is [5] Лидер Ян Дуглас, Новые колонисты (2103, texts.xml 50270),
in the Лагерь бандитов (location 34) and nowhere else (the valley's other
boss, Большой Мвамба in his camp 31, carries no ingot), and he keeps the
boss hours (bosses.py: 18:00 and 20:00). On every kill
his bag holds one ingot of 5 ounces of gold, 4796 New_Gold_Ingot_5: a row of
data/loot_manual.json at chance 1.0, which mobs.roll_table puts in without a
die and outside the two a kill's rolls may keep (mobs.SURE, MAX_DROPS), so
neither the cap nor the order of the rows can push it out. The ingot is a
proper item: the original's name and description (texts.xml 7638/7639,
data/build_orig_items.py rule 7d, which names the 1- and 10-ounce ones too),
the article's 5 g, an afro price of the article's 5 G at the game's one
rate (progression.GOLD_TO_AFRO_RATE, items.GOLD_INGOTS) -- of which a trader
pays 70 per cent, so the quest's 5 ounces are always the better deal. It changes hands, and it falls off a dead player like any loot
(«любой лут должен падать»): gold is what it is made of, not what it was
bought for (combat.gold_item).

Джеррах ал-Хакам, Староста поселка (5206) in the Западный поселок (183),
gives «Обмен слитка» (quest 10) and takes it back: one ingot, counted in the
bag, taken at the hand-in for exactly 5 ounces of gold (rew_gold 500 in
hundredths), repeatable, journalled, against the daily limit.

In process: the table and the certainty (a seeded generator, and a table
built to push the ingot out), nobody else rolling for it, where the boss
stands, the item's frame, names and ids in the exported table, the death
rule with the backpack's chance forced to 100, the trader's price, the quest
row and its texts, and a hundred corpses' bags through RoomCombat with a
real database. On a socket, the server's clock started just after six in
the evening (LAVA_BOSS_CLOCK): the quest taken at Джеррах and refused
without an ingot; the boss met in his camp, shot, his bag opened and the
ingot taken -- the journal counts it; handed in at Джеррах for 5 ounces in
the frame and in the database, the ingot gone; again with a second ingot;
and a third sold at his stall for 70 per cent of its price.

Written against the code before the change it fails from the first table on
-- no ingot in the boss's table, the ingot "New_Gold_Ingot_5" at 10 afro and
150 g, a gold thing that never falls, no quest 10 -- and on the socket at
Джеррах, who gives nothing.

    LAVA_RES=.../lava/res python3 server/test_boss_ingot.py
"""
import asyncio
import json
import math
import os
import random
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
# The owner's numbers are what the in-process part checks; the server below
# gets its own environment.
for _k in ("LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ", "LAVA_BOSS_CLOCK",
           "LAVA_WEAR_DROP", "LAVA_BAG_DROP", "LAVA_PASSAGES"):
    os.environ.pop(_k, None)

sys.path.insert(0, HERE)
import accounts      # noqa: E402
import barter        # noqa: E402
import bosses        # noqa: E402
import combat        # noqa: E402
import inventory     # noqa: E402
import items         # noqa: E402
import mobs          # noqa: E402
import names         # noqa: E402
import progression   # noqa: E402
import quests        # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

INGOT, INGOT_1, INGOT_10 = 4796, 7620, 4797     # New_Gold_Ingot_5 / _1 / _10
OLD_INGOTS = (3562, 3563)                        # Gold_Ingot_5 / _10: a lollipop's icon
BOSS = 2103                                      # m05_nc_Leader_lvl5
CAMP, WEST = 34, 183                             # Лагерь бандитов, Западный поселок
CAMP_CELL, WEST_CELL = (6272, 1840), (6262, 1825)
JERRAKH = 5206
QUEST = 10
ADMIN_GUN, ROUNDS = 1534, 6092
OUNCE = 100                         # gold travels in hundredths (progression.GOLD_OUNCE)
REWARD = 5 * OUNCE
# afro: the article's 5 G at the one rate (20 000 at the default 4000), and
# what a trader pays for it (Inventory.sell: cost x SMOD, floored)
PRICE = REWARD * progression.GOLD_TO_AFRO_RATE // OUNCE
SOLD = int(math.floor(PRICE * inventory.SMOD))
NOT_READY = 3                       # server.RES_NOT_READY
DAILY_MAX = 10                      # server.DAILY_MAX

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


# Read through getattr: on the code before this change they do not exist,
# and the suite has to say what is missing rather than stop at it.
SURE = getattr(mobs, "SURE", None)
loot_manual = getattr(items, "loot_manual", lambda: {})

# --- the boss and his table ---------------------------------------------------------
check("2103 is a boss and keeps the boss hours",
      (world.creature_role(BOSS), bosses.keeps_hours(BOSS)), ("boss", True))
check("the certain row's chance is 1.0", SURE, 1.0)
table = mobs.loot_table(BOSS)
check("the boss rolls for the ingot at 1.0 first, then for his level's valuable, then the"
      " camp's old chip (the owner's 5%, 2026-09-26)",
      table, [(INGOT, 1.0, True),
              (mobs.level_piece(mobs.VALUABLE_SERIES, mobs.stats(BOSS).level), 0.06, True),
              (3179, 0.05, False)])

N = 2000
rng = random.Random(20260925)
rolls = [mobs.roll_table(BOSS, rng) for _ in range(N)]
check("seeded, %d kills: the ingot in every one, once" % N,
      sorted({sum(1 for t, _n in r if t == INGOT) for r in rolls}), [1])
check("and the rolled rows keep their own two besides",
      max(sum(1 for t, _n in r if t != INGOT) for r in rolls) <= mobs.MAX_DROPS, True)

# A table the wiki might give the boss one day: two valuables that nearly
# always come up, and both with lower type ids than the ingot, so they roll
# before it. Under the cap of two they would take both places every time.
_saved = mobs._TABLES.get(BOSS)
try:
    mobs._TABLES[BOSS] = [(100, 0.999, True), (200, 0.999, True), (INGOT, 1.0, True),
                          (300, 0.999, False)]
    rng = random.Random(7)
    pushed = [mobs.roll_table(BOSS, rng) for _ in range(500)]
    check("no cap and no order of the rows pushes the ingot out",
          (all(any(t == INGOT for t, _n in r) for r in pushed),
           max(sum(1 for t, _n in r if t != INGOT) for r in pushed)),
          (True, mobs.MAX_DROPS))
finally:
    if _saved is None:
        mobs._TABLES.pop(BOSS, None)
    else:
        mobs._TABLES[BOSS] = _saved

check("nobody else rolls for any gold ingot",
      sorted(int(t) for t in mobs.TYPES if int(t) != BOSS
             and {r[0] for r in mobs.loot_table(int(t))} & {INGOT, INGOT_1, INGOT_10}), [])

# Where he stands: location 34 and no other file, no stand-in for a missing
# creature; and of the valley's settlements his camp is one of the two with
# a boss at all (the other, since the third batch of the valley's quests,
# is Большой Мвамба's, below).
where = set()
for name in sorted(os.listdir(os.path.join(world.RES, "locations", "static"))):
    if not name.endswith(".xml"):
        continue
    loc_id = int(name[:-4])
    try:
        spawns = world.location(loc_id).spawns
    except Exception:           # noqa: BLE001 -- a file the server cannot open is no room
        continue
    if any(t == BOSS or world.substitute(t) == BOSS for _c, t in spawns):
        where.add(loc_id)
check("the boss stands in the Лагерь бандитов and nowhere else", where, {CAMP})
check("which is the valley's camp at 6272,1840", world.settlements().get(CAMP_CELL), CAMP)
x0, y0, x1, y1 = world.NOOB_VALLEY
mob_types = world.mob_types()
valley_bosses = set()
for (gx, gy), loc_id in world.settlements().items():
    if not (x0 <= gx <= x1 and y0 <= gy <= y1):
        continue
    loc = world.location(loc_id)
    for _c, t in loc.spawns:
        if t not in mob_types or not names.known(t):
            t = world.substitute(t) if loc.war else None
        if t is not None and world.creature_role(t) == "boss":
            valley_bosses.add((loc_id, t))
# The one other boss of the Nubian files, nubia_boss (1406), Большой Мвамба,
# stands in the quest place Q_IV_pustina3 (31), which the valley's third
# batch of quests put on its own cell, «Лагерь Большого Мвамбы» 6274,1833
# (data/settlements_verified.json), for Шульц's «Экипировка к пистолету»
# (test_valley_market): the valley has two bosses now, and the ingot is the
# leader's alone.
MVAMBA = 1406
check("and the Nubian valley's bosses: the leader in his camp, Большой Мвамба in his",
      valley_bosses, {(CAMP, BOSS), (31, MVAMBA)})
with open(os.path.join(os.path.dirname(HERE), "data", "exits.json"), encoding="utf-8") as _fh:
    _doors = json.load(_fh)["doors"]
check("the Nubian files' other boss stands in his camp on its own cell, no door into it",
      (world.location(31).fn, sorted({t for _c, t in world.location(31).spawns
                                      if world.creature_role(t) == "boss"}),
       world.cell_of(31), sorted(k for k, v in _doors.items()
                                 for d in v["doors"] if d.get("target_loc_id") == 31)),
      ("Q_IV_pustina3", [MVAMBA], (6274, 1833), []))
check("  ..and carries no ingot, ordinary or for a quest",
      [t for t, *_r in mobs.loot_table(MVAMBA) + mobs.quest_table(MVAMBA) if t == INGOT], [])

# --- the ingot ----------------------------------------------------------------------
si = items.params_of(INGOT) or {}
check("the ingot: its 5 G in afro, nothing in gold, the article's 5 g, fifty to a stack",
      (si.get("cost"), si.get("g_cost"), si.get("weight"), si.get("max_count")),
      (PRICE, 0, 5, 50))
check("it changes hands: exchangeable, no quest's own, not premium",
      (si.get("exchang"), si.get("quest"), items.premium(INGOT), barter.tradable(INGOT)),
      (1, 0, False, True))
check("by the original's name and description, not the internal one",
      (names.ALL.get(si.get("name")), names.ALL.get(si.get("desc"))),
      ("5 унций золота", "Слиток номиналом в пять золотых унций."))
check("and so are its 1- and 10-ounce siblings named",
      [names.ALL.get(items.STRING_ID_OFFSET + t) for t in (INGOT_1, INGOT_10)],
      ["1 унция золота", "10 унций золота"])
check("with their descriptions under their ids",
      [names.ALL.get(items.DESC_ID_OFFSET + t) for t in (INGOT_1, INGOT_10)],
      ["Слиток номиналом в одну золотую унцию.", "Слиток номиналом в десять золотых унций."])
check("  ..which their frames point at, so the tooltip shows them",
      [items.static_info(t)[1].get("desc") for t in (INGOT_1, INGOT_10)],
      [items.DESC_ID_OFFSET + t for t in (INGOT_1, INGOT_10)])
check("the older Gold_Ingot_5/_10 take none of those rows",
      ["унци" in names.ALL.get(items.STRING_ID_OFFSET + t, "") for t in OLD_INGOTS],
      [False, False])
blob = names.document_bytes()
ids = [si.get("name"), si.get("desc")] + [off + t for t in (INGOT_1, INGOT_10)
                                          for off in (items.STRING_ID_OFFSET, items.DESC_ID_OFFSET)]
check("every id of theirs is in the table the launcher is handed",
      [bool(i) and names.known(i) and ("<s id='%d'>" % i).encode() in blob for i in ids],
      [True] * 6)
check("the frame keeps its shape: the designed one's keys, a simple object",
      (items.static_info(INGOT)[0],
       sorted(items.static_info(INGOT)[1]) == sorted(items.designed_info(INGOT)[1])),
      ("ss_si_simple_obj", True))
check("a corpse may hold it", mobs.droppable(INGOT), True)

# --- it is loot, and loot falls ---------------------------------------------------------
check("gold in its name, afro in its price: not one of the gold things",
      combat.gold_item(INGOT), False)
check("so a dead player may lose it", combat.drops_on_death(INGOT), True)


def row_of(uniq, type_id, slot, count=1):
    f = inventory.new_fields(type_id, count)
    f.update(uniq=uniq, type_id=type_id, slot=slot, char_id=1)
    for k in accounts.ITEM_FIELDS:
        f.setdefault(k, 0)
    return f


_chance = combat.BAG_DROP_CHANCE
try:
    combat.BAG_DROP_CHANCE = 100
    body = [row_of(1, INGOT, inventory.BAG), row_of(2, INGOT, inventory.BAG, 3),
            row_of(3, INGOT, inventory.BANK)]
    check("the backpack's chance forced to 100: one ingot falls whole, a stack of three "
          "loses a third, the bank keeps its own",
          [(r["uniq"], n) for r, n in combat.death_losses(body, (), random.Random(1))],
          [(1, 1), (2, 1)])
finally:
    combat.BAG_DROP_CHANCE = _chance

# --- what a trader pays ---------------------------------------------------------------
paid = max(1, int(math.floor(si.get("cost", 0) / float(si.get("sell_num", 1) or 1)
                             * inventory.SMOD * si.get("sell_mod", 1))))
check("a trader pays 70 per cent of it (Inventory.sell), less than the quest's "
      "5 ounces at the game's rate", (paid, paid < REWARD * progression.GOLD_TO_AFRO_RATE // OUNCE),
      (SOLD, True))
check("and no stall sells it -- sold for afro it would turn afro into gold",
      sorted(t for t, (root, _n, _a) in world.mob_types().items()
             if root == world.TRADER and INGOT in items.stock_for(t)), [])

# --- the quest ------------------------------------------------------------------------
q = quests.get(QUEST)
check("quest 10 is «Обмен слитка»", q.name if q else None, "Обмен слитка")
if q:
    # His valley tutorial quests (11-27) come after it in the table, so it
    # stays the first he gives, q_idx 0.
    check("Джеррах gives it and takes it back, and nobody else; it is the first he gives",
          (q.give, q.take, quests.given_by(JERRAKH)[0]), ([JERRAKH], [JERRAKH], QUEST))
    check("one ingot of 5 ounces, which the boss drops; exactly 5 ounces of gold, "
          "again and again, for anybody",
          (q.kind, q.objs, q.rew_gold, q.rew_afro, q.rew_obj, q.repeatable, q.level, q.rew_loc),
          (quests.BRING_L_OBJ, [(INGOT, 1, [BOSS])], REWARD, 0, [], 1, 0, 0))
    check("its marks on the map: the camp to go to, Джеррах to hand it in to",
          (q.loc, q.finish_loc), (world.pack(*CAMP_CELL), world.pack(*WEST_CELL)))
    check("four texts of its own, every id in the launcher's table",
          ([bool(t) for t in q.texts], [names.known(s) and ("<s id='%d'>" % s).encode() in blob
                                        for s in q.string_ids()]),
          ([True] * 4, [True] * 4))
    check("and the boss's name the journal shows is one the table has", names.known(BOSS), True)
    hours = ["%d:%02d" % divmod(m, 60) for m in bosses.parse_hours(bosses.DEFAULT_HOURS)]
    check("the hint names the boss hours as bosses.py keeps them",
          ([h in q.texts[quests.START] for h in hours], bosses.DEFAULT_STAY,
           "ждёт там час" in q.texts[quests.START]),
          ([True] * len(hours), 60.0, True))
    check("the texts talk of the ingot as the client names it",
          ["«5 унций золота»" in t for t in q.texts[1:3]], [True, True])
    check("and the macros are the client's own",
          sorted(set(re.findall(r"%[^%]*%", "".join(q.texts)))), ["%sex?:а%", "%имя%"])


# --- a corpse's bag, through RoomCombat and a real database -----------------------
class _Room(object):
    def __init__(self):
        self.loc = world.location(CAMP)
        self.npcs = {}
        self.players = {}
        self.ws = False

    def broadcast(self, frame, exclude=None):
        pass


DB0 = os.path.join(tempfile.mkdtemp(), "bags.db")
accounts.DB_PATH = DB0


async def _bags(kills):
    store = accounts.Store(DB0)
    rc = combat.RoomCombat(_Room(), store)
    combat.RNG.seed(25)
    per_bag = []
    for i in range(kills):
        mob = mobs.Mob(i + 1, BOSS, 10 + 3 * i)
        rc.corpse_gone(mob, [])
        n = 0
        for uniq in rc.loot[mob.cell].uniqs:
            row = store.item(uniq)
            if row["type_id"] == INGOT:
                if row["root"] != items.TRASH:
                    fails.append("bag row %r has the wrong root" % row)
                n += row["count"]
        per_bag.append(n)
    for bag in rc.loot.values():
        if bag.expiry is not None:
            bag.expiry.cancel()
    store.close()
    return per_bag


KILLS = 100
check("%d bosses killed leave %d bags, one ingot in each" % (KILLS, KILLS),
      sorted(set(asyncio.run(_bags(KILLS)))), [1])


# --- the server ------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "ingot.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("goldsmith", "secret")
_store.close()
CRED = accounts.credential("goldsmith", "secret")

# Five seconds past six on the Moscow clock, the owner's hours and stay: the
# boss is in his camp for the hour the test takes a couple of minutes of.
CLOCK = datetime(2026, 9, 24, 18, 0, 5)
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX=str(WEST_CELL[0]), LAVA_GY=str(WEST_CELL[1]),
           LAVA_AP_REGEN="25", LAVA_RESPAWN="600", LAVA_SEED="7",
           LAVA_BOSS_CLOCK=CLOCK.isoformat())
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


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


def counts(frames):
    """The q_di_bring_l_obj of the quest among the frames: (obj_num, complete) each."""
    return [(p["obj_num"], p["complete"]) for p in named(frames, "q_di_bring_l_obj")]


# What the server says to the player about his own things and purse, without
# the room around him.
OWN = ("cmdAck", "lcall", "ss_obj_status", "ss_di_heap", "userInfo_Player")


def answer(frames):
    return [n for n, _ in frames if n in OWN or n.startswith("q_")]


def give(c, type_id, n=1):
    """/give (test runs only): the thing lands in the bag, the server says
    so in chat, and a quest counting the bag is told after. Returns the
    frames and the new thing's oid."""
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.until(lambda f: f[0] == "userMsg") + c.frames(0.4)
    new = named(got, "ss_obj_status")
    return got, (str(new[0]["obj"]) if new else None)


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
        return probe.money(char_id)
    finally:
        probe.close()


def hand_in(c, jid, q_id):
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (jid, q_id))
    return c.frames(0.8)


CHAR = None
try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@goldsmith@;")
    c.frames()
    probe = accounts.Store(DB)
    CHAR = probe.db.execute("SELECT id FROM characters WHERE name = ?",
                            ("goldsmith",)).fetchone()["id"]
    probe.close()
    AFRO0, GOLD0 = money(CHAR)
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    arrival, pos = enter(c)

    # --- Джеррах gives the quest -----------------------------------------------------
    jerrakh = npc(arrival, JERRAKH)
    check("Джеррах stands in the Западный поселок", bool(jerrakh), True)
    check("he gives «Обмен слитка» first and takes it back, and keeps his services: "
          "a stall, repairs, no residence",
          [(jerrakh.get("give_quests") or [None])[0], QUEST in (jerrakh.get("take_quests") or [])]
          + [jerrakh.get(k) for k in ("can_trade", "can_repair", "can_set_home",
                                      "can_banking")],
          [QUEST, True, 1, 1, 0, 0])
    jid = jerrakh.get("id", 0)
    c.send("q_status;q_type=%d;" % QUEST)
    check("it is on offer, under its name",
          [(p["type"], p["status"], p["name"]) for p in named(c.frames(), "q_status")],
          [(QUEST, 1, quests.STRING_BASE + quests.STRINGS_PER_QUEST * QUEST + quests.NAME)])
    c.send("q_si;q_type=%d;" % QUEST)
    si_frames = named(c.frames(), "q_si_bring_l_obj")
    check("it asks for one ingot of 5 ounces off the boss and pays 5 ounces of gold, "
          "again and again",
          [(p["obj_1"], p["obj_num_1"], p["mobs_1"], p["obj_2"], p["rew_gold"], p["rew_afro"],
            p["rew_obj"], p["repeatable"], p["rew_loc"]) for p in si_frames],
          [(INGOT, 1, [BOSS], 0, REWARD, 0, [], 1, 0)])
    check("  ..which the client shows as 5 унций (rew_gold / 100)",
          [p["rew_gold"] / 100.0 for p in si_frames], [5.0])

    c.send("q_st;mob=%d;q_idx=0;" % jid)
    got = c.frames(0.8)
    check("taking it: the ack, then the quest in the journal at nought of one",
          ([(n, p.get("res")) for n, p in got if n in ("cmdAck", "lcall")], counts(got)),
          ([("cmdAck", 0)], [([0], 0)]))
    Q = named(got, "q_di_bring_l_obj")[0]["q_id"] if named(got, "q_di_bring_l_obj") else 0
    got = hand_in(c, jid, Q)
    check("handed in without an ingot: refused, nothing paid",
          (answer(got), [p["res"] for p in named(got, "cmdAck")], money(CHAR)),
          (["cmdAck"], [NOT_READY], (AFRO0, GOLD0)))

    # --- the admin gun, loaded ---------------------------------------------------------
    gun = rounds = None
    for label, cmd in (("gun", "/give %d" % ADMIN_GUN), ("rounds", "/give %d 50" % ROUNDS)):
        c.send("userMsg;entry=@%s@;group=0;" % cmd)
        got = c.until(lambda f: f[0] == "userMsg")
        oid = str(named(got, "ss_obj_status")[0]["obj"])
        if label == "gun":
            gun = oid
        else:
            rounds = oid
    c.send("ss_get;target=0;slot=11;")
    held = [str(x) for x in c.frames()[0][1]["o_list"]]
    if held[6] != "0":
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % gun)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
    c.until(lambda f: f[0] == "ss_di_firearm")

    # --- the boss, in his camp at six ---------------------------------------------------
    arrival, pos = goto(c, CAMP)
    camp = world.location(CAMP)
    infos = {p["id"]: p["name"] for p in named(arrival, "userInfo")}
    placed = {p["newUser"]: p["pos"] for p in named(arrival, "lch")
              if "newUser" in p and p["newUser"] in infos}
    boss_ids = [i for i, t in infos.items() if t == BOSS]
    check("at six the boss is in the Лагерь бандитов", len(boss_ids), 1)
    dead = None
    if boss_ids:
        boss = boss_ids[0]
        home = placed[boss]
        others = [cell for i, cell in placed.items() if i != boss]
        reach = mobs.stats(BOSS).aggro
        wary = max(mobs.stats(infos[i]).aggro for i in placed if i != boss) + 0.5
        # Out of his reach and everybody else's, with a clear line to him:
        # the admin gun's one shot is the whole fight.
        spots = sorted((mobs.hex_distance(cell, home, camp.width), cell)
                       for cell in range(camp.width * camp.height)
                       if cell not in camp.obstacles and cell not in placed.values()
                       and reach + 0.5 < mobs.hex_distance(cell, home, camp.width) <= 12
                       and mobs.line_of_fire(camp, cell, home) is None
                       and all(mobs.hex_distance(cell, o, camp.width) > wary for o in others))
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
    check("the boss falls", dead is not None, True)
    got = list(dead or [])
    if not named(got, "ss_loot"):
        got += c.until(lambda f: f[0] == "ss_loot", 5)
    where = [p["hex"][0] for p in named(got, "ss_loot") if p.get("s_status") == 1]
    check("his bag lies where he fell", len(where), 1)
    if where:
        placed_now = dict(placed)
        for n, p in c.seen:
            if n == "userMove" and p.get("id") in placed_now:
                placed_now[p["id"]] = p["path"][-1]
        wary_cells = {cell for cell in range(camp.width * camp.height)
                      if any(mobs.hex_distance(cell, o, camp.width) <= wary
                             for i, o in placed_now.items() if i != boss_ids[0])}
        path = mobs.find_path(camp, pos, lambda cell: cell == where[0]
                              or progression.within_reach(cell, where[0], camp.width,
                                                          camp.height), wary_cells)
        check("the bag is a walk away", path is not None, True)
        c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path or [pos]))
        c.frames(0.2 * len(path or [pos]) + 1.0)
        c.send("ss_create;s_type=0;target=%d;" % where[0])
        check("the bag opens", [p["res"] for p in named(c.frames(), "cmdAck")], [0])
        c.send("ss_get;slot=24;")
        lst = [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]
        loot = [inventory.parse_oid(o)[1] for o in lst[lst.index("0") + 1:]]
        print("  ..  the boss left %s" % sorted(loot))
        check("in it: one ingot of 5 ounces of gold", loot.count(INGOT), 1)
        c.send("ss_upd;s_status=3;obj=x0;param=1;")
        got = c.frames(0.8)
        check("taken whole: the ack first, and the journal counts the ingot, complete",
              ([p["res"] for p in named(got, "cmdAck")][:1], counts(got)), ([0], [([1], 1)]))
        c.send("ss_upd;s_status=0;obj=x0;param=1;")
        c.frames(0.3)
    check("the ingot is in the bag", bag_of(CHAR, INGOT), 1)
    c.send("ss_get_si;type=%d;" % INGOT)
    frame = named(c.frames(), "ss_si_simple_obj")
    check("the client is told its original name and description, its price and 5 g",
          [(names.ALL.get(p["name"]), names.ALL.get(p["desc"]), p["cost"], p["g_cost"],
            p["weight"], p["exchang"]) for p in frame],
          [("5 унций золота", "Слиток номиналом в пять золотых унций.", PRICE, 0, 5, 1)])
    told = []
    for t in (INGOT_1, INGOT_10):
        c.send("ss_get_si;type=%d;" % t)
        told += [(names.ALL.get(p["name"]), names.ALL.get(p["desc"]))
                 for p in named(c.frames(), "ss_si_simple_obj") if p.get("type") == t]
    check("and of its 1- and 10-ounce siblings, their names and descriptions",
          told, [("1 унция золота", "Слиток номиналом в одну золотую унцию."),
                 ("10 унций золота", "Слиток номиналом в десять золотых унций.")])

    # --- handed in at Джеррах -------------------------------------------------------------
    arrival, pos = goto(c, WEST)
    jid = npc(arrival, JERRAKH).get("id", 0)
    got = hand_in(c, jid, Q)
    gone = [p for p in named(got, "ss_obj_status") if p["status"] == 0]
    # A repeatable quest: the day's count follows the purse, before the ack
    # (server.DAILY_MAX counts repeatable hand-ins, and the journal reads it).
    check("handed in: the ingot leaves the bag, the purse follows, the day's"
          " count, then the ack",
          (answer(got), len(gone), [p["res"] for p in named(got, "cmdAck")]),
          (["ss_obj_status", "userInfo_Player", "q_sys", "cmdAck"], 1, [0]))
    check("  ..paid in full: 5 ounces of gold, as the client shows it (floor(gold / 100))",
          [(p["gold"] - GOLD0, p["gold"] // OUNCE - GOLD0 // OUNCE, p["afro"])
           for p in named(got, "userInfo_Player")], [(REWARD, 5, AFRO0)])
    check("  ..and so in the database, the ingot gone",
          (bag_of(CHAR, INGOT), money(CHAR)), (0, (AFRO0, GOLD0 + REWARD)))
    c.send("q_list;")
    check("the quest is out of the log", named(c.frames(), "q_list"), [{"q_id": [], "q_types": []}])

    # --- again ---------------------------------------------------------------------
    c.send("q_status;q_type=%d;" % QUEST)
    check("it is on offer again", [p["status"] for p in named(c.frames(), "q_status")], [1])
    c.send("q_st;mob=%d;q_idx=0;" % jid)
    got = c.frames(0.8)
    check("taken again, at nought", ([p["res"] for p in named(got, "cmdAck")], counts(got)),
          ([0], [([0], 0)]))
    Q2 = named(got, "q_di_bring_l_obj")[0]["q_id"] if named(got, "q_di_bring_l_obj") else 0
    got, _oid = give(c, INGOT, 1)
    check("a second ingot (from another hand, say): one of one", counts(got), [([1], 1)])
    got = hand_in(c, jid, Q2)
    check("handed in again: the ingot gone, a second 5 ounces, then the ack",
          (answer(got), [p["gold"] - GOLD0 for p in named(got, "userInfo_Player")],
           [p["res"] for p in named(got, "cmdAck")]),
          (["ss_obj_status", "userInfo_Player", "q_sys", "cmdAck"], [2 * REWARD], [0]))
    check("  ..10 ounces in all, no ingot left", (bag_of(CHAR, INGOT), money(CHAR)),
          (0, (AFRO0, GOLD0 + 2 * REWARD)))

    arrival, pos = goto(c, WEST)
    check("two hand-ins counted against the day, like any quest's",
          [p["daily_available"] for p in named(arrival, "q_sys")], [DAILY_MAX - 2])
    jid = npc(arrival, JERRAKH).get("id", 0)

    # --- or sold at his stall ---------------------------------------------------------
    got, ingot = give(c, INGOT, 1)
    c.send("ss_create;s_type=1;target=%d;" % jid)
    check("his stall opens", [p["res"] for p in named(c.frames(), "cmdAck")], [0])
    c.send("ss_upd;param=1;obj=x%s;s_status=2;" % ingot)
    got = c.frames()
    check("an ingot sold to a trader: 70 per cent of its price",
          (answer(got), [p["afro"] - AFRO0 for p in named(got, "userInfo_Player")]),
          (["cmdAck", "ss_obj_status", "userInfo_Player"], [SOLD]))
    c.send("ss_upd;obj=x0;s_status=0;")
    c.frames(0.3)
    check("  ..and in the database", (bag_of(CHAR, INGOT), money(CHAR)),
          (0, (AFRO0 + SOLD, GOLD0 + 2 * REWARD)))
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

try:
    probe = accounts.Store(DB)
    if CHAR is not None:
        check("the history holds the two hand-ins, the log nothing",
              (probe.quests_done_since(CHAR, 0), len(probe.quests(CHAR))), (2, 0))
    probe.close()
except Exception:
    import traceback
    fails.append("the database could not be read:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("boss ingot OK")
