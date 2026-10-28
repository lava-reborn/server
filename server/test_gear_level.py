"""Equipment has descriptive levels, retained specialisations and 5000-round stacks.

Real moves and displaced hand swaps at skill zero, persisted outfits after
login and level gain. Ammo prices, stack ceilings, money and overload rules
retain their existing integration checks below.
"""
import math
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

DB = os.path.join(tempfile.mkdtemp(), "gear_level.db")
os.environ["LAVA_DB"] = DB

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import progression  # noqa: E402
import sets  # noqa: E402
from inventory import BAG, CAMO, HEAD, PRIMARY, SECONDARY  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


KIT = inventory.STARTER_PISTOL    # Самострел, asks for nothing
NAGAN = 25566                     # Наган 1895, Стрельба 1
DEAGLE = 25656                    # Desert Eagle, Стрельба 6
KITCHEN = 6235                    # Кухонный нож, Ближний бой 4
TESAK = 6240                      # Тесак, Ближний бой 6
MEDKIT = 6046                     # a medicine asking Медицина 6
KOL = sets.SETS[11167]["members"]         # Колонист (A): the rung of level 2
NAL = sets.SETS[11185]["members"]         # Налетчик (A): level 8
SLOT = {"helm": HEAD, "shirt": CAMO, "armor": inventory.ARMOR,
        "pants": inventory.LEGS, "boots": inventory.BOOTS}
KS, ST = items.AMMO_9MM[0], items.AMMO_9MM[1]     # 9мм НАТО КС and СТ
START_AFRO = 13000


# --- the levels ----------------------------------------------------------------------
print("the levels")
check("the kit's pistol asks for nothing: a newborn keeps it in hand", inventory.item_level(KIT), 0)
check("Наган 1895, Desert Eagle: their Стрельба", (inventory.item_level(NAGAN),
                                                   inventory.item_level(DEAGLE)), (1, 6))
check("the knives: their Ближний бой", (inventory.item_level(KITCHEN),
                                        inventory.item_level(TESAK)), (4, 6))
check("every piece of Колонист is level 2, of Налетчик level 8",
      ({inventory.item_level(t) for t in KOL.values()},
       {inventory.item_level(t) for t in NAL.values()}), ({2}, {8}))
check("the level is the highest need_skills, whichever skill",
      inventory.item_level(NAL["helm"]),
      max(inventory.unpacked(items.params_of(NAL["helm"])["need_skills_m"],
                             items.params_of(NAL["helm"])["need_skills"], 5)))
check("no round asks for any level: loading is outside the rule",
      [t for t, (root, _n) in items.catalogue().items()
       if root == items.AMMO and inventory.item_level(t)], [])


def row(type_id, slot=BAG):
    return dict(uniq=1, type_id=type_id, root=items.root_of(type_id), slot=slot)


check("equipment levels no longer block wearing",
      [inventory.wearable(row(KOL["helm"]), lv) for lv in (0, 1, 2, 3)],
      [True, True, True, True])
check("a medicine asks Медицина 6 and is wearable at 0: not gear",
      (inventory.item_level(MEDKIT), inventory.wearable(row(MEDKIT), 0)), (6, True))
check("the refusal's line names the thing and both levels",
      inventory.level_line(row(NAGAN), 0),
      "«Наган 1895»: взять в руки можно с 1-го уровня, у вас 0-й")
check("  ..and says «надеть» for clothes",
      inventory.level_line(row(KOL["helm"]), 1),
      "«%s»: надеть можно с 2-го уровня, у вас 1-й" % inventory.item_title(KOL["helm"]))

# --- rounds: the stack and the price ------------------------------------------------
print()
print("rounds")
check("every round's stack is 5000: the window's ceiling and the bag's",
      {items.params_of(t)["max_count"] for t, (root, _n) in items.catalogue().items()
       if root == items.AMMO}, {5000})
check("junk keeps its designed 50: the rule is the rounds'",
      {items.designed_info(t)[1]["max_count"] for t, (root, _n) in items.catalogue().items()
       if root == items.TRASH}, {50})


def js_round(x):
    return math.floor(x + 0.5)


