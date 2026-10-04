"""What the gear adds: items' own bonus_* and the sets among them.

In process first. inventory.gear_bonus against the card: CharInterface's
showOD and showKrit are transcribed below as they stand, quirks included,
and a few thousand random outfits have to come out of both with the same
action points, crit and anti-crit, because the card is where the player
reads them. Then the sets by hand -- two to five pieces, a broken one, one
in the belt slot -- and the Character that carries the sum: f_* against
a_*, the maxima, the bare ap_max rp_info keeps for the card to add to. Then
Inventory.wear breaking a piece of a set, on a stand-in session.

Then one server over the socket: a character of the set's level (8) puts
on Налетчик (A) piece by piece, and after each ss_move the rp_info and usrUp that follow carry
exactly what the tables say; taking a piece off gives it back, a broken
piece does not count towards the set, a belt changes nothing, and after a
relog lenter's amax holds the set's action points.

    LAVA_RES=.../lava/res python3 server/test_gear.py
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

DB = os.path.join(tempfile.mkdtemp(), "gear.db")
os.environ["LAVA_DB"] = DB

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import progression  # noqa: E402
import sets  # noqa: E402
from inventory import ARMOR, BAG, BELT, BOOTS, CAMO, HEAD, LEGS, PRIMARY, SECONDARY  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


SLOT = {"helm": HEAD, "shirt": CAMO, "armor": ARMOR, "pants": LEGS, "boots": BOOTS}
# Локсли's ladder (data/sets.json), the A of each rung.
NAL8 = 11185           # Налетчик: bonuses at 2, 3, 4 and 5 pieces, attributes among them
STR4 = 11191           # Странник: likewise, other numbers
KOL2 = 11167           # Колонист: five pieces or nothing
BS0 = 11218            # Беженец: no set bonus at all
PIECES = list(sets.SETS[NAL8]["members"].items())      # helm, shirt, armor, pants, boots
BELT_BARE = 3577       # belt_assault_rifles: no bonus of its own
BELT_STR = 3722        # a belt with +3 strength of its own
AXE = 3034             # Топор: +3 strength, +2 agility, crit 10, a skill, two specs
PADDLE = 4853          # a cold arm with crit 5 and anti-crit 25
AK = 6478              # a firearm with anti-crit 1000
SALUS = 4917           # Салюс: +35 health -- for bonus_act_time once taken
ALPHA = 3115           # Альфа-реагент I: crit 10 -- likewise

_uniq = [0]


def row(type_id, slot, brk=100):
    _uniq[0] += 1
    return dict(uniq=_uniq[0], type_id=type_id, root=items.root_of(type_id), slot=slot, brk=brk)


# --- the card, transcribed ---------------------------------------------------
# CharInterface.as:135-183 and :184-417 with AS2's own semantics: an empty
# slot's item is undefined (None), getProp on it undefined, undefined equal
# only to undefined, "if(x && !isNaN(x))" for an item's number. A set's
# numbers are what ss_si_set brings (sets.frame); a set that was never asked
# for (typeID 0 or undefined, SetManager.requestSI) has none.

def prop(item, key):
    return None if item is None else item.get(key)


def item_number(item, key):
    v = prop(item, key)
    return v if v else 0


def num_of_set_item(eq, st):
    """PersEquip.getNumOfSetItem: head, armour, shirt, legs, boots."""
    n = 0
    for name in ("head", "armor", "camouflage", "legs", "boots"):
        it = eq[name]
        if prop(it, "setTypeID") == st and (prop(it, "__break") or 0) > 0:
            n += 1
    return n


def bonus_from_set(eq, name, item):
    st = prop(item, "setTypeID")
    frame = sets.frame(st) if st else {}
    n = num_of_set_item(eq, st)
    total = 0
    for k in range(2, 7):
        if n >= k:
            v = frame.get("bonus_%d%s" % (k, name))
            if v:
                total += v
    return total


def card_od(eq):
    od = 0
    for name in ("primary", "secondary", "head", "armor", "camouflage", "belt", "legs", "boots"):
        od += item_number(eq[name], "bonus_od")
    S = {k: prop(eq[k], "setTypeID") for k in eq}
    od += bonus_from_set(eq, "_od", eq["head"])
    if S["armor"] != S["head"]:
        od += bonus_from_set(eq, "_od", eq["armor"])
    if S["camouflage"] != S["armor"] and S["camouflage"] != S["head"]:
        od += bonus_from_set(eq, "_od", eq["camouflage"])
    if S["belt"] != S["camouflage"] and S["belt"] != S["armor"] and S["belt"] != S["head"]:
        od += bonus_from_set(eq, "_od", eq["belt"])
    if (S["legs"] != S["camouflage"] and S["legs"] != S["armor"] and S["legs"] != S["head"]
            and S["legs"] != S["belt"]):
        od += bonus_from_set(eq, "_od", eq["legs"])
    if (S["boots"] != S["legs"] and S["boots"] != S["camouflage"] and S["boots"] != S["armor"]
            and S["boots"] != S["head"] and S["boots"] != S["belt"] and S["boots"] != S["legs"]):
        od += bonus_from_set(eq, "_od", eq["boots"])
    return od


def card_krit(eq):
    """The bonus part of showKrit: (crit, anti-crit) on top of the formula."""
    cp = ce = 0
    for name in ("primary", "secondary", "head", "armor", "camouflage", "belt", "legs", "boots"):
        cp += item_number(eq[name], "bonus_cp")
        ce += item_number(eq[name], "bonus_ce")
    h, a, c, b, l, bo = (eq[k] for k in ("head", "armor", "camouflage", "belt", "legs", "boots"))
    S = lambda it: prop(it, "setTypeID")  # noqa: E731
    cp += bonus_from_set(eq, "_cp", h)
    ce += bonus_from_set(eq, "_ce", h)
    if S(a) != S(h):
        cp += bonus_from_set(eq, "_cp", a)
        ce += bonus_from_set(eq, "_ce", a)
    if S(c) != S(a) and S(c) != S(h):
        cp += bonus_from_set(eq, "_cp", c)
        ce += bonus_from_set(eq, "_ce", c)
    if S(b) != S(c) and S(b) != S(a) and S(b) != S(h):
        cp += bonus_from_set(eq, "_cp", l)          # sic: the legs, from the belt's step
        ce += bonus_from_set(eq, "_ce", l)
    if S(l) != S(c) and S(l) != S(a) and S(l) != S(h) and S(l) != S(b):
        cp += bonus_from_set(eq, "_cp", l)
        ce += bonus_from_set(eq, "_ce", l)
    if S(bo) != S(l) and S(bo) != S(c) and S(bo) != S(a) and S(bo) != S(h) and S(bo) != S(b):
        cp += bonus_from_set(eq, "_cp", bo)
        ce += bonus_from_set(eq, "_ce", bo)
    return cp, ce


CARD_SLOT = {HEAD: "head", CAMO: "camouflage", ARMOR: "armor", BELT: "belt", LEGS: "legs",
             BOOTS: "boots", PRIMARY: "primary", SECONDARY: "secondary"}


def card_equipment(rows):
    """The client's picture of these rows: each item as the frames built it."""
    eq = {name: None for name in CARD_SLOT.values()}
    for r in rows:
        if r["slot"] not in CARD_SLOT:
            continue
        si = items.params_of(r["type_id"])
        it = {k: si[k] for k in ("bonus_od", "bonus_cp", "bonus_ce") if k in si}
        if r["root"] == items.WEAR:
            it["setTypeID"] = si["set_type"]
        it["__break"] = r["brk"]
        eq[CARD_SLOT[r["slot"]]] = it
    return eq


