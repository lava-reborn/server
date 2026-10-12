"""Чёрный Ловелас[12] for afro and for gold, at Гали's stall.

The owner's order of 2026-10-13: «поставь ловеласа у Гали и за афро и за
голд». The set was the original's quest series Bs_U_LVL_12, quest types
only (_Q_mod00..mod10), and one type has one currency: the client buys
anything with a g_cost for gold (Trade.buy). So its A is the quest pieces,
priced in afro, and its G five types of our own (data/own_items.json,
own_items.py), which the release's objects.xml carries with the quest
pieces' pictures (client/build.py; client/test_client.py has the release).

In process:
  1. the types: the G is 60000-60004 in the server's catalogue, root and
     slot as the client reads them, each the copy of its quest piece; a
     table of our own types that would clash with the original's is refused;
  2. the prices by the rule the afro ones were designed by (data/sets.json
     _meta): t = 2/3 between Пустынник[10] and Спецназ[13], piece by piece,
     afro to whole thousands and gold to the same grain, 1 000 afro = 0.25 G
     at the wiki's 4 000 : 1 -- which is the A's price at that rate;
  3. the names in the table (names.ALL), as the ladder's A and G read;
  4. the sets: five A one set, five G one set with the same bonus and the
     same figure, and a mix of A and G two sets -- as every rung's A and G,
     which the original named as two sets ([A] and [G] rows of texts.xml);
  5. Гали's stall at Портовый рынок Абри (187): the band's sets, A then G,
     helm to boots, Чёрный Ловелас last.
Then on the wire (server.Session, in process): Гали's window is that stall,
each gold piece is bought for gold and refused for afro, each afro piece for
afro and refused for gold; then the character puts on two afro pieces and
three gold ones, and its card carries what the two sets add, then five gold
ones and the five-piece bonus.

    LAVA_RES=.../lava/res python3 server/test_lovelace.py
"""
import asyncio
import json
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DB = os.path.join(tempfile.mkdtemp(), "lovelace.db")
os.environ["LAVA_DB"] = DB
os.environ["LAVA_CHEATS"] = "1"
for _knob in ("LAVA_LOC", "LAVA_START"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import own_items  # noqa: E402
import sets  # noqa: E402
import setcraft  # noqa: E402
import shop_bands  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

A, G = 11120, 60000                  # the set_types: the quest row, our first piece
DESERT_A, DESERT_G = 11182, 11184    # Пустынник[10]
SPEC_A, SPEC_G = 11206, 11208        # Спецназ[13]
GALI, PORT = 1166, 187               # Гали «Торговец комплектами», Портовый рынок Абри
SLOTS = sets.SLOTS
A_TYPES = [11721, 11722, 11723, 11724, 11725]
G_TYPES = [60000, 60001, 60002, 60003, 60004]
A_PRICES = [42000, 25000, 50000, 33000, 17000]     # afro
G_PRICES = [1050, 625, 1250, 825, 425]             # hundredths of an ounce
WORDS = ["Шлем", "Жилет", "Броня", "Штанишки", "Ботинки"]
cat = items.catalogue()
with open(sets.PATH, encoding="utf-8") as fh:
    RAW = json.load(fh)["sets"]


def half_up(x):
    return int(math.floor(x + 0.5 + 1e-9))


def members(st):
    return [sets.SETS[st]["members"][s] for s in SLOTS]


def price(t):
    p = items.params_of(t)
    return p["cost"], p["g_cost"]


# --- 1. the types ------------------------------------------------------------------------
print("the types")
check("its A: the original's quest pieces, Bs_U_LVL_12 _Q_mod00, in the set of its [Q] row",
      (members(A), [cat[t][1] for t in A_TYPES], sets.SETS[A]["variant"]),
      (A_TYPES, ["%s_Bs_U_LVL_12_Q_mod00" % s for s in SLOTS], "A"))
check("its G: five types of our own in the server's catalogue, clothing, named as the G of"
      " the series, keyed by the first of them",
      (members(G), [cat[t] for t in G_TYPES], [items.own(t) for t in G_TYPES],
       sets.SETS[G]["variant"]),
      (G_TYPES, [(items.WEAR, "%s_Bs_U_LVL_12_G_mod00" % s) for s in SLOTS], [True] * 5, "G"))
check("  ..the original has none of them: its last type is 50 035, and no row named so",
      ([t for t in G_TYPES if t <= 50035],
       [t for t, (_r, n) in cat.items() if "Bs_U_LVL_12_G" in n and not items.own(t)]), ([], []))
check("  ..each the copy of its quest piece: its root and its picture (data/own_items.json)",
      [(own_items.load()[t]["like"], own_items.icon_path(*cat[t])) for t in G_TYPES],
      [(a, "classes/WearItem/%s_Bs_U_LVL_12_G_mod00/ico.swf" % s) for a, s in zip(A_TYPES, SLOTS)])
check("  ..each in its slot, as the client puts it",
      [items.static_info(t)[1]["slot_type"] for t in G_TYPES],
      [items.SLOT_HEAD, items.SLOT_CAMO, items.SLOT_ARMOR, items.SLOT_LEGS, items.SLOT_BOOTS])


def refused(doc, original=None):
    try:
        own_items.rows(original or cat, own_items.parse(doc))
    except own_items.Refused as e:
        return str(e)
    return None


ok = {"60000": {"name": "helm_Bs_U_LVL_12_G_mod00", "like": 11721}}
check("a table of our own types is refused where it would clash with the original's",
      [bool(refused({"items": d})) for d in (
          ok,
          {"11722": {"name": "helm_x", "like": 11721}},          # a type of the original's range
          {"65536": {"name": "helm_x", "like": 11721}},          # past an oid's four hex digits
          {"60000": {"name": "helm_Bs_U_LVL_12_Q_mod00", "like": 11721}},   # the original's name
          {"60000": {"name": "helm x", "like": 11721}},          # no folder name
          {"60000": {"name": "helm_x", "like": 4242424}},        # like no type
          {"60000": {"name": "helm_x", "like": 11721},
           "60001": {"name": "HELM_X", "like": 11722}})],         # one name twice
      [False, True, True, True, True, True, True])
check("  ..and a release's objects.xml, our rows in it, read as the original is ours all the same",
      refused({"items": ok}, dict(cat)), None)
xml = own_items.objects_xml(b"<?xml version='1.0'?>\n<data>\n<object type_id=\"11721\" "
                            b"root_type_id= \"1\" name=\"helm_Bs_U_LVL_12_Q_mod00\" />\n</data>",
                            {60000: (1, "helm_Bs_U_LVL_12_G_mod00")})
check("  ..the row the release writes, in the original's format, once however often it is laid",
      (xml.count(b'<object type_id="60000" root_type_id= "1" name="helm_Bs_U_LVL_12_G_mod00" />'),
       own_items.objects_xml(xml, {60000: (1, "helm_Bs_U_LVL_12_G_mod00")}) == xml), (1, True))

# --- 2. the prices -----------------------------------------------------------------------
print()
print("the prices")
T = 2 / 3.0          # (12 - 10) / (13 - 10)
check("the afro: 42 000, 25 000, 50 000, 33 000, 17 000 -- t = 2/3 between Пустынник and"
      " Спецназ, to whole thousands, as the rule designed them",
      ([price(t) for t in A_TYPES],
       [half_up((price(lo)[0] + (price(hi)[0] - price(lo)[0]) * T) / 1000.0) * 1000
        for lo, hi in zip(members(DESERT_A), members(SPEC_A))]),
      ([(p, 0) for p in A_PRICES], A_PRICES))
check("  ..between their neighbours: Пустынник 25 000 .. 10 000 and Спецназ 50 000 .. 20 000",
      ([price(t)[0] for t in members(DESERT_A)], [price(t)[0] for t in members(SPEC_A)]),
      ([25000, 15000, 30000, 20000, 10000], [50000, 30000, 60000, 40000, 20000]))
raw_g = [price(lo)[1] + (price(hi)[1] - price(lo)[1]) * T
         for lo, hi in zip(members(DESERT_G), members(SPEC_G))]
check("the gold: t = 2/3 between Пустынник (G) and Спецназ (G) -- 10.42, 6.25, 12.50, 8.33,"
      " 4.17 G -- to the grain of the afro, 1 000 afro = 0.25 G: 10.50, 6.25, 12.50, 8.25, 4.25",
      ([round(x) for x in raw_g], [half_up(x / 25.0) * 25 for x in raw_g], [price(t) for t in G_TYPES]),
      ([1042, 625, 1250, 833, 417], G_PRICES, [(0, p) for p in G_PRICES]))
check("  ..which is the A's price at the wiki's 4 000 afro = 1 G, the rule of every designed"
      " rung's G (Дредноут, Паладин)", [a // 40 for a in A_PRICES], G_PRICES)
check("  ..the set: 167 000 afro or 41.75 G, between Пустынник's 100 000 / 25 G and"
      " Спецназ's 200 000 / 50 G",
      (sum(A_PRICES), sum(G_PRICES), sum(price(t)[0] for t in members(DESERT_A)),
       sum(price(t)[1] for t in members(DESERT_G)), sum(price(t)[0] for t in members(SPEC_A)),
       sum(price(t)[1] for t in members(SPEC_G))),
      (167000, 4175, 100000, 2500, 200000, 5000))
check("the G is the A's numbers otherwise: armour, wear, weight, what it asks and adds",
      [t for a, g in zip(A_TYPES, G_TYPES)
       for t in [g] if any(items.params_of(a).get(k) != items.params_of(g).get(k) for k in (
           "armor_class", "max_break_abs", "weight", "bonus_hp", "bonus_st", "bonus_od",
           "bonus_cp", "bonus_ce", "need_attribs_m", "need_attribs", "need_skills_m",
           "need_skills"))], [])
check("  ..the A exchanged, the G not, as every rung's; neither premium nor a quest's",
      [(items.params_of(t)["exchang"], items.params_of(t)["premium"], items.params_of(t)["quest"])
       for t in (A_TYPES[0], G_TYPES[0])], [(1, 0, 0), (0, 0, 0)])
check("  ..Стрельба 12 and Телосложение 13 asked, the level the band reads them at",
      sorted({(inventory.item_level(t), shop_bands.level_of(t)) for t in A_TYPES + G_TYPES}),
      [(12, 12)])

# --- 3. the names ------------------------------------------------------------------------
print()
print("the names")
check("in the table under the item ids: the A plain, the G with (G), as «Шлем пустынника» and"
      " «Шлем пустынника (G)»",
      ([names.text(items.STRING_ID_OFFSET + t) for t in A_TYPES + G_TYPES],
       [names.text(items.STRING_ID_OFFSET + t) for t in (10629, 10649)]),
      (["%s Чёрного Ловеласа" % w for w in WORDS] + ["%s Чёрного Ловеласа (G)" % w for w in WORDS],
       ["Шлем пустынника", "Шлем пустынника (G)"]))
check("  ..over the original's «(Q)» and the internal name",
      (orig_texts.item_names()[11721], 60000 in orig_texts.item_names()),
      ("Шлем Чёрного Ловеласа (Q)", False))
check("  ..and the file writes them as the ladder does: [12][A], [12][G]",
      [RAW[str(st)]["members"]["helm"]["name"] for st in (A, G)],
      ["Шлем Чёрного Ловеласа[12][A]", "Шлем Чёрного Ловеласа[12][G]"])
check("each described by its quest piece's words, the gold one under its own id",
      [names.text(items.static_info(t)[1]["desc"]) for t in (A_TYPES[0], G_TYPES[0])],
      ["Встроен рентген сканер обнажающий натуру противника. Без смсок!"] * 2)
check("the sets: «Чёрный Ловелас» and «Чёрный Ловелас (G)», one description",
      [names.text(sets.NAME_ID_OFFSET + st) for st in (A, G)] + [
          names.text(sets.DESC_ID_OFFSET + G) == names.text(sets.DESC_ID_OFFSET + A)],
      ["Чёрный Ловелас", "Чёрный Ловелас (G)", True])
ids = [items.STRING_ID_OFFSET + t for t in A_TYPES + G_TYPES] \
    + [items.static_info(t)[1]["desc"] for t in A_TYPES + G_TYPES] \
    + [sets.NAME_ID_OFFSET + st for st in (A, G)] + [sets.DESC_ID_OFFSET + st for st in (A, G)]
check("every one of those ids in the preload, its text one the launcher takes",
      [i for i in ids if not names.known(i) or not orig_texts.launcher_ok(names.text(i))], [])

# --- 4. the sets -------------------------------------------------------------------------
print()
print("the sets")


def bonus_of(st, n):
    """What n pieces of a set add by the file's own columns, K by K up to n."""
    out = sets.zero()
    for k, line in RAW[str(st)]["bonus"].items():
        if int(k) > n:
            continue
        one = sets._bonus("t", line)
        for key in sets.SCALARS:
            out[key] += one[key]
        for kind, _t in sets.LISTS:
            out[kind] = [a + b for a, b in zip(out[kind], one[kind])]
    return out


def plus(*bs):
    out = sets.zero()
    for b in bs:
        for key in sets.SCALARS:
            out[key] += b[key]
        for kind, _t in sets.LISTS:
            out[kind] = [a + c for a, c in zip(out[kind], b[kind])]
    return out


check("the gold set adds what the afro one does, K by K: the wiki's one column of «Снаряжение"
      " Чёрного Ловеласа» serves both", sets.frame(G),
      dict(sets.frame(A), type=G, name=sets.NAME_ID_OFFSET + G, desc=sets.DESC_ID_OFFSET + G))
check("  ..five pieces: +200 stamina, +17 crit, Сила 2, Телосложение 3, Восприятие 2, after"
      " 2, 3 and 4 pieces' lines", RAW[str(G)]["bonus"]["5"],
      {"st": 200, "cp": 17, "Сила": 2, "Телосложение": 3, "Восприятие": 2})
check("five A are one set, five G one set, each with its five-piece bonus",
      (sets.pieces(A_TYPES), sets.pieces(G_TYPES), sets.bonuses(A_TYPES), sets.bonuses(G_TYPES)),
      ({A: 5}, {G: 5}, bonus_of(A, 5), bonus_of(G, 5)))
mix = A_TYPES[:2] + G_TYPES[2:]
check("a mix, two A and three G, is two sets: two pieces of the one and three of the other",
      (sets.pieces(mix), sets.bonuses(mix)), ({A: 2, G: 3}, plus(bonus_of(A, 2), bonus_of(G, 3))))
desert = members(DESERT_A)[:2] + members(DESERT_G)[2:]
check("  ..as every rung's A and G (the original's [A] and [G] rows): two of Пустынник and"
      " three of Пустынник (G)", sets.pieces(desert), {DESERT_A: 2, DESERT_G: 3})
check("the figure: res 111 for five of either, the wearer's own for a mix, as for Пустынник",
      (sets.look(A_TYPES), sets.look(G_TYPES), sets.look(mix), sets.look(desert)), (111, 111, 0, 0))
check("not reworked, as while it was a quest set: its A's mods have no pictures, its G has"
      " none (setcraft.NOT_REWORKED); every other rung of the ladder is",
      (sorted(setcraft.NOT_REWORKED), [t for t in A_TYPES + G_TYPES if t in setcraft.CHAINS],
       setcraft.MISSING), (sorted(A_TYPES + G_TYPES), [], []))

# --- 5. Гали's stall ---------------------------------------------------------------------
print()
print("Гали's stall")
stall = items.stock_for(GALI, PORT)
check("Гали at Портовый рынок Абри: Абри's band 8-12, Налетчик, Пустынник and Чёрный Ловелас,"
      " each A then G, helm to boots",
      stall, members(11185) + members(11187) + members(DESERT_A) + members(DESERT_G)
      + A_TYPES + G_TYPES)
check("  ..the last ten: the five afro pieces for afro, then the five gold ones for gold",
      [price(t) for t in stall[-10:]], [(p, 0) for p in A_PRICES] + [(0, p) for p in G_PRICES])
check("  ..the city's band says so on its own (shop_bands.wares): kind, level, slot, currency",
      [shop_bands.ware(t) for t in A_TYPES + G_TYPES],
      [("sets", 12, i, 0) for i in range(5)] + [("sets", 12, i, 1) for i in range(5)])
check("Тёмное Эхо[17], still a quest set, is on no stall of any city",
      sorted({t for st in RAW if RAW[st]["variant"] == "Q" for t in members(int(st))}
             & set(shop_bands.wares())), [])

# --- on the wire -------------------------------------------------------------------------
print()
print("on the wire")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("lovelace", "secret")
_store.close()
CRED = accounts.credential("lovelace", "secret")

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)


class Writer:
    """What Session needs of an asyncio StreamWriter, and a record of it."""

    def __init__(self):
        self.frames = []
        self.read = 0

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        pass

    async def drain(self):
        pass

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, text):
    name, params = decode(text)
    sess.handle(name, params)
    w = sess.writer
    out, w.read = w.frames[w.read:], len(w.frames)
    return out


def of(frames, name):
    return [p for n, p in frames if n == name]


def acks(frames):
    return [p["res"] for n, p in frames if n == "cmdAck"]


def purse(sess):
    return sess.char.afro, sess.char.gold


def rows(sess):
    return server.STORE.items_of(sess.char_id)


def bag(sess):
    return sorted(r["type_id"] for r in rows(sess))


def buy(sess, index, code):
    """One purchase by the window's index: (acks, what came, afro, gold spent)."""
    before, had = purse(sess), bag(sess)
    got = run(sess, "ss_upd;s_status=%d;obj=x%x;param=1;" % (code, index))
    now = bag(sess)
    came = [t for t in set(now) if now.count(t) > had.count(t)]
    return acks(got), came, before[0] - purse(sess)[0], before[1] - purse(sess)[1]


SLOT_OF = dict(zip(SLOTS, (inventory.HEAD, inventory.CAMO, inventory.ARMOR, inventory.LEGS,
                           inventory.BOOTS)))


def wear(sess, type_id, slot):
    r = next(r for r in rows(sess) if r["type_id"] == type_id)
    got = run(sess, "ss_move;obj=x%s;to=%d;from=%d;" % (inventory.oid_of(r), SLOT_OF[slot], r["slot"]))
    return acks(got)


def gear(sess):
    ch = sess.char
    return dict(hp=ch.bonus_hp, st=ch.bonus_st, od=ch.bonus_od, cp=ch.bonus_cp, ce=ch.bonus_ce,
                attribs=list(ch.bonus_attribs))


def want_gear(worn):
    """The pieces' own bonus_* and the sets' columns (bonus_of), by hand."""
    own = sets.zero()
    for t in worn:
        p = items.params_of(t)
        for key in sets.SCALARS:
            own[key] += p.get("bonus_" + key, 0)
    total = plus(own, *[bonus_of(st, n) for st, n in sets.pieces(worn).items()])
    return dict(hp=total["hp"], st=total["st"], od=total["od"], cp=total["cp"], ce=total["ce"],
                attribs=total["attribs"])


async def main():
    sess = server.Session(Writer(), "lovelace")
    run(sess, "hello;minor=2;major=0;")
    run(sess, "login;hash=@%s@;" % CRED)
    run(sess, "newPers;res=1;sex=0;name=@Ловелас@;")
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    run(sess, "userMsg;entry=@/money 300000 10000@;group=0;")
    run(sess, "userMsg;entry=@/skill 1 12@;group=0;")
    run(sess, "userMsg;entry=@/goto %d@;group=0;" % PORT)
    run(sess, "lenter;accept=1;")
    npc = {n.type_id: eid for eid, n in sess.room.npcs.items()}.get(GALI)
    check("Гали stands at Портовый рынок Абри", npc is not None, True)
    info = of(run(sess, "getInfo;lvl=0;id=%d;type=0;" % npc), "userInfo_Trader")
    window = list(info[0]["type_list"]) if info else []
    check("  ..his window is his stall there, the thirty", (window == stall, len(window)), (True, 30))
    si = {p["type"]: p for t in (A_TYPES[0], G_TYPES[0])
          for p in of(run(sess, "ss_get_si;type=%d;" % t), "ss_si_wear")}
    check("ss_get_si: the gold helmet's frame, a piece of the set 60000 for 10.50 ounces alone,"
          " the afro one's of 11120 for 42 000",
          [(si[t]["set_type"], si[t]["cost"], si[t]["g_cost"], names.known(si[t]["name"]))
           for t in (A_TYPES[0], G_TYPES[0])], [(A, 42000, 0, True), (G, 0, 1050, True)])
    s_si = {p["type"]: p for st in (A, G) for p in of(run(sess, "ss_get_s_si;type=%d;" % st),
                                                       "ss_si_set")}
    check("ss_get_s_si: the two sets' frames, figure 111", (s_si[A]["res"], s_si[G]["res"],
                                                             s_si[G]["name"]), (111, 111, 7060000))
    check("the stall opens: one ack", acks(run(sess, "ss_create;s_type=1;target=%d;" % npc)), [0])
    at = {t: window.index(t) for t in A_TYPES + G_TYPES}
    start = purse(sess)
    check("each gold piece for afro: refused, nothing taken, nothing given",
          [buy(sess, at[t], inventory.UPD_BUY) for t in G_TYPES],
          [([inventory.RES_REFUSED], [], 0, 0)] * 5)
    check("each afro piece for gold: refused, nothing taken, nothing given",
          [buy(sess, at[t], inventory.UPD_BUY_GOLD) for t in A_TYPES],
          [([inventory.RES_REFUSED], [], 0, 0)] * 5)
    check("each gold piece for gold: one ack, the piece, its price in hundredths of an ounce,"
          " no afro", [buy(sess, at[t], inventory.UPD_BUY_GOLD) for t in G_TYPES],
          [([0], [t], 0, p) for t, p in zip(G_TYPES, G_PRICES)])
    check("each afro piece for afro: one ack, the piece, its price, no gold",
          [buy(sess, at[t], inventory.UPD_BUY) for t in A_TYPES],
          [([0], [t], p, 0) for t, p in zip(A_TYPES, A_PRICES)])
    check("  ..the purse: 167 000 afro and 41.75 ounces less, the set's two prices",
          (start[0] - purse(sess)[0], start[1] - purse(sess)[1]), (167000, 4175))
    run(sess, "ss_upd;s_status=0;obj=x0;param=1;")

    check("the character, Стрельба 12, puts on the afro helmet and vest and the gold armour,"
          " trousers and boots: accepted, each",
          [wear(sess, t, s) for t, s in zip(A_TYPES[:2] + G_TYPES[2:], SLOTS)], [[0]] * 5)
    check("  ..its card: the pieces' own and two sets' -- two of the afro, three of the gold",
          gear(sess), want_gear(A_TYPES[:2] + G_TYPES[2:]))
    check("  ..which is more than five pieces of no set would give: +20 action points, Ловкость 1",
          (gear(sess)["od"] - sum(items.params_of(t)["bonus_od"] for t in mix),
           gear(sess)["attribs"]), (20, [0, 1, 0, 0, 0]))
    check("the gold helmet and vest in their place: accepted",
          [wear(sess, t, s) for t, s in zip(G_TYPES[:2], SLOTS)], [[0], [0]])
    check("  ..five of the gold set: the five-piece bonus on the card",
          gear(sess), want_gear(G_TYPES))
    check("  ..Сила 2, Ловкость 1, Телосложение 3, Восприятие 2, Интеллект 1 of it",
          gear(sess)["attribs"], [2, 1, 3, 2, 1])
    worn = {r["slot"]: r["type_id"] for r in rows(sess) if r["slot"] in inventory.SET_SLOTS}
    check("  ..and the figure the set draws: 111", sets.look([worn.get(s) for s in inventory.SET_SLOTS]),
          111)


try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("the wire broke:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("lovelace OK")