def window_price(si, n, gold=False, pmod=inventory.PMOD):
    """Ammo.initialize, then ExchangePan.countMoney, as the client does them."""
    cost = js_round(si["cost"] * 1000 / si["sell_num"]) / 1000
    g_cost = js_round(si["g_cost"] / si["sell_num"])
    cost_num = g_cost if gold and g_cost else cost
    return math.ceil(cost_num * n * pmod)


stall_rounds = [t for t in items.stock_for(1200) if items.root_of(t) == items.AMMO]
NS = (1, 2, 7, 19, 20, 21, 199, 200, 201, 999, 1000, 1234, 4999, 5000)
check("the price of n rounds is the window's, for every round of the pistol stall",
      [(t, n) for t in stall_rounds for n in NS
       for gold in ((False, True) if items.params_of(t)["g_cost"] else (False,))
       if inventory.buy_price(items.params_of(t), items.AMMO, n, gold)
       != window_price(items.params_of(t), n, gold)], [])
check("5000 of КС at 20 the pack of 20: 5000 afro",
      inventory.buy_price(items.params_of(KS), items.AMMO, 5000), 5000)
ODD = dict(cost=7, g_cost=30, sell_num=20)       # 0.35 afro, 1.5 -> 2 hundredths a round
check("an odd pack: the unit rounded as the client rounds it, gold to whole hundredths",
      [(inventory.buy_price(ODD, items.AMMO, n), inventory.buy_price(ODD, items.AMMO, n, True))
       for n in (1, 3, 5000)],
      [(window_price(ODD, n), window_price(ODD, n, True)) for n in (1, 3, 5000)])
check("  ..which is not cost*n/sell_num: 5000 at 30 the 20 is 10000, not 7500",
      inventory.buy_price(ODD, items.AMMO, 5000, True), 10000)
check("anything else: its own price", inventory.buy_price(items.params_of(NAGAN), items.FIRE_ARM, 1),
      items.params_of(NAGAN)["cost"])

# --- on a stand-in session: the displaced thing, and a level gained in play ----------
print()
print("in play")
store = accounts.Store(DB)
acc, _err = store.register("stand", "secret")
cid, _slot = store.create_character(acc, "Стойка", 0, 1)


class Stand:
    """The parts of server.Session that Inventory.ss_move touches."""

    def __init__(self):
        self.char_id = cid
        self.pid = 999
        self.room = None
        self.char = progression.Character.load(store, cid)
        self.frames = []
        self.said = []
        self.combat = combat.Fighter(self)

    def character(self):
        return self.char

    def send(self, *cmd, **params):
        self.frames.append((cmd[0], params))

    def say(self, text, group=0):
        self.said.append(text)

    answer = say


def put(type_id, slot):
    f = inventory.new_fields(type_id)
    root = f.pop("root")
    f["slot"] = slot
    return store.create_item(cid, type_id, root, **f)


kit = put(KIT, PRIMARY)
# Behind the rule's back, the way a row from before it would lie.
eagle = put(DEAGLE, SECONDARY)
nagan = put(NAGAN, BAG)
stand = Stand()
stand.char.set_spec(2, 2)  # Desert Eagle keeps its pistol-specialisation gate.
inv = inventory.Inventory(stand, store)


def move(r, dst):
    stand.frames, stand.said = [], []
    inv.ss_move({"obj": inventory.oid_of(store.item(r["uniq"])),
                 "from": store.item(r["uniq"])["slot"], "to": dst})
    return [p.get("res") for n, p in stand.frames if n == "cmdAck"], stand.said


res, said = move(kit, SECONDARY)
check("level-zero hand swap permits a displaced higher-tier weapon",
      (res,said,store.item(kit["uniq"])["slot"],store.item(eagle["uniq"])["slot"]),
      ([0],[],SECONDARY,PRIMARY))
res, said = move(nagan, PRIMARY)
check("level-zero Nagan replaces the held higher-tier weapon",
      (res,said,store.item(nagan["uniq"])["slot"],store.item(eagle["uniq"])["slot"]),
      ([0],[],PRIMARY,BAG))
stand.char.gain_xp(progression.SHOOTING, progression.skill_xp_max(0))
check("one shooting level gained in play", stand.char.level, 1)
res, said = move(eagle, SECONDARY)
check("higher-tier firearm equips after skill gain without relog",
      (res,said,store.item(eagle["uniq"])["slot"]),([0],[],SECONDARY))