# --- random outfits: the server's od/cp/ce are the card's ---------------------
print("the card")
CHOICES = {slot: [None] + [(sets.SETS[st]["members"][name], brk)
                           for st in (NAL8, STR4, KOL2, BS0) for brk in (100, 0)]
           for name, slot in SLOT.items()}
CHOICES[BELT] = [None, (BELT_BARE, 100), (BELT_STR, 100), (BELT_STR, 0)]
CHOICES[PRIMARY] = [None, (AXE, 100), (PADDLE, 100), (AK, 100)]
CHOICES[SECONDARY] = [None, (AK, 100), (PADDLE, 0)]
rng = random.Random(20260923)
differ = []
for _ in range(4000):
    rows = []
    for slot, options in CHOICES.items():
        pick = rng.choice(options)
        if pick is not None:
            rows.append(row(pick[0], slot, pick[1]))
    # ...and a whole set in the bag now and then, which counts for nothing.
    if rng.random() < 0.3:
        rows += [row(t, BAG) for t in sets.SETS[NAL8]["members"].values()]
    b = inventory.gear_bonus(rows)
    again = inventory.card_repeat(rows)
    eq = card_equipment(rows)
    shown = (b["od"], (b["cp"] + again[0], b["ce"] + again[1]))
    if shown != (card_od(eq), card_krit(eq)):
        differ.append(([(r["type_id"], r["slot"], r["brk"]) for r in rows],
                       shown, (card_od(eq), card_krit(eq))))
