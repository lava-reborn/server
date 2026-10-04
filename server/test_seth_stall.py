"""Барыга Сет (1187), the trader of the Nubian valley's arena, «Арена Нубии»
(167, 6270x1831), sells what his wiki page lists (the owner's «делай»,
2026-09-26). His stall stood empty: no entry in data/npcs.json, and his
page left out of data/trader_stock_wiki.json's by_type for want of a type
id («unbound»).

The page's «Торговля», in its order, as a stall of ours can hold it (the
rule and the leaving out are test_shops'):

  Walther P99        25636, the (A) copy the linker ties the page to
  9мм НАТО, twice    6092 КС and 6104 СТ: the two rows of the calibre Борис's
                     page, the valley's other stall, spells out
  Рубашка, Джинсы, Старые ботинки, Каска строителя, Кусковая броня
                     the five pieces of the owner's Колонист (data/sets.json
                     11167) whose numbers are these very pages' (A) columns:
                     10180, 10182, 10183, 10179 (the set's helmet, which the
                     owner calls «Гоглы с фильтром» by its icon), 10181
  Альфа-/Омега-Реагент I
                     4181 and 3208, the (A) copies
  left out           OP 1 (no article, no type, no row of the original) and
                     the five of «Старые вещи» (Водолазка, Брезентовые штаны,
                     Берцы, Железная каска, Рессорная броня), whose only
                     types in the client are the original's mob copies
                     (_Mob_M_, [M]) with no icon a stall could draw

In process: the stall is that list and no other trader's stall is what it
was not before -- recomputed without Сет's entry, every one of the 821
trader types but his sells the same -- and each piece of clothing on it
carries its article's numbers (data/wiki_items.json, the extractor's own
reading of data/wiki/pages.json, transcribed here independently of
data/sets.json). Then one server over the socket: a newborn at the arena
finds Сет trading and mending, his stall's frames are those numbers, he
buys each thing once at the price the window shows, the purse and the
bag agree, and at level 0 he may carry the level-2 and level-4 things but
not put them on (the owner's «вещи по уровню только можно носить»).

    LAVA_RES=.../lava/res python3 server/test_seth_stall.py
"""
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENC = "utf-8"

DB = os.path.join(tempfile.mkdtemp(), "seth_stall.db")
os.environ["LAVA_DB"] = DB

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import world  # noqa: E402
from inventory import BAG, HEAD, PRIMARY  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


SETH, ARENA, ARENA_CELL = 1187, 167, (6270, 1831)
WALTHER, KS, ST = 25636, 6092, 6104
HELM, SHIRT, ARMOR, PANTS, BOOTS = 10179, 10180, 10181, 10182, 10183
ALPHA, OMEGA = 4181, 3208
STALL = [WALTHER, KS, ST, SHIRT, PANTS, BOOTS, HELM, ARMOR, ALPHA, OMEGA]
# Rounds are bought by the number, anything else one at a time.
ROUNDS = 20
# What each costs, worked out by hand from the frames (pmod 1): the pistol
# and the clothes at their price, 20 rounds of a pack of 20 at 20 and at 60
# afro, the reagents at 2500.
PRICES = {WALTHER: 2800, KS: 20, ST: 60, SHIRT: 600, PANTS: 800, BOOTS: 400,
          HELM: 1000, ARMOR: 1200, ALPHA: 2500, OMEGA: 2500}
START_AFRO = 20000
# The pieces of clothing and the article each one's numbers are.
ARTICLE = {HELM: "Каска строителя", SHIRT: "Рубашка", ARMOR: "Кусковая броня",
           PANTS: "Джинсы", BOOTS: "Старые ботинки"}
# The level each thing asks (inventory.item_level): its Стрельба.
LEVEL = {WALTHER: 4, SHIRT: 2, PANTS: 2, BOOTS: 2, HELM: 2, ARMOR: 2,
         KS: 0, ST: 0, ALPHA: 0, OMEGA: 0}
cat = items.catalogue()

# --- in process ------------------------------------------------------------------------
print("the stall")
mt = world.mob_types()
check("1187 is nz_arena_trd, a trader, «Барыга Сет»",
      (mt[SETH][:2], names.text(SETH)),
      ((world.TRADER, "nz_arena_trd"), "Барыга Сет<br>Торговля для экспедиций"))
check("  ..standing in «Арена Нубии» (167), the cell 6270x1831",
      (world.location_at(*ARENA_CELL), [t for _c, t in world.location(ARENA).spawns]),
      (ARENA, [SETH]))
check("his stall is the wiki page's list, in its order: the data/npcs.json entry",
      (npcs.stock(SETH), items.stock_for(SETH)), (STALL, STALL))
check("  ..each by the name the player reads",
      [names.text(items.STRING_ID_OFFSET + t) for t in STALL],
      ["Walther P99$Пистолет", "9мм НАТО $КС", "9мм НАТО $СТ", "Рубашка", "Джинсы",
       "Старые ботинки", "Гоглы с фильтром", "Кусковая броня", "Альфа-реагент I",
       "Омега-реагент I"])