check("login cleanup leaves allowed high-tier equipment in place",
      (inv.over_level_to_bag(),store.item(eagle["uniq"])["slot"],inv.taken_off_lines()),
      ([],SECONDARY,[]))
store.close()


# --- over the socket --------------------------------------------------------------------
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
_store.register("gunner", "secret")
_store.close()
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_POLICY_PORT="0", LAVA_GX="5970", LAVA_GY="1730",
           LAVA_START_AFRO=str(START_AFRO), LAVA_CHEATS="1")
# The lines the server says by itself (Session.say) are off on a served
# server; this suite reads them as the server's reasons, so it asks for
# them by name.
env["LAVA_SERVER_CHAT"] = "1"
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
                return got + self.frames(0.6)
        return got


def named(frames, name):
    return [p for n, p in frames if n == name]


def oids(p):
    return [str(x) for x in p["o_list"]]


def enter(c, login, first=False):
    """Into the world; returns what arrived from the lenter on."""
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % accounts.credential(login, "secret"))
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@%s@;" % login)
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.until("lcall")
    c.send("lenter;accept=1;")
    got = c.until("lenter")
    return got[[n for n, _p in got].index("lenter"):] if any(n == "lenter" for n, _p in got) else got


def leave(c):
    c.send("logout;")
    c.frames(0.3)
    c.s.close()


def char_of(st, name):
    return st.db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()["id"]


def slots(c):
    """slot=11: the six clothes, the two hands, the bag."""
    c.send("ss_get;target=0;slot=11;")
    return oids(named(c.until("ss_ack"), "ss_ack")[0])


def ss_move(c, r, dst):
    """One move: the cmdAck's res, the chat lines, whether ss_obj_move came."""
    c.send("ss_move;obj=x%s;to=%d;from=%d;" % (inventory.oid_of(r), dst, r["slot"]))
    got = [(n, p) for n, p in c.frames(0.8) if n in ("cmdAck", "ss_obj_move", "userMsg")]
    res = [p["res"] for n, p in got if n == "cmdAck"]
    if res == [0]:
        previous=r["slot"]
        for other in wire_rows:
            if dst in inventory.BODY_SLOTS and other["uniq"] != r["uniq"] and other["slot"] == dst:
                other["slot"] = previous
        r["slot"] = dst
    return res, [str(p["entry"]) for n, p in got if n == "userMsg"], \
        [n for n, _p in got if n == "ss_obj_move"]


def chat(frames):
    return [str(p["entry"]) for n, p in frames if n == "userMsg"]