check("4000 random outfits: action points, and crit and anti-crit with the card's repeat, "
      "as the card adds them", differ[:3], [])

full = [row(t, SLOT[name]) for name, t in PIECES]
f8 = sets.frame(NAL8)
set_cp = sum(v for k, v in f8.items() if k.endswith("_cp"))
set_ce = sum(v for k, v in f8.items() if k.endswith("_ce"))
own_cp = sum(items.params_of(r["type_id"]).get("bonus_cp", 0) for r in full)
own_ce = sum(items.params_of(r["type_id"]).get("bonus_ce", 0) for r in full)
b = inventory.gear_bonus(full)
check("the whole of Налетчик: the gear's crit and anti-crit count the set once",
      (b["cp"], b["ce"]), (own_cp + set_cp, own_ce + set_ce))
check("  ..and no belt: the card's legs step gives it a second time, kept apart",
      inventory.card_repeat(full), (set_cp, set_ce))
b = inventory.gear_bonus(full[1:])
check("without the helmet the belt's step finds nothing to differ from: no repeat",
      (b["cp"], inventory.card_repeat(full[1:])),
      (sum(items.params_of(r["type_id"]).get("bonus_cp", 0) for r in full[1:])
       + sum(sets.SETS[NAL8]["bonus"][k]["cp"] for k in sets.SETS[NAL8]["bonus"] if k <= 4),
       (0, 0)))

# Whose rolls take the repeat: the firearm's, whose figure the card shows,
# and nobody else's -- the card shows no melee crit, and nothing at all
# without a firearm in hand.
once = progression.Character()
once.set_gear(inventory.gear_bonus(full))
twice = progression.Character()
twice.set_gear(inventory.gear_bonus(full), inventory.card_repeat(full))
pistol_once = progression.crit_chance(once, items.PISTOL)
check("a pistol's crit and anti-crit: the set twice, as the card reads",
      progression.crit_chance(twice, items.PISTOL),
      (pistol_once[0] + set_cp, pistol_once[1] + set_ce))
check("a blade's crit and the anti-crit against one: the set once",
      (combat.melee_crit(twice, None), combat.melee_crit_evade(twice)),
      (combat.melee_crit(once, None), combat.melee_crit_evade(once)))


class _Holding(object):
    """A session for Fighter.crit_evade_ranged: a character and a hand."""

    def __init__(self, ch, hand):
        self.char = ch
        self.inv = type("Hand", (), {"in_slot": lambda _self, _slot: hand})()

    def character(self):
        return self.char


GUN = {"root": items.FIRE_ARM, "type_id": inventory.STARTER_PISTOL}
check("the anti-crit of a target with no firearm: the pistol row, the set once",
      combat.Fighter(_Holding(twice, None)).crit_evade_ranged(), pistol_once[1])
check("  ..and with a pistol in hand: the card's figure, the set twice",
      combat.Fighter(_Holding(twice, GUN)).crit_evade_ranged(), pistol_once[1] + set_ce)

# --- sets by hand ------------------------------------------------------------------
print()
print("sets")