check("  ..priced in afro, nothing premium, nothing gold",
      [(t, items.params_of(t)["g_cost"], items.premium(t)) for t in STALL
       if items.params_of(t)["g_cost"] or items.premium(t) or items.params_of(t)["cost"] <= 0],
      [])
check("  ..and asking the levels of their Стрельба", {t: inventory.item_level(t) for t in STALL},
      LEVEL)

# Every trader of the client, as the stall would be without this change: the
# same data with Сет's entry taken out again.
traders = sorted(t for t, v in mt.items() if v[0] == world.TRADER)
now = {t: items.stock_for(t) for t in traders}
entry = npcs.STOCK.pop(SETH, None)
items._PREMIUM.clear()
try:
    without = {t: items.stock_for(t) for t in traders}
finally:
    if entry is not None:
        npcs.STOCK[SETH] = entry
    items._PREMIUM.clear()
check("without his entry Сет's stall is the empty one it was", without[SETH], [])
check("no other trader's stall changed: all %d others sell what they sold" % (len(traders) - 1),
      [t for t in traders if t != SETH and now[t] != without[t]], [])
check("  ..and every thing on Сет's stall was already on another's, number for number",
      [t for t in STALL if not any(t in now[o] for o in traders if o != SETH)], [])

# The articles' (A) columns, read off data/wiki_items.json by hand: the row
# names are the tooltip's, and so is the arithmetic of the need lists (a bit
# per attribute or skill in the client's order, the values dense).
with io.open(os.path.join(ROOT, "data", "wiki_items.json"), encoding="utf-8") as fh:
    WIKI_ITEMS = json.load(fh)
ROW_KEY = {"Уровень брони": "armor_class", "Износ": "max_break_abs", "Вес": "weight",
           "Здоровье": "bonus_hp", "Выносливость": "bonus_st", "Крит. попадание": "bonus_cp",
           "Избег. крит. попадание": "bonus_ce"}
SLOT_OF = {"Головной убор": 0, "Верхняя одежда": 1, "Броня": 2, "Штаны": 4, "Ботинки": 5}
ATTRIBS = ("Сила", "Ловкость", "Телосложение", "Восприятие", "Интеллект")
SKILLS = ("Ближний бой", "Стрельба", "Медицина", "Промышленность", "Производство")


def need(named, order):
    """{"Телосложение": 6} -> (mask, [values]) as Item.parseNeedBonus reads it."""
    bits = sorted(order.index(k) for k in named)
    return sum(1 << b for b in bits), [named[order[b]] for b in bits]


def article_numbers(page):
    """The ss_si_wear fields the article's (A) column gives."""
    table = WIKI_ITEMS[page]["tables"][0]
    col = table["columns"].index("Одежда (А)")
    rows = table["sections"]["общие"]
    out = {key: rows[row][col] for row, key in ROW_KEY.items()
           if row in rows and rows[row][col] is not None}
    out["cost"], out["g_cost"] = rows["Базовая цена"][col]["afro"], 0
    out["slot_type"] = SLOT_OF[rows["Тип"][col]]
    out["exchang"] = int(rows["Допустимость обмена"][col])
    out["premium"] = int(rows["Премиумность"][col])
    out["need_attribs_m"], out["need_attribs"] = need(rows["Необходимые атрибуты"][col], ATTRIBS)
    out["need_skills_m"], out["need_skills"] = need(rows["Необходимые навыки"][col], SKILLS)
    return out


WANT = {t: article_numbers(page) for t, page in ARTICLE.items()}
check("the articles, as read: Каска строителя 5 armour, 750 wear, 1500 g, 1000 afro,"
      " Телосложение 6 and Стрельба 2, +7 stamina, +1 crit",
      WANT[HELM], dict(armor_class=5, max_break_abs=750, weight=1500, bonus_st=7, bonus_cp=1,
                       cost=1000, g_cost=0, slot_type=0, exchang=1, premium=0,
                       need_attribs_m=4, need_attribs=[6], need_skills_m=2, need_skills=[2]))
check("each piece of clothing on the stall carries its article's (A) column",
      {t: {k: (items.params_of(t).get(k), v) for k, v in WANT[t].items()
           if items.params_of(t).get(k) != v} for t in ARTICLE if
       any(items.params_of(t).get(k) != v for k, v in WANT[t].items())}, {})

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
_store.register("arena", "secret")
_store.close()
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_POLICY_PORT="0", LAVA_GX=str(ARENA_CELL[0]), LAVA_GY=str(ARENA_CELL[1]),
           LAVA_START_AFRO=str(START_AFRO))
for _knob in ("LAVA_LOC", "LAVA_CHEATS"):
    env.pop(_knob, None)
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


def as_list(v):
    """A list field as the decoder leaves it."""
    return list(v) if isinstance(v, list) else ([] if v in (None, "") else [v])


def enter(c, login, first=False):
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


FRAME = {items.FIRE_ARM: "ss_si_firearm", items.AMMO: "ss_si_ammo", items.WEAR: "ss_si_wear",
         items.HEAL: "ss_si_heal"}

