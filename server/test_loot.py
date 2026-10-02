"""Kill a man and find more than rounds in his bag.

The owner's complaint (2026-09-24): «от мобов падают только патроны, хотя
раньше падал и лут». It was not a regression in the code -- mobs.loot_for
never read the loot table at all. It gave an animal its parts, an armed man
a handful of his rounds and nothing else, anyone else a cigarette, and the
wiki's table (data/loot_wiki.json) lay beside it with every item unresolved.
So a man's bag held rounds and only rounds.

Now a man carries a piece of the original's own junk of his level
(TrashLoot_LvL_*) whether or not he has a gun, and his kind's table is rolled
on top: the wiki's rows resolved to item types through the same linker the
stalls use, and the valuable of his level. Premium items stay out of the game
on both paths.

In process: the tables, the rates the dice give against the rates the table
states (a fixed seed; the cap of two per kill is worked out exactly), no
premium, quest or unpriced thing in any table of any creature, and the whole
road from a corpse to a bag on the ground through RoomCombat with a real
database. On a socket: location 100, the dump -- a knife against the bum
standing at 4363, a level-3 m05_bich with a knife of his own and no rounds to
leave, and his bag opened and emptied. Before this change it held one
cigarette. And before any of it, the server clears the rows of the bags the
last run left on the ground, which no room could ever show again.
"""
import asyncio
import json
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

sys.path.insert(0, HERE)
import accounts      # noqa: E402
import combat        # noqa: E402
import inventory     # noqa: E402
import items         # noqa: E402
import mobs          # noqa: E402
import names         # noqa: E402
import progression   # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

DUMP = 100
BUM_HOME = 4363             # an m05_bich of the dump, clear of the dogs
BUM = 411                   # m05_bich: level 3, a knife, no table rows
COURIER = 17                # m05_BanditCourier_lvl2: a pistol
NEGODYAI = 693              # m05_negodyai: the wiki's "Негодяй", six rows
COLONIST = 258              # nc_BanditRaider_lvl0: lists the premium Аптечка «Мини»
COLONIST_2 = 265            # nc_BanditAssaultGunner_lvl2: lists ValuableLoot_LvL_2
DOG = 82
KNIFE = 6229                # knife_lvl1_A, a stall's first blade
CIGARETTE = mobs.FALLBACK_LOOT

from testkit import check, fails  # noqa: E402


cat = items.catalogue()
by_name = {}
for _t, (_r, _n) in sorted(cat.items()):
    by_name.setdefault(_n, _t)
TRASH = [by_name["TrashLoot_LvL_%d" % k] for k in range(25)]
VALUABLE = [by_name["ValuableLoot_LvL_%d" % k] for k in range(25)]

# Read through getattr: on the code before this change these do not exist,
# and the suite has to say what is missing rather than stop at the first one.
loot_table = getattr(mobs, "loot_table", lambda type_id: [])
roll_table = getattr(mobs, "roll_table", lambda type_id, rng: [])
MAX_DROPS = getattr(mobs, "MAX_DROPS", None)


# --- the premium filter has no false positives among what drops ----------------------
# items.premium reads the internal name: (?:^|_)(?:P|pm)(?:_|$). Nothing a corpse
# carries may be taken for premium by it, and the one premium item the wiki
# lists as loot must be.
carried_kinds = set(TRASH + VALUABLE + [CIGARETTE])
for _word, _types in mobs.ANIMAL_LOOT:
    carried_kinds.update(_types)
for _cls, _gun in mobs.WEAPON_ITEM.items():
    _si = items.params_of(_gun) or {}
    carried_kinds.update((_si.get("comp_array") or [])[:1])
check("nothing a body carries reads as premium",
      sorted(t for t in carried_kinds if items.premium(t)), [])
check("every piece of junk has a name the client already holds",
      [t for t in TRASH + VALUABLE if not names.known(items.STRING_ID_OFFSET + t)], [])
# Every man of level 2 to 4 carries TrashLoot_LvL_2, and the original's text
# has no row for it: its name is the wiki page's title, whose "(trash)" only
# tells it apart from another page of the same name.
check("the level-2 junk is a plastic bottle, not a wiki page's title",
      names.ALL.get(items.STRING_ID_OFFSET + TRASH[2]), "Пластиковая бутылка")