def expected(worn, st=NAL8):
    """The tables read directly: every item's own numbers, then each K up
    to the count of this set's unbroken pieces in the five slots."""
    out = dict(hp=0, st=0, od=0, attribs=[0] * 5)
    for r in worn:
        si = items.params_of(r["type_id"])
        for key in ("hp", "st", "od"):
            out[key] += si.get("bonus_" + key, 0)
        a = inventory.unpacked(si.get("bonus_attribs_m"), si.get("bonus_attribs"), 5)
        out["attribs"] = [x + y for x, y in zip(out["attribs"], a)]
    n = sum(1 for r in worn if r["slot"] in inventory.SET_SLOTS and r["brk"] > 0
            and sets.set_of(r["type_id"]) == st)
    for k, bonus in sets.SETS[st]["bonus"].items():
        if k <= n:
            for key in ("hp", "st", "od"):
                out[key] += bonus[key]
            out["attribs"] = [x + y for x, y in zip(out["attribs"], bonus["attribs"])]
    return out


def got(worn):
    b = inventory.gear_bonus(worn)
    return dict(hp=b["hp"], st=b["st"], od=b["od"], attribs=b["attribs"])


for n in range(1, 6):
    check("%d piece(s) of Налетчик: own numbers and every K up to %d" % (n, n),
          got(full[:n]), expected(full[:n]))
check("  ..which at five is two strength, an agility and a constitution",
      got(full)["attribs"], [2, 1, 1, 0, 0])
check("  ..and at two nothing to an attribute yet", got(full[:2])["attribs"], [0] * 5)
broken = [dict(r, brk=0) if r["slot"] == ARMOR else r for r in full]
check("a broken armour: its own numbers stay, the set counts four",
      got(broken), expected(broken))
check("  ..which is not what five would give", got(broken) != got(full), True)
check("  ..and the same as four whole pieces plus the armour's own",
      got(broken)["attribs"], got([r for r in full if r["slot"] != ARMOR])["attribs"])
on_belt = full[:4] + [dict(full[4], slot=BELT)]
check("the fifth piece in the belt slot does not count towards the set",
      got(on_belt)["attribs"], got(full[:4])["attribs"])
check("  ..though a belt's own bonus does: +3 strength",
      got(full[:4] + [row(BELT_STR, BELT)])["attribs"],
      [a + b for a, b in zip(got(full[:4])["attribs"], [3, 0, 0, 0, 0])])
check("the whole set in the bag: nothing", inventory.gear_bonus(
    [dict(r, slot=BAG) for r in full]), sets.zero())
mixed = full[:2] + [row(sets.SETS[STR4]["members"][n], SLOT[n]) for n in ("armor", "pants", "boots")]


def set_part(st, n, key):
    return sum(b[key] for k, b in sets.SETS[st]["bonus"].items() if k <= n)


check("two of one set and three of another: each set by its own count",
      got(mixed)["st"], sum(items.params_of(r["type_id"]).get("bonus_st", 0) for r in mixed)
      + set_part(NAL8, 2, "st") + set_part(STR4, 3, "st"))
axe = inventory.gear_bonus([row(AXE, PRIMARY)])
check("a weapon in the hand lends its own: the axe's strength, agility, skill, specs",
      (axe["attribs"], axe["skills"][:2], sum(axe["specs"]) > 0, axe["cp"]),
      ([3, 2, 0, 0, 0], [2, 0], True, 10))
check("a medicine in the hand lends nothing: its bonus is what it does once taken",
      inventory.gear_bonus([row(SALUS, PRIMARY), row(ALPHA, SECONDARY)]), sets.zero())
check("a bonus list is read the way Item.parseNeedBonus reads it",
      inventory.unpacked(67, [3, 3, 1], 15), [3, 3, 0, 0, 0, 0, 1] + [0] * 8)

# --- the Character that carries it ----------------------------------------------
print()
print("the character")
ch = progression.Character()
b = sets.zero()
b.update(hp=10, st=20, od=7, cp=3, ce=4, attribs=[1, 0, 1, 0, 0], skills=[0, 2, 0, 0, 0])
changed = ch.set_gear(b)
check("what moved is reported per index, ready for a partial rp_info",
      changed, {"attribs": {0, 2}, "skills": {1}, "specs": set()})