try:
    c = Client(connect())
    arrival = enter(c, "arena", first=True)
    stalls = [p for p in named(arrival, "userInfo_Trader") if p.get("res") == SETH]
    check("a newborn at the arena is told of Сет", len(stalls), 1)
    info = stalls[0] if stalls else {}
    check("  ..trading his list, in its order, and mending (the page's «Ремонт»)",
          (as_list(info.get("type_list")), info.get("can_trade"), info.get("can_repair")),
          (STALL, 1, 1))
    npc = info.get("id")

    # What the window asks for each thing on the stall.
    frames = {}
    for t in STALL:
        c.send("ss_get_si;type=%d;" % t)
        cmd = FRAME[items.root_of(t)]
        got = named(c.until(cmd), cmd)
        frames[t] = got[0] if got else {}
    check("every thing on the stall answers its window, under its own name and price",
          {t: (p.get("type"), p.get("name"), p.get("cost"), p.get("g_cost")) for t, p in frames.items()},
          {t: (t, items.STRING_ID_OFFSET + t, items.params_of(t)["cost"], 0) for t in STALL})
    off = {}
    for t in ARTICLE:
        p = frames[t]
        diff = {k: (p.get(k) if not isinstance(v, list) else as_list(p.get(k)), v)
                for k, v in WANT[t].items()
                if (p.get(k) if not isinstance(v, list) else as_list(p.get(k))) != v}
        if diff:
            off[t] = diff
    check("ss_si_wear of each piece of clothing: its article's numbers", off, {})
    check("  ..the helmet in Колонист, the rest too (set_type 11167)",
          {frames[t].get("set_type") for t in ARTICLE}, {11167})
    check("Walther P99: Стрельба 4, 2800 afro", (frames[WALTHER].get("need_skills_m"),
                                               as_list(frames[WALTHER].get("need_skills")),
                                               frames[WALTHER].get("cost")), (2, [4], 2800))

    c.send("ss_create;s_type=1;target=%d;" % npc)
    check("the stall opens", named(c.frames(), "cmdAck"), [{"res": 0}])

    def purse():
        c.send("getInfo;lvl=0;id=0;type=0;")
        return named(c.until("userInfo_Player"), "userInfo_Player")[0]["afro"]

    afro = purse()
    check("the purse starts at LAVA_START_AFRO", afro, START_AFRO)
    bought, charged = {}, {}
    for idx, t in enumerate(STALL):
        n = ROUNDS if items.root_of(t) == items.AMMO else 1
        c.send("ss_upd;param=%d;obj=x%x;s_status=1;" % (n, idx))
        got = c.frames(0.8)
        ack = named(got, "cmdAck")
        new = named(got, "ss_obj_status")
        money = named(got, "userInfo_Player")
        bought[t] = (ack[0].get("res") if ack else None,
                     inventory.parse_oid(str(new[0]["obj"]))[1] if new else None)
        charged[t] = (afro - money[-1]["afro"]) if money else None
        if money:
            afro = money[-1]["afro"]
        if new:
            bought[t] += (str(new[0]["obj"]),)
    check("each thing on the stall bought, at level 0: accepted, and a thing of its type",
          {t: v[:2] for t, v in bought.items()}, {t: (0, t) for t in STALL})
    check("  ..at the price the window shows",
          charged, {t: inventory.buy_price(items.params_of(t), items.root_of(t),
                                           ROUNDS if items.root_of(t) == items.AMMO else 1)
                    for t in STALL})
    check("  ..which is 2800, 20, 60, 600, 800, 400, 1000, 1200, 2500 and 2500 afro", charged, PRICES)
    check("  ..and the purse is short by their sum", (purse(), afro),
          (START_AFRO - sum(PRICES.values()), START_AFRO - sum(PRICES.values())))

    # Bought is not worn: the level rule is the body's and the hand's.
    for label, t, dst in (("the Колонист helmet (2) on the head", HELM, HEAD),
                          ("Walther P99 (4) into the hand", WALTHER, PRIMARY)):
        got = "not bought"
        if len(bought[t]) > 2:
            c.send("ss_move;obj=x%s;to=%d;from=%d;" % (bought[t][2], dst, BAG))
            got = [p.get("res") for p in named(c.frames(0.8), "cmdAck")]
        check("level 0: %s refused with 45" % label, got, [inventory.RES_LEVEL])
    c.send("ss_upd;obj=x0;s_status=0;")
    leave(c)

    st = accounts.Store(DB)
    cid = st.db.execute("SELECT id FROM characters WHERE name = ?", ("arena",)).fetchone()["id"]
    rows = [r for r in st.items_of(cid) if r["slot"] == BAG]
    st.close()
    check("in the database: every thing bought is in the bag, the rounds %d each" % ROUNDS,
          ([t for t in STALL if t not in {r["type_id"] for r in rows}],
           sorted(r["count"] for r in rows if r["type_id"] in (KS, ST))),
          ([], [ROUNDS, ROUNDS]))
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
print("seth stall OK")
