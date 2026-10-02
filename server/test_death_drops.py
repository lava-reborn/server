"""What a dead player loses: the owner's rules of 2026-09-25, for every death.

  * «С персонажей должны падать случайные предметы из одежды с вероятностью
    10%, если оно афро; если голд-предметы, то они не падают» -- each piece
    in the six clothing slots falls with 10 per cent, unless it is a gold
    thing (combat.gold_item);
  * «при смерти падает часть лута из рюкзака», «Каждая вещь с шансом 30%» --
    each thing in the backpack falls with 30 per cent, and a stack of three
    and more loses a third of itself (combat.bag_share); the hands, the bank
    and what lies on a barter's table keep what they hold;
  * never: gold things, premium ones, a quest's own, the developers' gun --
    and all loot falls, the mine's emeralds too («любой лут должен падать в
    том числе из шахты»);
  * «При любой смерти»: to a mob or to a player, all of it into ONE bag on
    the cell of the death, one transaction for every move, the client told
    of each thing that left it (ss_obj_status 0) and of each stack that kept
    the rest (ss_di_heap), the bonuses and the figure recounted.

In process: which types may fall, the rates exactly (a stub whose hundred
rolls meet every number once, and a seeded generator over thousands of
deaths), and Store.drop_items on a real database -- the split into a new
row, and a row changed under the write rolling back the whole death.

On a socket the chances are raised to 100 per cent (LAVA_WEAR_DROP,
LAVA_BAG_DROP), so what falls is known to the piece: a character in a full
Колонист (A), a gold belt, the starter pistol in hand and a backpack of
every kind of thing dies to the dump's dog with a witness looking on; then
one player kills another in the open desert and empties the bag -- a level
above the other, so that no trophy joins it (test_trophies). Each time
the bag on the cell holds exactly what the dead lost, the rest stays theirs,
and a relog shows the same.

    LAVA_RES=.../lava/res python3 server/test_death_drops.py
"""
import os
import random
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
# The owner's numbers are what the in-process part checks; the server below
# gets its own environment.
for _knob in ("LAVA_WEAR_DROP", "LAVA_BAG_DROP"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import progression  # noqa: E402
import rooms  # noqa: E402
import sets  # noqa: E402
import world  # noqa: E402
from inventory import ARMOR, BAG, BANK, BELT, BOOTS, CAMO, HEAD, LEGS, PRIMARY  # noqa: E402
from protocol import decode  # noqa: E402

from testkit import check, fails  # noqa: E402


gold_item = getattr(combat, "gold_item", None)
death_losses = getattr(combat, "death_losses", None)

# --- the things --------------------------------------------------------------
KOLONIST_A = sets.SETS[11167]["members"]    # helm shirt armor pants boots, afro
KOLONIST_G = sets.SETS[11169]["members"]    # the same set's gold copy
SLOT = {"helm": HEAD, "shirt": CAMO, "armor": ARMOR, "pants": LEGS, "boots": BOOTS}
GOLD_BELT = 3599            # belt_assault_rifles_g: the gold mark of its name
PISTOL = inventory.STARTER_PISTOL
ROUNDS = inventory.STARTER_AMMO   # 9мм дареные: afro and gold both, an afro thing
AFRO_GUN = 25566            # Наган 1895, 400 afro
GOLD_GUN = 25567            # its gold copy, 1 hundredth of an ounce and no afro
GOLD_ROUNDS = 7006          # 9мм НАТО (G) $КС: the original's own [G]
SAND = 2258                 # Золотой песок: falls
EMERALD = 3159              # Небольшие изумруды: loot like any, falls («любой лут должен падать»)
QUEST = 260                 # qDogsMeat, «Мясо антилопы»: a quest's own
TICKET = 1124               # Билет в Донголу: the wiki says "нет", it falls now
PREMIUM = 6069              # an "(P)" medicine
GOLD_NAMED = 6196           # Ammo_stun_bolt_gold_10: "gold" in the name, sold for afro
GOLD_BLUEPRINT = 37670      # bpg_damage_25_gold_lvl10: the gold line's, sold for gold
                            # alone (items.GOLD_LINE_BLUEPRINTS, 2026-09-28)

# --- in process: which things may fall at all --------------------------------
wiki = items.wiki()
flags = {}
for rec in wiki.values():
    key = rec.get("drop_on_death", "none")
    flags[key] = flags.get(key, 0) + 1
check("the wiki's column, as it reached items_wiki.json: 88 да, 557 нет, 815 silent"
      " (with the belts and the gun stalls' lines of 2026-09-28)",
      (flags.get(1), flags.get(0), flags.get("none")), (88, 557, 815))
check("the owner's numbers: clothing 10 per cent, the backpack 30",
      (getattr(combat, "WEAR_DROP_CHANCE", None), getattr(combat, "BAG_DROP_CHANCE", None)),
      (10, 30))
check("a gold thing is known by its price, by the original's [G], and where no"
      " table prices it by the gold mark of its name",
      [gold_item(t) if gold_item else None for t in
       (KOLONIST_G["helm"], GOLD_GUN, GOLD_ROUNDS, GOLD_BELT, 13077, GOLD_BLUEPRINT)],
      [True] * 6)
check("and an afro one is not, a written afro price beating a gold-sounding name",
      [gold_item(t) if gold_item else None for t in
       (KOLONIST_A["helm"], AFRO_GUN, ROUNDS, SAND, TICKET, GOLD_NAMED, PISTOL)],
      [False] * 7)
check("never falls: gold, premium, a quest's own, the admin gun",
      [combat.drops_on_death(t) for t in
       (KOLONIST_G["helm"], GOLD_GUN, GOLD_ROUNDS, GOLD_BELT, GOLD_BLUEPRINT, PREMIUM, QUEST,
        items.ADMIN_GUN)],
      [False] * 8)
check("may fall: afro clothing, guns, rounds, the sand, the mine's emeralds -- and"
      " a thing the wiki marks «нет», since the owner said each thing",
      [combat.drops_on_death(t) for t in
       (KOLONIST_A["helm"], KOLONIST_A["boots"], AFRO_GUN, PISTOL, ROUNDS, SAND, EMERALD,
        TICKET)],
      [True] * 8)
check("the ticket is one of the wiki's «нет»", wiki[TICKET].get("drop_on_death"), 0)


def row_of(uniq, type_id, slot, count=1):
    f = inventory.new_fields(type_id, count)
    f.update(uniq=uniq, type_id=type_id, slot=slot, char_id=1)
    for k in accounts.ITEM_FIELDS:
        f.setdefault(k, 0)
    return f


class Cycle:
    """randint that walks a..b in turn: a hundred rolls meet every number
    from 1 to 100 exactly once, so a chance of c per cent comes up exactly
    c times in them."""

    def __init__(self):
        self.i = 0

    def randint(self, a, b):
        v = a + self.i % (b - a + 1)
        self.i += 1
        return v


def losses_over(rows, deaths, rng, locked=()):
    """Per row (by serial) the pieces lost over `deaths` deaths of a body
    that holds `rows` each time."""
    lost = {r["uniq"]: [] for r in rows}
    for _ in range(deaths):
        for row, n in death_losses(rows, locked, rng):
            lost[row["uniq"]].append(n)
    return lost


if death_losses:
    worn = row_of(1, KOLONIST_A["helm"], HEAD)
    single = row_of(2, AFRO_GUN, BAG)
    one = row_of(3, SAND, BAG, 1)
    two = row_of(4, SAND, BAG, 2)
    # One roll per row and death, so each row gets a stub of its own.
    lost = [losses_over([r], 100, Cycle())[r["uniq"]] for r in (worn, single, one, two)]
    check("a hundred deaths, every roll once: the clothing falls 10 times,"
          " a single thing 30, a stack of one and of two 30 each and whole",
          [(len(n), sorted(set(n))) for n in lost],
          [(10, [1]), (30, [1]), (30, [1]), (30, [2])])
    lost = losses_over([worn, single, one, two], 100, Cycle())
    check("and one body holding all four rolls once per row, in the rows' order:"
          " a hundred deaths are four hundred rolls",
          sum(len(n) for n in lost.values()),
          sum(1 for i in range(400) if i % 100 + 1 <= (10 if i % 4 == 0 else 30)))
    stacks = [row_of(10 + i, ROUNDS, BAG, n) for i, n in enumerate((3, 4, 5, 20, 200))]
    lost = losses_over(stacks, 100, Cycle())
    check("a stack of three and more loses a third, round(n/3), every time",
          [(len(lost[r["uniq"]]), sorted(set(lost[r["uniq"]]))) for r in stacks],
          [(100, [1]), (100, [1]), (100, [2]), (100, [7]), (100, [67])])
    kept = [row_of(20, KOLONIST_G["boots"], BOOTS), row_of(21, GOLD_BELT, BELT),
            row_of(22, GOLD_GUN, BAG), row_of(23, GOLD_ROUNDS, BAG, 30),
            row_of(25, QUEST, BAG, 1),
            row_of(26, AFRO_GUN, PRIMARY), row_of(27, SAND, BANK, 9),
            row_of(28, AFRO_GUN, BAG)]
    lost = losses_over(kept, 100, Cycle(), locked={28})
    check("nothing ever falls that is gold, a quest's, in the hand,"
          " in the bank or on a barter's table", sum(len(v) for v in lost.values()), 0)

    # A real generator, seeded: the rates hold over many deaths, and the
    # same seed gives the same losses thing for thing.
    body = [row_of(1, KOLONIST_A["helm"], HEAD), row_of(2, AFRO_GUN, BAG)]
    N = 40000
    lost = losses_over(body, N, random.Random(20260925))
    rates = (len(lost[1]) / float(N), len(lost[2]) / float(N))
    print("       seed 20260925, %d deaths: clothing %d (%.4f), backpack %d (%.4f)"
          % (N, len(lost[1]), rates[0], len(lost[2]), rates[1]))
    check("seeded, forty thousand deaths: 10 and 30 per cent within half a point",
          (abs(rates[0] - 0.10) < 0.005, abs(rates[1] - 0.30) < 0.005), (True, True))
    mixed = body + stacks + kept[:3]
    combat.RNG.seed(5)
    first = [[(r["uniq"], n) for r, n in death_losses(mixed)] for _ in range(50)]
    combat.RNG.seed(5)
    again = [[(r["uniq"], n) for r, n in death_losses(mixed)] for _ in range(50)]
    mine = random.Random(5)
    shadow = [[(r["uniq"], n) for r, n in death_losses(mixed, (), mine)] for _ in range(50)]
    check("the rolls are combat.RNG's (LAVA_SEED): the same seed, the same losses",
          (first == again, first == shadow), (True, True))
else:
    fails.append("combat.death_losses does not exist")

# --- in process: one transaction per death ------------------------------------
st = accounts.Store(os.path.join(tempfile.mkdtemp(), "drops.db"))
drop_items = getattr(st, "drop_items", None)
if drop_items:
    def made(type_id, count=1, slot=BAG, char_id=7):
        f = inventory.new_fields(type_id, count)
        f["slot"] = slot
        return st.create_item(char_id, type_id, f.pop("root"), **f)

    boots = made(KOLONIST_A["boots"], slot=BOOTS)
    stack = made(ROUNDS, 20)
    gun = made(AFRO_GUN)
    ground = drop_items(7, [(boots, None), (stack, 7), (gun, None)],
                        combat.LOOT_OWNER, BAG)
    check("whole things change owner under their serials, the part of a stack"
          " is a new row, in the order given",
          [(r["uniq"] == boots["uniq"], r["type_id"], r["char_id"], r["slot"], r["count"])
           for r in ground or []],
          [(True, boots["type_id"], 0, BAG, 1), (False, ROUNDS, 0, BAG, 7),
           (False, AFRO_GUN, 0, BAG, 1)])
    check("the stack keeps the rest under its own serial",
          (st.item(stack["uniq"])["char_id"], st.item(stack["uniq"])["count"]), (7, 13))
    check("and the part is a proper item of its own",
          ground and (ground[1]["uniq"] not in (boots["uniq"], stack["uniq"], gun["uniq"]),
                      ground[1]["root"], ground[1]["brk"]), (True, items.AMMO, 0))
    # A second death, of the same rows as read before the first one: the
    # stack is 13 now, so the write names a row that no longer exists as
    # read, and even the thing listed before it stays where it is.
    other = made(AFRO_GUN)
    before = {r["uniq"]: dict(r) for r in st.items_of(7)}
    check("a row changed under the write: nothing is written, not even the"
          " thing before it", drop_items(7, [(other, None), (stack, 7)],
                                         combat.LOOT_OWNER, BAG), None)
    check("everything as it was", {r["uniq"]: dict(r) for r in st.items_of(7)}, before)
    check("and nothing new on the ground",
          sorted(r["uniq"] for r in st.items_of(0)), sorted(r["uniq"] for r in ground))
    check("a split of nothing, or of the whole stack, is no split either",
          [drop_items(7, [(st.item(stack["uniq"]), n)], combat.LOOT_OWNER, BAG)
           for n in (0, 13)], [None, None])
else:
    fails.append("accounts.Store.drop_items does not exist")
st.close()


# --- the server ----------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "death_drops.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for login_ in ("victim", "witness", "hunter", "quarry"):
    _store.register(login_, "secret")
_store.close()
CRED = {n: accounts.credential(n, "secret") for n in ("victim", "witness", "hunter", "quarry")}

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730", LAVA_AP_REGEN="25",
           LAVA_RESPAWN="120", LAVA_SEED="3", LAVA_WEAR_DROP="100", LAVA_BAG_DROP="100")