check("health: 4*strength + 20*constitution + the gear's", ch.hp_max, 4 * 6 + 20 * 6 + 10)
check("stamina likewise", ch.sp_max, 4 * 5 + 20 * 6 + 20)
p = ch.rp_info()
check("rp_info: the base in a_attribs, with the gear in f_attribs",
      (p["a_attribs"], p["f_attribs"]), ([5] * 5, [6, 5, 6, 5, 5]))
check("  ..the skill's too", (p["a_skills"][1], p["f_skills"][1]), (0, 2))
check("  ..and ap_max bare: the card adds the gear's od itself", p["ap_max"], 50)
check("the ceiling the bar and the fight use is the card's ОД", ch.ap_ceiling, 57)
cp, ce = progression.crit_chance(ch, progression.PISTOL)
check("pistol crit: the card's formula and the gear's cp/ce on top",
      (cp, ce), ((5 * 8 + 5 * 4) / 4 + 2 / 4 - 1 + 3, (5 + 5) / 2 + 2 / 2 - 1 + 4))
check("the same gear again moves nothing", ch.set_gear(b), {"attribs": set(), "skills": set(), "specs": set()})
check("and none at all gives it back", (ch.set_gear(sets.zero())["attribs"], ch.hp_max, ch.ap_ceiling),
      ({0, 2}, 120, 50))

# --- a piece breaking, on a stand-in session ---------------------------------------
print()
print("breaking")
store = accounts.Store(DB)
acc, _err = store.register("breaker", "secret")
cid, _slot = store.create_character(acc, "Ломатель", 0, 1)


class Stand:
    """The parts of server.Session that Inventory.refresh_gear touches."""

    def __init__(self):
        self.char_id = cid
        self.pid = 999
        self.room = None
        self.char = progression.Character.load(store, cid)
        self.frames = []
        # The real one: its ap_max is what refresh_gear holds the pool to.
        self.combat = combat.Fighter(self)

    def character(self):
        return self.char

    def send(self, *cmd, **params):
        self.frames.append((cmd[0], params))

    def push_stats(self, **groups):
        self.send("rp_info", **self.char.rp_info(**groups))

    def push_vitals(self):
        self.send("usrUp", id=0, **self.char.vitals())


worn = {}
for name, t in PIECES:
    f = inventory.new_fields(t)
    worn[name] = store.create_item(cid, t, f["root"], slot=SLOT[name],
                                   brk=1 if name == "boots" else f["brk"],
                                   max_break_cur=f["max_break_cur"])
stand = Stand()
inv = inventory.Inventory(stand, store)
stand.combat.ap = 1000
inv.refresh_gear(push=False)
check("counted at load, nothing sent", (stand.frames, stand.char.bonus_attribs), ([], [2, 1, 1, 0, 0]))
check("action points held to the new ceiling", stand.combat.ap, stand.char.ap_ceiling)
# In a location, as lenter leaves it: the bar's ceiling sent, the pool full.
amax = stand.combat.amax_sent = stand.combat.ap = stand.char.ap_ceiling
hp_full = stand.char.hp = stand.char.hp_max
sp_full = stand.char.sp = stand.char.sp_max
inv.wear(worn["boots"], 1)
names_sent = [n for n, _p in stand.frames]
check("the boots break: their break, then the attributes that fell, then the bars",
      names_sent, ["ss_di_wear", "rp_info", "usrUp"])
rp = dict(stand.frames[1][1])
check("  ..strength and constitution, the five-piece line's",
      (rp["f_attribs_mask"], rp["f_attribs"]), (1 | 4, [6, 5]))
left = [dict(r, brk=0) if n == "boots" else r for n, r in worn.items()]
want = expected(left)
v = stand.frames[2][1]
check("  ..health down to four pieces' worth, and the current value with it",
      (v["hmax"], v["hcur"]), (4 * (5 + want["attribs"][0]) + 20 * (5 + want["attribs"][2]) + want["hp"],) * 2)