check("and no name of the junk or the valuables carries the page's tag",
      [t for t in TRASH + VALUABLE
       if "(trash)" in names.ALL.get(items.STRING_ID_OFFSET + t, "")], [])
check("the cigarette a creature with no parts of its own leaves reads in Russian",
      names.ALL.get(items.STRING_ID_OFFSET + CIGARETTE), "Сигарета")
MINI = items.resolve_title("Аптечка «Мини»")
check("the wiki's Аптечка «Мини» is a premium medicine",
      (len(MINI), all(items.premium(t) for t in MINI)), (1, True))

# --- the tables --------------------------------------------------------------------
with open(os.path.join(os.path.dirname(HERE), "data", "loot_wiki.json"), encoding="utf-8") as fh:
    WIKI = json.load(fh)
DESIGN = WIKI["design"]
check("at most as many table drops a kill as the file's design says",
      MAX_DROPS, DESIGN["max_drops_per_kill"])
col = loot_table(COLONIST)
col_types = [t for t, _c, _v in col]
check("the colonist's table resolves the wiki's rows: Консервная банка at the Обычный rate",
      [(t, c) for t, c, _v in col if t == TRASH[0]], [(TRASH[0], DESIGN["tiers"]["Обычный"]["chance"])])
check("and leaves out the premium medicine the wiki lists for it",
      [t for t in col_types if t in MINI], [])
neg = loot_table(NEGODYAI)
check("the Негодяй's table: the medicine and his level's valuable, then the wiki's junk",
      [(t, c, v) for t, c, v in neg],
      [(6055, 0.06, True), (VALUABLE[3], 0.06, True),
       (TRASH[1], 0.3, False), (TRASH[4], 0.3, False),
       (TRASH[7], 0.3, False), (TRASH[9], 0.3, False)])
check("a dog rolls for nothing its body does not already carry", loot_table(DOG), [])
# The colonists' wiki list names their own level's valuable among its
# ordinary rows. The camp's page wins over the every-man rule: the better
# chance, and the tier that came with it, so it rolls in its place among the
# ordinary rows rather than first (mobs.loot_table says why).
check("a colonist's own valuable, listed among the camp's ordinary rows, is "
      "one of them",
      [(c, v) for t, c, v in loot_table(COLONIST_2) if t == VALUABLE[2]],
      [(DESIGN["tiers"]["Обычный"]["chance"], False)])

tiers = {v["chance"] for v in DESIGN["tiers"].values()}
# The owner's own rows (data/loot_manual.json: the Nubian mine's marauders)
# carry the chances he set, which only those rows may have.
with open(os.path.join(os.path.dirname(HERE), "data", "loot_manual.json"), encoding="utf-8") as fh:
    MANUAL = json.load(fh)["by_type"]
wrong = []
for tid in mobs.TYPES:
    own = {(int(r["type"]), r["chance"]) for r in MANUAL.get(str(tid), [])}
    for t, chance, _v in loot_table(int(tid)):
        si = items.params_of(t) or {}
        if (items.premium(t) or si.get("quest") or si.get("cost", 0) <= 0
                or (chance not in tiers and (t, chance) not in own)
                or not names.known(items.STRING_ID_OFFSET + t)):
            wrong.append((int(tid), t))
check("no table of any creature holds a premium, quest or unpriced thing, "
      "or one at a rate the design does not have", wrong, [])
check("and there are tables at all", sum(1 for tid in mobs.TYPES if loot_table(int(tid))) > 1000, True)


# --- the rates ---------------------------------------------------------------------
def kept_rates(rows, cap):
    """The chance each row ends up in the bag: its own, times the chance that
    fewer than `cap` rows before it came up (valuables roll first)."""
    dist = [1.0] + [0.0] * cap           # dist[k]: k kept so far
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
rng = random.Random(20260924)
seen = {}
most = 0
for _ in range(N):
    got = roll_table(NEGODYAI, rng)
    most = max(most, len(got))
    for t, _n in got:
        seen[t] = seen.get(t, 0) + 1
off = []
for (t, p, _v), want in zip(neg, kept_rates(neg, MAX_DROPS or 2)):
    rate = seen.get(t, 0) / float(N)
    sigma = (want * (1 - want) / N) ** 0.5
    if abs(rate - want) > 4.5 * sigma:
        off.append((t, round(rate, 4), round(want, 4)))