# The lines the server says by itself (Session.say) are off on a served
# server; this suite reads them as the server's reasons, so it asks for
# them by name.
env["LAVA_SERVER_CHAT"] = "1"
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


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

    def _split(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.5):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._split()

    def until(self, pred, wait=3.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._split()
            out += new
            if any(pred(f) for f in new):
                break
        return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def chat(c, line):
    c.send("userMsg;entry=@%s@;group=0;" % line)


def newcomer(c, cred, name):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@%s@;" % name)
    c.frames()
    c.send("actPlayer;")
    got = c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    return got + c.frames(wait=2)


def come_back(c, cred):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    got = c.frames()
    c.send("selPers;num=0;")
    got += c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    return got + c.frames(wait=2)


def goto(c, where):
    """/goto a location by number or a map cell; the cell the lenter gave."""
    chat(c, "/goto %d %d" % where if isinstance(where, tuple) else "/goto %d" % where)
    c.until(lambda f: f[0] == "lcall", 3)
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return named(got, "lenter")[0]["pos"]


def leave(c):
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    time.sleep(0.2)


def char_id(name):
    st = accounts.Store(DB)
    row = st.db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()
    st.close()
    return row["id"]


def give(cid, type_id, count=1, slot=BAG):
    """A thing put straight into the database, the character logged out."""
    st = accounts.Store(DB)
    f = inventory.new_fields(type_id, count)
    f["slot"] = slot
    row = st.create_item(cid, type_id, f.pop("root"), **f)
    st.close()
    return row


def rows(cid):
    st = accounts.Store(DB)
    out = {r["uniq"]: r for r in st.items_of(cid)}
    st.close()
    return out


def oid(row):
    return inventory.oid_of(row)


def removed(frames):
    return sorted(str(p["obj"]) for p in named(frames, "ss_obj_status") if p["status"] == 0)


def sizes(frames):
    return [(str(p["obj"]), p["size"]) for p in named(frames, "ss_di_heap")]


def carried(c):
    """The character's own list: six clothing slots, two hands, the bag."""
    c.send("ss_get;target=0;slot=11;")
    got = c.until(lambda f: f[0] == "ss_ack")
    ack = named(got, "ss_ack")[0]
    listed = [str(o) for o in ack["o_list"]]
    return listed[:6], listed[6:8], sorted(listed[8:]), ack.get("set_res")


def vitals(c):
    """The character's own maxima, off the card: getInfo about itself."""
    c.send("getInfo;lvl=0;id=0;type=0;")
    own = lambda f: f[0] == "usrUp" and f[1].get("id", 0) == 0
    v = [p for n, p in c.until(own) if own((n, p))][0]
    return v["hmax"], v["smax"]


DUMP = 100
DOG_HOME = 4551          # the dog nearest the entrance (test_death)
DUMP_LOC = world.location(DUMP)
DESERT = (5992, 1760)    # open desert, pvp and nobody else in it (test_pvp)

try:
    # === a death to a mob ======================================================
    v = Client(connect())
    newcomer(v, CRED["victim"], "victim")
    goto(v, DUMP)
    leave(v)
    V = char_id("victim")
    kit = {r["type_id"]: r for r in rows(V).values()}
    body = {part: give(V, t, slot=SLOT[part]) for part, t in KOLONIST_A.items()}
    belt = give(V, GOLD_BELT, slot=BELT)
    pistol, rounds = kit[PISTOL], kit[ROUNDS]
    sand = give(V, SAND, 2)
    ticket = give(V, TICKET)
    afro_gun = give(V, AFRO_GUN)
    gold_gun = give(V, GOLD_GUN)
    gold_rounds = give(V, GOLD_ROUNDS, 30)
    quest = give(V, QUEST)
    banked = give(V, SAND, 3, slot=BANK)
    st = accounts.Store(DB)
    st.save_character_state(V, hp=1, sp=0)
    # At Колонист's level (2): below it the login would take the set off
    # into the bag (inventory.over_level_to_bag), and the body's own roll
    # would never be tried.
    st.save_stats(V, [("skill", progression.SHOOTING, 2, 0, progression.skill_xp_max(2))])
    st.save_character_state(V, level=2)
    st.close()
    check("the victim's rounds are the starter kit's twenty, the pistol in hand",
          (rounds["count"], rounds["slot"], pistol["slot"]), (20, BAG, PRIMARY))
    FALL_WHOLE = [body[p] for p in ("helm", "shirt", "armor", "pants", "boots")] + \
        [sand, ticket, afro_gun]
    KEPT = [belt, pistol, gold_gun, gold_rounds, quest, banked]

    w = Client(connect())
    newcomer(w, CRED["witness"], "witness")
    goto(w, DUMP)
    w.frames(0.5)
    v = Client(connect())
    arrival = come_back(v, CRED["victim"])
    pos = named(arrival, "lenter")[0]["pos"]
    wear_before, _hands, _bag, look_before = carried(v)
    check("the victim walks in wearing the whole Колонист (A), and its figure",
          (wear_before[3] == oid(belt), look_before), (True, sets.SETS[11167]["res"]))
    HMAX, SMAX = vitals(v)
    seen = w.frames(1.0)
    VP = [p["newUser"] for p in named(seen, "lch") if "newUser" in p][0]
    check("the witness sees the victim come in, under the players' id",
          VP, rooms.player_id(V))

    dog_aggro = mobs.stats(82).aggro
    path = [pos]
    while mobs.hex_distance(path[-1], DOG_HOME, DUMP_LOC.width) > dog_aggro - 0.5:
        path.append(min(
            (n for n in progression.hex_neighbours(path[-1], DUMP_LOC.width,
                                                   DUMP_LOC.height)
             if n not in DUMP_LOC.obstacles and n not in path),
            key=lambda n: mobs.hex_distance(n, DOG_HOME, DUMP_LOC.width)))
    step = path[-1]
    v.send("moveTo;path=|%s|;" % "|".join(str(c) for c in path))
    got = v.until(lambda f: f[0] == "lch" and f[1].get("dead") == 0, 40)
    got += v.frames(0.8)
    check("bitten to death", [p for n, p in got if n == "lch" and "dead" in p], [{"dead": 0}])
    after_dead = got[[i for i, (n, p) in enumerate(got)
                      if n == "lch" and p.get("dead") == 0][0]:]
    check("the victim is told each thing that left whole -- off the body and out"
          " of the bag -- and nothing else", removed(after_dead),
          sorted(oid(r) for r in FALL_WHOLE))
    check("and the rounds' new size: a third of twenty fell, thirteen stay",
          sizes(after_dead), [(oid(rounds), 13)])
    lines = [p["entry"] for p in named(after_dead, "userMsg")]
    check("and says so in the chat",
          [t.startswith("При гибели выпало:") and "(7 шт.)" in t for t in lines], [True])
    ups = [p for p in named(after_dead, "usrUp") if p.get("id") in (0, VP)]
    check("the set and its pieces are gone from the bars: 5 health (the set),"
          " 51 stamina (the pieces)",
          [(HMAX - p["hmax"], SMAX - p["smax"]) for p in ups][-1:], [(5, 51)])

    seen = w.frames(1.5)
    check("the witness sees one bag where the body fell",
          [(p["s_status"], p["hex"]) for p in named(seen, "ss_loot")], [(1, [step])])
    moves = [p for p in named(seen, "ss_obj_move") if p.get("id") == VP]
    check("and the figure taken off: the five counted slots, each empty now",
          sorted((p["to"], str(p["obj"])) for p in moves),
          sorted((s, "0") for s in inventory.SET_SLOTS))

    now_v = rows(V)
    st = accounts.Store(DB)
    ground = {r["uniq"]: r for r in st.items_of(combat.LOOT_OWNER)}
    st.close()
    parts = [r for u, r in ground.items() if u not in {x["uniq"] for x in FALL_WHOLE}]
    check("on the ground: every whole thing under its own serial, and the seven"
          " rounds as a row of their own",
          (sorted(u for u in ground if u in {x["uniq"] for x in FALL_WHOLE}),
           [(r["type_id"], r["count"], r["slot"]) for r in parts]),
          (sorted(x["uniq"] for x in FALL_WHOLE), [(ROUNDS, 7, BAG)]))
    check("the victim keeps exactly the rest: gold, the quest's, the"
          " hand, the bank, and thirteen rounds",
          sorted(now_v), sorted([r["uniq"] for r in KEPT] + [rounds["uniq"]]))
    check("where they were", [(now_v[r["uniq"]]["slot"], now_v[r["uniq"]].get("count"))
                              for r in KEPT + [rounds]],
          [(r["slot"], r["count"]) for r in KEPT] + [(BAG, 13)])
    check("nothing lost and nothing twice: pieces before = pieces after, with the ground",
          sum(r["count"] for r in now_v.values()) + sum(r["count"] for r in ground.values()),
          sum(r["count"] for r in FALL_WHOLE + KEPT) + 20)

    # The relog: the death, the body and the bag as the database has them.
    leave(v)
    w.frames(0.8)
    v = Client(connect())
    got = come_back(v, CRED["victim"])
    check("back in, still dead", [p["death"] for p in named(got, "persInfo")], [1])
    wear, hands, bag, look = carried(v)
    check("the relog shows the same: only the gold belt on the body, the pistol"
          " in hand, the rest of the backpack, no set figure",
          (wear, hands, bag, look),
          (["0", "0", "0", oid(belt), "0", "0"], [oid(pistol), "0"],
           sorted(oid(r) for r in (rounds, gold_gun, gold_rounds, quest)), None))
    check("and the bars without the set", vitals(v), (HMAX - 5, SMAX - 51))
    v.send("resurrect;res_type=0;")
    v.until(lambda f: f[0] == "lcall", 3)
    leave(v)
    leave(w)

    # === a death to a player =====================================================
    h = Client(connect())
    newcomer(h, CRED["hunter"], "hunter")
    q = Client(connect())
    newcomer(q, CRED["quarry"], "quarry")
    leave(q)
    Q, H = char_id("quarry"), char_id("hunter")
    qkit = {r["type_id"]: r for r in rows(Q).values()}
    q_rounds, q_pistol = qkit[ROUNDS], qkit[PISTOL]
    q_boots = give(Q, KOLONIST_A["boots"], slot=BOOTS)
    q_helm = give(Q, KOLONIST_G["helm"], slot=HEAD)
    q_gun = give(Q, AFRO_GUN)
    q_gold = give(Q, GOLD_GUN)
    # The quarry at Колонист's level (2), so the boots stay on for the body's
    # roll (inventory.over_level_to_bag), and the hunter a level above: then
    # the kill leaves no trophy (trophies.falls, test_trophies), and the bag
    # holds what fell off the body and nothing else.
    leave(h)
    st = accounts.Store(DB)
    st.save_character_state(Q, hp=1, sp=0)
    st.save_stats(Q, [("skill", progression.SHOOTING, 2, 0, progression.skill_xp_max(2))])
    st.save_character_state(Q, level=2)
    st.save_stats(H, [("skill", progression.SHOOTING, 3, 0, progression.skill_xp_max(3))])
    st.save_character_state(H, level=3)
    st.close()
    h = Client(connect())
    come_back(h, CRED["hunter"])

    goto(h, DESERT)
    h.frames(0.5)
    q = Client(connect())
    come_back(q, CRED["quarry"])
    where = goto(q, DESERT)
    got = h.frames(1.5)
    QP = rooms.player_id(Q)
    check("the hunter sees the quarry arrive in the desert",
          [p["newUser"] for p in named(got, "lch") if "newUser" in p], [QP])
    q.frames(0.5)
    desert = world.location(world.location_at(*DESERT))
    spot = next(n for n in progression.hex_neighbours(where, desert.width, desert.height)
                if n not in desert.obstacles)
    h.send("moveTo;path=|%d|%d|;" % (where, spot))
    h.frames(0.5 + mobs.HEX_MS / 1000.0)
    seen_h, seen_q = [], []
    for _ in range(25):
        h.send("ss_use;type=16;obj=x0;target=x1%08x;" % QP)
        seen_h += h.until(lambda f: f[0] in ("caHit", "caMiss", "cmdAck") and
                          (f[0] != "cmdAck" or f[1].get("res") != 0), 3.0)
        seen_q += q.frames(0.3)
        if any(n == "lch" and p.get("dead") == 0 for n, p in seen_q):
            break
    seen_h += h.frames(1.0)
    seen_q += q.frames(0.5)
    check("the quarry falls to the hunter's fists",
          [p for n, p in seen_q if n == "lch" and "dead" in p], [{"dead": 0}])
    check("its client told of the boots and the gun, and of the rounds' new size",
          (removed(seen_q), sizes(seen_q)),
          (sorted(oid(r) for r in (q_boots, q_gun)), [(oid(q_rounds), 13)]))
    check("the hunter sees one bag where the quarry fell",
          [(p["s_status"], p["hex"]) for p in named(seen_h, "ss_loot")], [(1, [where])])

    h.send("ss_create;s_type=0;target=%d;" % where)
    check("the hunter opens it", [p["res"] for p in named(h.frames(), "cmdAck")], [0])
    h.send("ss_get;slot=24;")
    listed = [str(o) for o in named(h.until(lambda f: f[0] == "ss_ack"), "ss_ack")[0]["o_list"]]
    inside = listed[listed.index("0") + 1:]
    st = accounts.Store(DB)
    # The first bag may still be lying in the dump: it lasts LOOT_LIFETIME.
    lying = [r for r in st.items_of(combat.LOOT_OWNER) if r["uniq"] not in ground]
    st.close()
    split = [r for r in lying if r["uniq"] not in (q_boots["uniq"], q_gun["uniq"])]
    check("and finds in it exactly the boots, the gun and seven rounds of a row"
          " of their own", (sorted(inside), [(r["type_id"], r["count"]) for r in split]),
          (sorted(oid(r) for r in lying), [(ROUNDS, 7)]))
    check("which are the quarry's things",
          sorted(r["uniq"] for r in lying if r["uniq"] != split[0]["uniq"]) if split else None,
          sorted((q_boots["uniq"], q_gun["uniq"])))
    check("and no trophy: the hunter stands a level above the quarry",
          [r["uniq"] for r in lying if r["root"] == items.TROPHY], [])
    h.send("ss_upd;s_status=3;obj=x0;param=1;")
    got = h.frames()
    check("takes the lot, and the empty bag is gone",
          [(n, p.get("res", p.get("s_status"))) for n, p in got if n in ("cmdAck", "ss_loot")],
          [("cmdAck", 0), ("ss_loot", 0)])
    mine = rows(H)
    check("the hunter owns them now, the seven rounds included",
          [(u in mine) for u in sorted(r["uniq"] for r in lying)], [True] * len(lying))
    left = rows(Q)
    check("the quarry keeps the gold helmet, the pistol in hand, the gold gun"
          " and thirteen rounds",
          (sorted(left), left.get(q_rounds["uniq"], {}).get("count")),
          (sorted(r["uniq"] for r in (q_rounds, q_pistol, q_helm, q_gold)), 13))
    leave(q)
    q = Client(connect())
    come_back(q, CRED["quarry"])
    wear, hands, bag, _look = carried(q)
    check("and a relog shows the same",
          (wear, hands, bag),
          ([oid(q_helm), "0", "0", "0", "0", "0"], [oid(q_pistol), "0"],
           sorted(oid(r) for r in (q_rounds, q_gold))))
    leave(q)
    leave(h)
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=5)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails or os.environ.get("LAVA_TEST_LOG"):
        fails.append("server log tail:\n" + out[-4000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("death drops OK")