check("  ..while the saved health and stamina stay: vitals holds them to the maxima",
      (stand.char.hp, stand.char.sp), (hp_full, sp_full))
stand.frames = []
inv.wear(worn["helm"], 1)
check("a worn piece that does not break sends only its break",
      [n for n, _p in stand.frames], ["ss_di_wear"])
store.update_item(worn["boots"]["uniq"], brk=100)
stand.frames = []
inv.refresh_gear()
v = [p for n, p in stand.frames if n == "usrUp"]
check("the boots mended: the health and stamina they took off come back, not a point lost",
      [(p["hcur"], p["hmax"], p["scur"], p["smax"]) for p in v],
      [(hp_full, hp_full, sp_full, sp_full)])
# Two pieces short of the three that carry Налетчик's od: the card's ОД falls
# at once, the bar's ceiling (and so the fight's) only at the next lenter.
for name in ("armor", "pants", "boots"):
    store.update_item(worn[name]["uniq"], brk=0)
stand.frames = []
inv.refresh_gear()
check("three pieces broken: the set's od is gone from the card's ОД",
      stand.char.ap_ceiling, amax - sets.SETS[NAL8]["bonus"][3]["od"])
check("  ..but the fight keeps the ceiling lenter sent, and the pool with it",
      (stand.combat.ap_max, stand.combat.ap), (amax, amax))
check("  ..so no c_ap goes out to cut the bar", [n for n, _p in stand.frames if n == "c_ap"], [])
store.close()

# --- over the socket ------------------------------------------------------------------
print()
print("on the wire")


def free_port():
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]


PORT = free_port()
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("wearer", "secret")
_store.close()
CRED = accounts.credential("wearer", "secret")
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_POLICY_PORT="0")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while True:
            left = deadline - time.time()
            if left <= 0:
                break
            self.s.settimeout(left)
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def until(self, name, timeout=15):
        got = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            got += self.frames(0.3)
            if any(n == name for n, _p in got):
                return got + self.frames(0.3)
        return got


def named(frames, name):
    return [p for n, p in frames if n == name]


def enter(c, first=False):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@wearer@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.until("lcall")
    c.send("lenter;accept=1;")
    return named(c.until("lenter"), "lenter")[0]


# Налетчик asks for level 8 of whoever wears it (inventory.py, "the level"),
# so the wearer is at 8 once the outfit is in the bag, and the card's base is
# a level-8 one: constitution follows the best skill, ОД 50 + 5 a level.
LEVEL = max(inventory.item_level(t) for _name, t in PIECES)
BASE = [5, 5, int(5 + 0.75 * LEVEL), 5, 5]
AP_BASE = 50 + 5 * LEVEL


def card(worn):
    """What the character's card and bars must say with these rows on."""
    e = expected(worn)
    a = [b + x for b, x in zip(BASE, e["attribs"])]
    return dict(f_attribs=a, hmax=4 * a[0] + 20 * a[2] + e["hp"], smax=4 * a[1] + 20 * a[2] + e["st"],
                amax=AP_BASE + e["od"])


def move(c, r, dst):
    """ss_move one row and read what follows it, the room's own traffic left out."""
    c.send("ss_move;obj=x%s;to=%d;from=%d;" % (inventory.oid_of(r), dst, r["slot"]))
    r["slot"] = dst
    return [(n, p) for n, p in c.frames(0.8)
            if n in ("cmdAck", "ss_obj_move", "rp_info") or (n == "usrUp" and p.get("id") == 0)]