check("each row of the Негодяй's table drops at the table's rate", (bool(neg), off), (True, []))
check("and never more than the cap in one kill", most <= (MAX_DROPS or 2) and most > 0, True)

# What the body carries, whatever the dice.
rng = random.Random(7)
bum = [mobs.loot_for(mobs.stats(BUM), rng) for _ in range(300)]
check("an unarmed man always carries a piece of junk of his level or up to two below",
      all(any(t in TRASH[1:4] for t, _n in drop) for drop in bum), True)
check("and no longer a cigarette", any(t == CIGARETTE for drop in bum for t, _n in drop), False)
rounds = (items.params_of(mobs.stats(COURIER).weapon_type_id) or {}).get("comp_array", [0])[0]
courier = [mobs.loot_for(mobs.stats(COURIER), rng) for _ in range(300)]
check("a gunman leaves his rounds and a piece of junk as well, every time",
      all({t for t, _n in d} & {rounds} and {t for t, _n in d} & set(TRASH[0:3])
          for d in courier), True)
dog = [mobs.loot_for(mobs.stats(DOG), rng) for _ in range(300)]
check("a dog is what it was: its meat, and maybe a fang or a skin",
      (all(drop[0] == (216, 1) for drop in dog),
       sorted({t for drop in dog for t, _n in drop})), (True, [216, 217, 218]))


# --- a corpse's bag, through RoomCombat and a real database -----------------------------
class _Room(object):
    def __init__(self):
        self.loc = world.location(DUMP)
        self.npcs = {}
        self.players = {}
        self.ws = False

    def broadcast(self, frame, exclude=None):
        pass


DB = os.path.join(tempfile.mkdtemp(), "loot.db")
accounts.DB_PATH = DB


async def _bags():
    store = accounts.Store(DB)
    rc = combat.RoomCombat(_Room(), store)
    combat.RNG.seed(11)
    kinds = {}
    kills = 400
    for i in range(kills):
        mob = mobs.Mob(i + 1, COLONIST, 10 + 3 * i)
        rc.corpse_gone(mob, [])
        for uniq in rc.loot[mob.cell].uniqs:
            row = store.item(uniq)
            kinds[row["type_id"]] = kinds.get(row["type_id"], 0) + 1
            if row["root"] != items.root_of(row["type_id"]):
                fails.append("bag row %r has the wrong root" % row)
    for bag in rc.loot.values():
        if bag.expiry is not None:
            bag.expiry.cancel()
    store.close()
    return kinds, kills


kinds, kills = asyncio.run(_bags())
check("a colonist's bags hold junk beyond what he carried",
      sum(n for t, n in kinds.items() if t in col_types) > kills, True)
check("and not one premium thing in %d bags" % kills,
      sorted(t for t in kinds if items.premium(t)), [])


# --- the server ------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
SDB = os.path.join(tempfile.mkdtemp(), "loot_srv.db")
accounts.DB_PATH = SDB
_store = accounts.Store(SDB)
_store.register("scavenger", "secret")
# A bag somebody's last run left on the ground: rows owned by nobody that no
# room will ever show again. The server clears them as it starts.
LEFT_OUT = [_store.create_item(combat.LOOT_OWNER, t, items.root_of(t))["uniq"]
            for t in (TRASH[0], VALUABLE[0])]
# And a thing somebody owns, which must stay where it is.
KEPT = _store.create_item(999, TRASH[1], items.root_of(TRASH[1]))["uniq"]
_store.close()
CRED = accounts.credential("scavenger", "secret")

# Nothing respawns while the scene lasts, the AP bar never throttles, the
# dice are seeded -- though what is checked holds for any seed.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=SDB,
           LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730",
           LAVA_RESPAWN="600",
           LAVA_AP_REGEN="25", LAVA_SEED="7")
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


def only(frames, *names_):
    return [(n, p) for n, p in frames if n in names_]


def oids(p):
    return [str(x) for x in p["o_list"]]


def entity(eid):
    return "x1%08x" % eid


def login(c, first=False):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@scavenger@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")


def cell_of(c, mob, home):
    for n, p in reversed(c.seen):
        if n == "userMove" and p.get("id") == mob:
            return p["path"][-1]
    return home