try:
    # --- a newborn: level 0 ------------------------------------------------------------
    c = Client(connect())
    enter(c, "wearer", first=True)
    leave(c)

    st = accounts.Store(DB)
    wid = char_of(st, "wearer")

    def seed(type_id, slot=BAG):
        f = inventory.new_fields(type_id)
        root = f.pop("root")
        f["slot"] = slot
        return st.create_item(wid, type_id, root, **f)

    goods = {"nagan": seed(NAGAN), "eagle": seed(DEAGLE), "kitchen": seed(KITCHEN),
             "medkit": seed(MEDKIT)}
    kol = {name: seed(t) for name, t in KOL.items()}
    # Qualified specialisation, but all base skills remain zero.
    worn_helm = seed(NAL["helm"], HEAD)
    worn_tesak = seed(TESAK, SECONDARY)
    ch=progression.Character.load(st,wid)
    ch.set_spec(1,1)
    ch.set_spec(2,2)  # Qualified for Desert Eagle even at base shooting zero.
    ch.save(st)
    held = [r for r in st.items_of(wid) if r["slot"] == PRIMARY][0]
    everything = sorted(r["uniq"] for r in st.items_of(wid))
    st.close()
    wire_rows=list(goods.values())+list(kol.values())+[worn_helm,worn_tesak,held]

    c = Client(connect())
    after = enter(c, "wearer")
    check("level-zero login keeps qualified high-tier clothes and knife",chat(after),[])
    lst=slots(c)
    check("helmet and both hands remain equipped after login",
          (lst[0],lst[6],lst[7]),
          (inventory.oid_of(worn_helm),inventory.oid_of(held),inventory.oid_of(worn_tesak)))
    allowed=[("Kolonist helmet",kol["helm"],HEAD),("Kolonist shirt",kol["shirt"],CAMO),
             ("Nagan first hand",goods["nagan"],PRIMARY),("Nagan hand swap",goods["nagan"],SECONDARY),
             ("kitchen knife",goods["kitchen"],SECONDARY),("Naletchnik helmet",worn_helm,HEAD),
             ("Desert Eagle",goods["eagle"],PRIMARY)]
    for label,r,dst in allowed:
        res,said,moved=ss_move(c,r,dst)
        check("level zero permits "+label,(res,said,moved),([0],[],["ss_obj_move"]))
    res,said,moved=ss_move(c,goods["medkit"],SECONDARY)
    check("medicine may still be carried without its use skill",(res,said,moved),([0],[],["ss_obj_move"]))
    ss_move(c,goods["medkit"],BAG)
    for name,r in kol.items():
        if r["slot"]==SLOT[name]:
            check("already equipped Kolonist piece: "+name,r["slot"],SLOT[name])
            continue
        res,said,moved=ss_move(c,r,SLOT[name])
        check("full Kolonist at base skill zero: "+name,(res,said,moved),([0],[],["ss_obj_move"]))
    ss_move(c,goods["kitchen"],SECONDARY)
    before=slots(c)
    check("complete higher-tier outfit and weapons are on at level zero",
          (before[:6],before[6:8]),
          ([inventory.oid_of(kol[n]) for n in ("helm","shirt","armor")]+["0"]+
           [inventory.oid_of(kol[n]) for n in ("pants","boots")],
           [inventory.oid_of(goods["eagle"]),inventory.oid_of(goods["kitchen"])]))
    leave(c)
    c=Client(connect())
    after=enter(c,"wearer")
    check("relogin keeps every slot and emits no obsolete level refusal",(slots(c),chat(after)),(before,[]))
    leave(c)
    st=accounts.Store(DB)
    check("all inventory rows survive moves and relogin",sorted(r["uniq"] for r in st.items_of(wid)),everything)
    ch=progression.Character.load(st,wid)
    ch.set_skill(progression.SHOOTING,2)
    ch.save(st)
    st.close()
    c=Client(connect())
    after=enter(c,"wearer")
    check("gaining two levels keeps the same high-tier equipment",(slots(c),chat(after)),(before,[]))
    leave(c)

    # --- 5000 rounds ----------------------------------------------------------------------
    c = Client(connect())
    arrival = enter(c, "gunner", first=True)
    c.send("userMsg;entry=@/spec 0 5@;group=0;")
    trained = c.frames()  # +5 strength for the two full ammo stacks below
    check("trained strength advertises exactly 50 kg",
          named(trained, "rp_info")[0]["max_weight"], 50000)
    traders = [(p["id"], p) for n, p in arrival if n == "userInfo_Trader"]
    # The pistol stall's list where it stands, the black market (102) of the
    # cell: Вади-Хальфа's band (shop_bands.py), then its rounds.
    stall = [(i, p) for i, p in traders if p["type_list"][:1] == items.stock_for(1200, 102)[:1]]
    check("the pistol stall stands on the starting cell", len(stall) > 0, True)
    npc, info = stall[0]
    price_list = info["type_list"]
    ks_idx, st_idx = price_list.index(KS), price_list.index(ST)
    c.send("ss_get_si;type=%d;" % KS)
    si = named(c.until("ss_si_ammo"), "ss_si_ammo")[0]
    check("ss_si_ammo: a stack of 5000, a pack of 20 at 20 afro",
          (si["max_count"], si["sell_num"], si["cost"]), (5000, 20, 20))
    c.send("ss_create;s_type=1;target=%d;" % npc)
    check("the stall opens", named(c.frames(), "cmdAck"), [{"res": 0}])
    c.send("ss_get;slot=8;")
    bag0 = oids(named(c.until("ss_ack"), "ss_ack")[0])

    def purse():
        c.send("getInfo;lvl=0;id=0;type=0;")
        return named(c.until("userInfo_Player"), "userInfo_Player")[0]["afro"]

    def buy(idx, n):
        c.send("ss_upd;param=%d;obj=x%x;s_status=1;" % (n, idx))
        return c.frames(0.8)

    afro = purse()
    check("the purse starts at LAVA_START_AFRO", afro, START_AFRO)
    got = buy(ks_idx, 5001)
    check("5001: past the window's ceiling, refused and nothing else",
          ([n for n, _p in got], got[0][1]["res"] != 0), (["cmdAck"], True))
    got = buy(st_idx, 5000)
    check("5000 of СТ at 3 a round is 15000: too poor, 21 and nothing else",
          [(n, p.get("res")) for n, p in got], [("cmdAck", inventory.RES_NO_MONEY)])
    check("  ..the purse untouched", purse(), afro)
    got = buy(ks_idx, 5000)
    check("5000 of КС: the ack, the stack, its size, the purse",
          [n for n, _p in got], ["cmdAck", "ss_obj_status", "ss_di_heap", "userInfo_Player"])
    check("  ..accepted, a new thing in the bag", (got[0][1]["res"], got[1][1]["status"]), (0, 1))
    first = str(got[1][1]["obj"])
    check("  ..of КС, ONE stack of all 5000",
          (inventory.parse_oid(first)[1], str(got[2][1]["obj"]), got[2][1]["size"]), (KS, first, 5000))
    price = window_price(items.params_of(KS), 5000)
    check("  ..charged what the window shows, 5000 afro", (price, got[3][1]["afro"]),
          (5000, afro - 5000))
    afro -= price
    check("  ..and the purse in play says the same", purse(), afro)
    c.send("ss_get;slot=8;")
    bag1 = oids(named(c.until("ss_ack"), "ss_ack")[0])
    check("the bag: what it held and the one new stack", bag1, bag0 + [first])
    got = buy(ks_idx, 5000)
    second = str(got[1][1]["obj"])
    check("5000 more: a second stack of 5000, 5000 afro more",
          (got[0][1]["res"], got[2][1]["size"], got[3][1]["afro"], second != first),
          (0, 5000, afro - 5000, True))
    afro -= 5000
    c.send("ss_heap_c;num=5000;trg=x%s;obj=x%s;" % (second, first))
    check("two full stacks do not join past 5000", [(n, p["res"] != 0) for n, p in c.frames()],
          [("cmdAck", True)])

    st = accounts.Store(DB)
    gid = char_of(st, "gunner")
    carried = sum(inventory.weight_of(r) for r in st.items_of(gid))
    limit = progression.Character.load(st, gid).max_weight()
    st.close()
    w = items.params_of(KS)["weight"]
    over = (limit - carried) // w + 1
    check("the bag so far: the kit and 40 kg of rounds", carried,
          sum(items.params_of(t)["weight"] * n for t, n in inventory.STARTER_KIT) + 10000 * w)
    check("the purse can pay for one round more than the bag can take", over <= afro, True)
    got = buy(ks_idx, over)
    check("%d rounds, a gram past %d: 27 and nothing else" % (over, limit),
          [(n, p.get("res")) for n, p in got], [("cmdAck", inventory.RES_OVERLOAD)])
    got = buy(ks_idx, over - 1)
    check("%d, to the gram: accepted" % (over - 1),
          (got[0][1]["res"], got[2][1]["size"], got[3][1]["afro"]), (0, over - 1, afro - (over - 1)))
    afro -= over - 1
    got = buy(ks_idx, 1)
    check("then one round more: 27", [(n, p.get("res")) for n, p in got],
          [("cmdAck", inventory.RES_OVERLOAD)])
    c.send("ss_upd;obj=x0;s_status=0;")
    leave(c)

    c = Client(connect())
    enter(c, "gunner")
    c.send("ss_get;target=0;slot=8;")
    bag = oids(named(c.until("ss_ack"), "ss_ack")[0])
    sizes = []
    for o in bag:
        if inventory.parse_oid(o)[1] == KS:
            c.send("ss_get_di;obj=x%s;" % o)
            sizes.append(named(c.until("ss_di_heap"), "ss_di_heap")[0]["size"])
    check("after a relog: the three stacks and the purse", (sorted(sizes), purse()),
          (sorted([5000, 5000, over - 1]), afro))
    leave(c)
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
print("gear level OK")