def step(label, c, r, dst, on):
    """One move, and the frames it must bring: rp_info for the attributes
    that changed, usrUp when a maximum did, nothing else."""
    before = card(on())
    frames = move(c, r, dst)
    after = card(on())
    moved = [i for i in range(5) if before["f_attribs"][i] != after["f_attribs"][i]]
    want = ["cmdAck", "ss_obj_move"] + (["rp_info"] if moved else []) \
        + (["usrUp"] if (before["hmax"], before["smax"]) != (after["hmax"], after["smax"]) else [])
    check(label + ": " + ", ".join(want[2:] or ["nothing more"]), [n for n, _p in frames], want)
    check("  ..accepted", frames and frames[0][1].get("res"), 0)
    for p in named(frames, "rp_info"):
        check("  ..f_attribs for exactly the attributes that moved",
              (p["f_attribs_mask"], p["f_attribs"]),
              (sum(1 << i for i in moved), [after["f_attribs"][i] for i in moved]))
        check("  ..a_attribs bare, ap_max bare", (p["a_attribs"], p["ap_max"]),
              ([BASE[i] for i in moved], AP_BASE))
    for p in named(frames, "usrUp"):
        check("  ..the new maxima, as the tables add up", (p["id"], p["hmax"], p["smax"]),
              (0, after["hmax"], after["smax"]))


try:
    c = Client(connect())
    lenter = enter(c, first=True)
    check("a newborn's ceiling is the bare 50", lenter.get("amax"), 50)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()

    # The outfit goes into the bag behind the server's back, as a purchase would.
    st = accounts.Store(DB)
    char_id = st.db.execute("SELECT id FROM characters WHERE name = ?", ("wearer",)).fetchone()["id"]

    def bag(type_id, brk=None):
        f = inventory.new_fields(type_id)
        return st.create_item(char_id, type_id, f["root"], slot=BAG,
                              brk=f["brk"] if brk is None else brk,
                              max_break_cur=f["max_break_cur"])

    rows = {name: bag(t) for name, t in PIECES}
    spare = bag(sets.SETS[NAL8]["members"]["armor"], brk=0)
    belt = bag(BELT_BARE)
    # And the wearer at the set's level, the way one who shot his way up has it.
    ch = progression.Character.load(st, char_id)
    ch.skill[progression.SHOOTING] = [LEVEL, 0, progression.skill_xp_max(LEVEL)]
    ch.recalc()
    ch.save(st)
    st.close()

    def on():
        return [r for r in list(rows.values()) + [spare, belt] if r["slot"] != BAG]

    c = Client(connect())
    lenter = enter(c)
    check("with it all in the bag the ceiling is the level's bare ОД", lenter.get("amax"), AP_BASE)
    c.send("getInfo;lvl=0;id=0;type=0;")
    v = named(c.until("usrUp"), "usrUp")[0]
    check("and the bars the level's own", (v["hmax"], v["smax"]),
          (4 * BASE[0] + 20 * BASE[2], 4 * BASE[1] + 20 * BASE[2]))

    for name, _t in PIECES:
        step("%s on (%d of the set)" % (name, len(on()) + 1), c, rows[name], SLOT[name], on)

    c.send("logout;")
    c.frames(0.3)
    c.s.close()

    c = Client(connect())
    lenter = enter(c)
    check("back in with the set on: amax is the card's ОД, the three-piece od included",
          lenter.get("amax"), card(on())["amax"])
    check("  ..which is more than the level's bare ОД", lenter.get("amax") > AP_BASE, True)
    c.send("rp_get_info;")
    p = named(c.until("rp_info"), "rp_info")[0]
    check("rp_info after the relog: the set's attributes in f_attribs, counted at load",
          (p["a_attribs"], p["f_attribs"], p["ap_max"]), (BASE, card(on())["f_attribs"], AP_BASE))
    c.send("getInfo;lvl=0;id=0;type=0;")
    v = named(c.until("usrUp"), "usrUp")[0]
    check("  ..and the bars", (v["hmax"], v["smax"]), (card(on())["hmax"], card(on())["smax"]))

    step("armour off: back to four", c, rows["armor"], BAG, on)
    step("a broken armour on: its own numbers, the set still four", c, spare, ARMOR, on)
    step("a belt on: the set does not notice", c, belt, BELT, on)
    step("the broken armour off", c, spare, BAG, on)
    step("the whole armour back: five again", c, rows["armor"], ARMOR, on)
    c.send("logout;")
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    if fails and os.environ.get("LAVA_TEST_LOG"):
        print(out[-6000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("gear OK")