try:
    # --- a character with a blade and the hand to use it: test_war_state's -----------
    c = Client(connect())
    login(c, first=True)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    store = accounts.Store(SDB)
    check("the bag the last run left on the ground is gone from the database",
          [store.item(u) for u in LEFT_OUT], [None, None])
    check("and nothing anybody owns went with it",
          (store.item(KEPT) or {}).get("char_id"), 999)
    char_id = store.character_by_name("scavenger")["id"]
    ch = progression.Character.load(store, char_id)
    ch.skill[progression.MELEE] = [20, 0, progression.skill_xp_max(20)]
    ch.recalc()
    ch.hp = ch.sp = None
    ch.save(store)
    for row in store.items_of(char_id):
        if row["slot"] == inventory.PRIMARY:
            store.update_item(row["uniq"], slot=inventory.BAG)
    fields = inventory.new_fields(KNIFE)
    root = fields.pop("root")
    fields["slot"] = inventory.PRIMARY
    knife = inventory.oid_of(store.create_item(char_id, KNIFE, root, **fields))
    store.close()

    c = Client(connect())
    login(c)
    c.send("userMsg;entry=@/goto %d@;group=0;" % DUMP)
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    arrival = c.frames(2)
    pos = named(arrival, "lenter")[0]["pos"]
    spawns = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    bum = spawns[BUM_HOME]

    # --- into the bum's reach and nobody else's ---------------------------------------
    loc = world.location(DUMP)
    W = loc.width
    others = [(cell, mobs.stats(t)) for cell, t in loc.spawns
              if cell != BUM_HOME and mobs.stats(t).can_attack]
    spot = lambda cell: (
        mobs.hex_distance(cell, BUM_HOME, W) <= mobs.stats(BUM).aggro - 0.5
        and all(mobs.hex_distance(cell, o, W) > st.aggro + 1.5 for o, st in others))
    path = mobs.find_path(loc, pos, spot, {BUM_HOME})
    check("there is a cell within the bum's reach only", path is not None, True)
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    pos = path[-1]
    c.until(lambda f: f[0] == "lch" and f[1].get("enemy") == bum, 6)

    dead = None
    for attempt in range(120):
        if mobs.adjacent(pos, cell_of(c, bum, BUM_HOME), loc):
            c.send("ss_use;type=16;obj=x%s;target=%s;" % (knife, entity(bum)))
            got = c.until(lambda f: f[0] == "c_ap"
                          or (f[0] == "cmdAck" and f[1]["res"] != 0), 3)
            got += c.frames(0.2)
        else:
            got = c.frames(0.4)
        if [p for n, p in got if n == "lch" and p.get("dead") == bum]:
            dead = got
            break
    check("the bum dies to the knife", dead is not None, True)
    where = cell_of(c, bum, BUM_HOME)
    got = c.until(lambda f: f[0] == "ss_loot", 5)
    check("his bag lies where he fell",
          named(got, "ss_loot"), [{"s_status": 1, "hex": [where]}])

    # --- the bag ---------------------------------------------------------------------
    c.send("ss_create;s_type=0;target=%d;" % where)
    check("the bag opens", only(c.frames(), "cmdAck"), [("cmdAck", {"res": 0})])
    c.send("ss_get;slot=24;")
    lst = oids(named(c.frames(), "ss_ack")[0])
    loot = lst[lst.index("0") + 1:]
    kinds = sorted({inventory.parse_oid(o)[1] for o in loot})
    check("a piece of junk of his level or up to two below is in it -- "
          "not the cigarette alone", bool(set(kinds) & set(TRASH[1:4])), True)
    check("and nothing premium", [t for t in kinds if items.premium(t)], [])
    c.send("ss_upd;s_status=3;obj=x0;param=1;")
    got = c.frames()
    check("take all: ack, and the empty bag vanishes",
          only(got, "cmdAck", "ss_loot"),
          [("cmdAck", {"res": 0}), ("ss_loot", {"s_status": 0, "hex": [where]})])
    c.send("ss_get;slot=8;")
    check("everything he left is in the player's bag",
          all(o in oids(named(c.frames(), "ss_ack")[0]) for o in loot), True)
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
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
print("loot OK")
