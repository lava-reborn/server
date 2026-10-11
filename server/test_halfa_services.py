"""Вади-Хальфа's services as the original had them (the owner's «займись
фулл восстановлением Вади-Хальфы», 2026-09-28): the healers' price and
their «Прописка», no «Прописка» at a thing, gold into afro at the one rate,
a thing priced in gold alone sold for afro, Хассир registering trophies
beside his stall, the stalls' goods, and Мортимер's and the lotteries'
service quests.

In process: the tables -- data/npcs.json 'healer_price', 'home' and
'stock', the one rate (progression.GOLD_TO_AFRO_RATE) where the auction and
the ingots read it, the gun stalls of the black market with the wiki's
models and no assault rifle, the clothing market by the owner's ladder
(data/sets.json), the rows 301-309. On a socket, a newcomer on the station
(37): the healer's frame and fee, «Прописка» at the healer and not at a
Trader or a fountain, c_ga, a gold-only thing sold at Хассир's, then in the
жилой квартал (36) Мортимер's cashing and change of ingots, and a lottery
drawn -- its row put on Мортимер for the run (LAVA_QUESTS), the lottery
men being seasonal residents the world does not stand yet.

    LAVA_RES=.../lava/res python3 server/test_halfa_services.py
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

MORTIMER, LOTTERY_MAN, GOLD_LOTTERY = 1188, 662, 711
HEALER, PRISON_HEALER, OASIS_HEALER, VALLEY_HEALER = 100, 2111, 1234, 5140
HASSIR, BOWL, TECHNOGEEK = 105, 634, 652
INGOT_1, INGOT_5, INGOT_10 = 7620, 4796, 4797
TICKET, GOLD_TICKET = 1307, 1333
CASH_1, CASH_5, CASH_10, SPLIT_5, SPLIT_10, JOIN_5, JOIN_10, LOTTERY, LOTTERY_G = range(301, 310)
GOLD_GOGGLES = 10739            # Очки налетчика[8][G]: 2.5 G and no afro price
STATION, QUARTER = 37, 36
NO_HOME = [75, 104, 625, 634, 816, 1692, 1753, 6516, 6517, 6518, 6519, 6824, 6825, 6826]

# The lottery's row on Мортимер for the run: the lottery men do not stand yet.
with open(os.path.join(os.path.dirname(HERE), "data", "quests.json"),
          encoding="utf-8") as fh:
    TABLE = json.load(fh)
for _row in TABLE["quests"]:
    if _row["type"] == LOTTERY:
        _row["give"], _row["take"] = [MORTIMER], [MORTIMER]
QUESTS_FILE = os.path.join(tempfile.mkdtemp(), "quests.json")
with open(QUESTS_FILE, "w", encoding="utf-8") as fh:
    json.dump(TABLE, fh, ensure_ascii=False)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import auction  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import orig_texts  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import sets  # noqa: E402
import trophies  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


RATE = progression.GOLD_TO_AFRO_RATE
OUNCE = progression.GOLD_OUNCE
cat = items.catalogue()
ICON_FOLDER = {items.FIRE_ARM: "FireArm", items.WEAR: "WearItem", items.HEAL: "Heal_Item",
               items.AMMO: "Ammo", items.TRASH: "SimpleObject", items.COLD_ARM: "ColdArm",
               items.TROPHY: "Trophy"}


def servable(t):
    """A stall can show it: a frame, a name the preload has, an icon, a price."""
    p = items.params_of(t)
    root, internal = cat[t]
    return bool(p) and names.known(p["name"]) and os.path.isfile(
        os.path.join(world.RES, "classes", ICON_FOLDER[root], internal, "ico.swf")) \
        and (p["cost"] > 0 or p["g_cost"] > 0)


def set_types(name):
    """The five pieces of a set of data/sets.json, by its name, helm to boots."""
    doc = json.load(open(os.path.join(os.path.dirname(HERE), "data", "sets.json"),
                         encoding="utf-8"))["sets"]
    s = [v for v in doc.values() if v["name"] == name][0]
    return [s["members"][k]["type"] for k in ("helm", "shirt", "armor", "pants", "boots")]


# --- in process: the tables -----------------------------------------------------------
try:
    check("the healers of Вади-Хальфа charge the original's 150, the prison's 250;"
          " the valley's keep the old fee",
          [npcs.healer_price(t, 10) for t in (HEALER, OASIS_HEALER, PRISON_HEALER, VALLEY_HEALER)],
          [150, 150, 250, 10])
    check("things and an unlisted commoner register nobody's home; Said and healers do",
          ([t for t in NO_HOME if world.offers_home(t)], world.offers_home(TECHNOGEEK),
           world.offers_home(44), world.offers_home(HEALER)), ([], False, True, True))
    check("Хассир registers trophies and keeps his stall; the butchers do not trade",
          (trophies.is_registrar(HASSIR), trophies.keeps_stall(HASSIR),
           world.entity_root(HASSIR, world.TRADER), trophies.keeps_stall(939)),
          (True, True, world.TRADER, False))
    check("one rate: the auction sorts by it", auction.GOLD_TO_AFRO, RATE)
    # In gold too since 2026-10-09: Мортимер sells them at face value.
    check("the ingots are worth their ounces: in afro at it, and in gold",
          [(items.params_of(t)["cost"], items.params_of(t)["g_cost"])
           for t in (INGOT_1, INGOT_5, INGOT_10)],
          [(RATE, OUNCE), (5 * RATE, 5 * OUNCE), (10 * RATE, 10 * OUNCE)])
    # With the plan's correction д (test_halfa_fixups): Странник[4] and the
    # gold sets of 4/6/8 in Halfa too, not at Локсли's in the valley alone --
    # and since the owner's «по уровню городов» (2026-10-10, shop_bands.py)
    # each of the town's set sellers its whole band, 4-8, both versions.
    both = lambda n: set_types(n + "[A]") + set_types(n + "[G]")
    town = both("Странник[4]") + both("Магриб[6]") + both("Налетчик[8]")
    # His belts: the four of 2026-09-28, «Подсумки рукопашника» of his article since
    # its link (2026-10-11), and each one's (G) right after it (items.GOLD_POUCHES,
    # the owner's «добавь еще голдовые подсумки»).
    belts = [3582, 3604, 3581, 3603, 3579, 3601, 3578, 3600, 5613, 5614]
    check("Хамис, Рияд and Ваккас sell the town's band: Странник, Магриб and Налетчик, each"
          " in both versions; Ваккас then five belts, each with its (G) after it",
          (items.stock_for(1205, 102), items.stock_for(650, 52), items.stock_for(1204, 102)),
          (town, town, town + belts))
    check("  ..the belts by the original's names and the wiki's prices: the ordinary in"
          " afro, the (G) in gold alone",
          [(names.text(items.STRING_ID_OFFSET + t), items.params_of(t)["cost"],
            items.params_of(t)["g_cost"]) for t in belts],
          [("Подсумки пистолетные", 3000, 0), ("Подсумки пистолетные (G)", 0, 50),
           ("Подсумки охотника", 8000, 0), ("Подсумки охотника (G)", 0, 160),
           ("Подсумки спецназовца", 40000, 0), ("Подсумки спецназовца (G)", 0, 800),
           ("Подсумки снайпера", 20000, 0), ("Подсумки снайпера (G)", 0, 400),
           ("Подсумки рукопашника", 40000, 0), ("Подсумки рукопашника (G)", 0, 800)])
    check("  ..each one a stall can show", [t for t in belts if not servable(t)], [])
    # Мортимер sells the ingots since 2026-10-09 (test_halfa_ingots).
    check("Мортимер sells the ingots; Марк Клаус and Ольсен sell nothing; Бартоломью has the Фуль",
          (items.stock_for(MORTIMER), items.stock_for(1959), items.stock_for(431),
           334 in items.stock_for(81)), ([INGOT_1, INGOT_5, INGOT_10], [], [], True))
    guns = {tr: [items.params_of(t)["weapon_type"] for t in items.stock_for(tr, 102)
                 if items.root_of(t) == items.FIRE_ARM] for tr in (1201, 1202, 1203)}
    check("the gun stalls sell the models of their own class, and no assault rifle",
          {tr: sorted(set(v)) for tr, v in guns.items()},
          {1201: [items.SHOTGUN], 1202: [items.RIFLE], 1203: [items.SMG]})
    check("  ..the town's band, 4-8, in both versions: ten shotguns, three rifles, two"
          " sub-machine guns, each twice, by its name",
          ({tr: len(v) for tr, v in guns.items()},
           sorted(names.text(items.STRING_ID_OFFSET + t).split("$")[0]
                  for t in items.stock_for(1203, 102) if items.root_of(t) == items.FIRE_ARM)),
          ({1201: 20, 1202: 6, 1203: 4},
           ["Borzh", "Borzh (G)", "Кустарный ПП", "Кустарный ПП (G)"]))
    check("«Билет в Донголу» is no longer the Пропуск or the lottery's ticket",
          sorted(set(items.links()[2].get(1124, [])) & {"Пропуск", "Лотерейный билет (8)"}), [])
    # The two traders left at the market cut off the map, the ladder's sets of
    # the levels in their own names, A then G (test_halfa_fixups holds the
    # rule; 2026-09-28); 5160 and 5161 their city's band in Абри's market (and
    # Донгола's, Абу-Хамед's: test_halfa_fixups, test_stall_bands).
    check("the clothing market by the owner's ladder: the levels in each trader's name, A then"
          " G, or at Абри's market its band -- and the town's miner's clothes, A then G",
          [items.stock_for(t, place) for t, place in ((5158, None), (5159, None), (5160, 378),
                                                      (5161, 378), (5181, None))],
          [both("Беженец[1]") + both("Колонист[2]") + both("Странник[4]") + both("Магриб[6]"),
           both("Налетчик[8]") + both("Пустынник[10]"),
           both("Налетчик[8]") + both("Пустынник[10]"),
           both("Налетчик[8]") + both("Пустынник[10]"),
           list(range(34480, 34485)) + list(range(34490, 34495))])
    check("the oasis: new models, the choice rounds and others, medicine",
          [len(items.stock_for(t, 62)) > 0 for t in (1224, 1227, 202)], [True] * 3)
    check("  ..the rounds are rounds, the medicine medicine",
          ({items.root_of(t) for t in items.stock_for(1227)},
           {items.root_of(t) for t in items.stock_for(202)}), ({items.AMMO}, {items.HEAL}))
    check("the lottery men sell their tickets; the gold one for gold alone",
          (items.stock_for(LOTTERY_MAN), items.stock_for(GOLD_LOTTERY),
           (items.params_of(GOLD_TICKET)["cost"], items.params_of(GOLD_TICKET)["g_cost"])),
          ([TICKET], [GOLD_TICKET], (0, 50)))
    everything = sorted({t for tr, place in ((1205, 102), (650, 52), (1204, 102), (81, 35),
                                             (5158, None), (5159, None), (5160, 378), (5161, 378),
                                             (1224, 62), (1227, 62), (202, 62), (662, 35),
                                             (711, 102), (1201, 102), (1202, 102), (1203, 102))
                         for t in items.stock_for(tr, place)})
    check("every one of these goods can be shown and priced, none premium",
          ([t for t in everything if not servable(t)], [t for t in everything if items.premium(t)]),
          ([], []))
    rows = {t: quests.get(t) for t in range(CASH_1, LOTTERY_G + 1)}
    check("Мортимер's seven rows are his, services, repeatable, their strings preloaded",
          [(q.give, q.take, q.service, q.repeatable, all(names.known(i) for i in q.string_ids()))
           for t, q in sorted(rows.items()) if t < LOTTERY],
          [([MORTIMER], [MORTIMER], True, 1, True)] * 7)
    check("  ..cashing: an ingot for its ounces less 0.05",
          [(q.wants(), q.rew_gold) for q in (rows[CASH_1], rows[CASH_5], rows[CASH_10])],
          [([(INGOT_1, 1)], 95), ([(INGOT_5, 1)], 495), ([(INGOT_10, 1)], 995)])
    check("  ..change: ounce for ounce, both ways",
          [(q.wants(), list(zip(q.rew_obj, q.num_rew_obj))) for q in
           (rows[SPLIT_5], rows[SPLIT_10], rows[JOIN_5], rows[JOIN_10])],
          [([(INGOT_5, 1)], [(INGOT_1, 5)]), ([(INGOT_10, 1)], [(INGOT_1, 10)]),
           ([(INGOT_1, 5)], [(INGOT_5, 1)]), ([(INGOT_1, 10)], [(INGOT_10, 1)])])
    check("  ..in the original's words (data/orig_misc.json)",
          [orig_texts.quests().get(t, {}).get("name") for t in (CASH_1, SPLIT_5, JOIN_10)],
          ["Обналичить 1 унцию золота", "Разменять 5 унций золота", "Разменять на 10 унций золота"])
    check("  ..the owner's ingot quest pays 2 ounces for the valley boss's two ingots of one",
          (quests.get(10).wants(), quests.get(10).rew_gold), ([(INGOT_1, 2)], 200))
    lottery = {LOTTERY: [LOTTERY_MAN], LOTTERY_G: [GOLD_LOTTERY]}
    check("the lotteries: the ticket for a prize drawn, up to the eighth level, a service",
          [(quests.get(t).take, quests.get(t).wants(),
            quests.get(t).max_level, quests.get(t).service, bool(quests.get(t).rew_random))
           for t in (LOTTERY, LOTTERY_G)],
          [([LOTTERY_MAN], [(TICKET, 1)], 8, True, True),
           ([GOLD_LOTTERY], [(GOLD_TICKET, 1)], 8, True, True)])
    check("  ..no premium prize, and the start names only what can be won",
          ([t for q in (LOTTERY, LOTTERY_G) for t, _n, _w in quests.get(q).rew_random
            if items.premium(t)], ["(P)" in quests.get(q).texts[quests.START]
                                   for q in (LOTTERY, LOTTERY_G)]), ([], [False, False]))
except Exception:
    import traceback
    fails.append("the tables in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "halfa_services.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("townsman", "secret")
_store.close()
CRED = accounts.credential("townsman", "secret")
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="5967", LAVA_GY="1727", LAVA_SEED="5",
           LAVA_POLICY_PORT="0", LAVA_QUESTS=QUESTS_FILE)
env.pop("LAVA_PASSAGES", None)
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

    def frames(self, wait=0.6):
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


def order(frames):
    return [n for n, _p in frames]


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def first(frames, name):
    got = named(frames, name)
    return got[0] if got else {}


def upto_ack(frames):
    seq = order(frames)
    return seq[:seq.index("cmdAck") + 1] if "cmdAck" in seq else seq


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(2)


def infos(frames):
    """type id -> its userInfo_* frame, of a population."""
    return {p["name"]: (n, p) for n, p in frames
            if n.startswith("userInfo_") and n != "userInfo_Player" and "name" in p}


def goto(c, loc):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc)
    c.until(lambda f: f[0] == "lcall")
    return arrive(c)


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.frames()
    return [str(p["obj"]).lstrip("x") for p in named(got, "ss_obj_status") if p["status"] == 1]


def given_by(npc_type):
    """What an NPC gives in the server's table (the run's, LAVA_QUESTS)."""
    return [r["type"] for r in TABLE["quests"] if npc_type in r.get("give", [])]


def take(c, npc, qtype, npc_type):
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, given_by(npc_type).index(qtype)))
    return c.frames(0.8)


def hand_in(c, npc, q_id):
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (npc, q_id))
    return c.frames(0.8)


def q_id_of(frames):
    ids = [p["q_id"] for n, p in frames if n.startswith("q_di_")]
    return ids[0] if ids else 0


def char_id():
    st = accounts.Store(DB)
    cid = st.db.execute("SELECT id FROM characters WHERE name = 'Townsman'").fetchone()["id"]
    st.close()
    return cid


def purse():
    st = accounts.Store(DB)
    got = tuple(st.money(char_id()))
    st.close()
    return got


def owned():
    st = accounts.Store(DB)
    out = {}
    for r in st.items_of(char_id()):
        out[r["type_id"]] = out.get(r["type_id"], 0) + (
            r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1)
    st.close()
    return out


try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    login = c.frames()
    check("the client is told the one rate",
          [p["gold_to_afro_rate"] for p in named(login, "constants")], [RATE])
    c.send("newPers;res=1;sex=0;name=@Townsman@;")
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    got = arrive(c)
    here = infos(got)
    # --- the healer, «Прописка» ---------------------------------------------------------
    kind, healer = here.get(HEALER, ("", {}))
    check("the station's healer: 150 afro, and «Прописка» beside the healing",
          (kind, healer.get("a_price"), healer.get("can_set_home")), ("userInfo_Medic", 150, 1))
    check("a fountain offers no «Прописка»", here.get(BOWL, ("", {}))[1].get("can_set_home"), 0)
    kind, hassir = here.get(HASSIR, ("", {}))
    check("Хассир: a trader who mends and registers trophies",
          (kind, hassir.get("can_trade"), hassir.get("can_repair"), hassir.get("can_trophy")),
          ("userInfo_Trader", 1, 1, 1))
    afro0, gold0 = purse()
    c.send("on_conv;mob=%d;op=1;" % healer["id"])
    got = c.frames()
    check("healing: the purse, the bars, the ack, 150 afro taken",
          (order(got), first(got, "userInfo_Player").get("afro")),
          (["userInfo_Player", "usrUp", "cmdAck"], afro0 - 150))
    c.send("on_conv;mob=%d;op=0;" % healer["id"])
    check("home registered at the healer", acks(c.frames()), [0])
    c.send("on_conv;mob=%d;op=0;" % hassir["id"])
    check("  ..not at a trader", acks(c.frames()), [2])
    c.send("on_conv;mob=%d;op=0;" % here[BOWL][1]["id"])
    check("  ..nor at a fountain", acks(c.frames()), [2])
    st = accounts.Store(DB)
    check("  ..and the home is the station",
          st.db.execute("SELECT home_loc FROM characters WHERE id = ?", (char_id(),)).fetchone()[0],
          STATION)
    st.close()

    # --- gold into afro ------------------------------------------------------------------
    c.send("userMsg;entry=@/money 0 300@;group=0;")
    c.frames()
    afro1, gold1 = purse()
    c.send("c_ga;gold=150;")
    got = c.frames()
    check("c_ga: 1.5 ounces into afro at the one rate, the ack, then the purse",
          (order(got), (first(got, "userInfo_Player").get("afro"),
                        first(got, "userInfo_Player").get("gold"))),
          (["cmdAck", "userInfo_Player"], (afro1 + 150 * RATE // OUNCE, gold1 - 150)))
    check("  ..acknowledged", acks(got), [0])
    c.send("c_ga;gold=100000;")
    got = c.frames()
    check("  ..more than the purse holds: refused, nothing moves",
          (order(got), acks(got), purse()), (["cmdAck"], [21], (afro1 + 150 * RATE // OUNCE, gold1 - 150)))

    # --- a thing priced in gold alone, sold at Хассир's ----------------------------------
    oid = give(c, GOLD_GOGGLES)[0]
    c.send("ss_create;s_type=1;target=%d;" % hassir["id"])
    check("Хассир's stall opens", acks(c.frames()), [0])
    afro2 = purse()[0]
    c.send("ss_upd;s_status=2;obj=x%s;param=1;" % oid)
    got = c.frames()
    c.send("ss_upd;s_status=0;obj=x0;")
    c.frames(0.3)
    check("a thing priced in gold alone is not bought for afro (inventory.SELL_GOLD_ONLY off)",
          (acks(got) != [0], purse()[0] - afro2, owned().get(GOLD_GOGGLES, 0) >= 1), (True, 0, True))

    # --- Мортимер ------------------------------------------------------------------------
    here = infos(goto(c, QUARTER))
    mort = here.get(MORTIMER, ("", {}))[1].get("id", 0)
    give(c, INGOT_5)
    got = take(c, mort, CASH_5, MORTIMER)
    check("cashing 5 ounces: taken, complete with the ingot in the bag",
          (acks(got), first(got, "q_di_bring_l_obj").get("complete")), ([0], 1))
    gold3 = purse()[1]
    got = hand_in(c, mort, q_id_of(got))
    check("  ..handed in: the ingot out, 4.95 ounces in, no q_sys (a service)",
          (upto_ack(got), acks(got), purse()[1] - gold3, owned().get(INGOT_5)),
          (["ss_obj_status", "userInfo_Player", "cmdAck"], [0], 495, None))
    give(c, INGOT_1, 5)
    got = take(c, mort, JOIN_5, MORTIMER)
    got = hand_in(c, mort, q_id_of(got))
    check("five ingots of an ounce changed into one of five",
          (acks(got), owned().get(INGOT_1), owned().get(INGOT_5)), ([0], None, 1))
    got = take(c, mort, SPLIT_5, MORTIMER)
    got = hand_in(c, mort, q_id_of(got))
    check("  ..and back", (acks(got), owned().get(INGOT_1), owned().get(INGOT_5)), ([0], 5, None))

    # --- a lottery, its row on Мортимер for the run --------------------------------------
    give(c, TICKET)
    got = take(c, mort, LOTTERY, MORTIMER)
    got = hand_in(c, mort, q_id_of(got))
    prizes = {t for t, _n, _w in quests.get(LOTTERY).rew_random}
    won = [t for t, n in owned().items() if t in prizes]
    check("a lottery: the ticket taken, one prize of its list won, no q_sys",
          (acks(got), owned().get(TICKET), len(won), "q_sys" in order(got)), ([0], None, 1, False))
    c.send("logout;")
    c.frames(0.3)
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=5)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-40:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa services OK")
