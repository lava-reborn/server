"""The Nubian mine's gold sand and emeralds, and Камал's «Золотоискатель».

The owner's decisions of 2026-09-25. The mine's marauders, [1] Слабый Мародёр
836 and [2] Мародёр 837, drop what the original's texts say they carried:
bags of gold sand (2258 Gold_sand) and emeralds (3159 small_emerald,
«Небольшие изумруды»). The chances are designed -- sand 0.50 from both
(the owner's, up from 0.20/0.30), an ordinary row; the emerald 0.10 from both, a valuable one --
and sit in data/loot_manual.json, rolled by mobs.loot_table beside the wiki's
table under the same rules (one roll a row, valuables first, two kept at
most). Nobody else drops either: the marauders stand in the mine's files and
nowhere else, and every other creature's table is what it was.

Both things are proper items: the original's name and description, the wiki
article's price and weight (100 afro and 100 g the bag, 400 afro and 10 g an
emerald), a trader at the Nubian market pays for them, and both fall off a
dead player like any loot (the owner: «любой лут должен падать»).

And Камал, on the first tier, gives a second quest beside the way out: the
original's «Золотоискатель» (texts.xml 59932-59935) with ten bags where it
said five. The bag is counted -- the journal is told each time the number
moves -- nine bags are refused, ten are taken at the hand-in for exactly one
ounce of gold (rew_gold 100: the purse is kept in hundredths), and it can be
done again -- the next day: once a day since 2026-09-28 (per_day 1, the
plan's gold taps), so the suite moves the first hand-in a day back. Камал
takes both his quests back: the way out, handed in, still moves the player,
takes nothing and is not counted against the day -- the sand's second
hand-in is.

In process: the tables and their rates (a fixed seed; the cap of two worked
out exactly, as test_loot does), every other creature's table against the
same table without the hand-made rows, the item frames and names, the
death rule, and a corpse's bag through RoomCombat with a real database. On a
socket: down through Рудо, one marauder killed and his bag emptied, the
quest taken, filled, refused at nine, handed in at ten, taken and handed in
again, the way up, and the sale at Борис's stall.

Written against the code before the change it fails from the first table on
-- no row of sand or emerald for either marauder, the bag worth 10 afro and
the emerald shown as "small_emerald", Камал with one quest -- and on the
socket at the second quest's q_st. Against the code that moved the player
at the take, it fails at both ways (4 checks): nothing journalled to hand
back, and Камал taking back the sand alone.
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

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
os.environ.pop("LAVA_PASSAGES", None)

sys.path.insert(0, HERE)
import accounts      # noqa: E402
import combat        # noqa: E402
import inventory     # noqa: E402
import items         # noqa: E402
import mobs          # noqa: E402
import names         # noqa: E402
import progression   # noqa: E402
import quests        # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

SAND, EMERALD = 2258, 3159
# The owner's junk for the mine's marauders (2026-09-26): broken watch,
# razor and wristwatch, ordinary rows after the sand.
JUNK = [(6919, 0.3, False), (6926, 0.3, False), (6932, 0.35, False)]
# And two valuables («давай еще золотой портсигар и золотой зуб»), rolled
# with the emerald and the level's own valuable, before the sand.
GOLD_ROWS = [(6950, 0.05, True), (6953, 0.05, True)]
WEAK, BANDIT = 836, 837
BANDITS = (WEAK, BANDIT)
MOUTH, TIER1, MARKET = 153, 612, 185
MOUTH_CELL = (6273, 1829)
MINE_FILES = {612, 767, 1011, 1217, 1248}
RUDO, KAMAL, BORIS = 1133, 1134, 5212
DOWN, UP, GOLD = 7, 8, 9
EMERALDS = 59                       # Камал's «Изумруды» (test_valley_market)
OLD_ADITS = 57                      # Шульц's «Старые штольни», before the way down
ADMIN_GUN, ROUNDS = 1534, 6092
NOT_READY = 3                       # server.RES_NOT_READY
DAILY_MAX = 10                      # server.DAILY_MAX
OUNCE = 100                         # gold travels in hundredths (progression.GOLD_OUNCE)
DESIGNED = {WEAK: {SAND: 0.5, EMERALD: 0.1}, BANDIT: {SAND: 0.5, EMERALD: 0.1}}

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


# Read through getattr: on the code before this change it does not exist,
# and the suite has to say what is missing rather than stop at it.
loot_manual = getattr(items, "loot_manual", lambda: {})

# --- the tables ------------------------------------------------------------------
check("the cap of two a kill is what it was", mobs.MAX_DROPS, 2)
valuable = {t: mobs.level_piece(mobs.VALUABLE_SERIES, mobs.stats(t).level) for t in BANDITS}
check("the weak marauder rolls for an emerald and his valuable, then a bag of sand and the owner's junk",
      mobs.loot_table(WEAK), [(EMERALD, 0.1, True), (valuable[WEAK], 0.06, True)] + GOLD_ROWS
      + [(SAND, 0.5, False)] + JUNK)
check("the marauder the same, with the better chance of sand",
      mobs.loot_table(BANDIT),
      [(EMERALD, 0.1, True), (valuable[BANDIT], 0.06, True)] + GOLD_ROWS + [(SAND, 0.5, False)] + JUNK)

# Every other creature's table against the same table built without the
# mine's hand-made rows: they change the marauders' and nobody else's. The
# file's other row, the valley boss's ingot (test_boss_ingot), stays in both.
now = {int(t): mobs.loot_table(int(t)) for t in mobs.TYPES}
_saved = (getattr(mobs, "_LOOT_MANUAL", None), dict(mobs._TABLES))
mobs._LOOT_MANUAL = {k: v for k, v in (_saved[0] or {}).items() if int(k) not in BANDITS}
mobs._TABLES.clear()
bare = {int(t): mobs.loot_table(int(t)) for t in mobs.TYPES}
mobs._LOOT_MANUAL, _tables = _saved
mobs._TABLES.clear()
mobs._TABLES.update(_tables)
check("the hand-made rows change the tables of the two marauders and of no other creature",
      sorted(t for t in now if now[t] != bare[t]), sorted(BANDITS))
check("and, of theirs, only by the sand, the emerald and the owner's junk",
      [sorted(set(now[t]) - set(bare[t])) for t in BANDITS],
      [sorted([(SAND, DESIGNED[t][SAND], False), (EMERALD, 0.1, True)] + JUNK + GOLD_ROWS) for t in BANDITS])
check("nobody else rolls for either", sorted(t for t, rows in now.items()
                                             if t not in BANDITS and {r[0] for r in rows} & {SAND, EMERALD}), [])

# Where they stand: the mine's files, and no stand-in for a missing creature.
where = {}
for name in sorted(os.listdir(os.path.join(world.RES, "locations", "static"))):
    if not name.endswith(".xml"):
        continue
    loc_id = int(name[:-4])
    try:
        spawns = world.location(loc_id).spawns
    except Exception:           # noqa: BLE001 -- a file the server cannot open is no room
        continue
    if any(t in BANDITS or world.substitute(t) in BANDITS for _c, t in spawns):
        where[loc_id] = sorted({t for _c, t in spawns if t in BANDITS})
check("the marauders stand in the mine's files and nowhere else", set(where), MINE_FILES)


def kept_rates(rows, cap):
    """The chance each row ends up in the bag (test_loot's): its own, times
    the chance that fewer than `cap` rows before it came up."""
    dist = [1.0] + [0.0] * cap
    out = []
    for _t, p, _v in rows:
        out.append(p * sum(dist[:cap]))
        new = list(dist)
        for k in range(cap):
            new[k] -= dist[k] * p
            new[k + 1] += dist[k] * p
        dist = new
    return out


N = 20000
for mob in BANDITS:
    rows = mobs.loot_table(mob)
    rng = random.Random(20260925 + mob)
    seen = {}
    for _ in range(N):
        for t, _n in mobs.roll_table(mob, rng):
            seen[t] = seen.get(t, 0) + 1
    off, kept = [], {}
    for (t, _p, _v), want in zip(rows, kept_rates(rows, mobs.MAX_DROPS)):
        kept[t] = want
        rate = seen.get(t, 0) / float(N)
        sigma = (want * (1 - want) / N) ** 0.5
        if abs(rate - want) > 4.5 * sigma:
            off.append((t, round(rate, 4), round(want, 4)))
    # The cap takes a bag of sand only when two of the four valuables rolled
    # before it (the emerald, the level's own, and since 2026-09-26 the gold
    # tooth and cigarette case) came up first: about 2 per cent of kills, so
    # the sand lands near 0.49 and the designed rates stand within 0.015.
    check("%d: sand and emeralds drop at the designed rates, less only the cap" % mob,
          (bool(rows), off, [abs(kept.get(t, 0) - DESIGNED[mob][t]) < 0.015
                             for t in (SAND, EMERALD)]),
          (True, [], [True, True]))

# --- the items -----------------------------------------------------------------
sand, emerald = items.params_of(SAND), items.params_of(EMERALD)
check("a bag of sand: the article's 100 afro and 100 g, nothing in gold",
      (sand["cost"], sand["g_cost"], sand["weight"]), (100, 0, 100))
check("an emerald: 400 afro and 10 g, a hundred to a stack",
      (emerald["cost"], emerald["g_cost"], emerald["weight"], emerald["max_count"]),
      (400, 0, 10, 100))
check("both by the original's names, not the internal ones",
      [names.ALL.get(p["name"]) for p in (sand, emerald)], ["Золотой песок", "Небольшие изумруды"])
check("and with its descriptions",
      [names.ALL.get(p["desc"]) for p in (sand, emerald)],
      ["В природе золото встречается чаще всего в виде зерен и песчинок, именно такими "
       "песчинками и наполнен этот мешочек.", "Кристаллы изумруда, очень ценятся торговцами."])
check("every id of theirs is in the table the launcher is handed",
      [names.known(p[k]) for p in (sand, emerald) for k in ("name", "desc")], [True] * 4)
check("the frame keeps its shape: the designed one's keys, simple objects both",
      [(items.static_info(t)[0], sorted(items.static_info(t)[1]) == sorted(items.designed_info(t)[1]))
       for t in (SAND, EMERALD)], [("ss_si_simple_obj", True)] * 2)
check("neither is premium or a quest's, so a corpse may hold them",
      [(items.premium(t), mobs.droppable(t)) for t in (SAND, EMERALD)], [(False, True)] * 2)
check("a dead player may lose the sand and the emeralds, like any loot",
      [combat.drops_on_death(t) for t in (SAND, EMERALD)], [True, True])
check("the numbers are the file's, for these two and, beside them, the valley "
      "boss's ingot alone (test_boss_ingot)", sorted(loot_manual()), [SAND, EMERALD, 4796])


# --- a corpse's bag, through RoomCombat and a real database -----------------------
class _Room(object):
    def __init__(self):
        self.loc = world.location(TIER1)
        self.npcs = {}
        self.players = {}
        self.ws = False

    def broadcast(self, frame, exclude=None):
        pass


DB0 = os.path.join(tempfile.mkdtemp(), "bags.db")
accounts.DB_PATH = DB0


async def _bags(mob_type, kills):
    store = accounts.Store(DB0)
    rc = combat.RoomCombat(_Room(), store)
    combat.RNG.seed(25)
    kinds = {}
    for i in range(kills):
        mob = mobs.Mob(i + 1, mob_type, 10 + 3 * i)
        rc.corpse_gone(mob, [])
        for uniq in rc.loot[mob.cell].uniqs:
            row = store.item(uniq)
            if row["root"] != items.TRASH and row["type_id"] in (SAND, EMERALD):
                fails.append("bag row %r has the wrong root" % row)
            kinds[row["type_id"]] = kinds.get(row["type_id"], 0) + row["count"]
    for bag in rc.loot.values():
        if bag.expiry is not None:
            bag.expiry.cancel()
    store.close()
    return kinds


KILLS = 600
for mob in BANDITS:
    kinds = asyncio.run(_bags(mob, KILLS))
    got = []
    for t in (SAND, EMERALD):
        want = DESIGNED[mob][t] * KILLS
        got.append(abs(kinds.get(t, 0) - want) <= 4.5 * (want * (1 - DESIGNED[mob][t])) ** 0.5)
    check("%d marauders %d leave bags of sand and emeralds on the ground, about as often "
          "as the table says" % (KILLS, mob), got, [True, True])


# --- the server ------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "gold.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("prospector", "secret")
_store.close()
CRED = accounts.credential("prospector", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX=str(MOUTH_CELL[0]), LAVA_GY=str(MOUTH_CELL[1]),
           LAVA_AP_REGEN="25", LAVA_RESPAWN="600", LAVA_SEED="7")
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


def npc(frames, type_id, frame="userInfo_Commoner"):
    return next((p for p in named(frames, frame) if p["name"] == type_id), {})


def way(c, npc_id):
    """A way of the mine's (test_mine): its quest, q_idx 0, taken -- the ack
    and the quest in the journal -- then handed back to the same NPC.
    Returns the frames of the take and those of the hand-in, up to its lcall
    and a moment more."""
    c.send("q_st;mob=%d;q_idx=0;" % npc_id)
    took = c.until(lambda f: f[0] == "q_di_del_obj", 3)
    di = named(took, "q_di_del_obj")
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (npc_id, di[0]["q_id"] if di else 0))
    return took, c.until(lambda f: f[0] == "lcall", 3) + c.frames(0.4)


def counts(frames):
    """The q_di_bring_l_obj of the quest among the frames: (obj_num, complete) each."""
    return [(p["obj_num"], p["complete"]) for p in named(frames, "q_di_bring_l_obj")]


# What the server says to the player about his own things and purse, without
# the room around him (a marauder's steps, the action-point bar).
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


def cell_of(c, mob, home):
    for n, p in reversed(c.seen):
        if n == "userMove" and p.get("id") == mob:
            return p["path"][-1]
    return home


CHAR = None
try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@prospector@;")
    c.frames()
    probe = accounts.Store(DB)
    CHAR = probe.db.execute("SELECT id FROM characters WHERE name = ?",
                            ("prospector",)).fetchone()["id"]
    # Шульц's «Старые штольни» done a day ago: Рудо's way down comes after it
    # (need_any), and a one-off is no hand-in of today's.
    probe.finish_quest(0, CHAR, OLD_ADITS, when=int(time.time()) - 86400)
    probe.close()
    AFRO0, GOLD0 = money(CHAR)
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    arrival, pos = enter(c)
    rudo = npc(arrival, RUDO)
    _took, got = way(c, rudo["id"])
    check("down through Рудо's quest, taken and handed back",
          [p["id"] for p in named(got, "lcall")], [TIER1])
    arrival, pos = enter(c)
    tier1 = world.location(TIER1)

    # --- Камал gives two quests now ---------------------------------------------------
    kamal = npc(arrival, KAMAL)
    check("Камал gives the way out first and the gold sand second (the emeralds third),"
          " and takes them back",
          (kamal.get("give_quests"), kamal.get("take_quests")),
          ([UP, GOLD, EMERALDS], [UP, GOLD, EMERALDS]))
    for q in (UP, GOLD):
        c.send("q_status;q_type=%d;" % q)
    check("both are on offer, under their names",
          [(p["type"], p["status"], p["name"]) for p in named(c.frames(), "q_status")],
          [(q, 1, quests.STRING_BASE + quests.STRINGS_PER_QUEST * q + quests.NAME)
           for q in (UP, GOLD)])
    c.send("q_si;q_type=%d;" % GOLD)
    si = named(c.frames(), "q_si_bring_l_obj")
    check("«Золотоискатель» asks for ten bags of sand and pays one ounce of gold, again and again",
          [(p["obj_1"], p["obj_num_1"], p["mobs_1"], p["obj_2"], p["rew_gold"], p["rew_afro"],
            p["rew_obj"], p["repeatable"], p["rew_loc"]) for p in si],
          [(SAND, 10, [WEAK, BANDIT], 0, OUNCE, 0, [], 1, 0)])
    texts = [names.text(sid) for sid in quests.get(GOLD).string_ids()] if quests.get(GOLD) else []
    check("in the original's words, with ten for five",
          (texts[:1], [t.count("10 мешков") for t in texts[1:3]],
           ["5 меш" in t for t in texts], all(names.known(s) for s in quests.get(GOLD).string_ids())
           if quests.get(GOLD) else False),
          (["Золотоискатель"], [2, 1], [False] * 4, True))

    c.send("q_st;mob=%d;q_idx=1;" % kamal["id"])
    got = c.frames(0.8)
    check("taking it: the ack, then the quest in the journal at nought of ten, no move",
          ([(n, p.get("res")) for n, p in got if n in ("cmdAck", "lcall")], counts(got)),
          ([("cmdAck", 0)], [([0], 0)]))
    Q = named(got, "q_di_bring_l_obj")[0]["q_id"] if named(got, "q_di_bring_l_obj") else 0
    c.send("q_list;")
    check("and it is in the log", named(c.frames(), "q_list"), [{"q_id": [Q], "q_types": [GOLD]}])

    # --- one marauder, killed; his bag, emptied -----------------------------------------
    for label, cmd in (("gun", "/give %d" % ADMIN_GUN), ("rounds", "/give %d 50" % ROUNDS)):
        c.send("userMsg;entry=@%s@;group=0;" % cmd)
        got = c.until(lambda f: f[0] == "userMsg")
        if label == "gun":
            gun = str(named(got, "ss_obj_status")[0]["obj"])
        else:
            rounds = str(named(got, "ss_obj_status")[0]["obj"])
    c.send("ss_get;target=0;slot=11;")
    held = [str(x) for x in c.frames()[0][1]["o_list"]]
    if held[6] != "0":
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % gun)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
    c.until(lambda f: f[0] == "ss_di_firearm")

    infos = {p["id"]: p["name"] for p in named(arrival, "userInfo") if p["name"] in BANDITS}
    bandits = {p["newUser"]: p["pos"] for p in named(arrival, "lch")
               if "newUser" in p and p["newUser"] in infos}
    aggro = mobs.stats(BANDIT).aggro
    target = min(bandits, key=lambda b: mobs.hex_distance(bandits[b], pos, tier1.width))
    near = [cell for cell in range(tier1.width * tier1.height)
            if cell not in tier1.obstacles and cell not in bandits.values()
            and mobs.hex_distance(cell, bandits[target], tier1.width) <= aggro - 1
            and all(mobs.hex_distance(cell, b, tier1.width) > aggro + 0.5
                    for i, b in bandits.items() if i != target)]
    pos = min(near, key=lambda cell: mobs.hex_distance(cell, pos, tier1.width))
    c.send("moveTo;path=|%d|;" % pos)
    c.until(lambda f: f[0] == "lch" and f[1].get("enemy") == target, 4)
    # It comes for him with a knife (mobs.stats: range 1): wait for it at his
    # side, so that it falls there and its bag lies a step away, never within
    # another marauder's reach. Shot on its way it would drop where the
    # others stand guard: the scatter (combat.cone_of) lets a shot land at
    # five hexes as well as at one.
    for _ in range(25):
        if progression.within_reach(bandits[target], pos, tier1.width, tier1.height):
            break
        for n, p in c.frames(0.2):
            if n == "userMove" and p.get("id") == target and p.get("path"):
                bandits[target] = p["path"][-1]
    dead = None
    for attempt in range(40):
        c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(target)))
        got = c.until(lambda f: f[0] == "ss_di_firearm"
                      or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.3)
        if [p for p in named(got, "lch") if p.get("dead") == target]:
            dead = got
            break
        time.sleep(0.5)
    check("a marauder falls", dead is not None, True)
    got = list(dead or [])
    if not named(got, "ss_loot"):
        got += c.until(lambda f: f[0] == "ss_loot", 5)
    where = [p["hex"][0] for p in named(got, "ss_loot") if p.get("s_status") == 1]
    check("his bag lies where he fell", len(where), 1)
    kind = infos[target]
    found = gems = 0
    if where:
        # Up to the bag, never within reach of another marauder: one that
        # took the player for its target would keep him, and hold the way
        # out further on shut with every blow it landed.
        wary = {cell for cell in range(tier1.width * tier1.height)
                if any(mobs.hex_distance(cell, b, tier1.width) <= aggro + 0.5
                       for i, b in bandits.items() if i != target)}
        path = mobs.find_path(tier1, pos, lambda cell: cell == where[0]
                              or progression.within_reach(cell, where[0], tier1.width,
                                                          tier1.height), wary)
        check("the bag is a walk away", path is not None, True)
        c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path or [pos]))
        c.frames(0.2 * len(path or [pos]) + 1.0)
        pos = (path or [pos])[-1]
        c.send("ss_create;s_type=0;target=%d;" % where[0])
        check("the bag opens", [p["res"] for p in named(c.frames(), "cmdAck")], [0])
        c.send("ss_get;slot=24;")
        lst = [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]
        loot = [inventory.parse_oid(o)[1] for o in lst[lst.index("0") + 1:]]
        level = mobs.stats(kind).level
        allowed = (set(mobs.series(mobs.TRASH_SERIES)[max(0, level - mobs.JUNK_SPREAD):level + 1])
                   | {t for t, _c, _v in mobs.loot_table(kind)})
        check("in it: a piece of his junk, and nothing his table does not hold",
              (bool(set(loot) & set(mobs.series(mobs.TRASH_SERIES))), sorted(set(loot) - allowed)),
              (True, []))
        found, gems = loot.count(SAND), loot.count(EMERALD)
        print("  ..  marauder %d left %s" % (kind, sorted(loot)))
        c.send("ss_upd;s_status=3;obj=x0;param=1;")
        got = c.frames(0.8)
        check("taken whole: the ack first; the journal told of a bag of sand only if there was one",
              ([p["res"] for p in named(got, "cmdAck")][:1], counts(got)),
              ([0], [([found], 0)] if found else []))
        c.send("ss_upd;s_status=0;obj=x0;param=1;")
        c.frames(0.3)

    # --- the bag counted, to nine ---------------------------------------------------
    have = found
    got, heap4 = give(c, SAND, 4)
    have += 4
    check("a stack of four: the journal counts its size", counts(got), [([have], 0)])
    while have < 9:
        got, _oid = give(c, SAND, 1)
        have += 1
        check("one more bag: %d of ten" % have, counts(got), [([have], 0)])
    c.send("q_di;q_id=%d;" % Q)
    check("asked again, the journal says nine", counts(c.frames()), [([9], 0)])

    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (kamal["id"], Q))
    got = c.frames(0.8)
    check("nine bags handed in: refused, nothing taken and nothing paid",
          (answer(got), [p["res"] for p in named(got, "cmdAck")]), (["cmdAck"], [NOT_READY]))
    check("  ..the bags stay in the bag, the purse as it was",
          (bag_of(CHAR, SAND), money(CHAR)), (9, (AFRO0, GOLD0)))

    got, heap2 = give(c, SAND, 2)
    check("two more: ten of ten, and the quest can be handed in", counts(got), [([10], 1)])

    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (kamal["id"], Q))
    got = c.frames(0.8)
    gone = [str(p["obj"]) for p in named(got, "ss_obj_status") if p["status"] == 0]
    # A repeatable quest: the day's count follows the purse, before the ack
    # (server.DAILY_MAX counts repeatable hand-ins, and the journal reads it).
    check("ten handed in: the bags leave the bag, the purse follows, the day's"
          " count, then the ack",
          ([n for n in answer(got) if n != "ss_obj_status"],
           len(gone), [(str(p["obj"]), p["size"]) for p in named(got, "ss_di_heap")],
           [p["res"] for p in named(got, "cmdAck")]),
          (["ss_di_heap", "userInfo_Player", "q_sys", "cmdAck"], 6, [(heap2, 1)], [0]))
    check("  ..paid in full: one ounce of gold, as the client shows it (floor(gold / 100))",
          [(p["gold"] - GOLD0, p["gold"] // OUNCE - GOLD0 // OUNCE, p["afro"])
           for p in named(got, "userInfo_Player")], [(OUNCE, 1, AFRO0)])
    check("  ..and so in the database: ten bags gone of eleven, one ounce more",
          (bag_of(CHAR, SAND), money(CHAR)), (1, (AFRO0, GOLD0 + OUNCE)))
    check("  ..the heap of four among them", heap4 in gone, True)
    c.send("q_list;")
    check("the quest is out of the log", named(c.frames(), "q_list"), [{"q_id": [], "q_types": []}])

    # --- once a day, then again ------------------------------------------------------
    c.send("q_status;q_type=%d;" % GOLD)
    check("handed in, it is not on offer again today (per_day 1)",
          [p["status"] for p in named(c.frames(), "q_status")], [0])
    probe = accounts.Store(DB)
    probe.db.execute("UPDATE char_quests_done SET done_at = done_at - 86400"
                     " WHERE char_id = ? AND type = ?", (CHAR, GOLD))
    probe.db.commit()
    probe.close()
    c.send("q_status;q_type=%d;" % GOLD)
    check("its hand-in a day back, it is on offer again",
          [p["status"] for p in named(c.frames(), "q_status")], [1])
    c.send("q_st;mob=%d;q_idx=1;" % kamal["id"])
    got = c.frames(0.8)
    check("taken again, it starts from the bag that was left over",
          ([p["res"] for p in named(got, "cmdAck")], counts(got)), ([0], [([1], 0)]))
    Q2 = named(got, "q_di_bring_l_obj")[0]["q_id"] if named(got, "q_di_bring_l_obj") else 0
    got, _oid = give(c, SAND, 9)
    check("nine more make ten", counts(got), [([10], 1)])
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (kamal["id"], Q2))
    got = c.frames(0.8)
    check("handed in again: both stacks gone, a second ounce, then the ack",
          (answer(got), [p["gold"] - GOLD0 for p in named(got, "userInfo_Player")],
           [p["res"] for p in named(got, "cmdAck")]),
          (["ss_obj_status", "ss_obj_status", "userInfo_Player", "q_sys", "cmdAck"],
           [2 * OUNCE], [0]))
    check("  ..no sand left, two ounces in all", (bag_of(CHAR, SAND), money(CHAR)),
          (0, (AFRO0, GOLD0 + 2 * OUNCE)))

    # --- the way up takes nothing ------------------------------------------------------
    got, sand_oid = give(c, SAND, 1)
    check("with no quest counting the bag, a bag of sand is only a bag of sand", counts(got), [])
    got, emerald_oid = give(c, EMERALD, 2)
    took, got = way(c, kamal["id"])
    check("Камал's way out, taken: the ack and the quest, the bag untouched",
          [(n, p.get("res")) for n, p in took
           if n in ("cmdAck", "lcall", "ss_obj_status", "ss_di_heap") or n.startswith("q_")],
          [("cmdAck", 0), ("q_di_del_obj", None)])
    check("handed back, it still moves the player: one ack, one lcall, nothing taken",
          [(n, p.get("res"), p.get("id")) for n, p in got
           if n in ("cmdAck", "lcall", "ss_obj_status", "ss_di_heap") or n.startswith("q_")],
          [("cmdAck", 0, None), ("lcall", None, MOUTH)])
    arrival, pos = enter(c)
    check("up at the mouth with the sand and the emeralds still on him",
          (bag_of(CHAR, SAND), bag_of(CHAR, EMERALD)), (1, 2 + gems))
    check("one hand-in counted against the day, the sand's second: the ways cost none",
          [p["daily_available"] for p in named(arrival, "q_sys")], [DAILY_MAX - 1])

    # --- and sold at the Nubian market ---------------------------------------------------
    c.send("userMsg;entry=@/goto %d@;group=0;" % MARKET)
    c.until(lambda f: f[0] == "lcall")
    arrival, pos = enter(c)
    boris = npc(arrival, BORIS, "userInfo_Trader")
    check("Борис keeps his stall at the market", bool(boris), True)
    c.send("ss_create;s_type=1;target=%d;" % boris.get("id", 0))
    check("the stall opens", [p["res"] for p in named(c.frames(), "cmdAck")], [0])
    afro = AFRO0
    for label, oid, cost, left in (("the bag of sand", sand_oid, 100, None),
                                   ("one emerald of two", emerald_oid, 400, 1),
                                   ("the other", emerald_oid, 400, None)):
        c.send("ss_upd;param=1;obj=x%s;s_status=2;" % oid)
        got = c.frames()
        # Inventory.sell's price, as ItemContainer.showCost draws it.
        paid = max(1, int(math.floor(cost / 1.0 * 1 * inventory.SMOD * 1 * 1.0)))
        afro += paid
        check("%s sold for %d afro" % (label, paid),
              (answer(got), [p["afro"] for p in named(got, "userInfo_Player")],
               [p["size"] for p in named(got, "ss_di_heap")]),
              (["cmdAck", "ss_di_heap" if left else "ss_obj_status", "userInfo_Player"],
               [afro], [left] if left else []))
    c.send("ss_upd;obj=x0;s_status=0;")
    c.frames(0.3)
    check("sold, and the afro in the purse",
          (bag_of(CHAR, SAND), bag_of(CHAR, EMERALD), money(CHAR)),
          (0, gems, (afro, GOLD0 + 2 * OUNCE)))
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
        check("the history holds the two hand-ins of the gold sand, the log nothing",
              (probe.quests_done_since(CHAR, 0, [GOLD]), len(probe.quests(CHAR))), (2, 0))
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
print("mine gold OK")
